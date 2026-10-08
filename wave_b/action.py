"""Row-preserving action/factor candidates; no action or price authority."""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import re
from zoneinfo import ZoneInfo

from .core import make_result, observations, request_views, require_inputs


_KINDS = ('daily', 'adj_factor', 'dividend')
_SYMBOLS = ('603993.SH', '600312.SH', '603228.SH')
_PUBLICATION_DATES = ('ann_date', 'imp_ann_date')


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _day(value):
    _require(type(value) is str and re.fullmatch(r'\d{8}', value), 'ACTION_DATE_ONLY_REQUIRED')
    try:
        result = datetime.strptime(value, '%Y%m%d').date()
    except ValueError:
        raise ValueError('ACTION_DATE_INVALID') from None
    _require(result.strftime('%Y%m%d') == value, 'ACTION_DATE_INVALID')
    return result


def _number(value):
    _require(type(value) is str and len(value) <= 160, 'ACTION_DECIMAL_STRING_REQUIRED')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError('ACTION_DECIMAL_INVALID') from None
    _require(result.is_finite() and len(result.as_tuple().digits) <= 100 and
             abs(result.as_tuple().exponent) <= 64, 'ACTION_DECIMAL_INVALID')
    return Fraction(result)


def _rational(value):
    return {'numerator': str(value.numerator), 'denominator': str(value.denominator)}


def _check_observation(row):
    values, ref = row['values'], row['ref']
    _require(values.get('ts_code') in _SYMBOLS, 'ACTION_SYMBOL_CROSSOVER')
    retrieved = ref['retrieved_at']
    _require(type(retrieved) is str and re.fullmatch(
        r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)', retrieved),
        'ACTION_RETRIEVED_INSTANT_REQUIRED')
    try:
        captured_day = datetime.fromisoformat(retrieved.replace('Z', '+00:00')).astimezone(
            ZoneInfo('Asia/Shanghai')).date()
    except ValueError:
        raise ValueError('ACTION_RETRIEVED_INSTANT_INVALID') from None
    _require(ref['available_at'] == retrieved and ref['published_at'] is None,
             'ACTION_CURRENT_OBSERVATION_CLOCK_REQUIRED')
    for field in _PUBLICATION_DATES:
        literal = values.get(field)
        if literal not in (None, ''):
            _require(_day(literal) <= captured_day, 'ACTION_FUTURE_PUBLICATION')
    for field in ('ex_date', 'record_date'):
        literal = values.get(field)
        if literal not in (None, ''):
            _day(literal)


def _original(row, origin):
    # Full source fields and ordinal remain distinct even for equivalent values.
    return {'origin': origin, 'values': deepcopy(row['values']), 'ref': deepcopy(row['ref']),
            'response_blocked': row['response_blocked'], 'fixture': row['fixture']}


def _receipt(view):
    keys = ('request_id', 'api_name', 'fields', 'date_scope', 'scope',
            'raw_sha256', 'request_fingerprint', 'retrieved_at', 'available_at',
            'published_at', 'response_blocked', 'reason_codes')
    receipt = {key: deepcopy(view[key]) for key in keys if key in view}
    business_fields = {'dividend': ('ts_code', 'ex_date'),
                       'adj_factor': ('ts_code', 'trade_date')}[view['api_name']]
    original_params = view.get('params', {})
    receipt['params'] = {key: deepcopy(original_params[key]) for key in business_fields
                         if key in original_params}
    receipt['params_projection'] = {
        'kind': 'BUSINESS_SCOPE_ONLY', 'included_fields': sorted(receipt['params']),
        'omitted_parameter_count': len(original_params) - len(receipt['params']),
        'original_params_retained_in_verified_inputs': True,
        'original_params_bound_by_request_fingerprint': True,
        'transport_parameters_exported': False,
    }
    return receipt


def _coverage_rows(inputs, api):
    views = request_views(inputs, api, origin='legacy')
    selected = {q['request_id']: q for q in views if q.get('scope') == 'COVERAGE'}
    rows = [r for r in observations(inputs, api, origin='legacy') if r['ref']['request_id'] in selected]
    for row in rows:
        _require(row['values'].get('ts_code') == selected[row['ref']['request_id']].get('ts_code'),
                 'ACTION_REQUEST_SYMBOL_MISMATCH')
    return rows


def _date_map(rows, api, symbol):
    result = {}
    for row in rows:
        if row['values']['ts_code'] != symbol:
            continue
        day = row['values'].get('trade_date')
        _day(day)
        _require(day not in result, 'ACTION_DUPLICATE_BAR_OR_FACTOR_DATE')
        number_fields = ('adj_factor',) if api == 'adj_factor' else ('open', 'high', 'low', 'close', 'pre_close')
        for field in number_fields:
            _require(_number(row['values'].get(field)) > 0, 'ACTION_PRICE_OR_FACTOR_NOT_POSITIVE')
        result[day] = row
    return result


