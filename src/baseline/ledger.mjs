// Independent integer reconciliation. Deliberately does not import the cost estimator.
const TRADE_NAMESPACES = new Set(['CORE_40', 'EVENT_3']);
const SIMULATION_MODES = new Set(['PAPER', 'DEV']);

function reject(code, message = code) {
  const error = new Error(message);
  error.code = code;
  throw error;
}

function cents(value, { legacy = false, nonnegative = false } = {}) {
  // Safe integer acceptance exists only in the explicitly legacy reconciliation adapter.
  if (legacy && Number.isSafeInteger(value)) value = String(value);
  if (typeof value !== 'string' || !/^(?:0|-?[1-9][0-9]{0,37})$/.test(value)) reject('INVALID_MONEY');
  const result = BigInt(value);
  if (nonnegative && result < 0n) reject('NEGATIVE_MONEY');
  return result;
}

function checkedMoney(value) {
  const result = value.toString();
  cents(result);
  return result;
}

function qty(value, { zero = false } = {}) {
  if (!Number.isSafeInteger(value) || value < (zero ? 0 : 1)) reject('INVALID_QUANTITY');
  return value;
}

function id(value) {
  if (typeof value !== 'string' || !value.length || value === 'UNSET_REQUIRED') reject('IDENTITY_REQUIRED');
  return value;
}

function validDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) reject('INVALID_TRADE_DATE');
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value) reject('INVALID_TRADE_DATE');
  return value;
}

function calendarIndex(dates) {
  if (!Array.isArray(dates) || dates.length < 2) reject('CALENDAR_REQUIRED');
  const index = new Map();
  let previous = '';
  dates.forEach((date, position) => {
    validDate(date);
    if (date <= previous) reject('INVALID_TRADING_CALENDAR');
    index.set(date, position);
    previous = date;
  });
  return index;
}

function tradingDate(timestamp) {
  if (typeof timestamp !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.test(timestamp)) {
    reject('EVENT_TIME_REQUIRED');
  }
  validDate(timestamp.slice(0, 10));
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.valueOf())) reject('INVALID_EVENT_TIME');
  const wallTime = timestamp.slice(11, 19);
  if (wallTime > '23:59:59' || Number(wallTime.slice(3, 5)) > 59 || Number(wallTime.slice(6, 8)) > 59) reject('INVALID_EVENT_TIME');
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(parsed);
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]));
  return { day: `${values.year}-${values.month}-${values.day}`, time: parsed.valueOf() };
}

function exactPriceGross(price, quantity) {
  if (typeof price !== 'string' || !/^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?$/.test(price) || price.endsWith('.0') || /\.[0-9]*0$/.test(price)) {
    reject('INVALID_DECIMAL');
  }
  const [whole, fraction = ''] = price.split('.');
  if (whole.length > 38) reject('DECIMAL_PRECISION_EXCEEDED');
  const denominator = 10n ** BigInt(fraction.length);
  const numerator = BigInt(whole + fraction) * BigInt(quantity) * 100n;
  if (numerator === 0n) reject('NONPOSITIVE_PRICE');
  return (numerator * 2n + denominator) / (denominator * 2n);
}

/**
 * Applies a caller-supplied chronological sequence of complete simulation fills.
 * It never sorts, supplies approval, executes orders, or copies account cash per strategy.
 */
