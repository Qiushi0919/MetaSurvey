// Closed synthetic entry over the unchanged, reviewed research composition.
// No real dataset, packet, result, permission or configuration is an input.
import fs from 'node:fs/promises';
import path from 'node:path';
import {canonical,hashValue,reference} from '../../src/contracts/validate.mjs';
import {assertSanitized} from '../../src/closure/contracts.mjs';
import {runFixtureChain,verifyFixtureChain,compareFixtureChains,invalidateFixtureChain} from '../../real-slice/src/fixture-chain.mjs';

const cases = new Set(['BASE','UPSTREAM_REVISION','TIMING_GAP','HARD_BLOCK']);
const issued = new WeakMap();
const check = (ok,code) => {if(!ok)throw new Error(code);};
export const artifacts = x => Object.fromEntries(['packet','draft','assessment','card'].map(k=>[k,x[k]]));

export async function produceFixture(options) {
 check(options && Object.getPrototypeOf(options) === Object.prototype &&
  Object.getOwnPropertySymbols(options).length===0 &&
  canonical(Object.getOwnPropertyNames(options).sort()) === canonical(['directory','fixture_case']), 'OVERNIGHT_REAL_INPUT_FORBIDDEN');
 const descriptors=Object.getOwnPropertyDescriptors(options);
 check(['directory','fixture_case'].every(k=>descriptors[k]&&Object.hasOwn(descriptors[k],'value')&&
  !Object.hasOwn(descriptors[k],'get')&&!Object.hasOwn(descriptors[k],'set')), 'OVERNIGHT_OPTIONS_ACCESSOR_FORBIDDEN');
 // Capture primitives once; guarded values must be the exact values consumed.
 // The caller's object is never read after this snapshot (including by producer).
 const snapshot=Object.freeze({directory:descriptors.directory.value,fixture_case:descriptors.fixture_case.value});
 check(cases.has(snapshot.fixture_case), 'OVERNIGHT_FIXTURE_CASE_INVALID');
 check(typeof snapshot.directory === 'string' && path.isAbsolute(snapshot.directory) &&
  path.resolve(snapshot.directory) === snapshot.directory, 'OVERNIGHT_FIXTURE_DIRECTORY_INVALID');
 const stat = await fs.lstat(snapshot.directory);
 check(stat.isDirectory() && !stat.isSymbolicLink() && await fs.realpath(snapshot.directory) === snapshot.directory,
  'OVERNIGHT_FIXTURE_DIRECTORY_INVALID');
 const result = await runFixtureChain(snapshot);
 // The export projector forbids outcome-shaped *field names*. Native V1 cards
 // require expected_mae_bps=UNSET_REQUIRED, so their unchanged contract verifier
 // remains authoritative; do not apply a different packet schema to that card.
 assertSanitized(result.packet);
 for (const name of ['packet','draft','assessment','card']) {
  const text=JSON.stringify(result[name]);
  check(!/(?:-----BEGIN|\bsk-[A-Za-z0-9]{20,}|\bAKIA[A-Z0-9]{16}\b|Bearer\s+\S+|file:\/\/|\/Users\/|\/tmp\/|\/private\/|postgres(?:ql)?:\/\/|[A-Z]:\\)/i.test(text),
   'OVERNIGHT_SECRET_OR_PATH_LEAKAGE');
 }
 check(result.packet.fixture_scope === 'SYNTHETIC_TEST_ONLY' && result.draft.fixture_scope === 'SYNTHETIC_TEST_ONLY' &&
  result.card.provenance.visibility_basis === 'SYNTHETIC' && result.card.symbol === 'SYNTHETIC:NON_SECURITY_FIXTURE' &&
  result.card.account_id === 'SYNTHETIC_FIXTURE:NON_ACCOUNT', 'OVERNIGHT_FIXTURE_AUTHORITY_INVALID');
 check(result.execution_writes === 0 && result.broker_transport_calls === 0 && result.production_enabled === false &&
  canonical(result.execution_state_before) === canonical(result.execution_state_after), 'OVERNIGHT_EXECUTION_FORBIDDEN');
 issued.set(result,canonical(result));
 return result;
}

export function verifyProducedFixture(result, {use_at}={}) {
 check(issued.get(result) === canonical(result), 'OVERNIGHT_FIXTURE_UNREGISTERED_OR_MUTATED');
 return verifyFixtureChain(result.chain,{...artifacts(result),use_at});
}

