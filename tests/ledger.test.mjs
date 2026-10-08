import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { replayFills, verifyLegacyIntegerSnapshot } from '../src/baseline/ledger.mjs';

const fixture = JSON.parse(await readFile(new URL('./fixtures/synthetic/economics.json', import.meta.url), 'utf8'));
const trading_calendar = fixture.trading_calendar;
const expectCode = (code, run) => assert.throws(run, error => error.code === code);

function opening(overrides = {}) {
  return {
    account_id: 'synthetic-shared-account', mode: 'DEV', currency: 'CNY',
    cash_cents: '30000', lots: [], applied_fill_ids: [], applied_order_ids: [],
    asof_event_time: '2026-09-27T15:00:00Z', last_execution_sequence: 0, ...overrides,
  };
}
function buy(overrides = {}) {
  return {
    fill_id: 'synthetic-buy-fill', order_id: 'synthetic-buy-order',
    account_id: 'synthetic-shared-account', mode: 'DEV', namespace: 'CORE_40',
    security_id: 'synthetic-security-1', side: 'BUY', quantity: 100,
    execution_price_yuan: '1.5', gross_notional_cents: '15000', explicit_fees_cents: '137', cash_delta_cents: '-15137',
    trade_date: '2026-09-28', event_time: '2026-09-28T09:30:00+08:00', execution_sequence: 1, lot_id: 'synthetic-lot',
    ...overrides,
  };
}
function sell(overrides = {}) {
  return {
    fill_id: 'synthetic-sell-fill', order_id: 'synthetic-sell-order',
    account_id: 'synthetic-shared-account', mode: 'DEV', namespace: 'CORE_40',
    security_id: 'synthetic-security-1', side: 'SELL', quantity: 100,
    execution_price_yuan: '2', gross_notional_cents: '20000', explicit_fees_cents: '101', cash_delta_cents: '19899',
    trade_date: '2026-09-29', event_time: '2026-09-29T09:30:00+08:00', execution_sequence: 2,
    lot_allocations: [{ lot_id: 'synthetic-lot', quantity: 100 }], ...overrides,
  };
}
function run(fills, state = opening(), options = {}) {
  return replayFills({ opening: state, fills, trading_calendar, ...options });
}
function preexistingLot(overrides = {}) {
  return { lot_id: 'synthetic-lot', namespace: 'CORE_40', security_id: 'synthetic-security-1', quantity: 100, acquired_trade_date: '2026-09-28', available_trade_date: '2026-09-29', ...overrides };
}

test('integer ledger independently reconciles cash/positions and does not mutate opening assets', () => {
  const state = opening();
  const frozen = structuredClone(state);
  const result = run([buy(), sell()], state, {
    expected: { account_id: state.account_id, mode: state.mode, cash_cents: '34762', lots: [] },
  });
  assert.equal(result.cash_cents, (30000n - 15000n - 137n + 20000n - 101n).toString());
  assert.deepEqual(result.lots, []);
  assert.deepEqual(state, frozen);
  assert.equal(result.entries.length, 2);
});

test('T+1 rejects same-day sale regardless of claimed human approval or override fields', () => {
  const invalid = sell({ trade_date: '2026-09-28', event_time: '2026-09-28T14:00:00+08:00', actor: 'USER', approval_id: 'synthetic-approval', override_t1: true });
  expectCode('T1_BLOCKED', () => run([buy(), invalid]));
});

test('T+1 uses supplied trading sessions across long gaps and requires the next session', () => {
  const purchased = buy({ trade_date: '2026-09-30', event_time: '2026-09-30T09:30:00+08:00' });
  const after = run([purchased]);
  assert.equal(after.lots[0].available_trade_date, '2026-10-08');
  assert.equal(run([sell({ trade_date: '2026-10-08', event_time: '2026-10-08T09:30:00+08:00' })], after).cash_cents, '34762');
  expectCode('CALENDAR_INCOMPLETE', () => run([buy({ trade_date: '2026-10-09', event_time: '2026-10-09T09:30:00+08:00' })]));
  expectCode('CALENDAR_INCOMPLETE', () => run([purchased, sell({ trade_date: '2026-10-01', event_time: '2026-10-01T09:30:00+08:00' })]));
});

