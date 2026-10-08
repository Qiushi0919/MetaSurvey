"""Owner-authorized, finite LOCAL_ONLY REST capture in a new immutable epoch.

Success is access evidence only. No provider/license/PIT/execution authority exists.
Exact response bytes are quarantined outside Git by explicit Owner probe permission.
"""
from __future__ import annotations
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dataclasses import dataclass

_OLD_PATH = Path(__file__).resolve().parents[1] / "tushare-admission/probe.py"
_old_spec = importlib.util.spec_from_file_location("_frozen_tushare_probe_utilities", _OLD_PATH)
_old = importlib.util.module_from_spec(_old_spec)
sys.modules[_old_spec.name] = _old
_old_spec.loader.exec_module(_old)
if hashlib.sha256(_OLD_PATH.read_bytes()).hexdigest() != "abb2fb787b197a8048c5b4a8d54ab6e2a68f356006f0794c7daf25b942e4487e":
    raise RuntimeError("FROZEN_UTILITY_EPOCH_MISMATCH")

VERSION = "1.0.0"
BASE_URL = "http://118.89.117.77:8030/"
PROVIDER_ID = "TUSHARE_MONTHLY_GATEWAY"
SOURCE_CLASSIFICATION = "OWNER_PROVIDED_MONTHLY_GATEWAY"
PURPOSE = "LOCAL_REAL_RESEARCH_ADMISSION_PROBE"
SYMBOLS = ("603993.SH", "600312.SH", "603228.SH")
KEYCHAIN_SERVICE = "ashare-trading-v1/tushare-monthly-gateway"
KEYCHAIN_ACCOUNT = "stock_api"
ARCHIVE_ROOT = Path("/Users/qiushi/投资研究/.p1b-archives/tushare-real-admission-20261005/captures")
MAX_BYTES = _old.MAX_BYTES
MIN_INTERVAL = 3.0
GATES = {key: "BLOCKED" for key in ("REAL_DATA_ADMISSION_GATE", "LOCAL_REAL_RESEARCH_GATE",
    "CLOUD_RESEARCH_EXPORT_GATE", "HISTORICAL_BACKTEST_GATE", "PRODUCTION_DATA_GATE",
    "REDISTRIBUTION", "CLOUD_MODEL", "RESEARCH_PILOT", "SIGNAL_ORDER", "BROKER_PRODUCTION")}

class ProbeError(Exception):
    pass

class Credential:
    __slots__ = ("_value", "_echo")
    def __init__(self, value):
        try:
            echo = _old.Credential(value)
        except Exception:
            raise ProbeError("CREDENTIAL_FORMAT_INVALID") from None
        object.__setattr__(self, "_value", value)
        object.__setattr__(self, "_echo", echo)
    def __setattr__(self, *_):
        raise ProbeError("CREDENTIAL_IMMUTABLE")
    def __repr__(self): return "Credential(<REDACTED>)"
    def __str__(self): return "<REDACTED>"

def _native_keychain_get(service, account):
    """Read RAM-only bytes through this Python application's Keychain ACL."""
    framework = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
    find = framework.SecKeychainFindGenericPassword
    find.argtypes = (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32,
        ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p)
    find.restype = ctypes.c_int32
    release = framework.SecKeychainItemFreeContent
    release.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
    release.restype = ctypes.c_int32
    service_bytes, account_bytes = service.encode("utf-8"), account.encode("utf-8")
    length, content = ctypes.c_uint32(), ctypes.c_void_p()
    try:
        status = find(None, len(service_bytes), service_bytes, len(account_bytes), account_bytes,
                      ctypes.byref(length), ctypes.byref(content), None)
        if type(status) is not int or status != 0:
            return status, None
        if length.value > 4096: raise ProbeError("KEYCHAIN_LOOKUP_FAILED")
        if not content.value:
            return status, b"" if length.value == 0 else None
        return status, ctypes.string_at(content, length.value)
    finally:
        if content.value:
            release(None, content)

