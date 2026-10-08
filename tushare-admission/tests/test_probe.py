"""Synthetic adversarial fixtures only. No account, licensed rows or real default fees."""
import base64
import dataclasses
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal

MODULE_PATH = Path(__file__).resolve().parents[1] / "probe.py"
spec = importlib.util.spec_from_file_location("tushare_diagnostic_probe", MODULE_PATH)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)

# A non-secret illustrative sentinel, confined to clearly marked synthetic test code.
SYNTHETIC_SENTINEL = "SYNTHETIC_NON_SECRET_123456789"
NOW = "2026-10-05T14:00:00.123456Z"


def request(api="daily", symbol="603993.SH"):
    return next(item for item in probe.build_plan()
                if item.api_name == api and dict(item.params).get("ts_code", symbol) == symbol)


def response(spec, rows=1, **overrides):
    values = {name: None for name in spec.fields}
    values.update(ts_code="603993.SH", trade_date="20260930", exchange="SSE", cal_date="20260930",
                  is_open="1", pretrade_date="20260929", close="12.000001",
                  end_date="20260630", ann_date="20260830", f_ann_date="20260830",
                  is_new="Y", update_flag="1", report_type="1")
    values.update(overrides)
    obj = {"code": 0, "msg": "", "data": {"fields": list(spec.fields),
           "items": [[values[name] for name in spec.fields] for _ in range(rows)]}}
    return json.dumps(obj).encode("utf-8")


class FakeClock:
    def __init__(self):
        self.elapsed = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.elapsed

    def sleep(self, delay):
        self.sleeps.append(delay)
        self.elapsed += delay


