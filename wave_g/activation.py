"""Read-only, file-backed Snapshot B preflight; actual execution stays blocked.

No positive actual authority exists in this module. Native supplier responses
are reopened, hashed and compared to imported rows. Clock transcripts preserve
their reported precision, but their semantics still need an independently
accepted actual collector and review issuer in a separately authorized phase.
The durable store wrappers below delegate only to immutable Wave F fixtures.
"""
from __future__ import annotations

import copy
from datetime import date, datetime, timezone, timedelta
import json
from pathlib import Path
import re
import os
import sqlite3
import threading
import uuid

from .common import ROOT, BASELINE_ROOT, ARCHIVE, SYMBOLS, UNSET, canonical, digest, sha, require, hash_value, timestamp, checked_file, checked_reference, decimal_string, metadata

PACKET_KIND = "WAVE_G_SNAPSHOT_B_PREFLIGHT_V1"
_PRIVATE_ROOT = ARCHIVE.parent
_PINNED = (
    ("docs/post-wave-e/adopted-private-pins.json", "sha256:de5ba8bafe920fabbbe67513393d4fb5b1c865e09a3d6f299c015782126aca9d", 76424),
    ("docs/post-wave-e/observation-original-map.json", "sha256:9e31fbd36065ea10a196bf62c2601b686e5d3df083c130d17b79d6ba573bf3e9", 69696),
    ("docs/post-wave-e/rules.json", "sha256:8be78b0eab2529c95c919cc145b8d50a27265db3d12490b3d69d6f1f8857b9c5", 867),
    ("docs/wave-f/Forward-Paper-Activation-Readiness.json", "sha256:6098458dd085a9afd17da873fc8b98719e77a5224e5ed498ca1876a2034b87af", 2036),
    ("docs/wave-f/Frozen-StrategySpec-v1.json", "sha256:d4eb866d6675e52f4b5158374f94a3152e4ae406c62add22a8c807762b0215da", 11343),
    ("docs/wave-f/Interface-Freeze.md", "sha256:4a74c7aca67d7bb79d617d04f2e4f30b9d82a4c2dbd49636d542151b77583ee9", 5929),
    ("docs/wave-f/Snapshot-B-Activation-Readiness.json", "sha256:eadcb552e33aaf2ed5fef1b188126433450c520f0993f75dc7420211796ff030", 2290),
    ("docs/wave-f/Snapshot-B-Runbook.md", "sha256:481ce1d40c51c310c879cb8b6a7c53090b76104a085b3c674d45696acb376889", 5062),
    ("post_wave_e/preflight.py", "sha256:e14e388cf14a267d9b78c3479c9fc3286c8d1bbeb9ecd4e2e4632539d8ced366", 819),
    ("post_wave_e/real_adapter.py", "sha256:7a25cab34da17cb9b4d04b70c02d5d92d50c55fbdf28e5d358da21b1e62da28c", 1449),
    ("wave_f/activation.py", "sha256:d4dae055f2408779f3266e52daca288aa3cac482bf92a0ed34ba7a376a44b9be", 38918),
    ("wave_f/tests/test_activation.py", "sha256:aeb087d69fb653ca016974670eddf42e81b4b91743591053a19459fcb3577b75", 47884),
)
_CLOCKS = ("event_time", "published_at", "available_at", "retrieved_at")
_WIDTHS = {"SECOND": 0, "MILLISECOND": 3, "MICROSECOND": 6, "NANOSECOND": 9}
_BASES = {"event_time": {"SOURCE_REPORTED_EVENT", "MARKET_EVENT_OBSERVATION"}, "published_at": {"SOURCE_PUBLICATION"}, "available_at": {"SOURCE_FIRST_AVAILABILITY", "COLLECTOR_AVAILABILITY_OBSERVATION"}, "retrieved_at": {"COLLECTOR_RETRIEVAL"}}
_NO = {"NO_ORDER": True, "NO_BROKER": True, "NO_MONEY": True, "NO_NATIVE_SIGNAL_APPROVAL_ORDER_FILL": True, "NO_CLOUD_MODEL_EXPORT_REDISTRIBUTION": True, "NO_PRODUCTION": True, "NO_ACTUAL_CAPTURE_OR_APPEND": True}
_PACKET_FIELDS = {"kind", "mode", "capture_id", "expected_session", "captured_at", "decision_cutoff", "snapshot_a", "frozen_inputs", "calendar", "bars", "statuses", "review", "authorizations"}
_SLOT_FIELDS = {"domain", "provenance", "source_identity", "source_version", "original_ref", "clock_evidence_ref", "row", "clocks"}
_STATUS = {"symbol", "session_date", "listed", "delisted", "st", "suspended", "limit_up", "limit_down"}
_BAR = {"symbol", "session_date", "price_basis", "units", "open", "high", "low", "close", "volume", "amount"}
_CALENDAR = {"venue", "session_date", "observation_kind", "is_open", "market_open", "market_close", "actual_open_observed_at", "actual_eod_observed_at"}


def _exact(value, fields, reason):
    require(type(value) is dict and set(value) == set(fields), reason)
    canonical(value)


def _json(raw, numeric_strings=False):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "WG_ACT_DUPLICATE_JSON_KEY")
            out[key] = value
        return out
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_float=str if numeric_strings else float,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("WG_ACT_NONFINITE_JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("WG_ACT_SOURCE_JSON_INVALID") from None


def _ref(ref, private=False):
    _exact(ref, {"path", "sha256", "bytes"}, "WG_ACT_ORIGINAL_REF_REQUIRED")
    hash_value(ref["sha256"])
    require(type(ref["bytes"]) is int and ref["bytes"] >= 0, "WG_ACT_REF_SIZE_INVALID")
    require(type(ref["path"]) is str, "WG_ACT_REF_PATH_TYPE_INVALID")
    p = Path(ref["path"])
    require(p.is_relative_to(_PRIVATE_ROOT) if private else p.is_relative_to(ROOT) or p.is_relative_to(BASELINE_ROOT) or p.is_relative_to(_PRIVATE_ROOT), "WG_ACT_REF_ROOT_INVALID")
    require(not private or p.is_file() and p.stat().st_mode & 0o777 == 0o600, "WG_ACT_PRIVATE_ORIGINAL_REQUIRED")
    raw = checked_reference(ref)
    require(len(raw) == ref["bytes"], "WG_ACT_REF_SIZE_DRIFT")
    return raw


def frozen_input_refs():
    """Direct immutable dependencies, rechecked on every call; never authority."""
    refs = [{"path": str(BASELINE_ROOT / p), "sha256": h, "bytes": n} for p, h, n in _PINNED]
    for r in refs:
        _ref(r)
    return refs


def _day(value):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d\d-\d\d", value), "WG_ACT_SESSION_DATE_INVALID")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("WG_ACT_SESSION_DATE_INVALID") from None


def _clock(token, role=None):
    """Return an internal comparison value; never pad or rewrite the token."""
    _exact(token, {"value", "precision", "basis"}, "WG_ACT_CLOCK_TOKEN_REQUIRED")
    value, precision, basis = token["value"], token["precision"], token["basis"]
    require(type(basis) is str and type(precision) is str, "WG_ACT_CLOCK_BASIS_INVALID")
    if precision == "UNKNOWN":
        require(value == "UNKNOWN" and basis == "UNKNOWN", "WG_ACT_UNKNOWN_CLOCK_INVALID")
        return None
    if precision == "DATE_ONLY":
        _day(value)
        require(basis == "DATE_ONLY_UNKNOWN_FIRST_VISIBILITY", "WG_ACT_DATE_ONLY_BASIS_INVALID")
        return None
    require(precision in _WIDTHS and type(value) is str, "WG_ACT_CLOCK_PRECISION_INVALID")
    match = re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.(\d+))?(?:Z|[+-]\d\d:\d\d)", value)
    require(match is not None and len(match.group(1) or "") == _WIDTHS[precision], "WG_ACT_REPORTED_PRECISION_DRIFT")
    if role:
        require(basis in _BASES[role], "WG_ACT_EVENT_DATE_AS_AVAILABILITY_FORBIDDEN")
    return timestamp(value)


