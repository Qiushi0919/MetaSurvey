"""Fail-closed realtime snapshot proxy. Not exchange or broker execution.

Only subsequent, fresh, source-timestamped snapshots can fill. Require positive
incremental traded volume as well as displayed side depth, when present.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal as D, ROUND_CEILING, ROUND_FLOOR
from .costs import decimal, fen, partial_fill_fees

def instant(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None: raise ValueError('TIMEZONE_REQUIRED')
    return result

def match(order, previous, current, now, available_cash_cents, sellable_quantity):
    def no(reason): return {'state':'UNFILLED','reason':reason}
    t=instant(now); submitted=instant(order['submitted_at'])
    if t>=instant(order['expires_at']): return no('ORDER_EXPIRED')
    if order['remaining_quantity']<=0: return no('ORDER_ALREADY_COMPLETE')
    if current.get('symbol')!=order['symbol'] or previous.get('symbol')!=order['symbol']:
        return no('SYMBOL_MISMATCH')
    if not current.get('source_at') or not previous.get('source_at'):
        return no('SOURCE_TIME_MISSING')
    ct,pt=instant(current['source_at']),instant(previous['source_at'])
    received=instant(current['received_at'])
    pr=instant(previous['received_at'])
    local=ct.astimezone(ZoneInfo('Asia/Shanghai'))
    if local.date().isoformat()!=order['session']: return no('ORDER_SESSION_MISMATCH')
    hm=(local.hour,local.minute)
    if not ((9,35)<=hm<(11,30) or (13,0)<=hm<(14,50)): return no('OUTSIDE_EXECUTION_WINDOW')
    if not pt<=pr<=received: return no('PREVIOUS_RECEIPT_CLOCK')
    if not submitted<pt<ct<=received<=t: return no('NON_CAUSAL_QUOTE')
    if (t-ct).total_seconds()>90: return no('STALE_MARKET_QUOTE')
    if ct.date()!=submitted.date(): return no('WRONG_EXECUTION_DATE')
    if current.get('status')!='TRADABLE' or current.get('state_evidence_verified') is not True:
        return no('TRADING_STATUS_UNVERIFIED')
    if current.get('limits_evidence_verified') is not True: return no('PRICE_LIMITS_UNVERIFIED')
    if previous.get('volume_unit')!='SHARES' or current.get('volume_unit')!='SHARES':
        return no('VOLUME_UNIT_UNVERIFIED')
    if any(type(q.get('volume')) is not int or q['volume']<0 for q in (previous,current)):
        return no('INTEGER_SHARE_VOLUME_REQUIRED')
    delta=decimal(current['volume'])-decimal(previous['volume'])
    if delta<=0: return no('NO_INCREMENTAL_MARKET_VOLUME')
    side=order['side'];ask='ask' if side=='BUY' else 'bid'
    book=bool(current.get(ask+'_price')) and current.get(ask+'_quantity',0)>0
    raw=decimal(current[ask+'_price'] if book else current['last'])
    price=(raw*(D('1.001') if side=='BUY' else D('.999'))).quantize(
        D('.01'),rounding=ROUND_CEILING if side=='BUY' else ROUND_FLOOR)
    if price<=decimal(current['down_limit']) or price>=decimal(current['up_limit']):
        return no('LIMIT_BOUNDARY_NO_FILL')
    if (side=='BUY' and price>decimal(order['limit_price'])) or (side=='SELL' and price<decimal(order['limit_price'])):
        return no('ORDER_PRICE_PROTECTION')
    # Latest-price proxy has no displayed depth: require 1% newly observed
    # market volume; with depth use min(10% depth, 1% incremental volume).
    capacity=int(delta*D('.01'))
    if book: capacity=min(capacity,int(decimal(current[ask+'_quantity'])*D('.10')))
    qty=min(order['remaining_quantity'],capacity)
    lot=order['lot_size']
    qty=qty//lot*lot
    if side=='SELL': qty=min(qty,sellable_quantity)
    if qty<=0: return no('INSUFFICIENT_CAUSAL_VOLUME_OR_T_PLUS_ONE')
    while qty>0:
        notional=fen(price*qty)
        fees=partial_fill_fees(order['filled_notional_cents'],notional,side,order['session'])
        delta_cash=(-notional if side=='BUY' else notional)-sum(fees.values())
        if available_cash_cents+delta_cash>=0: break
        qty-=lot
    if qty<=0: return no('FEE_INCLUSIVE_CASH_INSUFFICIENT')
    return {'state':'SIMULATED_FILL','quantity':qty,'price':str(price),
            'notional_cents':notional,'fees':fees,'cash_delta_cents':delta_cash,
            'source_at':current['source_at'],'received_at':current['received_at'],
            'model':'BOOK_DEPTH_AND_INCREMENTAL_VOLUME_PROXY' if book else 'LATEST_PRICE_INCREMENTAL_VOLUME_PROXY',
            'broker_execution':False}