def lookup_credential(*, service=KEYCHAIN_SERVICE, account=KEYCHAIN_ACCOUNT, native_getter=None):
    if type(service) is not str or type(account) is not str or not all(re.fullmatch(r"[A-Za-z0-9_.:@/ -]{1,160}", x) for x in (service, account)):
        return None, _lookup(False, "INVALID_KEYCHAIN_REFERENCE", "EXPLICIT_KEYCHAIN")
    if (service, account) != (KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT):
        return None, _lookup(False, "UNAPPROVED_KEYCHAIN_REFERENCE", "EXPLICIT_KEYCHAIN")
    try:
        getter = _native_keychain_get if native_getter is None else native_getter
        status, secret_bytes = getter(service, account)
        if type(status) is not int:
            return None, _lookup(False, "KEYCHAIN_LOOKUP_FAILED", "EXPLICIT_KEYCHAIN")
        if status == -25300:
            return None, _lookup(False, "KEYCHAIN_ITEM_NOT_FOUND", "EXPLICIT_KEYCHAIN")
        if status != 0 or type(secret_bytes) is not bytes or len(secret_bytes) > 4096:
            return None, _lookup(False, "KEYCHAIN_LOOKUP_FAILED", "EXPLICIT_KEYCHAIN")
        value = secret_bytes.decode("utf-8").strip()
        if not value:
            return None, _lookup(False, "KEYCHAIN_EMPTY", "EXPLICIT_KEYCHAIN")
        credential = Credential(value)
        return credential, _lookup(True, "FOUND", "EXPLICIT_KEYCHAIN")
    except Exception:
        return None, _lookup(False, "KEYCHAIN_LOOKUP_FAILED", "EXPLICIT_KEYCHAIN")

def _lookup(presence, result, source):
    return {"secret_presence": presence, "lookup_result": result, "credential_source": source}

def _hash(value):
    return "sha256:" + hashlib.sha256(value).hexdigest()

def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def _clock():
    value = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    _old._validate_clock(value)
    return value

@dataclass(frozen=True)
class RequestSpec:
    id: str
    category: str
    api_name: str
    params: tuple
    fields: tuple
    max_rows: int
    date_key: str | None
    start_date: str | None
    end_date: str | None
    units: tuple
    adjustment: str
    scope: str

    def public(self):
        return {"request_id": self.id, "category": self.category, "api_name": self.api_name,
                "params": dict(self.params), "fields": list(self.fields), "max_rows": self.max_rows,
                "date_scope": {"key": self.date_key, "start": self.start_date, "end": self.end_date},
                "units": dict(self.units), "price_adjustment": self.adjustment, "scope": self.scope}

def build_plan(stage="SMOKE"):
    if type(stage) is not str or stage not in ("SMOKE", "COVERAGE"):
        raise ProbeError("UNAPPROVED_PLAN_STAGE")
    start, end = ("20260928", "20260930") if stage == "SMOKE" else ("20250601", "20261005")
    fin = (("period", "20260630"),) if stage == "SMOKE" else (("start_date", "20230101"), ("end_date", "20261005"))
    from_old = {item.api_name: item for item in _old.build_plan() if dict(item.params).get("ts_code") == SYMBOLS[0]}
    definitions = (
        ("stock_basic", "SECURITY_STATUS", (), 1, None, None, None),
        ("suspend_d", "SECURITY_STATUS", (("start_date", start), ("end_date", end)), 512 if stage == "COVERAGE" else 16, "trade_date", start, end),
        ("daily", "RAW_BARS", (("start_date", start), ("end_date", end)), 512 if stage == "COVERAGE" else 3, "trade_date", start, end),
        ("adj_factor", "ADJUSTMENT_VERSIONS", (("start_date", start), ("end_date", end)), 512 if stage == "COVERAGE" else 3, "trade_date", start, end),
        ("dividend", "CORPORATE_ACTIONS", (("ann_date", "20260930"),) if stage == "SMOKE" else (), 256 if stage == "COVERAGE" else 16, "ann_date" if stage == "SMOKE" else None, "20260930" if stage == "SMOKE" else None, "20260930" if stage == "SMOKE" else None),
        ("fina_indicator", "FINANCIAL_REVISIONS", fin, 100, "end_date", "20260630" if stage == "SMOKE" else "20230101", "20260630" if stage == "SMOKE" else "20261005"),
        ("index_member_all", "INDUSTRY_MEMBERSHIP", (), 16, None, None, None),
    )
    calendar_start, calendar_end = ("20260928", "20261009") if stage == "SMOKE" else (start, end)
    specs = [RequestSpec("trade_cal-SSE-" + stage, "CALENDAR_RULES", "trade_cal",
        (("exchange", "SSE"), ("start_date", calendar_start), ("end_date", calendar_end), ("ts_type_name", BASE_URL)),
        ("exchange", "cal_date", "is_open", "pretrade_date"), 512 if stage == "COVERAGE" else 12,
        "cal_date", calendar_start, calendar_end, (), "NOT_APPLICABLE", stage)]
    for symbol in SYMBOLS:
        for api, category, params, cap, key, begin, stop in definitions:
            old = from_old[api]
            specs.append(RequestSpec(api + "-" + symbol + "-" + stage, category, api,
                (("ts_code", symbol),) + params + (("ts_type_name", BASE_URL),), old.fields, cap, key, begin, stop,
                old.units, old.adjustment_state, stage))
    return tuple(specs)

