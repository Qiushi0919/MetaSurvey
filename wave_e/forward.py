"""Wave E forward *readiness*, with no real forward authority.

Public API:
  readiness() -> metadata dict; run_real_forward(*args, **kwargs) always rejects.
  issue_fixture_authority(issuer, evidence) -> opaque FixtureAuthority.
  new_fixture_ledger() -> opaque FixtureLedger.
  append_fixture_day(ledger, authority, record) -> new current FixtureLedger.
  fixture_ledger_snapshot(ledger) -> detached FIXTURE_ONLY metadata/records dict.

The two builders are explicitly synthetic test tools. A HUMAN_USER dictionary
can authorize a fixture, never a live session, account, source, or native object.
All snapshots have actual_forward_days == 0; they are not accepted as handles.
Handles are process-local identities, sealed on every use. This is not a claim
about hostile interpreter access, external database transactions, or persistence.

Evidence requires exactly: kind, namespace, schema_version, observed_universe,
source_day, calendar_session, published_at, available_at, retrieved_at,
decision_cutoff, bindings. Calendar session requires kind, venue, source_ref,
session_day, market_close. Bindings require source_hash, rules_hash, code_hash,
schema_hash, receipt_hash. Issuer requires kind, scope, subject,
authorization_id, issued_at, expires_at. Every timestamp is an explicit
nanosecond timestamp with +08:00; date-only, naive, UTC, and midnight imputation
are rejected. Fixture calendar assertions do not establish real exchange proof.

Record inputs require the ledger fields below except daily_hash, which this
module generates. predecessor_hash must match the current ledger head. Signals
and hypothetical records use synthetic field shapes, never native contracts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


NAMESPACE = "LOCAL_FORWARD_PAPER_FIXTURE:CORE_40"
SCHEMA_VERSION = "1.0.0"
SYMBOLS = ("603993.SH", "600312.SH", "603228.SH")
_BASELINE_DAY = date(2026, 9, 30)
_SHA = re.compile(r"^[0-9a-f]{64}$")
_TS = re.compile(
    r"^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})\.(\d{9})\+08:00$"
)
_DAY = re.compile(r"^\d{8}$")
_BINDINGS = {"source_hash", "rules_hash", "code_hash", "schema_hash", "receipt_hash"}
_REASONS = {
    "FIXTURE_ONLY", "HUMAN_FIXTURE_AUTHORITY", "NOT_ACTUAL_FORWARD_DAY",
    "UNSET_REQUIRED", "PROVIDER_LICENSE_BLOCKED", "TRADEABILITY_UNKNOWN",
    "SOURCE_PIT_UNPROVEN", "NO_CANDIDATE", "SYNTHETIC_TRADEABILITY_ASSUMPTION",
    "NO_NATIVE_PROMOTION",
}
_UNKNOWNS = {"actual_account_cost_risk", "provider_license", "historical_pit",
             "tradeability", "source_integrity", "business_quality"}
_REQUIRED_UNKNOWNS = {"actual_account_cost_risk", "provider_license", "historical_pit"}
_RECORD_FIELDS = {
    "decision_cutoff", "observed_universe", "candidate_or_no_candidate",
    "signal_source", "hypothetical_entry", "hypothetical_exit", "tradeability",
    "cost_assumptions", "risk_state", "unknowns", "reason_codes",
    "predecessor_hash", "source_day", "namespace", "schema_version", "bindings",
}


class ForwardBlocked(ValueError):
    """Fail-closed error whose string contains metadata only."""


def _block(code: str) -> None:
    raise ForwardBlocked(code)


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        _block("FIXTURE_CANONICAL_VALUE_INVALID")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _exact(value: Any, fields: set[str], code: str) -> None:
    if type(value) is not dict or set(value) != fields:
        _block(code)


def _day(value: Any) -> date:
    if type(value) is not str or not _DAY.fullmatch(value):
        _block("SOURCE_DAY_INVALID")
    try:
        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        _block("SOURCE_DAY_INVALID")


def _timestamp(value: Any) -> tuple[date, str, int]:
    if type(value) is not str:
        _block("CLOCK_PRECISION_OR_TIMEZONE_INVALID")
    match = _TS.fullmatch(value)
    if match is None:
        _block("CLOCK_PRECISION_OR_TIMEZONE_INVALID")
    day, clock, ns = match.groups()
    try:
        parsed = datetime.strptime(day + "T" + clock, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        _block("CLOCK_VALUE_INVALID")
    if clock == "00:00:00":
        _block("MIDNIGHT_IMPUTATION_FORBIDDEN")
    seconds = parsed.hour * 3600 + parsed.minute * 60 + parsed.second
    # Integer arithmetic preserves every nanosecond, including across dates.
    absolute = parsed.date().toordinal() * 86_400_000_000_000
    absolute += seconds * 1_000_000_000 + int(ns)
    return parsed.date(), clock, absolute


def _strings(value: Any, allowed: set[str], required: set[str], code: str) -> None:
    if (type(value) is not list or any(type(x) is not str for x in value)
            or len(value) != len(set(value)) or not set(value) <= allowed
            or not required <= set(value)):
        _block(code)


def _universe(value: Any) -> None:
    if type(value) is not list or value != list(SYMBOLS):
        _block("UNIVERSE_OR_ORDER_DRIFT")


def _bindings(value: Any) -> None:
    _exact(value, _BINDINGS, "BINDINGS_SCHEMA_INVALID")
    if any(type(v) is not str or not _SHA.fullmatch(v) for v in value.values()):
        _block("BINDING_HASH_INVALID")


def _scope(value: dict) -> None:
    if value["namespace"] != NAMESPACE:
        _block("NAMESPACE_DRIFT")
    if value["schema_version"] != SCHEMA_VERSION:
        _block("SCHEMA_VERSION_DRIFT")
    _universe(value["observed_universe"])
    _bindings(value["bindings"])


@dataclass(frozen=True, eq=False)
class FixtureAuthority:
    """Opaque registered fixture capability; direct construction is rejected."""
    authority_id: str
    _body: dict


@dataclass(frozen=True, eq=False)
class FixtureLedger:
    """Opaque append-only fixture ledger, containing zero actual days."""
    ledger_id: str
    _body: dict


_AUTHORITIES: dict[int, tuple[FixtureAuthority, str]] = {}
_USED_AUTHORITIES: set[int] = set()
_LEDGERS: dict[int, tuple[FixtureLedger, str]] = {}
_HEADS: dict[str, FixtureLedger] = {}


def readiness() -> dict:
    """Report component readiness, not permission to start a real session."""
    return {
        "version": SCHEMA_VERSION,
        "namespace": NAMESPACE,
        "engine_ready": True,
        "real_start_state": "BLOCKED",
        "real_authority_issuance": "UNAVAILABLE_THIS_WAVE",
        "actual_forward_days": 0,
        "actual_settings": "UNSET_REQUIRED",
        "unset_actual_parameter_count": 30,
        "reason_codes": ["REAL_FORWARD_NOT_AUTHORIZED", "UNSET_REQUIRED",
                         "PROVIDER_LICENSE_BLOCKED", "SOURCE_PIT_UNPROVEN",
                         "TRADEABILITY_UNKNOWN"],
        "snapshot_b_state": "PENDING",
        "native_promotion": False,
        "scheduling_enabled": False,
    }


def run_real_forward(*args: Any, **kwargs: Any) -> None:
    """Always block, including booleans, receipts, copies and LLM approval."""
    _block("REAL_FORWARD_NOT_AUTHORIZED")


def issue_fixture_authority(issuer: dict, evidence: dict) -> FixtureAuthority:
    """Validate caller-supplied *synthetic* evidence and issue only a fixture.

    A valid HUMAN_USER issuer has scope FIXTURE_ONLY and subject
    SYNTHETIC_HUMAN_USER; this cannot represent a real Owner authorization.
    Receipt hashes bind synthetic evidence, not actual SourceAdmission receipts.
    """
    _exact(issuer, {"kind", "scope", "subject", "authorization_id", "issued_at",
                    "expires_at"}, "HUMAN_FIXTURE_AUTHORITY_SCHEMA_INVALID")
    if (issuer["kind"] != "HUMAN_USER" or issuer["scope"] != "FIXTURE_ONLY"
            or issuer["subject"] != "SYNTHETIC_HUMAN_USER"):
        _block("HUMAN_FIXTURE_AUTHORITY_REQUIRED")
    if (type(issuer["authorization_id"]) is not str
            or not re.fullmatch(r"fixture:[A-Za-z0-9_-]{1,80}", issuer["authorization_id"])):
        _block("FIXTURE_AUTHORIZATION_ID_INVALID")
    _exact(evidence, {"kind", "namespace", "schema_version", "observed_universe",
                      "source_day", "calendar_session", "published_at", "available_at",
                      "retrieved_at", "decision_cutoff", "bindings"},
           "FIXTURE_EVIDENCE_SCHEMA_INVALID")
    if evidence["kind"] != "SYNTHETIC_SOURCE_OBSERVATION":
        _block("SYNTHETIC_EVIDENCE_REQUIRED")
    _scope(evidence)
    source_day = _day(evidence["source_day"])
    if source_day <= _BASELINE_DAY:
        _block("SOURCE_DAY_NOT_NEW")
    # These are known closed days in the Wave E context, not a live calendar.
    if (source_day.weekday() >= 5
            or date(2026, 10, 1) <= source_day <= date(2026, 10, 7)):
        _block("FIXTURE_SESSION_CLOSED")
    session = evidence["calendar_session"]
    _exact(session, {"kind", "venue", "source_ref", "session_day", "market_close"},
           "SESSION_PROOF_SCHEMA_INVALID")
    if (session["kind"] != "SYNTHETIC_OPEN_SESSION" or session["venue"] != "SSE"
            or session["session_day"] != evidence["source_day"]
            or session["source_ref"] != "fixture://calendar/" + evidence["source_day"]):
        _block("SESSION_PROOF_BINDING_INVALID")
    close_day, close_clock, close_ns = _timestamp(session["market_close"])
    if close_day != source_day or close_clock != "15:00:00" or close_ns % 1_000_000_000:
        _block("SESSION_CLOSE_INVALID")
    clock_names = ("published_at", "available_at", "retrieved_at", "decision_cutoff")
    clocks = [_timestamp(evidence[name]) for name in clock_names]
    if any(day != source_day for day, _, _ in clocks):
        _block("SOURCE_CLOCK_DAY_MISMATCH")
    issued = _timestamp(issuer["issued_at"])[2]
    expires = _timestamp(issuer["expires_at"])[2]
    if not close_ns <= clocks[0][2] <= clocks[1][2] <= clocks[2][2] <= clocks[3][2]:
        _block("SOURCE_CLOCK_ORDER_INVALID")
    if not issued <= clocks[3][2] < expires:
        _block("AUTHORITY_CLOCK_ORDER_INVALID")
    authority_id = "fixture-authority:" + uuid.uuid4().hex
    body = {"issuer": copy.deepcopy(issuer), "evidence": copy.deepcopy(evidence),
            "authority_id": authority_id, "scope": "FIXTURE_ONLY",
            "actual_forward_days": 0, "native_promotion": False}
    handle = FixtureAuthority(authority_id, body)
    _AUTHORITIES[id(handle)] = (handle, _hash(body))
    return handle


def _authority(handle: Any) -> dict:
    if type(handle) is not FixtureAuthority:
        _block("REGISTERED_FIXTURE_AUTHORITY_REQUIRED")
    stored = _AUTHORITIES.get(id(handle))
    if stored is None or stored[0] is not handle or stored[1] != _hash(handle._body):
        _block("FIXTURE_AUTHORITY_IDENTITY_OR_SEAL_INVALID")
    if handle.authority_id != handle._body["authority_id"]:
        _block("FIXTURE_AUTHORITY_IDENTITY_OR_SEAL_INVALID")
    if id(handle) in _USED_AUTHORITIES:
        _block("FIXTURE_AUTHORITY_ALREADY_USED")
    return handle._body


def _ledger(handle: Any, *, current: bool = True) -> dict:
    if type(handle) is not FixtureLedger:
        _block("REGISTERED_FIXTURE_LEDGER_REQUIRED")
    stored = _LEDGERS.get(id(handle))
    if stored is None or stored[0] is not handle or stored[1] != _hash(handle._body):
        _block("FIXTURE_LEDGER_IDENTITY_OR_SEAL_INVALID")
    if handle.ledger_id != handle._body["ledger_id"]:
        _block("FIXTURE_LEDGER_IDENTITY_OR_SEAL_INVALID")
    if current and _HEADS.get(handle.ledger_id) is not handle:
        _block("STALE_FIXTURE_LEDGER_HANDLE")
    return handle._body


def new_fixture_ledger() -> FixtureLedger:
    """Create an empty fixture chain, with zero actual forward days."""
    ledger_id = "fixture-ledger:" + uuid.uuid4().hex
    body = {"ledger_id": ledger_id, "version": SCHEMA_VERSION,
            "namespace": NAMESPACE, "kind": "FORWARD_PAPER_FIXTURE",
            "scope": "FIXTURE_ONLY", "actual_forward_days": 0,
            "fixture_day_count": 0, "native_promotion": False,
            "head_hash": _hash({"kind": "FIXTURE_GENESIS", "ledger_id": ledger_id}),
            "records": []}
    handle = FixtureLedger(ledger_id, body)
    _LEDGERS[id(handle)] = (handle, _hash(body))
    _HEADS[ledger_id] = handle
    return handle


def _hypotheticals(value: Any, direction: str) -> set[str]:
    if type(value) is not list:
        _block("HYPOTHETICAL_SHAPE_INVALID")
    symbols: set[str] = set()
    for item in value:
        _exact(item, {"symbol", "direction", "quantity", "price_dpu"},
               "HYPOTHETICAL_SHAPE_INVALID")
        if item["symbol"] not in SYMBOLS or item["symbol"] in symbols:
            _block("HYPOTHETICAL_SYMBOL_OR_DUPLICATE_INVALID")
        if item["direction"] != direction:
            _block("HYPOTHETICAL_DIRECTION_INVALID")
        if type(item["quantity"]) is not int or item["quantity"] <= 0:
            _block("HYPOTHETICAL_QUANTITY_INVALID")
        if type(item["price_dpu"]) is not str:
            _block("HYPOTHETICAL_PRICE_INVALID")
        try:
            number = Decimal(item["price_dpu"])
        except InvalidOperation:
            _block("HYPOTHETICAL_PRICE_INVALID")
        if not number.is_finite() or number <= 0:
            _block("HYPOTHETICAL_PRICE_INVALID")
        symbols.add(item["symbol"])
    return symbols


def append_fixture_day(ledger: FixtureLedger, authority: FixtureAuthority,
                       record: dict) -> FixtureLedger:
    """Append one synthetic day atomically in this process; actual count stays 0.

    An old head cannot be used to replace or fork its successor. Failed
    validation does not consume a valid authority or change the head.
    """
    prior = _ledger(ledger)
    authorization = _authority(authority)
    _exact(record, _RECORD_FIELDS, "FIXTURE_RECORD_SCHEMA_INVALID")
    _scope(record)
    evidence = authorization["evidence"]
    if (record["source_day"] != evidence["source_day"]
            or record["decision_cutoff"] != evidence["decision_cutoff"]
            or record["bindings"] != evidence["bindings"]):
        _block("FIXTURE_AUTHORITY_RECORD_BINDING_DRIFT")
    if record["predecessor_hash"] != prior["head_hash"]:
        _block("FIXTURE_PREDECESSOR_CONFLICT")
    days = [row["source_day"] for row in prior["records"]]
    if record["source_day"] in days:
        _block("DUPLICATE_FIXTURE_DAY")
    if days and _day(record["source_day"]) <= _day(days[-1]):
        _block("FIXTURE_DAY_ORDER_INVALID")
    signal = record["signal_source"]
    _exact(signal, {"kind", "source_day", "source_hash", "receipt_hash"},
           "SIGNAL_SOURCE_SCHEMA_INVALID")
    if (signal["kind"] != "SYNTHETIC_RULE_ENGINE"
            or signal["source_day"] != record["source_day"]
            or signal["source_hash"] != record["bindings"]["source_hash"]
            or signal["receipt_hash"] != record["bindings"]["receipt_hash"]):
        _block("SIGNAL_SOURCE_BINDING_DRIFT")
    if (type(record["candidate_or_no_candidate"]) is not str
            or record["candidate_or_no_candidate"] not in {"CANDIDATE", "NO_CANDIDATE"}):
        _block("CANDIDATE_STATE_INVALID")
    entries = _hypotheticals(record["hypothetical_entry"], "ENTER_HYPOTHETICAL")
    exits = _hypotheticals(record["hypothetical_exit"], "EXIT_HYPOTHETICAL")
    if entries & exits:
        _block("SAME_DAY_HYPOTHETICAL_ROUNDTRIP_FORBIDDEN")
    if record["candidate_or_no_candidate"] == "NO_CANDIDATE" and entries:
        _block("NO_CANDIDATE_ENTRY_FORBIDDEN")
    if (type(record["tradeability"]) is not str
            or record["tradeability"] not in {"UNKNOWN", "ASSUME_TRADEABLE_FIXTURE_ONLY"}):
        _block("TRADEABILITY_STATE_INVALID")
    if record["tradeability"] == "UNKNOWN" and (entries or exits):
        _block("TRADEABILITY_UNKNOWN_BLOCKS_HYPOTHETICAL")
    _exact(record["cost_assumptions"], {"kind", "fixture_policy_ref",
                                       "actual_account_config"}, "COST_SCHEMA_INVALID")
    cost = record["cost_assumptions"]
    if (cost["kind"] != "SYNTHETIC_DPU" or cost["actual_account_config"] != "UNSET_REQUIRED"
            or type(cost["fixture_policy_ref"]) is not str
            or not re.fullmatch(r"fixture://cost/[A-Za-z0-9_-]{1,80}", cost["fixture_policy_ref"])):
        _block("COST_ACTUAL_PARAMETER_PROMOTION_FORBIDDEN")
    if record["risk_state"] != "UNKNOWN_UNSET_REQUIRED":
        _block("RISK_ACTUAL_PARAMETER_PROMOTION_FORBIDDEN")
    _strings(record["unknowns"], _UNKNOWNS, _REQUIRED_UNKNOWNS, "UNKNOWN_ERASURE_FORBIDDEN")
    required_reasons = {"FIXTURE_ONLY", "NOT_ACTUAL_FORWARD_DAY", "UNSET_REQUIRED"}
    if record["tradeability"] == "UNKNOWN":
        required_reasons.add("TRADEABILITY_UNKNOWN")
    else:
        required_reasons.add("SYNTHETIC_TRADEABILITY_ASSUMPTION")
    _strings(record["reason_codes"], _REASONS, required_reasons, "REASON_CODES_INVALID")
    stored_record = copy.deepcopy(record)
    stored_record["fixture_authority_hash"] = _hash(authorization)
    stored_record["daily_hash"] = _hash(stored_record)
    body = copy.deepcopy(prior)
    body["records"].append(stored_record)
    body["head_hash"] = stored_record["daily_hash"]
    body["fixture_day_count"] += 1
    # Hard-coded by construction, never copied from caller flags or counters.
    body["actual_forward_days"] = 0
    handle = FixtureLedger(ledger.ledger_id, body)
    _LEDGERS[id(handle)] = (handle, _hash(body))
    _HEADS[ledger.ledger_id] = handle
    _USED_AUTHORITIES.add(id(authority))
    return handle


def fixture_ledger_snapshot(ledger: FixtureLedger) -> dict:
    """Return a detached display object, which carries no execution authority."""
    body = copy.deepcopy(_ledger(ledger))
    body["actual_forward_days"] = 0
    body["snapshot_authority"] = "DISPLAY_ONLY"
    return body
