"""Frozen local virtual process. Actual source clocks; no retrospective fills."""
from copy import deepcopy
from datetime import datetime,timedelta
from decimal import Decimal as D
from zoneinfo import ZoneInfo
from pathlib import Path
import argparse, fcntl, json, os, time
from .store import *
from .gateway import capture
from .plan import prepare
from .account import apply_fill,reserve,open_actions,mark_current
from experiments.account20k_v1.matching import match

TZ=ZoneInfo('Asia/Shanghai')
def local():return datetime.now(TZ)
def atomic(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2));tmp.chmod(0o600);os.replace(tmp,path)
def heartbeat(status,**extra):
    atomic(ARCHIVE/'Heartbeat.json',dict(at=now(),pid=os.getpid(),status=status,**extra))
def calendar(day):
    path=ARCHIVE/'Calendar.json'
    if path.exists():
        v=read(path)
        if day in v['days'] and all(filehash(Path(p))==h for p,h in v['pins'].items()):
            return v
    tables={};pins={}
    for exchange in ('SSE','SZSE'):
        receipt,rows=capture('trade_cal',dict(exchange=exchange,start_date=day.replace('-',''),
            end_date=(datetime.fromisoformat(day)+timedelta(days=14)).strftime('%Y%m%d')))
        if receipt['state']!='SUCCESS':raise ValueError('CALENDAR_UNAVAILABLE')
        table={}
        for row in rows:
            date=datetime.strptime(row['cal_date'],'%Y%m%d').date().isoformat()
            if date in table or str(row.get('is_open')) not in ('0','1') or row['exchange']!=exchange:
                raise ValueError('CALENDAR_SCHEMA')
            table[date]=str(row['is_open'])=='1'
        tables[exchange]=table;p=Path(receipt['path'])/'Response.json';pins[str(p)]=filehash(p)
    if tables['SSE']!=tables['SZSE'] or len(tables['SSE'])!=15:raise ValueError('CALENDAR_INCOMPLETE')
    v=dict(days=tables['SSE'],pins=pins,retrieved_at=now());atomic(path,v);return v
def normalize(row,receipt):
    source=row.get('trade_time')
    if source:
        source=datetime.strptime(source,'%Y-%m-%d %H:%M:%S').replace(tzinfo=TZ).isoformat()
    q=dict(symbol=row.get('ts_code'),source_at=source,received_at=receipt['received_at'],
           last=row.get('close'),volume=row.get('vol'),volume_unit='SHARES',
           evidence_hash=receipt['response_hash'],status='UNKNOWN',state_evidence_verified=False,
           limits_evidence_verified=False)
    if type(q['volume']) is not int:raise ValueError('INTEGER_SHARE_VOLUME_REQUIRED')
    for side,provider in (('ask','ask'),('bid','bid')):
        q[side+'_price']=row.get(provider+'_price1')
        q[side+'_quantity']=row.get(provider+'_volume1')
    return q
def restrictions(symbol,day):
    # Only on an actual planned order, no blanket universe rescan.
    receipts=[];tables={}
    for api in ('stk_limit','suspend_d'):
        receipt,rows=capture(api,dict(ts_code=symbol,start_date=day.replace('-',''),end_date=day.replace('-','')))
        if receipt['state'] not in ('SUCCESS','EMPTY_RESPONSE'):raise ValueError('EXECUTION_STATE_UNAVAILABLE')
        receipts.append(receipt);tables[api]=rows
    limits=[r for r in tables['stk_limit'] if r.get('ts_code')==symbol and r.get('trade_date')==day.replace('-','')]
    if len(limits)!=1:raise ValueError('TODAY_LIMITS_MISSING')
    if tables['suspend_d']:raise ValueError('SUSPENSION_REQUIRES_VERIFIED_RESUMPTION')
    return dict(status='TRADABLE',state_evidence_verified=True,limits_evidence_verified=True,
        up_limit=limits[0]['up_limit'],down_limit=limits[0]['down_limit'],
        restriction_evidence=[r['response_hash'] for r in receipts])
def expire(account,day):
    changed=False
    for o in account['orders'].values():
        if o['state'] in ('SUBMITTED','PARTIALLY_FILLED') and now()>=datetime.fromisoformat(o['expires_at']).astimezone(ZoneInfo('UTC')).isoformat():
            o['state']='EXPIRED';o['reserve_cents']=0;o['expiry_reason']='UNFILLED_BY_REGISTERED_DEADLINE';changed=True
    reserve(account);return changed
