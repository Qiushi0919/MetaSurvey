"""File-backed real-shaped fixtures plus unchanged Wave F durable primitives.

All new dates/prices/status/clock transcripts are REAL_SHAPED_FIXTURE.
Existing supplier originals are read only; no network, credential or actual day.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wave_g import activation as a
from wave_g import common as gc
from wave_g.common import SYMBOLS, UNSET, canonical, digest, sha
from wave_f.tests.test_activation import fixture_case
from wave_f import activation as fa


def clock(day="2026-10-08", time="15:00:00", precision="SECOND", basis="MARKET_EVENT_OBSERVATION"):
    fraction = {"SECOND": "", "MILLISECOND": ".001", "MICROSECOND": ".000001", "NANOSECOND": ".000000001"}[precision]
    return {"value": day + "T" + time + fraction + "+08:00", "precision": precision, "basis": basis}


def save(path, body):
    raw = canonical(body)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
    return {"path": str(path), "sha256": sha(raw), "bytes": len(raw)}


def packet_fixture(directory, suffix="one", day="2026-10-08", transform=None, current_observation=False):
    """Freeze NEW fixture originals exclusively before invoking the validator."""
    frozen = a.frozen_input_refs()
    capture_id = "prep:" + suffix
    def clocks():
        return {"event_time": clock(day), "published_at": clock(day, "15:00:01", "SECOND", "SOURCE_PUBLICATION"), "available_at": clock(day, "15:00:02", "MICROSECOND", "SOURCE_FIRST_AVAILABILITY"), "retrieved_at": clock(day, "15:00:03", "NANOSECOND", "COLLECTOR_RETRIEVAL")}
    calendar = {"venue": "SSE", "session_date": day, "observation_kind": "ACTUAL_OPEN_AND_EOD_OBSERVATION", "is_open": True, "market_open": clock(day, "09:30:00"), "market_close": clock(day), "actual_open_observed_at": clock(day, "09:31:00"), "actual_eod_observed_at": clock(day)}
    bars = [{"symbol": s, "session_date": day, "price_basis": "RAW_UNADJUSTED", "units": {"price": "CNY_PER_SHARE", "volume": "HANDS", "amount": "CNY_THOUSANDS"}, "open": "10.1", "high": "11.0", "low": "9.9", "close": "10.3", "volume": "100.5", "amount": "120.55"} for s in SYMBOLS]
    statuses = [{"symbol": s, "session_date": day, "listed": True, "delisted": False, "st": "UNKNOWN", "suspended": "UNKNOWN", "limit_up": "UNKNOWN", "limit_down": "UNKNOWN"} for s in SYMBOLS]
    all_rows = [("ACTUAL_SESSION", calendar, clocks())] + [("RAW_BAR_1D", r, clocks()) for r in bars] + [("STATUS_1D", r, clocks()) for r in statuses]
    if transform:
        transform(all_rows)
    def slot(domain, row, tokens, number):
        if domain == "RAW_BAR_1D":
            payload = {"code": 0, "msg": None, "data": {"fields": ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"], "items": [[row["symbol"], row["session_date"].replace("-", ""), *[row[k] for k in ("open", "high", "low", "close")], "10.0", "0.3", "3.0", row["volume"], row["amount"]]]}}
        else:
            payload = {"observations": [row]}
        raw_ref = save(directory / (suffix + "-" + str(number) + ".response.json"), payload)
        source = {"domain": domain, "provenance": "REAL_SHAPED_FIXTURE", "source_identity": "fixture-source-not-owner-policy", "source_version": "fixture-source-v1", "original_ref": raw_ref, "row": copy.deepcopy(row), "clocks": copy.deepcopy(tokens)}
        current = {"kind": "CLOCK_EVIDENCE", "version": "1.0.0", "visibility": "OBSERVED_CURRENT_CAPTURE", "observed_at": clock(day, "15:00:04", "MICROSECOND", "COLLECTOR_AVAILABILITY_OBSERVATION"), "raw_sha256": raw_ref["sha256"], "row_hash": digest(row)} if current_observation else "UNKNOWN"
        proof = {"kind": "CAPTURE_CLOCK_EVIDENCE_PREPARATION_V1", "provenance": source["provenance"], "capture_id": capture_id, "domain": domain, "source_identity": source["source_identity"], "source_version": source["source_version"], "raw_sha256": raw_ref["sha256"], "row_hash": digest(row), "clocks": copy.deepcopy(tokens), "current_availability": current}
        source["clock_evidence_ref"] = save(directory / (suffix + "-" + str(number) + ".clocks.json"), proof)
        return source
    slots = [slot(*r, n) for n, r in enumerate(all_rows)]
    anchor = {"capture_id": "prep:old-A", "session_date": "2026-09-30", "retrieved_at": clock("2026-09-30", "15:01:00", "MICROSECOND", "COLLECTOR_RETRIEVAL"), "observed_universe": list(SYMBOLS), "raw_observation_hash": digest({"fixture_only_A_raw": True}), "source_policy_hash": frozen[2]["sha256"], "rules_hash": frozen[5]["sha256"]}
    anchor["original_ref"] = save(directory / (suffix + "-A.anchor.json"), copy.deepcopy(anchor))
    anchor["content_hash"] = digest(anchor)
    p = {"kind": a.PACKET_KIND, "mode": "PREPARATION_ONLY", "capture_id": capture_id, "expected_session": day, "captured_at": clock(day, "15:02:00", "SECOND", "COLLECTOR_RETRIEVAL"), "decision_cutoff": clock(day, "16:00:00"), "snapshot_a": anchor, "frozen_inputs": frozen, "calendar": slots[0], "bars": slots[1:4], "statuses": slots[4:], "review": {}, "authorizations": {"capture": "UNAVAILABLE_NEW_OWNER_REQUIRED", "forward": "UNAVAILABLE_SEPARATE_OWNER_REQUIRED", "actual_issuer": "UNAVAILABLE_NOT_DEPLOYED"}}
    return refresh_review(p)


def refresh_review(packet):
    packet["review"] = {"kind": "PREPARATION_REVIEW_DISPLAY_ONLY", "reviewer_id": "fixture-independent-reviewer", "reviewed_packet_hash": a.preflight_hash(packet), "reviewed_original_refs": a.review_original_refs(packet), "reviewed_at": clock(packet["expected_session"], "15:02:01"), "conclusion": "PREPARATION_ONLY"}
    return packet


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=a.ARCHIVE / "validation/activation")
        self.directory = Path(self.temp.name).resolve()
        self.directory.chmod(0o700)
        self.packet = packet_fixture(self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def reject(self, packet, reason, reseal=True):
        if reseal and set(packet) == a._PACKET_FIELDS:
            refresh_review(packet)
        with self.assertRaisesRegex(ValueError, reason):
            a.validate_preflight(packet)

    def test_complete_fixture_preserves_mixed_precision_without_actual_authority(self):
        value = a.validate_preflight(self.packet)
        body = value["body"]
        self.assertTrue(body["preparation_data_complete"])
        self.assertEqual(body["clock_metadata"][1]["clocks"], self.packet["bars"][0]["clocks"])
        self.assertEqual(body["clock_metadata"][1]["clocks"]["event_time"]["value"], "2026-10-08T15:00:00+08:00")
        self.assertEqual(value["actual_forward_days"], 0)
        self.assertFalse(value["live_authority"])
        self.assertFalse(body["safe_to_trade"])
        self.assertFalse(body["actual_snapshot_b_created"])
        self.assertFalse(body["actual_open_eod_independently_accepted"])
        self.assertFalse(body["caller_review_is_actual_authority"])
        self.assertEqual(len(body["no_flags"]), 7)
        self.assertTrue(all(body["no_flags"].values()))
        self.assertEqual(body["decision"], "NO_DECISION")
        self.assertEqual(len(body["status_unknowns"]), 12)

    def test_all_second_micro_nano_precisions_supported(self):
        for index, precision in enumerate(("SECOND", "MICROSECOND", "NANOSECOND", "MILLISECOND")):
            def transform(rows):
                for _, _, clocks in rows:
                    clocks["published_at"] = clock(time="15:00:01", precision=precision, basis="SOURCE_PUBLICATION")
            p = packet_fixture(self.directory, "precision" + str(index), transform=transform)
            result = a.validate_preflight(p)["body"]
            self.assertTrue(result["preparation_data_complete"])
            self.assertEqual(result["clock_metadata"][0]["clocks"]["published_at"], p["calendar"]["clocks"]["published_at"])

    def test_utc_retrieval_preserves_source_zone_and_precision(self):
        def transform(rows):
            for _, _, clocks in rows:
                clocks["retrieved_at"] = {"value": "2026-10-08T07:00:03.123456Z", "precision": "MICROSECOND", "basis": "COLLECTOR_RETRIEVAL"}
        p = packet_fixture(self.directory, "utc", transform=transform)
        result = a.validate_preflight(p)["body"]
        self.assertTrue(result["preparation_data_complete"])
        self.assertEqual(result["clock_metadata"][0]["clocks"]["retrieved_at"]["value"], "2026-10-08T07:00:03.123456Z")

    def test_date_only_publication_and_unknown_availability_preserved_and_incomplete(self):
        def transform(rows):
            for _, _, clocks in rows:
                clocks["published_at"] = {"value": "2026-10-08", "precision": "DATE_ONLY", "basis": "DATE_ONLY_UNKNOWN_FIRST_VISIBILITY"}
                clocks["available_at"] = {"value": "UNKNOWN", "precision": "UNKNOWN", "basis": "UNKNOWN"}
        p = packet_fixture(self.directory, "dateonly", transform=transform)
        result = a.validate_preflight(p)["body"]
        self.assertFalse(result["preparation_data_complete"])
        self.assertIn("WG_ACT_CRITICAL_CLOCK_UNKNOWN_OR_DATE_ONLY", result["findings"])
        self.assertEqual(result["clock_metadata"][0]["clocks"]["published_at"]["value"], "2026-10-08")
        self.assertNotIn("00:00:00", canonical(result).decode())

    def test_unknown_precise_clock_not_silent_zero(self):
        p = copy.deepcopy(self.packet)
        p["captured_at"] = {"value": "UNKNOWN", "precision": "UNKNOWN", "basis": "UNKNOWN"}
        result = a.validate_preflight(refresh_review(p))["body"]
        self.assertFalse(result["preparation_data_complete"])

    def test_current_observation_covers_no_decision_prep_without_historical_first_visibility(self):
        def transform(rows):
            for _, _, clocks in rows:
                clocks["published_at"] = {"value": "2026-10-08", "precision": "DATE_ONLY", "basis": "DATE_ONLY_UNKNOWN_FIRST_VISIBILITY"}
                clocks["available_at"] = {"value": "UNKNOWN", "precision": "UNKNOWN", "basis": "UNKNOWN"}
        p = packet_fixture(self.directory, "current-observed", transform=transform, current_observation=True)
        value = a.validate_preflight(p)
        result = value["body"]
        self.assertTrue(result["preparation_data_complete"])
        for row in result["clock_metadata"]:
            self.assertEqual(row["clocks"]["available_at"]["value"], "UNKNOWN")
            self.assertEqual(row["clocks"]["published_at"]["value"], "2026-10-08")
            self.assertEqual(row["current_availability_evidence"]["visibility"], "OBSERVED_CURRENT_CAPTURE")
            self.assertFalse(row["historical_first_visibility_proven"])
        self.assertFalse(value["historical_visibility_proven"])
        self.assertFalse(result["actual_open_eod_independently_accepted"])
        self.assertFalse(result["safe_to_trade"])

    def test_current_observation_cannot_cover_unknown_retrieval_or_actual_eod(self):
        def transform(rows):
            rows[1][2]["retrieved_at"] = {"value": "UNKNOWN", "precision": "UNKNOWN", "basis": "UNKNOWN"}
        p = packet_fixture(self.directory, "current-unknown-retrieval", transform=transform, current_observation=True)
        self.assertFalse(a.validate_preflight(p)["body"]["preparation_data_complete"])

    def test_current_observation_never_becomes_historical_first_visibility(self):
        p = packet_fixture(self.directory, "current-scope", current_observation=True)
        slot = p["bars"][0]
        proof = json.loads(Path(slot["clock_evidence_ref"]["path"]).read_text())
        proof["current_availability"]["visibility"] = "HISTORICAL_FIRST_VISIBILITY_PROVEN"
        slot["clock_evidence_ref"] = save(self.directory / "bad-current-scope.clocks.json", proof)
        self.reject(p, "CURRENT_CAPTURE_IS_NOT_HISTORICAL_FIRST_VISIBILITY")

    def test_current_observation_cannot_relabel_as_source_first_availability(self):
        p = packet_fixture(self.directory, "current-basis", current_observation=True)
        slot = p["bars"][0]
        proof = json.loads(Path(slot["clock_evidence_ref"]["path"]).read_text())
        proof["current_availability"]["observed_at"]["basis"] = "SOURCE_FIRST_AVAILABILITY"
        slot["clock_evidence_ref"] = save(self.directory / "bad-current-basis.clocks.json", proof)
        self.reject(p, "CURRENT_CAPTURE_IS_NOT_HISTORICAL_FIRST_VISIBILITY")

    def test_current_observation_cannot_predate_completed_retrieval(self):
        p = packet_fixture(self.directory, "current-order", current_observation=True)
        slot = p["bars"][0]
        proof = json.loads(Path(slot["clock_evidence_ref"]["path"]).read_text())
        proof["current_availability"]["observed_at"] = clock(time="15:00:02", basis="COLLECTOR_AVAILABILITY_OBSERVATION")
        slot["clock_evidence_ref"] = save(self.directory / "bad-current-order.clocks.json", proof)
        self.reject(p, "CURRENT_CAPTURE_CLOCK_ORDER_DRIFT")

    def test_current_observation_cannot_rebind_another_raw_response(self):
        p = packet_fixture(self.directory, "current-raw", current_observation=True)
        slot = p["bars"][0]
        proof = json.loads(Path(slot["clock_evidence_ref"]["path"]).read_text())
        proof["current_availability"]["raw_sha256"] = digest({"another": "response"})
        slot["clock_evidence_ref"] = save(self.directory / "bad-current-raw.clocks.json", proof)
        self.reject(p, "CURRENT_CAPTURE_IS_NOT_HISTORICAL_FIRST_VISIBILITY")

    def test_source_identity_version_change_cannot_reseal_review(self):
        for key in ("source_identity", "source_version"):
            p = copy.deepcopy(self.packet)
            p["bars"][0][key] = "changed-source-v2"
            self.reject(p, "CLOCK_OR_CAPTURE_SOURCE_ORIGINAL_BINDING_DRIFT")

    def test_precision_label_does_not_pad_seconds(self):
        self.packet["captured_at"]["precision"] = "NANOSECOND"
        self.reject(self.packet, "REPORTED_PRECISION_DRIFT")

    def test_event_clock_cannot_be_available_clock(self):
        p = packet_fixture(self.directory, "eventavailability", transform=lambda rows: rows[1][2].update(available_at=clock(time="15:00:02")))
        self.reject(p, "EVENT_DATE_AS_AVAILABILITY_FORBIDDEN")

    def test_source_original_hash_tamper_cannot_be_review_resealed(self):
        path = Path(self.packet["bars"][0]["original_ref"]["path"])
        before = path.read_bytes()
        path.write_bytes(before.replace(b'"10.3"', b'"10.4"'))
        self.reject(self.packet, "DEPENDENCY_INVALIDATED")
        self.assertEqual(path.read_bytes(), before.replace(b'"10.3"', b'"10.4"'))

    def test_outer_date_relabel_rejected_against_raw(self):
        p = copy.deepcopy(self.packet)
        p["expected_session"] = "2026-10-09"
        self.reject(p, "CAPTURE_FRESHNESS_OR_CUTOFF_DRIFT")

    def test_relabel_all_wrappers_but_keep_old_response_rejected(self):
        p = packet_fixture(self.directory, "next", "2026-10-09")
        old = self.packet["bars"][0]
        p["bars"][0]["original_ref"] = copy.deepcopy(old["original_ref"])
        self.reject(p, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT")

    def test_current_response_old_clock_transcript_rejected(self):
        p = packet_fixture(self.directory, "clocknext", "2026-10-09")
        p["bars"][0]["clock_evidence_ref"] = self.packet["bars"][0]["clock_evidence_ref"]
        self.reject(p, "CLOCK_OR_CAPTURE_SOURCE_ORIGINAL_BINDING_DRIFT")

    def test_clock_change_requires_original_transcript_not_self_review(self):
        self.packet["bars"][0]["clocks"]["retrieved_at"] = clock(time="15:00:04", basis="COLLECTOR_RETRIEVAL")
        self.reject(self.packet, "CLOCK_OR_CAPTURE_SOURCE_ORIGINAL_BINDING_DRIFT")

    def test_symbol_relabel_rejected(self):
        self.packet["bars"][0]["row"]["symbol"] = SYMBOLS[1]
        self.reject(self.packet, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT")

    def test_wrong_raw_unit_rejected_not_converted(self):
        self.packet["bars"][0]["row"]["units"]["volume"] = "SHARES"
        self.reject(self.packet, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT")

    def test_raw_adjusted_relabel_rejected(self):
        self.packet["bars"][0]["row"]["price_basis"] = "ADJUSTED"
        self.reject(self.packet, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT")

    def test_duplicate_scope_extra_symbol_rejected(self):
        self.packet["bars"].append(copy.deepcopy(self.packet["bars"][0]))
        self.reject(self.packet, "EXACT_THREE_DUPLICATE_OR_SCOPE_DRIFT")

    def test_missing_bar_not_suspension_or_flat_bar(self):
        self.packet["bars"].pop()
        result = a.validate_preflight(refresh_review(self.packet))["body"]
        self.assertFalse(result["preparation_data_complete"])
        self.assertEqual(result["coverage"]["bars"]["missing"], [SYMBOLS[2]])
        self.assertIn("WG_ACT_BARS_COVERAGE_UNKNOWN", result["findings"])
        self.assertEqual(result["tradeability"], "UNKNOWN")
        self.assertEqual(len(self.packet["bars"]), 2)

    def test_missing_status_not_normal(self):
        self.packet["statuses"] = []
        result = a.validate_preflight(refresh_review(self.packet))["body"]
        self.assertEqual(result["coverage"]["statuses"]["missing"], list(SYMBOLS))
        self.assertFalse(result["preparation_data_complete"])
        self.assertFalse(result["safe_to_trade"])

    def test_known_status_still_no_permission(self):
        def transform(rows):
            for domain, row, _ in rows:
                if domain == "STATUS_1D":
                    row.update(st=False, suspended=False, limit_up="11.0", limit_down="9.0")
        p = packet_fixture(self.directory, "known", transform=transform)
        result = a.validate_preflight(p)["body"]
        self.assertEqual(result["status_unknowns"], [])
        self.assertFalse(result["safe_to_trade"])

    def test_status_bool_not_integer(self):
        p = packet_fixture(self.directory, "bool", transform=lambda rows: rows[4][1].update(suspended=0))
        self.reject(p, "STATUS_TYPE_INVALID")

    def test_calendar_plan_cannot_prove_actual_open_eod(self):
        p = packet_fixture(self.directory, "plan", transform=lambda rows: rows[0][1].update(observation_kind="CALENDAR_PLAN"))
        result = a.validate_preflight(p)["body"]
        self.assertFalse(result["preparation_data_complete"])
        self.assertIn("WG_ACT_CALENDAR_PLAN_IS_NOT_ACTUAL_SESSION", result["findings"])

    def test_no_session_evidence_incomplete(self):
        self.packet["calendar"] = None
        result = a.validate_preflight(refresh_review(self.packet))["body"]
        self.assertFalse(result["preparation_data_complete"])
        self.assertIn("WG_ACT_ACTUAL_OPEN_AND_EOD_UNKNOWN", result["findings"])

    def test_future_eod_not_clock_plan(self):
        p = packet_fixture(self.directory, "futureeod", transform=lambda rows: rows[0][1].update(actual_eod_observed_at=clock(time="16:01:00")))
        self.reject(p, "ACTUAL_EOD_NOT_OBSERVED")

    def test_future_source_clock_rejected(self):
        p = packet_fixture(self.directory, "futureclock", transform=lambda rows: rows[1][2].update(retrieved_at=clock(time="16:01:00", basis="COLLECTOR_RETRIEVAL")))
        self.reject(p, "SOURCE_CLOCK_ORDER_OR_FRESHNESS_DRIFT")

    def test_pre_eod_available_cannot_use_fresh_retrieval(self):
        def transform(rows):
            rows[1][2].update(event_time=clock(time="14:59:58"), published_at=clock(time="14:59:59", basis="SOURCE_PUBLICATION"), available_at=clock(time="14:59:59", basis="SOURCE_FIRST_AVAILABILITY"))
        p = packet_fixture(self.directory, "preeod", transform=transform)
        self.reject(p, "PRE_EOD_SOURCE_AVAILABILITY")

    def test_nanosecond_availability_after_retrieval_rejected(self):
        def transform(rows):
            rows[1][2]["available_at"] = {"value": "2026-10-08T15:00:03.000000002+08:00", "precision": "NANOSECOND", "basis": "SOURCE_FIRST_AVAILABILITY"}
        p = packet_fixture(self.directory, "nsorder", transform=transform)
        self.reject(p, "SOURCE_CLOCK_ORDER_OR_FRESHNESS_DRIFT")

    def test_A_B_same_capture_id_rejected(self):
        self.packet["snapshot_a"]["capture_id"] = self.packet["capture_id"]
        self.reject(self.packet, "A_TO_B_LINEAGE_DRIFT")

    def test_A_hash_mutation_and_policy_reseal_rejected(self):
        self.packet["snapshot_a"]["rules_hash"] = digest({"changed": True})
        self.packet["snapshot_a"]["content_hash"] = digest({k: v for k, v in self.packet["snapshot_a"].items() if k != "content_hash"})
        self.reject(self.packet, "A_ORIGINAL_BINDING_DRIFT")

    def test_A_retrieval_change_cannot_be_self_hash_resealed(self):
        self.packet["snapshot_a"]["retrieved_at"] = clock("2026-09-30", "15:02:00", basis="COLLECTOR_RETRIEVAL")
        self.packet["snapshot_a"]["content_hash"] = digest({k: v for k, v in self.packet["snapshot_a"].items() if k != "content_hash"})
        self.reject(self.packet, "A_ORIGINAL_BINDING_DRIFT")

    def test_schema_strategy_source_policy_review_input_changes_rejected(self):
        for position in (2, 4, 5, 7, 10):
            p = copy.deepcopy(self.packet)
            p["frozen_inputs"][position]["sha256"] = digest({"changed": position})
            self.reject(p, "FROZEN_SOURCE_POLICY_STRATEGY_SCHEMA_REVIEW_INPUT_DRIFT")

    def test_each_dependency_reopened_and_required(self):
        original = a._ref
        seen = []
        def tracked(ref, private=False):
            seen.append(ref["path"])
            return original(ref, private)
        with patch.object(a, "_ref", tracked):
            a.validate_preflight(self.packet)
        self.assertTrue(set(r["path"] for r in a.review_original_refs(self.packet)) <= set(seen))
        with patch.object(a, "checked_reference", side_effect=ValueError("PREP_DEPENDENCY_INVALIDATED")):
            self.reject(self.packet, "DEPENDENCY_INVALIDATED", reseal=False)

    def test_review_stale_hash_originalrefs_or_wrong_kind_rejected(self):
        for key, replacement, reason in (("reviewed_packet_hash", digest({"old": True}), "REVIEW_PACKET_OR_DIRECT_ORIGINAL_DRIFT"), ("reviewed_original_refs", [], "REVIEW_PACKET_OR_DIRECT_ORIGINAL_DRIFT"), ("kind", "HUMAN", "REVIEW_IS_NOT_ACTUAL_ISSUER")):
            p = copy.deepcopy(self.packet)
            p["review"][key] = replacement
            self.reject(p, reason, reseal=False)

    def test_callers_HUMAN_LLM_bool_or_self_hash_do_not_unlock(self):
        for value in (True, "HUMAN", "LLM", digest({"approved": True}), {"owner": "HUMAN"}):
            p = copy.deepcopy(self.packet)
            p["authorizations"]["capture"] = value
            self.reject(p, "CALLER_AUTHORIZATION_CANNOT_UNLOCK")

    def test_closed_shape_rejects_native_order_fields(self):
        self.packet["native_order"] = {"side": "BUY"}
        self.reject(self.packet, "PREFLIGHT_SHAPE_INVALID", reseal=False)

    def test_read_only_no_original_mutation(self):
        refs = a.review_original_refs(self.packet)
        before = {r["path"]: Path(r["path"]).read_bytes() for r in refs}
        one = a.validate_preflight(self.packet)
        self.assertEqual(canonical(one), canonical(a.validate_preflight(copy.deepcopy(self.packet))))
        self.assertTrue(all(Path(p).read_bytes() == b for p, b in before.items()))

    def test_private_ref_permissions_and_symlink_required(self):
        p = Path(self.packet["bars"][0]["original_ref"]["path"])
        p.chmod(0o644)
        self.reject(self.packet, "PRIVATE_ORIGINAL_REQUIRED")
        p.chmod(0o600)
        link = self.directory / "symlink.json"
        link.symlink_to(p)
        self.packet["bars"][0]["original_ref"]["path"] = str(link)
        self.reject(self.packet, "PATH_INVALID")


class NativeOriginalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=a.ARCHIVE / "validation/activation")
        self.directory = Path(self.temp.name).resolve()
        self.directory.chmod(0o700)
        self.packet = packet_fixture(self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def test_actual_existing_three_originals_327_bars_no_fresh_b(self):
        value = a.existing_anchor_projection()["body"]
        self.assertEqual([x["symbol"] for x in value["observations"]], list(SYMBOLS))
        self.assertEqual([x["row_count"] for x in value["observations"]], [327, 327, 327])
        self.assertEqual(sum(x["row_count"] for x in value["observations"]), 981)
        self.assertTrue(all(x["expected_session_present"] is False for x in value["observations"]))
        self.assertTrue(all(x["retrieved_at"]["precision"] == "MICROSECOND" for x in value["observations"]))
        self.assertTrue(all(x["available_at"] == "UNKNOWN" for x in value["observations"]))
        self.assertTrue(all(x["rows"][0]["units"]["volume"] == "HANDS" for x in value["observations"]))
        self.assertFalse(value["actual_snapshot_b_created"])
        self.assertEqual(len(value["direct_input_refs"]), len(a._PINNED) + 3)

    def test_duplicate_raw_date_not_last_write_wins(self):
        raw = json.loads(Path(self.packet["bars"][0]["original_ref"]["path"]).read_text())
        raw["data"]["items"].append(copy.deepcopy(raw["data"]["items"][0]))
        ref = save(self.directory / "duplicate.json", raw)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_RAW_SYMBOL_SESSION"):
            a.inspect_daily_original(ref, SYMBOLS[0], clock(basis="COLLECTOR_RETRIEVAL"))

    def test_native_fields_schema_drift_rejected(self):
        raw = json.loads(Path(self.packet["bars"][0]["original_ref"]["path"]).read_text())
        raw["data"]["fields"].append("adjusted_close")
        ref = save(self.directory / "schema.json", raw)
        with self.assertRaisesRegex(ValueError, "DAILY_RESPONSE_SCHEMA_DRIFT"):
            a.inspect_daily_original(ref, SYMBOLS[0], clock(basis="COLLECTOR_RETRIEVAL"))

    def test_duplicate_json_key_rejected(self):
        p = self.directory / "duplicate-key.json"
        p.write_bytes(b'{"code":0,"code":0,"msg":null,"data":{}}')
        p.chmod(0o600)
        ref = {"path": str(p), "bytes": p.stat().st_size, "sha256": sha(p.read_bytes())}
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
            a.inspect_daily_original(ref, SYMBOLS[0], clock(basis="COLLECTOR_RETRIEVAL"))

    def test_unknown_native_date_rejected_not_today_imputed(self):
        raw = json.loads(Path(self.packet["bars"][0]["original_ref"]["path"]).read_text())
        raw["data"]["items"][0][1] = "UNKNOWN"
        ref = save(self.directory / "missing-date.json", raw)
        with self.assertRaisesRegex(ValueError, "RAW_SYMBOL_OR_DATE_INVALID"):
            a.inspect_daily_original(ref, SYMBOLS[0], clock(basis="COLLECTOR_RETRIEVAL"))

    def test_numeric_json_source_lexemes_preserved_no_float_rounding(self):
        raw = json.loads(Path(self.packet["bars"][0]["original_ref"]["path"]).read_text())
        b = canonical(raw).replace(b'"10.3"', b'10.300000001').replace(b'"100.5"', b'100.500000001')
        path = self.directory / "numeric-native.json"
        path.write_bytes(b); path.chmod(0o600)
        ref = {"path": str(path), "sha256": sha(b), "bytes": len(b)}
        out = a.inspect_daily_original(ref, SYMBOLS[0], clock(basis="COLLECTOR_RETRIEVAL"))
        self.assertEqual(out["rows"][0]["close"], "10.300000001")
        self.assertEqual(out["rows"][0]["volume"], "100.500000001")


class DurableWrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=a.ARCHIVE / "validation/activation")
        self.directory = Path(self.temp.name).resolve(); self.directory.chmod(0o700)
        self.path = self.directory / "chain.wave-f.fixture.sqlite3"
        self.genesis = a.create_fixture_ledger(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def append(self, case=None, head=None):
        return a.append_fixture_day(self.path, a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", case or fixture_case()), head or a.inspect_fixture_ledger(self.path)["head_hash"])

    def test_appendonly_fixture_no_money_and_separate_actual_counter(self):
        one = self.append()
        two = self.append(fixture_case("2026-10-09", "day2"))
        self.assertEqual(two["fixture_day_count"], 2)
        self.assertEqual(two["actual_forward_days"], 0)
        self.assertEqual(two["records"][1]["previous_hash"], one["head_hash"])
        self.assertEqual(a.inspect_fixture_ledger(self.path), two)
        self.assertTrue(all(r["decision"] == "NO_DECISION" and r["safe_to_trade"] is False and r["actual_policies"] == {k: UNSET for k in ("account", "cost", "risk")} for r in two["records"]))
        conn = sqlite3.connect(self.path)
        for sql in ("UPDATE fixture_days SET session_date='2026-10-12'", "DELETE FROM fixture_days"):
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute(sql)
        self.assertEqual({r[0] for r in conn.execute("SELECT name FROM sqlite_schema WHERE type='table'")}, {"fixture_metadata", "fixture_days", "fixture_failed_attempts"})
        conn.close()

    def test_duplicate_rejected_no_actual_increment(self):
        first = self.append()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PAPER_DAY"):
            self.append(fixture_case(identifier="duplicate"))
        self.assertEqual(a.inspect_fixture_ledger(self.path), first)

    def test_sanitized_failed_chain_persists_then_day_success(self):
        case = fixture_case(); case["bars"].pop()
        for actor, c in (("SYNTHETIC_HUMAN_USER", case), ("LLM", fixture_case())):
            with self.assertRaises(ValueError):
                a.attempt_fixture_day(self.path, actor, c, self.genesis["head_hash"])
        failures = a.recover_fixture_ledger(self.path)["result"]
        self.assertEqual(failures["fixture_day_count"], 0)
        self.assertEqual(failures["failed_capture_count"], 2)
        self.assertEqual(failures["failed_captures"][1]["previous_hash"], failures["failed_captures"][0]["attempt_hash"])
        self.assertTrue(all(x["untrusted_payload_retained"] is False for x in failures["failed_captures"]))
        completed = self.append()
        self.assertEqual(completed["failed_capture_count"], 2)
        self.assertEqual(completed["actual_forward_days"], 0)

    def test_restart_in_fresh_process_new_fixture_approval(self):
        self.append()
        script = "from wave_g import activation as a\nfrom wave_f.tests.test_activation import fixture_case\nimport json,sys\np=sys.argv[1]\nr=a.recover_fixture_ledger(p)\nh=a.issue_fixture_approval('SYNTHETIC_HUMAN_USER',fixture_case('2026-10-09','new-process'))\nx=a.append_fixture_day(p,h,r['result']['head_hash'])\nprint(json.dumps({'fixture':x['fixture_day_count'],'actual':x['actual_forward_days']}))\n"
        result = subprocess.run([sys.executable, "-B", "-c", script, str(self.path)], cwd=a.ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"fixture": 2, "actual": 0})

    def test_atomic_concurrent_same_head_one_success(self):
        approvals = [a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", fixture_case(identifier="concurrent" + str(i))) for i in range(2)]
        def append(h):
            try:
                a.append_fixture_day(self.path, h, self.genesis["head_hash"])
                return "SUCCESS"
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(append, approvals))
        self.assertEqual(values.count("SUCCESS"), 1)
        self.assertIn("WF_ACT_STALE_EXPECTED_HEAD", values)
        self.assertEqual(a.inspect_fixture_ledger(self.path)["actual_forward_days"], 0)

    def test_after_insert_failure_rolls_back_and_handle_remains_unused(self):
        handle = a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", fixture_case())
        original = fa._inspect
        count = 0
        def fail(*args):
            nonlocal count
            count += 1
            if count == 2:
                raise ValueError("WF_ACT_FIXTURE_INJECTED_FAILURE")
            return original(*args)
        with patch.object(fa, "_inspect", fail):
            with self.assertRaisesRegex(ValueError, "INJECTED_FAILURE"):
                a.append_fixture_day(self.path, handle, self.genesis["head_hash"])
        self.assertEqual(a.inspect_fixture_ledger(self.path), self.genesis)
        self.assertEqual(a.append_fixture_day(self.path, handle, self.genesis["head_hash"])["fixture_day_count"], 1)

    def test_recovery_no_repair_after_schema_corruption(self):
        conn = sqlite3.connect(self.path); conn.execute("CREATE TABLE unauthorized_extra(x)"); conn.close()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "STORE_SCHEMA_DRIFT"):
            a.recover_fixture_ledger(self.path)
        self.assertEqual(before, self.path.read_bytes())

    def test_capability_copies_and_json_do_not_authorize_fixture_append(self):
        handle = a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", fixture_case())
        for fake in (copy.copy(handle), copy.deepcopy(handle), handle._body, True, "HUMAN"):
            with self.assertRaises(ValueError):
                a.append_fixture_day(self.path, fake, self.genesis["head_hash"])
        self.assertEqual(a.inspect_fixture_ledger(self.path), self.genesis)

    def test_actual_entrypoints_hardblock_before_any_io_or_network(self):
        with patch("builtins.open", side_effect=AssertionError("IO attempted")), patch.object(a, "checked_file", side_effect=AssertionError("read attempted")), patch("pathlib.Path.stat", side_effect=AssertionError("stat attempted")), patch("socket.socket", side_effect=AssertionError("network attempted")):
            for entry in (a.execute_capture, a.append_actual_session, a.run_snapshot_b, a.run_real_forward):
                for approved in (True, "HUMAN", "LLM", digest({"approval": True})):
                    with self.assertRaisesRegex(ValueError, "NOT_AUTHORIZED"):
                        entry(path=self.path, approval=approved, capture=fixture_case(), actual_day=1, source_admitted=True)
        self.assertEqual(a.inspect_fixture_ledger(self.path), self.genesis)


class StagingStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=a.ARCHIVE / "validation/activation")
        self.directory = Path(self.temp.name).resolve(); self.directory.chmod(0o700)
        self.path = self.directory / "packets.wave-g.staging.sqlite3"
        self.genesis = a.create_staging_store(self.path)
        self.packet = packet_fixture(self.directory, "stage-one")

    def tearDown(self):
        self.temp.cleanup()

    def next_packet(self):
        p = packet_fixture(self.directory, "stage-two", "2026-10-09")
        p["snapshot_a"] = copy.deepcopy(self.packet["snapshot_a"])
        return refresh_review(p)

    def test_configuration_and_two_packets_prepare_algorithm_without_actual_days(self):
        one = a.stage_preflight_packet(self.path, self.packet, self.genesis["head_hash"])
        two = a.stage_preflight_packet(self.path, self.next_packet(), one["head_hash"])
        self.assertEqual(two["staged_fixture_count"], 2)
        self.assertEqual(two["actual_forward_days"], 0)
        self.assertFalse(two["actual_record_appended"])
        self.assertEqual(two["records"][1]["previous_hash"], one["head_hash"])
        self.assertTrue(all(x["decision"] == "NO_DECISION" and x["safe_to_trade"] is False and all(x["no_flags"].values()) for x in two["records"]))
        config = a.staging_store_configuration()
        self.assertFalse(config["core_sqlite_append_chain_algorithm_rebuild_required"])
        self.assertEqual(config["actual_mode"], "HARD_BLOCKED")
        self.assertEqual(a.inspect_staging_store(self.path), two)

    def test_duplicate_session_capture_and_old_head_fail(self):
        first = a.stage_preflight_packet(self.path, self.packet, self.genesis["head_hash"])
        with self.assertRaisesRegex(ValueError, "STALE_EXPECTED_HEAD"):
            a.stage_preflight_packet(self.path, self.next_packet(), self.genesis["head_hash"])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SESSION_CAPTURE_OR_RAW"):
            a.stage_preflight_packet(self.path, self.packet, first["head_hash"])
        self.assertEqual(a.inspect_staging_store(self.path), first)

    def test_failed_incomplete_capture_chain_then_success(self):
        bad = copy.deepcopy(self.packet); bad["bars"].pop(); refresh_review(bad)
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, "STAGING_INCOMPLETE_PREFLIGHT"):
                a.attempt_staging_packet(self.path, bad, self.genesis["head_hash"])
        failed = a.inspect_staging_store(self.path)
        self.assertEqual(failed["staged_fixture_count"], 0)
        self.assertEqual(failed["failed_attempt_count"], 2)
        self.assertEqual(failed["failed_attempts"][1]["previous_hash"], failed["failed_attempts"][0]["attempt_hash"])
        self.assertTrue(all(x["untrusted_payload_retained"] is False for x in failed["failed_attempts"]))
        final = a.stage_preflight_packet(self.path, self.packet, self.genesis["head_hash"])
        self.assertEqual(final["failed_attempt_count"], 2)
        self.assertEqual(final["actual_forward_days"], 0)

    def test_actual_candidate_cannot_be_appended_via_staging_before_io(self):
        p = copy.deepcopy(self.packet); p["bars"][0]["provenance"] = "UNVERIFIED_ACTUAL_CANDIDATE"
        with patch.object(a, "_st_path", side_effect=AssertionError("store touched")), patch.object(a, "_ref", side_effect=AssertionError("source touched")):
            with self.assertRaisesRegex(ValueError, "FIXTURE_ONLY_ACTUAL_APPEND_FORBIDDEN"):
                a.stage_preflight_packet(self.path, p, self.genesis["head_hash"])
        self.assertEqual(a.inspect_staging_store(self.path), self.genesis)

    def test_concurrent_single_winner(self):
        def run(_):
            try:
                a.stage_preflight_packet(self.path, self.packet, self.genesis["head_hash"])
                return "SUCCESS"
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(results.count("SUCCESS"), 1)
        self.assertIn("WG_ACT_STAGING_STALE_EXPECTED_HEAD", results)

    def test_failure_after_insert_rolls_back(self):
        original, count = a._st_inspect, 0
        def fail(*args):
            nonlocal count
            count += 1
            if count == 2: raise ValueError("WG_ACT_STAGING_INJECTED_FAILURE")
            return original(*args)
        with patch.object(a, "_st_inspect", fail):
            with self.assertRaisesRegex(ValueError, "INJECTED_FAILURE"):
                a.stage_preflight_packet(self.path, self.packet, self.genesis["head_hash"])
        self.assertEqual(a.inspect_staging_store(self.path), self.genesis)
        self.assertEqual(a.stage_preflight_packet(self.path, self.packet, self.genesis["head_hash"])["staged_fixture_count"], 1)

    def test_original_drift_blocks_restart_without_repair(self):
        a.stage_preflight_packet(self.path, self.packet, self.genesis["head_hash"])
        raw = Path(self.packet["bars"][0]["original_ref"]["path"])
        raw.write_bytes(raw.read_bytes().replace(b'"10.3"', b'"10.4"'))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "DEPENDENCY_INVALIDATED"):
            a.recover_staging_store(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_SQL_update_delete_insert_guards_and_schema_tamper(self):
        a.stage_preflight_packet(self.path, self.packet, self.genesis["head_hash"])
        conn = sqlite3.connect(self.path)
        for sql in ("DELETE FROM staging_records", "UPDATE staging_metadata SET hash='x'", "INSERT INTO staging_failures VALUES(1,'x','x','x','{}')"):
            with self.assertRaises(sqlite3.DatabaseError): conn.execute(sql)
        conn.execute("CREATE TABLE hidden_native_order(x)"); conn.commit(); conn.close()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "STAGING_SCHEMA_OR_INTEGRITY_DRIFT"):
            a.recover_staging_store(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_restart_fresh_process_verify_then_stage_next(self):
        first = a.stage_preflight_packet(self.path, self.packet, self.genesis["head_hash"])
        p = self.next_packet(); packet_file = self.directory / "next.json"
        save(packet_file, p)
        script = "from wave_g import activation as a\nimport json,sys\nr=a.recover_staging_store(sys.argv[1])\np=json.loads(open(sys.argv[2]).read())\nx=a.stage_preflight_packet(sys.argv[1],p,r['result']['head_hash'])\nprint(json.dumps({'staged':x['staged_fixture_count'],'actual':x['actual_forward_days']}))\n"
        x = subprocess.run([sys.executable, "-B", "-c", script, str(self.path), str(packet_file)], cwd=a.ROOT, text=True, capture_output=True)
        self.assertEqual(x.returncode, 0, x.stderr)
        self.assertEqual(json.loads(x.stdout), {"staged": 2, "actual": 0})
        self.assertEqual(a.inspect_staging_store(self.path)["records"][1]["previous_hash"], first["head_hash"])

    def test_changed_A_anchor_is_not_restart_continuity(self):
        first = a.stage_preflight_packet(self.path, self.packet, self.genesis["head_hash"])
        p = packet_fixture(self.directory, "different-A", "2026-10-09")
        with self.assertRaisesRegex(ValueError, "FROZEN_INPUT_ANCHOR_OR_SESSION_ORDER_DRIFT"):
            a.stage_preflight_packet(self.path, p, first["head_hash"])

    def test_stable_Git_identity_reads_mapped_checkout_bytes(self):
        ref = a.frozen_input_refs()[0]
        relative = Path(ref["path"]).relative_to(a.BASELINE_ROOT)
        mapped_root = self.directory / "clone"
        target = mapped_root / relative; target.parent.mkdir(parents=True)
        original = Path(ref["path"]).read_bytes(); target.write_bytes(original)
        with patch.object(gc, "ROOT", mapped_root):
            self.assertEqual(a._ref(ref), original)
            target.write_bytes(original + b" ")
            with self.assertRaisesRegex(ValueError, "DEPENDENCY_INVALIDATED"):
                a._ref(ref)
        self.assertEqual(Path(ref["path"]).read_bytes(), original)

    def test_preflight_validation_hash_stable_across_hash_seeds(self):
        packet_file = self.directory / "deterministic.json"; save(packet_file, self.packet)
        script = "from wave_g import activation as a\nfrom wave_g.common import digest\nimport json,sys\nprint(digest(a.validate_preflight(json.loads(open(sys.argv[1]).read()))))\n"
        expected = digest(a.validate_preflight(self.packet))
        for seed in ("1", "997"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            x = subprocess.run([sys.executable, "-B", "-c", script, str(packet_file)], cwd=a.ROOT, env=env, text=True, capture_output=True)
            self.assertEqual(x.returncode, 0, x.stderr)
            self.assertEqual(x.stdout.strip(), expected)


class ReadinessTests(unittest.TestCase):
    def test_honest_remaining_actual_work_and_no_money_block_for_prep(self):
        snapshot, forward = a.snapshot_readiness(), a.forward_readiness()
        self.assertFalse(snapshot["body"]["only_human_authorization_missing"])
        self.assertFalse(snapshot["body"]["actual_fresh_session_observed"])
        self.assertEqual(forward["body"]["actual_approval_issuer"], "UNAVAILABLE_NOT_DEPLOYED")
        self.assertIn("GENERIC_ALGORITHM_IMPLEMENTED", forward["body"]["actual_store"])
        self.assertFalse(forward["body"]["real_money_parameters_block_no_decision_engineering"])
        self.assertFalse(forward["body"]["synthetic_days_count_as_actual"])
        for value in (snapshot, forward):
            self.assertEqual(value["actual_forward_days"], 0)
            self.assertFalse(value["live_authority"])
            self.assertFalse(value["productionGate"])
            self.assertTrue(all(value["body"]["no_flags"].values()))
            self.assertEqual(len(value["body"]["no_flags"]), 7)
            self.assertFalse(value["body"]["scheduled"])

    def test_display_mutation_cannot_mutate_module_no_flags(self):
        changed = a.snapshot_readiness()
        changed["body"]["no_flags"]["NO_ORDER"] = False
        self.assertTrue(a.forward_readiness()["body"]["no_flags"]["NO_ORDER"])
        self.assertEqual(canonical(a.snapshot_readiness()), canonical(a.snapshot_readiness()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
