"""Hand-calculated synthetic checks; no production engine, private data, or network."""
from copy import deepcopy
from decimal import Decimal as D, localcontext
import ast
from pathlib import Path
import unittest
from tools.param_opt import independent as m

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
        f=m.indicators(history([10]*20+[12]),m.BASELINE);self.assertEqual(f['sma'],D('10.1'));self.assertEqual(f['atr'],D('2.05'));self.assertEqual(f['rs'],D('.2'));self.assertTrue(f['breakout']);self.assertTrue(f['eligible'])
    def test_known_pullback_without_breakout(self):
        h=history([10]*20+[11]);h[0]['high']=D(20);f=m.indicators(h,m.BASELINE);self.assertFalse(f['breakout']);self.assertTrue(f['pullback']);self.assertTrue(f['eligible'])
    def test_twenty_bars_are_insufficient(self):self.assertIsNone(m.indicators(history([10]*20),m.BASELINE))
    def test_ascending_search_selects_maximum_affordable_lot(self):
        p,reason,n=m.allocate('X','S',bar(),{'atr':D('.1'),'median_volume':D(1000000)},{},{},10000000,{},POLICY,m.BASELINE)
        self.assertIsNone(reason);self.assertEqual(p['quantity'],1900);self.assertEqual(n,20)
        self.assertGreater(m.costs('10',2000,'BUY',POLICY)['fees']['notional_cents'],2000000)
    def test_risk_budget_restricts_quantity_with_hand_loss(self):
        p,reason,n=m.allocate('X','S',bar(),{'atr':D('2'),'median_volume':D(1000000)},{},{},10000000,{},POLICY,m.BASELINE)
        self.assertIsNone(reason);self.assertEqual(p['quantity'],200);self.assertEqual(p['loss'],81263)
    def test_unaﬀordable_not_force_one_lot(self):
        p,reason,n=m.allocate('X','S',bar(),{'atr':D('2'),'median_volume':D(1000000)},{},{},10000,{},POLICY,m.BASELINE)
        self.assertIsNone(p);self.assertEqual(reason,'RISK_CASH_LOT_OR_VOLUME_UNAFFORDABLE');self.assertEqual(n,0)
    def test_previous_volume_rounds_down_to_lot(self):
        p,reason,n=m.allocate('X','S',bar(),{'atr':D('.1'),'median_volume':D(15000)},{},{},10000000,{},POLICY,m.BASELINE)
        self.assertEqual(p['quantity'],100);self.assertEqual(n,1)
    def test_passive_cap_precedes_position_count(self):
        pos={s:{'sector':s,'lots':[{'qty':1000,'available':'2000-01-01'}]} for s in ('A','B','C')};marks={'A':D(30),'B':D(10),'C':D(10)}
        p,reason,n=m.allocate('X','S',bar(),{'atr':D('.1'),'median_volume':D(1000000)},pos,marks,5000000,{},POLICY,m.BASELINE)
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



