"""Synthetic selector boundary fixtures, never Owner policy or source evidence."""
from copy import deepcopy
import unittest

from post_wave_e.common import SYMBOLS, canonical, digest, seal
from post_wave_e.pit import (COMPONENTS, financial_readiness, select_financial,
                            select_tradeability, tradeability_readiness)

S = SYMBOLS[0]
PERIOD = '20260630'
CUTOFF = '2026-08-15T16:00:00+08:00'
OBSERVED = 'OBSERVED_AT_TIME'
RECONSTRUCT = 'HISTORICAL_AVAILABILITY_RECONSTRUCTION'
FIRST = '2026-07-30T10:00:00+08:00'
LATE = '2026-09-01T10:00:00+08:00'
EFFECTIVE = '2026-08-01T10:00:00+08:00'


def common(symbol=S, when=FIRST):
    return {'symbol': symbol, 'event_time': '2026-06-30T00:00:00+08:00',
            'published_at': when, 'available_at': when, 'retrieved_at': when,
            'publication_precision': 'INSTANT', 'availability_precision': 'INSTANT',
            'date_only_fields': {}, 'clock_proof': 'SYNTHETIC_EXACT',
            'provenance': 'SYNTHETIC', 'source': 'SYNTHETIC_NOT_OWNER_POLICY',
            'source_version': 'synthetic-version-1', 'raw_hash': digest('synthetic-raw'),
            'row_ordinal': 0}


def financial(rid='first', parent=None, when=FIRST, statement='INCOME'):
    return common(when=when) | {
        'kind': 'FINANCIAL_REVISION', 'period': PERIOD, 'statement': statement,
        'revision_id': rid, 'supersedes_revision_id': parent,
        'revision_coverage_complete': True, 'coverage_kind': 'HISTORICAL_REVISIONS',
        'values': {'synthetic_revenue': '1000'}, 'units': 'SYNTHETIC_DECLARED'}


def trade(component, value=None, when=FIRST):
    defaults = {'ST': 'NORMAL', 'SUSPENSION': 'ACTIVE',
                'LIMIT': {'regime': 'BOUNDED', 'lower': '9', 'upper': '11',
                          'unit': 'CNY_PER_SHARE'},
                'DELIST': 'NOT_DELISTED', 'LISTED': 'LISTED', 'UNIVERSE': 'MEMBER'}
    return common(when=when) | {
        'kind': 'TRADEABILITY_HISTORY', 'component': component,
        'effective_from': '2026-07-01T00:00:00+08:00', 'effective_to': None,
        'coverage_complete': True, 'coverage_kind': 'HISTORICAL_INTERVAL',
        'value': deepcopy(defaults[component] if value is None else value)}


def trade_rows():
    return [trade(c) for c in COMPONENTS]


def inputs():
    # This imitates quarantine input shape for metadata tests. It is explicitly
    # synthetic and carries no independently verified source or Owner policies.
    result = []
    for symbol in SYMBOLS:
        observations = []
        for api in ('income', 'balancesheet', 'cashflow', 'fina_indicator',
                    'stock_basic', 'index_member_all'):
            observations.append({'api_name': api,
                                 'values': {'ts_code': symbol, 'end_date': PERIOD,
                                            'ann_date': '20260730', 'f_ann_date': '20260730',
                                            'update_flag': '1', 'synthetic_number': '12345'},
                                 'source_ref': {'raw_sha256': digest('SYNTHETIC-' + api),
                                                'request_id': 'SYNTHETIC-' + api,
                                                'request_fingerprint': digest('SYNTHETIC-request-' + api),
                                                'row_ordinal': 0, 'event_time': None,
                                                'published_at': None, 'available_at': LATE,
                                                'retrieved_at': LATE}})
        result.append(seal({'contract_name': 'RealResearchSandboxInput',
                            'namespace': 'LOCAL_EXPERIMENTAL_REAL_RESEARCH:CORE_40',
                            'symbol': symbol, 'formal_source_admission': 'BLOCKED',
                            'historical_visibility_proven': False, 'productionGate': False,
                            'license_verified': False, 'provider_identity_verified': False,
                            'transport_integrity_verified': False,
                            'fixture_label': 'SYNTHETIC_NOT_SOURCE_EVIDENCE',
                            'body': {'observations': observations, 'excluded': []}}))
    return result


