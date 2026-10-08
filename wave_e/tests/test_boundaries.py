"""Actual frozen-source boundaries; mutations simulated without editing originals."""
import copy, gzip, json, unittest
from unittest.mock import patch
from pathlib import Path
from wave_e import core, public
from wave_e.core import ROOT, ARCHIVE, SYMBOLS, NAMES, canonical, digest, frozen_context, context_hash, price_series, objects, assert_registered, transition, private_ref
from wave_e.run import verify_saved

class Boundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ctx=frozen_context();cls.values,cls.blobs=objects()
    def test_four_registered_positive_display_objects(self):
        self.assertEqual(tuple(x['contract_name'] for x in self.values),NAMES)
        for x in self.values:self.assertIs(transition(x,'LOCAL_DIAGNOSTIC_DISPLAY'),x)
    def test_caller_cannot_issue_arbitrary_body(self):
        for f in (core.register,core.derive):
            with self.assertRaises(ValueError):f(self.values[0])
        with self.assertRaises(TypeError):objects({'productionGate':True})
    def test_copy_reseal_cannot_be_registered(self):
        x=copy.deepcopy(self.values[0]);x['content_hash']=digest({k:v for k,v in x.items() if k!='content_hash'})
        with self.assertRaises(ValueError):assert_registered(x)
    def test_live_object_mutation_invalidates(self):
        x=self.values[0];old=x['body']['ENGINE_DIAGNOSTIC_READY']
        try:
            x['body']['ENGINE_DIAGNOSTIC_READY']='FORMAL_PRICE_BACKTEST_READY'
            with self.assertRaises(ValueError):assert_registered(x)
        finally:x['body']['ENGINE_DIAGNOSTIC_READY']=old
    def test_context_drift_invalidates_registered_object(self):
        q=copy.deepcopy(self.ctx);q['rules_hash']='sha256:'+'0'*64
        with patch.object(core,'frozen_context',return_value=q):
            with self.assertRaises(ValueError):assert_registered(self.values[0])
    def test_checked_source_mutation_fails_without_editing_original(self):
        real=core.checked_file
        def changed(p,expected=None):
            if p==ROOT/'wave_e/engine.py':raise ValueError('SIMULATED_SOURCE_DRIFT')
            return real(p,expected)
        with patch.object(core,'checked_file',side_effect=changed):
            with self.assertRaises(ValueError):assert_registered(self.values[0])
    def test_predecessor_gate_owner_literal_unchanged(self):
        old=json.loads((ROOT/'docs/wave-d/Gate.json').read_bytes());self.assertEqual(old['owner_acceptance'],'PENDING');self.assertFalse(old['productionGate'])
        current=json.loads((ROOT/'docs/wave-e/baseline-acceptance.json').read_bytes());self.assertEqual(current['owner_decision'],'ACCEPT_WITH_CONDITIONS_LOCAL_ONLY_ENGINEERING');self.assertFalse(current['downstream_admission_inferred'])
    def test_real_frozen_prices_exact_cohort_no_financial_fields(self):
        paths,meta=price_series(self.ctx);self.assertEqual(len(paths),2);self.assertEqual(len(meta),3)
        for series in paths.values():
            self.assertEqual(tuple(series),SYMBOLS)
            for rows in series.values():
                self.assertEqual(len(rows),327)
                for r in rows:self.assertEqual(set(r),{'trade_date','open','high','low','close','source_ref'})
    def test_current_observation_clocks_never_historical_pit(self):
        for x in self.values:self.assertFalse(x['historical_visibility_proven']);self.assertFalse(x['body'].get('formal_strategy_evidence',False))
    def test_readiness_domains_independent_and_formal_blocked(self):
        x=self.values[0]['body'];self.assertEqual(len(x['conditions']),18);self.assertEqual(x['ENGINE_DIAGNOSTIC_READY'],'READY');self.assertEqual(x['FORMAL_PRICE_BACKTEST_READY'],'BLOCKED');self.assertEqual(x['FORMAL_FUNDAMENTAL_PIT_BACKTEST_READY'],'BLOCKED');self.assertEqual(x['unset_actual_parameters'],30)
    def test_diagnostic_unknown_status_path_has_zero_fills(self):
        x=self.values[1]['body'];self.assertEqual(len(x['scenarios']),8)
        for s in x['scenarios']:
            self.assertFalse(s['tradeability_proven']);self.assertEqual(s['financial_features_used'],0)
            if s['name'].endswith(':UNKNOWN_BLOCK'):self.assertEqual(s['hypothetical_fills_count'],0)
    def test_replay_saved_private_bytes(self):self.assertTrue(verify_saved()['byte_identical'])
    def test_ledger_position_and_equity_records_exist(self):
        self.assertEqual(len([k for k in self.blobs if k.endswith('position-ledger.jsonl')]),8)
        self.assertEqual(len([k for k in self.blobs if k.endswith('equity-curve.csv')]),8)
    def test_all_actual_lookahead_prefix_proofs_pass(self):
        a=json.loads(self.blobs['lookahead-audit.json']);self.assertEqual(len(a['scenarios']),8)
        for x in a['scenarios']:
            self.assertEqual(len(x['prefix_proofs']),3);self.assertFalse(x['historical_pit_proven']);self.assertEqual(x['same_bar_fill_count'],0)
    def test_action_gaps_and_tolerance_never_closed(self):
        x=json.loads(self.blobs['action-adjustment-sensitivity.json']);self.assertEqual(x['preserved_multi_original_action_ambiguities'],5);self.assertEqual(x['preserved_nonzero_pre_close_deltas'],8);self.assertEqual(x['tolerance'],'UNSET_REQUIRED');self.assertFalse(x['authoritative_adjusted_price']);self.assertFalse(x['cash_dividend_share_credits']);self.assertFalse(x['total_return'])
    def test_zero_cost_not_net_edge(self):
        x=json.loads(self.blobs['cost-sensitivity.json']);self.assertFalse(x['net_edge_computed']);self.assertTrue(x['all_parameters_synthetic_DPU'])
    def test_factor_paths_separate_and_first_day_anchor(self):
        paths,_=price_series(self.ctx)
        for s in SYMBOLS:
            raw=paths['RAW_UNADJUSTED_OBSERVED'][s];adj=paths['FACTOR_FIRST_ANCHOR_SENSITIVITY_ONLY'][s]
            self.assertEqual(adj[0]['close'],raw[0]['close']);self.assertEqual(adj[-1]['source_ref']['anchor_day'],raw[0]['trade_date']);self.assertFalse(adj[-1]['source_ref']['authoritative_adjustment'])
    def test_status_and_universe_unknown_disclosed(self):
        x=json.loads(self.blobs['tradeability-assumption-registry.json'])
        for s in x['scenarios']:
            self.assertEqual(s['suspension'],'UNKNOWN');self.assertEqual(s['delisting'],'UNKNOWN');self.assertTrue(s['survivorship_bias_disclosed'])
    def test_native_and_cloud_transition_always_block(self):
        for x in self.values:
            for target in ('ResearchCard','CandidateEligibility','SignalEvent','Approval','OrderIntent','Fill','CLOUD_MODEL','FORMAL_PRICE_BACKTEST_READY'):
                with self.assertRaises(ValueError):transition(x,target)
    def test_snapshot_b_not_started_even_owner_like_dictionary(self):
        self.assertFalse(self.values[2]['body']['actual_run_executed'])
        with self.assertRaises(ValueError):core.run_snapshot_b({'actor_type':'HUMAN_USER','approved':True})
    def test_forward_actual_days_zero_not_scheduled(self):
        x=self.values[3]['body'];self.assertEqual(x['actual_forward_days'],0);self.assertFalse(x['scheduling_enabled']);self.assertFalse(x['actual_ledger_started']);self.assertEqual(x['minimum_actual_sessions'],20)
    def test_public_requests_no_entitlement(self):
        x=self.ctx['public'];self.assertEqual(x['public_GET_requests'],22);self.assertEqual(x['authenticated_requests'],0);self.assertEqual(x['credential_lookups'],0)
        for q in x['references']:self.assertFalse(q['credentials_attached']);self.assertEqual(q['reference_identity'],'PUBLIC_DOCUMENT_ONLY_NO_ACCOUNT_ENTITLEMENT')
    def test_official_docs_api_identity_from_heading(self):
        expected={32:'daily_basic',33:'income',36:'balancesheet',44:'cashflow',79:'fina_indicator'}
        for n,api in expected.items():
            q=next(x for x in self.ctx['public']['references'] if x['request_url'].endswith('doc_id='+str(n)));text=public.html_text(private_ref(q['decoded_ref']));self.assertIn('接口：'+api,''.join(text.split()))
    def test_sse_failed_bodies_never_operating_facts(self):
        self.assertEqual(len(self.ctx['public']['documents']),6)
        for d in self.ctx['public']['documents']:self.assertFalse(d['body_verified']);self.assertIsNone(d['text_ref']);self.assertEqual(d['reason'],'WAVE_E_SSE_DECODED_RESPONSE_NOT_PDF')
    def test_compressed_html_cannot_be_pdf(self):
        raw=public.decode(gzip.compress(b'<html>not a pdf</html>'),'gzip');fact=self.ctx['public']['documents'][0]['index_fact']
        with self.assertRaises(ValueError):public.pdf_identity(raw,fact)
    def test_unexpected_official_redirect_and_query_block(self):
        origin=self.ctx['public']['documents'][0]['index_fact']['uri']
        for target in ('https://unapproved.invalid/a.pdf',origin.replace('www.sse','static.sse')+'?auth=synthetic','http://static.sse.com.cn/a.pdf'):
            with self.assertRaises(ValueError):public.allowed_redirect(origin,target)
    def test_private_archive_substitution_outside_fixed_root(self):
        r=json.loads((ROOT/'docs/wave-e/public-ref.json').read_bytes());r['path']='/tmp/report.json'
        with self.assertRaises(ValueError):private_ref(r)
    def test_price_available_after_cutoff_blocks_without_mutation(self):
        ctx=copy.deepcopy(self.ctx);r=next(x for x in ctx['inputs'][0]['body']['observations'] if x['api_name']=='daily');r['source_ref']['available_at']='2099-01-01T18:00:00Z';r['source_ref']['retrieved_at']=r['source_ref']['available_at']
        with self.assertRaises(ValueError):price_series(ctx)
    def test_conflicting_duplicate_price_version_blocks(self):
        ctx=copy.deepcopy(self.ctx);obs=ctx['inputs'][0]['body']['observations'];r=copy.deepcopy(next(x for x in obs if x['api_name']=='daily'));r['values']['close']='1.234567';obs.append(r)
        with self.assertRaises(ValueError):price_series(ctx)
    def test_missing_factor_day_blocks_whole_run(self):
        ctx=copy.deepcopy(self.ctx);obs=ctx['inputs'][0]['body']['observations'];d=next(x['values']['trade_date'] for x in obs if x['api_name']=='adj_factor');ctx['inputs'][0]['body']['observations']=[x for x in obs if not (x['api_name']=='adj_factor' and x['values']['trade_date']==d)]
        with self.assertRaises(ValueError):price_series(ctx)

if __name__=='__main__':unittest.main()
