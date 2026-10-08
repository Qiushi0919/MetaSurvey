"""Exact factor arithmetic and observed action links; no inferred action feed."""
from fractions import Fraction
from .inputs import assert_dataset, diagnostic_header, require, number, date_only, value, row_ref, rational, SYMBOLS

def analyze_reconciliation(dataset):
    assert_dataset(dataset)
    result = diagnostic_header(dataset, 'FACTOR_ACTION_DIAGNOSTIC')
    result['symbols'] = []
    for symbol in SYMBOLS:
        selected = {q['api_name']: q for q in dataset['requests'] if q['scope'] == 'COVERAGE' and q.get('ts_code') == symbol and q['api_name'] in ('daily', 'adj_factor', 'dividend')}
        if not selected:
            continue
        require('daily' in selected and 'adj_factor' in selected, 'FACTOR_BAR_PAIR_MISSING')
        bars_request, factors_request = selected['daily'], selected['adj_factor']
        bars, factors = {}, {}
        for request, target in ((bars_request, bars), (factors_request, factors)):
            for row in request['rows']:
                day = value(row, 'trade_date'); date_only(day)
                require(day not in target, 'DUPLICATE_PRICE_OR_FACTOR_DATE')
                target[day] = row
        require(set(bars) == set(factors) and len(bars) > 0, 'FACTOR_BAR_DATE_MISMATCH')
        dates = sorted(bars)
        for day in dates:
            require(number(value(factors[day], 'adj_factor')) > 0, 'FACTOR_NOT_POSITIVE')
            for field in ('open', 'high', 'low', 'close', 'pre_close'):
                require(number(value(bars[day], field)) > 0, 'RAW_PRICE_NOT_POSITIVE')
        anchor = Fraction(number(value(factors[dates[-1]], 'adj_factor')))
        actions_request = selected.get('dividend')
        actions = actions_request['rows'] if actions_request else []
        action_by_date = {}
        for row in actions:
            day = value(row, 'ex_date')
            if value(row, 'div_proc') == '实施' and day is not None:
                date_only(day)
                action_by_date.setdefault(day, []).append(row)
        changes, references, normalized, gaps = [], [], [], []
        for i, day in enumerate(dates):
            factor = Fraction(number(value(factors[day], 'adj_factor')))
            ratios = {field: rational(Fraction(number(value(bars[day], field))) * factor / anchor) for field in ('open', 'high', 'low', 'close')}
            normalized.append({'trade_date': day, 'raw_bar_ref': row_ref(bars_request, bars[day]),
                               'factor_ref': row_ref(factors_request, factors[day]),
                               'diagnostic_anchor_date': dates[-1], 'diagnostic_exact_price_ratios': ratios,
                               'historical_price_or_return_authority': False, 'raw_fields_replaced': False})
            if i == 0:
                continue
            previous = dates[i - 1]
            old_factor = Fraction(number(value(factors[previous], 'adj_factor')))
            expected_reference = Fraction(number(value(bars[previous], 'close'))) * old_factor / factor
            provider_reference = Fraction(number(value(bars[day], 'pre_close')))
            delta = provider_reference - expected_reference
            references.append({'trade_date': day, 'previous_trade_date': previous,
                               'provider_pre_close': value(bars[day], 'pre_close'),
                               'factor_ratio_reference': rational(expected_reference), 'exact_delta': rational(delta),
                               'exact_equality': delta == 0, 'rounding_or_tolerance_policy': 'UNSET_REQUIRED',
                               'authoritative_reference_verified': False})
            if factor != old_factor:
                matching = action_by_date.get(day, [])
                entry = {'trade_date': day, 'factor_before': str(number(value(factors[previous], 'adj_factor'))),
                         'factor_after': str(number(value(factors[day], 'adj_factor'))), 'exact_change_ratio': rational(factor / old_factor),
                         'factor_change_ref': row_ref(factors_request, factors[day]),
                         'observed_implementation_refs': [row_ref(actions_request, row) for row in matching],
                         'source_terms': [{field: value(row, field) for field in ('ann_date', 'imp_ann_date', 'ex_date', 'stk_div', 'stk_bo_rate', 'stk_co_rate', 'cash_div', 'cash_div_tax')} for row in matching],
                         'link_status': 'OBSERVED_SAME_DATE_TERMS_NOT_FULL_ACTION_PROOF' if len(matching) == 1 else 'MULTIPLE_SOURCE_ROWS_NOT_RESOLVED' if matching else 'ACTION_EVIDENCE_MISSING',
                         'inferred_corporate_actions_created': 0}
                changes.append(entry)
                if not matching:
                    gaps.append({'trade_date': day, 'reason': 'FACTOR_CHANGE_WITHOUT_IMPLEMENTED_ACTION_ORIGINAL'})
                elif len(matching) > 1:
                    gaps.append({'trade_date': day, 'reason': 'MULTIPLE_ACTION_ORIGINALS_SEMANTICS_UNRESOLVED'})
        changes_dates = {x['trade_date'] for x in changes}
        unmatched = [{'trade_date': day, 'source_row_count': len(rows)} for day, rows in sorted(action_by_date.items()) if day in bars and day not in changes_dates]
        result['symbols'].append({'ts_code': symbol, 'bar_count': len(bars), 'factor_count': len(factors),
                                 'date_alignment': 'PASS_FOR_OBSERVED_ROWS', 'change_points': changes,
                                 'action_required_gaps': gaps, 'observed_actions_without_factor_change': unmatched,
                                 'pre_close_factor_reference_comparisons': references,
                                 'nonzero_reference_deltas': sum(not x['exact_equality'] for x in references),
                                 'diagnostic_normalized_prices': normalized,
                                 'rounding_tolerance': 'UNSET_REQUIRED', 'action_entitlement_ledger_reconstructed': False,
                                 'status': 'PARTIAL_NO_ADMITTED_ACTION_FEED_OR_HISTORICAL_VISIBILITY'})
    result['factor_math_implementation'] = 'EXACT_RATIONAL_NO_FLOAT_NO_ASSUMED_TOLERANCE'
    result['adjusted_prices_published_as_source'] = False
    return result
