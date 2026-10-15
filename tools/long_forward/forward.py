"""Pure, real-clock forward planning and settlement. No scheduler, I/O or network.

Caller persists each returned state/plan immutably and binds its hash in trusted
storage. Self hashes detect accidental changes, not malicious replacements of
an entire archive. Real cases require the root's case-bound provenance verifier.
"""
from copy import deepcopy
from decimal import Decimal, localcontext
from experiments.long_forward_v1 import engine as e

D=Decimal
VERSION='LONG_FORWARD_STATE_V1'

def _sealed(value):
    value=e._plain(value);value.pop('content_hash',None);value['content_hash']=e.digest(value);return value

def _check(value,label):
    if type(value) is not dict or value.get('content_hash')!=e.digest({k:v for k,v in value.items() if k!='content_hash'}):
        raise ValueError(label+'_HASH_MISMATCH')

def _restore(value):
    state=deepcopy(value)
    state['max_dd']=D(state['max_dd'])
    for rows in state['history'].values():
        for row in rows:
            for k in row:row[k]=D(row[k])
    for mark in state['marks'].values():mark['price']=D(mark['price'])
    for position in state['positions'].values():
        for k in ('stop_price','entry_compare_price'):position[k]=D(position[k])
    return state

def _new(case,protocol):
    return {'version':VERSION,'namespace':case['namespace'],'strategy_id':case['strategy_id'],
        'protocol_hash':e.digest(protocol),'sequence':0,'parent_hash':None,'last_consumed_session':None,
        'input_pins':{},'action_pins':{},'calendar_pins':{},'evidence_pins':{},'calendar_dates':[], 'active_plan':None,'settled':{},'events':[],
        'runtime':{'cash_cents':10000000,'positions':{},'receivables':{},'entitlements':{},
            'pending_sells':{},'pending_buys':[],'history':{s:[] for s in protocol['members']},
            'marks':{},'consecutive':{s:0 for s in protocol['members']},'peak_cents':10000000,'max_dd':'0'},
        'result':{'ledger':[],'fills':[],'unfilled':[],'decisions':[],'daily':[],'dividends':[],
            'errors':[],'complete_trades':0}}

def _inputs(case,now,protocol,verifier):
    now_at=e.instant(now)
    if case.get('mode')!='FORWARD_A':raise ValueError('FORWARD_MODE_REQUIRED')
    if case['evidence_grade'] not in (e.SYNTHETIC,'CURRENT_OBSERVED_FORWARD'):raise ValueError('FORWARD_OBSERVATION_GRADE_REQUIRED')
    if e.instant(case['run_at'])>now_at:raise ValueError('CASE_RUN_IN_FUTURE')
    dates,members,bars,receipt=e._validate(case,verifier,protocol)
    for proof in case['evidence'].values():
        if e.instant(proof['retrieved_at'])>now_at or e.instant(proof['available_at'])>now_at:raise ValueError('FORWARD_FUTURE_EVIDENCE')
    for meta in case['calendar']:
        if e.instant(meta['close_at'])>now_at:raise ValueError('UNFINISHED_SESSION_INPUT')
    # Calendar can name future sessions; no future quote is accepted.
    execution=case['execution_calendar']
    if not execution:raise ValueError('EXECUTION_CALENDAR_REQUIRED')
    if [d['date'] for d in execution]!=sorted(set(d['date'] for d in execution)):raise ValueError('EXECUTION_CALENDAR_ORDER')
    for meta in execution:
        e._proof(case,meta['evidence_ref'])
        if not e.instant(meta['open_at'])<e.instant(meta['close_at']):raise ValueError('EXECUTION_CALENDAR_CLOCK')
    union={m['date']:m for m in case['calendar']}
    for meta in execution:
        if meta['date'] in union:
            if any(meta[k]!=union[meta['date']][k] for k in ('open_at','close_at')):raise ValueError('EXECUTION_CALENDAR_CONFLICT')
        else:union[meta['date']]=meta
    all_dates=sorted(union)
    if any(day>dates[-1] and e.instant(meta['close_at'])<=now_at for day,meta in union.items()):
        raise ValueError('STALE_FORWARD_COMPLETED_SESSION')
    for day in dates:
        for symbol in members:
            if (day,symbol) not in bars:raise ValueError('FORWARD_COMPLETE_DAILY_GRID_REQUIRED')
            e._bar(case,bars[day,symbol])
    return dates,members,bars,union,all_dates,receipt

