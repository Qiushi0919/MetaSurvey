"""Persistent, data-only Forward Paper fixture boundary; real entry always blocks.

API: readiness(), create_fixture_store(path), issue_fixture_authority(kind,
evidence), append_fixture_record(path, authority, record, expected_head),
inspect_fixture_store(path), run_real_forward(*args, **kwargs).

All stores/authorities/records are SYNTHETIC_NOT_OWNER_POLICY/FIXTURE_ONLY.
No hypothetical fills are supported: the only decision is NO_DECISION and
extra Candidate/Signal/Order/Fill fields reject. Persistence is implemented,
not an actual Paper session or native ledger. Actual forward days are always 0.

Evidence has exactly: kind, scope, namespace, account_namespace,
strategy_namespace, mode, schema_version, observed_universe, source_day,
calendar_session, event_time, published_at, available_at, retrieved_at,
decision_cutoff, authorization, snapshot_a, snapshot_b, bindings.
kind is SYNTHETIC_SOURCE_OBSERVATION; authority kind and authorization subject
are SYNTHETIC_HUMAN_USER. authorization has authorization_id (fixture:<id>),
subject, issued_at, expires_at. calendar_session has kind
SYNTHETIC_OPEN_SESSION, venue SSE, source_ref fixture://calendar/<source_day>,
session_day, market_close. Dates are ISO YYYY-MM-DD; instants require explicit
9-digit nanoseconds and +08:00, never date-only/naive/imputed midnight.
The EOD event/close is 15:00:00; publication <= availability <= retrieval <=
cutoff are the same session and after close. This specific bar constraint is
not a universal event/publication ordering for future effective actions.

snapshot_a/b have kind SYNTHETIC_SNAPSHOT, namespace, version, source_day,
content_hash. A is the synthetic 2026-09-30 anchor, B is a fresh synthetic
session after it. Bindings are source_hash, rules_hash, code_hash, schema_hash,
strategy_spec_hash, source_policy_hash; hashes use sha256:<64 hex>.

Record has exactly: kind FORWARD_PAPER_FIXTURE_RECORD, scope, namespace,
account_namespace, strategy_namespace, mode, schema_version, observed_universe,
source_day, decision_cutoff, snapshot_a, snapshot_b, bindings, source_clocks
(event_time, published_at, available_at, retrieved_at), decision NO_DECISION,
tradeability UNKNOWN, actual_policies (account/cost/risk/strategy all
UNSET_REQUIRED), unknowns, reason_codes, idempotency_key (fixture:<id>).
Namespace/account/strategy/mode are the constants below. Required unknowns and
reasons cannot be erased. Parent expected_head is separate from the record.

SQLite metadata and records have update/delete guards; inserts require this
adapter's connection capability. Each transaction checks the full schema,
canonical metadata, full chain, day/key uniqueness and expected head. Reopen
returns detached DISPLAY_ONLY data, never an authority. Copies to another path
reject because metadata binds the canonical path. Hash-chain checks detect
inconsistent edits, not a privileged writer replacing and resealing an entire
store or a hostile interpreter. Those actions still cannot create real
authority: no real issuer or native promotion exists here. Authorities remain
opaque process-local capabilities; the *fixture ledger* persists across reopen.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from post_wave_e.common import SYMBOLS, VERSION, UNSET, canonical, digest, hash_value, require

NAMESPACE = "LOCAL_FORWARD_PAPER_FIXTURE:CORE_40"
ACCOUNT = "SYNTHETIC_ACCOUNT"
STRATEGY = "CORE_40"
MODE = "SYNTHETIC_NOT_OWNER_POLICY"
_SCOPE = "FIXTURE_ONLY"
_BASELINE = date(2026, 9, 30)
_TS = re.compile(r"^(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)\.(\d{9})\+08:00$")
_ID = re.compile(r"fixture:[A-Za-z0-9_-]{1,80}$")
_BINDINGS = {"source_hash", "rules_hash", "code_hash", "schema_hash", "strategy_spec_hash", "source_policy_hash"}
_COMMON = {"scope", "namespace", "account_namespace", "strategy_namespace", "mode", "schema_version", "observed_universe"}
_EVIDENCE = _COMMON | {"kind", "source_day", "calendar_session", "event_time", "published_at", "available_at", "retrieved_at", "decision_cutoff", "authorization", "snapshot_a", "snapshot_b", "bindings"}
_RECORD = _COMMON | {"kind", "source_day", "decision_cutoff", "snapshot_a", "snapshot_b", "bindings", "source_clocks", "decision", "tradeability", "actual_policies", "unknowns", "reason_codes", "idempotency_key"}
_CLOCKS = {"event_time", "published_at", "available_at", "retrieved_at"}
_UNKNOWNS = {"account_policy", "cost_policy", "risk_policy", "strategy_policy", "provider_license_transport", "historical_pit", "tradeability"}
_REASONS = {"FIXTURE_ONLY", "NOT_ACTUAL_FORWARD_DAY", "NO_DECISION", "UNSET_REQUIRED", "TRADEABILITY_UNKNOWN", "NO_NATIVE_PROMOTION"}
_LOCK = threading.RLock()

_TABLES = {
    "fixture_metadata": "CREATE TABLE fixture_metadata (id INTEGER PRIMARY KEY CHECK(id=1), body_json TEXT NOT NULL, metadata_hash TEXT NOT NULL)",
    "fixture_records": "CREATE TABLE fixture_records (sequence INTEGER PRIMARY KEY CHECK(sequence>0), source_day TEXT NOT NULL UNIQUE, idempotency_key TEXT NOT NULL UNIQUE, authority_id TEXT NOT NULL UNIQUE, predecessor_hash TEXT NOT NULL, daily_hash TEXT NOT NULL UNIQUE, body_json TEXT NOT NULL)",
}
_TRIGGERS = {
    "fixture_metadata_no_insert": "CREATE TRIGGER fixture_metadata_no_insert BEFORE INSERT ON fixture_metadata BEGIN SELECT RAISE(ABORT,'FIXTURE_METADATA_IMMUTABLE'); END",
    "fixture_metadata_no_update": "CREATE TRIGGER fixture_metadata_no_update BEFORE UPDATE ON fixture_metadata BEGIN SELECT RAISE(ABORT,'FIXTURE_METADATA_IMMUTABLE'); END",
    "fixture_metadata_no_delete": "CREATE TRIGGER fixture_metadata_no_delete BEFORE DELETE ON fixture_metadata BEGIN SELECT RAISE(ABORT,'FIXTURE_METADATA_IMMUTABLE'); END",
    "fixture_records_no_update": "CREATE TRIGGER fixture_records_no_update BEFORE UPDATE ON fixture_records BEGIN SELECT RAISE(ABORT,'FIXTURE_APPEND_ONLY'); END",
    "fixture_records_no_delete": "CREATE TRIGGER fixture_records_no_delete BEFORE DELETE ON fixture_records BEGIN SELECT RAISE(ABORT,'FIXTURE_APPEND_ONLY'); END",
    "fixture_records_guard_insert": "CREATE TRIGGER fixture_records_guard_insert BEFORE INSERT ON fixture_records WHEN fixture_append_authorized()!=1 BEGIN SELECT RAISE(ABORT,'FIXTURE_APPEND_CAPABILITY_REQUIRED'); END",
}


def _exact(value, fields, reason):
    require(type(value) is dict and set(value) == fields, reason)
    canonical(value)


def _day(value):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d\d-\d\d", value), "FORWARD_DAY_INVALID")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError("FORWARD_DAY_INVALID") from None


def _instant(value):
    require(type(value) is str, "FORWARD_CLOCK_INVALID")
    match = _TS.fullmatch(value)
    require(match is not None, "FORWARD_CLOCK_PRECISION_OR_ZONE_INVALID")
    day_text, clock, nano = match.groups()
    try:
        parsed = datetime.strptime(day_text + "T" + clock, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        raise ValueError("FORWARD_CLOCK_INVALID") from None
    require(clock != "00:00:00", "FORWARD_MIDNIGHT_IMPUTATION_FORBIDDEN")
    ns = parsed.date().toordinal() * 86_400_000_000_000
    ns += (parsed.hour * 3600 + parsed.minute * 60 + parsed.second) * 1_000_000_000 + int(nano)
    return parsed.date(), clock, ns


def _common(value):
    require(value["scope"] == _SCOPE, "FORWARD_SCOPE_DRIFT")
    require(value["namespace"] == NAMESPACE, "FORWARD_NAMESPACE_DRIFT")
    require(value["account_namespace"] == ACCOUNT, "FORWARD_ACCOUNT_DRIFT")
    require(value["strategy_namespace"] == STRATEGY, "FORWARD_STRATEGY_DRIFT")
    require(value["mode"] == MODE, "FORWARD_MODE_PROMOTION_FORBIDDEN")
    require(value["schema_version"] == VERSION, "FORWARD_VERSION_DRIFT")
    require(value["observed_universe"] == list(SYMBOLS), "FORWARD_UNIVERSE_DRIFT")


def _snapshot(value, day):
    _exact(value, {"kind", "namespace", "version", "source_day", "content_hash"}, "FORWARD_SNAPSHOT_SHAPE_INVALID")
    require(value["kind"] == "SYNTHETIC_SNAPSHOT" and value["namespace"] == NAMESPACE and value["version"] == VERSION and value["source_day"] == day, "FORWARD_SNAPSHOT_BINDING_INVALID")
    hash_value(value["content_hash"])


def _evidence(value):
    _exact(value, _EVIDENCE, "FORWARD_EVIDENCE_SHAPE_INVALID")
    _common(value)
    require(value["kind"] == "SYNTHETIC_SOURCE_OBSERVATION", "FORWARD_SYNTHETIC_EVIDENCE_REQUIRED")
    day = _day(value["source_day"])
    require(day > _BASELINE, "FORWARD_SOURCE_NOT_FRESH")
    require(day.weekday() < 5 and not date(2026, 10, 1) <= day <= date(2026, 10, 7), "FORWARD_FIXTURE_SESSION_CLOSED")
    session = value["calendar_session"]
    _exact(session, {"kind", "venue", "source_ref", "session_day", "market_close"}, "FORWARD_SESSION_SHAPE_INVALID")
    require(session["kind"] == "SYNTHETIC_OPEN_SESSION" and session["venue"] == "SSE" and session["source_ref"] == "fixture://calendar/" + value["source_day"] and session["session_day"] == value["source_day"], "FORWARD_SESSION_BINDING_INVALID")
    close_day, close_clock, close_ns = _instant(session["market_close"])
    require(close_day == day and close_clock == "15:00:00" and close_ns % 1_000_000_000 == 0, "FORWARD_SESSION_CLOSE_INVALID")
    event = _instant(value["event_time"])
    require(event[0] == day and event[2] == close_ns, "FORWARD_BAR_EVENT_INVALID")
    clocks = [_instant(value[key]) for key in ("published_at", "available_at", "retrieved_at", "decision_cutoff")]
    require(all(item[0] == day for item in clocks), "FORWARD_CLOCK_DAY_DRIFT")
    require(close_ns <= clocks[0][2] <= clocks[1][2] <= clocks[2][2] <= clocks[3][2], "FORWARD_CLOCK_ORDER_INVALID")
    issuer = value["authorization"]
    _exact(issuer, {"subject", "authorization_id", "issued_at", "expires_at"}, "FORWARD_AUTHORITY_SHAPE_INVALID")
    require(issuer["subject"] == "SYNTHETIC_HUMAN_USER", "FORWARD_SYNTHETIC_HUMAN_REQUIRED")
    require(type(issuer["authorization_id"]) is str and _ID.fullmatch(issuer["authorization_id"]), "FORWARD_AUTHORITY_ID_INVALID")
    require(_instant(issuer["issued_at"])[2] <= clocks[3][2] < _instant(issuer["expires_at"])[2], "FORWARD_AUTHORITY_EXPIRED_OR_FUTURE")
    _snapshot(value["snapshot_a"], _BASELINE.isoformat())
    _snapshot(value["snapshot_b"], value["source_day"])
    require(value["snapshot_a"]["content_hash"] != value["snapshot_b"]["content_hash"], "FORWARD_SNAPSHOT_NOT_FRESH")
    _exact(value["bindings"], _BINDINGS, "FORWARD_BINDINGS_SHAPE_INVALID")
    for bound in value["bindings"].values():
        hash_value(bound)


def _record(value, evidence):
    _exact(value, _RECORD, "FORWARD_RECORD_SHAPE_INVALID")
    _common(value)
    require(value["kind"] == "FORWARD_PAPER_FIXTURE_RECORD", "FORWARD_RECORD_KIND_INVALID")
    for key in ("source_day", "decision_cutoff", "snapshot_a", "snapshot_b", "bindings"):
        require(value[key] == evidence[key], "FORWARD_RECORD_AUTHORITY_BINDING_DRIFT")
    _exact(value["source_clocks"], _CLOCKS, "FORWARD_RECORD_CLOCK_SHAPE_INVALID")
    require(value["source_clocks"] == {key: evidence[key] for key in _CLOCKS}, "FORWARD_RECORD_CLOCK_BINDING_DRIFT")
    require(value["decision"] == "NO_DECISION", "FORWARD_NATIVE_DECISION_FORBIDDEN")
    require(value["tradeability"] == "UNKNOWN", "FORWARD_TRADEABILITY_PROMOTION_FORBIDDEN")
    _exact(value["actual_policies"], {"account", "cost", "risk", "strategy"}, "FORWARD_POLICY_SHAPE_INVALID")
    require(all(item == UNSET for item in value["actual_policies"].values()), "FORWARD_OWNER_POLICY_PROMOTION_FORBIDDEN")
    for key, expected in (("unknowns", _UNKNOWNS), ("reason_codes", _REASONS)):
        items = value[key]
        require(type(items) is list and all(type(item) is str for item in items) and len(items) == len(set(items)) and set(items) == expected, "FORWARD_UNKNOWN_OR_REASON_ERASURE")
    require(type(value["idempotency_key"]) is str and _ID.fullmatch(value["idempotency_key"]), "FORWARD_IDEMPOTENCY_KEY_INVALID")


@dataclass(frozen=True, eq=False)
class FixtureAuthority:
    """Opaque, process-local fixture capability. A copied body is not a handle."""
    authority_id: str
    _body: dict


_AUTHORITIES = {}
_USED = set()


def issue_fixture_authority(kind, evidence):
    require(kind == "SYNTHETIC_HUMAN_USER", "FORWARD_SYNTHETIC_HUMAN_REQUIRED")
    _evidence(evidence)
    identifier = "fixture-authority:" + uuid.uuid4().hex
    body = {"kind": kind, "authority_id": identifier, "evidence": copy.deepcopy(evidence), "scope": _SCOPE, "mode": MODE, "actual_forward_days": 0, "native_promotion": False}
    handle = FixtureAuthority(identifier, body)
    _AUTHORITIES[id(handle)] = (handle, digest(body))
    return handle


def _authority(handle):
    require(type(handle) is FixtureAuthority, "FORWARD_REGISTERED_FIXTURE_AUTHORITY_REQUIRED")
    saved = _AUTHORITIES.get(id(handle))
    require(saved is not None and saved[0] is handle and saved[1] == digest(handle._body) and handle.authority_id == handle._body["authority_id"], "FORWARD_AUTHORITY_IDENTITY_OR_SEAL_INVALID")
    require(handle.authority_id not in _USED, "FORWARD_AUTHORITY_ALREADY_USED")
    return handle._body


def _path(value, existing):
    require(type(value) in (str, Path) or isinstance(value, Path), "FORWARD_PATH_INVALID")
    p = Path(value)
    require(p.is_absolute() and p.resolve() == p and not p.is_symlink() and p.name.endswith(".fixture.sqlite3"), "FORWARD_PATH_INVALID")
    require(p.parent.is_dir() and stat.S_IMODE(p.parent.stat().st_mode) == 0o700, "FORWARD_PRIVATE_DIRECTORY_REQUIRED")
    if existing:
        require(p.is_file() and stat.S_ISREG(p.stat().st_mode) and stat.S_IMODE(p.stat().st_mode) == 0o600, "FORWARD_PRIVATE_STORE_REQUIRED")
    else:
        require(not p.exists(), "FORWARD_STORE_ALREADY_EXISTS")
    return p


def _connect(p, write=False):
    uri = p.as_uri() + ("?mode=rw" if write else "?mode=ro")
    conn = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    if write:
        conn.execute("PRAGMA synchronous=FULL")
        conn.create_function("fixture_append_authorized", 0, lambda: 1)
    return conn


def _schema(conn):
    actual = {row[0]: (row[1], row[2]) for row in conn.execute("SELECT name,type,sql FROM sqlite_schema WHERE sql IS NOT NULL")}
    wanted = dict({name: ("table", sql) for name, sql in _TABLES.items()}, **{name: ("trigger", sql) for name, sql in _TRIGGERS.items()})
    require(actual == wanted and conn.execute("PRAGMA user_version").fetchone()[0] == 1, "FORWARD_STORE_SCHEMA_DRIFT")
    require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "FORWARD_STORE_INTEGRITY_INVALID")


def _decode(body):
    import json
    try:
        value = json.loads(body)
    except (ValueError, TypeError):
        raise ValueError("FORWARD_STORE_JSON_INVALID") from None
    require(canonical(value).decode() == body, "FORWARD_STORE_CANONICAL_DRIFT")
    return value


def _chain(conn, p):
    _schema(conn)
    metadata_rows = conn.execute("SELECT id,body_json,metadata_hash FROM fixture_metadata").fetchall()
    require(len(metadata_rows) == 1 and metadata_rows[0][0] == 1, "FORWARD_STORE_METADATA_INVALID")
    metadata = _decode(metadata_rows[0][1])
    _exact(metadata, {"kind", "version", "scope", "namespace", "account_namespace", "strategy_namespace", "mode", "observed_universe", "store_id", "canonical_path", "actual_forward_days", "native_promotion"}, "FORWARD_STORE_METADATA_INVALID")
    require(metadata["kind"] == "FORWARD_PAPER_FIXTURE_STORE" and metadata["version"] == VERSION and metadata["scope"] == _SCOPE and metadata["namespace"] == NAMESPACE and metadata["account_namespace"] == ACCOUNT and metadata["strategy_namespace"] == STRATEGY and metadata["mode"] == MODE and metadata["observed_universe"] == list(SYMBOLS) and metadata["canonical_path"] == str(p) and type(metadata["actual_forward_days"]) is int and metadata["actual_forward_days"] == 0 and metadata["native_promotion"] is False, "FORWARD_STORE_BINDING_DRIFT")
    require(type(metadata["store_id"]) is str and re.fullmatch(r"fixture-store:[0-9a-f]{32}", metadata["store_id"]), "FORWARD_STORE_ID_INVALID")
    require(digest(metadata) == metadata_rows[0][2], "FORWARD_STORE_METADATA_HASH_INVALID")
    head = digest({"kind": "FIXTURE_GENESIS", "metadata_hash": metadata_rows[0][2]})
    records = []
    seen_days, seen_keys, seen_authorities = set(), set(), set()
    for row in conn.execute("SELECT sequence,source_day,idempotency_key,authority_id,predecessor_hash,daily_hash,body_json FROM fixture_records ORDER BY sequence"):
        item = _decode(row[6])
        _exact(item, {"sequence", "record", "fixture_authority", "fixture_authority_hash", "predecessor_hash", "daily_hash", "actual_forward_days", "native_promotion"}, "FORWARD_STORED_RECORD_SHAPE_INVALID")
        auth = item["fixture_authority"]
        _exact(auth, {"kind", "authority_id", "evidence", "scope", "mode", "actual_forward_days", "native_promotion"}, "FORWARD_STORED_AUTHORITY_SHAPE_INVALID")
        require(auth["kind"] == "SYNTHETIC_HUMAN_USER" and auth["scope"] == _SCOPE and auth["mode"] == MODE and type(auth["actual_forward_days"]) is int and auth["actual_forward_days"] == 0 and auth["native_promotion"] is False and type(auth["authority_id"]) is str and re.fullmatch(r"fixture-authority:[0-9a-f]{32}", auth["authority_id"]), "FORWARD_STORED_AUTHORITY_INVALID")
        _evidence(auth["evidence"])
        _record(item["record"], auth["evidence"])
        body = {key: val for key, val in item.items() if key != "daily_hash"}
        rec = item["record"]
        require(type(item["sequence"]) is int and item["sequence"] == len(records) + 1 and item["predecessor_hash"] == head and item["fixture_authority_hash"] == digest(auth) and item["daily_hash"] == digest(body) and type(item["actual_forward_days"]) is int and item["actual_forward_days"] == 0 and item["native_promotion"] is False, "FORWARD_CHAIN_HASH_OR_SEQUENCE_INVALID")
        require(tuple(row[:6]) == (item["sequence"], rec["source_day"], rec["idempotency_key"], auth["authority_id"], head, item["daily_hash"]), "FORWARD_STORE_COLUMN_DRIFT")
        require(rec["source_day"] not in seen_days and rec["idempotency_key"] not in seen_keys and auth["authority_id"] not in seen_authorities, "FORWARD_STORED_DUPLICATE_INVALID")
        require(not records or _day(rec["source_day"]) > _day(records[-1]["record"]["source_day"]), "FORWARD_DAY_ORDER_INVALID")
        seen_days.add(rec["source_day"])
        seen_keys.add(rec["idempotency_key"])
        seen_authorities.add(auth["authority_id"])
        records.append(item)
        head = item["daily_hash"]
    return {"kind": "FORWARD_PAPER_FIXTURE_DISPLAY", "version": VERSION, "scope": _SCOPE, "namespace": NAMESPACE, "mode": MODE, "store_id": metadata["store_id"], "head_hash": head, "fixture_day_count": len(records), "actual_forward_days": 0, "native_promotion": False, "snapshot_authority": "DISPLAY_ONLY", "records": records}


def create_fixture_store(path):
    """Create exclusive private synthetic storage, not any native account DB."""
    p = _path(path, existing=False)
    fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    conn = None
    try:
        conn = _connect(p, write=True)
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("BEGIN IMMEDIATE")
        for sql in _TABLES.values():
            conn.execute(sql)
        metadata = {"kind": "FORWARD_PAPER_FIXTURE_STORE", "version": VERSION, "scope": _SCOPE, "namespace": NAMESPACE, "account_namespace": ACCOUNT, "strategy_namespace": STRATEGY, "mode": MODE, "observed_universe": list(SYMBOLS), "store_id": "fixture-store:" + uuid.uuid4().hex, "canonical_path": str(p), "actual_forward_days": 0, "native_promotion": False}
        conn.execute("INSERT INTO fixture_metadata VALUES(1,?,?)", (canonical(metadata).decode(), digest(metadata)))
        for sql in _TRIGGERS.values():
            conn.execute(sql)
        conn.execute("PRAGMA user_version=1")
        result = _chain(conn, p)
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


def inspect_fixture_store(path):
    p = _path(path, existing=True)
    conn = _connect(p)
    try:
        conn.execute("BEGIN")
        return _chain(conn, p)
    finally:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.close()


def append_fixture_record(path, authority, record, expected_head):
    """Append in one SQLite transaction; validation failures consume nothing."""
    hash_value(expected_head)
    with _LOCK:
        p = _path(path, existing=True)
        body = _authority(authority)
        _evidence(body["evidence"])
        _record(record, body["evidence"])
        conn = _connect(p, write=True)
        try:
            conn.execute("BEGIN IMMEDIATE")
            before = _chain(conn, p)
            require(before["head_hash"] == expected_head, "FORWARD_STALE_HEAD_CONFLICT")
            prior = before["records"]
            require(not any(item["record"]["source_day"] == record["source_day"] for item in prior), "FORWARD_DUPLICATE_DAY")
            require(not any(item["record"]["idempotency_key"] == record["idempotency_key"] for item in prior), "FORWARD_DUPLICATE_IDEMPOTENCY_KEY")
            require(not prior or _day(record["source_day"]) > _day(prior[-1]["record"]["source_day"]), "FORWARD_DAY_ORDER_INVALID")
            item = {"sequence": len(prior) + 1, "record": copy.deepcopy(record), "fixture_authority": copy.deepcopy(body), "fixture_authority_hash": digest(body), "predecessor_hash": expected_head, "actual_forward_days": 0, "native_promotion": False}
            item["daily_hash"] = digest(item)
            conn.execute("INSERT INTO fixture_records VALUES(?,?,?,?,?,?,?)", (item["sequence"], record["source_day"], record["idempotency_key"], authority.authority_id, expected_head, item["daily_hash"], canonical(item).decode()))
            result = _chain(conn, p)
            conn.execute("COMMIT")
            _USED.add(authority.authority_id)
            return result
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()


def readiness():
    return {"version": VERSION, "namespace": NAMESPACE, "adapter_state": "IMPLEMENTED_FIXTURE_PERSISTENCE_ONLY", "storage_boundary": "ISOLATED_SQLITE_APPEND_ONLY", "supported_record": "NO_DECISION", "hypothetical_fill_support": False, "real_start_state": "BLOCKED", "real_authority_issuance": "UNAVAILABLE_THIS_WAVE", "actual_forward_days": 0, "actual_settings": UNSET, "snapshot_b_state": "PENDING", "source_admission": "BLOCKED", "provider_license_transport": "UNVERIFIED", "historical_visibility_proven": False, "native_promotion": False, "scheduling_enabled": False, "fixture_authorities": "PROCESS_LOCAL_OPAQUE", "fixture_ledger": "DURABLE_CANONICAL_PATH_BOUND", "integrity_limit": "NOT_PRIVILEGED_FILESYSTEM_OR_HOSTILE_INTERPRETER_PROOF", "reason_codes": ["REAL_FORWARD_NOT_AUTHORIZED", "UNSET_REQUIRED", "PROVIDER_LICENSE_BLOCKED", "SOURCE_PIT_UNPROVEN", "TRADEABILITY_UNKNOWN", "SEPARATE_HUMAN_OWNER_AUTHORIZATION_REQUIRED"]}


def run_real_forward(*args, **kwargs):
    raise ValueError("REAL_FORWARD_NOT_AUTHORIZED")
