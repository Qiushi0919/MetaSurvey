import fs from 'node:fs/promises';
import path from 'node:path';
import {hash,sha,canonical,seal,refOf,validate,requireSlice,makeAuthority,verifyProof,timestampNs,assertPublic} from './contracts.mjs';
import {normalizeCapture} from './providers.mjs';

export const SECURITIES=Object.freeze(['SSE:603993','SSE:600312','SSE:603228']);
export const CATEGORIES=Object.freeze(['SECURITY_STATUS','CALENDAR_RULES','RAW_BARS_1D','CORPORATE_ACTIONS','ADJUSTMENT_VERSIONS','FINANCIAL_REVISIONS','ANNOUNCEMENTS','INDUSTRY_MEMBERSHIP']);
const PURPOSE='LOCAL_CURRENT_OBSERVED_REFERENCE';
const permissions=()=>({local_reference:true,cloud_export:false,raw_export:false,redistribution:false,historical_backtest:false,production:false});
const equal=(a,b)=>canonical(a)===canonical(b);
const copy=x=>structuredClone(x);
const exact=(x,keys)=>x&&Object.getPrototypeOf(x)===Object.prototype&&equal(Object.keys(x).sort(),[...keys].sort());
const base=(name,version,id)=>({contract_name:name,contract_version:version,object_id:id,object_version:1,trace_id:id});
const ns=timestampNs;
const liveCollectors=new WeakSet();

// Trusted parent collector capability. The consumer never receives this object,
// a raw handle, authority private key, raw path or filesystem read function.
export function createCollector({specs,archiveDirectory=null,fixture=false}={}){
 requireSlice(Array.isArray(specs)&&specs.length>0,'SLICE_SCOPE_MISMATCH');
 const approved=new Map(specs.map(s=>[hash(s),copy(s)])),records=new WeakMap(),authority=makeAuthority();
 function approvedSpec(spec){
  requireSlice(approved.has(hash(spec))&&equal(approved.get(hash(spec)),spec),'SLICE_SCOPE_MISMATCH');
  requireSlice(exact(spec,['id','source_id','product','data_type','symbols','uri']),'SLICE_SCOPE_MISMATCH');
  requireSlice(spec.symbols.every(x=>SECURITIES.includes(x))&&new Set(spec.symbols).size===spec.symbols.length,'SLICE_SCOPE_MISMATCH');
  const u=new URL(spec.uri);requireSlice(u.protocol==='https:'&&['www.sse.com.cn','query.sse.com.cn','static.sse.com.cn'].includes(u.hostname)&&!u.username&&!u.password&&(!u.port||u.port==='443'),'SLICE_SCOPE_MISMATCH');
  return copy(spec);
 }
 async function retain(spec,bytes,retrieved_at,started_at,real){
  const raw=Buffer.from(bytes),raw_sha256=sha(raw);
  const record=seal({spec:copy(spec),raw_sha256,retrieved_at,started_at,scope:real?'CURRENT_OBSERVED':'SYNTHETIC_TEST_ONLY',collector_version:'1.0.0'});
  record.proof=authority.sign(record.content_hash);
  const handle=Object.freeze({capture_id:record.content_hash});
  let rawFile=null;
  if(archiveDirectory){await fs.mkdir(archiveDirectory,{recursive:true});rawFile=path.join(archiveDirectory,record.content_hash.slice(7)+'.raw');await fs.writeFile(rawFile,raw,{flag:'wx'});await fs.writeFile(rawFile+'.json',JSON.stringify({...record,capture_public_key_der:authority.publicKeyDer},null,2)+'\n',{flag:'wx'});}
  records.set(handle,{record:copy(record),raw,rawFile});return handle;
 }
 async function open(handle){const entry=records.get(handle);requireSlice(entry,'SLICE_CAPTURE_UNTRUSTED');verifyProof(entry.record,authority.publicKeyDer);requireSlice(sha(entry.raw)===entry.record.raw_sha256,'SLICE_RAW_MUTATION');if(entry.rawFile)requireSlice(sha(await fs.readFile(entry.rawFile))===entry.record.raw_sha256,'SLICE_RAW_MUTATION');return {record:copy(entry.record),bytes:Buffer.from(entry.raw)};}
 const collector=Object.freeze({
  async fetch(spec){requireSlice(!fixture,'SLICE_CAPTURE_UNTRUSTED');spec=approvedSpec(spec);const started_at=new Date().toISOString();
   const response=await fetch(spec.uri,{redirect:'error',signal:AbortSignal.timeout(25000),headers:{'User-Agent':'AshareLocalReference/1.0','Referer':'https://www.sse.com.cn/'}});
   requireSlice(response.ok&&response.url===spec.uri,'SLICE_CAPTURE_UNTRUSTED');const chunks=[];let count=0;
   for await(const b of response.body){count+=b.byteLength;requireSlice(count<=3*1024*1024,'SLICE_DQ_FAILED');chunks.push(Buffer.from(b));}
   // Completion clock is generated here, never accepted from API caller/provider.
   const retrieved_at=new Date().toISOString();return retain(spec,Buffer.concat(chunks),retrieved_at,started_at,true);
  },
  async fixtureCapture({spec,bytes,retrieved_at}){requireSlice(fixture,'SLICE_CAPTURE_UNTRUSTED');spec=approvedSpec(spec);ns(retrieved_at);return retain(spec,bytes,retrieved_at,retrieved_at,false);},
  open, publicKeyDer:authority.publicKeyDer,
  async manifest(handles){return Promise.all(handles.map(async h=>(await open(h)).record));}
 });
 if(!fixture)liveCollectors.add(collector);
 return collector;
}