export function replayFills({ opening, fills, trading_calendar, expected }) {
  if (!opening || !Array.isArray(fills)) reject('LEDGER_INPUT_REQUIRED');
  const account = id(opening.account_id);
  if (!SIMULATION_MODES.has(opening.mode)) reject('SIMULATION_ONLY');
  if (opening.currency !== 'CNY') reject('UNSUPPORTED_CURRENCY');
  if (!Array.isArray(opening.lots) || !Array.isArray(opening.applied_fill_ids) || !Array.isArray(opening.applied_order_ids)) {
    reject('LEDGER_STATE_REQUIRED');
  }
  const calendar = calendarIndex(trading_calendar);
  const openingEvent = tradingDate(opening.asof_event_time);
  qty(opening.last_execution_sequence, { zero: true });
  let cash = cents(opening.cash_cents, { nonnegative: true });
  const lots = new Map();
  for (const original of opening.lots) {
    const lot = structuredClone(original);
    if (lots.has(id(lot.lot_id))) reject('DUPLICATE_LOT');
    if (!TRADE_NAMESPACES.has(lot.namespace)) reject('STRATEGY_NAMESPACE_BLOCKED');
    id(lot.security_id);
    qty(lot.quantity);
    validDate(lot.acquired_trade_date);
    validDate(lot.available_trade_date);
    if (lot.acquired_trade_date > openingEvent.day) reject('FUTURE_OPENING_POSITION');
    const acquired = calendar.get(lot.acquired_trade_date);
    if (acquired === undefined || !calendar.has(lot.available_trade_date)) reject('CALENDAR_INCOMPLETE');
    if (trading_calendar[acquired + 1] !== lot.available_trade_date) reject('INVALID_T1_AVAILABILITY');
    lots.set(lot.lot_id, lot);
  }
  const appliedFills = new Set(opening.applied_fill_ids.map(id));
  const appliedOrders = new Set(opening.applied_order_ids.map(id));
  if (appliedFills.size !== opening.applied_fill_ids.length || appliedOrders.size !== opening.applied_order_ids.length) reject('DUPLICATE_EXECUTION_HISTORY');
  let previousTime = openingEvent.time;
  let previousSequence = opening.last_execution_sequence;
  let asof = opening.asof_event_time;
  const entries = [];
  for (const fill of fills) {
    const fillId = id(fill.fill_id);
    const orderId = id(fill.order_id);
    if (fill.account_id !== account) reject('ACCOUNT_MISMATCH');
    if (fill.mode !== opening.mode) reject('MODE_MISMATCH');
    if (!TRADE_NAMESPACES.has(fill.namespace)) reject('STRATEGY_NAMESPACE_BLOCKED');
    if (appliedFills.has(fillId)) reject('DUPLICATE_FILL');
    if (appliedOrders.has(orderId)) reject('DUPLICATE_ORDER_APPLICATION');
    qty(fill.quantity);
    qty(fill.execution_sequence);
    const event = tradingDate(fill.event_time);
    validDate(fill.trade_date);
    if (event.day !== fill.trade_date) reject('TRADE_DATE_TIME_MISMATCH');
    const dayIndex = calendar.get(fill.trade_date);
    if (dayIndex === undefined) reject('CALENDAR_INCOMPLETE');
    if (event.time < previousTime || fill.execution_sequence <= previousSequence) reject('ACTION_ORDERING_INVALID');
    const gross = cents(fill.gross_notional_cents, { nonnegative: true });
    if (gross !== exactPriceGross(fill.execution_price_yuan, fill.quantity)) reject('GROSS_NOTIONAL_MISMATCH');
    const fees = cents(fill.explicit_fees_cents, { nonnegative: true });
    const delta = cents(fill.cash_delta_cents);
    const security = id(fill.security_id);
    if (fill.side === 'BUY') {
      if (delta !== -(gross + fees)) reject('CASH_DELTA_MISMATCH');
      if (cash + delta < 0n) reject('INSUFFICIENT_CASH_AT_EVENT');
      const lotId = id(fill.lot_id);
      if (lots.has(lotId)) reject('DUPLICATE_LOT');
      const available = trading_calendar[dayIndex + 1];
      if (!available) reject('CALENDAR_INCOMPLETE');
      lots.set(lotId, {
        lot_id: lotId, namespace: fill.namespace, security_id: security, quantity: fill.quantity,
        acquired_trade_date: fill.trade_date, available_trade_date: available,
      });
    } else if (fill.side === 'SELL') {
      if (delta !== gross - fees) reject('CASH_DELTA_MISMATCH');
      if (!Array.isArray(fill.lot_allocations) || !fill.lot_allocations.length) reject('SELL_LOT_ALLOCATION_REQUIRED');
      const allocations = new Set();
      let allocated = 0n;
      // Validate the complete sell before applying any changes to lots.
      for (const allocation of fill.lot_allocations) {
        if (allocations.has(id(allocation.lot_id))) reject('DUPLICATE_LOT_ALLOCATION');
        allocations.add(allocation.lot_id);
        const lot = lots.get(allocation.lot_id);
        if (!lot) reject('LOT_NOT_FOUND');
        if (lot.namespace !== fill.namespace) reject('STRATEGY_NAMESPACE_MISMATCH');
        if (lot.security_id !== security) reject('SECURITY_MISMATCH');
        qty(allocation.quantity);
        if (allocation.quantity > lot.quantity) reject('INSUFFICIENT_POSITION');
        if (fill.trade_date < lot.available_trade_date) reject('T1_BLOCKED');
        allocated += BigInt(allocation.quantity);
      }
      if (allocated !== BigInt(fill.quantity)) reject('LOT_QUANTITY_MISMATCH');
      for (const allocation of fill.lot_allocations) {
        const lot = lots.get(allocation.lot_id);
        lot.quantity -= allocation.quantity;
        if (!lot.quantity) lots.delete(lot.lot_id);
      }
    } else reject('INVALID_SIDE');
    cash += delta;
    if (cash < 0n) reject('INSUFFICIENT_CASH_AT_EVENT');
    checkedMoney(cash);
    appliedFills.add(fillId);
    appliedOrders.add(orderId);
    entries.push({ fill_id: fillId, order_id: orderId, account_id: account, namespace: fill.namespace, mode: opening.mode, cash_delta_cents: checkedMoney(delta), cash_after_cents: checkedMoney(cash) });
    previousTime = event.time;
    previousSequence = fill.execution_sequence;
    asof = fill.event_time;
  }
  const result = {
    account_id: account, mode: opening.mode, currency: 'CNY', cash_cents: checkedMoney(cash),
    lots: [...lots.values()].sort((a, b) => a.lot_id < b.lot_id ? -1 : a.lot_id > b.lot_id ? 1 : 0),
    applied_fill_ids: [...appliedFills], applied_order_ids: [...appliedOrders], entries,
    asof_event_time: asof, last_execution_sequence: previousSequence,
  };
  if (expected) {
    if (expected.account_id !== account || expected.mode !== opening.mode) reject('EXPECTED_NAMESPACE_MISMATCH');
    if (cents(expected.cash_cents) !== cash) reject('LEDGER_CASH_MISMATCH');
    if (!Array.isArray(expected.lots)) reject('EXPECTED_LOTS_REQUIRED');
    const normalize = input => input.map(lot => `${lot.lot_id}|${lot.namespace}|${lot.security_id}|${lot.quantity}|${lot.acquired_trade_date}|${lot.available_trade_date}`).sort();
    if (JSON.stringify(normalize(expected.lots)) !== JSON.stringify(normalize(result.lots))) reject('LEDGER_POSITION_MISMATCH');
  }
  return result;
}

