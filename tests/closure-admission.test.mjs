import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,readdir,rm,writeFile,symlink} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {canonical,hashValue,sealContract} from '../src/contracts/validate.mjs';
import {dataDb,createDataFixture,observation} from './fixtures/p1a-data/helpers.mjs';
import {createClosureDataFixture,createClosurePolicy} from './fixtures/closure/data-helpers.mjs';
import {createAdmissionService} from '../src/closure/admission.mjs';
import {buildBrainPacket,writeManualExport} from '../src/closure/export.mjs';
import {createFixtureAuthority,closureRef,sealClosure,projectionHash,verifyClosureSignature,validateClosure} from '../src/closure/contracts.mjs';
import {readObject,ref,putObject,derived} from '../src/data/core.mjs';
import {freezeDataSnapshot,verifyDataSnapshot,lineageClosure} from '../src/data/snapshot.mjs';
import {ingestSourceObservation} from '../src/data/source.mjs';
import {ingestBar} from '../src/data/market.mjs';

const withDb=async run=>{const db=await dataDb();try{return await run(db);}finally{await db.close();}};
const rejects=(promise,code)=>assert.rejects(promise,error=>{assert.equal(error.code,code);return true;});
const args=f=>({snapshot:f.snapshot,receipt:f.receipt,purpose:f.purpose,strategy_id:f.strategy_id,now:f.now});
const admitArgs=(f,snapshot=f.snapshot)=>({snapshot,policy_ref:closureRef(f.policy),purpose:f.purpose,strategy_id:f.strategy_id,now:f.now,expires_at:f.policy.valid_until});

// This helper deliberately simulates an untrusted stored snapshot rather than weakening a production validator.
async function unsafeSnapshot(db,f,root,closureObjects){
 const refs=closureObjects.map(ref).sort((a,b)=>a.object_id.localeCompare(b.object_id)||a.object_version-b.object_version),old=f.snapshot;
 const inputs={root_refs:[ref(root)],closure_refs:refs,feature_version:old.lineage_bundle.feature_version,decision_cutoff:old.manifest.decision_cutoff,rules_hash:hashValue(['explicitly-untrusted-test-snapshot',root.content_hash])},data_hash=hashValue(inputs);
 const manifest=sealContract({...old.manifest,object_id:`snapshot:${data_hash.slice(7)}`,snapshot_id:data_hash,data_hash,evidence_refs:refs,rules_hash:inputs.rules_hash,provenance:{...old.manifest.provenance,source_hash:data_hash}});
 const lineage_bundle={...old.lineage_bundle,...inputs,data_hash,manifest_hash:manifest.content_hash};
 const stored=await putObject(db,derived(root,{kind:'SNAPSHOT',object_id:manifest.object_id,payload:{manifest,lineage_bundle},lineage_refs:refs,event_time:manifest.decision_cutoff}));
 return {status:'FROZEN',reason_codes:[],manifest,lineage_bundle,snapshot_ref:ref(stored),production_execution_enabled:false};
}
async function policyService(db,snapshot,overrides={}){const authority=createFixtureAuthority(),policy=await createClosurePolicy({db,snapshot,authority,overrides}),service=createAdmissionService({db,authority,approvedPolicyHashes:new Set([policy.content_hash])});await service.registerPolicy(policy);return {authority,policy,service};}