def _local_day(token):
    if _clock(token) is None:
        return None
    return datetime.fromisoformat(token["value"].replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=8))).date().isoformat()


def _native_daily(raw):
    value = _json(raw, numeric_strings=True)
    _exact(value, {"code", "msg", "data"}, "WG_ACT_DAILY_RESPONSE_SCHEMA_DRIFT")
    require(type(value["code"]) is int and value["code"] == 0 and value["msg"] is None, "WG_ACT_DAILY_RESPONSE_FAILED")
    data = value["data"]
    _exact(data, {"fields", "items"}, "WG_ACT_DAILY_RESPONSE_SCHEMA_DRIFT")
    fields = ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]
    require(data["fields"] == fields and type(data["items"]) is list, "WG_ACT_DAILY_RESPONSE_SCHEMA_DRIFT")
    rows, seen = [], set()
    for item in data["items"]:
        require(type(item) is list and len(item) == len(fields), "WG_ACT_DAILY_ROW_SCHEMA_DRIFT")
        r = dict(zip(fields, item))
        require(r["ts_code"] in SYMBOLS and type(r["trade_date"]) is str and re.fullmatch(r"\d{8}", r["trade_date"]), "WG_ACT_RAW_SYMBOL_OR_DATE_INVALID")
        session = r["trade_date"][:4] + "-" + r["trade_date"][4:6] + "-" + r["trade_date"][6:]
        _day(session)
        identity = (r["ts_code"], session)
        require(identity not in seen, "WG_ACT_DUPLICATE_RAW_SYMBOL_SESSION")
        seen.add(identity)
        numbers = {}
        for key in fields[2:]:
            require(type(r[key]) in (str, int), "WG_ACT_RAW_NUMERIC_TYPE_INVALID")
            numbers[key] = str(r[key])
            decimal_string(numbers[key], key not in {"change", "pct_chg"})
        require(decimal_string(numbers["low"]) > 0 and decimal_string(numbers["low"]) <= min(decimal_string(numbers[k]) for k in ("open", "close")) <= max(decimal_string(numbers[k]) for k in ("open", "close")) <= decimal_string(numbers["high"]), "WG_ACT_RAW_OHLC_INVALID")
        rows.append({"symbol": r["ts_code"], "session_date": session, "price_basis": "RAW_UNADJUSTED", "units": {"price": "CNY_PER_SHARE", "volume": "HANDS", "amount": "CNY_THOUSANDS"}, **{k: numbers[k] for k in ("open", "high", "low", "close", "amount")}, "volume": numbers["vol"]})
    return rows


def inspect_daily_original(original_ref, symbol, retrieved_at, expected_session=None):
    """Reopen an existing unadjusted response; daily dates remain DATE_ONLY.

    retrieved_at is caller supplied unless matched against the frozen adopted
    observation map by existing_anchor_projection(). Neither is first visibility.
    """
    require(symbol in SYMBOLS, "WG_ACT_EXACT_THREE_SCOPE_REQUIRED")
    _clock(retrieved_at, "retrieved_at")
    rows = _native_daily(_ref(original_ref, True))
    require(all(r["symbol"] == symbol for r in rows), "WG_ACT_RESPONSE_SYMBOL_SCOPE_DRIFT")
    if expected_session is not None:
        _day(expected_session)
    return {"kind": "ACTUAL_SHAPED_DAILY_READ_ONLY_PROJECTION", "original_ref": copy.deepcopy(original_ref), "symbol": symbol, "row_count": len(rows), "rows": rows, "retrieved_at": copy.deepcopy(retrieved_at), "event_date_precision": "DATE_ONLY", "published_at": "UNKNOWN", "available_at": "UNKNOWN", "expected_session_present": any(r["session_date"] == expected_session for r in rows) if expected_session else "UNKNOWN", "safe_to_trade": False, "actual_forward_days": 0, "live_authority": False}


def existing_anchor_projection(expected_session="2026-10-08"):
    """Exercise the actual-shaped parser on adopted originals, not a fresh B."""
    refs = frozen_input_refs()
    mapping = _json(_ref(refs[1]))
    adopted = {r["path"]: r for r in _json(_ref(refs[0]))["pins"]}
    observations, originals = [], []
    for symbol in SYMBOLS:
        candidates = [x for x in mapping["observation_originals"] if x["api_name"] == "daily" and x["scope"] == "COVERAGE" and x["request_id"] == "daily-" + symbol + "-COVERAGE"]
        require(len(candidates) == 1, "WG_ACT_ADOPTED_ANCHOR_IDENTITY_DRIFT")
        source = candidates[0]
        ref = source["original_refs"][0]
        require(adopted.get(ref["path"]) == ref and source["raw_sha256"] == ref["sha256"], "WG_ACT_ADOPTED_ORIGINAL_UNBOUND")
        retrieved = {"value": source["retrieved_at"], "precision": "MICROSECOND", "basis": "COLLECTOR_RETRIEVAL"}
        projected = inspect_daily_original(ref, symbol, retrieved, expected_session)
        projected.update(request_id=source["request_id"], request_fingerprint=source["request_fingerprint"])
        observations.append(projected)
        originals.append(ref)
    return metadata("WAVE_G_ACTUAL_ANCHOR_PROJECTION", {"state": "EXISTING_CURRENT_OBSERVATION_NOT_SNAPSHOT_B", "expected_session": expected_session, "observations": observations, "direct_input_refs": refs + originals, "snapshot_a_is_admitted": False, "actual_snapshot_b_created": False, "safe_to_trade": False, "no_flags": copy.deepcopy(_NO), "missing_status": "UNKNOWN", "first_visibility": "UNKNOWN_NO_DATE_TO_TIME_IMPUTATION"})


