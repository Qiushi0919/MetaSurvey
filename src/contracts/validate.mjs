import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import Decimal from 'decimal.js';

// Private precision: other modules or consumers cannot weaken money validation.
const ExactDecimal = Decimal.clone({ precision: 100, rounding: Decimal.ROUND_HALF_UP });

const directory = path.resolve(import.meta.dirname, '../../contracts/v1');
const ajv = new Ajv2020({ allErrors: true, strict: true, coerceTypes: false, useDefaults: false });
addFormats(ajv);
ajv.addKeyword('x-contract');
ajv.addKeyword('x-unit');
for (const file of fs.readdirSync(directory).filter(x => x.endsWith('.schema.json'))) ajv.addSchema(JSON.parse(fs.readFileSync(path.join(directory,file),'utf8')));

export class ContractViolation extends Error {
  constructor(code, details = []) { super(code); this.name = 'ContractViolation'; this.code = code; this.details = details; }
}
export function requireThat(condition, code, details) { if (!condition) throw new ContractViolation(code, details); }

export function canonical(value) {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'number') { requireThat(Number.isSafeInteger(value), 'INTEGER_JSON_NUMBER_REQUIRED'); return JSON.stringify(value); }
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  requireThat(value && Object.getPrototypeOf(value) === Object.prototype, 'JSON_OBJECT_REQUIRED');
  return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`;
}
export const hashValue = value => `sha256:${createHash('sha256').update(canonical(value)).digest('hex')}`;
export function contentHash(object) { const { content_hash, ...body } = object; return hashValue(body); }
export function sealContract(object) { return { ...structuredClone(object), content_hash: contentHash(object) }; }
export const reference = object => ({ object_id: object.object_id, object_version: object.object_version, content_hash: object.content_hash });
export function matchesRef(object, bound) { return bound && object.object_id === bound.object_id && object.object_version === bound.object_version && object.content_hash === bound.content_hash; }
export function timestampMs(value) { const ms = Date.parse(value); requireThat(Number.isFinite(ms) && /(Z|[+-]\d{2}:\d{2})$/.test(value), 'INVALID_CLOCK'); return ms; }
const exact = value => new ExactDecimal(value);
function bounded(value, low, high, code) { if (value !== 'UNSET_REQUIRED') requireThat(exact(value).gte(low) && exact(value).lte(high), code); }
function checkProvenance(p) {
  const available = timestampMs(p.available_at), retrieved = timestampMs(p.retrieved_at); timestampMs(p.event_time);
  requireThat(available <= retrieved, 'INVALID_CLOCK');
  if (p.publication_precision === 'SECOND') {
    requireThat(typeof p.published_at === 'string' && /(Z|[+-]\d{2}:\d{2})$/.test(p.published_at), 'INVALID_CLOCK');
    const published = timestampMs(p.published_at); requireThat(available >= published && retrieved >= published, 'INVALID_CLOCK');
  } else if (p.publication_precision === 'DATE_ONLY') requireThat(typeof p.published_at === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(p.published_at), 'INVALID_CLOCK');
  else requireThat(p.published_at === null, 'INVALID_CLOCK');
}
export function assertEvidenceVisible(envelope, cutoff, calendar = []) {
  validateContract('DataEnvelope', envelope);
  requireThat(envelope.data_quality === 'PASS', 'DATA_QUALITY_FAILED');
  const p = envelope.provenance;
  requireThat(p.publication_precision !== 'UNKNOWN', 'UNKNOWN_PUBLICATION');
  requireThat(timestampMs(p.available_at) <= timestampMs(cutoff), 'FUTURE_DATA');
  if (p.visibility_basis === 'OBSERVED_AT_TIME') requireThat(timestampMs(p.retrieved_at) <= timestampMs(cutoff), 'FUTURE_DATA');
  if (p.publication_precision === 'DATE_ONLY') {
    const next = [...calendar].sort().find(d => d > p.published_at);
    requireThat(next, 'UNKNOWN_PUBLICATION');
    requireThat(timestampMs(p.available_at) >= timestampMs(`${next}T00:00:00+08:00`), 'INVALID_CLOCK');
  }
}
export function validateContract(name, object, context = {}) {
  const validator = ajv.getSchema(`urn:ashare:contracts:v1:${name}`);
  requireThat(validator, 'UNSUPPORTED_VERSION');
  if (!validator(object)) throw new ContractViolation('CONTRACT_SCHEMA_INVALID', validator.errors.map(e => ({ path: e.instancePath, keyword: e.keyword })));
  requireThat(contentHash(object) === object.content_hash, 'HASH_MISMATCH');
  checkProvenance(object.provenance);
  if (object.invalidation.status === 'INVALIDATED') requireThat(object.invalidation.invalidated_at && object.invalidation.reason_code, 'INVALIDATION_REASON_REQUIRED');
  if (object.invalidation.status === 'ACTIVE') requireThat(object.invalidation.invalidated_at === null && object.invalidation.reason_code === null, 'INVALIDATION_STATE_INVALID');
  if (name === 'SecurityIdentity') {
    requireThat(object.symbol === `${object.exchange}:${object.security_code}`, 'SECURITY_IDENTITY_MISMATCH');
    if (object.tick_size !== 'UNSET_REQUIRED') requireThat(exact(object.tick_size).gt(0), 'PRICE_INVALID');
  }
  if (name === 'DataEnvelope') {
    requireThat(hashValue(object.payload) === object.payload_hash, 'HASH_MISMATCH');
    requireThat(object.adjustment !== 'RAW' || object.adjustment_version === 'RAW', 'RAW_ADJUSTMENT_VERSION_REQUIRED');
    requireThat(object.adjustment !== 'ADJUSTED' || !['RAW', 'UNSET_REQUIRED'].includes(object.adjustment_version), 'ADJUSTMENT_VERSION_REQUIRED');
    if (['BAR_1D','BAR_1M'].includes(object.data_kind)) requireThat(timestampMs(object.provenance.event_time) <= timestampMs(object.provenance.available_at), 'FUTURE_MARKET_DATA');
  }
  if (name === 'AccountProfile') {
    requireThat(object.profile_kind !== 'SYNTHETIC_FIXTURE' || object.mode !== 'PROD', 'SYNTHETIC_FIXTURE_ONLY');
    for (const key of ['max_single_trade_loss_bps','max_sector_exposure_bps','max_portfolio_drawdown_bps']) bounded(object.settings[key], 0, 10000, 'RISK_CONFIG_INVALID');
    for (const key of ['commission_rate','exchange_fee_rate','other_fee_rate','stamp_tax_sell_rate']) bounded(object.broker_costs[key],0,1,'COST_CONFIG_INVALID');
    if (object.settings.capital_cents !== 'UNSET_REQUIRED' && Object.values(object.settings.strategy_budget_cents).every(x => x !== 'UNSET_REQUIRED')) requireThat(Object.values(object.settings.strategy_budget_cents).reduce((a,x) => a+BigInt(x),0n) <= BigInt(object.settings.capital_cents), 'INSUFFICIENT_CASH');
  }
  if (name === 'FeatureSet') {
    for (const feature of Object.values(object.features)) requireThat(feature.quality !== 'VALID' || feature.value !== null, 'DATA_QUALITY_FAILED');
  }
  if (name === 'BrainPacket') {
    for (const evidence of object.evidence) assertEvidenceVisible(evidence, object.decision_cutoff, context.calendar);
    requireThat(new Set(object.evidence.map(e => e.content_hash)).size === object.evidence.length, 'DUPLICATE_EVIDENCE');
  }
  if (name === 'ResearchCard') {
    const h = object.trade.target_holding_sessions;
    if (object.strategy_id === 'RESEARCH_6_18M') requireThat(h === null && object.trade.can_produce_order === false, 'STRATEGY_NAMESPACE_MISMATCH');
    else {
      requireThat(h !== null && h.minimum <= h.maximum, 'STRATEGY_HORIZON_MISMATCH');
      const limits = object.strategy_id === 'CORE_40' ? [20,40] : [1,3];
      requireThat(h.minimum >= limits[0] && h.maximum <= limits[1], 'STRATEGY_HORIZON_MISMATCH');
    }
    requireThat(object.research.horizon_months.minimum >= 6 && object.research.horizon_months.maximum <=18 && object.research.horizon_months.minimum <= object.research.horizon_months.maximum, 'STRATEGY_HORIZON_MISMATCH');
    Object.values(object.scores).forEach(s => bounded(s,0,100,'SCORE_RANGE_INVALID'));
    const scenarios = object.probability.scenarios;
    scenarios.forEach(s => bounded(s.probability,0,1,'PROBABILITY_RANGE_INVALID'));
    if (scenarios.length) requireThat(scenarios.reduce((v,s) => v.plus(s.probability),exact(0)).eq(1),'PROBABILITY_SUM_INVALID');
    requireThat(!object.probability.calibrated || object.probability.calibration_ref !== null,'UNCALIBRATED_PROBABILITY');
    requireThat(!object.trade.can_produce_order || object.hard_blocks.length === 0,'DATA_QUALITY_FAILED');
  }
  if (name === 'CandidateEligibility') requireThat(!object.tradeable || (object.gate_status === 'PASS' && object.hard_blocks.length === 0 && object.cost_ref && object.admission_policy_version !== 'UNSET_REQUIRED' && !['X','UNSET_REQUIRED'].includes(object.grade)), 'UNRESOLVED_BUSINESS_POLICY');
  if (name === 'SignalEvent') {
    requireThat(object.strategy_id === 'CORE_40' ? object.signal_type !== 'EVENT_TRIGGER' : object.signal_type === 'EVENT_TRIGGER','STRATEGY_NAMESPACE_MISMATCH');
    if (['TRIGGERED','ACKNOWLEDGED','APPROVED','EXECUTION_READY','EXECUTED'].includes(object.state)) requireThat(object.triggered_at !== null, 'TRIGGER_TIME_REQUIRED');
    if (object.triggered_at) requireThat(timestampMs(object.expires_at) > timestampMs(object.triggered_at) && timestampMs(object.triggered_at) <= timestampMs(object.recorded_at),'INVALID_CLOCK');
  }
  if (name === 'Approval') {
    requireThat(timestampMs(object.expires_at) > timestampMs(object.approved_at), 'APPROVAL_EXPIRED');
    if (object.phase === 'FINAL_ORDER_CONFIRMATION') requireThat(object.cost_ref && object.order_terms_hash, 'FINAL_CONFIRMATION_REQUIRED');
    else requireThat(object.order_terms_hash === null, 'ORDER_TERMS_CHANGED');
  }
  if (['CostEstimate','Fill'].includes(name)) {
    requireThat(exact(object.price).gt(0), 'PRICE_INVALID');
    const fees = Object.values(object.fees).reduce((v,f) => v + BigInt(f),0n);
    if (name === 'CostEstimate') requireThat(fees === BigInt(object.total_cost_cents), 'RECONCILIATION_FAILED');
    if (object.slippage_treatment === 'INCLUDED_IN_EXECUTION_PRICE') requireThat(object.fees.slippage_cents === '0', 'SLIPPAGE_DOUBLE_COUNT');
    requireThat(exact(object.price).mul(object.quantity).mul(100).toDecimalPlaces(0,Decimal.ROUND_HALF_UP).eq(object.notional_cents),'RECONCILIATION_FAILED');
  }
  if (name === 'OrderIntent') requireThat(exact(object.limit_price).gt(0), 'PRICE_INVALID');
  if (name === 'OrderIntent') requireThat(object.status !== 'CONFIRMED' || object.final_confirmation_ref, 'FINAL_CONFIRMATION_REQUIRED');
  if (name === 'BacktestResult') requireThat(timestampMs(object.finished_at) >= timestampMs(object.started_at),'INVALID_CLOCK');
  return object;
}
export function contractNames() { return fs.readdirSync(directory).filter(f => f !== 'common.schema.json' && f.endsWith('.schema.json')).map(f => f.replace('.schema.json','')).sort(); }
