"""Explicit synthetic activation and private NO_DECISION persistence tests.

No actual source, credentials, native account/order schema or old store is used.
Every numerical value below is SYNTHETIC_NOT_OWNER_POLICY.
"""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from wave_f import activation as a
from wave_f.common import SYMBOLS, UNSET, canonical, digest


def instant(day, clock):
    return day + "T" + clock + ".000000000+08:00"


def fixture_case(day="2026-10-08", identifier="B-1"):
    """Only synthetic source facts; no strategy/economic/Owner policy defaults."""
    def clocks(event="15:00:00", publication="15:00:01", available="15:00:02", retrieved="15:00:03"):
        return {"event_time": instant(day, event), "published_at": instant(day, publication), "available_at": instant(day, available), "retrieved_at": instant(day, retrieved), "precision": "NANOSECOND"}
    bindings = {key: digest({"synthetic_binding": key}) if key.endswith("_hash") else "fixture-" + key + "-v1" for key in a._BINDINGS}
    anchor = {"kind": "SYNTHETIC_SNAPSHOT_A_ANCHOR", "capture_id": "fixture:A-1", "session_date": "2026-09-30", "retrieved_at": instant("2026-09-30", "15:01:00"), "observed_universe": list(SYMBOLS), "raw_observation_hash": digest({"synthetic_A_raw": True}), "source_policy_hash": bindings["source_policy_hash"], "rules_hash": bindings["rules_hash"]}
    anchor["content_hash"] = digest(anchor)
    source = lambda domain, symbol="": {"source": "fixture://" + domain + "/" + symbol.replace(".", "-") + day, "source_version": bindings["source_version"], "source_hash": digest({"synthetic_source": domain, "symbol": symbol, "day": day})}
    calendar = {"kind": "SYNTHETIC_ACTUAL_OPEN_OBSERVATION", "venue": "SSE", "session_date": day, "is_open": True, "market_open": instant(day, "09:30:00"), "market_close": instant(day, "15:00:00"), "actual_open_observed_at": instant(day, "09:31:00"), **source("calendar"), "clocks": clocks("09:30:00", "09:30:01", "09:30:02", "09:31:01")}
    bars = [{"symbol": symbol, "session_date": day, "price_basis": "RAW_UNADJUSTED", "units": {"price": "CNY_PER_SHARE", "volume": "SHARES"}, "open": "10.10", "high": "11.00", "low": "9.90", "close": "10.30", "volume": 1000, **source("bars", symbol), "clocks": clocks()} for symbol in SYMBOLS]
    statuses = [{"symbol": symbol, "session_date": day, "listed": True, "delisted": False, "st": "UNKNOWN", "suspended": "UNKNOWN", "limit_up": "UNKNOWN", "limit_down": "UNKNOWN", **source("status", symbol), "clocks": clocks()} for symbol in SYMBOLS]
    case = {"kind": "SYNTHETIC_ACTIVATION_CAPTURE", "provenance": a.PROVENANCE, "namespace": a.NAMESPACE, "version": a.FIXTURE_CAPTURE_VERSION, "capture_id": "fixture:" + identifier, "expected_session": day, "captured_at": instant(day, "15:00:04"), "decision_cutoff": instant(day, "15:01:00"), "snapshot_a": anchor, "calendar": calendar, "bars": bars, "statuses": statuses, "bindings": bindings, "review": {}, "authorization": {"kind": "SYNTHETIC_HUMAN_USER", "authorization_id": "fixture:human-" + identifier, "issued_at": instant(day, "09:00:00"), "expires_at": instant(day, "16:00:00")}}
    seal_fixture_originals(case)
    case["review"] = {"kind": "SYNTHETIC_INDEPENDENT_REVIEW", "reviewer_id": "fixture:reviewer-1", "reviewed_capture_hash": a.fixture_capture_hash(case), "reviewed_strategy_hash": bindings["strategy_hash"], "review_policy_hash": bindings["review_policy_hash"], "reviewed_at": instant(day, "15:00:05"), "conclusion": "FIXTURE_PREPARATION_ONLY"}
    return case


def seal_fixture_originals(case):
    """Declare NEW synthetic source originals; never called by production code.

    Updating review/DISPLAY metadata alone must not regenerate source originals.
    Tests invoke this explicitly when constructing new source packets, rather
    than when exercising a stale-original relabel attack.
    """
    for domain, rows in (("CALENDAR_ACTUAL_OPEN", [case["calendar"]]), ("RAW_BAR_1D", case["bars"]), ("STATUS_1D", case["statuses"])):
        for row in rows:
            original = {"kind": "SYNTHETIC_SOURCE_ORIGINAL", "provenance": a.PROVENANCE, "version": a.FIXTURE_CAPTURE_VERSION, "domain": domain, "source": row["source"], "source_version": row["source_version"], "row": copy.deepcopy({key: value for key, value in row.items() if key not in {"source", "source_version", "source_hash", "source_payload"}})}
            row["source_payload"] = original
            row["source_hash"] = digest(original)
    return case


def refresh_review(case, originals=False):
    if originals:
        seal_fixture_originals(case)
    case["review"]["reviewed_capture_hash"] = a.fixture_capture_hash(case)
    case["review"]["reviewed_strategy_hash"] = case["bindings"]["strategy_hash"]
    case["review"]["review_policy_hash"] = case["bindings"]["review_policy_hash"]
    return case