def _slot(slot, capture_id, session, domain):
    _exact(slot, _SLOT_FIELDS, "WG_ACT_SOURCE_SLOT_SHAPE_INVALID")
    require(slot["domain"] == domain and slot["provenance"] in {"REAL_SHAPED_FIXTURE", "UNVERIFIED_ACTUAL_CANDIDATE"}, "WG_ACT_SOURCE_DOMAIN_OR_PROVENANCE_INVALID")
    for key in ("source_identity", "source_version"):
        require(type(slot[key]) is str and 0 < len(slot[key]) <= 160, "WG_ACT_SOURCE_BINDING_REQUIRED")
    row = slot["row"]
    _exact(row, {"RAW_BAR_1D": _BAR, "STATUS_1D": _STATUS, "ACTUAL_SESSION": _CALENDAR}[domain], "WG_ACT_ROW_SCHEMA_DRIFT")
    require(row["session_date"] == session, "WG_ACT_IMPORTED_SESSION_DRIFT")
    _exact(slot["clocks"], _CLOCKS, "WG_ACT_FOUR_CLOCKS_REQUIRED")
    for key in _CLOCKS:
        _clock(slot["clocks"][key], key)
    raw = _ref(slot["original_ref"], True)
    if domain == "RAW_BAR_1D":
        native = _native_daily(raw)
    else:
        payload = _json(raw)
        _exact(payload, {"observations"}, "WG_ACT_OBSERVATION_RESPONSE_SCHEMA_DRIFT")
        require(type(payload["observations"]) is list, "WG_ACT_OBSERVATION_RESPONSE_SCHEMA_DRIFT")
        native = payload["observations"]
        for r in native:
            _exact(r, _STATUS if domain == "STATUS_1D" else _CALENDAR, "WG_ACT_ROW_SCHEMA_DRIFT")
        identities = [(r.get("symbol", "SSE"), r["session_date"]) for r in native]
        require(len(identities) == len(set(identities)), "WG_ACT_DUPLICATE_RAW_SYMBOL_SESSION")
    require(sum(r == row for r in native) == 1, "WG_ACT_SOURCE_ORIGINAL_ROW_BINDING_DRIFT")
    proof = _json(_ref(slot["clock_evidence_ref"], True))
    _exact(proof, {"kind", "provenance", "capture_id", "domain", "source_identity", "source_version", "raw_sha256", "row_hash", "clocks", "current_availability"}, "WG_ACT_CLOCK_EVIDENCE_REQUIRED")
    expected = {"kind": "CAPTURE_CLOCK_EVIDENCE_PREPARATION_V1", "provenance": slot["provenance"], "capture_id": capture_id, "domain": domain, "source_identity": slot["source_identity"], "source_version": slot["source_version"], "raw_sha256": slot["original_ref"]["sha256"], "row_hash": digest(row), "clocks": slot["clocks"], "current_availability": proof["current_availability"]}
    require(proof == expected, "WG_ACT_CLOCK_OR_CAPTURE_SOURCE_ORIGINAL_BINDING_DRIFT")
    current = proof["current_availability"]
    if current != "UNKNOWN":
        _exact(current, {"kind", "version", "visibility", "observed_at", "raw_sha256", "row_hash"}, "WG_ACT_CURRENT_CLOCK_EVIDENCE_REQUIRED")
        require(current["kind"] == "CLOCK_EVIDENCE" and current["version"] == "1.0.0" and current["visibility"] == "OBSERVED_CURRENT_CAPTURE" and current["raw_sha256"] == slot["original_ref"]["sha256"] and current["row_hash"] == digest(row), "WG_ACT_CURRENT_CAPTURE_IS_NOT_HISTORICAL_FIRST_VISIBILITY")
        require(_clock(current["observed_at"], "available_at") is not None, "WG_ACT_CURRENT_CAPTURE_INSTANT_REQUIRED")
        require(current["observed_at"]["basis"] == "COLLECTOR_AVAILABILITY_OBSERVATION", "WG_ACT_CURRENT_CAPTURE_IS_NOT_HISTORICAL_FIRST_VISIBILITY")
    if domain == "STATUS_1D":
        for key in ("listed", "delisted", "st", "suspended"):
            require(type(row[key]) is bool or row[key] == "UNKNOWN", "WG_ACT_STATUS_TYPE_INVALID")
        for key in ("limit_up", "limit_down"):
            if row[key] != "UNKNOWN":
                require(decimal_string(row[key]) > 0, "WG_ACT_LIMIT_INVALID")
    return copy.deepcopy(row), copy.deepcopy(current)


def preflight_hash(packet):
    _exact(packet, _PACKET_FIELDS, "WG_ACT_PREFLIGHT_SHAPE_INVALID")
    return digest({k: v for k, v in packet.items() if k != "review"})


def review_original_refs(packet):
    refs = copy.deepcopy(packet["frozen_inputs"])
    refs.append(copy.deepcopy(packet["snapshot_a"]["original_ref"]))
    for slot in ([packet["calendar"]] if packet["calendar"] else []) + packet["bars"] + packet["statuses"]:
        refs.extend((copy.deepcopy(slot["original_ref"]), copy.deepcopy(slot["clock_evidence_ref"])))
    unique = {canonical(r): r for r in refs}
    return [unique[k] for k in sorted(unique)]


