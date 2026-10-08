"""Synthetic attacks plus read-only deterministic replay of pinned G2 captures."""
from copy import deepcopy
import inspect
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from overnight.data import dataset as data
from overnight.data.coverage import analyze_coverage
from overnight.data import __main__ as sink

NOW = "2026-10-05T18:00:00.000000Z"
UNITS = {"daily": {k: "SYNTHETIC_UNIT_REFERENCE_ONLY" for k in ("open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount")},
         "adj_factor": {"adj_factor": "DIMENSIONLESS_FACTOR"}, "fina_indicator": {k: "UNKNOWN_UNVERIFIED" for k in ("eps", "roe", "debt_to_assets", "netprofit_yoy")}}

def fixture(api="daily", rows=None, symbol=data.SYMBOLS[0], *, blocked=False, scope="SMOKE"):
    fields = list(data.FIELDS[api])
    defaults = {k: None for k in fields}
    defaults.update(ts_code=symbol, symbol=symbol[:6], name="SYNTHETIC_SECURITY", exchange="SSE", curr_type="CNY", list_status="L",
        list_date="20000101", cal_date="20250602", is_open=1, pretrade_date="20250530", trade_date="20250602",
        open="10", high="11", low="9", close="10", pre_close="10", change="0", pct_chg="0", vol="100", amount="100",
        adj_factor="1", end_date="20260630", ann_date="20260930", eps="0.123456789012345678901", roe="1", debt_to_assets="1", netprofit_yoy="1", update_flag="1", in_date="20250101", out_date="", is_new="Y")
    source_rows = [defaults] if rows is None else [{**defaults, **r} for r in rows]
    raw = json.dumps({"code": 0, "data": {"fields": fields, "items": [[r[k] for k in fields] for r in source_rows]}}).encode()
    request = {"request_id": "synthetic-" + api + "-" + symbol, "request_fingerprint": data.sha((api + symbol).encode()),
        "api_name": api, "category": "SYNTHETIC", "scope": scope, "fields": fields, "max_rows": 16,
        "params": {"exchange": "SSE"} if api == "trade_cal" else {"ts_code": symbol}, "units": UNITS.get(api, {}),
        "price_adjustment": "RAW_UNADJUSTED_OHLC_PROVIDER_PRE_CLOSE_EX_RIGHTS" if api == "daily" else "FACTOR_ONLY_NO_ADJUSTED_PRICES" if api == "adj_factor" else "NOT_APPLICABLE",
        "date_scope": {"key": "cal_date" if api == "trade_cal" else "trade_date", "start": "20250601", "end": "20250603"},
        "request_started_at": NOW, "response_completed_at": NOW, "retrieved_at": NOW, "available_at": NOW,
        "published_at": None, "raw_sha256": data.sha(raw), "dq_status": "BLOCKED" if blocked else "PASS", "dq_reasons": ["SYNTHETIC_RESPONSE_BLOCKED"] if blocked else []}
    report = {"generated_at": NOW, "completed_at": NOW, "namespace": "CORE_40"}
    return request, raw, report

def normalized(api="daily", rows=None, symbol=data.SYMBOLS[0], **kwargs):
    return data.normalize_fixture_request(*fixture(api, rows, symbol, **kwargs))["requests"][0]

def complete_fixture():
    requests = [normalized("trade_cal", [{"cal_date": "20250601", "is_open": 0}, {"cal_date": "20250602", "is_open": 1}, {"cal_date": "20250603", "is_open": 1}])]
    for symbol in data.SYMBOLS:
        requests += [normalized("stock_basic", symbol=symbol), normalized("daily", [{"trade_date": "20250602"}, {"trade_date": "20250603"}], symbol),
                     normalized("adj_factor", [{"trade_date": "20250602"}, {"trade_date": "20250603"}], symbol), normalized("suspend_d", [], symbol)]
    return data.fixture_dataset(requests)