test('Closure DA: deterministic admitted fixture exports only a sanitized signed 1.1 packet',async()=>{
 const signatures=[];
 for(let i=0;i<2;i++)await withDb(async db=>{
  const f=await createClosureDataFixture({db}),packet=await buildBrainPacket(f),directory=await mkdtemp(path.join(os.tmpdir(),'closure-export-'));
  try{
   validateClosure('AdmissionReceipt',f.receipt);validateClosure('BrainPacket',packet);verifyClosureSignature(packet,f.service.trustPublicKeyDer());
   assert.equal(packet.receipt.admission,'ADMITTED');assert.equal(packet.evidence.length,1);assert.equal(packet.evidence[0].raw_uri,`sha256-object:${f.bar.raw_sha256.slice(7)}`);
   assert.equal(packet.can_produce_order,false);assert.equal(packet.production_enabled,false);assert.equal(packet.purpose,'FIXTURE_MANUAL_EXPORT');
   assert.equal(packet.data_hash,f.snapshot.manifest.data_hash);assert.notEqual(packet.projection_hash,packet.data_hash);
   const exported=await writeManualExport({...f,packet,directory}),again=await writeManualExport({...f,packet,directory});assert.deepEqual(again,exported);
   const bytes=await readFile(exported.path);assert.equal(bytes.toString(),canonical(packet)+'\n');assert.equal((await readdir(directory)).length,1);
   const{rows}=await db.query('SELECT event_json FROM p1a_closure.audit ORDER BY sequence');assert.equal(rows.length,2);assert.equal(rows[1].event_json.previous_hash,rows[0].event_json.event_hash);
   assert.ok(rows.every(r=>Object.keys(r.event_json).sort().join(',')==='chain_id,event_hash,event_time,event_type,previous_hash,reason_codes,refs,sequence'));
   signatures.push(canonical({policy:f.policy,receipt:f.receipt,packet}));
  }finally{await rm(directory,{recursive:true,force:true});}
 });
 assert.equal(signatures[0],signatures[1]);
});

test('Closure DA: authority and constructor approved hashes cannot be discovered or widened',async()=>withDb(async db=>{
 const f=await createDataFixture(db),authority=createFixtureAuthority(),policy=await createClosurePolicy({db,snapshot:f.snapshot,authority}),approved=new Set(),service=createAdmissionService({db,authority,approvedPolicyHashes:approved});
 approved.add(policy.content_hash);await rejects(service.registerPolicy(policy),'CLOSURE_POLICY_UNTRUSTED');
 assert.equal(service.db,undefined);assert.equal(service.authority,undefined);assert.equal(service.signObject,undefined);assert.equal(service.broker,undefined);assert.ok(Object.isFrozen(service));
 const key=service.trustPublicKeyDer();key.fill(0);assert.notDeepEqual(service.trustPublicKeyDer(),key);
}));

test('Closure DA: original OBSERVED/RECONSTRUCTED freeze counterexample is rejected at admission',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db});
 for(const scope of ['OBSERVED','RECONSTRUCTED']){
  const snapshot=await freezeDataSnapshot(db,{root_refs:[ref(f.bar)],decision_cutoff:f.cutoff,feature_version:'synthetic-counterexample',rules_hash:hashValue(['scope-counterexample',scope]),scope,trace_id:'counterexample-fixture',frozen_at:f.cutoff});
  assert.equal(snapshot.status,'FROZEN');await verifyDataSnapshot(db,snapshot);
  await rejects(f.service.admit(admitArgs(f,snapshot)),'CLOSURE_SYNTHETIC_SCOPE_ESCALATION');
 }
 await rejects(f.service.admit({...admitArgs(f),purpose:'REAL_RESEARCH'}),'CLOSURE_PURPOSE_MISMATCH');
}));

test('Closure DA: unconfigured and real source scope remains blocked independent of caller claims',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),s=structuredClone(f.snapshot);s.lineage_bundle.scope='REAL_RESEARCH';
 await rejects(f.service.admit(admitArgs(f,s)),'CLOSURE_SYNTHETIC_SCOPE_ESCALATION');
 const authority=createFixtureAuthority(),policy=sealClosure({...f.policy,allow_real_data:true});const service=createAdmissionService({db,authority,approvedPolicyHashes:new Set([policy.content_hash])});
 await rejects(service.registerPolicy(policy),'CLOSURE_IMPORT_INVALID');
}));

