"""Bounded diagnostics using captured calendar facts, never a weekday calendar."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from .dataset import DataError, SYMBOLS, VERSION, canonical, require, sha, validate_dataset

def value(row, field):
    return row["typed_fields"].get(field, {}).get("value")

def _decimal(row, field):
    cell = row["typed_fields"].get(field)
    require(cell is not None and cell["kind"] == "DECIMAL_STRING", "NUMERIC_CELL_INVALID")
    try: result = Decimal(cell["value"])
    except (ValueError, InvalidOperation): raise DataError("NUMERIC_CELL_INVALID") from None
    require(result.is_finite(), "NUMERIC_CELL_INVALID")
    return result

def _duplicates(keys):
    return sorted(str(k) for k, n in Counter(keys).items() if n > 1)

def _civil_dates(start, end):
    try:
        begin, finish = (datetime.strptime(x, "%Y%m%d") for x in (start, end))
    except (TypeError, ValueError): raise DataError("CALENDAR_SCOPE_INVALID") from None
    require(begin <= finish and (finish - begin).days <= 600, "CALENDAR_SCOPE_INVALID")
    return {(begin + timedelta(days=i)).strftime("%Y%m%d") for i in range((finish - begin).days + 1)}

def analyze_coverage(dataset):
    """Always QUARANTINED diagnostics; no coverage result can admit a source."""
    validate_dataset(dataset)
    requests = dataset["requests"]
    scopes = sorted({r["scope"] for r in requests})
    selected_scope = "COVERAGE" if "COVERAGE" in scopes else "SMOKE"
    selected = [r for r in requests if r["scope"] == selected_scope]
    calendar_requests = [r for r in selected if r["api_name"] == "trade_cal"]
    require(len(calendar_requests) <= 1, "DUPLICATE_CALENDAR_REQUEST")
    calendar = calendar_requests[0] if calendar_requests else None
    calendar_rows = calendar["rows"] if calendar else []
    calendar_dates = [value(r, "cal_date") for r in calendar_rows]
    invalid_calendar_rows = [r["row_ordinal"] for r in calendar_rows if value(r, "is_open") not in ("0", "1") and value(r, "is_open") not in (0, 1)]
    for row in calendar_rows:
        date, previous = row["typed_fields"].get("cal_date", {}), row["typed_fields"].get("pretrade_date", {})
        if date.get("kind") != "DATE" or previous.get("kind") not in ("DATE", "NULL") or previous.get("kind") == "DATE" and previous["value"] >= date["value"]:
            invalid_calendar_rows.append(row["row_ordinal"])
    invalid_calendar_rows = sorted(set(invalid_calendar_rows))
    calendar_duplicates = _duplicates(calendar_dates)
    calendar_holes = sorted(_civil_dates(calendar["date_scope"]["start"], calendar["date_scope"]["end"]) - set(calendar_dates)) if calendar else []
    open_dates = {value(r, "cal_date") for r in calendar_rows if str(value(r, "is_open")) == "1"}
    calendar_complete = bool(calendar) and not calendar_holes and not calendar_duplicates and not invalid_calendar_rows
    by_symbol = {}
    for symbol in SYMBOLS:
        bar_requests = [r for r in selected if r["api_name"] == "daily" and r["ts_code"] == symbol]
        factor_requests = [r for r in selected if r["api_name"] == "adj_factor" and r["ts_code"] == symbol]
        status_requests = [r for r in selected if r["api_name"] == "stock_basic" and r["ts_code"] == symbol]
        suspension_requests = [r for r in selected if r["api_name"] == "suspend_d" and r["ts_code"] == symbol]
        require(max(len(bar_requests), len(factor_requests), len(status_requests), len(suspension_requests)) <= 1, "DUPLICATE_API_SYMBOL_REQUEST")
        bars = bar_requests[0]["rows"] if bar_requests else []
        factors = factor_requests[0]["rows"] if factor_requests else []
        bar_dates = [value(r, "trade_date") for r in bars]
        factor_dates = [value(r, "trade_date") for r in factors]
        duplicate_dates = _duplicates(bar_dates)
        invalid_bars = []
        for row in bars:
            reasons = []
            if value(row, "ts_code") != symbol: reasons.append("SYMBOL_CROSSOVER")
            try:
                o, h, l, c, p, vol, amount = [_decimal(row, name) for name in ("open", "high", "low", "close", "pre_close", "vol", "amount")]
                if min(o, h, l, c, p) <= 0 or h < max(o, l, c) or l > min(o, h, c): reasons.append("RAW_OHLC_OR_PRECLOSE_INVALID")
                if min(vol, amount) < 0: reasons.append("NEGATIVE_VOLUME_AMOUNT")
            except DataError: reasons.append("REQUIRED_DECIMAL_MISSING_OR_INVALID")
            if reasons: invalid_bars.append({"row_ordinal": row["row_ordinal"], "reasons": reasons})
        statuses = []
        for row in status_requests[0]["rows"] if status_requests else []:
            statuses.append({"ts_code": value(row, "ts_code"), "symbol": value(row, "symbol"), "exchange": value(row, "exchange"),
                             "curr_type": value(row, "curr_type"), "list_status": value(row, "list_status")})
        identity_valid = len(statuses) == 1 and statuses[0]["ts_code"] == symbol and statuses[0]["symbol"] == symbol[:6] and statuses[0]["exchange"] == "SSE" and statuses[0]["curr_type"] == "CNY" and statuses[0]["list_status"] in ("L", "D", "P")
        expected = open_dates if calendar_complete else set()
        missing = sorted(expected - set(bar_dates)) if calendar_complete else None
        outside = sorted(set(bar_dates) - open_dates) if calendar else None
        factor_alignment = bool(bar_requests and factor_requests) and set(bar_dates) == set(factor_dates) and not _duplicates(factor_dates)
        factor_invalid = []
        for row in factors:
            try:
                if _decimal(row, "adj_factor") <= 0: factor_invalid.append(row["row_ordinal"])
            except DataError: factor_invalid.append(row["row_ordinal"])
        suspension_rows = suspension_requests[0]["rows"] if suspension_requests else []
        suspension_state = "EMPTY_RESPONSE_STATUS_UNKNOWN" if suspension_requests and not suspension_rows else "OBSERVED_ROWS_HISTORY_UNPROVEN" if suspension_rows else "NOT_CAPTURED_UNKNOWN"
        discontinuities = []
        ordered = sorted(bars, key=lambda r: value(r, "trade_date") or "")
        if not duplicate_dates and not invalid_bars:
            for previous, current in zip(ordered, ordered[1:]):
                if _decimal(previous, "close") != _decimal(current, "pre_close"):
                    discontinuities.append({"date": value(current, "trade_date"), "previous_date": value(previous, "trade_date"),
                        "previous_raw_close": value(previous, "close"), "provider_pre_close": value(current, "pre_close"),
                        "classification": "REFERENCE_DISCONTINUITY_ACTION_RECONCILIATION_REQUIRED"})
        by_symbol[symbol] = {"bars": len(bars), "unique_bar_dates": len(set(bar_dates)), "factor_rows": len(factors),
            "bar_dates_first": min(bar_dates) if bar_dates else None, "bar_dates_last": max(bar_dates) if bar_dates else None,
            "observed_target_320_met": len(set(bar_dates)) >= 320, "duplicates": duplicate_dates, "invalid_bars": invalid_bars,
            "calendar_missing_bar_sessions": missing, "bars_outside_observed_open_calendar": outside,
            "gap_classification": "UNEXPLAINED_SUSPENSION_STATUS_UNKNOWN" if missing else "NO_GAP_IN_OBSERVED_COMPLETE_CALENDAR" if calendar_complete else "UNKNOWN_CALENDAR_INCOMPLETE",
            "factor_date_alignment": factor_alignment, "factor_duplicate_dates": _duplicates(factor_dates), "factor_invalid_rows": factor_invalid,
            "security_identity_valid_for_observed_row": identity_valid, "security_observations": statuses,
            "security_status_history": "UNPROVEN_CURRENT_ONLY", "suspension_status": suspension_state,
            "empty_suspension_means_no_suspension": False, "pre_close_reference_discontinuities": discontinuities,
            "pre_close_equals_prior_raw_close_required": False,
            "raw_price_adjustment": bar_requests[0]["price_adjustment"] if bar_requests else None,
            "unit_observations": bar_requests[0]["units"] if bar_requests else {}, "gateway_unit_identity_verified": False,
            "admission_status": "BLOCKED", "historical_visibility_proven": False}
    references = dataset.get("reference_comparison")
    comparison = {"state": "NO_REFERENCE_FIXTURE", "calendar": [], "security": [], "numeric_second_source": "NOT_AVAILABLE_NOT_COMPARABLE"}
    if references:
        observed = {}
        for request in requests:
            if request["api_name"] == "trade_cal":
                for row in request["rows"]:
                    observed.setdefault(value(row, "cal_date"), set()).add(str(value(row, "is_open")))
        for fact in references["calendar_reference_facts"]:
            states = sorted(observed.get(fact["date"], set()))
            comparison["calendar"].append({"date": fact["date"], "official_expected_is_open": fact["official_expected_is_open"],
                "captured_gateway_states": states, "match": states == [str(fact["official_expected_is_open"])]})
        for fact in references["security_reference_facts"]:
            symbol = fact["gateway_ts_code"]
            comparison["security"].append({"official_reference_symbol": fact["official_reference_symbol"], "gateway_ts_code": symbol,
                "match": symbol in by_symbol and by_symbol[symbol]["security_identity_valid_for_observed_row"] and fact["official_reference_symbol"] == "SSE:" + symbol[:6]})
        comparison["state"] = "PASS_COMPARED_EXISTING_REFERENCE_FACTS_ONLY" if all(r["match"] for r in comparison["calendar"] + comparison["security"]) else "REFERENCE_MISMATCH"
        comparison["source_reference_sha256"] = references["reference_sha256"]
    failures = not calendar_complete or bool(calendar_holes or calendar_duplicates or invalid_calendar_rows or any(r["duplicates"] or r["invalid_bars"] or r["calendar_missing_bar_sessions"] or r["bars_outside_observed_open_calendar"] or r["factor_invalid_rows"] or not r["factor_date_alignment"] or not r["security_identity_valid_for_observed_row"] for r in by_symbol.values()))
    return {"version": VERSION, "fixture": dataset["fixture"], "state": "QUARANTINED", "namespace": "CORE_40",
        "source_admission": "BLOCKED", "historical_visibility_proven": False, "productionGate": False,
        "dataset_sha256": sha(canonical(dataset)), "coverage_code_hash": sha(Path(__file__).read_bytes()), "scope": selected_scope,
        "diagnostic_result": "GAPS_OR_INVALID_OBSERVATIONS" if failures else "PASS_BOUNDED_ENGINEERING_ONLY",
        "calendar": {"rows": len(calendar_rows), "open_sessions": len(open_dates), "civil_date_holes": calendar_holes,
                     "duplicate_dates": calendar_duplicates, "invalid_state_rows": invalid_calendar_rows, "complete_bounded_calendar": calendar_complete,
                     "calendar_authority": "GATEWAY_CAPTURE_UNVERIFIED_EXISTING_SSE_REFERENCE_ONLY", "weekday_inference_used": False},
        "symbols": by_symbol, "existing_sse_reference_comparison": comparison,
        "limitations": ["ALL_ROWS_QUARANTINED", "NO_PROVIDER_LICENSE_ADMISSION", "NO_HISTORICAL_AVAILABLE_AT_PROOF",
            "NO_NUMERIC_SECOND_SOURCE", "EMPTY_SUSPENSION_RESPONSE_IS_UNKNOWN", "CURRENT_SECURITY_STATUS_IS_NOT_HISTORY",
            "PRE_CLOSE_CAN_BE_EX_RIGHTS_REFERENCE", "GATEWAY_UNITS_NOT_INDEPENDENTLY_CONFIRMED"]}
