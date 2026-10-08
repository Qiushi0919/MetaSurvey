"""Independent raw-reopen review and isolated NO_DECISION forward stores.

Simulation and actual state are separate namespaces and file types.  Actual
authority is exclusively external enrolled Owner/Reviewer signatures.  Neither
producer JSON, a display hash, nor an offline fixture is an authority.
"""
from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import uuid

from .common import ARCHIVE, ROOT, SYMBOLS, canonical, digest, hash_value, metadata, policy, bindings, ref, reopen, require, seal, timestamp, decimal_string, UNSET
from .common import sha

ACTUAL_NAMESPACE = "ACTUAL_FORWARD_NO_DECISION"
SIMULATION_NAMESPACE = "OFFLINE_SIMULATION_FORWARD_NO_DECISION"
_NO = {"NO_ORDER": True, "NO_BROKER": True, "NO_MONEY": True,
       "NO_NATIVE_SIGNAL_APPROVAL_ORDER_FILL": True,
       "NO_CLOUD_MODEL_EXPORT_REDISTRIBUTION": True, "NO_PRODUCTION": True}
_LOCK = threading.RLock()


def _exact(value, fields, reason):
    require(type(value) is dict and set(value) == set(fields), reason)
    canonical(value)


def _json(raw, numeric_strings=False):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "WH_FORWARD_DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_float=str if numeric_strings else float,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("WH_FORWARD_NONFINITE_JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("WH_FORWARD_INVALID_JSON") from None


def _unseal(value):
    require(type(value) is dict and "content_hash" in value, "WH_FORWARD_SEALED_OBJECT_REQUIRED")
    hash_value(value["content_hash"])
    require(value["content_hash"] == digest({k: v for k, v in value.items() if k != "content_hash"}), "WH_FORWARD_CONTENT_HASH_DRIFT")
    return value


def _day(value):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d\d-\d\d", value), "WH_FORWARD_SESSION_DATE_REQUIRED")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("WH_FORWARD_SESSION_DATE_REQUIRED") from None


def _auth():
    from . import auth
    return auth


_PLAN = {"version", "kind", "mode", "session", "symbols", "endpoint", "source_identity", "source_schema_version", "bindings", "jobs", "session_evidence_ref", "snapshot_a_ref", "plan_hash"}
_MANIFEST = {"version", "kind", "mode", "capture_id", "plan", "plan_hash", "policy_hash", "strategy_hash", "source_schema_version", "source_identity", "endpoint", "session", "symbols", "started_at", "completed_at", "clock_precision", "jobs", "source_session_evidence_ref", "snapshot_a_ref", "capture_authorization", "coverage", "status_unknowns", "source_admission", "historical_visibility_proven", "safe_to_trade", "decision", "actual_forward_days", "content_hash"}
_CLOCK = {"version", "kind", "mode", "capture_id", "job_id", "request_identity", "source_identity", "source_schema_version", "session", "started_at", "retrieved_at", "retrieved_precision", "event_time", "event_precision", "published_at", "published_precision", "source_available_at", "source_available_precision", "current_available_at", "current_available_precision", "visibility_basis", "historical_visibility_proven", "source_response_hash"}
_JOB = {"job_id", "api_name", "params", "fields", "max_rows", "mandatory", "symbol", "units", "adjustment_state"}
_FIELDS = {
    "trade_cal": ["exchange", "cal_date", "is_open", "pretrade_date"],
    "daily": ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"],
    "stock_basic": ["ts_code", "symbol", "name", "exchange", "curr_type", "list_status", "list_date", "delist_date"],
    "suspend_d": ["ts_code", "trade_date", "suspend_timing", "suspend_type"],
    "stk_limit": ["ts_code", "trade_date", "pre_close", "up_limit", "down_limit"],
}
_UNITS = {
    "trade_cal": {"is_open": "ENUM_0_1"},
    "daily": {"open": "CNY", "high": "CNY", "low": "CNY", "close": "CNY", "pre_close": "PROVIDER_EX_RIGHTS_REFERENCE_CNY", "change": "CNY", "pct_chg": "PERCENT", "vol": "LOT_HAND", "amount": "THOUSAND_CNY"},
    "stock_basic": {}, "suspend_d": {},
    "stk_limit": {"pre_close": "PROVIDER_REFERENCE_CNY", "up_limit": "CNY", "down_limit": "CNY"},
}
_ADJUSTMENT = {"trade_cal": "NOT_APPLICABLE", "daily": "RAW_UNADJUSTED_OHLC_PRE_CLOSE_EX_RIGHTS_REFERENCE",
               "stock_basic": "NOT_APPLICABLE", "suspend_d": "EVENT_RECORD_NOT_COMPLETE_CURRENT_STATE",
               "stk_limit": "PROVIDER_LIMIT_OBSERVATION_NOT_REGIME_PROOF"}


def _precision(value):
    timestamp(value)
    fractional = re.search(r"\.(\d+)(?:Z|[+-]\d\d:\d\d)$", value)
    width = len(fractional.group(1)) if fractional else 0
    return "SECOND" if width == 0 else "MILLISECOND" if width <= 3 else "MICROSECOND" if width <= 6 else "NANOSECOND"


def _local_day(value):
    timestamp(value)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=8))).date().isoformat()


def _validate_plan_independently(plan, actual):
    _exact(plan, _PLAN, "WH_FORWARD_PLAN_SHAPE")
    p = policy(); session = _day(plan["session"]).isoformat()
    mode = "LOCAL_ONLY_NON_TRADEABLE_CURRENT_OBSERVATION" if actual else "OFFLINE_SIMULATION"
    require(plan["version"] == "1.0.0" and plan["kind"] == "BOUNDED_CURRENT_CAPTURE_PLAN" and plan["mode"] == mode and plan["symbols"] == list(SYMBOLS) and plan["endpoint"] == p["endpoint"] and plan["source_identity"] == p["source_identity"] and plan["source_schema_version"] == p["source_schema_version"] and plan["bindings"] == bindings(), "WH_FORWARD_PLAN_BINDING_DRIFT")
    require(plan["plan_hash"] == digest({k: v for k, v in plan.items() if k != "plan_hash"}), "WH_FORWARD_PLAN_HASH_DRIFT")
    require(type(plan["jobs"]) is list and len(plan["jobs"]) == 13, "WH_FORWARD_PLAN_JOB_COUNT")
    expected_order = [("trade_cal", None)] + [(api, symbol) for api in ("daily", "stock_basic", "suspend_d", "stk_limit") for symbol in SYMBOLS]
    for job, (api, symbol) in zip(plan["jobs"], expected_order):
        _exact(job, _JOB, "WH_FORWARD_JOB_SHAPE")
        params = {"exchange": "SSE", "start_date": session.replace("-", ""), "end_date": session.replace("-", "")} if api == "trade_cal" else {"ts_code": symbol}
        if api in ("daily", "suspend_d", "stk_limit"): params["trade_date"] = session.replace("-", "")
        require(job["api_name"] == api and job["symbol"] == symbol and job["job_id"] == ("trade_cal-SSE" if symbol is None else api + "-" + symbol) and job["params"] == params and job["fields"] == _FIELDS[api] and type(job["mandatory"]) is bool and job["mandatory"] == (api in ("trade_cal", "daily")) and type(job["max_rows"]) is int and job["max_rows"] == (8 if api == "suspend_d" else 1) and job["units"] == _UNITS[api] and job["adjustment_state"] == _ADJUSTMENT[api], "WH_FORWARD_JOB_POLICY_SCOPE_DRIFT")
    return plan


