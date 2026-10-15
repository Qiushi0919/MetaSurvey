"""Fixed-nine long-window controls. New implementation, not independent verification.

Pure; consumes an already source-admitted HISTORY Case. Does not establish data
admission itself. Reuses sealed V3 cost arithmetic, never calls strategy engine.
Integer bonus/split lots are valued on ex date and locked to actual listing date.
"""
from decimal import Decimal as D, localcontext
from hashlib import sha256
from datetime import date
import json

from tools.v3_review.benchmarks import cents, cost, profile_for

RULES_REF = 'sha256:1061fa2d9fb25aeecd60ce26bc404801325882966ee4058994d7eede8dfc084f'
SPECS = (
    {'id': 'NINE_BUY_HOLD_100', 'name': '固定九股等预算简单持有（100%目标）', 'allocation_fraction': '1.00'},
    {'id': 'NINE_BUY_HOLD_60_CASH40', 'name': '固定九股60%等预算＋40%现金', 'allocation_fraction': '0.60'},
)


def _digest(obj):
    return 'sha256:' + sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def yearly(series, initial):
    """Continuous-account calendar year attribution; no annual rebalance/reset."""
    result=[]; opening=initial
    for year in sorted({r['session'][:4] for r in series}):
        rows=[r for r in series if r['session'].startswith(year)]
        peak=opening; mdd=D(0)
        for row in rows:
            peak=max(peak,row['nav_cents']);mdd=max(mdd,D(peak-row['nav_cents'])/peak)
        ending=rows[-1]['nav_cents']
        result.append(dict(year=year,first_session=rows[0]['session'],last_session=rows[-1]['session'],sessions=len(rows),
            opening_nav_cents=opening,ending_nav_cents=ending,net_return=str(D(ending)/opening-1),
            within_year_max_drawdown=str(mdd),account_reset=False))
        opening=ending
    return result


def build_benchmarks(case, protocol):
    supported = protocol.get('version')=='1.0.0' or (protocol.get('version')=='2.0.0'
        and protocol.get('input_method_version')=='HISTORY_RAW_V2'
        and protocol.get('forward',{}).get('enabled') is False
        and case.get('input_policy_ref')==protocol.get('input_policy_ref')
        and isinstance(protocol.get('input_policy_ref'),str))
    if (not supported or case.get('mode')!='HISTORY'
        or case.get('protocol_ref')!=_digest(protocol)
        or case.get('namespace')!=protocol.get('namespace')
        or case.get('strategy_id')!=protocol.get('strategy_id')
        or protocol.get('benchmark',{}).get('rules_ref')!=RULES_REF
        or case['fee_schedule']!=protocol['fee_schedule']):
        raise ValueError('BENCHMARK_PROTOCOL_BINDING')
    members={m['symbol']:m['sector'] for m in case['universe']}
    if len(members)!=9 or len(case['universe'])!=9 or members!=protocol['members']:
        raise ValueError('EXACT_NINE_MEMBERS_REQUIRED')
    if type(protocol['initial_cash_cents']) is not int or protocol['initial_cash_cents']<=0:
        raise ValueError('INITIAL_CASH_REQUIRED')
    all_dates=[r['date'] for r in case['calendar']]
    if all_dates!=sorted(set(all_dates)):raise ValueError('ORDERED_CALENDAR_REQUIRED')
    target=protocol['target_window']
    dates=[d for d in all_dates if target['start']<=d<=target['end']]
    if not dates or case['window']!={'first_session':dates[0],'last_session':dates[-1]}:
        raise ValueError('BENCHMARK_WINDOW_BINDING')
    seen=set(); action_dates=set()
    for action in case['actions']:
        if action['id'] in seen:raise ValueError('DUPLICATE_ACTION')
        seen.add(action['id'])
        pair=(action['symbol'],action['ex_date'])
        if pair in action_dates:raise ValueError('MULTIPLE_ACTION_COMPOSITION_UNSUPPORTED')
        action_dates.add(pair)
        if action['symbol'] not in members:raise ValueError('ACTION_SYMBOL_OUTSIDE_SCOPE')
        if action['record_date'] not in all_dates or action['ex_date'] not in all_dates:
            raise ValueError('ACTION_CALENDAR_REQUIRED')
        if all_dates.index(action['ex_date'])!=all_dates.index(action['record_date'])+1:
            raise ValueError('ACTION_RECORD_EX_NOT_ADJACENT')
        cash,bonus,split,tax=[D(action[k]) for k in ('cash_per_share','bonus_ratio','split_ratio','tax_rate')]
        if not all(x.is_finite() for x in (cash,bonus,split,tax)) or cash<0 or bonus<0 or split<1 or tax!=D('.20'):
            raise ValueError('ACTION_VALUES_OR_SIMULATED_TAX_INVALID')
        for field,needed in (('pay_date',cash>0),('shares_available_date',bonus+split>1)):
            value=action[field]
            if needed and (not value or value<action['ex_date']):raise ValueError('ACTION_REQUIRED_SETTLEMENT_DATE:'+field)
            if value is not None and (type(value) is not str or date.fromisoformat(value).isoformat()!=value):
                raise ValueError('ACTION_SETTLEMENT_DATE_INVALID')
    with localcontext() as context:
        context.prec=80
        return [_run(case,protocol,spec,dates) for spec in SPECS]


