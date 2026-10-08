import Decimal from 'decimal.js';
import { createHash } from 'node:crypto';

// Private arithmetic context: caller Decimal.set() cannot change settlement.
const D = Decimal.clone({ precision: 100, rounding: Decimal.ROUND_HALF_UP });
const VERSION = '1.0.0';
const SCOPE = 'ECONOMIC_DIAGNOSTIC_ONLY';
const COMPONENTS = ['commission', 'stamp_tax', 'exchange_fee', 'clearing_fee', 'regulatory_fee', 'other_fee', 'slippage'];
const COMMON = ['rate', 'rate_unit', 'sides', 'effective_from', 'effective_to', 'evidence_ref'];
const TOP = ['contract_name', 'contract_version', 'profile_id', 'profile_version', 'profile_scope', 'production_enabled', 'currency', 'money_unit', 'rounding_mode', 'commission_scope', 'market', 'instrument_kind', 'trading_method', 'source', ...COMPONENTS, 'content_hash'];
const EXTRA = { commission: ['minimum_cents'], stamp_tax: ['included_in'], exchange_fee: ['included_in'], clearing_fee: ['included_in'], regulatory_fee: ['included_in'], other_fee: ['included_in'], slippage: ['treatment'] };
const PRICE = /^(0|[1-9][0-9]{0,13})(\.[0-9]{1,6})?$/;
const RATE = /^(0|1)(\.[0-9]{1,12})?$/;
const CENTS = /^(0|[1-9][0-9]{0,37})$/;
const ID = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$/;
const HASH = /^sha256:[a-f0-9]{64}$/;
const UNKNOWN = x => x === undefined || x === null || x === 'UNKNOWN' || x === 'UNSET_REQUIRED';
const plain = x => x !== null && typeof x === 'object' && !Array.isArray(x) && Object.getPrototypeOf(x) === Object.prototype;
const sorted = x => Array.isArray(x) ? x.map(sorted) : plain(x) ? Object.fromEntries(Object.keys(x).sort().map(k => [k, sorted(x[k])])) : x;
const digest = x => 'sha256:' + createHash('sha256').update(JSON.stringify(sorted(x))).digest('hex');
const date = x => typeof x === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(x) && Number.isFinite(Date.parse(x + 'T00:00:00Z')) && new Date(x + 'T00:00:00Z').toISOString().slice(0, 10) === x;
const fail = code => { throw Object.assign(new Error(code), { code }); };
const check = (ok, code) => { if (!ok) fail(code); };
const exact = (x, keys) => plain(x) && Object.keys(x).length === keys.length && keys.every(k => Object.hasOwn(x, k));
const round = x => new D(x).times(100).toDecimalPlaces(0, D.ROUND_HALF_UP).toFixed(0);
const money = x => { check(typeof x === 'string' && CENTS.test(x), 'INTEGER_CENTS_REQUIRED'); return BigInt(x); };
const rate = x => { check(typeof x === 'string' && RATE.test(x) && new D(x).gte(0) && new D(x).lte(1), 'FRACTION_RATE_REQUIRED'); return new D(x); };
function readPrice(x) { check(typeof x === 'string' && PRICE.test(x) && new D(x).gt(0), 'EXACT_POSITIVE_PRICE_REQUIRED'); return new D(x); }

function required(profile) {
  const missing = [];
  if (!plain(profile)) return ['profile'];
  for (const key of TOP) if (UNKNOWN(profile[key])) missing.push(key);
  for (const key of COMPONENTS) {
    if (!plain(profile[key])) { if (!UNKNOWN(profile[key])) missing.push(key + '.fields'); continue; }
    for (const field of [...COMMON, ...EXTRA[key]]) if (UNKNOWN(profile[key][field])) missing.push(key + '.' + field);
  }
  if (plain(profile.source)) for (const key of ['kind', 'evidence_id', 'description']) if (UNKNOWN(profile.source[key])) missing.push('source.' + key);
  return missing;
}

