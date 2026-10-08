"""C12 reported-status observations, never an admitted historical status feed."""
from copy import deepcopy
from datetime import timezone, timedelta

from .core import (
    SYMBOLS, START, END, clock, date_literal, make_result, observations,
    request_views, require, require_inputs,
)

STATUS_APIS = ('stock_basic', 'stock_st', 'namechange', 'suspend_d')


def _key(value):
    return (value['origin'], value['request_id'], value['raw_sha256'])


def _calendar(inputs):
    """Use captured facts only; repeated source observations remain counted."""
    rows = observations(inputs, 'trade_cal', origin='legacy')
    states, rejected = {}, 0
    for observation in rows:
        values = observation['values']
        date, opened = values.get('cal_date'), values.get('is_open')
        if (observation['response_blocked'] or not date_literal(date) or
                not START <= date <= END or str(opened) not in ('0', '1') or
                values.get('exchange') != 'SSE'):
            rejected += 1
            continue
        states.setdefault(date, set()).add(str(opened))
    conflicts = sorted(date for date, seen in states.items() if len(seen) != 1)
    opened = sorted(date for date, seen in states.items() if seen == {'1'})
    return states, opened, {
        'source': 'CAPTURED_LEGACY_CALENDAR_ONLY',
        'physical_observation_count': len(rows),
        'distinct_valid_civil_dates': len(states),
        'observed_open_sessions': len(opened),
        'conflicting_calendar_dates': conflicts,
        'blocked_invalid_or_outside_window_observations': rejected,
        'weekday_inference_used': False,
        'calendar_admission': 'BLOCKED',
    }


def _local_block_reasons(view):
    """Unknown capture clocks and bad filter dates retain whole blocked requests."""
    reasons = set()
    values = [row.get('values', row) for row in view.get('rows', [])]
    scope = view.get('date_scope') or {}
    observed_day = None
    retrieved, available = view.get('retrieved_at'), view.get('available_at')
    if retrieved is None or available is None:
        reasons.add('STATUS_CAPTURE_CLOCK_UNKNOWN')
    else:
        try:
            clock(retrieved)
            captured = clock(available)
        except ValueError:
            reasons.add('STATUS_CAPTURE_CLOCK_INVALID')
        else:
            if retrieved != available:
                reasons.add('STATUS_CAPTURE_CLOCK_INCONSISTENT')
            else:
                observed_day = captured.astimezone(timezone(timedelta(hours=8))).strftime('%Y%m%d')
    if view['api_name'] == 'namechange':
        if scope.get('key') != 'ann_date':
            reasons.add('NAMECHANGE_FILTER_BASIS_UNKNOWN')
        start, end = scope.get('start'), scope.get('end')
        known_window = date_literal(start) and date_literal(end) and start <= end
        if not known_window:
            reasons.add('NAMECHANGE_FILTER_WINDOW_UNKNOWN')
        for row in values:
            announced = row.get('ann_date')
            if not date_literal(announced):
                reasons.add('NAMECHANGE_ANN_DATE_UNKNOWN')
            else:
                if not START <= announced <= END:
                    reasons.add('NAMECHANGE_ANN_DATE_OUTSIDE_FROZEN_WINDOW')
                if known_window and not start <= announced <= end:
                    reasons.add('NAMECHANGE_ANN_DATE_OUTSIDE_REQUEST_FILTER')
                if observed_day is not None and announced > observed_day:
                    reasons.add('NAMECHANGE_FUTURE_PUBLICATION')
    elif view['api_name'] in ('stock_st', 'suspend_d'):
        for row in values:
            traded = row.get('trade_date')
            if not date_literal(traded):
                reasons.add('STATUS_TRADE_DATE_UNKNOWN')
            elif not START <= traded <= END:
                reasons.add('STATUS_TRADE_DATE_OUTSIDE_FROZEN_WINDOW')
    return sorted(reasons)


def _capture_clock_state(reasons):
    for state in ('UNKNOWN', 'INVALID', 'INCONSISTENT'):
        if 'STATUS_CAPTURE_CLOCK_' + state in reasons:
            return state
    return 'PRESERVED_CAPTURE_CLOCKS'


def _effective_dates(api, values):
    if api == 'stock_basic':
        return {
            'list_date': values.get('list_date'), 'delist_date': values.get('delist_date'),
            'basis': 'CURRENT_IDENTITY_OBSERVATION_NOT_A_HISTORICAL_NAME_OR_STATUS_INTERVAL',
        }
    if api == 'namechange':
        start, end = values.get('start_date'), values.get('end_date')
        interval = 'REPORTED_DATE_ONLY_INTERVAL_UNVERIFIED'
        if not date_literal(start) or not date_literal(end):
            interval = 'UNKNOWN_BOUNDARY_NO_INFINITE_OR_CURRENT_NAME_SUBSTITUTION'
        elif start > end:
            interval = 'AMBIGUOUS_REVERSED_REPORTED_INTERVAL'
        return {'start_date': start, 'end_date': end, 'basis': interval}
    return {'trade_date': values.get('trade_date'), 'basis': 'REPORTED_DATE_ONLY_EVENT_UNVERIFIED'}


