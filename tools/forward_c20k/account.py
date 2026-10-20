"""Integer-fen virtual account transitions. No broker or live money."""
from copy import deepcopy
from decimal import Decimal as D
from experiments.account20k_v1.costs import fen, dividend_tax_for_sale
from .store import ledger, digest, now

def reserve(account):
    account['frozen_cash_cents']=sum(o.get('reserve_cents',0) for o in account['orders'].values()
        if o['side']=='BUY' and o['state'] in ('SUBMITTED','PARTIALLY_FILLED'))
    account['tax_reserve_cents']=sum(fen(D(l['quantity'])*sum(
        (D(d['gross_cash_per_share']) for d in l.get('dividends',[])),D(0))*D('.20'))
        for p in account['positions'].values() for l in p['lots'])
    account['available_cash_cents']=account['cash_cents']-account['frozen_cash_cents']-account['tax_reserve_cents']
    if account['available_cash_cents']<0: raise ValueError('RESERVATION_EXCEEDS_CASH')

def apply_fill(account, order_id, fill, snapshot_hash):
    order=account['orders'][order_id]
    if snapshot_hash in order.get('consumed_snapshots',[]): raise ValueError('SNAPSHOT_ALREADY_CONSUMED')
    qty=fill['quantity'];symbol=order['symbol']
    if not 0<qty<=order['remaining_quantity']: raise ValueError('ORDER_QUANTITY')
    if order['side']=='BUY':
        p=account['positions'].setdefault(symbol,dict(sector=order['sector'],lots=[],
            entry_session=order['session'],entry_compare_price=fill['price'],
            stop_price=str(D(fill['price'])-D('2.5')*D(order['atr20'])),mark_price=fill['price']))
        p['lots'].append(dict(lot_id=order_id+'-'+str(len(account['fills'])),quantity=qty,
            acquired=order['session'],available_date=order['next_session'],dividends=[],
            acquisition_cost_cents=fill['notional_cents']+sum(fill['fees'].values())))
        # Partial fills share one entry: weighted actual execution price, not
        # whichever poll happened to fill first.
        total_qty=order['quantity']-order['remaining_quantity']+qty
        average=D(order['filled_notional_cents']+fill['notional_cents'])/100/total_qty
        p['entry_compare_price']=str(average)
        p['stop_price']=str(average-D('2.5')*D(order['atr20']))
        ledger(account,'SIMULATED_BUY',fill['cash_delta_cents'],order_id)
        order['reserve_cents']=max(0,order['reserve_cents']+fill['cash_delta_cents'])
    else:
        p=account['positions'][symbol]
        if sum(l['quantity'] for l in p['lots'] if l['available_date']<=order['session'])<qty:
            raise ValueError('T_PLUS_ONE')
        tax=dividend_tax_for_sale(p['lots'],qty,order['session'])
        ledger(account,'SIMULATED_SELL',fill['cash_delta_cents'],order_id)
        if tax['tax_cents']: ledger(account,'SIMULATED_DIVIDEND_TAX',-tax['tax_cents'],order_id)
        remaining=qty;cost=0
        for lot in sorted(p['lots'],key=lambda l:(l['acquired'],l['lot_id'])):
            take=min(remaining,lot['quantity'])
            if take:
                allocated=int(D(lot['acquisition_cost_cents'])*take/lot['quantity'])
                lot['acquisition_cost_cents']-=allocated;cost+=allocated;lot['quantity']-=take;remaining-=take
        p['lots']=[l for l in p['lots'] if l['quantity']]
        if not p['lots']:del account['positions'][symbol]
        account['realized_pnl_cents']=account.get('realized_pnl_cents',0)+fill['cash_delta_cents']-cost-tax['tax_cents']
        fill=deepcopy(fill);fill['dividend_tax']=tax
    order['remaining_quantity']-=qty;order['filled_notional_cents']+=fill['notional_cents']
    order['state']='PARTIALLY_FILLED' if order['remaining_quantity'] else 'FILLED'
    if order['state']=='FILLED':order['reserve_cents']=0
    order.setdefault('consumed_snapshots',[]).append(snapshot_hash)
    account['fills'].append(dict(fill,order_id=order_id,at=now(),snapshot_hash=snapshot_hash))
    reserve(account)

