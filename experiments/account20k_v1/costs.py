"""Simulation-only per-order cumulative fees and FIFO cash-dividend tax.

Commission inclusion is Owner's simulation assumption, not broker verification.
Decimal ROUND_HALF_EVEN to fen, separately per fee, cumulative within one order.
This module does not use network, secrets or historical performance results.
"""
from calendar import monthrange
from datetime import date
from decimal import Decimal as D, ROUND_HALF_EVEN

def decimal(value):
    if isinstance(value,(float,bool)): raise ValueError('EXACT_DECIMAL_REQUIRED')
    result=D(value)
    if not result.is_finite() or result<0: raise ValueError('NONNEGATIVE_FINITE_REQUIRED')
    return result

def fen(value):
    return int((decimal(value)*100).quantize(D(1), rounding=ROUND_HALF_EVEN))

def cumulative_fees(notional_cents, side, session):
    if type(notional_cents) is not int or notional_cents<0 or side not in ('BUY','SELL'):
        raise ValueError('FEE_INPUT_INVALID')
    date.fromisoformat(session)
    if session<'2021-01-01': raise ValueError('UNREGISTERED_COST_DATE')
    amount=D(notional_cents)/100
    stamp=D('.0005') if session>='2023-08-28' else D('.001')
    transfer=D('.00001') if session>='2022-04-29' else D('.00002')
    return {
        'commission_cents':max(500,fen(amount*D('.00025'))) if notional_cents else 0,
        'stamp_cents':fen(amount*stamp) if side=='SELL' else 0,
        'transfer_cents':fen(amount*transfer),
    }

def partial_fill_fees(prior_notional_cents, new_notional_cents, side, session):
    """The order owns prior notional; polling itself is never a fill."""
    if type(new_notional_cents) is not int or new_notional_cents<=0:
        raise ValueError('POSITIVE_EXECUTION_REQUIRED')
    before=cumulative_fees(prior_notional_cents,side,session)
    after=cumulative_fees(prior_notional_cents+new_notional_cents,side,session)
    return {k:after[k]-before[k] for k in after}

def anniversary(day, months):
    month=day.year*12+day.month-1+months
    year,m=divmod(month,12);m+=1
    return date(year,m,min(day.day,monthrange(year,m)[1]))

def dividend_rate(acquired, delivered):
    """Calendar-month holding convention, delivery date excludes that day's holding.

    Equal month/year anniversary remains inclusive boundary (20% / 10%).
    Only ordinary unrestricted SH/SZ shares acquired on public markets.
    """
    start,end=date.fromisoformat(acquired),date.fromisoformat(delivered)
    if end<=start: raise ValueError('T_PLUS_ONE_REQUIRED')
    if end<=anniversary(start,1): return D('.20')
    if end<=anniversary(start,12): return D('.10')
    return D('0')

def dividend_tax_for_sale(lots, quantity, delivered):
    """Read-only FIFO tax estimate for dividend rights attached to sold shares.

    Lots: acquisition date, quantity and gross dividend per share entitlements.
    An unpaid dividend still accrues a tax payable; reserve it at sale. Corporate
    actions lacking tax basis (e.g. taxable stock dividend) block separately.
    """
    remaining=quantity;items=[]
    if type(quantity) is not int or quantity<=0: raise ValueError('QUANTITY_REQUIRED')
    for lot in sorted(lots,key=lambda x:(x['acquired'],x['lot_id'])):
        take=min(remaining,lot['quantity'])
        if take<=0: continue
        rate=dividend_rate(lot['acquired'],delivered)
        gross=sum((decimal(x['gross_cash_per_share']) for x in lot.get('dividends',[])),D(0))*take
        items.append(dict(lot_id=lot['lot_id'],quantity=take,rate=str(rate),
                          tax_cents=fen(gross*rate)))
        remaining-=take
        if not remaining: break
    if remaining: raise ValueError('INSUFFICIENT_FIFO_QUANTITY')
    return {'tax_cents':sum(x['tax_cents'] for x in items),'lots':items,
            'label':'SIMULATED_DIFFERENTIATED_DIVIDEND_TAX_NOT_BROKER_ASSESSMENT'}
