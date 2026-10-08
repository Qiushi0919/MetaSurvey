"""Refresh/DQ tests use explicit closures, gaps and conflicting versions."""
from copy import deepcopy
from datetime import date, timedelta
import unittest

from backtest_5y.maintenance import build_update_plan, validate_records


def rec(domain='PRICE', day='2026-01-02', symbol='S', identity=None, fields=None, revision='r1'):
    return {'source': 'FIXTURE', 'domain': domain, 'symbol': symbol,
            'identity': identity or domain + ':' + day, 'event_date': day,
            'revision_id': revision, 'fields': fields or {'trade_date': day.replace('-', ''),
                'open': '10', 'high': '11', 'low': '9', 'close': '10', 'vol': '100'},
            'published_at': None, 'available_at': None, 'first_visible_at': None,
            'retrieved_at': '2026-10-08T01:00:00+00:00', 'units': {},
            'provenance': {'test_only': True}}


def req(domain='PRICE', symbols=('S',), start='2026-01-01', end='2026-01-06', fields=None):
    return {'id': domain.lower(), 'domain': domain, 'symbols': list(symbols),
            'start': start, 'end': end, 'fields': fields or ['trade_date','open','high','low','close','vol'],
            'window': 'Frozen rule window unchanged', 'pit_requirements': ['revision_chain'],
            'revision_lookback_days': 30, 'refresh_mode': 'INCREMENTAL_WITH_OVERLAP'}