def activate(account,cal,day):
    plan=account.get('plan')
    if not plan or plan['state']!='FROZEN' or plan['execution_session']!=day:return False
    if datetime.fromisoformat(plan['frozen_at'])>=datetime.fromisoformat(day+'T09:30:00+08:00'):
        raise ValueError('PLAN_NOT_FROZEN_BEFORE_OPEN')
    future=sorted(d for d,opened in cal['days'].items() if opened and d>day)
    if not future:raise ValueError('NEXT_T1_CALENDAR_MISSING')
    # Starting late is observable. Do not submit a morning plan after the
    # registered first execution window has already passed.
    hm=(local().hour,local().minute)
    if hm>=(14,50):return False
    open_actions(account,plan.get('known_actions',[]),day)
    for o in plan['orders']:
        if o['order_id'] in account['orders']:continue
        account['orders'][o['order_id']]=dict(o,state='SUBMITTED',submitted_at=now(),next_session=future[0],
            plan_hash=plan['content_hash'],consumed_snapshots=[])
    reserve(account)
    account.setdefault('observations',{}).setdefault(day,dict(plan_hash=plan['content_hash'],first_at=now(),cycles=0,errors=[],symbols=[]))
    return True
def eod(account,day,cal):
    expire(account,day)
    old_observation=account.get('observations',{}).get(day)
    receipt=prepare(account,day)
    if receipt['state']=='FROZEN':
        account['plan']=receipt;account['state']='PLAN_FROZEN_WAITING_EXECUTION'
    else: account['state']='PLAN_BLOCKED';account['latest_plan_attempt']=receipt
    if receipt.get('close_reconciled') is True:
        if old_observation and day not in [r['session'] for r in account['settlements']]:
            # Empty plans are valid only when actual monitoring occurred. With
            # orders, stale/missing execution evidence cannot count as success.
            times=[datetime.fromisoformat(t).astimezone(TZ) for t in old_observation.get('cycle_times',[])]
            morning=[t for t in times if t.hour<12];afternoon=[t for t in times if t.hour>=13]
            gaps=[(b-a).total_seconds() for part in (morning,afternoon) for a,b in zip(part,part[1:])]
            ok=(bool(morning and afternoon) and morning[0].strftime('%H:%M')<='09:40'
                and morning[-1].strftime('%H:%M')>='11:20'
                and afternoon[0].strftime('%H:%M')<='13:10'
                and afternoon[-1].strftime('%H:%M')>='14:40'
                and max(gaps,default=0)<=660 and not old_observation['errors']
                and set(old_observation['symbols'])==set(config()['members']))
            status='SETTLED' if ok else 'BLOCKED_OBSERVATION_GAP'
            settlement=dict(session=day,status=status,at=now(),plan_hash=old_observation['plan_hash'],
                cash_cents=account['cash_cents'],positions=deepcopy(account['positions']),
                nav_cents=account['nav_cents'],fills=[f for f in account['fills'] if account['orders'][f['order_id']]['session']==day])
            account['settlements'].append(settlement)
            if ok:account['effective_observation_days']+=1
            save(ARCHIVE/('Settlement-'+day+'.json'),settlement)
    account=checkpoint(account,'EOD_PLAN_ATTEMPT')
    heartbeat(account['state'],plan_state=receipt['state'],reason=receipt.get('reason'))
    return account
