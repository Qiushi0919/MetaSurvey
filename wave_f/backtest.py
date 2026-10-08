"""Deterministic, closed-shape SYNTHETIC execution/accounting laboratory.

This module has no data reader, optimizer, native execution issuer or actual-run
activation mechanism. ``run_formal`` is unconditionally blocked. Hashes below
detect fixture mutation; they are never historical-source or Owner authority.

Fixture v1 input (all keys required; no extra keys):
  case: version="1.0.0", label=SYNTHETIC_NOT_OWNER_POLICY,
    namespace="SYNTHETIC:CORE_40", account="fixture-account", symbols=SYMBOLS,
    freeze_at, calendar, window, policy, costs, initial, decisions, market,
    actions, factors, benchmark, freeze.
  calendar: [{date, open_at, close_at}]; ordered explicit exchange sessions,
    including acquisition/decision/settlement/action dates outside the window.
    At most 5,000 sessions / 15,000 market rows / 15,000 decisions. An explicit
    250,000 state-unit audit budget blocks unbounded lot/entitlement growth.
  window: {first_session,last_session}; contiguous subset of calendar.
  policy: {version, label, money_rounding="HALF_EVEN", valuation_basis="RAW",
    factor_application="NONE", buy_lot, max_position_qty, max_position_fraction,
    max_exposure_fraction, max_drawdown_fraction, max_turnover_per_session,
    manual_kill_sessions}. Fractions/rates/price/index are Decimal strings.
  costs: [{version,label,effective_from,effective_until,commission_rate,
    minimum_commission_cents,exchange_rate,exchange_included,other_buy_rate,
    other_sell_rate,other_included,sell_tax_rate,slippage_bps}]. Dates inclusive;
    exactly one complete schedule covers each simulated session. No fees default.
  initial: {cash_cents,positions:[{id,symbol,qty,cost_cents,acquired_session,
    available_session}]}; prior acquisitions and next-calendar-session T+1.
  decision: {id,session,cutoff,frozen_at,execute_session,sequence,symbol,side,
    qty,facts,content_hash}; side BUY/SELL; execute_session must be the actual
    next calendar session, NEVER the next observed price bar. Cutoff >= session
    close; cutoff <= frozen_at < next session open. Each decision is sealed
    excluding content_hash; facts are [{kind,period_end,value,clock}], kind
    PRICE/FINANCIAL; financial period_end <= cutoff Shanghai date. Every fact's
    event/published/available/retrieved <= cutoff. Decisions can use previous
    revealed observations, but cannot change the globally frozen policy.
  market: every window session x exact three symbols: {session,symbol,
    price_kind="RAW",open,close,status,listing_status,st_status,lower_limit,
    upper_limit,bar_clock,tradeability_clock}. RAW prices/limits must be exact
    positive 0.01 CNY ticks. status TRADABLE/SUSPENDED/
    NON_TRADEABLE; UNKNOWN blocks. listing_status ACTIVE/DELISTED and st_status
    NORMAL/ST are explicit. Open null only when not TRADABLE. Close positive is
    an explicit synthetic mark (including suspension carry), not missing-data
    inference. Limits required for TRADABLE. At either limit or with slippage
    outside limits, conservative daily proxy records no execution. Tradeability
    published/available/retrieved <= open; complete bar available >= close.
  clock: {event_time,published_at,available_at,retrieved_at,source,
    source_version,source_hash}; source="SYNTHETIC_FIXTURE", complete instants.
    published<=available<=retrieved; event clock has independent semantics.
  actions: [{id,kind,symbol,record_session,ex_session,pay_session,
    cash_per_share_cents,withholding_rate,ratio_numerator,ratio_denominator,
    share_available_session,clock}]. All shape keys required, inapplicable values
    null. CASH_DIVIDEND: integer per-share cents and explicit fixed withholding,
    record < ex <= pay. Record close fixes entitlement, ex recognizes net
    receivable, pay transfers it to cash before executions. SPLIT/BONUS_SHARE:
    record session must immediately precede ex, exact integer share ratios,
    explicit availability >= ex; no fractional cash-in-lieu. BONUS_SHARE keeps
    original settled lot and adds zero-cost new shares; SPLIT changes original
    lot with unchanged total cost. Rights, dynamic holding-period tax,
    ambiguous/nonadjacent/fractional share actions explicitly block. Action
    published/available/retrieved must be <= record-session close, not necessarily
    <= global policy freeze: the hash pins the fixture dataset; it does not make
    later announcements visible earlier. No entitlement exists before record.
  factors: [{session,symbol,value}]; informational only, never applied to RAW.
  benchmark: {version,label,initial_level,levels:[{session,level,clock}]}; complete
    window, positive synthetic total-return index, independent of traded shares.
  freeze: {policy_hash,decision_hash,market_hash,initial_hash,action_hash,
    benchmark_hash}. policy_hash covers policy/costs/calendar/window/symbols/
    namespace/account/freeze_at, action_hash covers actions AND factors. These
    hashes and per-decision seals MUST be computed before passing the case.
    freeze_at < first window open AND every simulated outcome publication.

Cash/fees/book costs are integer CNY cents; round once per notional/fee component
with HALF_EVEN. Slippage adjusts proxy execution price, so commissions/limits use
that price; its cash impact is disclosed separately, never charged twice. Sell
cash is usable by later same-session decisions only in their frozen sequence.
No margin, shorting or forced terminal liquidation. Gross is the SAME executed
quantities with disclosed friction added back, not a zero-cost alternative run.
Receivables count in equity, not spendable cash. Outcomes/ledger remain labelled
synthetic daily proxies, not observed auctions or native Order/Fill objects.
All fixture input/output JSON integers have absolute value <= 9007199254740991;
larger calculated balances reject instead of losing precision in a later JSON
consumer. Calculations use Decimal precision 100, with <= 50 significant input
digits. Integer-cent fixture representation is NOT a native ledger contract.
"""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from zoneinfo import ZoneInfo

from wave_f.common import (LABEL, SYMBOLS, VERSION, UNSET, canonical, digest,
                           hash_value, keys, metadata, require, session_date,
                           timestamp, decimal_string, unavailable)

NAMESPACE = 'SYNTHETIC:CORE_40'
ACCOUNT = 'fixture-account'
ZERO = Decimal('0')
ONE = Decimal('1')
CENT = Decimal('0.01')
RATIO = Decimal('0.00000001')
JSON_INTEGER_MAX = 9007199254740991


