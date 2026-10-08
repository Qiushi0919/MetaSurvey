import test,{before,after} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {canonical,reference,sealContract,validateContract} from '../../src/contracts/validate.mjs';
import {sealClosure} from '../../src/closure/contracts.mjs';
import {seal} from '../../p1b/src/contracts.mjs';
import {validate} from '../src/contracts.mjs';
import {runFixtureChain,verifyFixtureChain,compareFixtureChains,invalidateFixtureChain} from '../src/fixture-chain.mjs';

let directory,base,replay;
const artifacts=x=>Object.fromEntries(['packet','draft','assessment','card'].map(k=>[k,x[k]]));
before(async()=>{directory=await fs.mkdtemp(path.join(os.tmpdir(),'ashare-fixture-chain-test-'));base=await runFixtureChain({directory});replay=await runFixtureChain({directory});});
after(async()=>{if(directory)await fs.rm(directory,{recursive:true,force:true});});

test('composed fixture actually crosses the native-isolated Closure consumer, import, frozen semantics and native V1 card',()=>{
 assert.equal(verifyFixtureChain(base.chain,artifacts(base)),true);validate('FixtureResearchChain',base.chain);validateContract('ResearchCard',base.card);
 assert.equal(base.packet.contract_version,'1.1.0');assert.equal(base.draft.contract_version,'1.0.0');assert.equal(base.assessment.contract_version,'1.0.0');assert.equal(base.card.contract_version,'1.0.0');
 assert.equal(base.isolation.mechanism,'MACOS_SANDBOX_EXEC_AND_NODE_PERMISSION');assert.equal(base.isolation.deny_default,true);
 assert.equal(base.packet.strategy_id,'CORE_40');assert.equal(base.draft.strategy_id,'CORE_40');assert.equal(base.assessment.strategy_id,'CORE_40');assert.equal(base.card.strategy_id,'CORE_40');
 assert.deepEqual(base.chain.packet_ref,reference(base.packet));assert.deepEqual(base.chain.draft_ref,reference(base.draft));assert.deepEqual(base.chain.assessment_ref,reference(base.assessment));assert.deepEqual(base.chain.card_ref,reference(base.card));
 assert.ok(base.chain.source_evidence_refs.length>0);assert.deepEqual(base.chain.source_evidence_refs,base.packet.evidence.map(reference));assert.deepEqual(base.identity.phase_order,['COST_ESTIMATED','SUITABILITY_EVALUATED']);assert.equal(base.identity.draft_cost_test.scope,'SYNTHETIC_TEST_ONLY');
});

test('two real fixture executions replay exact packet/draft/assessment/card chain and identity hashes',()=>{
 assert.equal(base.replay_hash,replay.replay_hash);for(const k of ['chain','packet','draft','assessment','card','identity'])assert.equal(canonical(base[k]),canonical(replay[k]));
 assert.deepEqual(compareFixtureChains(base.chain,replay.chain).invalidated_card_refs,[]);
});

test('synthetic S means REQUEST_REVIEW only while native card real grades/money/edge/probability/sizing stay unknown',()=>{
 assert.equal(base.assessment.actionability_grade,'S');assert.equal(base.assessment.next_action,'REQUEST_REVIEW');assert.equal(base.chain.max_action,'REQUEST_REVIEW');assert.equal(base.chain.real_grade,'UNSET_REQUIRED');assert.equal(base.card.grade,'UNSET_REQUIRED');assert.equal(base.card.price.reference_price,null);
 assert.equal(base.card.symbol,'SYNTHETIC:NON_SECURITY_FIXTURE');assert.equal(base.card.account_id,'SYNTHETIC_FIXTURE:NON_ACCOUNT');assert.equal(base.card.provenance.visibility_basis,'SYNTHETIC');
 for(const k of ['real_net_edge','real_sizing','probability'])assert.equal(base.chain[k],'UNSET_REQUIRED');assert.equal(base.chain.real_account_suitability,'BLOCKED');
 for(const k of ['tradeable','can_produce_order','production_enabled'])assert.equal(base.chain[k],false);assert.equal(base.card.trade.can_produce_order,false);assert.equal(base.card.probability.calibrated,false);assert.deepEqual(base.card.probability.scenarios,[]);assert.equal(base.assessment.research_card_ref,null);
 assert.equal(base.identity.semantics_evidence_role,'ILLUSTRATIVE_FIXED_COORDINATE_NOT_DERIVED_COMPANY_FACT');
});

test('native OS-only and Node probes deny network, process spawn, artifact writes and capabilities',()=>{
 for(const probes of [base.probes,base.native_os_probes]){assert.equal(probes.network.denied,true);assert.ok(probes.execution.length===2&&probes.execution.every(x=>x.denied));assert.equal(probes.write.denied,true);assert.deepEqual(probes.capability.environment_keys,['TZ']);assert.equal(probes.capability.global_db_present,false);assert.equal(probes.capability.global_broker_present,false);assert.equal(probes.capability.regular_file_descriptor_count,0);}
 assert.equal(base.execution_writes,0);assert.equal(base.broker_transport_calls,0);assert.deepEqual(base.execution_state_before,base.execution_state_after);
});

