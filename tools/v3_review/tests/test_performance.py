"""Small SYNTHETIC accounting examples; no engine, market or private-file access."""
from copy import deepcopy
from decimal import Decimal, localcontext
import unittest
from tools.v3_review.performance import derive_performance, digest, PerformanceError, INITIAL_CENTS

D=Decimal
DATES=['2025-01-02','2025-01-03','2025-01-06','2025-01-07','2025-01-08','2025-01-09']

class Fixture:
    def __init__(self,n=3):
        self.case={'run_id':'SYNTHETIC-PERFORMANCE-ONLY','namespace':'SYNTHETIC','strategy_id':'SYNTHETIC_ACCOUNTING',
                   'evidence_grade':'SYNTHETIC_ENGINE_TEST','rules':{'initial_cash_cents':INITIAL_CENTS},
                   'universe':[{'symbol':'A','sector':'G1'},{'symbol':'B','sector':'G2'}],
                   'calendar':[{'date':d} for d in DATES[:n]],'window':{'first_session':DATES[0],'last_session':DATES[n-1]},'actions':[]}
        self.r={'version':'2.0.0','run_id':self.case['run_id'],'namespace':'SYNTHETIC','strategy_id':self.case['strategy_id'],
                'engine_called':True,'status':'SIMULATED_TRADES','fills':[],'ledger':[],'daily':[],'dividends':[],
                'unfilled':[],'complete_trades':0,'positions':{},'receivables':{}}
        self.cash=INITIAL_CENTS;self.qty={'A':0,'B':0};self.recv={}
    def ledger(self,day,kind,delta,symbol,**extra):
        rows=self.r['ledger'];row={'sequence':len(rows),'session':day,'kind':kind,'symbol':symbol,'reference':extra.pop('reference',symbol),
          'cash_before_cents':self.cash,'cash_delta_cents':delta,'cash_after_cents':self.cash+delta,
          'previous_hash':rows[-1]['content_hash'] if rows else digest({'initial_cash_cents':INITIAL_CENTS}),**extra}
        self.cash+=delta;row['content_hash']=digest(row);rows.append(row);return row
    def fill(self,day,side,symbol='A',qty=100,price='10.00',raw=None,fee=500):
        raw=raw or price;notional=int(D(price)*qty*100);rawnotional=int(D(raw)*qty*100)
        slip=(notional-rawnotional) if side=='BUY' else (rawnotional-notional)
        fees={'notional_cents':notional,'raw_notional_cents':rawnotional,'commission_cents':fee,
              'exchange_cents':0,'other_cents':0,'sell_tax_cents':0,'total_fee_cents':fee,
              'minimum_commission_uplift_cents':min(100,fee),'slippage_cents':slip}
        delta=-notional-fee if side=='BUY' else notional-fee
        row=self.ledger(day,'SIMULATED_'+side,delta,symbol,side=side,quantity=qty,execution_price=price,fees=fees)
        self.r['fills'].append(deepcopy(row));self.qty[symbol]+=qty if side=='BUY' else -qty
    def ex(self,day='2025-01-03',symbol='A',cash='1',bonus='0',pay='2025-01-06'):
        a={'id':'ACTION:'+symbol,'symbol':symbol,'record_date':DATES[0],'ex_date':day,'pay_date':pay,
           'shares_available_date':DATES[-1] if bonus!='0' else None,'cash_per_share':cash,'bonus_ratio':bonus,'split_ratio':'1','tax_rate':'0.20'}
        self.case['actions'].append(a);net=int(D(cash)*self.qty[symbol]*80);added=int(D(bonus)*self.qty[symbol]);quantity=self.qty[symbol]
        self.ledger(day,'ACTION_EX',0,symbol,reference=a['id'],id=a['id'],stage='EX',record_quantity=quantity,
                    gross_cash_per_share=cash,tax_rate='0.20',net_receivable_cents=net,added_shares=added)
        self.qty[symbol]+=added
        if net:self.recv[a['id']]={'symbol':symbol,'net_cents':net,'pay_date':pay}
    def pay(self,day= '2025-01-06',symbol='A'):
        key='ACTION:'+symbol;entry=self.recv.pop(key);self.ledger(day,'DIVIDEND_PAYMENT',entry['net_cents'],symbol,reference=key)
    def snapshot(self,day,marks=None):
        marks=marks or {'A':'10','B':'10'};positions=[]
        for s,q in self.qty.items():
            if q:positions.append({'symbol':s,'sector':'G1' if s=='A' else 'G2','quantity':q,
                                  'mark':{'price':marks[s]},'market_value_cents':int(D(marks[s])*q*100)})
        exposure=sum(p['market_value_cents'] for p in positions);receivable=sum(x['net_cents'] for x in self.recv.values())
        self.r['daily'].append({'session':day,'cash_cents':self.cash,'exposure_cents':exposure,'receivable_cents':receivable,
                               'nav_cents':self.cash+exposure+receivable,'positions':positions})
    def finish(self):
        r=self.r;r['final_cash_cents']=self.cash;r['positions']={s:{'lots':[{'quantity':q}]} for s,q in self.qty.items() if q};r['receivables']=deepcopy(self.recv)
        r['total_fee_cents']=sum(f['fees']['total_fee_cents'] for f in r['fills']);r['total_slippage_cents']=sum(f['fees']['slippage_cents'] for f in r['fills'])
        with localcontext() as ctx:
            ctx.prec=80;peak=INITIAL_CENTS;maximum=D(0)
            for row in r['daily']:
                peak=max(peak,row['nav_cents']);maximum=max(maximum,D(peak-row['nav_cents'])/peak)
            r['net_return']=str(D(r['daily'][-1]['nav_cents']-INITIAL_CENTS)/INITIAL_CENTS) if r['daily'] else None
            r['maximum_drawdown']=str(maximum) if r['daily'] else None
        r['input_hash']=digest(self.case);r['content_hash']=digest({k:v for k,v in r.items() if k!='content_hash'})
        return self.case,r
    def derive(self):return derive_performance(*self.finish())

