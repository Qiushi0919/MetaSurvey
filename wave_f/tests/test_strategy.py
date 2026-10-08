import json, unittest
from copy import deepcopy
from unittest.mock import patch
from wave_f.common import *
from wave_f import strategy as s

def bundle():
    values = {'ttm_revenue_growth':'0.1','gross_margin_change':'0.01',
        'operating_cash_to_net_income':'1','net_income_positive':True,
        'roic_above_cost_of_capital':True,'net_debt_to_ebitda':'1',
        'valuation_percentile':'0.4','official_catalyst_unexpired':True,
        'evidence_complete':True,'hard_risk':False,'historical_tradeable':True,
        'net_edge_bps':'500','gross_expected_bps':'650','round_trip_cost_bps':'100',
        'uncertainty_buffer_bps':'50','edge_to_cost_ratio':'5',
        'close_above_ma60':True,'ma60_slope_20':'1','sector_rs20':'0.04',
        'distance_ma20_atr':'0.5','volume3_to_volume20':'0.5',
        'close_above_previous3_high':True,'breakout60_ratio':'0.01',
        'volume_to_volume20':'2','extension_from_breakout':'0.02'}
    return {'provenance':LABEL,'symbol':SYMBOLS[0], 'decision_at':'2026-10-01T16:30:00.000000001+08:00',
            'features':{k:{'value':values[k],'unit':unit,'available_at':'2026-09-30T16:00:00+08:00',
                'retrieved_at':'2026-09-30T17:00:00+08:00','source_hash':digest({'fixture':k}),
                'period_end':'2026-06-30' if k in s.FINANCIAL else None} for k,unit in s.FEATURE_UNITS.items()}}

class StrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=json.loads(checked_file(s.SPEC)); cls.spec_hash=digest(cls.spec)
    def evaluate(self,b=None,f='CORE40_Q_PULLBACK_V1'):
        return s.evaluate_fixture(f,b or bundle(),self.spec_hash)
    def test_two_families_registered_not_ma_diagnostic(self):
        self.assertEqual(2,self.spec['family_count']);self.assertFalse(self.spec['fairness']['optimization_performed'])
        self.assertTrue(self.spec['fairness']['wave_e_ma20_ma60_not_final_owner_strategy'])
    def test_pullback_fixture_rule(self): self.assertEqual('HYPOTHETICAL_RESEARCH_MATCH',self.evaluate()['decision'])
    def test_breakout_fixture_rule(self): self.assertEqual('HYPOTHETICAL_RESEARCH_MATCH',self.evaluate(f='CORE40_Q_BREAKOUT_V1')['decision'])
    def test_failures_not_winner_selected(self):
        b=bundle();b['features']['sector_rs20']['value']='0'
        for f in ('CORE40_Q_PULLBACK_V1','CORE40_Q_BREAKOUT_V1'): self.assertEqual('NO_DECISION',self.evaluate(b,f)['decision'])
    def test_exact_cost_included_edge(self):
        b=bundle();b['features']['net_edge_bps']['value']='600'
        with self.assertRaisesRegex(ValueError,'NET_EDGE_RECONCILIATION'):self.evaluate(b)
    def test_cost_ratio_reconciled(self):
        b=bundle();b['features']['edge_to_cost_ratio']['value']='100'
        with self.assertRaisesRegex(ValueError,'EDGE_COST_RECONCILIATION'):self.evaluate(b)
    def test_zero_cost_cannot_infinite_edge(self):
        b=bundle();b['features']['round_trip_cost_bps']['value']='0'
        with self.assertRaisesRegex(ValueError,'COST_OR_UNCERTAINTY'):self.evaluate(b)
    def test_unknown_feature_is_no_decision(self):
        b=bundle();b['features']['valuation_percentile']['value']=None
        self.assertEqual('NO_DECISION',self.evaluate(b)['decision'])
    def test_future_clock_is_no_decision(self):
        b=bundle();b['features']['gross_margin_change']['available_at']='2026-10-01T16:30:00.000000002+08:00'
        self.assertEqual('NO_DECISION',self.evaluate(b)['decision'])
    def test_future_retrieval_not_observed_then(self):
        b=bundle();b['features']['gross_margin_change']['retrieved_at']='2026-10-02T16:00:00+08:00'
        self.assertIn('FUTURE_FEATURE',self.evaluate(b)['reason_codes'])
    def test_visible_clock_order_cannot_be_reversed(self):
        b=bundle();b['features']['ttm_revenue_growth']['available_at']='2026-10-01T16:20:00+08:00'
        with self.assertRaisesRegex(ValueError,'CLOCK_ORDER'):self.evaluate(b)
    def test_oversized_decimal_not_silently_rounded(self):
        b=bundle();b['features']['gross_expected_bps']['value']='1'+'0'*100
        with self.assertRaisesRegex(ValueError,'DECIMAL_PRECISION'):self.evaluate(b)
    def test_future_metadata_no_prefix_leak(self):
        b=bundle();b['features']['gross_margin_change']['available_at']='2026-10-02T16:00:00+08:00'
        a=self.evaluate(b);b['features']['gross_margin_change']['value']='999999';b['features']['gross_margin_change']['source_hash']=digest('future replaced')
        self.assertEqual(a,self.evaluate(b))
    def test_future_financial_period_no_prefix_leak(self):
        b=bundle();b['features']['gross_margin_change']['period_end']='2026-12-31'
        a=self.evaluate(b);b['features']['gross_margin_change']['value']='123456'
        self.assertEqual(a,self.evaluate(b));self.assertIn('FUTURE_FINANCIAL_PERIOD',a['reason_codes'])
    def test_missing_period_no_decision(self):
        b=bundle();b['features']['gross_margin_change']['period_end']=None
        self.assertIn('UNKNOWN_FINANCIAL_PERIOD',self.evaluate(b)['reason_codes'])
    def test_missing_clock_not_midnight(self):
        b=bundle();b['features']['valuation_percentile']['available_at']=None
        self.assertIn('UNKNOWN_CLOCK',self.evaluate(b)['reason_codes'])
    def test_date_only_clock_rejected(self):
        b=bundle();b['features']['valuation_percentile']['available_at']='2026-09-30'
        with self.assertRaises(ValueError): self.evaluate(b)
    def test_float_rejected(self):
        b=bundle();b['features']['valuation_percentile']['value']=0.4
        with self.assertRaises(ValueError): self.evaluate(b)
    def test_boolean_numeric_coercion_rejected(self):
        b=bundle();b['features']['net_income_positive']['value']=1
        with self.assertRaises(ValueError): self.evaluate(b)
    def test_unit_coercion_rejected(self):
        b=bundle();b['features']['sector_rs20']['unit']='PERCENT'
        with self.assertRaises(ValueError): self.evaluate(b)
    def test_unknown_status_hard_block(self):
        b=bundle();b['features']['historical_tradeable']['value']=None
        self.assertEqual('NO_DECISION',self.evaluate(b)['decision'])
    def test_hard_risk_cannot_be_score_overridden(self):
        b=bundle();b['features']['hard_risk']['value']=True
        self.assertEqual('NO_DECISION',self.evaluate(b)['decision'])
    def test_unknown_catalyst_no_positive(self):
        b=bundle();b['features']['official_catalyst_unexpired']['value']=None
        self.assertEqual('NO_DECISION',self.evaluate(b)['decision'])
    def test_scope_namespace_extra_rejected(self):
        for k,v in [('namespace','EVENT_3'),('OrderIntent',{}),('owner_approved',True)]:
            b=bundle();b[k]=v
            with self.assertRaises(ValueError):self.evaluate(b)
    def test_symbol_expansion_rejected(self):
        b=bundle();b['symbol']='000001.SZ'
        with self.assertRaises(ValueError):self.evaluate(b)
    def test_actual_provenance_rejected(self):
        b=bundle();b['provenance']='ADMITTED'
        with self.assertRaises(ValueError):self.evaluate(b)
    def test_family_after_result_not_added(self):
        with self.assertRaisesRegex(ValueError,'FAMILY_NOT_PREDECLARED'):self.evaluate(f='WINNER_AFTER_REVEAL')
    def test_spec_after_result_mutation_rejected(self):
        with self.assertRaisesRegex(ValueError,'SPEC_MUTATED'):s.evaluate_fixture('CORE40_Q_PULLBACK_V1',bundle(),digest('changed'))
    def test_output_no_execution_or_signal(self):
        v=self.evaluate();self.assertFalse(v['live_authority']);self.assertFalse(v['native_signal_issued'])
    def test_evaluate_does_not_mutate_inputs(self):
        b=bundle();old=deepcopy(b);self.evaluate(b);self.assertEqual(old,b)
    def test_no_formal_strategy_or_optimizer(self):
        for fn in (s.run_actual_strategy,s.optimize):
            with self.assertRaises(ValueError):fn({'owner_approved':True,'result':'profitable'})
    def test_retrospective_is_not_unseen_oos(self):self.assertTrue(self.spec['evaluation']['retrospective_split']['OOS_claim'].startswith('NONE'))
    def test_account_unknown_and_candidate_not_production(self):
        self.assertEqual('30_UNSET_REQUIRED',self.spec['actual_account_parameters']);self.assertFalse(self.spec['productionGate'])
    def freeze_case(self):return {'provenance':LABEL,'rules':{'entry':'fixture'},'evaluation':{'samples':10},'frozen_at':'2026-10-01T00:00:00.000000001Z','reveal_at':'2026-10-01T00:00:00.000000002Z'}
    def test_freeze_before_reveal_ns(self):
        c=self.freeze_case();f=s.freeze_fixture(c);self.assertEqual(c,s.verify_freeze(f,f['content_hash']))
    def test_freeze_after_reveal_rejected(self):
        c=self.freeze_case();c['frozen_at']=c['reveal_at']
        with self.assertRaises(ValueError):s.freeze_fixture(c)
    def test_hidden_policy_mutation_rejected(self):
        f=s.freeze_fixture(self.freeze_case());h=f['content_hash'];f['frozen']['rules']['entry']='changed'
        f=seal({k:v for k,v in f.items() if k!='content_hash'})
        with self.assertRaises(ValueError):s.verify_freeze(f,h)
    def test_synthetic_unset_no_default(self):
        c=self.freeze_case();c['rules']['capital']=UNSET
        with self.assertRaises(ValueError):s.freeze_fixture(c)
    def test_fixture_not_human_authority(self):
        c=self.freeze_case();c['provenance']='HUMAN_USER'
        with self.assertRaises(ValueError):s.freeze_fixture(c)

if __name__=='__main__':unittest.main()