def _number(value, positive=False, nonnegative=False):
    require(type(value) in (str, int), "WH_FORWARD_NATIVE_DECIMAL_TYPE")
    result = decimal_string(str(value), False)
    require(len(result.as_tuple().digits) <= 100 and abs(result.as_tuple().exponent) <= 100 and (not positive or result > 0) and (not nonnegative or result >= 0), "WH_FORWARD_NATIVE_DECIMAL_RANGE")
    return result


def _parse_original(job, raw, session):
    """Independent native parsing; no producer parser or normalized rows used."""
    require(type(raw) is bytes and 0 < len(raw) <= 2 * 1024 * 1024, "WH_FORWARD_RAW_SIZE")
    doc = _json(raw, True)
    _exact(doc, {"code", "msg", "data"}, "WH_FORWARD_NATIVE_RESPONSE_SHAPE")
    require(type(doc["code"]) is int and (doc["msg"] is None or type(doc["msg"]) is str), "WH_FORWARD_NATIVE_CODE")
    if doc["code"] != 0:
        denied = any(x in (doc["msg"] or "").lower() for x in ("没有权限", "无权限", "权限不足", "积分不足", "permission denied", "entitlement not granted", "insufficient points"))
        return {"status": "API_DENIED" if denied else "API_ERROR", "reason_code": "ENTITLEMENT_NOT_GRANTED" if denied else "SOURCE_API_ERROR", "rows": [], "row_count": None}
    _exact(doc["data"], {"fields", "items"}, "WH_FORWARD_NATIVE_DATA_SHAPE")
    fields, items = doc["data"]["fields"], doc["data"]["items"]
    require(type(fields) is list and all(type(v) is str for v in fields) and len(fields) == len(set(fields)) and type(items) is list and (set(fields) == set(_FIELDS[job["api_name"]]) or not fields and not items) and len(items) <= job["max_rows"], "WH_FORWARD_NATIVE_FIELDS_ROWS")
    rows, seen = [], set()
    for values in items:
        require(type(values) is list and len(values) == len(fields), "WH_FORWARD_NATIVE_ROW_SHAPE")
        row = dict(zip(fields, values)); row_id = digest(row)
        require(row_id not in seen, "WH_FORWARD_DUPLICATE_NATIVE_ROW"); seen.add(row_id)
        if job["api_name"] == "trade_cal":
            require(row["exchange"] == "SSE" and row["cal_date"] == session.replace("-", "") and type(row["is_open"]) is int and row["is_open"] == 1, "WH_FORWARD_SESSION_CALENDAR_CONFLICT")
        else:
            require(row["ts_code"] == job["symbol"], "WH_FORWARD_NATIVE_SYMBOL_DRIFT")
            if "trade_date" in row: require(row["trade_date"] == session.replace("-", ""), "WH_FORWARD_STALE_NATIVE_SESSION")
        if job["api_name"] == "daily":
            o, h, l, c = (_number(row[k], True) for k in ("open", "high", "low", "close"))
            require(l <= min(o, c) <= max(o, c) <= h, "WH_FORWARD_OHLC_CONFLICT")
            for name in ("pre_close", "change", "pct_chg", "vol", "amount"):
                _number(row[name], positive=name == "pre_close", nonnegative=name in ("vol", "amount"))
        if job["api_name"] == "stock_basic":
            require(row["symbol"] == job["symbol"].split(".")[0] and type(row["name"]) is str and 1 <= len(row["name"]) <= 160 and row["exchange"] == "SSE" and row["curr_type"] == "CNY" and row["list_status"] in ("L", "D", "P"), "WH_FORWARD_SECURITY_BASIC_SCHEMA_INVALID")
            for field in ("list_date", "delist_date"):
                value = row[field]
                if value is not None and value != "":
                    require(type(value) is str and re.fullmatch(r"\d{8}", value), "WH_FORWARD_SECURITY_BASIC_DATE_INVALID")
                    _day(value[:4] + "-" + value[4:6] + "-" + value[6:])
        if job["api_name"] == "suspend_d":
            require(row["suspend_type"] in ("S", "R") and (row["suspend_timing"] is None or type(row["suspend_timing"]) is str), "WH_FORWARD_SUSPENSION_EVENT_SCHEMA_INVALID")
        if job["api_name"] == "stk_limit":
            require(_number(row["up_limit"], True) >= _number(row["down_limit"], True) and _number(row["pre_close"], True) > 0, "WH_FORWARD_LIMIT_CONFLICT")
        rows.append(row)
    return {"status": "SUCCESS" if rows else "EMPTY", "reason_code": None if rows else "SOURCE_EMPTY_NOT_COMPLETE_STATUS_PROOF", "rows": rows, "row_count": len(rows)}


def _witness(ref_value, session, actual):
    doc = _json(reopen(ref_value, private=True))
    _exact(doc, {"version", "kind", "session", "symbols", "actual_session_open", "eod_observed", "observed_at", "precision", "original_refs", "witness_source"}, "WH_FORWARD_WITNESS_SHAPE")
    require(doc["version"] == "1.0.0" and doc["kind"] == ("ACTUAL_SESSION_WITNESS" if actual else "OFFLINE_SIMULATION_SESSION_WITNESS") and doc["session"] == session and doc["symbols"] == list(SYMBOLS) and doc["actual_session_open"] is True and doc["eod_observed"] is True and doc["precision"] == _precision(doc["observed_at"]) and _local_day(doc["observed_at"]) == session, "WH_FORWARD_CURRENT_OPEN_EOD_WITNESS_REQUIRED")
    require(type(doc["witness_source"]) is str and 1 <= len(doc["witness_source"]) <= 160, "WH_FORWARD_WITNESS_SOURCE_REQUIRED")
    require(type(doc["original_refs"]) is list and 1 <= len(doc["original_refs"]) <= 4 and len({x["path"] for x in doc["original_refs"]}) == len(doc["original_refs"]), "WH_FORWARD_WITNESS_ORIGINALS_REQUIRED")
    for item in doc["original_refs"]: reopen(item, private=True)
    return doc


