"""Meaningful synthetic C12 observations and forbidden history/authority paths."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from wave_b.core import (
    canonical, fixture_inputs, observations, require_cutoff, require_result, sha,
)
from wave_b.status import analyze

SYMBOL = '603993.SH'
CLOCK = '2026-10-06T01:00:00Z'
FIELDS = {
    'stock_basic': ['ts_code', 'symbol', 'name', 'exchange', 'curr_type', 'list_status', 'list_date', 'delist_date'],
    'stock_st': ['ts_code', 'name', 'trade_date', 'type', 'type_name'],
    'namechange': ['ts_code', 'name', 'start_date', 'end_date', 'ann_date', 'change_reason'],
    'suspend_d': ['ts_code', 'trade_date', 'suspend_timing', 'suspend_type'],
}


def request(api, rows, **extra):
    key = 'ann_date' if api == 'namechange' else 'trade_date' if api in ('stock_st', 'suspend_d') else None
    return {
        'api_name': api, 'ts_code': SYMBOL,
        'params': {'ts_code': SYMBOL, 'start_date': '20250601', 'end_date': '20261005'},
        'fields': FIELDS[api],
        'date_scope': {'key': key, 'start': '20250601', 'end': '20261005'},
        'rows': [{'values': {'ts_code': SYMBOL, **row}} for row in rows],
        **extra,
    }


def legacy_calendar():
    # Saturday is explicitly captured open; no unseen Monday is inferred.
    rows = [
        {'row_ordinal': n, 'typed_fields': {key: {'value': value} for key, value in values.items()}}
        for n, values in enumerate([
            {'exchange': 'SSE', 'cal_date': '20250607', 'is_open': '1', 'pretrade_date': '20250606'},
            {'exchange': 'SSE', 'cal_date': '20250608', 'is_open': '0', 'pretrade_date': '20250607'},
            {'exchange': 'SSE', 'cal_date': '20250610', 'is_open': '1', 'pretrade_date': '20250607'},
        ])
    ]
    return {
        'request_id': 'SYNTHETIC-CALENDAR', 'api_name': 'trade_cal', 'ts_code': None,
        'params': {'exchange': 'SSE'}, 'scope': 'COVERAGE',
        'date_scope': {'key': 'cal_date', 'start': '20250601', 'end': '20261005'},
        'raw_sha256': sha(canonical(rows)), 'request_fingerprint': sha(b'SYNTHETIC-CALENDAR-REQUEST'),
        'retrieved_at': CLOCK, 'available_at': CLOCK, 'published_at': None,
        'response_dq': 'PASS', 'response_dq_reasons': [], 'rows': rows,
    }


def inputs(*requests):
    return fixture_inputs(new_requests=list(requests), legacy_requests=[legacy_calendar()])


def symbol_gap(result):
    return next(item for item in result['body']['status_known_gaps'] if item['ts_code'] == SYMBOL)


def name_row(**extra):
    return {'name': 'SYNTHETIC_OLD_NAME', 'start_date': '20200101', 'end_date': '20250602',
            'ann_date': '20250901', 'change_reason': 'SYNTHETIC_REPORTED_REASON', **extra}


def failed_view(api='namechange', rows=None, **extra):
    """Actual failed-request shape; no capture is invented to satisfy the fixture helper."""
    view = request(api, rows or [])
    view.update({
        'origin': 'new', 'request_id': 'SYNTHETIC-FAILED-' + api,
        'raw_sha256': None, 'request_fingerprint': sha(('SYNTHETIC-FAILED-' + api).encode()),
        'retrieved_at': None, 'available_at': None, 'published_at': None,
        'response_blocked': True, 'reason_codes': ['SYNTHETIC_REQUEST_FAILED'],
        'row_count': len(view['rows']), 'fixture': True, **extra,
    })
    return view


def analyze_failed_views(views):
    # The core synthetic helper deliberately requires captured clocks. Interface
    # doubles exercise the analyzer's failed-request interface path.
    source = inputs()
    def requested(_inputs, api, origin='all'):
        return deepcopy([view for view in views if view['api_name'] == api])
    def observed(_inputs, api, origin='all'):
        if api == 'trade_cal': return observations(source, api, origin)
        out = []
        for view in requested(_inputs, api, origin):
            for ordinal, row in enumerate(view['rows']):
                out.append({
                    'values': deepcopy(row['values']), 'fixture': True,
                    'response_blocked': view['response_blocked'],
                    'ref': {**{key: view[key] for key in ('origin', 'request_id', 'request_fingerprint',
                                                         'raw_sha256', 'retrieved_at', 'available_at', 'published_at')},
                            'row_ordinal': ordinal},
                })
        return out
    with patch('wave_b.status.request_views', requested), patch('wave_b.status.observations', observed):
        return analyze(source)


class StatusTests(unittest.TestCase):
    def test_failed_namechange_request_without_capture_clocks_remains_blocked_unknown(self):
        result = analyze_failed_views([failed_view()])
        coverage = symbol_gap(result)['api_coverage']['namechange']
        self.assertEqual(coverage['state'], 'BLOCKED_EMPTY_RESPONSE_UNKNOWN')
        self.assertEqual(coverage['request_count'], 1)
        self.assertEqual(result['body']['security_status_timeline'], [])
        block = coverage['whole_response_blocks_retained'][0]
        self.assertIsNone(block['raw_sha256'])
        self.assertIsNone(block['retrieved_at'])
        self.assertIsNone(block['available_at'])
        self.assertEqual(block['capture_clock_state'], 'UNKNOWN')
        self.assertIn('SYNTHETIC_REQUEST_FAILED', block['reason_codes'])
        self.assertIn('STATUS_CAPTURE_CLOCK_UNKNOWN', block['reason_codes'])
        self.assertEqual(result['body']['c12_technical_coverage']['engineering_state'], 'UNKNOWN')
        self.assertEqual((result['state'], result['source_admission'], result['productionGate']), ('QUARANTINED', 'BLOCKED', False))

    def test_uncaptured_request_without_clock_is_locally_blocked_even_without_provider_block(self):
        view = failed_view(response_blocked=False, reason_codes=[])
        coverage = symbol_gap(analyze_failed_views([view]))['api_coverage']['namechange']
        self.assertEqual(coverage['state'], 'BLOCKED_EMPTY_RESPONSE_UNKNOWN')
        self.assertEqual(coverage['whole_response_blocks_retained'][0]['reason_codes'], ['STATUS_CAPTURE_CLOCK_UNKNOWN'])
        self.assertFalse(coverage['empty_response_proves_negative'])

    def test_partial_namechange_rows_without_capture_clock_are_preserved_whole_blocked(self):
        view = failed_view(rows=[name_row(), name_row(ann_date='20250902')],
                           response_blocked=False, reason_codes=[])
        result = analyze_failed_views([view]); rows = result['body']['security_status_timeline']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['response_blocked'] for row in rows))
        self.assertTrue(all(row['collector_available_at'] is None and row['collector_retrieved_at'] is None for row in rows))
        self.assertTrue(all('STATUS_CAPTURE_CLOCK_UNKNOWN' in row['response_reason_codes'] for row in rows))
        self.assertFalse(any('NAMECHANGE_FUTURE_PUBLICATION' in row['response_reason_codes'] for row in rows))
        self.assertEqual(symbol_gap(result)['api_coverage']['namechange']['whole_response_blocks_retained'][0]['row_count'], 2)

    def test_all_failed_status_api_requests_are_retained_with_unknown_capture_clocks(self):
        views = [failed_view(api) for api in FIELDS]
        result = analyze_failed_views(views)
        coverage = symbol_gap(result)['api_coverage']
        for api in FIELDS:
            self.assertEqual(coverage[api]['request_count'], 1)
            self.assertEqual(coverage[api]['state'], 'BLOCKED_EMPTY_RESPONSE_UNKNOWN')
            block = coverage[api]['whole_response_blocks_retained'][0]
            self.assertIsNone(block['available_at'])
            self.assertEqual(block['capture_clock_state'], 'UNKNOWN')
        self.assertFalse(result['historical_visibility_proven'])
        self.assertFalse(result['license_verified'])

    def test_one_missing_capture_clock_never_substitutes_the_other_clock(self):
        for retrieved, available in ((None, CLOCK), (CLOCK, None)):
            with self.subTest(retrieved=retrieved, available=available):
                view = failed_view(rows=[name_row()], retrieved_at=retrieved,
                                   available_at=available, response_blocked=False, reason_codes=[])
                row = analyze_failed_views([view])['body']['security_status_timeline'][0]
                self.assertEqual(row['collector_retrieved_at'], retrieved)
                self.assertEqual(row['collector_available_at'], available)
                self.assertEqual(row['capture_clock_state'], 'UNKNOWN')
                self.assertTrue(row['response_blocked'])
                self.assertNotIn('NAMECHANGE_FUTURE_PUBLICATION', row['response_reason_codes'])

    def test_invalid_or_inconsistent_capture_clocks_preserve_blocked_request_metadata(self):
        for available, state in (('SYNTHETIC_INVALID_CLOCK', 'INVALID'), ('2026-10-06T01:00:01Z', 'INCONSISTENT')):
            with self.subTest(state=state):
                view = failed_view(retrieved_at=CLOCK, available_at=available,
                                   response_blocked=False, reason_codes=[])
                coverage = symbol_gap(analyze_failed_views([view]))['api_coverage']['namechange']
                self.assertEqual(coverage['state'], 'BLOCKED_EMPTY_RESPONSE_UNKNOWN')
                block = coverage['whole_response_blocks_retained'][0]
                self.assertEqual(block['retrieved_at'], CLOCK)
                self.assertEqual(block['available_at'], available)
                self.assertEqual(block['capture_clock_state'], state)
                self.assertIn('STATUS_CAPTURE_CLOCK_' + state, block['reason_codes'])

    def test_empty_st_and_suspension_are_unknown_not_verified_negatives(self):
        result = analyze(inputs(request('stock_st', []), request('suspend_d', [])))
        coverage = symbol_gap(result)['api_coverage']
        for api in ('stock_st', 'suspend_d'):
            self.assertEqual(coverage[api]['state'], 'EMPTY_RESPONSE_UNKNOWN')
            self.assertFalse(coverage[api]['empty_response_proves_negative'])
            self.assertEqual(coverage[api]['observed_open_sessions_without_reported_event'], ['20250607', '20250610'])
            self.assertEqual(coverage[api]['unobserved_session_status'], 'UNKNOWN_NOT_VERIFIED_NEGATIVE')

    def test_current_name_and_list_status_never_backfill_historical_rows(self):
        row = {'symbol': '603993', 'name': 'SYNTHETIC_CURRENT_NAME', 'exchange': 'SSE', 'curr_type': 'CNY',
               'list_status': 'L', 'list_date': '20000101', 'delist_date': None}
        result = analyze(inputs(request('stock_basic', [row])))
        timeline = result['body']['security_status_timeline']
        self.assertEqual(len(timeline), 1)
        self.assertEqual(timeline[0]['effective_dates']['list_date'], '20000101')
        self.assertIn('CURRENT_IDENTITY_OBSERVATION_NOT_A_HISTORICAL', timeline[0]['effective_dates']['basis'])
        self.assertFalse(symbol_gap(result)['current_name_backfilled_to_history'])
        self.assertEqual(symbol_gap(result)['api_coverage']['namechange']['state'], 'NOT_CAPTURED_UNKNOWN')

    def test_legitimate_status_observations_remain_quarantined_without_license(self):
        source = inputs(
            request('stock_st', [{'name': 'SYNTHETIC_ST', 'trade_date': '20250607', 'type': 'ST', 'type_name': 'SYNTHETIC_TYPE'}]),
            request('namechange', [name_row()]),
            request('suspend_d', [{'trade_date': '20250610', 'suspend_timing': 'SYNTHETIC_TIMING', 'suspend_type': 'S'}]),
        )
        result = analyze(source)
        self.assertIs(require_result(result), result)
        self.assertEqual(result['kind'], 'SECURITY_STATUS_CANDIDATE')
        self.assertEqual(set(result['body']), {'c12_technical_coverage', 'security_status_timeline', 'status_known_gaps'})
        self.assertEqual((result['state'], result['source_admission']), ('QUARANTINED', 'BLOCKED'))
        for key in ('provider_identity_verified', 'license_verified', 'transport_integrity_verified', 'historical_visibility_proven', 'productionGate'):
            self.assertIs(result[key], False)
        self.assertEqual(result['body']['c12_technical_coverage']['engineering_state'], 'PARTIAL')
        self.assertEqual(result['body']['c12_technical_coverage']['real_security_status_objects_issued'], 0)
        self.assertTrue(all(not row['response_blocked'] for row in result['body']['security_status_timeline']))

    def test_namechange_filters_ann_date_not_earlier_effective_start_or_end(self):
        result = analyze(inputs(request('namechange', [name_row()])))
        row = result['body']['security_status_timeline'][0]
        self.assertFalse(row['response_blocked'])
        self.assertEqual(row['effective_dates']['start_date'], '20200101')
        self.assertEqual(row['publication_date_literal'], '20250901')
        self.assertEqual(symbol_gap(result)['api_coverage']['namechange']['request_filter_basis'], 'ANN_DATE_NOT_EFFECTIVE_START_OR_END_DATE')

    def test_outside_ann_date_preserves_whole_blocked_response(self):
        result = analyze(inputs(request('namechange', [name_row(), name_row(ann_date='20250531')])))
        rows = result['body']['security_status_timeline']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['response_blocked'] for row in rows))
        self.assertEqual(rows[1]['reported_values']['ann_date'], '20250531')
        self.assertEqual(symbol_gap(result)['api_coverage']['namechange']['whole_response_blocks_retained'][0]['row_count'], 2)

    def test_unknown_ann_date_or_filter_basis_cannot_select_a_valid_subset(self):
        for change in ({'rows': [name_row(), name_row(ann_date='')]},
                       {'date_scope': {'key': 'start_date', 'start': '20250601', 'end': '20261005'}}):
            with self.subTest(change=tuple(change)):
                q = request('namechange', change.get('rows', [name_row(), name_row()]))
                if 'date_scope' in change: q['date_scope'] = change['date_scope']
                result = analyze(inputs(q))
                self.assertEqual(len(result['body']['security_status_timeline']), 2)
                self.assertTrue(all(row['response_blocked'] for row in result['body']['security_status_timeline']))

    def test_future_publication_blocks_every_row_with_exact_capture_clock_preserved(self):
        result = analyze(inputs(request('namechange', [name_row(), name_row(ann_date='20261007')])))
        rows = result['body']['security_status_timeline']
        self.assertTrue(all(row['response_blocked'] for row in rows))
        self.assertTrue(all('NAMECHANGE_FUTURE_PUBLICATION' in row['response_reason_codes'] for row in rows))
        self.assertTrue(all(row['collector_available_at'] == CLOCK and row['published_at'] is None for row in rows))

    def test_unknown_namechange_filter_window_blocks_whole_response(self):
        q = request('namechange', [name_row(), name_row()],
                    date_scope={'key': 'ann_date', 'start': '20250601', 'end': None})
        rows = analyze(inputs(q))['body']['security_status_timeline']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['response_blocked'] for row in rows))
        self.assertTrue(all('NAMECHANGE_FILTER_WINDOW_UNKNOWN' in row['response_reason_codes'] for row in rows))

    def test_namechange_row_outside_explicit_request_filter_blocks_whole_response(self):
        q = request('namechange', [name_row(), name_row(ann_date='20250904')],
                    date_scope={'key': 'ann_date', 'start': '20250901', 'end': '20250903'})
        rows = analyze(inputs(q))['body']['security_status_timeline']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['response_blocked'] for row in rows))
        self.assertTrue(all('NAMECHANGE_ANN_DATE_OUTSIDE_REQUEST_FILTER' in row['response_reason_codes'] for row in rows))

    def test_blocked_empty_status_request_keeps_block_and_unknown_metadata(self):
        q = request('stock_st', [], response_blocked=True, reason_codes=['SYNTHETIC_RESPONSE_BLOCKED'])
        coverage = symbol_gap(analyze(inputs(q)))['api_coverage']['stock_st']
        self.assertEqual(coverage['state'], 'BLOCKED_EMPTY_RESPONSE_UNKNOWN')
        self.assertFalse(coverage['empty_response_proves_negative'])
        self.assertEqual(coverage['whole_response_blocks_retained'][0]['row_count'], 0)
        self.assertEqual(coverage['whole_response_blocks_retained'][0]['reason_codes'], ['SYNTHETIC_RESPONSE_BLOCKED'])

    def test_future_availability_is_rejected_at_an_earlier_historical_cutoff(self):
        source = inputs(request('stock_st', [{'name': 'SYNTHETIC_ST', 'trade_date': '20250607', 'type': 'ST', 'type_name': 'SYNTHETIC'}]))
        observation = observations(source, 'stock_st')[0]
        with self.assertRaisesRegex(ValueError, 'OBSERVATION_NOT_AVAILABLE_AT_CUTOFF'):
            require_cutoff(observation, '2026-06-07T01:00:00Z')
        row = analyze(source)['body']['security_status_timeline'][0]
        self.assertEqual(row['collector_available_at'], CLOCK)
        self.assertFalse(row['historical_visibility_proven'])

    def test_caller_cannot_backdate_available_at_to_effective_day(self):
        q = request('stock_st', [], retrieved_at=CLOCK, available_at='2025-06-07T01:00:00Z')
        with self.assertRaisesRegex(ValueError, 'CLOCK_BACKFILL_FORBIDDEN'): inputs(q)

    def test_cross_symbol_row_is_rejected(self):
        q = request('stock_st', [{'ts_code': '600312.SH', 'trade_date': '20250607'}])
        with self.assertRaisesRegex(ValueError, 'SYMBOL_SCOPE_INVALID'): inputs(q)

    def test_cross_namespace_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'FIXTURE_PERMISSION_INVALID'):
            inputs(request('stock_st', [], namespace='EVENT_3'))

    def test_input_copy_cannot_supply_registered_authority(self):
        source = inputs(request('stock_st', []))
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_OR_MUTATED_INPUT'): analyze(deepcopy(source))

    def test_registered_input_mutation_is_rejected(self):
        source = inputs(request('stock_st', [{'trade_date': '20250607', 'name': 'SYNTHETIC'}]))
        source['new'][0]['rows'][0]['values']['trade_date'] = '20250610'
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_OR_MUTATED_INPUT'): analyze(source)

    def test_authoritative_blocked_request_keeps_all_rows_and_reasons(self):
        q = request('stock_st', [{'trade_date': '20250607'}, {'trade_date': '20250610'}],
                    response_blocked=True, reason_codes=['SYNTHETIC_WHOLE_RESPONSE_BLOCKED'])
        result = analyze(inputs(q)); rows = result['body']['security_status_timeline']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['response_blocked'] for row in rows))
        self.assertTrue(all(row['response_reason_codes'] == ['SYNTHETIC_WHOLE_RESPONSE_BLOCKED'] for row in rows))
        self.assertEqual(symbol_gap(result)['api_coverage']['stock_st']['unblocked_observation_count'], 0)

    def test_calendar_uses_observed_saturday_and_does_not_infer_unseen_weekday(self):
        result = analyze(inputs(request('stock_st', [{'trade_date': '20250607'}])))
        self.assertEqual(result['body']['security_status_timeline'][0]['calendar_match'], 'OBSERVED_OPEN')
        self.assertEqual(symbol_gap(result)['api_coverage']['stock_st']['observed_open_sessions_without_reported_event'], ['20250610'])
        self.assertFalse(result['body']['c12_technical_coverage']['calendar']['weekday_inference_used'])

    def test_repeat_analysis_is_deterministic_and_does_not_mutate_input(self):
        source = inputs(request('namechange', [name_row()]))
        before = canonical(source)
        first, second = analyze(source), analyze(source)
        self.assertEqual(canonical(first), canonical(second))
        self.assertEqual(canonical(source), before)
        self.assertEqual(first['content_hash'], second['content_hash'])

    def test_blank_name_end_and_reversed_interval_remain_unknown_or_ambiguous(self):
        result = analyze(inputs(request('namechange', [name_row(end_date=''), name_row(start_date='20250902', end_date='20250901')])))
        rows = result['body']['security_status_timeline']
        self.assertEqual(rows[0]['effective_dates']['end_date'], '')
        self.assertEqual(rows[0]['effective_dates']['basis'], 'UNKNOWN_BOUNDARY_NO_INFINITE_OR_CURRENT_NAME_SUBSTITUTION')
        self.assertEqual(rows[1]['effective_dates']['basis'], 'AMBIGUOUS_REVERSED_REPORTED_INTERVAL')
        self.assertFalse(symbol_gap(result)['historical_status_complete'])

    def test_duplicate_observations_keep_distinct_row_ordinals_and_raw_refs(self):
        row = {'trade_date': '20250607', 'name': 'SYNTHETIC_ST'}
        result = analyze(inputs(request('stock_st', [row, row])))
        rows = result['body']['security_status_timeline']
        self.assertEqual(len(rows), 2)
        self.assertEqual([row['source_ref']['row_ordinal'] for row in rows], [0, 1])
        self.assertEqual(rows[0]['source_ref']['raw_sha256'], rows[1]['source_ref']['raw_sha256'])

    def test_reported_resumption_does_not_infer_normal_status_between_events(self):
        result = analyze(inputs(request('suspend_d', [{'trade_date': '20250607', 'suspend_type': 'R'}])))
        coverage = symbol_gap(result)['api_coverage']['suspend_d']
        self.assertFalse(coverage['event_intervals_inferred'])
        self.assertEqual(coverage['observed_open_sessions_without_reported_event'], ['20250610'])
        self.assertEqual(coverage['unobserved_session_status'], 'UNKNOWN_NOT_VERIFIED_NEGATIVE')

    def test_informational_reason_does_not_override_authoritative_response_status(self):
        q = request('stock_st', [{'trade_date': '20250607'}], reason_codes=['SYNTHETIC_INFORMATION_ONLY'])
        row = analyze(inputs(q))['body']['security_status_timeline'][0]
        self.assertFalse(row['response_blocked'])
        self.assertEqual(row['response_reason_codes'], ['SYNTHETIC_INFORMATION_ONLY'])

    def test_unknown_trade_date_blocks_whole_status_response_without_dropping_rows(self):
        result = analyze(inputs(request('stock_st', [{'trade_date': '20250607'}, {'trade_date': ''}])))
        rows = result['body']['security_status_timeline']
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['response_blocked'] for row in rows))
        self.assertTrue(all('STATUS_TRADE_DATE_UNKNOWN' in row['response_reason_codes'] for row in rows))


if __name__ == '__main__': unittest.main()