def _state(current,case,protocol,bars,dates):
    if current is None:return _new(case,protocol)
    _check(current,'STATE');state=deepcopy(current)
    for k in ('namespace','strategy_id'):
        if state[k]!=case[k]:raise ValueError('STATE_IDENTITY_MISMATCH')
    if state['protocol_hash']!=e.digest(protocol):raise ValueError('STATE_PROTOCOL_MISMATCH')
    if dates[:len(state['calendar_dates'])]!=state['calendar_dates']:raise ValueError('CONSUMED_CALENDAR_CHANGED')
    for key,h in state['input_pins'].items():
        day,symbol=key.split('|',1)
        if (day,symbol) not in bars or e.digest(bars[day,symbol])!=h:raise ValueError('CONSUMED_BAR_CHANGED')
    meta_by_day={m['date']:m for m in case['calendar']}
    for day,h in state['calendar_pins'].items():
        if day not in meta_by_day or e.digest(meta_by_day[day])!=h:raise ValueError('CONSUMED_CALENDAR_METADATA_CHANGED')
    for ref,h in state['evidence_pins'].items():
        if ref not in case['evidence'] or e.digest(case['evidence'][ref])!=h:raise ValueError('CONSUMED_EVIDENCE_CHANGED')
    known={a['id']:a for a in case['actions']}
    for key,h in state['action_pins'].items():
        if key not in known or e.digest(known[key])!=h:raise ValueError('KNOWN_ACTION_CHANGED')
    for a in case['actions']:
        if a['id'] not in state['action_pins'] and state['last_consumed_session'] and a['record_date']<=state['last_consumed_session']:
            raise ValueError('LATE_ACTION_CANNOT_BACKFILL_ENTITLEMENT')
    return state

def _consume(state,case,dates,members,bars,through,execute,all_dates,mark_only=False):
    start=len(state['calendar_dates']);end=dates.index(through)
    if end<start:return
    runtime=_restore(state['runtime'])
    # Extend only calendar metadata for T+1; no future bars are processed.
    local=deepcopy(case)
    lookup={m['date']:m for m in case['calendar']+case['execution_calendar']}
    local['calendar']=[lookup[d] for d in all_dates]
    if not execute and not mark_only:
        # Warmup/missed sessions do not acquire retroactive portfolio marks.
        local['window']['first_session']='9999-12-31'
    e._run(local,all_dates,members,bars,runtime,state['result'],start_index=start,stop_index=end,
        execute=execute,make_decisions=False,history_tail=False)
    state['runtime']=e._plain(runtime);state['last_consumed_session']=through;state['calendar_dates']=dates[:end+1]
    for (d,s),bar in bars.items():
        if d<=through:state['input_pins'][d+'|'+s]=e.digest(bar)
    state['action_pins'].update({a['id']:e.digest(a) for a in case['actions']})
    state['calendar_pins'].update({m['date']:e.digest(m) for m in case['calendar'] if m['date']<=through})
    refs={bar['evidence_ref'] for (d,s),bar in bars.items() if d<=through}
    refs.update(m['evidence_ref'] for m in case['calendar'] if m['date']<=through)
    refs.update(a['evidence_ref'] for a in case['actions'])
    refs.update(m['selection_evidence_ref'] for m in case['universe'])
    state['evidence_pins'].update({ref:e.digest(case['evidence'][ref]) for ref in refs})

def prepare(case,current_state,now,protocol,provenance_verifier=None):
    with localcontext() as ctx:
        ctx.prec=80
        return _prepare(case,current_state,now,protocol,provenance_verifier)

