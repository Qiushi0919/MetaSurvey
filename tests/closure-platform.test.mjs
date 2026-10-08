import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import {createClosureDataFixture} from './fixtures/closure/data-helpers.mjs';
import {buildBrainPacket,writeManualExport} from '../src/closure/export.mjs';
import {importResearchResult,assertDraftTransition} from '../src/closure/import.mjs';
import {runIsolatedConsumer,isolationAvailable} from '../src/closure/isolation.mjs';
import {verifyExportArtifact} from '../src/closure/consumer.mjs';
import {closureRef,validateClosure,createFixtureAuthority} from '../src/closure/contracts.mjs';
import {sealCostProfile} from '../src/cost/index.mjs';
import {canonical,hashValue,sealContract} from '../src/contracts/validate.mjs';

const baseline=JSON.parse(await fs.readFile(new URL('./fixtures/p1a-paper/baseline.json',import.meta.url)));
// Explicit synthetic hypothetical costs, never production defaults.
const costProfile=sealCostProfile({...baseline.cost_profile,effective_from:'2026-01-01',effective_to:'2026-12-31'});
const realAccountProfile=JSON.parse(await fs.readFile(new URL('../config/account-profile.unconfigured.v1.json',import.meta.url)));
const tradeTerms={side:'BUY',price:'10',quantity:100,trade_date:'2026-09-30'};
const resultFor=packet=>({packet_ref:closureRef(packet),receipt_ref:closureRef(packet.receipt),strategy_id:packet.strategy_id,purpose:packet.purpose,observations:packet.evidence.map(e=>({evidence_ref:closureRef(e),statement:'Synthetic evidence is visible at its cutoff.',classification:'DESCRIPTIVE_ONLY'}))});
async function setup(t){const f=await createClosureDataFixture();t.after(()=>f.db.close());const packet=await buildBrainPacket(f);return {...f,packet,result:resultFor(packet),realAccountProfile,costProfile,tradeTerms};}
async function businessCounts(db){const tables=['public.approvals','public.order_drafts','public.orders_sim','public.orders_real','public.fills_sim','public.fills_real','public.ledger_sim','public.ledger_real','p1a_paper.accounts','p1a_paper.orders','p1a_paper.fills','p1a_paper.ledger'];return Object.fromEntries(await Promise.all(tables.map(async table=>[table,(await db.query(`SELECT count(*)::int n FROM ${table}`)).rows[0].n])));}

test('closure import uses actual cost before account suitability and deterministically produces NON_TRADEABLE only',async t=>{
 const f=await setup(t),before=await businessCounts(f.db),events=[];
 const service={...f.service,audit:async event=>{events.push(event.event_type);return f.service.audit(event);}};
 let accountReads=0;const observed=new Proxy(realAccountProfile,{get(target,key){if(key==='contract_name'){accountReads++;events.push('ACCOUNT_READ');}return target[key];}});
 const first=await importResearchResult({...f,service,realAccountProfile:observed}),second=await importResearchResult(f);
 assert.ok(accountReads>0);assert.ok(events.indexOf('IMPORT_COST_ESTIMATED')<events.indexOf('ACCOUNT_READ'));
 assert.deepEqual(first.phase_order,['COST_ESTIMATED','SUITABILITY_EVALUATED']);assert.equal(first.cost_estimate.total_friction_cents,'195');assert.equal(first.draft.cost_test.estimate_hash,hashValue(first.cost_estimate));assert.equal(first.draft.cost_test.cost_profile_ref.content_hash,costProfile.content_hash);
 assert.equal(canonical(first.draft),canonical(second.draft));validateClosure('ResearchDraft',first.draft);
 assert.equal(first.draft.can_produce_order,false);assert.equal(first.draft.tradeable,false);assert.equal(first.draft.validation_status,'NON_TRADEABLE');assert.equal(first.draft.real_account_suitability,'BLOCKED');
 for(const key of ['real_net_edge','real_sizing','grade','scoring_policy_version','probability_policy_version','sizing_policy_version','edge_policy_version'])assert.equal(first.draft[key],'UNSET_REQUIRED');
 assert.deepEqual(await businessCounts(f.db),before);
});

