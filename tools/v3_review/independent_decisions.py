"""Independent frozen-V3 decision reconstruction. Standard library only.

Input is a preserved Case, never original decisions/fills. Original outputs are
read only by compare_result after the independently generated trace exists.
This verifier is not a new strategy run or a data/PIT/license admission service.
"""
from collections import Counter
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


def indicators(history):
    if len(history)<21:return None
    window=history[-21:];last=window[-1];mean=sum(x['close'] for x in window[1:])/20
    ranges=[max(window[i]['high']-window[i]['low'],abs(window[i]['high']-window[i-1]['close']),abs(window[i]['low']-window[i-1]['close'])) for i in range(1,21)]
    atr=sum(ranges)/20;relative=last['close']/window[0]['close']-1
    breakout=last['close']>max(x['high'] for x in window[:-1])
    pullback=last['low']<=mean<last['close'] and last['close']>window[-2]['close']
    return {'sma':mean,'atr':atr,'rs':relative,'eligible':atr>0 and (breakout or pullback),
            'breakout':breakout,'pullback':pullback,'median_volume':median(x['volume_shares'] for x in window[1:])}


def executable(row, quote, quantity):
    if row['status']=='SUSPENDED':return 'SUSPENDED'
    price=quote['price'];opened=D(row['open'])
    if min(opened,price)<=D(row['lower_limit']) or max(opened,price)>=D(row['upper_limit']):return 'LIMIT_OR_SLIPPAGE_BOUND'
    if not D(row['low'])<=price<=D(row['high']):return 'SLIPPAGE_OUTSIDE_DAILY_RANGE'
    if quantity>int(D(row['volume_shares'])*D('.01')):return 'ACTUAL_SESSION_VOLUME_CAP'
    return None


def allocate(symbol, sector, bar, feature, positions, marks, cash, receivables, policy):
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
        stop=(entry['price']-2*atr).quantize(D('.01'),rounding=ROUND_HALF_EVEN)
        if stop<=0:continue
        exit_quote=costs(stop,qty,'SELL',policy);loss=-entry['delta']-exit_quote['delta']
        if -entry['delta']<=cash and entry['fees']['notional_cents']<=budget and loss<=int(D(nav)*D('.01')):
            selected={'quantity':qty,'entry':entry,'stop':stop,'loss':loss,'atr':atr,'nav_cents':nav,'budget_cents':budget}
    return selected,None if selected else 'RISK_CASH_LOT_OR_VOLUME_UNAFFORDABLE',evaluated


def reconstruct(case):
    """Reconstruct only the pre-existing declared V3 strategy; never reads EngineResult."""
    with localcontext() as context:
        context.prec=80
        return _reconstruct(case)


def _reconstruct(case):
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
                    plan,reason,lot_count=allocate(s,members[s],bar,candidate['feature'],holdings,marks,cash,receivables,policy);evaluated_lots+=lot_count
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
        feature={s:indicators(history[s]) for s in members}
        fresh_reasons={}
        for s,pos in holdings.items():
            age=index-pos['entry_index']+1;reason='MAXIMUM_40_EXCHANGE_SESSIONS' if age>=40 else None
            if current[s]['status']=='TRADABLE':
                close=D(current[s]['close'])
                if close<=pos['stop']:reason='CLOSE_STOP_2_ATR20'
                elif feature[s] and close<feature[s]['sma']:reason='CLOSE_LOGIC_INVALIDATION_SMA20'
                elif age>=20 and close<=pos['entry_compare']:reason='DAY20_NONPOSITIVE_ADJUSTED_PRICE_RETURN'
            if reason:
                fresh_reasons[s]=reason
                if s not in waiting_sell:waiting_sell[s]=reason
        excluded={};strength={}
        for group,symbols in groups.items():
            if any(feature[s] is None or current[s]['status']!='TRADABLE' or streak[s]<21 for s in symbols):excluded[group]='INCOMPLETE_OR_SUSPENDED_MEMBER_21_REAL_BARS_REQUIRED'
            else:strength[group]=sum(feature[s]['rs'] for s in symbols)/len(symbols)
        chosen=sorted((g for g,v in strength.items() if v>0),key=lambda g:(-strength[g],g))[:2]
        eligible=[s for s in members if members[s] in chosen and feature[s]['eligible'] and s not in holdings]
        ranking=sorted(eligible,key=lambda s:(chosen.index(members[s]),-(feature[s]['rs']-strength[members[s]]),s))
        if last_index-index<=40:ranking=[]
        waiting_buy=[{'symbol':s,'feature':deepcopy(feature[s])} for s in ranking]
        decisions.append({'session':day,'market_close_at':calendar['close_at'],'decision_at':calendar['decision_at'],'decision_clock_label':'SIMULATED_POST_CLOSE_DECISION_TIME','historical_visibility_proven':False,'next_session':dates[index+1] if index+1<len(dates) else None,'sector_sample_rs20':{s:str(v) for s,v in strength.items()},'selected_sectors':chosen,'sector_exclusions':excluded,'ranked_buy_symbols':ranking,'pending_sell_reasons':dict(waiting_sell)})
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


def main():
    parser=argparse.ArgumentParser();parser.add_argument('run_directory',type=Path);parser.add_argument('output_directory',type=Path);args=parser.parse_args()
    if args.output_directory.exists():raise ValueError('NEW_OUTPUT_DIRECTORY_REQUIRED')
    case_path=args.run_directory/'Case.json';result_path=args.run_directory/'EngineResult.json';run_path=args.run_directory/'Run.json'
    case=json.loads(case_path.read_text());run=json.loads(run_path.read_text())
    for field,p in [('case_hash',case_path),('engine_result_hash',result_path)]:
        if run[field]!='sha256:'+sha256(p.read_bytes()).hexdigest():raise ValueError('PRESERVED_RUN_FILE_HASH_MISMATCH:'+field)
    if run.get('status')!='SIMULATED_TRADES' or run.get('engine_called') is not True:raise ValueError('SUCCESSFUL_PRESERVED_RUN_REQUIRED')
    trace=reconstruct(case)
    # Read outcomes only after reconstruction; there is no outcome feedback path.
    result=json.loads(result_path.read_text());review=compare_result(trace,result)
    review.update(run_id=case['run_id'],scope='INDEPENDENT_RECONSTRUCTION_NOT_NEW_STRATEGY_OR_PIT_PROOF',case_hash=run['case_hash'],engine_result_hash=run['engine_result_hash'],reviewer_source_hash='sha256:'+sha256(Path(__file__).read_bytes()).hexdigest())
    args.output_directory.mkdir(parents=True)
    for name,obj in [('Trace.json',trace),('Review.json',review)]:
        with (args.output_directory/name).open('x') as handle:json.dump(obj,handle,ensure_ascii=False,indent=2);handle.write('\n')
    print(json.dumps({k:v for k,v in review.items() if k!='differences'},ensure_ascii=False))
    return not review['passed']

if __name__=='__main__':raise SystemExit(main())