def analyze(inputs):
    """Preserve reports/ref clocks and separate positive observations from gaps."""
    require_inputs(inputs)
    calendar_states, open_dates, calendar_summary = _calendar(inputs)
    views = [view for api in STATUS_APIS for view in request_views(inputs, api)]
    by_request = {_key(view): view for view in views}
    local_blocks = {_key(view): _local_block_reasons(view) for view in views}
    reasons = {_key(view): sorted(set(view.get('reason_codes', [])) | set(local_blocks[_key(view)]))
               for view in views}
    timeline = []
    for api in STATUS_APIS:
        for observation in observations(inputs, api):
            values, ref = observation['values'], observation['ref']
            symbol = values.get('ts_code')
            require(symbol in SYMBOLS and symbol == by_request[_key(ref)].get('ts_code'),
                    'STATUS_SYMBOL_SCOPE_INVALID')
            date = values.get('trade_date') if api in ('stock_st', 'suspend_d') else None
            seen = calendar_states.get(date)
            calendar_match = ('OBSERVED_OPEN' if seen == {'1'} else
                              'OBSERVED_CLOSED' if seen == {'0'} else
                              'UNKNOWN_OR_CONFLICTING_CALENDAR' if date is not None else
                              'NOT_A_TRADE_DATE_EVENT')
            blocked = observation['response_blocked'] or bool(local_blocks[_key(ref)])
            timeline.append({
                'ts_code': symbol, 'api_name': api,
                'reported_values': deepcopy(values),
                'effective_dates': _effective_dates(api, values),
                'publication_date_literal': values.get('ann_date') if api == 'namechange' else None,
                'publication_precision': 'DATE_ONLY' if api == 'namechange' else None,
                'published_at': ref['published_at'],
                'collector_retrieved_at': ref['retrieved_at'],
                'collector_available_at': ref['available_at'],
                'capture_clock_state': _capture_clock_state(local_blocks[_key(ref)]),
                'historical_visibility_proven': False,
                'source_ref': deepcopy(ref),
                'response_blocked': blocked,
                'response_reason_codes': reasons[_key(ref)],
                'technical_observation': 'BLOCKED_RESPONSE_RETAINED' if blocked else 'OBSERVED_UNVERIFIED',
                'calendar_match': calendar_match,
                'supplier_status_semantics': 'UNVERIFIED_NO_EVENT_TO_INTERVAL_EXPANSION',
            })

    gaps = []
    for symbol in SYMBOLS:
        symbol_rows = [row for row in timeline if row['ts_code'] == symbol]
        detail = {'ts_code': symbol, 'historical_status_complete': False,
                  'current_name_backfilled_to_history': False, 'api_coverage': {}}
        for api in STATUS_APIS:
            requested = [view for view in views if view.get('ts_code') == symbol and view['api_name'] == api]
            rows = [row for row in symbol_rows if row['api_name'] == api]
            usable = [row for row in rows if not row['response_blocked']]
            whole_blocked = any(view['response_blocked'] or local_blocks[_key(view)] for view in requested)
            state = ('NOT_CAPTURED_UNKNOWN' if not requested else
                     'BLOCKED_EMPTY_RESPONSE_UNKNOWN' if not rows and whole_blocked else
                     'EMPTY_RESPONSE_UNKNOWN' if not rows else
                     'BLOCKED_RESPONSE_RETAINED' if not usable else
                     'CURRENT_OBSERVATIONS_ONLY' if api == 'stock_basic' else
                     'OBSERVED_ROWS_COVERAGE_UNPROVEN')
            coverage = {
                'state': state, 'request_count': len(requested), 'physical_row_count': len(rows),
                'unblocked_observation_count': len(usable),
                'empty_response_proves_negative': False,
                'whole_response_blocks_retained': [
                    {'request_id': view['request_id'], 'request_fingerprint': view['request_fingerprint'],
                     'origin': view['origin'], 'raw_sha256': view['raw_sha256'],
                     'row_count': view['row_count'], 'reason_codes': reasons[_key(view)],
                     'retrieved_at': view.get('retrieved_at'), 'available_at': view.get('available_at'),
                     'published_at': view.get('published_at'),
                     'capture_clock_state': _capture_clock_state(local_blocks[_key(view)])}
                    for view in requested if view['response_blocked'] or local_blocks[_key(view)]
                ],
            }
            if api in ('stock_st', 'suspend_d'):
                dates = sorted({row['reported_values']['trade_date'] for row in usable})
                coverage.update({
                    'observed_trade_dates': dates,
                    'observed_open_sessions_without_reported_event': sorted(set(open_dates) - set(dates)),
                    'unobserved_session_status': 'UNKNOWN_NOT_VERIFIED_NEGATIVE',
                    'event_intervals_inferred': False,
                })
            elif api == 'namechange':
                coverage['historical_name_coverage'] = 'UNPROVEN_NO_CURRENT_NAME_BACKFILL'
                coverage['request_filter_basis'] = 'ANN_DATE_NOT_EFFECTIVE_START_OR_END_DATE'
            else:
                coverage['historical_identity_status'] = 'UNPROVEN_CURRENT_ONLY'
            detail['api_coverage'][api] = coverage
        gaps.append(detail)

    unblocked = sum(not row['response_blocked'] for row in timeline)
    body = {
        'c12_technical_coverage': {
            'condition_id': 'C12', 'engineering_state': 'PARTIAL' if unblocked else 'UNKNOWN',
            'business_condition_closure': 'NOT_CLOSED',
            'frozen_window': {'start': START, 'end': END}, 'calendar': calendar_summary,
            'physical_status_observation_count': len(timeline),
            'unblocked_status_observation_count': unblocked,
            'historical_status_complete': False,
            'real_security_status_objects_issued': 0,
            'limitations': ['PROVIDER_LICENSE_TRANSPORT_UNVERIFIED', 'NO_HISTORICAL_AVAILABILITY_PROOF',
                            'EMPTY_ST_OR_SUSPENSION_IS_UNKNOWN', 'CURRENT_NAME_STATUS_IS_NOT_HISTORY'],
        },
        'security_status_timeline': timeline,
        'status_known_gaps': gaps,
    }
    return make_result(inputs, 'SECURITY_STATUS_CANDIDATE', body, __file__)
