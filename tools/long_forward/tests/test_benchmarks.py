"""Synthetic-only control accounting, with hand-calculated expected values."""
from copy import deepcopy
from decimal import Decimal as D
import unittest
from tools.long_forward.benchmarks import build_benchmarks, _digest, RULES_REF, yearly


def fixture():
    days=['2025-12-30','2025-12-31','2026-01-02']
    symbols=['SYNTHETIC:'+str(n) for n in range(9)]
    fee=dict(effective_from='2021-01-01',effective_until='2026-12-31',commission_rate='0.0003',minimum_commission_cents=500,
             exchange_included=True,exchange_rate='0.0000341',other_included=False,other_buy_rate='0.00001',other_sell_rate='0.00001',sell_tax_rate='0.0005',slippage_bps='0')
    p=dict(version='1.0.0',namespace='SYNTHETIC_TEST_ONLY',strategy_id='SYNTHETIC_TEST_ONLY',initial_cash_cents=9000000,
           members={s:'SYNTHETIC_SECTOR' for s in symbols},fee_schedule=[fee],benchmark={'rules_ref':RULES_REF},
           target_window={'start':days[0],'end':days[-1]})
    c=dict(run_id='SYNTHETIC_NOT_INVESTMENT_EVIDENCE',mode='HISTORY',namespace=p['namespace'],strategy_id=p['strategy_id'],protocol_ref=_digest(p),
           fee_schedule=deepcopy(p['fee_schedule']),calendar=[{'date':d} for d in days],universe=[{'symbol':s,'sector':'SYNTHETIC_SECTOR'} for s in symbols],
           window={'first_session':days[0],'last_session':days[-1]},actions=[],bars=[])
    for day in days:
        for symbol in symbols:c['bars'].append(dict(session=day,symbol=symbol,status='TRADABLE',open='10',high='11',low='9',close='10',
            lower_limit='8',upper_limit='12',lot_size=100,volume_shares='1000000'))
    return c,p


def add_action(c,bonus='.1',cash='1',listing='2026-01-04',pay='2026-01-04'):
    c['actions']=[dict(id='SYNTHETIC_ACTION',symbol='SYNTHETIC:0',record_date='2025-12-30',ex_date='2025-12-31',
        pay_date=pay,shares_available_date=listing,cash_per_share=cash,bonus_ratio=bonus,split_ratio='1',tax_rate='.20')]
    for row in c['bars']:
        if row['symbol']=='SYNTHETIC:0' and row['session']>='2025-12-31':
            row.update(open='8.18',high='9',low='8',close='8.18',lower_limit='7',upper_limit='10')