def validate_preflight(packet):
    """Integrity/completeness assessment only; no actual PASS or capability.

    Review JSON and transcripts are untrusted preparation data. An apparently
    complete packet remains BLOCKED until a new Owner scope and independent
    actual collector/review/Human issuer deployment are accepted elsewhere.
    """
    _exact(packet, _PACKET_FIELDS, "WG_ACT_PREFLIGHT_SHAPE_INVALID")
    require(packet["kind"] == PACKET_KIND and packet["mode"] == "PREPARATION_ONLY", "WG_ACT_PREPARATION_ONLY_REQUIRED")
    require(type(packet["capture_id"]) is str and re.fullmatch(r"prep:[A-Za-z0-9_.-]{1,100}", packet["capture_id"]), "WG_ACT_PREPARATION_CAPTURE_ID_REQUIRED")
    require(packet["frozen_inputs"] == frozen_input_refs(), "WG_ACT_FROZEN_SOURCE_POLICY_STRATEGY_SCHEMA_REVIEW_INPUT_DRIFT")
    require(packet["authorizations"] == {"capture": "UNAVAILABLE_NEW_OWNER_REQUIRED", "forward": "UNAVAILABLE_SEPARATE_OWNER_REQUIRED", "actual_issuer": "UNAVAILABLE_NOT_DEPLOYED"}, "WG_ACT_CALLER_AUTHORIZATION_CANNOT_UNLOCK")
    session = _day(packet["expected_session"])
    a = packet["snapshot_a"]
    _exact(a, {"capture_id", "session_date", "retrieved_at", "observed_universe", "raw_observation_hash", "source_policy_hash", "rules_hash", "original_ref", "content_hash"}, "WG_ACT_A_LINEAGE_REQUIRED")
    require(a["observed_universe"] == list(SYMBOLS) and type(a["capture_id"]) is str and a["capture_id"] != packet["capture_id"] and session > _day(a["session_date"]), "WG_ACT_A_TO_B_LINEAGE_DRIFT")
    for k in ("raw_observation_hash", "source_policy_hash", "rules_hash", "content_hash"):
        hash_value(a[k])
    require(a["content_hash"] == digest({k: v for k, v in a.items() if k != "content_hash"}), "WG_ACT_ANCHOR_HASH_INVALID")
    require(_json(_ref(a["original_ref"], True)) == {k: v for k, v in a.items() if k not in {"content_hash", "original_ref"}}, "WG_ACT_A_ORIGINAL_BINDING_DRIFT")
    require(a["source_policy_hash"] == packet["frozen_inputs"][2]["sha256"] and a["rules_hash"] == packet["frozen_inputs"][5]["sha256"], "WG_ACT_ANCHOR_FROZEN_POLICY_DRIFT")
    anchor_ns = _clock(a["retrieved_at"], "retrieved_at")
    captured_ns, cutoff_ns = _clock(packet["captured_at"], "retrieved_at"), _clock(packet["decision_cutoff"])
    findings, clocks = [], []
    def finding(code):
        if code not in findings:
            findings.append(code)
    if anchor_ns is None or captured_ns is None or cutoff_ns is None:
        finding("WG_ACT_CRITICAL_CLOCK_UNKNOWN_OR_DATE_ONLY")
    else:
        require(anchor_ns < captured_ns <= cutoff_ns and _local_day(packet["captured_at"]) == session.isoformat() and _local_day(packet["decision_cutoff"]) == session.isoformat(), "WG_ACT_CAPTURE_FRESHNESS_OR_CUTOFF_DRIFT")
        require(_local_day(a["retrieved_at"]) == a["session_date"], "WG_ACT_ANCHOR_CLOCK_DATE_DRIFT")
    slots, current_evidence = [], {}
    calendar = None
    if packet["calendar"] is None:
        finding("WG_ACT_ACTUAL_OPEN_AND_EOD_UNKNOWN")
    else:
        calendar, current = _slot(packet["calendar"], packet["capture_id"], session.isoformat(), "ACTUAL_SESSION")
        current_evidence[packet["calendar"]["clock_evidence_ref"]["path"]] = current
        slots.append(packet["calendar"])
        if calendar["observation_kind"] != "ACTUAL_OPEN_AND_EOD_OBSERVATION" or calendar["is_open"] is not True:
            finding("WG_ACT_CALENDAR_PLAN_IS_NOT_ACTUAL_SESSION")
        require(calendar["venue"] == "SSE", "WG_ACT_VENUE_DRIFT")
        values = {k: _clock(calendar[k]) for k in ("market_open", "market_close", "actual_open_observed_at", "actual_eod_observed_at")}
        if any(v is None for v in values.values()):
            finding("WG_ACT_ACTUAL_OPEN_AND_EOD_UNKNOWN")
        else:
            require(all(_local_day(calendar[k]) == session.isoformat() for k in values), "WG_ACT_SESSION_CLOCK_DATE_DRIFT")
            require(values["market_open"] <= values["actual_open_observed_at"] < values["market_close"] <= values["actual_eod_observed_at"] and (captured_ns is None or values["actual_eod_observed_at"] <= captured_ns), "WG_ACT_ACTUAL_EOD_NOT_OBSERVED")
            require(values["market_open"] == timestamp(session.isoformat() + "T09:30:00+08:00") and values["market_close"] == timestamp(session.isoformat() + "T15:00:00+08:00"), "WG_ACT_MARKET_BOUNDARY_DRIFT")
    coverage = {}
    unknowns = []
    for key, domain in (("bars", "RAW_BAR_1D"), ("statuses", "STATUS_1D")):
        require(type(packet[key]) is list, "WG_ACT_OBSERVATION_LIST_REQUIRED")
        observed = []
        for slot in packet[key]:
            row, current = _slot(slot, packet["capture_id"], session.isoformat(), domain)
            current_evidence[slot["clock_evidence_ref"]["path"]] = current
            require(row["symbol"] in SYMBOLS and row["symbol"] not in observed, "WG_ACT_EXACT_THREE_DUPLICATE_OR_SCOPE_DRIFT")
            observed.append(row["symbol"])
            slots.append(slot)
            if key == "statuses":
                unknowns.extend({"symbol": row["symbol"], "field": k, "state": "UNKNOWN"} for k in sorted(_STATUS - {"symbol", "session_date"}) if row[k] == "UNKNOWN")
        coverage[key] = {"observed": observed, "missing": [s for s in SYMBOLS if s not in observed]}
        if coverage[key]["missing"]:
            finding("WG_ACT_" + key.upper() + "_COVERAGE_UNKNOWN")
    for slot in slots:
        token_map = slot["clocks"]
        values = {key: _clock(token_map[key], key) for key in _CLOCKS}
        current = current_evidence[slot["clock_evidence_ref"]["path"]]
        current_ns = _clock(current["observed_at"], "available_at") if type(current) is dict else None
        clocks.append({"domain": slot["domain"], "symbol": slot["row"].get("symbol", "SSE"), "clocks": copy.deepcopy(token_map), "current_availability_evidence": current, "historical_first_visibility_proven": False})
        if values["event_time"] is None or values["retrieved_at"] is None:
            finding("WG_ACT_CRITICAL_CLOCK_UNKNOWN_OR_DATE_ONLY")
            continue
        require(all(_local_day(token_map[k]) == session.isoformat() for k in _CLOCKS if values[k] is not None), "WG_ACT_SOURCE_CLOCK_SESSION_DRIFT")
        known = [values[k] for k in _CLOCKS if values[k] is not None]
        require(known == sorted(known) and (cutoff_ns is None or values["retrieved_at"] <= cutoff_ns) and (captured_ns is None or values["retrieved_at"] <= captured_ns) and (anchor_ns is None or values["retrieved_at"] > anchor_ns), "WG_ACT_SOURCE_CLOCK_ORDER_OR_FRESHNESS_DRIFT")
        if current_ns is not None:
            require(_local_day(current["observed_at"]) == session.isoformat() and values["retrieved_at"] <= current_ns and (captured_ns is None or current_ns <= captured_ns) and (cutoff_ns is None or current_ns <= cutoff_ns), "WG_ACT_CURRENT_CAPTURE_CLOCK_ORDER_DRIFT")
        if values["published_at"] is None or values["available_at"] is None:
            if current_ns is None:
                finding("WG_ACT_CRITICAL_CLOCK_UNKNOWN_OR_DATE_ONLY")
        if calendar:
            minimum = _clock(calendar["actual_eod_observed_at"])
            if minimum is not None and slot["domain"] in {"RAW_BAR_1D", "STATUS_1D"}:
                availability = values["available_at"] if values["available_at"] is not None else current_ns
                require(values["event_time"] == _clock(calendar["market_close"]) and values["retrieved_at"] >= minimum and (availability is None or availability >= minimum), "WG_ACT_PRE_EOD_SOURCE_AVAILABILITY")
    raw_identity = digest(sorted({slot["original_ref"]["sha256"] for slot in slots}))
    require(raw_identity != a["raw_observation_hash"], "WG_ACT_B_REUSES_A_RAW_IDENTITY")
    review = packet["review"]
    _exact(review, {"kind", "reviewer_id", "reviewed_packet_hash", "reviewed_original_refs", "reviewed_at", "conclusion"}, "WG_ACT_PREPARATION_REVIEW_REQUIRED")
    require(review["kind"] == "PREPARATION_REVIEW_DISPLAY_ONLY" and review["conclusion"] == "PREPARATION_ONLY" and type(review["reviewer_id"]) is str and review["reviewer_id"] != packet["capture_id"], "WG_ACT_REVIEW_IS_NOT_ACTUAL_ISSUER")
    require(review["reviewed_packet_hash"] == preflight_hash(packet) and review["reviewed_original_refs"] == review_original_refs(packet), "WG_ACT_REVIEW_PACKET_OR_DIRECT_ORIGINAL_DRIFT")
    reviewed_ns = _clock(review["reviewed_at"])
    if reviewed_ns is None:
        finding("WG_ACT_REVIEW_TIME_UNKNOWN")
    else:
        require(captured_ns is None or captured_ns <= reviewed_ns and (cutoff_ns is None or reviewed_ns <= cutoff_ns), "WG_ACT_REVIEW_CLOCK_ORDER_DRIFT")
    return metadata("WAVE_G_SNAPSHOT_B_PREFLIGHT", {"state": "PREPARATION_CHECKED_ACTUAL_ACTIVATION_BLOCKED", "packet_hash": preflight_hash(packet), "capture_id": packet["capture_id"], "expected_session": session.isoformat(), "integrity_checks": "PASS_PREPARATION_ONLY", "preparation_data_complete": not findings, "findings": findings, "coverage": coverage, "status_unknowns": unknowns, "tradeability": "UNKNOWN", "decision": "NO_DECISION", "safe_to_trade": False, "no_flags": copy.deepcopy(_NO), "clock_metadata": clocks, "raw_observation_hash": raw_identity, "snapshot_a_hash": a["content_hash"], "direct_input_refs": review_original_refs(packet), "actual_snapshot_b_created": False, "actual_issuer_available": False, "caller_review_is_actual_authority": False, "actual_open_eod_independently_accepted": False, "remaining_actual_work": _actual_work(), "account_cost_risk": {k: UNSET for k in ("account", "cost", "risk")}})


