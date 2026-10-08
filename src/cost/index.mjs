import Decimal from 'decimal.js';
import { hashValue } from '../contracts/validate.mjs';

// This constructor is private; caller Decimal.set() cannot weaken arithmetic.
const D = Decimal.clone({ precision: 100, rounding: Decimal.ROUND_HALF_UP });
const centsPattern = /^(0|[1-9][0-9]{0,37})$/;
const pricePattern = /^(0|[1-9][0-9]{0,13})(\.[0-9]{1,6})?$/;
const ratePattern = /^(0|1)(\.[0-9]{1,10})?$/;
export class EconomicViolation extends Error {
  constructor(code) { super(code); this.name = 'EconomicViolation'; this.code = code; }
}
export function ensure(condition, code) { if (!condition) throw new EconomicViolation(code); }
export function assertPaperMode(mode) { ensure(mode === 'DEV' || mode === 'PAPER', 'PRODUCTION_DISABLED_P1A'); }
export function cents(value) { ensure(typeof value === 'string' && centsPattern.test(value), 'INTEGER_CENTS_REQUIRED'); return BigInt(value); }
export function quantity(value) { ensure(Number.isSafeInteger(value) && value > 0, 'POSITIVE_SAFE_QUANTITY_REQUIRED'); return value; }
export function price(value) { ensure(typeof value === 'string' && pricePattern.test(value) && new D(value).gt(0), 'EXACT_PRICE_REQUIRED'); return new D(value); }
function rate(value) { ensure(typeof value === 'string' && ratePattern.test(value) && new D(value).gte(0) && new D(value).lte(1), 'EXACT_RATE_REQUIRED'); return new D(value); }
export function roundCents(yuan) { return new D(yuan).times(100).toDecimalPlaces(0, D.ROUND_HALF_UP).toFixed(0); }
export function grossNotionalCents(unitPrice, qty) { return roundCents(price(unitPrice).times(quantity(qty))); }
export function sealCostProfile(value) { const { content_hash, ...body } = structuredClone(value); return { ...body, content_hash: hashValue(body) }; }
function validDate(value) {
  if(typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date=new Date(`${value}T00:00:00Z`);return Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value;
}
export function validateCostProfile(profile, { mode, trade_date }) {
  assertPaperMode(mode);
  ensure(profile && profile.contract_name === 'CostProfile' && profile.contract_version === '1.0.0', 'COST_PROFILE_VERSION_INVALID');
  ensure(profile.profile_scope === 'SYNTHETIC_TEST_ONLY' && profile.production_enabled === false, 'COST_PROFILE_SCOPE_INVALID');
  ensure(typeof profile.object_id === 'string' && profile.object_id && Number.isSafeInteger(profile.object_version) && profile.object_version > 0, 'COST_PROFILE_ID_INVALID');
  const { content_hash, ...body } = profile;
  ensure(content_hash === hashValue(body), 'COST_PROFILE_HASH_MISMATCH');
  ensure(profile.currency === 'CNY' && profile.money_unit === 'INTEGER_CENTS_STRING' && profile.rounding_mode === 'HALF_UP' && profile.commission_scope === 'PER_ORDER', 'COST_SETTLEMENT_POLICY_UNSUPPORTED');
  ensure(validDate(trade_date) && profile.effective_from <= trade_date && trade_date <= profile.effective_to, 'COST_PROFILE_DATE_INVALID');
  ensure(validDate(profile.effective_from) && validDate(profile.effective_to) && profile.effective_from <= profile.effective_to, 'COST_PROFILE_DATE_INVALID');
  rate(profile.commission_rate); cents(profile.minimum_commission_cents); rate(profile.stamp_tax_sell_rate);
  for (const key of ['exchange_fee', 'other_fee']) {
    ensure(profile[key] && ['COMMISSION', 'EXCLUDED'].includes(profile[key].included_in), 'FEE_INCLUSION_REQUIRED');
    rate(profile[key].rate);
  }
  ensure(profile.slippage && ['INCLUDED_IN_EXECUTION_PRICE', 'SEPARATE_ESTIMATE'].includes(profile.slippage.treatment), 'SLIPPAGE_TREATMENT_REQUIRED');
  rate(profile.slippage.rate);
  ensure(profile.slippage.treatment !== 'INCLUDED_IN_EXECUTION_PRICE' || new D(profile.slippage.rate).eq(0), 'SLIPPAGE_DOUBLE_COUNTING');
  ensure(profile.source && profile.source.kind === 'SYNTHETIC_FIXTURE' && typeof profile.source.description === 'string' && profile.source.description, 'COST_PROVENANCE_REQUIRED');
  return true;
}
function components(profile, side, notionalYuan) {
  const fee = r => BigInt(roundCents(new D(notionalYuan).times(rate(r))));
  const proportional = fee(profile.commission_rate);
  const minimum = cents(profile.minimum_commission_cents);
  const effect = proportional < minimum ? minimum - proportional : 0n;
  const result = {
    commission_cents: (proportional + effect).toString(),
    proportional_commission_cents: proportional.toString(),
    minimum_commission_effect_cents: effect.toString(),
    stamp_tax_cents: (side === 'SELL' ? fee(profile.stamp_tax_sell_rate) : 0n).toString(),
    exchange_fee_cents: (profile.exchange_fee.included_in === 'EXCLUDED' ? fee(profile.exchange_fee.rate) : 0n).toString(),
    other_fee_cents: (profile.other_fee.included_in === 'EXCLUDED' ? fee(profile.other_fee.rate) : 0n).toString(),
    slippage_cents: (profile.slippage.treatment === 'SEPARATE_ESTIMATE' ? fee(profile.slippage.rate) : 0n).toString(),
  };
  result.total_friction_cents = ['commission_cents','stamp_tax_cents','exchange_fee_cents','other_fee_cents','slippage_cents'].reduce((sum, key) => sum + BigInt(result[key]), 0n).toString();
  result.actual_commission_cents = (proportional + effect).toString();
  return result;
}
// Per-order cumulative economics. Fill gross is rounded independently at execution;
// fees use the exact cumulative notional, never a sum of rounded per-fill fees.
export function cumulativeCost({ mode, profile, side, fills, trade_date }) {
  validateCostProfile(profile, { mode, trade_date });
  ensure(side === 'BUY' || side === 'SELL', 'ORDER_SIDE_INVALID');
  ensure(Array.isArray(fills), 'FILLS_REQUIRED');
  let total = new D(0), gross = 0n, qty = 0;
  for (const fill of fills) {
    const q = quantity(fill.quantity); const p = price(fill.price);
    qty += q; ensure(Number.isSafeInteger(qty), 'QUANTITY_OVERFLOW');
    total = total.plus(p.times(q)); gross += BigInt(roundCents(p.times(q)));
  }
  const cost = fills.length ? components(profile, side, total) : Object.fromEntries(['commission_cents','proportional_commission_cents','minimum_commission_effect_cents','stamp_tax_cents','exchange_fee_cents','other_fee_cents','slippage_cents','total_friction_cents','actual_commission_cents'].map(k => [k, '0']));
  const friction = BigInt(cost.total_friction_cents);
  ensure(gross < 10n ** 38n && friction < 10n ** 38n && (side !== 'BUY' || gross+friction < 10n ** 38n), 'MONEY_OVERFLOW');
  return {
    cost_version: profile.object_version, cost_profile_ref: { object_id: profile.object_id, object_version: profile.object_version, content_hash: profile.content_hash },
    side, quantity: qty, notional_cents: gross.toString(), ...cost,
    cash_delta_cents: (side === 'BUY' ? -gross - friction : gross - friction).toString(),
    slippage_treatment: profile.slippage.treatment,
    included_relationship: { exchange_fee: profile.exchange_fee.included_in, other_fee: profile.other_fee.included_in },
  };
}
export function estimateCost({ mode, profile, side, price: unitPrice, quantity: qty, trade_date }) {
  return cumulativeCost({ mode, profile, side, fills: [{ price: unitPrice, quantity: qty }], trade_date });
}
export function affordableQuantity({ mode, profile, side = 'BUY', price: unitPrice, lot_size, available_cash_cents, max_quantity, trade_date }) {
  validateCostProfile(profile, { mode, trade_date }); ensure(side === 'BUY', 'AFFORDABILITY_BUY_ONLY');
  price(unitPrice); quantity(lot_size); quantity(max_quantity); const budget = cents(available_cash_cents);
  let low = 0, high = Math.floor(max_quantity / lot_size);
  while (low < high) {
    const mid = low + Math.ceil((high - low) / 2);
    const cost = estimateCost({ mode, profile, side, price: unitPrice, quantity: mid * lot_size, trade_date });
    if (-BigInt(cost.cash_delta_cents) <= budget) low = mid; else high = mid - 1;
  }
  const qty = low * lot_size;
  return { quantity: qty, all_in_cents: qty ? (-BigInt(estimateCost({ mode, profile, side, price: unitPrice, quantity: qty, trade_date }).cash_delta_cents)).toString() : '0', reason_code: qty ? 'AFFORDABLE_WITH_FEES' : 'REJECT_FEE_INCLUSIVE_AFFORDABILITY' };
}
export function incrementalCost({ mode, profile, side, previous_fills, next_fill, trade_date }) {
  const previous = cumulativeCost({ mode, profile, side, fills: previous_fills, trade_date });
  const total = cumulativeCost({ mode, profile, side, fills: [...previous_fills, next_fill], trade_date });
  return { cumulative: total, delta: Object.fromEntries(['notional_cents','commission_cents','proportional_commission_cents','minimum_commission_effect_cents','stamp_tax_cents','exchange_fee_cents','other_fee_cents','slippage_cents','total_friction_cents','actual_commission_cents','cash_delta_cents'].map(k => [k, (BigInt(total[k]) - BigInt(previous[k])).toString()])) };
}
// Conservative partial-fill reserve: each remaining share may be its own execution,
// so ceiling-to-cent per share bounds all per-execution gross rounding patterns.
export function maximumBuyReservation({mode,profile,executed_fills=[],remaining_quantity,limit_price,trade_date}) {
  ensure(Number.isSafeInteger(remaining_quantity)&&remaining_quantity>=0,'REMAINING_QUANTITY_INVALID');
  const paid=cumulativeCost({mode,profile,side:'BUY',fills:executed_fills,trade_date});
  if(!remaining_quantity)return '0';
  const bound=cumulativeCost({mode,profile,side:'BUY',fills:[...executed_fills,{price:limit_price,quantity:remaining_quantity}],trade_date});
  const gross=BigInt(price(limit_price).times(100).toDecimalPlaces(0,D.ROUND_CEIL).toFixed(0))*BigInt(remaining_quantity);
  const value=gross+BigInt(bound.total_friction_cents)-BigInt(paid.total_friction_cents);
  ensure(value>=0n&&value<10n**38n,'MONEY_OVERFLOW');return value.toString();
}
