"""Independent hand-oracle fee and causal-match counterexamples; no market I/O.
Production functions are only the system under test, never the source of expected
numbers. Every expectation below is hand-derived or an explicit fail-closed
invariant. JSON receipts pin the exact source reviewed.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
from experiments.account20k_v1 import costs, matching


def samples():
    order=dict(order_id='SYNTHETIC-ORDER-1',symbol='TEST',side='BUY',session='2026-10-21',submitted_at='2026-10-21T09:30:00+08:00',expires_at='2026-10-21T14:57:00+08:00',remaining_quantity=500,filled_notional_cents=0,limit_price='11',lot_size=100)
    previous=dict(symbol='TEST',source_at='2026-10-21T09:36:00+08:00',received_at='2026-10-21T09:36:01+08:00',volume=100000,volume_unit='SHARES')
    current=dict(symbol='TEST',source_at='2026-10-21T09:36:10+08:00',received_at='2026-10-21T09:36:11+08:00',volume=120000,volume_unit='SHARES',status='TRADABLE',state_evidence_verified=True,limits_evidence_verified=True,down_limit='9',up_limit='11',last='10',ask_price='10',ask_quantity=10000,book_quantity_unit='SHARES')
    return order,previous,current,'2026-10-21T09:36:12+08:00'


def review():
    checks=[]
    def equal(name,actual,expected):checks.append(dict(name=name,passed=actual==expected,actual=actual,expected=expected))
    def refuse(name,mutation):
        o,p,c,t=samples();o,p,c,t=mutation(o,p,c,t)
        try:
            result=matching.match(o,p,c,t,2000000,500)
            passed=result.get('state')!='SIMULATED_FILL';actual=result
        except (ValueError,KeyError,TypeError):passed=True;actual='REJECTED_INVALID_INPUT'
        checks.append(dict(name=name,passed=passed,expected='NO_SIMULATED_FILL',actual=actual))
    equal('minimum_commission_first_partial',costs.partial_fill_fees(0,100000,'BUY','2026-10-21'),dict(commission_cents=500,stamp_cents=0,transfer_cents=1))
    equal('same_order_second_partial_no_second_minimum',costs.partial_fill_fees(100000,100000,'BUY','2026-10-21'),dict(commission_cents=0,stamp_cents=0,transfer_cents=1))
    equal('independent_orders_each_minimum',sum(sum(costs.partial_fill_fees(0,100000,'BUY','2026-10-21').values()) for _ in range(2)),1002)
    equal('commission_boundary_20000_CNY',costs.cumulative_fees(2000000,'BUY','2026-10-21')['commission_cents'],500)
    equal('commission_above_minimum_20040_CNY',costs.cumulative_fees(2004000,'BUY','2026-10-21')['commission_cents'],501)
    for day,expected in [('2022-04-28',1520),('2022-04-29',1510),('2023-08-27',1510),('2023-08-28',1010)]:
        equal('dated_sell_fee_'+day,sum(costs.cumulative_fees(1000000,'SELL',day).values()),expected)
    o,p,c,t=samples();a=matching.match(o,p,c,t,2000000,500)
    equal('positive_causal_fill_hand_quantity_price_cash',{k:a.get(k) for k in ['state','quantity','price','cash_delta_cents']},dict(state='SIMULATED_FILL',quantity=200,price='10.01',cash_delta_cents=-200702))
    def current_change(**kwargs):return lambda o,p,c,t:(o,p,dict(c,**kwargs),t)
    refuse('string_false_is_not_verified_limits',current_change(limits_evidence_verified='false'))
    refuse('source_clock_missing',current_change(source_at=None))
    refuse('future_source_clock',current_change(source_at='2026-10-21T09:37:00+08:00'))
    refuse('stale_quote',lambda o,p,c,t:(o,p,c,'2026-10-21T09:40:00+08:00'))
    refuse('repeated_market_snapshot_no_new_volume',current_change(volume=100000))
    refuse('noninteger_market_share_volume',current_change(volume='120000.5'))
    refuse('previous_received_after_current',lambda o,p,c,t:(o,dict(p,received_at='2026-10-21T09:40:00+08:00'),c,t))
    refuse('order_session_must_match_execution_session',lambda o,p,c,t:(dict(o,session='2022-04-28'),p,c,t))
    def lunch(o,p,c,t):
        return dict(o,submitted_at='2026-10-21T12:00:00+08:00'),dict(p,source_at='2026-10-21T12:01:00+08:00',received_at='2026-10-21T12:01:01+08:00'),dict(c,source_at='2026-10-21T12:01:10+08:00',received_at='2026-10-21T12:01:11+08:00'),'2026-10-21T12:01:12+08:00'
    refuse('lunch_break_no_continuous_market_fill',lunch)
    refuse('unverified_current_status',current_change(state_evidence_verified=False))
    refuse('unknown_share_volume_unit',current_change(volume_unit='LOTS'))
    refuse('order_limit_protects',lambda o,p,c,t:(dict(o,limit_price='10.00'),p,c,t))
    return dict(kind='IndependentAccount20kHandOracleReview',synthetic=True,investment_evidence=False,recorded_at=datetime.now(timezone.utc).isoformat(),passed=all(c['passed'] for c in checks),count=len(checks),checks=checks,source_hashes={str(Path(m.__file__).resolve()):'sha256:'+sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (costs,matching)},limitations=['This verifies fee arithmetic and matcher refusal invariants; per-order identity and snapshot idempotency require caller-state audit','No private source/market data read; no strategy performance claims'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=review();a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(dict(passed=r['passed'],count=r['count'],failed=[c['name'] for c in r['checks'] if not c['passed']])))
