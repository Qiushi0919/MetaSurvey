"""Pure, local, NON_PIT_DIAGNOSTIC simulation; never an execution authority.

Every policy argument is mandatory and explicitly synthetic. DPU is an
unverified source-price diagnostic unit, with 100 integer minor units per DPU;
it is not CNY, a real account, a fee entitlement or a production default.
Historical prices here do not prove historical availability. Source references
are provenance labels supplied by the caller, not admission or PIT authority.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import hashlib
import json
import re


SYMBOLS = ("600312.SH", "603228.SH", "603993.SH")
ROW_KEYS = {"trade_date", "open", "high", "low", "close", "source_ref"}
POLICY_KEYS = {
    "initial_cash_minor", "commission_bps", "min_commission_minor",
    "sell_tax_bps", "slippage_bps", "lot_size", "tradeability",
}
TRADEABILITY = {"BLOCK_UNKNOWN", "ASSUME_TRADEABLE_DIAGNOSTIC_ONLY"}
DECIMAL_TEXT = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
INTEGER_TEXT = re.compile(r"(?:0|[1-9][0-9]*)\Z")
ENTER = "ENTER_HYPOTHETICAL"
EXIT = "EXIT_HYPOTHETICAL"


class DiagnosticInputError(ValueError):
    """A malformed or incomplete diagnostic input blocks the entire run."""


def _error(code: str) -> None:
    raise DiagnosticInputError(code)


def _decimal(value: object, code: str, *, positive: bool = False) -> Decimal:
    # Numeric literals/floats, exponent notation, signs and nonfinite values
    # cannot silently enter the money calculation from JSON coercion.
    if not isinstance(value, str) or not DECIMAL_TEXT.fullmatch(value):
        _error(code)
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        _error(code)
    if not parsed.is_finite() or (positive and parsed <= 0):
        _error(code)
    # Arithmetic is finite at the fixed Decimal100 precision. Oversized inputs
    # are rejected before any calculation, rather than rounded on ingestion.
    if len(parsed.as_tuple().digits) > 100 or parsed.adjusted() > 96:
        _error("DECIMAL_INPUT_EXCEEDS_PRECISION_100")
    return parsed


def _minor(value: object, code: str) -> int:
    if not isinstance(value, str) or not INTEGER_TEXT.fullmatch(value):
        _error(code)
    if len(value) > 96:
        _error("INTEGER_MINOR_EXCEEDS_PRECISION_100")
    return int(value)


def _reference(value: object) -> dict:
    if type(value) is not dict or not value:
        _error("SOURCE_REFERENCE_REQUIRED")

    def validate(item: object) -> None:
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is list:
            for member in item:
                validate(member)
            return
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                _error("SOURCE_REFERENCE_NON_STRING_KEY")
            for member in item.values():
                validate(member)
            return
        _error("SOURCE_REFERENCE_NOT_JSON_SAFE_NO_FLOATS")

    validate(value)
    return deepcopy(value)


def _validate(rows_by_symbol: object, policy: object) -> tuple[dict, dict]:
    if type(rows_by_symbol) is not dict or not 1 <= len(rows_by_symbol) <= 3:
        _error("EXPLICIT_ONE_TO_THREE_DIAGNOSTIC_SYMBOLS_REQUIRED")
    if any(symbol not in SYMBOLS for symbol in rows_by_symbol):
        _error("SYMBOL_OUTSIDE_FROZEN_THREE_STOCK_SCOPE")
    if type(policy) is not dict or set(policy) != POLICY_KEYS:
        _error("EXPLICIT_EXACT_SYNTHETIC_POLICY_REQUIRED")
    if type(policy["tradeability"]) is not str or policy["tradeability"] not in TRADEABILITY:
        _error("TRADEABILITY_POLICY_INVALID")
    if type(policy["lot_size"]) is not int or policy["lot_size"] < 1 or len(str(policy["lot_size"])) > 96:
        _error("EXPLICIT_POSITIVE_INTEGER_DIAGNOSTIC_LOT_REQUIRED")
    validated_policy = deepcopy(policy)
    validated_policy["initial_cash_minor"] = _minor(policy["initial_cash_minor"], "INITIAL_CASH_MINOR_INVALID")
    validated_policy["min_commission_minor"] = _minor(policy["min_commission_minor"], "MIN_COMMISSION_MINOR_INVALID")
    for key in ("commission_bps", "sell_tax_bps", "slippage_bps"):
        validated_policy[key] = _decimal(policy[key], f"{key.upper()}_INVALID")
    if validated_policy["slippage_bps"] >= 10000:
        _error("SLIPPAGE_WOULD_MAKE_EXIT_PRICE_NONPOSITIVE")
    result = {}
    calendar = None
    for symbol in sorted(rows_by_symbol):
        original = rows_by_symbol[symbol]
        if type(original) is not list or not original:
            _error("MISSING_DIAGNOSTIC_PRICE_ROWS")
        validated = []
        dates = []
        for row in original:
            if type(row) is not dict or set(row) != ROW_KEYS:
                _error("PRICE_ROW_EXACT_KEYS_REQUIRED_NO_FINANCE_ADJUSTMENT_INDUSTRY")
            date = row["trade_date"]
            if type(date) is not str or not re.fullmatch(r"[0-9]{8}", date):
                _error("TRADE_DATE_YYYYMMDD_REQUIRED")
            try:
                parsed = datetime.strptime(date, "%Y%m%d")
            except ValueError:
                _error("TRADE_DATE_INVALID")
            if parsed.strftime("%Y%m%d") != date:
                _error("TRADE_DATE_INVALID")
            prices = {name: _decimal(row[name], f"{name.upper()}_POSITIVE_DECIMAL_STRING_REQUIRED", positive=True)
                      for name in ("open", "high", "low", "close")}
            if not prices["low"] <= min(prices["open"], prices["close"]) <= max(prices["open"], prices["close"]) <= prices["high"]:
                _error("OHLC_BOUNDS_INVALID")
            validated.append({"trade_date": date, **prices, "source_ref": _reference(row["source_ref"])})
            dates.append(date)
        if len(set(dates)) != len(dates):
            _error("DUPLICATE_PRICE_SESSION")
        if dates != sorted(dates):
            _error("PRICE_SESSIONS_NOT_SORTED")
        if calendar is not None and dates != calendar:
            _error("NONALIGNED_OR_MISSING_SYMBOL_CALENDAR_BLOCKS_FULL_RUN")
        calendar = dates
        result[symbol] = validated
    return result, validated_policy


def _text(value: Decimal) -> str:
    if not value.is_finite():
        _error("NONFINITE_DIAGNOSTIC_ARITHMETIC")
    return format(value, "f")


def _rounded_minor(value: Decimal) -> int:
    try:
        return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    except InvalidOperation:
        _error("DIAGNOSTIC_ARITHMETIC_EXCEEDS_PRECISION_100")


def _source(symbol: str, row: dict) -> dict:
    return {"symbol": symbol, "trade_date": row["trade_date"], "source_ref": deepcopy(row["source_ref"])}


def run_scenario(rows_by_symbol: dict, policy: dict) -> dict:
    """Run explicitly synthetic DPU accounting on caller-supplied prices.

    Signals use close(t), trailing MA20/MA60, and close(t)/close(t-20).
    Their first possible fill is the next observed session's open. Shared cash
    processes exits before entries, then exact lexical symbol order. Holdings
    are marked using the source close, with no forced terminal liquidation.
    ``BLOCK_UNKNOWN`` still diagnoses close conditions but permits no fills.
    Inputs are validated in full first: partial acceptance is impossible.
    """
    rows, p = _validate(rows_by_symbol, policy)
    symbols = sorted(rows)
    dates = [row["trade_date"] for row in rows[symbols[0]]]
    cash = p["initial_cash_minor"]
    initial_cash = cash
    lot = p["lot_size"]
    positions = {symbol: {"quantity": 0, "acquired_date": None, "acquired_index": None,
                          "acquired_source_ref": None, "book_cost_minor": 0} for symbol in symbols}
    pending = []
    signals = []
    fills = []
    equity = []
    gross_turnover = 0
    fees_paid = 0
    outcomes = []
    peak = initial_cash
    max_drawdown = Decimal(0)
    max_drawdown_date = None
    violations = {"future_index_violations": [], "same_bar_fill_violations": [],
                  "t_plus_one_violations": [], "ledger_mismatch_violations": [],
                  "negative_cash_violations": []}

    with localcontext() as context:
        context.prec = 100
        context.rounding = ROUND_HALF_EVEN
        for index, date in enumerate(dates):
            # These signals were constructed only at the previous observed
            # close. Nothing at today's close affects their open execution.
            current_pending = sorted(pending, key=lambda signal: (0 if signal["direction"] == EXIT else 1, signal["symbol"]))
            pending = []
            for signal in current_pending:
                symbol = signal["symbol"]
                row = rows[symbol][index]
                direction = signal["direction"]
                if int(signal["decision_index"]) >= index:
                    violations["same_bar_fill_violations"].append(signal["signal_id"])
                    _error("SAME_BAR_FILL_BLOCKED")
                if p["tradeability"] == "BLOCK_UNKNOWN":
                    outcomes.append({"signal_id": signal["signal_id"], "symbol": symbol,
                                     "attempt_date": date, "attempt_index": str(index),
                                     "status": "BLOCKED_TRADEABILITY_UNKNOWN",
                                     "reason_codes": ["CURRENT_TRADEABILITY_NOT_PROVEN", "NOT_HISTORICAL_PIT"]})
                    continue
                position = positions[symbol]
                if direction == EXIT and (position["quantity"] != lot or position["acquired_index"] >= index):
                    violations["t_plus_one_violations"].append(signal["signal_id"])
                    _error("T_PLUS_ONE_OR_POSITION_INVARIANT_BLOCKED")
                if direction == ENTER and position["quantity"] != 0:
                    _error("DUPLICATE_DIAGNOSTIC_POSITION_BLOCKED")
                multiplier = Decimal(1) + (p["slippage_bps"] / Decimal(10000)) * (1 if direction == ENTER else -1)
                price = row["open"] * multiplier
                gross_minor = _rounded_minor(price * lot * 100)
                commission = max(_rounded_minor(Decimal(gross_minor) * p["commission_bps"] / 10000), p["min_commission_minor"])
                tax = _rounded_minor(Decimal(gross_minor) * p["sell_tax_bps"] / 10000) if direction == EXIT else 0
                fee = commission + tax
                delta = -gross_minor - fee if direction == ENTER else gross_minor - fee
                if cash + delta < 0:
                    outcomes.append({"signal_id": signal["signal_id"], "symbol": symbol,
                                     "attempt_date": date, "attempt_index": str(index),
                                     "status": "BLOCKED_FEE_INCLUSIVE_AFFORDABILITY",
                                     "reason_codes": ["SYNTHETIC_CASH_INSUFFICIENT_INCLUDING_FEES", "NOT_HISTORICAL_PIT"]})
                    continue
                before = cash
                cash += delta
                fill = {
                    "diagnostic_only": True, "signal_id": signal["signal_id"], "symbol": symbol,
                    "direction": direction, "decision_date": signal["decision_date"],
                    "decision_index": signal["decision_index"], "fill_date": date, "fill_index": str(index),
                    "quantity": lot, "source_open": _text(row["open"]), "fill_price": _text(price),
                    "gross_minor": str(gross_minor), "commission_minor": str(commission),
                    "exit_tax_minor": str(tax), "fees_minor": str(fee), "cash_before_minor": str(before),
                    "cash_delta_minor": str(delta), "cash_after_minor": str(cash),
                    "decision_source_ref": deepcopy(signal["decision_source_ref"]),
                    "fill_source_ref": _source(symbol, row),
                    "reason_codes": ["ASSUMED_TRADEABLE_DIAGNOSTIC_ONLY", "NEXT_OBSERVED_SESSION_OPEN", "NOT_HISTORICAL_PIT"],
                }
                if before + delta != cash:
                    violations["ledger_mismatch_violations"].append(signal["signal_id"])
                    _error("DIAGNOSTIC_LEDGER_MISMATCH")
                if direction == ENTER:
                    position.update(quantity=lot, acquired_date=date, acquired_index=index,
                                    acquired_source_ref=_source(symbol, row), book_cost_minor=gross_minor + fee)
                else:
                    position.update(quantity=0, acquired_date=None, acquired_index=None,
                                    acquired_source_ref=None, book_cost_minor=0)
                gross_turnover += gross_minor
                fees_paid += fee
                fills.append(fill)
                outcomes.append({"signal_id": signal["signal_id"], "symbol": symbol,
                                 "attempt_date": date, "attempt_index": str(index),
                                 "status": "FILLED_HYPOTHETICAL",
                                 "reason_codes": ["ASSUMED_TRADEABLE_DIAGNOSTIC_ONLY", "NOT_HISTORICAL_PIT"]})

            marked = {symbol: _rounded_minor(rows[symbol][index]["close"] * positions[symbol]["quantity"] * 100) for symbol in symbols}
            value = cash + sum(marked.values())
            peak = max(peak, value)
            drawdown = (Decimal(peak - value) / peak) if peak else Decimal(0)
            if drawdown > max_drawdown:
                max_drawdown, max_drawdown_date = drawdown, date
            equity.append({
                "trade_date": date, "cash_minor": str(cash), "marked_positions_minor": {key: str(number) for key, number in marked.items()},
                "quantities": {symbol: positions[symbol]["quantity"] for symbol in symbols},
                "equity_minor": str(value), "peak_equity_minor": str(peak), "drawdown_ratio": _text(drawdown),
                "source_refs": [_source(symbol, rows[symbol][index]) for symbol in symbols],
            })
            if index < 59:
                continue
            for symbol in symbols:
                row = rows[symbol][index]
                close = row["close"]
                ma20 = sum((item["close"] for item in rows[symbol][index - 19:index + 1]), Decimal(0)) / 20
                ma60 = sum((item["close"] for item in rows[symbol][index - 59:index + 1]), Decimal(0)) / 60
                momentum20 = close / rows[symbol][index - 20]["close"]
                direction = None
                if positions[symbol]["quantity"] == 0 and close > ma20 > ma60 and momentum20 > 1:
                    direction = ENTER
                elif positions[symbol]["quantity"] == lot and close < ma20:
                    direction = EXIT
                if direction is None:
                    continue
                window = [_source(symbol, item) for item in rows[symbol][index - 59:index + 1]]
                if any(ref["trade_date"] > date for ref in window):
                    violations["future_index_violations"].append(f"{symbol}:{date}")
                    _error("FUTURE_DECISION_WINDOW_BLOCKED")
                signal_id = hashlib.sha256(json.dumps({"symbol": symbol, "date": date, "direction": direction,
                                                       "source": row["source_ref"], "window": window},
                                                      sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
                signal = {
                    "diagnostic_only": True, "signal_id": signal_id, "symbol": symbol, "direction": direction,
                    "decision_date": date, "decision_index": str(index), "ma20": _text(ma20), "ma60": _text(ma60),
                    "momentum20_ratio": _text(momentum20), "source_close": _text(close),
                    "decision_source_ref": _source(symbol, row), "window_source_refs": window,
                    "momentum_base_source_ref": _source(symbol, rows[symbol][index - 20]),
                    "status": "OBSERVED_CLOSE_DIAGNOSTIC_ONLY",
                    "reason_codes": ["NEXT_OBSERVED_SESSION_OPEN_REQUIRED", "NOT_HISTORICAL_PIT"],
                }
                signals.append(signal)
                pending.append(signal)

        reconciled = initial_cash + sum(int(fill["cash_delta_minor"]) for fill in fills)
        if reconciled != cash:
            violations["ledger_mismatch_violations"].append("FINAL_CASH_RECONCILIATION")
            _error("FINAL_DIAGNOSTIC_LEDGER_MISMATCH")
        if cash < 0:
            violations["negative_cash_violations"].append("FINAL_CASH")
            _error("DIAGNOSTIC_MARGIN_NOT_ALLOWED")
        output_positions = [{"symbol": symbol, "quantity": positions[symbol]["quantity"],
                             "acquired_date": positions[symbol]["acquired_date"],
                             "acquired_source_ref": deepcopy(positions[symbol]["acquired_source_ref"]),
                             "book_cost_minor": str(positions[symbol]["book_cost_minor"])} for symbol in symbols]
        return {
            "signals": signals, "fills": fills, "positions": output_positions, "equity": equity,
            "drawdown": {"max_drawdown_ratio": _text(max_drawdown), "max_drawdown_date": max_drawdown_date,
                         "unit": "DPU_EQUITY_RATIO_DIAGNOSTIC_ONLY", "forced_terminal_liquidation": False},
            "turnover": {"gross_turnover_minor": str(gross_turnover), "fees_paid_minor": str(fees_paid),
                         "gross_to_initial_cash_ratio": _text(Decimal(gross_turnover) / initial_cash) if initial_cash else None,
                         "unit": "DPU_MINOR_DIAGNOSTIC_ONLY", "zero_initial_cash_ratio_defined": bool(initial_cash)},
            "audit": {"state": "NON_PIT_DIAGNOSTIC", "historical_visibility_proven": False,
                      "production_eligible": False, "formal_backtest_eligible": False,
                      "reason_codes": ["NOT_HISTORICAL_PIT", "SYNTHETIC_DPU_POLICY_ONLY", "NO_EXECUTION_AUTHORITY"],
                      "cash_ordering": "EXIT_THEN_ENTER_EXACT_SYMBOL_ORDER", "symbol_order": symbols,
                      "initial_cash_minor": str(initial_cash), "final_cash_minor": str(cash),
                      "cash_reconciliation_minor": str(reconciled), "diagnostic_outcomes": outcomes,
                      "terminal_pending_signals": [{"signal_id": signal["signal_id"], "symbol": signal["symbol"],
                                                    "decision_date": signal["decision_date"],
                                                    "status": "PENDING_NO_NEXT_OBSERVED_SESSION",
                                                    "reason_codes": ["NEXT_SESSION_NOT_OBSERVED", "NOT_HISTORICAL_PIT"]}
                                                   for signal in pending], **violations},
            "assumptions": {"state": "NON_PIT_DIAGNOSTIC", "policy": deepcopy(policy),
                            "unit": "UNVERIFIED_SOURCE_PRICE_DPU", "minor_units_per_dpu": "100",
                            "all_policy_parameters_synthetic": True, "tradeability_proven": False,
                            "historical_visibility_proven": False, "corporate_actions_applied": False,
                            "raw_adjusted_authority": "CALLER_MUST_ISOLATE_UPSTREAM_SERIES_NO_FACTOR_ENTITLEMENT",
                            "rounding": "HALF_EVEN", "decimal_precision": "100",
                            "entry_rule": "close(t)>MA20(t)>MA60(t) and close(t)/close(t-20)>1",
                            "exit_rule": "close(t)<MA20(t)", "fill_rule": "next observed session open",
                            "terminal_liquidation": False, "maximum_holding_sessions": None,
                            "one_diagnostic_lot_per_symbol": True, "shared_synthetic_cash": True,
                            "fee_scenario_is_net_edge": False, "native_object_issued": False},
        }