def _run(case,protocol,spec,dates):
    initial=protocol['initial_cash_cents'];cash=initial;symbols=sorted(protocol['members'])
    bars={(r['session'],r['symbol']):r for r in case['bars']}
    if len(bars)!=len(case['bars']):raise ValueError('DUPLICATE_BAR')
    slot=int(D(initial)*D(spec['allocation_fraction'])/9)
    lots={s:[] for s in symbols};marks={};entitlements={};receivables={}
    trades=[];rejected=[];ledger=[];series=[];actions=[];errors=[]
    dividend=0;peak=initial;peakday='INITIAL_CAPITAL';maximum=D(0);trough=None;ddpeak=None
    all_dates=[r['date'] for r in case['calendar']]
    def quantity(symbol):return sum(l['quantity'] for l in lots[symbol])
    def book(day,kind,delta,symbol,**extra):
        nonlocal cash
        before=cash
        if before+delta<0:raise ValueError('NEGATIVE_CASH')
        cash+=delta
        ledger.append(dict(session=day,kind=kind,symbol=symbol,cash_before_cents=before,cash_delta_cents=delta,cash_after_cents=cash,**extra))
    day=None
    try:
        for day in dates:
            rows={s:bars[(day,s)] for s in symbols}
            for symbol,row in rows.items():
                if row['status'] not in ('TRADABLE','SUSPENDED'):raise ValueError('UNKNOWN_STATUS')
                if row['status']=='TRADABLE':
                    nums=[D(row[k]) for k in ('open','high','low','close','lower_limit','upper_limit','volume_shares')]
                    if not all(x.is_finite() and x>0 for x in nums):raise ValueError('INVALID_TRADABLE_DATA')
                    o,h,l,c,lo,hi,v=nums
                    if not lo<=l<=min(o,c)<=max(o,c)<=h<=hi or lo>=hi:raise ValueError('INVALID_OHLC_LIMITS')
                    if type(row['lot_size']) is not int or row['lot_size']<1:raise ValueError('INVALID_LOT')
                elif any(row[k] is not None for k in ('open','high','low','close')) or D(row['volume_shares'])!=0:
                    raise ValueError('INVALID_SUSPENSION')
            for a in case['actions']:
                if a['ex_date']!=day:continue
                symbol=a['symbol'];qty=entitlements.get(a['id'],0);ratio=D(a['split_ratio'])+D(a['bonus_ratio']);total=D(qty)*ratio
                if total!=int(total):raise ValueError('FRACTIONAL_ACTION_UNSUPPORTED:'+a['id'])
                if quantity(symbol)!=qty:raise ValueError('RECORD_EX_QUANTITY_CONFLICT')
                newmark=(marks[symbol]-D(a['cash_per_share']))/ratio if symbol in marks else None
                if newmark is not None and newmark<=0:raise ValueError('ACTION_NONPOSITIVE_MARK')
                net=cents(D(qty)*D(a['cash_per_share'])*(1-D(a['tax_rate'])))
                added=int(total)-qty
                if added:lots[symbol].append(dict(quantity=added,available_date=a['shares_available_date'],origin=a['id']))
                if newmark is not None:marks[symbol]=newmark
                if net:receivables[a['id']]={'cents':net,'pay_date':a['pay_date'],'symbol':symbol}
                event=dict(id=a['id'],session=day,symbol=symbol,stage='EX',record_quantity=qty,added_shares=added,
                    share_availability=a['shares_available_date'],net_receivable_cents=net,tax_rate=a['tax_rate'],gross_cash_per_share=a['cash_per_share'])
                actions.append(event);book(day,'ACTION_EX',0,symbol,action_id=a['id'],added_shares=added)
            for key,rec in list(receivables.items()):
                if rec['pay_date']<=day:
                    book(day,'DIVIDEND_PAYMENT',rec['cents'],rec['symbol'],action_id=key);dividend+=rec['cents'];del receivables[key]
            if day==dates[0]:
                for symbol in symbols:
                    row=rows[symbol];reason=None;q=None
                    if row['status']=='SUSPENDED':reason='SUSPENDED'
                    else:
                        lot=row['lot_size'];volume_limit=int(D(row['volume_shares'])*D('.01'))//lot*lot
                        upper=min(volume_limit,int(D(slot)/100/D(row['open']))//lot*lot)
                        for qty in range(upper,0,-lot):
                            trial=cost(row['open'],qty,'BUY',profile_for(case,day))
                            if -trial['cash_delta_cents']<=min(slot,cash):q=trial;break
                        if q is None:reason='SLOT_CASH_LOT_OR_VOLUME_UNAFFORDABLE'
                        else:
                            fill=D(q['execution_price']);opened=D(row['open'])
                            if min(fill,opened)<=D(row['lower_limit']) or max(fill,opened)>=D(row['upper_limit']):reason='LIMIT_OR_SLIPPAGE_BOUND'
                            elif not D(row['low'])<=fill<=D(row['high']):reason='SLIPPAGE_OUTSIDE_DAILY_RANGE'
                    if reason:rejected.append(dict(session=day,symbol=symbol,reason=reason,slot_budget_cents=slot));continue
                    book(day,'BUY',q['cash_delta_cents'],symbol)
                    idx=all_dates.index(day);available=all_dates[idx+1] if idx+1<len(all_dates) else '9999-12-31'
                    lots[symbol].append(dict(quantity=q['quantity'],available_date=available,origin='INITIAL_BUY'))
                    trades.append(dict(session=day,symbol=symbol,**q))
            for symbol,row in rows.items():
                if row['status']=='TRADABLE':marks[symbol]=D(row['close'])
                if quantity(symbol) and symbol not in marks:raise ValueError('NO_CAUSAL_MARK')
            for a in case['actions']:
                if a['record_date']==day:entitlements[a['id']]=quantity(a['symbol'])
            exposure=sum(cents(marks[s]*quantity(s)) for s in symbols if quantity(s));recv=sum(r['cents'] for r in receivables.values());nav=cash+exposure+recv
            if nav<=0:raise ValueError('NONPOSITIVE_NAV')
            if nav>peak:peak=nav;peakday=day
            dd=D(peak-nav)/peak
            if dd>maximum:maximum=dd;trough=day;ddpeak=peakday
            series.append(dict(session=day,nav_cents=nav,nav_cny=str(D(nav)/100),cash_cents=cash,exposure_cents=exposure,
                receivable_cents=recv,drawdown_fraction=str(dd),exposure_fraction=str(D(exposure)/nav)))
    except (ValueError,KeyError,ArithmeticError) as exc:
        errors.append(dict(session=day,error=type(exc).__name__,detail=str(exc)))
    valid=not errors;terminal=[];reserve=0
    if valid:
        for symbol in symbols:
            qty=quantity(symbol)
            if not qty:continue
            eligible=sum(l['quantity'] for l in lots[symbol] if l['available_date']<=dates[-1]);row=bars[(dates[-1],symbol)]
            reason=None;q=None
            if not eligible:reason='ALL_SHARES_LOCKED'
            elif row['status']=='SUSPENDED':reason='SUSPENDED'
            else:
                q=cost(str(marks[symbol]),eligible,'SELL',profile_for(case,dates[-1]));price=D(q['execution_price'])
                if min(price,marks[symbol])<=D(row['lower_limit']) or max(price,marks[symbol])>=D(row['upper_limit']):reason='LIMIT_OR_SLIPPAGE_BOUND'
                elif not D(row['low'])<=price<=D(row['high']):reason='SLIPPAGE_OUTSIDE_DAILY_RANGE'
                elif eligible>D(row['volume_shares'])*D('.01'):reason='VOLUME_PARTICIPATION_LIMIT'
            fee=q['fees_cents'] if q is not None and reason is None else None
            if fee is not None:reserve+=fee
            terminal.append(dict(symbol=symbol,quantity=qty,settlement_eligible_quantity=eligible,locked_quantity=qty-eligible,
                market_value_cents=cents(marks[symbol]*qty),lots=lots[symbol],hypothetical_sell_fee_cents=fee,
                hypothetical_sell_fee_unavailable_reason=reason,terminal_sale_executed=False))
    maxpeak=initial if ddpeak=='INITIAL_CAPITAL' else next((r['nav_cents'] for r in series if r['session']==ddpeak),initial)
    recovery=next((r['session'] for r in series if trough and r['session']>trough and r['nav_cents']>=maxpeak),None)
    return dict(id=spec['id'],name=spec['name'],run_id=case['run_id'],protocol_ref=case['protocol_ref'],
        status='COMPLETED_DIAGNOSTIC_CONTROL' if valid else 'FAILED_PARTIAL_INVALID',errors=errors,nav_series=series,
        net_return=str(D(series[-1]['nav_cents'])/initial-1) if valid else None,max_drawdown=str(maximum) if valid else None,
        drawdown_dates=dict(peak=ddpeak,trough=trough,recovery=recovery) if valid else None,yearly=yearly(series,initial) if valid else [],
        trades=trades,rejections=rejected,ledger=ledger,actions=actions,terminal_positions=terminal,
        partial_holdings=lots if not valid else None,terminal_cash_cents=cash,terminal_receivable_cents=sum(r['cents'] for r in receivables.values()),
        fees_cents=sum(x['fees_cents'] for x in trades),slippage_cents=sum(x['slippage_cents'] for x in trades),dividend_cents=dividend,
        initial_budget_per_symbol_cents=slot,initial_invested_notional_cents=sum(x['notional_cents'] for x in trades),
        average_exposure_fraction=str(sum(D(r['exposure_fraction']) for r in series)/len(series)) if valid else None,
        maximum_exposure_fraction=str(max(D(r['exposure_fraction']) for r in series)) if valid else None,
        exposed_sessions=sum(r['exposure_cents']>0 for r in series),last40_no_new_entry_effect='NONE_SINGLE_INITIAL_PURCHASE_ONLY',
        hypothetical_terminal_sell_fees_cents=reserve if valid else None,
        terminal_fee_estimate_scope='ONLY_SETTLEMENT_ELIGIBLE_QUANTITY_WITH_LAST_DAY_EXECUTION_BOUNDS; NOT_A_LIQUIDATION',
        terminal_fee_estimate_complete=valid and all(p['hypothetical_sell_fee_cents'] is not None and p['locked_quantity']==0 for p in terminal),
        terminal_sell_fee_reserve_is_fill=False,cost_label='SIMULATED_COSTS',dividend_tax_label='FLAT20_SIMULATION_NOT_ACTUAL_TAX',
        historical_visibility_proven=False,untouched_oos=False,production_enabled=False)