def _actual_work():
    return ["NEW_OWNER_ONCE_EXACT_THREE_READ_ONLY_CAPTURE_SCOPE", "FRESH_ACTUAL_OPEN_EOD_AND_SOURCE_AVAILABILITY_ACCEPTANCE", "ACTUAL_COLLECTOR_TRANSPORT_SOURCE_CLOCK_TRANSCRIPT_DEPLOYMENT_AND_REVIEW", "VERSION_BOUND_SOURCE_EXCEPTION_AND_CAPTURE_ACCEPTANCE_POLICY", "INDEPENDENT_ACTUAL_ORIGINAL_REOPEN_REVIEW_ISSUER", "SEPARATE_OWNER_FORWARD_SCOPE_AND_HUMAN_ISSUER", "ACTUAL_STORE_EXACTLY_ONCE_APPEND_DEPLOYMENT_AND_INDEPENDENT_REVIEW"]


def snapshot_readiness():
    return metadata("WAVE_G_SNAPSHOT_B_ACTIVATION_READINESS", {"state": "READ_ONLY_REAL_SHAPED_PREFLIGHT_IMPLEMENTED_ACTUAL_BLOCKED", "planned_first_post_holiday_session": "2026-10-08", "calendar_plan_is_actual_session": False, "actual_fresh_session_observed": False, "actual_eod_observed": False, "actual_snapshot_b_created": False, "exact_symbols": list(SYMBOLS), "adapter": "FILE_REOPEN_HASH_NATIVE_RESPONSE_ROW_CLOCK_TRANSCRIPT_COMPARISON_PREPARATION_ONLY", "clock_precision": ["SECOND", "MILLISECOND", "MICROSECOND", "NANOSECOND", "DATE_ONLY", "UNKNOWN"], "date_only_unknown": "PRESERVED_NO_IMPUTATION_CURRENT_CAPTURE_EVIDENCE_DOES_NOT_PROVE_HISTORICAL_FIRST_VISIBILITY", "source_admission": "BLOCKED_PROVIDER_LICENSE_TRANSPORT_UNVERIFIED", "only_human_authorization_missing": False, "required_future_evidence": _actual_work(), "direct_input_refs": frozen_input_refs(), "safe_to_trade": False, "no_flags": copy.deepcopy(_NO), "scheduled": False})


