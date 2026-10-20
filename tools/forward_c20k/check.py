"""Portable synthetic unit checks. No private files, market or credentials."""
from copy import deepcopy
import unittest
from experiments.account20k_v1.costs import *
from experiments.account20k_v1.matching import match
from .account import apply_fill, reserve, reconcile_close

class Costs(unittest.TestCase):
    def test_minimum(self):
        self.assertEqual(cumulative_fees(100000,'BUY','2026-10-20'),
            {'commission_cents':500,'stamp_cents':0,'transfer_cents':1})
    def test_sell(self):
        self.assertEqual(cumulative_fees(100000,'SELL','2026-10-20'),
            {'commission_cents':500,'stamp_cents':50,'transfer_cents':1})
    def test_no_fill(self):
        self.assertEqual(sum(cumulative_fees(0,'BUY','2026-10-20').values()),0)
    def test_partial_order(self):
        a=partial_fill_fees(0,100000,'BUY','2026-10-20');b=partial_fill_fees(100000,100000,'BUY','2026-10-20')
        self.assertEqual(a['commission_cents']+b['commission_cents'],500)
    def test_separate_orders(self):
        self.assertEqual(sum(partial_fill_fees(0,100000,'BUY','2026-10-20')['commission_cents'] for _ in range(2)),1000)
    def test_historical_dates(self):
        self.assertEqual(cumulative_fees(1000000,'SELL','2021-10-20')['transfer_cents'],20)
        self.assertEqual(cumulative_fees(1000000,'SELL','2023-08-27')['stamp_cents'],1000)
    def test_month_boundary(self):
        self.assertEqual(dividend_rate('2026-01-31','2026-02-28'),D('.20'))
        self.assertEqual(dividend_rate('2026-01-31','2026-03-01'),D('.10'))
    def test_year_boundary(self):
        self.assertEqual(dividend_rate('2025-10-20','2026-10-20'),D('.10'))
        self.assertEqual(dividend_rate('2025-10-20','2026-10-21'),D('0'))
    def test_fifo(self):
        lots=[dict(lot_id='a',acquired='2026-01-01',quantity=100,dividends=[{'gross_cash_per_share':'1'}]),
              dict(lot_id='b',acquired='2026-10-01',quantity=100,dividends=[{'gross_cash_per_share':'1'}])]
        self.assertEqual(dividend_tax_for_sale(lots,150,'2026-10-20')['tax_cents'],2000)

def fixture():
    order=dict(symbol='603228.SH',side='BUY',session='2026-10-20',submitted_at='2026-10-20T09:35:00+08:00',
        expires_at='2026-10-20T14:50:00+08:00',remaining_quantity=200,filled_notional_cents=0,
        limit_price='10.20',lot_size=100)
    previous=dict(symbol='603228.SH',source_at='2026-10-20T09:36:00+08:00',
        received_at='2026-10-20T09:36:02+08:00',volume_unit='SHARES',volume=10000)
    current=dict(previous,source_at='2026-10-20T09:37:00+08:00',received_at='2026-10-20T09:37:02+08:00',
        volume=40000,last='10',status='TRADABLE',state_evidence_verified=True,limits_evidence_verified=True,
        down_limit='9',up_limit='11',ask_price=None,ask_quantity=None)
    return order,previous,current,'2026-10-20T09:37:03+08:00',2000000,0
class Matching(unittest.TestCase):
    def test_causal_fill(self):
        r=match(*fixture());self.assertEqual((r['quantity'],r['price'],r['cash_delta_cents']),(200,'10.01',-200702))
    def test_stale(self):
        a=list(fixture());a[3]='2026-10-20T09:40:03+08:00';self.assertEqual(match(*a)['reason'],'STALE_MARKET_QUOTE')
    def test_no_source(self):
        a=list(fixture());a[2]['source_at']=None;self.assertEqual(match(*a)['reason'],'SOURCE_TIME_MISSING')
    def test_preorder(self):
        a=list(fixture());a[0]['submitted_at']='2026-10-20T09:36:00+08:00';self.assertEqual(match(*a)['state'],'UNFILLED')
    def test_no_volume(self):
        a=list(fixture());a[2]['volume']=10000;self.assertEqual(match(*a)['reason'],'NO_INCREMENTAL_MARKET_VOLUME')
    def test_cash(self):
        a=list(fixture());a[4]=50000;self.assertEqual(match(*a)['state'],'UNFILLED')
    def test_unknown_limit(self):
        a=list(fixture());a[2]['limits_evidence_verified']='false';self.assertEqual(match(*a)['state'],'UNFILLED')
    def test_wrong_session(self):
        a=list(fixture());a[0]['session']='2026-10-19';self.assertEqual(match(*a)['state'],'UNFILLED')
    def test_lunch(self):
        a=list(fixture());a[2]['source_at']='2026-10-20T12:01:00+08:00';a[2]['received_at']=a[2]['source_at'];a[3]=a[2]['source_at'];self.assertEqual(match(*a)['state'],'UNFILLED')
    def test_price_protection(self):
        a=list(fixture());a[0]['limit_price']='10.00';self.assertEqual(match(*a)['reason'],'ORDER_PRICE_PROTECTION')
    def test_depth_capacity(self):
        a=list(fixture());a[2].update(ask_price='10',ask_quantity=500);self.assertEqual(match(*a)['state'],'UNFILLED')

class Account(unittest.TestCase):
    def account(self):
        o=fixture()[0];o.update(quantity=200,reserve_cents=201000,sector='PCB_SAMPLE',next_session='2026-10-21',
                               atr20='0.3',order_id='o',state='SUBMITTED')
        return dict(cash_cents=2000000,positions={},orders={'o':o},fills=[],ledger=[],dividends=[],
                    peak_cents=2000000,maximum_drawdown='0')
    def test_fill_and_replay(self):
        a=self.account();r=match(*fixture());apply_fill(a,'o',r,'sha256:x')
        self.assertEqual(a['cash_cents'],1799298);self.assertEqual(a['frozen_cash_cents'],0)
        with self.assertRaises(ValueError):apply_fill(a,'o',r,'sha256:x')
    def test_no_fee_on_expiry(self):
        a=self.account();a['orders']['o']['state']='EXPIRED';reserve(a)
        self.assertEqual(a['available_cash_cents'],2000000);self.assertEqual(a['ledger'],[])
    def test_cash_dividend(self):
        a=self.account();apply_fill(a,'o',match(*fixture()),'sha256:x')
        action=dict(id='div',symbol='603228.SH',record_date='2026-10-20',ex_date='2026-10-21',
                    pay_date='2026-10-21',cash_per_share='0.5',bonus_ratio='0',split_ratio='1')
        c=dict(calendar=[{'date':'2026-10-20'},{'date':'2026-10-21'}],actions=[action],
            bars=[{'session':d,'symbol':'603228.SH','status':'TRADABLE','close':'10'} for d in ('2026-10-20','2026-10-21')])
        reconcile_close(a,c,'2026-10-20');self.assertEqual(a['tax_reserve_cents'],2000)
        reconcile_close(a,c,'2026-10-21');self.assertEqual(a['cash_cents'],1809298)
        reconcile_close(a,c,'2026-10-21');self.assertEqual(a['cash_cents'],1809298)

if __name__=='__main__':unittest.main()
