"""Meaningful synthetic financial attacks; no network, credentials or capture writes."""
import copy
import hashlib
import json
import unittest
from wave_b.core import fixture_inputs, observations, require_cutoff, require_result
from wave_b.financial import analyze

T = '2026-10-06T01:00:00Z'
SYMBOL = '603993.SH'
PERIOD = '20260630'
FIELDS = ['ts_code', 'ann_date', 'end_date', 'eps', 'roe', 'debt_to_assets', 'netprofit_yoy', 'update_flag']


def hashed(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def row(period=PERIOD, announcement='20260825', eps='0.31', flag='1', **extra):
    return {'ts_code': SYMBOL, 'end_date': period, 'ann_date': announcement,
            'eps': eps, 'roe': '2.5000', 'debt_to_assets': '40.01', 'netprofit_yoy': '-3.12',
            'update_flag': flag, **extra}


def request(rows=None, request_id='SYNTHETIC-FINANCIAL', period=PERIOD, blocked=False, **extra):
    return {'request_id': request_id, 'api_name': 'fina_indicator', 'ts_code': SYMBOL,
            'params': {'ts_code': SYMBOL, 'period': period}, 'fields': FIELDS,
            'date_scope': {'key': 'end_date', 'start': period, 'end': period},
            'response_blocked': blocked, 'reason_codes': ['SYNTHETIC_UPSTREAM_BLOCK'] if blocked else [],
            'rows': [{'values': values} for values in (rows if rows is not None else [row(period=period)])], **extra}


def legacy_request(rows=None, request_id='SYNTHETIC-OLD', blocked=False):
    rows = rows if rows is not None else [row()]
    return {'request_id': request_id, 'api_name': 'fina_indicator', 'ts_code': SYMBOL,
            'params': {'ts_code': SYMBOL, 'start_date': '20230101', 'end_date': '20261005'},
            'date_scope': {'key': 'end_date', 'start': '20230101', 'end': '20261005'},
            'response_dq': 'BLOCKED' if blocked else 'PASS',
            'response_dq_reasons': ['DATE_SCOPE_MISMATCH'] if blocked else [],
            'retrieved_at': T, 'available_at': T, 'published_at': None,
            'raw_sha256': hashed({'legacy': rows}), 'request_fingerprint': hashed({'id': request_id}),
            'rows': [{'row_ordinal': index, 'typed_fields': {name: {'value': value} for name, value in values.items()}} for index, values in enumerate(rows)]}


def revision(result):
    return result['body']['financial_revision_candidate']


def ranges(result):
    return result['body']['financial_range_semantics']


class FinancialCandidateTests(unittest.TestCase):
    def test_date_only_no_midnight_and_missing_f_ann_stays_unavailable(self):
        result = analyze(fixture_inputs(new_requests=[request()]))
        observation = revision(result)['observations'][0]
        self.assertEqual(observation['source_ann_date'], '20260825')
        self.assertEqual(observation['source_ann_date_precision'], 'DATE_ONLY')
        self.assertIsNone(observation['published_at'])
        self.assertIsNone(observation['source_f_ann_date'])
        self.assertEqual(observation['f_ann_date_state'], 'NOT_REQUESTED_OR_NOT_PROVIDED')
        self.assertFalse(observation['f_ann_date_requested'])
        self.assertEqual(observation['available_at'], T)
        self.assertEqual(observation['retrieved_at'], T)
        self.assertFalse(result['historical_visibility_proven'])
        self.assertFalse(result['productionGate'])
        self.assertEqual(result['source_admission'], 'BLOCKED')

    def test_f_ann_only_preserved_when_source_actually_supplies_literal(self):
        result = analyze(fixture_inputs(new_requests=[request(rows=[row(f_ann_date='20260901')])]))
        item = revision(result)['observations'][0]
        self.assertEqual(item['source_f_ann_date'], '20260901')
        self.assertEqual(item['source_f_ann_date_precision'], 'DATE_ONLY')
        self.assertFalse(item['f_ann_date_requested'])
        self.assertIsNone(item['published_at'])
        self.assertEqual(item['available_at'], T)

    def test_one_out_of_scope_row_blocks_whole_response_without_dropping_valid_sibling(self):
        result = analyze(fixture_inputs(new_requests=[request(rows=[row(), row(period='20250331')])]))
        items = revision(result)['observations']
        self.assertEqual(len(items), 2)
        self.assertTrue(items[0]['period_within_request_scope'])
        self.assertFalse(items[1]['period_within_request_scope'])
        self.assertTrue(all(item['whole_response_blocked'] for item in items))
        self.assertEqual(ranges(result)['requests'][0]['out_of_scope_row_count'], 1)
        self.assertEqual(revision(result)['origin_counts']['new']['whole_blocked_observation_count'], 2)

    def test_report_period_not_announcement_semantics_in_range(self):
        q = request(rows=[row(period='20250331', announcement='20250825'),
                          row(period='20250630', announcement='20260101')])
        q['params'] = {'ts_code': SYMBOL, 'start_date': '20250601', 'end_date': '20261005'}
        q['date_scope'] = {'key': 'end_date', 'start': '20250601', 'end': '20261005'}
        result = analyze(fixture_inputs(new_requests=[q]))
        items = revision(result)['observations']
        self.assertFalse(items[0]['period_within_request_scope'])
        self.assertTrue(items[1]['period_within_request_scope'])
        self.assertEqual(ranges(result)['filter_semantics'], 'REPORT_PERIOD_NOT_ANN_DATE')
        self.assertFalse(ranges(result)['announcement_time_filter_proven'])

    def test_preserve_old_scope_failures_and_whole_blocked_rows_for_comparison(self):
        old = legacy_request(rows=[row(period='20221231'), row()], blocked=True)
        result = analyze(fixture_inputs(legacy_requests=[old], new_requests=[request()]))
        counts = revision(result)['origin_counts']
        self.assertEqual(counts['legacy']['observation_count'], 2)
        self.assertEqual(counts['legacy']['scope_failure_observation_count'], 1)
        self.assertEqual(counts['legacy']['whole_blocked_response_count'], 1)
        self.assertEqual(counts['legacy']['whole_blocked_observation_count'], 2)
        self.assertEqual(counts['new']['observation_count'], 1)
        self.assertEqual(len(revision(result)['observations']), 3)
        self.assertEqual(ranges(result)['requests'][0]['upstream_reason_codes_preserved'], ['DATE_SCOPE_MISMATCH'])

    def test_revision_graph_preserves_flag_changes_metric_changes_and_all_raw_versions(self):
        old = legacy_request(rows=[row(flag='1', eps='0.31'), row(flag='0', eps='0.32')])
        new = request(rows=[row(flag='0', eps='0.31')])
        result = analyze(fixture_inputs(legacy_requests=[old], new_requests=[new]))
        group = revision(result)['observed_revision_graph'][0]
        self.assertEqual(group['observation_count'], 3)
        self.assertEqual(group['distinct_observed_values_versions'], 3)
        self.assertEqual(group['distinct_metric_versions'], 2)
        self.assertEqual(len(group['versions']), 3)
        self.assertEqual(len(group['observed_relations']), 3)
        self.assertEqual(group['revision_chronology'], 'UNKNOWN')
        self.assertFalse(group['update_flag_is_chronology'])
        self.assertFalse(group['old_versions_overwritten'])
        self.assertFalse(group['duplicate_source_references_collapsed'])
        self.assertEqual(group['versions'][0]['source_update_flag'], '1')
        self.assertEqual(group['versions'][1]['source_update_flag'], '0')

    def test_identical_metric_values_never_collapse_duplicate_source_references(self):
        q = request(rows=[row(), row()], raw_sha256=hashed({'capture': 1}))
        r = request(rows=[row()], request_id='SYNTHETIC-SECOND', raw_sha256=hashed({'capture': 2}))
        result = analyze(fixture_inputs(new_requests=[q, r]))
        group = revision(result)['observed_revision_graph'][0]
        self.assertEqual(group['observation_count'], 3)
        self.assertEqual(group['distinct_metric_versions'], 1)
        self.assertEqual(len(set(group['observation_ids'])), 3)
        self.assertEqual([v['raw_row_ref']['row_ordinal'] for v in group['versions']], [0, 1, 0])

    def test_inputs_copied_mutated_or_permission_promoted_rejected(self):
        original = fixture_inputs(new_requests=[request()])
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_OR_MUTATED_INPUT'):
            analyze(copy.deepcopy(original))
        original['new'][0]['rows'][0]['values']['eps'] = '999'
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_OR_MUTATED_INPUT'):
            analyze(original)
        promoted = fixture_inputs(new_requests=[request()])
        promoted['source_admission'] = 'ADMITTED'
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_OR_MUTATED_INPUT'):
            analyze(promoted)

    def test_output_mutation_does_not_mutate_registered_inputs_and_invalidates_result(self):
        inputs = fixture_inputs(new_requests=[request()])
        result = analyze(inputs)
        revision(result)['observations'][0]['source_values']['eps'] = '777'
        self.assertEqual(observations(inputs, 'fina_indicator')[0]['values']['eps'], '0.31')
        with self.assertRaisesRegex(ValueError, 'CANDIDATE_VERSION_INVALIDATED'):
            require_result(result)
        self.assertEqual(revision(analyze(inputs))['observations'][0]['source_values']['eps'], '0.31')

    def test_capture_instant_cutoff_rejects_future_and_historical_query_remains_unknown(self):
        inputs = fixture_inputs(new_requests=[request()])
        observation = observations(inputs, 'fina_indicator')[0]
        with self.assertRaisesRegex(ValueError, 'OBSERVATION_NOT_AVAILABLE_AT_CUTOFF'):
            require_cutoff(observation, '2026-10-06T00:59:59Z')
        self.assertIs(require_cutoff(observation, T), observation)
        query = revision(analyze(inputs))['historical_cutoff_query']
        self.assertFalse(query['allowed'])
        self.assertEqual(query['state'], 'UNKNOWN')

    def test_future_ann_or_f_ann_literal_blocks_complete_response_and_preserves_raw(self):
        for field in ('ann_date', 'f_ann_date'):
            q = request(rows=[row(), row(**{field: '20261007'})])
            result = analyze(fixture_inputs(new_requests=[q]))
            items = revision(result)['observations']
            self.assertEqual(len(items), 2)
            self.assertFalse(items[0]['source_future_publication_literal'])
            self.assertTrue(items[1]['source_future_publication_literal'])
            self.assertTrue(all(item['whole_response_blocked'] for item in items))
            self.assertIsNone(items[1]['published_at'])
            self.assertEqual(ranges(result)['requests'][0]['future_publication_literal_row_count'], 1)

    def test_stable_result_hash_and_changed_raw_source_invalidate_identity(self):
        first = fixture_inputs(new_requests=[request()])
        a, b = analyze(first), analyze(first)
        self.assertEqual(a['content_hash'], b['content_hash'])
        self.assertEqual(a['input_identity'], b['input_identity'])
        different = fixture_inputs(new_requests=[request(raw_sha256=hashed({'changed_source_byte': True}))])
        c = analyze(different)
        self.assertNotEqual(a['input_identity'], c['input_identity'])
        self.assertNotEqual(a['content_hash'], c['content_hash'])
        self.assertNotEqual(revision(a)['observations'][0]['observation_id'], revision(c)['observations'][0]['observation_id'])
        self.assertEqual(revision(a)['observations'][0]['metric_hash'], revision(c)['observations'][0]['metric_hash'])

    def test_empty_response_never_proves_no_financial_revision_or_filter_correctness(self):
        result = analyze(fixture_inputs(new_requests=[request(rows=[])]))
        self.assertEqual(revision(result)['combined_observation_count'], 0)
        self.assertEqual(ranges(result)['requests'][0]['scope_evaluation'], 'EMPTY_IS_NOT_FILTER_PROOF')
        self.assertFalse(ranges(result)['provider_filter_repaired'])
        self.assertEqual(result['source_admission'], 'BLOCKED')

    def test_decimal_literals_lossless_and_invalid_numbers_or_dates_rejected(self):
        values = [row(eps='0.3100'), row(eps='0.31')]
        result = analyze(fixture_inputs(new_requests=[request(rows=values)]))
        self.assertEqual([o['metrics']['eps'] for o in revision(result)['observations']], ['0.3100', '0.31'])
        for value in ('NaN', 'Infinity', '1E999'):
            with self.assertRaisesRegex(ValueError, 'FINANCIAL_DECIMAL_INVALID'):
                analyze(fixture_inputs(new_requests=[request(rows=[row(eps=value)])]))
        with self.assertRaisesRegex(ValueError, 'FINANCIAL_DECIMAL_STRING_REQUIRED'):
            analyze(fixture_inputs(new_requests=[request(rows=[row(eps=5)])]))
        with self.assertRaisesRegex(ValueError, 'FINANCIAL_DATE_ONLY_LITERAL_INVALID'):
            analyze(fixture_inputs(new_requests=[request(rows=[row(announcement='20260230')])]))

    def test_new_query_window_and_filter_contract_cannot_be_widened(self):
        for q in [request(period='20250331'),
                  request(params={'ts_code': SYMBOL, 'start_date': '20230101', 'end_date': '20261005'},
                          date_scope={'key': 'end_date', 'start': '20230101', 'end': '20261005'}),
                  request(date_scope={'key': 'ann_date', 'start': PERIOD, 'end': PERIOD})]:
            with self.assertRaisesRegex(ValueError, 'FINANCIAL_NEW_REQUEST_WINDOW_INVALID|FINANCIAL_REPORT_PERIOD_SCOPE_REQUIRED'):
                analyze(fixture_inputs(new_requests=[q]))

    def test_all_six_exact_quarterly_probe_scopes_and_three_range_queries_counted_separately(self):
        periods = ('20250630', '20250930', '20251231', '20260331', '20260630', '20260930')
        qs = [request(request_id=f'SYNTHETIC-PERIOD-{p}', period=p, rows=[row(period=p)]) for p in periods]
        qs.extend(request(request_id=f'SYNTHETIC-RANGE-{i}', rows=[],
                          params={'ts_code': SYMBOL, 'start_date': '20250601', 'end_date': '20261005'},
                          date_scope={'key': 'end_date', 'start': '20250601', 'end': '20261005'}) for i in range(3))
        result = analyze(fixture_inputs(new_requests=qs))
        self.assertEqual(ranges(result)['new_narrow_period_request_count'], 6)
        self.assertEqual(ranges(result)['new_range_request_count'], 3)
        self.assertEqual(ranges(result)['new_observed_requested_periods'], sorted(periods))
        self.assertEqual(ranges(result)['new_probe_coverage_by_symbol'][0]['missing_expected_period_probes'], [])
        self.assertFalse(ranges(result)['new_probe_coverage_by_symbol'][0]['data_completeness_proven'])

    def test_synthetic_clock_backfill_and_fake_midnight_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'CLOCK_BACKFILL_FORBIDDEN'):
            fixture_inputs(new_requests=[request(available_at='2026-08-25T00:00:00Z')])
        with self.assertRaisesRegex(ValueError, 'CLOCK_BACKFILL_FORBIDDEN'):
            fixture_inputs(new_requests=[request(published_at='2026-08-25T00:00:00Z')])


if __name__ == '__main__':
    unittest.main()