def open_actions(account,actions,session):
    rights=account.setdefault('dividend_rights',{})
    for action in actions:
        aid=action['id'];sym=action['symbol'];p=account['positions'].get(sym)
        if action['ex_date']!=session or not p:continue
        if D(action['bonus_ratio']) or D(action['split_ratio'])!=1:
            raise ValueError('UNSUPPORTED_SHARE_DISTRIBUTION_TAX_BASIS:'+aid)
        if aid not in rights:raise ValueError('MISSING_PRIOR_DIVIDEND_ENTITLEMENT:'+aid)
        if not rights[aid].get('adjusted'):
            p['stop_price']=str(D(p['stop_price'])-D(action['cash_per_share']))
            p['entry_compare_price']=str(D(p['entry_compare_price'])-D(action['cash_per_share']))
            p['mark_price']=str(D(p['mark_price'])-D(action['cash_per_share']))
            rights[aid]['adjusted']=True
    for aid,r in rights.items():
        if not r['paid'] and r['pay_date'] and r['pay_date']<=session:
            ledger(account,'GROSS_DIVIDEND_PAYMENT',r['gross_cents'],aid);r['paid']=True
            account['dividends'].append(dict(id=aid,event='PAY',session=session,gross_cents=r['gross_cents']))
    reserve(account)

def mark_current(account,session):
    exposure=sum(fen(D(p['mark_price'])*sum(l['quantity'] for l in p['lots'])) for p in account['positions'].values())
    receivable=sum(r['gross_cents'] for r in account.get('dividend_rights',{}).values() if not r['paid'] and r['ex_date']<=session)
    account.update(exposure_cents=exposure,receivable_cents=receivable,
                   nav_cents=account['cash_cents']+exposure+receivable)
    account['net_of_contingent_tax_nav_cents']=account['nav_cents']-account.get('tax_reserve_cents',0)
    cost=sum(l['acquisition_cost_cents'] for p in account['positions'].values() for l in p['lots'])
    account['unrealized_pnl_cents']=exposure-cost
    account['total_fees_cents']=sum(sum(f['fees'].values()) for f in account['fills'])
    account['net_return']=str(D(account['nav_cents'])/2000000-1)

def reconcile_close(account,case,session):
    """Process only actual days, using the independently validated raw Case.

    Cash dividends accrue gross, pay on evidenced date; FIFO disposal assesses
    tax. An estimated 20% tax reserve limits spending, never claims actual tax.
    Unsupported share distributions block instead of inventing cost/tax basis.
    """
    rows={(b['session'],b['symbol']):b for b in case['bars']}
    previous=account.get('last_close_session')
    days=[x['date'] for x in case['calendar'] if (previous is None and x['date']==session)
          or (previous is not None and previous<x['date']<=session)]
    rights=account.setdefault('dividend_rights',{})
    for day in days:
        for action in case['actions']:
            aid=action['id'];sym=action['symbol'];p=account['positions'].get(sym)
            if action['record_date']==day and p and aid not in rights:
                if D(action['bonus_ratio']) or D(action['split_ratio'])!=1:
                    raise ValueError('UNSUPPORTED_SHARE_DISTRIBUTION_TAX_BASIS:'+aid)
                qty=sum(l['quantity'] for l in p['lots'] if l['acquired']<=day)
                rights[aid]=dict(symbol=sym,quantity=qty,gross_cents=fen(D(qty)*D(action['cash_per_share'])),
                    ex_date=action['ex_date'],pay_date=action['pay_date'],paid=False)
                for lot in p['lots']:
                    if lot['acquired']<=day:
                        lot.setdefault('dividends',[]).append(dict(id=aid,gross_cash_per_share=action['cash_per_share']))
                account['dividends'].append(dict(id=aid,event='RECORD',session=day,quantity=qty))
            if action['ex_date']==day and p and aid in rights and not rights[aid].get('adjusted'):
                p['stop_price']=str(D(p['stop_price'])-D(action['cash_per_share']))
                p['entry_compare_price']=str(D(p['entry_compare_price'])-D(action['cash_per_share']))
                rights[aid]['adjusted']=True
        for aid,right in rights.items():
            if not right['paid'] and right['pay_date'] and right['pay_date']<=day:
                ledger(account,'GROSS_DIVIDEND_PAYMENT',right['gross_cents'],aid);right['paid']=True
                account['dividends'].append(dict(id=aid,event='PAY',session=day,gross_cents=right['gross_cents']))
        for sym,p in account['positions'].items():
            bar=rows[day,sym]
            if bar['status']=='TRADABLE':p['mark_price']=bar['close']
        account['last_close_session']=day
    reserve(account)
    mark_current(account,session)
    account['peak_cents']=max(account['peak_cents'],account['nav_cents'])
    dd=D(account['peak_cents']-account['nav_cents'])/account['peak_cents']
    account['maximum_drawdown']=str(max(D(account['maximum_drawdown']),dd))