test('Closure DA: quarantined persisted root is blocked before any export exists',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),bad=await putObject(db,{...f.bar,object_id:'synthetic:quarantined',data_quality_status:'QUARANTINED',tradeability:'NON_TRADEABLE'}),closure=await lineageClosure(db,[ref(f.bar)],f.cutoff),snapshot=await unsafeSnapshot(db,f,bad,[...closure.filter(o=>o.kind!=='BAR_1D'),bad]);
 await rejects(f.service.admit(admitArgs(f,snapshot)),'CLOSURE_DATA_QUARANTINED');
}));

test('Closure DA: UNKNOWN_LICENSE and UNVERIFIED_TERMS cannot pass a well-hashed snapshot',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db});
 for(const [field,value,code] of [['license_type','UNKNOWN_LICENSE','CLOSURE_LICENSE_UNKNOWN'],['terms_version','UNVERIFIED_TERMS','CLOSURE_TERMS_UNVERIFIED']]){
  const source={...f.barObservation.source_policy,[field]:value},payload=f.barObservation.payload,at=f.barObservation.published_at;
  const o=await ingestSourceObservation(db,{source,rawBytes:Buffer.from(JSON.stringify({published_at:at,available_at:at,fact:payload})),object_id:`source:unknown-${field}`,payload,retrieved_at:at,trace_id:'synthetic-negative-policy',clocks:{event_time:at,published_at:at,publication_precision:'SECOND',clock_proof:{type:'SOURCE_FIELD',available_path:'available_at',published_path:'published_at'}}});
  const bar=await ingestBar(db,{observation:o,security:f.security,calendar:f.calendar,...payload,object_id:`synthetic:unknown-${field}`});
  const snapshot=await freezeDataSnapshot(db,{root_refs:[ref(bar)],decision_cutoff:f.cutoff,feature_version:'negative-policy',rules_hash:hashValue(field),trace_id:'negative-policy',frozen_at:f.cutoff});assert.equal(snapshot.status,'FROZEN');await verifyDataSnapshot(db,snapshot);
  await rejects(f.service.admit(admitArgs(f,snapshot)),code);
 }
}));

test('Closure DA: future raw-clock data cannot be exported through a caller-made frozen manifest',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),payload={...f.barObservation.payload,trade_date:'2026-10-08'},at='2026-10-08T15:01:00+08:00';
 const source=await observation(db,{id:'source:future-closure',payload,at}),bar=await ingestBar(db,{observation:source,security:f.security,calendar:f.calendar,...payload,object_id:'synthetic:future-closure'}),base=await lineageClosure(db,[ref(f.bar)],f.cutoff),snapshot=await unsafeSnapshot(db,f,bar,[...base.filter(o=>o.object_id!==f.barObservation.object_id&&o.kind!=='BAR_1D'),source,bar]);
 await rejects(f.service.admit(admitArgs(f,snapshot)),'CLOSURE_FUTURE_DATA');
}));

test('Closure DA: available_at spoof is rejected from original bytes, despite coherent new hashes',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db});
 const spoof=await putObject(db,{...f.barObservation,object_id:'source:spoof-available',available_at:'2026-09-28T15:01:00+08:00'});
 const bar=await putObject(db,derived(spoof,{kind:'BAR_1D',object_id:'synthetic:spoof-available',payload:f.bar.payload,security_id:f.security.security_id,canonical_symbol:f.security.canonical_symbol,lineage_refs:[ref(f.security),ref(f.calendar)],event_time:f.bar.event_time}));
 const closure=await lineageClosure(db,[ref(f.bar)],f.cutoff),snapshot=await unsafeSnapshot(db,f,bar,[...closure.filter(o=>o.object_id!==f.barObservation.object_id&&o.kind!=='BAR_1D'),spoof,bar]);
 await rejects(f.service.admit(admitArgs(f,snapshot)),'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');
}));

