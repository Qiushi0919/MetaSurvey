import unittest,json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from wave_d import core
from wave_d.probe import plan,analyze,STATUS_DAY,verify_capture
from wave_d.status_action import complete_set,adjustment_features
from wave_d.public_enrich import allowed_target,parse_pdf
from wave_c.core import digest

class WaveDBoundaries(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.inputs=core.load_inputs();cls.assessments=core.assess(cls.inputs);cls.reports=core.reports(cls.assessments);cls.comparison=core.comparison(cls.reports)
 def test_exact_three_no_real_account_defaults(self):
  self.assertEqual(tuple(x['symbol'] for x in self.inputs),core.SYMBOLS)
  for r in self.reports:self.assertFalse(r['productionGate']);self.assertEqual(r['real_account_settings'],'UNSET_REQUIRED')
 def test_closed_generic_derive(self):
  with self.assertRaisesRegex(ValueError,'DIRECT_ISSUE'):core.derive(self.inputs[0],'Assessment',{'quality':999})
 def test_closed_generic_register(self):
  with self.assertRaisesRegex(ValueError,'DIRECT_ISSUE'):core.register(self.inputs[0])
 def test_private_mint_no_body_parameter(self):
  ctx,up=core._context(self.inputs[0])
  with self.assertRaises(TypeError):core._mint('Report',core.SYMBOLS[0],ctx,up,(self.assessments[0],),body={'quality':999})
 def test_private_upstream_copy_not_authority(self):
  ctx,up=core._context(self.inputs[0])
  with self.assertRaisesRegex(ValueError,'UPSTREAM_FORGERY'):core._mint('Input',core.SYMBOLS[0],ctx,deepcopy(up))
 def test_private_upstream_mutation_not_authority(self):
  ctx,up=core._context(self.inputs[0]);copy=deepcopy(up);copy['capture']['requests'][0]['rows'][0]['values']['name']='SYNTHETIC_FORGED_NAME'
  with self.assertRaisesRegex(ValueError,'UPSTREAM_FORGERY'):core._mint('Input',core.SYMBOLS[0],ctx,copy)
 def test_context_copy_modified_blocks(self):
  ctx,up=core._context(self.inputs[0]);ctx['rules']['productionGate']=True
  with self.assertRaisesRegex(ValueError,'CONTEXT_FORGERY'):core._mint('Input',core.SYMBOLS[0],ctx,up)
 def test_caller_copy_reseal_not_registered(self):
  v=deepcopy(self.reports[0]);v['content_hash']=digest({k:x for k,x in v.items() if k!='content_hash'})
  with self.assertRaisesRegex(ValueError,'UNREGISTERED'):core.assert_registered(v)
 def test_missing_cohort_cannot_compare(self):
  with self.assertRaises(ValueError):core.comparison(self.reports[:2])
 def test_reordered_cohort_cannot_assess(self):
  with self.assertRaises(ValueError):core.assess(list(reversed(self.inputs)))
 def test_raw_source_invalidation_live(self):
  ctx,_=core._context(self.inputs[0]);target=next(p for p,h in ctx['pins'] if str(p).endswith('.response.json'));original=Path.read_bytes
  with patch.object(Path,'read_bytes',lambda p:b'CHANGED_RAW' if p==target else original(p)):
   with self.assertRaisesRegex(ValueError,'DEPENDENCY_INVALIDATED'):core.assert_registered(self.reports[0])
 def test_no_source_verification_cache_across_calls(self):
  core.assert_registered(self.reports[0]);ctx,_=core._context(self.inputs[0]);target=next(p for p,h in ctx['pins'] if str(p).endswith('.response.json'));original=Path.read_bytes
  with patch.object(Path,'read_bytes',lambda p:b'CHANGED_AFTER_FIRST_SUCCESS' if p==target else original(p)):
   with self.assertRaises(ValueError):core.assert_registered(self.reports[0])
 def test_rules_invalidation_live(self):
  target=core.ROOT/'docs/wave-d/rules.json';original=Path.read_bytes
  with patch.object(Path,'read_bytes',lambda p:b'CHANGED_RULES' if p==target else original(p)):
   with self.assertRaises(ValueError):core.assert_registered(self.comparison)
 def test_code_invalidation_live(self):
  target=core.ROOT/'wave_d/financial.py';original=Path.read_bytes
  with patch.object(Path,'read_bytes',lambda p:b'CHANGED_CODE' if p==target else original(p)):
   with self.assertRaises(ValueError):core.assert_registered(self.reports[0])
 def test_future_announcement_not_visible(self):
  spec=next(p for p in plan() if p['api_name']=='fina_indicator');values=['603993.SH','20270101','20260630','10','20','30','40','50','1'];raw=json.dumps({'code':0,'data':{'fields':spec['fields'],'items':[values]}}).encode();x=analyze(spec,raw,'2026-10-06T12:00:00Z');self.assertEqual(x['rows'],[]);self.assertIn('FUTURE_DATE_LITERAL',x['excluded'][0]['reason_codes'])
 def test_old_valuation_date_cannot_current_request(self):
  spec=next(p for p in plan() if p['api_name']=='daily_basic');raw=json.dumps({'code':0,'data':{'fields':spec['fields'],'items':[['603993.SH','20250101',*['1']*8]]}}).encode();x=analyze(spec,raw,'2026-10-06T12:00:00Z');self.assertEqual(x['rows'],[])
 def test_empty_per_symbol_not_status_negative(self):
  self.assertFalse(complete_set([], 'stock_st')[0]);self.assertFalse(complete_set([], 'suspend_d')[0])
 def test_real_status_terminal_failure_preserved(self):
  capture=verify_capture()
  for api in ('stock_st','suspend_d'):self.assertFalse(complete_set(capture['requests'],api)[0])
 def test_current_industry_cannot_history(self):
  for r in self.reports:
   f=next(f for f in r['body']['features'] if f['name']=='historical_industry_membership');self.assertIsNone(f['value'])
 def test_raw_adjusted_separate_no_return_claim(self):
  for r in self.reports:self.assertFalse(r['body']['adjustment']['raw_series_overwritten']);self.assertFalse(r['body']['adjustment']['independent_source_verified']);self.assertEqual(r['body']['adjustment']['preserved_nonzero_references'],8)
 def test_official_redirect_only_same_path(self):
  uri='https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-09-30/603993_20260930_TEST.pdf'
  self.assertEqual(allowed_target(uri,uri.replace('www.','static.')),uri.replace('www.','static.'))
  for target in [uri.replace('www.sse.com.cn','evil.invalid'),uri.replace('www.','static.').replace('603993_','600312_'),uri.replace('www.','static.')+'?token=SYNTHETIC']:
   with self.assertRaises(ValueError):allowed_target(uri,target)
 def test_html_never_pdf_catalyst(self):
  with self.assertRaisesRegex(ValueError,'PDF_FORMAT'):parse_pdf(b'<html>synthetic</html>',{'symbol':'603993.SH','title':'SYNTHETIC'})
 def test_unknown_cash_not_zero(self):
  for r in self.reports:
   for f in r['body']['features']:
    if f['state'] in ('UNKNOWN','CONFLICT'):self.assertIsNone(f['value'])
 def test_comparison_has_no_total_score_or_buy_sell(self):
  self.assertEqual(self.comparison['body']['buy_sell'],'FORBIDDEN');self.assertEqual(self.comparison['body']['total_score'],'UNSET_REQUIRED')
 def test_current_data_keeps_old_coordinate_cutoff(self):
  for r in self.reports:self.assertLess(r['body']['coordinates_cutoff'],r['decision_cutoff']);self.assertEqual(r['body']['coordinates_policy'],'PRESERVED_WAVE_C_ORIGINAL_EXPERIMENTAL_NOT_UPDATED_WITH_NEW_FINANCIALS')
if __name__=='__main__':unittest.main()
