"""Versioned sizing from V1; actual ATR distance controls both stop and quantity."""
from decimal import Decimal as D, localcontext, ROUND_HALF_EVEN
from experiments.e2e_pilot_v1.execution import fee_for, cents, exact, quote, RULES

def build_portfolio(candidates, cash_cents, positions, nav_cents, fee_schedule, trade_date, atr_multiple):
    """Candidates are ranked upstream, price/ATR/lot explicit; no averaging down.

    Positions carry symbol/sector/quantity/mark_price. Gross caps use execution
    notional; cash and 1% planned loss include entry and estimated stop exit fees.
    Stop loss is planned risk, not a promise when markets gap or exits cannot fill.
    """
    with localcontext() as ctx:
        ctx.prec = 80
        if type(cash_cents) is not int or type(nav_cents) is not int or min(cash_cents, nav_cents) < 0:
            raise ValueError('INTEGER_CENTS_REQUIRED')
        if any(type(p.get('quantity')) is not int or p['quantity'] <= 0 for p in positions):
            raise ValueError('POSITIVE_INTEGER_POSITION_QUANTITY_REQUIRED')
        if len({p['symbol'] for p in positions}) != len(positions):
            raise ValueError('DUPLICATE_POSITION')
        profile = fee_for(fee_schedule, trade_date)
        invested = sum(cents(exact(p['mark_price'], D('0.01')) * p['quantity']) for p in positions)
        sectors = {}
        for p in positions:
            sectors[p['sector']] = sectors.get(p['sector'], 0) + cents(exact(p['mark_price']) * p['quantity'])
        held = {p['symbol'] for p in positions}
        passive_breach = (any(cents(exact(p['mark_price'])*p['quantity']) > int(nav_cents*D('0.20')) for p in positions)
                          or any(value > int(nav_cents*D('0.40')) for value in sectors.values()))
        accepted, rejected = [], []
        seen = set()
        for candidate in candidates:
            symbol, sector = candidate['symbol'], candidate['sector']
            if symbol in seen:
                rejected.append({'symbol': symbol, 'reason': 'DUPLICATE_CANDIDATE'}); continue
            seen.add(symbol)
            reason = None
            if symbol in held: reason = 'NO_AVERAGING_OR_SAME_DAY_REENTRY'
            elif passive_breach: reason = 'PASSIVE_POSITION_OR_SECTOR_CAP'
            elif len(held) >= RULES['maximum_positions']: reason = 'POSITION_COUNT_LIMIT'
            elif invested >= int(nav_cents * D(RULES['invested_fraction'])): reason = 'PASSIVE_OR_ACTIVE_EXPOSURE_CAP'
            elif sectors.get(sector, 0) >= int(nav_cents * D(RULES['sector_new_fraction'])): reason = 'SECTOR_CAP'
            if reason:
                rejected.append({'symbol': symbol, 'reason': reason}); continue
            price, atr = exact(candidate['price'], D('0.01')), exact(candidate['atr20'], D('0.000001'))
            lot = candidate['lot_size']
            if type(lot) is not int or lot < 1: raise ValueError('HISTORICAL_LOT_REQUIRED')
            # Bound the loop by both cash/caps and declared previous-session volume.
            budget = min(cash_cents, int(nav_cents * D('0.20')),
                         int(nav_cents * D('0.60')) - invested,
                         int(nav_cents * D('0.40')) - sectors.get(sector, 0))
            maximum = int(D(budget) / (price * 100) / lot) * lot
            volume = exact(candidate['previous20_median_volume_shares'], 0)
            maximum = min(maximum, int(volume * D(RULES['maximum_volume_participation']) / lot) * lot)
            chosen = None
            for qty in range(maximum, 0, -lot):
                buy = quote(str(price), qty, 'BUY', trade_date, profile)
                execution = D(buy['execution_price'])
                stop = (execution - D(atr_multiple) * atr).quantize(D('0.01'), rounding=ROUND_HALF_EVEN)
                if stop <= 0: continue
                sell = quote(str(stop), qty, 'SELL', trade_date, profile)
                risk = -buy['cash_delta_cents'] - sell['cash_delta_cents']
                notional = buy['fees']['notional_cents']
                if (-buy['cash_delta_cents'] <= cash_cents and notional <= budget
                        and risk <= int(nav_cents * D('0.01'))):
                    chosen = dict(symbol=symbol, sector=sector, quantity=qty, stop_price=str(stop),
                                  planned_loss_cents=risk, entry=buy, estimated_stop_exit=sell,
                                  atr20=str(atr), lot_size=lot)
                    break
            if chosen is None:
                rejected.append({'symbol': symbol, 'reason': 'RISK_CASH_LOT_OR_VOLUME_UNAFFORDABLE'}); continue
            accepted.append(chosen)
            cash_cents += chosen['entry']['cash_delta_cents']
            invested += chosen['entry']['fees']['notional_cents']
            sectors[sector] = sectors.get(sector, 0) + chosen['entry']['fees']['notional_cents']
            held.add(symbol)
        return {'plans': accepted, 'rejections': rejected, 'remaining_cash_cents': cash_cents,
                'invested_cents': invested, 'cost_label': 'SIMULATED_COSTS', 'real_account': False}