test('Closure DA: one-byte raw-store mutation invalidates prior admitted receipt and export',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db});let attackedReads=0;
 const corruptDb={query:async(sql,params)=>{const out=await db.query(sql,params);if(sql.includes("encode(raw_bytes,'hex')")&&params?.[0]===f.bar.raw_sha256){attackedReads++;return {...out,rows:out.rows.map(r=>({...r,hex:Buffer.concat([Buffer.from(r.hex,'hex'),Buffer.from(' ')]).toString('hex')}))};}return out;}};
 const service=createAdmissionService({db:corruptDb,authority:f.authority,approvedPolicyHashes:new Set([f.policy.content_hash])});
 await rejects(service.verifyReceipt(args(f)),'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');assert.ok(attackedReads>0);
 await rejects(buildBrainPacket({...f,service}),'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');
}));

test('Closure DA: explicit per-kind freshness and fulfilled coverage have no permissive defaults',async()=>{
 for(const [override,code] of [
  [{freshness_seconds_by_kind:{SOURCE_OBSERVATION:1,SECURITY:1,CALENDAR:1,BAR_1D:1}},'CLOSURE_STALE_DATA'],
  [{freshness_seconds_by_kind:{BAR_1D:30*86400}},'CLOSURE_STALE_DATA']
 ])await withDb(db=>rejects(createClosureDataFixture({db,policyOverrides:override}),code));
 for(const key of ['symbols','exchanges','from_date','object_kinds'])await withDb(async db=>{
  const f=await createDataFixture(db),authority=createFixtureAuthority(),p=await createClosurePolicy({db,snapshot:f.snapshot,authority}),coverage=structuredClone(p.coverage);
  if(key==='symbols')coverage.symbols.push('SZSE:000001');if(key==='exchanges')coverage.exchanges.push('SZSE');if(key==='from_date')coverage.from_date='2026-09-28';if(key==='object_kinds')coverage.object_kinds=coverage.object_kinds.filter(x=>x!=='CALENDAR');
  const policy=sealClosure({...p,coverage}),service=createAdmissionService({db,authority,approvedPolicyHashes:new Set([policy.content_hash])});await service.registerPolicy(policy);
  await rejects(service.admit({snapshot:f.snapshot,policy_ref:closureRef(policy),purpose:'FIXTURE_MANUAL_EXPORT',strategy_id:'RESEARCH_6_18M',now:f.cutoff,expires_at:policy.valid_until}),'CLOSURE_COVERAGE_INCOMPLETE');
 });
});

test('Closure DA: source-less normalized data cannot satisfy closure admission',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),bad=await putObject(db,{...f.bar,object_id:'synthetic:no-source',lineage_refs:[ref(f.security),ref(f.calendar)]}),closure=await lineageClosure(db,[ref(f.bar)],f.cutoff),snapshot=await unsafeSnapshot(db,f,bad,[...closure.filter(o=>o.kind!=='BAR_1D'),bad]);
 await rejects(f.service.admit(admitArgs(f,snapshot)),'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');
}));

test('Closure DA: source binding requires exact approved raw bytes and terms, not caller assertions',async()=>withDb(async db=>{
 const f=await createDataFixture(db),authority=createFixtureAuthority(),p=await createClosurePolicy({db,snapshot:f.snapshot,authority});
 const policy=sealClosure({...p,source_bindings:p.source_bindings.map(b=>({...b,raw_hashes:[hashValue('unrelated explicit synthetic raw')]}))}),service=createAdmissionService({db,authority,approvedPolicyHashes:new Set([policy.content_hash])});await service.registerPolicy(policy);
 await rejects(service.admit({snapshot:f.snapshot,policy_ref:closureRef(policy),purpose:'FIXTURE_MANUAL_EXPORT',strategy_id:'RESEARCH_6_18M',now:f.cutoff,expires_at:policy.valid_until}),'CLOSURE_SOURCE_NOT_APPROVED');
}));

