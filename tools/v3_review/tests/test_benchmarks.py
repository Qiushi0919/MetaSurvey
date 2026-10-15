import unittest
from copy import deepcopy
from tools.v3_review.benchmarks import build_benchmarks, cost


def fixture():
    fee=dict(effective_from='2020-01-01',effective_until='2030-01-01',slippage_bps='10',commission_rate='.0003',minimum_commission_cents=500,exchange_included=True,exchange_rate='.0000341',other_included=False,other_buy_rate='.00001',other_sell_rate='.00001',sell_tax_rate='.0005')
    days=['2025-01-02','2025-01-03','2025-01-06']
    case=dict(run_id='SYNTHETIC',universe=[{'symbol':'A','sector':'S'}],calendar=[{'date':d} for d in days],window={'first_session':days[0],'last_session':days[-1]},fee_schedule=[fee],actions=[],bars=[dict(session=d,symbol='A',status='TRADABLE',lot_size=100,open='10.00',close='10.00',high='11.00',low='9.00',lower_limit='8.00',upper_limit='12.00',volume_shares='10000000') for d in days])
    protocol=dict(version='1.0.0',baseline_run_id='SYNTHETIC',initial_cash_cents=1000000,benchmarks=[{'id':'TEST','name':'synthetic','allocation_fraction':'1.00'}])
    return case,protocol


class BenchmarkTests(unittest.TestCase):
    def test_budget_includes_minimum_fee_no_extra_lot(self):
        c,p=fixture(); before=deepcopy(c);r=build_benchmarks(c,p)[0]
        self.assertEqual(r['trades'][0]['quantity'],900)
        self.assertEqual(r['fees_cents'],509)
        self.assertEqual(r['terminal_cash_cents'],98591)
        self.assertEqual(c,before)
        self.assertEqual(r['nav_series'][-1]['nav_cents'],998591)

    def test_expensive_peer_stays_cash(self):
        c,p=fixture();p['initial_cash_cents']=10000;r=build_benchmarks(c,p)[0]
        self.assertEqual(len(r['rejections']),1);self.assertEqual(r['net_return'],'0')

    def test_limit_does_not_invent_entry(self):
        c,p=fixture();c['bars'][0]['upper_limit']='10.00';r=build_benchmarks(c,p)[0]
        self.assertEqual(r['rejections'][0]['reason'],'LIMIT_OR_SLIPPAGE_BOUND');self.assertEqual(r['trades'],[])

    def test_cash_dividend_ex_accrual_then_pay(self):
        c,p=fixture();c['actions']=[dict(id='D',symbol='A',record_date='2025-01-02',ex_date='2025-01-03',pay_date='2025-01-06',cash_per_share='1',split_ratio='1',bonus_ratio='0',tax_rate='.20')]
        for b in c['bars'][1:]:b['close']='9.00'
        r=build_benchmarks(c,p)[0]
        self.assertEqual(r['nav_series'][1]['receivable_cents'],72000)
        self.assertEqual(r['nav_series'][2]['receivable_cents'],0)
        self.assertEqual(r['dividend_cents'],72000)
        self.assertEqual(r['nav_series'][1]['nav_cents'],r['nav_series'][2]['nav_cents'])

    def test_cash_mixed_slot_and_no_reinvestment(self):
        c,p=fixture();p['benchmarks'][0]['allocation_fraction']='.60';r=build_benchmarks(c,p)[0]
        self.assertEqual(r['trades'][0]['quantity'],500);self.assertEqual(len(r['trades']),1)
        self.assertGreater(r['terminal_cash_cents'],400000)

    def test_scope_bind(self):
        c,p=fixture();p['baseline_run_id']='OTHER'
        with self.assertRaises(ValueError):build_benchmarks(c,p)

    def test_noncash_action_not_silently_supported(self):
        c,p=fixture();c['actions']=[dict(split_ratio='1',bonus_ratio='.1')]
        with self.assertRaises(ValueError):build_benchmarks(c,p)

    def test_sale_reserve_is_explicitly_not_fill(self):
        c,p=fixture();r=build_benchmarks(c,p)[0]
        self.assertFalse(r['terminal_sell_fee_reserve_is_fill'])
        self.assertGreater(r['hypothetical_terminal_sell_fees_cents'],0)
        self.assertEqual(len(r['trades']),1)


if __name__=='__main__':unittest.main()