def forward_readiness():
    return metadata("WAVE_G_FORWARD_PAPER_ACTIVATION_READINESS", {"state": "NO_DECISION_FIXTURE_AND_REAL_SHAPED_PREFLIGHT_READY_ACTUAL_BLOCKED", "supported_decision": "NO_DECISION", "durable_fixture_engine": "IMMUTABLE_WAVE_F_1.0.1_SQLITE_NO_DECISION_ONLY", "actual_record_appended": False, "actual_approval_issuer": "UNAVAILABLE_NOT_DEPLOYED", "actual_store": "GENERIC_ALGORITHM_IMPLEMENTED_OFFLINE_STAGING_ACTUAL_MODE_HARDBLOCKED", "staging_store_configuration": staging_store_configuration(), "future_requirements": _actual_work(), "real_money_parameters_block_no_decision_engineering": False, "real_account_parameters": {k: UNSET for k in ("account", "cost", "risk")}, "synthetic_days_count_as_actual": False, "safe_to_trade": False, "no_flags": copy.deepcopy(_NO), "native_order_fields_supported": False, "execution_or_native_promotion": False, "privileged_rewrite_or_hostile_interpreter_proof": False, "direct_input_refs": frozen_input_refs(), "scheduled": False})


# A new isolated preparation store, never an actual Forward ledger. The same
# transaction/chain algorithms are implemented here over real-shaped packets;
# an actual authority boundary must be added and independently accepted later.
_ST_LOCK = threading.RLock()
_ST_TABLES = {
    "staging_metadata": "CREATE TABLE staging_metadata(id INTEGER PRIMARY KEY CHECK(id=1),body TEXT NOT NULL,hash TEXT NOT NULL)",
    "staging_records": "CREATE TABLE staging_records(sequence INTEGER PRIMARY KEY CHECK(sequence>0),session TEXT NOT NULL UNIQUE,capture_id TEXT NOT NULL UNIQUE,observation_hash TEXT NOT NULL UNIQUE,previous_hash TEXT NOT NULL,record_hash TEXT NOT NULL UNIQUE,body TEXT NOT NULL)",
    "staging_failures": "CREATE TABLE staging_failures(sequence INTEGER PRIMARY KEY CHECK(sequence>0),attempt_id TEXT NOT NULL UNIQUE,previous_hash TEXT NOT NULL,attempt_hash TEXT NOT NULL UNIQUE,body TEXT NOT NULL)",
}
_ST_TRIGGERS = {}
for _table in _ST_TABLES:
    for _operation in ("UPDATE", "DELETE"):
        name = _table + "_no_" + _operation.lower()
        _ST_TRIGGERS[name] = "CREATE TRIGGER " + name + " BEFORE " + _operation + " ON " + _table + " BEGIN SELECT RAISE(ABORT,'WG_ACT_STAGING_APPEND_ONLY'); END"
    name = _table + "_guard_insert"
    _ST_TRIGGERS[name] = "CREATE TRIGGER " + name + " BEFORE INSERT ON " + _table + " WHEN wave_g_staging_capability()!=1 BEGIN SELECT RAISE(ABORT,'WG_ACT_STAGING_CAPABILITY_REQUIRED'); END"


def staging_store_configuration():
    return {"kind": "WAVE_G_NO_DECISION_STAGING_CONFIGURATION", "version": "1.0.0", "namespace": "OFFLINE_REAL_SHAPED_FIXTURE_STAGING_ONLY", "suffix": ".wave-g.staging.sqlite3", "directory_mode": "0700", "file_mode": "0600", "schema_version": 1, "tables": sorted(_ST_TABLES), "record_decision": "NO_DECISION", "safe_to_trade": False, "no_flags": copy.deepcopy(_NO), "actual_forward_days": 0, "actual_mode": "HARD_BLOCKED", "algorithm_implemented": ["EXCLUSIVE_CREATION", "CANONICAL_PATH_SCHEMA_HASH_BINDING", "BEGIN_IMMEDIATE_EXPECTED_HEAD_ATOMIC_APPEND", "SESSION_CAPTURE_RAW_OBSERVATION_DEDUPLICATION", "FROZEN_INPUT_SOURCE_VERSION_AND_A_ANCHOR_BINDING", "SANITIZED_APPEND_ONLY_FAILURE_CHAIN", "REOPEN_ALL_ORIGINALS_ON_INSPECTION_RESTART", "NO_REPAIR_RECOVERY"], "future_coding_required": ["SEPARATELY_AUTHORIZED_ACTUAL_COLLECTOR_AND_SOURCE_SPECIFIC_ADAPTER_BINDING", "INDEPENDENT_CAPTURE_REVIEW_AND_HUMAN_SCOPED_ISSUER_CAPABILITY_ADAPTER", "NEW_REVIEWED_ACTUAL_NAMESPACE_AND_COUNTING_BINDING_TO_ACCEPTED_SESSIONS"], "core_sqlite_append_chain_algorithm_rebuild_required": False, "money_configuration_required_for_no_decision_staging": False}


def _st_path(path, existing):
    require(type(path) is str or isinstance(path, Path), "WG_ACT_STAGING_PATH_INVALID")
    p = Path(path)
    require(p.is_absolute() and p.resolve() == p and not p.is_symlink() and p.is_relative_to(_PRIVATE_ROOT) and p.name.endswith(".wave-g.staging.sqlite3"), "WG_ACT_STAGING_PATH_INVALID")
    require(p.parent.is_dir() and p.parent.stat().st_mode & 0o777 == 0o700, "WG_ACT_STAGING_PRIVATE_PARENT_REQUIRED")
    require(p.is_file() and p.stat().st_mode & 0o777 == 0o600 if existing else not p.exists(), "WG_ACT_STAGING_STORE_REQUIRED_OR_EXISTS")
    return p


def _st_connect(p, write=False):
    conn = sqlite3.connect(p.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, isolation_level=None, timeout=10)
    if write:
        conn.execute("PRAGMA synchronous=FULL")
        conn.create_function("wave_g_staging_capability", 0, lambda: 1)
    return conn


def _st_decode(raw):
    value = _json(raw)
    require(canonical(value).decode() == raw, "WG_ACT_STAGING_NON_CANONICAL")
    return value


def _st_fixture_packet(packet):
    _exact(packet, _PACKET_FIELDS, "WG_ACT_PREFLIGHT_SHAPE_INVALID")
    slots = ([packet["calendar"]] if packet["calendar"] else []) + packet["bars"] + packet["statuses"]
    require(slots and all(type(x) is dict and x.get("provenance") == "REAL_SHAPED_FIXTURE" for x in slots), "WG_ACT_STAGING_FIXTURE_ONLY_ACTUAL_APPEND_FORBIDDEN")
    value = validate_preflight(packet)
    require(value["body"]["preparation_data_complete"], "WG_ACT_STAGING_INCOMPLETE_PREFLIGHT")
    return value


