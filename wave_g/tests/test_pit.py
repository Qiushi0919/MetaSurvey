"""Actual original/clock integrity and meaningful synthetic PIT adversaries."""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from unittest.mock import patch
import json
import tempfile
import unittest

import wave_g.pit as mod
import wave_g.common as shared
from wave_g.common import SYMBOLS, canonical, digest
from post_wave_e.tests.test_pit import trade_rows, trade, financial, PERIOD, FIRST, LATE, EFFECTIVE, CUTOFF


class ActualPITTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x=mod.evidence();cls.m=mod.evidence_matrix();cls.p=mod.pit_progress()

    def fact(self,fid):
        return next(f for f in self.x['new_facts'] if f['fact_id']==fid)

    def test_bounded_exact_scope_and_no_auth(self):
        self.assertEqual(self.x['exact_symbols'],list(SYMBOLS))
        self.assertEqual(self.x['actual_public_GET_requests'],len(self.x['captures']))
        self.assertLessEqual(len(self.x['captures']),16)
        self.assertLessEqual(self.x['discovery_query_count'],12)
        self.assertLessEqual(self.x['discovery_tool_calls'],4)
        self.assertEqual((self.x['authenticated_requests'],self.x['credential_lookups'],self.x['redirect_followed_count']),(0,0,0))
        self.assertTrue(all(c['http_status']==200 for c in self.x['captures']))

    def test_oct8_calendar_uses_actual_document_date_not_directory(self):
        f=self.fact('SSE_2026_OCT8_PLANNED_REOPEN_VERIFIED')
        self.assertEqual((f['publication_date'],f['value']['url_directory_date']),('2026-09-17','2026-09-15'))
        self.assertEqual(f['value']['planned_resume'],'2026-10-08')
        self.assertIsNone(f['historical_available_at'])
        self.assertFalse(f['observed_at_the_time'])
        self.assertFalse(f['value']['generation_time_is_publication_or_availability_proof'])

    def test_current_retrieval_and_date_only_never_historical_available(self):
        for c in self.x['captures']:
            self.assertIsNone(c['published_at']);self.assertIsNone(c['available_at'])
            self.assertFalse(c['path_date_is_publication_proof'])
        for f in self.x['new_facts']:
            self.assertIsNone(f['historical_available_at'])
            self.assertFalse(f['historical_visibility_proven'])
            self.assertFalse(f['observed_at_the_time'])

    def test_differential_action_oracle_and_a_share_scope(self):
        f=self.fact('CMOC_2024_DIFFERENTIAL_EX_REFERENCE')['value']
        expected=(Decimal('17460842176')*Decimal('0.255')/Decimal('17565772619')).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP)
        self.assertEqual(expected,Decimal(f['ex_reference_cash_cny_per_share']))
        self.assertNotEqual(f['gross_cash_cny_per_share'],f['ex_reference_cash_cny_per_share'])
        action=self.fact('CMOC_2024_A_SHARE_DISTRIBUTION_NOTICE')['value']
        self.assertEqual(action['share_class'],'A_SHARE_ONLY_H_SHARE_EXCLUDED')
        self.assertEqual((action['record_date'],action['ex_date'],action['announced_cash_payment_date']),('2025-06-26','2025-06-27','2025-06-27'))
        self.assertTrue(action['announced_payment_not_account_receipt'])
        self.assertFalse(f['factor_plus_cash_double_count_permitted'])
        self.assertEqual(f['adjustment_factor_linkage'],'UNKNOWN')

    def test_jingwang_later_claim_not_primary_implementation(self):
        f=self.fact('JINGWANG_2024_ACTION_RETROSPECTIVE_CLAIM')
        self.assertEqual(f['issuer_name'],'深圳市景旺电子股份有限公司')
        self.assertEqual(f['value']['announcement_number'],'2025-071')
        self.assertEqual((f['publication_date'],f['effective_date']),('2025-07-10','2025-06-11'))
        self.assertFalse(f['value']['primary_implementation_notice_captured'])
        for key in ('record_date','ex_date','cash_receipt_date'):self.assertEqual(f['value'][key],'UNKNOWN')

    def test_half_report_name_units_and_proposal_remain_local(self):
        n=self.fact('PINGGAO_2024_HALF_REPORT_NAME_ANCHOR')
        self.assertIsNone(n['publication_date'])
        self.assertEqual(n['value']['document_security_name'],'平高电气')
        self.assertEqual(n['value']['previous_name_cell'],'DASH_NOT_CONTINUOUS_NO_NAME_CHANGE_PROOF')
        f=self.fact('PINGGAO_2024_HALF_REPORT_UNIT_AND_PROPOSAL')['value']
        self.assertEqual((f['table_amount_unit'],f['provider_unit_mapping']),('CNY_YUAN','UNKNOWN'))
        self.assertTrue(f['unaudited']);self.assertTrue(f['proposal_requires_shareholder_approval'])
        self.assertEqual(f['implementation_date'],'UNKNOWN')

    def test_abnormal_move_and_no_correction_not_st_or_revision_proof(self):
        f=self.fact('JINGWANG_2025_ABNORMAL_MOVE_DATED_CLAIM')['value']
        self.assertEqual(f['issuer_claimed_trading_dates'],['2025-09-10','2025-09-11','2025-09-12'])
        self.assertEqual((f['st_status'],f['full_daily_suspension_status']),('UNKNOWN','UNKNOWN'))
        r=self.fact('JINGWANG_2025_NO_CORRECTION_STATEMENT')['value']
        self.assertFalse(r['revision_chain_proven']);self.assertEqual(r['financial_first_visibility'],'UNKNOWN')

    def test_all_continuous_gaps_unchanged_and_missing_never_no(self):
        self.assertEqual(self.m['body']['continuous_historical_domains_closed'],0)
        for row in self.m['body']['rows']:
            self.assertFalse(row['historical_visibility_proven'])
            for d in row['domains']:
                self.assertEqual(d['covered_intervals'],[])
                self.assertEqual(d['absence_means'],'UNKNOWN')
                self.assertFalse(d['can_trade'])
                if d['domain']!='listing_anchor':self.assertEqual(d['historical_coverage'],'UNKNOWN')

    def test_old_redirect_failures_and_new_preparation_failures_retained(self):
        self.assertEqual(sorted(self.x['predecessor_failed_capture_ids']),['action-603228','financial-600312','financial-600312-www'])
        self.assertTrue(all(Path(r['path']).is_file() for r in mod.preserved_refs()))
        failures=[json.loads(Path(r['path']).read_text()) for r in mod.preserved_refs() if r['path'].endswith('.json') and 'validation' in r['path']]
        self.assertTrue(all(f['result']=='FAIL' for f in failures))
        self.assertEqual({f['failure'] for f in failures},{'FACT_ID_ISSUER_MISLABEL','ANNOUNCEMENT_NUMBER_TRANSCRIPTION'})

    def test_all_direct_originals_and_failed_epochs_private_and_pinned(self):
        rs=mod.source_pins();self.assertEqual(len(rs),len({r['path'] for r in rs}))
        for r in mod.evidence_refs():
            p=Path(r['path']);self.assertFalse(p.is_symlink())
            self.assertEqual(p.stat().st_mode&0o777,0o600)
            self.assertEqual(p.stat().st_size,r['bytes'])
        self.assertIn(str(mod.EVIDENCE_PATH),{r['path'] for r in rs})

    def test_every_pinned_source_mutation_fails_before_result(self):
        original=mod.checked_file
        for r in mod.source_pins():
            with self.subTest(path=Path(r['path']).name):
                target=str(mod.locate_reference(r['path']))
                def read(path,expected=None):
                    if str(path)==target:
                        self.assertEqual(expected,r['sha256']);raise ValueError('TEST_ORIGINAL_MUTATED')
                    return original(path,expected)
                with patch.object(mod,'checked_file',side_effect=read):
                    with self.assertRaisesRegex(ValueError,'TEST_ORIGINAL_MUTATED'):mod.evidence_matrix()

    def test_relocated_git_reference_reads_actual_checkout_and_detects_mutation(self):
        refs=[self.x['predecessor_matrix_ref'],self.x['predecessor_price_gate_ref']]
        originals={r['path']:Path(shared.locate_reference(r['path'])).read_bytes() for r in refs}
        with tempfile.TemporaryDirectory(dir=mod.ARCHIVE/'validation/pit',prefix='synthetic-checkout-') as tmp:
            checkout=Path(tmp)
            for r in refs:
                target=checkout/Path(r['path']).relative_to(shared.BASELINE_ROOT)
                target.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
                target.write_bytes(originals[r['path']]);target.chmod(0o600)
            before=deepcopy(refs)
            read=mod.checked_file
            actual_reads=[]
            def local_read(path,expected=None):
                # A fallback to the original checkout would fail this positive case.
                self.assertNotIn(str(path),originals)
                actual_reads.append(str(path))
                return read(path,expected)
            with patch.object(shared,'ROOT',checkout),patch.object(mod,'ROOT',checkout),patch.object(mod,'checked_file',side_effect=local_read):
                for r in refs:self.assertEqual(mod._ref(r,False),originals[r['path']])
                self.assertEqual(refs,before)
                for r in refs:
                    target=checkout/Path(r['path']).relative_to(shared.BASELINE_ROOT)
                    self.assertIn(str(target),actual_reads)
                    target.write_bytes(originals[r['path']]+b'\nSYNTHETIC_MUTATION\n')
                    with self.assertRaisesRegex(ValueError,'DEPENDENCY_INVALIDATED'):mod._ref(r,False)
                    target.write_bytes(originals[r['path']])
                self.assertEqual(mod.evidence_matrix(),self.m)
            for r in refs:
                self.assertEqual(Path(shared.locate_reference(r['path'])).read_bytes(),originals[r['path']])

    def test_mapping_keeps_two_document_allowlist_and_private_archive_fixed(self):
        r=deepcopy(self.x['predecessor_matrix_ref'])
        r['path']=str(shared.BASELINE_ROOT/'docs/wave-f/Wave-F-Gate-Review.md')
        with self.assertRaisesRegex(ValueError,'PREDECESSOR_PATH'):mod._ref(r,False)
        p=Path(self.x['captures'][0]['body_ref']['path'])
        self.assertEqual(shared.locate_reference(p),p)

    def test_manifest_clock_and_status_promotions_rejected(self):
        changes=[lambda x:x.update(historical_visibility_proven=True),
                 lambda x:x['captures'][0].update(available_at='2025-01-01T00:00:00Z'),
                 lambda x:x['captures'][0].update(path_date_is_publication_proof=True),
                 lambda x:x['new_facts'][0].update(observed_at_the_time=True),
                 lambda x:x['new_facts'][0].update(can_trade=True),
                 lambda x:x['new_facts'][0].update(historical_available_at='2025-06-23T00:00:00+08:00'),
                 lambda x:x['new_facts'][0].update(symbol='300322.SZ')]
        for mutate in changes:
            x=deepcopy(self.x);mutate(x)
            with self.assertRaises(ValueError):mod._validate_manifest(x)

    def test_cash_factor_conflation_and_statement_scope_rejected(self):
        x=deepcopy(self.x)
        f=next(f for f in x['new_facts'] if f['fact_id']=='CMOC_2024_DIFFERENTIAL_EX_REFERENCE')
        f['value']['ex_reference_cash_cny_per_share']='0.255'
        with self.assertRaisesRegex(ValueError,'CASH_FACTOR_CONFLATION'):mod._validate_manifest(x)
        x=deepcopy(self.x)
        f=next(f for f in x['new_facts'] if f['fact_id']=='JINGWANG_2024_ACTION_RETROSPECTIVE_CLAIM')
        f['value']['primary_implementation_notice_captured']=True
        with self.assertRaisesRegex(ValueError,'ACTION_CLAIM_SCOPE'):mod._validate_manifest(x)

    def test_planned_open_does_not_fake_actual_session(self):
        for day,want in [('2026-10-08','PLANNED_OPEN'),('2026-10-07','HOLIDAY_CLOSED'),
                         ('2026-10-10','WEEKEND_CLOSED'),('2025-10-08','HOLIDAY_CLOSED'),('2025-10-09','PLANNED_OPEN')]:
            x=mod.planned_calendar_day(day)
            self.assertEqual(x['body']['planned_status'],want)
            self.assertEqual(x['body']['actual_session'],'UNKNOWN')
            self.assertEqual(x['body']['eod_complete'],'UNKNOWN')
            self.assertFalse(x['live_authority']);self.assertFalse(x['body']['safe_to_trade'])
        for day in ('2026-10-08T00:00:00Z','2024-10-08','2026-02-30'):
            with self.assertRaises(ValueError):mod.planned_calendar_day(day)

    def test_no_caller_authority_and_resealed_metadata_cannot_run(self):
        for fn in (mod.evidence_matrix,mod.pit_progress):
            with self.assertRaises(TypeError):fn({'Owner':'HUMAN','PIT':'PASS'})
        fake=deepcopy(self.p);fake['live_authority']=True;fake['content_hash']=digest(fake)
        with self.assertRaisesRegex(ValueError,'WG_SEPARATE_HUMAN_ACTIVATION_AUTHORIZATION_REQUIRED'):
            mod.run_formal(fake,owner_approved=True)
        self.assertFalse(self.p['body']['formal_price_backtest_ready'])
        self.assertFalse(self.p['body']['formal_fundamental_pit_ready'])
        self.assertEqual(self.p['actual_forward_days'],0)

    def test_deterministic_copies_do_not_change_sources(self):
        self.assertEqual(self.m,mod.evidence_matrix());self.assertEqual(self.p,mod.pit_progress())
        x=mod.evidence();x['new_facts'][0]['value']['gross_cash_cny_per_share']='999'
        self.assertEqual(mod.evidence(),self.x)
        canonical(self.m);canonical(self.p)


