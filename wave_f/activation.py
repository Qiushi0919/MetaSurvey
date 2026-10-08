"""Wave F activation preparation; every positive path is explicitly synthetic.

No actual snapshot, research Paper session, human approval, account ledger,
Signal, Order or Fill can be issued here. ``run_snapshot_b``,
``run_real_forward`` and ``append_actual_session`` unconditionally reject.

Fixture capture v1.0.1 is a closed JSON object with fields kind, provenance,
namespace, version, capture_id, expected_session, captured_at, decision_cutoff,
snapshot_a, calendar, bars, statuses, bindings, review and authorization.
kind=SYNTHETIC_ACTIVATION_CAPTURE, provenance=SYNTHETIC_NOT_OWNER_POLICY,
namespace=LOCAL_FORWARD_PAPER_FIXTURE:CORE_40 and version=1.0.1. Shared readiness
metadata remains version=1.0.0; this is a locally versioned synthetic shape,
not a new project-level contract. Identifiers
are fixture:<alphanumeric/underscore/hyphen>; source URIs fixture:// only.

snapshot_a fields: kind SYNTHETIC_SNAPSHOT_A_ANCHOR, capture_id, session_date
2026-09-30, retrieved_at, observed_universe (exact three symbols),
raw_observation_hash, source_policy_hash, rules_hash, content_hash. Its
content_hash seals all other fields. A is a fixture current-observation anchor,
never an admitted snapshot. Capturing different bytes with A's capture_id
does not count as B.

calendar fields: kind SYNTHETIC_ACTUAL_OPEN_OBSERVATION, venue SSE,
session_date, is_open True, market_open, market_close, actual_open_observed_at,
source, source_version, source_hash, source_payload, clocks. Each of the three bars has
symbol, session_date, price_basis RAW_UNADJUSTED, units {price:CNY_PER_SHARE,
volume:SHARES}, open/high/low/close Decimal strings, volume integer, source,
source_version, source_hash, source_payload, clocks. Each status has symbol, session_date,
listed/delisted/st/suspended bool or UNKNOWN, limit_up/limit_down positive
Decimal strings or UNKNOWN, source/source_version/source_hash/source_payload/clocks. Clocks
are exactly event_time/published_at/available_at/retrieved_at/precision,
precision=NANOSECOND; each instant is YYYY-MM-DDTHH:MM:SS.nnnnnnnnn+08:00.
No DATE_ONLY or imputed midnight. Status unknowns are retained; absence is
not an assertion of safety. Current implementation requires all three bars:
it deliberately does not treat a missing suspended-security bar as complete.

Each source_payload is a closed canonical JSON fixture original with kind
SYNTHETIC_SOURCE_ORIGINAL, provenance SYNTHETIC_NOT_OWNER_POLICY, version
1.0.1, domain CALENDAR_ACTUAL_OPEN / RAW_BAR_1D / STATUS_1D, source,
source_version, and row. row is the exact imported observation excluding
source/source_version/source_hash/source_payload. It includes original dates,
symbol where applicable, values, units and all original observation clocks.
source_hash = sha256(canonical(source_payload)). The imported row, URI and
version must exactly match the original. Changing wrapper dates/clocks or
source URI, then re-sealing DISPLAY/review metadata cannot relabel an old raw
daily observation as a fresh one. These embedded packets are solely synthetic;
they are not proof of actual supplier originals or historical availability.

bindings fields: source_version, rules_version, strategy_version,
source_policy_version, schema_version, rules_hash, strategy_hash,
source_policy_hash, schema_hash, review_policy_hash. Versions are explicit
fixture-* strings. review fields: kind SYNTHETIC_INDEPENDENT_REVIEW,
reviewer_id, reviewed_capture_hash, reviewed_strategy_hash, review_policy_hash,
reviewed_at, conclusion FIXTURE_PREPARATION_ONLY. reviewed_capture_hash hashes
the capture excluding review/authorization. This is fixture review data,
not proof of an actual independent review. authorization fields: kind
SYNTHETIC_HUMAN_USER, authorization_id, issued_at, expires_at. The function
issue_fixture_approval returns an opaque process-local fixture capability;
caller strings, copied objects and persisted JSON do not become real authority.

The new private *.wave-f.fixture.sqlite3 store contains metadata, days and
failed_attempts only. Days are generated internally as NO_DECISION, with
safe_to_trade=False, tradeability=UNKNOWN, actual_forward_days=0 and account/
cost/risk=UNSET_REQUIRED. This does not require actual money policy. Failure
preservation stores a sanitized reason and a generated attempt ID, never the
untrusted failed payload or its hash. Both chains are append-only, canonical,
path-bound and checked under BEGIN IMMEDIATE. Expected head, duplicate day,
capture identity, observation identity and frozen-policy checks are atomic.
Recovery is inspection only; it never truncates, fixes or re-seals corruption.
Ordinary trigger/schema/hash checks are not proof against a privileged writer
replacing and re-sealing an entire store, or a hostile Python interpreter.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
import uuid

from .common import SYMBOLS, UNSET, VERSION, canonical, digest, require, hash_value, decimal_string, metadata

NAMESPACE = "LOCAL_FORWARD_PAPER_FIXTURE:CORE_40"
PROVENANCE = "SYNTHETIC_NOT_OWNER_POLICY"
FIXTURE_CAPTURE_VERSION = "1.0.1"
_BASELINE = "2026-09-30"
_TS = re.compile(r"^(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)\.(\d{9})\+08:00$")
_ID = re.compile(r"^fixture:[A-Za-z0-9_-]{1,80}$")
_VERSION = re.compile(r"^fixture-[A-Za-z0-9_.-]{1,80}$")
_SOURCE = re.compile(r"^fixture://[A-Za-z0-9_./-]{1,150}$")
_CASE = {"kind", "provenance", "namespace", "version", "capture_id", "expected_session", "captured_at", "decision_cutoff", "snapshot_a", "calendar", "bars", "statuses", "bindings", "review", "authorization"}
_CLOCKS = {"event_time", "published_at", "available_at", "retrieved_at", "precision"}
_BINDINGS = {"source_version", "rules_version", "strategy_version", "source_policy_version", "schema_version", "rules_hash", "strategy_hash", "source_policy_hash", "schema_hash", "review_policy_hash"}
_FROZEN = set(_BINDINGS)
_LOCK = threading.RLock()


def _exact(value, fields, reason):
    require(type(value) is dict and set(value) == fields, reason)
    canonical(value)


def _day(value):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d\d-\d\d", value), "WF_ACT_SESSION_DATE_INVALID")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("WF_ACT_SESSION_DATE_INVALID") from None


def _instant(value):
    match = _TS.fullmatch(value) if type(value) is str else None
    require(match is not None, "WF_ACT_NANOSECOND_SHANGHAI_INSTANT_REQUIRED")
    day, clock, nanos = match.groups()
    try:
        parsed = datetime.strptime(day + "T" + clock, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        raise ValueError("WF_ACT_INSTANT_INVALID") from None
    require(clock != "00:00:00", "WF_ACT_MIDNIGHT_IMPUTATION_FORBIDDEN")
    value_ns = parsed.date().toordinal() * 86_400_000_000_000
    value_ns += (parsed.hour * 3600 + parsed.minute * 60 + parsed.second) * 1_000_000_000 + int(nanos)
    return day, clock, value_ns


def _identifier(value):
    require(type(value) is str and _ID.fullmatch(value), "WF_ACT_FIXTURE_ID_REQUIRED")


def _source(row, expected_version, domain):
    require(type(row["source"]) is str and _SOURCE.fullmatch(row["source"]), "WF_ACT_FIXTURE_SOURCE_REQUIRED")
    require(row["source_version"] == expected_version, "WF_ACT_SOURCE_VERSION_DRIFT")
    hash_value(row["source_hash"])
    original = row["source_payload"]
    _exact(original, {"kind", "provenance", "version", "domain", "source", "source_version", "row"}, "WF_ACT_SOURCE_ORIGINAL_REQUIRED")
    require(original["kind"] == "SYNTHETIC_SOURCE_ORIGINAL" and original["provenance"] == PROVENANCE and original["version"] == FIXTURE_CAPTURE_VERSION and original["domain"] == domain, "WF_ACT_SOURCE_ORIGINAL_KIND_OR_DOMAIN_DRIFT")
    require(digest(original) == row["source_hash"], "WF_ACT_SOURCE_ORIGINAL_HASH_INVALID")
    expected_row = {key: value for key, value in row.items() if key not in {"source", "source_version", "source_hash", "source_payload"}}
    require(original["source"] == row["source"] and original["source_version"] == row["source_version"] and original["row"] == expected_row, "WF_ACT_SOURCE_ORIGINAL_ROW_BINDING_DRIFT")


def _clocks(value, session, anchor_ns, cutoff_ns, event_ns, minimum_ns):
    _exact(value, _CLOCKS, "WF_ACT_FOUR_CLOCKS_REQUIRED")
    require(value["precision"] == "NANOSECOND", "WF_ACT_DATE_ONLY_FORBIDDEN")
    times = {key: _instant(value[key]) for key in _CLOCKS - {"precision"}}
    require(all(value[0] == session for value in times.values()), "WF_ACT_CLOCK_SESSION_DRIFT")
    require(times["event_time"][2] == event_ns, "WF_ACT_EVENT_TIME_DRIFT")
    require(minimum_ns <= times["published_at"][2] <= times["available_at"][2] <= times["retrieved_at"][2] <= cutoff_ns, "WF_ACT_CLOCK_ORDER_OR_FUTURE")
    require(times["retrieved_at"][2] > anchor_ns, "WF_ACT_RETRIEVAL_NOT_AFTER_A")
    return times["retrieved_at"][2]


def fixture_capture_hash(case):
    """Data-only fingerprint for fixture review construction, never authority."""
    _exact(case, _CASE, "WF_ACT_CAPTURE_SHAPE_INVALID")
    require(case["kind"] == "SYNTHETIC_ACTIVATION_CAPTURE" and case["provenance"] == PROVENANCE, "WF_ACT_SYNTHETIC_CAPTURE_REQUIRED")
    return digest({key: value for key, value in case.items() if key not in {"review", "authorization"}})


def _observations_hash(case):
    return digest({"calendar": case["calendar"], "bars": case["bars"], "statuses": case["statuses"]})


def validate_fixture_capture(case):
    """Strict fresh-session/EOD algorithm over explicitly synthetic observations.

    This returns NON_TRADEABLE DISPLAY_ONLY metadata. It never observes a real
    session and never constructs an actual/admitted Snapshot B.
    """
    _exact(case, _CASE, "WF_ACT_CAPTURE_SHAPE_INVALID")
    require(case["kind"] == "SYNTHETIC_ACTIVATION_CAPTURE" and case["provenance"] == PROVENANCE, "WF_ACT_SYNTHETIC_CAPTURE_REQUIRED")
    require(case["namespace"] == NAMESPACE and case["version"] == FIXTURE_CAPTURE_VERSION, "WF_ACT_NAMESPACE_OR_VERSION_DRIFT")
    _identifier(case["capture_id"])
    day = _day(case["expected_session"])
    require(day > _day(_BASELINE), "WF_ACT_SESSION_NOT_AFTER_A")
    # A bounded 2026 holiday fixture check, not an actual-open observation.
    require(day.weekday() < 5 and not date(2026, 10, 1) <= day <= date(2026, 10, 7), "WF_ACT_FIXTURE_CALENDAR_CLOSED")
    session = day.isoformat()
    cutoff = _instant(case["decision_cutoff"])
    captured = _instant(case["captured_at"])
    require(cutoff[0] == session and captured[0] == session and captured[2] <= cutoff[2], "WF_ACT_CAPTURE_CUTOFF_DRIFT")

    a = case["snapshot_a"]
    _exact(a, {"kind", "capture_id", "session_date", "retrieved_at", "observed_universe", "raw_observation_hash", "source_policy_hash", "rules_hash", "content_hash"}, "WF_ACT_ANCHOR_SHAPE_INVALID")
    require(a["kind"] == "SYNTHETIC_SNAPSHOT_A_ANCHOR" and a["session_date"] == _BASELINE and a["observed_universe"] == list(SYMBOLS), "WF_ACT_ANCHOR_BINDING_INVALID")
    _identifier(a["capture_id"])
    anchor = _instant(a["retrieved_at"])
    require(anchor[0] == _BASELINE and a["capture_id"] != case["capture_id"], "WF_ACT_CAPTURE_ID_NOT_FRESH")
    for key in ("raw_observation_hash", "source_policy_hash", "rules_hash", "content_hash"):
        hash_value(a[key])
    require(a["content_hash"] == digest({key: value for key, value in a.items() if key != "content_hash"}), "WF_ACT_ANCHOR_HASH_INVALID")
    require(captured[2] > anchor[2], "WF_ACT_CAPTURE_NOT_AFTER_A")

    bound = case["bindings"]
    _exact(bound, _BINDINGS, "WF_ACT_BINDINGS_SHAPE_INVALID")
    for key, value in bound.items():
        if key.endswith("_hash"):
            hash_value(value)
        else:
            require(type(value) is str and _VERSION.fullmatch(value), "WF_ACT_EXPLICIT_FIXTURE_VERSION_REQUIRED")
    require(a["source_policy_hash"] == bound["source_policy_hash"] and a["rules_hash"] == bound["rules_hash"], "WF_ACT_A_TO_B_POLICY_DRIFT")

    calendar = case["calendar"]
    _exact(calendar, {"kind", "venue", "session_date", "is_open", "market_open", "market_close", "actual_open_observed_at", "source", "source_version", "source_hash", "source_payload", "clocks"}, "WF_ACT_CALENDAR_OBSERVATION_REQUIRED")
    require(calendar["kind"] == "SYNTHETIC_ACTUAL_OPEN_OBSERVATION" and calendar["venue"] == "SSE" and calendar["session_date"] == session and calendar["is_open"] is True, "WF_ACT_OPEN_OBSERVATION_REQUIRED")
    opening, closing, actual_open = [_instant(calendar[key]) for key in ("market_open", "market_close", "actual_open_observed_at")]
    require(opening[0] == closing[0] == actual_open[0] == session and opening[1] == "09:30:00" and closing[1] == "15:00:00" and opening[2] % 1_000_000_000 == closing[2] % 1_000_000_000 == 0, "WF_ACT_SESSION_BOUNDARIES_INVALID")
    require(opening[2] <= actual_open[2] <= closing[2] < captured[2], "WF_ACT_EOD_NOT_OBSERVED")
    cal_retrieved = _clocks(calendar["clocks"], session, anchor[2], cutoff[2], opening[2], opening[2])
    require(actual_open[2] <= cal_retrieved <= captured[2], "WF_ACT_OPEN_CLOCK_OBSERVATION_DRIFT")
    _source(calendar, bound["source_version"], "CALENDAR_ACTUAL_OPEN")

    require(type(case["bars"]) is list and len(case["bars"]) == len(SYMBOLS), "WF_ACT_EOD_BAR_COVERAGE_UNKNOWN")
    require(type(case["statuses"]) is list and len(case["statuses"]) == len(SYMBOLS), "WF_ACT_STATUS_COVERAGE_UNKNOWN")
    require([row.get("symbol") if type(row) is dict else None for row in case["bars"]] == list(SYMBOLS), "WF_ACT_BAR_UNIVERSE_OR_DUPLICATE")
    require([row.get("symbol") if type(row) is dict else None for row in case["statuses"]] == list(SYMBOLS), "WF_ACT_STATUS_UNIVERSE_OR_DUPLICATE")
    unknowns = []
    retrieved = [cal_retrieved]
    for row in case["bars"]:
        _exact(row, {"symbol", "session_date", "price_basis", "units", "open", "high", "low", "close", "volume", "source", "source_version", "source_hash", "source_payload", "clocks"}, "WF_ACT_BAR_SHAPE_INVALID")
        require(row["session_date"] == session and row["price_basis"] == "RAW_UNADJUSTED", "WF_ACT_BAR_SESSION_OR_ADJUSTMENT_DRIFT")
        require(row["units"] == {"price": "CNY_PER_SHARE", "volume": "SHARES"}, "WF_ACT_RAW_PRICE_UNITS_REQUIRED")
        prices = {key: decimal_string(row[key]) for key in ("open", "high", "low", "close")}
        require(all(value > 0 for value in prices.values()) and prices["low"] <= min(prices["open"], prices["close"]) <= max(prices["open"], prices["close"]) <= prices["high"], "WF_ACT_RAW_OHLC_INVALID")
        require(type(row["volume"]) is int and row["volume"] >= 0, "WF_ACT_INTEGER_VOLUME_REQUIRED")
        retrieved_at = _clocks(row["clocks"], session, anchor[2], cutoff[2], closing[2], closing[2])
        require(retrieved_at > closing[2], "WF_ACT_RETRIEVAL_NOT_AFTER_EOD")
        _source(row, bound["source_version"], "RAW_BAR_1D")
        retrieved.append(retrieved_at)
    for row in case["statuses"]:
        _exact(row, {"symbol", "session_date", "listed", "delisted", "st", "suspended", "limit_up", "limit_down", "source", "source_version", "source_hash", "source_payload", "clocks"}, "WF_ACT_STATUS_SHAPE_INVALID")
        require(row["session_date"] == session, "WF_ACT_STATUS_SESSION_DRIFT")
        for key in ("listed", "delisted", "st", "suspended"):
            require(type(row[key]) is bool or row[key] == "UNKNOWN", "WF_ACT_STATUS_ENUM_INVALID")
            if row[key] == "UNKNOWN":
                unknowns.append(row["symbol"] + ":" + key)
        require(not (row["listed"] is True and row["delisted"] is True), "WF_ACT_CONFLICTING_STATUS")
        for key in ("limit_up", "limit_down"):
            if row[key] == "UNKNOWN":
                unknowns.append(row["symbol"] + ":" + key)
            else:
                require(decimal_string(row[key]) > 0, "WF_ACT_LIMIT_VALUE_INVALID")
        if row["limit_up"] != "UNKNOWN" and row["limit_down"] != "UNKNOWN":
            require(decimal_string(row["limit_down"]) <= decimal_string(row["limit_up"]), "WF_ACT_CONFLICTING_LIMITS")
        retrieved_at = _clocks(row["clocks"], session, anchor[2], cutoff[2], closing[2], closing[2])
        require(retrieved_at > closing[2], "WF_ACT_RETRIEVAL_NOT_AFTER_EOD")
        _source(row, bound["source_version"], "STATUS_1D")
        retrieved.append(retrieved_at)
    require(max(retrieved) <= captured[2], "WF_ACT_CAPTURE_BEFORE_SOURCE_RETRIEVAL")
    observation_hash = _observations_hash(case)
    require(observation_hash != a["raw_observation_hash"], "WF_ACT_OBSERVATION_NOT_FRESH")
    capture_hash = fixture_capture_hash(case)
    require(capture_hash != a["content_hash"], "WF_ACT_A_TO_B_HASH_NOT_DISTINCT")

    review = case["review"]
    _exact(review, {"kind", "reviewer_id", "reviewed_capture_hash", "reviewed_strategy_hash", "review_policy_hash", "reviewed_at", "conclusion"}, "WF_ACT_REVIEW_SHAPE_INVALID")
    require(review["kind"] == "SYNTHETIC_INDEPENDENT_REVIEW" and review["conclusion"] == "FIXTURE_PREPARATION_ONLY", "WF_ACT_FIXTURE_REVIEW_REQUIRED")
    _identifier(review["reviewer_id"])
    review_time = _instant(review["reviewed_at"])
    require(review_time[0] == session and captured[2] <= review_time[2] <= cutoff[2], "WF_ACT_REVIEW_BEFORE_CAPTURE_OR_FUTURE")
    require(review["reviewed_capture_hash"] == capture_hash and review["reviewed_strategy_hash"] == bound["strategy_hash"] and review["review_policy_hash"] == bound["review_policy_hash"], "WF_ACT_REVIEW_VERSION_BINDING_DRIFT")
    auth = case["authorization"]
    _exact(auth, {"kind", "authorization_id", "issued_at", "expires_at"}, "WF_ACT_AUTHORIZATION_SHAPE_INVALID")
    require(auth["kind"] == "SYNTHETIC_HUMAN_USER", "WF_ACT_LLM_NOT_SYNTHETIC_HUMAN")
    _identifier(auth["authorization_id"])
    issued, expiry = _instant(auth["issued_at"]), _instant(auth["expires_at"])
    require(issued[2] <= opening[2] and cutoff[2] < expiry[2], "WF_ACT_AUTHORIZATION_FUTURE_OR_EXPIRED")
    return {"version": FIXTURE_CAPTURE_VERSION, "kind": "FIXTURE_ACTIVATION_DISPLAY_ONLY", "provenance": PROVENANCE, "namespace": NAMESPACE, "expected_session": session, "fixture_capture_hash": capture_hash, "fixture_observation_hash": observation_hash, "fixture_review_hash": digest(review), "snapshot_a_hash": a["content_hash"], "fresh_session_fixture_valid": True, "eod_fixture_complete": True, "tradeability": "UNKNOWN", "status_unknowns": unknowns, "safe_to_trade": False, "decision": "NO_DECISION", "actual_snapshot_b_created": False, "actual_forward_days": 0, "live_authority": False, "native_promotion": False}


@dataclass(frozen=True, eq=False)
class FixtureApproval:
    """A process-local fixture handle; never a human or trading credential."""
    approval_id: str
    _body: dict


_APPROVALS = {}
_USED = set()


def issue_fixture_approval(kind, case):
    require(kind == "SYNTHETIC_HUMAN_USER", "WF_ACT_LLM_NOT_SYNTHETIC_HUMAN")
    validated = validate_fixture_capture(case)
    body = {"kind": kind, "approval_id": "fixture-approval:" + uuid.uuid4().hex, "case": copy.deepcopy(case), "validated": validated, "actual_authority": False}
    approval = FixtureApproval(body["approval_id"], body)
    _APPROVALS[id(approval)] = (approval, digest(body))
    return approval


def _approval(handle):
    require(type(handle) is FixtureApproval, "WF_ACT_REGISTERED_FIXTURE_APPROVAL_REQUIRED")
    saved = _APPROVALS.get(id(handle))
    require(saved is not None and saved[0] is handle and saved[1] == digest(handle._body) and handle.approval_id == handle._body["approval_id"], "WF_ACT_APPROVAL_IDENTITY_OR_MUTATION")
    require(handle.approval_id not in _USED, "WF_ACT_APPROVAL_ALREADY_USED")
    require(validate_fixture_capture(handle._body["case"]) == handle._body["validated"], "WF_ACT_APPROVAL_CAPTURE_DRIFT")
    return handle._body


_TABLES = {
    "fixture_metadata": "CREATE TABLE fixture_metadata (id INTEGER PRIMARY KEY CHECK(id=1), body_json TEXT NOT NULL, body_hash TEXT NOT NULL)",
    "fixture_days": "CREATE TABLE fixture_days (sequence INTEGER PRIMARY KEY CHECK(sequence>0), session_date TEXT NOT NULL UNIQUE, capture_id TEXT NOT NULL UNIQUE, observation_hash TEXT NOT NULL UNIQUE, approval_id TEXT NOT NULL UNIQUE, previous_hash TEXT NOT NULL, day_hash TEXT NOT NULL UNIQUE, body_json TEXT NOT NULL)",
    "fixture_failed_attempts": "CREATE TABLE fixture_failed_attempts (sequence INTEGER PRIMARY KEY CHECK(sequence>0), attempt_id TEXT NOT NULL UNIQUE, previous_hash TEXT NOT NULL, attempt_hash TEXT NOT NULL UNIQUE, body_json TEXT NOT NULL)",
}
_TRIGGERS = {
    "fixture_metadata_no_insert": "CREATE TRIGGER fixture_metadata_no_insert BEFORE INSERT ON fixture_metadata BEGIN SELECT RAISE(ABORT,'WF_ACT_IMMUTABLE'); END",
    "fixture_metadata_no_update": "CREATE TRIGGER fixture_metadata_no_update BEFORE UPDATE ON fixture_metadata BEGIN SELECT RAISE(ABORT,'WF_ACT_IMMUTABLE'); END",
    "fixture_metadata_no_delete": "CREATE TRIGGER fixture_metadata_no_delete BEFORE DELETE ON fixture_metadata BEGIN SELECT RAISE(ABORT,'WF_ACT_IMMUTABLE'); END",
}
for _table in ("fixture_days", "fixture_failed_attempts"):
    for _op in ("update", "delete"):
        _TRIGGERS[_table + "_no_" + _op] = "CREATE TRIGGER " + _table + "_no_" + _op + " BEFORE " + _op.upper() + " ON " + _table + " BEGIN SELECT RAISE(ABORT,'WF_ACT_APPEND_ONLY'); END"
    _TRIGGERS[_table + "_guard_insert"] = "CREATE TRIGGER " + _table + "_guard_insert BEFORE INSERT ON " + _table + " WHEN wave_f_fixture_capability()!=1 BEGIN SELECT RAISE(ABORT,'WF_ACT_FIXTURE_CAPABILITY_REQUIRED'); END"


def _path(path, existing):
    require(type(path) is str or isinstance(path, Path), "WF_ACT_FIXTURE_PATH_INVALID")
    p = Path(path)
    require(p.is_absolute() and p.resolve() == p and not p.is_symlink() and p.name.endswith(".wave-f.fixture.sqlite3"), "WF_ACT_FIXTURE_PATH_INVALID")
    require(p.parent.is_dir() and stat.S_IMODE(p.parent.stat().st_mode) == 0o700, "WF_ACT_PRIVATE_PARENT_REQUIRED")
    if existing:
        require(p.is_file() and stat.S_ISREG(p.stat().st_mode) and stat.S_IMODE(p.stat().st_mode) == 0o600, "WF_ACT_PRIVATE_STORE_REQUIRED")
    else:
        require(not p.exists(), "WF_ACT_STORE_ALREADY_EXISTS")
    return p


def _connect(p, write=False):
    conn = sqlite3.connect(p.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, isolation_level=None, timeout=10)
    conn.execute("PRAGMA foreign_keys=ON")
    if write:
        conn.execute("PRAGMA synchronous=FULL")
        conn.create_function("wave_f_fixture_capability", 0, lambda: 1)
    return conn


def _decode(raw):
    try:
        body = json.loads(raw)
    except (ValueError, TypeError):
        raise ValueError("WF_ACT_STORE_JSON_INVALID") from None
    require(canonical(body).decode() == raw, "WF_ACT_STORE_NON_CANONICAL")
    return body


def _schema(conn):
    actual = {row[0]: (row[1], row[2]) for row in conn.execute("SELECT name,type,sql FROM sqlite_schema WHERE sql IS NOT NULL")}
    expected = {name: ("table", sql) for name, sql in _TABLES.items()} | {name: ("trigger", sql) for name, sql in _TRIGGERS.items()}
    require(actual == expected and conn.execute("PRAGMA user_version").fetchone()[0] == 1, "WF_ACT_STORE_SCHEMA_DRIFT")
    require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "WF_ACT_STORE_INTEGRITY_INVALID")


def _genesis(kind, metadata_hash):
    return digest({"kind": kind, "metadata_hash": metadata_hash})


def _inspect(conn, p):
    _schema(conn)
    rows = conn.execute("SELECT id,body_json,body_hash FROM fixture_metadata").fetchall()
    require(len(rows) == 1 and rows[0][0] == 1, "WF_ACT_STORE_METADATA_INVALID")
    meta = _decode(rows[0][1])
    _exact(meta, {"kind", "version", "provenance", "namespace", "canonical_path", "store_id", "observed_universe", "actual_forward_days", "native_promotion"}, "WF_ACT_STORE_METADATA_INVALID")
    require(meta["kind"] == "WAVE_F_NO_DECISION_FIXTURE_STORE" and meta["version"] == VERSION and meta["provenance"] == PROVENANCE and meta["namespace"] == NAMESPACE and meta["canonical_path"] == str(p) and meta["observed_universe"] == list(SYMBOLS) and type(meta["actual_forward_days"]) is int and meta["actual_forward_days"] == 0 and meta["native_promotion"] is False, "WF_ACT_STORE_BINDING_DRIFT")
    require(type(meta["store_id"]) is str and re.fullmatch(r"fixture-store:[0-9a-f]{32}", meta["store_id"]), "WF_ACT_STORE_ID_INVALID")
    require(digest(meta) == rows[0][2], "WF_ACT_STORE_METADATA_HASH_INVALID")
    head = _genesis("WAVE_F_FIXTURE_DAYS_GENESIS", rows[0][2])
    records, seen_ids, seen_observations, seen_approvals, seen_auth_ids = [], set(), set(), set(), set()
    frozen, anchor_hash = None, None
    for row in conn.execute("SELECT sequence,session_date,capture_id,observation_hash,approval_id,previous_hash,day_hash,body_json FROM fixture_days ORDER BY sequence"):
        item = _decode(row[7])
        _exact(item, {"sequence", "previous_hash", "day_hash", "case", "validated", "fixture_approval_id", "decision", "tradeability", "safe_to_trade", "actual_policies", "actual_forward_days", "native_promotion"}, "WF_ACT_DAY_SHAPE_INVALID")
        case = item["case"]
        validated = validate_fixture_capture(case)
        require(item["validated"] == validated and item["decision"] == "NO_DECISION" and item["tradeability"] == "UNKNOWN" and item["safe_to_trade"] is False and item["actual_policies"] == {"account": UNSET, "cost": UNSET, "risk": UNSET} and type(item["actual_forward_days"]) is int and item["actual_forward_days"] == 0 and item["native_promotion"] is False, "WF_ACT_DAY_NATIVE_PROMOTION_OR_POLICY_DRIFT")
        require(type(item["fixture_approval_id"]) is str and re.fullmatch(r"fixture-approval:[0-9a-f]{32}", item["fixture_approval_id"]), "WF_ACT_STORED_FIXTURE_APPROVAL_INVALID")
        require(type(item["sequence"]) is int and item["sequence"] == len(records) + 1 and item["previous_hash"] == head and item["day_hash"] == digest({key: value for key, value in item.items() if key != "day_hash"}), "WF_ACT_DAY_CHAIN_INVALID")
        require(tuple(row[:7]) == (item["sequence"], case["expected_session"], case["capture_id"], validated["fixture_observation_hash"], item["fixture_approval_id"], head, item["day_hash"]), "WF_ACT_DAY_COLUMN_DRIFT")
        require(case["capture_id"] not in seen_ids and validated["fixture_observation_hash"] not in seen_observations and item["fixture_approval_id"] not in seen_approvals and case["authorization"]["authorization_id"] not in seen_auth_ids, "WF_ACT_STORED_DUPLICATE")
        require(not records or _day(case["expected_session"]) > _day(records[-1]["case"]["expected_session"]), "WF_ACT_STORED_SESSION_ORDER")
        bindings = {key: case["bindings"][key] for key in _FROZEN}
        if frozen is None:
            frozen, anchor_hash = bindings, validated["snapshot_a_hash"]
        require(bindings == frozen and validated["snapshot_a_hash"] == anchor_hash, "WF_ACT_FROZEN_POLICY_OR_ANCHOR_DRIFT")
        seen_ids.add(case["capture_id"])
        seen_observations.add(validated["fixture_observation_hash"])
        seen_approvals.add(item["fixture_approval_id"])
        seen_auth_ids.add(case["authorization"]["authorization_id"])
        records.append(item)
        head = item["day_hash"]
    failure_head = _genesis("WAVE_F_FIXTURE_FAILURES_GENESIS", rows[0][2])
    failures = []
    for row in conn.execute("SELECT sequence,attempt_id,previous_hash,attempt_hash,body_json FROM fixture_failed_attempts ORDER BY sequence"):
        item = _decode(row[4])
        _exact(item, {"sequence", "attempt_id", "previous_hash", "attempt_hash", "kind", "reason_code", "untrusted_payload_retained", "untrusted_payload_hash_retained", "actual_forward_days"}, "WF_ACT_FAILURE_SHAPE_INVALID")
        require(item["kind"] == "SYNTHETIC_FAILED_CAPTURE_METADATA" and type(item["attempt_id"]) is str and re.fullmatch(r"fixture-failure:[0-9a-f]{32}", item["attempt_id"]), "WF_ACT_FAILURE_KIND_INVALID")
        require(type(item["reason_code"]) is str and re.fullmatch(r"WF_ACT_[A-Z0-9_]{1,100}", item["reason_code"]) and item["untrusted_payload_retained"] is False and item["untrusted_payload_hash_retained"] is False and type(item["actual_forward_days"]) is int and item["actual_forward_days"] == 0, "WF_ACT_FAILURE_METADATA_INVALID")
        require(type(item["sequence"]) is int and item["sequence"] == len(failures) + 1 and item["previous_hash"] == failure_head and item["attempt_hash"] == digest({key: value for key, value in item.items() if key != "attempt_hash"}) and tuple(row[:4]) == (item["sequence"], item["attempt_id"], failure_head, item["attempt_hash"]), "WF_ACT_FAILURE_CHAIN_INVALID")
        failures.append(item)
        failure_head = item["attempt_hash"]
    return {"kind": "WAVE_F_FIXTURE_LEDGER_DISPLAY_ONLY", "version": VERSION, "provenance": PROVENANCE, "namespace": NAMESPACE, "store_id": meta["store_id"], "head_hash": head, "failure_head_hash": failure_head, "fixture_day_count": len(records), "failed_capture_count": len(failures), "records": records, "failed_captures": failures, "actual_forward_days": 0, "live_authority": False, "native_promotion": False}


def create_fixture_ledger(path):
    p = _path(path, False)
    descriptor = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    conn = None
    try:
        conn = _connect(p, True)
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("BEGIN IMMEDIATE")
        for sql in _TABLES.values():
            conn.execute(sql)
        body = {"kind": "WAVE_F_NO_DECISION_FIXTURE_STORE", "version": VERSION, "provenance": PROVENANCE, "namespace": NAMESPACE, "canonical_path": str(p), "store_id": "fixture-store:" + uuid.uuid4().hex, "observed_universe": list(SYMBOLS), "actual_forward_days": 0, "native_promotion": False}
        conn.execute("INSERT INTO fixture_metadata VALUES(1,?,?)", (canonical(body).decode(), digest(body)))
        for sql in _TRIGGERS.values():
            conn.execute(sql)
        conn.execute("PRAGMA user_version=1")
        result = _inspect(conn, p)
        conn.execute("COMMIT")
        return result
    except Exception:
        if conn is not None and conn.in_transaction:
            conn.execute("ROLLBACK")
        if conn is not None:
            conn.close()
            conn = None
        p.unlink(missing_ok=True)
        raise
    finally:
        if conn is not None:
            conn.close()


def inspect_fixture_ledger(path):
    p = _path(path, True)
    conn = _connect(p)
    try:
        conn.execute("BEGIN")
        return _inspect(conn, p)
    finally:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.close()


def append_fixture_day(path, approval, expected_head):
    """Atomic fixture append; validation failures consume no approval or day."""
    hash_value(expected_head)
    with _LOCK:
        p = _path(path, True)
        approved = _approval(approval)
        case, validated = approved["case"], approved["validated"]
        conn = _connect(p, True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            before = _inspect(conn, p)
            require(before["head_hash"] == expected_head, "WF_ACT_STALE_EXPECTED_HEAD")
            for previous in before["records"]:
                require(previous["case"]["expected_session"] != case["expected_session"], "WF_ACT_DUPLICATE_PAPER_DAY")
                require(previous["case"]["capture_id"] != case["capture_id"], "WF_ACT_DUPLICATE_CAPTURE_ID")
                require(previous["validated"]["fixture_observation_hash"] != validated["fixture_observation_hash"], "WF_ACT_DUPLICATE_OBSERVATION")
                require(previous["case"]["authorization"]["authorization_id"] != case["authorization"]["authorization_id"], "WF_ACT_DUPLICATE_AUTHORIZATION_ID")
            if before["records"]:
                previous = before["records"][-1]
                require(_day(case["expected_session"]) > _day(previous["case"]["expected_session"]), "WF_ACT_SESSION_ORDER_INVALID")
                require({key: case["bindings"][key] for key in _FROZEN} == {key: previous["case"]["bindings"][key] for key in _FROZEN} and validated["snapshot_a_hash"] == previous["validated"]["snapshot_a_hash"], "WF_ACT_FROZEN_POLICY_OR_ANCHOR_DRIFT")
            item = {"sequence": before["fixture_day_count"] + 1, "previous_hash": expected_head, "case": copy.deepcopy(case), "validated": copy.deepcopy(validated), "fixture_approval_id": approval.approval_id, "decision": "NO_DECISION", "tradeability": "UNKNOWN", "safe_to_trade": False, "actual_policies": {"account": UNSET, "cost": UNSET, "risk": UNSET}, "actual_forward_days": 0, "native_promotion": False}
            item["day_hash"] = digest(item)
            conn.execute("INSERT INTO fixture_days VALUES(?,?,?,?,?,?,?,?)", (item["sequence"], case["expected_session"], case["capture_id"], validated["fixture_observation_hash"], approval.approval_id, expected_head, item["day_hash"], canonical(item).decode()))
            result = _inspect(conn, p)
            conn.execute("COMMIT")
            _USED.add(approval.approval_id)
            return result
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()


def _preserve_failure(path, reason):
    # Never retain caller payload, identity, exception details or payload hash.
    if not (type(reason) is str and re.fullmatch(r"WF_ACT_[A-Z0-9_]{1,100}", reason)):
        reason = "WF_ACT_INVALID_FIXTURE_INPUT"
    p = _path(path, True)
    conn = _connect(p, True)
    try:
        conn.execute("BEGIN IMMEDIATE")
        before = _inspect(conn, p)
        item = {"sequence": before["failed_capture_count"] + 1, "attempt_id": "fixture-failure:" + uuid.uuid4().hex, "previous_hash": before["failure_head_hash"], "kind": "SYNTHETIC_FAILED_CAPTURE_METADATA", "reason_code": reason, "untrusted_payload_retained": False, "untrusted_payload_hash_retained": False, "actual_forward_days": 0}
        item["attempt_hash"] = digest(item)
        conn.execute("INSERT INTO fixture_failed_attempts VALUES(?,?,?,?,?)", (item["sequence"], item["attempt_id"], item["previous_hash"], item["attempt_hash"], canonical(item).decode()))
        _inspect(conn, p)
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def attempt_fixture_day(path, kind, case, expected_head):
    """Fixture-only convenience with immutable sanitized failure retention.

    It never returns a successful actual capture. When validation/append fails,
    the failure chain retains a safe reason, the day chain stays unchanged and
    the original exception is re-raised. Corrupt stores are left untouched.
    """
    _path(path, True)
    try:
        approval = issue_fixture_approval(kind, case)
        return append_fixture_day(path, approval, expected_head)
    except ValueError as error:
        with _LOCK:
            _preserve_failure(path, str(error))
        raise


def recover_fixture_ledger(path, expected_head=None):
    """Read-only recovery inspection; mismatch/corruption blocks, never repairs."""
    result = inspect_fixture_ledger(path)
    if expected_head is not None:
        hash_value(expected_head)
        require(result["head_hash"] == expected_head, "WF_ACT_RECOVERY_HEAD_MISMATCH")
    return {"kind": "WAVE_F_FIXTURE_RECOVERY_DISPLAY_ONLY", "recovery_action": "VERIFIED_READ_ONLY_NO_REPAIR", "result": result, "new_approval_required_for_append": True, "actual_forward_days": 0, "live_authority": False}


def snapshot_readiness():
    return metadata({"state": "PREPARATION_IMPLEMENTED_ACTUAL_ACTIVATION_BLOCKED", "planned_first_post_holiday_session": "2026-10-08", "calendar_plan_is_actual_session": False, "actual_fresh_session_observed": False, "actual_eod_observed": False, "snapshot_a_is_admitted": False, "actual_snapshot_b_created": False, "exact_symbols": list(SYMBOLS), "fixture_capture_version": FIXTURE_CAPTURE_VERSION, "source_original_binding": "CANONICAL_EMBEDDED_SYNTHETIC_ORIGINAL_SESSION_SYMBOL_VALUES_UNITS_CLOCKS_SHA256", "actual_source_original_proof_captured_this_module": False, "freshness_and_eod_algorithms": "SYNTHETIC_ADVERSARIAL_TESTED_ONLY", "lineage_binding": "A_ANCHOR_CAPTURE_SOURCE_RULES_STRATEGY_POLICY_REVIEW_HASH_VERSION", "missing_status_or_bar": "UNKNOWN_BLOCKS_COMPLETENESS", "required_future_evidence": ["NEW_SCOPED_HUMAN_OWNER_AUTHORIZATION", "ACTUAL_OPEN_SESSION_OBSERVATION_NOT_CALENDAR_PLAN", "ACTUAL_EOD_SOURCE_AVAILABILITY_FOR_EXACT_THREE_SYMBOLS", "FOUR_PRECISE_CLOCKS_NO_DATE_ONLY_IMPUTATION", "FRESH_RETRIEVAL_AFTER_A_AND_ACTUAL_EOD", "CANONICAL_SOURCE_POLICY_AND_ALLOWED_LOCAL_EXCEPTION_REVIEW", "VERSION_BOUND_STRATEGY_INTERPRETATION_AND_CAPTURE_REVIEW", "INDEPENDENT_ACTUAL_CAPTURE_REVIEW"], "formal_source_admission": "BLOCKED_PROVIDER_LICENSE_TRANSPORT_UNVERIFIED", "scheduled": False, "only_human_authorization_missing": False, "reason_codes": ["WF_ACT_SEPARATE_HUMAN_AUTH_REQUIRED", "WF_ACT_ACTUAL_OPEN_EOD_UNOBSERVED", "WF_ACT_SOURCE_POLICY_REVIEW_REQUIRED", "WF_ACT_STRATEGY_INTERPRETATION_REVIEW_REQUIRED"]})


def forward_readiness():
    return metadata({"state": "NO_DECISION_FIXTURE_ENGINEERING_READY_REAL_START_BLOCKED", "supported_decision": "NO_DECISION", "synthetic_ledger": "ISOLATED_DURABLE_APPEND_ONLY_SQLITE", "failed_capture_preservation": "SANITIZED_REASON_CHAIN_NO_UNTRUSTED_PAYLOAD", "restart_recovery": "READ_ONLY_VERIFY_NO_REPAIR_NEW_FIXTURE_APPROVAL", "actual_record_appended": False, "real_account_parameters": {"account": UNSET, "cost": UNSET, "risk": UNSET}, "real_money_parameters_block_no_decision_engineering": False, "native_order_fields_supported": False, "synthetic_days_count_as_actual": False, "real_approval_issuer": "UNAVAILABLE_THIS_WAVE", "future_requirements": ["ACTUAL_REVIEWED_FRESH_SNAPSHOT_B", "SEPARATE_HUMAN_OWNER_AUTHORIZATION_FOR_FORWARD_SCOPE", "FROZEN_RESEARCH_PAPER_INTERPRETATION_AND_NO_DECISION_POLICY", "LOCAL_SOURCE_EXCEPTION_AND_CAPTURE_ACCEPTANCE_REVIEW", "INDEPENDENT_REVIEW_ENTRY_NO_LIVE_CREDENTIAL"], "formal_source_admission": "BLOCKED", "historical_backtest_admission": "BLOCKED", "execution_or_native_promotion": False, "privileged_rewrite_or_hostile_interpreter_proof": False, "scheduled": False, "reason_codes": ["WF_ACT_REAL_FORWARD_NOT_AUTHORIZED", "WF_ACT_ACTUAL_SNAPSHOT_B_MISSING", "WF_ACT_FUTURE_POLICY_REVIEW_REQUIRED"]})


def run_snapshot_b(*args, **kwargs):
    raise ValueError("WF_ACT_ACTUAL_SNAPSHOT_B_NOT_AUTHORIZED")


def run_real_forward(*args, **kwargs):
    raise ValueError("WF_ACT_REAL_FORWARD_NOT_AUTHORIZED")


def append_actual_session(*args, **kwargs):
    raise ValueError("WF_ACT_ACTUAL_PAPER_APPEND_NOT_AUTHORIZED")
