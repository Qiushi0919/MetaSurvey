"""Independent read-only Case/EngineResult reconciliation. No project imports or engine calls.
Usage: python -m tools.long_forward.independent RUN_DIRECTORY OUTPUT_JSON
This is arithmetic/execution-accounting review, not signal-selection or data certification.
"""
import json, sys, hashlib
from pathlib import Path
from decimal import Decimal as D, ROUND_HALF_EVEN, ROUND_CEILING, getcontext, localcontext
from collections import defaultdict
from statistics import median


def cents(v):return int((D(v)*100).quantize(D(1),rounding=ROUND_HALF_EVEN))
def canon(v):return 'sha256:'+hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def rawhash(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def quote(price,qty,side,p):
 raw=D(price); execution=(raw*(1+(1 if side=='BUY' else -1)*D(p['slippage_bps'])/10000)).quantize(D('.01'),rounding=ROUND_HALF_EVEN)
 n=cents(execution*qty);rn=cents(raw*qty);unfloored=int((D(n)*D(p['commission_rate'])).quantize(D(1),rounding=ROUND_HALF_EVEN));commission=max(unfloored,p['minimum_commission_cents'])
 exchange=0 if p['exchange_included'] else int((D(n)*D(p['exchange_rate'])).quantize(D(1),rounding=ROUND_HALF_EVEN))
 other=0 if p['other_included'] else int((D(n)*D(p['other_buy_rate'] if side=='BUY' else p['other_sell_rate'])).quantize(D(1),rounding=ROUND_HALF_EVEN))
 tax=int((D(n)*D(p['sell_tax_rate'])).quantize(D(1),rounding=ROUND_HALF_EVEN)) if side=='SELL' else 0
 fees=dict(notional_cents=n,raw_notional_cents=rn,commission_cents=commission,minimum_commission_uplift_cents=commission-unfloored,exchange_cents=exchange,other_cents=other,sell_tax_cents=tax,total_fee_cents=commission+exchange+other+tax,slippage_cents=abs(n-rn))
 return execution,fees,(-n-fees['total_fee_cents'] if side=='BUY' else n-fees['total_fee_cents'])

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


def audit_objects(case,result,yearly=None):
 with localcontext() as context:
  context.prec=80
  return _audit_objects(case,result,yearly)


def _audit_objects(case,result,yearly):
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
     stop=(price-2*atr).quantize(D('.01'),rounding=ROUND_HALF_EVEN);_,_,exit_delta=quote(stop,q,'SELL',p);risk=-delta-exit_delta
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
 return {'kind':'IndependentLongForwardArithmetic','yearly_recomputed':annual,'run_id':case['run_id'],'status':result['status'],'checked_fills':len(expected_fills),'checked_ledger_rows':sequence,'checked_daily_rows':len(daily),'checks':dict(checks),'assertions':sum(checks.values()),'failures':failures,'passed':not failures,'recomputed':{'final_cash_cents':cash,'last_nav_cents':lastnav,'maximum_drawdown':str(dd),'total_fee_cents':fees_total,'total_slippage_cents':slip_total,'complete_trades':complete},'limits':['No engine/quote imports or calls','No authentication/network','Signal ranking and missed opportunity completeness not independently recomputed','Does not certify reconstructed source/PIT/license or investment validity','Partial-engine failure requires separate current-day inspection']}

def audit(directory):
 directory=Path(directory);cp=directory/'Case.json';rp=directory/'EngineResult.json';yp=directory/'Yearly.json'
 case=json.loads(cp.read_text());result=json.loads(rp.read_text())
 data=audit_objects(case,result,json.loads(yp.read_text()) if yp.is_file() else None)
 data.update(case_file_hash=rawhash(cp),result_file_hash=rawhash(rp),reviewer_code_hash=rawhash(Path(__file__)))
 return data


if __name__=='__main__':
 directory=Path(sys.argv[1]).resolve();output=Path(sys.argv[2]);data=audit(directory)
 with output.open('x') as f:json.dump(data,f,ensure_ascii=False,indent=2);f.write('\n')
 print(json.dumps({k:data.get(k) for k in ('run_id','passed','checked_fills','checked_ledger_rows','checked_daily_rows','assertions')},ensure_ascii=False))
 if not data['passed']:sys.exit(1)