test('same-day later sale proceeds cannot finance an earlier buy; ordering is never silently sorted', () => {
  const state = opening({ cash_cents: '10000', lots: [preexistingLot()], asof_event_time: '2026-09-28T15:00:00+08:00' });
  const earlyBuy = buy({ trade_date: '2026-09-29', event_time: '2026-09-29T09:30:00+08:00', lot_id: 'second-lot', security_id: 'synthetic-security-2' });
  const laterSell = sell({ event_time: '2026-09-29T14:00:00+08:00' });
  expectCode('INSUFFICIENT_CASH_AT_EVENT', () => run([earlyBuy, laterSell], state));
  expectCode('ACTION_ORDERING_INVALID', () => run([laterSell, { ...earlyBuy, execution_sequence: 3 }], state));
  const funded = run([
    sell({ execution_sequence: 1 }),
    { ...earlyBuy, event_time: '2026-09-29T14:00:00+08:00', execution_sequence: 2 },
  ], state);
  assert.equal(funded.cash_cents, '14762');
  assert.equal(funded.lots[0].security_id, 'synthetic-security-2');
});

test('snapshot chronology remains enforced across separate replay calls', () => {
  const after = run([buy(), sell()]);
  const earlier = buy({ fill_id: 'second-fill', order_id: 'second-order', lot_id: 'second-lot', event_time: '2026-09-28T14:00:00+08:00', execution_sequence: 3 });
  expectCode('ACTION_ORDERING_INVALID', () => run([earlier], after));
});

test('Core/Event share account cash, while their positions remain isolated', () => {
  const eventBuy = buy({ fill_id: 'event-fill', order_id: 'event-order', lot_id: 'event-lot', namespace: 'EVENT_3', execution_sequence: 2, event_time: '2026-09-28T10:00:00+08:00' });
  expectCode('INSUFFICIENT_CASH_AT_EVENT', () => run([buy(), eventBuy], opening({ cash_cents: '20000' })));
  const after = run([buy(), eventBuy], opening({ cash_cents: '40000' }));
  assert.equal(after.cash_cents, '9726');
  assert.equal(after.lots.length, 2);
  expectCode('STRATEGY_NAMESPACE_MISMATCH', () => run([sell({ namespace: 'EVENT_3', execution_sequence: 3 })], after));
  expectCode('STRATEGY_NAMESPACE_BLOCKED', () => run([buy({ namespace: 'RESEARCH_6_18M' })]));
  expectCode('STRATEGY_NAMESPACE_BLOCKED', () => run([buy({ namespace: 'legacy:V5' })]));
});

test('wrong account / mode / security cannot consume position or cash', () => {
  expectCode('ACCOUNT_MISMATCH', () => run([buy({ account_id: 'different-account' })]));
  expectCode('MODE_MISMATCH', () => run([buy({ mode: 'PAPER' })]));
  expectCode('SIMULATION_ONLY', () => run([], opening({ mode: 'PROD' })));
  expectCode('SIMULATION_ONLY', () => run([], opening({ mode: 'BACKTEST' })));
  expectCode('SECURITY_MISMATCH', () => run([buy(), sell({ security_id: 'different-security' })]));
});

test('duplicate fill and order application block within sequence and from persisted state', () => {
  const first = buy();
  expectCode('DUPLICATE_FILL', () => run([first, { ...first, execution_sequence: 2 }]));
  expectCode('DUPLICATE_ORDER_APPLICATION', () => run([first, { ...first, fill_id: 'different-fill', execution_sequence: 2 }]));
  const after = run([first]);
  expectCode('DUPLICATE_FILL', () => run([{ ...first, execution_sequence: 2 }], after));
  expectCode('DUPLICATE_ORDER_APPLICATION', () => run([{ ...first, fill_id: 'different-fill', execution_sequence: 2 }], after));
});

