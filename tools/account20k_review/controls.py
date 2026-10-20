"""Independent 20k buy/hold accounting, ascending lot enumeration; no strategy engine."""
from decimal import Decimal as D,localcontext
from datetime import datetime,timezone
from pathlib import Path
import json
from tools.account20k_history import run
from tools.account20k_history.independent import cents,costs

def audit(case,control):
    with localcontext() as ctx:
        ctx.prec=80
        cash=2000000;peak=cash;dd=D(0);fees=0;slip=0;paid=0;count=0;fail=[];marks={};qty={m['symbol']:0 for m in case['universe']};rights={};recv={};ledger=[];fills=[];refused=[];fractions=[]
        dates=[x['date'] for x in case['calendar'] if case['window']['first_session']<=x['date']<=case['window']['last_session']];bars={(x['session'],x['symbol']):x for x in case['bars']};actual={x['session']:x for x in control['nav_series']};slot=int(D(2000000)*(1 if control['id'].endswith('100') else D('.6'))/9)
        def eq(label,a,b):
            nonlocal count
            count+=1
            if a!=b:fail.append(dict(check=label,actual=str(a),expected=str(b)))
        def post(day,kind,sym,delta,**extra):
            nonlocal cash
            before=cash;cash+=delta;ledger.append(dict(session=day,kind=kind,symbol=sym,cash_before_cents=before,cash_delta_cents=delta,cash_after_cents=cash,**extra))
        for day in dates:
            for a in case['actions']:
                if a['ex_date']!=day:continue
                s=a['symbol'];q=rights.get(a['id'],0);ratio=D(a['split_ratio'])+D(a['bonus_ratio']);added=D(q)*(ratio-1);eq('whole_bonus_shares',added,int(added));eq('record_ex_shares',q,qty[s]);qty[s]+=int(added)
                if s in marks:marks[s]=(marks[s]-D(a['cash_per_share']))/ratio
                net=cents(D(q)*D(a['cash_per_share'])*(1-D(a['tax_rate'])))
                if net:recv[a['id']]=(net,a['pay_date'],s)
                post(day,'ACTION_EX',s,0,action_id=a['id'],added_shares=int(added))
            for aid,(value,pay,s) in list(recv.items()):
                if pay<=day:post(day,'DIVIDEND_PAYMENT',s,value,action_id=aid);paid+=value;del recv[aid]
            if day==dates[0]:
                profile=next(x for x in case['fee_schedule'] if x['effective_from']<=day<=x['effective_until'])
                for s in sorted(qty):
                    b=bars[day,s];reason=None;chosen=None
                    if b['status']=='SUSPENDED':reason='SUSPENDED'
                    else:
                        lot=b['lot_size'];maximum=min(int(D(slot)/100/D(b['open']))//lot*lot,int(D(b['volume_shares'])*D('.01'))//lot*lot)
                        for q in range(lot,maximum+1,lot):
                            v=costs(b['open'],q,'BUY',profile)
                            if -v['delta']<=min(slot,cash):chosen=(q,v)
                        if chosen is None:reason='SLOT_CASH_LOT_OR_VOLUME_UNAFFORDABLE'
                        else:
                            q,v=chosen;price=v['price']
                            if min(price,D(b['open']))<=D(b['lower_limit']) or max(price,D(b['open']))>=D(b['upper_limit']):reason='LIMIT_OR_SLIPPAGE_BOUND'
                            elif not D(b['low'])<=price<=D(b['high']):reason='SLIPPAGE_OUTSIDE_DAILY_RANGE'
                    if reason:refused.append(dict(session=day,symbol=s,reason=reason,slot_budget_cents=slot));continue
                    q,v=chosen;qty[s]+=q;fees+=v['fees']['total_fee_cents'];slip+=v['fees']['slippage_cents'];post(day,'BUY',s,v['delta']);fills.append(dict(session=day,symbol=s,execution_price=str(v['price']),quantity=q,notional_cents=v['fees']['notional_cents'],fees_cents=v['fees']['total_fee_cents'],slippage_cents=v['fees']['slippage_cents'],cash_delta_cents=v['delta']))
            for s in qty:
                if bars[day,s]['status']=='TRADABLE':marks[s]=D(bars[day,s]['close'])
            for a in case['actions']:
                if a['record_date']==day:rights[a['id']]=qty[a['symbol']]
            exposure=sum(cents(marks[s]*q) for s,q in qty.items() if q);receivable=sum(x[0] for x in recv.values());nav=cash+exposure+receivable;peak=max(peak,nav);dd=max(dd,D(peak-nav)/peak);fractions.append(D(exposure)/nav)
            for k,v in [('nav_cents',nav),('cash_cents',cash),('exposure_cents',exposure),('receivable_cents',receivable)]:eq(day+':'+k,actual[day][k],v)
        for k,v in [('trades',fills),('rejections',refused),('ledger',ledger),('fees_cents',fees),('slippage_cents',slip),('dividend_cents',paid),('terminal_cash_cents',cash),('terminal_receivable_cents',sum(x[0] for x in recv.values()))]:eq(k,control[k],v)
        eq('daily_count',len(actual),len(dates));eq('net_return',D(control['net_return']),D(nav)/2000000-1);eq('mdd',D(control['max_drawdown']),dd);eq('average_exposure',D(control['average_exposure_fraction']),sum(fractions)/len(fractions));eq('terminal_quantities',{p['symbol']:p['quantity'] for p in control['terminal_positions']},{s:q for s,q in qty.items() if q})
        return dict(control=control['id'],partition=control['partition'],bps=control['bps'],passed=not fail,assertions=count,failures=fail,days=len(dates),fills=len(fills),rejections=len(refused))

def main():
    base,_=run.source();reg=run.registration();cfg=next(c for c in reg['configs'] if c['id']=='P029');report=[]
    for row in run.read(run.ARCHIVE/'Results.json')['controls']:
        c,p=run.derive(base,cfg,row['partition'],row['bps'],datetime.now(timezone.utc).isoformat());report.append(audit(c,row))
    out=dict(kind='Independent20kHoldControlReview',at=datetime.now(timezone.utc).isoformat(),passed=all(x['passed'] for x in report),controls=len(report),assertions=sum(x['assertions'] for x in report),reports=report,scope='Independent ascendinglot purchases, fill/nonfill, datedfees, corporateactions, ledger anddailycash/exposure/NAV; terminal holdings areunrealized, noforcedsales')
    path=run.ARCHIVE.parent/'forward-c20k-20261020/review/Hold-Controls-Independent.json'
    with path.open('x') as f:json.dump(out,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in out.items() if k!='reports'}));print([x for x in report if not x['passed']][:1])
if __name__=='__main__':main()