def once():
    verify_freeze()
    started=now();day=local().date().isoformat();hm=(local().hour,local().minute)
    if day>=config()['source_expiry']:
        event('SOURCE_EXPIRED',started_at=started);heartbeat('SOURCE_EXPIRED');return
    lock=ARCHIVE/'runtime.lock'
    with lock.open('a') as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:heartbeat('OTHER_INSTANCE_RUNNING');return
        heartbeat('TRIGGERED',started_at=started)
        account=state();cal=calendar(day)
        if not cal['days'].get(day):
            event('NON_TRADING_SESSION',started_at=started,session=day);heartbeat('NON_TRADING_SESSION');return
        if (18,30)<=hm<(21,30):
            if (account.get('plan') or {}).get('input_session')==day and account['plan']['state']=='FROZEN':
                heartbeat('EOD_ALREADY_FROZEN');return
            eod(account,day,cal);return
        if not ((9,35)<=hm<(11,30) or (13,0)<=hm<(14,50)):
            if expire(account,day):checkpoint(account,'ORDERS_EXPIRED')
            heartbeat('OUTSIDE_EXECUTION_WINDOW');return
        activated=activate(account,cal,day)
        active=[o for o in account['orders'].values() if o['state'] in ('SUBMITTED','PARTIALLY_FILLED')]
        # A single-symbol endpoint is actually entitled; batching is not.
        sell_symbols={o['symbol'] for o in active if o['side']=='SELL'}
        buy_symbols={o['symbol'] for o in active if o['side']=='BUY'}
        symbols=sorted(config()['members'],key=lambda s:(0 if s in sell_symbols else 1 if s in buy_symbols else 2,s))
        quotes=account.setdefault('quotes',{})
        errors=[];seen=[]
        for symbol in symbols:
            verify_freeze()
            if not ((9,35)<=(local().hour,local().minute)<(11,30) or (13,0)<=(local().hour,local().minute)<(14,50)):break
            heartbeat('COLLECTING',symbol=symbol,cycle_started_at=started,plan_active=activated)
            try:
                orders=[o for o in account['orders'].values() if o['symbol']==symbol and o['state'] in ('SUBMITTED','PARTIALLY_FILLED')]
                restriction=restrictions(symbol,day) if orders else {}
                receipt,rows=capture('rt_k',dict(ts_code=symbol))
                if receipt['state']!='SUCCESS' or len(rows)!=1 or rows[0].get('ts_code')!=symbol:
                    raise ValueError('RT_SINGLE_QUOTE_UNAVAILABLE')
                quote=normalize(rows[0],receipt);quote.update(restriction)
                quotes=account['quotes'];previous=quotes.get(symbol);quotes[symbol]=quote;seen.append(symbol)
                if not quote['source_at'] or not 0<=(datetime.fromisoformat(now())-datetime.fromisoformat(quote['source_at'])).total_seconds()<=90:
                    raise ValueError('STALE_OR_MISSING_SOURCE_CLOCK')
                if symbol in account['positions']:
                    account['positions'][symbol]['mark_price']=str(quote['last'])
                for o in orders:
                    if previous is None:continue
                    own_reserve=o['reserve_cents'] if o['side']=='BUY' else 0
                    sellable=sum(l['quantity'] for l in account['positions'].get(symbol,{}).get('lots',[]) if l['available_date']<=day)
                    result=match(o,previous,quote,now(),account['available_cash_cents']+own_reserve,sellable)
                    event('ORDER_OBSERVATION',order_id=o['order_id'],quote_hash=digest(quote),result=result)
                    if result['state']=='SIMULATED_FILL':
                        candidate=deepcopy(account);apply_fill(candidate,o['order_id'],result,digest(quote));account=candidate
                mark_current(account,day);account=checkpoint(account,'REAL_QUOTE_OBSERVED')
            except Exception as exc:
                reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                errors.append(dict(symbol=symbol,reason=reason));event('QUOTE_OR_MATCH_BLOCKED',symbol=symbol,reason=reason)
        if activated:
            observation=account['observations'][day];observation['cycles']+=1
            observation.setdefault('cycle_times',[]).append(started)
            observation['errors'].extend(errors);observation['symbols']=sorted(set(observation['symbols'])|set(seen))
            account['state']='MONITORING_VALID_PLAN' if not errors else 'MONITORING_WITH_DATA_BLOCKS'
        else:account['state']='COLLECTING_REAL_QUOTES_NO_VALID_PLAN'
        checkpoint(account,'INTRADAY_CYCLE')
        receipt=event('INTRADAY_TRIGGER_RECEIPT',started_at=started,finished_at=now(),session=day,
            symbols_received=seen,errors=errors,valid_plan=activated,account_state=account['state'],
            filled_orders=len(account['fills']),cash_cents=account['cash_cents'],effective_observation_days=account['effective_observation_days'])
        heartbeat(account['state'],last_receipt=receipt)
def main():
    p=argparse.ArgumentParser();p.add_argument('--serve',action='store_true');p.add_argument('--once',action='store_true');args=p.parse_args()
    os.umask(0o077)
    while True:
        start=time.monotonic()
        try:once()
        except Exception as exc:
            reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
            event('RUNTIME_BLOCKED',reason=reason);heartbeat('BLOCKED',reason=reason)
        if not args.serve:break
        # launchd restarts exits; no catch-up trades on wake. Missing heartbeat
        # >10 minutes is displayed as OFFLINE, never as a healthy active task.
        end=start+300
        while time.monotonic()<end:
            if (ARCHIVE/'STOP').exists():heartbeat('STOPPED');return
            time.sleep(min(10,max(0,end-time.monotonic())))
if __name__=='__main__':main()