def _json_integer_range(value):
    if type(value) is int:
        require(abs(value) <= JSON_INTEGER_MAX, 'WF_BT_JSON_INTEGER_RANGE')
    elif type(value) is list:
        for item in value: _json_integer_range(item)
    elif type(value) is dict:
        for item in value.values(): _json_integer_range(item)


def _int(value, minimum=0):
    require(type(value) is int and minimum <= value <= JSON_INTEGER_MAX, 'WF_BT_INTEGER')
    return value


def _dec(value, minimum=ZERO, maximum=Decimal('1000000000000')):
    result = decimal_string(value)
    require(len(result.as_tuple().digits) <= 50, 'WF_BT_DECIMAL_PRECISION')
    require(minimum <= result <= maximum, 'WF_BT_DECIMAL_RANGE')
    return result


def _money(value):
    return int((value * 100).quantize(ONE, rounding=ROUND_HALF_EVEN))


def _fraction(value):
    return format(value.quantize(RATIO, rounding=ROUND_HALF_EVEN), 'f')


def _price(value):
    result = _dec(value, CENT)
    require(result % CENT == 0, 'WF_BT_PRICE_TICK')
    return result


def _instant_day(value):
    return (datetime.fromisoformat(value.replace('Z', '+00:00'))
            .astimezone(ZoneInfo('Asia/Shanghai')).date())


def _name(value):
    require(type(value) is str and 0 < len(value) <= 120, 'WF_BT_IDENTIFIER')
    return value


def _clock(value, cutoff=None, no_future_event=False):
    keys(value, ['event_time', 'published_at', 'available_at', 'retrieved_at',
                 'source', 'source_version', 'source_hash'])
    require(value['source'] == 'SYNTHETIC_FIXTURE', 'WF_BT_NOT_SYNTHETIC_SOURCE')
    _name(value['source_version']); hash_value(value['source_hash'])
    instants = {key: timestamp(value[key]) for key in
                ('event_time', 'published_at', 'available_at', 'retrieved_at')}
    require(instants['published_at'] <= instants['available_at'] <=
            instants['retrieved_at'], 'WF_BT_CLOCK_ORDER')
    if cutoff is not None:
        ns = timestamp(cutoff)
        require(all(instants[k] <= ns for k in
                    ('published_at', 'available_at', 'retrieved_at')),
                'WF_BT_PIT_VISIBILITY')
        if no_future_event:
            require(instants['event_time'] <= ns, 'WF_BT_FUTURE_EVENT')
    return instants


def _policy_body(case):
    return {key: case[key] for key in ('policy', 'costs', 'calendar', 'window',
            'symbols', 'namespace', 'account', 'freeze_at')}