def validate_plan(plan):
    if type(plan) not in (tuple, list) or len(plan) > 22:
        raise ProbeError("REQUEST_BUDGET_EXCEEDED")
    allowed = {item.id: item for stage in ("SMOKE", "COVERAGE") for item in build_plan(stage)}
    result, seen, stages = [], set(), set()
    for item in plan:
        if type(item) is not RequestSpec:
            raise ProbeError("UNAPPROVED_REQUEST_SCOPE")
        if (any(type(value) is not str for value in (item.id, item.category, item.api_name, item.adjustment, item.scope))
            or any(value is not None and type(value) is not str for value in (item.date_key, item.start_date, item.end_date))
            or type(item.max_rows) is not int or type(item.fields) is not tuple
            or any(type(value) is not str for value in item.fields)
            or any(type(values) is not tuple or any(type(pair) is not tuple or len(pair) != 2
                or any(type(value) is not str for value in pair) for pair in values) for values in (item.params, item.units))
            or allowed.get(item.id) != item):
            raise ProbeError("UNAPPROVED_REQUEST_SCOPE")
        if item.id in seen: raise ProbeError("DUPLICATE_REQUEST")
        seen.add(item.id); stages.add(item.scope); result.append(allowed[item.id])
    if len(stages) > 1: raise ProbeError("MIXED_PLAN_STAGES")
    return tuple(result)

def request_fingerprint(spec):
    validate_plan((spec,))
    return _hash(_canonical({"provider_id": PROVIDER_ID, "endpoint_base": BASE_URL,
        "api_name": spec.api_name, "params": dict(spec.params), "fields": list(spec.fields),
        "namespace": "CORE_40", "purpose": PURPOSE, "scope": spec.scope}))

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ProbeError("AUTH_REDIRECT_BLOCKED")

def _live_transport(spec, credential):
    validate_plan((spec,))
    if type(credential) is not Credential: raise ProbeError("CREDENTIAL_TYPE_INVALID")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    url = BASE_URL + "/" + spec.api_name  # exact SDK1.4.29 appended path; no route fallback
    wire = {"api_name": spec.api_name, "token": credential._value,
            "params": dict(spec.params), "fields": ",".join(spec.fields)}
    req = urllib.request.Request(url, data=_canonical(wire), method="POST", headers={"Content-Type": "application/json"})
    try:
        response = opener.open(req, timeout=20)
    except urllib.error.HTTPError as error:
        if 300 <= error.code < 400: raise ProbeError("AUTH_REDIRECT_BLOCKED") from None
        response = error  # meaningful failure response retained, only after secret-echo checks
    except ProbeError:
        raise
    except Exception:
        raise ProbeError("TRANSPORT_ERROR") from None
    try:
        with response:
            if response.geturl() != url: raise ProbeError("AUTH_REDIRECT_BLOCKED")
            status = int(response.code)
            raw = response.read(MAX_BYTES + 1)
    except ProbeError:
        raise
    except Exception:
        raise ProbeError("TRANSPORT_ERROR") from None
    if len(raw) > MAX_BYTES: raise ProbeError("RESPONSE_SIZE_EXCEEDED")
    return status, raw

def _secret_check(raw, credential):
    if type(raw) is not bytes or len(raw) > MAX_BYTES: raise ProbeError("RESPONSE_SIZE_EXCEEDED")
    if type(credential) is not Credential: raise ProbeError("CREDENTIAL_TYPE_INVALID")
    if credential._echo.body_contains_secret(raw): raise ProbeError("SECRET_ECHO_DETECTED")
    try:
        text = raw.decode("utf-8")
        unescaped = re.sub(r"\\u([0-9a-fA-F]{4})", lambda match: chr(int(match.group(1), 16)), text)
        if credential._echo.text_contains_secret(unescaped): raise ProbeError("SECRET_ECHO_DETECTED")
    except UnicodeDecodeError:
        # An invalid UTF-8 response cannot be valid JSON and cannot be reliably
        # checked for encoded credentials. Discard it before any hash or sink.
        raise ProbeError("NON_UTF8_RESPONSE_QUARANTINE") from None
    try:
        parsed = _old.parse_response(raw)
    except Exception:
        return
    if credential._echo.object_contains_secret(parsed): raise ProbeError("SECRET_ECHO_DETECTED")

def _decimal(value):
    try: return Decimal(_old.decimal_text(value))
    except Exception: raise ProbeError("DQ_DECIMAL_INVALID") from None

def _date(value):
    try: return _old._date(value)
    except Exception: raise ProbeError("DQ_DATE_INVALID") from None

