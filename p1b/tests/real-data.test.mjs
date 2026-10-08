import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRealAdmissionService} from '../src/real-data.mjs';
import {makeDevelopmentAuthority,seal,hash,refOf,sha,timestampNs,validateP1B} from '../src/contracts.mjs';
import {sealContract} from '../../src/contracts/validate.mjs';

// Real small original TLS captures, not invented provider data or a simulated historical clock.
const dir=new URL('./fixtures/real-reference/',import.meta.url);
const manifest=JSON.parse(fs.readFileSync(new URL('capture-manifest.json',dir),'utf8'));
function captures(){
 const calendar=manifest.items.find(x=>x.id==='sse-calendar'),terms=manifest.items.find(x=>x.id==='sse-terms');
 return [{source_id:'official:sse-calendar-reference',source_version:calendar.raw_sha256,original_uri:calendar.original_uri,raw_bytes:fs.readFileSync(new URL(calendar.filename,dir)),raw_sha256:calendar.raw_sha256,retrieved_at:calendar.retrieved_at,capture_method:'ACTUAL_HTTP_TLS_DOWNLOAD',terms:{original_uri:terms.original_uri,raw_bytes:fs.readFileSync(new URL(terms.filename,dir)),raw_sha256:terms.raw_sha256,retrieved_at:terms.retrieved_at,capture_method:'ACTUAL_HTTP_TLS_DOWNLOAD'}}];
}
const coverage={exchange:'SSE',symbols:[],from:'2026-09-20',to:'2026-10-10',data_type:'CALENDAR_REFERENCE'};
function make({input=captures(),authority=makeDevelopmentAuthority(),codeEpoch='P1B_RD_TEST_CODE_EPOCH'}={}){
 const preliminary=createRealAdmissionService({captures:input,approvedPolicyHashes:new Set(),authority,codeEpoch});
 const use_at=input[0].retrieved_at,policy=preliminary.buildPolicy({source_id:input[0].source_id,use_at,coverage});
 const approvedPolicyHashes=new Set([policy.content_hash]);
 const service=createRealAdmissionService({captures:input,approvedPolicyHashes,authority,codeEpoch});
 const policy_ref=service.registerPolicy(policy),snapshot=service.createSnapshot({policy_ref}),receipt=service.admit({policy_ref,snapshot}),packet=service.buildPacket({receipt,snapshot});
 const request={packet,receipt,snapshot,use_at,purpose:policy.purpose,strategy_id:policy.strategy_id};
 return {service,authority,input,policy,snapshot,receipt,packet,request,approvedPolicyHashes};
}
const check=(f,code)=>assert.throws(f,e=>e.message===code);
function resign(x,authority){const o=seal(x);o.proof=authority.sign(o.content_hash);return o;}

test('REAL_PUBLIC_CAPTURE_TEST_REFERENCE: original byte/terms chain yields local-only observed calendar snapshot, receipt and sanitized packet',()=>{
 const f=make(),o=f.service.observationFor('official:sse-calendar-reference');
 assert.equal(manifest.acquisition,'ACTUAL_HTTP_TLS_DOWNLOAD');assert.equal(sha(f.input[0].raw_bytes),manifest.items.find(x=>x.id==='sse-calendar').raw_sha256);
 assert.equal(o.clock.published_date,'2026-09-17');assert.equal(o.clock.published_at,null);assert.equal(o.clock.publication_precision,'DATE_ONLY');
 assert.equal(o.clock.available_at,f.input[0].retrieved_at);assert.equal(o.clock.historical_availability_proven,false);
 assert.deepEqual(o.calendar.open_dates,['2026-09-28','2026-10-08']);assert.deepEqual(o.calendar.weekend_closures,['2026-09-20','2026-10-10']);
 assert.deepEqual(o.calendar.closures,['2026-09-25','2026-09-26','2026-09-27','2026-10-01','2026-10-02','2026-10-03','2026-10-04','2026-10-05','2026-10-06','2026-10-07']);
 assert.equal(f.snapshot.scope,'OBSERVED');assert.equal(f.snapshot.provenance.published_at,'2026-09-17');
 assert.equal(f.service.verifyPacket(f.request).admission,'ADMITTED');assert.equal(f.packet.transfer_mode,'LOCAL_REVIEW_ONLY');
 assert.deepEqual(f.packet.coverage.symbols,[]);assert.equal(f.packet.can_produce_order,false);assert.equal(f.packet.production_enabled,false);
 assert.equal(f.service.assertTransfer(f.packet,'LOCAL_REVIEW_ONLY'),true);assert.equal(JSON.stringify(f.packet).includes('raw_bytes'),false);
 assert.equal(JSON.stringify(f.packet).includes('/Users/'),false);assert.equal(f.packet.permissions.cloud_export,false);assert.equal(f.packet.permissions.historical_backtest,false);
});

