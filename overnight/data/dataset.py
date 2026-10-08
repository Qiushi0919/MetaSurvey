"""Closed, read-only G2 quarantine loader and lossless diagnostic normalization.

This is a sidecar, never a DataEnvelope, Snapshot, admission, or historical clock.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.0.1-diagnostic"
SYMBOLS = ("603993.SH", "600312.SH", "603228.SH")
INPUT_PINS = {
    "docs/p1b-real-admission/Gate.json": "sha256:9bbaf33c0c69e7dcf8e572110a59684d621b60d8677f235ec463e22276113917",
    "docs/p1b-real-admission/code-provenance.json": "sha256:a2014a579f5df70745bf4e47fb0bbb0df1a1becde875c9a2767cb76df0ade359",
    "docs/p1b-real-admission/cross-source-comparison.json": "sha256:9c17312b4c5463f26601458c87025ae68ed9bceb0299ef57d306ffbad2cb2a86",
}
_REAL_DATASETS = {}
FIELDS = {
    "trade_cal": ("exchange", "cal_date", "is_open", "pretrade_date"),
    "stock_basic": ("ts_code", "symbol", "name", "exchange", "curr_type", "list_status", "list_date", "delist_date"),
    "suspend_d": ("ts_code", "trade_date", "suspend_timing", "suspend_type"),
    "daily": ("ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"),
    "adj_factor": ("ts_code", "trade_date", "adj_factor"),
    "dividend": ("ts_code", "end_date", "ann_date", "div_proc", "stk_div", "stk_bo_rate", "stk_co_rate", "cash_div", "cash_div_tax", "record_date", "ex_date", "pay_date", "imp_ann_date"),
    "fina_indicator": ("ts_code", "ann_date", "end_date", "eps", "roe", "debt_to_assets", "netprofit_yoy", "update_flag"),
    "index_member_all": ("ts_code", "l1_code", "l1_name", "l2_code", "l2_name", "l3_code", "l3_name", "in_date", "out_date", "is_new"),
}

class DataError(ValueError):
    """Fixed reason code; never echo source values or internal paths."""

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()

def require(condition, reason):
    if not condition: raise DataError(reason)

def _pinned_local(relative, expected):
    path = ROOT / relative
    require(path.resolve() == path and path.is_file() and not path.is_symlink(), "PINNED_LOCAL_PATH_INVALID")
    raw = path.read_bytes()
    require(sha(raw) == expected, "PINNED_INPUT_MUTATED")
    return raw

def _load_verifier():
    provenance = json.loads(_pinned_local("docs/p1b-real-admission/code-provenance.json", INPUT_PINS["docs/p1b-real-admission/code-provenance.json"]))
    require(provenance["approved_policy_count"] == 0 and provenance["production_enabled"] is False, "PROVENANCE_AUTHORITY_INVALID")
    require(len(provenance["files"]) == 9, "SOURCE_PIN_INVENTORY_INVALID")
    for item in provenance["files"]: _pinned_local(item["path"], item["sha256"])
    require(sha((ROOT / "tushare-admission/probe.py").read_bytes()) == "sha256:abb2fb787b197a8048c5b4a8d54ab6e2a68f356006f0794c7daf25b942e4487e", "FROZEN_UTILITY_MUTATED")
    spec = importlib.util.spec_from_file_location("_overnight_frozen_g2_evidence", ROOT / "tushare-real-admission/parent/evidence.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally: sys.dont_write_bytecode = previous
    return module, provenance

def _clock(value):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value), "CLOCK_INVALID")
    try: return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: raise DataError("CLOCK_INVALID") from None

def _validate_request_clocks(request, report):
    values = [_clock(report[k]) for k in ("generated_at", "completed_at")]
    start, end = (_clock(request[k]) for k in ("request_started_at", "response_completed_at"))
    require(values[0] <= start <= end <= values[1], "CLOCK_OUTSIDE_REPORT_OR_REVERSED")
    require(all(request[k] == request["response_completed_at"] for k in ("retrieved_at", "available_at")), "HISTORICAL_CLOCK_SPOOF")
    require(request.get("published_at") is None, "DATE_ONLY_MIDNIGHT_SPOOF")
    return end

def _date_literal(value):
    if type(value) is not str or re.fullmatch(r"\d{8}", value) is None: return False
    try: datetime.strptime(value, "%Y%m%d"); return True
    except ValueError: return False

def _safe_text(value):
    require(type(value) is str and len(value) <= 1024, "STRING_SHAPE_INVALID")
    # Reject embedded/percent-encoded paths and generic credential forms rather
    # than trimming text or relying on a stock name being trustworthy. Capture
    # credentials are separately screened by the pinned raw collector boundary.
    decoded = value
    for _ in range(8):
        if unquote(decoded) == decoded: break
        decoded = unquote(decoded)
    require(unquote(decoded) == decoded, "STRING_ENCODING_DEPTH_INVALID")
    require(not decoded.startswith("/") and not re.search(
        r"file://|/(?:Users|tmp|private|var|home|etc|opt|Volumes)/|(?:^|[=\s(])/[A-Za-z][^\s]*/|"
        r"[A-Za-z]:[\\/]|postgres(?:ql)?://", decoded, re.I),
        "INTERNAL_PATH_IN_ROW")
    require(not re.search(r"\bBearer\s+\S+|\bsk-[A-Za-z0-9_-]{20,}|\bAKIA[A-Z0-9]{16}\b|"
                         r"-----BEGIN|(?:token|password|secret|credential|api[_-]?key)\s*[=:]\s*\S+", decoded, re.I),
            "SECRET_PATTERN_IN_ROW")
    require(re.fullmatch(r"[A-Fa-f0-9]{40,}", decoded) is None, "SECRET_PATTERN_IN_ROW")
    return value

def _number(value):
    require(type(value) in (str, int, Decimal) and type(value) is not bool, "DECIMAL_INVALID")
    try: number = Decimal(value)
    except (InvalidOperation, ValueError): raise DataError("DECIMAL_INVALID") from None
    require(number.is_finite(), "DECIMAL_INVALID")
    require(len(str(value)) <= 160 and abs(number.adjusted()) <= 100, "DECIMAL_RANGE_INVALID")
    return format(number, "f")

def _typed_value(api, field, value, units):
    unit = units.get(field)
    basis = "OFFICIAL_PRODUCT_DOCUMENTATION_REFERENCE_GATEWAY_UNVERIFIED" if unit is not None else "UNKNOWN_UNVERIFIED"
    if field.endswith("_date"):
        if value is None: return {"kind": "NULL", "value": None, "precision": "DATE_ONLY", "unit_basis": "NOT_APPLICABLE"}
        valid = _date_literal(value)
        return {"kind": "DATE" if valid else "INVALID_DATE_LITERAL", "value": _safe_text(value) if type(value) is str else _number(value),
                "precision": "DATE_ONLY", "unit_basis": "NOT_APPLICABLE"}
    if value is None:
        result = {"kind": "NULL", "value": None, "unit_basis": basis}
    elif unit is not None or type(value) is Decimal:
        result = {"kind": "DECIMAL_STRING", "value": _number(value), "unit_basis": basis}
    elif type(value) is int:
        result = {"kind": "INTEGER_STRING", "value": str(value), "unit_basis": basis}
    elif type(value) is str:
        result = {"kind": "STRING", "value": _safe_text(value), "unit_basis": basis}
    else: raise DataError("CELL_TYPE_INVALID")
    if unit is not None: result["unit"] = unit
    return result

def _normalize_request(request, raw, report, *, fixture):
    require(request.get("namespace", "CORE_40") == "CORE_40" and report.get("namespace") == "CORE_40", "NAMESPACE_CROSSOVER")
    require(request["api_name"] in {"stock_basic", "suspend_d", "trade_cal", "daily", "adj_factor", "dividend", "fina_indicator", "index_member_all"}, "API_SCOPE_INVALID")
    require(tuple(request["fields"]) == FIELDS[request["api_name"]], "REQUEST_FIELDS_INVALID")
    require(request["scope"] in ("SMOKE", "COVERAGE"), "SCOPE_INVALID")
    if request["api_name"] == "daily":
        require(request["price_adjustment"] == "RAW_UNADJUSTED_OHLC_PROVIDER_PRE_CLOSE_EX_RIGHTS", "RAW_ADJUSTED_CONTAMINATION")
    if request["api_name"] == "adj_factor":
        require(request["price_adjustment"] == "FACTOR_ONLY_NO_ADJUSTED_PRICES", "RAW_ADJUSTED_CONTAMINATION")
    symbol = request["params"].get("ts_code")
    require(symbol is None and request["api_name"] == "trade_cal" or symbol in SYMBOLS, "SYMBOL_SCOPE_INVALID")
    end = _validate_request_clocks(request, report)
    require(type(raw) is bytes and sha(raw) == request["raw_sha256"], "RAW_MUTATED")
    try:
        doc = json.loads(raw, parse_float=Decimal, parse_constant=lambda _: (_ for _ in ()).throw(DataError("DECIMAL_INVALID")))
    except (ValueError, UnicodeDecodeError): raise DataError("RAW_JSON_INVALID") from None
    require(type(doc) is dict and type(doc.get("code")) is int and doc["code"] == 0 and type(doc.get("data")) is dict, "API_RESPONSE_INVALID")
    fields, vectors = doc["data"].get("fields"), doc["data"].get("items")
    require(type(fields) is list and type(vectors) is list and all(type(field) is str for field in fields) and len(fields) == len(set(fields)), "TABLE_SHAPE_INVALID")
    require(set(fields) == set(request["fields"]) or fields == [] and vectors == [], "SCHEMA_MISMATCH")
    require(len(vectors) <= request["max_rows"], "ROW_CAP_EXCEEDED")
    rows = []
    for ordinal, vector in enumerate(vectors):
        require(type(vector) is list and len(vector) == len(fields), "ROW_SHAPE_INVALID")
        source = dict(zip(fields, vector))
        require(source.get("ts_code") == symbol if symbol else source.get("exchange") == "SSE", "SYMBOL_CROSSOVER")
        typed = {field: _typed_value(request["api_name"], field, source[field], request["units"]) for field in fields}
        reasons = ["INVALID_DATE_LITERAL:" + field for field, value in typed.items() if value["kind"] == "INVALID_DATE_LITERAL"]
        for field in ("ann_date", "f_ann_date", "imp_ann_date"):
            item = typed.get(field)
            if item and item["kind"] == "DATE" and item["value"] > end.astimezone(timezone(timedelta(hours=8))).strftime("%Y%m%d"):
                reasons.append("FUTURE_PUBLICATION_DATE:" + field)
        rows.append({"row_ordinal": ordinal, "state": "QUARANTINED", "fixture": fixture, "typed_fields": typed,
                     "normalization_reasons": reasons, "response_blocked": request["dq_status"] == "BLOCKED"})
    return {"request_id": request["request_id"], "request_fingerprint": request["request_fingerprint"], "api_name": request["api_name"],
        "scope": request["scope"], "ts_code": symbol, "category": request["category"], "params": dict(request["params"]),
        "row_count": len(rows), "units": dict(request["units"]), "reference_unit_basis": "OFFICIAL_PRODUCT_REFERENCE_GATEWAY_UNVERIFIED",
        "namespace": "CORE_40", "state": "QUARANTINED", "fixture": fixture,
        "raw_sha256": request["raw_sha256"], "report_sha256": report["_report_sha256"], "date_scope": request["date_scope"],
        "request_started_at": request["request_started_at"], "response_completed_at": request["response_completed_at"],
        "retrieved_at": request["retrieved_at"], "available_at": request["available_at"], "available_at_basis": "FIRST_OBSERVED_BY_THIS_COLLECTOR",
        "published_at": None, "historical_visibility_proven": False, "source_admission": "BLOCKED", "price_adjustment": request["price_adjustment"],
        "response_dq": request["dq_status"], "response_dq_reasons": request.get("dq_reasons", []), "rows": rows}

def normalize_fixture_request(request, raw, report):
    """Pure injection seam, always labeled SYNTHETIC; cannot register real data."""
    copied = dict(report)
    copied["_report_sha256"] = sha(canonical(report))
    normalized = _normalize_request(request, raw, copied, fixture=True)
    return fixture_dataset([normalized])

def fixture_dataset(requests):
    require(type(requests) is list and all(r.get("fixture") is True for r in requests), "FIXTURE_LABEL_REQUIRED")
    return {"version": VERSION, "provenance": "SYNTHETIC", "fixture": True, "state": "QUARANTINED", "namespace": "CORE_40",
            "source_admission": "BLOCKED", "historical_visibility_proven": False, "productionGate": False, "requests": requests,
            "source_pins": [], "reference_comparison": None}

def validate_dataset(dataset):
    require(type(dataset) is dict and dataset.get("version") == VERSION, "DATASET_SHAPE_INVALID")
    require(dataset.get("state") == "QUARANTINED" and dataset.get("namespace") == "CORE_40" and dataset.get("source_admission") == "BLOCKED"
        and dataset.get("historical_visibility_proven") is False and dataset.get("productionGate") is False, "DATASET_AUTHORITY_ESCALATION")
    fixture = dataset.get("fixture")
    require(type(fixture) is bool, "FIXTURE_LABEL_INVALID")
    if not fixture:
        entry = _REAL_DATASETS.get(id(dataset))
        require(entry is not None and entry[0] is dataset and entry[1] == canonical(dataset), "REAL_DATASET_UNREGISTERED_OR_MUTATED")
    else: require(dataset.get("provenance") == "SYNTHETIC", "FIXTURE_PROVENANCE_INVALID")
    for request in dataset["requests"]:
        require(request["fixture"] is fixture and request["state"] == "QUARANTINED" and request["namespace"] == "CORE_40"
            and request["source_admission"] == "BLOCKED" and request["historical_visibility_proven"] is False, "REQUEST_AUTHORITY_ESCALATION")
        require(all(row["state"] == "QUARANTINED" and row["fixture"] is fixture for row in request["rows"]), "ROW_AUTHORITY_ESCALATION")
    return dataset

def load_verified_dataset():
    """No caller roots/clocks: only two frozen G2 reports and their exact bytes."""
    gate = json.loads(_pinned_local("docs/p1b-real-admission/Gate.json", INPUT_PINS["docs/p1b-real-admission/Gate.json"]))
    require(gate["REAL_DATA_ADMISSION_GATE"] == "BLOCKED" and gate["historical_visibility_proven"] is False and gate["productionGate"] is False, "GATE_AUTHORITY_ESCALATION")
    verifier, provenance = _load_verifier()
    requests = []
    require(len(gate["probe_report_refs"]) == 2, "REPORT_INVENTORY_INVALID")
    for ref in gate["probe_report_refs"]:
        bytes_report = verifier.read_file(ref["path"])
        require(sha(bytes_report) == ref["sha256"], "REPORT_MUTATED")
        try: report, _ = verifier.verify_report(ref["path"])
        except Exception: raise DataError("FROZEN_G2_VERIFICATION_FAILED") from None
        report["_report_sha256"] = ref["sha256"]
        for request in report["requests"]:
            requests.append(_normalize_request(request, verifier.read_file(request["raw_ref"]), report, fixture=False))
    require(len(requests) == 44 and sum(len(r["rows"]) for r in requests) == 2786, "G2_INVENTORY_INVALID")
    comparison = json.loads(_pinned_local("docs/p1b-real-admission/cross-source-comparison.json", INPUT_PINS["docs/p1b-real-admission/cross-source-comparison.json"]))
    dataset = {"version": VERSION, "provenance": "PINNED_G2_CAPTURE_DERIVED", "fixture": False, "state": "QUARANTINED", "namespace": "CORE_40",
        "source_admission": "BLOCKED", "historical_visibility_proven": False, "productionGate": False,
        "provider_id": "TUSHARE_MONTHLY_GATEWAY", "source_classification": "OWNER_PROVIDED_MONTHLY_GATEWAY", "gateway_units_verified": False,
        "source_pins": [{"object": name, "sha256": value} for name, value in INPUT_PINS.items()] + [{"object": p["path"], "sha256": p["sha256"]} for p in provenance["files"]],
        "normalizer_code_hash": sha(Path(__file__).read_bytes()), "requests": requests,
        "reference_comparison": {"reference_sha256": comparison["source_evidence"]["sha256"],
            "calendar_reference_facts": [{"date": r["date"].replace("-", ""), "official_expected_is_open": r["official_expected_is_open"]} for r in comparison["calendar_comparisons"]],
            "security_reference_facts": [{"official_reference_symbol": r["official_reference_symbol"], "gateway_ts_code": r["gateway_ts_code"]} for r in comparison["security_code_reference_comparisons"]],
            "numerical_bar_action_second_source": "NOT_AVAILABLE_NOT_COMPARABLE"}}
    _REAL_DATASETS[id(dataset)] = (dataset, canonical(dataset))
    return validate_dataset(dataset)