def reseal(value):
    return seal({k: v for k, v in value.items() if k != 'content_hash'})


class FinancialSelectorTests(unittest.TestCase):
    def select(self, rows, cutoff=CUTOFF, mode=OBSERVED):
        return select_financial(rows, S, PERIOD, cutoff, mode)

    def test_first_visible_revision(self):
        r = self.select([financial()])
        self.assertEqual(r['status'], 'SELECTED_FIXTURE_ONLY')
        self.assertEqual(r['selected']['INCOME']['revision_id'], 'first')

    def test_prefix_late_revision_noninterference(self):
        base = self.select([financial()])
        late = financial('later', 'first', LATE)
        self.assertEqual(base, self.select([financial(), late]))

    def test_late_revision_metadata_and_body_mutations_excluded(self):
        base = self.select([financial()])
        late = financial('later', 'first', LATE)
        late['revision_id'] = 'future ID must not enter hash'
        late['supersedes_revision_id'] = 'missing future parent'
        late['values'] = {'future_title': 'opaque future metadata'}
        late['unexpected_future_field'] = 'body not inspected'
        self.assertEqual(base, self.select([late, financial()]))

    def test_future_duplicate_revision_id_excluded(self):
        later = financial('first', None, LATE)
        later['values']['synthetic_revenue'] = '8888'
        self.assertEqual(self.select([financial()]), self.select([financial(), later]))

    def test_future_retrieval_does_not_revise_observed_prefix(self):
        later = financial('later', 'first', '2026-08-01T10:00:00+08:00')
        later['retrieved_at'] = LATE
        self.assertEqual(self.select([financial()]), self.select([financial(), later]))

    def test_latest_explicit_complete_chain(self):
        second = financial('second', 'first', '2026-08-01T10:00:00+08:00')
        second['values']['synthetic_revenue'] = '1200'
        r = self.select([second, financial()])
        self.assertEqual(r['selected']['INCOME']['revision_id'], 'second')

    def test_input_order_does_not_choose_revision(self):
        second = financial('second', 'first', '2026-08-01T10:00:00+08:00')
        self.assertEqual(self.select([financial(), second]), self.select([second, financial()]))

    def test_preserves_source_version_hash_ordinal(self):
        row = financial()
        row['source_version'] = 'fixture-version-exact'
        row['row_ordinal'] = 19
        r = self.select([row])
        self.assertEqual(r['selected']['INCOME'], row)

    def test_selected_copies_are_isolated(self):
        row = financial()
        r = self.select([row])
        r['selected']['INCOME']['values']['synthetic_revenue'] = '0'
        self.assertEqual(row['values']['synthetic_revenue'], '1000')

    def test_date_only_publication_stays_unknown(self):
        row = financial()
        row.update(published_at=None, publication_precision='DATE_ONLY',
                   date_only_fields={'ann_date': '20260730'})
        self.assertEqual(self.select([row])['status'], 'UNKNOWN')

    def test_date_only_availability_stays_unknown(self):
        row = financial()
        row.update(available_at=None, availability_precision='DATE_ONLY',
                   date_only_fields={'available_date': '20260730'})
        self.assertIn('AVAILABILITY_CLOCK_UNKNOWN_OR_DATE_ONLY',
                      self.select([row])['reason_codes'])

    def test_date_only_midnight_imputation_rejected(self):
        row = financial()
        row.update(publication_precision='DATE_ONLY',
                   published_at='2026-07-30T00:00:00+08:00')
        with self.assertRaisesRegex(ValueError, 'PIT_DATE_ONLY_OR_UNKNOWN_IMPUTED'):
            self.select([row])

    def test_unknown_publication_stays_unknown(self):
        row = financial()
        row.update(published_at=None, publication_precision='UNKNOWN')
        self.assertEqual(self.select([row])['selected'], {})

    def test_actual_quarantine_cannot_self_declare_synthetic_proof(self):
        row = financial()
        row['provenance'] = 'QUARANTINED'
        with self.assertRaisesRegex(ValueError, 'PIT_ACTUAL_PROOF_FORBIDDEN'):
            self.select([row])

    def test_actual_quarantine_unproven_stays_blocked(self):
        row = financial()
        row.update(provenance='QUARANTINED', clock_proof='UNPROVEN')
        self.assertEqual(self.select([row])['status'], 'UNKNOWN')

    def test_posthoc_reconstruction_is_not_observed_then(self):
        row = financial()
        row['retrieved_at'] = LATE
        r = self.select([row], mode=RECONSTRUCT)
        self.assertEqual(r['status'], 'SELECTED_FIXTURE_ONLY')
        self.assertFalse(r['observed_at_cutoff'])
        self.assertFalse(r['historical_visibility_proven'])

    def test_unproven_reconstruction_remains_unknown(self):
        row = financial()
        row.update(clock_proof='UNPROVEN', retrieved_at=LATE)
        self.assertEqual(self.select([row], mode=RECONSTRUCT)['status'], 'UNKNOWN')

    def test_reconstruction_future_availability_excluded(self):
        r = self.select([financial()], mode=RECONSTRUCT)
        self.assertEqual(r, self.select([financial(), financial('later', 'first', LATE)],
                                        mode=RECONSTRUCT))

    def test_current_revision_cannot_backfill(self):
        row = financial()
        row['coverage_kind'] = 'CURRENT_REVISION_SNAPSHOT'
        self.assertIn('CURRENT_REVISION_NOT_HISTORICAL', self.select([row])['reason_codes'])

    def test_partial_revision_coverage_blocks(self):
        row = financial()
        row['revision_coverage_complete'] = False
        self.assertEqual(self.select([row])['status'], 'UNKNOWN')

    def test_missing_predecessor_not_assumed_first_version(self):
        self.assertIn('FINANCIAL_REVISION_CHAIN_INCOMPLETE',
                      self.select([financial('second', 'missing')])['reason_codes'])

    def test_branching_revisions_fail_closed(self):
        a = financial('second-a', 'first', '2026-08-01T10:00:00+08:00')
        b = financial('second-b', 'first', '2026-08-02T10:00:00+08:00')
        self.assertEqual(self.select([financial(), a, b])['selected'], {})

    def test_two_unlinked_roots_not_last_row_wins(self):
        second = financial('second', None, '2026-08-01T10:00:00+08:00')
        self.assertIn('FINANCIAL_REVISION_CONFLICT',
                      self.select([financial(), second])['reason_codes'])

    def test_revision_id_collision_values_rejected(self):
        row = financial()
        other = financial()
        other['values']['synthetic_revenue'] = '2000'
        self.assertIn('FINANCIAL_REVISION_ID_CONFLICT',
                      self.select([row, other])['reason_codes'])

    def test_identical_duplicate_does_not_create_fork(self):
        self.assertEqual(self.select([financial(), financial()])['status'],
                         'SELECTED_FIXTURE_ONLY')

    def test_cycle_has_no_selected_version(self):
        a = financial('a', 'b')
        b = financial('b', 'a', '2026-08-01T10:00:00+08:00')
        self.assertEqual(self.select([a, b])['status'], 'UNKNOWN')

    def test_revision_chronology_not_reverse(self):
        a = financial('first', None, '2026-08-01T10:00:00+08:00')
        b = financial('second', 'first', FIRST)
        self.assertIn('FINANCIAL_REVISION_CHRONOLOGY_CONFLICT',
                      self.select([a, b])['reason_codes'])

    def test_update_flag_is_not_a_revision_clock(self):
        row = financial()
        row['update_flag'] = '1'
        with self.assertRaisesRegex(ValueError, 'PREP_SHAPE_INVALID'):
            self.select([row])

    def test_no_observation_returns_unknown(self):
        r = self.select([])
        self.assertEqual(r['status'], 'UNKNOWN')
        self.assertEqual(r['visible_count'], 0)

    def test_other_period_not_in_prefix_hash(self):
        row = financial()
        row['period'] = '20260331'
        self.assertEqual(self.select([financial()]), self.select([row, financial()]))

    def test_multiple_statements_have_independent_chains(self):
        r = self.select([financial(), financial(statement='BALANCESHEET')])
        self.assertEqual(set(r['selected']), {'INCOME', 'BALANCESHEET'})

    def test_event_time_is_not_forced_before_publication(self):
        row = financial()
        row['event_time'] = '2026-10-01T09:00:00+08:00'
        self.assertEqual(self.select([row])['status'], 'SELECTED_FIXTURE_ONLY')

    def test_cutoff_nanosecond_boundary(self):
        row = financial(when='2026-08-15T16:00:00.000000001+08:00')
        self.assertEqual(self.select([row])['visible_count'], 0)

    def test_cutoff_timezone_equivalence(self):
        self.assertEqual(self.select([financial()], cutoff='2026-08-15T08:00:00Z')
                         ['selected'], self.select([financial()])['selected'])

    def test_naive_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, 'PREP_INSTANT_REQUIRED'):
            self.select([financial()], cutoff='2026-08-15T16:00:00')

    def test_invalid_mode_rejected(self):
        with self.assertRaisesRegex(ValueError, 'PIT_MODE_INVALID'):
            self.select([financial()], mode='PUBLIC_IS_ALWAYS_PIT')

    def test_financial_float_value_rejected(self):
        row = financial()
        row['values']['synthetic_revenue'] = 1000.1
        with self.assertRaises(ValueError):
            self.select([row])

    def test_boolean_ordinal_rejected(self):
        row = financial()
        row['row_ordinal'] = True
        with self.assertRaisesRegex(ValueError, 'PIT_ORDINAL_INVALID'):
            self.select([row])

    def test_source_hash_format_rejected(self):
        row = financial()
        row['raw_hash'] = 'not-a-hash'
        with self.assertRaises(ValueError):
            self.select([row])

    def test_publication_after_availability_rejected(self):
        row = financial()
        row['published_at'] = '2026-07-31T00:00:00+08:00'
        with self.assertRaisesRegex(ValueError, 'PIT_PUBLICATION_AFTER_AVAILABILITY'):
            self.select([row])

    def test_unverified_units_remain_unknown(self):
        row = financial()
        row['units'] = 'UNVERIFIED_SOURCE_UNITS'
        self.assertIn('FINANCIAL_UNITS_UNVERIFIED', self.select([row])['reason_codes'])

    def test_synthetic_result_is_never_live_authority(self):
        r = self.select([financial()])
        self.assertEqual(r['formal_source_admission'], 'BLOCKED')
        for k in ('live_authority', 'historical_visibility_proven', 'productionGate',
                  'safe_to_trade'):
            self.assertIs(r[k], False)

    def test_future_reporting_period_is_unknown_without_row_metadata(self):
        row = financial()
        row['period'] = '20261231'
        r = select_financial([row], S, '20261231', CUTOFF, OBSERVED)
        self.assertEqual(r['status'], 'UNKNOWN')
        self.assertEqual(r['visible_count'], 0)
        self.assertEqual(r['visible_records_hash'], digest([]))
        self.assertEqual(r['selected'], {})
        self.assertEqual(r['reason_codes'], ['FUTURE_REPORTING_PERIOD_NOT_VISIBLE'])

    def test_future_period_values_and_ids_never_enter_result(self):
        a = financial()
        a['period'] = '20261231'
        b = deepcopy(a)
        b['revision_id'] = 'future-opaque-version'
        b['values']['synthetic_revenue'] = '987654321'
        b['extra_future_metadata'] = 'not inspected'
        first = select_financial([a], S, '20261231', CUTOFF, OBSERVED)
        other = select_financial([a, b], S, '20261231', CUTOFF, OBSERVED)
        self.assertEqual(first, other)

    def test_reporting_period_uses_shanghai_date_at_utc_boundary(self):
        row = financial()
        row['period'] = '20260816'
        before = select_financial([row], S, '20260816',
                                  '2026-08-15T15:59:59.999999999Z', OBSERVED)
        after = select_financial([row], S, '20260816',
                                 '2026-08-15T16:00:00Z', OBSERVED)
        self.assertEqual(before['status'], 'UNKNOWN')
        self.assertEqual(after['status'], 'SELECTED_FIXTURE_ONLY')

    def test_cutoff_local_date_cannot_override_shanghai_date(self):
        row = financial()
        row['period'] = '20260816'
        r = select_financial([row], S, '20260816',
                             '2026-08-16T00:00:00+09:00', OBSERVED)
        self.assertEqual(r['visible_count'], 0)
        self.assertEqual(r['status'], 'UNKNOWN')