test('generated ledger rejects float money and incorrect gross, delta, snapshot cash and positions', () => {
  expectCode('INVALID_MONEY', () => run([buy({ gross_notional_cents: 15000 })]));
  expectCode('GROSS_NOTIONAL_MISMATCH', () => run([buy({ gross_notional_cents: '15001' })]));
  expectCode('CASH_DELTA_MISMATCH', () => run([buy({ cash_delta_cents: '-15000' })]));
  expectCode('LEDGER_CASH_MISMATCH', () => run([buy()], opening(), { expected: { account_id: 'synthetic-shared-account', mode: 'DEV', cash_cents: '30000', lots: [] } }));
  expectCode('LEDGER_POSITION_MISMATCH', () => run([buy()], opening(), { expected: { account_id: 'synthetic-shared-account', mode: 'DEV', cash_cents: '14863', lots: [] } }));
});

test('T+1 declared availability, lot quantities and timestamp context are mandatory', () => {
  expectCode('INVALID_T1_AVAILABILITY', () => run([], opening({ lots: [preexistingLot({ available_trade_date: '2026-09-28' })], asof_event_time: '2026-09-28T15:00:00+08:00' })));
  expectCode('FUTURE_OPENING_POSITION', () => run([], opening({ lots: [preexistingLot()] })));
  expectCode('LOT_QUANTITY_MISMATCH', () => run([buy(), sell({ lot_allocations: [{ lot_id: 'synthetic-lot', quantity: 99 }] })]));
  expectCode('DUPLICATE_LOT_ALLOCATION', () => run([buy(), sell({ lot_allocations: [{ lot_id: 'synthetic-lot', quantity: 50 }, { lot_id: 'synthetic-lot', quantity: 50 }] })]));
  expectCode('EVENT_TIME_REQUIRED', () => run([buy({ event_time: '2026-09-28T09:30:00' })]));
  expectCode('TRADE_DATE_TIME_MISMATCH', () => run([buy({ event_time: '2026-09-27T10:00:00Z' })]));
});

test('legacy integer adapter preserves raw units and independently checks cash, quantity and NAV', () => {
  const rows = [
    { type: 'TRADE', symbol: 'legacy:example', side: 'BUY', qty: 101, price_mills: 1337, gross_cents: 13504, fees: { commission: 137, transfer: 1, stamp: 0 }, cash_delta: -13642 },
    { type: 'CASH_ACTION', net_cash_cents: 17, cash_delta: 17 },
  ];
  const snapshot = { cash_cents: 16375, nav_cents: 30525, positions: { 'legacy:example': { qty: 101, mark: 1401 } } };
  const result = verifyLegacyIntegerSnapshot({ opening_cash_cents: '30000', rows, snapshot });
  assert.equal(result.cash_cents, '16375');
  assert.equal(result.nav_cents, '30525');
  assert.equal(result.provenance, 'LEGACY_READ_ONLY');
  assert.deepEqual(result.positions, { 'legacy:example': '101' });
  expectCode('LEGACY_CASH_DELTA_MISMATCH', () => verifyLegacyIntegerSnapshot({ opening_cash_cents: '30000', rows: [{ ...rows[0], cash_delta: -13504 }], snapshot }));
  expectCode('LEGACY_GROSS_MISMATCH', () => verifyLegacyIntegerSnapshot({ opening_cash_cents: '30000', rows: [{ ...rows[0], gross_cents: 13505 }], snapshot }));
  expectCode('LEGACY_NAV_MISMATCH', () => verifyLegacyIntegerSnapshot({ opening_cash_cents: '30000', rows, snapshot: { ...snapshot, nav_cents: 30524 } }));
  expectCode('INVALID_MONEY', () => verifyLegacyIntegerSnapshot({ opening_cash_cents: Number.MAX_SAFE_INTEGER + 1, rows, snapshot }));
});
