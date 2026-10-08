import Decimal from 'decimal.js';

// Private constructor: never change Decimal's process-global arithmetic settings.
const ExactDecimal = Decimal.clone({ precision: 100, rounding: Decimal.ROUND_HALF_UP });
const REQUIRED_COST_FIELDS = [
  'version', 'provenance', 'effective_from', 'effective_to', 'currency',
  'commission_rate', 'minimum_commission_cents', 'commission_scope',
  'exchange_fee_rate', 'exchange_fee_included', 'stamp_tax_sell_rate',
  'other_fee_rate', 'other_fee_included', 'rounding_mode', 'slippage_treatment',
];

function reject(code, message = code) {
  const error = new Error(message);
  error.code = code;
  throw error;
}

export function parseCents(value, { nonnegative = false } = {}) {
  if (typeof value !== 'string' || !/^(?:0|-?[1-9][0-9]{0,37})$/.test(value)) {
    reject('INVALID_MONEY', 'Cents must be canonical integer strings of at most 38 digits.');
  }
  const result = BigInt(value);
  if (nonnegative && result < 0n) reject('NEGATIVE_MONEY');
  return result;
}

function centsString(value) {
  const result = value.toString();
  parseCents(result);
  return result;
}

function decimal(value, scale, { signed = false, positive = false } = {}) {
  const expression = signed ? /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/ : /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/;
  if (typeof value !== 'string' || !expression.test(value)) reject('INVALID_DECIMAL');
  const [whole, fraction = ''] = value.split('.');
  if (fraction.length > scale || whole.replace('-', '').length > 38) reject('DECIMAL_PRECISION_EXCEEDED');
  const result = new ExactDecimal(value);
  if (result.toFixed() !== value) reject('NONCANONICAL_DECIMAL');
  if (positive && !result.gt(0)) reject('NONPOSITIVE_PRICE');
  return result;
}

export function roundYuanToCents(value) {
  const yuan = decimal(value, 16, { signed: true });
  return centsString(BigInt(yuan.times(100).toDecimalPlaces(0, Decimal.ROUND_HALF_UP).toFixed(0)));
}

function componentCents(yuan) {
  return BigInt(yuan.times(100).toDecimalPlaces(0, Decimal.ROUND_HALF_UP).toFixed(0));
}

function validDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) reject('INVALID_TRADE_DATE');
  const instant = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(instant.valueOf()) || instant.toISOString().slice(0, 10) !== value) reject('INVALID_TRADE_DATE');
}

function quantity(value, allowZero = false) {
  if (!Number.isSafeInteger(value) || value < (allowZero ? 0 : 1)) reject('INVALID_QUANTITY');
}

export function validateCostConfig(config, trade_date) {
  if (!config || typeof config !== 'object' || Array.isArray(config)) reject('COST_CONFIG_REQUIRED');
  for (const field of REQUIRED_COST_FIELDS) {
    if (!Object.hasOwn(config, field) || config[field] === undefined || config[field] === 'UNSET_REQUIRED') {
      reject('UNSET_REQUIRED', `Missing cost parameter: ${field}`);
    }
  }
  if (typeof config.version !== 'string' || !config.version.length) reject('COST_VERSION_REQUIRED');
  if (!['SYNTHETIC_NOT_PRODUCTION', 'LEGACY_READ_ONLY'].includes(config.provenance)) reject('BASELINE_CONFIG_ONLY');
  if (config.currency !== 'CNY') reject('UNSUPPORTED_CURRENCY');
  if (config.commission_scope !== 'PER_ORDER') reject('UNSUPPORTED_COMMISSION_SCOPE');
  if (config.rounding_mode !== 'HALF_UP') reject('UNSUPPORTED_ROUNDING');
  if (config.slippage_treatment !== 'INCLUDED_IN_EXECUTION_PRICE') reject('SLIPPAGE_DOUBLE_COUNT_OR_UNRESOLVED');
  for (const field of ['exchange_fee_included', 'other_fee_included']) {
    if (typeof config[field] !== 'boolean') reject('FEE_INCLUSION_UNRESOLVED');
  }
  for (const field of ['commission_rate', 'exchange_fee_rate', 'stamp_tax_sell_rate', 'other_fee_rate']) {
    const rate = decimal(config[field], 10);
    if (rate.lt(0) || rate.gt(1)) reject('INVALID_FEE_RATE');
  }
  parseCents(config.minimum_commission_cents, { nonnegative: true });
  validDate(config.effective_from);
  if (config.effective_to !== null) validDate(config.effective_to);
  if (config.effective_to !== null && config.effective_to < config.effective_from) reject('INVALID_COST_VALIDITY');
  validDate(trade_date);
  if (trade_date < config.effective_from || (config.effective_to !== null && trade_date >= config.effective_to)) {
    reject('COST_VERSION_NOT_EFFECTIVE');
  }
  return config;
}

/** An estimate of ONE complete order. Partial-fill settlement is outside this P0 harness. */
export function estimateCost({ price, quantity: qty, side, trade_date, config }) {
  validateCostConfig(config, trade_date);
  quantity(qty);
  if (!['BUY', 'SELL'].includes(side)) reject('INVALID_SIDE');
  const notional = decimal(price, 6, { positive: true }).times(qty);
  const gross = componentCents(notional);
  const minimum = new ExactDecimal(config.minimum_commission_cents).div(100);
  const commission = componentCents(ExactDecimal.max(notional.times(config.commission_rate), minimum));
  const exchange = config.exchange_fee_included ? 0n : componentCents(notional.times(config.exchange_fee_rate));
  const other = config.other_fee_included ? 0n : componentCents(notional.times(config.other_fee_rate));
  const stamp = side === 'SELL' ? componentCents(notional.times(config.stamp_tax_sell_rate)) : 0n;
  const explicit = commission + exchange + other + stamp;
  const cashDelta = side === 'BUY' ? -(gross + explicit) : gross - explicit;
  return {
    cost_model_version: config.version,
    provenance: config.provenance,
    commission_scope: config.commission_scope,
    rounding_mode: config.rounding_mode,
    slippage_treatment: config.slippage_treatment,
    currency: 'CNY', side, quantity: qty, execution_price_yuan: price, trade_date,
    gross_notional_cents: centsString(gross),
    components_cents: {
      commission: centsString(commission), exchange: centsString(exchange),
      other: centsString(other), stamp: centsString(stamp),
    },
    explicit_fees_cents: centsString(explicit),
    cash_delta_cents: centsString(cashDelta),
    all_in_buy_cents: side === 'BUY' ? centsString(gross + explicit) : null,
  };
}

/** Largest lot-aligned BUY quantity that fits the fee-inclusive budget. No implicit lot size. */
export function affordableQty({ price, lot_size, budget_cents, max_quantity, trade_date, config }) {
  validateCostConfig(config, trade_date);
  decimal(price, 6, { positive: true });
  quantity(lot_size);
  quantity(max_quantity, true);
  const budget = parseCents(budget_cents, { nonnegative: true });
  let low = 0;
  let high = Math.floor(max_quantity / lot_size);
  while (low < high) {
    const middle = low + Math.ceil((high - low) / 2);
    const quote = estimateCost({ price, quantity: middle * lot_size, side: 'BUY', trade_date, config });
    if (BigInt(quote.all_in_buy_cents) <= budget) low = middle;
    else high = middle - 1;
  }
  return low * lot_size;
}