def _validate(case):
    keys(case, ['version', 'label', 'namespace', 'account', 'symbols', 'freeze_at',
                'calendar', 'window', 'policy', 'costs', 'initial', 'decisions',
                'market', 'actions', 'factors', 'benchmark', 'freeze'])
    require(case['version'] == VERSION and case['label'] == LABEL,
            'WF_BT_FIXTURE_LABEL_REQUIRED')
    require(case['namespace'] == NAMESPACE and case['account'] == ACCOUNT and
            case['symbols'] == list(SYMBOLS), 'WF_BT_NAMESPACE')
    frozen = timestamp(case['freeze_at'])
    keys(case['freeze'], ['policy_hash', 'decision_hash', 'market_hash',
                          'initial_hash', 'action_hash', 'benchmark_hash'])
    expected = {'policy_hash': digest(_policy_body(case)),
                'decision_hash': digest(case['decisions']),
                'market_hash': digest(case['market']),
                'initial_hash': digest(case['initial']),
                'action_hash': digest({'actions': case['actions'],
                                       'factors': case['factors']}),
                'benchmark_hash': digest(case['benchmark'])}
    require(case['freeze'] == expected, 'WF_BT_FREEZE_INVALIDATED')

    require(type(case['calendar']) is list and 2 <= len(case['calendar']) <= 5000,
            'WF_BT_CALENDAR')
    calendar = {}
    for row in case['calendar']:
        keys(row, ['date', 'open_at', 'close_at'])
        day = session_date(row['date'])
        require(row['date'] not in calendar, 'WF_BT_DUPLICATE_SESSION')
        open_ns, close_ns = timestamp(row['open_at']), timestamp(row['close_at'])
        require(open_ns < close_ns and
                datetime.fromisoformat(row['open_at'].replace('Z', '+00:00')).
                    astimezone(ZoneInfo('Asia/Shanghai')).date() == day and
                datetime.fromisoformat(row['close_at'].replace('Z', '+00:00')).
                    astimezone(ZoneInfo('Asia/Shanghai')).date() == day,
                'WF_BT_SESSION_CLOCK')
        calendar[row['date']] = row
    dates = list(calendar)
    require(dates == sorted(dates), 'WF_BT_CALENDAR_ORDER')
    for previous, current in zip(dates, dates[1:]):
        require(timestamp(calendar[previous]['close_at']) <
                timestamp(calendar[current]['open_at']), 'WF_BT_SESSION_OVERLAP')
    keys(case['window'], ['first_session', 'last_session'])
    first, last = case['window']['first_session'], case['window']['last_session']
    require(first in calendar and last in calendar and first <= last,
            'WF_BT_WINDOW')
    active = dates[dates.index(first):dates.index(last)+1]
    require(frozen < timestamp(calendar[first]['open_at']),
            'WF_BT_POLICY_AFTER_REVEAL')
    next_session = {day: dates[i+1] if i+1 < len(dates) else None
                    for i, day in enumerate(dates)}

    policy = case['policy']
    keys(policy, ['version', 'label', 'money_rounding', 'valuation_basis',
                  'factor_application', 'buy_lot', 'max_position_qty',
                  'max_position_fraction', 'max_exposure_fraction',
                  'max_drawdown_fraction', 'max_turnover_per_session',
                  'manual_kill_sessions'])
    _name(policy['version'])
    require(policy['label'] == LABEL and policy['money_rounding'] == 'HALF_EVEN',
            'WF_BT_POLICY_REQUIRED')
    require(policy['valuation_basis'] == 'RAW', 'WF_BT_ADJUSTED_PRICE_BLOCKED')
    require(policy['factor_application'] == 'NONE', 'WF_BT_FACTOR_CASH_DOUBLE_COUNT')
    _int(policy['buy_lot'], 1); _int(policy['max_position_qty'], 1)
    for key in ('max_position_fraction', 'max_exposure_fraction',
                'max_drawdown_fraction'):
        _dec(policy[key], Decimal('0.00000001'), ONE)
    _dec(policy['max_turnover_per_session'], Decimal('0.00000001'))
    require(type(policy['manual_kill_sessions']) is list and
            len(set(policy['manual_kill_sessions'])) ==
            len(policy['manual_kill_sessions']) and
            all(day in active for day in policy['manual_kill_sessions']),
            'WF_BT_KILL_POLICY')

    require(type(case['costs']) is list and 0 < len(case['costs']) <= 100,
            'WF_BT_COST_SCHEDULE_REQUIRED')
    for cost in case['costs']:
        keys(cost, ['version', 'label', 'effective_from', 'effective_until',
                    'commission_rate', 'minimum_commission_cents', 'exchange_rate',
                    'exchange_included', 'other_buy_rate', 'other_sell_rate',
                    'other_included', 'sell_tax_rate', 'slippage_bps'])
        _name(cost['version']); require(cost['label'] == LABEL, 'WF_BT_COST_LABEL')
        require(session_date(cost['effective_from']) <=
                session_date(cost['effective_until']), 'WF_BT_COST_DATES')
        for key in ('commission_rate', 'exchange_rate', 'other_buy_rate',
                    'other_sell_rate', 'sell_tax_rate'):
            _dec(cost[key], maximum=ONE)
        _int(cost['minimum_commission_cents'])
        _dec(cost['slippage_bps'], maximum=Decimal('1000'))
        require(type(cost['exchange_included']) is bool and
                type(cost['other_included']) is bool, 'WF_BT_FEE_INCLUSION_UNKNOWN')
    costs = {}
    for day in active:
        matches = [cost for cost in case['costs'] if
                   cost['effective_from'] <= day <= cost['effective_until']]
        require(len(matches) == 1, 'WF_BT_DATED_COST_AMBIGUOUS_OR_MISSING')
        costs[day] = matches[0]

    keys(case['initial'], ['cash_cents', 'positions'])
    _int(case['initial']['cash_cents'])
    require(type(case['initial']['positions']) is list and
            len(case['initial']['positions']) <= 100, 'WF_BT_INITIAL_POSITIONS')
    lot_ids = set()
    for lot in case['initial']['positions']:
        keys(lot, ['id', 'symbol', 'qty', 'cost_cents', 'acquired_session',
                   'available_session'])
        _name(lot['id']); _int(lot['qty'], 1); _int(lot['cost_cents'])
        require(lot['id'] not in lot_ids and lot['symbol'] in SYMBOLS,
                'WF_BT_INITIAL_LOT')
        lot_ids.add(lot['id'])
        require(lot['acquired_session'] in calendar and
                lot['acquired_session'] < first and
                lot['available_session'] == next_session[lot['acquired_session']],
                'WF_BT_INITIAL_T_PLUS_ONE')

    require(type(case['market']) is list and len(case['market']) <= 15000,
            'WF_BT_MARKET_SHAPE')
    market = {}
    for row in case['market']:
        keys(row, ['session', 'symbol', 'price_kind', 'open', 'close', 'status',
                   'listing_status', 'st_status', 'lower_limit', 'upper_limit',
                   'bar_clock', 'tradeability_clock'])
        key = (row['session'], row['symbol'])
        require(row['session'] in active and row['symbol'] in SYMBOLS and
                key not in market, 'WF_BT_MARKET_IDENTITY')
        require(row['price_kind'] == 'RAW', 'WF_BT_ADJUSTED_PRICE_BLOCKED')
        require(row['status'] in ('TRADABLE', 'SUSPENDED', 'NON_TRADEABLE') and
                row['listing_status'] in ('ACTIVE', 'DELISTED') and
                row['st_status'] in ('NORMAL', 'ST'), 'WF_BT_UNKNOWN_TRADEABILITY')
        _price(row['close'])
        if row['status'] == 'TRADABLE':
            price = _price(row['open'])
            lower = _price(row['lower_limit'])
            upper = _price(row['upper_limit'])
            require(lower < upper and lower <= price <= upper,
                    'WF_BT_LIMIT_REGIME')
        else:
            if row['open'] is not None: _price(row['open'])
            for key_name in ('lower_limit', 'upper_limit'):
                if row[key_name] is not None:
                    _price(row[key_name])
        observed = _clock(row['bar_clock'])
        require(observed['available_at'] >= timestamp(
                calendar[row['session']]['close_at']) and
                observed['published_at'] >= timestamp(calendar[row['session']]['close_at'])
                and observed['published_at'] > frozen and
                _instant_day(row['bar_clock']['event_time']) == session_date(row['session']),
                'WF_BT_OUTCOME_REVEAL_CLOCK')
        _clock(row['tradeability_clock'], calendar[row['session']]['open_at'],
               no_future_event=True)
        market[key] = row
    require(set(market) == {(day, symbol) for day in active for symbol in SYMBOLS},
            'WF_BT_MISSING_SESSION_BAR')

    require(type(case['decisions']) is list and len(case['decisions']) <= 15000,
            'WF_BT_DECISIONS')
    decisions, ids, sequences = {}, set(lot_ids), set()
    for row in case['decisions']:
        keys(row, ['id', 'session', 'cutoff', 'frozen_at', 'execute_session',
                   'sequence', 'symbol', 'side', 'qty', 'facts', 'content_hash'])
        _name(row['id']); _int(row['sequence']); _int(row['qty'], 1)
        require(row['id'] not in ids and row['symbol'] in SYMBOLS and
                row['side'] in ('BUY', 'SELL'), 'WF_BT_DECISION_IDENTITY')
        ids.add(row['id'])
        require(row['content_hash'] == digest({k: v for k, v in row.items()
                                               if k != 'content_hash'}),
                'WF_BT_DECISION_INVALIDATED')
        require(row['session'] in calendar and row['execute_session'] ==
                next_session[row['session']] and row['execute_session'] is not None,
                'WF_BT_NEXT_CALENDAR_SESSION_REQUIRED')
        execution = row['execute_session']
        require(execution >= first, 'WF_BT_EXECUTION_BEFORE_WINDOW')
        cutoff, decision_frozen = timestamp(row['cutoff']), timestamp(row['frozen_at'])
        require(timestamp(calendar[row['session']]['close_at']) <= cutoff <=
                decision_frozen < timestamp(calendar[execution]['open_at']),
                'WF_BT_FREEZE_BEFORE_REVEAL')
        pair = (execution, row['sequence'])
        require(pair not in sequences, 'WF_BT_CASH_SEQUENCE_AMBIGUOUS')
        sequences.add(pair)
        require(type(row['facts']) is list and 0 < len(row['facts']) <= 100,
                'WF_BT_DECISION_FACTS_REQUIRED')
        cutoff_date = _instant_day(row['cutoff'])
        for fact in row['facts']:
            keys(fact, ['kind', 'period_end', 'value', 'clock'])
            require(fact['kind'] in ('PRICE', 'FINANCIAL'), 'WF_BT_FACT_KIND')
            _dec(fact['value'])
            _clock(fact['clock'], row['cutoff'], no_future_event=True)
            if fact['kind'] == 'FINANCIAL':
                require(session_date(fact['period_end']) <= cutoff_date,
                        'WF_BT_FUTURE_FINANCIAL_PERIOD')
            else:
                require(fact['period_end'] is None, 'WF_BT_PRICE_PERIOD')
        decisions.setdefault(execution, []).append(row)
    for rows in decisions.values(): rows.sort(key=lambda row: row['sequence'])

    require(type(case['actions']) is list and len(case['actions']) <= 100,
            'WF_BT_ACTIONS')
    actions, action_ids, economic_action_ids = [], set(), set()
    for action in case['actions']:
        keys(action, ['id', 'kind', 'symbol', 'record_session', 'ex_session',
                      'pay_session', 'cash_per_share_cents', 'withholding_rate',
                      'ratio_numerator', 'ratio_denominator',
                      'share_available_session', 'clock'])
        _name(action['id'])
        require(action['id'] not in action_ids and action['symbol'] in SYMBOLS,
                'WF_BT_ACTION_IDENTITY')
        action_ids.add(action['id'])
        require(action['kind'] in ('CASH_DIVIDEND', 'SPLIT', 'BONUS_SHARE'),
                'WF_BT_UNSUPPORTED_ACTION')
        require(action['record_session'] in active and
                action['ex_session'] in calendar and
                action['record_session'] < action['ex_session'], 'WF_BT_ACTION_DATES')
        economic_id = (action['kind'], action['symbol'], action['record_session'],
                       action['ex_session'])
        require(economic_id not in economic_action_ids, 'WF_BT_DUPLICATE_ECONOMIC_ACTION')
        economic_action_ids.add(economic_id)
        _clock(action['clock'], calendar[action['record_session']]['close_at'])
        if action['kind'] == 'CASH_DIVIDEND':
            _int(action['cash_per_share_cents'])
            _dec(action['withholding_rate'], maximum=ONE)
            require(action['pay_session'] in calendar and
                    action['ex_session'] <= action['pay_session'] and
                    all(action[key] is None for key in ('ratio_numerator',
                        'ratio_denominator', 'share_available_session')),
                    'WF_BT_DIVIDEND_DATES_OR_FIELDS')
        else:
            numerator = _int(action['ratio_numerator'], 1)
            denominator = _int(action['ratio_denominator'], 1)
            require(action['ex_session'] == next_session[action['record_session']]
                    and action['share_available_session'] in calendar and
                    action['share_available_session'] >= action['ex_session'] and
                    all(action[key] is None for key in ('pay_session',
                         'cash_per_share_cents', 'withholding_rate')),
                    'WF_BT_SHARE_ACTION_DATES_OR_FIELDS')
            if action['kind'] == 'BONUS_SHARE':
                require(numerator > denominator, 'WF_BT_BONUS_RATIO')
        actions.append(action)
    # Two actions for the same record/ex security would need explicit composition
    # and basis ordering. This fixture v1 blocks rather than inventing that rule.
    share_actions = [(a['symbol'], a['ex_session']) for a in actions
                     if a['kind'] != 'CASH_DIVIDEND']
    require(len(share_actions) == len(set(share_actions)),
            'WF_BT_AMBIGUOUS_SHARE_ACTION')
    require(type(case['factors']) is list and len(case['factors']) <= 15000,
            'WF_BT_FACTOR_SHAPE')
    factor_ids = set()
    for factor in case['factors']:
        keys(factor, ['session', 'symbol', 'value'])
        key = (factor['session'], factor['symbol'])
        require(factor['session'] in calendar and factor['symbol'] in SYMBOLS and
                key not in factor_ids, 'WF_BT_FACTOR_IDENTITY')
        factor_ids.add(key); _dec(factor['value'], Decimal('0.00000001'))

    benchmark = case['benchmark']
    keys(benchmark, ['version', 'label', 'initial_level', 'levels'])
    _name(benchmark['version']); require(benchmark['label'] == LABEL, 'WF_BT_BENCHMARK')
    _dec(benchmark['initial_level'], Decimal('0.00000001'))
    require(type(benchmark['levels']) is list, 'WF_BT_BENCHMARK')
    levels = {}
    for row in benchmark['levels']:
        keys(row, ['session', 'level', 'clock'])
        require(row['session'] in active and row['session'] not in levels,
                'WF_BT_BENCHMARK_IDENTITY')
        _dec(row['level'], Decimal('0.00000001'))
        observed = _clock(row['clock'])
        require(observed['available_at'] >= timestamp(calendar[row['session']]['close_at'])
                and observed['published_at'] >= timestamp(calendar[row['session']]['close_at'])
                and observed['published_at'] > frozen and
                _instant_day(row['clock']['event_time']) == session_date(row['session']),
                'WF_BT_BENCHMARK_REVEAL')
        levels[row['session']] = row['level']
    require(set(levels) == set(active), 'WF_BT_BENCHMARK_MISSING')
    return calendar, active, next_session, market, costs, decisions, actions, levels