test('closure missing/unknown/real cost cannot reach suitability and fake cost_ref cannot replace Cost Engine',async t=>{
 const f=await setup(t);let reads=0;const observed=new Proxy(realAccountProfile,{get(target,key){reads++;return target[key];}});
 for(const c of [undefined,{...costProfile,profile_scope:'REAL'},sealCostProfile({...costProfile,commission_rate:'UNSET_REQUIRED'})])await assert.rejects(importResearchResult({...f,costProfile:c,realAccountProfile:observed}),/CLOSURE_COST_REQUIRED_FIRST|EXACT_RATE_REQUIRED/);
 await assert.rejects(importResearchResult({...f,result:{...f.result,cost_ref:closureRef(costProfile)}}),/CLOSURE_IMPORT_INVALID/);assert.equal(reads,0);
 const{rows}=await f.db.query("SELECT event_type FROM p1a_closure.audit WHERE event_type='IMPORT_COST_ESTIMATED'");assert.equal(rows.length,0);
});

test('closure caller real-account verification assertions cannot promote fixture suitability',async t=>{
 const f=await setup(t),profile=sealContract({...realAccountProfile,broker_capability_verified:true,cost_reconciliation_passed:true,program_trading_compliance_checked:true,paper_acceptance_passed:true,kill_switch_test_passed:true});
 const{draft}=await importResearchResult({...f,realAccountProfile:profile});assert.equal(draft.real_account_suitability,'BLOCKED');assert.equal(draft.real_net_edge,'UNSET_REQUIRED');assert.equal(draft.real_sizing,'UNSET_REQUIRED');assert.equal(draft.tradeable,false);
});

test('closure untrusted LLM BUY/APPROVE/HUMAN/OrderIntent and arbitrary payload cannot write execution objects',async t=>{
 const f=await setup(t),before=await businessCounts(f.db);
 const mutations=[...['BUY','APPROVE','HUMAN_USER','OrderIntent','REAL_ACCOUNT_SUITABLE','REAL_NET_EDGE','REAL_SIZING','TRADEABLE','broker'].map(statement=>({...f.result,observations:[{...f.result.observations[0],statement}]})),{...f.result,Approval:{actor_type:'HUMAN_USER'}},{...f.result,OrderIntent:{side:'BUY'}},{...f.result,productionGate:true},{...f.result,observations:[{...f.result.observations[0],arbitrary_payload:{instruction:'BUY'}}]}];
 for(const result of mutations)await assert.rejects(importResearchResult({...f,result}),/CLOSURE_LLM_EXECUTION_INJECTION|CLOSURE_IMPORT_INVALID/);
 assert.deepEqual(await businessCounts(f.db),before);
});

test('closure result namespace/purpose/version/evidence crossover and future/path/secret descriptions are refused',async t=>{
 const f=await setup(t);
 const mutations=[{result:{...f.result,strategy_id:'CORE_40'},code:'CLOSURE_NAMESPACE_MISMATCH'},{result:{...f.result,purpose:'REAL_RESEARCH'},code:'CLOSURE_PURPOSE_MISMATCH'},{result:{...f.result,receipt_ref:{...f.result.receipt_ref,object_version:2}},code:'CLOSURE_RECEIPT_INVALIDATED'},{result:{...f.result,observations:[{...f.result.observations[0],evidence_ref:{...f.result.observations[0].evidence_ref,content_hash:hashValue('not admitted')}}]},code:'CLOSURE_IMPORT_INVALID'},...['MAE is 20','MFE next session','future_return is high','outcome is profitable'].map(statement=>({result:{...f.result,observations:[{...f.result.observations[0],statement}]},code:'CLOSURE_OUTCOME_LEAKAGE'})),...['file:///private/fixture/raw.json','/Users/synthetic/raw.db','Bearer SYNTHETIC_ATTACK_ONLY'].map(statement=>({result:{...f.result,observations:[{...f.result.observations[0],statement}]},code:'CLOSURE_SECRET_OR_PATH_LEAKAGE'}))];
 for(const{result,code}of mutations)await assert.rejects(importResearchResult({...f,result}),e=>e.code===code);
});