class TradeabilitySelectorTests(unittest.TestCase):
    def select(self, rows, effective=EFFECTIVE, cutoff=CUTOFF, mode=OBSERVED):
        return select_tradeability(rows, S, effective, cutoff, mode)

    def test_complete_synthetic_history_selection(self):
        self.assertEqual(self.select(trade_rows())['status'], 'SELECTED_FIXTURE_ONLY')

    def test_absence_is_unknown_for_every_component(self):
        r = self.select([])
        self.assertEqual(r['component_states'], {c: 'UNKNOWN' for c in COMPONENTS})
        self.assertFalse(r['safe_to_trade'])

    def test_missing_single_component_is_unknown(self):
        rows = [r for r in trade_rows() if r['component'] != 'SUSPENSION']
        r = self.select(rows)
        self.assertIn('STATUS_COMPONENT_MISSING:SUSPENSION', r['reason_codes'])
        self.assertEqual(r['selected'], {})

    def test_current_universe_does_not_backfill(self):
        rows = trade_rows()
        rows[-1]['coverage_kind'] = 'CURRENT_SNAPSHOT'
        self.assertIn('CURRENT_STATUS_NOT_HISTORICAL', self.select(rows)['reason_codes'])

    def test_current_status_does_not_backfill(self):
        rows = trade_rows()
        rows[0]['coverage_kind'] = 'CURRENT_SNAPSHOT'
        self.assertEqual(self.select(rows)['status'], 'UNKNOWN')

    def test_incomplete_interval_is_unknown(self):
        rows = trade_rows()
        rows[1]['coverage_complete'] = False
        self.assertIn('STATUS_HISTORY_COVERAGE_INCOMPLETE', self.select(rows)['reason_codes'])

    def test_known_suspension_blocks(self):
        rows = trade_rows()
        rows[1]['value'] = 'SUSPENDED'
        self.assertEqual(self.select(rows)['status'], 'BLOCKED_FIXTURE_ONLY')

    def test_known_delisting_blocks(self):
        rows = trade_rows()
        rows[3]['value'] = 'DELISTED'
        self.assertIn('STATUS_KNOWN_BLOCK:DELIST', self.select(rows)['reason_codes'])

    def test_not_listed_blocks(self):
        rows = trade_rows()
        rows[4]['value'] = 'NOT_LISTED'
        self.assertEqual(self.select(rows)['status'], 'BLOCKED_FIXTURE_ONLY')

    def test_not_universe_member_blocks(self):
        rows = trade_rows()
        rows[5]['value'] = 'NOT_MEMBER'
        self.assertEqual(self.select(rows)['status'], 'BLOCKED_FIXTURE_ONLY')

    def test_unknown_status_is_not_clear(self):
        rows = trade_rows()
        rows[1]['value'] = 'UNKNOWN'
        self.assertIn('STATUS_VALUE_UNKNOWN:SUSPENSION', self.select(rows)['reason_codes'])

    def test_st_flag_requires_unset_policy(self):
        rows = trade_rows()
        rows[0]['value'] = 'ST'
        self.assertIn('ST_POLICY_UNSET_REQUIRED', self.select(rows)['reason_codes'])
        self.assertFalse(self.select(rows)['safe_to_trade'])

    def test_known_limit_does_not_imply_price_inside_band(self):
        r = self.select(trade_rows())
        self.assertIn('ORDER_PRICE_NOT_PROVIDED', r['reason_codes'])
        self.assertFalse(r['safe_to_trade'])

    def test_invalid_reversed_limit_rejected(self):
        rows = trade_rows()
        rows[2]['value']['lower'] = '12'
        with self.assertRaisesRegex(ValueError, 'PIT_LIMIT_RANGE_INVALID'):
            self.select(rows)

    def test_float_price_limit_rejected(self):
        rows = trade_rows()
        rows[2]['value']['lower'] = 9.0
        with self.assertRaises(ValueError):
            self.select(rows)

    def test_no_limit_requires_explicit_evidence(self):
        rows = trade_rows()
        rows[2]['value'] = {'regime': 'NO_LIMIT'}
        self.assertEqual(self.select(rows)['status'], 'SELECTED_FIXTURE_ONLY')

    def test_unknown_limit_blocks_selection(self):
        rows = trade_rows()
        rows[2]['value'] = {'regime': 'UNKNOWN'}
        self.assertEqual(self.select(rows)['selected'], {})

    def test_overlapping_conflicting_states_fail_closed(self):
        extra = trade('SUSPENSION', 'SUSPENDED')
        self.assertIn('STATUS_OVERLAPPING_VERSION_CONFLICT:SUSPENSION',
                      self.select(trade_rows() + [extra])['reason_codes'])

    def test_distinct_overlapping_versions_not_last_row_wins(self):
        extra = trade('SUSPENSION')
        extra['source_version'] = 'another-synthetic-version'
        self.assertEqual(self.select(trade_rows() + [extra])['status'], 'UNKNOWN')

    def test_identical_status_duplicate_deduplicates_without_conflict(self):
        self.assertEqual(self.select(trade_rows() + [trade('SUSPENSION')])['status'],
                         'SELECTED_FIXTURE_ONLY')

    def test_effective_interval_end_is_exclusive(self):
        rows = trade_rows()
        rows[1]['effective_to'] = EFFECTIVE
        self.assertIn('STATUS_COMPONENT_MISSING:SUSPENSION', self.select(rows)['reason_codes'])

    def test_effective_interval_begin_is_inclusive(self):
        rows = trade_rows()
        for row in rows:
            row['effective_from'] = EFFECTIVE
        self.assertEqual(self.select(rows)['status'], 'SELECTED_FIXTURE_ONLY')

    def test_effective_interval_gap_is_unknown(self):
        rows = trade_rows()
        rows[1]['effective_to'] = '2026-07-31T15:00:00+08:00'
        self.assertEqual(self.select(rows)['status'], 'UNKNOWN')

    def test_future_effective_event_can_be_publicly_known(self):
        rows = trade_rows()
        for row in rows:
            row['event_time'] = '2026-10-08T09:00:00+08:00'
            row['effective_from'] = '2026-10-08T09:00:00+08:00'
        self.assertEqual(self.select(rows, effective='2026-10-08T10:00:00+08:00')['status'],
                         'SELECTED_FIXTURE_ONLY')

    def test_late_future_status_metadata_is_excluded(self):
        extra = trade('SUSPENSION', 'SUSPENDED', LATE)
        extra['future_title'] = 'unknown future schema field'
        self.assertEqual(self.select(trade_rows()), self.select(trade_rows() + [extra]))

    def test_status_future_retrieval_excluded_from_observed(self):
        extra = trade('SUSPENSION', 'SUSPENDED')
        extra['retrieved_at'] = LATE
        self.assertEqual(self.select(trade_rows()), self.select(trade_rows() + [extra]))

    def test_reconstructed_status_not_observed_then(self):
        rows = trade_rows()
        for row in rows:
            row['retrieved_at'] = LATE
        r = self.select(rows, mode=RECONSTRUCT)
        self.assertEqual(r['status'], 'SELECTED_FIXTURE_ONLY')
        self.assertFalse(r['observed_at_cutoff'])

    def test_status_date_only_is_unknown(self):
        rows = trade_rows()
        rows[1].update(published_at=None, publication_precision='DATE_ONLY',
                       date_only_fields={'publication_date': '20260730'})
        self.assertEqual(self.select(rows)['status'], 'UNKNOWN')

    def test_unproven_current_rows_cannot_clear_history(self):
        rows = trade_rows()
        for row in rows:
            row.update(provenance='QUARANTINED', clock_proof='UNPROVEN')
        r = self.select(rows)
        self.assertEqual(r['status'], 'UNKNOWN')
        self.assertFalse(r['historical_visibility_proven'])

    def test_status_caller_production_field_rejected(self):
        rows = trade_rows()
        rows[0]['productionGate'] = True
        with self.assertRaisesRegex(ValueError, 'PREP_SHAPE_INVALID'):
            self.select(rows)

    def test_scope_cannot_expand_to_other_security(self):
        with self.assertRaisesRegex(ValueError, 'PIT_SYMBOL_SCOPE'):
            select_tradeability([], '000001.SZ', EFFECTIVE, CUTOFF, OBSERVED)

    def test_complete_history_has_no_order_authority(self):
        r = self.select(trade_rows())
        for field in ('safe_to_trade', 'live_authority', 'productionGate',
                      'historical_visibility_proven'):
            self.assertIs(r[field], False)