def _matches(rows, symbol, day, field, implemented=False):
    return [r for r in rows if r['values'].get('ts_code') == symbol and
            r['values'].get(field) == day and
            (not implemented or r['values'].get('div_proc') == '实施')]


def _observation_consistency(old_rows, new_rows):
    comparisons = []
    for new in new_rows:
        comparisons.append({
            'new_ref': deepcopy(new['ref']),
            'exact_full_field_matches': [deepcopy(old['ref']) for old in old_rows
                                        if old['values'] == new['values']],
            'new_response_blocked': new['response_blocked'],
            'observation_consistency_only': True,
            'independent_source_or_historical_visibility_proof': False,
            'originals_merged_or_deleted': False,
        })
    return comparisons


def analyze(inputs):
    """Return the three frozen diagnostic sections, without input/report writes."""
    require_inputs(inputs)
    legacy = {api: _coverage_rows(inputs, api) for api in _KINDS}
    new = {api: observations(inputs, api, origin='new') for api in ('adj_factor', 'dividend')}
    new_views = {api: request_views(inputs, api, origin='new') for api in ('adj_factor', 'dividend')}
    for row in [r for rows in (*legacy.values(), *new.values()) for r in rows]:
        _check_observation(row)

    view_by_id = {q['request_id']: q for views in new_views.values() for q in views}
    for api, field in (('adj_factor', 'trade_date'), ('dividend', 'ex_date')):
        for row in new[api]:
            q = view_by_id[row['ref']['request_id']]
            expected = q.get('params', {}).get(field)
            if not row['response_blocked']:
                _require(expected is not None and row['values'].get(field) == expected,
                         'ACTION_TARGET_FACTOR_DATE_MISMATCH' if api == 'adj_factor' else
                         'ACTION_TARGET_EX_DATE_MISMATCH')

    symbols, changes, ambiguous, gaps, nonzero = [], [], [], [], []
    for symbol in _SYMBOLS:
        bars = _date_map(legacy['daily'], 'daily', symbol)
        factors = _date_map(legacy['adj_factor'], 'adj_factor', symbol)
        if not bars and not factors:
            continue
        _require(set(bars) == set(factors) and bool(bars), 'ACTION_FACTOR_BAR_DATE_MISMATCH')
        blocked = any(r['response_blocked'] for r in (*bars.values(), *factors.values()))
        symbols.append({'ts_code': symbol, 'bar_row_count': len(bars), 'factor_row_count': len(factors),
                        'date_alignment': 'ENGINEERING_READY', 'status': 'BLOCKED' if blocked else 'PARTIAL'})
        if blocked:
            gaps.append({'ts_code': symbol, 'reason': 'BAR_OR_FACTOR_RESPONSE_BLOCKED'})
            continue
        dates = sorted(bars)
        for previous, day in zip(dates, dates[1:]):
            old_factor = _number(factors[previous]['values']['adj_factor'])
            factor = _number(factors[day]['values']['adj_factor'])
            expected = _number(bars[previous]['values']['close']) * old_factor / factor
            reported = _number(bars[day]['values']['pre_close'])
            delta = reported - expected
            comparison = {'ts_code': symbol, 'trade_date': day, 'previous_trade_date': previous,
                          'previous_bar_ref': deepcopy(bars[previous]['ref']),
                          'current_bar_ref': deepcopy(bars[day]['ref']),
                          'previous_factor_ref': deepcopy(factors[previous]['ref']),
                          'current_factor_ref': deepcopy(factors[day]['ref']),
                          'provider_pre_close': bars[day]['values']['pre_close'],
                          'diagnostic_exact_factor_reference': _rational(expected),
                          'exact_delta': _rational(delta), 'exact_equality': delta == 0,
                          'tolerance_policy': 'UNSET_REQUIRED', 'authoritative_reference_verified': False}
            if delta:
                nonzero.append(comparison)
            if factor == old_factor:
                continue

            old_actions = _matches(legacy['dividend'], symbol, day, 'ex_date', implemented=True)
            new_actions_all = _matches(new['dividend'], symbol, day, 'ex_date')
            new_actions = [r for r in new_actions_all if not r['response_blocked']]
            new_factors_all = _matches(new['adj_factor'], symbol, day, 'trade_date')
            new_factors = [r for r in new_factors_all if not r['response_blocked']]
            factor_checks = [{'new_ref': deepcopy(row['ref']),
                              'legacy_ref': deepcopy(factors[day]['ref']),
                              'literal_equality': row['values'].get('adj_factor') == factors[day]['values']['adj_factor'],
                              'exact_numeric_equality': _number(row['values'].get('adj_factor')) == factor,
                              'observation_consistency_only': True,
                              'independent_source_or_historical_visibility_proof': False}
                             for row in new_factors]
            status = 'AMBIGUOUS' if len(old_actions) > 1 else 'PARTIAL' if len(old_actions) == 1 else 'UNKNOWN'
            entry = {'ts_code': symbol, 'trade_date': day, 'effective_date_precision': 'DATE_ONLY',
                     'previous_trade_date': previous, 'factor_before': _original(factors[previous], 'legacy'),
                     'factor_after': _original(factors[day], 'legacy'),
                     'exact_change_ratio': _rational(factor / old_factor),
                     'pre_close_factor_reference': comparison,
                     'legacy_implemented_actions': [_original(row, 'legacy') for row in old_actions],
                     'new_same_date_action_rows': [_original(row, 'new') for row in new_actions_all],
                     'new_same_date_factor_rows': [_original(row, 'new') for row in new_factors_all],
                     'new_factor_comparisons': factor_checks,
                     'new_action_comparisons': _observation_consistency(old_actions, new_actions),
                     'new_action_request_views': [_receipt(q) for q in new_views['dividend']
                                                 if q.get('params', {}).get('ts_code') == symbol and
                                                 q.get('params', {}).get('ex_date') == day],
                     'new_factor_request_views': [_receipt(q) for q in new_views['adj_factor']
                                                 if q.get('params', {}).get('ts_code') == symbol and
                                                 q.get('params', {}).get('trade_date') == day],
                     'status': status, 'inferred_corporate_actions_created': 0,
                     'action_entitlement_ledger_reconstructed': False}
            changes.append(entry)
            if len(old_actions) > 1:
                differing = sorted(field for field in set().union(*(r['values'] for r in old_actions))
                                   if len({repr(r['values'].get(field)) for r in old_actions}) > 1)
                ambiguous.append({'ts_code': symbol, 'trade_date': day, 'status': 'AMBIGUOUS',
                                  'original_row_count': len(old_actions),
                                  'originals': [_original(row, 'legacy') for row in old_actions],
                                  'new_originals': [_original(row, 'new') for row in new_actions_all],
                                  'different_source_fields': differing,
                                  'resolution': 'UNKNOWN_NO_VERIFIED_SOURCE_ROW_ID_OR_VERSION_CHRONOLOGY',
                                  'resolved': False, 'rows_merged_deduplicated_or_replaced': False,
                                  'economic_terms_aggregated': False,
                                  'observation_consistency_only': True})
                gaps.append({'ts_code': symbol, 'trade_date': day, 'reason': 'MULTIPLE_ACTION_ORIGINALS_SEMANTICS_UNRESOLVED'})
            elif not old_actions:
                gaps.append({'ts_code': symbol, 'trade_date': day, 'reason': 'LEGACY_IMPLEMENTED_ACTION_ORIGINAL_MISSING'})
            if not new_actions:
                gaps.append({'ts_code': symbol, 'trade_date': day, 'reason': 'TARGET_ACTION_NONEMPTY_UNBLOCKED_OBSERVATION_NOT_ESTABLISHED'})
            if not new_factors:
                gaps.append({'ts_code': symbol, 'trade_date': day, 'reason': 'TARGET_FACTOR_NONEMPTY_UNBLOCKED_OBSERVATION_NOT_ESTABLISHED'})
            elif any(not q['exact_numeric_equality'] for q in factor_checks):
                gaps.append({'ts_code': symbol, 'trade_date': day, 'reason': 'TARGET_FACTOR_VALUE_CONFLICT'})

    body = {
        'factor_action_reconciliation': {
            'status': 'PARTIAL' if changes else 'UNKNOWN', 'symbols': symbols,
            'change_point_count': len(changes), 'change_points': changes,
            'legacy_action_originals': [_original(row, 'legacy') for row in legacy['dividend']],
            'new_action_originals': [_original(row, 'new') for row in new['dividend']],
            'new_factor_originals': [_original(row, 'new') for row in new['adj_factor']],
            'arithmetic': 'EXACT_FRACTION_FROM_DECIMAL_STRINGS',
            'independent_source_evidence': False, 'history_visibility_inferred': False,
            'adjusted_prices_published_as_source': False, 'action_entitlement_ledger_reconstructed': False},
        'ambiguous_action_cases': {
            'status': 'AMBIGUOUS' if ambiguous else 'UNKNOWN', 'case_count': len(ambiguous), 'cases': ambiguous,
            'originals_merged_or_deleted': False, 'resolution_inferred_from_equal_cash_or_factor': False},
        'adjustment_known_gaps': {
            'status': 'PARTIAL', 'gaps': gaps,
            'nonzero_reference_delta_count': len(nonzero), 'nonzero_reference_deltas': nonzero,
            'nonzero_reference_delta_resolution': 'UNKNOWN',
            'rounding_tolerance_policy': 'UNSET_REQUIRED',
            'authoritative_adjusted_prices': False, 'actual_entitlement_ledger': False,
            'action_formula_or_rights_inferred': False, 'negative_action_proof_from_empty_response': False,
            'historical_backtest_ready': False, 'license_or_source_admission_proven': False},
    }
    return make_result(inputs, 'ACTION_FACTOR_CANDIDATE', body, __file__)