def _prepare(case,current,now,protocol,verifier):
    dates,members,bars,calendar,all_dates,receipt=_inputs(case,now,protocol,verifier)
    state=_state(current,case,protocol,bars,dates)
    if state['active_plan'] is not None:
        return {'status':'FIRST_PLAN_WINS','plan':deepcopy(state['active_plan']),'state':deepcopy(current)}
    day=dates[-1];bootstrap=current is None
    if not bootstrap and state['last_consumed_session']!=day:raise ValueError('SETTLEMENT_REQUIRED_BEFORE_NEW_PLAN')
    next_days=[d for d in all_dates if d>day]
    if not next_days:raise ValueError('NEXT_EXECUTION_CALENDAR_MISSING')
    intended=next_days[0]
    if bootstrap:
        eligible=[d for d in next_days if e.instant(calendar[d]['open_at'])>e.instant(now)]
        if not eligible:raise ValueError('NO_FUTURE_EXECUTION_SESSION')
        execution=eligible[0]
        if execution!=intended and protocol['forward'].get('bootstrap_delayed_entry') is not True:raise ValueError('BOOTSTRAP_DELAY_NOT_AUTHORIZED')
    else:
        execution=intended
        if e.instant(now)>=e.instant(calendar[execution]['open_at']):
            return {'status':'MISSED','reason':'PLAN_NOT_FROZEN_BEFORE_NEXT_OPEN','plan':None,'state':deepcopy(current)}
    if all_dates.index(execution)+1>=len(all_dates):raise ValueError('T_PLUS_ONE_CALENDAR_MISSING')
    if e.instant(now)<e.instant(protocol['frozen_at']):raise ValueError('PLAN_BEFORE_PROTOCOL_FREEZE')
    if bootstrap:_consume(state,case,dates,members,bars,day,False,all_dates)
    runtime=_restore(state['runtime']);meta=deepcopy(calendar[day]);meta.update(decision_at=now,decision_clock_label='ACTUAL_FORWARD_FREEZE_TIME')
    e._decide(case,all_dates,all_dates.index(day),meta,{s:bars[day,s] for s in members},members,runtime,state['result'],False)
    decision=state['result']['decisions'][-1];decision['next_session']=execution
    plan=_sealed({'kind':'FORWARD_FROZEN_PLAN_V1','namespace':case['namespace'],'strategy_id':case['strategy_id'],
        'run_id':case['run_id'],'protocol_hash':e.digest(protocol),'case_hash':e.digest(case),
        'prior_state_hash':current['content_hash'] if current else None,'source_session':day,
        'frozen_at':now,'execution_session':execution,'execution_open_at':calendar[execution]['open_at'],
        'decision':deepcopy(decision),'pending_buys':e._plain(runtime['pending_buys']),
        'pending_sells':deepcopy(runtime['pending_sells']),'bootstrap':bootstrap,
        'bootstrap_skipped_sessions':[d for d in next_days if d<execution],
        'sizing':'FROZEN_V2_RISK_CASH_LOT_RULES_AT_ACTUAL_NEXT_OPEN',
        'provenance_receipt':receipt})
    state['runtime']=e._plain(runtime);state['active_plan']=plan;state['sequence']+=1
    state['parent_hash']=current['content_hash'] if current else None
    state['events'].append({'kind':'BOOTSTRAP_DELAYED_ENTRY' if execution!=intended else 'PLAN_FROZEN',
        'at':now,'plan_hash':plan['content_hash'],'execution_session':execution})
    return {'status':'PLAN_FROZEN','plan':plan,'state':_sealed(state)}

def settle(case,current_state,frozen_plan,now,protocol,provenance_verifier=None):
    with localcontext() as ctx:
        ctx.prec=80
        return _settle(case,current_state,frozen_plan,now,protocol,provenance_verifier)