class _Ledger:
    """In-memory synthetic bookkeeping; no persistent or native output path."""

    def __init__(self, initial, genesis):
        self.cash = initial['cash_cents']
        self.lots = deepcopy(initial['positions'])
        self.entitlements = {}
        self.entries = []
        self.audit_units = 0
        self.head = digest({'label': LABEL, 'genesis': genesis})

    def quantities(self):
        return {s: sum(lot['qty'] for lot in self.lots if lot['symbol'] == s)
                for s in SYMBOLS}

    def state(self):
        require(len(self.lots) <= 1000, 'WF_BT_OPEN_LOT_BUDGET')
        return {'cash_cents': self.cash, 'lots': deepcopy(self.lots),
                'entitlements': deepcopy(self.entitlements),
                'quantities': self.quantities(),
                'receivable_cents': sum(e['net_cents'] for e in self.entitlements.values()
                                        if e['state'] == 'EX_RECEIVABLE'),
                'book_cost_cents': sum(lot['cost_cents'] for lot in self.lots)}

    def audit(self, session, kind, reference, before, cash_delta, qty_delta,
              details):
        after = self.state()
        self.audit_units += (len(before['lots']) + len(after['lots']) +
                             sum(len(e['record_lots']) for e in before['entitlements'].values()) +
                             sum(len(e['record_lots']) for e in after['entitlements'].values()) + 1)
        require(self.audit_units <= 250000, 'WF_BT_AUDIT_MEMORY_BUDGET')
        require(after['cash_cents'] == before['cash_cents'] + cash_delta and
                after['cash_cents'] >= 0, 'WF_BT_CASH_RECONCILIATION')
        require(all(after['quantities'][s] == before['quantities'][s] +
                    qty_delta.get(s, 0) for s in SYMBOLS), 'WF_BT_SHARE_RECONCILIATION')
        require(all(lot['qty'] > 0 and lot['cost_cents'] >= 0 for lot in self.lots),
                'WF_BT_LOT_RECONCILIATION')
        require(len({lot['id'] for lot in self.lots}) == len(self.lots),
                'WF_BT_LOT_ID_COLLISION')
        entry = {'index': len(self.entries), 'label': LABEL, 'namespace': NAMESPACE,
                 'account': ACCOUNT, 'session': session, 'kind': kind,
                 'reference': reference, 'previous_hash': self.head,
                 'cash_delta_cents': cash_delta,
                 'quantity_delta': {s: qty_delta.get(s, 0) for s in SYMBOLS},
                 'before': before, 'after': after, 'details': details}
        entry['content_hash'] = digest(entry)
        self.entries.append(entry); self.head = entry['content_hash']

    def equity(self, prices):
        market_value = sum(_money(prices[s] * quantity) for s, quantity in
                           self.quantities().items())
        receivable = self.state()['receivable_cents']
        return self.cash + market_value + receivable, market_value, receivable