def _anchor(ref_value, session, actual):
    doc = _json(reopen(ref_value, private=True))
    _exact(doc, {"capture_id", "session_date", "retrieved_at", "observed_universe", "raw_observation_hash", "source_policy_hash", "rules_hash", "version", "kind", "source_original_refs", "source_admission", "historical_visibility_proven"}, "WH_FORWARD_REFERENCE_A_SHAPE")
    require(doc["version"] == "1.0.0" and doc["kind"] == ("CURRENT_OBSERVED_REFERENCE_A_NOT_ADMITTED" if actual else "OFFLINE_SIMULATION_REFERENCE_A") and doc["source_admission"] == "BLOCKED" and doc["historical_visibility_proven"] is False and doc["observed_universe"] == list(SYMBOLS) and _day(doc["session_date"]).isoformat() < session and type(doc["capture_id"]) is str, "WH_FORWARD_A_TO_B_LINEAGE_DRIFT")
    require(1 <= len(doc["capture_id"]) <= 160, "WH_FORWARD_REFERENCE_A_CAPTURE_ID_REQUIRED")
    if actual:
        frozen = _json(reopen(ref(ROOT / "config/wave-h/snapshot-a-reference.json")))
        require(ref_value == frozen["snapshot_a_ref"], "WH_FORWARD_REAL_REFERENCE_A_FIXED_PIN_REQUIRED")
    for name in ("raw_observation_hash", "source_policy_hash", "rules_hash"): hash_value(doc[name])
    require(doc["rules_hash"] == bindings()["strategy_hash"], "WH_FORWARD_A_STRATEGY_DRIFT")
    timestamp(doc["retrieved_at"])
    require(type(doc["source_original_refs"]) is list and len(doc["source_original_refs"]) == 3 and len({x["path"] for x in doc["source_original_refs"]}) == 3 and doc["raw_observation_hash"] == digest(doc["source_original_refs"]), "WH_FORWARD_A_ORIGINAL_IDENTITY_DRIFT")
    for symbol, item in zip(SYMBOLS, doc["source_original_refs"]):
        raw = _json(reopen(item, private=True), True)
        _exact(raw, {"code", "msg", "data"}, "WH_FORWARD_A_SOURCE_SCHEMA")
        require(type(raw["code"]) is int and raw["code"] == 0, "WH_FORWARD_A_SOURCE_FAILED")
        _exact(raw["data"], {"fields", "items"}, "WH_FORWARD_A_SOURCE_SCHEMA")
        fields, values = raw["data"]["fields"], raw["data"]["items"]
        require(fields == _FIELDS["daily"] and type(values) is list and bool(values), "WH_FORWARD_A_DAILY_ORIGINAL_REQUIRED")
        dates = []
        for value in values:
            require(type(value) is list and len(value) == len(fields), "WH_FORWARD_A_ROW_SHAPE")
            row = dict(zip(fields, value))
            require(row["ts_code"] == symbol and type(row["trade_date"]) is str and re.fullmatch(r"\d{8}", row["trade_date"]), "WH_FORWARD_A_SYMBOL_DATE_DRIFT")
            dates.append(_day(row["trade_date"][:4] + "-" + row["trade_date"][4:6] + "-" + row["trade_date"][6:]).isoformat())
        require(max(dates) == doc["session_date"], "WH_FORWARD_A_LATEST_SESSION_DRIFT")
    return doc


def _request_identity(plan, job):
    return digest({"endpoint": plan["endpoint"], "source_identity": plan["source_identity"], "source_schema_version": plan["source_schema_version"], "session": plan["session"], "plan_hash": plan["plan_hash"], "job": job})