class ReadinessMetadataTests(unittest.TestCase):
    def test_financial_current_metadata_remains_blocked(self):
        r = financial_readiness(inputs())
        self.assertEqual(r['status'], 'BLOCKED')
        self.assertEqual(len(r['coverage']), 12)
        self.assertEqual(r['actual_selected_versions'], 0)

    def test_financial_readiness_does_not_return_values(self):
        r = financial_readiness(inputs())
        b = canonical(r)
        self.assertNotIn(b'synthetic_number', b)
        self.assertNotIn(b'12345', b)

    def test_financial_date_only_fields_not_timestamped(self):
        row = financial_readiness(inputs())['coverage'][0]
        self.assertEqual(row['date_only_field_counts'], {'ann_date': 1, 'f_ann_date': 1})
        self.assertEqual(row['first_visibility'], 'UNKNOWN')
        self.assertEqual(row['publication_clock'], 'UNKNOWN')

    def test_revision_update_flag_is_only_field_presence(self):
        row = financial_readiness(inputs())['coverage'][0]
        self.assertEqual(row['revision_flag_field_present_rows'], 1)
        self.assertTrue(row['update_flag_is_not_chronology'])
        self.assertEqual(row['revision_chronology'], 'UNKNOWN')

    def test_preserves_original_raw_ordinal_metadata(self):
        row = financial_readiness(inputs())['coverage'][0]
        self.assertEqual(row['raw_sources'][0]['row_ordinals'], [0])
        self.assertEqual(row['raw_sources'][0]['raw_hash'], digest('SYNTHETIC-income'))

    def test_same_payload_different_request_preserves_distinct_sources(self):
        xs = inputs()
        original = xs[0]['body']['observations'][0]
        second = deepcopy(original)
        second['source_ref']['request_id'] = 'SYNTHETIC-income-second-request'
        second['source_ref']['request_fingerprint'] = digest('SYNTHETIC-second-request')
        xs[0]['body']['observations'].append(second)
        xs[0] = reseal(xs[0])
        row = financial_readiness(xs)['coverage'][0]
        self.assertEqual(row['observed_rows'], 2)
        self.assertEqual(len(row['raw_sources']), 2)
        self.assertEqual({r['raw_hash'] for r in row['raw_sources']},
                         {original['source_ref']['raw_sha256']})
        self.assertEqual({r['request_id'] for r in row['raw_sources']},
                         {'SYNTHETIC-income', 'SYNTHETIC-income-second-request'})
        self.assertTrue(all(r['row_ordinals'] == [0] for r in row['raw_sources']))

    def test_same_request_new_capture_preserves_retrieval_versions(self):
        xs = inputs()
        second = deepcopy(xs[0]['body']['observations'][0])
        second['source_ref']['retrieved_at'] = '2026-09-02T10:00:00+08:00'
        second['source_ref']['available_at'] = second['source_ref']['retrieved_at']
        xs[0]['body']['observations'].append(second)
        xs[0] = reseal(xs[0])
        row = financial_readiness(xs)['coverage'][0]
        self.assertEqual(len(row['raw_sources']), 2)
        self.assertEqual({r['retrieved_at'] for r in row['raw_sources']},
                         {LATE, '2026-09-02T10:00:00+08:00'})

    def test_identical_complete_identity_keeps_ordinal_multiset(self):
        xs = inputs()
        xs[0]['body']['observations'].append(deepcopy(xs[0]['body']['observations'][0]))
        xs[0] = reseal(xs[0])
        row = financial_readiness(xs)['coverage'][0]
        self.assertEqual(row['observed_rows'], 2)
        self.assertEqual(len(row['raw_sources']), 1)
        self.assertEqual(row['raw_sources'][0]['row_ordinals'], [0, 0])
        self.assertEqual(row['raw_sources'][0]['row_count'], 2)

    def test_content_version_is_original_content_hash_not_provider_revision(self):
        row = financial_readiness(inputs())['coverage'][0]['raw_sources'][0]
        self.assertEqual(row['content_version'], row['raw_hash'])
        self.assertEqual(row['request_fingerprint'], digest('SYNTHETIC-request-income'))

    def test_current_universe_history_false(self):
        r = tradeability_readiness(inputs())
        self.assertEqual(r['status'], 'BLOCKED')
        for row in r['coverage']:
            self.assertFalse(row['current_universe_backfill'])
            self.assertFalse(row['survivorship_free_universe'])
            self.assertFalse(row['absence_implies_safe'])

    def test_every_real_status_component_unknown(self):
        r = tradeability_readiness(inputs())
        for row in r['coverage']:
            self.assertEqual(set(row['historical_components']), set(COMPONENTS))
            self.assertTrue(all(v['status'] == 'UNKNOWN' for v in
                                row['historical_components'].values()))

    def test_missing_current_stock_row_is_not_safe(self):
        xs = inputs()
        for i, x in enumerate(xs):
            x['body']['observations'] = [r for r in x['body']['observations']
                                         if r['api_name'] != 'stock_basic']
            xs[i] = reseal(x)
        r = tradeability_readiness(xs)
        self.assertTrue(all(row['current_security_rows'] == 0 for row in r['coverage']))
        self.assertEqual(r['status'], 'BLOCKED')

    def test_input_seal_mutation_rejected(self):
        xs = inputs()
        xs[0]['body']['observations'][0]['values']['synthetic_number'] = '0'
        with self.assertRaisesRegex(ValueError, 'PIT_INPUT_SEAL_INVALID'):
            financial_readiness(xs)

    def test_self_resealed_claim_cannot_promote_license(self):
        xs = inputs()
        xs[0]['license_verified'] = True
        xs[0] = reseal(xs[0])
        with self.assertRaisesRegex(ValueError, 'PIT_INPUT_SOURCE_PROMOTION'):
            financial_readiness(xs)

    def test_self_resealed_claim_cannot_promote_history(self):
        xs = inputs()
        xs[0]['historical_visibility_proven'] = True
        xs[0] = reseal(xs[0])
        with self.assertRaisesRegex(ValueError, 'PIT_INPUT_SOURCE_PROMOTION'):
            tradeability_readiness(xs)

    def test_self_resealed_publication_imputation_rejected(self):
        xs = inputs()
        xs[0]['body']['observations'][0]['source_ref']['published_at'] = FIRST
        xs[0] = reseal(xs[0])
        with self.assertRaisesRegex(ValueError, 'PIT_INPUT_CLOCK_PROMOTION'):
            financial_readiness(xs)

    def test_cohort_missing_or_wrong_order_rejected(self):
        with self.assertRaisesRegex(ValueError, 'PIT_INPUT_COHORT_INVALID'):
            financial_readiness(inputs()[:2])
        with self.assertRaisesRegex(ValueError, 'PIT_INPUT_COHORT_INVALID'):
            tradeability_readiness(list(reversed(inputs())))

    def test_actual_forward_and_production_not_granted(self):
        for r in (financial_readiness(inputs()), tradeability_readiness(inputs())):
            self.assertIs(r['productionGate'], False)
            self.assertIs(r['live_authority'], False)
            self.assertIs(r['historical_visibility_proven'], False)
            self.assertEqual(r['formal_source_admission'], 'BLOCKED')


if __name__ == '__main__':
    unittest.main()