def _fees(price, raw_price, qty, side, cost):
    notional = _money(price * qty)
    raw_notional = _money(raw_price * qty)
    commission_unfloored = _money(Decimal(notional) / 100 * _dec(cost['commission_rate']))
    commission = max(commission_unfloored, cost['minimum_commission_cents'])
    exchange = 0 if cost['exchange_included'] else _money(
        Decimal(notional) / 100 * _dec(cost['exchange_rate']))
    other_rate = cost['other_buy_rate'] if side == 'BUY' else cost['other_sell_rate']
    other = 0 if cost['other_included'] else _money(Decimal(notional) / 100 * _dec(other_rate))
    tax = _money(Decimal(notional) / 100 * _dec(cost['sell_tax_rate'])) if side == 'SELL' else 0
    return {'notional_cents': notional, 'raw_notional_cents': raw_notional,
            'commission_cents': commission,
            'minimum_commission_uplift_cents': commission-commission_unfloored,
            'exchange_cents': exchange, 'other_cents': other, 'sell_tax_cents': tax,
            'total_fee_cents': commission+exchange+other+tax,
            'slippage_cents': abs(notional-raw_notional)}


def run_fixture(case):
    """Execute only an explicit synthetic fixture; returns JSON-safe audit data.

    Malformed/unavailable source/policy/clock objects fail the whole fixture.
    Economic/execution constraints produce explicit NO_EXECUTION records without
    modifying cash or holdings. A non-tradeable next session is not skipped.
    """
    canonical(case)
    _json_integer_range(case)
    # A private copy ensures engine calculations never mutate caller policy/data.
    case = deepcopy(case)
    with localcontext() as context:
        context.prec = 100
        return _run(case)


