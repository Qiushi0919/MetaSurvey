import copy,json,unittest
from pathlib import Path
from experiments.e2e_pilot_v1.research import evaluate,financial,score,avg,digest,exact,ROOT
from decimal import Decimal
CFG=json.loads((ROOT/'experiments/e2e_pilot_v1/method.json').read_text())
def fixture():
 sources=[];companies=[]
 for s in CFG['universe']:
  for member in s['members']:
   symbol=member['symbol'];sid='synthetic:'+symbol;clock='2026-10-14T06:30:00+00:00';h='a'*64
   sources.append({'source_id':sid,'symbol':symbol.split('.')[0],'sha256':h,'url':'https://example.invalid/synthetic-not-source','retrieved_at':clock,'available_at':clock,'historical_visibility_proven':False})
   facts={k:{'value':v,'unit':'CNY','period':'FY2024' if k=='prior_revenue' else 'FY2025','consolidation':'CONSOLIDATED_GROUP','source_id':sid,'page':1,'location':'synthetic case, not company fact','retrieved_at':clock,'available_at':clock,'historical_visibility_proven':False,'text_numeric_presence_verified':True,'source_components':[v],'revision_version':h} for k,v in [('revenue','120'),('prior_revenue','100'),('net_profit','12'),('operating_cashflow','18')]}
   companies.append({'symbol':symbol,'sector':s['id'],'facts':facts})
 return {'kind':'E2EPilotFinancialInputs','version':'1.0.0','created_at':'2026-10-14T07:00:00+00:00','method_sha256':digest((ROOT/'experiments/e2e_pilot_v1/method.json').read_bytes()).split(':')[1],'companies':companies,'sources':sources}
class Research(unittest.TestCase):
 def test_frozen_formula_independent_hand_calculation(self):
  o=evaluate(fixture(),CFG);self.assertEqual(o['companies'][0]['fundamental_factor_score'],'83.3333');self.assertEqual(o['sectors'][0]['financial_proxy_subtotal'],'83.3333')
 def test_full_totals_not_filled_from_financial_proxy(self):
  o=evaluate(fixture(),CFG);self.assertTrue(all(x['total'] is None for x in o['companies']+o['sectors']))
 def test_missing_member_does_not_renormalize(self):
  f=fixture();del f['companies'][0]['facts']['revenue'];o=evaluate(f,CFG);self.assertIsNone(o['sectors'][0]['financial_proxy_subtotal']);self.assertIsNotNone(o['sectors'][1]['financial_proxy_subtotal'])
 def test_nonpositive_profit_blocks_conversion(self):
  f=fixture();f['companies'][0]['facts']['net_profit'].update(value='0',source_components=['0']);o=evaluate(f,CFG);self.assertIsNone(o['companies'][0]['fundamental_factor_score'])
 def test_group_parent_mismatch_block(self):
  f=fixture();f['companies'][0]['facts']['net_profit']['consolidation']='PARENT';self.assertIsNone(evaluate(f,CFG)['companies'][0]['fundamental_factor_score'])
 def test_units_cannot_be_assumed(self):
  f=fixture();f['companies'][0]['facts']['revenue']['unit']='TEN_THOUSAND_CNY';self.assertIsNone(evaluate(f,CFG)['companies'][0]['fundamental_factor_score'])
 def test_future_observation_blocks(self):
  f=fixture();f['created_at']='2026-10-13T00:00:00+00:00';self.assertIsNone(evaluate(f,CFG)['companies'][0]['fundamental_factor_score'])
 def test_source_hash_binding(self):
  f=fixture();f['companies'][0]['facts']['revenue']['revision_version']='b'*64
  with self.assertRaisesRegex(ValueError,'FACT_SOURCE_BINDING'):evaluate(f,CFG)
 def test_component_arithmetic_binding(self):
  f=fixture();f['companies'][0]['facts']['revenue']['value']='130'
  with self.assertRaisesRegex(ValueError,'SOURCE_COMPONENT_ARITHMETIC'):evaluate(f,CFG)
 def test_upstream_sector_reference(self):
  o=evaluate(fixture(),CFG);self.assertEqual(o['companies'][0]['upstream_sector_ref']['content_hash'],o['sectors'][0]['content_hash'])
 def test_risk_unknown_keeps_null(self):self.assertIsNone(evaluate(fixture(),CFG)['sectors'][0]['total'])
 def test_no_float_money(self):
  with self.assertRaises(ValueError):exact(1.2)
 def test_infinite_rejected(self):
  with self.assertRaises(ValueError):exact('NaN')
 def test_missing_universe_member_rejected(self):
  f=fixture();f['companies'].pop()
  with self.assertRaisesRegex(ValueError,'FIXED_UNIVERSE'):evaluate(f,CFG)
 def test_percent_anchors_clamp(self):self.assertEqual(score(Decimal('2'),['0','1']),'100.0000');self.assertEqual(score(Decimal('-2'),['0','1']),'0.0000')
 def test_seven_weights_preserved(self):self.assertEqual(list(CFG['stock_weights'].values()),[25,20,15,15,10,10,5])
if __name__=='__main__':unittest.main()
