import test from 'node:test';
import assert from 'node:assert/strict';
import { visibleEnvelopes, freezeSnapshot, createFreezeSession, assertVisible, assertFresh, validateBrainPacket, validateOrderChain, productionGate, orderTermsHash } from '../src/baseline/gates.mjs';
import { sealContract, hashValue, reference } from '../src/contracts/validate.mjs';
import { examples, envelope, accountProfile, T, LATER, FUTURE } from './helpers.mjs';

test('PIT rejects future data before packet hash, including titles and IDs',()=>{
  const old=envelope(),future=envelope({object_id:'future-acquisition-title',payload:{title:'SECRET_FUTURE_TITLE'},payload_hash:hashValue({title:'SECRET_FUTURE_TITLE'})});
  future.provenance.available_at=FUTURE;const sealed=sealContract(future);
  const result=visibleEnvelopes([old,sealed],T);
  assert.deepEqual(result,[old]);assert.ok(!JSON.stringify(result).includes('SECRET_FUTURE_TITLE'));
  assert.equal(hashValue(result),hashValue([old]));
});
test('Observed late retrieval cannot be backdated; reconstructed visibility is explicitly tagged',()=>{
  const e=envelope();e.provenance.retrieved_at=FUTURE;e.provenance.visibility_basis='OBSERVED_AT_TIME';
  assert.throws(()=>assertVisible(sealContract(e),T),{code:'FUTURE_DATA'});
  e.provenance.visibility_basis='HISTORICAL_AVAILABILITY_RECONSTRUCTION';assertVisible(sealContract(e),T);
});
test('Date-only publications require next exchange session availability and unknown dates block',()=>{
  const e=envelope();e.provenance.published_at='2026-10-05';e.provenance.publication_precision='DATE_ONLY';
  assert.throws(()=>assertVisible(sealContract(e),FUTURE,['2026-10-05','2026-10-08']),{code:'INVALID_CLOCK'});
  assert.throws(()=>assertVisible(sealContract(e),FUTURE),{code:'UNKNOWN_PUBLICATION'});
});
test('Freeze-before-reveal uses retained immutable decision, forbids uncommitted or duplicate reveal',()=>{
  const original=examples().all.SnapshotManifest;
  const f=freezeSnapshot({snapshot:original,envelopes:[envelope()],cutoff:T});
  const session=createFreezeSession(f),decision={action:'WAIT',notes:'synthetic'};
  assert.throws(()=>session.reveal({future_price:'99'},LATER),{code:'FREEZE_BEFORE_REVEAL_REQUIRED'});
  session.commit(decision,T);decision.action='BUY';
  assert.throws(()=>session.reveal({},T),{code:'FREEZE_BEFORE_REVEAL_REQUIRED'});
  assert.equal(session.reveal({future_price:'99'},LATER).decision.action,'WAIT');
  assert.throws(()=>session.reveal({},FUTURE),{code:'FREEZE_BEFORE_REVEAL_REQUIRED'});
});
test('Stale (>5 seconds) and future prices fail closed, exact boundary is explicit',()=>{
  assertFresh(T,'2026-10-05T02:00:05Z');
  assert.throws(()=>assertFresh(T,'2026-10-05T02:00:05.001Z'),{code:'STALE_MARKET_DATA'});
  assert.throws(()=>assertFresh(FUTURE,T),{code:'FUTURE_MARKET_DATA'});
});
test('Authenticated two-phase version chain is preparable only, never production executable',()=>{
  const result=validateOrderChain(examples().chain);assert.equal(result.structurally_preparable,true);assert.equal(result.production_execution_enabled,false);
});
test('Model self-claim HUMAN identity does not authenticate a user approval',()=>{
  const chain=examples().chain;delete chain.authority;
  assert.throws(()=>validateOrderChain(chain),{code:'APPROVAL_NOT_AUTHENTICATED'});
  chain.authority={actor_type:'LLM',actor_id:'fixture-user',verified_approval_hashes:new Set([chain.decisionApproval.content_hash,chain.confirmation.content_hash])};
  assert.throws(()=>validateOrderChain(chain),{code:'APPROVAL_NOT_AUTHENTICATED'});
});
test('Card version/cost/quantity/account/mode/namespace changes invalidate old approvals',()=>{
  for (const patch of [{quantity:200},{mode:'PAPER'},{account_id:'other'},{strategy_id:'EVENT_3'},{limit_price:'11'}]) {
    const chain=examples().chain;chain.order=sealContract({...chain.order,...patch});assert.throws(()=>validateOrderChain(chain));
  }
  const chain=examples().chain;chain.card=sealContract({...chain.card,object_version:2});assert.throws(()=>validateOrderChain(chain),{code:'CARD_VERSION_INVALIDATED'});
});
test('Expired approvals, future approval clocks and stale signals cannot be reused',()=>{
  const expired=examples().chain;expired.now=FUTURE;assert.throws(()=>validateOrderChain(expired),{code:'APPROVAL_EXPIRED'});
  const future=examples().chain;future.confirmation=sealContract({...future.confirmation,approved_at:LATER});assert.throws(()=>validateOrderChain(future),{code:'INVALID_CLOCK'});
  const stale=examples().chain;stale.now=LATER;assert.throws(()=>validateOrderChain(stale),{code:'STALE_MARKET_DATA'});
});
test('Unknown config/missing fields/null/NaN block production and never inherit legacy assumptions',()=>{
  const p=accountProfile(),r=productionGate(p);assert.equal(r.allowed,false);assert.ok(r.missing_paths.includes('/settings/capital_cents'));assert.equal(p.broker_costs.commission_rate,'UNSET_REQUIRED');
  for (const bad of [null,{},sealContract({...p,settings:{...p.settings,capital_cents:null}}),sealContract({...p,settings:{...p.settings,capital_cents:'NaN'}})]) assert.equal(productionGate(bad).allowed,false);
});
test('BrainPacket binds the exact frozen snapshot, cutoff and ordered evidence',()=>{
  const all=examples().all;validateBrainPacket(all.BrainPacket,all.SnapshotManifest);
  assert.throws(()=>validateBrainPacket(sealContract({...all.BrainPacket,snapshot_ref:{...all.BrainPacket.snapshot_ref,object_version:2}}),all.SnapshotManifest),{code:'SNAPSHOT_BINDING_MISMATCH'});
  assert.throws(()=>validateBrainPacket(sealContract({...all.BrainPacket,evidence:[]}),all.SnapshotManifest),{code:'SNAPSHOT_BINDING_MISMATCH'});
});
function rebindSignal(chain, patch) {
  chain.signal=sealContract({...chain.signal,...patch});
  chain.decisionApproval=sealContract({...chain.decisionApproval,signal_ref:reference(chain.signal)});
  chain.order=sealContract({...chain.order,signal_ref:reference(chain.signal),decision_approval_ref:reference(chain.decisionApproval)});
  chain.confirmation=sealContract({...chain.confirmation,signal_ref:reference(chain.signal),order_terms_hash:orderTermsHash(chain.order)});
  chain.order=sealContract({...chain.order,final_confirmation_ref:reference(chain.confirmation)});
  chain.authority.verified_approval_hashes=new Set([chain.decisionApproval.content_hash,chain.confirmation.content_hash]);
  return chain;
}
test('Honestly resealed and rebound chains still reject rule mismatch and missing/future trigger',()=>{
  assert.throws(()=>validateOrderChain(rebindSignal(examples().chain,{rule_version:'different'})),{code:'SIGNAL_VERSION_INVALIDATED'});
  assert.throws(()=>validateOrderChain(rebindSignal(examples().chain,{triggered_at:null})),{code:'TRIGGER_TIME_REQUIRED'});
  assert.throws(()=>validateOrderChain(rebindSignal(examples().chain,{triggered_at:LATER})),{code:'INVALID_CLOCK'});
});
test('Even self-declared fully configured verification cannot enable P0 production',()=>{
  const p=accountProfile();
  p.profile_kind='VERIFIED_ACCOUNT';p.mode='PROD';
  p.settings={capital_cents:'0',target_order_cents:'0',max_positions:1,max_single_trade_loss_bps:'0',max_sector_exposure_bps:'0',daily_loss_limit_cents:'0',max_portfolio_drawdown_bps:'0',margin_allowed:false,monthly_trade_frequency:0,strategy_budget_cents:{CORE_40:'0',EVENT_3:'0'}};
  p.broker_costs={broker_id:'synthetic-self-claim',commission_rate:'0',minimum_commission_cents:'0',commission_scope:'PER_ORDER',exchange_fee_rate:'0',exchange_fee_included:false,other_fee_rate:'0',other_fee_included:false,stamp_tax_sell_rate:'0',statutory_rate_source:'synthetic-unverified',statutory_rate_verified_at:T,effective_from:'2026-10-05',effective_to:null,slippage_base_bps:'0',slippage_stress_bps:'0',rounding_mode:'HALF_UP',configuration_source:'synthetic-self-claim'};
  p.user_risk_policy_version='synthetic-self-claim';
  for(const k of ['broker_capability_verified','cost_reconciliation_passed','program_trading_compliance_checked','paper_acceptance_passed','kill_switch_test_passed'])p[k]=true;
  const gate=productionGate(sealContract(p));assert.equal(gate.allowed,false);assert.deepEqual(gate.missing_paths,[]);assert.ok(gate.reason_codes.includes('PRODUCTION_DISABLED_P0'));
});