class DiagnosticTests(unittest.TestCase):
    def assert_reason(self, reason, callback):
        with self.assertRaises(probe.ProbeError) as error:
            callback()
        self.assertEqual(str(error.exception), reason)

    def test_named_credential_absence_blocks_before_network_or_transport_construction(self):
        secret, lookup = probe._read_synthetic_named_storage(environ={"TUSHARE_TOKEN": SYNTHETIC_SENTINEL})
        self.assertIsNone(secret)  # no default credential fallback
        with patch.object(probe, "make_transport", side_effect=AssertionError("NO_NETWORK")):
            report = probe.run_probe(credential=secret, lookup_result=lookup, clock=lambda: NOW)
        self.assertEqual(report["network_requests"], 0)
        self.assertEqual(len(report["requests"]), 34)
        self.assertEqual(len(report["categories"]), 8)
        self.assertTrue(all(r["row_count"] is None and r["retrieved_at"] is None for r in report["requests"]))
        self.assertEqual(report["actual_account_tier"], 15000)
        self.assertEqual(report["account_tier_evidence"], "OWNER_ASSERTION_NOT_PROVIDER_ACCOUNT_VERIFIED")

    def test_valid_env_lookup_has_no_credential_or_reversible_representation(self):
        secret, lookup = probe._read_synthetic_named_storage(environ={probe.ENV_NAME: SYNTHETIC_SENTINEL})
        self.assertEqual(lookup["credential_lookup_result"], "FOUND")
        self.assertNotIn(SYNTHETIC_SENTINEL, repr(secret) + str(secret) + json.dumps(lookup))
        self.assertNotIn(base64.b64encode(SYNTHETIC_SENTINEL.encode()).decode(), json.dumps(lookup))

    def test_keychain_requires_exact_explicit_reference_no_scan(self):
        calls = []
        def lookup(args, **kwargs):
            calls.append(args)
            return type("Result", (), {"returncode": 0, "stdout": (SYNTHETIC_SENTINEL + "\n").encode()})()
        secret, result = probe._read_synthetic_named_storage(environ={}, keychain_service="synthetic.test.service",
              keychain_account="synthetic.test.account", keychain_runner=lookup)
        self.assertIsInstance(secret, probe.Credential)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], ["/usr/bin/security", "find-generic-password", "-s", "synthetic.test.service",
                                   "-a", "synthetic.test.account", "-w"])
        self.assertNotIn("synthetic.test.service", json.dumps(result))
        bad, result = probe._read_synthetic_named_storage(environ={}, keychain_service="only.service", keychain_runner=lookup)
        self.assertIsNone(bad)
        self.assertEqual(len(calls), 1)

    def test_keychain_errors_and_stderr_never_reach_diagnostic(self):
        def failure(*args, **kwargs):
            raise RuntimeError(SYNTHETIC_SENTINEL)
        secret, result = probe._read_synthetic_named_storage(environ={}, keychain_service="test.service", keychain_account="test.account", keychain_runner=failure)
        self.assertIsNone(secret)
        self.assertNotIn(SYNTHETIC_SENTINEL, json.dumps(result))
        self.assertEqual(result["credential_lookup_result"], "KEYCHAIN_LOOKUP_FAILED")

    def test_invalid_credential_format_is_not_reported_as_presence(self):
        secret, result = probe._read_synthetic_named_storage(environ={probe.ENV_NAME: "url?token=bad"})
        self.assertIsNone(secret)
        self.assertFalse(result["secret_presence"])

    def test_plan_is_three_stocks_finite_documented_filters_only(self):
        plan = probe.build_plan()
        self.assertEqual(len(plan), 34)
        self.assertEqual({dict(s.params)["ts_code"] for s in plan if "ts_code" in dict(s.params)}, set(probe.SYMBOLS))
        self.assertFalse(any("limit" in dict(s.params) for s in plan))  # no undocumented parameter relied on
        self.assertEqual(dict(request("dividend").params), {"ts_code": "603993.SH", "ann_date": "20260930"})
        self.assertEqual(dict(request("income").params)["period"], "20260630")

    def test_wrong_stock_full_market_or_date_widening_rejected_pre_network(self):
        original = request()
        changes = [dataclasses.replace(original, params=(("ts_code", "000001.SZ"),)),
                   dataclasses.replace(original, params=()),
                   dataclasses.replace(original, date_start="20200101"),
                   dataclasses.replace(original, api_name="daily_vip"),
                   dataclasses.replace(original, fields=original.fields + ("token",))]
        for altered in changes:
            with self.subTest(altered=altered.api_name):
                self.assert_reason("UNAPPROVED_REQUEST_SCOPE", lambda: probe.run_synthetic_probe(plan=(altered,), transport=lambda *_: self.fail("NETWORK")))

    def test_request_subclass_and_atom_equality_overrides_do_not_bypass_allowlist(self):
        class ForgedSpec(probe.RequestSpec):
            def __eq__(self, other): return True
            def __ne__(self, other): return False
        original = request()
        altered = ForgedSpec(**{**dataclasses.asdict(original), "api_name": "p_delete"})
        self.assert_reason("UNAPPROVED_REQUEST_SCOPE", lambda: probe.validate_plan([altered]))
        class ForgedTuple(tuple):
            def __eq__(self, other): return True
            def __ne__(self, other): return False
        altered = dataclasses.replace(original, params=ForgedTuple((("ts_code", "000001.SZ"),)))
        self.assert_reason("UNAPPROVED_REQUEST_SCOPE", lambda: probe.validate_plan([altered]))

    def test_credential_subclass_cannot_replace_wire_or_echo_checker(self):
        class ForgedCredential(probe.Credential):
            def body_contains_secret(self, body): return False
            def _wire_value(self): return "DIFFERENT_SYNTHETIC_VALUE"
        altered = ForgedCredential(SYNTHETIC_SENTINEL)
        self.assert_reason("CREDENTIAL_TYPE_INVALID", lambda: probe.run_synthetic_probe(
            plan=[request()], credential=altered, transport=lambda *_: self.fail("MOCK_SEND")))
        self.assert_reason("CREDENTIAL_TYPE_INVALID", lambda: probe.summarize_response(
            request(), response(request()), credential=altered))
        public = probe.run_probe(credential=altered, transport=lambda *_: self.fail("NO_NETWORK"))
        self.assertEqual(public["network_requests"], 0)

    def test_public_probe_ignores_caller_clock_metadata_injection(self):
        report = probe.run_probe(plan=[], clock=lambda: SYNTHETIC_SENTINEL)
        self.assertNotIn(SYNTHETIC_SENTINEL, json.dumps(report))
        self.assertIsNotNone(probe._validate_clock(report["generated_at"]))
        self.assertIsNotNone(probe._validate_clock(report["completed_at"]))

    def test_synthetic_invalid_clock_rejected_before_register_or_write(self):
        invalid = (SYNTHETIC_SENTINEL, "2026-10-05", "2026-10-05T12:00:00",
                   "2026-02-30T12:00:00Z", "2026-10-05T25:00:00Z", "2026-10-05T12:00:60Z")
        for value in invalid:
            previous = len(probe._sealed_reports)
            self.assert_reason("CLOCK_INVALID", lambda: probe.run_synthetic_probe(
                plan=[], transport=lambda *_: self.fail("NO_MOCK_SEND"), clock=lambda: value))
            self.assertEqual(len(probe._sealed_reports), previous)

    def test_pure_summary_invalid_naive_retrieval_clock_fails_controlled(self):
        for value in (SYNTHETIC_SENTINEL, "2026-10-05", "2026-10-05T12:00:00"):
            self.assert_reason("CLOCK_INVALID", lambda: probe.summarize_response(
                request("income"), response(request("income")), retrieved_at=value))

    def test_duplicate_requests_and_over_budget_are_blocked(self):
        self.assert_reason("DUPLICATE_REQUEST", lambda: probe.validate_plan([request(), request()]))
        self.assert_reason("REQUEST_BUDGET_EXCEEDED", lambda: probe.validate_plan([request()] * 35))

    def test_authenticated_redirect_fails_without_receiving_location_or_retry(self):
        handler = probe._NoRedirect()
        self.assert_reason("AUTH_REDIRECT_BLOCKED", lambda: handler.redirect_request(None, None, 302, "",
              {"Location": "https://other.test/?token=" + SYNTHETIC_SENTINEL}, "https://other.test"))

    def test_current_transport_gate_blocks_before_environment_keychain_or_network(self):
        class NeverRead(dict):
            def get(self, *_): raise AssertionError("CREDENTIAL_LOOKUP")
        def forbidden(*_args, **_kwargs): self.fail("KEYCHAIN_OR_NETWORK")
        secret, lookup = probe.lookup_credential(environ=NeverRead(), keychain_service="test.service",
                 keychain_account="test.account", keychain_runner=forbidden)
        self.assertIsNone(secret)
        self.assertIsNone(lookup["secret_presence"])
        self.assertEqual(lookup["credential_storage"], "NOT_ACCESSED")
        with patch.object(probe.urllib.request, "build_opener", side_effect=AssertionError("NO_NETWORK")):
            self.assert_reason("TRANSPORT_GATE_UNVERIFIED", probe.make_transport)
            report = probe.run_probe(credential=probe.Credential(SYNTHETIC_SENTINEL), transport=forbidden)
        self.assertEqual(report["network_requests"], 0)
        self.assertEqual(report["credential_rotation_gate"], "NEW_CREDENTIAL_REQUIRED")
        self.assertEqual(report["old_credential_use"], "PROHIBITED")
        self.assertEqual(report["provider_id"], "TUSHARE_MONTHLY_GATEWAY")
        self.assertEqual(sum(s["phase"] == "A" for s in report["requests"]), 16)
        self.assertEqual(sum(s["phase"] == "B" for s in report["requests"]), 18)
        self.assertTrue(all(s["reason_code"] == "PHASE_A_NOT_PASSED" for s in report["requests"] if s["phase"] == "B"))

    def test_empty_success_is_distinct_from_denial(self):
        item = request()
        empty = probe.summarize_response(item, response(item, rows=0))
        self.assertEqual(empty["status"], "EMPTY_RESPONSE_NOT_COVERAGE")
        self.assertEqual(empty["row_count"], 0)
        denial = probe.summarize_response(item, b'{"code":-2002,"msg":"permission not granted","data":null}')
        self.assertEqual(denial["status"], "ENTITLEMENT_NOT_GRANTED")
        self.assertIsNone(denial["row_count"])
        self.assertIsNone(denial["source_response_hash"])

    def test_empty_response_without_fields_is_empty_not_entitlement_grant(self):
        empty = probe.summarize_response(request(), b'{"code":0,"msg":"","data":{"fields":[],"items":[]}}')
        self.assertEqual(empty["status"], "EMPTY_RESPONSE_NOT_COVERAGE")
        self.assertEqual(empty["response_schema"], [])

    def test_arbitrary_error_message_never_saved_or_hashed(self):
        raw = json.dumps({"code": -1, "msg": "http://server/?token=" + SYNTHETIC_SENTINEL}).encode()
        result = probe.summarize_response(request(), raw)
        self.assertNotIn(SYNTHETIC_SENTINEL, json.dumps(result))
        self.assertIsNone(result["source_response_hash"])

    def test_echoed_plain_base64_hex_secret_is_discarded_before_hashing(self):
        item = request()
        secret = probe.Credential(SYNTHETIC_SENTINEL)
        for echo in (SYNTHETIC_SENTINEL, base64.b64encode(SYNTHETIC_SENTINEL.encode()).decode(),
                     SYNTHETIC_SENTINEL.encode().hex(), SYNTHETIC_SENTINEL.encode().hex().upper(),
                     "".join("%%%02X" % ord(c) for c in SYNTHETIC_SENTINEL)):
            obj = json.loads(response(item))
            obj["msg"] = echo
            self.assert_reason("CREDENTIAL_ECHO_RESPONSE_DISCARDED", lambda: probe.summarize_response(item, json.dumps(obj).encode(), credential=secret))

    def test_json_unicode_echo_field_name_also_discarded(self):
        item = request()
        secret = probe.Credential(SYNTHETIC_SENTINEL)
        escaped = "".join("\\u%04x" % ord(c) for c in SYNTHETIC_SENTINEL)
        for raw in (b'{"code":-1,"msg":"' + escaped.encode() + b'"}',
                    b'{"code":-1,"' + escaped.encode() + b'":"arbitrary"}'):
            self.assert_reason("CREDENTIAL_ECHO_RESPONSE_DISCARDED", lambda: probe.summarize_response(item, raw, credential=secret))

    def test_deep_percent_encoding_zero_through_twelve_discards_before_hash(self):
        item = request()
        secret = probe.Credential(SYNTHETIC_SENTINEL)
        echo = SYNTHETIC_SENTINEL
        for depth in range(13):
            raw = json.dumps({"code": -1, "msg": echo}).encode()
            self.assert_reason("CREDENTIAL_ECHO_RESPONSE_DISCARDED", lambda: probe.summarize_response(item, raw, credential=secret))
            if depth == 0:
                echo = "".join("%%%02X" % ord(c) for c in echo)
            else:
                echo = probe.urllib.parse.quote(echo, safe="")

    def test_unresolved_percent_encoding_discarded_without_unbounded_decode(self):
        encoded = "%41"
        for _ in range(12):
            encoded = probe.urllib.parse.quote(encoded, safe="")
        raw = json.dumps({"code": -1, "msg": encoded}).encode()
        self.assert_reason("CREDENTIAL_ECHO_RESPONSE_DISCARDED", lambda: probe.summarize_response(
            request(), raw, credential=probe.Credential(SYNTHETIC_SENTINEL)))

    def test_auth_rate_and_ambiguous_messages_do_not_falsely_deny_entitlement(self):
        for message, expected in (
            ("当前权限有效但内部异常", "API_ERROR"),
            ("rate limit prevents permission check", "RATE_LIMITED"),
            ("token无效无法核验权限", "AUTHENTICATION_FAILED"),
            ("抱歉，您没有访问该接口的权限", "ENTITLEMENT_NOT_GRANTED")):
            result = probe.summarize_response(request(), json.dumps({"code": -1, "msg": message}).encode())
            self.assertEqual(result["status"], expected)

    def test_transport_exception_with_secret_or_unknown_reason_is_redacted(self):
        item = request()
        for error in (RuntimeError(SYNTHETIC_SENTINEL), probe.ProbeError(SYNTHETIC_SENTINEL)):
            def failing(*_): raise error
            result = probe.run_synthetic_probe(plan=(item,), credential=probe.Credential(SYNTHETIC_SENTINEL), transport=failing, clock=lambda: NOW)
            self.assertNotIn(SYNTHETIC_SENTINEL, json.dumps(result))
            self.assertEqual(result["requests"][0]["status"], "BLOCKED")

    def test_secret_cannot_be_injected_into_lookup_metadata(self):
        self.assert_reason("CREDENTIAL_METADATA_INVALID", lambda: probe.run_synthetic_probe(transport=lambda *_: None, lookup_result={
            "secret_presence": False, "credential_lookup_result": SYNTHETIC_SENTINEL, "credential_storage": "NAMED_ENVIRONMENT"}))

    def test_row_cap_scope_and_calendar_exchange_response_validation(self):
        item = request()
        self.assert_reason("RESPONSE_ROW_CAP_EXCEEDED", lambda: probe.summarize_response(item, response(item, rows=4)))
        self.assert_reason("RESPONSE_SYMBOL_OUTSIDE_SCOPE", lambda: probe.summarize_response(item, response(item, ts_code="000001.SZ")))
        self.assert_reason("RESPONSE_DATE_OUTSIDE_SCOPE", lambda: probe.summarize_response(item, response(item, trade_date="20261008")))
        cal = request("trade_cal")
        self.assert_reason("RESPONSE_EXCHANGE_OUTSIDE_SCOPE", lambda: probe.summarize_response(cal, response(cal, exchange="SZSE")))

    def test_strict_schema_rejects_extra_missing_duplicated_fields_and_bad_cells(self):
        item = request()
        data = json.loads(response(item))
        data["data"]["fields"].append("credential")
        data["data"]["items"][0].append("value")
        self.assert_reason("RESPONSE_FIELDS_UNAPPROVED", lambda: probe.summarize_response(item, json.dumps(data).encode()))
        data = json.loads(response(item))
        data["data"]["fields"].pop()
        data["data"]["items"][0].pop()
        self.assert_reason("RESPONSE_FIELDS_MISSING", lambda: probe.summarize_response(item, json.dumps(data).encode()))
        self.assert_reason("DUPLICATE_JSON_KEY", lambda: probe.parse_response(b'{"code":0,"code":1}'))

    def test_json_decimal_preserves_all_digits_and_rejects_nan_float_and_rounding(self):
        parsed = probe.parse_response(b'{"price":12.12345678901234567890}')
        self.assertIsInstance(parsed["price"], Decimal)
        self.assertEqual(probe.decimal_text(parsed["price"]), "12.12345678901234567890")
        self.assert_reason("DECIMAL_TYPE_INVALID", lambda: probe.decimal_text(0.1))
        self.assert_reason("NON_FINITE_NUMBER", lambda: probe.parse_response(b'{"price":NaN}'))
        self.assert_reason("DECIMAL_TEXT_INVALID", lambda: probe.decimal_text("1e3"))
        self.assert_reason("DECIMAL_PRECISION_EXCEEDED", lambda: probe.decimal_text(Decimal("1e1000")))

    def test_unit_adjustment_and_provider_preclose_semantics_are_explicit(self):
        item = request()
        units = dict(item.units)
        self.assertEqual(units["vol"], "LOT_HAND_NO_SHARE_CONVERSION")
        self.assertEqual(units["amount"], "THOUSAND_YUAN")
        self.assertEqual(item.adjustment_state, "RAW_UNADJUSTED_OHLC_PROVIDER_PRE_CLOSE_EX_RIGHTS")
        self.assertEqual(dict(request("income").units)["total_revenue"], "UNSET_REQUIRED")
        self.assertEqual(request("adj_factor").adjustment_state, "FACTOR_ONLY_NO_ADJUSTED_PRICES")

    def test_revision_flag_and_report_type_not_full_revision_visibility(self):
        item = request("income")
        result = probe.summarize_response(item, response(item), retrieved_at=NOW)
        self.assertFalse(result["source_version_evidence"]["revision_history_proven"])
        self.assertEqual(result["source_version_evidence"]["update_flag_values"], ["1"])
        self.assertEqual(result["publication_precision"], "DATE_ONLY")
        self.assert_reason("FUTURE_PUBLICATION_DATE", lambda: probe.summarize_response(item, response(item, ann_date="20261006"), retrieved_at=NOW))

    def test_invalid_dates_membership_old_history_and_revision_flags_fail_closed(self):
        self.assert_reason("DATE_INVALID", lambda: probe.summarize_response(request(), response(request(), trade_date="20260230")))
        item = request("index_member_all")
        self.assert_reason("RESPONSE_MEMBERSHIP_OUTSIDE_SCOPE", lambda: probe.summarize_response(item, response(item, is_new="N")))
        item = request("income")
        self.assert_reason("REVISION_FLAG_UNRECOGNIZED", lambda: probe.summarize_response(item, response(item, update_flag="99")))

    def test_technical_success_never_closes_license_gates_or_emits_admission_lineage(self):
        item = request()
        result = probe.run_synthetic_probe(plan=(item,), credential=probe.Credential(SYNTHETIC_SENTINEL),
              transport=lambda *_: (200, response(item)), clock=lambda: NOW)
        observed = result["requests"][0]
        self.assertEqual(observed["status"], "TECHNICAL_ACCESS_OBSERVED")
        self.assertEqual(observed["available_at"], NOW)
        self.assertIsNone(observed["event_time"])
        self.assertIsNone(observed["published_at"])
        self.assertFalse(observed["historical_visibility_proven"])
        self.assertEqual(result["admission_lineage_status"], "NOT_ISSUED")
        self.assertTrue(all(x is None for x in observed["lineage"].values()))
        self.assertTrue(all(x == "BLOCKED" for x in result["gate_states"].values()))
        self.assertFalse(result["raw_persisted"])
        self.assertEqual(result["replayability"], "CAPTURE_HASH_ONLY_NOT_REPLAYABLE")
        self.assertNotIn("12.000001", json.dumps(result))  # no actual values in metadata report
        self.assertTrue(all(c["coverage_status"] == "BLOCKED" for c in result["categories"]))

    def test_announcements_are_skipped_and_never_inferred_from_15000_tier(self):
        report = probe.run_probe(clock=lambda: NOW)
        self.assertEqual(report["skipped"][0]["api_name"], "anns_d")
        self.assertEqual(report["skipped"][0]["reason_code"], "INDEPENDENT_ENTITLEMENT_NOT_VERIFIED")
        self.assertFalse(any(s.api_name == "anns_d" for s in probe.build_plan()))

    def test_each_real_network_attempt_obeys_independent_local_rate_budget(self):
        clock = FakeClock()
        items = [request("daily"), request("adj_factor"), request("income")]
        times = []
        def sender(item, *_):
            times.append(clock.elapsed)
            return 200, response(item)
        report = probe.run_synthetic_probe(plan=items, credential=probe.Credential(SYNTHETIC_SENTINEL), transport=sender,
              monotonic=clock.monotonic, sleeper=clock.sleep, clock=lambda: NOW)
        self.assertEqual(report["network_requests"], 0)
        self.assertEqual(report["mock_transport_attempts"], 3)
        self.assertEqual(times, [0.0, 3.0, 6.0])
        self.assertEqual(clock.sleeps, [3.0, 3.0])

    def test_rate_budget_cannot_be_disabled_by_fake_noop_wait(self):
        self.assert_reason("LOCAL_RATE_BUDGET_NOT_ENFORCED", lambda: probe.run_synthetic_probe(
            plan=[request("daily"), request("adj_factor")], credential=probe.Credential(SYNTHETIC_SENTINEL),
            transport=lambda item, *_: (200, response(item)), monotonic=lambda: 0.0,
            sleeper=lambda _: None, clock=lambda: NOW))

    def test_oversize_response_discarded_no_schema_or_hash(self):
        self.assert_reason("RESPONSE_SIZE_EXCEEDED", lambda: probe.parse_response(b"x" * (probe.MAX_BYTES + 1)))

    def test_report_exclusive_external_archive_only_permissions(self):
        report = probe.run_probe(clock=lambda: NOW)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(probe, "ARCHIVE_ROOT", root):
                path = root / "synthetic-metadata.json"
                probe.save_report(report, path)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assert_reason("OUTPUT_EXISTS_NO_OVERWRITE", lambda: probe.save_report(report, path))
                self.assert_reason("OUTPUT_OUTSIDE_APPROVED_ARCHIVE", lambda: probe.save_report(report, root.parent / "outside-report.json"))
                (root / "link").symlink_to(root.parent, target_is_directory=True)
                self.assert_reason("OUTPUT_OUTSIDE_APPROVED_ARCHIVE", lambda: probe.save_report(report, root / "link" / "escape.json"))

    def test_arbitrary_or_mutated_report_cannot_persist_raw_token_objects(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.object(probe, "ARCHIVE_ROOT", root):
                self.assert_reason("REPORT_NOT_PRODUCED_BY_RUNNER", lambda: probe.save_report({"token": SYNTHETIC_SENTINEL}, root / "raw.json"))
                report = probe.run_probe(clock=lambda: NOW)
                report["requests"][0]["raw"] = SYNTHETIC_SENTINEL
                self.assert_reason("REPORT_MUTATED_NO_PERSISTENCE", lambda: probe.save_report(report, root / "mutated.json"))
                self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