test('Closure DA: prefixed or suffixed unknown terms markers never count as verified fixture terms',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db});
 for(const terms_version of ['UNVERIFIED_TERMS_v0','unknown:terms_version','synthetic-UNSET_REQUIRED-v1']){
  const policy=sealClosure({...f.policy,object_id:`synthetic:terms-check-${hashValue(terms_version).slice(7)}`,source_bindings:f.policy.source_bindings.map(b=>({...b,terms_version}))}),service=createAdmissionService({db,authority:f.authority,approvedPolicyHashes:new Set([policy.content_hash])});
  await rejects(service.registerPolicy(policy),'CLOSURE_TERMS_UNVERIFIED');
 }
}));

test('Closure DA: receipt is bound to snapshot, namespace, purpose, version and trust root',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db});
 await rejects(f.service.verifyReceipt({...args(f),purpose:'REAL_RESEARCH'}),'CLOSURE_PURPOSE_MISMATCH');
 await rejects(f.service.verifyReceipt({...args(f),strategy_id:'CORE_40'}),'CLOSURE_NAMESPACE_MISMATCH');
 const changed=await freezeDataSnapshot(db,{root_refs:[ref(f.bar)],decision_cutoff:f.cutoff,feature_version:'synthetic-feature-2',rules_hash:f.snapshot.manifest.rules_hash,trace_id:'changed-snapshot',frozen_at:f.cutoff});
 await rejects(f.service.verifyReceipt({...args(f),snapshot:changed}),'CLOSURE_RECEIPT_INVALIDATED');
 const unknown=f.authority.signObject({...f.receipt,object_version:2});await rejects(f.service.verifyReceipt({...args(f),receipt:unknown}),'CLOSURE_RECEIPT_UNKNOWN');
 const other=createFixtureAuthority(Buffer.alloc(32,17)),forged=other.signObject({...f.receipt,issuer:other.issuer});await rejects(f.service.verifyReceipt({...args(f),receipt:forged}),'CLOSURE_POLICY_UNTRUSTED');
 const unsigned={...f.receipt,proof:{algorithm:'ED25519',signature:'A'.repeat(86)+'=='}};await rejects(f.service.verifyReceipt({...args(f),receipt:unsigned}),'CLOSURE_SIGNATURE_INVALID');
}));

test('Closure DA: revocation and half-open expiry invalidate old packets without rewriting seals',async()=>{
 for(const kind of ['RECEIPT','POLICY'])await withDb(async db=>{
  const f=await createClosureDataFixture({db}),packet=await buildBrainPacket(f),directory=await mkdtemp(path.join(os.tmpdir(),'closure-rejected-export-'));
  try{
   await (kind==='RECEIPT'?f.service.revokeReceipt:f.service.revokePolicy)({hash:kind==='RECEIPT'?f.receipt.content_hash:f.policy.content_hash,now:f.now,reason_code:kind==='RECEIPT'?'CLOSURE_RECEIPT_REVOKED':'CLOSURE_POLICY_REVOKED'});
   await rejects(writeManualExport({...f,packet,directory}),kind==='RECEIPT'?'CLOSURE_RECEIPT_REVOKED':'CLOSURE_POLICY_REVOKED');assert.deepEqual(await readdir(directory),[]);
  }finally{await rm(directory,{recursive:true,force:true});}
 });
 await withDb(async db=>{const f=await createClosureDataFixture({db});await rejects(f.service.verifyReceipt({...args(f),now:f.receipt.expires_at}),'CLOSURE_RECEIPT_EXPIRED');await rejects(f.service.verifyReceipt({...args(f),now:'2026-09-30T15:59:59+08:00'}),'CLOSURE_RECEIPT_EXPIRED');});
});

