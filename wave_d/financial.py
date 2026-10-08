"""Current-observed financial facts, with period and revision-safe Decimal math.

This module has no provider admission, account, score or execution authority.
Missing fields in narrower historical schemas do not erase populated fields.
Every source version remains in the caller's Input; no update_flag is chronology.
"""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import json
from zoneinfo import ZoneInfo


SYMBOLS = ('603993.SH', '600312.SH', '603228.SH')
FINANCIAL_UNIT = 'PROVIDER_FINANCIAL_SCALE_UNVERIFIED'
_Q = Decimal('0.000001')
_SHANGHAI = ZoneInfo('Asia/Shanghai')
_FIELDS = {
    'daily_basic': (
        ('close', 'source_daily_basic_close', 'SOURCE_DECLARED_CNY_PER_SHARE_UNVERIFIED_GATEWAY'),
        ('pe_ttm', 'source_pe_ttm', 'SOURCE_REPORTED_TTM_RATIO_UNVERIFIED_GATEWAY'),
        ('pb', 'source_pb', 'SOURCE_REPORTED_RATIO_UNVERIFIED_GATEWAY'),
        ('ps_ttm', 'source_ps_ttm', 'SOURCE_REPORTED_TTM_RATIO_UNVERIFIED_GATEWAY'),
        ('total_mv', 'source_total_mv', 'SOURCE_DECLARED_WAN_CNY_UNVERIFIED_GATEWAY'),
        ('circ_mv', 'source_circ_mv', 'SOURCE_DECLARED_WAN_CNY_UNVERIFIED_GATEWAY'),
        ('total_share', 'source_total_share', 'SOURCE_DECLARED_WAN_SHARES_UNVERIFIED_GATEWAY'),
        ('turnover_rate', 'source_turnover_rate', 'SOURCE_DECLARED_PERCENT_UNVERIFIED_GATEWAY'),
    ),
    'income': (
        ('revenue', 'source_revenue', FINANCIAL_UNIT),
        ('total_revenue', 'source_total_revenue', FINANCIAL_UNIT),
        ('oper_cost', 'source_operating_cost', FINANCIAL_UNIT),
        ('n_income', 'source_consolidated_net_profit', FINANCIAL_UNIT),
        ('n_income_attr_p', 'source_parent_net_profit', FINANCIAL_UNIT),
    ),
    'balancesheet': (
        ('total_assets', 'source_total_assets', FINANCIAL_UNIT),
        ('total_liab', 'source_total_liabilities', FINANCIAL_UNIT),
        ('total_hldr_eqy_inc_min_int', 'source_equity_including_minority', FINANCIAL_UNIT),
        ('accounts_receiv', 'source_accounts_receivable', FINANCIAL_UNIT),
        ('inventories', 'source_inventories', FINANCIAL_UNIT),
        ('money_cap', 'source_money_capital', FINANCIAL_UNIT),
    ),
    'cashflow': (
        ('net_profit', 'source_cashflow_net_profit', FINANCIAL_UNIT),
        ('n_cashflow_act', 'source_operating_cashflow', FINANCIAL_UNIT),
        ('c_pay_acq_const_fiolta', 'source_capital_expenditure', FINANCIAL_UNIT),
    ),
    'fina_indicator': (
        ('roe', 'source_roe', FINANCIAL_UNIT),
        ('debt_to_assets', 'source_debt_to_assets', FINANCIAL_UNIT),
        ('netprofit_yoy', 'source_netprofit_yoy', FINANCIAL_UNIT),
        ('or_yoy', 'source_revenue_yoy', FINANCIAL_UNIT),
        ('grossprofit_margin', 'source_gross_margin', FINANCIAL_UNIT),
    ),
}


def _num(value):
    if type(value) is not str:
        raise ValueError('WAVE_D_DECIMAL_STRING_REQUIRED')
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('WAVE_D_DECIMAL_INVALID') from exc
    if (not number.is_finite() or abs(number.as_tuple().exponent) > 64
            or len(number.as_tuple().digits) > 100):
        raise ValueError('WAVE_D_DECIMAL_INVALID')
    return number


def _text(value):
    with localcontext() as ctx:
        ctx.prec = 50
        ctx.rounding = ROUND_HALF_EVEN
        rounded = value.quantize(_Q)
        return format(abs(rounded) if rounded.is_zero() else rounded, 'f')


def _refs(rows):
    unique = {}
    for row in rows:
        ref = row['source_ref']
        key = json.dumps(ref, sort_keys=True, separators=(',', ':'), allow_nan=False)
        unique[key] = ref
    return [deepcopy(unique[key]) for key in sorted(unique)]


