"""Hand-built accounting checks, no engine import and no private data."""
from copy import deepcopy
from decimal import Decimal as D
import unittest
from tools.long_forward.independent import quote, canon, audit_objects, annual_rows


def fee(transfer='.00001',tax='.0005'):
 return dict(commission_rate='.0003',minimum_commission_cents=500,exchange_included=True,exchange_rate='.0000341',
 other_included=False,other_buy_rate=transfer,other_sell_rate=transfer,sell_tax_rate=tax,slippage_bps='0',effective_from='2021-06-01',effective_until='2026-09-30')


def empty_case():
 days=['2025-12-31','2026-01-02']
 c=dict(run_id='SYNTHETIC_ARITHMETIC_ONLY',mode='HISTORY',calendar=[{'date':d} for d in days],universe=[{'symbol':'TEST','sector':'TEST'}],
 fee_schedule=[fee()],window={'first_session':days[0],'last_session':days[-1]},actions=[],bars=[dict(session=d,symbol='TEST',status='TRADABLE',open='10',high='11',low='9',close='10',volume_shares='100000') for d in days])
 r=dict(input_hash=canon(c),engine_called=True,status='RUN_NO_TRADES',ledger=[],daily=[dict(session=d,positions=[],cash_cents=10000000,exposure_cents=0,receivable_cents=0,nav_cents=10000000,held_quantity=0,available_quantity=0) for d in days],
 dividends=[],decisions=[],fills=[],final_cash_cents=10000000,receivables={},complete_trades=0,total_fee_cents=0,total_slippage_cents=0,maximum_drawdown='0',net_return='0',positions={})
 r['content_hash']=canon(r)
 return c,r


class IndependentTests(unittest.TestCase):
 def test_three_dated_statutory_boundaries_hand_calculation(self):
  for profile,buy,sell in [(fee('.00002','.001'),520,1520),(fee('.00001','.001'),510,1510),(fee('.00001','.0005'),510,1010)]:
   self.assertEqual(quote('10',1000,'BUY',profile)[1]['total_fee_cents'],buy)
   self.assertEqual(quote('10',1000,'SELL',profile)[1]['total_fee_cents'],sell)
 def test_slip_embedded_once_and_commission_minimum(self):
  p=fee();p['slippage_bps']='10';price,cost,delta=quote('10',100,'BUY',p)
  self.assertEqual(price,D('10.01'));self.assertEqual(cost['slippage_cents'],100)
  self.assertEqual(cost['commission_cents'],500);self.assertEqual(delta,-100601)
 def test_empty_complete_run_reconciles(self):
  c,r=empty_case();a=audit_objects(c,r);self.assertTrue(a['passed']);self.assertEqual(a['checked_daily_rows'],2)
 def test_resealed_nav_error_is_caught(self):
  c,r=empty_case();r['daily'][1]['nav_cents']+=100;r['content_hash']=canon({k:v for k,v in r.items() if k!='content_hash'})
  a=audit_objects(c,r);self.assertFalse(a['passed']);self.assertTrue(any(x['check']=='daily_nav_cents' for x in a['failures']))
 def test_fee_overlap_caught_even_without_trades(self):
  c,r=empty_case();c['fee_schedule'].append(deepcopy(c['fee_schedule'][0]));r['input_hash']=canon(c);r['content_hash']=canon({k:v for k,v in r.items() if k!='content_hash'})
  a=audit_objects(c,r);self.assertFalse(a['passed']);self.assertEqual(a['checks']['full_calendar_fee_coverage'],2)
 def test_failed_run_is_not_arithmetic_pass(self):
  c,r=empty_case();r['status']='ENGINE_FAILED';a=audit_objects(c,r)
  self.assertFalse(a['passed']);self.assertEqual(a['status'],'NOT_FULLY_REVIEWABLE')
 def test_annual_continuous_account_and_yearly_mismatch(self):
  x=annual_rows([dict(session='2025-12-31',nav_cents=11000),dict(session='2026-01-02',nav_cents=9900)],[],10000)
  self.assertEqual(x[1]['opening_nav_cents'],11000);self.assertEqual(D(x[1]['net_return_fraction']),D('-.1'))
  c,r=empty_case();years=annual_rows(r['daily'],[]);years[1]['fees_cents']=1
  a=audit_objects(c,r,years);self.assertFalse(a['passed']);self.assertTrue(any(z['check']=='yearly_fees_cents' for z in a['failures']))
 def test_resealed_result_ledger_uncovered_row_fails(self):
  c,r=empty_case();r['ledger'].append({'session':'2030-01-01'});r['content_hash']=canon({k:v for k,v in r.items() if k!='content_hash'})
  a=audit_objects(c,r);self.assertFalse(a['passed']);self.assertTrue(any(z['check']=='ledger_coverage' for z in a['failures']))

if __name__=='__main__':unittest.main()