export function fixtureProof(result) {
 verifyProducedFixture(result);
 const objectRefs = Object.fromEntries(['packet','draft','assessment','card','chain'].map(k=>[k,reference(result[k])]));
 return {version:'1.0.0-diagnostic',kind:'SYNTHETIC_RESEARCH_CHAIN_PROOF',fixture:true,namespace:'CORE_40',
  source_admission:'BLOCKED',historical_visibility_proven:false,productionGate:false,
  real_snapshot_B_exists:false,real_card_count:0,model_calls:0,real_admission_receipts_issued:0,
  execution_writes:result.execution_writes,broker_transport_calls:result.broker_transport_calls,
  execution_state_hash:hashValue(result.execution_state_before),object_refs:objectRefs,
  replay_hash:result.replay_hash,phase_order:result.identity.phase_order,
  isolation_mechanism:result.isolation.mechanism,deny_default:result.isolation.deny_default,
  export_packet_sanitized:true,native_card_verified_by_frozen_contract:true,other_artifacts_secret_path_scan:true,
  fixture_time_is_not_actual_forward_paper_day:true,
  chain_card_scope:'SYNTHETIC_TEST_ONLY',real_account_fields:'UNSET_REQUIRED'};
}

export async function runFixtureSuite(directory) {
 const first=await produceFixture({directory,fixture_case:'BASE'}),second=await produceFixture({directory,fixture_case:'BASE'});
 check(canonical(first.chain)===canonical(second.chain) && first.replay_hash===second.replay_hash,'OVERNIGHT_REPLAY_DIFFERED');
 const baseProof=fixtureProof(first),checks=[];
 const attack=(name,fn)=>{let rejected=false;try{fn();}catch{rejected=true;}check(rejected,'OVERNIGHT_ATTACK_NOT_BLOCKED');checks.push({name,result:'BLOCKED_AS_REQUIRED'});};
 attack('EXPIRED_CARD',()=>verifyProducedFixture(first,{use_at:'2026-10-02T16:00:00.000000001+08:00'}));
 attack('BEFORE_CUTOFF',()=>verifyProducedFixture(first,{use_at:'2026-09-30T15:59:59.999999999+08:00'}));
 attack('RESEALED_CALLER_COPY',()=>verifyProducedFixture(structuredClone(first)));
 const revision=await produceFixture({directory,fixture_case:'UPSTREAM_REVISION'}),revisionReplay=await produceFixture({directory,fixture_case:'UPSTREAM_REVISION'});
 check(canonical(revision.chain)===canonical(revisionReplay.chain)&&revision.replay_hash===revisionReplay.replay_hash,'OVERNIGHT_REPLAY_DIFFERED');
 const revisionProof=fixtureProof(revision),delta=compareFixtureChains(first.chain,revision.chain);
 check(delta.invalidated_card_refs.length===1 && revision.card.object_version===first.card.object_version+1,'OVERNIGHT_VERSION_CHAIN_INVALID');
 attack('UPSTREAM_CHANGE_STALE_CARD',()=>verifyProducedFixture(first));
 const timing=await produceFixture({directory,fixture_case:'TIMING_GAP'}),timingProof=fixtureProof(timing);
 check(timing.assessment.research_grade==='HIGH'&&timing.assessment.actionability_grade==='A'&&timing.chain.max_action==='WATCH','OVERNIGHT_FROZEN_SEMANTICS_DIFFERED');
 const blocked=await produceFixture({directory,fixture_case:'HARD_BLOCK'}),blockedProof=fixtureProof(blocked);
 check(blocked.assessment.actionability_grade==='X'&&blocked.chain.max_action==='BLOCKED','OVERNIGHT_FROZEN_SEMANTICS_DIFFERED');
 // These narrow the frozen module's authority irreversibly; run last.
 invalidateFixtureChain(blocked.chain,{reason:'RECEIPT_REVOKED'});
 attack('RECEIPT_REVOCATION',()=>verifyProducedFixture(blocked));
 invalidateFixtureChain(revision.chain,{reason:'POLICY_REVOKED'});
 attack('POLICY_REVOCATION',()=>verifyProducedFixture(revision));
 return {proof:{...baseProof,kind:'SYNTHETIC_CHAIN_SUITE_PROOF',deterministic_executions:4,total_fixture_executions:6,
  base_and_revision_replays_equal:true,version_delta:delta,invalidation_attacks:checks,
  cases:[baseProof,revisionProof,timingProof,blockedProof],new_real_source_observations:0},
  artifacts:{base:artifacts(first),revision:artifacts(revision),timing:artifacts(timing),hard_block:artifacts(blocked)}};
}