class BenchmarkTests(unittest.TestCase):
    def test_fixed_two_controls_and_cash_inclusive_nine_slots(self):
        c,p=fixture();a,b=build_benchmarks(c,p)
        self.assertEqual((len(a['trades']),len(b['trades'])),(9,9))
        self.assertEqual([x['quantity'] for x in a['trades']],[900]*9)
        self.assertEqual([x['quantity'] for x in b['trades']],[500]*9)
        self.assertEqual(a['terminal_cash_cents'],9000000-9*(900000+509))
        self.assertEqual(a['nav_series'][-1]['nav_cents'],9000000-9*509)
        self.assertEqual(a['fees_cents'],4581)
        self.assertFalse(a['terminal_sell_fee_reserve_is_fill'])
    def test_rejected_slot_never_redistributed_or_retried(self):
        c,p=fixture();c['bars'][0]['open']=c['bars'][0]['close']=c['bars'][0]['high']='12'
        a=build_benchmarks(c,p)[0]
        self.assertEqual(len(a['trades']),8);self.assertEqual(len(a['rejections']),1)
        self.assertTrue(all(t['quantity']==900 for t in a['trades']))
        self.assertEqual(a['rejections'][0]['reason'],'LIMIT_OR_SLIPPAGE_BOUND')
    def test_missing_bar_retains_prior_entries_but_invalidates_metrics(self):
        c,p=fixture();c['bars']=[r for r in c['bars'] if not(r['symbol']=='SYNTHETIC:0' and r['session']=='2025-12-31')]
        a=build_benchmarks(c,p)[0]
        self.assertEqual(a['status'],'FAILED_PARTIAL_INVALID');self.assertEqual(len(a['trades']),9)
        self.assertEqual(len(a['nav_series']),1);self.assertIsNone(a['net_return']);self.assertIsNone(a['max_drawdown'])
    def test_bonus_valued_but_locked_and_cash_receivable_unspent(self):
        c,p=fixture();add_action(c);a=build_benchmarks(c,p)[0]
        pos=a['terminal_positions'][0]
        self.assertEqual((pos['quantity'],pos['settlement_eligible_quantity'],pos['locked_quantity']),(990,900,90))
        self.assertEqual(pos['market_value_cents'],809820)
        self.assertEqual(a['terminal_receivable_cents'],72000)
        self.assertEqual(a['dividend_cents'],0);self.assertEqual(len(a['trades']),9)
        self.assertFalse(a['terminal_fee_estimate_complete'])
        # 900 * 8.18 = 7362 CNY; 5 commission + .07 transfer + 3.68 stamp.
        self.assertEqual(pos['hypothetical_sell_fee_cents'],875)
        self.assertEqual(a['actions'][0]['record_quantity'],900)
    def test_listing_unlocks_bonus_pay_date_cash_no_reinvestment(self):
        c,p=fixture();add_action(c,listing='2026-01-02',pay='2026-01-02');a=build_benchmarks(c,p)[0]
        self.assertEqual(a['terminal_positions'][0]['settlement_eligible_quantity'],990)
        self.assertEqual(a['terminal_receivable_cents'],0);self.assertEqual(a['dividend_cents'],72000)
        self.assertEqual(a['terminal_cash_cents'],9000000-9*900509+72000)
        self.assertEqual(len(a['trades']),9)
    def test_fractional_entitlement_keeps_prior_ledger_not_rounding_down(self):
        c,p=fixture();add_action(c,bonus='.0001');a=build_benchmarks(c,p)[0]
        self.assertEqual(a['status'],'FAILED_PARTIAL_INVALID');self.assertIn('FRACTIONAL',a['errors'][0]['detail'])
        self.assertEqual(len(a['ledger']),9);self.assertEqual(len(a['nav_series']),1)
        self.assertEqual(a['partial_holdings']['SYNTHETIC:0'][0]['quantity'],900)
    def test_bonus_listing_missing_rejected(self):
        c,p=fixture();add_action(c,listing=None)
        with self.assertRaisesRegex(ValueError,'REQUIRED_SETTLEMENT'):build_benchmarks(c,p)
    def test_cash_pay_date_missing_rejected(self):
        c,p=fixture();add_action(c,pay=None)
        with self.assertRaisesRegex(ValueError,'REQUIRED_SETTLEMENT'):build_benchmarks(c,p)
    def test_suspension_terminal_has_no_liquidation_estimate(self):
        c,p=fixture();r=c['bars'][-9];r.update(status='SUSPENDED',open=None,high=None,low=None,close=None,volume_shares='0')
        a=build_benchmarks(c,p)[0];pos=a['terminal_positions'][0]
        self.assertEqual(pos['market_value_cents'],900000);self.assertIsNone(pos['hypothetical_sell_fee_cents'])
        self.assertEqual(pos['hypothetical_sell_fee_unavailable_reason'],'SUSPENDED');self.assertFalse(a['terminal_fee_estimate_complete'])
    def test_daily_volume_cap_is_not_ignored(self):
        c,p=fixture();c['bars'][0]['volume_shares']='30000';a=build_benchmarks(c,p)[0]
        self.assertEqual(a['trades'][0]['quantity'],300)
    def test_fee_boundary_uses_first_entry_date_profile(self):
        c,p=fixture();old=deepcopy(p['fee_schedule'][0]);old.update(effective_until='2025-12-29',minimum_commission_cents=99999)
        p['fee_schedule'][0]['effective_from']='2025-12-30';p['fee_schedule'].insert(0,old);c['fee_schedule']=deepcopy(p['fee_schedule']);c['protocol_ref']=_digest(p)
        a=build_benchmarks(c,p)[0];self.assertEqual(a['trades'][0]['fees_cents'],509)
    def test_yearly_is_continuous_prior_close_not_reset(self):
        rows=[dict(session='2025-12-31',nav_cents=11000),dict(session='2026-01-02',nav_cents=9900),dict(session='2026-02-02',nav_cents=12100)]
        a,b=yearly(rows,10000)
        self.assertEqual((a['opening_nav_cents'],b['opening_nav_cents']),(10000,11000))
        self.assertEqual(D(b['net_return']),D('.1'));self.assertEqual(D(b['within_year_max_drawdown']),D('.1'))
        self.assertFalse(b['account_reset'])
    def test_protocol_or_members_mismatch_rejects(self):
        c,p=fixture();p['initial_cash_cents']+=1
        with self.assertRaisesRegex(ValueError,'PROTOCOL_BINDING'):build_benchmarks(c,p)
        c,p=fixture();c['universe'].pop()
        with self.assertRaisesRegex(ValueError,'EXACT_NINE'):build_benchmarks(c,p)
    def test_forward_cannot_be_marked_historical_control(self):
        c,p=fixture();c['mode']='FORWARD_A'
        with self.assertRaisesRegex(ValueError,'PROTOCOL_BINDING'):build_benchmarks(c,p)
    def test_no_mutation_of_input_case_or_protocol(self):
        c,p=fixture();before=deepcopy((c,p));build_benchmarks(c,p);self.assertEqual((c,p),before)
    def test_single_session_initial_shares_remain_tplusone_locked(self):
        c,p=fixture();c['calendar']=c['calendar'][:1];c['bars']=c['bars'][:9];day=c['calendar'][0]['date']
        c['window']['last_session']=day;p['target_window']['end']=day;c['protocol_ref']=_digest(p)
        a=build_benchmarks(c,p)[0];self.assertEqual(a['terminal_positions'][0]['locked_quantity'],900)
        self.assertIsNone(a['terminal_positions'][0]['hypothetical_sell_fee_cents'])



    def test_history_raw_v2_changes_identity_not_economics(self):
        c,p=fixture();before=build_benchmarks(c,p)
        p.update(version='2.0.0',input_method_version='HISTORY_RAW_V2',forward={'enabled':False},input_policy_ref='sha256:'+'a'*64)
        c['input_policy_ref']=p['input_policy_ref'];c['protocol_ref']=_digest(p)
        after=build_benchmarks(c,p)
        for a,b in zip(before,after):
            a.pop('protocol_ref');b.pop('protocol_ref');self.assertEqual(a,b)
    def test_unknown_history_version_rejected_even_if_rehashed(self):
        c,p=fixture();p['version']='3.0.0';c['protocol_ref']=_digest(p)
        self.assertRaisesRegex(ValueError,'PROTOCOL_BINDING',build_benchmarks,c,p)
    def test_v2_missing_policy_binding_rejected(self):
        c,p=fixture();p.update(version='2.0.0',input_method_version='HISTORY_RAW_V2',forward={'enabled':False},input_policy_ref='sha256:'+'a'*64);c['protocol_ref']=_digest(p)
        self.assertRaisesRegex(ValueError,'PROTOCOL_BINDING',build_benchmarks,c,p)

if __name__=='__main__':unittest.main()
