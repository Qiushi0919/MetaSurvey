"""Preregistered same-window buy-and-hold controls; no production engine import."""
from decimal import Decimal as D, localcontext, ROUND_HALF_EVEN


def cents(x):
    return int((D(x)*100).quantize(D(1), rounding=ROUND_HALF_EVEN))


def cost(price, qty, side, profile):
    raw = D(price)
    execution = (raw*(1+D(profile['slippage_bps'])/10000*(1 if side == 'BUY' else -1))).quantize(D('.01'), rounding=ROUND_HALF_EVEN)
    notional = cents(execution*qty)
    commission = max(profile['minimum_commission_cents'], cents(execution*qty*D(profile['commission_rate'])))
    exchange = 0 if profile['exchange_included'] else cents(execution*qty*D(profile['exchange_rate']))
    other = 0 if profile['other_included'] else cents(execution*qty*D(profile['other_buy_rate' if side == 'BUY' else 'other_sell_rate']))
    tax = 0 if side == 'BUY' else cents(execution*qty*D(profile['sell_tax_rate']))
    fee = commission+exchange+other+tax
    return dict(execution_price=str(execution),quantity=qty,notional_cents=notional,fees_cents=fee,
                slippage_cents=cents(abs(execution-raw)*qty),cash_delta_cents=(-notional-fee if side=='BUY' else notional-fee))


def profile_for(case, day):
    p = [p for p in case['fee_schedule'] if p['effective_from'] <= day <= p['effective_until']]
    if len(p) != 1: raise ValueError('DATED_COST_PROFILE_REQUIRED')
    return p[0]


def build_benchmarks(case, protocol):
    if protocol['version'] != '1.0.0' or case['run_id'] != protocol['baseline_run_id']:
        raise ValueError('BENCHMARK_PROTOCOL_BINDING')
    if any(D(a['split_ratio']) != 1 or D(a['bonus_ratio']) != 0 for a in case['actions']):
        raise ValueError('BENCHMARK_V1_CASH_ACTIONS_ONLY')
    with localcontext() as ctx:
        ctx.prec = 80
        return [_run(case,protocol,b) for b in protocol['benchmarks']]