function validate(profile, trade_date) {
  check(exact(profile, TOP), 'PROFILE_CLOSED_SCHEMA_REQUIRED');
  check(profile.contract_name === 'EconomicDiagnosticCostProfile' && profile.contract_version === VERSION, 'PROFILE_VERSION_INVALID');
  check(typeof profile.profile_id === 'string' && ID.test(profile.profile_id) && Number.isSafeInteger(profile.profile_version) && profile.profile_version > 0, 'PROFILE_ID_VERSION_INVALID');
  check(profile.production_enabled === false, 'PRODUCTION_DISABLED');
  check(['SYNTHETIC_FIXTURE', 'ACTUAL_ACCOUNT'].includes(profile.profile_scope), 'PROFILE_SCOPE_INVALID');
  check(profile.currency === 'CNY' && profile.money_unit === 'INTEGER_CENTS_STRING' && profile.rounding_mode === 'HALF_UP' && profile.commission_scope === 'PER_ORDER_CUMULATIVE', 'SETTLEMENT_POLICY_UNSUPPORTED');
  check(profile.market === 'SSE' && profile.instrument_kind === 'A_SHARE' && profile.trading_method === 'AUCTION', 'PRODUCT_SCOPE_INVALID');
  check(date(trade_date), 'TRADE_DATE_INVALID');
  const { content_hash, ...body } = profile;
  check(typeof content_hash === 'string' && HASH.test(content_hash) && content_hash === digest(body), 'PROFILE_HASH_MISMATCH');
  // Evidence admission is intentionally unavailable for actual broker profiles.
  // Labels, owner inputs and self hashes are not document verification.
  check(profile.profile_scope === 'SYNTHETIC_FIXTURE', 'ACTUAL_ACCOUNT_EVIDENCE_NOT_ADMITTED');
  check(exact(profile.source, ['kind', 'evidence_id', 'description']) && profile.source.kind === 'SYNTHETIC_FIXTURE' && typeof profile.source.evidence_id === 'string' && ID.test(profile.source.evidence_id) && typeof profile.source.description === 'string' && profile.source.description.length > 0 && profile.source.description.length <= 1000, 'SYNTHETIC_PROVENANCE_REQUIRED');
  for (const name of COMPONENTS) {
    const c = profile[name];
    check(exact(c, [...COMMON, ...EXTRA[name]]), 'COMPONENT_CLOSED_SCHEMA_REQUIRED');
    rate(c.rate);
    check(c.rate_unit === 'FRACTION_OF_NOTIONAL', 'RATE_UNIT_UNSUPPORTED');
    check(Array.isArray(c.sides) && c.sides.length > 0 && c.sides.length <= 2 && new Set(c.sides).size === c.sides.length && c.sides.every(x => x === 'BUY' || x === 'SELL'), 'COMPONENT_SIDES_INVALID');
    check(date(c.effective_from) && date(c.effective_to) && c.effective_from <= c.effective_to && c.effective_from <= trade_date && trade_date <= c.effective_to, 'COMPONENT_DATE_OUT_OF_SCOPE');
    check(c.evidence_ref === 'SYNTHETIC:' + profile.source.evidence_id, 'COMPONENT_EVIDENCE_NOT_BOUND');
    if (name === 'commission') money(c.minimum_cents);
    if (name !== 'commission' && name !== 'slippage') check(['COMMISSION', 'SEPARATE'].includes(c.included_in), 'FEE_INCLUSION_REQUIRED');
    if (name !== 'commission' && name !== 'slippage' && c.included_in === 'COMMISSION') check(c.sides.every(s => profile.commission.sides.includes(s)), 'INCLUDED_FEE_WITHOUT_COMMISSION_SIDE');
    if (name === 'stamp_tax') check(c.sides.length === 1 && c.sides[0] === 'SELL' && c.included_in === 'SEPARATE', 'STAMP_TAX_SIDE_OR_INCLUSION_INVALID');
    if (name === 'slippage') {
      check(['INCLUDED_IN_EXECUTION_PRICE', 'SEPARATE_ESTIMATE'].includes(c.treatment), 'SLIPPAGE_TREATMENT_REQUIRED');
      check(c.treatment !== 'INCLUDED_IN_EXECUTION_PRICE' || new D(c.rate).eq(0), 'SLIPPAGE_DOUBLE_COUNTING');
    }
  }
}

function readFills(fills) {
  check(Array.isArray(fills) && fills.length > 0 && fills.length <= 10000, 'NONEMPTY_FILLS_REQUIRED');
  let exactNotional = new D(0), gross = 0n, quantity = 0;
  for (const fill of fills) {
    check(exact(fill, ['price', 'quantity']), 'FILL_CLOSED_SCHEMA_REQUIRED');
    check(Number.isSafeInteger(fill.quantity) && fill.quantity > 0, 'POSITIVE_SAFE_QUANTITY_REQUIRED');
    quantity += fill.quantity; check(Number.isSafeInteger(quantity), 'QUANTITY_OVERFLOW');
    const n = readPrice(fill.price).times(fill.quantity);
    exactNotional = exactNotional.plus(n); gross += BigInt(round(n));
  }
  check(gross < 10n ** 38n, 'MONEY_OVERFLOW');
  return { exactNotional, gross, quantity };
}