def _st_frozen(packet):
    slots = [packet["calendar"]] + packet["bars"] + packet["statuses"]
    source = sorted({(x["domain"], x["source_identity"], x["source_version"]) for x in slots})
    return digest({"frozen_inputs": packet["frozen_inputs"], "snapshot_a_hash": packet["snapshot_a"]["content_hash"], "source_bindings": [list(x) for x in source]})


def _st_inspect(conn, p):
    expected = {k: ("table", v) for k, v in _ST_TABLES.items()} | {k: ("trigger", v) for k, v in _ST_TRIGGERS.items()}
    actual = {name: (kind, sql) for name, kind, sql in conn.execute("SELECT name,type,sql FROM sqlite_schema WHERE sql IS NOT NULL")}
    require(actual == expected and conn.execute("PRAGMA user_version").fetchone()[0] == 1 and conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "WG_ACT_STAGING_SCHEMA_OR_INTEGRITY_DRIFT")
    stored = conn.execute("SELECT id,body,hash FROM staging_metadata").fetchall()
    require(len(stored) == 1 and stored[0][0] == 1, "WG_ACT_STAGING_METADATA_INVALID")
    meta = _st_decode(stored[0][1])
    _exact(meta, {"kind", "version", "namespace", "canonical_path", "store_id", "configuration", "frozen_inputs"}, "WG_ACT_STAGING_METADATA_INVALID")
    require(meta["kind"] == "WAVE_G_OFFLINE_STAGING_STORE" and meta["version"] == "1.0.0" and meta["namespace"] == "OFFLINE_REAL_SHAPED_FIXTURE_STAGING_ONLY" and meta["canonical_path"] == str(p) and type(meta["store_id"]) is str and re.fullmatch(r"staging:[0-9a-f]{32}", meta["store_id"]) and meta["configuration"] == staging_store_configuration() and meta["frozen_inputs"] == frozen_input_refs() and digest(meta) == stored[0][2], "WG_ACT_STAGING_METADATA_OR_PATH_BINDING_DRIFT")
    head = digest({"kind": "STAGING_RECORDS_GENESIS", "metadata_hash": stored[0][2]})
    records, seen_sessions, seen_captures, seen_raw = [], set(), set(), set()
    frozen = None
    for row in conn.execute("SELECT sequence,session,capture_id,observation_hash,previous_hash,record_hash,body FROM staging_records ORDER BY sequence"):
        record = _st_decode(row[6])
        _exact(record, {"sequence", "previous_hash", "record_hash", "packet", "validation_hash", "frozen_binding", "decision", "tradeability", "safe_to_trade", "no_flags", "actual_forward_days", "provenance"}, "WG_ACT_STAGING_RECORD_SHAPE_INVALID")
        packet = record["packet"]
        value = _st_fixture_packet(packet)
        require(record["validation_hash"] == digest(value) and record["frozen_binding"] == _st_frozen(packet) and record["decision"] == "NO_DECISION" and record["tradeability"] == "UNKNOWN" and record["safe_to_trade"] is False and record["no_flags"] == _NO and type(record["actual_forward_days"]) is int and record["actual_forward_days"] == 0 and record["provenance"] == "REAL_SHAPED_FIXTURE_NEVER_ACTUAL_SESSION", "WG_ACT_STAGING_NO_DECISION_OR_INPUT_DRIFT")
        require(type(record["sequence"]) is int and record["sequence"] == len(records) + 1 and record["previous_hash"] == head and record["record_hash"] == digest({k: v for k, v in record.items() if k != "record_hash"}), "WG_ACT_STAGING_RECORD_CHAIN_DRIFT")
        raw_identity = value["body"]["raw_observation_hash"]
        require(tuple(row[:6]) == (record["sequence"], packet["expected_session"], packet["capture_id"], raw_identity, head, record["record_hash"]), "WG_ACT_STAGING_RECORD_COLUMN_DRIFT")
        require(packet["expected_session"] not in seen_sessions and packet["capture_id"] not in seen_captures and raw_identity not in seen_raw and (not records or packet["expected_session"] > records[-1]["packet"]["expected_session"]), "WG_ACT_STAGING_DUPLICATE_OR_SESSION_ORDER")
        frozen = frozen or record["frozen_binding"]
        require(record["frozen_binding"] == frozen, "WG_ACT_STAGING_FROZEN_INPUT_OR_ANCHOR_DRIFT")
        seen_sessions.add(packet["expected_session"]); seen_captures.add(packet["capture_id"]); seen_raw.add(raw_identity)
        records.append(record); head = record["record_hash"]
    failure_head = digest({"kind": "STAGING_FAILURES_GENESIS", "metadata_hash": stored[0][2]})
    failures = []
    for row in conn.execute("SELECT sequence,attempt_id,previous_hash,attempt_hash,body FROM staging_failures ORDER BY sequence"):
        item = _st_decode(row[4])
        _exact(item, {"sequence", "attempt_id", "previous_hash", "attempt_hash", "kind", "reason_code", "untrusted_payload_retained", "actual_forward_days"}, "WG_ACT_STAGING_FAILURE_SHAPE_INVALID")
        require(item["kind"] == "SANITIZED_STAGING_FIXTURE_FAILURE" and type(item["reason_code"]) is str and re.fullmatch(r"WG_ACT_[A-Z0-9_]{1,120}", item["reason_code"]) and type(item["attempt_id"]) is str and re.fullmatch(r"staging-failure:[0-9a-f]{32}", item["attempt_id"]) and item["untrusted_payload_retained"] is False and type(item["actual_forward_days"]) is int and item["actual_forward_days"] == 0, "WG_ACT_STAGING_FAILURE_METADATA_INVALID")
        require(type(item["sequence"]) is int and item["sequence"] == len(failures) + 1 and item["previous_hash"] == failure_head and item["attempt_hash"] == digest({k: v for k, v in item.items() if k != "attempt_hash"}) and tuple(row[:4]) == (item["sequence"], item["attempt_id"], failure_head, item["attempt_hash"]), "WG_ACT_STAGING_FAILURE_CHAIN_DRIFT")
        failures.append(item); failure_head = item["attempt_hash"]
    return {"kind": "WAVE_G_OFFLINE_STAGING_DISPLAY_ONLY", "namespace": meta["namespace"], "head_hash": head, "failure_head_hash": failure_head, "staged_fixture_count": len(records), "failed_attempt_count": len(failures), "records": records, "failed_attempts": failures, "actual_forward_days": 0, "actual_record_appended": False, "decision": "NO_DECISION", "safe_to_trade": False, "no_flags": copy.deepcopy(_NO), "live_authority": False}


