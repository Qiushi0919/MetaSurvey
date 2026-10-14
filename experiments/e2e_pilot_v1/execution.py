"""Isolated E2E pilot: deterministic sizing and fail-closed historical diagnostic.

No network, credentials, database, broker, optimizer or old artifact mutation.
Public entry points:
  build_portfolio(candidates, cash_cents, positions, nav_cents, fee_schedule, trade_date)
  run_diagnostic(case)
Case shape is illustrated by tests/test_execution.py::case(). Required keys:
namespace,strategy_id,label,run_id,rules,rules_hash,preregistration_ref,frozen_at,
run_at,admission,admission_hash,calendar,universe,window,bars,fee_schedule.
Real cases also require method_ref raw SHA256 and calendar_coverage containing
start/end and every civil date with explicit is_open boolean and evidence_ref.
Real cases bind preregistration_ref to raw SHA256 of protocol.json and exactly
match protocol.frozen_at/fee_schedule. Admission false values return every
admission gap before invoking the engine. Synthetic and historical are distinct.
Caller must verify source/purpose admission before constructing case; a hash is
integrity only, never license evidence. Costs reuse the existing pure hypothetical
fee helper, retaining its HALF_EVEN contract. All orders/fills are simulations.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext, ROUND_FLOOR, ROUND_HALF_EVEN
from hashlib import sha256
from pathlib import Path
from statistics import median
import json
import re

from backtest_5y.economics import quote_hypothetical

NAMESPACE = 'EXPERIMENT:CORE40:E2E_PILOT_V1'
STRATEGY = 'CORE40_E2E_PRICE_VOLUME_DIAGNOSTIC_V1'
D = Decimal
RULES = {
    'initial_cash_cents': 10000000, 'maximum_positions': 3,
    'single_open_fraction': '0.20', 'invested_fraction': '0.60',
    'sector_new_fraction': '0.40', 'planned_loss_fraction': '0.01',
    'atr_sessions': 20, 'atr_multiplier': '2', 'relative_strength_sessions': 20,
    'stage_exit_sessions': 20, 'terminal_exit_sessions': 40,
    'entry': 'PRIOR_20_HIGH_BREAKOUT_OR_SMA20_PULLBACK_ABOVE_SMA20',
    'selection': 'TOP2_POSITIVE_EQUAL_WEIGHT_SAMPLE_SECTOR_RS20_THEN_COMPANY_EXCESS_RS20',
    'pullback': 'ALSO_CLOSE_GREATER_THAN_PREVIOUS_CLOSE',
    'entry_tail_sessions': 40,
    'entry_expiry': 'NEXT_EXCHANGE_SESSION_ONLY',
    'stop': 'CLOSE_TRIGGER_NEXT_EXECUTABLE_OPEN_RETRY_UNTIL_FILLED',
    'cash_order': 'SELL_FIRST_THEN_BUY_SORTED_BY_FROZEN_RANK',
    'passive_breach': 'HOLD_NO_FORCED_SALE_BLOCK_NEW_BUYS',
    'terminal': 'MARK_OPEN_POSITIONS_NO_FORCED_LIQUIDATION',
    'execution': 'DAILY_OPEN_PROXY_CONSERVATIVE_LIMIT_TOUCH_BLOCK',
    'corporate_actions': 'EVIDENCED_NONE_ONLY_OTHER_ACTIONS_BLOCK',
    'commission_scope': 'PER_ORDER', 'money_rounding': 'HALF_EVEN',
    'maximum_volume_participation': '0.01',
}


class PreflightError(ValueError):
    def __init__(self, reasons):
        self.reasons = reasons
        super().__init__(';'.join(reasons))


def digest(obj):
    return 'sha256:' + sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def exact(value, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError('EXACT_DECIMAL_REQUIRED')
    result = D(value)
    if not result.is_finite() or len(result.as_tuple().digits) > 40 or abs(result.as_tuple().exponent) > 20:
        raise ValueError('FINITE_BOUNDED_DECIMAL_REQUIRED')
    if minimum is not None and result < minimum:
        raise ValueError('DECIMAL_BELOW_MINIMUM')
    return result


def cents(value):
    return int((value * 100).quantize(D(1), rounding=ROUND_HALF_EVEN))


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('TIMEZONE_REQUIRED')
    return result


def fee_for(schedule, day):
    candidates = [x for x in schedule if x['effective_from'] <= day <= x['effective_until']]
    if len(candidates) != 1:
        raise ValueError('EXACTLY_ONE_DATED_FEE_PROFILE_REQUIRED')
    return candidates[0]


def quote(price, qty, side, day, profile):
    result = quote_hypothetical(price, qty, side, day, profile)
    if result['state'] != 'COMPUTABLE_HYPOTHETICAL':
        raise ValueError('COST_NOT_COMPUTABLE:' + ','.join(result['reason_codes']))
    return result


def build_portfolio(candidates, cash_cents, positions, nav_cents, fee_schedule, trade_date):
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
                stop = (execution - D(2) * atr).quantize(D('0.01'), rounding=ROUND_HALF_EVEN)
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


def _validate(case):
    if case.get('namespace') != NAMESPACE or case.get('strategy_id') != STRATEGY:
        raise ValueError('EXPERIMENT_IDENTITY_MISMATCH')
    if case.get('label') not in ('HISTORICAL_DIAGNOSTIC', 'SYNTHETIC_ENGINE_TEST'):
        raise ValueError('DIAGNOSTIC_LABEL_REQUIRED')
    if case.get('rules') != RULES or case.get('rules_hash') != digest(RULES):
        raise ValueError('FROZEN_RULES_MISMATCH')
    if not case.get('preregistration_ref') or instant(case['frozen_at']) > instant(case['run_at']):
        raise ValueError('PREREGISTRATION_REQUIRED')
    if case['label'] == 'HISTORICAL_DIAGNOSTIC':
        protocol_bytes = Path(__file__).with_name('protocol.json').read_bytes()
        protocol = json.loads(protocol_bytes)
        if case['preregistration_ref'] != 'sha256:' + sha256(protocol_bytes).hexdigest():
            raise ValueError('REAL_PROTOCOL_HASH_REQUIRED')
        if case['frozen_at'] != protocol['frozen_at'] or case['fee_schedule'] != protocol['fee_schedule']:
            raise ValueError('REAL_PROTOCOL_OR_COST_MISMATCH')
        method_bytes = Path(__file__).with_name('method.json').read_bytes()
        if case.get('method_ref') != 'sha256:' + sha256(method_bytes).hexdigest():
            raise ValueError('REAL_METHOD_HASH_REQUIRED')
    admission = case['admission']
    if case.get('admission_hash') != digest(admission): raise ValueError('ADMISSION_HASH_MISMATCH')
    admission_gaps = ['ADMISSION_REQUIRED:' + field for field in (
        'license_for_local_historical_diagnostic', 'historical_price_visibility',
        'calendar_complete', 'execution_domains_complete', 'membership_scope_explicit')
        if admission.get(field) is not True]
    if admission_gaps: raise PreflightError(admission_gaps)
    if not all(admission.get(x) for x in ('source', 'product', 'purpose', 'evidence_refs')):
        raise ValueError('SOURCE_PURPOSE_EVIDENCE_REQUIRED')
    if case['label'] == 'HISTORICAL_DIAGNOSTIC' and admission.get('evidence_kind') == 'SYNTHETIC':
        raise ValueError('SYNTHETIC_CANNOT_ADMIT_REAL')
    calendar = case['calendar']
    dates = [x['date'] for x in calendar]
    if not dates or dates != sorted(set(dates)): raise ValueError('CALENDAR_UNIQUE_ORDER_REQUIRED')
    for day in calendar:
        date.fromisoformat(day['date'])
        if not instant(day['open_at']) < instant(day['close_at']): raise ValueError('CALENDAR_CLOCK_INVALID')
        if not day['evidence_ref']: raise ValueError('CALENDAR_EVIDENCE_REQUIRED')
    if case['label'] == 'HISTORICAL_DIAGNOSTIC':
        _real_scope(case, protocol, json.loads(method_bytes), dates)
    universe = case['universe']
    if not universe or len({x['symbol'] for x in universe}) != len(universe): raise ValueError('UNIVERSE_INVALID')
    if any(not x.get('sector') or not x.get('selection_evidence_ref') for x in universe): raise ValueError('UNIVERSE_EVIDENCE_REQUIRED')
    first, last = case['window']['first_session'], case['window']['last_session']
    if first not in dates or last not in dates or first > last or dates.index(first) < 20:
        raise ValueError('CONTINUOUS_WINDOW_OR_WARMUP_MISSING')
    bars = {}
    for row in case['bars']:
        key = row['session'], row['symbol']
        if key in bars: raise ValueError('DUPLICATE_BAR')
        bars[key] = row
    for index, day in enumerate(calendar):
        for member in universe:
            row = bars[(day['date'], member['symbol'])]
            if row['price_kind'] != 'RAW' or row['status'] not in ('TRADABLE', 'SUSPENDED'):
                raise ValueError('UNKNOWN_EXECUTION_STATUS_OR_PRICE_BASIS')
            if row['action_status'] != 'NONE_VERIFIED': raise ValueError('CORPORATE_ACTION_UNSUPPORTED_OR_UNKNOWN')
            if type(row['lot_size']) is not int or row['lot_size'] <= 0: raise ValueError('HISTORICAL_LOT_REQUIRED')
            if row['listing_status'] != 'ACTIVE' or row['st_status'] not in ('NORMAL', 'ST'):
                raise ValueError('LISTING_OR_ST_UNKNOWN')
            for kind in ('price', 'status', 'lot', 'action', 'limit'):
                proof = row['evidence'][kind]
                if not all(proof.get(x) for x in ('source_ref', 'source_hash', 'source_version',
                                                   'event_time', 'published_at', 'available_at', 'retrieved_at', 'historical_visible_at')):
                    raise ValueError('EXECUTION_EVIDENCE_INCOMPLETE:' + kind)
                if not re.fullmatch(r'sha256:[0-9a-f]{64}', proof['source_hash']):
                    raise ValueError('SOURCE_HASH_INVALID')
                clocks = {x: instant(proof[x]) for x in ('event_time', 'published_at', 'available_at', 'retrieved_at', 'historical_visible_at')}
                cutoff = instant(day['close_at'] if kind == 'price' else day['open_at'])
                if max(clocks['historical_visible_at'], clocks['available_at'], clocks['event_time']) > cutoff: raise ValueError('FUTURE_DATA:' + kind)
                if clocks['published_at'] > clocks['historical_visible_at']: raise ValueError('VISIBILITY_PRECEDES_PUBLICATION')
                if clocks['available_at'] > clocks['retrieved_at']: raise ValueError('CAPTURE_CLOCK_CONFLICT')
            values = {k: exact(row[k], D('0.01')) for k in ('open', 'high', 'low', 'close', 'lower_limit', 'upper_limit')}
            if any(v % D('0.01') for v in values.values()): raise ValueError('CENT_TICK_REQUIRED')
            if values['low'] > min(values['open'], values['close']) or values['high'] < max(values['open'], values['close']):
                raise ValueError('OHLC_INVALID')
            if values['lower_limit'] >= values['upper_limit']: raise ValueError('LIMIT_BOUNDS_INVALID')
            if values['low'] < values['lower_limit'] or values['high'] > values['upper_limit']:
                raise ValueError('PRICE_OUTSIDE_LIMITS')
            exact(row['volume_shares'], 0)
            if index and exact(row['previous_close']) != exact(bars[(dates[index-1], member['symbol'])]['close']):
                raise ValueError('PREVIOUS_RAW_CLOSE_MISMATCH')
        quote('1.00', 100, 'BUY', day['date'], fee_for(case['fee_schedule'], day['date']))
    return calendar, bars



def _real_scope(case, protocol, method, dates):
    """Bind real runs to frozen peers and every declared exchange calendar day.

    Daily coverage is source evidence, not a generated weekday calendar. We only
    generate expected civil dates to detect omissions; is_open must be supplied.
    """
    expected_members = {member['symbol']: sector['id']
                        for sector in method['universe'] for member in sector['members']}
    actual_members = {member['symbol']: member['sector'] for member in case['universe']}
    if actual_members != expected_members or len(case['universe']) != len(expected_members):
        raise ValueError('REAL_FROZEN_UNIVERSE_MISMATCH')
    target = protocol['target_window']
    coverage = case.get('calendar_coverage')
    if not isinstance(coverage, dict) or coverage.get('start') != target['warmup_start'] or coverage.get('end') != target['end']:
        raise ValueError('REAL_COMPLETE_CALENDAR_COVERAGE_REQUIRED')
    rows = coverage.get('days', [])
    start, end = date.fromisoformat(target['warmup_start']), date.fromisoformat(target['end'])
    expected_dates = [(start+timedelta(days=n)).isoformat() for n in range((end-start).days+1)]
    if [row.get('date') for row in rows] != expected_dates:
        raise ValueError('REAL_CALENDAR_CIVIL_DATE_GAP_OR_TRUNCATION')
    if any(type(row.get('is_open')) is not bool or not row.get('evidence_ref') for row in rows):
        raise ValueError('REAL_CALENDAR_DAY_STATUS_EVIDENCE_REQUIRED')
    open_dates = [row['date'] for row in rows if row['is_open']]
    if dates != open_dates:
        raise ValueError('REAL_EXCHANGE_SESSIONS_MISMATCH')
    active = [day for day in open_dates if target['start'] <= day <= target['end']]
    if not active or case['window'] != {'first_session': active[0], 'last_session': active[-1]}:
        raise ValueError('REAL_PREREGISTERED_WINDOW_MISMATCH')
    if len([day for day in open_dates if day < active[0]]) < 20:
        raise ValueError('REAL_WARMUP_INCOMPLETE')


def _features(rows):
    if len(rows) < 21: return None
    close = D(rows[-1]['close'])
    atr = sum(max(D(row['high'])-D(row['low']), abs(D(row['high'])-D(previous['close'])),
                  abs(D(row['low'])-D(previous['close']))) for previous, row in zip(rows[-21:-1], rows[-20:])) / 20
    sma = sum(D(row['close']) for row in rows[-20:]) / 20
    rs = close / D(rows[-21]['close']) - 1
    entry = close > max(D(row['high']) for row in rows[-21:-1]) or (close > sma and D(rows[-1]['low']) <= sma and close > D(rows[-2]['close']))
    return dict(atr20=atr, sma20=sma, rs20=rs, eligible=entry and atr > 0)


def _no_fill(row, quote_result):
    if row['status'] != 'TRADABLE': return 'SUSPENDED'
    price = D(quote_result['execution_price'])
    if price <= D(row['lower_limit']) or price >= D(row['upper_limit']): return 'LIMIT_OR_SLIPPAGE_BOUND'
    if D(row['open']) <= D(row['lower_limit']) or D(row['open']) >= D(row['upper_limit']): return 'OPEN_AT_LIMIT'
    if price < D(row['low']) or price > D(row['high']): return 'SLIPPAGE_PRICE_OUTSIDE_DAILY_RANGE'
    if quote_result['quantity'] > int(D(row['volume_shares']) * D(RULES['maximum_volume_participation'])):
        return 'ACTUAL_SESSION_VOLUME_CAP'
    return None


def run_diagnostic(case):
    """Attempt once; report failed preflight without claiming engine ran.

    Explicit status separates DATA_BLOCKED, RUN_NO_TRADES, SIMULATED_TRADES.
    Input hashes/proofs are retained; external adapter, not this arithmetic,
    establishes legal source admission and authentic historical visibility.
    """
    base = {'version': '1.0.0', 'namespace': NAMESPACE, 'strategy_id': STRATEGY,
            'run_id': case.get('run_id'), 'run_attempted': True, 'engine_called': False,
            'label': case.get('label'), 'cost_label': 'SIMULATED_COSTS',
            'untouched_oos': False, 'formal_five_year_validation': False,
            'production_enabled': False, 'real_account': False, 'native_orders': False,
            'rules_hash': digest(RULES), 'input_hash': digest(case),
            'fills': [], 'unfilled': [], 'ledger': [], 'equity': [], 'decisions': [],
            'complete_trades': 0, 'net_return': None, 'maximum_drawdown': None}
    try:
        with localcontext() as ctx:
            ctx.prec = 80
            calendar, bars = _validate(case)
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        return {**base, 'status': 'DATA_BLOCKED', 'reason_codes': getattr(exc, 'reasons', [str(exc)]), 'errors': [type(exc).__name__ + ':' + str(exc)]}
    try:
        with localcontext() as ctx:
            ctx.prec = 80
            return _run(case, calendar, bars, base)
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        return {**base, 'status': 'ENGINE_FAILED', 'engine_called': True, 'reason_codes': [str(exc)],
                'errors': [type(exc).__name__ + ':' + str(exc)], 'partial_run_invalid': True}


def _run(case, calendar, bars, base):
    result = deepcopy(base)
    result.update(engine_called=True, status='RUN_NO_TRADES', reason_codes=[], errors=[])
    cash, positions, pending_buys, pending_sells = RULES['initial_cash_cents'], {}, [], {}
    sectors = {m['symbol']: m['sector'] for m in case['universe']}
    dates = [d['date'] for d in calendar]
    first, last = case['window']['first_session'], case['window']['last_session']
    history = {symbol: [] for symbol in sectors}
    peak = RULES['initial_cash_cents']; max_dd = D(0)
    def record(day, symbol, side, value, reason):
        nonlocal cash
        before = cash; cash += value['cash_delta_cents']
        entry = {'sequence': len(result['ledger']), 'session': day, 'symbol': symbol, 'side': side,
                 'reason': reason, 'quantity': value['quantity'], 'execution_price': value['execution_price'],
                 'cash_before_cents': before, 'cash_delta_cents': value['cash_delta_cents'],
                 'cash_after_cents': cash, 'fees': value['fees'], 'label': case['label'],
                 'cost_label': 'SIMULATED_COSTS', 'previous_hash': result['ledger'][-1]['content_hash'] if result['ledger'] else digest({'initial_cash_cents': cash-value['cash_delta_cents']})}
        entry['content_hash'] = digest(entry)
        result['ledger'].append(entry); result['fills'].append(deepcopy(entry))
    for index, day_meta in enumerate(calendar):
        day = day_meta['date']
        if day > last: break
        if day >= first:
            profile = fee_for(case['fee_schedule'], day)
            sold_today = set()
            for symbol, reason in sorted(list(pending_sells.items())):
                pos, row = positions[symbol], bars[(day, symbol)]
                sale = quote(row['open'], pos['quantity'], 'SELL', day, profile)
                rejection = 'T_PLUS_ONE' if index <= pos['entry_index'] else _no_fill(row, sale)
                if cash + sale['cash_delta_cents'] < 0: rejection = 'EXIT_FEES_EXCEED_CASH'
                if rejection:
                    result['unfilled'].append(dict(session=day, symbol=symbol, side='SELL', reason=rejection, retained_quantity=pos['quantity']))
                    continue
                record(day, symbol, 'SELL', sale, reason)
                result['complete_trades'] += 1
                del positions[symbol]; del pending_sells[symbol]; sold_today.add(symbol)
            # NAV/risk sizing uses prior close (not today's unseen closing price).
            marked = [dict(symbol=s, sector=p['sector'], quantity=p['quantity'], mark_price=history[s][-1]['close']) for s, p in positions.items()]
            nav = cash + sum(cents(D(p['mark_price'])*p['quantity']) for p in marked)
            for pending in pending_buys:
                symbol = pending['symbol']; row = bars[(day, symbol)]
                if symbol in sold_today:
                    result['unfilled'].append(dict(session=day, symbol=symbol, side='BUY', reason='NO_SAME_DAY_REENTRY')); continue
                candidate = {**pending, 'price': row['open'], 'lot_size': row['lot_size']}
                nav = cash + sum(cents(D(p['mark_price'])*p['quantity']) for p in marked)
                allocation = build_portfolio([candidate], cash, marked, nav, case['fee_schedule'], day)
                if not allocation['plans']:
                    result['unfilled'].append(dict(session=day, symbol=symbol, side='BUY', reason=allocation['rejections'][0]['reason'])); continue
                plan = allocation['plans'][0]; buy = plan['entry']
                rejection = _no_fill(row, buy)
                if rejection:
                    result['unfilled'].append(dict(session=day, symbol=symbol, side='BUY', reason=rejection)); continue
                record(day, symbol, 'BUY', buy, 'FROZEN_CLOSE_SIGNAL')
                positions[symbol] = dict(sector=sectors[symbol], quantity=plan['quantity'], entry_index=index,
                                         entry_price=buy['execution_price'], stop_price=plan['stop_price'], planned_loss_cents=plan['planned_loss_cents'])
                marked.append(dict(symbol=symbol, sector=sectors[symbol], quantity=plan['quantity'], mark_price=buy['execution_price']))
            pending_buys = []
        for symbol in sectors: history[symbol].append(bars[(day, symbol)])
        if day < first: continue
        features = {symbol: _features(history[symbol]) for symbol in sectors}
        for symbol, pos in positions.items():
            feature = features[symbol]; close = D(bars[(day, symbol)]['close'])
            age = index-pos['entry_index']+1
            reason = None
            if close <= D(pos['stop_price']): reason = 'CLOSE_STOP_2_ATR20'
            elif close < feature['sma20']: reason = 'CLOSE_LOGIC_INVALIDATION_SMA20'
            elif age >= 40: reason = 'MAXIMUM_40_SESSIONS'
            elif age >= 20 and close <= D(pos['entry_price']): reason = 'DAY20_NONPOSITIVE_PRICE_RETURN'
            if reason: pending_sells.setdefault(symbol, reason)
        sector_rs = {}
        for sector in set(sectors.values()):
            members = [features[s]['rs20'] for s in sectors if sectors[s] == sector]
            sector_rs[sector] = sum(members) / len(members)
        selected_sectors = sorted([s for s in sector_rs if sector_rs[s] > 0], key=lambda s: (-sector_rs[s],s))[:2]
        candidates = sorted([s for s in sectors if features[s]['eligible'] and sectors[s] in selected_sectors and s not in positions],
                            key=lambda s: (selected_sectors.index(sectors[s]), -(features[s]['rs20']-sector_rs[sectors[s]]), s))
        if dates.index(last) - index <= RULES['entry_tail_sessions']:
            candidates = []
        pending_buys = [dict(symbol=s, sector=sectors[s], atr20=str(features[s]['atr20']),
                            previous20_median_volume_shares=str(median(D(r['volume_shares']) for r in history[s][-20:]))) for s in candidates]
        result['decisions'].append({'session': day, 'cutoff': day_meta['close_at'],
                                    'next_session': dates[index+1] if index+1 < len(dates) else None,
                                    'sector_sample_rs20': {k: str(v) for k,v in sorted(sector_rs.items())},
                                    'selected_sample_sectors': selected_sectors, 'ranked_buy_symbols': candidates, 'pending_sell_reasons': dict(pending_sells),
                                    'research_dimensions_validated': ['SAMPLE_PRICE_RELATIVE_STRENGTH_ONLY']})
        exposure = sum(cents(D(bars[(day,s)]['close'])*p['quantity']) for s,p in positions.items())
        equity = cash + exposure; peak = max(peak,equity); max_dd = max(max_dd,D(peak-equity)/peak)
        result['equity'].append(dict(session=day,cash_cents=cash,exposure_cents=exposure,nav_cents=equity,
                                     passive_exposure_cap_exceeded=exposure>D(equity)*D('0.60')))
    result.update(status='SIMULATED_TRADES' if result['fills'] else 'RUN_NO_TRADES',
                  positions=[dict(symbol=s,**p) for s,p in sorted(positions.items())],
                  terminal_pending_exits=dict(pending_sells), terminal_pending_entries=pending_buys,
                  final_cash_cents=cash, net_return=str(D(result['equity'][-1]['nav_cents'])/RULES['initial_cash_cents']-1),
                  maximum_drawdown=str(max_dd), total_fee_cents=sum(f['fees']['total_fee_cents'] for f in result['fills']),
                  total_slippage_cents=sum(f['fees']['slippage_cents'] for f in result['fills']),
                  engine_boundary='PRICE_VOLUME_SAMPLE_DIAGNOSTIC_NOT_FULL_RESEARCH_VALIDATION')
    result['gross_same_fills_return'] = str((D(result['equity'][-1]['nav_cents']) + result['total_fee_cents'] + result['total_slippage_cents']) / RULES['initial_cash_cents'] - 1)
    result['turnover_notional_cents'] = sum(f['fees']['notional_cents'] for f in result['fills'])
    result['benchmark_excess'] = None
    result['benchmark_excess_reason'] = 'NO_ADMITTED_BENCHMARK_PROVIDED'
    result['content_hash'] = digest(result)
    return result