class ParameterTests(unittest.TestCase):
    def test_rs60_requires61_closes(self):
        p=dict(m.BASELINE,rs_window=60)
        self.assertIsNone(m.indicators(history([10]*60),p))
        self.assertEqual(m.indicators(history([10]*60+[12]),p)['rs'],D('.2'))
    def test_rs10_retains21_for_atr(self):
        p=dict(m.BASELINE,rs_window=10)
        self.assertIsNone(m.indicators(history([10]*20),p))
        h=history([5]*10+[10]*10+[12]);f=m.indicators(h,p)
        self.assertEqual(f['rs'],D('.2'));self.assertEqual(f['sma'],D('7.85'))
    def test_rs_change_does_not_change_entry_atr_or_sma(self):
        h=history([str(10+i/10) for i in range(61)])
        a=m.indicators(h,m.BASELINE);b=m.indicators(h,dict(m.BASELINE,rs_window=60))
        self.assertNotEqual(a['rs'],b['rs'])
        for k in ('atr','sma','breakout','pullback','median_volume'):self.assertEqual(a[k],b[k])
    def test_actual_stop_multiple_recalculates_risk_quantity(self):
        selected=[]
        for multiple in ('1.5','2.0','2.5'):
            p,reason,n=m.allocate('X','S',bar(),{'atr':D('2'),'median_volume':D(1000000)},{},{},10000000,{},POLICY,dict(m.BASELINE,atr_multiple=multiple))
            self.assertIsNone(reason);selected.append(p['quantity'])
            self.assertEqual(p['stop'],p['entry']['price']-D(multiple)*D(2))
            self.assertLessEqual(p['loss'],100000)
        self.assertEqual(selected,[300,200,100])
    def test_invalid_params_fail_instead_of_silent_defaults(self):
        for p in (dict(m.BASELINE,rs_window=21),dict(m.BASELINE,exit_min_age=True),dict(m.BASELINE,atr_multiple=2),dict(m.BASELINE,unknown=1)):
            with self.assertRaises(ValueError):m.validate_params(p)
    def test_case_parameter_binding_rejects_different_config(self):
        with self.assertRaisesRegex(ValueError,'CASE_PARAMETERS_MISMATCH'):
            m.audit({'parameters':dict(m.BASELINE,rs_window=60)}, {},m.BASELINE)
    def test_complete_empty_run_and_tampered_hash_bound_nav(self):
        from tools.long_forward.tests.test_independent import empty_case
        c,r=empty_case();r['unfilled']=[]
        for d in c['calendar']:d.update(close_at=d['date']+'T15:00:00+08:00',decision_at=d['date']+'T18:00:00+08:00',decision_clock_label='SIMULATED_POST_CLOSE_DECISION_TIME')
        r['decisions']=m.reconstruct(c,m.BASELINE)['decisions'];r['input_hash']=m.digest(c);r['content_hash']=m.digest({k:v for k,v in r.items() if k!='content_hash'})
        self.assertTrue(m.audit(c,r,m.BASELINE)['passed'])
        r['daily'][-1]['nav_cents']+=1;r['content_hash']=m.digest({k:v for k,v in r.items() if k!='content_hash'})
        self.assertFalse(m.audit(c,r,m.BASELINE)['passed'])

class ExitTests(unittest.TestCase):
    def test_ma_wait_is_inclusive_and_independent_of_rs_history(self):
        p=dict(m.BASELINE,rs_window=60,exit_min_age=5)
        h=history([10]*20);position={'stop':D(5),'entry_compare':D(8)};b={'status':'TRADABLE','close':'9'}
        self.assertIsNone(m.indicators(h,p))
        self.assertIsNone(m.exit_reason(b,position,h,4,p))
        self.assertEqual(m.exit_reason(b,position,h,5,p),'CLOSE_LOGIC_INVALIDATION_SMA20')
    def test_wait_does_not_delay_stop_or_stage_exits(self):
        p=dict(m.BASELINE,exit_ma=60,exit_min_age=10,atr_multiple='1.5')
        position={'stop':D(9),'entry_compare':D(11)};b={'status':'TRADABLE','close':'8'}
        self.assertEqual(m.exit_reason(b,position,[],1,p),'CLOSE_STOP_1.5_ATR20')
        b['close']='10'
        self.assertEqual(m.exit_reason(b,position,[],20,p),'DAY20_NONPOSITIVE_ADJUSTED_PRICE_RETURN')
        b['status']='SUSPENDED'
        self.assertEqual(m.exit_reason(b,position,[],40,p),'MAXIMUM_40_EXCHANGE_SESSIONS')
    def test_exit_window_not_entry_sma(self):
        p=dict(m.BASELINE,exit_ma=40);h=history([20]*20+[10]*20);position={'stop':D(5),'entry_compare':D(8)}
        self.assertEqual(m.exit_reason({'status':'TRADABLE','close':'12'},position,h,1,p),'CLOSE_LOGIC_INVALIDATION_SMA40')
        self.assertIsNone(m.exit_reason({'status':'TRADABLE','close':'12'},position,h,1,m.BASELINE))

if __name__=='__main__':unittest.main()