def _review(capture_manifest_ref, expected_plan, actual):
    _validate_plan_independently(expected_plan, actual)
    manifest = _json(reopen(capture_manifest_ref, private=True)); _exact(manifest, _MANIFEST, "WH_FORWARD_MANIFEST_SHAPE"); _unseal(manifest)
    mode = expected_plan["mode"]
    require(manifest["version"] == "1.0.0" and manifest["kind"] == ("ACTUAL_CURRENT_CAPTURE" if actual else "OFFLINE_SIMULATION_CAPTURE") and manifest["mode"] == mode and manifest["plan"] == expected_plan and manifest["plan_hash"] == expected_plan["plan_hash"] and manifest["session"] == expected_plan["session"] and manifest["symbols"] == list(SYMBOLS) and manifest["endpoint"] == expected_plan["endpoint"] and manifest["source_identity"] == expected_plan["source_identity"] and manifest["source_schema_version"] == expected_plan["source_schema_version"] and manifest["policy_hash"] == bindings()["policy_hash"] and manifest["strategy_hash"] == bindings()["strategy_hash"] and manifest["source_session_evidence_ref"] == expected_plan["session_evidence_ref"] and manifest["snapshot_a_ref"] == expected_plan["snapshot_a_ref"], "WH_FORWARD_CAPTURE_PLAN_BINDING_DRIFT")
    require(manifest["source_admission"] == "BLOCKED" and manifest["historical_visibility_proven"] is False and manifest["safe_to_trade"] is False and manifest["decision"] == "NO_DECISION" and type(manifest["actual_forward_days"]) is int and manifest["actual_forward_days"] == 0 and type(manifest["capture_id"]) is str and manifest["capture_id"].startswith("actual:" if actual else "sim:"), "WH_FORWARD_CAPTURE_AUTHORITY_OR_MODE_DRIFT")
    if actual:
        claims = _auth().verify_persisted_capture(manifest["capture_authorization"])
        scope = claims["scope"]
        require(scope["plan_hash"] == expected_plan["plan_hash"] and scope["session_evidence_hash"] == expected_plan["session_evidence_ref"]["sha256"] and scope["snapshot_a_hash"] == expected_plan["snapshot_a_ref"]["sha256"] and claims["bindings"] == bindings() and claims["session"] == manifest["session"] and manifest["capture_id"] == "actual:" + claims["nonce"], "WH_FORWARD_CAPTURE_SIGNED_BINDING_DRIFT")
        require(timestamp(claims["issued_at"]) <= timestamp(manifest["started_at"]) <= timestamp(manifest["completed_at"]) < timestamp(claims["expires_at"]), "WH_FORWARD_CAPTURE_OUTSIDE_SIGNED_VALIDITY")
        capture_dir = ARCHIVE / "capture" / "actual" / claims["nonce"]
        require(capture_manifest_ref["path"] == str(capture_dir / "capture-manifest.json"), "WH_FORWARD_ACTUAL_ARCHIVE_NAMESPACE_REQUIRED")
        claim_ref = ref(capture_dir / "capture-claim.json")
        consumed = _json(reopen(claim_ref, private=True))
        _exact(consumed, {"kind", "capture_id", "plan_hash", "permit_nonce", "started_at", "no_retry"}, "WH_FORWARD_CAPTURE_CONSUMED_CLAIM_SHAPE")
        require(consumed == {"kind": "ACTUAL_CAPTURE_CONSUMED_CLAIM", "capture_id": manifest["capture_id"], "plan_hash": manifest["plan_hash"], "permit_nonce": claims["nonce"], "started_at": manifest["started_at"], "no_retry": True}, "WH_FORWARD_CAPTURE_CONSUMED_CLAIM_DRIFT")
    else:
        require(manifest["capture_authorization"] is None, "WH_FORWARD_SIMULATION_HAS_CAPTURE_AUTHORITY")
    witness = _witness(expected_plan["session_evidence_ref"], manifest["session"], actual)
    if actual: require(timestamp(witness["observed_at"]) <= timestamp(claims["issued_at"]), "WH_FORWARD_OWNER_GRANT_PRECEDES_ACTUAL_SESSION_FACTS")
    anchor = _anchor(expected_plan["snapshot_a_ref"], manifest["session"], actual)
    require(anchor["capture_id"] != manifest["capture_id"], "WH_FORWARD_A_CAPTURE_REUSED")
    require(_local_day(manifest["started_at"]) == manifest["session"] == _local_day(manifest["completed_at"]) and manifest["clock_precision"] == _precision(manifest["completed_at"]) and timestamp(anchor["retrieved_at"]) <= timestamp(manifest["started_at"]) and timestamp(witness["observed_at"]) <= timestamp(manifest["started_at"]) <= timestamp(manifest["completed_at"]), "WH_FORWARD_CAPTURE_FRESHNESS_CLOCK_CONFLICT")
    require(type(manifest["jobs"]) is list and len(manifest["jobs"]) == len(expected_plan["jobs"]), "WH_FORWARD_MISSING_CAPTURE_JOB")
    originals = [capture_manifest_ref, expected_plan["session_evidence_ref"], expected_plan["snapshot_a_ref"], *witness["original_refs"], *anchor["source_original_refs"]]
    if actual: originals.append(claim_ref)
    raw_hashes, raw_paths, daily_hashes, rows, clocks = set(), set(), set(), [], []
    for job, entry in zip(expected_plan["jobs"], manifest["jobs"]):
        _exact(entry, {"job", "request_identity", "status", "reason_code", "raw_ref", "clock_ref", "source_response_hash", "row_count"}, "WH_FORWARD_JOB_RESULT_SHAPE")
        request_id = _request_identity(expected_plan, job)
        require(entry["job"] == job and entry["request_identity"] == request_id, "WH_FORWARD_JOB_REQUEST_DRIFT")
        if actual:
            require(entry["raw_ref"]["path"] == str(capture_dir / (job["job_id"] + ".raw.json")) and entry["clock_ref"]["path"] == str(capture_dir / (job["job_id"] + ".clock.json")), "WH_FORWARD_ACTUAL_JOB_ARCHIVE_REQUIRED")
            request_claim_ref = ref(capture_dir / (job["job_id"] + ".request-claim.json"))
            request_claim = _json(reopen(request_claim_ref, private=True))
            _exact(request_claim, {"job_id", "permit_nonce", "request_identity", "started_at", "attempt", "no_retry"}, "WH_FORWARD_REQUEST_CONSUMED_CLAIM_SHAPE")
            require(request_claim["job_id"] == job["job_id"] and request_claim["permit_nonce"] == claims["nonce"] and request_claim["request_identity"] == request_id and type(request_claim["attempt"]) is int and request_claim["attempt"] == 1 and request_claim["no_retry"] is True, "WH_FORWARD_REQUEST_CONSUMED_CLAIM_DRIFT")
            originals.append(request_claim_ref)
        raw = reopen(entry["raw_ref"], private=True); original_sha = sha(raw)
        require(original_sha == entry["source_response_hash"] and entry["raw_ref"]["path"] not in raw_paths, "WH_FORWARD_RAW_DUPLICATE_OR_HASH_DRIFT"); raw_hashes.add(original_sha); raw_paths.add(entry["raw_ref"]["path"])
        if job["api_name"] == "daily":
            require(original_sha not in daily_hashes, "WH_FORWARD_DUPLICATE_DAILY_RAW"); daily_hashes.add(original_sha)
        parsed = _parse_original(job, raw, manifest["session"])
        require(entry["status"] == parsed["status"] and entry["reason_code"] == parsed["reason_code"] and entry["row_count"] == parsed["row_count"] and (entry["row_count"] is None or type(entry["row_count"]) is int), "WH_FORWARD_PRODUCER_SUMMARY_NOT_ORIGINAL")
        if job["mandatory"]: require(parsed["status"] == "SUCCESS" and parsed["row_count"] == 1, "WH_FORWARD_MANDATORY_EXACT_THREE_SESSION_REQUIRED")
        clock = _json(reopen(entry["clock_ref"], private=True)); _exact(clock, _CLOCK, "WH_FORWARD_CLOCK_ORIGINAL_SHAPE")
        if actual: require(request_claim["started_at"] == clock["started_at"], "WH_FORWARD_REQUEST_ACTUAL_CLOCK_DRIFT")
        require(clock["version"] == "1.0.0" and clock["kind"] == ("ACTUAL_CURRENT_CAPTURE_CLOCK" if actual else "OFFLINE_SIMULATION_CAPTURE_CLOCK") and clock["mode"] == mode and clock["capture_id"] == manifest["capture_id"] and clock["job_id"] == job["job_id"] and clock["request_identity"] == request_id and clock["source_identity"] == expected_plan["source_identity"] and clock["source_schema_version"] == expected_plan["source_schema_version"] and clock["session"] == manifest["session"] and clock["source_response_hash"] == original_sha, "WH_FORWARD_CLOCK_CAPTURE_RAW_BINDING_DRIFT")
        require(clock["event_time"] == manifest["session"] and clock["event_precision"] == "DATE_ONLY" and clock["published_at"] is None and clock["published_precision"] == "UNKNOWN" and clock["source_available_at"] is None and clock["source_available_precision"] == "UNKNOWN" and clock["current_available_at"] == clock["retrieved_at"] and clock["current_available_precision"] == clock["retrieved_precision"] == _precision(clock["retrieved_at"]) and clock["visibility_basis"] == "CURRENT_CAPTURE_COMPLETED_NOT_HISTORICAL_FIRST_VISIBLE" and clock["historical_visibility_proven"] is False, "WH_FORWARD_CURRENT_VISIBILITY_NOT_HISTORICAL_OR_DATE_ONLY")
        require(_local_day(clock["started_at"]) == manifest["session"] == _local_day(clock["retrieved_at"]) and timestamp(manifest["started_at"]) <= timestamp(clock["started_at"]) <= timestamp(clock["retrieved_at"]) <= timestamp(manifest["completed_at"]), "WH_FORWARD_SOURCE_CLOCK_ORDER_OR_FRESHNESS_DRIFT")
        originals.extend((entry["raw_ref"], entry["clock_ref"])); rows.append({"job": job, "rows": parsed["rows"], "status": parsed["status"]}); clocks.append(clock)
    raw_observation_hash = digest(sorted(raw_hashes))
    require(raw_observation_hash != anchor["raw_observation_hash"], "WH_FORWARD_B_REUSES_A_ORIGINALS")
    direct_refs = sorted({canonical(x): x for x in originals}.values(), key=canonical)
    unknowns = [{"symbol": symbol, "field": field, "state": "UNKNOWN", "reason_code": "CURRENT_RESPONSE_NOT_COMPLETE_VERIFIED_STATE"} for symbol in SYMBOLS for field in ("ST_NAME_HISTORY", "SUSPENSION_COMPLETE_STATE", "CORPORATE_ACTION_COMPLETENESS", "PRICE_LIMIT_REGIME", "PROVIDER_LICENSE_TRANSPORT")]
    require(manifest["status_unknowns"] == unknowns, "WH_FORWARD_UNKNOWN_STATUS_PROMOTION")
    coverage = {"requested_symbols": list(SYMBOLS), "observed_daily_symbols": list(SYMBOLS), "mandatory_daily_count": 3, "session_calendar_consistent": True, "planned_calendar_is_actual_session_proof": False}
    require(manifest["coverage"] == coverage, "WH_FORWARD_COVERAGE_SUMMARY_DRIFT")
    return seal({"version": "1.0.0", "kind": "INDEPENDENT_ORIGINAL_REOPEN_ACCEPTANCE_REQUEST", "mode": mode,
                 "capture_hash": manifest["content_hash"], "capture_manifest_hash": capture_manifest_ref["sha256"],
                 "capture_id": manifest["capture_id"], "session": manifest["session"], "symbols": list(SYMBOLS),
                 "started_at": manifest["started_at"], "completed_at": manifest["completed_at"],
                 "plan_hash": expected_plan["plan_hash"], "bindings": bindings(), "source_schema_version": manifest["source_schema_version"],
                 "raw_observation_hash": raw_observation_hash, "original_refs": direct_refs, "originals_digest": digest(direct_refs),
                 "independently_reopened": True, "coverage": coverage, "status_unknowns": unknowns, "clock_metadata": clocks,
                 "decision": "NO_DECISION", "safe_to_trade": False, "no_flags": copy.deepcopy(_NO), "source_admission": "BLOCKED",
                 "historical_visibility_proven": False, "actual_forward_days": 0, "is_authority": False,
                 "acceptance_state": "REQUEST_EXTERNAL_INDEPENDENT_REVIEWER_SIGNATURE" if actual else "OFFLINE_SIMULATION_REQUEST_NO_AUTHORITY"})


