"""Independent Long/Forward V1 successor of sealed V2; never production.

Public API run_diagnostic(case, provenance_verifier=None, protocol=None). The root builder owns
source admission. Real runs additionally require a callable verifier returning a
case-bound receipt, not a boolean supplied inside the case. No network, secrets,
broker, mutation, or optimization. V1 sizing/cost pure functions are reused.

Case: namespace,strategy_id,run_id,evidence_grade,protocol_ref,method_ref,run_at,
calendar[{date,open_at,close_at,decision_at,decision_clock_label,evidence_ref}],
calendar_coverage{start,end,days[{date,is_open,evidence_ref}]}, universe[{symbol,
sector,selection_evidence_ref}],window{first_session,last_session},fee_schedule,
evidence{ref:{source,source_version,raw_sha256,published_at,available_at,
retrieved_at,visibility_assumption}},bars[{session,symbol,status,price_kind,open,
high,low,close,volume_shares,lower_limit,upper_limit,lot_size,evidence_ref}],
actions[{id,symbol,record_date,ex_date,pay_date,shares_available_date,
cash_per_share,bonus_ratio,split_ratio,tax_rate,evidence_ref}]. Action monetary
inputs and ratios are exact decimal strings. pay_date may be null only if no
cash; shares_available_date may be null only if no additional shares. Genuine
due dates may be outside the window or non-exchange days; cash is recognized at
the first later exchange-session processing point, never fabricated as settled. NONE means actions=[] only when the
root's admitted source receipt establishes complete action coverage.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, localcontext, ROUND_HALF_EVEN, ROUND_CEILING
from hashlib import sha256
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo
import json
import re

from experiments.e2e_pilot_v1.execution import (
    build_portfolio, quote, fee_for, cents, digest, exact, instant, RULES as V1_RULES,
)

D = Decimal
HERE = Path(__file__).resolve().parent
GRADE = 'RECONSTRUCTED_HISTORY_DIAGNOSTIC'
SYNTHETIC = 'SYNTHETIC_ENGINE_TEST'
CLOCK_LABEL = 'SIMULATED_POST_CLOSE_DECISION_TIME'
HASH = re.compile(r'sha256:[0-9a-f]{64}')
RULES = {**V1_RULES,
         'corporate_actions':'CAUSAL_GROSS_PRICE_ADJUSTMENT_NET20_TAX_RECEIVABLE_INTEGER_SHARES',
         'decision_clock':'SIMULATED_1800_POST_CLOSE_NOT_HISTORICAL_PIT',
         'suspension':'NULL_OHLC_ZERO_VOLUME_STALE_MARK_21_CONSECUTIVE_TRADABLE_BARS',
         'decimal_internal_precision':80,'v1_sizing_bridge_decimal_places':12,
         'v1_sizing_atr_rounding':'ROUND_CEILING','v1_sizing_mark_rounding':'ROUND_HALF_EVEN'}


def _hash(raw): return 'sha256:' + sha256(raw).hexdigest()


def _proof(case, ref):
    proof = case['evidence'][ref]
    if 'published_at' not in proof:raise ValueError('EXPLICIT_PUBLICATION_OR_NULL_REQUIRED')
    if not all(proof.get(k) for k in ('source','source_version','raw_sha256','available_at','retrieved_at','visibility_assumption')):
        raise ValueError('SOURCE_CLOCK_OR_VISIBILITY_ASSUMPTION_MISSING:' + str(ref))
    if not HASH.fullmatch(proof['raw_sha256']): raise ValueError('SOURCE_HASH_INVALID')
    if instant(proof['available_at']) > instant(proof['retrieved_at']): raise ValueError('SOURCE_CLOCK_ORDER')
    if instant(proof['retrieved_at']) > instant(case['run_at']): raise ValueError('FUTURE_RETRIEVAL')
    if proof.get('published_at') is not None and instant(proof['published_at']) > instant(proof['available_at']):
        raise ValueError('PUBLICATION_AFTER_AVAILABLE')
    return proof


def _scope(case, protocol):
    if not isinstance(protocol,dict):raise ValueError('EXPLICIT_FROZEN_PROTOCOL_REQUIRED')
    if case.get('protocol_ref') != digest(protocol):raise ValueError('FROZEN_PROTOCOL_HASH_MISMATCH')
    if case.get('method_ref') != protocol['method_ref']:raise ValueError('FROZEN_METHOD_HASH_MISMATCH')
    if case['namespace'] != protocol['namespace'] or case['strategy_id'] != protocol['strategy_id']:
        raise ValueError('STRATEGY_NAMESPACE_MISMATCH')
    if case.get('mode') not in ('HISTORY','FORWARD_A'):raise ValueError('EXPLICIT_MODE_REQUIRED')
    expected_grade=GRADE if case['mode']=='HISTORY' else 'CURRENT_OBSERVED_FORWARD'
    if case['evidence_grade'] not in (expected_grade,SYNTHETIC):raise ValueError('MODE_EVIDENCE_GRADE_MISMATCH')
    if case['fee_schedule'] != protocol['fee_schedule']:raise ValueError('FROZEN_COST_POLICY_MISMATCH')
    if instant(case['run_at']) < instant(protocol['frozen_at']):raise ValueError('RUN_BEFORE_FREEZE')
    if protocol.get('rules_hash') != digest(RULES):raise ValueError('PROTOCOL_RULES_HASH_MISMATCH')
    if case['evidence_grade']==SYNTHETIC and protocol.get('synthetic_only') is not True:
        raise ValueError('SYNTHETIC_CANNOT_USE_REAL_PROTOCOL')
    if case['evidence_grade']!=SYNTHETIC and protocol.get('synthetic_only') is True:
        raise ValueError('REAL_CANNOT_USE_SYNTHETIC_PROTOCOL')
    target=protocol['target_window'] if case['mode']=='HISTORY' else case['forward_scope']
    if case['mode']=='FORWARD_A':
        if target['warmup_start']!=protocol['forward']['warmup_start'] or target['start']!=protocol['forward']['first_decision_session']:
            raise ValueError('FORWARD_FIXED_START_MISMATCH')
    return {'target_window':target,'members':protocol['members']}


def _validate(case, provenance_verifier, protocol):
    if any(not isinstance(case.get(k),str) or not case[k] for k in ('run_id','strategy_id','namespace')):raise ValueError('RUN_IDENTITY_REQUIRED')
    if case['evidence_grade'] not in (GRADE,SYNTHETIC,'CURRENT_OBSERVED_FORWARD'): raise ValueError('EVIDENCE_GRADE_UNSUPPORTED')
    if case.get('rules') != RULES or case.get('rules_hash') != digest(RULES):raise ValueError('FROZEN_RULES_MISMATCH')
    scope = _scope(case, protocol)
    target = scope['target_window']
    universe = case['universe']
    members = {m['symbol']: m['sector'] for m in universe}
    if members != scope['members'] or len(members) != len(universe): raise ValueError('FROZEN_UNIVERSE_MISMATCH')
    for m in universe: _proof(case,m['selection_evidence_ref'])
    coverage = case['calendar_coverage']
    if coverage['start'] != target['warmup_start'] or coverage['end'] != target['end']:
        raise ValueError('CALENDAR_COVERAGE_TRUNCATED')
    start,end = date.fromisoformat(coverage['start']),date.fromisoformat(coverage['end'])
    expected = [(start+timedelta(days=n)).isoformat() for n in range((end-start).days+1)]
    if [d['date'] for d in coverage['days']] != expected: raise ValueError('CIVIL_CALENDAR_INCOMPLETE')
    for day in coverage['days']:
        if type(day['is_open']) is not bool: raise ValueError('CALENDAR_OPEN_STATUS_UNKNOWN')
        _proof(case,day['evidence_ref'])
    dates = [d['date'] for d in case['calendar']]
    if dates != [d['date'] for d in coverage['days'] if d['is_open']]: raise ValueError('EXCHANGE_CALENDAR_MISMATCH')
    active = [d for d in dates if target['start'] <= d <= target['end']]
    if not active or case['window'] != {'first_session':active[0],'last_session':active[-1]}:
        raise ValueError('PREREGISTERED_WINDOW_TRUNCATED')
    if dates.index(active[0]) < 20: raise ValueError('WARMUP_INCOMPLETE')
    for i,day in enumerate(case['calendar']):
        opened,closed,decision = (instant(day[k]) for k in ('open_at','close_at','decision_at'))
        if not opened < closed < decision: raise ValueError('DECISION_MUST_FOLLOW_CLOSE')
        if case['mode']=='HISTORY' and day['decision_clock_label'] != CLOCK_LABEL: raise ValueError('SIMULATED_DECISION_CLOCK_LABEL_REQUIRED')
        local = decision.astimezone(ZoneInfo('Asia/Shanghai'))
        if case['mode']=='HISTORY' and (local.date().isoformat() != day['date'] or (local.hour,local.minute,local.second) != (18,0,0)):
            raise ValueError('FROZEN_1800_DECISION_TIME_REQUIRED')
        if i+1 < len(dates) and decision >= instant(case['calendar'][i+1]['open_at']):
            raise ValueError('DECISION_NOT_BEFORE_NEXT_OPEN')
        _proof(case,day['evidence_ref'])
        quote('1.00',100,'BUY',day['date'],fee_for(case['fee_schedule'],day['date']))
    bars = {}
    for row in case['bars']:
        key=(row['session'],row['symbol'])
        if key in bars: raise ValueError('DUPLICATE_BAR')
        if row['session'] not in dates or row['symbol'] not in members: raise ValueError('OUT_OF_SCOPE_BAR')
        bars[key]=row
    action_calendar=dates
    if case['mode']=='FORWARD_A':action_calendar=sorted(set(dates+[m['date'] for m in case['execution_calendar']]))
    seen=set(); action_dates=set()
    action_fields={'id','symbol','record_date','ex_date','pay_date','shares_available_date','cash_per_share','bonus_ratio','split_ratio','tax_rate','evidence_ref'}
    for a in case['actions']:
        if set(a)!=action_fields:raise ValueError('ACTION_CLOSED_SHAPE_OR_COMPLEX_EVENT_UNSUPPORTED')
        if a['id'] in seen: raise ValueError('DUPLICATE_ACTION')
        seen.add(a['id'])
        if a['symbol'] not in members: raise ValueError('OUT_OF_SCOPE_ACTION')
        if (a['symbol'],a['ex_date']) in action_dates: raise ValueError('MULTIPLE_ACTION_COMPOSITION_UNSUPPORTED')
        action_dates.add((a['symbol'],a['ex_date']))
        for field in ('record_date','ex_date'):
            if a.get(field) not in action_calendar: raise ValueError('ACTION_DATE_MISSING_OR_OUTSIDE_COVERAGE:' + field)
        if action_calendar.index(a['ex_date']) != action_calendar.index(a['record_date'])+1: raise ValueError('ACTION_RECORD_EX_NOT_ADJACENT')
        for field in ('cash_per_share','bonus_ratio','split_ratio','tax_rate'):
            if type(a[field]) is not str: raise ValueError('ACTION_DECIMAL_STRING_REQUIRED')
        cash,bonus,split,tax = (exact(a[k],0) for k in ('cash_per_share','bonus_ratio','split_ratio','tax_rate'))
        if split < 1 or tax != D('.20'): raise ValueError('ACTION_RATIO_OR_SIMULATED_TAX_UNSUPPORTED')
        for field,required in (('pay_date',cash>0),('shares_available_date',split+bonus>1)):
            if a[field] is None:
                if required:raise ValueError('ACTION_REQUIRED_DATE_MISSING:'+field)
                continue
            if type(a[field]) is not str or date.fromisoformat(a[field]).isoformat()!=a[field] or a[field]<a['ex_date']:
                raise ValueError('ACTION_PAYMENT_OR_SHARE_DATE_INVALID')
        if cash == 0 and bonus == 0 and split == 1: raise ValueError('EMPTY_ACTION_NOT_EVIDENCE_OF_NONE')
        _proof(case,a['evidence_ref'])
    receipt=None
    if case['evidence_grade'] != SYNTHETIC:
        if not callable(provenance_verifier): raise ValueError('EXTERNAL_PROVENANCE_VERIFIER_REQUIRED')
        receipt=provenance_verifier(deepcopy(case))
        if (type(receipt) is not dict or receipt.get('verified') is not True or receipt.get('case_hash') != digest(case)
            or not HASH.fullmatch(str(receipt.get('receipt_hash',''))) or receipt.get('purpose') != ('LOCAL_HISTORICAL_DIAGNOSTIC' if case['mode']=='HISTORY' else 'LOCAL_FORWARD_VIRTUAL_LEDGER')):
            raise ValueError('PROVENANCE_RECEIPT_NOT_CASE_BOUND')
    return dates,members,bars,receipt


def _bar(case,row):
    _proof(case,row['evidence_ref'])
    if row['price_kind'] != 'RAW' or row['status'] not in ('TRADABLE','SUSPENDED'): raise ValueError('RAW_STATUS_REQUIRED')
    if type(row['lot_size']) is not int or row['lot_size'] < 1: raise ValueError('LOT_SIZE_REQUIRED')
    volume=exact(row['volume_shares'],0)
    if volume != int(volume): raise ValueError('INTEGER_SHARE_VOLUME_REQUIRED')
    keys=('open','high','low','close')
    if row['status']=='SUSPENDED':
        if any(row[k] is not None for k in keys) or volume != 0: raise ValueError('SUSPENDED_OHLC_MUST_BE_NULL_VOLUME_ZERO')
        return
    numbers={k:exact(row[k],D('.01')) for k in (*keys,'lower_limit','upper_limit')}
    if any(v%D('.01') for v in numbers.values()): raise ValueError('RAW_CENT_TICK_REQUIRED')
    if not numbers['lower_limit'] <= numbers['low'] <= min(numbers['open'],numbers['close']) <= max(numbers['open'],numbers['close']) <= numbers['high'] <= numbers['upper_limit']:
        raise ValueError('OHLC_OR_LIMIT_ORDER')
    if numbers['lower_limit'] >= numbers['upper_limit']: raise ValueError('LIMIT_BOUNDS_UNKNOWN')


def _feature(rows):
    if len(rows)<21:return None
    close=rows[-1]['close']; sma=sum(r['close'] for r in rows[-20:])/20
    atr=sum(max(r['high']-r['low'],abs(r['high']-p['close']),abs(r['low']-p['close'])) for p,r in zip(rows[-21:-1],rows[-20:]))/20
    rs=close/rows[-21]['close']-1
    trigger=close>max(r['high'] for r in rows[-21:-1]) or (close>sma and rows[-1]['low']<=sma and close>rows[-2]['close'])
    return dict(sma=sma,atr=atr,rs=rs,eligible=trigger and atr>0)


def _blocked_fill(row,value):
    if row['status']=='SUSPENDED':return 'SUSPENDED'
    fill=D(value['execution_price']); opened=D(row['open'])
    if min(fill,opened)<=D(row['lower_limit']) or max(fill,opened)>=D(row['upper_limit']):return 'LIMIT_OR_SLIPPAGE_BOUND'
    if not D(row['low'])<=fill<=D(row['high']):return 'SLIPPAGE_OUTSIDE_DAILY_RANGE'
    if value['quantity']>int(D(row['volume_shares'])*D('.01')):return 'ACTUAL_SESSION_VOLUME_CAP'
    return None


def _position_qty(position):return sum(lot['quantity'] for lot in position['lots'])


def _plain(value):
    if isinstance(value,D):return str(value)
    if isinstance(value,dict):return {k:_plain(v) for k,v in value.items()}
    if isinstance(value,list):return [_plain(v) for v in value]
    return value


def run_diagnostic(case,provenance_verifier=None,protocol=None):
    result={'version':'long-forward-1.0.0','namespace':case.get('namespace'),'strategy_id':case.get('strategy_id'),
            'run_id':case.get('run_id'),'evidence_grade':case.get('evidence_grade'),
            'input_hash':digest(case),'run_attempted':True,'engine_called':False,'status':'DATA_BLOCKED',
            'historical_visibility_proven':False,'untouched_oos':False,'formal_five_year_validation':False,
            'production_enabled':False,'cost_label':'SIMULATED_COSTS','dividend_tax_label':'SIMULATED_FLAT_20_PERCENT',
            'fills':[],'unfilled':[],'ledger':[],'decisions':[],'daily':[],'dividends':[],'errors':[],
            'reason_codes':[],'net_return':None,'maximum_drawdown':None,'complete_trades':0}
    try:
        with localcontext() as ctx:
            ctx.prec=80
            if case.get('mode')!='HISTORY':raise ValueError('USE_FORWARD_PREPARE_SETTLE_FOR_FORWARD_MODE')
            dates,members,bars,receipt=_validate(case,provenance_verifier,protocol)
    except (ValueError,TypeError,KeyError,ArithmeticError,OSError) as exc:
        result['reason_codes']=[str(exc)];result['errors']=[{'stage':'PREFLIGHT','error':type(exc).__name__,'detail':str(exc)}]
        result['content_hash']=digest(result);return result
    result['provenance_receipt']=receipt
    state={'cash_cents':10000000,'positions':{},'receivables':{},'entitlements':{},'pending_sells':{},'pending_buys':[],
           'history':{s:[] for s in members},'marks':{},'consecutive':{s:0 for s in members},'peak_cents':10000000,'max_dd':D(0)}
    result['engine_called']=True
    try:
        with localcontext() as ctx:
            ctx.prec=80
            _run(case,dates,members,bars,state,result)
        result['status']='SIMULATED_TRADES' if result['fills'] else 'RUN_NO_TRADES'
    except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
        result['status']='ENGINE_FAILED';result['partial_run']=True;result['failed_at']=state.get('current_session')
        result['reason_codes']=[str(exc)]
        result['errors'].append({'stage':'ENGINE','session':state.get('current_session'),'error':type(exc).__name__,'detail':str(exc)})
    result['final_cash_cents']=state['cash_cents']
    result['positions']=_plain(state['positions']);result['receivables']=_plain(state['receivables'])
    result['pending_sells']=deepcopy(state['pending_sells']);result['pending_buys']=_plain(state['pending_buys'])
    result['last_completed_session']=result['daily'][-1]['session'] if result['daily'] else None
    result['net_return']=str(D(result['daily'][-1]['nav_cents'])/10000000-1) if result['daily'] else None
    result['maximum_drawdown']=str(state['max_dd']) if result['daily'] else None
    result['performance_scope']='PARTIAL_COMPLETED_DAYS_ONLY' if result['status']=='ENGINE_FAILED' else 'ENTIRE_PREREGISTERED_WINDOW'
    result['total_fee_cents']=sum(x['fees']['total_fee_cents'] for x in result['fills'])
    result['total_slippage_cents']=sum(x['fees']['slippage_cents'] for x in result['fills'])
    result['content_hash']=digest(result)
    return result


def _ledger(state,result,day,kind,delta,reference,**extra):
    before=state['cash_cents'];after=before+delta
    if after<0:raise ValueError('CASH_UNDERFLOW')
    state['cash_cents']=after
    row={'sequence':len(result['ledger']),'session':day,'kind':kind,'reference':reference,'cash_before_cents':before,
         'cash_delta_cents':delta,'cash_after_cents':state['cash_cents'],**_plain(extra),
         'previous_hash':result['ledger'][-1]['content_hash'] if result['ledger'] else digest({'initial_cash_cents':10000000})}
    row['content_hash']=digest(row);result['ledger'].append(row)
    return row


def _action_ex(case,a,state,result,day):
    symbol=a['symbol'];gross=D(a['cash_per_share']);ratio=D(a['split_ratio'])+D(a['bonus_ratio'])
    entitlement=state['entitlements'].get(a['id'],0)
    total= D(entitlement)*ratio
    if total!=int(total):raise ValueError('FRACTIONAL_CORPORATE_ACTION_SHARES_UNSUPPORTED:'+a['id'])
    net_cash=cents(D(entitlement)*gross*(1-D(a['tax_rate'])))
    # Check every transformation before mutating state (atomic action application).
    for row in state['history'][symbol]:
        if any((row[k]-gross)/ratio<=0 for k in ('open','high','low','close')):
            raise ValueError('NONPOSITIVE_CORPORATE_ACTION_ADJUSTMENT')
    p=state['positions'].get(symbol)
    if p and (p['stop_price']-gross)/ratio<=0:raise ValueError('STOP_ADJUSTMENT_NONPOSITIVE')
    if p and _position_qty(p)!=entitlement:raise ValueError('RECORD_EX_POSITION_RECONCILIATION_FAILED')
    for row in state['history'][symbol]:
        for k in ('open','high','low','close'):row[k]=(row[k]-gross)/ratio
    for pending in state['pending_buys']:
        if pending['symbol']==symbol:pending['atr20']=str(D(pending['atr20'])/ratio)
    if symbol in state['marks']:
        state['marks'][symbol]['price']=(state['marks'][symbol]['price']-gross)/ratio
        state['marks'][symbol]['adjustment_event']=a['id']
    if p:
        p['stop_price']=(p['stop_price']-gross)/ratio
        p['entry_compare_price']=(p['entry_compare_price']-gross)/ratio
        additional=int(total)-entitlement
        if additional:
            p['lots'].append({'quantity':additional,'available_date':a['shares_available_date'],'origin':a['id']})
    if net_cash:
        state['receivables'][a['id']]={'net_cents':net_cash,'pay_date':a['pay_date'],'symbol':symbol}
    event={'id':a['id'],'session':day,'stage':'EX','symbol':symbol,'record_quantity':entitlement,
           'gross_cash_per_share':a['cash_per_share'],'tax_rate':a['tax_rate'],'net_receivable_cents':net_cash,
           'added_shares':int(total)-entitlement,'share_availability':a['shares_available_date'],
           'price_transform':{'subtract_gross_cash':str(gross),'divide_ratio':str(ratio)},'evidence_ref':a['evidence_ref']}
    result['dividends'].append(event)
    _ledger(state,result,day,'ACTION_EX',0,a['id'],**event)


def _run(case,dates,members,bars,state,result,start_index=0,stop_index=None,execute=True,make_decisions=True,history_tail=True):
    first,last=case['window']['first_session'],case['window']['last_session'];last_index=dates.index(last)
    actions=case['actions']
    for index,meta in enumerate(case['calendar']):
        if index<start_index:continue
        if stop_index is not None and index>stop_index:break
        day=meta['date'];state['current_session']=day
        if day>last:break
        rows={s:bars[(day,s)] for s in members}
        # Validate day atomically before applying any cash or action mutation.
        for row in rows.values():_bar(case,row)
        for a in actions:
            if a['ex_date']==day:_action_ex(case,a,state,result,day)
        for action_id,receivable in list(state['receivables'].items()):
            if receivable['pay_date']<=day:
                _ledger(state,result,day,'DIVIDEND_PAYMENT',receivable['net_cents'],action_id,symbol=receivable['symbol'])
                result['dividends'].append({'id':action_id,'session':day,'stage':'PAY','net_cents':receivable['net_cents']})
                del state['receivables'][action_id]
        if day>=first and execute:
            _open(case,dates,index,day,rows,members,state,result)
        for symbol,row in rows.items():
            if row['status']=='TRADABLE':
                state['history'][symbol].append({k:D(row[k]) for k in ('open','high','low','close','volume_shares')})
                state['marks'][symbol]={'price':D(row['close']),'source_session':day,'stale_mark':False}
                state['consecutive'][symbol]+=1
            else:
                state['consecutive'][symbol]=0
                if symbol in state['marks']:state['marks'][symbol]['stale_mark']=True
        for a in actions:
            if a['record_date']==day:
                qty=_position_qty(state['positions'][a['symbol']]) if a['symbol'] in state['positions'] else 0
                state['entitlements'][a['id']]=qty
                result['dividends'].append({'id':a['id'],'session':day,'stage':'RECORD','symbol':a['symbol'],'quantity':qty})
        if day<first:continue
        if make_decisions:_decide(case,dates,index,meta,rows,members,state,result,history_tail)
        positions=[];exposure=0
        for symbol,p in state['positions'].items():
            mark=state['marks'].get(symbol)
            if mark is None:raise ValueError('NO_REAL_MARK_FOR_POSITION')
            value=cents(mark['price']*_position_qty(p));exposure+=value
            positions.append({'symbol':symbol,'sector':p['sector'],'quantity':_position_qty(p),
                              'held_quantity':_position_qty(p),
                              'available_quantity':sum(l['quantity'] for l in p['lots'] if l['available_date']<=day),
                              'mark':_plain(mark),'market_value_cents':value,'lots':deepcopy(p['lots'])})
        receivable=sum(r['net_cents'] for r in state['receivables'].values())
        nav=state['cash_cents']+exposure+receivable
        state['peak_cents']=max(state['peak_cents'],nav);state['max_dd']=max(state['max_dd'],D(state['peak_cents']-nav)/state['peak_cents'])
        result['daily'].append({'session':day,'cash_cents':state['cash_cents'],'exposure_cents':exposure,
                                'receivable_cents':receivable,'nav_cents':nav,'positions':positions,
                                'held_quantity':sum(p['quantity'] for p in positions),
                                'available_quantity':sum(p['available_quantity'] for p in positions),
                                'suspended_symbols':[s for s,r in rows.items() if r['status']=='SUSPENDED'],
                                'raw_bar_count':sum(r['status']=='TRADABLE' for r in rows.values()),
                                'passive_exposure_cap_exceeded':exposure>D(nav)*D('.60')})


def _open(case,dates,index,day,rows,members,state,result):
    profile=fee_for(case['fee_schedule'],day);sold_today=set()
    for symbol,reason in sorted(list(state['pending_sells'].items())):
        row=rows[symbol];position=state['positions'][symbol]
        qty=sum(l['quantity'] for l in position['lots'] if l['available_date']<=day)
        failure='SUSPENDED' if row['status']=='SUSPENDED' else ('T_PLUS_ONE_OR_ACTION_SHARES_LOCKED' if qty==0 else None)
        sale=None
        if failure is None:
            sale=quote(row['open'],qty,'SELL',day,profile);failure=_blocked_fill(row,sale)
            if state['cash_cents']+sale['cash_delta_cents']<0:failure='EXIT_FEES_EXCEED_CASH'
        if failure:
            result['unfilled'].append({'session':day,'symbol':symbol,'side':'SELL','reason':failure,'retained_quantity':_position_qty(position)});continue
        row_ledger=_ledger(state,result,day,'SIMULATED_SELL',sale['cash_delta_cents'],symbol,symbol=symbol,side='SELL',
                           quantity=qty,execution_price=sale['execution_price'],fees=sale['fees'],reason=reason)
        result['fills'].append(deepcopy(row_ledger));sold_today.add(symbol)
        position['lots']=[l for l in position['lots'] if l['available_date']>day]
        if not position['lots']:
            del state['positions'][symbol];del state['pending_sells'][symbol];result['complete_trades']+=1
        else:result['unfilled'].append({'session':day,'symbol':symbol,'side':'SELL','reason':'ACTION_SHARES_STILL_LOCKED','retained_quantity':_position_qty(position)})
    for pending in state['pending_buys']:
        symbol=pending['symbol'];row=rows[symbol]
        failure='NO_SAME_DAY_REENTRY' if symbol in sold_today else ('SUSPENDED' if row['status']=='SUSPENDED' else None)
        if failure:
            result['unfilled'].append({'session':day,'symbol':symbol,'side':'BUY','reason':failure});continue
        marked=[{'symbol':s,'sector':p['sector'],'quantity':_position_qty(p),'mark_price':str(state['marks'][s]['price'].quantize(D('0.000000000001'),rounding=ROUND_HALF_EVEN))} for s,p in state['positions'].items()]
        nav=state['cash_cents']+sum(cents(D(p['mark_price'])*p['quantity']) for p in marked)+sum(r['net_cents'] for r in state['receivables'].values())
        candidate={**pending,'price':row['open'],'lot_size':row['lot_size'],
                   'atr20':str(D(pending['atr20']).quantize(D('0.000000000001'),rounding=ROUND_CEILING))}
        allocation=build_portfolio([candidate],state['cash_cents'],marked,nav,case['fee_schedule'],day)
        if not allocation['plans']:
            result['unfilled'].append({'session':day,'symbol':symbol,'side':'BUY','reason':allocation['rejections'][0]['reason']});continue
        plan=allocation['plans'][0];buy=plan['entry'];failure=_blocked_fill(row,buy)
        if failure:
            result['unfilled'].append({'session':day,'symbol':symbol,'side':'BUY','reason':failure});continue
        if index+1>=len(dates):raise ValueError('NEXT_SESSION_SETTLEMENT_MISSING')
        row_ledger=_ledger(state,result,day,'SIMULATED_BUY',buy['cash_delta_cents'],symbol,symbol=symbol,side='BUY',quantity=plan['quantity'],
                           execution_price=buy['execution_price'],fees=buy['fees'],planned_loss_cents=plan['planned_loss_cents'])
        result['fills'].append(deepcopy(row_ledger))
        state['positions'][symbol]={'sector':members[symbol],'entry_index':index,'entry_compare_price':D(buy['execution_price']),
                                    'stop_price':D(plan['stop_price']),'lots':[{'quantity':plan['quantity'],'available_date':dates[index+1],'origin':'BUY'}]}
        state['marks'][symbol]={'price':D(buy['execution_price']),'source_session':day,'stale_mark':False}
    state['pending_buys']=[]

def _decide(case,dates,index,meta,rows,members,state,result,history_tail=True):
    day=meta['date'];last_index=dates.index(case['window']['last_session'])
    features={s:_feature(state['history'][s]) for s in members}
    for symbol,p in state['positions'].items():
        age=index-p['entry_index']+1;reason=None
        if age>=40:reason='MAXIMUM_40_EXCHANGE_SESSIONS'
        if rows[symbol]['status']=='TRADABLE':
            close=D(rows[symbol]['close']);feature=features[symbol]
            if close<=p['stop_price']:reason='CLOSE_STOP_2_ATR20'
            elif feature and close<feature['sma']:reason='CLOSE_LOGIC_INVALIDATION_SMA20'
            elif age>=20 and close<=p['entry_compare_price']:reason='DAY20_NONPOSITIVE_ADJUSTED_PRICE_RETURN'
        if reason:state['pending_sells'].setdefault(symbol,reason)
    sector_rs={};excluded={}
    for sector in sorted(set(members.values())):
        group=[s for s in members if members[s]==sector]
        if any(features[s] is None or rows[s]['status']!='TRADABLE' or state['consecutive'][s]<21 for s in group):
            excluded[sector]='INCOMPLETE_OR_SUSPENDED_MEMBER_21_REAL_BARS_REQUIRED';continue
        sector_rs[sector]=sum(features[s]['rs'] for s in group)/len(group)
    chosen=sorted([s for s in sector_rs if sector_rs[s]>0],key=lambda s:(-sector_rs[s],s))[:2]
    candidates=sorted([s for s in members if members[s] in chosen and features[s]['eligible'] and s not in state['positions']],
                      key=lambda s:(chosen.index(members[s]),-(features[s]['rs']-sector_rs[members[s]]),s))
    if history_tail and last_index-index<=40:candidates=[]
    state['pending_buys']=[{'symbol':s,'sector':members[s],'atr20':str(features[s]['atr']),
                           'previous20_median_volume_shares':str(median(r['volume_shares'] for r in state['history'][s][-20:]))} for s in candidates]
    result['decisions'].append({'session':day,'market_close_at':meta['close_at'],'decision_at':meta['decision_at'],
                                'decision_clock_label':meta['decision_clock_label'],'historical_visibility_proven':False,
                                'next_session':dates[index+1] if index+1<len(dates) else None,
                                'sector_sample_rs20':_plain(sector_rs),'selected_sectors':chosen,'sector_exclusions':excluded,
                                'ranked_buy_symbols':candidates,'pending_sell_reasons':deepcopy(state['pending_sells'])})