test('closure Draft cannot transition into Candidate/Signal/Approval/OrderIntent/Order/Fill',async t=>{
 const f=await setup(t),{draft}=await importResearchResult(f);
 assert.equal(assertDraftTransition(draft,'ResearchDraft'),draft);
 for(const kind of ['CandidateTradeable','CandidateEligibility','Signal','SignalEvent','Approval','OrderIntent','Order','Fill','UNKNOWN'])assert.throws(()=>assertDraftTransition(draft,kind),/CLOSURE_DRAFT_NON_EXECUTABLE/);
 assert.throws(()=>assertDraftTransition({...draft,can_produce_order:true},'OrderIntent'),/CLOSURE_IMPORT_INVALID|CLOSURE_HASH_MISMATCH/);
});

test('closure standalone consumer pins parent public key and checks artifact/receipt/projection integrity',async t=>{
 const f=await setup(t),key=f.service.trustPublicKeyDer();assert.equal(verifyExportArtifact(f.packet,key),f.packet);
 for(const packet of [{...f.packet,production_enabled:true},{...f.packet,projection_hash:hashValue('changed')},{...f.packet,receipt:{...f.packet.receipt,admission:'BLOCKED'}},{...f.packet,proof:{...f.packet.proof,signature:'A'.repeat(86)+'=='}}])assert.throws(()=>verifyExportArtifact(packet,key),/CLOSURE_/);
 assert.throws(()=>verifyExportArtifact(f.packet,createFixtureAuthority(Buffer.alloc(32,74)).publicKeyDer),/CLOSURE_SIGNATURE_INVALID/);
});

test('closure actual isolated MANUAL_EXPORT roundtrip blocks raw/DB/credentials/repo/network/exec in native OS and Node layers',async t=>{
 const f=await setup(t),dir=await fs.mkdtemp(path.join(os.tmpdir(),'closure-platform-test-'));t.after(()=>fs.rm(dir,{recursive:true,force:true}));
 const exported=await writeManualExport({...f,directory:dir});
 if(!await isolationAvailable()){await assert.rejects(runIsolatedConsumer({...f,export_path:exported.path}),/CLOSURE_ISOLATION_UNAVAILABLE/);return;}
 const forbidden=[];for(const name of ['raw.json','state.db','credentials.json','broker-capability.json']){const file=path.join(dir,name);await fs.writeFile(file,canonical({scope:'SYNTHETIC_TEST_ONLY',private_canary:name}));forbidden.push(file);}forbidden.push(path.resolve('package.json'),path.resolve('config/account-profile.unconfigured.v1.json'));
 const server=net.createServer(socket=>socket.end());await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
 const before=await businessCounts(f.db),out=await runIsolatedConsumer({...f,export_path:exported.path,probeOptions:{read_paths:forbidden,network:true,network_port:server.address().port,exec:true,capability_discovery:true}});
 for(const probes of [out.probes,out.native_os_probes]){assert.equal(probes.reads.length,forbidden.length);assert.ok(probes.reads.every(r=>r.denied));assert.equal(probes.network.denied,true);assert.deepEqual(probes.execution,[{index:0,denied:true},{index:1,denied:true}]);assert.deepEqual(probes.capability.environment_keys,['TZ']);assert.equal(probes.capability.global_db_present,false);assert.equal(probes.capability.global_broker_present,false);assert.equal(probes.capability.regular_file_descriptor_count,0);assert.equal(probes.write.denied,true);}
 assert.equal(out.execution_writes,0);assert.equal(out.broker_transport_calls,0);assert.equal(out.isolation.artifact_byte_hash,exported.byte_hash);assert.equal(out.isolation.deny_default,true);
 const imported=await importResearchResult({...f,result:out.result});assert.equal(imported.draft.tradeable,false);assert.equal(imported.draft.can_produce_order,false);assert.deepEqual(await businessCounts(f.db),before);
});