function legacyRoundMills(priceMills, quantity) {
  const numerator = cents(priceMills, { legacy: true, nonnegative: true }) * BigInt(qty(quantity));
  return (numerator + 5n) / 10n;
}

/** Read-only V5-style arithmetic verifier; does not relabel its experiment or infer fee rules. */
export function verifyLegacyIntegerSnapshot({ opening_cash_cents, opening_positions = [], rows, snapshot }) {
  if (!Array.isArray(rows) || !snapshot) reject('LEGACY_INPUT_REQUIRED');
  let cash = cents(opening_cash_cents, { legacy: true, nonnegative: true });
  const positions = new Map();
  for (const position of opening_positions) {
    if (positions.has(id(position.symbol))) reject('DUPLICATE_POSITION');
    positions.set(position.symbol, BigInt(qty(position.quantity)));
  }
  for (const row of rows) {
    const delta = cents(row.cash_delta, { legacy: true });
    if (row.type === 'TRADE') {
      const quantity = BigInt(qty(row.qty));
      const symbol = id(row.symbol);
      const gross = cents(row.gross_cents, { legacy: true, nonnegative: true });
      if (Object.hasOwn(row, 'price_mills') && legacyRoundMills(row.price_mills, row.qty) !== gross) reject('LEGACY_GROSS_MISMATCH');
      if (!row.fees || typeof row.fees !== 'object' || Array.isArray(row.fees) || !Object.keys(row.fees).length) reject('LEGACY_ITEMIZED_FEES_REQUIRED');
      const fees = Object.values(row.fees).reduce((sum, value) => sum + cents(value, { legacy: true, nonnegative: true }), 0n);
      const existing = positions.get(symbol) ?? 0n;
      if (row.side === 'BUY') {
        if (delta !== -(gross + fees)) reject('LEGACY_CASH_DELTA_MISMATCH');
        positions.set(symbol, existing + quantity);
      } else if (row.side === 'SELL') {
        if (delta !== gross - fees) reject('LEGACY_CASH_DELTA_MISMATCH');
        if (existing < quantity) reject('LEGACY_NEGATIVE_POSITION');
        if (existing === quantity) positions.delete(symbol);
        else positions.set(symbol, existing - quantity);
      } else reject('INVALID_SIDE');
    } else if (row.type === 'CASH_ACTION') {
      if (delta !== cents(row.net_cash_cents, { legacy: true, nonnegative: true })) reject('LEGACY_CASH_ACTION_MISMATCH');
    } else reject('LEGACY_UNSUPPORTED_ENTRY');
    cash += delta;
    if (cash < 0n) reject('LEGACY_NEGATIVE_CASH');
    checkedMoney(cash);
  }
  if (cash !== cents(snapshot.cash_cents, { legacy: true })) reject('LEGACY_CASH_MISMATCH');
  const snapshotPositions = snapshot.positions;
  if (!snapshotPositions || typeof snapshotPositions !== 'object' || Array.isArray(snapshotPositions)) reject('LEGACY_SNAPSHOT_POSITIONS_REQUIRED');
  if (positions.size !== Object.keys(snapshotPositions).length) reject('LEGACY_POSITION_MISMATCH');
  for (const [symbol, position] of Object.entries(snapshotPositions)) {
    if (positions.get(symbol) !== BigInt(qty(position.qty))) reject('LEGACY_POSITION_MISMATCH');
  }
  let nav = null;
  if (Object.hasOwn(snapshot, 'nav_cents')) {
    nav = cash;
    for (const position of Object.values(snapshotPositions)) nav += legacyRoundMills(position.mark, position.qty);
    if (nav !== cents(snapshot.nav_cents, { legacy: true })) reject('LEGACY_NAV_MISMATCH');
  }
  return {
    cash_cents: checkedMoney(cash), nav_cents: nav === null ? null : checkedMoney(nav),
    positions: Object.fromEntries([...positions.entries()].map(([symbol, quantity]) => [symbol, quantity.toString()])),
    provenance: 'LEGACY_READ_ONLY',
  };
}
