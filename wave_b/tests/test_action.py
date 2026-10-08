"""Synthetic-only action/factor boundary and exact-original regression tests."""
import copy
from decimal import localcontext
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wave_b.action import analyze
from wave_b.core import fixture_inputs, observations, reject_real_consumer, require_cutoff, require_result


SYMBOL = '603993.SH'
RETRIEVED = '2026-10-06T01:00:00Z'
PREVIOUS, DAY = '20250626', '20250627'


def legacy_request(api, values, *, identity=None, blocked=False):
    identity = identity or 'SYNTHETIC-LEGACY-' + api
    raw = json.dumps({'fixture': True, 'api': api, 'identity': identity, 'values': values}, sort_keys=True).encode()
    return {'request_id': identity, 'api_name': api, 'scope': 'COVERAGE', 'ts_code': SYMBOL,
            'params': {'ts_code': SYMBOL, 'start_date': '20250601', 'end_date': '20261005'},
            'date_scope': {'key': 'trade_date', 'start': '20250601', 'end': '20261005'},
            'raw_sha256': 'sha256:' + hashlib.sha256(raw).hexdigest(),
            'request_fingerprint': 'sha256:' + hashlib.sha256(identity.encode()).hexdigest(),
            'retrieved_at': RETRIEVED, 'available_at': RETRIEVED, 'published_at': None,
            'response_dq': 'BLOCKED' if blocked else 'PASS', 'response_dq_reasons': [],
            'rows': [{'row_ordinal': i, 'typed_fields': {k: {'value': v} for k, v in row.items()}}
                     for i, row in enumerate(values)]}


def action_values(**changes):
    values = {'ts_code': SYMBOL, 'ann_date': '20250401', 'imp_ann_date': '20250620',
              'record_date': PREVIOUS, 'ex_date': DAY, 'pay_date': '20250630',
              'end_date': '20241231', 'div_proc': '实施', 'cash_div': '0.08',
              'cash_div_tax': '0.1', 'stk_div': '0', 'stk_bo_rate': None, 'stk_co_rate': None}
    values.update(changes)
    return values


def new_request(api, values, *, day=DAY, blocked=False):
    field = 'trade_date' if api == 'adj_factor' else 'ex_date'
    return {'api_name': api, 'ts_code': SYMBOL, 'params': {'ts_code': SYMBOL, field: day},
            'date_scope': {'key': field, 'start': day, 'end': day},
            'response_blocked': blocked, 'reason_codes': ['SYNTHETIC_BLOCKED'] if blocked else [],
            'rows': [{'values': row} for row in values]}


def requests(actions=None):
    if actions is None:
        actions = [action_values()]
    bars = [{'ts_code': SYMBOL, 'trade_date': PREVIOUS, 'open': '0.3', 'high': '0.4',
             'low': '0.2', 'close': '0.3', 'pre_close': '0.3'},
            {'ts_code': SYMBOL, 'trade_date': DAY, 'open': '0.2', 'high': '0.3',
             'low': '0.1', 'close': '0.2', 'pre_close': '0.2'}]
    factors = [{'ts_code': SYMBOL, 'trade_date': PREVIOUS, 'adj_factor': '2'},
               {'ts_code': SYMBOL, 'trade_date': DAY, 'adj_factor': '3'}]
    return [legacy_request('daily', bars), legacy_request('adj_factor', factors),
            legacy_request('dividend', actions)]


def inputs(actions=None, new=None, legacy=None):
    if new is None:
        new = [new_request('adj_factor', [{'ts_code': SYMBOL, 'trade_date': DAY, 'adj_factor': '3'}]),
               new_request('dividend', [action_values()])]
    return fixture_inputs(legacy_requests=legacy or requests(actions), new_requests=new)


def sections(source):
    return analyze(source)['body']


