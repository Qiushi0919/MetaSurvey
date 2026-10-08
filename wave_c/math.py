"""Pure Decimal research math. No trust, scores-to-trades or external state."""
from decimal import Decimal, localcontext, ROUND_HALF_EVEN

def num(value):
    if type(value) is not str:raise ValueError('WAVE_C_DECIMAL_STRING_REQUIRED')
    d=Decimal(value)
    if not d.is_finite() or abs(d.as_tuple().exponent)>64 or len(d.as_tuple().digits)>100:raise ValueError('WAVE_C_DECIMAL_INVALID')
    return d

def text(value):
    if value is None:return None
    with localcontext() as c:
        c.prec=50;c.rounding=ROUND_HALF_EVEN
        return format(value.quantize(Decimal('0.000001')),'f')

def raw_statistics(closes,amounts):
    if len(closes)<61:raise ValueError('WAVE_C_PRICE_WINDOW_INSUFFICIENT')
    with localcontext() as c:
        c.prec=50;c.rounding=ROUND_HALF_EVEN
        xs=[num(x) for x in closes]
        if any(x<=0 for x in xs):raise ValueError('WAVE_C_PRICE_INVALID')
        last=xs[-1];ma20=sum(xs[-20:])/20;ma60=sum(xs[-60:])/60
        changes=[(xs[i]/xs[i-1]-1)*100 for i in range(len(xs)-20,len(xs))]
        mean=sum(changes)/20;vol=(sum((x-mean)**2 for x in changes)/19).sqrt()
        peak=xs[-60];draw=Decimal(0)
        for x in xs[-60:]:peak=max(peak,x);draw=min(draw,(x/peak-1)*100)
        return {'last_raw_close':text(last),'raw_ma20':text(ma20),'raw_ma60':text(ma60),
          'raw_price_change_20_sessions_pct':text((last/xs[-21]-1)*100),'raw_price_change_60_sessions_pct':text((last/xs[-61]-1)*100),
          'distance_ma20_pct':text((last/ma20-1)*100),'distance_ma60_pct':text((last/ma60-1)*100),
          'raw_max_drawdown_60_sessions_pct':text(draw),'raw_daily_volatility_20_sessions_pct':text(vol),
          'reported_amount_mean20':text(sum(num(x) for x in amounts[-20:])/20)}

def pairwise_rank(values,direction='HIGHER'):
    if direction not in ('HIGHER','LOWER'):raise ValueError('WAVE_C_SCORE_DIRECTION_INVALID')
    if len(values)!=3 or any(x is None for x in values):return [None]*len(values)
    with localcontext() as c:
        c.prec=50;c.rounding=ROUND_HALF_EVEN
        xs=[num(x) for x in values];out=[]
        for i,x in enumerate(xs):
            wins=sum(Decimal('0.5') if x==y else Decimal(int((x>y) if direction=='HIGHER' else (x<y))) for j,y in enumerate(xs) if j!=i)
            out.append(text(wins*100/2))
        return out

def mean_score(values):
    if not values or any(x is None for x in values):return None
    with localcontext() as c:
        c.prec=50;c.rounding=ROUND_HALF_EVEN
        return text(sum(num(x) for x in values)/len(values))