def review_capture(capture_manifest_ref, expected_plan):
    """Signable display request; signatures originate outside the producer."""
    actual = type(expected_plan) is dict and expected_plan.get("mode") == "LOCAL_ONLY_NON_TRADEABLE_CURRENT_OBSERVATION"
    if actual: _auth().ensure_actual_enrolled()
    return _review(capture_manifest_ref, expected_plan, actual)


def _review_bind(claims, request):
    scope = claims["scope"]
    require(claims["bindings"] == request["bindings"] and claims["session"] == request["session"] and timestamp(claims["issued_at"]) >= timestamp(request["completed_at"]) and scope["capture_hash"] == request["capture_hash"] and scope["capture_manifest_hash"] == request["capture_manifest_hash"] and scope["plan_hash"] == request["plan_hash"] and scope["acceptance_request_hash"] == request["content_hash"] and scope["originals_digest"] == request["originals_digest"], "WH_FORWARD_INDEPENDENT_ACCEPTANCE_BINDING_DRIFT")


def _snapshot(capture_manifest_ref, expected_plan, request, signed_acceptance, actual):
    return seal({"version": "1.0.0", "kind": "ACTUAL_LOCAL_SNAPSHOT_B" if actual else "OFFLINE_SIMULATION_SNAPSHOT_B",
                 "namespace": ACTUAL_NAMESPACE if actual else SIMULATION_NAMESPACE,
                 "body": {"session": request["session"], "capture_id": request["capture_id"], "capture_manifest_ref": copy.deepcopy(capture_manifest_ref),
                          "expected_plan": copy.deepcopy(expected_plan), "acceptance_request": copy.deepcopy(request), "signed_acceptance": copy.deepcopy(signed_acceptance),
                          "raw_observation_hash": request["raw_observation_hash"], "snapshot_a_ref": copy.deepcopy(expected_plan["snapshot_a_ref"]),
                          "source_schema_version": expected_plan["source_schema_version"], "decision": "NO_DECISION", "safe_to_trade": False,
                          "no_flags": copy.deepcopy(_NO), "source_admission": "BLOCKED", "historical_visibility_proven": False,
                          "actual_forward_days": 0, "is_native_signal_order": False, "money_authority": False}})


def issue_snapshot_b(capture_manifest_ref, expected_plan, review_handle):
    _auth().ensure_actual_enrolled()
    # Registry is checked first; no actual original is reopened during H-A.
    manifest = _json(reopen(capture_manifest_ref, private=True))
    claims = _auth().require_review(review_handle, manifest.get("content_hash"))
    request = _review(capture_manifest_ref, expected_plan, True); _review_bind(claims, request)
    return _snapshot(capture_manifest_ref, expected_plan, request, claims["signed_envelope"], True)


def issue_simulation_snapshot(capture_manifest_ref, expected_plan):
    request = _review(capture_manifest_ref, expected_plan, False)
    return _snapshot(capture_manifest_ref, expected_plan, request, None, False)


def _validate_snapshot(snapshot, actual, restart=False):
    _exact(snapshot, {"version", "kind", "namespace", "body", "content_hash"}, "WH_FORWARD_SNAPSHOT_SHAPE"); _unseal(snapshot)
    require(snapshot["version"] == "1.0.0" and snapshot["kind"] == ("ACTUAL_LOCAL_SNAPSHOT_B" if actual else "OFFLINE_SIMULATION_SNAPSHOT_B") and snapshot["namespace"] == (ACTUAL_NAMESPACE if actual else SIMULATION_NAMESPACE), "WH_FORWARD_SNAPSHOT_NAMESPACE_PROMOTION")
    body = snapshot["body"]
    _exact(body, {"session", "capture_id", "capture_manifest_ref", "expected_plan", "acceptance_request", "signed_acceptance", "raw_observation_hash", "snapshot_a_ref", "source_schema_version", "decision", "safe_to_trade", "no_flags", "source_admission", "historical_visibility_proven", "actual_forward_days", "is_native_signal_order", "money_authority"}, "WH_FORWARD_SNAPSHOT_BODY_SHAPE")
    request = _review(body["capture_manifest_ref"], body["expected_plan"], actual)
    if actual:
        claims = _auth().verify_persisted_review(body["signed_acceptance"]); _review_bind(claims, request)
    else:
        require(body["signed_acceptance"] is None, "WH_FORWARD_SIMULATION_REVIEW_AUTHORITY")
    require(snapshot == _snapshot(body["capture_manifest_ref"], body["expected_plan"], request, body["signed_acceptance"], actual), "WH_FORWARD_SNAPSHOT_ORIGINAL_OR_VERSION_DRIFT")
    return snapshot