test('Closure DA: registered newer policy requires fresh receipt; old admission does not inherit',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),next=sealClosure({...f.policy,object_version:2,version_chain_parent:closureRef(f.policy)}),service=createAdmissionService({db,authority:f.authority,approvedPolicyHashes:new Set([f.policy.content_hash,next.content_hash])});
 await service.registerPolicy(next);await rejects(service.verifyReceipt(args(f)),'CLOSURE_RECEIPT_INVALIDATED');
 const receipt=await service.admit({...admitArgs(f),policy_ref:closureRef(next)});assert.equal(receipt.policy_ref.object_version,2);assert.notEqual(receipt.content_hash,f.receipt.content_hash);
}));

test('Closure DA: all-signed arbitrary packet evidence still fails source-derived projection comparison',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),packet=await buildBrainPacket(f),changed=structuredClone(packet),envelope=changed.evidence[0];
 envelope.payload.close='11.00';envelope.payload_hash=hashValue(envelope.payload);changed.evidence[0]=sealContract(envelope);changed.projection_hash=projectionHash(changed);
 const signed=f.authority.signObject(changed);validateClosure('BrainPacket',signed);verifyClosureSignature(signed,f.service.trustPublicKeyDer());
 await rejects(f.service.verifyPacket({...args(f),packet:signed}),'CLOSURE_HASH_MISMATCH');
 const{proof,content_hash,...body}=changed;await rejects(f.service.signPacket({...f,body}),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');
}));

test('Closure DA: future MAE/MFE, arbitrary payload, secret and path fields are refused, not trimmed',async()=>{
 for(const extra of [{mae_cents:'1'},{mfe_cents:'1'},{future_return:'1'},{unrequested_numeric_fact:'1'},{raw_path:'/Users/private/raw'},{note:'Bearer synthetic-secret-value'}])await withDb(async db=>{
  const f=await createClosureDataFixture({db}),bad=await putObject(db,{...f.bar,object_id:'synthetic:payload-injection',payload:{...f.bar.payload,...extra},payload_sha256:hashValue({...f.bar.payload,...extra})}),base=await lineageClosure(db,[ref(f.bar)],f.cutoff),snapshot=await unsafeSnapshot(db,f,bad,[...base.filter(o=>o.kind!=='BAR_1D'),bad]);
  const code=extra.note||extra.raw_path?'CLOSURE_SECRET_OR_PATH_LEAKAGE':'CLOSURE_EXPORT_FIELDS_FORBIDDEN';await rejects(f.service.admit(admitArgs(f,snapshot)),code);
 });
});

test('Closure DA: source fact outcome fields cannot hide behind a safe normalized root',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),payload={...f.barObservation.payload,future_mae_cents:'1'},o=await observation(db,{id:'source:outcome-field',payload,at:f.barObservation.published_at}),bar=await ingestBar(db,{observation:o,security:f.security,calendar:f.calendar,...payload,object_id:'synthetic:source-outcome-field'}),snapshot=await freezeDataSnapshot(db,{root_refs:[ref(bar)],decision_cutoff:f.cutoff,feature_version:'synthetic',rules_hash:hashValue('outcome-source'),trace_id:'outcome-source',frozen_at:f.cutoff});
 assert.equal(snapshot.status,'FROZEN');await rejects(f.service.admit(admitArgs(f,snapshot)),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');
}));

test('Closure DA: arbitrary original source fact fields are refused even when not named future or outcome',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),payload={...f.barObservation.payload,next_day_price:'99.00'},o=await observation(db,{id:'source:extra-fact',payload,at:f.barObservation.published_at}),bar=await ingestBar(db,{observation:o,security:f.security,calendar:f.calendar,...payload,object_id:'synthetic:extra-fact'}),snapshot=await freezeDataSnapshot(db,{root_refs:[ref(bar)],decision_cutoff:f.cutoff,feature_version:'synthetic',rules_hash:hashValue('extra-source-fact'),trace_id:'extra-source-fact',frozen_at:f.cutoff});
 assert.equal(snapshot.status,'FROZEN');await verifyDataSnapshot(db,snapshot);assert.equal(Object.hasOwn(bar.payload,'next_day_price'),false);
 const p=await createClosurePolicy({db,snapshot,authority:f.authority,overrides:{object_id:'synthetic:extra-fact-policy'}}),service=createAdmissionService({db,authority:f.authority,approvedPolicyHashes:new Set([p.content_hash])});await service.registerPolicy(p);
 await rejects(service.admit({...admitArgs(f,snapshot),policy_ref:closureRef(p)}),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');
}));