def _run(case):
    calendar, active, following, market, costs, decisions, actions, levels = _validate(case)
    ledger = _Ledger(case['initial'], case['freeze'])
    policy = case['policy']
    first_prices = {s: _dec(market[(active[0], s)]['open'] or
                                market[(active[0], s)]['close']) for s in SYMBOLS}
    initial_equity, initial_value, _ = ledger.equity(first_prices)
    require(initial_equity > 0, 'WF_BT_INITIAL_EQUITY')
    require(all(qty <= policy['max_position_qty'] for qty in ledger.quantities().values()),
            'WF_BT_INITIAL_POSITION_LIMIT')
    require(Decimal(initial_value) / initial_equity <= _dec(policy['max_exposure_fraction'])
            and all(Decimal(_money(first_prices[s]*qty)) / initial_equity <=
                    _dec(policy['max_position_fraction']) for s, qty in
                    ledger.quantities().items()), 'WF_BT_INITIAL_EXPOSURE_LIMIT')
    fee_totals = {key: 0 for key in ('commission_cents', 'minimum_commission_uplift_cents',
                   'exchange_cents', 'other_cents', 'sell_tax_cents',
                   'dividend_withholding_cents', 'total_fee_cents', 'slippage_cents')}
    executions, daily = [], []
    peak_net = peak_gross = initial_equity
    max_net_dd = max_gross_dd = ZERO
    cumulative_turnover = 0
    kill_active = False
    for day in active:
        open_prices = {s: _dec(market[(day, s)]['open'] or market[(day, s)]['close'])
                       for s in SYMBOLS}
        close_prices = {s: _dec(market[(day, s)]['close']) for s in SYMBOLS}
        day_turnover = 0

        for action in actions:
            if action['ex_session'] != day: continue
            before = ledger.state(); entitlement = ledger.entitlements[action['id']]
            require(entitlement['state'] == 'RECORDED', 'WF_BT_ENTITLEMENT_STATE')
            if action['kind'] == 'CASH_DIVIDEND':
                entitlement['state'] = 'EX_RECEIVABLE'
                fee_totals['dividend_withholding_cents'] += entitlement['tax_cents']
                fee_totals['total_fee_cents'] += entitlement['tax_cents']
                ledger.audit(day, 'DIVIDEND_EX_RECEIVABLE', action['id'], before, 0, {},
                             {'gross_cents': entitlement['gross_cents'],
                              'tax_cents': entitlement['tax_cents'],
                              'net_cents': entitlement['net_cents']})
            else:
                qty_change = 0
                for recorded in entitlement['record_lots']:
                    matching = [lot for lot in ledger.lots if lot['id'] == recorded['id']]
                    require(len(matching) == 1 and matching[0]['qty'] == recorded['qty'],
                            'WF_BT_SHARE_ENTITLEMENT_CHANGED')
                    lot = matching[0]
                    numerator = recorded['qty'] * action['ratio_numerator']
                    require(numerator % action['ratio_denominator'] == 0,
                            'WF_BT_FRACTIONAL_SHARE_ACTION_UNSUPPORTED')
                    new_qty = numerator // action['ratio_denominator']
                    if action['kind'] == 'SPLIT':
                        require(new_qty > 0, 'WF_BT_FRACTIONAL_SHARE_ACTION_UNSUPPORTED')
                        qty_change += new_qty-lot['qty']; lot['qty'] = new_qty
                        lot['available_session'] = max(lot['available_session'],
                                                       action['share_available_session'])
                    else:
                        bonus = new_qty-recorded['qty']; qty_change += bonus
                        if bonus:
                            ledger.lots.append({'id': action['id']+':'+lot['id'],
                                'symbol': action['symbol'], 'qty': bonus, 'cost_cents': 0,
                                'acquired_session': day,
                                'available_session': action['share_available_session']})
                entitlement['state'] = 'SHARES_CREDITED'
                ledger.audit(day, action['kind']+'_CREDIT', action['id'], before, 0,
                             {action['symbol']: qty_change},
                             {'share_available_session': action['share_available_session'],
                              'ratio_numerator': action['ratio_numerator'],
                              'ratio_denominator': action['ratio_denominator']})

        for action in actions:
            if action['kind'] != 'CASH_DIVIDEND' or action['pay_session'] != day: continue
            before = ledger.state(); entitlement = ledger.entitlements[action['id']]
            require(entitlement['state'] == 'EX_RECEIVABLE', 'WF_BT_ENTITLEMENT_STATE')
            ledger.cash += entitlement['net_cents']; entitlement['state'] = 'PAID'
            ledger.audit(day, 'DIVIDEND_PAY', action['id'], before, entitlement['net_cents'],
                         {}, {'net_cents': entitlement['net_cents']})

        # Opening turnover denominator includes causal ex/pay credits, so an ex
        # price drop does not discard the dividend receivable from portfolio NAV.
        day_start_equity, _, _ = ledger.equity(open_prices)
        require(day_start_equity > 0, 'WF_BT_NONPOSITIVE_EQUITY')

        for decision in decisions.get(day, []):
            before = ledger.state()
            symbol, side, qty = decision['symbol'], decision['side'], decision['qty']
            row = market[(day, symbol)]
            output = {'label': LABEL, 'namespace': NAMESPACE, 'account': ACCOUNT,
                      'decision_id': decision['id'], 'decision_hash': decision['content_hash'],
                      'decision_session': decision['session'], 'execution_session': day,
                      'sequence': decision['sequence'], 'symbol': symbol, 'side': side,
                      'qty': qty, 'model': 'SYNTHETIC_DAILY_PROXY_NOT_OBSERVED_AUCTION',
                      'status': 'NO_EXECUTION', 'reason': None, 'proxy_price': None,
                      'cost_version': costs[day]['version'], 'fees': None,
                      'native_order': False, 'productionGate': False}
            reason = None
            if row['listing_status'] != 'ACTIVE': reason = 'WF_BT_DELISTED'
            elif row['status'] != 'TRADABLE': reason = 'WF_BT_'+row['status']
            if reason is None:
                raw_price = _dec(row['open'])
                direction = ONE if side == 'BUY' else -ONE
                price = (raw_price * (ONE + direction * _dec(costs[day]['slippage_bps']) /
                                     10000)).quantize(CENT, rounding=ROUND_HALF_EVEN)
                require(price > 0, 'WF_BT_PROXY_PRICE')
                lower, upper = _dec(row['lower_limit']), _dec(row['upper_limit'])
                if raw_price in (lower, upper) or not lower < price < upper:
                    reason = 'WF_BT_PRICE_LIMIT_PROXY_NO_EXECUTION'
                fees = _fees(price, raw_price, qty, side, costs[day])
                output['proxy_price'] = format(price, 'f'); output['fees'] = fees
                quantities = ledger.quantities()
                equity, value, _ = ledger.equity(open_prices)
                # Opening gap/action risk is recognized before new risk is added.
                if Decimal(peak_net-equity) / peak_net >= _dec(policy['max_drawdown_fraction']):
                    kill_active = True
                if reason is None and side == 'BUY':
                    if kill_active or day in policy['manual_kill_sessions']:
                        reason = 'WF_BT_KILL_BLOCKS_NEW_RISK'
                    elif qty % policy['buy_lot']:
                        reason = 'WF_BT_BUY_LOT'
                    elif quantities[symbol]+qty > policy['max_position_qty']:
                        reason = 'WF_BT_POSITION_QUANTITY_LIMIT'
                    elif ledger.cash < fees['notional_cents']+fees['total_fee_cents']:
                        reason = 'WF_BT_FEE_INCLUSIVE_AFFORDABILITY'
                    else:
                        after_equity = equity-fees['total_fee_cents']-fees['slippage_cents']
                        projected_position = _money(open_prices[symbol]*(quantities[symbol]+qty))
                        projected_exposure = value+_money(open_prices[symbol]*qty)
                        if (after_equity <= 0 or Decimal(projected_position)/after_equity >
                                _dec(policy['max_position_fraction'])):
                            reason = 'WF_BT_POSITION_VALUE_LIMIT'
                        elif Decimal(projected_exposure)/after_equity > _dec(policy['max_exposure_fraction']):
                            reason = 'WF_BT_EXPOSURE_LIMIT'
                elif reason is None:
                    available = sum(lot['qty'] for lot in ledger.lots if lot['symbol'] == symbol
                                    and lot['available_session'] is not None and
                                    lot['available_session'] <= day)
                    if qty > available: reason = 'WF_BT_T_PLUS_ONE_OR_NO_HOLDING'
                    elif qty % policy['buy_lot'] and qty != quantities[symbol]:
                        reason = 'WF_BT_ODD_LOT_PARTIAL_SELL'
                    elif (fees['notional_cents'] < fees['total_fee_cents'] and
                            ledger.cash < fees['total_fee_cents']-fees['notional_cents']):
                        reason = 'WF_BT_FEE_INCLUSIVE_AFFORDABILITY'
                if (reason is None and Decimal(day_turnover+fees['notional_cents'])/
                        day_start_equity > _dec(policy['max_turnover_per_session'])):
                    reason = 'WF_BT_TURNOVER_LIMIT'
            output['reason'] = reason
            if reason is None:
                if side == 'BUY':
                    cash_delta = -fees['notional_cents']-fees['total_fee_cents']
                    ledger.cash += cash_delta
                    ledger.lots.append({'id': decision['id'], 'symbol': symbol, 'qty': qty,
                        'cost_cents': fees['notional_cents']+fees['total_fee_cents'],
                        'acquired_session': day, 'available_session': following[day]})
                    book_removed = 0
                else:
                    cash_delta = fees['notional_cents']-fees['total_fee_cents']
                    ledger.cash += cash_delta; remaining, book_removed = qty, 0
                    for lot in list(ledger.lots):
                        if (lot['symbol'] != symbol or lot['available_session'] is None or
                                lot['available_session'] > day or remaining == 0): continue
                        take = min(remaining, lot['qty'])
                        allocated = lot['cost_cents'] if take == lot['qty'] else int(
                            (Decimal(lot['cost_cents'])*take/lot['qty']).quantize(
                                ONE, rounding=ROUND_HALF_EVEN))
                        lot['qty'] -= take; lot['cost_cents'] -= allocated
                        book_removed += allocated; remaining -= take
                        if lot['qty'] == 0: ledger.lots.remove(lot)
                    require(remaining == 0, 'WF_BT_SELL_ALLOCATION')
                for key in fee_totals:
                    if key in fees: fee_totals[key] += fees[key]
                day_turnover += fees['notional_cents']; cumulative_turnover += fees['notional_cents']
                output['status'] = 'HYPOTHETICAL_EXECUTION'
                ledger.audit(day, side+'_HYPOTHETICAL', decision['id'], before, cash_delta,
                             {symbol: qty if side == 'BUY' else -qty},
                             {'fees': fees, 'proxy_price': output['proxy_price'],
                              'book_cost_removed_cents': book_removed})
            else:
                ledger.audit(day, 'NO_EXECUTION', decision['id'], before, 0, {},
                             {'reason': reason})
            executions.append(output)

        for action in actions:
            if action['record_session'] != day: continue
            before = ledger.state()
            recorded_lots = [deepcopy(lot) for lot in ledger.lots if lot['symbol'] == action['symbol']]
            qty = sum(lot['qty'] for lot in recorded_lots)
            gross = qty*action['cash_per_share_cents'] if action['kind'] == 'CASH_DIVIDEND' else 0
            tax = int((Decimal(gross)*_dec(action['withholding_rate'])).quantize(
                ONE, rounding=ROUND_HALF_EVEN)) if action['kind'] == 'CASH_DIVIDEND' else 0
            ledger.entitlements[action['id']] = {'kind': action['kind'], 'symbol': action['symbol'],
                'state': 'RECORDED', 'record_session': day, 'record_qty': qty,
                'record_lots': recorded_lots, 'gross_cents': gross, 'tax_cents': tax,
                'net_cents': gross-tax}
            ledger.audit(day, 'ACTION_RECORD', action['id'], before, 0, {},
                         {'record_qty': qty, 'gross_cents': gross, 'tax_cents': tax})

        equity, value, receivable = ledger.equity(close_prices)
        gross_equity = equity+fee_totals['total_fee_cents']+fee_totals['slippage_cents']
        peak_net = max(peak_net, equity); peak_gross = max(peak_gross, gross_equity)
        net_dd = Decimal(peak_net-equity)/peak_net
        gross_dd = Decimal(peak_gross-gross_equity)/peak_gross
        max_net_dd = max(max_net_dd, net_dd); max_gross_dd = max(max_gross_dd, gross_dd)
        if net_dd >= _dec(policy['max_drawdown_fraction']): kill_active = True
        before = ledger.state()
        ledger.audit(day, 'EOD_MARK', day, before, 0, {}, {'prices':
            {s: format(close_prices[s], 'f') for s in SYMBOLS},
            'market_value_cents': value, 'receivable_cents': receivable,
            'net_equity_cents': equity, 'gross_equity_cents': gross_equity})
        require(equity == ledger.cash+value+receivable, 'WF_BT_EQUITY_RECONCILIATION')
        daily.append({'session': day, 'cash_cents': ledger.cash, 'market_value_cents': value,
            'receivable_cents': receivable, 'net_equity_cents': equity,
            'gross_equity_cents': gross_equity, 'net_drawdown_fraction': _fraction(net_dd),
            'gross_drawdown_fraction': _fraction(gross_dd), 'turnover_notional_cents': day_turnover,
            'turnover_fraction': _fraction(Decimal(day_turnover)/day_start_equity),
            'exposure_fraction': _fraction(Decimal(value)/equity) if equity else None,
            'kill_active': kill_active or day in policy['manual_kill_sessions'],
            'benchmark_level': levels[day], 'ledger_head': ledger.head})

    deferred = [{'decision_id': row['id'], 'execute_session': day,
                 'status': 'DEFERRED_BEYOND_TERMINAL', 'label': LABEL}
                for day, rows in decisions.items() if day > active[-1] for row in rows]
    terminal = ledger.state()
    net_pnl = daily[-1]['net_equity_cents']-initial_equity
    gross_pnl = net_pnl+fee_totals['total_fee_cents']+fee_totals['slippage_cents']
    benchmark_return = _dec(levels[active[-1]])/_dec(case['benchmark']['initial_level'])-ONE
    average_equity = sum(Decimal(row['net_equity_cents']) for row in daily)/len(daily)
    body = {'version': VERSION, 'label': LABEL, 'namespace': NAMESPACE, 'account': ACCOUNT,
        'source_admitted': False, 'productionGate': False, 'live_authority': False,
        'actual_forward_days': 0, 'fixture_hash': digest(case), 'freeze': case['freeze'],
        'initial_equity_cents': initial_equity, 'execution_proxies': executions,
        'deferred_decisions': deferred, 'daily': daily, 'ledger': ledger.entries,
        'ledger_head': ledger.head, 'terminal': terminal, 'terminal_liquidation': False,
        'metrics': {'gross_pnl_cents': gross_pnl, 'net_pnl_cents': net_pnl,
            'gross_return_fraction': _fraction(Decimal(gross_pnl)/initial_equity),
            'net_return_fraction': _fraction(Decimal(net_pnl)/initial_equity),
            'benchmark_return_fraction': _fraction(benchmark_return),
            'net_excess_fraction': _fraction(Decimal(net_pnl)/initial_equity-benchmark_return),
            'maximum_net_drawdown_fraction': _fraction(max_net_dd),
            'maximum_gross_drawdown_fraction': _fraction(max_gross_dd),
            'turnover_notional_cents': cumulative_turnover,
            'turnover_fraction': _fraction(Decimal(cumulative_turnover)/average_equity),
            'hypothetical_execution_count': sum(row['status'] == 'HYPOTHETICAL_EXECUTION'
                                                for row in executions),
            'fees': fee_totals, 'open_positions': terminal['quantities'],
            'unpaid_receivable_cents': terminal['receivable_cents']},
        'limitations': ['SYNTHETIC_DAILY_PROXY_NOT_OBSERVED_AUCTION',
            'NO_ACTUAL_SOURCE_OR_OWNER_POLICY', 'NO_NATIVE_EXECUTION_OBJECTS',
            'NO_MINUTE_QUEUE_PARTIAL_FILL_OR_MAE_MFE_MODEL',
            'NO_RIGHTS_OR_FRACTIONAL_CASH_IN_LIEU_OR_DYNAMIC_DIVIDEND_TAX',
            'GROSS_USES_SAME_EXECUTED_QUANTITIES', 'NO_TERMINAL_LIQUIDATION']}
    _json_integer_range(body)
    body['content_hash'] = digest(body)
    return body