def create_staging_store(path):
    p = _st_path(path, False)
    frozen = frozen_input_refs()
    descriptor = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600); os.close(descriptor)
    conn = _st_connect(p, True)
    try:
        conn.execute("PRAGMA journal_mode=DELETE"); conn.execute("BEGIN IMMEDIATE")
        for sql in _ST_TABLES.values(): conn.execute(sql)
        body = {"kind": "WAVE_G_OFFLINE_STAGING_STORE", "version": "1.0.0", "namespace": "OFFLINE_REAL_SHAPED_FIXTURE_STAGING_ONLY", "canonical_path": str(p), "store_id": "staging:" + uuid.uuid4().hex, "configuration": staging_store_configuration(), "frozen_inputs": frozen}
        conn.execute("INSERT INTO staging_metadata VALUES(1,?,?)", (canonical(body).decode(), digest(body)))
        for sql in _ST_TRIGGERS.values(): conn.execute(sql)
        conn.execute("PRAGMA user_version=1")
        result = _st_inspect(conn, p); conn.execute("COMMIT")
        return result
    finally:
        if conn.in_transaction: conn.execute("ROLLBACK")
        conn.close()
        # Failed initialization remains untouched for independent inspection.


def inspect_staging_store(path):
    p = _st_path(path, True); conn = _st_connect(p)
    try:
        conn.execute("BEGIN")
        return _st_inspect(conn, p)
    finally:
        if conn.in_transaction: conn.execute("ROLLBACK")
        conn.close()


def stage_preflight_packet(path, packet, expected_head):
    value = _st_fixture_packet(packet)
    hash_value(expected_head)
    with _ST_LOCK:
        p = _st_path(path, True); conn = _st_connect(p, True)
        try:
            conn.execute("BEGIN IMMEDIATE"); before = _st_inspect(conn, p)
            require(before["head_hash"] == expected_head, "WG_ACT_STAGING_STALE_EXPECTED_HEAD")
            for old in before["records"]:
                require(old["packet"]["expected_session"] != packet["expected_session"] and old["packet"]["capture_id"] != packet["capture_id"] and _st_fixture_packet(old["packet"])["body"]["raw_observation_hash"] != value["body"]["raw_observation_hash"], "WG_ACT_STAGING_DUPLICATE_SESSION_CAPTURE_OR_RAW")
            if before["records"]:
                old = before["records"][-1]
                require(packet["expected_session"] > old["packet"]["expected_session"] and _st_frozen(packet) == old["frozen_binding"], "WG_ACT_STAGING_FROZEN_INPUT_ANCHOR_OR_SESSION_ORDER_DRIFT")
            record = {"sequence": before["staged_fixture_count"] + 1, "previous_hash": expected_head, "packet": copy.deepcopy(packet), "validation_hash": digest(value), "frozen_binding": _st_frozen(packet), "decision": "NO_DECISION", "tradeability": "UNKNOWN", "safe_to_trade": False, "no_flags": copy.deepcopy(_NO), "actual_forward_days": 0, "provenance": "REAL_SHAPED_FIXTURE_NEVER_ACTUAL_SESSION"}
            record["record_hash"] = digest(record)
            conn.execute("INSERT INTO staging_records VALUES(?,?,?,?,?,?,?)", (record["sequence"], packet["expected_session"], packet["capture_id"], value["body"]["raw_observation_hash"], expected_head, record["record_hash"], canonical(record).decode()))
            result = _st_inspect(conn, p); conn.execute("COMMIT")
            return result
        finally:
            if conn.in_transaction: conn.execute("ROLLBACK")
            conn.close()


def attempt_staging_packet(path, packet, expected_head):
    try:
        return stage_preflight_packet(path, packet, expected_head)
    except ValueError as error:
        reason = str(error)
        if not re.fullmatch(r"WG_ACT_[A-Z0-9_]{1,120}", reason): reason = "WG_ACT_STAGING_INVALID_PREPARATION_INPUT"
        with _ST_LOCK:
            p = _st_path(path, True); conn = _st_connect(p, True)
            try:
                conn.execute("BEGIN IMMEDIATE"); before = _st_inspect(conn, p)
                item = {"sequence": before["failed_attempt_count"] + 1, "attempt_id": "staging-failure:" + uuid.uuid4().hex, "previous_hash": before["failure_head_hash"], "kind": "SANITIZED_STAGING_FIXTURE_FAILURE", "reason_code": reason, "untrusted_payload_retained": False, "actual_forward_days": 0}
                item["attempt_hash"] = digest(item)
                conn.execute("INSERT INTO staging_failures VALUES(?,?,?,?,?)", (item["sequence"], item["attempt_id"], item["previous_hash"], item["attempt_hash"], canonical(item).decode()))
                _st_inspect(conn, p); conn.execute("COMMIT")
            finally:
                if conn.in_transaction: conn.execute("ROLLBACK")
                conn.close()
        raise


def recover_staging_store(path, expected_head=None):
    result = inspect_staging_store(path)
    if expected_head is not None:
        hash_value(expected_head)
        require(result["head_hash"] == expected_head, "WG_ACT_STAGING_RECOVERY_HEAD_MISMATCH")
    return {"kind": "WAVE_G_STAGING_RECOVERY_DISPLAY_ONLY", "recovery_action": "VERIFIED_READ_ONLY_NO_REPAIR", "result": result, "actual_forward_days": 0, "actual_issuer_required_before_any_future_actual_mode": True, "live_authority": False}


def _fixture():
    frozen_input_refs()
    from wave_f import activation
    return activation


def create_fixture_ledger(path):
    return _fixture().create_fixture_ledger(path)


def issue_fixture_approval(kind, case):
    return _fixture().issue_fixture_approval(kind, case)


def append_fixture_day(path, approval, expected_head):
    return _fixture().append_fixture_day(path, approval, expected_head)


def attempt_fixture_day(path, kind, case, expected_head):
    return _fixture().attempt_fixture_day(path, kind, case, expected_head)


def inspect_fixture_ledger(path):
    return _fixture().inspect_fixture_ledger(path)


def recover_fixture_ledger(path, expected_head=None):
    return _fixture().recover_fixture_ledger(path, expected_head)


def execute_capture(*args, **kwargs):
    raise ValueError("WG_ACT_ACTUAL_CAPTURE_NOT_AUTHORIZED")


def append_actual_session(*args, **kwargs):
    raise ValueError("WG_ACT_ACTUAL_FORWARD_APPEND_NOT_AUTHORIZED")


def run_snapshot_b(*args, **kwargs):
    raise ValueError("WG_ACT_ACTUAL_SNAPSHOT_B_NOT_AUTHORIZED")


def run_real_forward(*args, **kwargs):
    raise ValueError("WG_ACT_ACTUAL_FORWARD_NOT_AUTHORIZED")