test('closure isolated consumer refuses modified/symlink artifact and caller runtime permission overrides',async t=>{
 const f=await setup(t),dir=await fs.mkdtemp(path.join(os.tmpdir(),'closure-platform-test-'));t.after(()=>fs.rm(dir,{recursive:true,force:true}));const e=await writeManualExport({...f,directory:dir});
 if(!await isolationAvailable()){await assert.rejects(runIsolatedConsumer({...f,export_path:e.path}),/CLOSURE_ISOLATION_UNAVAILABLE/);return;}
 await assert.rejects(runIsolatedConsumer({...f,export_path:e.path,probeOptions:{allowed_dirs:[dir]}}),/CLOSURE_IMPORT_INVALID/);
 await fs.writeFile(e.path,canonical({...f.packet,can_produce_order:true}));await assert.rejects(runIsolatedConsumer({...f,export_path:e.path}),/CLOSURE_HASH_MISMATCH/);
 await fs.writeFile(e.path,canonical(f.packet));const link=path.join(dir,'symlink.json');await fs.symlink(e.path,link);await assert.rejects(runIsolatedConsumer({...f,export_path:link}),/ELOOP|CLOSURE_IMPORT_INVALID/);
});

test('closure consumer and importer check live receipt again at final use boundary',async t=>{
 const f=await setup(t),dir=await fs.mkdtemp(path.join(os.tmpdir(),'closure-platform-test-'));t.after(()=>fs.rm(dir,{recursive:true,force:true}));const e=await writeManualExport({...f,directory:dir});
 if(await isolationAvailable()){let calls=0;const service={...f.service,verifyPacket:async args=>{if(++calls===2)await f.service.revokeReceipt({hash:f.receipt.content_hash,now:f.now,reason_code:'CLOSURE_RECEIPT_REVOKED'});return f.service.verifyPacket(args);}};await assert.rejects(runIsolatedConsumer({...f,service,export_path:e.path}),/CLOSURE_RECEIPT_REVOKED/);assert.equal(calls,2);}
 else await f.service.revokeReceipt({hash:f.receipt.content_hash,now:f.now,reason_code:'CLOSURE_RECEIPT_REVOKED'});
 await assert.rejects(importResearchResult(f),/CLOSURE_RECEIPT_REVOKED/);
});

test('closure parent owns immutable import copies across async verification boundaries',async t=>{
 const f=await setup(t);f.costProfile=structuredClone(f.costProfile);f.tradeTerms=structuredClone(f.tradeTerms);const expected=closureRef(f.packet);let changed=false;
 const service={...f.service,verifyPacket:async args=>{if(!changed){changed=true;f.packet.can_produce_order=true;f.result.observations[0].statement='BUY';f.costProfile.commission_rate='UNSET_REQUIRED';f.tradeTerms.quantity=0;}return f.service.verifyPacket(args);}};
 const out=await importResearchResult({...f,service});assert.deepEqual(out.draft.packet_ref,expected);assert.equal(out.draft.can_produce_order,false);assert.equal(out.cost_estimate.quantity,100);assert.equal(out.draft.observations[0].statement,'Synthetic evidence is visible at its cutoff.');
});

test('closure receipt revoked after real Cost Engine runs cannot accept an imported Draft',async t=>{
 const f=await setup(t),before=await businessCounts(f.db);const service={...f.service,audit:async event=>{const out=await f.service.audit(event);if(event.event_type==='IMPORT_COST_ESTIMATED')await f.service.revokeReceipt({hash:f.receipt.content_hash,now:f.now,reason_code:'CLOSURE_RECEIPT_REVOKED'});return out;}};
 await assert.rejects(importResearchResult({...f,service}),/CLOSURE_RECEIPT_REVOKED/);assert.deepEqual(await businessCounts(f.db),before);
 const{rows}=await f.db.query("SELECT event_type FROM p1a_closure.audit WHERE event_type IN ('IMPORT_COST_ESTIMATED','IMPORT_ACCEPTED','IMPORT_REJECTED') ORDER BY sequence");assert.deepEqual(rows.map(r=>r.event_type),['IMPORT_COST_ESTIMATED','IMPORT_REJECTED']);
});
