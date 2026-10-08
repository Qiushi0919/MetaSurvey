"""Actual-source integrity + synthetic time/status adversaries, no live issuer."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import unittest

from wave_f.common import SYMBOLS, digest, canonical
from wave_f.pit import (DOMAINS, EVIDENCE_HASH, EVIDENCE_PATH, REQUIRED_PRICE_DOMAINS,
                        evidence, evidence_refs, source_pins, three_symbol_matrix,
                        minimum_price_gate, select_history, run_formal)
from post_wave_e.pit import COMPONENTS, select_financial
from post_wave_e.tests.test_pit import trade_rows, trade, financial, FIRST, LATE, EFFECTIVE, CUTOFF, PERIOD

OBSERVED = 'OBSERVED_AT_TIME'
RECONSTRUCT = 'HISTORICAL_AVAILABILITY_RECONSTRUCTION'
S = SYMBOLS[0]


class ActualEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = evidence()
        cls.matrix = three_symbol_matrix()
        cls.gate = minimum_price_gate()

    def test_exact_scope_and_capture_counts(self):
        x = self.actual
        self.assertEqual(x['exact_symbols'], list(SYMBOLS))
        self.assertEqual((x['actual_public_GET_requests'], x['discovery_query_count'],
                          x['discovery_tool_calls']), (10, 10, 3))
        self.assertEqual((x['authenticated_requests'], x['credential_lookups']), (0, 0))

    def test_failed_originals_preserved_without_redirect(self):
        bad = [c for c in self.actual['captures'] if c['http_status'] != 200]
        self.assertEqual(len(bad), 3)
        self.assertTrue(all(c['http_status'] == 301 and not c['pdf_signature'] and
                            not c['redirect_followed'] for c in bad))
        self.assertTrue(all(Path(c['body_ref']['path']).is_file() for c in bad))

    def test_date_only_source_not_fabricated_instant(self):
        self.assertTrue(all(c['published_at'] is None and c['available_at'] is None
                            for c in self.actual['captures']))
        self.assertTrue(all(f['historical_available_at'] is None and
                            f['observed_at_the_time'] is False for f in self.actual['facts']))

    def test_listing_anchors_do_not_grant_continuous_history(self):
        for r in self.matrix['body']['rows']:
            ds = {d['domain']: d for d in r['domains']}
            self.assertEqual(ds['listing_anchor']['historical_coverage'], 'SINGLE_DATE_ANCHOR_ONLY')
            self.assertEqual(ds['listing_delisting_history']['historical_coverage'], 'UNKNOWN')
            self.assertEqual(ds['listing_delisting_history']['covered_intervals'], [])

    def test_603993_document_proves_a_share_label_not_h_share_date(self):
        f = next(x for x in self.actual['facts'] if x['fact_id'] == 'LISTING_603993_A_SHARE')
        self.assertEqual((f['scope'], f['value']), ('A_SHARE_603993_NOT_H_SHARE_03993', '2012-10-09'))
        c = next(x for x in self.actual['captures'] if x['capture_id'] == f['evidence_capture_ids'][0])
        self.assertTrue(c['pdf_signature'])
        self.assertIn('www1.hkexnews.hk', c['url'])

    def test_600312_current_issuer_not_contemporaneous(self):
        f = next(x for x in self.actual['facts'] if x['fact_id'] == 'LISTING_600312_A_SHARE')
        self.assertEqual(f['evidence_kind'], 'CURRENT_ISSUER_RETROSPECTIVE_WEBPAGE')
        self.assertIsNone(f['publication_date'])
        self.assertEqual(f['value'], '2001-02-21')

    def test_603228_notice_has_separate_publication_and_effective_date(self):
        f = next(x for x in self.actual['facts'] if x['fact_id'] == 'LISTING_603228_A_SHARE')
        self.assertEqual((f['publication_date'], f['value']), ('2017-01-05', '2017-01-06'))
        self.assertFalse(f['observed_at_the_time'])

    def test_2026_rule_originals_and_delayed_clauses_bound(self):
        f = next(x for x in self.actual['facts'] if x['fact_id'] == 'SSE_RULE_2026_EFFECTIVE')
        self.assertEqual((f['publication_date'], f['effective_date']), ('2026-04-24', '2026-07-06'))
        self.assertEqual(f['value']['general_limit_percent'], '10')
        self.assertIn('3.3.17', f['clause_refs'])
        self.assertEqual(f['delayed_clause_refs'], ['3.6.2', '3.6.3', '3.6.4', '3.6.9', '3.6.10'])
        self.assertEqual(len(f['evidence_capture_ids']), 3)

    def test_2023_publication_is_not_effective_session(self):
        f = next(x for x in self.actual['facts'] if x['fact_id'] == 'SSE_RULE_2023_EFFECTIVE_UNRESOLVED')
        self.assertEqual(f['publication_date'], '2023-02-17')
        self.assertIsNone(f['effective_date'])
        self.assertEqual(f['value'], 'FIRST_MAINBOARD_REGISTERED_IPO_LISTING_DAY')

    def test_rule_definition_not_daily_security_limits(self):
        for row in self.matrix['body']['rows']:
            d = next(x for x in row['domains'] if x['domain'] == 'historical_price_limit_regime')
            self.assertEqual(d['historical_coverage'], 'UNKNOWN')
            self.assertIn('RULE_2026_NOT_BACKFILLED', d['reason_codes'])
            self.assertEqual(d['covered_intervals'], [])

    def test_raw_range_does_not_claim_history_or_session_completeness(self):
        for row in self.matrix['body']['rows']:
            q = row['raw_bars']
            self.assertEqual((q['observation_count'], q['distinct_date_count']), (330, 327))
            self.assertEqual((q['range_from'], q['range_to']), ('20250603', '20260930'))
            self.assertFalse(q['continuous_session_coverage_proven'])
            self.assertIsNone(q['historical_available_at'])

    def test_financial_dates_and_revisions_stay_unknown(self):
        for row in self.matrix['body']['rows']:
            for d in row['domains']:
                if d['domain'] in ('financial_ann_fann_date', 'revision_chronology_first_visibility'):
                    self.assertEqual(d['historical_coverage'], 'UNKNOWN')
                    self.assertIn('UPDATE_FLAG_NOT_REVISION_CHAIN', d['reason_codes'])
                    self.assertIn('ANN_DATE_F_ANN_DATE_DATE_ONLY_NOT_INSTANT', d['reason_codes'])

    def test_price_and_fundamental_formal_gate_remain_blocked(self):
        x = self.gate['body']
        self.assertEqual(x['PRICE_BACKTEST_MINIMUM_PIT_READY'], 'BLOCKED')
        self.assertFalse(x['formal_price_backtest_can_start'])
        self.assertFalse(x['formal_fundamental_pit_backtest_can_start'])
        self.assertEqual(len(x['per_security_history_blockers']), len(SYMBOLS) * len(REQUIRED_PRICE_DOMAINS))

    def test_provider_product_docs_not_gateway_license(self):
        x = self.matrix['body']
        self.assertEqual(x['source_provider_license_transport'], 'BLOCKED_INDEPENDENT_GATE')
        self.assertEqual(x['actual_account_parameters'], '30_UNSET_REQUIRED')
        self.assertTrue(all(r['authority'] == 'PRODUCT_OR_CALENDAR_DOCUMENT_ONLY_NOT_ENTITLEMENT_OR_HISTORY'
                            for r in self.actual['reused_document_refs']))

    def test_all_domains_scope_and_remaining_ranges_explicit(self):
        for row in self.matrix['body']['rows']:
            self.assertEqual([d['domain'] for d in row['domains']], list(DOMAINS))
            self.assertTrue(all(d['absence_means'] == 'UNKNOWN' and not d['can_trade'] and
                                d['unfilled_range'] == 'REQUESTED_HISTORICAL_WINDOW_UNSET_REQUIRED'
                                for d in row['domains']))

    def test_hash_versions_pins_exact_private_size_and_scope(self):
        rs = evidence_refs()
        self.assertEqual(len(rs), 31)
        self.assertEqual(len({r['path'] for r in rs}), 31)
        for r in rs:
            p = Path(r['path'])
            self.assertTrue(p.is_relative_to(EVIDENCE_PATH.parent))
            self.assertFalse(p.is_symlink())
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            self.assertEqual(p.stat().st_size, r['bytes'])
        self.assertGreater(len(source_pins()), len(rs))

    def test_manifest_hash_check_before_metadata_use(self):
        import wave_f.pit as mod
        original = mod.checked_file
        def intercepted(path, expected=None):
            if Path(path) == EVIDENCE_PATH:
                self.assertEqual(expected, EVIDENCE_HASH)
                raise ValueError('PREP_DEPENDENCY_INVALIDATED')
            return original(path, expected)
        with patch.object(mod, 'checked_file', side_effect=intercepted):
            with self.assertRaisesRegex(ValueError, 'DEPENDENCY_INVALIDATED'):
                mod.three_symbol_matrix()

    def test_each_original_hash_intercept_fails_before_matrix(self):
        import wave_f.pit as mod
        original = mod.checked_file
        refs = evidence_refs()
        for r in refs:
            with self.subTest(path=Path(r['path']).name):
                def intercepted(path, expected=None):
                    if str(path) == r['path']:
                        self.assertEqual(expected, r['sha256'])
                        raise ValueError('PREP_DEPENDENCY_INVALIDATED')
                    return original(path, expected)
                with patch.object(mod, 'checked_file', side_effect=intercepted):
                    with self.assertRaisesRegex(ValueError, 'DEPENDENCY_INVALIDATED'):
                        mod.evidence()

    def test_no_argument_factory_and_issuer_no_caller_flags(self):
        for fn in (three_symbol_matrix, minimum_price_gate):
            with self.assertRaises(TypeError):
                fn({'historical_visibility_proven': True, 'Owner': 'HUMAN', 'hash': EVIDENCE_HASH})
        with self.assertRaisesRegex(ValueError, 'FORMAL_HISTORY_NOT_ADMITTED'):
            run_formal({'PRICE_BACKTEST_MINIMUM_PIT_READY': 'PASS'})

    def test_metadata_reseal_never_authorizes_order_or_history(self):
        x = deepcopy(self.gate)
        x['body']['PRICE_BACKTEST_MINIMUM_PIT_READY'] = 'PASS'
        x['historical_visibility_proven'] = True
        x['content_hash'] = digest({k:v for k,v in x.items() if k != 'content_hash'})
        with self.assertRaisesRegex(ValueError, 'FORMAL_HISTORY_NOT_ADMITTED'):
            run_formal(x, actor='HUMAN', approved=True)
        self.assertFalse(self.gate['live_authority'])
        self.assertEqual(self.gate['actual_forward_days'], 0)

    def test_copies_do_not_mutate_pinned_evidence(self):
        x = evidence()
        x['facts'][0]['value'] = '1900-01-01'
        self.assertEqual(evidence()['facts'][0]['value'], '2012-10-09')

    def test_deterministic_matrix_and_gate_replay(self):
        self.assertEqual(self.matrix, three_symbol_matrix())
        self.assertEqual(self.gate, minimum_price_gate())
        canonical(self.matrix)
        canonical(self.gate)


class FixtureHistoryTests(unittest.TestCase):
    def select(self, rows, cutoff=CUTOFF, mode=OBSERVED):
        return select_history(rows, S, EFFECTIVE, cutoff, mode)

    def test_positive_complete_fixture_has_no_actual_authority(self):
        x = self.select(trade_rows())
        self.assertEqual(x['status'], 'SELECTED_FIXTURE_ONLY')
        self.assertFalse(x['safe_to_trade'])
        self.assertFalse(x['historical_visibility_proven'])
        self.assertFalse(x['live_authority'])

    def test_future_status_mutation_does_not_change_prefix(self):
        rows = trade_rows()
        future = trade('ST', 'ST', LATE)
        future['unexpected_future_field'] = 'not revealed'
        self.assertEqual(self.select(rows), self.select(rows + [future]))

    def test_actual_quarantine_same_content_hash_not_synthetic_proof(self):
        rows = trade_rows()
        for r in rows:
            r.update(provenance='QUARANTINED', clock_proof='UNPROVEN')
        x = self.select(rows)
        self.assertEqual(x['status'], 'UNKNOWN')
        self.assertEqual(x['selected'], {})

    def test_actual_self_declared_synthetic_clock_rejected(self):
        rows = trade_rows()
        rows[0]['provenance'] = 'QUARANTINED'
        with self.assertRaisesRegex(ValueError, 'ACTUAL_PROOF_FORBIDDEN'):
            self.select(rows)

    def test_date_only_clock_cannot_impute_midnight(self):
        rows = trade_rows()
        rows[0].update(publication_precision='DATE_ONLY', published_at='2026-07-30T00:00:00+08:00')
        with self.assertRaisesRegex(ValueError, 'DATE_ONLY_OR_UNKNOWN_IMPUTED'):
            self.select(rows)

    def test_reconstruction_is_never_observed_then(self):
        rows = trade_rows()
        for r in rows:
            r['retrieved_at'] = LATE
        observed = self.select(rows)
        reconstructed = self.select(rows, mode=RECONSTRUCT)
        self.assertEqual(observed['status'], 'UNKNOWN')
        self.assertEqual(reconstructed['status'], 'SELECTED_FIXTURE_ONLY')
        self.assertFalse(reconstructed['observed_at_cutoff'])

    def test_absent_rows_unknown_not_normal_or_member(self):
        x = self.select([])
        self.assertEqual(x['status'], 'UNKNOWN')
        self.assertEqual(x['selected'], {})

    def test_invalid_scope_not_expandable_with_valid_hash(self):
        with self.assertRaisesRegex(ValueError, 'SYMBOL_SCOPE'):
            select_history(trade_rows(), '000001.SZ', EFFECTIVE, CUTOFF, OBSERVED)

    def test_financial_future_reporting_period_hidden(self):
        rows = [financial()]
        rows[0]['period'] = '20261231'
        rows[0]['revision_id'] = 'future title hidden'
        x = select_financial(rows, S, '20261231', CUTOFF, OBSERVED)
        self.assertEqual(x['visible_count'], 0)
        self.assertEqual(x['selected'], {})

    def test_financial_future_revision_body_ignored(self):
        first = financial()
        future = financial('later', 'first', LATE)
        future['values'] = {'future': 'SYNTHETIC_OPAQUE'}
        self.assertEqual(select_financial([first], S, PERIOD, CUTOFF, OBSERVED),
                         select_financial([first, future], S, PERIOD, CUTOFF, OBSERVED))

    def test_financial_latest_retrieval_not_historical_visibility(self):
        row = financial()
        row['retrieved_at'] = LATE
        self.assertEqual(select_financial([row], S, PERIOD, CUTOFF, OBSERVED)['status'], 'UNKNOWN')
        x = select_financial([row], S, PERIOD, CUTOFF, RECONSTRUCT)
        self.assertEqual(x['status'], 'SELECTED_FIXTURE_ONLY')
        self.assertFalse(x['observed_at_cutoff'])


def _missing_component(component):
    def test(self):
        x = self.select([r for r in trade_rows() if r['component'] != component])
        self.assertEqual(x['status'], 'UNKNOWN')
        self.assertFalse(x['safe_to_trade'])
    return test


def _current_component(component):
    def test(self):
        rows = trade_rows()
        next(r for r in rows if r['component'] == component)['coverage_kind'] = 'CURRENT_SNAPSHOT'
        x = self.select(rows)
        self.assertEqual(x['status'], 'UNKNOWN')
        self.assertFalse(x['safe_to_trade'])
    return test


for _component in COMPONENTS:
    setattr(FixtureHistoryTests, 'test_missing_' + _component.lower(), _missing_component(_component))
    setattr(FixtureHistoryTests, 'test_current_backfill_' + _component.lower(), _current_component(_component))


if __name__ == '__main__':
    unittest.main()