class CaptureTests(unittest.TestCase):
    def reject(self, case, reason=None, reseal=True, reseal_originals=False):
        if reseal and type(case) is dict and set(case) == a._CASE:
            refresh_review(case, originals=reseal_originals)
        with self.assertRaises(ValueError) as caught:
            a.validate_fixture_capture(case)
        if reason:
            self.assertIn(reason, str(caught.exception))

    def test_synthetic_complete_capture_still_no_decision_no_authority(self):
        value = a.validate_fixture_capture(fixture_case())
        self.assertTrue(value["fresh_session_fixture_valid"])
        self.assertTrue(value["eod_fixture_complete"])
        self.assertEqual(value["decision"], "NO_DECISION")
        self.assertEqual(value["actual_forward_days"], 0)
        self.assertFalse(value["live_authority"])
        self.assertFalse(value["native_promotion"])
        self.assertFalse(value["actual_snapshot_b_created"])

    def test_unknown_status_retained_never_safe(self):
        case = fixture_case()
        for row in case["statuses"]:
            for key in ("listed", "delisted", "st", "suspended"):
                row[key] = "UNKNOWN"
        result = a.validate_fixture_capture(refresh_review(case, originals=True))
        self.assertEqual(len(result["status_unknowns"]), 18)
        self.assertEqual(result["tradeability"], "UNKNOWN")
        self.assertFalse(result["safe_to_trade"])

    def test_known_status_never_order_permission(self):
        case = fixture_case()
        for row in case["statuses"]:
            row.update(st=False, suspended=False, limit_up="11.00", limit_down="9.00")
        result = a.validate_fixture_capture(refresh_review(case, originals=True))
        self.assertEqual(result["status_unknowns"], [])
        self.assertFalse(result["safe_to_trade"])
        self.assertEqual(result["decision"], "NO_DECISION")

    def test_calendar_plan_cannot_actual_open(self):
        case = fixture_case(); case["calendar"]["kind"] = "PLANNED_SESSION"
        self.reject(case, "OPEN_OBSERVATION_REQUIRED")

    def test_calendar_open_boolean_false(self):
        case = fixture_case(); case["calendar"]["is_open"] = False
        self.reject(case, "OPEN_OBSERVATION_REQUIRED")

    def test_calendar_open_integer_not_bool(self):
        case = fixture_case(); case["calendar"]["is_open"] = 1
        self.reject(case, "OPEN_OBSERVATION_REQUIRED")

    def test_missing_actual_open_observation(self):
        case = fixture_case(); del case["calendar"]["actual_open_observed_at"]
        self.reject(case, "CALENDAR_OBSERVATION_REQUIRED")

    def test_actual_open_before_open(self):
        case = fixture_case(); case["calendar"]["actual_open_observed_at"] = instant("2026-10-08", "09:29:59")
        self.reject(case, "EOD_NOT_OBSERVED")

    def test_actual_open_after_close(self):
        case = fixture_case(); case["calendar"]["actual_open_observed_at"] = instant("2026-10-08", "15:00:01")
        self.reject(case, "EOD_NOT_OBSERVED")

    def test_calendar_retrieval_before_actual_open(self):
        case = fixture_case(); case["calendar"]["clocks"]["retrieved_at"] = instant("2026-10-08", "09:30:59")
        self.reject(case, "OPEN_CLOCK_OBSERVATION_DRIFT")

    def test_market_close_not_declared_eod(self):
        case = fixture_case(); case["calendar"]["market_close"] = instant("2026-10-08", "14:59:59")
        self.reject(case, "SESSION_BOUNDARIES_INVALID")

    def test_nanosecond_market_boundary_drift(self):
        case = fixture_case(); case["calendar"]["market_close"] = "2026-10-08T15:00:00.000000001+08:00"
        self.reject(case, "SESSION_BOUNDARIES_INVALID")

    def test_eod_capture_before_close(self):
        case = fixture_case(); case["captured_at"] = instant("2026-10-08", "14:59:59")
        self.reject(case, "EOD_NOT_OBSERVED")

    def test_future_cutoff_different_day(self):
        case = fixture_case(); case["decision_cutoff"] = instant("2026-10-09", "15:01:00")
        self.reject(case, "CAPTURE_CUTOFF_DRIFT")

    def test_captured_after_cutoff(self):
        case = fixture_case(); case["captured_at"] = instant("2026-10-08", "15:01:01")
        self.reject(case, "CAPTURE_CUTOFF_DRIFT")

    def test_holiday_plan_rejected(self):
        self.reject(fixture_case("2026-10-07"), "FIXTURE_CALENDAR_CLOSED")

    def test_weekend_plan_rejected(self):
        self.reject(fixture_case("2026-10-10"), "FIXTURE_CALENDAR_CLOSED")

    def test_pre_anchor_day_rejected(self):
        self.reject(fixture_case("2026-09-30"), "SESSION_NOT_AFTER_A")

    def test_invalid_session_date(self):
        case = fixture_case(); case["expected_session"] = "2026-13-08"
        self.reject(case, "SESSION_DATE_INVALID")

    def test_missing_bar_not_imputed_suspension(self):
        case = fixture_case(); case["bars"].pop()
        self.reject(case, "EOD_BAR_COVERAGE_UNKNOWN")

    def test_known_suspension_does_not_admit_missing_bar(self):
        case = fixture_case(); case["statuses"][-1]["suspended"] = True; case["bars"].pop()
        self.reject(case, "EOD_BAR_COVERAGE_UNKNOWN")

    def test_missing_status_not_safe(self):
        case = fixture_case(); case["statuses"].pop()
        self.reject(case, "STATUS_COVERAGE_UNKNOWN")

    def test_duplicate_bar_symbol(self):
        case = fixture_case(); case["bars"][1]["symbol"] = SYMBOLS[0]
        self.reject(case, "BAR_UNIVERSE_OR_DUPLICATE")

    def test_duplicate_status_symbol(self):
        case = fixture_case(); case["statuses"][1]["symbol"] = SYMBOLS[0]
        self.reject(case, "STATUS_UNIVERSE_OR_DUPLICATE")

    def test_fourth_security_reject(self):
        case = fixture_case(); case["bars"].append(copy.deepcopy(case["bars"][0]))
        self.reject(case, "EOD_BAR_COVERAGE_UNKNOWN")

    def test_stale_daily_bar(self):
        case = fixture_case(); case["bars"][0]["session_date"] = "2026-09-30"
        self.reject(case, "BAR_SESSION_OR_ADJUSTMENT_DRIFT")

    def test_stale_status(self):
        case = fixture_case(); case["statuses"][0]["session_date"] = "2026-09-30"
        self.reject(case, "STATUS_SESSION_DRIFT")

    def test_future_status(self):
        case = fixture_case(); case["statuses"][0]["session_date"] = "2026-10-09"
        self.reject(case, "STATUS_SESSION_DRIFT")

    def test_current_status_without_session_rejected(self):
        case = fixture_case(); del case["statuses"][0]["session_date"]
        self.reject(case, "STATUS_SHAPE_INVALID")

    def test_adjusted_bar_cannot_raw(self):
        case = fixture_case(); case["bars"][0]["price_basis"] = "FORWARD_ADJUSTED"
        self.reject(case, "BAR_SESSION_OR_ADJUSTMENT_DRIFT")

    def test_price_units_required(self):
        case = fixture_case(); case["bars"][0]["units"]["price"] = "UNKNOWN"
        self.reject(case, "RAW_PRICE_UNITS_REQUIRED")

    def test_float_price_rejected(self):
        case = fixture_case(); case["bars"][0]["close"] = 10.3
        self.reject(case, reseal=False)

    def test_integer_price_rejected(self):
        case = fixture_case(); case["bars"][0]["close"] = 10
        self.reject(case, "DECIMAL_REQUIRED")

    def test_nan_price_rejected(self):
        case = fixture_case(); case["bars"][0]["close"] = "NaN"
        self.reject(case, "DECIMAL_REQUIRED")

    def test_zero_price_rejected(self):
        case = fixture_case(); case["bars"][0]["low"] = "0"
        self.reject(case, "RAW_OHLC_INVALID")

    def test_ohlc_inconsistent(self):
        case = fixture_case(); case["bars"][0]["high"] = "10.00"
        self.reject(case, "RAW_OHLC_INVALID")

    def test_boolean_volume_rejected(self):
        case = fixture_case(); case["bars"][0]["volume"] = True
        self.reject(case, "INTEGER_VOLUME_REQUIRED")

    def test_negative_volume_rejected(self):
        case = fixture_case(); case["bars"][0]["volume"] = -1
        self.reject(case, "INTEGER_VOLUME_REQUIRED")

    def test_date_only_bar_clock(self):
        case = fixture_case(); case["bars"][0]["clocks"]["available_at"] = "2026-10-08"
        self.reject(case, "NANOSECOND_SHANGHAI_INSTANT_REQUIRED")

    def test_date_only_precision_claim(self):
        case = fixture_case(); case["statuses"][0]["clocks"]["precision"] = "DATE_ONLY"
        self.reject(case, "DATE_ONLY_FORBIDDEN")

    def test_midnight_imputation(self):
        case = fixture_case(); case["bars"][0]["clocks"]["published_at"] = instant("2026-10-08", "00:00:00")
        self.reject(case, "MIDNIGHT_IMPUTATION_FORBIDDEN")

    def test_naive_timezone(self):
        case = fixture_case(); case["bars"][0]["clocks"]["retrieved_at"] = "2026-10-08T15:00:03.000000000"
        self.reject(case, "NANOSECOND_SHANGHAI_INSTANT_REQUIRED")

    def test_wrong_timezone(self):
        case = fixture_case(); case["decision_cutoff"] = "2026-10-08T15:01:00.000000000Z"
        self.reject(case, "NANOSECOND_SHANGHAI_INSTANT_REQUIRED")

    def test_clock_precision_lost(self):
        case = fixture_case(); case["decision_cutoff"] = "2026-10-08T15:01:00+08:00"
        self.reject(case, "NANOSECOND_SHANGHAI_INSTANT_REQUIRED")

    def test_missing_four_clock(self):
        case = fixture_case(); del case["bars"][0]["clocks"]["published_at"]
        self.reject(case, "FOUR_CLOCKS_REQUIRED")

    def test_null_publication_not_guessed(self):
        case = fixture_case(); case["bars"][0]["clocks"]["published_at"] = None
        self.reject(case, "NANOSECOND_SHANGHAI_INSTANT_REQUIRED")

    def test_event_not_eod(self):
        case = fixture_case(); case["bars"][0]["clocks"]["event_time"] = instant("2026-10-08", "14:59:59")
        self.reject(case, "EVENT_TIME_DRIFT")

    def test_future_available_clock(self):
        case = fixture_case(); case["bars"][0]["clocks"]["available_at"] = instant("2026-10-08", "15:01:01")
        self.reject(case, "CLOCK_ORDER_OR_FUTURE")

    def test_nanosecond_future_retrieval(self):
        case = fixture_case(); case["bars"][0]["clocks"]["retrieved_at"] = "2026-10-08T15:01:00.000000001+08:00"
        self.reject(case, "CLOCK_ORDER_OR_FUTURE")

    def test_future_published_not_visible(self):
        case = fixture_case(); case["statuses"][0]["clocks"]["published_at"] = instant("2026-10-08", "16:00:00")
        self.reject(case, "CLOCK_ORDER_OR_FUTURE")

    def test_retrieved_before_available(self):
        case = fixture_case(); case["bars"][0]["clocks"]["retrieved_at"] = instant("2026-10-08", "15:00:01")
        self.reject(case, "CLOCK_ORDER_OR_FUTURE")

    def test_retrieval_at_eod_not_after(self):
        case = fixture_case()
        for key in ("published_at", "available_at", "retrieved_at"):
            case["bars"][0]["clocks"][key] = instant("2026-10-08", "15:00:00")
        self.reject(case, "RETRIEVAL_NOT_AFTER_EOD")

    def test_capture_precedes_source_retrieval(self):
        case = fixture_case(); case["bars"][0]["clocks"]["retrieved_at"] = instant("2026-10-08", "15:00:05")
        self.reject(case, "CAPTURE_BEFORE_SOURCE_RETRIEVAL", reseal_originals=True)

    def test_clock_from_stale_session(self):
        case = fixture_case(); case["bars"][0]["clocks"]["retrieved_at"] = instant("2026-09-30", "15:00:03")
        self.reject(case, "CLOCK_SESSION_DRIFT")

    def test_anchor_hash_tamper(self):
        case = fixture_case(); case["snapshot_a"]["retrieved_at"] = instant("2026-09-30", "15:02:00")
        self.reject(case, "ANCHOR_HASH_INVALID")

    def test_same_capture_identity_as_a(self):
        case = fixture_case(); case["capture_id"] = case["snapshot_a"]["capture_id"]
        self.reject(case, "CAPTURE_ID_NOT_FRESH")

    def test_anchor_wrong_cohort(self):
        case = fixture_case(); case["snapshot_a"]["observed_universe"] = [SYMBOLS[0]]
        self.reject(case, "ANCHOR_BINDING_INVALID")

    def test_anchor_date_only(self):
        case = fixture_case(); case["snapshot_a"]["retrieved_at"] = "2026-09-30"
        case["snapshot_a"]["content_hash"] = digest({key: value for key, value in case["snapshot_a"].items() if key != "content_hash"})
        self.reject(case, "NANOSECOND_SHANGHAI_INSTANT_REQUIRED")

    def test_a_b_policy_drift(self):
        case = fixture_case(); case["bindings"]["source_policy_hash"] = digest({"changed": True})
        self.reject(case, "A_TO_B_POLICY_DRIFT")

    def test_source_version_drift(self):
        case = fixture_case(); case["bars"][0]["source_version"] = "fixture-other-v2"
        self.reject(case, "SOURCE_VERSION_DRIFT")

    def test_actual_source_uri_not_fixture(self):
        case = fixture_case(); case["bars"][0]["source"] = "https://example.org/data"
        self.reject(case, "FIXTURE_SOURCE_REQUIRED")

    def test_source_query_not_retained(self):
        case = fixture_case(); case["bars"][0]["source"] = "fixture://bars?credential=SYNTHETIC_REDACTION_MARKER"
        self.reject(case, "FIXTURE_SOURCE_REQUIRED")

    def test_missing_source_hash(self):
        case = fixture_case(); case["bars"][0]["source_hash"] = None
        self.reject(case, "HASH_INVALID")

    def test_owner_policy_version_not_fixture(self):
        case = fixture_case(); case["bindings"]["strategy_version"] = "OWNER_APPROVED"
        self.reject(case, "EXPLICIT_FIXTURE_VERSION_REQUIRED")

    def test_review_stale_capture_hash(self):
        case = fixture_case(); case["bars"][0]["close"] = "10.40"
        seal_fixture_originals(case)
        self.reject(case, "REVIEW_VERSION_BINDING_DRIFT", reseal=False)

    def test_review_strategy_hash_drift(self):
        case = fixture_case(); case["review"]["reviewed_strategy_hash"] = digest({"wrong": 1})
        self.reject(case, "REVIEW_VERSION_BINDING_DRIFT", reseal=False)

    def test_review_before_capture(self):
        case = fixture_case(); case["review"]["reviewed_at"] = instant("2026-10-08", "15:00:03")
        self.reject(case, "REVIEW_BEFORE_CAPTURE_OR_FUTURE")

    def test_review_after_cutoff(self):
        case = fixture_case(); case["review"]["reviewed_at"] = "2026-10-08T15:01:00.000000001+08:00"
        self.reject(case, "REVIEW_BEFORE_CAPTURE_OR_FUTURE")

    def test_real_review_claim_not_fixture(self):
        case = fixture_case(); case["review"]["conclusion"] = "ADMITTED"
        self.reject(case, "FIXTURE_REVIEW_REQUIRED")

    def test_llm_case_approval_rejected(self):
        case = fixture_case(); case["authorization"]["kind"] = "LLM_APPROVE"
        self.reject(case, "LLM_NOT_SYNTHETIC_HUMAN")

    def test_future_authorization_not_pre_capture(self):
        case = fixture_case(); case["authorization"]["issued_at"] = instant("2026-10-08", "09:30:01")
        self.reject(case, "AUTHORIZATION_FUTURE_OR_EXPIRED")

    def test_expiry_at_cutoff(self):
        case = fixture_case(); case["authorization"]["expires_at"] = case["decision_cutoff"]
        self.reject(case, "AUTHORIZATION_FUTURE_OR_EXPIRED")

    def test_capture_identity_actual_string_rejected(self):
        case = fixture_case(); case["capture_id"] = "actual-capture"
        self.reject(case, "FIXTURE_ID_REQUIRED")

    def test_conflicting_listing_status(self):
        case = fixture_case(); case["statuses"][0]["delisted"] = True
        self.reject(case, "CONFLICTING_STATUS")

    def test_conflicting_price_limits(self):
        case = fixture_case(); case["statuses"][0].update(limit_up="9", limit_down="11")
        self.reject(case, "CONFLICTING_LIMITS")

    def test_status_absent_enum_not_false(self):
        case = fixture_case(); case["statuses"][0]["suspended"] = None
        self.reject(case, "STATUS_ENUM_INVALID")

    def test_unknown_boolean_integer_reject(self):
        case = fixture_case(); case["statuses"][0]["st"] = 0
        self.reject(case, "STATUS_ENUM_INVALID")

    def test_no_extra_order_or_approval_fields(self):
        for key in ("OrderIntent", "Signal", "Approval", "Fill", "Candidate", "human_approved", "productionGate"):
            case = fixture_case(); case[key] = True
            self.reject(case, "CAPTURE_SHAPE_INVALID", reseal=False)

    def test_strategy_namespace_isolation(self):
        for namespace in ("CORE_40", "LOCAL_FORWARD_PAPER_FIXTURE:EVENT_3", "LOCAL_FORWARD_PAPER_FIXTURE:RESEARCH_6_18M"):
            case = fixture_case(); case["namespace"] = namespace
            self.reject(case, "NAMESPACE_OR_VERSION_DRIFT")

    def test_synthetic_marker_cannot_actual(self):
        case = fixture_case(); case["provenance"] = "ACTUAL_OWNER_APPROVED"
        self.reject(case, "SYNTHETIC_CAPTURE_REQUIRED", reseal=False)

    def test_fixture_review_fingerprint_never_authority(self):
        self.assertTrue(a.fixture_capture_hash(fixture_case()).startswith("sha256:"))
        with self.assertRaisesRegex(ValueError, "REGISTERED_FIXTURE_APPROVAL_REQUIRED"):
            a._approval({"reviewed_capture_hash": a.fixture_capture_hash(fixture_case()), "actor": "HUMAN"})

    def test_old_capture_shape_version_not_silently_upgraded(self):
        case = fixture_case(); case["version"] = "1.0.0"
        self.reject(case, "NAMESPACE_OR_VERSION_DRIFT")

    def test_preliminary_reviewer_prior_original_hash_relabel_counterexample(self):
        first, second = fixture_case(), fixture_case("2026-10-09", "B-2")
        for domain in ("bars", "statuses"):
            for old, new in zip(first[domain], second[domain]):
                new["source_hash"] = old["source_hash"]
                new["source"] = old["source"]
        second["calendar"]["source_hash"] = first["calendar"]["source_hash"]
        second["calendar"]["source"] = first["calendar"]["source"]
        # Same refresh function used by R1: it cannot regenerate originals.
        refresh_review(second)
        self.reject(second, "SOURCE_ORIGINAL_HASH_INVALID", reseal_originals=False)

    def test_prior_original_payload_and_hash_cannot_relabel_session(self):
        first, second = fixture_case(), fixture_case("2026-10-09", "B-2")
        for domain in ("bars", "statuses"):
            for old, new in zip(first[domain], second[domain]):
                for key in ("source", "source_hash", "source_payload"):
                    new[key] = copy.deepcopy(old[key])
        for key in ("source", "source_hash", "source_payload"):
            second["calendar"][key] = copy.deepcopy(first["calendar"][key])
        self.reject(second, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT", reseal_originals=False)

    def test_raw_bar_value_cannot_change_outer_wrapper_only(self):
        case = fixture_case(); case["bars"][0]["close"] = "10.40"
        self.reject(case, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT", reseal_originals=False)

    def test_bar_symbol_cannot_swap_source_originals(self):
        case = fixture_case()
        case["bars"][0]["source_payload"] = copy.deepcopy(case["bars"][1]["source_payload"])
        case["bars"][0]["source_hash"] = case["bars"][1]["source_hash"]
        self.reject(case, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT", reseal_originals=False)

    def test_raw_bar_units_cannot_change_original_payload_only(self):
        case = fixture_case(); original = case["bars"][0]["source_payload"]
        original["row"]["units"]["volume"] = "LOTS"
        case["bars"][0]["source_hash"] = digest(original)
        self.reject(case, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT", reseal_originals=False)

    def test_bar_clock_cannot_shift_wrapper_only(self):
        case = fixture_case(); case["bars"][0]["clocks"]["retrieved_at"] = "2026-10-08T15:00:03.000000001+08:00"
        self.reject(case, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT", reseal_originals=False)

    def test_source_uri_cannot_shift_wrapper_only(self):
        case = fixture_case(); case["bars"][0]["source"] = "fixture://different-source"
        self.reject(case, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT", reseal_originals=False)

    def test_original_data_mutation_without_hash_update_rejects(self):
        case = fixture_case(); case["bars"][0]["source_payload"]["row"]["close"] = "10.40"
        self.reject(case, "SOURCE_ORIGINAL_HASH_INVALID", reseal_originals=False)

    def test_calendar_original_is_actual_open_observation_not_monthly_plan(self):
        case = fixture_case(); case["calendar"]["source_payload"]["domain"] = "MONTHLY_CALENDAR_PLAN"
        case["calendar"]["source_hash"] = digest(case["calendar"]["source_payload"])
        self.reject(case, "SOURCE_ORIGINAL_KIND_OR_DOMAIN_DRIFT", reseal_originals=False)

    def test_status_original_cannot_replace_unknown_by_false_outer_only(self):
        case = fixture_case(); case["statuses"][0]["suspended"] = False
        self.reject(case, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT", reseal_originals=False)

    def test_source_payload_required_bar(self):
        case = fixture_case(); del case["bars"][0]["source_payload"]
        self.reject(case, "BAR_SHAPE_INVALID", reseal_originals=False)

    def test_source_payload_required_status(self):
        case = fixture_case(); del case["statuses"][0]["source_payload"]
        self.reject(case, "STATUS_SHAPE_INVALID", reseal_originals=False)

    def test_source_payload_required_calendar(self):
        case = fixture_case(); del case["calendar"]["source_payload"]
        self.reject(case, "CALENDAR_OBSERVATION_REQUIRED", reseal_originals=False)

    def test_actual_original_marker_cannot_fixture(self):
        case = fixture_case(); case["bars"][0]["source_payload"]["provenance"] = "ACTUAL"
        case["bars"][0]["source_hash"] = digest(case["bars"][0]["source_payload"])
        self.reject(case, "SOURCE_ORIGINAL_KIND_OR_DOMAIN_DRIFT", reseal_originals=False)

    def test_raw_source_payload_extra_native_field_rejected(self):
        case = fixture_case(); case["bars"][0]["source_payload"]["Order"] = {"actor": "HUMAN"}
        case["bars"][0]["source_hash"] = digest(case["bars"][0]["source_payload"])
        self.reject(case, "SOURCE_ORIGINAL_REQUIRED", reseal_originals=False)

    def test_genuine_new_synthetic_source_original_session_passes(self):
        first, second = fixture_case(), fixture_case("2026-10-09", "B-2")
        self.assertNotEqual(first["bars"][0]["source_hash"], second["bars"][0]["source_hash"])
        self.assertEqual(second["bars"][0]["source_payload"]["row"]["session_date"], "2026-10-09")
        result = a.validate_fixture_capture(second)
        self.assertTrue(result["fresh_session_fixture_valid"])
        self.assertEqual(result["version"], "1.0.1")
        self.assertFalse(result["actual_snapshot_b_created"])


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wave-f-activation-")
        self.directory = Path(self.temp.name).resolve()
        self.directory.chmod(0o700)
        self.path = self.directory / "private.wave-f.fixture.sqlite3"
        self.genesis = a.create_fixture_ledger(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def append(self, case=None, head=None):
        handle = a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", case or fixture_case())
        return a.append_fixture_day(self.path, handle, head or a.inspect_fixture_ledger(self.path)["head_hash"])

    def test_exclusive_creation_and_permissions(self):
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.genesis["fixture_day_count"], 0)
        self.assertEqual(self.genesis["actual_forward_days"], 0)
        with self.assertRaisesRegex(ValueError, "STORE_ALREADY_EXISTS"):
            a.create_fixture_ledger(self.path)

    def test_wrong_suffix_rejected(self):
        with self.assertRaisesRegex(ValueError, "FIXTURE_PATH_INVALID"):
            a.create_fixture_ledger(self.directory / "runtime.sqlite3")

    def test_relative_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "FIXTURE_PATH_INVALID"):
            a.create_fixture_ledger(Path("bad.wave-f.fixture.sqlite3"))

    def test_public_parent_rejected(self):
        public = self.directory / "public"; public.mkdir(mode=0o755)
        with self.assertRaisesRegex(ValueError, "PRIVATE_PARENT_REQUIRED"):
            a.create_fixture_ledger(public / "bad.wave-f.fixture.sqlite3")

    def test_public_file_rejected(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "PRIVATE_STORE_REQUIRED"):
            a.inspect_fixture_ledger(self.path)

    def test_symlink_store_rejected(self):
        p = self.directory / "link.wave-f.fixture.sqlite3"; p.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, "FIXTURE_PATH_INVALID"):
            a.inspect_fixture_ledger(p)

    def test_one_day_no_money_no_native_order(self):
        value = self.append()
        self.assertEqual(value["fixture_day_count"], 1)
        self.assertEqual(value["actual_forward_days"], 0)
        record = value["records"][0]
        self.assertEqual(record["actual_policies"], {"account": UNSET, "cost": UNSET, "risk": UNSET})
        self.assertEqual(record["decision"], "NO_DECISION")
        self.assertFalse(record["safe_to_trade"])
        conn = sqlite3.connect(self.path)
        self.assertEqual({row[0] for row in conn.execute("SELECT name FROM sqlite_schema WHERE type='table'")}, {"fixture_metadata", "fixture_days", "fixture_failed_attempts"})
        conn.close()

    def test_two_days_hash_chain_reopen(self):
        first = self.append()
        second = self.append(fixture_case("2026-10-09", "B-2"))
        self.assertEqual(second["fixture_day_count"], 2)
        self.assertEqual(second["records"][1]["previous_hash"], first["head_hash"])
        self.assertEqual(a.inspect_fixture_ledger(self.path), second)
        self.assertEqual(second["actual_forward_days"], 0)

    def test_duplicate_day_rejected(self):
        self.append()
        with self.assertRaisesRegex(ValueError, "DUPLICATE_PAPER_DAY"):
            self.append(fixture_case(identifier="B-another"))
        self.assertEqual(a.inspect_fixture_ledger(self.path)["fixture_day_count"], 1)

    def test_duplicate_capture_id_across_dates_rejected(self):
        self.append()
        case = fixture_case("2026-10-09", "B-1"); case["authorization"]["authorization_id"] = "fixture:new-auth"
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CAPTURE_ID"):
            self.append(case)

    def test_duplicate_authorization_id_rejected(self):
        self.append()
        case = fixture_case("2026-10-09", "B-2"); case["authorization"]["authorization_id"] = "fixture:human-B-1"
        with self.assertRaisesRegex(ValueError, "DUPLICATE_AUTHORIZATION_ID"):
            self.append(case)

    def test_old_head_rejected_and_approval_not_consumed(self):
        self.append()
        case = fixture_case("2026-10-09", "B-2")
        handle = a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", case)
        with self.assertRaisesRegex(ValueError, "STALE_EXPECTED_HEAD"):
            a.append_fixture_day(self.path, handle, self.genesis["head_hash"])
        result = a.append_fixture_day(self.path, handle, a.inspect_fixture_ledger(self.path)["head_hash"])
        self.assertEqual(result["fixture_day_count"], 2)

    def test_duplicate_handle_not_reusable(self):
        handle = a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", fixture_case())
        first = a.append_fixture_day(self.path, handle, self.genesis["head_hash"])
        with self.assertRaisesRegex(ValueError, "APPROVAL_ALREADY_USED"):
            a.append_fixture_day(self.path, handle, first["head_hash"])

    def test_handle_copy_and_json_not_authority(self):
        handle = a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", fixture_case())
        for fake in (copy.copy(handle), copy.deepcopy(handle), json.loads(canonical(handle._body))):
            with self.assertRaises(ValueError):
                a.append_fixture_day(self.path, fake, self.genesis["head_hash"])

    def test_unregistered_handle_not_authority(self):
        handle = a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", fixture_case())
        fake = a.FixtureApproval(handle.approval_id, handle._body)
        with self.assertRaisesRegex(ValueError, "APPROVAL_IDENTITY_OR_MUTATION"):
            a.append_fixture_day(self.path, fake, self.genesis["head_hash"])

    def test_llm_issuer_rejected(self):
        for actor in ("LLM", "APPROVE", "HUMAN", True, "OWNER"):
            with self.assertRaisesRegex(ValueError, "LLM_NOT_SYNTHETIC_HUMAN"):
                a.issue_fixture_approval(actor, fixture_case())

    def test_handle_body_mutation_rejected(self):
        handle = a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", fixture_case())
        handle._body["case"]["bars"][0]["close"] = "10.40"
        with self.assertRaisesRegex(ValueError, "APPROVAL_IDENTITY_OR_MUTATION"):
            a.append_fixture_day(self.path, handle, self.genesis["head_hash"])

    def test_detached_original_case_mutation_no_effect(self):
        case = fixture_case(); handle = a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", case)
        case["bars"][0]["close"] = "99"
        result = a.append_fixture_day(self.path, handle, self.genesis["head_hash"])
        self.assertEqual(result["records"][0]["case"]["bars"][0]["close"], "10.30")

    def test_hidden_strategy_change_between_days_rejected(self):
        self.append()
        case = fixture_case("2026-10-09", "B-2"); case["bindings"]["strategy_hash"] = digest({"changed": True}); refresh_review(case)
        with self.assertRaisesRegex(ValueError, "FROZEN_POLICY_OR_ANCHOR_DRIFT"):
            self.append(case)

    def test_hidden_source_version_between_days_rejected(self):
        self.append()
        case = fixture_case("2026-10-09", "B-2"); case["bindings"]["source_version"] = "fixture-source-v2"
        for row in [case["calendar"], *case["bars"], *case["statuses"]]:
            row["source_version"] = "fixture-source-v2"
        refresh_review(case, originals=True)
        with self.assertRaisesRegex(ValueError, "FROZEN_POLICY_OR_ANCHOR_DRIFT"):
            self.append(case)

    def test_anchor_change_between_days_rejected(self):
        self.append()
        case = fixture_case("2026-10-09", "B-2"); case["snapshot_a"]["capture_id"] = "fixture:A-new"
        case["snapshot_a"]["content_hash"] = digest({key: value for key, value in case["snapshot_a"].items() if key != "content_hash"})
        refresh_review(case)
        with self.assertRaisesRegex(ValueError, "FROZEN_POLICY_OR_ANCHOR_DRIFT"):
            self.append(case)

    def test_session_order_rejected(self):
        self.append(fixture_case("2026-10-09", "B-2"))
        with self.assertRaisesRegex(ValueError, "SESSION_ORDER_INVALID"):
            self.append(fixture_case())

    def test_concurrent_same_head_has_exactly_one_winner(self):
        handles = [a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", fixture_case(identifier="concurrent-" + str(i))) for i in range(2)]
        def invoke(handle):
            try:
                a.append_fixture_day(self.path, handle, self.genesis["head_hash"])
                return "PASS"
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(invoke, handles))
        self.assertEqual(values.count("PASS"), 1)
        self.assertIn("WF_ACT_STALE_EXPECTED_HEAD", values)
        self.assertEqual(a.inspect_fixture_ledger(self.path)["fixture_day_count"], 1)

    def test_transaction_rollback_after_insert(self):
        handle = a.issue_fixture_approval("SYNTHETIC_HUMAN_USER", fixture_case())
        original = a._inspect
        count = 0
        def failing_inspect(*args):
            nonlocal count
            count += 1
            if count == 2:
                raise ValueError("WF_ACT_SYNTHETIC_AFTER_INSERT_FAILURE")
            return original(*args)
        with patch.object(a, "_inspect", failing_inspect):
            with self.assertRaisesRegex(ValueError, "SYNTHETIC_AFTER_INSERT_FAILURE"):
                a.append_fixture_day(self.path, handle, self.genesis["head_hash"])
        self.assertEqual(a.inspect_fixture_ledger(self.path), self.genesis)
        self.assertEqual(a.append_fixture_day(self.path, handle, self.genesis["head_hash"])["fixture_day_count"], 1)

    def test_failed_capture_reason_persists_without_day_or_payload(self):
        case = fixture_case(); case["bars"].pop()
        with self.assertRaisesRegex(ValueError, "EOD_BAR_COVERAGE_UNKNOWN"):
            a.attempt_fixture_day(self.path, "SYNTHETIC_HUMAN_USER", case, self.genesis["head_hash"])
        value = a.inspect_fixture_ledger(self.path)
        self.assertEqual(value["head_hash"], self.genesis["head_hash"])
        self.assertEqual(value["fixture_day_count"], 0)
        self.assertEqual(value["failed_capture_count"], 1)
        failure = value["failed_captures"][0]
        self.assertEqual(failure["reason_code"], "WF_ACT_EOD_BAR_COVERAGE_UNKNOWN")
        self.assertFalse(failure["untrusted_payload_retained"])
        self.assertFalse(failure["untrusted_payload_hash_retained"])
        self.assertNotIn("case", failure)

    def test_failed_capture_untrusted_marker_not_persisted(self):
        case = fixture_case(); case["untrusted_extra"] = "SYNTHETIC_REDACTION_MARKER_DO_NOT_RETAIN"
        with self.assertRaises(ValueError):
            a.attempt_fixture_day(self.path, "SYNTHETIC_HUMAN_USER", case, self.genesis["head_hash"])
        self.assertNotIn(b"SYNTHETIC_REDACTION_MARKER_DO_NOT_RETAIN", self.path.read_bytes())
        self.assertNotIn(b"untrusted_extra", self.path.read_bytes())

    def test_multiple_failed_captures_chain_then_success(self):
        for actor in ("LLM", "OWNER"):
            with self.assertRaises(ValueError):
                a.attempt_fixture_day(self.path, actor, fixture_case(), self.genesis["head_hash"])
        failed = a.inspect_fixture_ledger(self.path)
        self.assertEqual(failed["failed_capture_count"], 2)
        self.assertEqual(failed["failed_captures"][1]["previous_hash"], failed["failed_captures"][0]["attempt_hash"])
        result = a.attempt_fixture_day(self.path, "SYNTHETIC_HUMAN_USER", fixture_case(), self.genesis["head_hash"])
        self.assertEqual(result["fixture_day_count"], 1)
        self.assertEqual(result["failed_capture_count"], 2)
        self.assertEqual(result["actual_forward_days"], 0)

    def test_recovery_read_only_and_new_approval_required(self):
        final = self.append()
        before = self.path.read_bytes()
        recovered = a.recover_fixture_ledger(self.path, final["head_hash"])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(recovered["new_approval_required_for_append"])
        self.assertFalse(recovered["live_authority"])
        with self.assertRaises(ValueError):
            a.append_fixture_day(self.path, recovered, final["head_hash"])

    def test_recovery_wrong_head_no_repair(self):
        self.append()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "RECOVERY_HEAD_MISMATCH"):
            a.recover_fixture_ledger(self.path, self.genesis["head_hash"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_fresh_process_reopen_and_append(self):
        self.append()
        script = """import json,sys\nfrom wave_f import activation as a\nfrom wave_f.tests.test_activation import fixture_case\np=sys.argv[1]\nx=a.recover_fixture_ledger(p)\nh=a.issue_fixture_approval('SYNTHETIC_HUMAN_USER',fixture_case('2026-10-09','restart-2'))\ny=a.append_fixture_day(p,h,x['result']['head_hash'])\nprint(json.dumps({'fixture_days':y['fixture_day_count'],'actual_days':y['actual_forward_days'],'live_authority':y['live_authority']}))\n"""
        completed = subprocess.run([sys.executable, "-B", "-c", script, str(self.path)], cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"fixture_days": 2, "actual_days": 0, "live_authority": False})

    def test_copied_store_rejects_path_binding(self):
        self.append()
        copied = self.directory / "copy.wave-f.fixture.sqlite3"; shutil.copyfile(self.path, copied); copied.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "STORE_BINDING_DRIFT"):
            a.inspect_fixture_ledger(copied)

    def test_display_mutation_no_store_or_authority_effect(self):
        value = self.append()
        value["records"][0]["decision"] = "ORDER"
        fresh = a.inspect_fixture_ledger(self.path)
        self.assertEqual(fresh["records"][0]["decision"], "NO_DECISION")
        with self.assertRaises(ValueError):
            a.append_fixture_day(self.path, value, fresh["head_hash"])

    def test_sql_day_update_and_delete_guards(self):
        self.append()
        conn = sqlite3.connect(self.path)
        for sql in ("UPDATE fixture_days SET session_date='2026-10-09'", "DELETE FROM fixture_days"):
            with self.assertRaisesRegex(sqlite3.DatabaseError, "APPEND_ONLY"):
                conn.execute(sql)
        conn.close()
        self.assertEqual(a.inspect_fixture_ledger(self.path)["fixture_day_count"], 1)

    def test_sql_metadata_immutable(self):
        conn = sqlite3.connect(self.path)
        for sql in ("UPDATE fixture_metadata SET body_hash='x'", "DELETE FROM fixture_metadata", "INSERT INTO fixture_metadata VALUES(2,'x','x')"):
            with self.assertRaisesRegex(sqlite3.DatabaseError, "IMMUTABLE"):
                conn.execute(sql)
        conn.close()

    def test_raw_sql_insert_needs_capability(self):
        conn = sqlite3.connect(self.path)
        with self.assertRaises(sqlite3.DatabaseError):
            conn.execute("INSERT INTO fixture_failed_attempts VALUES(1,'fake','fake','fake','{}')")
        conn.close()
        self.assertEqual(a.inspect_fixture_ledger(self.path)["failed_capture_count"], 0)

    def test_schema_mutation_blocks_without_repair(self):
        conn = sqlite3.connect(self.path); conn.execute("CREATE TABLE native_orders(x)"); conn.commit(); conn.close()
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "STORE_SCHEMA_DRIFT"):
            a.recover_fixture_ledger(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_schema_trigger_removal_blocks(self):
        conn = sqlite3.connect(self.path); conn.execute("DROP TRIGGER fixture_days_no_update"); conn.commit(); conn.close()
        with self.assertRaisesRegex(ValueError, "STORE_SCHEMA_DRIFT"):
            a.inspect_fixture_ledger(self.path)

    def test_same_length_data_tamper_detected(self):
        self.append()
        raw = self.path.read_bytes()
        self.assertIn(b'"close":"10.30"', raw)
        changed = raw.replace(b'"close":"10.30"', b'"close":"10.40"', 1)
        self.assertEqual(len(raw), len(changed))
        self.path.write_bytes(changed)
        with self.assertRaises(ValueError):
            a.inspect_fixture_ledger(self.path)

    def test_failed_attempt_hash_tamper_detected(self):
        with self.assertRaises(ValueError):
            a.attempt_fixture_day(self.path, "LLM", fixture_case(), self.genesis["head_hash"])
        raw = self.path.read_bytes(); marker = b"WF_ACT_LLM_NOT_SYNTHETIC_HUMAN"
        self.assertIn(marker, raw)
        self.path.write_bytes(raw.replace(marker, b"WF_ACT_XLM_NOT_SYNTHETIC_HUMAN", 1))
        with self.assertRaises(ValueError):
            a.recover_fixture_ledger(self.path)

    def test_actual_entrypoints_ignore_all_caller_unlock_flags(self):
        for entry in (a.run_snapshot_b, a.run_real_forward, a.append_actual_session):
            with self.assertRaisesRegex(ValueError, "NOT_AUTHORIZED"):
                entry(fixture_case(), actor="HUMAN", owner_approved=True, productionGate=True, source_admitted=True, token_present=True, approval_hash=digest({"fake": True}), path=str(self.path))
        self.assertEqual(a.inspect_fixture_ledger(self.path), self.genesis)

    def test_stale_original_relabel_cannot_append_next_day(self):
        self.append()
        first, second = fixture_case(), fixture_case("2026-10-09", "B-2")
        for old, new in zip(first["bars"], second["bars"]):
            for key in ("source", "source_hash", "source_payload"):
                new[key] = copy.deepcopy(old[key])
        refresh_review(second)
        head = a.inspect_fixture_ledger(self.path)["head_hash"]
        with self.assertRaisesRegex(ValueError, "SOURCE_ORIGINAL_ROW_BINDING_DRIFT"):
            a.attempt_fixture_day(self.path, "SYNTHETIC_HUMAN_USER", second, head)
        result = a.inspect_fixture_ledger(self.path)
        self.assertEqual(result["fixture_day_count"], 1)
        self.assertEqual(result["head_hash"], head)
        self.assertEqual(result["failed_capture_count"], 1)
        self.assertEqual(result["actual_forward_days"], 0)


class ReadinessTests(unittest.TestCase):
    def test_snapshot_requirements_more_than_new_human_authorization(self):
        value = a.snapshot_readiness(); body = value["body"]
        self.assertFalse(body["only_human_authorization_missing"])
        self.assertFalse(body["actual_fresh_session_observed"])
        self.assertFalse(body["actual_eod_observed"])
        self.assertFalse(body["actual_snapshot_b_created"])
        self.assertFalse(body["scheduled"])
        self.assertFalse(value["live_authority"])
        self.assertEqual(value["actual_forward_days"], 0)
        self.assertEqual(body["exact_symbols"], list(SYMBOLS))
        self.assertEqual(body["formal_source_admission"], "BLOCKED_PROVIDER_LICENSE_TRANSPORT_UNVERIFIED")

    def test_money_unknown_does_not_block_no_decision_engineering(self):
        value = a.forward_readiness(); body = value["body"]
        self.assertFalse(body["real_money_parameters_block_no_decision_engineering"])
        self.assertEqual(body["real_account_parameters"], {"account": UNSET, "cost": UNSET, "risk": UNSET})
        self.assertFalse(body["native_order_fields_supported"])
        self.assertFalse(body["synthetic_days_count_as_actual"])
        self.assertFalse(body["execution_or_native_promotion"])
        self.assertFalse(body["actual_record_appended"])
        self.assertEqual(value["actual_forward_days"], 0)

    def test_readiness_is_deterministic_data_only(self):
        self.assertEqual(canonical(a.snapshot_readiness()), canonical(a.snapshot_readiness()))
        self.assertEqual(canonical(a.forward_readiness()), canonical(a.forward_readiness()))
        self.assertFalse(a.forward_readiness()["body"]["privileged_rewrite_or_hostile_interpreter_proof"])

    def test_fixture_detector_deterministic_no_actual_days(self):
        case = fixture_case()
        self.assertEqual(canonical(a.validate_fixture_capture(case)), canonical(a.validate_fixture_capture(copy.deepcopy(case))))
        self.assertEqual(a.validate_fixture_capture(case)["actual_forward_days"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