def readiness():
    return metadata({'engine': 'SYNTHETIC_DETERMINISTIC_BACKTEST_LABORATORY',
        'fixture_version': VERSION, 'fixture_label': LABEL,
        'fixture_execution': 'AVAILABLE', 'formal_execution': 'BLOCKED',
        'actual_source_reader': 'NOT_IMPLEMENTED_OR_ACTIVATED',
        'supports': ['EXPLICIT_NEXT_CALENDAR_SESSION', 'NO_SAME_BAR', 'LOT_T_PLUS_ONE',
            'DATED_ALL_IN_FEES', 'MINIMUM_COMMISSION', 'SELL_TAX', 'EXCHANGE_INCLUSION',
            'SLIPPAGE_PRICE_AND_LIMIT_CHECK', 'FROZEN_CASH_SEQUENCE', 'NO_MARGIN_OR_SHORTS',
            'RAW_ONLY', 'UNKNOWN_TRADEABILITY_BLOCK', 'SUSPENSION_NO_EXECUTION',
            'CONSERVATIVE_DAILY_PRICE_LIMIT_PROXY', 'CASH_DIVIDEND_RECORD_EX_PAY',
            'EXACT_SPLIT_AND_BONUS_WITH_EXPLICIT_SETTLEMENT', 'NO_FACTOR_CASH_DOUBLE_COUNT',
            'POSITION_EXPOSURE_TURNOVER_LIMITS', 'DRAWDOWN_NEW_RISK_KILL',
            'INTEGER_CENT_AUDIT', 'GROSS_NET_BENCHMARK_DRAWDOWN', 'TERMINAL_OPEN_POSITIONS'],
        'unsupported_actions': ['RIGHTS', 'FRACTIONAL_SHARES_CASH_IN_LIEU',
            'DYNAMIC_HOLDING_PERIOD_DIVIDEND_TAX', 'NONADJACENT_SHARE_RECORD_EX',
            'MULTIPLE_SHARE_ACTIONS_SAME_EX_SECURITY'],
        'not_claimed': ['OBSERVED_AUCTION_FILLS', 'INTRADAY_QUEUE_OR_PARTIAL_FILL',
            'THREE_SCENARIO_COST_CALIBRATION', 'MINUTE_MAE_MFE',
            'ACTUAL_DATA_ADMISSION', 'ACTUAL_STRATEGY_OR_OWNER_POLICY',
            'BROKER_RECONCILIATION', 'FORMAL_BACKTEST_AUTHORITY'],
        'fixture_dataset_pinning': 'HASH_NOT_PIT_AUTHORITY;ACTION_VISIBLE_BY_RECORD_CLOSE',
        'money_representation': 'PYTHON_INTEGER_CNY_CENTS_FIXTURE_NOT_NATIVE_LEDGER_CONTRACT',
        'json_integer_max': JSON_INTEGER_MAX, 'decimal_precision': 100,
        'maximum_decimal_significant_input_digits': 50,
        'fixture_scale_limits': {'calendar_sessions': 5000, 'market_rows': 15000,
                                'decisions': 15000, 'open_lots': 1000,
                                'audit_state_units': 250000},
        'requires_before_formal': ['SEPARATE_HUMAN_OWNER_AUTHORIZATION',
            'ADMITTED_VERSIONED_HISTORICAL_PIT_SNAPSHOT', 'VERIFIED_DATED_TRADEABILITY',
            'PROVIDER_LICENSE_TRANSPORT_ADMISSION', 'OWNER_STRATEGY_EVALUATION_FREEZE',
            'EXPLICIT_ACCOUNT_COST_RISK_UNITS_POLICY', 'REVIEWED_REAL_ADAPTER'],
        'account_cost_risk_policy': UNSET, 'native_signal_order_broker_path': False})


def run_formal(*args, **kwargs):
    unavailable('WF_BT_FORMAL_BACKTEST_NOT_AUTHORIZED')