def _settle(case,current,plan,now,protocol,verifier):
    if current is None:return {'status':'MISSED','reason':'NO_PREEXISTING_FROZEN_PLAN','state':None}
    if plan is None:return _missed_mark(case,current,now,protocol,verifier)
    _check(current,'STATE');_check(plan,'PLAN')
    if plan['content_hash'] in current['settled']:
        previous=current['settled'][plan['content_hash']]
        if previous['settlement_case_hash']!=e.digest(case):raise ValueError('SETTLED_CASE_CHANGED')
        return {'status':'ALREADY_SETTLED','receipt':deepcopy(previous),'state':deepcopy(current)}
    if current['active_plan']!=plan:raise ValueError('PLAN_NOT_BOUND_TO_CURRENT_STATE')
    dates,members,bars,calendar,all_dates,receipt=_inputs(case,now,protocol,verifier)
    state=_state(current,case,protocol,bars,dates);day=plan['execution_session']
    if day!=dates[-1]:raise ValueError('SETTLEMENT_MUST_USE_EXACT_EXECUTION_SESSION')
    if e.instant(plan['frozen_at'])>=e.instant(calendar[day]['open_at']):raise ValueError('LATE_OR_BACKFILLED_PLAN')
    if e.instant(now)<e.instant(calendar[day]['close_at']):raise ValueError('SETTLEMENT_BEFORE_CLOSE')
    if plan['execution_open_at']!=calendar[day]['open_at']:raise ValueError('EXECUTION_OPEN_CHANGED')
    if plan['protocol_hash']!=e.digest(protocol):raise ValueError('PLAN_PROTOCOL_MISMATCH')
    new_dates=dates[len(state['calendar_dates']):]
    if not new_dates or new_dates[-1]!=day:raise ValueError('SETTLEMENT_SESSION_ALREADY_CONSUMED')
    skipped=new_dates[:-1]
    if skipped!=plan['bootstrap_skipped_sessions']:raise ValueError('UNPLANNED_SESSION_GAP')
    before=len(state['result']['fills'])
    try:
        if skipped:
            if state['runtime']['positions'] or state['result']['fills']:raise ValueError('BOOTSTRAP_SKIP_WITH_EXPOSURE')
            _consume(state,case,dates,members,bars,skipped[-1],False,all_dates)
        _consume(state,case,dates,members,bars,day,True,all_dates)
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        # One session is an atomic transition. Keep original cash, plan and
        # hash chain for retry; no partially applied day escapes as settled.
        return {'status':'SETTLEMENT_BLOCKED','reason':str(exc),'failed_session':day,
                'failed_at':now,'state':deepcopy(current),'plan':deepcopy(plan)}
    state['result']['daily'][-1].update(observation_status='FROZEN_PLAN_SETTLED',decision_executed=True)
    receipt_out={'kind':'FORWARD_SETTLEMENT_RECEIPT_V1','session':day,'settled_at':now,'plan_hash':plan['content_hash'],
        'settlement_case_hash':e.digest(case),'fills_added':len(state['result']['fills'])-before,
        'provenance_receipt':receipt,'status':'SETTLED'}
    state['settled'][plan['content_hash']]=receipt_out;state['active_plan']=None;state['sequence']+=1
    state['parent_hash']=current['content_hash'];state['events'].append(receipt_out)
    return {'status':'SETTLED','receipt':receipt_out,'state':_sealed(state)}


def _missed_mark(case,current,now,protocol,verifier):
    _check(current,'STATE')
    if current['active_plan'] is not None:raise ValueError('ACTIVE_PLAN_REQUIRES_EXPLICIT_EXPIRED_PLAN_ARCHIVE')
    dates,members,bars,calendar,all_dates,receipt=_inputs(case,now,protocol,verifier)
    state=_state(current,case,protocol,bars,dates);day=dates[-1]
    if state['last_consumed_session']==day:
        previous=next((x for x in reversed(state['events']) if x.get('kind')=='MISSED_NO_PLAN_MARK_ONLY' and x.get('session')==day),None)
        if previous and previous['case_hash']==e.digest(case):
            return {'status':'ALREADY_MARKED_MISSED','receipt':previous,'state':deepcopy(current)}
        raise ValueError('MISSED_SESSION_ALREADY_CONSUMED')
    # No old order is executed, including an outstanding sell. The risk remains
    # present and will be considered by the next genuine prepare call.
    state['runtime']['pending_buys']=[]
    before_daily=len(state['result']['daily']);before_fills=len(state['result']['fills'])
    try:
        _consume(state,case,dates,members,bars,day,False,all_dates,mark_only=True)
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        return {'status':'SETTLEMENT_BLOCKED','reason':str(exc),'failed_session':day,
                'failed_at':now,'state':deepcopy(current),'plan':None}
    if len(state['result']['fills'])!=before_fills:raise ValueError('MARK_ONLY_UNEXPECTED_FILL')
    for row in state['result']['daily'][before_daily:]:
        row.update(observation_status='MISSED_NO_PLAN_MARK_ONLY',decision_executed=False,recorded_at=now,
                   historical_bookkeeping_only=True)
    receipt={'kind':'MISSED_NO_PLAN_MARK_ONLY','session':day,'marked_at':now,'case_hash':e.digest(case),
        'missing_sessions':[r['session'] for r in state['result']['daily'][before_daily:]],
        'fills_added':0,'successful_forward_days_added':0,'provenance_receipt':receipt}
    state['sequence']+=1;state['parent_hash']=current['content_hash'];state['events'].append(receipt)
    return {'status':'MISSED_NO_PLAN_MARK_ONLY','receipt':receipt,'state':_sealed(state)}