def analyze_response(spec, raw, retrieved_at):
    """Pure DQ: no source admission; normalized values stay in memory only."""
    validate_plan((spec,))
    try: clock = _old._validate_clock(retrieved_at)
    except Exception: raise ProbeError("CLOCK_INVALID") from None
    default = {"provider_code": None, "provider_msg_classification": "UNPARSED_RESPONSE",
        "row_count": None, "response_schema": None, "dq_status": "BLOCKED", "dq_reasons": [],
        "event_dates": [], "published_dates": [], "publication_precision": "UNKNOWN",
        "provider_version": "UNSET_REQUIRED", "revision_history_proven": False,
        "industry_historical_visibility_proven": False}
    try:
        doc = _old.parse_response(raw)
    except Exception:
        return {**default, "dq_reasons": ["RESPONSE_JSON_INVALID"]}
    if type(doc) is not dict or type(doc.get("code")) is not int:
        return {**default, "dq_reasons": ["PROVIDER_CODE_INVALID"]}
    code = doc["code"]
    msg = doc.get("msg")
    text = msg.lower() if type(msg) is str else ""
    if code != 0:
        if any(x in text for x in ("token无效", "invalid token", "认证失败", "authentication failed")):
            classification = "AUTHENTICATION_FAILED"
        elif any(x in text for x in ("rate limit", "限流", "频次超")):
            classification = "RATE_LIMITED"
        elif code in (2002, -2002) or any(x in text for x in ("没有访问", "无权限", "权限不足", "permission denied", "permission not granted")):
            classification = "ENTITLEMENT_NOT_GRANTED"
        else: classification = "API_ERROR"
        return {**default, "provider_code": code, "provider_msg_classification": classification,
                "dq_reasons": [classification]}
    data = doc.get("data")
    if type(data) is not dict or type(data.get("fields")) is not list or type(data.get("items")) is not list:
        return {**default, "provider_code": code, "provider_msg_classification": "API_SUCCESS_INVALID_TABLE", "dq_reasons": ["TABLE_INVALID"]}
    fields, values = data["fields"], data["items"]
    if (any(type(name) is not str or name not in spec.fields for name in fields)
        or len(fields) != len(set(fields)) or (set(fields) != set(spec.fields) and not (not fields and not values))):
        return {**default, "provider_code": code, "dq_reasons": ["SCHEMA_MISMATCH"]}
    if len(values) > spec.max_rows:
        return {**default, "provider_code": code, "dq_reasons": ["ROW_CAP_EXCEEDED"]}
    seen, dates, publications, quarters, version_flags, open_sessions = set(), set(), set(), set(), set(), set()
    provider_dates = {}
    schema = {name: set() for name in fields}; normalized = []
    try:
        for vector in values:
            if type(vector) is not list or len(vector) != len(fields): raise ProbeError("ROW_SHAPE_INVALID")
            row = dict(zip(fields, vector)); params = dict(spec.params)
            if "ts_code" in params and row["ts_code"] != params["ts_code"]: raise ProbeError("SYMBOL_SCOPE_MISMATCH")
            if spec.api_name == "stock_basic":
                if row["symbol"] != params["ts_code"][:6] or row["exchange"] != "SSE" or row["curr_type"] != "CNY":
                    raise ProbeError("SECURITY_IDENTITY_MISMATCH")
                if row["list_status"] not in ("L", "D", "P"): raise ProbeError("SECURITY_STATUS_INVALID")
            if spec.api_name == "trade_cal" and row["exchange"] != "SSE": raise ProbeError("EXCHANGE_SCOPE_MISMATCH")
            if spec.date_key:
                date = _date(row[spec.date_key])
                if not spec.start_date <= date <= spec.end_date: raise ProbeError("DATE_SCOPE_MISMATCH")
                dates.add(date)
            converted = {}
            for name, value in row.items():
                if value is None: kind = "NULL"; converted[name] = None
                elif name in dict(spec.units):
                    converted[name] = format(_decimal(value), "f"); kind = "DECIMAL_STRING"
                elif type(value) in (str, int):
                    converted[name] = value; kind = "STRING" if type(value) is str else "INTEGER"
                else: raise ProbeError("CELL_TYPE_INVALID")
                schema[name].add(kind)
                if name.endswith("_date") and value is not None:
                    date_value = _date(value)
                    provider_dates.setdefault(name, set()).add(date_value)
                    if name in ("ann_date", "f_ann_date"):
                        if date_value > clock.astimezone(timezone(timedelta(hours=8))).strftime("%Y%m%d"):
                            raise ProbeError("FUTURE_PUBLICATION_DATE")
                        publications.add(date_value)
            if spec.api_name == "suspend_d":
                key = (row["ts_code"], row["trade_date"], row["suspend_type"], row["suspend_timing"])
            elif spec.api_name in ("daily", "adj_factor", "trade_cal", "stock_basic"):
                key = (row.get("ts_code", row.get("exchange")), row.get("trade_date", row.get("cal_date")))
            else:
                key = tuple((name, str(converted[name])) for name in sorted(converted))  # distinct revisions append, exact duplicate reject
            if key in seen: raise ProbeError("DUPLICATE_KEY")
            seen.add(key)
            if spec.api_name == "daily":
                needed = ("open", "high", "low", "close", "pre_close", "vol", "amount")
                if any(row[name] is None for name in needed): raise ProbeError("RAW_BAR_REQUIRED_VALUE_MISSING")
                o, h, l, c, p, v, a = [_decimal(row[name]) for name in needed]
                if min(o, h, l, c, p) <= 0 or h < max(o, l, c) or l > min(o, h, c): raise ProbeError("OHLC_INVALID")
                if min(v, a) < 0: raise ProbeError("NEGATIVE_VOLUME_AMOUNT")
            if spec.api_name == "adj_factor" and (row["adj_factor"] is None or _decimal(row["adj_factor"]) <= 0):
                raise ProbeError("FACTOR_INVALID")
            if spec.api_name == "trade_cal" and str(row["is_open"]) not in ("0", "1"): raise ProbeError("CALENDAR_STATE_INVALID")
            if spec.api_name == "trade_cal" and row["pretrade_date"] is not None and _date(row["pretrade_date"]) >= _date(row["cal_date"]):
                raise ProbeError("CALENDAR_PREVIOUS_DATE_INVALID")
            if spec.api_name == "trade_cal" and str(row["is_open"]) == "1": open_sessions.add(row["cal_date"])
            if spec.api_name == "index_member_all" and row["is_new"] not in ("Y", "N"): raise ProbeError("INDUSTRY_CURRENT_SCOPE_MISMATCH")
            if spec.api_name == "fina_indicator":
                quarters.add(row["end_date"])
                if row.get("update_flag") is not None: version_flags.add(str(row["update_flag"]))
            normalized.append(converted)
    except ProbeError as error:
        return {**default, "provider_code": 0, "provider_msg_classification": "API_SUCCESS_DQ_FAILED",
                "row_count": len(values), "dq_reasons": [str(error)]}
    return {**default, "provider_code": 0,
        "provider_msg_classification": "API_SUCCESS_NONEMPTY" if values else "API_SUCCESS_EMPTY_NOT_COVERAGE",
        "row_count": len(values), "response_schema": [{"field": name, "types": sorted(schema[name])} for name in fields],
        "dq_status": "PASS" if values else "EMPTY_NOT_COVERAGE", "dq_reasons": [],
        "event_dates": sorted(dates), "published_dates": sorted(publications),
        "publication_precision": "DATE_ONLY" if publications else "UNKNOWN",
        "provider_date_fields": {key: sorted(value) for key, value in provider_dates.items()},
        "coverage": {"unique_dates": len(dates), "open_sessions": len(open_sessions), "unique_report_periods": len(quarters),
                     "target_sessions": 320, "target_quarters": 12,
                     "target_counts_met": len(open_sessions) >= 320 if spec.api_name == "trade_cal" else len(quarters) >= 12 if spec.api_name == "fina_indicator" else len(dates) >= 320,
                     "coverage_sufficient_for_admission": False},
        "revision_flags_observed": sorted(version_flags),
        "normalized_hash": _hash(_canonical(sorted(normalized, key=lambda r: _canonical(r))))}