test('wrong packet/draft/assessment/card/receipt/snapshot refs fail even when caller recalculates chain hash',()=>{
 for(const k of ['packet_ref','draft_ref','assessment_ref','card_ref','receipt_ref','snapshot_ref']){const wrong=structuredClone(base.chain);wrong[k].object_version+=1;assert.throws(()=>verifyFixtureChain(sealContract(wrong),artifacts(base)),/SLICE_REF_INVALIDATED/);}
 const unknown=sealContract({...base.chain,object_id:'synthetic:caller-chain'});assert.throws(()=>verifyFixtureChain(unknown,artifacts(base)),/SLICE_REF_INVALIDATED/);
});

test('resealed caller objects cannot replace trusted imported packet/draft/assessment/card evidence',()=>{
 const p=structuredClone(base.packet);p.object_version++;const d=structuredClone(base.draft);d.object_version++;const a=structuredClone(base.assessment);a.object_version++;const c=structuredClone(base.card);c.object_version++;
 for(const [name,value] of [['packet',sealClosure(p)],['draft',sealClosure(d)],['assessment',seal(a)],['card',sealContract(c)]])assert.throws(()=>verifyFixtureChain(base.chain,{...artifacts(base),[name]:value}),/SLICE_REF_INVALIDATED|CLOSURE_|P1B_/);
 const upgraded=structuredClone(base.card);upgraded.grade='S';upgraded.trade.can_produce_order=true;upgraded.hard_blocks=[];assert.throws(()=>verifyFixtureChain(base.chain,{...artifacts(base),card:sealContract(upgraded)}),/SLICE_/);
});

test('invalidation parents, semantics-input hash and trace cannot be caller spoofed',()=>{
 const attacks=[{...base.chain,semantics_input_hash:'sha256:'+'0'.repeat(64)},{...base.chain,trace_id:'caller-trace'},{...base.chain,source_evidence_refs:[base.chain.card_ref]},{...base.chain,invalidation:{...base.chain.invalidation,parent_refs:[base.chain.card_ref,base.chain.card_ref,base.chain.card_ref,base.chain.card_ref]}}];
 for(const attack of attacks)assert.throws(()=>verifyFixtureChain(sealContract(attack),artifacts(base)),/SLICE_REF_INVALIDATED/);
});

test('chain verifier rejects expired/before-cutoff/offsetless use clocks and invalidated card',()=>{
 for(const use_at of ['2026-10-03T00:00:00+08:00','2026-09-29T00:00:00+08:00','2026-09-30T16:00:00'])assert.throws(()=>verifyFixtureChain(base.chain,{...artifacts(base),use_at}),/SLICE_CARD_INVALIDATED/);
 const invalid=structuredClone(base.card);invalid.invalidation={...invalid.invalidation,status:'INVALIDATED',invalidated_at:base.packet.decision_cutoff,reason_code:'CARD_VERSION_INVALIDATED'};assert.throws(()=>verifyFixtureChain(base.chain,{...artifacts(base),card:sealContract(invalid)}),/SLICE_CARD_INVALIDATED/);
});

test('fixture cutoff and TTL use exact nanosecond boundaries, including equivalent timezone offsets',()=>{
 assert.equal(base.packet.decision_cutoff,'2026-09-30T16:00:00+08:00');assert.equal(base.card.invalidation.valid_until,'2026-10-02T16:00:00+08:00');
 for(const use_at of [base.packet.decision_cutoff,'2026-09-30T08:00:00.000000000Z','2026-09-30T16:00:00.000000001+08:00','2026-10-02T15:59:59.999999999+08:00',base.card.invalidation.valid_until,'2026-10-02T08:00:00.000000000Z'])assert.equal(verifyFixtureChain(base.chain,{...artifacts(base),use_at}),true);
 for(const use_at of ['2026-09-30T15:59:59.999999999+08:00','2026-09-30T07:59:59.999999999Z','2026-10-02T16:00:00.000000001+08:00','2026-10-02T08:00:00.000000001Z'])assert.throws(()=>verifyFixtureChain(base.chain,{...artifacts(base),use_at}),/SLICE_CARD_INVALIDATED/);
});

test('fixture verifier rejects normalized illegal dates and 24:00 even if JavaScript places them inside the valid window',()=>{
 // September 31 and October 1 24:00 normalize inside this fixture's validity;
 // rejecting them must depend on ISO/calendar validity rather than range alone.
 for(const use_at of ['2026-09-31T16:00:00+08:00','2026-10-01T24:00:00+08:00','2026-02-30T16:00:00+08:00','2026-10-01T12:00:00.0000000001+08:00'])assert.throws(()=>verifyFixtureChain(base.chain,{...artifacts(base),use_at}),/SLICE_CARD_INVALIDATED/);
});

