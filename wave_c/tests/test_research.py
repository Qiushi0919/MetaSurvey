import unittest,copy,json
from pathlib import Path
from unittest.mock import patch
from decimal import Decimal,localcontext
from wave_c.core import ROOT,ARCHIVE,SYMBOLS,load_real_inputs,assert_registered,digest,seal,_reason,derive,register,_register,context_for
from wave_c.math import raw_statistics,pairwise_rank,mean_score,num,text
from wave_c.research import assess_all,build_features,score
from wave_c.report import make_reports,render
from wave_c.run import verify_saved

class MathTests(unittest.TestCase):
    def test_synthetic_constant_raw_prices(self):
        v=raw_statistics(['10']*61,['2']*61)
        self.assertEqual(v['raw_daily_volatility_20_sessions_pct'],'0.000000');self.assertEqual(v['raw_max_drawdown_60_sessions_pct'],'0.000000')
    def test_synthetic_rising_raw_prices(self):
        v=raw_statistics([str(x) for x in range(1,62)],['2']*61)
        self.assertEqual(v['raw_ma20'],'51.500000');self.assertEqual(v['raw_price_change_20_sessions_pct'],'48.780488')
    def test_synthetic_drawdown_is_negative(self):
        v=raw_statistics(['10']*60+['5'],['2']*61);self.assertEqual(v['raw_max_drawdown_60_sessions_pct'],'-50.000000')
    def test_pairwise_rank_and_tie(self):self.assertEqual(pairwise_rank(['1','2','2']),['0.000000','75.000000','75.000000'])
    def test_inverse_debt_rank(self):self.assertEqual(pairwise_rank(['1','2','3'],'LOWER'),['100.000000','50.000000','0.000000'])
    def test_unknown_not_zero_imputed(self):self.assertEqual(pairwise_rank(['1',None,'3']),[None,None,None]);self.assertIsNone(mean_score(['0',None]))
    def test_small_window_blocks(self):self.assertRaises(ValueError,raw_statistics,['1']*60,['1']*60)
    def test_nonpositive_price_blocks(self):self.assertRaises(ValueError,raw_statistics,['0']*61,['1']*61)
    def test_numeric_float_forbidden(self):self.assertRaises(ValueError,num,1.5)
    def test_nonfinite_forbidden(self):self.assertRaises(ValueError,num,'NaN')
    def test_private_decimal_precision(self):
        with localcontext() as c:c.prec=2;self.assertEqual(mean_score(['100','0','0']),'33.333333')
    def test_half_even_display(self):self.assertEqual(text(Decimal('1.0000005')),'1.000000')
    def test_score_direction_invalid(self):self.assertRaises(ValueError,pairwise_rank,['1','2','3'],'GUESS')

class ActualResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.inputs=load_real_inputs();cls.assessments=assess_all(cls.inputs);cls.reports=make_reports(cls.assessments)
    def test_three_real_symbols(self):self.assertEqual(tuple(x['symbol'] for x in self.inputs),SYMBOLS)
    def test_registered_copy_and_reseal_forbidden(self):
        x=copy.deepcopy(self.inputs[0]);self.assertRaises(ValueError,assert_registered,x)
        self.assertRaises(ValueError,assert_registered,seal({k:v for k,v in x.items() if k!='content_hash'}))
    def test_former_generic_mint_and_derive_forbidden(self):
        self.assertRaises(ValueError,derive,self.inputs[0],'Assessment',{'quality_score':'SYNTHETIC_INJECTION'},tuple(self.inputs[1:]))
        self.assertRaises(ValueError,register,self.assessments[0],*context_for(self.inputs[0]))
    def test_private_mint_recomputes_and_rejects_forged_assessment(self):
        ctx,upstream=context_for(self.inputs[0]);body=copy.deepcopy(self.assessments[0]);body.pop('content_hash');body['body']['quality_score']['value']='99.999999'
        self.assertRaises(ValueError,_register,body,ctx,upstream,tuple(self.inputs))
    def test_private_mint_recomputes_and_rejects_forged_input(self):
        ctx,upstream=context_for(self.inputs[0]);body=copy.deepcopy(self.inputs[0]);body.pop('content_hash');body['body']['observations'][0]['values']['name']='SYNTHETIC_FORGERY'
        self.assertRaises(ValueError,_register,body,ctx,upstream)
    def test_context_copy_cannot_change_issued_methods(self):
        ctx,upstream=context_for(self.inputs[0]);ctx['rules']['quality']['metrics']['roe']='LOWER';assert_registered(self.reports[0])
        body={k:v for k,v in self.inputs[0].items() if k!='content_hash'};self.assertRaises(ValueError,_register,body,ctx,upstream)
    def test_unknown_production_config(self):
        for r in self.reports:self.assertFalse(r['productionGate']);self.assertEqual(r['real_account_settings'],'UNSET_REQUIRED')
    def test_historical_available_at_not_backfilled(self):
        for x in self.inputs:
            for o in x['body']['observations']:self.assertEqual(o['source_ref']['available_at'],o['source_ref']['retrieved_at']);self.assertIsNone(o['source_ref']['published_at'])
    def test_empty_status_remains_unknown(self):
        for a in self.assessments:
            for f in a['body']['features']:
                if f['name'] in ('st_status','suspension_status'):self.assertIsNone(f['value']);self.assertEqual(f['state'],'UNKNOWN')
    def test_no_ttm_pe_from_quarter_eps(self):
        for a in self.assessments:self.assertIsNone(next(f['value'] for f in a['body']['features'] if f['name']=='valuation_ttm_pe'))
    def test_actual_quality_and_timing_have_real_values(self):
        for a in self.assessments:
            self.assertIsNotNone(a['body']['quality_score']['value']);self.assertIsNotNone(a['body']['timing_score']['value'])
    def test_real_feature_sources_are_bound(self):
        for a in self.assessments:
            for f in a['body']['features']:
                if f['value'] is not None:self.assertTrue(f['source_refs'])
    def test_grade_probability_and_edge_unknown(self):
        for a in self.assessments:self.assertEqual(a['body']['experimental_grade'],'UNSET_REQUIRED');self.assertEqual(a['body']['quality_score']['probability_claim'],'UNSET_REQUIRED')
    def test_future_publication_literal_excluded(self):
        q={'api_name':'dividend','response_blocked':False,'retrieved_at':'2026-10-06T01:00:00Z'}
        self.assertEqual(_reason(q,{'values':{'ann_date':'20261007'}},'2026-10-06T02:00:00Z'),'FUTURE_PUBLICATION_LITERAL')
    def test_future_action_schedule_not_realized(self):
        q={'api_name':'dividend','response_blocked':False,'retrieved_at':'2026-10-06T01:00:00Z'}
        self.assertIsNone(_reason(q,{'values':{'ann_date':'20261005','pay_date':'20261101'}},'2026-10-06T02:00:00Z'))
    def test_current_industry_never_historical(self):
        for a in self.assessments:self.assertIsNone(next(f['value'] for f in a['body']['features'] if f['name']=='historical_industry_membership'))
    def test_whole_blocked_financial_not_consumed(self):
        for x in self.inputs:self.assertTrue(any(z['api_name']=='fina_indicator' for z in x['body']['excluded']))
    def test_quality_does_not_supply_timing_inputs(self):
        for a in self.assessments:
            q={x['feature_name'] for x in a['body']['quality_score']['component_scores']['components']};t={x['feature_name'] for x in a['body']['timing_score']['component_scores']['components']};self.assertFalse(q&t)
    def test_high_quality_low_timing_counterexample(self):
        synthetic=[[{'name':'q','value':str(q),'source_refs':[]},{'name':'t','value':str(t),'source_refs':[]}] for q,t in [(3,1),(2,2),(1,3)]]
        rules={'quality':{'meaning':'SYNTHETIC_UNCALIBRATED'},'timing':{'meaning':'SYNTHETIC_UNCALIBRATED'}}
        self.assertEqual(score('quality',{'q':'HIGHER'},synthetic,rules)[0]['value'],'100.000000');self.assertEqual(score('timing',{'t':'HIGHER'},synthetic,rules)[0]['value'],'0.000000')
    def test_financial_period_mismatch_blocks_quality(self):
        synthetic=[[{'name':'q','value':str(i),'source_refs':[]},{'name':'latest_observed_report_period','value':period,'source_refs':[]}] for i,period in enumerate(['20250630','20260630','20260630'])]
        self.assertTrue(all(s['value'] is None for s in score('quality',{'q':'HIGHER'},synthetic,{'quality':{'meaning':'SYNTHETIC'}})))
    def test_render_contains_ten_dimensions(self):
        for r in self.reports:self.assertEqual(len(r['body']['sections']),10);self.assertIn('为何当前不可交易',render(r));self.assertIn('UNKNOWN',render(r))
    def test_report_mutation_rejected(self):
        x=self.reports[0];old=x['tradeable'];x['tradeable']=True
        try:self.assertRaises(ValueError,assert_registered,x)
        finally:x['tradeable']=old
    def test_rule_code_and_source_mutation_invalidates(self):
        source=json.loads((ROOT/'docs/p1b-real-admission/Gate.json').read_bytes())['raw_inventory'][0]['path']
        provider=json.loads((ROOT/'docs/wave-c/provider-resolution.json').read_bytes())
        for path in [ROOT/'docs/wave-c/rules.json',ROOT/'wave_c/math.py',Path(source),ROOT/'docs/wave-c/provider-resolution.json',Path(provider['references'][0]['path'])]:
            original=Path.read_bytes
            def read(p):return original(p)+(b' ' if p==path else b'')
            with patch.object(Path,'read_bytes',read):self.assertRaises(ValueError,assert_registered,self.reports[0])
    def test_deterministic_persisted_replay(self):self.assertTrue(verify_saved()['deterministic'])
    def test_cross_namespace_rejected(self):self.assertRaises(ValueError,assess_all,list(reversed(self.inputs)))

if __name__=='__main__':unittest.main()
