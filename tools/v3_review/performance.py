"""Pure accounting derivation from a sealed Case and EngineResult.

No strategy execution, source request, credential lookup or filesystem mutation.
The reader must separately bind actual file hashes and authority. Canonical input
and ledger hashes are rechecked here; hashes alone do not prove source licensing.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import json

D = Decimal
INITIAL_CENTS = 10_000_000
FEE_COMPONENTS = ('commission_cents','exchange_cents','other_cents','sell_tax_cents')

class PerformanceError(ValueError): pass

def digest(value):
    return 'sha256:' + sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def integer(value, label, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum): raise PerformanceError(label)
    return value

def decimal(value):
    if type(value) not in (str,int): raise PerformanceError('DECIMAL_STRING_OR_INTEGER_REQUIRED')
    result = D(value)
    if not result.is_finite(): raise PerformanceError('FINITE_DECIMAL_REQUIRED')
    return result

def money(value): return format(D(value)/100,'.2f')
def fraction(value, denominator): return str(D(value)/D(denominator)) if denominator else None
def cents(value): return int((value*100).quantize(D(1),rounding=ROUND_HALF_EVEN))
def require(condition, label):
    if not condition: raise PerformanceError(label)

def _mdd(series, initial):
    peak = initial; peak_day = series[0]['session'] if series else None
    peak_source = 'INITIAL_CAPITAL_BEFORE_FIRST_SESSION'
    maximum = D(0); worst = None
    for row in series:
        nav = row['nav_cents']
        if nav > peak:
            peak, peak_day, peak_source = nav,row['session'],'DAILY_CLOSE'
        dd = D(peak-nav)/peak
        row['drawdown_fraction'] = str(dd)
        if dd > maximum:
            maximum = dd
            worst = {'peak_session':peak_day,'peak_source':peak_source,'trough_session':row['session'],
                     'peak_nav_cents':peak,'trough_nav_cents':nav}
    result = {'fraction':str(maximum),'peak_session':None,'peak_source':None,'trough_session':None,
              'recovery_session':None,'peak_nav_cents':None,'trough_nav_cents':None,'recovered':None,
              'state':'NO_DRAWDOWN' if series else 'NO_COMPLETED_SESSIONS',
              'tie_policy':'earliest equal peak; earliest maximum-drawdown trough; first later close >= peak'}
    if worst:
        result.update(worst,state='DRAWDOWN',recovered=False)
        for row in series:
            if row['session']>worst['trough_session'] and row['nav_cents']>=worst['peak_nav_cents']:
                result.update(recovery_session=row['session'],recovered=True);break
    return result

def derive_performance(case, engine_result):
    """Return deterministic JSON-safe performance, or raise on inconsistent inputs.

    Cents remain exact integers. Display CNY and fractions are Decimal strings.
    Partial-engine results use completed-close days only; unvalued tail fills
    remain visible but excluded from contributions. There are no external flows.
    """
    with localcontext() as ctx:
        ctx.prec = 80
        return _derive(case,engine_result)

def _derive(case, r):
    require(type(case) is dict and type(r) is dict,'OBJECT_INPUTS_REQUIRED')
    require(r.get('input_hash')==digest(case),'CASE_RESULT_HASH_MISMATCH')
    require(r.get('content_hash')==digest({k:v for k,v in r.items() if k!='content_hash'}),'RESULT_CONTENT_HASH_MISMATCH')
    for key in ('run_id','namespace','strategy_id'):
        require(case.get(key) and r.get(key)==case[key],'CASE_RESULT_IDENTITY_MISMATCH:'+key)
    require(integer(case.get('rules',{}).get('initial_cash_cents'),'INTEGER_INITIAL_CAPITAL_REQUIRED')==INITIAL_CENTS,'REGISTERED_100000_CNY_REQUIRED')
    require(type(r.get('engine_called')) is bool,'ENGINE_CALLED_BOOLEAN_REQUIRED')
    groups = {m['symbol']:m['sector'] for m in case['universe']}
    require(len(groups)==len(case['universe']) and bool(groups),'UNIQUE_UNIVERSE_REQUIRED')
    output = {'kind':'V3PerformanceDerivation','version':'1.0.0','run_id':case['run_id'],
              'namespace':case['namespace'],'strategy_id':case['strategy_id'],
              'source_hashes':{'case_content_hash':digest(case),'engine_result_content_hash':r['content_hash'],
                               'engine_result_canonical_hash':digest(r)},
              'units':{'money':'INTEGER_CENTS_AND_DECIMAL_CNY','returns':'FRACTION_NOT_PERCENT',
                       'drawdown':'NONNEGATIVE_FRACTION','contribution':'NET_PNL_DIVIDED_BY_INITIAL_100000_CNY'},
              'status':'ENGINE_NOT_RUN','engine_called':r['engine_called'],'source_status':r['status'],
              'summary':None,'baseline':{'session':case['window']['first_session'],'point':'BEFORE_FIRST_SESSION',
                                       'nav_cents':INITIAL_CENTS,'nav_cny':money(INITIAL_CENTS)},
              'nav_series':[],'trades':[],'unfilled':deepcopy(r.get('unfilled',[])),
              'symbol_contributions':[],'group_contributions':[], 'max_drawdown':_mdd([],INITIAL_CENTS),
              'fee_summary':None,'dividend_summary':None,'reconciliation':None,
              'limitations':['HISTORICAL_DIAGNOSTIC_NOT_UNTOUCHED_OOS','SIMULATED_COSTS',
                             'slippage is embedded in execution price and is not deducted twice',
                             'fixed contemporary sample; no formal PIT or investment effectiveness claim',
                             'trade table counts filled orders, not closed round-trip strategies']}
    if not r['engine_called']:
        require(not any(r.get(k) for k in ('daily','fills','ledger')),'UNRUN_ENGINE_WITH_ACTIVITY')
        output['content_hash']=digest(output);return output
    require(r['status'] in ('SIMULATED_TRADES','RUN_NO_TRADES','ENGINE_FAILED'),'ENGINE_RESULT_STATUS_UNSUPPORTED')
    days = r['daily']; dates = [x['session'] for x in days]
    require(dates==sorted(set(dates)),'ORDERED_UNIQUE_DAILY_SESSIONS_REQUIRED')
    calendars = {x['date'] for x in case['calendar']}
    require(all(d in calendars and case['window']['first_session']<=d<=case['window']['last_session'] for d in dates),'DAILY_SCOPE_MISMATCH')
    if r['status']!='ENGINE_FAILED':
        require(dates==[x['date'] for x in case['calendar'] if case['window']['first_session']<=x['date']<=case['window']['last_session']],'COMPLETE_RESULT_DATE_COVERAGE')
    cutoff = dates[-1] if dates else None
    ledger = r['ledger']; fills = r['fills']; actions = {a['id']:a for a in case.get('actions',[])}
    require(len(actions)==len(case.get('actions',[])),'DUPLICATE_ACTION_ID')
    prev_hash=digest({'initial_cash_cents':INITIAL_CENTS}); cash=INITIAL_CENTS; prev_session=None
    trade_rows=[]; fill_ledger=[]; fees_all=defaultdict(int)
    for sequence,row in enumerate(ledger):
        require(row.get('sequence')==sequence and row.get('previous_hash')==prev_hash,'LEDGER_SEQUENCE_OR_CHAIN_MISMATCH')
        require(row.get('content_hash')==digest({k:v for k,v in row.items() if k!='content_hash'}),'LEDGER_ROW_HASH_MISMATCH')
        prev_hash=row['content_hash'];session=row['session']
        require(session in calendars and (prev_session is None or session>=prev_session),'LEDGER_SESSION_ORDER_OR_SCOPE')
        prev_session=session
        delta=integer(row['cash_delta_cents'],'INTEGER_CASH_DELTA_REQUIRED')
        integer(row['cash_before_cents'],'INTEGER_LEDGER_CASH_REQUIRED',0)
        integer(row['cash_after_cents'],'INTEGER_LEDGER_CASH_REQUIRED',0)
        require(row['cash_before_cents']==cash and row['cash_after_cents']==cash+delta,'LEDGER_CASH_CHAIN_MISMATCH');cash+=delta
        require(cash>=0,'NEGATIVE_CASH')
        kind=row['kind']
        require(kind in ('SIMULATED_BUY','SIMULATED_SELL','DIVIDEND_PAYMENT','ACTION_EX'),'UNSUPPORTED_LEDGER_KIND')
        symbol=row['symbol'];require(symbol in groups,'LEDGER_UNKNOWN_SYMBOL')
        if kind in ('SIMULATED_BUY','SIMULATED_SELL'):
            side='BUY' if kind=='SIMULATED_BUY' else 'SELL';require(row['side']==side,'LEDGER_SIDE_CONFLICT')
            qty=integer(row['quantity'],'POSITIVE_INTEGER_QUANTITY',1);fee=row['fees']
            for key in (*FEE_COMPONENTS,'notional_cents','raw_notional_cents','minimum_commission_uplift_cents','total_fee_cents','slippage_cents'):
                integer(fee[key],'NONNEGATIVE_INTEGER_FEE:'+key,0)
            require(sum(fee[k] for k in FEE_COMPONENTS)==fee['total_fee_cents'],'FEE_COMPONENT_TOTAL_MISMATCH')
            require(fee['minimum_commission_uplift_cents']<=fee['commission_cents'],'COMMISSION_UPLIFT_NOT_SUBSET')
            require(cents(decimal(row['execution_price'])*qty)==fee['notional_cents'],'NOTIONAL_PRICE_QUANTITY_MISMATCH')
            expected=-fee['notional_cents']-fee['total_fee_cents'] if side=='BUY' else fee['notional_cents']-fee['total_fee_cents']
            require(delta==expected,'FILL_CASH_FEE_MISMATCH')
            slip=fee['notional_cents']-fee['raw_notional_cents'] if side=='BUY' else fee['raw_notional_cents']-fee['notional_cents']
            require(slip==fee['slippage_cents'],'EMBEDDED_SLIPPAGE_MISMATCH')
            for key in fee:fees_all[key]+=integer(fee[key],'NONNEGATIVE_INTEGER_FEE:'+key,0)
            fill_ledger.append(row)
            trade_rows.append({'sequence':sequence,'session':session,'symbol':symbol,'group':groups[symbol],'side':side,
                               'quantity':qty,'execution_price_cny':row['execution_price'],
                               'notional_cents':fee['notional_cents'],'notional_cny':money(fee['notional_cents']),
                               'raw_notional_cents':fee['raw_notional_cents'],'fees_cents':fee['total_fee_cents'],
                               'fees_cny':money(fee['total_fee_cents']),'slippage_cents':fee['slippage_cents'],
                               'slippage_cny':money(fee['slippage_cents']),'cash_delta_cents':delta,'cash_delta_cny':money(delta),
                               'fee_components_cents':deepcopy(fee),'reason':row.get('reason'),
                               'ledger_hash':row['content_hash'],'included_in_valuation_scope':cutoff is not None and session<=cutoff})
        elif kind=='ACTION_EX':require(delta==0,'ACTION_EX_CANNOT_MOVE_CASH')
    require(fills==fill_ledger,'FILLS_LEDGER_DIVERGENCE')
    require(integer(r.get('final_cash_cents'),'INTEGER_FINAL_CASH_REQUIRED',0)==cash,'FINAL_CASH_MISMATCH')
    integer(r.get('total_fee_cents'),'INTEGER_TOTAL_FEES_REQUIRED',0)
    integer(r.get('total_slippage_cents'),'INTEGER_TOTAL_SLIPPAGE_REQUIRED',0)
    require(r.get('total_fee_cents')==fees_all['total_fee_cents'] and r.get('total_slippage_cents')==fees_all['slippage_cents'],'RESULT_COST_TOTAL_MISMATCH')
    output['trades']=trade_rows
    if not days:
        output.update(status='NO_COMPLETED_SESSIONS');output['content_hash']=digest(output);return output
    symbol_totals={s:{'symbol':s,'group':g,'buy_cash_out_cents':0,'sell_cash_in_cents':0,
                       'dividend_paid_cents':0,'dividend_net_entitled_cents':0,'dividend_gross_cents':0,
                       'dividend_simulated_tax_cents':0,'fees_cents':0,'slippage_cents':0,
                       'filled_buy_orders':0,'filled_sell_orders':0,'ending_market_value_cents':0,
                       'ending_receivable_cents':0,'ending_quantity':0} for s,g in groups.items()}
    qtys=defaultdict(int);receivables={};cash=INITIAL_CENTS;cursor=0;scope_fees=defaultdict(int);dividend_events=[]
    def apply(row):
        nonlocal cash
        kind=row['kind'];symbol=row['symbol'];item=symbol_totals[symbol];cash+=row['cash_delta_cents']
        if kind=='SIMULATED_BUY':
            qtys[symbol]+=row['quantity'];item['buy_cash_out_cents']-=row['cash_delta_cents'];item['filled_buy_orders']+=1
        elif kind=='SIMULATED_SELL':
            qtys[symbol]-=row['quantity'];require(qtys[symbol]>=0,'SELL_EXCEEDS_HELD_SHARES');item['sell_cash_in_cents']+=row['cash_delta_cents'];item['filled_sell_orders']+=1
        elif kind=='ACTION_EX':
            a=actions.get(row['id']);require(a is not None and a['symbol']==symbol and a['ex_date']==row['session'],'ACTION_REFERENCE_CONFLICT')
            require(row['id'] not in seen_actions,'DUPLICATE_ACTION_EX');seen_actions.add(row['id'])
            quantity=integer(row['record_quantity'],'INTEGER_RECORD_QUANTITY',0);require(quantity==qtys[symbol],'ACTION_HELD_QUANTITY_MISMATCH')
            gross=decimal(a['cash_per_share'])*quantity
            net=cents(gross*(1-decimal(a['tax_rate'])))
            require(row['net_receivable_cents']==net,'DIVIDEND_NET_ENTITLEMENT_MISMATCH')
            require(decimal(row['gross_cash_per_share'])==decimal(a['cash_per_share']) and decimal(row['tax_rate'])==decimal(a['tax_rate']),'DIVIDEND_SOURCE_VALUES_MISMATCH')
            additional=D(quantity)*(decimal(a['split_ratio'])+decimal(a['bonus_ratio'])-1)
            require(additional==additional.to_integral_value() and row['added_shares']==int(additional),'ACTION_SHARES_MISMATCH')
            qtys[symbol]+=int(additional)
            if net:receivables[row['id']]={'symbol':symbol,'net_cents':net,'pay_date':a['pay_date']}
            gross_cents=cents(gross);item['dividend_net_entitled_cents']+=net;item['dividend_gross_cents']+=gross_cents;item['dividend_simulated_tax_cents']+=gross_cents-net
            dividend_events.append({'id':row['id'],'session':row['session'],'stage':'EX','symbol':symbol,'group':groups[symbol],
                                    'record_quantity':quantity,'gross_cents':gross_cents,'net_cents':net,
                                    'simulated_tax_cents':gross_cents-net,'added_shares':int(additional),'pay_date':a['pay_date']})
        elif kind=='DIVIDEND_PAYMENT':
            ref=row['reference'];entry=receivables.pop(ref,None)
            require(entry is not None and entry['symbol']==symbol and entry['net_cents']==row['cash_delta_cents'],'DIVIDEND_PAYMENT_RECEIVABLE_MISMATCH')
            require(entry['pay_date']<=row['session'],'DIVIDEND_PAID_BEFORE_DUE')
            item['dividend_paid_cents']+=row['cash_delta_cents'];dividend_events.append({'id':ref,'session':row['session'],'stage':'PAY','symbol':symbol,'group':groups[symbol],'net_cents':row['cash_delta_cents']})
        if kind in ('SIMULATED_BUY','SIMULATED_SELL'):
            item['fees_cents']+=row['fees']['total_fee_cents'];item['slippage_cents']+=row['fees']['slippage_cents']
            for key,value in row['fees'].items():scope_fees[key]+=value
    seen_actions=set()
    for day in days:
        for key in ('cash_cents','exposure_cents','receivable_cents','nav_cents'):
            integer(day[key],'INTEGER_DAILY_MONEY_REQUIRED:'+key,0)
        while cursor<len(ledger) and ledger[cursor]['session']<=day['session']:
            apply(ledger[cursor]);cursor+=1
        positions=day['positions'];present=set();value=0
        for p in positions:
            symbol=p['symbol'];require(symbol in groups and symbol not in present,'DAILY_POSITION_IDENTITY');present.add(symbol)
            require(p['sector']==groups[symbol],'DAILY_GROUP_MISMATCH')
            quantity=integer(p['quantity'],'DAILY_POSITIVE_QUANTITY',1);require(quantity==qtys[symbol],'DAILY_HOLDINGS_RECONCILIATION')
            integer(p['market_value_cents'],'INTEGER_MARK_VALUE_REQUIRED',0)
            marked=cents(decimal(p['mark']['price'])*quantity);require(marked==p['market_value_cents'],'DAILY_MARK_RECONCILIATION');value+=marked
        require({s for s,q in qtys.items() if q}==present,'DAILY_MISSING_POSITION')
        recv=sum(x['net_cents'] for x in receivables.values())
        require(day['cash_cents']==cash and day['exposure_cents']==value and day['receivable_cents']==recv,'DAILY_CASH_ASSET_RECONCILIATION')
        nav=cash+value+recv;require(day['nav_cents']==nav and nav>0,'DAILY_NAV_RECONCILIATION')
        output['nav_series'].append({'session':day['session'],'nav_cents':nav,'nav_cny':money(nav),
                                     'return_fraction':fraction(nav-INITIAL_CENTS,INITIAL_CENTS),
                                     'cash_cents':cash,'cash_cny':money(cash),'receivable_cents':recv,'receivable_cny':money(recv),
                                     'exposure_cents':value,'exposure_cny':money(value),'exposure_fraction':fraction(value,nav),
                                     'cash_fraction':fraction(cash,nav),'receivable_fraction':fraction(recv,nav),
                                     'holdings':deepcopy(positions)})
    last=days[-1];final_nav=last['nav_cents']
    for p in last['positions']:
        symbol_totals[p['symbol']]['ending_market_value_cents']=p['market_value_cents'];symbol_totals[p['symbol']]['ending_quantity']=p['quantity']
    for entry in receivables.values():symbol_totals[entry['symbol']]['ending_receivable_cents']+=entry['net_cents']
    for item in symbol_totals.values():
        contribution=item['sell_cash_in_cents']-item['buy_cash_out_cents']+item['dividend_paid_cents']+item['ending_market_value_cents']+item['ending_receivable_cents']
        item.update(contribution_cents=contribution,contribution_cny=money(contribution),contribution_fraction=fraction(contribution,INITIAL_CENTS))
    require(sum(x['contribution_cents'] for x in symbol_totals.values())==final_nav-INITIAL_CENTS,'CONTRIBUTION_NAV_RECONCILIATION')
    if r['status']!='ENGINE_FAILED':
        require(r['receivables']==receivables,'TERMINAL_RECEIVABLES_MISMATCH')
        terminal_qty={s:sum(l['quantity'] for l in p['lots']) for s,p in r['positions'].items()}
        require(terminal_qty=={s:q for s,q in qtys.items() if q},'TERMINAL_POSITIONS_MISMATCH')
    aggregate={}
    for item in symbol_totals.values():
        group=aggregate.setdefault(item['group'],{'group':item['group'],'members':[]})
        group['members'].append(item['symbol'])
        for key,value in item.items():
            if key.endswith('_cents') or key in ('filled_buy_orders','filled_sell_orders','ending_quantity'):group[key]=group.get(key,0)+value
    for group in aggregate.values():group.update(contribution_cny=money(group['contribution_cents']),contribution_fraction=fraction(group['contribution_cents'],INITIAL_CENTS))
    mdd=_mdd(output['nav_series'],INITIAL_CENTS)
    require(decimal(r['net_return'])==D(final_nav-INITIAL_CENTS)/INITIAL_CENTS,'SOURCE_NET_RETURN_MISMATCH')
    require(decimal(r['maximum_drawdown'])==D(mdd['fraction']),'SOURCE_DRAWDOWN_MISMATCH')
    gross=sum(x['dividend_gross_cents'] for x in symbol_totals.values());net=sum(x['dividend_net_entitled_cents'] for x in symbol_totals.values());paid=sum(x['dividend_paid_cents'] for x in symbol_totals.values())
    output.update(status='VERIFIED' if r['status']!='ENGINE_FAILED' else 'PARTIAL_COMPLETED_DAYS_ONLY',
                  symbol_contributions=list(symbol_totals.values()),group_contributions=list(aggregate.values()),max_drawdown=mdd,
                  fee_summary={'components_cents':{k:scope_fees[k] for k in FEE_COMPONENTS},'total_fee_cents':scope_fees['total_fee_cents'],
                               'minimum_commission_uplift_cents':scope_fees['minimum_commission_uplift_cents'],
                               'uplift_included_in_commission':True,'slippage_cents':scope_fees['slippage_cents'],
                               'slippage_embedded_not_additional_cash_debit':True,
                               'total_friction_cents':scope_fees['total_fee_cents']+scope_fees['slippage_cents'],
                               'recorded_all_fills_fee_cents':fees_all['total_fee_cents'],'recorded_all_fills_slippage_cents':fees_all['slippage_cents']},
                  dividend_summary={'gross_entitled_cents':gross,'net_entitled_cents':net,'simulated_tax_cents':gross-net,
                                    'paid_cents':paid,'ending_receivable_cents':sum(x['net_cents'] for x in receivables.values()),
                                    'tax_label':'SIMULATED_FLAT_20_PERCENT','events':dividend_events},
                  reconciliation={'status':'PASS','initial_capital_cents':INITIAL_CENTS,'ledger_cash_final_cents':r['final_cash_cents'],
                                  'valued_cash_final_cents':last['cash_cents'],'contribution_sum_cents':sum(x['contribution_cents'] for x in symbol_totals.values()),
                                  'nav_profit_cents':final_nav-INITIAL_CENTS,'difference_cents':0,'validated_daily_rows':len(days),
                                  'validated_ledger_rows':len(ledger),'excluded_unvalued_tail_ledger_rows':len(ledger)-cursor,
                                  'valuation_cutoff':cutoff,'initial_cash_is_not_company_income':True},
                  summary={'initial_cash_cents':INITIAL_CENTS,'final_nav_cents':final_nav,'final_nav_cny':money(final_nav),
                           'net_profit_cents':final_nav-INITIAL_CENTS,'net_return_fraction':fraction(final_nav-INITIAL_CENTS,INITIAL_CENTS),
                           'max_drawdown_fraction':mdd['fraction'],'fees_cents':scope_fees['total_fee_cents'],'slippage_cents':scope_fees['slippage_cents'],
                           'dividend_net_cents':net,'completed_sessions':len(days),'filled_orders':sum(t['included_in_valuation_scope'] for t in trade_rows),
                           'complete_trades':r['complete_trades'],'complete_trades_source':'ORIGINAL_ENGINE_NOT_REDEFINED',
                           'first_session':dates[0],'last_session':cutoff})
    output['content_hash']=digest(output)
    return output
