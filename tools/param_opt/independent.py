"""Independent PARAM_OPT_V1 decision reconstruction and accounting. Standard library only.

Input is a preserved Case, never original decisions/fills. Original outputs are
read only by compare_result after the independently generated trace exists.
This verifier is not a new strategy run or a data/PIT/license admission service.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from decimal import Decimal as D, localcontext, ROUND_HALF_EVEN, ROUND_CEILING
from hashlib import sha256
from pathlib import Path
from statistics import median
import argparse
import json


def cents(value):
    return int((D(value)*100).quantize(D(1), rounding=ROUND_HALF_EVEN))


def digest(value):
    return 'sha256:'+sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def costs(raw, quantity, side, policy):
    raw=D(raw)
    price=(raw*(1+D(1 if side=='BUY' else -1)*D(policy['slippage_bps'])/10000)).quantize(D('.01'),rounding=ROUND_HALF_EVEN)
    notional=cents(price*quantity); original=cents(raw*quantity)
    def rate(value):return int((D(notional)*D(value)).quantize(D(1),rounding=ROUND_HALF_EVEN))
    base=rate(policy['commission_rate']);commission=max(base,policy['minimum_commission_cents'])
    exchange=0 if policy['exchange_included'] else rate(policy['exchange_rate'])
    other=0 if policy['other_included'] else rate(policy['other_buy_rate'] if side=='BUY' else policy['other_sell_rate'])
    tax=rate(policy['sell_tax_rate']) if side=='SELL' else 0
    fees={'notional_cents':notional,'raw_notional_cents':original,'commission_cents':commission,
          'minimum_commission_uplift_cents':commission-base,'exchange_cents':exchange,
          'other_cents':other,'sell_tax_cents':tax,'total_fee_cents':commission+exchange+other+tax,'slippage_cents':abs(notional-original)}
    delta=(-notional if side=='BUY' else notional)-fees['total_fee_cents']
    return {'price':price,'fees':fees,'delta':delta}


def indicators(history, params):
    if len(history)<max(21,params["rs_window"]+1):return None
    window=history[-21:];last=window[-1];mean=sum(x['close'] for x in window[1:])/20
    ranges=[max(window[i]['high']-window[i]['low'],abs(window[i]['high']-window[i-1]['close']),abs(window[i]['low']-window[i-1]['close'])) for i in range(1,21)]
    atr=sum(ranges)/20;relative=last['close']/history[-params['rs_window']-1]['close']-1
    breakout=last['close']>max(x['high'] for x in window[:-1])
    pullback=last['low']<=mean<last['close'] and last['close']>window[-2]['close']
    return {'sma':mean,'atr':atr,'rs':relative,'eligible':atr>0 and (breakout or pullback),
            'breakout':breakout,'pullback':pullback,'median_volume':median(x['volume_shares'] for x in window[1:])}


def exit_reason(bar,position,history,age,params):
    reason='MAXIMUM_40_EXCHANGE_SESSIONS' if age>=40 else None
    if bar['status']=='TRADABLE':
        close=D(bar['close'])
        if close<=position['stop']:reason='CLOSE_STOP_'+format(D(params['atr_multiple']).normalize(),'f')+'_ATR20'
        elif age>=params['exit_min_age'] and len(history)>=params['exit_ma'] and close<sum(r['close'] for r in history[-params['exit_ma']:])/params['exit_ma']:
            reason='CLOSE_LOGIC_INVALIDATION_SMA'+str(params['exit_ma'])
        elif age>=20 and close<=position['entry_compare']:reason='DAY20_NONPOSITIVE_ADJUSTED_PRICE_RETURN'
    return reason


def executable(row, quote, quantity):
    if row['status']=='SUSPENDED':return 'SUSPENDED'
    price=quote['price'];opened=D(row['open'])
    if min(opened,price)<=D(row['lower_limit']) or max(opened,price)>=D(row['upper_limit']):return 'LIMIT_OR_SLIPPAGE_BOUND'
    if not D(row['low'])<=price<=D(row['high']):return 'SLIPPAGE_OUTSIDE_DAILY_RANGE'
    if quantity>int(D(row['volume_shares'])*D('.01')):return 'ACTUAL_SESSION_VOLUME_CAP'
    return None


def allocate(symbol, sector, bar, feature, positions, marks, cash, receivables, policy, params):
    """Enumerate all allowable lots ascending, independently of production descending search."""
    values={s:cents(marks[s].quantize(D('.000000000001'),rounding=ROUND_HALF_EVEN)*sum(x['qty'] for x in p['lots'])) for s,p in positions.items()}
    sector_values={p['sector']:sum(values[s] for s,p2 in positions.items() if p2['sector']==p['sector']) for p in positions.values()}
    invested=sum(values.values());nav=cash+invested+sum(x['amount'] for x in receivables.values())
    if symbol in positions:return None,'NO_AVERAGING_OR_SAME_DAY_REENTRY',0
    if any(v>int(D(nav)*D('.20')) for v in values.values()) or any(v>int(D(nav)*D('.40')) for v in sector_values.values()):return None,'PASSIVE_POSITION_OR_SECTOR_CAP',0
    if len(positions)>=3:return None,'POSITION_COUNT_LIMIT',0
    if invested>=int(D(nav)*D('.60')):return None,'PASSIVE_OR_ACTIVE_EXPOSURE_CAP',0
    if sector_values.get(sector,0)>=int(D(nav)*D('.40')):return None,'SECTOR_CAP',0
    budget=min(cash,int(D(nav)*D('.20')),int(D(nav)*D('.60'))-invested,int(D(nav)*D('.40'))-sector_values.get(sector,0))
    lot=bar['lot_size'];raw=D(bar['open']);maximum=min(int(D(budget)/(raw*100)/lot)*lot,int(feature['median_volume']*D('.01')/lot)*lot)
    atr=feature['atr'].quantize(D('.000000000001'),rounding=ROUND_CEILING)
    selected=None;evaluated=0
    for qty in range(lot,maximum+1,lot):
        evaluated+=1;entry=costs(raw,qty,'BUY',policy)
        stop=(entry['price']-D(params['atr_multiple'])*atr).quantize(D('.01'),rounding=ROUND_HALF_EVEN)
        if stop<=0:continue
        exit_quote=costs(stop,qty,'SELL',policy);loss=-entry['delta']-exit_quote['delta']
        if -entry['delta']<=cash and entry['fees']['notional_cents']<=budget and loss<=int(D(nav)*D('.01')):
            selected={'quantity':qty,'entry':entry,'stop':stop,'loss':loss,'atr':atr,'nav_cents':nav,'budget_cents':budget}
    return selected,None if selected else 'RISK_CASH_LOT_OR_VOLUME_UNAFFORDABLE',evaluated


def reconstruct(case, params):
    """Reconstruct only the pre-existing declared V3 strategy; never reads EngineResult."""
    with localcontext() as context:
        context.prec=80
        return _reconstruct(case, validate_params(params))


def _reconstruct(case, params):
    dates=[x['date'] for x in case['calendar']];members={x['symbol']:x['sector'] for x in case['universe']}
    rows={(x['session'],x['symbol']):x for x in case['bars']};groups={g:[s for s in members if members[s]==g] for g in sorted(set(members.values()))}
    first,last=case['window']['first_session'],case['window']['last_session'];last_index=dates.index(last)
    cash=10000000;holdings={};marks={};receivables={};entitlements={};history={s:[] for s in members};streak={s:0 for s in members}
    waiting_sell={};waiting_buy=[];decisions=[];fills=[];unfilled=[];daily=[];features_trace=[];attempts=[];evaluated_lots=0
    def quantity(symbol):return sum(x['qty'] for x in holdings.get(symbol,{}).get('lots',[]))
    for index,calendar in enumerate(case['calendar']):
        day=calendar['date']
        if day>last:break
        current={s:rows[(day,s)] for s in members}
        for action in case['actions']:
            if action['ex_date']!=day:continue
            s=action['symbol'];subtract=D(action['cash_per_share']);ratio=D(action['split_ratio'])+D(action['bonus_ratio']);old=entitlements.get(action['id'],0)
            extra=D(old)*(ratio-1)
            if extra!=int(extra):raise ValueError('UNSUPPORTED_FRACTIONAL_ENTITLEMENT')
            for record in history[s]:
                for field in ('open','high','low','close'):record[field]=(record[field]-subtract)/ratio
            for candidate in waiting_buy:
                if candidate['symbol']==s:candidate['feature']['atr']/=ratio
            if s in marks:marks[s]=(marks[s]-subtract)/ratio
            if s in holdings:
                holdings[s]['stop']=(holdings[s]['stop']-subtract)/ratio;holdings[s]['entry_compare']=(holdings[s]['entry_compare']-subtract)/ratio
                if extra:holdings[s]['lots'].append({'qty':int(extra),'available':action['shares_available_date']})
            net=cents(D(old)*subtract*(1-D(action['tax_rate'])))
            if net:receivables[action['id']]={'amount':net,'due':action['pay_date']}
        due=[key for key,value in receivables.items() if value['due']<=day]
        for key in due:cash+=receivables.pop(key)['amount']
        policy_rows=[p for p in case['fee_schedule'] if p['effective_from']<=day<=p['effective_until']]
        if len(policy_rows)!=1:raise ValueError('COST_DATE_AMBIGUITY')
        policy=policy_rows[0];sold=set()
        if day>=first:
            for s in sorted(waiting_sell):
                bar=current[s];q=sum(x['qty'] for x in holdings[s]['lots'] if x['available']<=day)
                reason='SUSPENDED' if bar['status']=='SUSPENDED' else ('T_PLUS_ONE_OR_ACTION_SHARES_LOCKED' if q==0 else None)
                sale=None
                if reason is None:
                    sale=costs(bar['open'],q,'SELL',policy);reason=executable(bar,sale,q)
                    if cash+sale['delta']<0:reason='EXIT_FEES_EXCEED_CASH'
                attempts.append({'session':day,'symbol':s,'side':'SELL','quantity':q,'outcome':reason or 'FILLED'})
                if reason:
                    unfilled.append({'session':day,'symbol':s,'side':'SELL','reason':reason,'retained_quantity':quantity(s)});continue
                cash+=sale['delta'];fills.append({'session':day,'symbol':s,'side':'SELL','quantity':q,'execution_price':str(sale['price']),'fees':sale['fees'],'cash_delta_cents':sale['delta'],'reason':waiting_sell[s]});sold.add(s)
                holdings[s]['lots']=[x for x in holdings[s]['lots'] if x['available']>day]
                if not holdings[s]['lots']:del holdings[s];del waiting_sell[s]
                else:unfilled.append({'session':day,'symbol':s,'side':'SELL','reason':'ACTION_SHARES_STILL_LOCKED','retained_quantity':quantity(s)})
            for candidate in waiting_buy:
                s=candidate['symbol'];bar=current[s]
                reason='NO_SAME_DAY_REENTRY' if s in sold else ('SUSPENDED' if bar['status']=='SUSPENDED' else None)
                plan=None;lot_count=0
                if reason is None:
                    plan,reason,lot_count=allocate(s,members[s],bar,candidate['feature'],holdings,marks,cash,receivables,policy,params);evaluated_lots+=lot_count
                if plan:reason=executable(bar,plan['entry'],plan['quantity'])
                attempts.append({'session':day,'symbol':s,'side':'BUY','quantity':plan['quantity'] if plan else None,'outcome':reason or 'FILLED','enumerated_lots':lot_count,'nav_cents':plan['nav_cents'] if plan else None,'budget_cents':plan['budget_cents'] if plan else None})
                if reason:unfilled.append({'session':day,'symbol':s,'side':'BUY','reason':reason});continue
                buy=plan['entry'];cash+=buy['delta'];fills.append({'session':day,'symbol':s,'side':'BUY','quantity':plan['quantity'],'execution_price':str(buy['price']),'fees':buy['fees'],'cash_delta_cents':buy['delta'],'planned_loss_cents':plan['loss']})
                holdings[s]={'sector':members[s],'entry_index':index,'entry_compare':buy['price'],'stop':plan['stop'],'lots':[{'qty':plan['quantity'],'available':dates[index+1]}]};marks[s]=buy['price']
        for s,bar in current.items():
            if bar['status']=='TRADABLE':history[s].append({k:D(bar[k]) for k in ('open','high','low','close','volume_shares')});marks[s]=D(bar['close']);streak[s]+=1
            else:streak[s]=0
        for action in case['actions']:
            if action['record_date']==day:entitlements[action['id']]=quantity(action['symbol'])
        if day<first:continue
        feature={s:indicators(history[s],params) for s in members}
        fresh_reasons={}
        for s,pos in holdings.items():
            age=index-pos['entry_index']+1
            reason=exit_reason(current[s],pos,history[s],age,params)
            if reason:
                fresh_reasons[s]=reason
                if s not in waiting_sell:waiting_sell[s]=reason
        excluded={};strength={}
        for group,symbols in groups.items():
            if any(feature[s] is None or current[s]['status']!='TRADABLE' or streak[s]<max(21,params['rs_window']+1) for s in symbols):excluded[group]='INCOMPLETE_OR_SUSPENDED_MEMBER_'+str(max(21,params['rs_window']+1))+'_REAL_BARS_REQUIRED'
            else:strength[group]=sum(feature[s]['rs'] for s in symbols)/len(symbols)
        chosen=sorted((g for g,v in strength.items() if v>0),key=lambda g:(-strength[g],g))[:2]
        eligible=[s for s in members if members[s] in chosen and feature[s]['eligible'] and s not in holdings]
        ranking=sorted(eligible,key=lambda s:(chosen.index(members[s]),-(feature[s]['rs']-strength[members[s]]),s))
        if last_index-index<=40:ranking=[]
        waiting_buy=[{'symbol':s,'feature':deepcopy(feature[s])} for s in ranking]
        decisions.append({'session':day,'market_close_at':calendar['close_at'],'decision_at':calendar['decision_at'],'decision_clock_label':calendar['decision_clock_label'],'historical_visibility_proven':False,'next_session':dates[index+1] if index+1<len(dates) else None,'sector_sample_rs20':{s:str(v) for s,v in strength.items()},'selected_sectors':chosen,'sector_exclusions':excluded,'ranked_buy_symbols':ranking,'pending_sell_reasons':dict(waiting_sell)})
        features_trace.append({'session':day,'company':{s:{k:str(v) if isinstance(v,D) else v for k,v in value.items()} if value else None for s,value in feature.items()},'new_exit_reasons':fresh_reasons})
        exposure=sum(cents(marks[s]*quantity(s)) for s in holdings);rec=sum(x['amount'] for x in receivables.values())
        daily.append({'session':day,'cash_cents':cash,'exposure_cents':exposure,'receivable_cents':rec,'nav_cents':cash+exposure+rec,'positions':{s:quantity(s) for s in holdings}})
    return {'decisions':decisions,'fills':fills,'unfilled':unfilled,'daily':daily,'attempts':attempts,'features':features_trace,'enumerated_lots':evaluated_lots}


def compare_result(trace, original):
    differences=[];counts={}
    def compare(group,actual,expected):
        counts[group]=max(len(actual),len(expected))
        for index in range(max(len(actual),len(expected))):
            a=actual[index] if index<len(actual) else None;b=expected[index] if index<len(expected) else None
            if a!=b:differences.append({'group':group,'index':index,'independent':a,'preserved':b})
    compare('decisions',trace['decisions'],original['decisions'])
    fields=('session','symbol','side','quantity','execution_price','fees','cash_delta_cents','reason','planned_loss_cents')
    compare('fills',trace['fills'],[{k:v for k,v in row.items() if k in fields} for row in original['fills']])
    compare('unfilled',trace['unfilled'],original['unfilled'])
    compare('daily',trace['daily'],[{**{k:row[k] for k in ('session','cash_cents','exposure_cents','receivable_cents','nav_cents')},'positions':{p['symbol']:p['quantity'] for p in row['positions']}} for row in original['daily']])
    return {'passed':not differences,'compared':counts,'difference_count':len(differences),'differences':differences,'independent_attempts':len(trace['attempts']),'enumerated_lots':trace['enumerated_lots'],'unfilled_reason_counts':dict(Counter(row['reason'] for row in trace['unfilled']))}


BASELINE = {'rs_window':20,'exit_ma':20,'exit_min_age':0,'atr_multiple':'2.0'}

def validate_params(params):
    if set(params)!=set(BASELINE):raise ValueError('PARAMETER_KEYS')
    for key,values in [('rs_window',(10,20,40,60)),('exit_ma',(20,40,60)),('exit_min_age',(0,5,10))]:
        if type(params[key]) is not int or params[key] not in values:raise ValueError('PARAMETER_VALUE:'+key)
    if not isinstance(params['atr_multiple'],str) or D(params['atr_multiple']) not in (D('1.5'),D('2.0'),D('2.5')):raise ValueError('PARAMETER_VALUE:atr_multiple')
    return dict(params)

canon = digest

def quote(price,qty,side,policy):
    result=costs(price,qty,side,policy)
    return result['price'],result['fees'],result['delta']

def annual_rows(daily, fills, initial=10000000):
 out=[];opening=initial
 for year in sorted({r['session'][:4] for r in daily}):
  rows=[r for r in daily if r['session'].startswith(year)];peak=opening;mdd=D(0)
  for row in rows:
   peak=max(peak,row['nav_cents']);mdd=max(mdd,D(peak-row['nav_cents'])/peak)
  out.append(dict(year=year,first_session=rows[0]['session'],last_session=rows[-1]['session'],
   opening_nav_cents=opening,ending_nav_cents=rows[-1]['nav_cents'],
   net_return_fraction=str(D(rows[-1]['nav_cents']-opening)/opening),max_drawdown_fraction=str(mdd),
   filled_orders=sum(f['session'].startswith(year) for f in fills),
   fees_cents=sum(f['fees']['total_fee_cents'] for f in fills if f['session'].startswith(year))))
  opening=rows[-1]['nav_cents']
 return out


def audit_objects(case,result,params,yearly=None):
 with localcontext() as context:
  context.prec=80
  return _audit_objects(case,result,params,yearly)


def _audit_objects(case,result,params,yearly):
 if result.get('status') not in ('SIMULATED_TRADES','RUN_NO_TRADES'):
  return dict(kind='IndependentLongForwardArithmetic',run_id=case.get('run_id'),passed=False,
    status='NOT_FULLY_REVIEWABLE',failures=[{'check':'complete_run_required','actual':result.get('status')}],
    limits=['Failed partial run needs separate current-day review; no valid total performance asserted'])
 checks=defaultdict(int);failures=[]
 def eq(group,actual,expected,context):
  checks[group]+=1
  if actual!=expected:failures.append(dict(check=group,context=context,actual=str(actual),expected=str(expected)))
 def yes(group,value,context):eq(group,bool(value),True,context)
 eq('case_result_binding',result['input_hash'],canon(case),'input_hash')
 eq('result_content_hash',result['content_hash'],canon({k:v for k,v in result.items() if k!='content_hash'}),'result')
 yes('real_engine_called',result['engine_called'],'must have actual invocation')
 eq('history_mode',case.get('mode'),'HISTORY','case')
 for day in case['calendar']:
  eq('full_calendar_fee_coverage',sum(p['effective_from']<=day['date']<=p['effective_until'] for p in case['fee_schedule']),1,day['date'])
 dates=[x['date'] for x in case['calendar']];symbols={m['symbol']:m['sector'] for m in case['universe']};bars={(b['session'],b['symbol']):b for b in case['bars']}
 actions=case['actions'];by_day=defaultdict(list)
 for row in result['ledger']:by_day[row['session']].append(row)
 daily={x['session']:x for x in result['daily']};declarations={(x['id'],x['stage']):x for x in result['dividends']}
 decisions={x['session']:x for x in result['decisions']}
 cash=10000000;positions={};marks={};hist={s:[] for s in symbols};entitlements={};receivables={};peak=10000000;dd=D(0);fees_total=0;slip_total=0;complete=0;expected_fills=[];sequence=0;priorhash=canon({'initial_cash_cents':cash});lastnav=None
 def quantity(s):return sum(l['quantity'] for l in positions.get(s,[]))
 for idx,day in enumerate(dates):
  if day>case['window']['last_session']:break
  if result['status']=='ENGINE_FAILED' and day>result['last_completed_session']:break
  dayrows=by_day[day];used=set();sold=set();buy_seen=False
  # Actions are processed before all open fills. Historical comparison data are transformed only on ex-day.
  expected_actions=[]
  for a in actions:
   if a['ex_date']!=day:continue
   s=a['symbol'];cashper=D(a['cash_per_share']);ratio=D(a['split_ratio'])+D(a['bonus_ratio']);q=entitlements.get(a['id'],0);net=cents(D(q)*cashper*(1-D(a['tax_rate'])));extra=D(q)*(ratio-1)
   yes('integer_action_shares',extra==int(extra),a['id']);eq('record_ex_shares',quantity(s),q,a['id'])
   event=declarations.get((a['id'],'EX'),{})
   for k,v in [('record_quantity',q),('net_receivable_cents',net),('added_shares',int(extra))]:eq('action_entitlement',event.get(k),v,a['id']+':'+k)
   if extra:positions[s].append({'quantity':int(extra),'available_date':a['shares_available_date'],'origin':a['id']})
   if net:receivables[a['id']]={'net_cents':net,'pay_date':a['pay_date'],'symbol':s}
   if s in marks:marks[s]=(marks[s]-cashper)/ratio
   for h in hist[s]:
    for k in ('open','high','low','close'):h[k]=(h[k]-cashper)/ratio
   expected_actions.append(a['id'])
  expected_pays={aid:r['net_cents'] for aid,r in receivables.items() if r['pay_date']<=day}
  eq('action_ledger_set',[r['reference'] for r in dayrows if r['kind']=='ACTION_EX'],expected_actions,day)
  eq('payment_ledger_set',{r['reference']:r['cash_delta_cents'] for r in dayrows if r['kind']=='DIVIDEND_PAYMENT'},expected_pays,day)
  for row in dayrows:
   ctx=day+':'+str(sequence);eq('ledger_sequence',row['sequence'],sequence,ctx);sequence+=1
   eq('ledger_hash_chain',row['previous_hash'],priorhash,ctx);eq('ledger_content_hash',row['content_hash'],canon({k:v for k,v in row.items() if k!='content_hash'}),ctx);priorhash=row['content_hash']
   eq('cash_before',row['cash_before_cents'],cash,ctx);kind=row['kind']
   if kind=='ACTION_EX':delta=0;yes('event_before_fills',not buy_seen and not sold,ctx)
   elif kind=='DIVIDEND_PAYMENT':
    delta=expected_pays[row['reference']];eq('payment_event',declarations[(row['reference'],'PAY')]['net_cents'],delta,ctx);receivables.pop(row['reference']);yes('payment_before_fills',not buy_seen and not sold,ctx)
   else:
    yes('known_ledger_kind',kind in ('SIMULATED_BUY','SIMULATED_SELL'),ctx);s=row['symbol'];side=row['side'];q=row['quantity'];bar=bars[(day,s)]
    profiles=[p for p in case['fee_schedule'] if p['effective_from']<=day<=p['effective_until']];eq('dated_cost_profile_count',len(profiles),1,ctx);p=profiles[0]
    price,fee,delta=quote(bar['open'],q,side,p);eq('execution_price',D(row['execution_price']),price,ctx);eq('fees',row['fees'],fee,ctx)
    fees_total+=fee['total_fee_cents'];slip_total+=fee['slippage_cents'];expected_fills.append(row)
    yes('positive_integer_quantity',type(q) is int and q>0,ctx);eq('tradable_fill',bar['status'],'TRADABLE',ctx)
    yes('limit_and_daily_range',D(bar['lower_limit'])<min(price,D(bar['open'])) and max(price,D(bar['open']))<D(bar['upper_limit']) and D(bar['low'])<=price<=D(bar['high']),ctx)
    yes('actual_day_volume_cap',q<=int(D(bar['volume_shares'])*D('.01')),ctx)
    prior_decision=decisions.get(dates[idx-1],{})
    if side=='SELL':
     yes('sell_first',not buy_seen,ctx);sold.add(s);available=sum(l['quantity'] for l in positions.get(s,[]) if l['available_date']<=day)
     eq('t_plus_one_sell_available',q,available,ctx);yes('sell_prior_close_decision',s in prior_decision.get('pending_sell_reasons',{}),ctx)
     positions[s]=[l for l in positions[s] if l['available_date']>day]
     if not positions[s]:del positions[s];complete+=1
    else:
     buy_seen=True;yes('no_reentry_or_averaging',s not in positions and s not in sold,ctx);eq('buy_lot_multiple',q%bar['lot_size'],0,ctx)
     yes('prior_close_candidate',s in prior_decision.get('ranked_buy_symbols',[]),ctx)
     exposed={ps:cents(marks[ps].quantize(D('.000000000001'),rounding=ROUND_HALF_EVEN)*quantity(ps)) for ps in positions};invested=sum(exposed.values());sectorvalue=sum(v for ps,v in exposed.items() if symbols[ps]==symbols[s]);nav=cash+invested+sum(r['net_cents'] for r in receivables.values())
     yes('position_count_cap',len(positions)<3,ctx);yes('single_open_cap',fee['notional_cents']<=int(D(nav)*D('.2')),ctx);yes('total_open_cap',invested+fee['notional_cents']<=int(D(nav)*D('.6')),ctx);yes('sector_open_cap',sectorvalue+fee['notional_cents']<=int(D(nav)*D('.4')),ctx)
     yes('passive_single_cap',all(v<=int(D(nav)*D('.2')) for v in exposed.values()),ctx)
     sectorvalues={sec:sum(v for ps,v in exposed.items() if symbols[ps]==sec) for sec in set(symbols.values())};yes('passive_sector_cap',all(v<=int(D(nav)*D('.4')) for v in sectorvalues.values()),ctx)
     h=hist[s];yes('atr_history',len(h)>=21,ctx);atr=(sum(max(r['high']-r['low'],abs(r['high']-old['close']),abs(r['low']-old['close'])) for old,r in zip(h[-21:-1],h[-20:]))/20).quantize(D('.000000000001'),rounding=ROUND_CEILING)
     stop=(price-D(params['atr_multiple'])*atr).quantize(D('.01'),rounding=ROUND_HALF_EVEN);_,_,exit_delta=quote(stop,q,'SELL',p);risk=-delta-exit_delta
     eq('planned_stop_loss',row['planned_loss_cents'],risk,ctx);yes('one_percent_risk_cap',risk<=int(D(nav)*D('.01')),ctx);yes('previous_volume_cap',q<=int(median(x['volume_shares'] for x in h[-20:])*D('.01')/bar['lot_size'])*bar['lot_size'],ctx)
     positions[s]=[{'quantity':q,'available_date':dates[idx+1],'origin':'BUY'}];marks[s]=price
   eq('cash_delta',row['cash_delta_cents'],delta,ctx);cash+=delta;eq('cash_after',row['cash_after_cents'],cash,ctx);yes('no_negative_cash',cash>=0,ctx)
  for s in symbols:
   bar=bars[(day,s)]
   if bar['status']=='TRADABLE':hist[s].append({k:D(bar[k]) for k in ('open','high','low','close','volume_shares')});marks[s]=D(bar['close'])
  for a in actions:
   if a['record_date']==day:
    entitlements[a['id']]=quantity(a['symbol']);eq('record_event',declarations[(a['id'],'RECORD')]['quantity'],entitlements[a['id']],a['id'])
  if day<case['window']['first_session']:continue
  actual=daily[day];eq('daily_symbols',set(p['symbol'] for p in actual['positions']),set(positions),day)
  exposure=sum(cents(marks[s]*quantity(s)) for s in positions);rec=sum(r['net_cents'] for r in receivables.values());nav=cash+exposure+rec;lastnav=nav;peak=max(peak,nav);dd=max(dd,D(peak-nav)/peak)
  for key,value in [('cash_cents',cash),('exposure_cents',exposure),('receivable_cents',rec),('nav_cents',nav),('held_quantity',sum(quantity(s) for s in positions)),('available_quantity',sum(l['quantity'] for ls in positions.values() for l in ls if l['available_date']<=day))]:eq('daily_'+key,actual[key],value,day)
  for p in actual['positions']:
   s=p['symbol'];eq('daily_position_lots',p['lots'],positions[s],day+':'+s);eq('daily_position_quantity',p['quantity'],quantity(s),day+':'+s);eq('daily_mark',D(p['mark']['price']),marks[s],day+':'+s);eq('daily_position_value',p['market_value_cents'],cents(marks[s]*quantity(s)),day+':'+s)
 eq('ledger_coverage',sequence,len(result['ledger']),'all rows')
 eq('daily_coverage',list(daily),[d for d in dates if case['window']['first_session']<=d<=case['window']['last_session']],'target dates')
 eq('declaration_uniqueness',len(declarations),len(result['dividends']),'all actions')
 eq('all_fills_from_ledger',result['fills'],expected_fills,'fills');eq('final_cash',result['final_cash_cents'],cash,'final');eq('final_receivables',result['receivables'],receivables,'final')
 eq('complete_trades',result['complete_trades'],complete,'final');eq('total_fees',result['total_fee_cents'],fees_total,'final');eq('total_slippage',result['total_slippage_cents'],slip_total,'final');eq('maximum_drawdown',D(result['maximum_drawdown']),dd,'final');eq('net_return',D(result['net_return']),D(lastnav)/10000000-1,'final')
 eq('final_position_symbols',set(result['positions']),set(positions),'final')
 for s in positions:eq('final_position_lots',result['positions'][s]['lots'],positions[s],s)
 annual=annual_rows(result['daily'],result['fills'])
 if yearly is not None:
  eq('yearly_row_count',len(yearly),len(annual),'years')
  for actual,expected in zip(yearly,annual):
   for key in ('year','first_session','last_session','filled_orders','fees_cents'):
    eq('yearly_'+key,actual.get(key),expected[key],expected['year'])
   for key in ('net_return_fraction','max_drawdown_fraction'):
    # Public display may use default 28-digit context, independent arithmetic uses 80.
    yes('yearly_'+key,actual.get(key) is not None and abs(D(actual[key])-D(expected[key]))<=D('1e-26'),expected['year'])
 return {'kind':'IndependentLongForwardArithmetic','yearly_recomputed':annual,'run_id':case['run_id'],'status':result['status'],'checked_fills':len(expected_fills),'checked_ledger_rows':sequence,'checked_daily_rows':len(daily),'checks':dict(checks),'assertions':sum(checks.values()),'failures':failures,'passed':not failures,'recomputed':{'final_cash_cents':cash,'last_nav_cents':lastnav,'maximum_drawdown':str(dd),'total_fee_cents':fees_total,'total_slippage_cents':slip_total,'complete_trades':complete},'limits':['No engine/quote imports or calls','No authentication/network','Does not certify reconstructed source/PIT/license or investment validity','Partial-engine failure requires separate current-day inspection']}


def audit(case, result, params):
    """Reconstruct decisions before comparing outcomes; never imports production code.

    Accounting is a second independently derived ledger check. Neither audit
    certifies data provenance, original PIT or investment effectiveness.
    """
    params=validate_params(params)
    if case.get('parameters',params)!=params:raise ValueError('CASE_PARAMETERS_MISMATCH')
    trace=reconstruct(case,params)
    decisions=compare_result(trace,result)
    arithmetic=audit_objects(case,result,params)
    failures=decisions['differences']+arithmetic['failures']
    return dict(kind='IndependentParamOptReview',run_id=case.get('run_id'),parameters=params,
                passed=not failures,failures=failures,counts=decisions['compared'],
                arithmetic_counts=arithmetic.get('checks',{}),arithmetic_assertions=arithmetic.get('assertions',0),
                independent_attempts=decisions['independent_attempts'],enumerated_lots=trace['enumerated_lots'],
                unfilled_reason_counts=decisions['unfilled_reason_counts'],
                recomputed=arithmetic.get('recomputed'),
                reviewer_sha256='sha256:'+sha256(Path(__file__).read_bytes()).hexdigest(),
                case_hash=digest(case),result_hash=digest(result),
                limits=['Standard library only; no production engine/cost function imports',
                        'Independent ascending lot enumeration; explicit decision and refusal reconstruction',
                        'Reconstructed input/PIT/provider status is not independently certified',
                        'No investment effectiveness or statistical superiority claim'])