export function validateClock(clock,use_at){
 validate('ClockEvidence',clock);const available=ns(clock.available_at),retrieved=ns(clock.retrieved_at),observed=ns(clock.observation_event_at),cutoff=ns(use_at);
 requireSlice(available===retrieved&&observed===retrieved,'SLICE_CLOCK_INVALID');
 requireSlice(retrieved<=cutoff,'SLICE_FUTURE_DATA');
 if(clock.published_at)requireSlice(ns(clock.published_at)<=retrieved&&ns(clock.published_at)<=cutoff,'SLICE_FUTURE_DATA');
 if(clock.published_precision==='MINUTE')requireSlice(/:\d{2}:00(?:\.0+)?(?:Z|[+-]\d{2}:\d{2})$/.test(clock.published_at),'SLICE_CLOCK_INVALID');
 if(clock.published_date){const date=new Date(Number(retrieved/1000000n)+8*3600000).toISOString().slice(0,10);requireSlice(clock.published_date<=date,'SLICE_FUTURE_DATA');}
 requireSlice(!clock.historical_visibility_proven,'HISTORICAL_VISIBILITY_UNPROVEN');
}

export function createAdmissionService({collector,normalize,termsHandle,approvedPolicyHashes=[],codeEpoch}={}){
 requireSlice(liveCollectors.has(collector)&&normalize===normalizeCapture&&typeof codeEpoch==='string'&&codeEpoch.length>0,'SLICE_CAPTURE_UNTRUSTED');
 const approved=new Set(approvedPolicyHashes),observations=new Map(),policies=new Map(),snapshots=new Map(),receipts=new Map(),revokedPolicies=new Set(),revokedReceipts=new Set(),authority=makeAuthority();
 const lookup=(map,ref)=>{const x=map.get(ref?.content_hash);requireSlice(x&&equal(refOf(x.object),ref),'SLICE_REF_INVALIDATED');return x;};
 async function terms(){const t=await collector.open(termsHandle);requireSlice(t.record.scope==='CURRENT_OBSERVED'&&t.record.spec.uri==='https://www.sse.com.cn/home/legal/','SLICE_TERMS_UNPROVEN');
  const text=t.bytes.toString('utf8').replace(/<[^>]+>/g,'').replace(/\s/g,'');requireSlice(text.includes('非商业目的')&&/浏览(?:和|、)?下载/.test(text),'SLICE_TERMS_UNPROVEN');return t;
 }
 async function sourceCheck(entry){const original=await collector.open(entry.handle);requireSlice(equal(original.record,entry.record),'SLICE_CAPTURE_UNTRUSTED');const normalized=normalize({spec:original.record.spec,bytes:original.bytes});requireSlice(hash(normalized)===entry.normalizedHash,'SLICE_PROJECTION_MISMATCH');return original;}
 async function checkPolicy(ref,use_at){const p=lookup(policies,ref);requireSlice(!revokedPolicies.has(ref.content_hash),'SLICE_POLICY_REVOKED');requireSlice(p.object.code_epoch===codeEpoch&&p.object.use_at===use_at,'SLICE_REF_INVALIDATED');const o=lookup(observations,p.object.observation_ref);await sourceCheck(o);validateClock(o.object.clock,use_at);const t=await terms();requireSlice(t.record.content_hash===p.object.terms_capture_hash&&t.record.raw_sha256===p.object.terms_raw_sha256,'SLICE_TERMS_UNPROVEN');requireSlice(ns(t.record.retrieved_at)<=ns(use_at),'SLICE_FUTURE_DATA');return p.object;}
 function policyBody(o,t,use_at){return {...base('SourceAdmissionPolicy','2.0.0','policy:'+hash({o:refOf(o),t:t.record.content_hash,use_at,codeEpoch}).slice(7)),source_id:o.source_id,product:o.product,data_type:o.data_type,observation_ref:refOf(o),terms_capture_hash:t.record.content_hash,terms_raw_sha256:t.record.raw_sha256,entitlement_basis:'CAPTURED_SSE_WEBSITE_NONCOMMERCIAL_REFERENCE_ONLY',purpose:PURPOSE,namespace:'CORE_40',coverage:o.coverage,clock_contract_version:'1.0.0',code_epoch:codeEpoch,use_at,permissions:permissions(),projection:'REFERENCE_FACTS_ONLY',historical_visibility_proven:false,production_enabled:false};}
 const facade=Object.freeze({
  publicKeyDer:authority.publicKeyDer,
  async observe(handle){const {record,bytes}=await collector.open(handle);requireSlice(record.scope==='CURRENT_OBSERVED','SLICE_CAPTURE_UNTRUSTED');
   const normalized=normalize({spec:record.spec,bytes});
   requireSlice(exact(normalized,['published_date','published_at','published_precision','event_time','event_date','business_effective_at','effective_from','effective_to','facts','coverage']),'SLICE_DQ_FAILED');
   requireSlice(record.spec.source_id==='official:sse-disclosure-reference'||record.spec.source_id==='official:sse-calendar-reference-v2','SLICE_SCOPE_MISMATCH');
   requireSlice(['ANNOUNCEMENTS','CALENDAR_RULES'].includes(record.spec.data_type),'SLICE_ENTITLEMENT_UNKNOWN');
   const clock=seal({...base('ClockEvidence','1.0.0','clock:'+record.content_hash.slice(7)),business_timezone:'Asia/Shanghai',scope:'CURRENT_OBSERVED',event_time:normalized.event_time,event_date:normalized.event_date,business_effective_at:normalized.business_effective_at,published_at:normalized.published_at,published_date:normalized.published_date,published_precision:normalized.published_precision,available_at:record.retrieved_at,retrieved_at:record.retrieved_at,observation_event_at:record.retrieved_at,effective_from:normalized.effective_from,effective_to:normalized.effective_to,availability_basis:'ACTUAL_RETRIEVAL_BOUNDARY',historical_visibility_proven:false});
   validateClock(clock,record.retrieved_at);
   const facts=copy(normalized.facts);facts.forEach(assertPublic);
   requireSlice(facts.every(f=>f.symbol===null||record.spec.symbols.includes(f.symbol)),'SLICE_SCOPE_MISMATCH');
   const coverage=normalized.coverage;requireSlice(equal(coverage.symbols,record.spec.symbols)&&coverage.complete===false,'SLICE_COVERAGE_INCOMPLETE');
   requireSlice(coverage.from<=coverage.to&&facts.every(f=>f.date===null||(f.date>=coverage.from&&f.date<=coverage.to)),'SLICE_COVERAGE_INCOMPLETE');
   requireSlice(record.spec.data_type==='ANNOUNCEMENTS'?facts.every(f=>f.kind==='DOCUMENT_REFERENCE'&&f.symbol!==null):facts.every(f=>['CALENDAR_CLOSED','CALENDAR_OPEN','SESSION_RULE'].includes(f.kind)&&f.symbol===null),'SLICE_PRODUCT_MISMATCH');
   const object=seal({...base('SourceObservation','2.0.0','observation:'+record.content_hash.slice(7)),source_id:record.spec.source_id,product:record.spec.product,source_version:record.raw_sha256,original_uri:record.spec.uri,raw_sha256:record.raw_sha256,capture_attestation_hash:record.content_hash,data_type:record.spec.data_type,scope:'CURRENT_OBSERVED',clock,facts,fact_hashes:facts.map(hash),coverage,data_quality_status:'PASS',normalized_hash:hash(normalized)});
   validate('SourceObservation',object);observations.set(object.content_hash,{object:copy(object),handle,record:copy(record),normalizedHash:hash(normalized)});return copy(object);
  },
  async policyFor(observation,use_at){observation=copy(observation);validate('SourceObservation',observation);const entry=lookup(observations,refOf(observation));requireSlice(equal(entry.object,observation),'SLICE_REF_INVALIDATED');await sourceCheck(entry);validateClock(observation.clock,use_at);const t=await terms();requireSlice(ns(t.record.retrieved_at)<=ns(use_at),'SLICE_FUTURE_DATA');const policy=seal(policyBody(observation,t,use_at));validate('SourceAdmissionPolicy',policy);return policy;},
  async registerPolicy(policy){policy=copy(policy);validate('SourceAdmissionPolicy',policy);requireSlice(approved.has(policy.content_hash),'SLICE_POLICY_UNKNOWN');const o=lookup(observations,policy.observation_ref);await sourceCheck(o);const t=await terms();requireSlice(equal(policy,seal(policyBody(o.object,t,policy.use_at))),'SLICE_SCOPE_MISMATCH');validateClock(o.object.clock,policy.use_at);requireSlice(ns(t.record.retrieved_at)<=ns(policy.use_at),'SLICE_FUTURE_DATA');policies.set(policy.content_hash,{object:copy(policy)});return refOf(policy);},
  // Approval is parent-owned. To avoid consumer self-approval, create a fresh facade
  // with final approved hashes; no public addApproval method exists.
  async snapshot({observation_refs,policy_refs,use_at}){
   observation_refs=copy(observation_refs);policy_refs=copy(policy_refs);
   requireSlice(Array.isArray(observation_refs)&&observation_refs.length===policy_refs?.length&&observation_refs.length>0,'SLICE_COVERAGE_INCOMPLETE');
   requireSlice(new Set(observation_refs.map(r=>r.content_hash)).size===observation_refs.length,'SLICE_SCOPE_MISMATCH');
   const objects=[];for(let i=0;i<observation_refs.length;i++){const o=lookup(observations,observation_refs[i]).object,p=await checkPolicy(policy_refs[i],use_at);requireSlice(equal(p.observation_ref,observation_refs[i]),'SLICE_SCOPE_MISMATCH');objects.push(o);}
   const factHashes=objects.flatMap(o=>o.fact_hashes),facts=objects.flatMap(o=>o.facts),date=new Date(Number(ns(use_at)/1000000n)+8*3600000).toISOString().slice(0,10);
   const closed=facts.some(f=>f.kind==='CALENDAR_CLOSED'&&f.date===date),open=facts.some(f=>f.kind==='CALENDAR_OPEN'&&f.date===date);requireSlice(!(closed&&open),'SLICE_DQ_FAILED');
   const category_status=Object.fromEntries(CATEGORIES.map(c=>[c,objects.some(o=>o.data_type===c)?'PARTIAL':'BLOCKED']));
   const object=seal({...base('StockSnapshot','1.0.0','snapshot:'+hash({observation_refs,policy_refs,use_at}).slice(7)),scope:'CURRENT_OBSERVED',namespace:'CORE_40',purpose:PURPOSE,decision_cutoff:use_at,observation_refs:copy(observation_refs),policy_refs:copy(policy_refs),source_hashes:objects.map(o=>o.raw_sha256),fact_hashes:factHashes,data_hash:hash({observation_refs,policy_refs,factHashes}),category_status,market_state:closed?'CLOSED':open?'OPEN':'UNKNOWN',latest_trading_session:null,live_price:null,trade_trigger:false,tradeable:false,historical_visibility_proven:false,completion:'PARTIAL_RESEARCH_ONLY',production_enabled:false});validate('StockSnapshot',object);snapshots.set(object.content_hash,{object:copy(object)});return copy(object);
  },
  async admit(snapshot){snapshot=copy(snapshot);validate('StockSnapshot',snapshot);requireSlice(equal(lookup(snapshots,refOf(snapshot)).object,snapshot),'SLICE_REF_INVALIDATED');for(const p of snapshot.policy_refs)await checkPolicy(p,snapshot.decision_cutoff);
   const object=seal({...base('AdmissionReceipt','2.0.0','receipt:'+snapshot.content_hash.slice(7)),snapshot_ref:refOf(snapshot),observation_refs:snapshot.observation_refs,policy_refs:snapshot.policy_refs,namespace:'CORE_40',purpose:PURPOSE,use_at:snapshot.decision_cutoff,code_epoch:codeEpoch,permissions:permissions(),admission:'ADMITTED_EXACT_REFERENCE_SCOPE',historical_visibility_proven:false,production_enabled:false});object.proof=authority.sign(object.content_hash);validate('AdmissionReceipt',object);receipts.set(object.content_hash,{object:copy(object)});return copy(object);
  },
  async packet(snapshot,receipt){snapshot=copy(snapshot);receipt=copy(receipt);await facade.verifyReceipt(snapshot,receipt,receipt.use_at);const projection=snapshot.observation_refs.flatMap(r=>lookup(observations,r).object.facts);const object=seal({...base('BrainPacket','2.0.0','packet:'+hash({s:refOf(snapshot),r:refOf(receipt),projection}).slice(7)),snapshot_ref:refOf(snapshot),receipt_ref:refOf(receipt),namespace:'CORE_40',purpose:PURPOSE,decision_cutoff:snapshot.decision_cutoff,transfer_mode:'LOCAL_REVIEW_ONLY',projection,projection_hash:hash(projection),category_status:snapshot.category_status,market_state:snapshot.market_state,latest_trading_session:snapshot.latest_trading_session,live_price:null,trade_trigger:false,tradeable:false,can_produce_order:false,cloud_export_allowed:false,historical_visibility_proven:false,production_enabled:false});object.proof=authority.sign(object.content_hash);validate('BrainPacket',object);return copy(object);},
  async verifyReceipt(snapshot,receipt,use_at){snapshot=copy(snapshot);receipt=copy(receipt);validate('StockSnapshot',snapshot);validate('AdmissionReceipt',receipt);verifyProof(receipt,authority.publicKeyDer);const stored=receipts.get(receipt.content_hash);requireSlice(stored&&equal(stored.object,receipt),'SLICE_RECEIPT_UNKNOWN');requireSlice(!revokedReceipts.has(receipt.content_hash),'SLICE_RECEIPT_REVOKED');requireSlice(equal(lookup(snapshots,refOf(snapshot)).object,snapshot)&&equal(receipt.snapshot_ref,refOf(snapshot))&&receipt.use_at===use_at&&snapshot.decision_cutoff===use_at&&receipt.code_epoch===codeEpoch,'SLICE_REF_INVALIDATED');for(const p of receipt.policy_refs)await checkPolicy(p,use_at);return true;},
  async verifyPacket({packet,snapshot,receipt,use_at,purpose=PURPOSE,namespace='CORE_40',mode='CURRENT_OBSERVED'}){packet=copy(packet);snapshot=copy(snapshot);receipt=copy(receipt);requireSlice(mode==='CURRENT_OBSERVED','HISTORICAL_VISIBILITY_UNPROVEN');requireSlice(purpose===PURPOSE&&namespace==='CORE_40','SLICE_PERMISSION_DENIED');validate('BrainPacket',packet);verifyProof(packet,authority.publicKeyDer);await facade.verifyReceipt(snapshot,receipt,use_at);const expected=await facade.packet(snapshot,receipt);requireSlice(equal(packet,expected),'SLICE_PROJECTION_MISMATCH');return true;},
  async transfer(context,target){context=copy(context);await facade.verifyPacket(context);requireSlice(target==='LOCAL_REVIEW_ONLY','SLICE_PERMISSION_DENIED');return copy(context.packet);},
  revokeReceipt(h){requireSlice(receipts.has(h),'SLICE_RECEIPT_UNKNOWN');revokedReceipts.add(h);},
  revokePolicy(h){requireSlice(policies.has(h),'SLICE_POLICY_UNKNOWN');revokedPolicies.add(h);}
 });
 return facade;
}

export function compareSnapshots(a,b,{featureDependencies=[]}={}){
 validate('StockSnapshot',a);validate('StockSnapshot',b);requireSlice(a.scope===b.scope,'SLICE_SCOPE_MISMATCH');
 const old=new Set(a.fact_hashes),next=new Set(b.fact_hashes),removed=[...old].filter(x=>!next.has(x)),added=[...next].filter(x=>!old.has(x));
 return {scope:a.scope,snapshot_changed:a.content_hash!==b.content_hash,source_bytes_changed:!equal(a.source_hashes,b.source_hashes),removed_fact_hashes:removed,added_fact_hashes:added,unchanged_fact_hashes:[...old].filter(x=>next.has(x)),invalidated_feature_refs:featureDependencies.filter(f=>f.fact_hashes.some(h=>removed.includes(h))).map(f=>f.feature_ref),old_packet_invalidated:a.content_hash!==b.content_hash,real_post_holiday_proof:false};
}
