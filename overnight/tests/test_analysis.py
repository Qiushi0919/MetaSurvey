import copy
import unittest
from overnight.analysis.reconcile import analyze_reconciliation
from overnight.analysis.financial import analyze_financial
from overnight.analysis.inputs import AnalysisError, assert_dataset, instant_ns

SYMBOL = '603993.SH'
COMPLETED = '2026-10-05T12:00:00.000000001Z'

def row(i, fields):
    return {'row_ordinal': i, 'state': 'QUARANTINED',
            'typed_fields': {k: {'kind': 'NULL' if v is None else 'SOURCE_LITERAL', 'value': None if v is None else str(v)} for k, v in fields.items()}}

def request(api, rows, scope=None):
    return {'api_name': api, 'scope': 'COVERAGE', 'ts_code': SYMBOL,
            'request_fingerprint': 'synthetic:' + api, 'raw_sha256': 'sha256:' + '1' * 64,
            'report_sha256': 'sha256:' + '2' * 64, 'request_started_at': '2026-10-05T12:00:00.000000000Z',
            'response_completed_at': COMPLETED, 'available_at': COMPLETED, 'retrieved_at': COMPLETED,
            'published_at': None, 'response_dq': 'PASS', 'response_dq_reasons': [], 'date_scope': scope,
            'price_adjustment': 'RAW_UNADJUSTED_OHLC_PROVIDER_PRE_CLOSE_EX_RIGHTS' if api == 'daily' else 'FACTOR_ONLY_NO_ADJUSTED_PRICES',
            'rows': rows}

def dataset(requests):
    return {'fixture': True, 'provenance': 'SYNTHETIC', 'productionGate': False, 'namespace': 'CORE_40', 'state': 'QUARANTINED',
            'source_admission': 'BLOCKED', 'historical_visibility_proven': False, 'requests': requests}

def prices(action=True):
    bars = [row(0, dict(ts_code=SYMBOL, trade_date='20261001', open='0.3', high='0.4', low='0.2', close='0.3', pre_close='0.3')),
            row(1, dict(ts_code=SYMBOL, trade_date='20261002', open='0.2', high='0.3', low='0.1', close='0.2', pre_close='0.2'))]
    factors = [row(0, dict(ts_code=SYMBOL, trade_date='20261001', adj_factor='2')),
               row(1, dict(ts_code=SYMBOL, trade_date='20261002', adj_factor='3'))]
    actions = [row(0, dict(ts_code=SYMBOL, div_proc='实施', ex_date='20261002', ann_date='20260930', imp_ann_date='20261001', stk_div='0', cash_div_tax='0.1', cash_div='0.08'))] if action else []
    return dataset([request('daily', bars), request('adj_factor', factors), request('dividend', actions)])

def financial():
    rows = [row(0, dict(ts_code=SYMBOL, end_date='20221231', ann_date='20230318', eps='1.20', roe='10', update_flag='0')),
            row(1, dict(ts_code=SYMBOL, end_date='20230331', ann_date='20230429', eps='0.3', roe='9', update_flag='0')),
            row(2, dict(ts_code=SYMBOL, end_date='20230331', ann_date='20230429', eps='0.3', roe='9', update_flag='1')),
            row(3, dict(ts_code=SYMBOL, end_date='20230331', ann_date='20230501', eps='0.4', roe='9', update_flag='1'))]
    q = request('fina_indicator', rows, {'key': 'end_date', 'start': '20230101', 'end': '20261005'})
    q['response_dq'] = 'BLOCKED'; q['response_dq_reasons'] = ['DATE_SCOPE_MISMATCH']
    return dataset([q])