def _forward_bind(claims, snapshot, expected_head=None):
    scope = claims["scope"]
    require(claims["bindings"] == bindings() and claims["session"] == scope["session"] == snapshot["body"]["session"] and timestamp(claims["issued_at"]) >= timestamp(snapshot["body"]["signed_acceptance"]["body"]["issued_at"]) and scope["snapshot_hash"] == snapshot["content_hash"], "WH_FORWARD_SEPARATE_HUMAN_FORWARD_BINDING_DRIFT")
    if expected_head is not None: require(scope["expected_head"] == expected_head, "WH_FORWARD_GRANT_EXPECTED_HEAD_DRIFT")


def _series_binding(plan):
    """Stable series identifiers exclude changing per-response content hashes."""
    return digest({"bindings": plan["bindings"], "source_schema_version": policy()["source_schema_version"],
                   "source_identity": plan["source_identity"], "snapshot_a_ref": plan["snapshot_a_ref"]})


def store_configuration(actual=False):
    require(type(actual) is bool, "WH_FORWARD_NAMESPACE_BOOLEAN_INVALID")
    return {"version": "1.0.0", "namespace": ACTUAL_NAMESPACE if actual else SIMULATION_NAMESPACE,
            "suffix": ".wave-h.actual.sqlite3" if actual else ".wave-h.simulation.sqlite3",
            "schema_version": 1, "decision": "NO_DECISION", "safe_to_trade": False,
            "no_flags": copy.deepcopy(_NO), "source_admission": "BLOCKED",
            "historical_visibility_proven": False, "account_cost_risk": {k: UNSET for k in ("account", "cost", "risk")},
            "money_configuration_required": False, "actual_authority": "EXTERNAL_ENROLLED_SIGNATURES_REQUIRED" if actual else "NEVER",
            "algorithm": ["EXCLUSIVE_CREATE", "BEGIN_IMMEDIATE_EXPECTED_HEAD", "EXACTLY_ONCE_SESSION_CAPTURE_RAW",
                          "FROZEN_SERIES_BINDING", "APPEND_ONLY_FAILURE_CHAIN", "REOPEN_ORIGINALS_AND_PUBLIC_SIGNATURES", "READ_ONLY_RECOVERY_NO_REPAIR"]}


_TABLES = {
    "forward_metadata": "CREATE TABLE forward_metadata(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL,hash TEXT NOT NULL)",
    "forward_sessions": "CREATE TABLE forward_sessions(sequence INTEGER PRIMARY KEY CHECK(sequence>0),session TEXT NOT NULL UNIQUE,capture_id TEXT NOT NULL UNIQUE,observation_hash TEXT NOT NULL UNIQUE,previous_hash TEXT NOT NULL,record_hash TEXT NOT NULL UNIQUE,body TEXT NOT NULL)",
    "forward_failures": "CREATE TABLE forward_failures(sequence INTEGER PRIMARY KEY CHECK(sequence>0),attempt_id TEXT NOT NULL UNIQUE,previous_hash TEXT NOT NULL,attempt_hash TEXT NOT NULL UNIQUE,body TEXT NOT NULL)",
}
_TRIGGERS = {}
for _table in _TABLES:
    for _operation in ("UPDATE", "DELETE"):
        _name = _table + "_no_" + _operation.lower()
        _TRIGGERS[_name] = "CREATE TRIGGER " + _name + " BEFORE " + _operation + " ON " + _table + " BEGIN SELECT RAISE(ABORT,'WH_FORWARD_APPEND_ONLY'); END"
    _name = _table + "_guard_insert"
    _TRIGGERS[_name] = "CREATE TRIGGER " + _name + " BEFORE INSERT ON " + _table + " WHEN wave_h_forward_capability()!=1 BEGIN SELECT RAISE(ABORT,'WH_FORWARD_CAPABILITY_REQUIRED'); END"


def _path(path, existing, actual):
    require(type(path) is str or isinstance(path, Path), "WH_FORWARD_PATH_INVALID")
    p = Path(path)
    suffix = store_configuration(actual)["suffix"]
    require(p.is_absolute() and p.resolve() == p and not p.is_symlink() and p.is_relative_to(ARCHIVE / "forward") and p.name.endswith(suffix), "WH_FORWARD_PATH_OR_NAMESPACE_INVALID")
    require(p.parent.is_dir() and p.parent.stat().st_mode & 0o777 == 0o700, "WH_FORWARD_PRIVATE_PARENT_REQUIRED")
    require(p.is_file() and p.stat().st_mode & 0o777 == 0o600 if existing else not p.exists(), "WH_FORWARD_STORE_REQUIRED_OR_EXISTS")
    return p


def _connect(p, write=False):
    conn = sqlite3.connect(p.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True,
                           isolation_level=None, timeout=10)
    if write:
        conn.execute("PRAGMA synchronous=FULL")
        conn.create_function("wave_h_forward_capability", 0, lambda: 1)
    return conn


def _decode(raw):
    result = _json(raw)
    require(canonical(result).decode() == raw, "WH_FORWARD_NONCANONICAL_STATE")
    return result


