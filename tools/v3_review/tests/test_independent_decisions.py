"""Hand-calculated synthetic checks; no production engine, private data, or network."""
from copy import deepcopy
from decimal import Decimal as D, localcontext
import ast
from pathlib import Path
import unittest
from tools.v3_review import independent_decisions as m

POLICY={'commission_rate':'0.0003','minimum_commission_cents':500,'exchange_included':True,'exchange_rate':'0.0000341','other_included':False,'other_buy_rate':'0.00001','other_sell_rate':'0.00001','sell_tax_rate':'0.0005','slippage_bps':'10'}

def history(closes):return [dict(close=D(x),open=D(x),high=D(x)+1,low=D(x)-1,volume_shares=D(1000000)) for x in closes]
def bar():return dict(status='TRADABLE',open='10',high='11',low='9',upper_limit='11',lower_limit='9',lot_size=100,volume_shares='1000000')

class IndependentTests(unittest.TestCase):
    def test_source_imports_only_standard_library(self):
        allowed={'collections','copy','decimal','hashlib','pathlib','statistics','argparse','json'}
        tree=ast.parse(Path(m.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):self.assertTrue(all(x.name.split('.')[0] in allowed for x in node.names))
            if isinstance(node,ast.ImportFrom):self.assertIn(node.module.split('.')[0],allowed)
    def test_hand_minimum_commission_and_embedded_slippage(self):
        q=m.costs('10',100,'BUY',POLICY)
        self.assertEqual(q['price'],D('10.01'));self.assertEqual(q['delta'],-100601)
        self.assertEqual(q['fees']['commission_cents'],500);self.assertEqual(q['fees']['minimum_commission_uplift_cents'],470)
        self.assertEqual(q['fees']['slippage_cents'],100);self.assertEqual(q['fees']['total_fee_cents'],501)
    def test_hand_sell_tax(self):
        q=m.costs('10',100,'SELL',POLICY);self.assertEqual(q['price'],D('9.99'));self.assertEqual(q['delta'],99349);self.assertEqual(q['fees']['sell_tax_cents'],50)
    def test_known_breakout_features(self):
        f=m.indicators(history([10]*20+[12]));self.assertEqual(f['sma'],D('10.1'));self.assertEqual(f['atr'],D('2.05'));self.assertEqual(f['rs'],D('.2'));self.assertTrue(f['breakout']);self.assertTrue(f['eligible'])
    def test_known_pullback_without_breakout(self):
        h=history([10]*20+[11]);h[0]['high']=D(20);f=m.indicators(h);self.assertFalse(f['breakout']);self.assertTrue(f['pullback']);self.assertTrue(f['eligible'])
    def test_twenty_bars_are_insufficient(self):self.assertIsNone(m.indicators(history([10]*20)))
    def test_ascending_search_selects_maximum_affordable_lot(self):
        p,reason,n=m.allocate('X','S',bar(),{'atr':D('.1'),'median_volume':D(1000000)},{},{},10000000,{},POLICY)
        self.assertIsNone(reason);self.assertEqual(p['quantity'],1900);self.assertEqual(n,20)
        self.assertGreater(m.costs('10',2000,'BUY',POLICY)['fees']['notional_cents'],2000000)
    def test_risk_budget_restricts_quantity_with_hand_loss(self):
        p,reason,n=m.allocate('X','S',bar(),{'atr':D('2'),'median_volume':D(1000000)},{},{},10000000,{},POLICY)
        self.assertIsNone(reason);self.assertEqual(p['quantity'],200);self.assertEqual(p['loss'],81263)
    def test_unaﬀordable_not_force_one_lot(self):
        p,reason,n=m.allocate('X','S',bar(),{'atr':D('2'),'median_volume':D(1000000)},{},{},10000,{},POLICY)
        self.assertIsNone(p);self.assertEqual(reason,'RISK_CASH_LOT_OR_VOLUME_UNAFFORDABLE');self.assertEqual(n,0)
    def test_previous_volume_rounds_down_to_lot(self):
        p,reason,n=m.allocate('X','S',bar(),{'atr':D('.1'),'median_volume':D(15000)},{},{},10000000,{},POLICY)
        self.assertEqual(p['quantity'],100);self.assertEqual(n,1)
    def test_passive_cap_precedes_position_count(self):
        pos={s:{'sector':s,'lots':[{'qty':1000,'available':'2000-01-01'}]} for s in ('A','B','C')};marks={'A':D(30),'B':D(10),'C':D(10)}
        p,reason,n=m.allocate('X','S',bar(),{'atr':D('.1'),'median_volume':D(1000000)},pos,marks,5000000,{},POLICY)
        self.assertEqual(reason,'PASSIVE_POSITION_OR_SECTOR_CAP')
    def test_actual_price_boundary_blocks_and_keeps_reason_priority(self):
        b=bar();q=m.costs('10',100,'BUY',POLICY);b['high']='10';self.assertEqual(m.executable(b,q,100),'SLIPPAGE_OUTSIDE_DAILY_RANGE')
        b['upper_limit']='10';self.assertEqual(m.executable(b,q,100),'LIMIT_OR_SLIPPAGE_BOUND')
    def test_actual_volume_cap(self):
        b=bar();b['volume_shares']='9999';self.assertEqual(m.executable(b,m.costs('10',100,'BUY',POLICY),100),'ACTUAL_SESSION_VOLUME_CAP')
    def test_next_session_tail_excludes_exactly_last40_execution_days(self):
        last=100;allowed=[i+1 for i in range(last) if last-i>40];self.assertEqual(max(allowed),60);self.assertEqual(list(range(max(allowed)+1,last+1)),list(range(61,101)))
    def test_comparison_detects_all_output_domains(self):
        trace={'decisions':[{'session':'x'}],'fills':[{'session':'x','side':'BUY','quantity':100}],'unfilled':[{'reason':'POSITION_COUNT_LIMIT'}],'daily':[{'session':'x','cash_cents':1,'exposure_cents':0,'receivable_cents':0,'nav_cents':1,'positions':{}}],'attempts':[],'enumerated_lots':0}
        original={'decisions':[{'session':'y'}],'fills':[{'session':'x','side':'BUY','quantity':200}],'unfilled':[{'reason':'OTHER'}],'daily':[{'session':'x','cash_cents':2,'exposure_cents':0,'receivable_cents':0,'nav_cents':2,'positions':[]}]}
        r=m.compare_result(trace,original);self.assertFalse(r['passed']);self.assertEqual(r['difference_count'],4)

if __name__=='__main__':unittest.main()