class ActionTests(unittest.TestCase):
    def test_exact_fraction_has_no_context_rounding_or_float(self):
        with localcontext() as ctx:
            ctx.prec = 2
            result = sections(inputs())['factor_action_reconciliation']
        point = result['change_points'][0]
        self.assertEqual(point['exact_change_ratio'], {'numerator': '3', 'denominator': '2'})
        self.assertEqual(point['pre_close_factor_reference']['diagnostic_exact_factor_reference'],
                         {'numerator': '1', 'denominator': '5'})
        self.assertTrue(point['pre_close_factor_reference']['exact_equality'])

    def test_multiple_announcements_never_merge_equal_economic_terms(self):
        result = sections(inputs([action_values(), action_values(ann_date='20250501')]))
        case = result['ambiguous_action_cases']['cases'][0]
        self.assertEqual(case['original_row_count'], 2)
        self.assertEqual(case['different_source_fields'], ['ann_date'])
        self.assertFalse(case['resolved'])
        self.assertFalse(case['economic_terms_aggregated'])
        self.assertEqual([o['ref']['row_ordinal'] for o in case['originals']], [0, 1])

    def test_identical_original_rows_keep_two_ordinals_and_ambiguity(self):
        result = sections(inputs([action_values(), action_values()]))
        case = result['ambiguous_action_cases']['cases'][0]
        self.assertEqual(case['original_row_count'], 2)
        self.assertEqual(case['different_source_fields'], [])
        self.assertFalse(case['rows_merged_deduplicated_or_replaced'])

    def test_single_new_match_cannot_erase_second_legacy_original(self):
        result = sections(inputs([action_values(), action_values(ann_date='20250501')]))
        point = result['factor_action_reconciliation']['change_points'][0]
        self.assertEqual(point['status'], 'AMBIGUOUS')
        self.assertEqual(len(point['legacy_implemented_actions']), 2)
        self.assertEqual(len(point['new_same_date_action_rows']), 1)
        self.assertEqual(len(point['new_action_comparisons'][0]['exact_full_field_matches']), 1)
        self.assertFalse(point['new_action_comparisons'][0]['independent_source_or_historical_visibility_proof'])

    def test_missing_legacy_action_cannot_be_inferred_from_factor_or_new_row(self):
        result = sections(inputs([]))
        point = result['factor_action_reconciliation']['change_points'][0]
        self.assertEqual(point['status'], 'UNKNOWN')
        self.assertEqual(point['inferred_corporate_actions_created'], 0)
        self.assertIn('LEGACY_IMPLEMENTED_ACTION_ORIGINAL_MISSING',
                      [g['reason'] for g in result['adjustment_known_gaps']['gaps']])

    def test_mismatched_factor_and_bar_dates_cannot_join_by_position(self):
        legacy = requests()
        legacy[1]['rows'][1]['typed_fields']['trade_date']['value'] = '20250630'
        with self.assertRaisesRegex(ValueError, 'ACTION_FACTOR_BAR_DATE_MISMATCH'):
            analyze(inputs(legacy=legacy))

    def test_new_wrong_factor_date_rejected_instead_of_relabelled(self):
        new = [new_request('adj_factor', [{'ts_code': SYMBOL, 'trade_date': '20250630', 'adj_factor': '3'}])]
        with self.assertRaisesRegex(ValueError, 'ACTION_TARGET_FACTOR_DATE_MISMATCH'):
            analyze(inputs(new=new))

    def test_new_wrong_ex_date_rejected_instead_of_merged(self):
        new = [new_request('dividend', [action_values(ex_date='20250630')])]
        with self.assertRaisesRegex(ValueError, 'ACTION_TARGET_EX_DATE_MISMATCH'):
            analyze(inputs(new=new))

    def test_duplicate_legacy_factor_date_is_not_silently_overwritten(self):
        legacy = requests()
        legacy[1]['rows'].append(copy.deepcopy(legacy[1]['rows'][0]))
        with self.assertRaisesRegex(ValueError, 'ACTION_DUPLICATE_BAR_OR_FACTOR_DATE'):
            analyze(inputs(legacy=legacy))

    def test_future_announcement_and_implementation_publication_block(self):
        for field in ('ann_date', 'imp_ann_date'):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, 'ACTION_FUTURE_PUBLICATION'):
                    analyze(inputs([action_values(**{field: '20261007'})]))

    def test_capture_local_day_can_cross_utc_day_without_midnight_guess(self):
        legacy = requests([action_values(ann_date='20261006')])
        for q in legacy:
            q['retrieved_at'] = q['available_at'] = '2026-10-05T16:01:00Z'
        point = sections(inputs(legacy=legacy))['factor_action_reconciliation']['change_points'][0]
        row = point['legacy_implemented_actions'][0]
        self.assertEqual(row['values']['ann_date'], '20261006')
        self.assertEqual(row['ref']['retrieved_at'], '2026-10-05T16:01:00Z')
        self.assertIsNone(row['ref']['published_at'])

    def test_future_effective_date_is_preserved_without_future_publication_inference(self):
        row = action_values(ex_date='20261007', record_date='20261006')
        result = sections(inputs([row], new=[]))['factor_action_reconciliation']
        self.assertEqual(result['legacy_action_originals'][0]['values']['ex_date'], '20261007')
        self.assertEqual(result['change_points'][0]['status'], 'UNKNOWN')

    def test_date_and_all_source_clocks_remain_separate(self):
        row = sections(inputs())['factor_action_reconciliation']['change_points'][0]['legacy_implemented_actions'][0]
        self.assertEqual(row['values']['ann_date'], '20250401')
        self.assertEqual(row['values']['imp_ann_date'], '20250620')
        self.assertEqual(row['values']['record_date'], PREVIOUS)
        self.assertEqual(row['values']['ex_date'], DAY)
        self.assertEqual(row['ref']['retrieved_at'], RETRIEVED)
        self.assertEqual(row['ref']['available_at'], RETRIEVED)
        self.assertIsNone(row['ref']['published_at'])
        self.assertRegex(row['ref']['raw_sha256'], '^sha256:[0-9a-f]{64}$')

    def test_backfilled_available_clock_rejected(self):
        legacy = requests()
        legacy[2]['available_at'] = '2025-06-20T00:00:00Z'
        with self.assertRaisesRegex(ValueError, 'ACTION_CURRENT_OBSERVATION_CLOCK_REQUIRED'):
            analyze(inputs(legacy=legacy))

    def test_cutoff_before_current_observation_does_not_gain_historical_visibility(self):
        source = inputs()
        row = observations(source, 'dividend', origin='new')[0]
        with self.assertRaisesRegex(ValueError, 'OBSERVATION_NOT_AVAILABLE_AT_CUTOFF'):
            require_cutoff(row, '2025-06-20T00:00:00Z')
        result = analyze(source)
        self.assertFalse(result['historical_visibility_proven'])
        self.assertFalse(result['body']['adjustment_known_gaps']['historical_backtest_ready'])

    def test_copied_or_mutated_observation_cannot_forge_historical_cutoff(self):
        source = inputs()
        row = observations(source, 'dividend', origin='new')[0]
        self.assertIs(require_cutoff(row, RETRIEVED), row)
        copied = copy.deepcopy(row)
        copied['ref']['available_at'] = '2025-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_OR_MUTATED_OBSERVATION'):
            require_cutoff(copied, '2025-06-27T00:00:00Z')
        row['ref']['available_at'] = '2025-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_OR_MUTATED_OBSERVATION'):
            require_cutoff(row, '2025-06-27T00:00:00Z')

    def test_registered_observation_cannot_survive_parent_input_mutation(self):
        source = inputs()
        row = observations(source, 'dividend', origin='new')[0]
        source['new'][1]['rows'][0]['values']['ann_date'] = '20250501'
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_OR_MUTATED_INPUT'):
            require_cutoff(row, RETRIEVED)

    def test_nonzero_exact_delta_remains_gap_without_tolerance(self):
        legacy = requests()
        legacy[0]['rows'][1]['typed_fields']['pre_close']['value'] = '0.1999999999999999'
        gaps = sections(inputs(legacy=legacy))['adjustment_known_gaps']
        self.assertEqual(gaps['nonzero_reference_delta_count'], 1)
        self.assertEqual(gaps['nonzero_reference_deltas'][0]['exact_delta'],
                         {'numerator': '-1', 'denominator': '10000000000000000'})
        self.assertEqual(gaps['rounding_tolerance_policy'], 'UNSET_REQUIRED')
        self.assertEqual(gaps['nonzero_reference_delta_resolution'], 'UNKNOWN')

    def test_legacy_row_cannot_cross_request_security_identity(self):
        legacy = requests()
        legacy[2]['rows'][0]['typed_fields']['ts_code']['value'] = '600312.SH'
        with self.assertRaisesRegex(ValueError, 'ACTION_REQUEST_SYMBOL_MISMATCH'):
            analyze(inputs(legacy=legacy))

    def test_target_factor_conflict_is_not_hidden_by_rounding(self):
        new = [new_request('adj_factor', [{'ts_code': SYMBOL, 'trade_date': DAY, 'adj_factor': '3.0000000001'}])]
        result = sections(inputs(new=new))
        point = result['factor_action_reconciliation']['change_points'][0]
        self.assertFalse(point['new_factor_comparisons'][0]['exact_numeric_equality'])
        self.assertIn('TARGET_FACTOR_VALUE_CONFLICT', [g['reason'] for g in result['adjustment_known_gaps']['gaps']])

    def test_empty_response_is_no_negative_action_proof(self):
        new = [new_request('dividend', []), new_request('adj_factor', [])]
        result = sections(inputs(new=new))
        point = result['factor_action_reconciliation']['change_points'][0]
        self.assertEqual(point['new_action_request_views'][0]['params']['ex_date'], DAY)
        self.assertEqual(point['new_same_date_action_rows'], [])
        self.assertFalse(result['adjustment_known_gaps']['negative_action_proof_from_empty_response'])

    def test_request_receipt_exports_business_scope_and_retains_original_transport_input(self):
        endpoint = 'http://example.invalid/synthetic-facade/'
        new = [new_request('adj_factor', [{'ts_code': SYMBOL, 'trade_date': DAY, 'adj_factor': '3'}]),
               new_request('dividend', [action_values()])]
        for q in new:
            q['params']['ts_type_name'] = endpoint
        source = inputs(new=new)
        before = copy.deepcopy(source)
        result = analyze(source)
        self.assertEqual(source, before)
        self.assertTrue(all(q['params']['ts_type_name'] == endpoint for q in source['new']))
        self.assertNotIn(endpoint, json.dumps(result, ensure_ascii=False))
        self.assertNotIn('ts_type_name', json.dumps(result['body'], ensure_ascii=False))
        point = result['body']['factor_action_reconciliation']['change_points'][0]
        for key, field in (('new_action_request_views', 'ex_date'),
                           ('new_factor_request_views', 'trade_date')):
            receipt = point[key][0]
            self.assertEqual(receipt['params'], {'ts_code': SYMBOL, field: DAY})
            self.assertEqual(receipt['params_projection']['kind'], 'BUSINESS_SCOPE_ONLY')
            self.assertEqual(receipt['params_projection']['omitted_parameter_count'], 1)
            self.assertTrue(receipt['params_projection']['original_params_retained_in_verified_inputs'])
            self.assertTrue(receipt['params_projection']['original_params_bound_by_request_fingerprint'])
            self.assertFalse(receipt['params_projection']['transport_parameters_exported'])

    def test_transport_projection_does_not_remove_original_request_identity_binding(self):
        def with_endpoint(endpoint):
            new = [new_request('dividend', [action_values()])]
            new[0]['params']['ts_type_name'] = endpoint
            return analyze(inputs(new=new))
        first = with_endpoint('http://example.invalid/synthetic-one/')
        second = with_endpoint('http://example.invalid/synthetic-two/')
        point1 = first['body']['factor_action_reconciliation']['change_points'][0]
        point2 = second['body']['factor_action_reconciliation']['change_points'][0]
        receipt1 = point1['new_action_request_views'][0]
        receipt2 = point2['new_action_request_views'][0]
        self.assertEqual(receipt1['params'], receipt2['params'])
        self.assertNotEqual(receipt1['request_fingerprint'], receipt2['request_fingerprint'])
        self.assertNotEqual(first['input_identity'], second['input_identity'])
        self.assertNotEqual(first['content_hash'], second['content_hash'])

    def test_blocked_new_rows_preserved_without_consistency_or_ledger_proof(self):
        new = [new_request('dividend', [action_values()], blocked=True)]
        result = sections(inputs(new=new))
        point = result['factor_action_reconciliation']['change_points'][0]
        self.assertTrue(point['new_same_date_action_rows'][0]['response_blocked'])
        self.assertEqual(point['new_action_comparisons'], [])
        self.assertFalse(point['action_entitlement_ledger_reconstructed'])

    def test_blocked_legacy_price_response_does_not_compute_change_authority(self):
        legacy = requests()
        legacy[1]['response_dq'] = 'BLOCKED'
        result = sections(inputs(legacy=legacy))
        self.assertEqual(result['factor_action_reconciliation']['change_point_count'], 0)
        self.assertEqual(result['factor_action_reconciliation']['symbols'][0]['status'], 'BLOCKED')
        self.assertEqual(len(result['factor_action_reconciliation']['legacy_action_originals']), 1)

    def test_nonfinite_zero_negative_and_float_factor_rejected(self):
        for value in ('NaN', 'Infinity', '0', '-1', 3.0):
            with self.subTest(value=value):
                legacy = requests()
                legacy[1]['rows'][1]['typed_fields']['adj_factor']['value'] = value
                with self.assertRaises(ValueError):
                    analyze(inputs(legacy=legacy))

    def test_copy_and_mutated_inputs_rejected_by_registration(self):
        source = inputs()
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_OR_MUTATED_INPUT'):
            analyze(copy.deepcopy(source))
        source['legacy']['requests'][2]['rows'][0]['typed_fields']['ann_date']['value'] = '20250501'
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_OR_MUTATED_INPUT'):
            analyze(source)

    def test_input_not_mutated_and_result_values_are_not_input_aliases(self):
        source = inputs()
        before = copy.deepcopy(source)
        result = analyze(source)
        self.assertEqual(source, before)
        result['body']['factor_action_reconciliation']['legacy_action_originals'][0]['values']['cash_div'] = '9'
        self.assertEqual(source, before)
        with self.assertRaisesRegex(ValueError, 'CANDIDATE_VERSION_INVALIDATED'):
            require_result(result)

    def test_deterministic_replay_and_source_hash_changes_identity(self):
        source = inputs()
        first, second = analyze(source), analyze(source)
        self.assertEqual(first['content_hash'], second['content_hash'])
        legacy = requests()
        legacy[2]['raw_sha256'] = 'sha256:' + 'f' * 64
        changed = analyze(inputs(legacy=legacy))
        self.assertNotEqual(changed['input_identity'], first['input_identity'])
        self.assertNotEqual(changed['content_hash'], first['content_hash'])

    def test_changed_producer_bytes_invalidate_registered_candidate_without_disk_write(self):
        result = analyze(inputs())
        action_path = Path(__file__).resolve().parents[1] / 'action.py'
        original_read = Path.read_bytes
        def changed_read(path):
            data = original_read(path)
            return data + b'\n# synthetic changed code epoch\n' if path == action_path else data
        with patch.object(Path, 'read_bytes', changed_read):
            with self.assertRaisesRegex(ValueError, 'INPUT_SOURCE_OR_CODE_CHANGED'):
                require_result(result)

    def test_quarantine_cannot_be_authoritative_ledger_price_or_consumer_input(self):
        result = analyze(inputs())
        self.assertTrue(result['fixture'])
        self.assertEqual(result['kind'], 'ACTION_FACTOR_CANDIDATE')
        self.assertEqual(result['state'], 'QUARANTINED')
        self.assertEqual(result['source_admission'], 'BLOCKED')
        self.assertFalse(result['productionGate'])
        self.assertFalse(result['body']['factor_action_reconciliation']['adjusted_prices_published_as_source'])
        self.assertFalse(result['body']['adjustment_known_gaps']['actual_entitlement_ledger'])
        self.assertFalse(result['body']['adjustment_known_gaps']['action_formula_or_rights_inferred'])
        for consumer in ('BrainPacket', 'ResearchAssessment', 'ResearchCard', 'Candidate', 'Signal'):
            with self.subTest(consumer=consumer):
                with self.assertRaisesRegex(ValueError, 'QUARANTINED_INPUT_NOT_ADMITTED'):
                    reject_real_consumer(result, consumer)
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_CANDIDATE'):
            require_result(copy.deepcopy(result))


if __name__ == '__main__':
    unittest.main()
