"""Bounded SDK-compatible diagnostic; never grants source or execution authority.

No SDK dependency, saved token fallback, raw data persistence or automatic retries.
Wire numbers are parsed as Decimal. Reports retain metadata only while provider
retention permission is unknown; response hashes alone are not replayable evidence.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable

VERSION = "1.0.0"
BASE_URL = "http://118.89.117.77:8030/"
PROVIDER_ID = "TUSHARE_MONTHLY_GATEWAY"
SYMBOLS = ("603993.SH", "600312.SH", "603228.SH")
ENV_NAME = "TUSHARE_PROXY_TOKEN"
ARCHIVE_ROOT = Path("/Users/qiushi/投资研究/.p1b-archives/tushare-admission-20261005/data")
MAX_BYTES = 2 * 1024 * 1024
MAX_REQUESTS = 34
MIN_INTERVAL_SECONDS = 3.0  # local probe budget, not an asserted account entitlement
GATES = {key: "BLOCKED" for key in (
    "LOCAL_REAL_RESEARCH_GATE", "CLOUD_RESEARCH_EXPORT_GATE", "HISTORICAL_BACKTEST_GATE",
    "PRODUCTION_DATA_GATE", "REDISTRIBUTION", "CLOUD_MODEL", "RESEARCH_PILOT",
    "SIGNAL_ORDER", "BROKER_PRODUCTION")}


class ProbeError(Exception):
    """Only controlled reason codes cross the diagnostic boundary."""


class Credential:
    __slots__ = ("_value",)

    def __init__(self, value: str):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{12,512}", value):
            raise ProbeError("CREDENTIAL_FORMAT_INVALID")
        self._value = value

    def __repr__(self):
        return "Credential(<REDACTED>)"

    def __str__(self):
        return "<REDACTED>"

    def _wire_value(self):
        return self._value

    def body_contains_secret(self, body: bytes):
        # Any response echo containing the credential is discarded, including its hash.
        try:
            return self.text_contains_secret(body.decode("utf-8"))
        except UnicodeDecodeError:
            return self._value.encode("utf-8") in body

    def text_contains_secret(self, text):
        value = self._value.encode("utf-8")
        representations = (self._value, base64.b64encode(value).decode("ascii"),
                           base64.urlsafe_b64encode(value).decode("ascii"))
        for _ in range(9):  # initial layer + up to eight decoded layers, final checked
            if any(item in text or item.rstrip("=") in text for item in representations):
                return True
            if value.hex() in text.lower():
                return True
            decoded = urllib.parse.unquote(text)
            if decoded == text:
                return False
            text = decoded
        # Unresolved encoding is conservatively discarded, never hashed as evidence.
        # The finite budget prevents nested encoding from causing unbounded work.
        return True

    def object_contains_secret(self, obj):
        if isinstance(obj, str):
            return self.text_contains_secret(obj)
        if isinstance(obj, dict):
            return any(self.object_contains_secret(key) or self.object_contains_secret(value)
                       for key, value in obj.items())
        if isinstance(obj, list):
            return any(self.object_contains_secret(value) for value in obj)
        return False


def lookup_credential(*, environ=None, keychain_service=None, keychain_account=None,
                      keychain_runner=None):
    """Latest owner transport/rotation gate precedes *any* secret storage lookup.

    Supplier HTTPS endpoint evidence and a newly rotated credential reference have
    not been supplied. HTTP-only declaration + explicit owner exception also absent.
    No caller-provided assertion can turn this preparation artifact into authority.
    """
    return None, {"secret_presence": None,
                  "credential_lookup_result": "NOT_ATTEMPTED_TRANSPORT_GATE_UNVERIFIED",
                  "credential_storage": "NOT_ACCESSED"}


def _read_synthetic_named_storage(*, environ, keychain_service=None, keychain_account=None,
                        keychain_runner=None):
    """Only a named environment variable or an explicitly named Keychain item.

    No .env sourcing, password CSV, file scan, chat/session lookup or registry fallback.
    Service/account strings are never copied into the report.
    """
    if type(environ) is not dict:
        raise ProbeError("SYNTHETIC_STORAGE_MAPPING_REQUIRED")
    env = environ
    if keychain_service is not None or keychain_account is not None:
        if not all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_.:@/ -]{1,160}", x)
                   for x in (keychain_service, keychain_account)):
            return None, {"secret_presence": False, "credential_lookup_result": "INVALID_KEYCHAIN_REFERENCE",
                          "credential_storage": "EXPLICIT_KEYCHAIN"}
        try:
            item = keychain_runner(
                ["/usr/bin/security", "find-generic-password", "-s", keychain_service,
                 "-a", keychain_account, "-w"], capture_output=True, timeout=10, check=False,
            )
            if item.returncode != 0:
                return None, {"secret_presence": False, "credential_lookup_result": "KEYCHAIN_LOOKUP_FAILED",
                              "credential_storage": "EXPLICIT_KEYCHAIN"}
            value = item.stdout.decode("utf-8").strip()
        except Exception:
            return None, {"secret_presence": False, "credential_lookup_result": "KEYCHAIN_LOOKUP_FAILED",
                          "credential_storage": "EXPLICIT_KEYCHAIN"}
        store = "EXPLICIT_KEYCHAIN"
    else:
        value = env.get(ENV_NAME)
        store = "NAMED_ENVIRONMENT"
    if not value:
        return None, {"secret_presence": False, "credential_lookup_result": "CREDENTIAL_REFERENCE_MISSING",
                      "credential_storage": store}
    try:
        credential = Credential(value)
    except ProbeError:
        return None, {"secret_presence": False, "credential_lookup_result": "CREDENTIAL_FORMAT_INVALID",
                      "credential_storage": store}
    return credential, {"secret_presence": True, "credential_lookup_result": "FOUND",
                        "credential_storage": store}


@dataclass(frozen=True)
class RequestSpec:
    id: str
    category: str
    api_name: str
    params: tuple[tuple[str, str], ...]
    fields: tuple[str, ...]
    max_rows: int
    date_key: str | None
    date_start: str | None
    date_end: str | None
    documentation_url: str
    units: tuple[tuple[str, str], ...]
    adjustment_state: str
    update_rule: str

    def public(self):
        return {"request_id": self.id, "category": self.category, "actual_api_product": self.api_name,
                "request_scope": dict(self.params), "requested_fields": list(self.fields),
                "response_row_cap": self.max_rows, "date_scope": {
                    "key": self.date_key, "start": self.date_start, "end": self.date_end},
                "documentation_url": self.documentation_url, "units": dict(self.units),
                "adjustment_state": self.adjustment_state, "update_rule": self.update_rule,
                "update_rule_authority": "OFFICIAL_API_DOCUMENTATION_NOT_PROXY_VERIFIED"}


def build_plan():
    """One calendar + 11 APIs x three stock identities = 34 finite requests."""
    specs = [RequestSpec(
        "trade_cal-SSE", "EXCHANGE_CALENDAR", "trade_cal",
        (("exchange", "SSE"), ("start_date", "20260928"), ("end_date", "20261009")),
        ("exchange", "cal_date", "is_open", "pretrade_date"), 12,
        "cal_date", "20260928", "20261009", "https://tushare.pro/document/2?doc_id=26",
        (("is_open", "ENUM_0_CLOSED_1_OPEN"),), "NOT_APPLICABLE", "UNSET_REQUIRED")]
    definitions = (
        ("stock_basic", "SECURITY_BASIC_STATUS", 25, ("ts_code", "symbol", "name", "exchange", "curr_type", "list_status", "list_date", "delist_date"),
         (), 1, None, None, None, (), "NOT_APPLICABLE", "UNSET_REQUIRED"),
        ("stock_st", "SECURITY_BASIC_STATUS", 397, ("ts_code", "trade_date", "type", "type_name"),
         (("start_date", "20260928"), ("end_date", "20260930")), 16, "trade_date", "20260928", "20260930", (), "NOT_APPLICABLE", "DAILY_0920_ASIA_SHANGHAI"),
        ("suspend_d", "SECURITY_BASIC_STATUS", 214, ("ts_code", "trade_date", "suspend_timing", "suspend_type"),
         (("start_date", "20260928"), ("end_date", "20260930")), 16, "trade_date", "20260928", "20260930", (), "NOT_APPLICABLE", "IRREGULAR"),
        ("daily", "RAW_DAILY_BARS", 27, ("ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"),
         (("start_date", "20260928"), ("end_date", "20260930")), 3, "trade_date", "20260928", "20260930",
         (("open", "PROVIDER_PRICE_CURRENCY_UNVERIFIED"), ("high", "PROVIDER_PRICE_CURRENCY_UNVERIFIED"), ("low", "PROVIDER_PRICE_CURRENCY_UNVERIFIED"), ("close", "PROVIDER_PRICE_CURRENCY_UNVERIFIED"),
          ("pre_close", "PROVIDER_EX_RIGHTS_REFERENCE_PRICE_UNVERIFIED"), ("change", "PROVIDER_PRICE_CURRENCY_UNVERIFIED"), ("pct_chg", "PERCENT"), ("vol", "LOT_HAND_NO_SHARE_CONVERSION"), ("amount", "THOUSAND_YUAN")),
         "RAW_UNADJUSTED_OHLC_PROVIDER_PRE_CLOSE_EX_RIGHTS", "TRADING_DAY_1500_TO_1600_ASIA_SHANGHAI"),
        ("dividend", "CORPORATE_ACTIONS_DIVIDENDS", 103, ("ts_code", "end_date", "ann_date", "div_proc", "stk_div", "stk_bo_rate", "stk_co_rate", "cash_div", "cash_div_tax", "record_date", "ex_date", "pay_date", "imp_ann_date"),
         (("ann_date", "20260930"),), 16, "ann_date", "20260930", "20260930",
         (("stk_div", "SHARES_PER_SHARE"), ("stk_bo_rate", "SHARES_PER_SHARE"), ("stk_co_rate", "SHARES_PER_SHARE"), ("cash_div", "PROVIDER_CURRENCY_PER_SHARE_UNVERIFIED_POST_TAX"), ("cash_div_tax", "PROVIDER_CURRENCY_PER_SHARE_UNVERIFIED_PRE_TAX")),
         "CORPORATE_ACTION_TERMS_NOT_PRICE", "DAILY_2000_TO_2100_ASIA_SHANGHAI"),
        ("adj_factor", "ADJUSTMENT_FACTORS", 28, ("ts_code", "trade_date", "adj_factor"),
         (("start_date", "20260928"), ("end_date", "20260930")), 3, "trade_date", "20260928", "20260930",
         (("adj_factor", "DIMENSIONLESS_FACTOR"),), "FACTOR_ONLY_NO_ADJUSTED_PRICES", "TRADING_DAY_0915_TO_0920_ASIA_SHANGHAI"),
        ("income", "FINANCIALS_INDICATORS", 33, ("ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type", "basic_eps", "total_revenue", "revenue", "n_income", "update_flag"),
         (("period", "20260630"),), 32, "end_date", "20260630", "20260630",
         (("basic_eps", "PROVIDER_CURRENCY_PER_SHARE_UNVERIFIED"), ("total_revenue", "UNSET_REQUIRED"), ("revenue", "UNSET_REQUIRED"), ("n_income", "UNSET_REQUIRED")), "NOT_APPLICABLE", "UNSET_REQUIRED"),
        ("balancesheet", "FINANCIALS_INDICATORS", 36, ("ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type", "total_share", "total_assets", "total_liab", "total_hldr_eqy_exc_min_int", "update_flag"),
         (("period", "20260630"),), 32, "end_date", "20260630", "20260630",
         (("total_share", "SHARES"), ("total_assets", "UNSET_REQUIRED"), ("total_liab", "UNSET_REQUIRED"), ("total_hldr_eqy_exc_min_int", "UNSET_REQUIRED")), "NOT_APPLICABLE", "UNSET_REQUIRED"),
        ("cashflow", "FINANCIALS_INDICATORS", 44, ("ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type", "net_profit", "n_cashflow_act", "n_cashflow_inv_act", "n_cash_flows_fnc_act", "update_flag"),
         (("period", "20260630"),), 32, "end_date", "20260630", "20260630",
         (("net_profit", "UNSET_REQUIRED"), ("n_cashflow_act", "UNSET_REQUIRED"), ("n_cashflow_inv_act", "UNSET_REQUIRED"), ("n_cash_flows_fnc_act", "UNSET_REQUIRED")), "NOT_APPLICABLE", "UNSET_REQUIRED"),
        ("fina_indicator", "FINANCIALS_INDICATORS", 79, ("ts_code", "ann_date", "end_date", "eps", "roe", "debt_to_assets", "netprofit_yoy", "update_flag"),
         (("period", "20260630"),), 32, "end_date", "20260630", "20260630",
         (("eps", "PROVIDER_CURRENCY_PER_SHARE_UNVERIFIED"), ("roe", "PROVIDER_RATIO_SCALE_UNVERIFIED"), ("debt_to_assets", "PROVIDER_RATIO_SCALE_UNVERIFIED"), ("netprofit_yoy", "PERCENT")), "NOT_APPLICABLE", "UNSET_REQUIRED"),
        ("index_member_all", "INDUSTRY_CLASSIFICATION", 335, ("ts_code", "l1_code", "l1_name", "l2_code", "l2_name", "l3_code", "l3_name", "in_date", "out_date", "is_new"),
         (("is_new", "Y"),), 16, None, None, None, (), "NOT_APPLICABLE", "UNSET_REQUIRED"),
    )
    for symbol in SYMBOLS:
        for api, category, doc, fields, params, cap, dk, ds, de, units, adjustment, update in definitions:
            specs.append(RequestSpec(f"{api}-{symbol}", category, api,
                         (("ts_code", symbol),) + params, fields, cap, dk, ds, de,
                         f"https://tushare.pro/document/2?doc_id={doc}", units, adjustment, update))
    return tuple(specs)


def validate_plan(plan):
    canonical = {s.id: s for s in build_plan()}
    if type(plan) not in (list, tuple) or len(plan) > MAX_REQUESTS:
        raise ProbeError("REQUEST_BUDGET_EXCEEDED")
    seen = set()
    for spec in plan:
        if type(spec) is not RequestSpec:
            raise ProbeError("UNAPPROVED_REQUEST_SCOPE")
        strings = (spec.id, spec.category, spec.api_name, spec.documentation_url,
                   spec.adjustment_state, spec.update_rule)
        if (any(type(item) is not str for item in strings)
            or any(item is not None and type(item) is not str
                   for item in (spec.date_key, spec.date_start, spec.date_end))
            or type(spec.max_rows) is not int or type(spec.fields) is not tuple
            or any(type(item) is not str for item in spec.fields)
            or any(type(items) is not tuple or any(type(pair) is not tuple or len(pair) != 2
                   or any(type(item) is not str for item in pair) for pair in items)
                   for items in (spec.params, spec.units))
            or canonical.get(spec.id) != spec):
            raise ProbeError("UNAPPROVED_REQUEST_SCOPE")
        if spec.id in seen:
            raise ProbeError("DUPLICATE_REQUEST")
        seen.add(spec.id)
    return tuple(canonical[spec.id] for spec in plan)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProbeError("AUTH_REDIRECT_BLOCKED")


def make_transport():
    # Latest owner instruction blocks HTTP and requires supplier-provided HTTPS
    # evidence or a subsequent explicit limited HTTP exception. Neither exists.
    raise ProbeError("TRANSPORT_GATE_UNVERIFIED")



def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProbeError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse_response(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ProbeError("RESPONSE_SIZE_EXCEEDED")
    try:
        return json.loads(raw.decode("utf-8"), parse_float=Decimal,
                          parse_constant=lambda value: (_ for _ in ()).throw(ProbeError("NON_FINITE_NUMBER")),
                          object_pairs_hook=_object_pairs)
    except ProbeError:
        raise
    except Exception:
        raise ProbeError("RESPONSE_JSON_INVALID") from None


def decimal_text(value):
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, int, str)):
        raise ProbeError("DECIMAL_TYPE_INVALID")
    if isinstance(value, str) and not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", value):
        raise ProbeError("DECIMAL_TEXT_INVALID")
    try:
        number = Decimal(value)
    except Exception:
        raise ProbeError("DECIMAL_TEXT_INVALID") from None
    if not number.is_finite():
        raise ProbeError("NON_FINITE_NUMBER")
    # No normalization/quantization may round a provider value. Excess precision stays rejected.
    if len(number.as_tuple().digits) > 100 or abs(number.as_tuple().exponent) > 100:
        raise ProbeError("DECIMAL_PRECISION_EXCEEDED")
    return format(number, "f")


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{8}", value):
        raise ProbeError("DATE_INVALID")
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        raise ProbeError("DATE_INVALID") from None
    return value


def _validate_clock(value):
    """Diagnostic clocks are explicit UTC instants, never naive/date-only strings."""
    if (type(value) is not str or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z", value)):
        raise ProbeError("CLOCK_INVALID")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        raise ProbeError("CLOCK_INVALID") from None


def _read_clock(clock):
    try:
        value = clock()
    except Exception:
        raise ProbeError("CLOCK_INVALID") from None
    _validate_clock(value)
    return value


def summarize_response(spec, raw, *, credential=None, retrieved_at=None):
    """Extract field metadata/counts only; never emits raw rows or provider messages."""
    validate_plan((spec,))
    capture_clock = _validate_clock(retrieved_at) if retrieved_at is not None else None
    if credential is not None and type(credential) is not Credential:
        raise ProbeError("CREDENTIAL_TYPE_INVALID")
    if credential is not None and Credential.body_contains_secret(credential, raw):
        raise ProbeError("CREDENTIAL_ECHO_RESPONSE_DISCARDED")
    doc = parse_response(raw)
    if credential is not None and Credential.object_contains_secret(credential, doc):
        raise ProbeError("CREDENTIAL_ECHO_RESPONSE_DISCARDED")
    if not isinstance(doc, dict) or type(doc.get("code")) is not int:
        raise ProbeError("RESPONSE_CODE_INVALID")
    api_code = doc["code"]
    if api_code != 0:
        # Classify fixed signals only; arbitrary provider text is never copied.
        message = doc.get("msg")
        lower = message.lower() if isinstance(message, str) else ""
        if (re.search(r"(?:token|credential).{0,20}(?:invalid|expired|无效|错误|过期|不正确|失效)", lower)
                or re.search(r"(?:invalid|expired).{0,20}(?:token|credential)", lower)
                or any(word in lower for word in ("认证失败", "authentication failed"))):
            status, reason = "AUTHENTICATION_FAILED", "API_AUTHENTICATION_FAILED_OBSERVED"
        elif any(word in lower for word in ("频次超", "次数超", "超过频", "限流", "rate limit", "frequency exceeded")):
            status, reason = "RATE_LIMITED", "API_RATE_LIMIT_OBSERVED"
        elif any(word in lower for word in ("没有权限", "无权限", "权限不足", "没有访问", "积分不足",
                  "permission denied", "permission not granted", "entitlement not granted", "insufficient points")):
            status, reason = "ENTITLEMENT_NOT_GRANTED", "API_ACCESS_DENIED_OBSERVED"
        else:
            status, reason = "API_ERROR", "API_ERROR_OBSERVED"
        return {"status": status, "reason_code": reason, "api_code": api_code,
                "row_count": None, "response_schema": None, "source_response_hash": None,
                "entitlement_evidence": "DENIAL_RESPONSE_ONLY_NOT_LICENSE_PROOF"}
    data = doc.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("fields"), list) or not isinstance(data.get("items"), list):
        raise ProbeError("RESPONSE_TABLE_INVALID")
    fields, rows = data["fields"], data["items"]
    if len(fields) != len(set(fields)) or any(not isinstance(x, str) or x not in spec.fields for x in fields):
        raise ProbeError("RESPONSE_FIELDS_UNAPPROVED")
    # Response projection must be exact. Missing critical fields cannot certify scope/version.
    if set(fields) != set(spec.fields) and not (not rows and not fields):
        raise ProbeError("RESPONSE_FIELDS_MISSING")
    if len(rows) > spec.max_rows:
        raise ProbeError("RESPONSE_ROW_CAP_EXCEEDED")
    date_values, publication_dates, update_flags, report_types = set(), set(), set(), set()
    schema_types = {name: set() for name in fields}
    numeric = dict(spec.units)
    for values in rows:
        if not isinstance(values, list) or len(values) != len(fields):
            raise ProbeError("RESPONSE_ROW_SHAPE_INVALID")
        row = dict(zip(fields, values))
        params = dict(spec.params)
        if "ts_code" in params and row.get("ts_code") != params["ts_code"]:
            raise ProbeError("RESPONSE_SYMBOL_OUTSIDE_SCOPE")
        if spec.api_name == "trade_cal" and row.get("exchange") != "SSE":
            raise ProbeError("RESPONSE_EXCHANGE_OUTSIDE_SCOPE")
        if spec.date_key:
            date = _date(row[spec.date_key])
            if not (spec.date_start <= date <= spec.date_end):
                raise ProbeError("RESPONSE_DATE_OUTSIDE_SCOPE")
            date_values.add(date)
        if spec.api_name == "index_member_all" and row["is_new"] != "Y":
            raise ProbeError("RESPONSE_MEMBERSHIP_OUTSIDE_SCOPE")
        if spec.api_name == "trade_cal" and str(row["is_open"]) not in ("0", "1"):
            raise ProbeError("RESPONSE_CALENDAR_STATE_INVALID")
        for name, value in row.items():
            if value is None:
                schema_types[name].add("NULL")
                continue
            if name in numeric:
                decimal_text(value)
                schema_types[name].add("DECIMAL_STRING_LOSSLESS_IN_MEMORY")
            elif isinstance(value, str):
                schema_types[name].add("STRING")
            elif type(value) is int:
                schema_types[name].add("INTEGER")
            else:
                raise ProbeError("RESPONSE_CELL_TYPE_INVALID")
            if name in ("ann_date", "f_ann_date"):
                published_date = _date(value)
                if retrieved_at is not None:
                    current_date = capture_clock.astimezone(
                        timezone(timedelta(hours=8))).strftime("%Y%m%d")
                    if published_date > current_date:
                        raise ProbeError("FUTURE_PUBLICATION_DATE")
                publication_dates.add(published_date)
            elif name.endswith("_date"):
                _date(value)
            if name == "update_flag":
                flag = str(value)
                if flag not in ("0", "1"):
                    raise ProbeError("REVISION_FLAG_UNRECOGNIZED")
                update_flags.add(flag)
            if name == "report_type":
                rt = str(value)
                if rt not in tuple(str(x) for x in range(1, 13)):
                    raise ProbeError("REPORT_TYPE_UNRECOGNIZED")
                report_types.add(rt)
    return {"status": "TECHNICAL_ACCESS_OBSERVED" if rows else "EMPTY_RESPONSE_NOT_COVERAGE",
            "reason_code": "API_SUCCESS_NOT_ENTITLEMENT_OR_LICENSE" if rows else "API_EMPTY_SUCCESS_NO_ROWS_PROVEN",
            "api_code": 0, "row_count": len(rows),
            "response_schema": [{"field": name, "observed_types": sorted(schema_types[name])} for name in fields],
            "source_response_hash": "sha256:" + hashlib.sha256(raw).hexdigest(),
            "source_version": "UNSET_REQUIRED", "source_version_evidence": {
                "update_flag_values": sorted(update_flags), "report_type_values": sorted(report_types),
                "immutable_provider_revision_id": None, "revision_history_proven": False},
            "event_dates": sorted(date_values), "published_dates": sorted(publication_dates),
            "publication_precision": "DATE_ONLY" if publication_dates else "UNKNOWN",
            "entitlement_evidence": "TECHNICAL_ACCESS_ONLY_NOT_ACCOUNT_PRODUCT_LICENSE"}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def run_probe(*, plan=None, credential=None, lookup_result=None, transport=None,
              monotonic=time.monotonic, sleeper=time.sleep, clock=utc_now):
    """Public entry is preparation only while transport and rotation are unverified."""
    report = _run_diagnostic(plan=plan, credential=None, lookup_result={
        "secret_presence": False, "credential_lookup_result": "CREDENTIAL_REFERENCE_MISSING",
        "credential_storage": "NAMED_ENVIRONMENT"}, clock=utc_now)
    report["credential_lookup"] = {"secret_presence": None,
        "credential_lookup_result": "NOT_ATTEMPTED_TRANSPORT_GATE_UNVERIFIED",
        "credential_storage": "NOT_ACCESSED"}
    report["provider_id"] = PROVIDER_ID
    report["transport_gate"] = "BLOCKED_FORMAL_HTTPS_ENDPOINT_EVIDENCE_MISSING"
    report["credential_rotation_gate"] = "NEW_CREDENTIAL_REQUIRED"
    report["supplier_https_endpoint"] = None
    report["supplier_http_only_declaration"] = None
    report["owner_limited_http_exception"] = None
    report["old_credential_use"] = "PROHIBITED"
    report["status"] = "BLOCKED_TRANSPORT_AND_NEW_CREDENTIAL_REQUIRED"
    report["canonical_transport"] = "SDK_COMPATIBLE_HTTP_WIRE_NOT_ENABLED"
    report["mcp_role"] = "DISCOVERY_SMOKE_ONLY_AFTER_CANONICAL_SDK_COMPLETE"
    phase_a = {"SECURITY_BASIC_STATUS", "EXCHANGE_CALENDAR", "RAW_DAILY_BARS", "ADJUSTMENT_FACTORS"}
    for item in report["requests"]:
        item["phase"] = "A" if item["category"] in phase_a else "B"
        item["reason_code"] = "TRANSPORT_GATE_UNVERIFIED" if item["phase"] == "A" else "PHASE_A_NOT_PASSED"
    report["phase_execution"] = {"A": "BLOCKED_TRANSPORT_AND_ROTATION", "B": "BLOCKED_PHASE_A_NOT_PASSED"}
    report["coverage_expansion"] = "REQUIRES_NEW_OWNER_PROPOSAL_AND_APPROVAL"
    _sealed_reports[id(report)] = (report, _serialize_report(report))
    return report


def run_synthetic_probe(*, plan=None, credential=None, lookup_result=None, transport,
                        monotonic=time.monotonic, sleeper=time.sleep, clock=utc_now):
    """Explicit offline test seam, never creates the real transport or real evidence."""
    report = _run_diagnostic(plan=plan, credential=credential, lookup_result=lookup_result,
                            transport=transport, monotonic=monotonic, sleeper=sleeper, clock=clock)
    report["fixture"] = True
    report["report_kind"] = "SYNTHETIC_DIAGNOSTIC_NOT_ADMISSION"
    report["mock_transport_attempts"] = report["network_requests"]
    report["network_requests"] = 0
    _sealed_reports[id(report)] = (report, _serialize_report(report))
    return report


def _run_diagnostic(*, plan=None, credential=None, lookup_result=None, transport=None,
                    monotonic=time.monotonic, sleeper=time.sleep, clock=utc_now):
    specs = validate_plan(build_plan() if plan is None else plan)
    if credential is not None and type(credential) is not Credential:
        raise ProbeError("CREDENTIAL_TYPE_INVALID")
    # Fixed keys prevent caller-supplied credential metadata becoming an exfiltration path.
    lookup_result = lookup_result or {"secret_presence": credential is not None,
                                      "credential_lookup_result": "FOUND" if credential else "CREDENTIAL_REFERENCE_MISSING",
                                      "credential_storage": "NAMED_ENVIRONMENT"}
    if (set(lookup_result) != {"secret_presence", "credential_lookup_result", "credential_storage"}
            or type(lookup_result["secret_presence"]) is not bool
            or lookup_result["secret_presence"] != (credential is not None)
            or lookup_result["credential_lookup_result"] not in (
                "FOUND", "CREDENTIAL_REFERENCE_MISSING", "CREDENTIAL_FORMAT_INVALID",
                "INVALID_KEYCHAIN_REFERENCE", "KEYCHAIN_LOOKUP_FAILED")
            or lookup_result["credential_storage"] not in ("NAMED_ENVIRONMENT", "EXPLICIT_KEYCHAIN")):
        raise ProbeError("CREDENTIAL_METADATA_INVALID")
    report = {"version": VERSION, "report_kind": "BOUNDED_DIAGNOSTIC_NOT_ADMISSION",
              "fixture": False, "generated_at": _read_clock(clock), "actual_account_tier": 15000,
              "account_tier_evidence": "OWNER_ASSERTION_NOT_PROVIDER_ACCOUNT_VERIFIED",
              "purchased_product": "MONTHLY_CARD_OWNER_ASSERTED",
              "purchased_product_verified": False, "expiration": "UNSET_REQUIRED",
              "credential_lookup": dict(lookup_result), "source": "USER_PROVIDED_THIRD_PARTY_COMPATIBLE_ENDPOINT",
              "endpoint": BASE_URL, "provider_operator_identity": "UNSET_REQUIRED",
              "official_tushare_relationship": "UNSET_REQUIRED", "namespace": "CORE_40",
              "symbols": list(SYMBOLS), "maximum_requests": MAX_REQUESTS,
              "minimum_interval_seconds": MIN_INTERVAL_SECONDS, "network_requests": 0,
              "historical_visibility_proven": False, "raw_persisted": False,
              "retention": "UNSET_REQUIRED", "storage": "METADATA_HASH_ONLY_NO_RAW_OR_ROWS",
              "transfer": "BLOCKED", "local_license": "UNSET_REQUIRED",
              "gate_states": dict(GATES), "admission_objects": {
                  "SourceObservation": None, "ClockEvidence": None, "policy": None,
                  "snapshot": None, "receipt": None}, "admission_lineage_status": "NOT_ISSUED",
              "replayability": "CAPTURE_HASH_ONLY_NOT_REPLAYABLE",
              "requests": [], "skipped": [{"category": "STRUCTURED_ANNOUNCEMENTS", "api_name": "anns_d",
                   "status": "SKIPPED", "reason_code": "INDEPENDENT_ENTITLEMENT_NOT_VERIFIED",
                   "existing_SSE_chain_preserved": True}], "status": "PREPARED"}
    sender = transport
    last_started = None
    for spec in specs:
        result = spec.public()
        result.update({"event_time": None, "published_at": None, "available_at": None,
                       "retrieved_at": None, "timezone": "Asia/Shanghai",
                       "available_at_basis": "NO_CAPTURE_NOT_ASSIGNED",
                       "source_version": "UNSET_REQUIRED", "source_response_hash": None,
                       "row_count": None, "response_schema": None,
                       "entitlement_evidence": "UNSET_REQUIRED", "terms_license_evidence": "UNSET_REQUIRED",
                       "retention": "UNSET_REQUIRED", "storage": "METADATA_HASH_ONLY",
                       "transfer": "BLOCKED", "historical_visibility_proven": False,
                       "lineage": {"SourceObservation": None, "ClockEvidence": None,
                                   "policy": None, "snapshot": None, "receipt": None}})
        if credential is None:
            result.update({"status": "BLOCKED", "reason_code": "CREDENTIAL_REFERENCE_MISSING"})
        else:
            if sender is None:
                sender = make_transport()
            now = monotonic()
            if last_started is not None:
                delay = max(0, MIN_INTERVAL_SECONDS - (now - last_started))
                if delay:
                    sleeper(delay)
                now = monotonic()
                if now - last_started < MIN_INTERVAL_SECONDS:
                    raise ProbeError("LOCAL_RATE_BUDGET_NOT_ENFORCED")
            last_started = now
            report["network_requests"] += 1
            try:
                status, raw = sender(spec, credential)
                if type(status) is not int or status != 200:
                    raise ProbeError("HTTP_UNEXPECTED_STATUS")
                capture_at = _read_clock(clock)  # successful capture completion, never provider dates
                summary = summarize_response(spec, raw, credential=credential, retrieved_at=capture_at)
                result.update(summary)
                result.update({"http_status": status, "retrieved_at": capture_at,
                               "available_at": capture_at, "available_at_basis": "ACTUAL_CURRENT_RETRIEVAL_ONLY"})
            except ProbeError as error:
                reason = str(error)
                # An injected transport cannot copy arbitrary exception text into the report.
                if reason not in SAFE_REASONS:
                    reason = "CONTROLLED_PROBE_ERROR"
                result.update({"status": "BLOCKED", "reason_code": reason})
            except Exception:
                result.update({"status": "BLOCKED", "reason_code": "TRANSPORT_ERROR"})
        report["requests"].append(result)
    report["status"] = "BLOCKED_CREDENTIAL_REFERENCE_MISSING" if credential is None else "DIAGNOSTICS_COMPLETE_ADMISSION_BLOCKED"
    report["categories"] = []
    for category in ("SECURITY_BASIC_STATUS", "EXCHANGE_CALENDAR", "RAW_DAILY_BARS",
                     "CORPORATE_ACTIONS_DIVIDENDS", "ADJUSTMENT_FACTORS", "FINANCIALS_INDICATORS",
                     "INDUSTRY_CLASSIFICATION", "STRUCTURED_ANNOUNCEMENTS"):
        requests = [r for r in report["requests"] if r["category"] == category]
        statuses = sorted({r["status"] for r in requests})
        report["categories"].append({"category": category, "request_ids": [r["request_id"] for r in requests],
            "technical_statuses": statuses if requests else ["SKIPPED"],
            "actual_captured_rows": sum(r["row_count"] or 0 for r in requests),
            "coverage_status": "BLOCKED", "local_license_status": "UNSET_REQUIRED",
            "historical_visibility_proven": False, "admission_lineage_status": "NOT_ISSUED"})
    report["completed_at"] = _read_clock(clock)
    _sealed_reports[id(report)] = (report, _serialize_report(report))
    return report


SAFE_REASONS = frozenset({
    "AUTH_REDIRECT_BLOCKED", "HTTP_AUTH_ACCESS_DENIED", "HTTP_RATE_LIMITED", "HTTP_ERROR",
    "TRANSPORT_ERROR", "RESPONSE_SIZE_EXCEEDED", "HTTP_UNEXPECTED_STATUS",
    "DUPLICATE_JSON_KEY", "NON_FINITE_NUMBER", "RESPONSE_JSON_INVALID", "RESPONSE_CODE_INVALID",
    "RESPONSE_TABLE_INVALID", "RESPONSE_FIELDS_UNAPPROVED", "RESPONSE_FIELDS_MISSING",
    "RESPONSE_ROW_CAP_EXCEEDED", "RESPONSE_ROW_SHAPE_INVALID", "RESPONSE_SYMBOL_OUTSIDE_SCOPE",
    "RESPONSE_EXCHANGE_OUTSIDE_SCOPE", "RESPONSE_DATE_OUTSIDE_SCOPE", "RESPONSE_MEMBERSHIP_OUTSIDE_SCOPE",
    "RESPONSE_CALENDAR_STATE_INVALID", "RESPONSE_CELL_TYPE_INVALID", "DECIMAL_TYPE_INVALID",
    "DECIMAL_TEXT_INVALID", "DECIMAL_PRECISION_EXCEEDED", "DATE_INVALID",
    "REVISION_FLAG_UNRECOGNIZED", "REPORT_TYPE_UNRECOGNIZED", "CREDENTIAL_ECHO_RESPONSE_DISCARDED",
    "FUTURE_PUBLICATION_DATE",
    "CLOCK_INVALID",
})


_sealed_reports = {}


def _serialize_report(report):
    return (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def save_report(report, output):
    # Only unmodified bytes produced by this process may use the persistence boundary.
    # Private registry is a DEV diagnostic guard, not a policy/receipt authentication system.
    entry = _sealed_reports.get(id(report))
    if entry is None or entry[0] is not report:
        raise ProbeError("REPORT_NOT_PRODUCED_BY_RUNNER")
    if _serialize_report(report) != entry[1]:
        raise ProbeError("REPORT_MUTATED_NO_PERSISTENCE")
    output = Path(output)
    resolved = output.resolve()
    if not resolved.is_relative_to(ARCHIVE_ROOT.resolve()) or resolved == ARCHIVE_ROOT.resolve():
        raise ProbeError("OUTPUT_OUTSIDE_APPROVED_ARCHIVE")
    if output.exists() or output.is_symlink():
        raise ProbeError("OUTPUT_EXISTS_NO_OVERWRITE")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive creation and restrictive mode: no historical diagnostic can be replaced.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(entry[1])


def main():
    parser = argparse.ArgumentParser(description="Bounded diagnostic only; no source admission authority.")
    parser.add_argument("--output", required=True, help="New report path under parent-approved external archive")
    parser.add_argument("--keychain-service")
    parser.add_argument("--keychain-account")
    args = parser.parse_args()
    try:
        credential, result = lookup_credential(keychain_service=args.keychain_service,
                                             keychain_account=args.keychain_account)
        report = run_probe(credential=credential, lookup_result=result)
        save_report(report, args.output)
        print(json.dumps({"status": report["status"], "network_requests": report["network_requests"],
                          "report_saved": True, "raw_persisted": False}))
        return 0
    except Exception:
        # Never print a traceback, parser/provider/body/URL/credential-derived diagnostics.
        print(json.dumps({"status": "BLOCKED", "reason_code": "CONTROLLED_RUNNER_FAILURE"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