def _feature(name, value, unit, formula, rows=(), reasons=(), period=None, conflict=False):
    reasons = list(reasons)
    if value is None and not reasons:
        reasons = ['WAVE_D_MISSING_EVIDENCE']
    return {
        'name': name,
        'state': 'CONFLICT' if conflict else 'UNKNOWN' if value is None else
                 'OBSERVED' if formula.startswith('SOURCE_') else 'DERIVED',
        'value': value,
        'unit': unit,
        'formula': formula,
        'source_refs': _refs(rows),
        'reason_codes': reasons,
        'period': period,
    }


def _day(value):
    if type(value) is not str or len(value) != 8 or not value.isdigit():
        raise ValueError('WAVE_D_SOURCE_DATE_INVALID')
    return datetime.strptime(value, '%Y%m%d').date()


def _eligible(row, symbol):
    if type(row) is not dict or type(row.get('values')) is not dict:
        return 'WAVE_D_OBSERVATION_INVALID'
    values = row['values']
    if values.get('ts_code') != symbol:
        return 'WAVE_D_SYMBOL_MISMATCH'
    ref = row.get('source_ref')
    if type(ref) is not dict:
        return 'WAVE_D_CLOCK_EVIDENCE_MISSING'
    try:
        captured = datetime.fromisoformat(ref['retrieved_at'].replace('Z', '+00:00'))
        if captured.tzinfo is None:
            raise ValueError('timezone required')
        captured_day = captured.astimezone(_SHANGHAI).date()
        for field in ('trade_date', 'end_date', 'ann_date', 'f_ann_date'):
            value = values.get(field)
            if value not in (None, '') and _day(value) > captured_day:
                return 'WAVE_D_FUTURE_SOURCE_DATE'
        period = values.get('trade_date' if row['api_name'] == 'daily_basic' else 'end_date')
        _day(period)
    except (KeyError, TypeError, ValueError, AttributeError):
        return 'WAVE_D_SOURCE_DATE_OR_CLOCK_INVALID'
    if row['api_name'] in ('income', 'balancesheet', 'cashflow'):
        if values.get('report_type') != '1' or values.get('comp_type') != '1':
            return 'WAVE_D_NON_PRIMARY_STATEMENT_SCOPE_PRESERVED'
        if period[4:] not in ('0331', '0630', '0930', '1231'):
            return 'WAVE_D_NON_STANDARD_CUMULATIVE_PERIOD'
    return None


def _scalar(rows, field):
    """Resolve observed non-null numbers; absent narrower-schema fields are history."""
    values = set()
    invalid = False
    for row in rows:
        raw = row['values'].get(field)
        if raw is None or raw == '':
            continue
        try:
            number = _num(raw)
            _text(number)  # Check that its requested display is representable.
            values.add(number)
        except (ValueError, InvalidOperation):
            invalid = True
    if invalid:
        return None, 'WAVE_D_INVALID_SOURCE_DECIMAL'
    if len(values) > 1:
        return None, 'WAVE_D_OBSERVED_FINANCIAL_VERSION_CONFLICT'
    return (next(iter(values)), None) if values else (None, 'WAVE_D_MISSING_EVIDENCE')