test('Closure DA: signed path/secret or production assertions cannot be written to a manual file',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),packet=await buildBrainPacket(f),directory=await mkdtemp(path.join(os.tmpdir(),'closure-rejected-bytes-'));
 try{
  for(const value of ['file:///Users/private/raw','Bearer synthetic-secret-value']){
   const p=structuredClone(packet);p.evidence[0].raw_uri=value;p.evidence[0]=sealContract(p.evidence[0]);p.projection_hash=projectionHash(p);const signed=f.authority.signObject(p);
   await rejects(writeManualExport({...f,packet:signed,directory}),'CLOSURE_SECRET_OR_PATH_LEAKAGE');assert.deepEqual(await readdir(directory),[]);
  }
  const production={...packet,production_enabled:true};await rejects(writeManualExport({...f,packet:production,directory}),'CLOSURE_SYNTHETIC_SCOPE_ESCALATION');assert.deepEqual(await readdir(directory),[]);
 }finally{await rm(directory,{recursive:true,force:true});}
}));

test('Closure DA: caller mutation during an await cannot swap the serialized packet',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),packet=await buildBrainPacket(f),directory=await mkdtemp(path.join(os.tmpdir(),'closure-copy-boundary-'));
 try{
  const original=canonical(packet),promise=writeManualExport({...f,packet,directory});packet.evidence[0].raw_uri='file:///Users/private/raw';
  const exported=await promise;assert.equal((await readFile(exported.path,'utf8')).trim(),original);
 }finally{await rm(directory,{recursive:true,force:true});}
}));

test('Closure DA: source event_time cannot be caller-refreshed beyond its original publication bytes',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),source=await putObject(db,{...f.barObservation,object_id:'source:caller-refreshed',event_time:f.now}),bar=await putObject(db,derived(source,{kind:'BAR_1D',object_id:'synthetic:caller-refreshed',payload:f.bar.payload,security_id:f.security.security_id,canonical_symbol:f.security.canonical_symbol,lineage_refs:[ref(f.security),ref(f.calendar)],event_time:f.bar.event_time}));
 const snapshot=await freezeDataSnapshot(db,{root_refs:[ref(bar)],decision_cutoff:f.cutoff,feature_version:'synthetic-freshness-attack',rules_hash:hashValue('source-event-spoof'),trace_id:'synthetic-freshness-attack',frozen_at:f.cutoff});assert.equal(snapshot.status,'FROZEN');await verifyDataSnapshot(db,snapshot);
 await rejects(f.service.admit(admitArgs(f,snapshot)),'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');
}));

test('Closure DA: code or schema policy epoch change does not auto-approve an old receipt',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),next=sealClosure({...f.policy,object_id:'synthetic:policy-new-code-and-schema-epoch'}),service=createAdmissionService({db,authority:f.authority,approvedPolicyHashes:new Set([next.content_hash])});
 await service.registerPolicy(next);await rejects(service.verifyReceipt(args(f)),'CLOSURE_POLICY_UNTRUSTED');
 const packet=await buildBrainPacket(f);await rejects(service.verifyPacket({...args(f),packet}),'CLOSURE_POLICY_UNTRUSTED');
 const receipt=await service.admit({...admitArgs(f),policy_ref:closureRef(next)});assert.equal(receipt.policy_ref.object_id,next.object_id);
}));