def _run(case, protocol, spec):
    initial=protocol['initial_cash_cents']; cash=initial
    symbols=sorted(m['symbol'] for m in case['universe'])
    dates=[d['date'] for d in case['calendar'] if case['window']['first_session']<=d['date']<=case['window']['last_session']]
    if not dates or not symbols: raise ValueError('EMPTY_BENCHMARK_SCOPE')
    bars={(r['session'],r['symbol']):r for r in case['bars']}
    if len(bars)!=len(case['bars']):raise ValueError('DUPLICATE_BAR')
    slot=int(D(initial)*D(spec['allocation_fraction'])/len(symbols))
    holdings={s:0 for s in symbols}; entitlements={}; receivables={}; marks={}
    trades=[]; rejected=[]; ledger=[]; series=[]; dividend=0; peak=initial; peakday='INITIAL_CAPITAL'; maximum=D(0); trough=None; ddpeak=None
    def book(day,kind,delta,symbol):
        nonlocal cash
        before=cash;cash+=delta
        if cash<0:raise ValueError('NEGATIVE_CASH')
        ledger.append(dict(session=day,kind=kind,symbol=symbol,cash_before_cents=before,cash_delta_cents=delta,cash_after_cents=cash))
    for day in dates:
        for a in case['actions']:
            if a['ex_date']!=day:continue
            qty=entitlements.get(a['id'],0); ratio=D(a['split_ratio'])+D(a['bonus_ratio'])
            new=D(qty)*ratio
            if new!=int(new):raise ValueError('FRACTIONAL_ACTION_UNSUPPORTED')
            holdings[a['symbol']]+=int(new)-qty
            if a['symbol'] in marks:marks[a['symbol']]=(marks[a['symbol']]-D(a['cash_per_share']))/ratio
            net=cents(D(qty)*D(a['cash_per_share'])*(1-D(a['tax_rate'])))
            if net:receivables[a['id']]={'cents':net,'pay_date':a['pay_date'],'symbol':a['symbol']}
        for key,rec in list(receivables.items()):
            if rec['pay_date']<=day:
                book(day,'DIVIDEND_PAYMENT',rec['cents'],rec['symbol']);dividend+=rec['cents'];del receivables[key]
        if day==dates[0]:
            for symbol in symbols:
                row=bars[(day,symbol)];reason=None;q=None
                if row['status']=='SUSPENDED':reason='SUSPENDED'
                elif row['status']!='TRADABLE':raise ValueError('UNKNOWN_STATUS')
                else:
                    lot=row['lot_size']
                    if type(lot)!=int or lot<=0:raise ValueError('INVALID_LOT')
                    volume_limit=int(D(row['volume_shares'])*D('.01'))//lot*lot
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
                book(day,'BUY',q['cash_delta_cents'],symbol);holdings[symbol]=q['quantity'];trades.append(dict(session=day,symbol=symbol,**q))
        for symbol in symbols:
            row=bars[(day,symbol)]
            if row['status']=='TRADABLE':marks[symbol]=D(row['close'])
            elif row['status']!='SUSPENDED':raise ValueError('UNKNOWN_STATUS')
            if holdings[symbol] and symbol not in marks:raise ValueError('NO_CAUSAL_MARK')
        for a in case['actions']:
            if a['record_date']==day:entitlements[a['id']]=holdings[a['symbol']]
        exposure=sum(cents(marks[s]*q) for s,q in holdings.items() if q);recv=sum(r['cents'] for r in receivables.values());nav=cash+exposure+recv
        if nav>peak:peak=nav;peakday=day
        dd=D(peak-nav)/peak
        if dd>maximum:maximum=dd;trough=day;ddpeak=peakday
        series.append(dict(session=day,nav_cents=nav,nav_cny=str(D(nav)/100),cash_cents=cash,exposure_cents=exposure,receivable_cents=recv,drawdown_fraction=str(dd),exposure_fraction=str(D(exposure)/nav)))
    terminal=[dict(symbol=s,quantity=q,market_value_cents=cents(marks[s]*q)) for s,q in holdings.items() if q]
    reserve=sum(cost(str(marks[s]),q,'SELL',profile_for(case,dates[-1]))['fees_cents'] for s,q in holdings.items() if q)
    maxpeakvalue=initial if ddpeak=='INITIAL_CAPITAL' else next((r['nav_cents'] for r in series if r['session']==ddpeak),initial)
    recovery=next((r['session'] for r in series if trough and r['session']>trough and r['nav_cents']>=maxpeakvalue),None)
    return dict(id=spec['id'],name=spec['name'],run_id=case['run_id'],status='COMPLETED_DIAGNOSTIC_CONTROL',nav_series=series,
                net_return=str(D(series[-1]['nav_cents'])/initial-1),max_drawdown=str(maximum),drawdown_dates=dict(peak=ddpeak,trough=trough,recovery=recovery),
                trades=trades,rejections=rejected,ledger=ledger,terminal_positions=terminal,terminal_cash_cents=cash,terminal_receivable_cents=sum(x['cents'] for x in receivables.values()),
                fees_cents=sum(x['fees_cents'] for x in trades),slippage_cents=sum(x['slippage_cents'] for x in trades),dividend_cents=dividend,
                initial_budget_per_symbol_cents=slot,initial_invested_notional_cents=sum(x['notional_cents'] for x in trades),
                average_exposure_fraction=str(sum(D(r['exposure_fraction']) for r in series)/len(series)),maximum_exposure_fraction=str(max(D(r['exposure_fraction']) for r in series)),
                exposed_sessions=sum(r['exposure_cents']>0 for r in series),last40_no_new_entry_effect='NONE_SINGLE_INITIAL_PURCHASE_ONLY',
                hypothetical_terminal_sell_fees_cents=reserve,terminal_sell_fee_reserve_is_fill=False,cost_label='SIMULATED_COSTS',historical_visibility_proven=False,untouched_oos=False)