def financial_features(observations, symbol):
    """Return (latest features, all-period conflict codes, limitations/warnings).

    Statement rows are primary consolidated YTD/type1/company1 only; balance
    fields are point-in-time, and cannot silently match a different cash period.
    No annualization, synthesized TTM, CNY conversion or revision ordering occurs.
    """
    if symbol not in SYMBOLS or type(observations) is not list:
        raise ValueError('WAVE_D_FINANCIAL_SCOPE_INVALID')
    groups = {api: {} for api in _FIELDS}
    warnings = {
        'WAVE_D_FINANCIAL_UNITS_NOT_INDEPENDENTLY_VERIFIED',
        'WAVE_D_REVISION_CHRONOLOGY_UNKNOWN_NO_UPDATE_FLAG_ORDER',
        'WAVE_D_YTD_IS_NOT_SINGLE_QUARTER_OR_TTM',
        'WAVE_D_VALUATION_SOURCE_REPORTED_TTM_NOT_INDEPENDENT_TTM',
        'WAVE_D_CURRENT_OBSERVED_NOT_HISTORICAL_PIT',
    }
    for row in observations:
        if type(row) is not dict or row.get('api_name') not in groups:
            continue
        issue = _eligible(row, symbol)
        if issue:
            warnings.add(issue + ':' + row['api_name'])
            continue
        api = row['api_name']
        period = row['values']['trade_date' if api == 'daily_basic' else 'end_date']
        groups[api].setdefault(period, []).append(row)
    conflicts = set()
    blocked = set()
    for api, periods in groups.items():
        for period, rows in periods.items():
            for field, _, _ in _FIELDS[api]:
                _, issue = _scalar(rows, field)
                if issue == 'WAVE_D_OBSERVED_FINANCIAL_VERSION_CONFLICT':
                    blocked.add((api, period))
                    scope = ':1:1:' if api in ('income', 'balancesheet', 'cashflow') else ':UNSPECIFIED_SCOPE:'
                    conflicts.add(issue + ':' + api + ':' + period + scope + field)
                elif issue == 'WAVE_D_INVALID_SOURCE_DECIMAL':
                    warnings.add(issue + ':' + api + ':' + period + ':' + field)
    latest = {api: max(periods) if periods else None for api, periods in groups.items()}
    features = []
    for api in _FIELDS:
        period = latest[api]
        rows = groups[api].get(period, [])
        for field, name, unit in _FIELDS[api]:
            number, issue = _scalar(rows, field)
            conflict = (api, period) in blocked
            if conflict:
                number = None
                issue = 'WAVE_D_OBSERVED_FINANCIAL_VERSION_CONFLICT'
            formula = ('SOURCE_REPORTED_TTM_NOT_INDEPENDENTLY_CONSTRUCTED'
                       if field in ('pe_ttm', 'ps_ttm') else
                       'SOURCE_POINT_IN_TIME_LITERAL' if api in ('daily_basic', 'balancesheet') else
                       'SOURCE_REPORTED_INDICATOR_LITERAL' if api == 'fina_indicator' else
                       'SOURCE_CUMULATIVE_YTD_LITERAL_NOT_TTM')
            reasons = ['WAVE_D_UNIT_NOT_INDEPENDENTLY_VERIFIED',
                       'WAVE_D_REVISION_CHRONOLOGY_UNKNOWN']
            if issue:
                reasons.append(issue)
            features.append(_feature(name, _text(number) if number is not None else None,
                                     unit, formula, rows, reasons, period, conflict))

    def values(api, period, field):
        rows = groups[api].get(period, [])
        value, reason = _scalar(rows, field)
        if (api, period) in blocked:
            return None, rows, 'WAVE_D_OBSERVED_FINANCIAL_VERSION_CONFLICT'
        return value, rows, reason

    def derived(name, unit, formula, period, rows, value=None, reason=None):
        displayed = None
        if value is not None:
            try:
                displayed = _text(value)
            except InvalidOperation:
                reason = 'WAVE_D_DERIVED_DECIMAL_RANGE_INVALID'
        reasons = ['WAVE_D_UNIT_NOT_INDEPENDENTLY_VERIFIED',
                   'WAVE_D_CURRENT_OBSERVED_NOT_HISTORICAL_PIT']
        if reason:
            reasons.append(reason)
        features.append(_feature(name, displayed,
                                 unit, formula, rows, reasons, period,
                                 reason in ('WAVE_D_OBSERVED_FINANCIAL_VERSION_CONFLICT',
                                            'WAVE_D_CROSS_PRODUCT_CONSOLIDATED_PROFIT_MISMATCH')))

    with localcontext() as ctx:
        ctx.prec = 50
        ctx.rounding = ROUND_HALF_EVEN
        income_period = latest['income']
        for field, name in (('revenue', 'derived_revenue_yoy'),
                            ('n_income', 'derived_consolidated_profit_yoy')):
            current, rows, reason = values('income', income_period, field)
            prior_period = (str(int(income_period[:4]) - 1).zfill(4) + income_period[4:]
                            if income_period else None)
            prior, old_rows, old_reason = values('income', prior_period, field)
            issue = reason or old_reason
            value = None
            if issue is None:
                if prior <= 0:
                    issue = 'WAVE_D_NON_POSITIVE_PRIOR_YEAR_BASE'
                else:
                    value = (current / prior - 1) * 100
            derived(name, 'PERCENT_COMPARABLE_YTD_UNVERIFIED_GATEWAY',
                    'CURRENT_SAME_CUMULATIVE_PERIOD_OVER_PREVIOUS_YEAR_MINUS_ONE_X100; NOT_TTM',
                    income_period, rows + old_rows, value, issue)

        cash_period = latest['cashflow']
        cfo, cash_rows, cfo_issue = values('cashflow', cash_period, 'n_cashflow_act')
        cash_profit, _, cash_profit_issue = values('cashflow', cash_period, 'net_profit')
        income_profit, income_rows, income_issue = values('income', income_period, 'n_income')
        cash_issue = cfo_issue
        denom = None
        if cash_period != income_period and income_period is not None:
            cash_issue = 'WAVE_D_STATEMENT_PERIOD_MISMATCH'
        elif cash_profit_issue == 'WAVE_D_OBSERVED_FINANCIAL_VERSION_CONFLICT' or income_issue == 'WAVE_D_OBSERVED_FINANCIAL_VERSION_CONFLICT':
            cash_issue = 'WAVE_D_OBSERVED_FINANCIAL_VERSION_CONFLICT'
        elif cash_profit_issue == 'WAVE_D_INVALID_SOURCE_DECIMAL' or income_issue == 'WAVE_D_INVALID_SOURCE_DECIMAL':
            cash_issue = 'WAVE_D_INVALID_SOURCE_DECIMAL'
        elif cash_profit is not None and income_profit is not None and cash_profit != income_profit:
            cash_issue = 'WAVE_D_CROSS_PRODUCT_CONSOLIDATED_PROFIT_MISMATCH'
            conflicts.add(cash_issue + ':' + str(cash_period))
        elif cash_profit is not None:
            denom = cash_profit
            if income_profit is None:
                warnings.add('WAVE_D_CROSS_PRODUCT_PROFIT_CHECK_UNAVAILABLE')
        elif cash_profit_issue == 'WAVE_D_MISSING_EVIDENCE' and cash_period == income_period:
            denom = income_profit
            if denom is None:
                cash_issue = income_issue
            else:
                warnings.add('WAVE_D_CASHFLOW_PROFIT_ABSENT_MATCHED_INCOME_DENOMINATOR')
        else:
            cash_issue = cash_profit_issue
        cash_value = None
        if cash_issue is None:
            if denom is None:
                cash_issue = 'WAVE_D_MISSING_EVIDENCE'
            elif denom <= 0:
                cash_issue = 'WAVE_D_NON_POSITIVE_CONSOLIDATED_PROFIT'
            else:
                cash_value = cfo / denom
        derived('cash_conversion_ratio', 'RATIO_SAME_CUMULATIVE_PERIOD_UNVERIFIED_GATEWAY',
                'CFO_YTD_OVER_CONSOLIDATED_NET_PROFIT_SAME_PERIOD_TYPE1_COMPANY1; NEVER_PARENT_PROFIT',
                cash_period, cash_rows + income_rows, cash_value, cash_issue)

        capex, _, capex_issue = values('cashflow', cash_period, 'c_pay_acq_const_fiolta')
        proxy_issue = cfo_issue or capex_issue
        if proxy_issue is None and capex < 0:
            proxy_issue = 'WAVE_D_NEGATIVE_CAPITAL_PAYMENT'
        derived('cash_after_capex_proxy', FINANCIAL_UNIT,
                'CFO_YTD_MINUS_FIXED_INTANGIBLE_LONG_TERM_ASSET_CASH_PAYMENTS; PROXY_NOT_FREE_CASH_FLOW',
                cash_period, cash_rows, cfo - capex if proxy_issue is None else None, proxy_issue)

        balance_period = latest['balancesheet']
        liabilities, balance_rows, liabilities_issue = values('balancesheet', balance_period, 'total_liab')
        assets, _, assets_issue = values('balancesheet', balance_period, 'total_assets')
        debt_issue = liabilities_issue or assets_issue
        if debt_issue is None and assets <= 0:
            debt_issue = 'WAVE_D_NON_POSITIVE_TOTAL_ASSETS'
        derived('debt_ratio_pct', 'PERCENT_POINT_IN_TIME_UNVERIFIED_GATEWAY',
                'TOTAL_LIABILITIES_OVER_TOTAL_ASSETS_X100_SAME_POINT_IN_TIME',
                balance_period, balance_rows,
                liabilities / assets * 100 if debt_issue is None else None, debt_issue)
        revenue, revenue_rows, revenue_issue = values('income', income_period, 'revenue')
        for field, name in (('accounts_receiv', 'receivables_to_revenue_ratio'),
                            ('inventories', 'inventory_to_revenue_ratio')):
            numerator, rows, numerator_issue = values('balancesheet', balance_period, field)
            issue = numerator_issue or revenue_issue
            if balance_period != income_period:
                issue = 'WAVE_D_STATEMENT_PERIOD_MISMATCH'
            elif issue is None and revenue <= 0:
                issue = 'WAVE_D_NON_POSITIVE_REVENUE'
            derived(name, 'RATIO_POINT_IN_TIME_TO_YTD_UNVERIFIED_GATEWAY',
                    field.upper() + '_POINT_IN_TIME_OVER_SAME_END_DATE_REVENUE_YTD; NOT_TURNOVER_NOT_ANNUALIZED',
                    balance_period, rows + revenue_rows,
                    numerator / revenue if issue is None else None, issue)
    return features, sorted(conflicts), sorted(warnings)
