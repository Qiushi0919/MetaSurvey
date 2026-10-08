import test from 'node:test';
import assert from 'node:assert/strict';
import Decimal from 'decimal.js';
import { createHash } from 'node:crypto';
import { readFileSync, statSync } from 'node:fs';
import { quoteCost, netEdge } from '../cost.mjs';

const sorted = x => Array.isArray(x) ? x.map(sorted) : x && typeof x === 'object' ? Object.fromEntries(Object.keys(x).sort().map(k => [k, sorted(x[k])])) : x;
const hash = x => 'sha256:' + createHash('sha256').update(JSON.stringify(sorted(x))).digest('hex');
const seal = p => { const { content_hash, ...body } = p; return { ...body, content_hash: hash(body) }; };
// Entire profile is invented for arithmetic; it is never an actual tariff/default.
function fixture() {
  const component = (rate, sides = ['BUY', 'SELL']) => ({ rate, rate_unit: 'FRACTION_OF_NOTIONAL', sides, effective_from: '2026-01-01', effective_to: '2026-12-31', evidence_ref: 'SYNTHETIC:cost-fixture-v1' });
  return seal({ contract_name: 'EconomicDiagnosticCostProfile', contract_version: '1.0.0', profile_id: 'cost-fixture', profile_version: 1, profile_scope: 'SYNTHETIC_FIXTURE', production_enabled: false, currency: 'CNY', money_unit: 'INTEGER_CENTS_STRING', rounding_mode: 'HALF_UP', commission_scope: 'PER_ORDER_CUMULATIVE', market: 'SSE', instrument_kind: 'A_SHARE', trading_method: 'AUCTION', source: { kind: 'SYNTHETIC_FIXTURE', evidence_id: 'cost-fixture-v1', description: 'Invented arithmetic oracle; NOT_OWNER_DEFAULT; NOT_REAL_TARIFF' }, commission: { ...component('0.001'), minimum_cents: '100' }, stamp_tax: { ...component('0.0005', ['SELL']), included_in: 'SEPARATE' }, exchange_fee: { ...component('0.00003'), included_in: 'COMMISSION' }, clearing_fee: { ...component('0.00002'), included_in: 'SEPARATE' }, regulatory_fee: { ...component('0.00001'), included_in: 'COMMISSION' }, other_fee: { ...component('0'), included_in: 'SEPARATE' }, slippage: { ...component('0.0001'), treatment: 'SEPARATE_ESTIMATE' } });
}
const input = (profile = fixture(), extra = {}) => ({ mode: 'ECONOMIC_DIAGNOSTIC_ONLY', profile, side: 'BUY', fills: [{ price: '10', quantity: 100 }], trade_date: '2026-10-08', ...extra });
const change = (fn) => { const p = fixture(); fn(p); return seal(p); };
function blocked(value, code) { assert.equal(value.status, 'NOT_COMPUTABLE'); assert.equal(value.net_edge_cents, null); assert.equal(value.safe_to_trade, false); assert.equal(value.production_enabled, false); assert.ok(value.reason_codes.includes(code), value.reason_codes.join(',')); }
const required = [
  ...Object.keys(fixture()),
  ...['commission', 'stamp_tax', 'exchange_fee', 'clearing_fee', 'regulatory_fee', 'other_fee', 'slippage'].flatMap(c => Object.keys(fixture()[c]).map(k => c + '.' + k)),
  ...Object.keys(fixture().source).map(k => 'source.' + k),
];
for (const path of required) test('missing required field blocks: ' + path, () => {
  const p = fixture(); const parts = path.split('.'); let item = p; for (const part of parts.slice(0, -1)) item = item[part]; delete item[parts.at(-1)];
  const out = quoteCost(input(p)); blocked(out, 'REQUIRED_COST_CONFIG_UNSET'); assert.ok(out.missing_fields.includes(path));
});
for (const unknown of [undefined, null, 'UNKNOWN', 'UNSET_REQUIRED']) test('unknown differs from explicit zero: ' + String(unknown), () => {
  blocked(quoteCost(input(change(p => p.clearing_fee.rate = unknown))), 'REQUIRED_COST_CONFIG_UNSET');
});
test('explicit zeros compute only synthetic, never authority', () => {
  const p = change(p => { for (const k of ['commission', 'stamp_tax', 'exchange_fee', 'clearing_fee', 'regulatory_fee', 'other_fee', 'slippage']) p[k].rate = '0'; p.commission.minimum_cents = '0'; });
  const out = quoteCost(input(p)); assert.equal(out.status, 'COMPUTABLE_SYNTHETIC_ONLY'); assert.equal(out.total_friction_cents, '0'); assert.equal(out.cash_delta_cents, '-100000'); assert.equal(out.evidence_tier, 'SYNTHETIC_NOT_REAL'); assert.equal(out.native_authority, false);
});
for (const mode of ['PRODUCTION', 'PAPER', 'DEV', 'OWNER_SET', undefined]) test('mode rejected: ' + String(mode), () => blocked(quoteCost(input(fixture(), { mode })), 'MODE_NOT_AUTHORIZED'));
test('fully populated actual profile self hash and OWNER_SET is not evidence', () => blocked(quoteCost(input(change(p => { p.profile_scope = 'ACTUAL_ACCOUNT'; p.source.kind = 'OWNER_SET'; }))), 'ACTUAL_ACCOUNT_EVIDENCE_NOT_ADMITTED'));
test('old synthetic CostProfile is not promoted', () => blocked(quoteCost(input(change(p => p.contract_name = 'CostProfile'))), 'PROFILE_VERSION_INVALID'));
test('production true cannot be set by profile', () => blocked(quoteCost(input(change(p => p.production_enabled = true))), 'PRODUCTION_DISABLED'));
test('tampered profile hash fails', () => { const p = fixture(); p.commission.rate = '0'; blocked(quoteCost(input(p)), 'PROFILE_HASH_MISMATCH'); });
test('closed profile and component schema', () => {
  blocked(quoteCost(input(change(p => p.account_capital = '5000'))), 'PROFILE_CLOSED_SCHEMA_REQUIRED');
  blocked(quoteCost(input(change(p => p.commission.extra = 1))), 'COMPONENT_CLOSED_SCHEMA_REQUIRED');
});
test('one-yuan synthetic minimum boundary and cumulative partial fills', () => {
  const below = quoteCost(input(fixture(), { fills: [{ price: '9.90', quantity: 100 }] }));
  const at = quoteCost(input()); const above = quoteCost(input(fixture(), { fills: [{ price: '10.05', quantity: 100 }] }));
  assert.equal(below.commission_cents, '100'); assert.equal(at.commission_cents, '100'); assert.equal(above.commission_cents, '101');
  const split = quoteCost(input(fixture(), { fills: [{ price: '10', quantity: 50 }, { price: '10', quantity: 50 }] }));
  assert.equal(split.commission_cents, '100'); assert.equal(split.total_friction_cents, at.total_friction_cents);
  const oneHalf = quoteCost(input(fixture(), { fills: [{ price: '10', quantity: 50 }] })); assert.equal(oneHalf.commission_cents, '100'); assert.notEqual((2n * BigInt(oneHalf.commission_cents)).toString(), split.commission_cents);
});
test('commission reference fees included once and clearing separate', () => {
  const out = quoteCost(input()); assert.equal(out.exchange_fee_proportional_cents, '3'); assert.equal(out.exchange_fee_cents, '0'); assert.equal(out.regulatory_fee_cents, '0'); assert.equal(out.clearing_fee_cents, '2'); assert.equal(out.slippage_cents, '10'); assert.equal(out.total_friction_cents, '112');
  const separate = quoteCost(input(change(p => p.exchange_fee.included_in = 'SEPARATE'))); assert.equal(separate.total_friction_cents, '115');
});
test('included fee cannot have side without comprehensive commission', () => blocked(quoteCost(input(change(p => p.commission.sides = ['SELL']))), 'INCLUDED_FEE_WITHOUT_COMMISSION_SIDE'));
test('stamp tax seller only', () => { assert.equal(quoteCost(input()).stamp_tax_cents, '0'); assert.equal(quoteCost(input(fixture(), { side: 'SELL' })).stamp_tax_cents, '50'); blocked(quoteCost(input(change(p => p.stamp_tax.sides = ['BUY', 'SELL']))), 'STAMP_TAX_SIDE_OR_INCLUSION_INVALID'); });
test('slippage included price must be explicit zero incremental rate', () => {
  blocked(quoteCost(input(change(p => p.slippage.treatment = 'INCLUDED_IN_EXECUTION_PRICE'))), 'SLIPPAGE_DOUBLE_COUNTING');
  const out = quoteCost(input(change(p => { p.slippage.treatment = 'INCLUDED_IN_EXECUTION_PRICE'; p.slippage.rate = '0'; }))); assert.equal(out.slippage_cents, '0'); assert.equal(out.total_friction_cents, '102');
});
for (const value of [0.001, -1, Infinity, NaN, '-0.001', 'NaN', 'Infinity', '1e-3', '0.01%', '1.000000000001', '0.0000000000001']) test('rate must be exact fraction string: ' + String(value), () => blocked(quoteCost(input(change(p => p.commission.rate = value))), 'FRACTION_RATE_REQUIRED'));
test('percent unit cannot be confused with fractional rate', () => blocked(quoteCost(input(change(p => p.exchange_fee.rate_unit = 'PERCENT'))), 'RATE_UNIT_UNSUPPORTED'));
for (const value of [-1, 100, '1.00', '01', '1e2']) test('integer cents only: ' + value, () => blocked(quoteCost(input(change(p => p.commission.minimum_cents = value))), 'INTEGER_CENTS_REQUIRED'));
for (const value of [0, -1, 0.1, Number.MAX_SAFE_INTEGER + 1, '100']) test('quantity strict: ' + value, () => blocked(quoteCost(input(fixture(), { fills: [{ price: '10', quantity: value }] })), 'POSITIVE_SAFE_QUANTITY_REQUIRED'));
for (const value of [10, 0, '-1', '0', '1e2', 'Infinity', '0.0000001']) test('price exact positive string: ' + value, () => blocked(quoteCost(input(fixture(), { fills: [{ price: value, quantity: 100 }] })), 'EXACT_POSITIVE_PRICE_REQUIRED'));
test('quantity sum overflow', () => blocked(quoteCost(input(fixture(), { fills: [{ price: '10', quantity: Number.MAX_SAFE_INTEGER }, { price: '10', quantity: 1 }] })), 'QUANTITY_OVERFLOW'));
test('nonempty one order fills closed schema', () => { blocked(quoteCost(input(fixture(), { fills: [] })), 'NONEMPTY_FILLS_REQUIRED'); blocked(quoteCost(input(fixture(), { fills: [{ price: '10', quantity: 100, fee: '0' }] })), 'FILL_CLOSED_SCHEMA_REQUIRED'); });
test('trade date and every component validity window', () => {
  blocked(quoteCost(input(fixture(), { trade_date: '2026-02-30' })), 'TRADE_DATE_INVALID');
  for (const c of ['commission', 'stamp_tax', 'exchange_fee', 'clearing_fee', 'regulatory_fee', 'other_fee', 'slippage']) blocked(quoteCost(input(change(p => p[c].effective_to = '2026-10-07'))), 'COMPONENT_DATE_OUT_OF_SCOPE');
  blocked(quoteCost(input(change(p => p.clearing_fee.effective_from = '2027-01-01'))), 'COMPONENT_DATE_OUT_OF_SCOPE');
});
test('side and evidence provenance cannot be guessed', () => {
  blocked(quoteCost(input(fixture(), { side: 'HOLD' })), 'ORDER_SIDE_INVALID');
  blocked(quoteCost(input(change(p => p.clearing_fee.sides = []))), 'COMPONENT_SIDES_INVALID');
  blocked(quoteCost(input(change(p => p.commission.evidence_ref = 'OWNER_SET'))), 'COMPONENT_EVIDENCE_NOT_BOUND');
  blocked(quoteCost(input(change(p => p.source.kind = 'BROKER_VERIFIED'))), 'SYNTHETIC_PROVENANCE_REQUIRED');
});
test('round fill gross separately; rate fee on cumulative exact notional', () => {
  const p = change(p => { for (const c of ['commission', 'stamp_tax', 'exchange_fee', 'clearing_fee', 'regulatory_fee', 'other_fee', 'slippage']) p[c].rate = '0'; p.commission.rate = '1'; p.commission.minimum_cents = '0'; });
  const out = quoteCost(input(p, { fills: [{ price: '0.005', quantity: 1 }, { price: '0.005', quantity: 1 }] }));
  assert.equal(out.notional_cents, '2'); assert.equal(out.exact_notional_yuan, '0.01'); assert.equal(out.commission_cents, '1'); assert.equal(out.cash_delta_cents, '-3');
});
test('private Decimal context resists caller precision/rounding mutation', () => {
  const before = quoteCost(input()); const prior = { precision: Decimal.precision, rounding: Decimal.rounding };
  Decimal.set({ precision: 1, rounding: Decimal.ROUND_DOWN });
  try { assert.deepEqual(quoteCost(input()), before); } finally { Decimal.set(prior); }
});
test('deterministic quote has stable input/output trace', () => {
  const a = quoteCost(input()), b = quoteCost(input()); assert.deepEqual(a, b); assert.match(a.request_hash, /^sha256:[a-f0-9]{64}$/); const { content_hash, ...body } = a; assert.equal(content_hash, hash(body));
});
const edgeInput = profile => ({ mode: 'ECONOMIC_DIAGNOSTIC_ONLY', profile: profile || fixture(), buy_fills: [{ price: '10', quantity: 100 }], sell_fills: [{ price: '10.1', quantity: 100 }], buy_date: '2026-10-08', sell_date: '2026-10-09' });
test('net edge reconciles both per order costs without floats', () => {
  const out = netEdge(edgeInput()); assert.equal(out.gross_edge_cents, '1000'); assert.equal(out.buy.total_friction_cents, '112'); assert.equal(out.sell.total_friction_cents, '164'); assert.equal(out.net_edge_cents, '724'); assert.equal(BigInt(out.net_edge_cents), BigInt(out.buy.cash_delta_cents) + BigInt(out.sell.cash_delta_cents)); assert.equal(out.production_enabled, false);
});
test('positive gross can be negative net edge', () => { const x = edgeInput(); x.sell_fills[0].price = '10.01'; const out = netEdge(x); assert.equal(out.gross_edge_cents, '100'); assert.equal(out.net_edge_cents, '-174'); });
test('unknown input cannot produce optimistic edge', () => { const p = change(p => p.slippage.rate = 'UNSET_REQUIRED'); blocked(netEdge(edgeInput(p)), 'REQUIRED_COST_CONFIG_UNSET'); });
test('net edge requires closed quantity, forward dates and all evidence windows', () => {
  const x = edgeInput(); x.sell_fills[0].quantity = 99; blocked(netEdge(x), 'ROUND_TRIP_QUANTITY_MISMATCH');
  const y = edgeInput(); y.sell_date = '2026-10-07'; blocked(netEdge(y), 'ROUND_TRIP_DATE_INVALID');
  const z = edgeInput(change(p => p.commission.effective_to = '2026-10-08')); blocked(netEdge(z), 'COMPONENT_DATE_OUT_OF_SCOPE');
});
test('net edge production mode is blocked', () => { const x = edgeInput(); x.mode = 'PRODUCTION'; blocked(netEdge(x), 'MODE_NOT_AUTHORIZED'); });
test('malformed request object and undeclared fields fail closed', () => {
  for (const value of [null, [], 'PRODUCTION', 1]) { blocked(quoteCost(value), 'REQUEST_OBJECT_REQUIRED'); blocked(netEdge(value), 'REQUEST_OBJECT_REQUIRED'); }
  blocked(quoteCost({ ...input(), order_intent: 'FORGED' }), 'REQUEST_CLOSED_SCHEMA_REQUIRED');
  blocked(netEdge({ ...edgeInput(), approval: 'LLM_APPROVE' }), 'REQUEST_CLOSED_SCHEMA_REQUIRED');
});
const official = JSON.parse(readFileSync(new URL('../../config/wave-hb/official-fee-evidence.json', import.meta.url), 'utf8'));
for (const capture of official.captures) test('official original can reopen without credentials: ' + capture.id, () => {
  const bytes = readFileSync(capture.raw_ref.path);
  assert.equal(bytes.length, capture.raw_ref.bytes);
  assert.equal('sha256:' + createHash('sha256').update(bytes).digest('hex'), capture.raw_ref.sha256);
  assert.equal(statSync(capture.raw_ref.path).mode & 0o777, 0o600);
  assert.equal(capture.response_status, 200); assert.equal(capture.credential_present, false); assert.equal(capture.proxy_used, false); assert.equal(capture.redirect_followed, false);
  assert.match(capture.retrieved_at, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/);
});
test('official rate derivations retain units and never become defaults', () => {
  const [exchange, law, reduction] = official.reference_facts;
  assert.equal(new Decimal('0.00341').div(100).toFixed(), exchange.rate_fraction);
  assert.equal(new Decimal(law.rate_fraction).times('0.5').toFixed(), reduction.rate_fraction);
  assert.deepEqual(exchange.sides, ['BUY', 'SELL']); assert.deepEqual(reduction.sides, ['SELL']);
  assert.equal(official.direct_official_gets, 6); assert.equal(official.search_queries, 3);
  assert.equal(official.actual_profile_admission, false); assert.equal(official.production_enabled, false); assert.equal(official.historical_interval_completeness_proven, false);
  for (const fact of official.reference_facts) { assert.equal(fact.actual_fee_profile_default, false); assert.equal(fact.historical_pit_proven, false); assert.equal(fact.effective_to, 'UNKNOWN'); assert.equal(fact.available_at_basis, 'CURRENT_LOCAL_CAPTURE_NOT_HISTORICAL_FIRST_VISIBLE'); }
});