class DataTests(unittest.TestCase):
    def reason(self, reason, operation):
        with self.assertRaises(data.DataError) as raised: operation()
        self.assertEqual(str(raised.exception), reason)

    def test_embedded_percent_encoded_paths_and_generic_credentials_rejected(self):
        for value in ('x=/Users/synthetic-review/private.txt', 'prefix file:///tmp/synthetic',
                      'x=%2FUsers%2Fsynthetic%2Fprivate.txt', 'x=%252FUsers%252Fsynthetic%252Fprivate.txt',
                      'x=C:\\synthetic\\private.txt', 'postgres://synthetic/private'):
            q, raw, report = fixture('stock_basic', [{'name': value}])
            self.reason('INTERNAL_PATH_IN_ROW', lambda: data.normalize_fixture_request(q, raw, report))
        for value in ('Bearer SYNTHETIC_REVIEW_ONLY', 'sk-' + 'SYNTHETIC_ONLY_' * 3, 'token=SYNTHETIC_ONLY',
                      'password%3DSYNTHETIC_ONLY', 'api_key=SYNTHETIC_ONLY', 'a' * 40):
            q, raw, report = fixture('stock_basic', [{'name': value}])
            self.reason('SECRET_PATTERN_IN_ROW', lambda: data.normalize_fixture_request(q, raw, report))

    def test_pinned_real_replay_deterministic_44_requests_2786_rows_all_quarantine(self):
        first, second = data.load_verified_dataset(), data.load_verified_dataset()
        self.assertEqual(data.canonical(first), data.canonical(second))
        self.assertEqual(len(first["requests"]), 44)
        self.assertEqual(sum(len(r["rows"]) for r in first["requests"]), 2786)
        self.assertTrue(all(r["state"] == "QUARANTINED" for q in first["requests"] for r in q["rows"]))
        self.assertEqual(len(first["source_pins"]), 12)
        for q in first["requests"]:
            self.assertEqual(q["retrieved_at"], q["response_completed_at"])
            self.assertEqual(q["available_at"], q["response_completed_at"])
            self.assertIsNone(q["published_at"])
            self.assertNotIn("/Users/", data.canonical(q["rows"]).decode())

    def test_pinned_real_coverage_327_sessions_and_existing_13_3_references(self):
        result = analyze_coverage(data.load_verified_dataset())
        self.assertFalse(result["fixture"])
        self.assertEqual(result["calendar"]["open_sessions"], 327)
        self.assertEqual(result["calendar"]["rows"], 492)
        self.assertEqual(result["diagnostic_result"], "PASS_BOUNDED_ENGINEERING_ONLY")
        for row in result["symbols"].values():
            self.assertEqual(row["bars"], 327)
            self.assertTrue(row["factor_date_alignment"])
            self.assertEqual(row["suspension_status"], "EMPTY_RESPONSE_STATUS_UNKNOWN")
            self.assertFalse(row["empty_suspension_means_no_suspension"])
            self.assertFalse(row["gateway_unit_identity_verified"])
        comparison = result["existing_sse_reference_comparison"]
        self.assertEqual(len(comparison["calendar"]), 13)
        self.assertEqual(len(comparison["security"]), 3)
        self.assertEqual(comparison["numeric_second_source"], "NOT_AVAILABLE_NOT_COMPARABLE")
        self.assertEqual(result["source_admission"], "BLOCKED")

    def test_loader_has_no_caller_roots_clock_or_source_authority(self):
        self.assertEqual(list(inspect.signature(data.load_verified_dataset).parameters), [])
        for key in ("root", "clock", "report", "source_admission"):
            with self.assertRaises(TypeError): data.load_verified_dataset(**{key: "forged"})

    def test_pin_mutation_blocked_without_writing_original_file(self):
        original = Path.read_bytes
        target = data.ROOT / "docs/p1b-real-admission/Gate.json"
        def changed(path):
            raw = original(path)
            return raw + b" " if path == target else raw
        with patch.object(Path, "read_bytes", changed):
            self.reason("PINNED_INPUT_MUTATED", data.load_verified_dataset)

    def test_real_dataset_clone_mutation_and_production_escalation_blocked(self):
        real = data.load_verified_dataset()
        self.reason("REAL_DATASET_UNREGISTERED_OR_MUTATED", lambda: analyze_coverage(deepcopy(real)))
        real["requests"][0]["available_at"] = "2000-01-01T00:00:00Z"
        self.reason("REAL_DATASET_UNREGISTERED_OR_MUTATED", lambda: analyze_coverage(real))
        fake = complete_fixture(); fake["productionGate"] = True
        self.reason("DATASET_AUTHORITY_ESCALATION", lambda: analyze_coverage(fake))

    def test_raw_mutation_namespace_symbol_and_unexpected_field_rejected(self):
        q, raw, report = fixture()
        self.reason("RAW_MUTATED", lambda: data.normalize_fixture_request(q, raw + b" ", report))
        for namespace in ("EVENT_3", "RESEARCH_6_18M"):
            self.reason("NAMESPACE_CROSSOVER", lambda: data.normalize_fixture_request(q, raw, {**report, "namespace": namespace}))
        source = json.loads(raw); source["data"]["items"][0][0] = "600312.SH"
        changed = json.dumps(source).encode(); q["raw_sha256"] = data.sha(changed)
        self.reason("SYMBOL_CROSSOVER", lambda: data.normalize_fixture_request(q, changed, report))
        q, raw, report = fixture(); q["fields"].append("token")
        self.reason("REQUEST_FIELDS_INVALID", lambda: data.normalize_fixture_request(q, raw, report))

    def test_decimal_json_literal_keeps_every_digit_and_unknown_unit_unverified(self):
        q, raw, report = fixture()
        literal = "10.12345678901234567890123456789"
        raw = raw.replace(b'"10"', literal.encode(), 1); q["raw_sha256"] = data.sha(raw)
        q["units"] = {}
        row = data.normalize_fixture_request(q, raw, report)["requests"][0]["rows"][0]
        self.assertEqual(row["typed_fields"]["open"]["value"], literal)
        self.assertEqual(row["typed_fields"]["open"]["unit_basis"], "UNKNOWN_UNVERIFIED")
        self.assertEqual(row["typed_fields"]["open"]["kind"], "DECIMAL_STRING")
        self.reason("DECIMAL_INVALID", lambda: data._number(float("1.1")))
        self.reason("DECIMAL_INVALID", lambda: data._number("NaN"))

    def test_available_at_backdate_future_capture_and_midnight_publication_spoof(self):
        for change, expected in (({"available_at": "2020-01-01T00:00:00Z"}, "HISTORICAL_CLOCK_SPOOF"),
            ({"response_completed_at": "2050-01-01T00:00:00Z"}, "CLOCK_OUTSIDE_REPORT_OR_REVERSED"),
            ({"published_at": "2026-09-30T00:00:00Z"}, "DATE_ONLY_MIDNIGHT_SPOOF"),
            ({"retrieved_at": "2026-10-05"}, "HISTORICAL_CLOCK_SPOOF")):
            q, raw, report = fixture(); q.update(change)
            self.reason(expected, lambda: data.normalize_fixture_request(q, raw, report))

    def test_future_publication_preserved_as_invalid_quarantine_not_pit_or_subset(self):
        q, raw, report = fixture("fina_indicator", [{"ann_date": "20261007"}, {"ann_date": "20260930"}], blocked=True)
        result = data.normalize_fixture_request(q, raw, report)
        rows = result["requests"][0]["rows"]
        self.assertEqual(rows[0]["normalization_reasons"], ["FUTURE_PUBLICATION_DATE:ann_date"])
        self.assertEqual(rows[0]["typed_fields"]["ann_date"]["precision"], "DATE_ONLY")
        self.assertTrue(all(r["response_blocked"] for r in rows))
        self.assertTrue(result["fixture"])
        self.assertEqual(result["provenance"], "SYNTHETIC")

    def test_publication_date_uses_shanghai_day_without_fabricated_midnight(self):
        # At 18:00Z Shanghai is already Oct 6; this day is not future evidence.
        q, raw, report = fixture("fina_indicator", [{"ann_date": "20261006"}], blocked=True)
        normalized = data.normalize_fixture_request(q, raw, report)["requests"][0]
        self.assertEqual(normalized["rows"][0]["normalization_reasons"], [])
        self.assertIsNone(normalized["published_at"])
        self.assertEqual(normalized["available_at"], NOW)

    def test_blank_industry_date_and_real_financial_blocked_response_preserved_whole(self):
        real = data.load_verified_dataset()
        industry = [q for q in real["requests"] if q["api_name"] == "index_member_all"]
        self.assertEqual(len(industry), 6)
        for q in industry:
            cell = q["rows"][0]["typed_fields"]["out_date"]
            self.assertEqual(cell["kind"], "INVALID_DATE_LITERAL")
            self.assertEqual(cell["value"], "")
            self.assertTrue(q["rows"][0]["response_blocked"])
        bad_financial = [q for q in real["requests"] if q["api_name"] == "fina_indicator" and q["response_dq"] == "BLOCKED"]
        self.assertTrue(bad_financial)
        self.assertTrue(all(row["response_blocked"] and row["state"] == "QUARANTINED" for q in bad_financial for row in q["rows"]))

    def test_raw_adjusted_factor_separation_cannot_be_renamed(self):
        for api in ("daily", "adj_factor"):
            q, raw, report = fixture(api); q["price_adjustment"] = "ADJUSTED"
            self.reason("RAW_ADJUSTED_CONTAMINATION", lambda: data.normalize_fixture_request(q, raw, report))

    def test_fixture_diagnostics_pass_without_source_promotion_or_weekday_inference(self):
        result = analyze_coverage(complete_fixture())
        self.assertTrue(result["fixture"])
        self.assertEqual(result["diagnostic_result"], "PASS_BOUNDED_ENGINEERING_ONLY")
        self.assertFalse(result["calendar"]["weekday_inference_used"])
        self.assertEqual(result["source_admission"], "BLOCKED")
        self.assertFalse(result["historical_visibility_proven"])

    def test_missing_bar_not_excused_by_empty_suspension_and_duplicate_not_deduped(self):
        missing = complete_fixture()
        bars = next(r for r in missing["requests"] if r["api_name"] == "daily")
        bars["rows"].pop()
        result = analyze_coverage(missing)["symbols"][data.SYMBOLS[0]]
        self.assertEqual(result["calendar_missing_bar_sessions"], ["20250603"])
        self.assertEqual(result["gap_classification"], "UNEXPLAINED_SUSPENSION_STATUS_UNKNOWN")
        duplicate = complete_fixture()
        bars = next(r for r in duplicate["requests"] if r["api_name"] == "daily")
        bars["rows"].append(deepcopy(bars["rows"][0]))
        result = analyze_coverage(duplicate)
        self.assertEqual(result["symbols"][data.SYMBOLS[0]]["duplicates"], ["20250602"])
        self.assertEqual(result["diagnostic_result"], "GAPS_OR_INVALID_OBSERVATIONS")

    def test_calendar_hole_remains_unknown_and_previous_date_invalid(self):
        missing = complete_fixture(); missing["requests"][0]["rows"].pop(0)
        result = analyze_coverage(missing)
        self.assertEqual(result["calendar"]["civil_date_holes"], ["20250601"])
        self.assertIsNone(result["symbols"][data.SYMBOLS[0]]["calendar_missing_bar_sessions"])
        bad = complete_fixture(); bad["requests"][0]["rows"][0]["typed_fields"]["pretrade_date"]["value"] = "20250601"
        self.assertFalse(analyze_coverage(bad)["calendar"]["complete_bounded_calendar"])

    def test_absent_calendar_cannot_produce_engineering_pass(self):
        missing = complete_fixture(); missing["requests"].pop(0)
        result = analyze_coverage(missing)
        self.assertFalse(result["calendar"]["complete_bounded_calendar"])
        self.assertEqual(result["diagnostic_result"], "GAPS_OR_INVALID_OBSERVATIONS")

    def test_factor_date_misalignment_invalid_ohlc_negative_amount_and_prec_close(self):
        bad = complete_fixture()
        factor = next(r for r in bad["requests"] if r["api_name"] == "adj_factor")
        factor["rows"][0]["typed_fields"]["trade_date"]["value"] = "20250601"
        self.assertFalse(analyze_coverage(bad)["symbols"][data.SYMBOLS[0]]["factor_date_alignment"])
        for field, invalid in (("high", "1"), ("amount", "-1"), ("pre_close", "0")):
            bad = complete_fixture(); bars = next(r for r in bad["requests"] if r["api_name"] == "daily")
            bars["rows"][0]["typed_fields"][field]["value"] = invalid
            self.assertTrue(analyze_coverage(bad)["symbols"][data.SYMBOLS[0]]["invalid_bars"])

    def test_prec_close_reference_discontinuity_is_action_question_not_price_adjustment(self):
        changed = complete_fixture(); bars = next(r for r in changed["requests"] if r["api_name"] == "daily")
        bars["rows"][1]["typed_fields"]["pre_close"]["value"] = "9.9"
        result = analyze_coverage(changed)["symbols"][data.SYMBOLS[0]]
        self.assertEqual(len(result["pre_close_reference_discontinuities"]), 1)
        self.assertFalse(result["pre_close_equals_prior_raw_close_required"])
        self.assertEqual(result["invalid_bars"], [])

    def test_security_identity_currency_or_status_history_not_guessed(self):
        bad = complete_fixture(); security = next(r for r in bad["requests"] if r["api_name"] == "stock_basic")
        security["rows"][0]["typed_fields"]["curr_type"]["value"] = "USD"
        result = analyze_coverage(bad)["symbols"][data.SYMBOLS[0]]
        self.assertFalse(result["security_identity_valid_for_observed_row"])
        self.assertEqual(result["security_status_history"], "UNPROVEN_CURRENT_ONLY")

    def test_internal_path_source_string_cannot_enter_row_artifact(self):
        q, raw, report = fixture("stock_basic", [{"name": "/Users/private/secret.txt"}])
        self.reason("INTERNAL_PATH_IN_ROW", lambda: data.normalize_fixture_request(q, raw, report))

    def test_output_sink_0600_exclusive_parent_symlink_and_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve(); target = base / "private" / "fixture.json"
            sink.exclusive_write(target, b"SYNTHETIC_NON_SECRET_BYTES")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.reason("OUTPUT_EXISTS_NO_OVERWRITE", lambda: sink.exclusive_write(target, b"replacement"))
            (base / "link").symlink_to(base / "private", target_is_directory=True)
            self.reason("OUTPUT_SYMLINK_OR_DIRECTORY_INVALID", lambda: sink.exclusive_write(base / "link" / "next.json", b"fixture"))
            self.reason("OUTPUT_PATH_INVALID", lambda: sink.exclusive_write(base / ".." / "escape.json", b"fixture"))

    def test_fixture_or_mutated_coverage_cannot_persist_as_actual_output(self):
        fixture_data = complete_fixture(); coverage = analyze_coverage(fixture_data)
        self.reason("FIXTURE_REAL_OUTPUT_BLOCKED", lambda: sink.write_outputs(fixture_data, coverage, "fixture-test"))
        real = data.load_verified_dataset(); coverage = analyze_coverage(real); coverage["productionGate"] = True
        self.reason("COVERAGE_MUTATED", lambda: sink.write_outputs(real, coverage, "never-persisted-test"))

if __name__ == "__main__": unittest.main()