_capture_registry = {}
_report_registry = {}
_CAPTURE_ISSUER = object()
class CaptureHandle:
    __slots__ = ()
    def __repr__(self): return "CaptureHandle(<OPAQUE>)"

def _register_capture(raw, spec, credential, status, started, completed, fixture, *, _issuer=None):
    if _issuer is not _CAPTURE_ISSUER: raise ProbeError("CAPTURE_ISSUER_REQUIRED")
    _secret_check(raw, credential)
    if type(status) is not int or status < 100 or status > 599: raise ProbeError("HTTP_STATUS_INVALID")
    _old._validate_clock(started); _old._validate_clock(completed)
    if _old._validate_clock(completed) < _old._validate_clock(started): raise ProbeError("CLOCK_REVERSED")
    handle = CaptureHandle()
    _capture_registry[id(handle)] = (handle, bytes(raw), spec, status, started, completed, fixture)
    return handle

def _open_capture(handle):
    entry = _capture_registry.get(id(handle))
    if type(handle) is not CaptureHandle or entry is None or entry[0] is not handle:
        raise ProbeError("UNREGISTERED_CAPTURE")
    return entry

def _safe_run_id(run_id):
    if type(run_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,90}", run_id): raise ProbeError("RUN_ID_INVALID")
    return run_id