test('Closure DA: existing export symlink and output directory symlink are refused',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db}),packet=await buildBrainPacket(f),directory=await mkdtemp(path.join(os.tmpdir(),'closure-export-symlink-')),elsewhere=await mkdtemp(path.join(os.tmpdir(),'closure-export-target-'));
 try{
  const target=path.join(elsewhere,'outside.json');await writeFile(target,canonical(packet)+'\n');await symlink(target,path.join(directory,`brain-packet-${packet.content_hash.slice(7)}.json`));
  await rejects(writeManualExport({...f,packet,directory}),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');assert.equal((await readFile(target,'utf8')).trim(),canonical(packet));
  const linked=path.join(directory,'linked-dir');await symlink(elsewhere,linked);await rejects(writeManualExport({...f,packet,directory:linked}),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');assert.deepEqual(await readdir(elsewhere),['outside.json']);
 }finally{await rm(directory,{recursive:true,force:true});await rm(elsewhere,{recursive:true,force:true});}
}));

test('Closure DA: outcome titles in IDs, trace, feature metadata and source metadata cannot escape sanitization',async()=>withDb(async db=>{
 const f=await createClosureDataFixture({db});
 for(const fields of [{object_id:'synthetic:mae:500'},{object_id:'synthetic:trace-attack',trace_id:'synthetic:mfe:500'}]){
  const bar=await putObject(db,{...f.bar,...fields});
  const snapshot=await freezeDataSnapshot(db,{root_refs:[ref(bar)],decision_cutoff:f.cutoff,feature_version:'synthetic-feature-1',rules_hash:hashValue(fields),trace_id:'synthetic-meta-attack',frozen_at:f.cutoff});assert.equal(snapshot.status,'FROZEN');
  await rejects(f.service.admit(admitArgs(f,snapshot)),'CLOSURE_OUTCOME_LEAKAGE');
 }
 const source=await putObject(db,{...f.barObservation,object_id:'source:future_return:500'}),bar=await putObject(db,derived(source,{kind:'BAR_1D',object_id:'synthetic:source-ref-meta',payload:f.bar.payload,security_id:f.security.security_id,canonical_symbol:f.security.canonical_symbol,lineage_refs:[ref(f.security),ref(f.calendar)],event_time:f.bar.event_time}));
 const snapshot=await freezeDataSnapshot(db,{root_refs:[ref(bar)],decision_cutoff:f.cutoff,feature_version:'synthetic-feature-1',rules_hash:hashValue('source-meta-attack'),trace_id:'synthetic-source-meta',frozen_at:f.cutoff});assert.equal(snapshot.status,'FROZEN');
 await rejects(f.service.admit(admitArgs(f,snapshot)),'CLOSURE_OUTCOME_LEAKAGE');
 const featureSnapshot=await freezeDataSnapshot(db,{root_refs:[ref(f.bar)],decision_cutoff:f.cutoff,feature_version:'synthetic:future_return:500',rules_hash:hashValue('feature-meta-attack'),trace_id:'synthetic-feature-meta',frozen_at:f.cutoff});
 await rejects(f.service.admit(admitArgs(f,featureSnapshot)),'CLOSURE_OUTCOME_LEAKAGE');
 const policy=sealClosure({...f.policy,source_bindings:f.policy.source_bindings.map(b=>({...b,source_id:'source:daily_nav:500'}))}),service=createAdmissionService({db,authority:f.authority,approvedPolicyHashes:new Set([policy.content_hash])});await rejects(service.registerPolicy(policy),'CLOSURE_OUTCOME_LEAKAGE');
 const packet=await buildBrainPacket(f),p=structuredClone(packet);p.evidence[0].provenance.source_id='source:future_return:500';p.evidence[0]=sealContract(p.evidence[0]);p.projection_hash=projectionHash(p);
 await rejects(f.service.verifyPacket({...args(f),packet:f.authority.signObject(p)}),'CLOSURE_OUTCOME_LEAKAGE');
}));