class PerformanceTests(unittest.TestCase):
    def test_cash_only_zero_is_observed_not_unrun(self):
        f=Fixture();f.r['status']='RUN_NO_TRADES'
        for d in DATES[:3]:f.snapshot(d)
        p=f.derive();self.assertEqual(p['status'],'VERIFIED');self.assertEqual(p['summary']['final_nav_cny'],'100000.00');self.assertEqual(p['summary']['net_return_fraction'],'0');self.assertEqual(p['max_drawdown']['state'],'NO_DRAWDOWN');self.assertIsNone(p['max_drawdown']['peak_session']);self.assertEqual(len(p['symbol_contributions']),2)
    def test_open_position_pnl_includes_terminal_market_value(self):
        f=Fixture(1);f.fill(DATES[0],'BUY',price='10.01',raw='10.00');f.snapshot(DATES[0],{'A':'12'})
        p=f.derive();a=p['symbol_contributions'][0]
        self.assertEqual(a['buy_cash_out_cents'],100600);self.assertEqual(a['sell_cash_in_cents'],0);self.assertEqual(a['ending_market_value_cents'],120000);self.assertEqual(a['contribution_cents'],19400);self.assertEqual(p['summary']['net_profit_cents'],19400)
    def test_sell_proceeds_are_not_profit_and_slippage_not_deducted_twice(self):
        f=Fixture(2);f.fill(DATES[0],'BUY',price='10.01',raw='10');f.snapshot(DATES[0]);f.fill(DATES[1],'SELL',price='11.99',raw='12',fee=600);f.snapshot(DATES[1]);f.r['complete_trades']=1
        p=f.derive();a=p['symbol_contributions'][0];self.assertEqual(a['sell_cash_in_cents'],119300);self.assertEqual(a['contribution_cents'],18700);self.assertEqual(p['summary']['net_profit_cents'],18700);self.assertEqual(p['fee_summary']['slippage_cents'],200);self.assertEqual(p['fee_summary']['total_fee_cents'],1100);self.assertEqual(p['summary']['complete_trades'],1);self.assertEqual(p['summary']['filled_orders'],2)
    def test_paid_cash_dividend_moves_receivable_not_profit_twice(self):
        f=Fixture(3);f.fill(DATES[0],'BUY');f.snapshot(DATES[0]);f.ex();f.snapshot(DATES[1],{'A':'9'});f.pay();f.snapshot(DATES[2],{'A':'9'})
        p=f.derive();a=p['symbol_contributions'][0];self.assertEqual(p['nav_series'][1]['receivable_cents'],8000);self.assertEqual(p['nav_series'][2]['receivable_cents'],0);self.assertEqual(p['nav_series'][1]['nav_cents'],p['nav_series'][2]['nav_cents']);self.assertEqual(a['contribution_cents'],-2500);self.assertEqual(p['dividend_summary']['simulated_tax_cents'],2000);self.assertEqual(p['dividend_summary']['paid_cents'],8000)
    def test_unpaid_dividend_ends_as_receivable(self):
        f=Fixture(2);f.fill(DATES[0],'BUY');f.snapshot(DATES[0]);f.ex(pay='2025-02-01');f.snapshot(DATES[1],{'A':'9'})
        p=f.derive();a=p['symbol_contributions'][0];self.assertEqual(a['dividend_paid_cents'],0);self.assertEqual(a['ending_receivable_cents'],8000);self.assertEqual(a['contribution_cents'],-2500);self.assertEqual(p['reconciliation']['difference_cents'],0)
    def test_bonus_shares_in_terminal_value_not_cash_income(self):
        f=Fixture(2);f.fill(DATES[0],'BUY',fee=0);f.snapshot(DATES[0]);f.ex(cash='0',bonus='1');f.snapshot(DATES[1],{'A':'5'})
        p=f.derive();a=p['symbol_contributions'][0];self.assertEqual(a['ending_quantity'],200);self.assertEqual(a['contribution_cents'],0);self.assertEqual(p['dividend_summary']['net_entitled_cents'],0)
    def test_group_and_company_contributions_add_to_nav_profit(self):
        f=Fixture(1);f.fill(DATES[0],'BUY','A',fee=0);f.fill(DATES[0],'BUY','B',fee=0);f.snapshot(DATES[0],{'A':'12','B':'9'})
        p=f.derive();self.assertEqual([x['contribution_cents'] for x in p['group_contributions']],[20000,-10000]);self.assertEqual(p['summary']['net_profit_cents'],10000)
    def test_mdd_ties_keep_earliest_peak_trough_first_recovery(self):
        f=Fixture(6);f.fill(DATES[0],'BUY',qty=10000,fee=0)
        for d,mark in zip(DATES,['12','12','10','10','12','11']):f.snapshot(d,{'A':mark})
        p=f.derive();m=p['max_drawdown'];self.assertEqual(m['peak_session'],DATES[0]);self.assertEqual(m['trough_session'],DATES[2]);self.assertEqual(m['recovery_session'],DATES[4]);self.assertTrue(m['recovered'])
    def test_initial_capital_peak_before_first_down_day(self):
        f=Fixture(2);f.fill(DATES[0],'BUY',fee=500);f.snapshot(DATES[0]);f.snapshot(DATES[1]);p=f.derive();self.assertEqual(p['max_drawdown']['peak_source'],'INITIAL_CAPITAL_BEFORE_FIRST_SESSION');self.assertEqual(p['max_drawdown']['peak_session'],DATES[0]);self.assertEqual(p['max_drawdown']['trough_session'],DATES[0]);self.assertIsNone(p['max_drawdown']['recovery_session'])
    def test_partial_tail_fills_visible_but_not_attributed_without_mark(self):
        f=Fixture(3);f.snapshot(DATES[0]);f.fill(DATES[1],'BUY');f.r['status']='ENGINE_FAILED';p=f.derive()
        self.assertEqual(p['status'],'PARTIAL_COMPLETED_DAYS_ONLY');self.assertEqual(p['summary']['net_profit_cents'],0);self.assertEqual(p['summary']['fees_cents'],0);self.assertEqual(p['fee_summary']['recorded_all_fills_fee_cents'],500);self.assertFalse(p['trades'][0]['included_in_valuation_scope']);self.assertEqual(p['reconciliation']['excluded_unvalued_tail_ledger_rows'],1)
    def test_unrun_has_null_summary_not_zero_return(self):
        f=Fixture();f.r['engine_called']=False;f.r['status']='DATA_BLOCKED';p=f.derive();self.assertEqual(p['status'],'ENGINE_NOT_RUN');self.assertIsNone(p['summary']);self.assertEqual(p['nav_series'],[])
    def test_hash_binding_rejects_other_case(self):
        f=Fixture(1);f.snapshot(DATES[0]);c,r=f.finish();c['run_id']='other'
        with self.assertRaisesRegex(PerformanceError,'CASE_RESULT_HASH'):derive_performance(c,r)
    def test_forged_daily_nav_with_rehashed_result_is_rejected(self):
        f=Fixture(1);f.snapshot(DATES[0]);c,r=f.finish();r['daily'][0]['nav_cents']+=1;r['content_hash']=digest({k:v for k,v in r.items() if k!='content_hash'})
        with self.assertRaisesRegex(PerformanceError,'DAILY_NAV'):derive_performance(c,r)
    def test_modified_fill_copy_rejected_even_rehashed_result(self):
        f=Fixture(1);f.fill(DATES[0],'BUY');f.snapshot(DATES[0]);c,r=f.finish();r['fills'][0]['quantity']=200;r['content_hash']=digest({k:v for k,v in r.items() if k!='content_hash'})
        with self.assertRaisesRegex(PerformanceError,'FILLS_LEDGER'):derive_performance(c,r)
    def test_ledger_chain_mutation_rejected(self):
        f=Fixture(1);f.fill(DATES[0],'BUY');f.snapshot(DATES[0]);c,r=f.finish();r['ledger'][0]['cash_after_cents']+=1;r['content_hash']=digest({k:v for k,v in r.items() if k!='content_hash'})
        with self.assertRaisesRegex(PerformanceError,'LEDGER_ROW_HASH'):derive_performance(c,r)
    def test_no_input_mutation_and_deterministic(self):
        f=Fixture(1);f.snapshot(DATES[0]);c,r=f.finish();before=deepcopy((c,r));a=derive_performance(c,r);b=derive_performance(c,r);self.assertEqual(a,b);self.assertEqual((c,r),before)
    def test_float_money_rejected(self):
        f=Fixture(1);f.fill(DATES[0],'BUY');f.snapshot(DATES[0]);c,r=f.finish();r['daily'][0]['positions'][0]['mark']['price']=10.0;r['content_hash']=digest({k:v for k,v in r.items() if k!='content_hash'})
        with self.assertRaisesRegex(PerformanceError,'DECIMAL_STRING'):derive_performance(c,r)
    def test_float_daily_cents_rejected_even_equal_integer_value(self):
        f=Fixture(1);f.snapshot(DATES[0]);c,r=f.finish();r['daily'][0]['nav_cents']=float(INITIAL_CENTS);r['content_hash']=digest({k:v for k,v in r.items() if k!='content_hash'})
        with self.assertRaisesRegex(PerformanceError,'INTEGER_DAILY_MONEY'):derive_performance(c,r)
    def test_float_initial_capital_rejected(self):
        f=Fixture(1);f.snapshot(DATES[0]);f.case['rules']['initial_cash_cents']=float(INITIAL_CENTS);c,r=f.finish()
        with self.assertRaisesRegex(PerformanceError,'INTEGER_INITIAL_CAPITAL'):derive_performance(c,r)
    def test_unknown_group_in_daily_positions_rejected(self):
        f=Fixture(1);f.fill(DATES[0],'BUY');f.snapshot(DATES[0]);c,r=f.finish();r['daily'][0]['positions'][0]['sector']='FAKE';r['content_hash']=digest({k:v for k,v in r.items() if k!='content_hash'})
        with self.assertRaisesRegex(PerformanceError,'DAILY_GROUP'):derive_performance(c,r)

if __name__=='__main__':unittest.main()