def _mkdir_tree(root):
    root = Path(root)
    for node in (root, *root.parents):
        if node.is_symlink(): raise ProbeError("ARCHIVE_SYMLINK_BLOCKED")
        if node.exists() and not node.is_dir(): raise ProbeError("ARCHIVE_DIRECTORY_INVALID")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root

def _exclusive_write(path, raw):
    path = Path(path)
    if not path.is_absolute() or any(part in (".", "..") for part in path.parts): raise ProbeError("ARCHIVE_PATH_INVALID")
    directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parent.parts[1:]:
            try: os.mkdir(part, 0o700, dir_fd=directory)
            except FileExistsError: pass
            try:
                next_dir = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            except OSError:
                raise ProbeError("ARCHIVE_SYMLINK_OR_INVALID_DIRECTORY") from None
            os.close(directory); directory = next_dir
        try:
            fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        except FileExistsError:
            raise ProbeError("ARTIFACT_EXISTS_NO_OVERWRITE") from None
        with os.fdopen(fd, "wb") as output: output.write(raw)
    finally:
        os.close(directory)

def persist_capture(handle, run_id):
    entry = _open_capture(handle)
    if entry[6]: raise ProbeError("SYNTHETIC_CAPTURE_CANNOT_PERSIST_AS_REAL")
    _safe_run_id(run_id)
    spec, raw = entry[2], entry[1]
    path = ARCHIVE_ROOT / run_id / spec.api_name / (spec.id + ".response.json")
    _exclusive_write(path, raw)
    if _hash(path.read_bytes()) != _hash(raw): raise ProbeError("PERSISTED_RAW_INTEGRITY_FAILED")
    return {"raw_ref": str(path), "raw_sha256": _hash(raw), "raw_bytes": len(raw),
            "raw_storage_authority": "OWNER_PROBE_QUARANTINE_ONLY_SUPPLIER_LICENSE_UNVERIFIED"}

def _matrix(requests):
    categories = []
    for category in ("SECURITY_STATUS", "CALENDAR_RULES", "RAW_BARS", "CORPORATE_ACTIONS", "ADJUSTMENT_VERSIONS", "FINANCIAL_REVISIONS", "ANNOUNCEMENTS", "INDUSTRY_MEMBERSHIP"):
        rows = [r for r in requests if r["category"] == category]
        categories.append({"category": category, "probe_statuses": sorted({r["status"] for r in rows}) if rows else ["NOT_QUERIED"],
            "entitlement_status": "TECHNICAL_ACCESS_ONLY" if any(r.get("row_count", 0) for r in rows) else "NOT_PROVEN",
            "provider_identity_status": "UNVERIFIED", "license_status": "UNVERIFIED", "transport_status": "HTTP_OWNER_ACCEPTED_FOR_PROBE_INTEGRITY_UNVERIFIED",
            "raw_integrity": "HASH_CAPTURE_ONLY" if any(r.get("raw_sha256") for r in rows) else "NOT_CAPTURED",
            "clock_status": "CURRENT_OBSERVED_ONLY" if any(r.get("response_completed_at") for r in rows) else "NOT_CAPTURED",
            "coverage_status": "NOT_ADMITTED", "dq_statuses": sorted({r.get("dq_status", "BLOCKED") for r in rows}),
            "historical_visibility_proven": False, "admission_status": "BLOCKED",
            "reason_codes": ["PROVIDER_IDENTITY_AND_PURPOSE_LICENSE_UNVERIFIED"], "next_action": "OWNER_PROVIDER_LICENSE_EVIDENCE"})
    return categories

def run_probe(*, credential=None, credential_source="OWNER_PROVIDED_CURRENT_TURN_RUNTIME", stage="SMOKE", run_id=None, persist=True):
    """Real collector: caller cannot supply transport, clocks, endpoint or provider authority."""
    if credential is not None and type(credential) is not Credential: raise ProbeError("CREDENTIAL_TYPE_INVALID")
    if type(credential_source) is not str or credential_source not in ("OWNER_PROVIDED_CURRENT_TURN_RUNTIME", "EXPLICIT_KEYCHAIN"): raise ProbeError("CREDENTIAL_SOURCE_INVALID")
    if type(persist) is not bool: raise ProbeError("PERSISTENCE_FLAG_INVALID")
    run_id = _safe_run_id(run_id) if run_id is not None else "run-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if credential is not None and credential._echo.text_contains_secret(run_id): raise ProbeError("SECRET_ECHO_DETECTED")
    if persist and credential is not None:
        target = ARCHIVE_ROOT / run_id
        if target.exists() or target.is_symlink(): raise ProbeError("RUN_EXISTS_NO_NETWORK")
    return _run(credential, credential_source, build_plan(stage), run_id, _live_transport, _clock, False, persist, time.monotonic, time.sleep)