test('fixture chain cannot widen namespace, source scope, Grade or production fields',async()=>{
 for(const mutation of [{namespace:'EVENT_3'},{scope:'REAL_STOCK_RESEARCH'},{production_enabled:true},{can_produce_order:true},{real_grade:'S'},{max_action:'BUY'},{probability:'0.85'}])assert.throws(()=>verifyFixtureChain(sealContract({...base.chain,...mutation}),artifacts(base)),/SLICE_DQ_FAILED/);
 await assert.rejects(()=>runFixtureChain({directory,fixture_case:'REAL_STOCK'}),/SLICE_SCOPE_MISMATCH/);
});

test('a real synthetic upstream bar revision supersedes compatibility card, including when semantics output is unchanged',async()=>{
 const revised=await runFixtureChain({directory,fixture_case:'UPSTREAM_REVISION'});assert.notEqual(base.packet.content_hash,revised.packet.content_hash);assert.notEqual(base.draft.content_hash,revised.draft.content_hash);assert.equal(base.assessment.content_hash,revised.assessment.content_hash);assert.equal(revised.card.object_version,base.card.object_version+1);assert.equal(revised.chain.object_version,base.chain.object_version+1);
 assert.throws(()=>verifyFixtureChain(base.chain,artifacts(base)),/SLICE_CARD_INVALIDATED/);assert.equal(verifyFixtureChain(revised.chain,artifacts(revised)),true);
 const diff=compareFixtureChains(base.chain,revised.chain);assert.deepEqual(diff.invalidated_card_refs,[base.chain.card_ref]);assert.ok(diff.changed_ref_names.includes('packet_ref')&&diff.changed_ref_names.includes('draft_ref')&&diff.changed_ref_names.includes('card_ref'));assert.ok(diff.unaffected_ref_names.includes('assessment_ref'));assert.equal(diff.real_snapshot_B_exists,false);
 const same=await runFixtureChain({directory,fixture_case:'UPSTREAM_REVISION'});assert.equal(revised.replay_hash,same.replay_hash);assert.equal(revised.chain.content_hash,same.chain.content_hash);
});

test('composition reuses frozen Quality-vs-Timing and HardBlock precedence without duplicating grade logic',async()=>{
 const timing=await runFixtureChain({directory,fixture_case:'TIMING_GAP'});assert.equal(timing.assessment.research_grade,'HIGH');assert.equal(timing.assessment.dimensions.company_quality,'PASS');assert.equal(timing.assessment.dimensions.timing,'GAP');assert.equal(timing.assessment.actionability_grade,'A');assert.equal(timing.chain.max_action,'WATCH');assert.equal(timing.card.grade,'UNSET_REQUIRED');
 const blocked=await runFixtureChain({directory,fixture_case:'HARD_BLOCK'});assert.equal(blocked.assessment.research_grade,'HIGH');assert.equal(blocked.assessment.actionability_grade,'X');assert.equal(blocked.chain.max_action,'BLOCKED');assert.throws(()=>verifyFixtureChain(timing.chain,artifacts(timing)),/SLICE_CARD_INVALIDATED/);assert.equal(blocked.execution_writes,0);assert.deepEqual(blocked.execution_state_before,blocked.execution_state_after);
});

test('fixture receipt/policy revocation is irreversible and no repeat producer run restores authority',async()=>{
 const local=await runFixtureChain({directory,fixture_case:'BASE'});
 assert.throws(()=>invalidateFixtureChain(local.chain,{reason:'APPROVE'}),/SLICE_PERMISSION_DENIED/);assert.equal(verifyFixtureChain(local.chain,artifacts(local)),true);
 const revoked=invalidateFixtureChain(local.chain,{reason:'RECEIPT_REVOKED'});assert.equal(revoked.invalidation_reason,'RECEIPT_REVOKED');assert.equal(revoked.production_enabled,false);
 assert.throws(()=>verifyFixtureChain(local.chain,artifacts(local)),/SLICE_CARD_INVALIDATED/);await assert.rejects(()=>runFixtureChain({directory,fixture_case:'BASE'}),/SLICE_CARD_INVALIDATED/);
 const other=await runFixtureChain({directory,fixture_case:'UPSTREAM_REVISION'});invalidateFixtureChain(other.chain,{reason:'POLICY_REVOKED'});assert.throws(()=>verifyFixtureChain(other.chain,artifacts(other)),/SLICE_CARD_INVALIDATED/);await assert.rejects(()=>runFixtureChain({directory,fixture_case:'UPSTREAM_REVISION'}),/SLICE_CARD_INVALIDATED/);
});
