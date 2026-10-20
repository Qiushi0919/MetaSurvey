"""Synthetic end-to-end initial-capital and independent reconstruction checks."""
from copy import deepcopy
from decimal import Decimal as D
import unittest
from tools.param_opt.tests.test_engine import case as old_case
from experiments.account20k_history_v1 import engine as e
from tools.account20k_history.independent import audit,BASELINE

def case(params=BASELINE):
 c,p=old_case(params);p['initial_cash_cents']=2000000;p['rules_hash']=e.digest(e.RULES)
 for fee in p['fee_schedule']:fee['commission_rate']='0.00025'
 c.update(initial_cash_cents=2000000,rules=deepcopy(e.RULES),rules_hash=p['rules_hash'],fee_schedule=deepcopy(p['fee_schedule']),protocol_ref=e.digest(p))
 return c,p

class CapitalTests(unittest.TestCase):
 def test_three_fixed_candidates_independently_reconstruct(self):
  for params in (BASELINE,dict(BASELINE,rs_window=10,exit_min_age=10,atr_multiple='2.5'),dict(BASELINE,rs_window=10,exit_min_age=5,atr_multiple='2.5')):
   with self.subTest(params=params):
    c,p=case(params);r=e.run_diagnostic(c,protocol=p)
    self.assertTrue(r['engine_called'],r['errors']);self.assertEqual(r['ledger'][0]['cash_before_cents'],2000000)
    reviewed=audit(c,r,params);self.assertTrue(reviewed['passed'],reviewed['failures'][:2])
 def test_cash_protocol_mismatch_blocks_before_engine(self):
  c,p=case();c['initial_cash_cents']=10000000;r=e.run_diagnostic(c,protocol=p)
  self.assertFalse(r['engine_called']);self.assertIn('INITIAL_CAPITAL_BINDING',r['reason_codes'])
 def test_missing_cash_blocks(self):
  c,p=case();del c['initial_cash_cents'];r=e.run_diagnostic(c,protocol=p)
  self.assertFalse(r['engine_called']);self.assertIn('INITIAL_CAPITAL_BINDING',r['reason_codes'])
 def test_zero_cash_blocks(self):
  c,p=case();c['initial_cash_cents']=p['initial_cash_cents']=0;c['protocol_ref']=e.digest(p);r=e.run_diagnostic(c,protocol=p)
  self.assertFalse(r['engine_called']);self.assertIn('INITIAL_CAPITAL_BINDING',r['reason_codes'])
 def test_future_changes_do_not_change_past_decisions(self):
  c,p=case();r=e.run_diagnostic(c,protocol=p);cut=c['calendar'][120]['date'];altered=deepcopy(c)
  for row in altered['bars']:
   if row['session']>cut:
    for key in ('open','high','low','close','lower_limit','upper_limit'):row[key]=str(D(row[key])*2)
  other=e.run_diagnostic(altered,protocol=p)
  self.assertEqual([d for d in r['decisions'] if d['session']<=cut],[d for d in other['decisions'] if d['session']<=cut])
 def test_rules_no_stale_100k_constant(self):
  self.assertNotIn('initial_cash_cents',e.RULES)
  self.assertEqual(e.RULES['initial_capital_source'],'CASE_AND_PROTOCOL_EQUAL_POSITIVE_INTEGER_CENTS')
if __name__=='__main__':unittest.main()