test('real observation constructor copies bytes, terms, approved set and caller outputs',()=>{
 const f=make();f.input[0].raw_bytes.fill(0);f.input[0].terms.raw_bytes.fill(0);f.input[0].retrieved_at='1900-01-01T00:00:00Z';f.approvedPolicyHashes.clear();
 const o=f.service.observationFor('official:sse-calendar-reference');o.calendar.closures=[];o.clock.available_at='1900-01-01T00:00:00Z';
 assert.equal(f.service.observationFor('official:sse-calendar-reference').calendar.closures.length,10);assert.equal(f.service.verifyPacket(f.request).admission,'ADMITTED');
 const audit=f.service.auditEvents();audit[0].refs[0].content_hash='sha256:'+ '0'.repeat(64);assert.notDeepEqual(audit,f.service.auditEvents());
});

test('raw mutation reaches original byte hash guard',()=>{
 const input=captures();input[0].raw_bytes[0]^=1;
 const s=createRealAdmissionService({captures:input,approvedPolicyHashes:new Set(),authority:makeDevelopmentAuthority(),codeEpoch:'P1B_RD_TEST_CODE_EPOCH'});
 check(()=>s.observationFor(input[0].source_id),'P1B_SOURCE_HASH_MISMATCH');
});

test('terms mutation reaches original terms hash guard',()=>{
 const input=captures();input[0].terms.raw_bytes[0]^=1;
 const s=createRealAdmissionService({captures:input,approvedPolicyHashes:new Set(),authority:makeDevelopmentAuthority(),codeEpoch:'P1B_RD_TEST_CODE_EPOCH'});
 check(()=>s.observationFor(input[0].source_id),'P1B_SOURCE_HASH_MISMATCH');
});

test('self-hashed unknown or missing terms cannot acquire local permission',()=>{
 const input=captures();input[0].terms.raw_bytes=Buffer.from('<html>Public access only; license UNKNOWN.</html>');input[0].terms.raw_sha256=sha(input[0].terms.raw_bytes);
 const s=createRealAdmissionService({captures:input,approvedPolicyHashes:new Set(),authority:makeDevelopmentAuthority(),codeEpoch:'P1B_RD_TEST_CODE_EPOCH'});
 check(()=>s.observationFor(input[0].source_id),'P1B_TERMS_UNVERIFIED');
});

test('wrong original host and unknown source fail source admission, not a code-proof shortcut',()=>{
 const input=captures();input[0].original_uri='https://example.org/calendar';const s=createRealAdmissionService({captures:input,approvedPolicyHashes:new Set(),authority:makeDevelopmentAuthority(),codeEpoch:'P1B_RD_TEST_CODE_EPOCH'});
 check(()=>s.observationFor(input[0].source_id),'P1B_SOURCE_UNAPPROVED');check(()=>s.observationFor('public:market-universe'),'P1B_SOURCE_UNAPPROVED');
});

test('one-microsecond future retrieval and old historical cutoff are blocked',()=>{
 const f=make(),earlier='2026-10-05T10:08:22.746221+00:00';assert.equal(timestampNs(f.input[0].retrieved_at)-timestampNs(earlier),1000n);
 check(()=>f.service.buildPolicy({source_id:f.policy.source_id,use_at:earlier,coverage}),'P1B_FUTURE_DATA');
 check(()=>f.service.buildPolicy({source_id:f.policy.source_id,use_at:'2026-09-17T00:00:00+08:00',coverage}),'P1B_FUTURE_DATA');
});

test('future terms capture is also required before use',()=>{
 const input=captures();input[0].terms.retrieved_at='2026-10-05T10:08:22.746223+00:00';
 const s=createRealAdmissionService({captures:input,approvedPolicyHashes:new Set(),authority:makeDevelopmentAuthority(),codeEpoch:'P1B_RD_TEST_CODE_EPOCH'});
 check(()=>s.buildPolicy({source_id:input[0].source_id,use_at:input[0].retrieved_at,coverage}),'P1B_FUTURE_DATA');
});