def run_synthetic_probe(*, credential, plan, transport, clock, monotonic=time.monotonic, sleeper=time.sleep):
    """Explicit fixture seam, no raw persistence or real network classification."""
    if credential is not None and type(credential) is not Credential: raise ProbeError("CREDENTIAL_TYPE_INVALID")
    return _run(credential, "SYNTHETIC_FIXTURE", validate_plan(plan), "synthetic-fixture", transport, clock, True, False, monotonic, sleeper)

def _run(credential, credential_source, plan, run_id, transport, clock, fixture, persist, monotonic, sleeper):
    if credential is not None and type(credential) is not Credential: raise ProbeError("CREDENTIAL_TYPE_INVALID")
    if type(credential_source) is not str or credential_source not in ("OWNER_PROVIDED_CURRENT_TURN_RUNTIME", "EXPLICIT_KEYCHAIN", "SYNTHETIC_FIXTURE"):
        raise ProbeError("CREDENTIAL_SOURCE_INVALID")
    _safe_run_id(run_id)
    if credential is not None and credential._echo.text_contains_secret(run_id): raise ProbeError("SECRET_ECHO_DETECTED")
    plan = validate_plan(plan)
    generated = clock(); _old._validate_clock(generated)
    report = {"version": VERSION, "report_kind": "SYNTHETIC_PROBE_FIXTURE" if fixture else "OWNER_AUTHORIZED_QUARANTINE_PROBE",
        "fixture": fixture, "run_id": run_id, "generated_at": generated, "provider_id": PROVIDER_ID,
        "source_classification": SOURCE_CLASSIFICATION, "purpose": PURPOSE, "namespace": "CORE_40", "symbols": list(SYMBOLS),
        "actual_account_tier": 15000, "account_tier_evidence": "OWNER_ASSERTION_NOT_ACCOUNT_VERIFIED", "owner_asserted_expiration_date": "2026-11-05",
        "expiration_precision": "DATE_ONLY", "expiration_instant": "UNSET_REQUIRED", "credential_rotation_required": False,
        "credential_exposure_risk": "OWNER_ACCEPTED", "credential_lookup": _lookup(credential is not None, "PRESENT_RUNTIME" if credential else "SECRET_NOT_AVAILABLE", credential_source),
        "transport": "HTTP_OWNER_ACCEPTED_FOR_PROBE_INTEGRITY_UNVERIFIED", "provider_identity_verified": False, "license_verified": False,
        "historical_visibility_proven": False, "productionGate": False, "gates": dict(GATES), "requests": [],
        "admission_refs": {"SourceObservation": None, "ClockEvidence": None, "policy": None, "snapshot": None, "receipt": None},
        "cross_cutting": {"C14": "BLOCKED_HISTORICAL", "C19": "UNSET_REQUIRED_HISTORICAL"},
        "network_requests": 0, "mock_transport_attempts": 0, "code_hash": _hash(Path(__file__).read_bytes()),
        "frozen_utility_hash": _hash(_OLD_PATH.read_bytes())}
    last = None
    for spec in plan:
        item = {**spec.public(), "request_fingerprint": request_fingerprint(spec), "source_classification": SOURCE_CLASSIFICATION,
            "request_started_at": None, "response_completed_at": None, "http_status": None, "provider_code": None,
            "provider_msg_classification": "NOT_QUERIED", "row_count": None, "response_schema": None,
            "raw_ref": None, "raw_sha256": None, "dq_status": "BLOCKED", "historical_visibility_proven": False,
            "event_time": None, "business_effective_at": None, "published_at": None, "published_precision": "UNKNOWN",
            "observation_event_at": None, "available_at": None, "retrieved_at": None, "available_at_basis": None,
            "admission_status": "BLOCKED", "code_hash": report["code_hash"], "reason_codes": []}
        if credential is None:
            item.update(status="BLOCKED_SECRET_NOT_AVAILABLE", reason_codes=["SECRET_NOT_AVAILABLE"])
        else:
            now = monotonic()
            if last is not None and now - last < MIN_INTERVAL:
                sleeper(MIN_INTERVAL - (now - last)); now = monotonic()
                if now - last < MIN_INTERVAL: raise ProbeError("LOCAL_RATE_BUDGET_NOT_ENFORCED")
            last = now
            started = clock(); _old._validate_clock(started)
            report["mock_transport_attempts" if fixture else "network_requests"] += 1
            try:
                status, raw = transport(spec, credential)
                completed = clock(); _old._validate_clock(completed)
                handle = _register_capture(raw, spec, credential, status, started, completed, fixture, _issuer=_CAPTURE_ISSUER)
                analysis = analyze_response(spec, raw, completed)
                item.update(analysis)
                item.update(request_started_at=started, response_completed_at=completed, http_status=status,
                    raw_sha256=_hash(raw), observation_event_at=completed, available_at=completed, retrieved_at=completed,
                    available_at_basis="FIRST_OBSERVED_BY_THIS_COLLECTOR", published_precision=analysis["publication_precision"])
                if persist: item.update(persist_capture(handle, run_id))
                item["status"] = "PROBE_SUCCESS" if status == 200 and analysis["provider_code"] == 0 else "PROBE_RESPONSE_FAILURE"
                if analysis["dq_status"] == "BLOCKED": item["status"] = "QUARANTINE_DQ_OR_API_FAILURE"
            except Exception as error:
                reason = str(error) if type(error) is ProbeError else "CONTROLLED_CAPTURE_FAILURE"
                if reason not in SAFE_REASONS: reason = "CONTROLLED_CAPTURE_FAILURE"
                item.update(status="QUARANTINE" if reason in {"SECRET_ECHO_DETECTED", "NON_UTF8_RESPONSE_QUARANTINE"} else "BLOCKED",
                            reason_codes=[reason])
        report["requests"].append(item)
    report["categories"] = _matrix(report["requests"])
    report["status"] = "PROBE_COMPLETED_ADMISSION_BLOCKED" if credential else "BLOCKED_SECRET_NOT_AVAILABLE"
    report["completed_at"] = clock(); _old._validate_clock(report["completed_at"])
    if credential is not None and credential._echo.object_contains_secret(report): raise ProbeError("SECRET_ECHO_DETECTED")
    _report_registry[id(report)] = (report, _canonical(report))
    return report

