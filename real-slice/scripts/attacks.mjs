import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createAdmissionService,createCollector} from '../src/core.mjs';
import {captureSpecs,normalizeCapture,tushareAdapter} from '../src/providers.mjs';
import {seal,refOf,canonical} from '../src/contracts.mjs';

// Exercises actual live captures, exact policies, registered objects and signatures.
// Only the test's own external capture may be tampered then restored byte-exactly.
export async function runLiveAttacks(live){
 const {service,stocks,observations,policies,use_at,capture,config}=live,first=stocks[0],base={...first,use_at},results=[];
 const alter=(x,fn)=>{const n=structuredClone(x);fn(n);return seal(n);};
 async function deny(id,fn,boundary='LIVE_REGISTERED_REFERENCE'){try{await fn();results.push({id,status:'FAIL_ACCEPTED',boundary});}catch(e){assert.match(e.code??e.message,/SLICE_|HISTORICAL_VISIBILITY_UNPROVEN/);results.push({id,status:'PASS_FAIL_CLOSED',reason_code:e.code??e.message,boundary});}}
 const observation=(id,fn)=>deny(id,()=>service.policyFor(alter(observations[1],fn),use_at));
 const packet=(id,fn)=>deny(id,()=>service.verifyPacket({...base,packet:alter(first.packet,fn)}));
 await service.verifyPacket(base);
 await observation('fake_available_at',x=>{x.clock=alter(x.clock,c=>c.available_at='2026-09-30T00:00:00Z');});
 await observation('retrieved_at_backdating',x=>{x.clock=alter(x.clock,c=>{c.retrieved_at='2026-09-30T00:00:00Z';c.available_at=c.retrieved_at;c.observation_event_at=c.retrieved_at;});});
 await observation('DATE_ONLY_midnight_fabrication',x=>{x.clock=alter(x.clock,c=>c.published_at=c.published_date+'T00:00:00+08:00');});
 await observation('trade_date_to_available_at',x=>{x.clock=alter(x.clock,c=>c.available_at='2026-09-30T00:00:00+08:00');});
 await observation('provider_update_window_spoof',x=>{x.clock=alter(x.clock,c=>c.available_at='2026-09-30T16:00:00+08:00');});
 await observation('historical_visibility_escalation',x=>{x.clock=alter(x.clock,c=>c.historical_visibility_proven=true);});
 await deny('current_to_historical_PIT',()=>service.verifyPacket({...base,mode:'HISTORICAL_PIT'}));
 await deny('synthetic_to_observed',()=>createAdmissionService({...config,collector:createCollector({specs:captureSpecs(),fixture:true})}));
 await deny('source_product_entitlement_mismatch',()=>service.registerPolicy(alter(policies[1],x=>x.product='SSE_MARKET_FEED')));
 await deny('purpose_escalation',()=>service.verifyPacket({...base,purpose:'PRODUCTION_EXECUTION'}));
 await deny('local_to_cloud_escalation',()=>service.transfer(base,'CLOUD_MODEL'));
 await deny('coverage_widening',()=>service.registerPolicy(alter(policies[1],x=>x.coverage.complete=true)));
 await observation('symbol_widening',x=>{x.coverage.symbols.push('SSE:600000');});
 await observation('date_widening',x=>{x.coverage.from='1990-01-01';});
 await deny('namespace_crossover',()=>service.verifyPacket({...base,namespace:'EVENT_3'}));
 const r=capture.manifest.records[2],rawFile=path.join(path.dirname(capture.manifestPath),r.content_hash.slice(7)+'.raw'),bytes=await fs.readFile(rawFile);
 try{await fs.writeFile(rawFile,Buffer.concat([bytes,Buffer.from('\nmutation')]));await deny('raw_byte_mutation',()=>service.verifyPacket(base));}finally{await fs.writeFile(rawFile,bytes);assert.deepEqual(await fs.readFile(rawFile),bytes);}
 await deny('receipt_reuse_other_stock',()=>service.verifyReceipt(stocks[1].snapshot,first.receipt,use_at));
 await deny('receipt_reuse_other_cutoff',()=>service.verifyPacket({...base,use_at:'2026-10-08T12:00:00Z'}));
 await observation('source_version_mutation',x=>x.source_version='sha256:'+'0'.repeat(64));
 await observation('corporate_action_future_leakage',x=>{x.data_type='CORPORATE_ACTIONS';x.facts[0].future_ex_date='2026-10-08';});
 await observation('adjustment_factor_future_leakage',x=>{x.data_type='ADJUSTMENT_VERSIONS';x.facts[0].factor='1.2';});
 await observation('financial_revision_leakage',x=>{x.data_type='FINANCIAL_REVISIONS';x.facts[0].hidden_revision={published_at:'2026-10-08T12:00:00Z',profit:'100'};});
 await observation('industry_current_label_backfill',x=>{x.data_type='INDUSTRY_MEMBERSHIP';x.facts[0].current_sector='synthetic-current-label';});
 await observation('announcement_revision_loss',x=>{x.facts=x.facts.slice(1);x.fact_hashes=x.fact_hashes.slice(1);});
 await packet('raw_cloud_payload_leakage',x=>{x.projection[0].raw_document='unapproved raw body';});
 await packet('secret_token_leakage',x=>{x.projection[0].token='SYNTHETIC_SECRET_TEST_NOT_REAL_TOKEN';});
 await packet('future_outcome_leakage',x=>{x.projection[0].future_MAE='9.99';});
 await deny('caller_self_signed_capture_restore',()=>capture.collector.open({...capture.handles[2]}));
 await deny('caller_normalizer_replacement',()=>createAdmissionService({...config,normalize:()=>normalizeCapture}));
 await deny('policy_self_approval',()=>service.registerPolicy(alter(policies[1],x=>x.permissions.cloud_export=true)));
 let receiver_calls=0;
 const receiver={verifyReceipt:async()=>{receiver_calls++;return true;},verifyPacket:async()=>{receiver_calls++;return true;},packet:async()=>{receiver_calls++;return first.packet;}};
 const backdated=alter(first.snapshot,x=>x.decision_cutoff='2026-09-30T00:00:00Z');
 await deny('receiver_packet_call_backdating',()=>service.packet.call(receiver,backdated,first.receipt));
 await deny('receiver_packet_apply_backdating',()=>service.packet.apply(receiver,[backdated,first.receipt]));
 await deny('receiver_verify_wrong_cutoff',()=>service.verifyPacket.call(receiver,{...base,use_at:'2026-10-08T12:00:00Z'}));
 await deny('receiver_transfer_unverified_raw_payload',()=>service.transfer.call(receiver,{packet:{raw_document:'SYNTHETIC',token:'SYNTHETIC',production_enabled:true}},'LOCAL_REVIEW_ONLY'));
 await service.verifyPacket.call(receiver,base);assert.equal(receiver_calls,0);
 const pendingInput=structuredClone(base),pendingTransfer=service.transfer(pendingInput,'LOCAL_REVIEW_ONLY');pendingInput.packet.projection[0].raw_document='SYNTHETIC_UNAPPROVED';pendingInput.snapshot.decision_cutoff='2026-09-30T00:00:00Z';
 assert.equal(canonical(await pendingTransfer),canonical(first.packet));results.push({id:'mutation_during_await_transfer',status:'PASS_IMMUTABLE_INPUT',boundary:'LIVE_REGISTERED_REFERENCE'});
 const pendingSnapshot=structuredClone(first.snapshot),pendingPacket=service.packet(pendingSnapshot,first.receipt);pendingSnapshot.decision_cutoff='2026-09-30T00:00:00Z';assert.equal(canonical(await pendingPacket),canonical(first.packet));results.push({id:'mutation_during_await_packet',status:'PASS_IMMUTABLE_INPUT',boundary:'LIVE_REGISTERED_REFERENCE'});
 const pendingRequest={observation_refs:structuredClone(first.snapshot.observation_refs),policy_refs:structuredClone(first.snapshot.policy_refs),use_at},pendingFreeze=service.snapshot(pendingRequest);pendingRequest.observation_refs[0]=refOf(observations[3]);pendingRequest.policy_refs[0]=refOf(policies[3]);assert.equal(canonical(await pendingFreeze),canonical(first.snapshot));results.push({id:'mutation_during_await_snapshot_refs',status:'PASS_IMMUTABLE_INPUT',boundary:'LIVE_REGISTERED_REFERENCE'});
 const adapter=tushareAdapter({entitlement:{verified:true}});await deny('Tushare_forged_entitlement',()=>adapter.fetch({}),'PRE_SECRET_PRE_NETWORK');
 // Revocations intentionally narrow this test issuer; final delivery issuer is separate.
 service.revokeReceipt(first.receipt.content_hash);await deny('receipt_revocation',()=>service.verifyPacket(base));
 await deny('receiver_verify_revoked_receipt',()=>service.verifyPacket.call(receiver,base));assert.equal(receiver_calls,0);
 service.revokePolicy(stocks[1].snapshot.policy_refs.find(p=>p.content_hash===policies[2].content_hash).content_hash);await deny('policy_revocation',()=>service.verifyPacket({...stocks[1],use_at}));
 await service.verifyPacket({...stocks[2],use_at});
 const summary={version:'1.0.0',scope:'ACTUAL_CURRENT_OBSERVED_REFERENCE_AUTHORITY_ATTACKS',decision_cutoff:use_at,code_version:live.evidence.code_version,source_tree_hash:live.evidence.source_tree_hash,actual_live_capture_count:capture.manifest.records.length,cases:results,pass:results.filter(r=>r.status.startsWith('PASS_')).length,fail:results.filter(r=>!r.status.startsWith('PASS_')).length,unmodified_control_after_attacks:'PASS',raw_test_capture_restored_exactly:true,real_financial_action_factor_industry_algorithms_tested:false,limits:'Unsupported category insertion is denied at this reference boundary; missing real revision/action/factor/industry histories are not certified.',model_calls:0,execution_writes:0};
 assert.equal(summary.fail,0);return summary;
}