def _inspect(conn, p, actual):
    expected = {k: ("table", v) for k, v in _TABLES.items()} | {k: ("trigger", v) for k, v in _TRIGGERS.items()}
    observed = {name: (kind, sql) for name, kind, sql in conn.execute("SELECT name,type,sql FROM sqlite_schema WHERE sql IS NOT NULL")}
    require(observed == expected and conn.execute("PRAGMA user_version").fetchone()[0] == 1 and conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "WH_FORWARD_SCHEMA_OR_INTEGRITY_DRIFT")
    rows = conn.execute("SELECT id,body,hash FROM forward_metadata").fetchall()
    require(len(rows) == 1 and rows[0][0] == 1, "WH_FORWARD_METADATA_REQUIRED")
    meta = _decode(rows[0][1])
    _exact(meta, {"kind", "version", "namespace", "canonical_path", "store_id", "configuration", "bindings"}, "WH_FORWARD_METADATA_SHAPE")
    require(meta["kind"] == "WAVE_H_FORWARD_STORE" and meta["version"] == "1.0.0" and meta["namespace"] == store_configuration(actual)["namespace"] and meta["canonical_path"] == str(p) and re.fullmatch(r"forward:[0-9a-f]{32}", meta["store_id"]) and meta["configuration"] == store_configuration(actual) and meta["bindings"] == bindings() and digest(meta) == rows[0][2], "WH_FORWARD_METADATA_BINDING_DRIFT")
    head = digest({"kind": "FORWARD_RECORD_GENESIS", "metadata_hash": rows[0][2]})
    records, sessions, captures, raw_hashes = [], set(), set(), set()
    series = None
    for row in conn.execute("SELECT sequence,session,capture_id,observation_hash,previous_hash,record_hash,body FROM forward_sessions ORDER BY sequence"):
        item = _decode(row[6])
        _exact(item, {"sequence", "previous_hash", "record_hash", "snapshot", "forward_authorization", "series_binding", "decision", "safe_to_trade", "no_flags", "actual_forward_days", "provenance"}, "WH_FORWARD_RECORD_SHAPE")
        snapshot = _validate_snapshot(item["snapshot"], actual, restart=True)
        body = snapshot["body"]
        if actual:
            claims = _auth().verify_persisted_forward(item["forward_authorization"])
            _forward_bind(claims, snapshot, item["previous_hash"])
        else:
            require(item["forward_authorization"] is None, "WH_FORWARD_SIMULATION_HAS_AUTHORITY")
        require(item["decision"] == "NO_DECISION" and item["safe_to_trade"] is False and item["no_flags"] == _NO and item["provenance"] == ("REAL_ACCEPTED_CURRENT_SESSION" if actual else "OFFLINE_SIMULATION_NEVER_ACTUAL") and type(item["actual_forward_days"]) is int and item["actual_forward_days"] == (len(records) + 1 if actual else 0), "WH_FORWARD_DECISION_OR_AUTHORITY_DRIFT")
        require(type(item["sequence"]) is int and item["sequence"] == len(records) + 1 and item["previous_hash"] == head and item["record_hash"] == digest({k: v for k, v in item.items() if k != "record_hash"}), "WH_FORWARD_CHAIN_DRIFT")
        require(tuple(row[:6]) == (item["sequence"], body["session"], body["capture_id"], body["raw_observation_hash"], head, item["record_hash"]), "WH_FORWARD_RECORD_COLUMN_DRIFT")
        require(body["session"] not in sessions and body["capture_id"] not in captures and body["raw_observation_hash"] not in raw_hashes and (not records or body["session"] > records[-1]["snapshot"]["body"]["session"]), "WH_FORWARD_DUPLICATE_OR_SESSION_ORDER")
        expected_series = _series_binding(body["expected_plan"])
        series = series or expected_series
        require(item["series_binding"] == expected_series == series, "WH_FORWARD_FROZEN_SERIES_DRIFT")
        sessions.add(body["session"]); captures.add(body["capture_id"]); raw_hashes.add(body["raw_observation_hash"])
        records.append(item); head = item["record_hash"]
    failure_head = digest({"kind": "FORWARD_FAILURE_GENESIS", "metadata_hash": rows[0][2]})
    failures = []
    for row in conn.execute("SELECT sequence,attempt_id,previous_hash,attempt_hash,body FROM forward_failures ORDER BY sequence"):
        item = _decode(row[4])
        _exact(item, {"sequence", "attempt_id", "previous_hash", "attempt_hash", "kind", "reason_code", "untrusted_payload_retained", "actual_forward_days"}, "WH_FORWARD_FAILURE_SHAPE")
        require(item["kind"] == "SANITIZED_FORWARD_FAILURE" and re.fullmatch(r"WH_[A-Z0-9_]{1,140}", item["reason_code"]) and re.fullmatch(r"forward-failure:[0-9a-f]{32}", item["attempt_id"]) and item["untrusted_payload_retained"] is False and type(item["actual_forward_days"]) is int and item["actual_forward_days"] == 0, "WH_FORWARD_FAILURE_INVALID")
        require(type(item["sequence"]) is int and item["sequence"] == len(failures) + 1 and item["previous_hash"] == failure_head and item["attempt_hash"] == digest({k: v for k, v in item.items() if k != "attempt_hash"}) and tuple(row[:4]) == (item["sequence"], item["attempt_id"], failure_head, item["attempt_hash"]), "WH_FORWARD_FAILURE_CHAIN_DRIFT")
        failures.append(item); failure_head = item["attempt_hash"]
    return {"kind": "WAVE_H_FORWARD_STORE_DISPLAY", "namespace": meta["namespace"], "head_hash": head,
            "failure_head_hash": failure_head, "accepted_session_count": len(records),
            "simulated_accepted_session_count": 0 if actual else len(records),
            "actual_forward_days": len(records) if actual else 0, "failed_attempt_count": len(failures),
            "records": records, "failed_attempts": failures, "decision": "NO_DECISION", "safe_to_trade": False,
            "no_flags": copy.deepcopy(_NO), "live_money_authority": False, "source_admission": "BLOCKED"}


def _create(path, actual):
    p = _path(path, False, actual)
    frozen = bindings()
    descriptor = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600); os.close(descriptor)
    conn = _connect(p, True)
    try:
        conn.execute("PRAGMA journal_mode=DELETE"); conn.execute("BEGIN IMMEDIATE")
        for sql in _TABLES.values(): conn.execute(sql)
        body = {"kind": "WAVE_H_FORWARD_STORE", "version": "1.0.0", "namespace": store_configuration(actual)["namespace"], "canonical_path": str(p), "store_id": "forward:" + uuid.uuid4().hex, "configuration": store_configuration(actual), "bindings": frozen}
        conn.execute("INSERT INTO forward_metadata VALUES(1,?,?)", (canonical(body).decode(), digest(body)))
        for sql in _TRIGGERS.values(): conn.execute(sql)
        conn.execute("PRAGMA user_version=1")
        result = _inspect(conn, p, actual); conn.execute("COMMIT")
        return result
    finally:
        if conn.in_transaction: conn.execute("ROLLBACK")
        conn.close()


def _read(path, actual):
    p = _path(path, True, actual); conn = _connect(p)
    try:
        conn.execute("BEGIN")
        return _inspect(conn, p, actual)
    finally:
        if conn.in_transaction: conn.execute("ROLLBACK")
        conn.close()


def _append(path, snapshot, expected_head, actual, forward_claims=None):
    value = _validate_snapshot(snapshot, actual)
    hash_value(expected_head)
    if actual: _forward_bind(forward_claims, value, expected_head)
    with _LOCK:
        p = _path(path, True, actual); conn = _connect(p, True)
        try:
            conn.execute("BEGIN IMMEDIATE"); before = _inspect(conn, p, actual)
            require(before["head_hash"] == expected_head, "WH_FORWARD_STALE_EXPECTED_HEAD")
            body = value["body"]
            for old in before["records"]:
                previous = old["snapshot"]["body"]
                require(previous["session"] != body["session"] and previous["capture_id"] != body["capture_id"] and previous["raw_observation_hash"] != body["raw_observation_hash"], "WH_FORWARD_DUPLICATE_SESSION_CAPTURE_RAW")
            series = _series_binding(body["expected_plan"])
            if before["records"]:
                previous = before["records"][-1]
                require(body["session"] > previous["snapshot"]["body"]["session"] and series == previous["series_binding"], "WH_FORWARD_SESSION_ORDER_OR_SERIES_DRIFT")
            item = {"sequence": before["accepted_session_count"] + 1, "previous_hash": expected_head,
                    "snapshot": copy.deepcopy(value), "forward_authorization": copy.deepcopy(forward_claims["signed_envelope"]) if actual else None,
                    "series_binding": series, "decision": "NO_DECISION", "safe_to_trade": False,
                    "no_flags": copy.deepcopy(_NO), "actual_forward_days": before["accepted_session_count"] + 1 if actual else 0,
                    "provenance": "REAL_ACCEPTED_CURRENT_SESSION" if actual else "OFFLINE_SIMULATION_NEVER_ACTUAL"}
            item["record_hash"] = digest(item)
            conn.execute("INSERT INTO forward_sessions VALUES(?,?,?,?,?,?,?)", (item["sequence"], body["session"], body["capture_id"], body["raw_observation_hash"], expected_head, item["record_hash"], canonical(item).decode()))
            result = _inspect(conn, p, actual); conn.execute("COMMIT")
            return result
        finally:
            if conn.in_transaction: conn.execute("ROLLBACK")
            conn.close()


