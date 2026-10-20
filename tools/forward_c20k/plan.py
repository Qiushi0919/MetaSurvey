"""Actual close-data preparation; never consumes optimization outcomes."""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal as D, localcontext, ROUND_CEILING, ROUND_HALF_EVEN
from zoneinfo import ZoneInfo
from statistics import median
from pathlib import Path
from tools.long_forward import builder
from experiments.param_opt_v1 import engine
from experiments.param_opt_v1.sizing import build_portfolio
from .store import ARCHIVE, ROOT, config, read, now, save, filehash, digest, event

OLD_ARCHIVE=ROOT.parent/'.p1b-archives/long-forward-20261015'

def protected_buy_price(close):
    # One fen price for both fee-inclusive sizing and the submitted limit.
    # The previous adapter rounded only the latter, causing sizing to reject
    # e.g. 12.10 * 1.02 = 12.342 before any plan could be frozen.
    return (D(close)*D('1.02')).quantize(D('.01'),rounding=ROUND_HALF_EVEN)

def latest_capture(day):
    matches=[]
    for folder in OLD_ARCHIVE.glob('capture-*'):
        p=folder/'Manifest.json'
        if p.is_file() and not p.is_symlink():
            m=read(p)
            if m.get('scope',{}).get('end_date')==day.replace('-','') and m.get('priority')=='forward':
                matches.append((m.get('retrieved_at',''),folder))
    return max(matches,default=(None,None))[1]