function calculate(profile, side, fills) {
  check(side === 'BUY' || side === 'SELL', 'ORDER_SIDE_INVALID');
  const { exactNotional, gross, quantity } = readFills(fills);
  const fees = {}, reference = {};
  for (const name of COMPONENTS) {
    const c = profile[name];
    const applicable = c.sides.includes(side);
    const proportional = applicable ? BigInt(round(exactNotional.times(rate(c.rate)))) : 0n;
    reference[name + '_proportional_cents'] = proportional.toString();
    if (name === 'commission') {
      const minimum = applicable ? money(c.minimum_cents) : 0n;
      fees.commission_cents = (proportional < minimum ? minimum : proportional).toString();
      reference.minimum_commission_effect_cents = (proportional < minimum ? minimum - proportional : 0n).toString();
    } else {
      const extra = name === 'slippage' ? c.treatment === 'SEPARATE_ESTIMATE' : c.included_in === 'SEPARATE';
      fees[name + '_cents'] = (extra ? proportional : 0n).toString();
    }
  }
  const friction = Object.values(fees).reduce((s, x) => s + BigInt(x), 0n);
  check(friction < 10n ** 38n && gross + friction < 10n ** 38n, 'MONEY_OVERFLOW');
  return { side, quantity, notional_cents: gross.toString(), exact_notional_yuan: exactNotional.toFixed(), ...fees, ...reference, total_friction_cents: friction.toString(), cash_delta_cents: (side === 'BUY' ? -gross - friction : gross - friction).toString(), included_relationship: Object.fromEntries(COMPONENTS.filter(x => !['commission', 'slippage'].includes(x)).map(x => [x, profile[x].included_in])), slippage_treatment: profile.slippage.treatment };
}

function result(status, reasons, body = {}) {
  const value = { contract_name: 'EconomicDiagnosticCostResult', contract_version: VERSION, mode: SCOPE, scope: SCOPE, status, reason_codes: reasons, missing_fields: [], source_refs: [], net_edge_cents: null, production_enabled: false, safe_to_trade: false, native_authority: false, historical_pit_proven: false, source_admission: false, evidence_tier: status === 'COMPUTABLE_SYNTHETIC_ONLY' ? 'SYNTHETIC_NOT_REAL' : 'NOT_ADMITTED', ...body };
  return { ...value, content_hash: digest(value) };
}
function modeCheck(mode) { check(mode === SCOPE, 'MODE_NOT_AUTHORIZED'); }
function ref(profile) { return { profile_id: profile.profile_id, profile_version: profile.profile_version, content_hash: profile.content_hash }; }
function sources(profile) { return COMPONENTS.map(component => ({ component, evidence_ref: profile[component].evidence_ref, evidence_kind: 'SYNTHETIC_FIXTURE', production_admitted: false })); }
function blocked(error) { return result('NOT_COMPUTABLE', [error.code || 'INVALID_INPUT'], { profile_ref: null, request_hash: null }); }

export function quoteCost(request = {}) {
  try {
    check(plain(request), 'REQUEST_OBJECT_REQUIRED');
    const { mode, profile, side, fills, trade_date } = request;
    modeCheck(mode);
    check(exact(request, ['mode', 'profile', 'side', 'fills', 'trade_date']), 'REQUEST_CLOSED_SCHEMA_REQUIRED');
    const missing = required(profile);
    if (missing.length) return result('NOT_COMPUTABLE', ['REQUIRED_COST_CONFIG_UNSET'], { missing_fields: missing, profile_ref: null, request_hash: null });
    validate(profile, trade_date);
    const quote = calculate(profile, side, fills);
    return result('COMPUTABLE_SYNTHETIC_ONLY', ['SYNTHETIC_ARITHMETIC_ONLY'], { profile_ref: ref(profile), source_refs: sources(profile), request_hash: digest({ mode, profile_hash: profile.content_hash, side, fills, trade_date }), trade_date, ...quote });
  } catch (error) { return blocked(error); }
}

export function netEdge(request = {}) {
  try {
    check(plain(request), 'REQUEST_OBJECT_REQUIRED');
    const { mode, profile, buy_fills, sell_fills, buy_date, sell_date } = request;
    modeCheck(mode);
    check(exact(request, ['mode', 'profile', 'buy_fills', 'sell_fills', 'buy_date', 'sell_date']), 'REQUEST_CLOSED_SCHEMA_REQUIRED');
    const missing = required(profile);
    if (missing.length) return result('NOT_COMPUTABLE', ['REQUIRED_COST_CONFIG_UNSET'], { missing_fields: missing, profile_ref: null, request_hash: null });
    validate(profile, buy_date); validate(profile, sell_date);
    check(buy_date <= sell_date, 'ROUND_TRIP_DATE_INVALID');
    const buy = calculate(profile, 'BUY', buy_fills), sell = calculate(profile, 'SELL', sell_fills);
    check(buy.quantity === sell.quantity, 'ROUND_TRIP_QUANTITY_MISMATCH');
    const edge = BigInt(buy.cash_delta_cents) + BigInt(sell.cash_delta_cents);
    check(edge > -(10n ** 38n) && edge < 10n ** 38n, 'MONEY_OVERFLOW');
    return result('COMPUTABLE_SYNTHETIC_ONLY', ['SYNTHETIC_ARITHMETIC_ONLY'], { profile_ref: ref(profile), source_refs: sources(profile), request_hash: digest({ mode, profile_hash: profile.content_hash, buy_fills, sell_fills, buy_date, sell_date }), buy_date, sell_date, buy, sell, gross_edge_cents: (BigInt(sell.notional_cents) - BigInt(buy.notional_cents)).toString(), net_edge_cents: edge.toString() });
  } catch (error) { return blocked(error); }
}