def _failure(path, actual, reason):
    if not re.fullmatch(r"WH_[A-Z0-9_]{1,140}", reason): reason = "WH_FORWARD_INVALID_UNTRUSTED_INPUT"
    with _LOCK:
        p = _path(path, True, actual); conn = _connect(p, True)
        try:
            conn.execute("BEGIN IMMEDIATE"); before = _inspect(conn, p, actual)
            item = {"sequence": before["failed_attempt_count"] + 1, "attempt_id": "forward-failure:" + uuid.uuid4().hex,
                    "previous_hash": before["failure_head_hash"], "kind": "SANITIZED_FORWARD_FAILURE", "reason_code": reason,
                    "untrusted_payload_retained": False, "actual_forward_days": 0}
            item["attempt_hash"] = digest(item)
            conn.execute("INSERT INTO forward_failures VALUES(?,?,?,?,?)", (item["sequence"], item["attempt_id"], item["previous_hash"], item["attempt_hash"], canonical(item).decode()))
            _inspect(conn, p, actual); conn.execute("COMMIT")
        finally:
            if conn.in_transaction: conn.execute("ROLLBACK")
            conn.close()


def create_actual_store(path):
    _auth().ensure_actual_enrolled()
    return _create(path, True)


def inspect_actual_store(path):
    _auth().ensure_actual_enrolled()
    return _read(path, True)


def append_actual_session(path, snapshot, forward_handle, expected_head):
    claims = _auth().require_forward(forward_handle, snapshot.get("content_hash") if type(snapshot) is dict else "INVALID")
    return _append(path, snapshot, expected_head, True, claims)


def attempt_actual_session(path, snapshot, forward_handle, expected_head):
    # Invalid/non-enrolled authority never causes even a failure-store write.
    claims = _auth().require_forward(forward_handle, snapshot.get("content_hash") if type(snapshot) is dict else "INVALID")
    try:
        return _append(path, snapshot, expected_head, True, claims)
    except ValueError as error:
        _failure(path, True, str(error)); raise


def recover_actual_store(path, expected_head=None):
    result = inspect_actual_store(path)
    if expected_head is not None:
        hash_value(expected_head); require(result["head_hash"] == expected_head, "WH_FORWARD_RECOVERY_HEAD_MISMATCH")
    return {"kind": "WAVE_H_ACTUAL_FORWARD_RECOVERY_DISPLAY", "recovery_action": "VERIFIED_READ_ONLY_NO_REPAIR", "result": result, "live_money_authority": False}


def create_simulation_store(path): return _create(path, False)
def inspect_simulation_store(path): return _read(path, False)
def append_simulation_session(path, snapshot, expected_head): return _append(path, snapshot, expected_head, False)


def attempt_simulation_session(path, snapshot, expected_head):
    try:
        return _append(path, snapshot, expected_head, False)
    except ValueError as error:
        _failure(path, False, str(error)); raise


def recover_simulation_store(path, expected_head=None):
    result = inspect_simulation_store(path)
    if expected_head is not None:
        hash_value(expected_head); require(result["head_hash"] == expected_head, "WH_FORWARD_RECOVERY_HEAD_MISMATCH")
    return {"kind": "WAVE_H_SIMULATION_FORWARD_RECOVERY_DISPLAY", "recovery_action": "VERIFIED_READ_ONLY_NO_REPAIR", "result": result, "actual_forward_days": 0, "live_money_authority": False}


def readiness():
    return metadata("WAVE_H_ACTUAL_FORWARD_READINESS", {
        "implementation": "READY_FOR_ONE_SHOT_OWNER_AUTH",
        "actual_snapshot_b": "NOT_YET_RUN", "actual_forward_days": 0,
        "actual_namespace": ACTUAL_NAMESPACE, "simulation_namespace": SIMULATION_NAMESPACE,
        "actual_store_configuration": store_configuration(True),
        "algorithms_implemented": ["INDEPENDENT_NATIVE_RAW_AND_CLOCK_REOPEN", "SIGNED_CAPTURE_PUBLIC_PROOF_REVERIFICATION",
            "EXTERNAL_INDEPENDENT_REVIEW_BINDING", "DETERMINISTIC_SNAPSHOT_B_ISSUANCE_AFTER_REVIEW",
            "SEPARATE_HUMAN_FORWARD_SCOPE_AND_EXPECTED_HEAD", "EXCLUSIVE_ACTUAL_NAMESPACE_STORE",
            "ATOMIC_EXACTLY_ONCE_SESSION_COUNT", "FROZEN_SERIES_WITH_CHANGING_RESPONSE_HASHES",
            "FAILURE_CHAIN", "RESTART_SIGNATURE_AND_ORIGINAL_REOPEN", "READ_ONLY_RECOVERY_NO_REPAIR"],
        "runtime_prerequisites": ["FRESH_H_B_OWNER_PUBLIC_KEY_ENROLLMENT_OUTSIDE_PRODUCER",
            "ACTUAL_SESSION_EOD_WITNESS_AND_FRESH_CAPTURE", "EXTERNAL_INDEPENDENT_REVIEWER_SIGNATURE",
            "SEPARATE_HUMAN_FORWARD_APPEND_SIGNATURE", "PRIVATE_ACTUAL_STATE_DIRECTORY"],
        "account_cost_risk": {k: UNSET for k in ("account", "cost", "risk")},
        "money_configuration_required_for_no_decision": False,
        "provider_license_transport": "UNKNOWN_NOT_ADMITTED", "historical_first_visibility": "NOT_ASSERTED",
        "signed_display_json_is_native_authority": False, "no_flags": copy.deepcopy(_NO),
        "safe_to_trade": False, "decision": "NO_DECISION"})


def issue_native(*args, **kwargs): raise ValueError("WH_FORWARD_NATIVE_AUTHORITY_FORBIDDEN")
def connect_broker(*args, **kwargs): raise ValueError("WH_FORWARD_BROKER_FORBIDDEN")
def cloud_export(*args, **kwargs): raise ValueError("WH_FORWARD_CLOUD_EXPORT_FORBIDDEN")
def execute_trade(*args, **kwargs): raise ValueError("WH_FORWARD_TRADE_FORBIDDEN")