def prepare(account, session):
    """A successful plan must be independently rebuildable from sealed capture.

    Reuse the strict existing raw adapter; its factor/action disagreements remain
    blocking. That is an input validator, not inheritance of A cash or plans.
    """
    original_account=account;account=deepcopy(account)
    cfg=config();at=now()
    folder=ARCHIVE/'plans'/at.replace(':','').replace('+','_');folder.mkdir(parents=True)
    receipt={'kind':'ForwardC20kPlanAttempt','account_id':cfg['account_id'],'at':at,
             'input_session':session,'state':'BLOCKED','engine_called':False,
             'orders':[],'config_hash':filehash(ROOT/'experiments/account20k_v1/Config.json')}
    try:
        local=datetime.fromisoformat(at).astimezone(ZoneInfo('Asia/Shanghai'))
        if local.date().isoformat()!=session or (local.hour,local.minute)<(18,30):
            raise ValueError('WAIT_ACTUAL_1830_COMPLETED_SESSION')
        capture=latest_capture(session)
        if capture is None: raise ValueError('WAIT_SHARED_FORWARD_A_CAPTURE_NO_DUPLICATE_FETCH')
        manifest=capture/'Manifest.json';receipt.update(capture=str(capture),capture_hash=filehash(manifest))
        prior=None
        if account.get('consumed_input'):
            ref=account['consumed_input'];p=Path(ref['path'])
            if not p.is_relative_to(ARCHIVE/'plans') or p.resolve()!=p or filehash(p)!=ref['hash']:
                raise ValueError('PREVIOUS_INPUT_HASH')
            prior=read(p)
        from .input import build_case
        report,case=build_case(capture,'C20K-'+local.strftime('%Y%m%dT%H%M%S'),at,folder,prior=prior)
        save(folder/'BuildReport.json',report)
        receipt['input_errors']=report.get('errors',[])
        if case is None: raise ValueError('STRICT_CURRENT_INPUT_BUILD_BLOCKED')
        # No inherited P&L or retrospective strategy decisions.
        dates=[x['date'] for x in case['calendar']]
        if not dates or dates[-1]!=session: raise ValueError('STALE_CLOSE_INPUT')
        from .account import reconcile_close
        reconcile_close(account,case,session)
        case=deepcopy(case);case['parameters']=cfg['parameters']
        save(folder/'Case.json',case)
        account['consumed_input']={'path':str(folder/'Case.json'),'hash':filehash(folder/'Case.json')}
        # Close reconciliation is an independent atomic stage. A later plan
        # failure must not erase today's already reconciled real virtual ledger.
        original_account.clear();original_account.update(deepcopy(account))
        receipt['close_reconciled']=True
        future=[x for x in case['execution_calendar'] if x['date']>session]
        if not future: raise ValueError('NEXT_SESSION_CALENDAR_MISSING')
        execution=future[0]['date'];receipt['execution_session']=execution
        if datetime.fromisoformat(at)>=datetime.fromisoformat(execution+'T09:30:00+08:00'):
            raise ValueError('MISSED_PLAN_FREEZE')
        members=cfg['members']
        if {x['symbol']:x['sector'] for x in case['universe']}!=members:
            raise ValueError('NINE_MEMBER_BINDING')
        state={'cash_cents':2000000,'positions':{},'receivables':{},'entitlements':{},
               'pending_sells':{},'pending_buys':[],'history':{s:[] for s in members},
               'marks':{},'consecutive':{s:0 for s in members},'peak_cents':2000000,'max_dd':D(0)}
        result={k:[] for k in ('decisions','ledger','daily','dividends','fills','unfilled')}
        bars={(x['session'],x['symbol']):x for x in case['bars']}
        with localcontext() as ctx:
            ctx.prec=80
            engine._run(case,dates,members,bars,state,result,execute=False,make_decisions=False)
            state['cash_cents']=account['cash_cents']
            for symbol,p in account['positions'].items():
                state['positions'][symbol]=dict(p,entry_index=dates.index(p['entry_session']),
                    stop_price=D(p['stop_price']),entry_compare_price=D(p['entry_compare_price']))
            engine._decide(case,dates,len(dates)-1,case['calendar'][-1],
                           {s:bars[session,s] for s in members},members,state,result,history_tail=False)
        # Reuse dated cost profile shape; commission includes both regulatory
        # fees, unlike some older historical profiles.
        schedule=deepcopy(case['fee_schedule'])
        for fee in schedule:
            fee.update(commission_rate='0.00025',minimum_commission_cents=500,
                       slippage_bps='10',exchange_included=True,other_included=False)
        candidates=[]
        for p in state['pending_buys']:
            b=bars[session,p['symbol']]
            candidates.append(dict(p,price=str(protected_buy_price(b['close'])),lot_size=b['lot_size']))
        held=[dict(symbol=s,sector=p['sector'],quantity=sum(l['quantity'] for l in p['lots']),
                   mark_price=bars[session,s]['close'] or p['mark_price']) for s,p in account['positions'].items()]
        allocated=build_portfolio(candidates,account['available_cash_cents'],held,account['nav_cents'],schedule,execution,'2.5')
        save(folder/'Decision.json',engine._plain(result['decisions'][-1]))
        orders=[]
        for symbol,reason in state['pending_sells'].items():
            p=account['positions'][symbol];qty=sum(l['quantity'] for l in p['lots']);close=D(p['mark_price'])
            orders.append(dict(order_id=f'{execution}-{symbol}-SELL',symbol=symbol,sector=members[symbol],
                               side='SELL',quantity=qty,remaining_quantity=qty,lot_size=1,
                               limit_price=str((close*D('.98')).quantize(D('.01'))),reason=reason,
                               session=execution,expires_at=execution+'T14:50:00+08:00',
                               filled_notional_cents=0,reserve_cents=0,state='PLANNED'))
        for i,p in enumerate(allocated['plans']):
            symbol=p['symbol'];close=D(bars[session,symbol]['close'])
            orders.append(dict(order_id=f'{execution}-{symbol}-BUY-{i}',symbol=symbol,sector=members[symbol],
                               side='BUY',quantity=p['quantity'],remaining_quantity=p['quantity'],
                               lot_size=p['lot_size'],atr20=p['atr20'],limit_price=str(protected_buy_price(close)),
                               planned_loss_cents=p['planned_loss_cents'],session=execution,
                               expires_at=execution+'T14:50:00+08:00',filled_notional_cents=0,
                               reserve_cents=-p['entry']['cash_delta_cents'],state='PLANNED'))
        receipt.update(state='FROZEN',engine_called=True,orders=orders,rejections=allocated['rejections'],
                       frozen_at=now(),decision=result['decisions'][-1],
                       case_hash=digest(case),next_calendar_hash=digest(future[0]),
                       known_actions=case['actions'],
                       history_performance_used=False)
        account['consumed_input']={'path':str(folder/'Case.json'),'hash':filehash(folder/'Case.json')}
        original_account.clear();original_account.update(account)
    except Exception as exc:
        receipt['reason']=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
    receipt['content_hash']=digest(receipt);save(folder/'Plan.json',receipt)
    event('PLAN_ATTEMPT',state=receipt['state'],reason=receipt.get('reason'),
          plan_hash=receipt['content_hash'],path=str(folder/'Plan.json'))
    return receipt
