// Invariant/reference harness only. There is deliberately no broker transport.
import { validateContract, requireThat, hashValue, matchesRef, reference, timestampMs, sealContract, assertEvidenceVisible } from '../contracts/validate.mjs';

function active(object, now) {
  requireThat(object.invalidation.status === 'ACTIVE', 'CARD_VERSION_INVALIDATED');
  if (object.invalidation.valid_until) requireThat(timestampMs(object.invalidation.valid_until) > timestampMs(now),'APPROVAL_EXPIRED');
  if (object.expires_at) requireThat(timestampMs(object.expires_at) > timestampMs(now),'APPROVAL_EXPIRED');
}
export function assertFresh(at, now, maxAgeSeconds = 5) {
  const age = timestampMs(now)-timestampMs(at);
  requireThat(age >=0,'FUTURE_MARKET_DATA'); requireThat(age <= maxAgeSeconds*1000,'STALE_MARKET_DATA');
}
export function assertVisible(envelope, cutoff, calendar = []) {
  assertEvidenceVisible(envelope,cutoff,calendar);
}
export function validateBrainPacket(packet, snapshot, context = {}) {
  validateContract('BrainPacket', packet, context); validateContract('SnapshotManifest', snapshot);
  requireThat(matchesRef(snapshot,packet.snapshot_ref) && packet.decision_cutoff === snapshot.decision_cutoff,'SNAPSHOT_BINDING_MISMATCH');
  requireThat(timestampMs(snapshot.frozen_at) <= timestampMs(packet.recorded_at),'INVALID_CLOCK');
  requireThat(hashValue(packet.evidence) === snapshot.data_hash && snapshot.evidence_refs.length === packet.evidence.length && packet.evidence.every((e,i) => matchesRef(e,snapshot.evidence_refs[i])),'SNAPSHOT_BINDING_MISMATCH');
  return packet;
}
export function visibleEnvelopes(envelopes, cutoff, calendar = []) {
  // Rejected titles/IDs/reasons do not become output metadata or hash inputs.
  return envelopes.filter(e => { try { assertVisible(e,cutoff,calendar); return true; } catch { return false; } }).map(e => structuredClone(e));
}
export function freezeSnapshot({ snapshot, envelopes, cutoff, calendar = [] }) {
  requireThat(snapshot.decision_cutoff===cutoff,'INVALID_CLOCK');
  const accepted=visibleEnvelopes(envelopes,cutoff,calendar);
  const frozen=sealContract({ ...snapshot, evidence_refs:accepted.map(reference), data_hash:hashValue(accepted) });
  validateContract('SnapshotManifest',frozen);
  requireThat(timestampMs(frozen.frozen_at) >= timestampMs(cutoff),'INVALID_CLOCK');
  return { manifest:frozen, evidence:accepted };
}
export function revealForRegression(frozen, decision, decisionHash, revealTime) {
  validateContract('SnapshotManifest',frozen.manifest);
  requireThat(hashValue(frozen.evidence)===frozen.manifest.data_hash,'HASH_MISMATCH');
  requireThat(frozen.manifest.evidence_refs.length===frozen.evidence.length && frozen.evidence.every((e,i)=>matchesRef(e,frozen.manifest.evidence_refs[i])),'HASH_MISMATCH');
  requireThat(hashValue(decision)===decisionHash,'HASH_MISMATCH');
  requireThat(timestampMs(revealTime)>timestampMs(frozen.manifest.frozen_at),'FREEZE_BEFORE_REVEAL_REQUIRED');
  return { frozen_hash:frozen.manifest.content_hash, decision_hash:decisionHash, reveal_at:revealTime };
}
export function createFreezeSession(frozen) {
  // The commitment is retained by this session, never supplied by the caller at reveal.
  const captured=structuredClone(frozen);
  let committed=null, revealed=false;
  return {
    commit(decision, at) {
      requireThat(!committed && !revealed,'DUPLICATE_DECISION');
      requireThat(timestampMs(at)>=timestampMs(captured.manifest.frozen_at),'INVALID_CLOCK');
      committed={ decision:structuredClone(decision), decision_hash:hashValue(decision), committed_at:at };
      return structuredClone(committed);
    },
    reveal(futureData, at) {
      requireThat(committed && !revealed,'FREEZE_BEFORE_REVEAL_REQUIRED');
      requireThat(timestampMs(at)>timestampMs(committed.committed_at),'FREEZE_BEFORE_REVEAL_REQUIRED');
      const proof=revealForRegression(captured,committed.decision,committed.decision_hash,at);
      revealed=true;
      return { proof, decision:structuredClone(committed.decision), future_data:structuredClone(futureData) };
    },
  };
}
export function orderTermsHash(order) {
  const fields=['object_id','object_version','mode','account_id','strategy_id','symbol','side','quantity','order_type','limit_price','trade_date','card_ref','signal_ref','decision_approval_ref','cost_ref','account_snapshot_hash','client_order_id','prepared_at','expires_at'];
  return hashValue(Object.fromEntries(fields.map(k => [k,order[k]])));
}
export function validateOrderChain({card,signal,decisionApproval,confirmation,order,cost,now,authority,currentAccountSnapshotHash}) {
  for (const [name,item] of [['ResearchCard',card],['SignalEvent',signal],['Approval',decisionApproval],['Approval',confirmation],['OrderIntent',order],['CostEstimate',cost]]) { validateContract(name,item); active(item,now); requireThat(timestampMs(item.recorded_at)<=timestampMs(now),'INVALID_CLOCK'); }
  for (const [object,key] of [[decisionApproval,'approved_at'],[confirmation,'approved_at'],[order,'prepared_at'],[cost,'estimated_at']]) requireThat(timestampMs(object[key])<=timestampMs(now),'INVALID_CLOCK');
  for (const object of [signal,decisionApproval,confirmation,cost,order]) {
    requireThat(object.strategy_id===card.strategy_id,'STRATEGY_NAMESPACE_MISMATCH');
    requireThat(object.mode===card.mode,'MODE_MISMATCH');
    requireThat(object.account_id===card.account_id,'ACCOUNT_MISMATCH');
    if ('symbol' in object) requireThat(object.symbol===card.symbol,'STRATEGY_NAMESPACE_MISMATCH');
  }
  requireThat(card.strategy_id!=='RESEARCH_6_18M' && card.trade.can_produce_order && !card.hard_blocks.length,'UNRESOLVED_BUSINESS_POLICY');
  requireThat(card.probability.calibrated,'UNCALIBRATED_PROBABILITY');
  requireThat(card.scoring_policy_version!=='UNSET_REQUIRED' && card.probability.edge_policy_version!=='UNSET_REQUIRED' && card.trade.sizing_policy_version!=='UNSET_REQUIRED','UNRESOLVED_BUSINESS_POLICY');
  requireThat(matchesRef(card,signal.card_ref),'CARD_VERSION_INVALIDATED');
  requireThat(signal.rule_version===card.rule_version,'SIGNAL_VERSION_INVALIDATED');
  requireThat(signal.triggered_at && timestampMs(signal.triggered_at)<=timestampMs(now),'INVALID_CLOCK');
  for (const a of [decisionApproval,confirmation,order]) {
    requireThat(matchesRef(card,a.card_ref),'CARD_VERSION_INVALIDATED');
    requireThat(matchesRef(signal,a.signal_ref),'SIGNAL_VERSION_INVALIDATED');
    requireThat(a.account_snapshot_hash===currentAccountSnapshotHash,'ORDER_TERMS_CHANGED');
  }
  requireThat(signal.state==='TRIGGERED' || signal.state==='ACKNOWLEDGED','SIGNAL_VERSION_INVALIDATED');
  assertFresh(signal.market_data_at,now);
  requireThat(matchesRef(decisionApproval,order.decision_approval_ref) && matchesRef(confirmation,order.final_confirmation_ref),'USER_APPROVAL_REQUIRED');
  requireThat(decisionApproval.phase==='DECISION_APPROVAL' && confirmation.phase==='FINAL_ORDER_CONFIRMATION','FINAL_CONFIRMATION_REQUIRED');
  for (const a of [decisionApproval,confirmation]) {
    requireThat(a.decision==='USER_APPROVED','USER_APPROVAL_REQUIRED');
    requireThat(authority?.actor_type==='HUMAN_USER' && authority.actor_id===a.actor_id && authority.verified_approval_hashes instanceof Set && authority.verified_approval_hashes.has(a.content_hash),'APPROVAL_NOT_AUTHENTICATED');
  }
  requireThat(timestampMs(decisionApproval.approved_at)>=timestampMs(signal.triggered_at ?? signal.recorded_at) && timestampMs(order.prepared_at)>=timestampMs(decisionApproval.approved_at) && timestampMs(confirmation.approved_at)>=timestampMs(order.prepared_at),'INVALID_CLOCK');
  requireThat(matchesRef(cost,order.cost_ref) && matchesRef(cost,confirmation.cost_ref),'ORDER_TERMS_CHANGED');
  requireThat(cost.side===order.side && cost.quantity===order.quantity && cost.price===order.limit_price,'ORDER_TERMS_CHANGED');
  requireThat(confirmation.order_terms_hash===orderTermsHash(order),'ORDER_TERMS_CHANGED');
  requireThat(order.status==='CONFIRMED','FINAL_CONFIRMATION_REQUIRED');
  // Return validation result only; no order is dispatched.
  return { structurally_preparable:true, production_execution_enabled:false, reason_codes:['PRODUCTION_DISABLED_P0'] };
}
export function unsetPaths(value, pointer='') {
  if (value==='UNSET_REQUIRED') return [pointer];
  if (!value || typeof value!=='object') return [];
  return Object.entries(value).flatMap(([key,v]) => unsetPaths(v,`${pointer}/${key}`));
}
export function productionGate(profile) {
  try { validateContract('AccountProfile',profile); }
  catch (error) { return { allowed:false, reason_codes:['UNSET_REQUIRED_CONFIG','PRODUCTION_DISABLED_P0'], validation_code:error.code, missing_paths:[] }; }
  const missing=unsetPaths(profile);
  const codes=new Set(['PRODUCTION_DISABLED_P0']);
  if (missing.length) codes.add('UNSET_REQUIRED_CONFIG');
  if (profile.profile_kind!=='VERIFIED_ACCOUNT') codes.add('SYNTHETIC_FIXTURE_ONLY');
  for (const k of ['broker_capability_verified','cost_reconciliation_passed','program_trading_compliance_checked','paper_acceptance_passed','kill_switch_test_passed']) if (!profile[k]) codes.add('UNRESOLVED_BUSINESS_POLICY');
  return { allowed:false, reason_codes:[...codes], missing_paths:missing };
}