SAFE_REASONS = frozenset({"AUTH_REDIRECT_BLOCKED", "TRANSPORT_ERROR", "RESPONSE_SIZE_EXCEEDED", "SECRET_ECHO_DETECTED",
    "NON_UTF8_RESPONSE_QUARANTINE",
    "CREDENTIAL_TYPE_INVALID", "HTTP_STATUS_INVALID", "CLOCK_REVERSED", "ARCHIVE_SYMLINK_BLOCKED", "ARCHIVE_DIRECTORY_INVALID",
    "ARTIFACT_EXISTS_NO_OVERWRITE", "PERSISTED_RAW_INTEGRITY_FAILED", "UNREGISTERED_CAPTURE", "RUN_ID_INVALID",
    "CAPTURE_ISSUER_REQUIRED", "ARCHIVE_PATH_INVALID", "ARCHIVE_SYMLINK_OR_INVALID_DIRECTORY"})

def save_report(report):
    entry = _report_registry.get(id(report))
    if type(report) is not dict or entry is None or entry[0] is not report: raise ProbeError("REPORT_UNREGISTERED")
    if _canonical(report) != entry[1]: raise ProbeError("REPORT_MUTATED")
    if report["fixture"]: raise ProbeError("SYNTHETIC_REPORT_CANNOT_PERSIST_AS_REAL")
    run_id = _safe_run_id(report["run_id"])
    path = ARCHIVE_ROOT / run_id / "probe-report.json"
    _exclusive_write(path, entry[1] + b"\n")
    return str(path)

def main():
    parser = argparse.ArgumentParser(description="Finite local Owner-authorized quarantine probe, no admission/execution.")
    parser.add_argument("--stage", choices=("SMOKE", "COVERAGE"), default="SMOKE")
    parser.add_argument("--run-id")
    parser.add_argument("--keychain-service", default=KEYCHAIN_SERVICE)
    parser.add_argument("--keychain-account", default=KEYCHAIN_ACCOUNT)
    args = parser.parse_args()
    try:
        credential, lookup = lookup_credential(service=args.keychain_service, account=args.keychain_account)
        report = run_probe(credential=credential, credential_source="EXPLICIT_KEYCHAIN", stage=args.stage, run_id=args.run_id)
        # Reader results have fixed enums; register exact finalized metadata without raw output.
        report["credential_lookup"] = lookup
        _report_registry[id(report)] = (report, _canonical(report))
        path = save_report(report)
        print(json.dumps({"status": report["status"], "network_requests": report["network_requests"], "report_saved": True}))
        return 0
    except Exception:
        print(json.dumps({"status": "BLOCKED", "reason_code": "CONTROLLED_RUNNER_FAILURE"}))
        return 2

if __name__ == "__main__": raise SystemExit(main())