class MaintenanceTests(unittest.TestCase):
    def test_all_empty_domains_symbols_and_idempotent_initial_plan(self):
        requirements = [req(symbols=('S', 'T')), req('FINANCIAL_INCOME', fields=['end_date','ann_date','revenue'])]
        a = build_update_plan([], requirements, '2026-01-06')
        self.assertEqual(a, build_update_plan([], deepcopy(requirements), '2026-01-06'))
        self.assertEqual(len(a['rows']), 3)
        self.assertEqual(a['rows'][0]['requested_intervals'], [{'start': '2026-01-01', 'end': '2026-01-06'}])
        self.assertEqual(a['rows'][0]['calendar_state'], 'UNKNOWN_NO_CALENDAR')
        self.assertEqual(a['rows'][0]['distinct_event_dates'], 0)
        self.assertFalse(a['full_strategy_data_pass'])
        self.assertEqual(a['actual_pit_admitted_records'], 0)

    def test_no_weekday_gap_inference_without_explicit_calendar(self):
        rows = [rec(day='2026-01-02'), rec(day='2026-01-04')]
        p = build_update_plan(rows, [req()], '2026-01-06')['rows'][0]
        self.assertEqual(p['missing_open_session_dates'], [])
        self.assertFalse(p['gap_detection_complete'])
        self.assertEqual(p['calendar_state'], 'UNKNOWN_NO_CALENDAR')
        self.assertIn('EXPLICIT_CALENDAR_COVERAGE_INCOMPLETE', p['reason_codes'])

    def test_explicit_calendar_extraordinary_open_closed_days_and_field_gap(self):
        # Saturday open; Monday closed. Never derive either from the weekday.
        open_days = {'2026-01-02', '2026-01-03', '2026-01-04', '2026-01-06'}
        calendar = []
        for offset in range(6):
            day = (date(2026, 1, 1)+timedelta(days=offset)).isoformat()
            calendar.append(rec('CALENDAR', day, '*', fields={'cal_date': day.replace('-', ''),
                'exchange': 'SSE', 'is_open': '1' if day in open_days else '0'}))
        incomplete = rec(day='2026-01-04')
        incomplete['fields']['vol'] = None
        p = build_update_plan(calendar + [rec(), incomplete], [req()], '2026-01-06')['rows'][0]
        self.assertEqual(p['missing_open_session_dates'], ['2026-01-03', '2026-01-04', '2026-01-06'])
        self.assertNotIn('2026-01-05', p['missing_open_session_dates'])
        self.assertEqual(p['incomplete_field_dates'], ['2026-01-04'])
        self.assertEqual(p['calendar_state'], 'EXPLICIT_COMPLETE')
        self.assertTrue(p['gap_detection_complete'])
        self.assertFalse(p['calendar_is_historical_pit_admitted'])

    def test_capture_duplicates_not_distinct_observations_or_closed_raw_count(self):
        row = rec()
        p = build_update_plan([row, deepcopy(row), deepcopy(row)], [req()], '2026-01-06')['rows'][0]
        self.assertEqual(p['raw_record_versions'], 3)
        self.assertEqual(p['distinct_event_dates'], 1)
        self.assertEqual(p['field_date_counts']['close'], 1)
        self.assertFalse(p['gap_detection_complete'])

    def test_incremental_collector_overlap_and_history_gap_are_explicit(self):
        requirements = [req(start='2025-11-01', end='2026-02-01')]
        p = build_update_plan([rec(day='2026-01-15')], requirements, '2026-01-31')['rows'][0]
        kinds = {r['kind']: r for r in p['requests']}
        self.assertEqual(kinds['INCREMENTAL']['start'], '2026-01-16')
        self.assertEqual(kinds['REVISION_OVERLAP']['start'], '2025-12-16')
        self.assertEqual(kinds['REVISION_OVERLAP']['lookback_unit'], 'CALENDAR_DAYS')
        self.assertEqual(kinds['INITIAL_HISTORY_GAP']['start'], '2025-11-01')
        self.assertEqual(p['requested_intervals'], [{'start': '2025-11-01', 'end': '2026-01-31'}])
        self.assertFalse(p['collector_overlap_is_pit_guarantee'])

    def test_version_domains_forced_full_sweep_even_after_through_reached(self):
        for domain in ('FINANCIAL_INCOME', 'STATUS', 'INDUSTRY_MEMBERSHIP', 'CATALYST', 'UNIVERSE'):
            requirement = req(domain, fields=['x'])
            row = rec(domain, '2026-01-06', fields={'x':'value'})
            p = build_update_plan([row], [requirement], '2026-01-06')['rows'][0]
            self.assertEqual(p['refresh_mode'], 'FULL_VERSION_SWEEP')
            self.assertEqual(p['requested_intervals'], [{'start':'2026-01-01','end':'2026-01-06'}])
            self.assertTrue(p['requests'][0]['all_available_revisions'])
            self.assertFalse(p['requests'][0]['event_only_safe'])
        for domain in ('STATUS', 'INDUSTRY_MEMBERSHIP', 'UNIVERSE'):
            p = build_update_plan([], [req(domain)], '2026-01-06')['rows'][0]
            self.assertTrue(p['requests'][0]['full_valid_intervals'])

    def test_calendar_version_conflict_is_not_closed_or_open_truth(self):
        one = rec('CALENDAR', '2026-01-02', '*', fields={'cal_date':'20260102','is_open':'1'})
        zero = deepcopy(one)
        zero['fields']['is_open'] = '0'
        p = build_update_plan([one, zero], [req()], '2026-01-06')['rows'][0]
        self.assertEqual(p['calendar_conflict_dates'], ['2026-01-02'])
        self.assertFalse(p['gap_detection_complete'])
        self.assertEqual(p['missing_open_session_dates'], [])

    def test_bad_numeric_ohlc_volume_date_clock_order_report_end(self):
        price = rec()
        price['fields'].update(high='8', vol='-1', close='NaN', trade_date='20260230')
        price['published_at'] = '2026-01-03T10:00:00+08:00'
        price['first_visible_at'] = '2026-01-03T09:00:00+08:00'
        financial = rec('FINANCIAL_INCOME', '2026-03-31', fields={
            'end_date': '20260331', 'ann_date': '20260320', 'revenue': 'bad'})
        dq = validate_records([price, financial])
        codes = {r['code'] for r in dq['errors']}
        self.assertTrue({'NUMBER_NONFINITE', 'NEGATIVE_VOLUME_OR_NOTIONAL', 'INVALID_DATE',
            'OHLC_HIGH_BELOW_COMPONENT', 'CLOCK_ORDER_REVERSED',
            'FINANCIAL_ANNOUNCEMENT_BEFORE_REPORT_END', 'NUMBER_INVALID'} <= codes)
        self.assertEqual(dq['state'], 'INVALID_RECORDS')

    def test_missing_units_date_only_clock_remain_unknown_and_versions_preserved(self):
        a = rec()
        a['published_at'] = '20260102'
        b = deepcopy(a)
        b['revision_id'] = 'r2'
        b['fields']['close'] = '10.10'
        dq = validate_records([a, b])
        self.assertEqual(dq['errors'], [])
        self.assertEqual(dq['conflicts'], [])
        self.assertEqual(len(dq['multiple_versions']), 1)
        self.assertTrue({'FIELD_UNIT_UNRESOLVED', 'DATE_ONLY_CLOCK_NOT_EXACT', 'HISTORICAL_CLOCK_UNKNOWN'} <=
                        {w['code'] for w in dq['warnings']})
        self.assertEqual(dq['actual_pit_admitted_records'], 0)

    def test_same_revision_value_conflict_preserved_and_no_cross_version_field_assembly(self):
        a, b = rec(), rec()
        a['fields']['vol'] = None
        b['fields']['close'] = None
        dq = validate_records([a, b])
        self.assertEqual(dq['state'], 'VERSION_CONFLICT')
        self.assertEqual(dq['error_count'], 0)
        p = build_update_plan([a, b], [req()], '2026-01-06')['rows'][0]
        self.assertEqual(p['missing_fields'], [])
        self.assertEqual(p['complete_field_dates'], 0)
        self.assertEqual(p['incomplete_field_dates'], ['2026-01-02'])

    def test_cross_source_identity_prefixes_do_not_hide_ohlc_conflict(self):
        a = rec(identity='old:daily:20260102')
        b = rec(identity='gateway:2026-01-02')
        b['source'] = 'SECOND_PROVIDER'
        b['fields']['close'] = '10.10'
        b['fields']['vol'] = '10000'
        dq = validate_records([a, b])
        self.assertEqual(dq['state'], 'VERSION_CONFLICT')
        self.assertEqual(dq['cross_source_price_conflicts'][0]['field'], 'close')
        self.assertFalse(dq['cross_source_price_conflicts'][0]['preferred_source_automatically_selected'])
        check = dq['cross_source_volume_checks'][0]
        self.assertEqual(check['state'], 'UNKNOWN_UNITS_NOT_COMPARABLE')
        self.assertFalse(check['absolute_values_compared'])
        p = build_update_plan([a, b], [req()], '2026-01-06')['rows'][0]
        self.assertEqual(p['complete_field_dates'], 0)
        self.assertEqual(p['unreconciled_conflict_dates'], ['2026-01-02'])

    def test_volume_only_different_unknown_units_not_called_conflict_and_exact_clock_count(self):
        a = rec()
        a['first_visible_at'] = '20260102'
        b = deepcopy(a)
        b['source'] = 'OTHER'
        b['fields']['vol'] = '10000'
        dq = validate_records([a, b])
        self.assertEqual(dq['cross_source_price_conflicts'], [])
        self.assertEqual(dq['state'], 'STRUCTURAL_PASS_PIT_UNPROVEN')
        self.assertEqual(dq['cross_source_volume_checks'][0]['state'], 'UNKNOWN_UNITS_NOT_COMPARABLE')
        p = build_update_plan([a, b], [req()], '2026-01-06')['rows'][0]
        self.assertEqual(p['clock_date_counts']['first_visible_at'], 0)
        a['units']['vol'] = b['units']['vol'] = 'LOTS_100_SHARES'
        dq = validate_records([a, b])
        self.assertEqual(dq['cross_source_volume_checks'][0]['state'], 'CROSS_SOURCE_VOLUME_CONFLICT')
        self.assertEqual(dq['state'], 'VERSION_CONFLICT')

    def test_malformed_metadata_and_revision_are_reported_without_crash(self):
        row = rec()
        row.update(domain=None, identity=[], revision_id={'bad': 'revision'}, event_date=['2026-01-02'])
        dq = validate_records([row])
        self.assertEqual(dq['state'], 'INVALID_RECORDS')
        codes = {r['code'] for r in dq['errors']}
        self.assertTrue({'METADATA_STRING_REQUIRED', 'IDENTITY_REQUIRED', 'REVISION_ID_INVALID', 'INVALID_DATE'} <= codes)

    def test_clock_namespaces_do_not_infer_order_between_available_and_first_visible(self):
        row = rec()
        row['published_at'] = '2026-01-02T01:00:00+00:00'
        row['available_at'] = '2026-01-02T02:00:00+00:00'
        row['first_visible_at'] = '2026-01-02T03:00:00+00:00'
        self.assertEqual(validate_records([row])['errors'], [])
        row['first_visible_at'] = '2026-01-02T01:30:00+00:00'
        self.assertEqual(validate_records([row])['errors'], [])


if __name__ == '__main__':
    unittest.main()