class AnalysisTests(unittest.TestCase):
    def test_exact_factor_math_retains_raw_and_uses_rational_not_float(self):
        source = prices(); before = copy.deepcopy(source); result = analyze_reconciliation(source)
        self.assertEqual(source, before)
        first = result['symbols'][0]['diagnostic_normalized_prices'][0]['diagnostic_exact_price_ratios']['close']
        self.assertEqual(first, {'numerator': '1', 'denominator': '5'})
        self.assertFalse(result['adjusted_prices_published_as_source'])
        self.assertFalse(result['productionGate'])

    def test_change_point_links_original_terms_without_inventing_action(self):
        result = analyze_reconciliation(prices())['symbols'][0]
        self.assertEqual(len(result['change_points']), 1)
        entry = result['change_points'][0]
        self.assertEqual(entry['source_terms'][0]['cash_div_tax'], '0.1')
        self.assertEqual(entry['source_terms'][0]['cash_div'], '0.08')
        self.assertEqual(entry['inferred_corporate_actions_created'], 0)
        self.assertFalse(result['action_entitlement_ledger_reconstructed'])

    def test_missing_action_original_remains_gap_partial(self):
        result = analyze_reconciliation(prices(False))['symbols'][0]
        self.assertEqual(len(result['action_required_gaps']), 1)
        self.assertEqual(result['change_points'][0]['link_status'], 'ACTION_EVIDENCE_MISSING')

    def test_factor_date_mismatch_cannot_join_by_position(self):
        source = prices(); source['requests'][1]['rows'][1]['typed_fields']['trade_date']['value'] = '20261003'
        with self.assertRaisesRegex(AnalysisError, 'FACTOR_BAR_DATE_MISMATCH'):
            analyze_reconciliation(source)

    def test_duplicate_factor_date_rejected(self):
        source = prices(); source['requests'][1]['rows'].append(copy.deepcopy(source['requests'][1]['rows'][0]))
        with self.assertRaisesRegex(AnalysisError, 'DUPLICATE_PRICE_OR_FACTOR_DATE'):
            analyze_reconciliation(source)

    def test_zero_negative_nonfinite_and_float_factors_rejected(self):
        for v in ('0', '-1', 'NaN', 'Infinity', 0.5):
            source = prices(); source['requests'][1]['rows'][0]['typed_fields']['adj_factor']['value'] = v
            with self.assertRaises(AnalysisError):
                analyze_reconciliation(source)

    def test_nonzero_preclose_delta_does_not_gain_guessed_tolerance(self):
        source = prices(); source['requests'][0]['rows'][1]['typed_fields']['pre_close']['value'] = '0.1999'
        result = analyze_reconciliation(source)['symbols'][0]
        self.assertEqual(result['nonzero_reference_deltas'], 1)
        self.assertEqual(result['rounding_tolerance'], 'UNSET_REQUIRED')

    def test_scope_is_report_period_not_announcement(self):
        result = analyze_financial(financial())
        self.assertEqual(len(result['observations']), 4)
        first = result['observations'][0]
        self.assertFalse(first['period_within_requested_scope'])
        self.assertEqual(first['ann_date'], '20230318')
        self.assertEqual(first['state'], 'QUARANTINED')
        self.assertEqual(len(result['requests'][0]['out_of_scope_refs']), 1)

    def test_all_in_scope_rows_of_blocked_response_remain_quarantined(self):
        result = analyze_financial(financial())
        self.assertTrue(all(r['state'] == 'QUARANTINED' and r['request_dq'] == 'BLOCKED' for r in result['observations']))
        self.assertEqual(result['source_admission'], 'BLOCKED')

    def test_source_flag_only_version_is_not_metric_or_historical_revision_proof(self):
        result = analyze_financial(financial())
        group = next(g for g in result['revision_groups'] if g['report_period'] == '20230331')
        self.assertEqual(group['observation_count'], 3)
        self.assertEqual(group['distinct_observed_versions'], 3)
        self.assertEqual(group['distinct_metric_versions'], 2)
        self.assertFalse(group['version_chronology_proven'])
        self.assertFalse(group['availability_inferred_from_flag_or_date'])

    def test_same_period_future_revision_publication_blocked(self):
        for field in ('ann_date', 'f_ann_date'):
            source = financial(); source['requests'][0]['rows'][3]['typed_fields'][field] = {'kind': 'DATE_ONLY', 'value': '20261006'}
            with self.assertRaisesRegex(AnalysisError, 'FUTURE_PUBLICATION'):
                analyze_financial(source)

    def test_future_implementation_publication_blocked_but_future_exdate_allowed(self):
        source = prices(); source['requests'][2]['rows'][0]['typed_fields']['ex_date']['value'] = '20261006'
        self.assertEqual(len(analyze_reconciliation(source)['symbols'][0]['action_required_gaps']), 1)
        source['requests'][2]['rows'][0]['typed_fields']['imp_ann_date']['value'] = '20261006'
        with self.assertRaisesRegex(AnalysisError, 'FUTURE_PUBLICATION'):
            analyze_reconciliation(source)

    def test_date_only_never_becomes_midnight_or_historical_availability(self):
        result = analyze_financial(financial())
        self.assertTrue(all(r['published_at'] is None and r['available_at'] == COMPLETED for r in result['observations']))
        source = financial(); source['requests'][0]['rows'][0]['typed_fields']['ann_date']['value'] = '2023-03-18T00:00:00+08:00'
        with self.assertRaisesRegex(AnalysisError, 'DATE_ONLY_LITERAL_REQUIRED'):
            analyze_financial(source)

    def test_available_retrieved_spoof_and_nanosecond_order_rejected(self):
        for field in ('available_at', 'retrieved_at'):
            source = prices(); source['requests'][0][field] = '2025-01-01T00:00:00Z'
            with self.assertRaisesRegex(AnalysisError, 'CAPTURE_CLOCK_SPOOF'):
                analyze_reconciliation(source)
        source = prices(); source['requests'][0]['request_started_at'] = '2026-10-05T12:00:00.000000002Z'
        with self.assertRaisesRegex(AnalysisError, 'CAPTURE_CLOCK_SPOOF'):
            analyze_reconciliation(source)
        self.assertEqual(instant_ns('2026-10-05T12:00:00.000000001Z'), instant_ns('2026-10-05T20:00:00.000000001+08:00'))

    def test_namespace_symbol_and_raw_adjusted_contamination_rejected(self):
        for modify in (lambda d: d.update(namespace='EVENT_3'),
                       lambda d: d['requests'][0].update(ts_code='000001.SZ'),
                       lambda d: d['requests'][0].update(price_adjustment='QFQ')):
            source = prices(); modify(source)
            with self.assertRaises(AnalysisError):
                analyze_reconciliation(source)

    def test_quarantine_promotion_and_fake_real_inventory_rejected(self):
        for modify in (lambda d: d.update(source_admission='ADMITTED'),
                       lambda d: d.update(historical_visibility_proven=True),
                       lambda d: d.update(fixture=False),
                       lambda d: d['requests'][0]['rows'][0].update(state='ADMITTED')):
            source = prices(); modify(source)
            with self.assertRaises(AnalysisError):
                assert_dataset(source)

    def test_duplicate_api_scope_cannot_silently_replace_original_request(self):
        source = prices(); duplicate = copy.deepcopy(source['requests'][1])
        duplicate['request_fingerprint'] += ':other'; source['requests'].append(duplicate)
        with self.assertRaisesRegex(AnalysisError, 'DUPLICATE_API_SYMBOL_SCOPE'):
            analyze_reconciliation(source)

    def test_real_dataset_requires_registered_exact_bytes_not_44_labels(self):
        source = prices(); source['fixture'] = False
        source['requests'] = [copy.deepcopy(source['requests'][0]) for _ in range(44)]
        with self.assertRaisesRegex(AnalysisError, 'REAL_DATASET_UNREGISTERED_OR_MUTATED'):
            assert_dataset(source)

if __name__ == '__main__':
    unittest.main()
