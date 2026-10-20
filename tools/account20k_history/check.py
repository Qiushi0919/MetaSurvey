"""Offline synthetic account adaptation checks; no evidence archive or market reads."""
import unittest
from copy import deepcopy
from decimal import Decimal as D
from experiments.account20k_history_v1.sizing import build_portfolio
from experiments.e2e_pilot_v1.execution import quote
from experiments.account20k_history_v1 import engine
from tools.account20k_history.independent import costs
from tools.long_forward.history_v2 import protocol

class AccountAdaptation(unittest.TestCase):
 def setUp(self):
  self.fees=deepcopy(protocol()['fee_schedule'])
  for p in self.fees:p['commission_rate']='0.00025'
  self.profile=self.fees[-1]
 def test_commission_minimum(self):
  for side in ('BUY','SELL'):
   q=quote('10',100,side,'2026-01-05',self.profile)
   self.assertEqual(q['fees']['commission_cents'],500)
   self.assertEqual(q['fees']['exchange_cents'],0)
 def test_independent_quote(self):
  for profile in self.fees:
   for side in ('BUY','SELL'):
    for qty in (100,500,10000):
     q=quote('25.31',qty,side,profile['effective_from'],profile);ind=costs('25.31',qty,side,profile)
     self.assertEqual(q['fees'],ind['fees']);self.assertEqual(q['cash_delta_cents'],ind['delta'])
 def test_small_account_unaffordable(self):
  c=dict(symbol='TEST',sector='S',price='100',atr20='1',lot_size=100,previous20_median_volume_shares='1000000')
  out=build_portfolio([c],2000000,[],2000000,self.fees,'2026-01-05','2.5')
  self.assertEqual(out['plans'],[]);self.assertEqual(out['rejections'][0]['reason'],'RISK_CASH_LOT_OR_VOLUME_UNAFFORDABLE')
 def test_cash_risk_and_lot(self):
  c=dict(symbol='TEST',sector='S',price='10',atr20='0.2',lot_size=100,previous20_median_volume_shares='1000000')
  out=build_portfolio([c],2000000,[],2000000,self.fees,'2026-01-05','2.5')
  p=out['plans'][0];self.assertEqual(p['quantity']%100,0);self.assertLessEqual(p['planned_loss_cents'],20000);self.assertGreaterEqual(out['remaining_cash_cents'],0);self.assertLessEqual(p['entry']['fees']['notional_cents'],400000)
 def test_dynamic_warmup(self):
  rows=[dict(close=D(10+i)/10,high=D(10+i)/10+D('.1'),low=D(10+i)/10-D('.1')) for i in range(61)]
  self.assertIsNone(engine._feature(rows[:60],dict(rs_window=60)))
  self.assertIsNotNone(engine._feature(rows,dict(rs_window=60)))
 def test_scope_cash_binding(self):
  p=protocol();p.update(initial_cash_cents=2000000)
  c=dict(run_id='test',strategy_id='test',namespace='test',evidence_grade=engine.SYNTHETIC,rules=engine.RULES,rules_hash=engine.digest(engine.RULES),parameters={},initial_cash_cents=0)
  with self.assertRaises((ValueError,KeyError)):engine._validate(c,None,p)
if __name__=='__main__':unittest.main()