test('DATE_ONLY midnight and fabricated availability cannot alter signed source-derived projection',()=>{
 const f=make(),changed=structuredClone(f.packet);changed.evidence[0].clock.published_at='2026-09-17T00:00:00+08:00';changed.evidence[0].clock.available_at='2026-09-17T00:00:00+08:00';
 changed.projection_hash=hash({snapshot_ref:changed.snapshot_ref,receipt_ref:changed.receipt_ref,data_hash:changed.data_hash,decision_cutoff:changed.decision_cutoff,evidence:changed.evidence});
 const packet=resign(changed,f.authority);validateP1B('BrainPacket',packet);check(()=>f.service.verifyPacket({...f.request,packet}),'P1B_PROJECTION_MISMATCH');
});

test('finite calendar coverage cannot widen to complete year, unknown days or stock symbols',()=>{
 const f=make();check(()=>f.service.buildPolicy({source_id:f.policy.source_id,use_at:f.request.use_at,coverage:{...coverage,from:'2026-01-01',to:'2026-12-31'}}),'P1B_CALENDAR_COVERAGE');
 check(()=>f.service.buildPolicy({source_id:f.policy.source_id,use_at:f.request.use_at,coverage:{...coverage,from:'2026-09-21',to:'2026-09-24'}}),'P1B_CALENDAR_COVERAGE');
 check(()=>f.service.buildPolicy({source_id:f.policy.source_id,use_at:f.request.use_at,coverage:{...coverage,symbols:['SSE:600000']}}),'P1B_SCOPE_MISMATCH');
 assert.equal(f.packet.evidence[0].calendar.open_dates.includes('2026-09-21'),false);
});

test('narrow policy projects only its exact finite source facts',()=>{
 const input=captures(),authority=makeDevelopmentAuthority(),codeEpoch='P1B_RD_TEST_CODE_EPOCH',s0=createRealAdmissionService({captures:input,approvedPolicyHashes:new Set(),authority,codeEpoch});
 const p=s0.buildPolicy({source_id:input[0].source_id,use_at:input[0].retrieved_at,coverage:{...coverage,from:'2026-10-01',to:'2026-10-08'}}),s=createRealAdmissionService({captures:input,approvedPolicyHashes:new Set([p.content_hash]),authority,codeEpoch});
 const pr=s.registerPolicy(p),snapshot=s.createSnapshot({policy_ref:pr}),receipt=s.admit({policy_ref:pr,snapshot}),packet=s.buildPacket({receipt,snapshot});
 assert.deepEqual(packet.evidence[0].calendar.weekend_closures,[]);assert.deepEqual(packet.evidence[0].calendar.open_dates,['2026-10-08']);assert.equal(packet.evidence[0].calendar.closures.length,7);
 assert.equal(s.verifyPacket({packet,receipt,snapshot,use_at:p.use_at,purpose:p.purpose,strategy_id:p.strategy_id}).admission,'ADMITTED');
});

test('caller policy hash does not self-approve and no Set mutation widens constructor approval',()=>{
 const f=make(),s=createRealAdmissionService({captures:captures(),approvedPolicyHashes:new Set(),authority:f.authority,codeEpoch:'P1B_RD_TEST_CODE_EPOCH'});
 check(()=>s.registerPolicy(f.policy),'P1B_SOURCE_UNAPPROVED');
 const changed=f.service.buildPolicy({source_id:f.policy.source_id,use_at:f.request.use_at,coverage:{...coverage,from:'2026-10-01',to:'2026-10-08'}});f.approvedPolicyHashes.add(changed.content_hash);
 check(()=>f.service.registerPolicy(changed),'P1B_SOURCE_UNAPPROVED');
});

test('forged terms binding and code epoch are rejected even with internally consistent hashes',()=>{
 const f=make(),changed=seal({...f.policy,terms_raw_sha256:'sha256:'+'0'.repeat(64)});
 check(()=>f.service.registerPolicy(changed),'P1B_SOURCE_FACT_MISMATCH');
 check(()=>f.service.registerPolicy(seal({...f.policy,code_epoch:'OTHER_APPROVED_CODE'})),'P1B_CODE_EPOCH_MISMATCH');
});

test('forged snapshot, future clock and observation reference cannot replace locally frozen bytes',()=>{
 const f=make(),changed=sealContract({...f.snapshot,evidence_refs:[{...f.snapshot.evidence_refs[0],content_hash:'sha256:'+'0'.repeat(64)}]});
 check(()=>f.service.admit({policy_ref:refOf(f.policy),snapshot:changed}),'P1B_SOURCE_FACT_MISMATCH');
 const future=sealContract({...f.snapshot,decision_cutoff:'2026-10-06T00:00:00Z',frozen_at:'2026-10-06T00:00:00Z'});
 check(()=>f.service.admit({policy_ref:refOf(f.policy),snapshot:future}),'P1B_POINT_IN_TIME_ONLY');
});

