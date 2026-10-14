"""Synthetic in-memory graph mutations; never reads the real local Run or PDFs."""
from copy import deepcopy
import json,unittest
from experiments.e2e_pilot_v1.tests.test_research import fixture,CFG
from experiments.e2e_pilot_v1.research import ROOT,evaluate,digest,seal,validate_run
from experiments.e2e_pilot_v1.execution import run_diagnostic,build_portfolio,RULES,digest as objhash,STRATEGY,NAMESPACE

def package():
 raw=(ROOT/'experiments/e2e_pilot_v1/protocol.json').read_bytes();proto=json.loads(raw);m=(ROOT/'experiments/e2e_pilot_v1/method.json').read_bytes()
 admission={k:False for k in ('license_for_local_historical_diagnostic','historical_price_visibility','calendar_complete','execution_domains_complete','membership_scope_explicit')}
 c={'namespace':NAMESPACE,'strategy_id':STRATEGY,'label':'HISTORICAL_DIAGNOSTIC','run_id':'SYNTHETIC-REJECTION-TEST-NOT-ACTUAL','rules':RULES,'rules_hash':objhash(RULES),'preregistration_ref':digest(raw),'method_ref':digest(m),'frozen_at':proto['frozen_at'],'run_at':'2026-10-14T08:00:00+00:00','fee_schedule':proto['fee_schedule'],'universe':[{'symbol':x['symbol'],'sector':s['id'],'selection_evidence_ref':'SYNTHETIC'} for s in CFG['universe'] for x in s['members']],'admission':admission,'admission_hash':objhash(admission)}
 inputs=fixture();data=evaluate(inputs,CFG);p=build_portfolio([],10000000,[],10000000,proto['fee_schedule'],'2026-10-14');p.update(state='BLOCKED_NO_COMPLETE_CANDIDATES_OR_ADMITTED_PRICE',cash_cents=p['remaining_cash_cents'],positions=[],planned_orders=p['plans'],risk_budget_cents=100000,account_kind='VIRTUAL_EXPERIMENT_NOT_OWNER_ACCOUNT',builder_called=True,eligibility_rejections=[{'symbol':x['symbol'],'reason':'FULL_SCORE_AND_EXECUTION_INPUTS_INCOMPLETE'} for x in data['companies']])
 out={'kind':'E2EPilotRun','version':'1.0.0','namespace':NAMESPACE,'experiment_id':CFG['experiment_id'],'run_id':'SYNTHETIC-GRAPH-TEST','method_version':'SAMPLE_FINANCIAL_HEALTH_V1 / COMPANY_SEVEN_FACTOR_V1_PARTIAL','recorded_at':'2026-10-14T08:00:00+00:00','method_hash':digest(m),'protocol_hash':digest(raw),'financial_inputs':inputs,**data,'diagnostic_case':c,'diagnostic':run_diagnostic(c),'portfolio':p,'result_type':'CURRENT_OBSERVED_EXPERIMENTAL_RESEARCH','productionGate':False,'historical_visibility_proven':False,'limitations':['SYNTHETIC_TEST_NOT_REAL_SCORE']};out['content_hash']=seal(out);return out
class Lineage(unittest.TestCase):
 def test_complete_rejection_graph_recomputes(self):self.assertFalse(validate_run(package())['diagnostic']['engine_called'])
 def reject(self,mutate,error):
  p=package();mutate(p);p['content_hash']=seal(p)
  with self.assertRaisesRegex(ValueError,error):validate_run(p)
 def test_resealed_stock_score_rejected(self):self.reject(lambda p:p['companies'][0].update(total='99'),'SCORE_RECOMPUTATION')
 def test_resealed_sector_ref_rejected(self):self.reject(lambda p:p['companies'][0]['upstream_sector_ref'].update(content_hash='sha256:'+'a'*64),'SCORE_RECOMPUTATION')
 def test_false_trade_run_rejected(self):self.reject(lambda p:p['diagnostic'].update(engine_called=True),'DIAGNOSTIC_RECOMPUTATION')
 def test_false_portfolio_rejected(self):self.reject(lambda p:p['portfolio'].update(cash_cents=999),'PORTFOLIO_BINDING')
 def test_oos_relabel_rejected(self):self.reject(lambda p:p.update(result_type='UNTOUCHED_OOS'),'REAL_SYNTHETIC_SCOPE')
 def test_method_version_relabel_rejected(self):self.reject(lambda p:p.update(method_version='APPROVED'),'RESULT_METHOD_VERSION')
 def test_result_before_inputs_rejected(self):self.reject(lambda p:p.update(recorded_at='2026-10-14T06:28:00+00:00'),'RESULT_BEFORE_INPUT')
if __name__=='__main__':unittest.main()