class PITFixtureAdversaries(unittest.TestCase):
    def status(self,rows,mode='OBSERVED_AT_TIME'):
        return mod.select_history(rows,SYMBOLS[0],EFFECTIVE,CUTOFF,mode)

    def financial(self,rows,mode='OBSERVED_AT_TIME'):
        return mod.select_financial_fixture(rows,SYMBOLS[0],PERIOD,CUTOFF,mode)

    def test_future_status_body_and_future_revision_cannot_affect_prefix(self):
        base=self.status(trade_rows());future=trade('ST','ST',LATE);future['future_unchecked_field']='hidden'
        self.assertEqual(base,self.status(trade_rows()+[future]))
        base=self.financial([financial()]);future=financial('future','missing-parent',LATE)
        future['values']={'future_profit':'999999'};future['future_unchecked_field']='hidden'
        self.assertEqual(base,self.financial([future,financial()]))

    def test_late_retrieval_distinguishes_observed_from_reconstruction(self):
        r=financial();r['retrieved_at']=LATE
        self.assertEqual(self.financial([r])['status'],'UNKNOWN')
        x=self.financial([r],'HISTORICAL_AVAILABILITY_RECONSTRUCTION')
        self.assertEqual(x['status'],'SELECTED_FIXTURE_ONLY')
        self.assertFalse(x['observed_at_cutoff']);self.assertFalse(x['historical_visibility_proven'])

    def test_date_only_cannot_impute_midnight_and_current_rows_unknown(self):
        r=financial();r.update(publication_precision='DATE_ONLY',published_at=None,date_only_fields={'ann_date':'20260730'})
        self.assertEqual(self.financial([r])['status'],'UNKNOWN')
        r['published_at']='2026-07-30T00:00:00+08:00'
        with self.assertRaisesRegex(ValueError,'DATE_ONLY_OR_UNKNOWN_IMPUTED'):self.financial([r])
        rows=trade_rows()
        for r in rows:r.update(provenance='QUARANTINED',clock_proof='UNPROVEN',coverage_kind='CURRENT_SNAPSHOT')
        self.assertEqual(self.status(rows)['status'],'UNKNOWN')

    def test_missing_suspension_st_and_conflicting_status_never_normal(self):
        for component in ('ST','SUSPENSION'):
            rows=[r for r in trade_rows() if r['component']!=component]
            self.assertEqual(self.status(rows)['status'],'UNKNOWN')
        rows=trade_rows()+[trade('ST','ST','2026-08-01T10:00:00+08:00')]
        self.assertEqual(self.status(rows)['status'],'UNKNOWN')
        self.assertFalse(self.status(trade_rows())['safe_to_trade'])

    def test_revision_chain_missing_parent_duplicate_and_current_snapshot(self):
        for rows in ([financial('later','absent')],
                     [financial(),financial('second',None)],
                     [financial()|{'coverage_kind':'CURRENT_REVISION_SNAPSHOT'}]):
            self.assertEqual(self.financial(rows)['status'],'UNKNOWN')
        later=financial('later','first','2026-08-01T10:00:00+08:00')
        x=self.financial([later,financial()])
        self.assertEqual(x['selected']['INCOME']['revision_id'],'later')
        self.assertFalse(x['live_authority']);self.assertFalse(x['safe_to_trade'])

    def test_future_period_and_fake_actual_exact_clock_rejected(self):
        x=mod.select_financial_fixture([],SYMBOLS[0],'20261231',CUTOFF,'OBSERVED_AT_TIME')
        self.assertEqual(x['status'],'UNKNOWN')
        self.assertIn('FUTURE_REPORTING_PERIOD_NOT_VISIBLE',x['reason_codes'])
        r=financial();r['provenance']='QUARANTINED'
        with self.assertRaisesRegex(ValueError,'ACTUAL_PROOF_FORBIDDEN'):self.financial([r])


if __name__=='__main__':unittest.main()