test('receipt signature cannot be replaced by caller-supplied identity',()=>{
 const f=make(),attacker=makeDevelopmentAuthority(),receipt=resign(f.receipt,attacker);
 check(()=>f.service.verifyPacket({...f.request,receipt}),'P1B_SIGNATURE_INVALID');
});

test('registered receipt required; replay into another service is refused',()=>{
 const f=make(),s=createRealAdmissionService({captures:captures(),approvedPolicyHashes:new Set([f.policy.content_hash]),authority:f.authority,codeEpoch:'P1B_RD_TEST_CODE_EPOCH'});s.registerPolicy(f.policy);
 check(()=>s.verifyPacket(f.request),'P1B_RECEIPT_UNKNOWN');
});

test('receipt and policy revocation remain active on every packet use and local transfer',()=>{
 const a=make();a.service.revokeReceipt(a.receipt.content_hash);check(()=>a.service.verifyPacket(a.request),'P1B_RECEIPT_REVOKED');check(()=>a.service.assertTransfer(a.packet,'LOCAL_REVIEW_ONLY'),'P1B_RECEIPT_REVOKED');
 const b=make();b.service.revokePolicy(b.policy.content_hash);check(()=>b.service.verifyPacket(b.request),'P1B_POLICY_REVOKED');check(()=>b.service.buildPacket({receipt:b.receipt,snapshot:b.snapshot}),'P1B_POLICY_REVOKED');
});

test('POINT_IN_TIME_ONLY receipt cannot be reused at another cutoff even one microsecond later',()=>{
 const f=make();check(()=>f.service.verifyPacket({...f.request,use_at:'2026-10-05T10:08:22.746223+00:00'}),'P1B_POINT_IN_TIME_ONLY');
});

test('purpose and CORE_40 namespace cannot be promoted to model research or EVENT_3',()=>{
 const f=make();check(()=>f.service.verifyPacket({...f.request,purpose:'CORE_40_HISTORICAL_RESEARCH'}),'P1B_SCOPE_MISMATCH');
 check(()=>f.service.verifyPacket({...f.request,strategy_id:'EVENT_3'}),'P1B_SCOPE_MISMATCH');
});

test('signed modified calendar fact is rejected by actual source-derived projection',()=>{
 const f=make(),changed=structuredClone(f.packet);changed.evidence[0].calendar.closures.shift();
 const packet=resign(changed,f.authority);validateP1B('BrainPacket',packet);check(()=>f.service.verifyPacket({...f.request,packet}),'P1B_PROJECTION_MISMATCH');
});

test('arbitrary packet payload, internal path and extra consumer self-assertion are blocked',()=>{
 const f=make();check(()=>f.service.verifyPacket({...f.request,packet:resign({...f.packet,raw_bytes:'anything'},f.authority)}),'P1B_ARBITRARY_PAYLOAD');
 check(()=>f.service.verifyPacket({...f.request,packet:resign({...f.packet,trace_id:'/Users/qiushi/secret'},f.authority)}),'P1B_SECRET_OR_PATH');
 check(()=>f.service.createSnapshot({policy_ref:refOf(f.policy),source_class:'OFFICIAL',available_at:'1900-01-01T00:00:00Z'}),'P1B_ARBITRARY_PAYLOAD');
});

test('MANUAL_EXPORT API model cloud broker and trading transfer modes stay denied',()=>{
 const f=make();for(const target of ['MANUAL_EXPORT','API','MODEL','CLOUD','REDISTRIBUTION','TRADING','BROKER','PRODUCTION'])check(()=>f.service.assertTransfer(f.packet,target),'P1B_PERMISSION_SCOPE');
 assert.equal(f.service.auditEvents().every(e=>Object.keys(e).every(k=>['sequence','action','reason_code','refs','code_epoch','previous_hash','content_hash'].includes(k))),true);
 const rejected=f.service.auditEvents().filter(e=>e.action.endsWith('_REJECTED'));assert.equal(rejected.length,8);assert.equal(rejected.every(e=>e.reason_code==='P1B_PERMISSION_SCOPE'&&e.refs.length===0),true);
 let previous=null;for(const e of f.service.auditEvents()){const {content_hash,...body}=e;assert.equal(hash(body),content_hash);assert.equal(e.previous_hash,previous);previous=content_hash;}
});
