import {canonical, sealContract, validateContract} from '../../src/contracts/validate.mjs';
import {hash, sha, seal, refOf, validateP1B, assertPublicPayload, verifyTrustedProof, requireP1B, timestampNs} from './contracts.mjs';

const SOURCE='official:sse-calendar-reference';
const ARTICLE='https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml';
const TERMS='https://www.sse.com.cn/home/legal/';
const PURPOSE='LOCAL_NONCOMMERCIAL_CALENDAR_REFERENCE';
const STRATEGY='CORE_40';
const PERMISSIONS=Object.freeze({local_download:true,local_reference:true,cloud_export:false,redistribution:false,historical_backtest:false,model_research:false,trading:false});
const same=(a,b)=>canonical(a)===canonical(b);
const clone=x=>structuredClone(x);
const digits=h=>h.slice(7);
const fail=(ok,code)=>requireP1B(ok,code);
function keys(x,allowed){fail(x&&Object.getPrototypeOf(x)===Object.prototype&&Object.keys(x).every(k=>allowed.includes(k)),'P1B_ARBITRARY_PAYLOAD');}
function date(value){const valid=typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value+'T00:00:00Z'));fail(valid&&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value,'P1B_CALENDAR_COVERAGE');return value;}
function instant(value){try{return timestampNs(value);}catch{throw new Error('P1B_POINT_IN_TIME_ONLY');}}
function text(bytes){return Buffer.from(bytes).toString('utf8').replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,'').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi,'').replace(/<[^>]*>/g,' ').replace(/&(?:nbsp|#160);/g,' ').replace(/\s+/g,' ').trim();}
function day(year,month,number){return date(`${year}-${String(month).padStart(2,'0')}-${String(number).padStart(2,'0')}`);}
function range(from,to){const out=[];for(let n=Date.parse(from+'T00:00:00Z'),end=Date.parse(to+'T00:00:00Z');n<=end;n+=86400000){fail(out.length<62,'P1B_SOURCE_FACT_MISMATCH');out.push(new Date(n).toISOString().slice(0,10));}return out;}

// This parser is deliberately bound to one reviewed announcement. It does not infer weekdays,
// a complete trading calendar, securities coverage, or an intraday publication time.
function parseCalendar(bytes){
 const html=Buffer.from(bytes).toString('utf8'),body=text(bytes);
 fail(body.includes('上海证券交易所')&&body.includes('中秋节、国庆节休市安排'),'P1B_SOURCE_FACT_MISMATCH');
 const signed=[...body.matchAll(/(20\d{2})年(\d{1,2})月(\d{1,2})日/g)].map(m=>day(m[1],m[2],m[3]));
 fail(signed.length===1,'P1B_SOURCE_FACT_MISMATCH');
 const published=signed[0],year=published.slice(0,4);
 fail(new RegExp(`关于${year}年中秋节、国庆节休市安排`).test(html),'P1B_SOURCE_FACT_MISMATCH');
 const segment=body.match(/一、休市安排：([\s\S]*?)二、/);
 fail(segment,'P1B_SOURCE_FACT_MISMATCH');
 const s=segment[1];
 const closed=[...s.matchAll(/(\d{1,2})月(\d{1,2})日（星期[一二三四五六日]）至(\d{1,2})月(\d{1,2})日（星期[一二三四五六日]）休市/g)];
 const open=[...s.matchAll(/(\d{1,2})月(\d{1,2})日（星期[一二三四五六日]）起照常开市/g)];
 const weekends=s.match(/另外，([\s\S]*?)为周末休市/);
 fail(closed.length===2&&open.length===2&&weekends,'P1B_SOURCE_FACT_MISMATCH');
 const weekend=[...weekends[1].matchAll(/(\d{1,2})月(\d{1,2})日（星期[六日]）/g)];
 fail(weekend.length===2,'P1B_SOURCE_FACT_MISMATCH');
 const closures=closed.flatMap(m=>range(day(year,m[1],m[2]),day(year,m[3],m[4]))).sort();
 const open_dates=open.map(m=>day(year,m[1],m[2])).sort();
 const weekend_closures=weekend.map(m=>day(year,m[1],m[2])).sort();
 fail(new Set([...closures,...open_dates,...weekend_closures]).size===closures.length+open_dates.length+weekend_closures.length,'P1B_SOURCE_FACT_MISMATCH');
 fail(open_dates.every(d=>Date.parse(d+'T00:00:00Z')>Date.parse(published+'T00:00:00Z')),'P1B_SOURCE_FACT_MISMATCH');
 return {closures,open_dates,weekend_closures,publication_date:published};
}
function inspectCapture(c){
 fail(c.source_id===SOURCE&&c.original_uri===ARTICLE&&c.capture_method==='ACTUAL_HTTP_TLS_DOWNLOAD','P1B_SOURCE_UNAPPROVED');
 fail(c.source_version===c.raw_sha256&&sha(c.raw_bytes)===c.raw_sha256,'P1B_SOURCE_HASH_MISMATCH');
 fail(c.terms?.original_uri===TERMS&&c.terms.capture_method==='ACTUAL_HTTP_TLS_DOWNLOAD','P1B_TERMS_UNVERIFIED');
 fail(sha(c.terms.raw_bytes)===c.terms.raw_sha256,'P1B_SOURCE_HASH_MISMATCH');
 const t=text(c.terms.raw_bytes);
 fail(t.includes('任何机构或者个人可基于非商业目的浏览、下载本网站的内容')&&t.includes('未经上海证券交易所书面许可')&&t.includes('不得以向他人出售牟利为目的'),'P1B_TERMS_UNVERIFIED');
 instant(c.retrieved_at);instant(c.terms.retrieved_at);
 const calendar=parseCalendar(c.raw_bytes);
 fail(c.retrieved_at.slice(0,10)>=calendar.publication_date,'P1B_FUTURE_DATA');
 return calendar;
}

/** Trusted parent construction boundary; neither the raw bytes nor the signing capability escape. */
export function createRealAdmissionService({captures,approvedPolicyHashes,authority,codeEpoch}){
 fail(Array.isArray(captures)&&captures.length===1&&approvedPolicyHashes instanceof Set,'P1B_SOURCE_UNAPPROVED');
 fail(typeof codeEpoch==='string'&&codeEpoch.length>0&&typeof authority?.publicKeyDer==='string'&&typeof authority.sign==='function','P1B_CODE_EPOCH_MISMATCH');
 assertPublicPayload({code_epoch:codeEpoch});
 const c=clone(captures[0]);c.raw_bytes=Buffer.from(c.raw_bytes);if(c.terms)c.terms.raw_bytes=Buffer.from(c.terms.raw_bytes);
 const approved=new Set(approvedPolicyHashes),publicKey=authority.publicKeyDer,sign=authority.sign.bind(authority);
 const policies=new Map(),snapshots=new Map(),receipts=new Map(),packets=new Map(),revokedPolicies=new Set(),revokedReceipts=new Set(),events=[];
 const event=(action,reason,refs=[])=>{const core={sequence:events.length+1,action,reason_code:reason,refs:clone(refs),code_epoch:codeEpoch,previous_hash:events.at(-1)?.content_hash??null};assertPublicPayload(core);events.push({...core,content_hash:hash(core)});};
 const signed=(body,name)=>{const object=seal(body);object.proof=clone(sign(object.content_hash));validateP1B(name,object);verifyTrustedProof(object,publicKey);return object;};
 function observationFor(source_id){
  fail(source_id===SOURCE,'P1B_SOURCE_UNAPPROVED');const calendar=inspectCapture(c);
  const core={contract_name:'SourceObservation',contract_version:'1.1.0',object_version:1,trace_id:`p1b-rd:${digits(c.raw_sha256)}`,source_id:SOURCE,source_version:c.source_version,original_uri:ARTICLE,raw_sha256:c.raw_sha256,terms_raw_sha256:c.terms.raw_sha256,scope:'OBSERVED',data_type:'CALENDAR_REFERENCE',clock:{published_date:calendar.publication_date,published_at:null,available_at:c.retrieved_at,retrieved_at:c.retrieved_at,publication_precision:'DATE_ONLY',clock_basis:'RETRIEVAL_OBSERVATION',historical_availability_proven:false},calendar,data_quality_status:'PASS'};
  const o=seal({...core,object_id:`p1b-observation:${digits(hash(core))}`});validateP1B('SourceObservation',o);return clone(o);
 }
 function coverageOf(coverage,calendar){
  keys(coverage,['exchange','symbols','from','to','data_type']);
  fail(coverage.exchange==='SSE'&&Array.isArray(coverage.symbols)&&coverage.symbols.length===0&&coverage.data_type==='CALENDAR_REFERENCE','P1B_SCOPE_MISMATCH');
  date(coverage.from);date(coverage.to);
  const days=[...calendar.closures,...calendar.open_dates,...calendar.weekend_closures].sort();
  fail(coverage.from<=coverage.to&&coverage.from>=days[0]&&coverage.to<=days.at(-1)&&days.some(d=>d>=coverage.from&&d<=coverage.to),'P1B_CALENDAR_COVERAGE');
  return clone(coverage);
 }
 function buildPolicy(args){
  keys(args,['source_id','use_at','coverage']);const {source_id,use_at,coverage}=clone(args),o=observationFor(source_id);
  fail(instant(use_at)>=instant(c.retrieved_at)&&instant(use_at)>=instant(c.terms.retrieved_at),'P1B_FUTURE_DATA');
  const scoped=coverageOf(coverage,o.calendar);
  const core={contract_name:'SourceAdmissionPolicy',contract_version:'1.1.0',object_version:1,trace_id:o.trace_id,strategy_id:STRATEGY,purpose:PURPOSE,coverage:scoped,permissions:clone(PERMISSIONS),production_enabled:false,source_id:SOURCE,source_version:c.source_version,raw_sha256:c.raw_sha256,terms_raw_sha256:c.terms.raw_sha256,terms_uri:TERMS,license_type:'SSE_NONCOMMERCIAL_BROWSE_DOWNLOAD_ONLY',terms_status:'VERIFIED_FOR_NARROW_LOCAL_REFERENCE',validity:'POINT_IN_TIME_ONLY',use_at,code_epoch:codeEpoch};
  const p=seal({...core,object_id:`p1b-policy:${digits(hash(core))}`});validateP1B('SourceAdmissionPolicy',p);return clone(p);
 }
 function policyFor(ref){
  keys(ref,['object_id','object_version','content_hash']);const p=policies.get(ref.content_hash);
  fail(p&&same(refOf(p),ref),'P1B_SOURCE_UNAPPROVED');fail(!revokedPolicies.has(p.content_hash),'P1B_POLICY_REVOKED');
  fail(approved.has(p.content_hash),'P1B_SOURCE_UNAPPROVED');
  const rebuilt=buildPolicy({source_id:p.source_id,use_at:p.use_at,coverage:p.coverage});fail(same(p,rebuilt),'P1B_SOURCE_FACT_MISMATCH');return p;
 }
 function registerPolicy(input){
  const p=clone(input);validateP1B('SourceAdmissionPolicy',p);fail(p.code_epoch===codeEpoch,'P1B_CODE_EPOCH_MISMATCH');
  const derived=buildPolicy({source_id:p.source_id,use_at:p.use_at,coverage:p.coverage});fail(same(p,derived),'P1B_SOURCE_FACT_MISMATCH');fail(approved.has(p.content_hash),'P1B_SOURCE_UNAPPROVED');
  fail(!revokedPolicies.has(p.content_hash),'P1B_POLICY_REVOKED');policies.set(p.content_hash,p);event('POLICY_REGISTERED','P1B_POINT_IN_TIME_ONLY',[refOf(p)]);return refOf(p);
 }
 function createSnapshot(args){
  keys(args,['policy_ref']);const p=policyFor(clone(args.policy_ref)),o=observationFor(p.source_id);
  const data_hash=hash({observation_ref:refOf(o),policy_ref:refOf(p),coverage:p.coverage,purpose:p.purpose,strategy_id:p.strategy_id,code_epoch:codeEpoch});
  const id=`p1b-snapshot:${digits(data_hash)}`;
  const m=sealContract({contract_name:'SnapshotManifest',contract_version:'1.0.0',object_id:id,object_version:1,trace_id:o.trace_id,recorded_at:p.use_at,business_timezone:'Asia/Shanghai',provenance:{event_time:c.retrieved_at,published_at:o.clock.published_date,available_at:c.retrieved_at,retrieved_at:c.retrieved_at,publication_precision:'DATE_ONLY',source_id:SOURCE,source_version:c.source_version,source_hash:c.raw_sha256,visibility_basis:'OBSERVED_AT_TIME'},reason_codes:[],invalidation:{status:'ACTIVE',valid_until:null,invalidated_at:null,conditions:['POINT_IN_TIME_ONLY','SOURCE_OR_TERMS_CHANGED','POLICY_OR_RECEIPT_REVOKED'],reason_code:null},snapshot_id:id,decision_cutoff:p.use_at,data_hash,evidence_refs:[refOf(o)],rules_hash:p.content_hash,scope:'OBSERVED',excluded_metadata_exported:false,frozen_at:p.use_at});
  validateContract('SnapshotManifest',m);assertPublicPayload(m);snapshots.set(m.content_hash,clone(m));event('SNAPSHOT_FROZEN','P1B_POINT_IN_TIME_ONLY',[refOf(m)]);return clone(m);
 }
 function inspectSnapshot(snapshot,p){
  validateContract('SnapshotManifest',snapshot);assertPublicPayload(snapshot);fail(snapshot.scope==='OBSERVED'&&snapshot.provenance.visibility_basis==='OBSERVED_AT_TIME','P1B_SCOPE_MISMATCH');
  fail(snapshot.decision_cutoff===p.use_at&&snapshot.frozen_at===p.use_at,'P1B_POINT_IN_TIME_ONLY');
  fail(instant(snapshot.decision_cutoff)>=instant(c.retrieved_at)&&instant(snapshot.decision_cutoff)>=instant(c.terms.retrieved_at),'P1B_FUTURE_DATA');
  const stored=snapshots.get(snapshot.content_hash);fail(stored&&same(stored,snapshot),'P1B_SOURCE_FACT_MISMATCH');
  const o=observationFor(p.source_id),expected=hash({observation_ref:refOf(o),policy_ref:refOf(p),coverage:p.coverage,purpose:p.purpose,strategy_id:p.strategy_id,code_epoch:codeEpoch});
  fail(snapshot.data_hash===expected&&snapshot.rules_hash===p.content_hash&&same(snapshot.evidence_refs,[refOf(o)]),'P1B_SOURCE_FACT_MISMATCH');return o;
 }
 function admit(args){
  keys(args,['policy_ref','snapshot']);const {policy_ref,snapshot}=clone(args),p=policyFor(policy_ref),o=inspectSnapshot(snapshot,p);
  const core={contract_name:'AdmissionReceipt',contract_version:'1.1.0',object_version:1,trace_id:o.trace_id,strategy_id:STRATEGY,purpose:PURPOSE,coverage:clone(p.coverage),permissions:clone(PERMISSIONS),production_enabled:false,verification:'VERIFIED',admission:'ADMITTED',policy_ref:refOf(p),snapshot_ref:refOf(snapshot),observation_ref:refOf(o),data_hash:snapshot.data_hash,use_at:p.use_at,code_epoch:codeEpoch};
  const r=signed({...core,object_id:`p1b-receipt:${digits(hash(core))}`},'AdmissionReceipt');receipts.set(r.content_hash,clone(r));event('RECEIPT_ADMITTED','P1B_POINT_IN_TIME_ONLY',[refOf(r)]);return clone(r);
 }
 function inspectReceipt(receipt,snapshot,use_at,purpose,strategy_id){
  fail(purpose===PURPOSE&&strategy_id===STRATEGY,'P1B_SCOPE_MISMATCH');validateP1B('AdmissionReceipt',receipt);verifyTrustedProof(receipt,publicKey);
  fail(receipt.code_epoch===codeEpoch,'P1B_CODE_EPOCH_MISMATCH');fail(receipt.purpose===purpose&&receipt.strategy_id===strategy_id,'P1B_SCOPE_MISMATCH');
  fail(use_at===receipt.use_at,'P1B_POINT_IN_TIME_ONLY');fail(!revokedReceipts.has(receipt.content_hash),'P1B_RECEIPT_REVOKED');
  const stored=receipts.get(receipt.content_hash);fail(stored&&same(stored,receipt),'P1B_RECEIPT_UNKNOWN');const p=policyFor(receipt.policy_ref),o=inspectSnapshot(snapshot,p);
  fail(receipt.use_at===p.use_at&&same(receipt.coverage,p.coverage)&&same(receipt.permissions,p.permissions)&&same(receipt.snapshot_ref,refOf(snapshot))&&same(receipt.observation_ref,refOf(o))&&receipt.data_hash===snapshot.data_hash,'P1B_SCOPE_MISMATCH');return {p,o};
 }
 function packetBody(receipt,snapshot,p,o){
  const calendar=clone(o.calendar);for(const k of ['closures','open_dates','weekend_closures'])calendar[k]=calendar[k].filter(d=>d>=p.coverage.from&&d<=p.coverage.to);
  const projection={snapshot_ref:refOf(snapshot),receipt_ref:refOf(receipt),data_hash:snapshot.data_hash,decision_cutoff:p.use_at,evidence:[{observation_ref:refOf(o),source_id:SOURCE,raw_sha256:c.raw_sha256,clock:clone(o.clock),calendar,data_type:'CALENDAR_REFERENCE'}]};
  const core={contract_name:'BrainPacket',contract_version:'1.2.0',object_version:1,trace_id:o.trace_id,strategy_id:STRATEGY,purpose:PURPOSE,coverage:clone(p.coverage),permissions:clone(PERMISSIONS),production_enabled:false,transfer_mode:'LOCAL_REVIEW_ONLY',...projection,projection_hash:hash(projection),can_produce_order:false,contains_account_identity_or_credentials:false};
  return {...core,object_id:`p1b-packet:${digits(hash(core))}`};
 }
 function buildPacket(args){
  keys(args,['receipt','snapshot']);const {receipt,snapshot}=clone(args),{p,o}=inspectReceipt(receipt,snapshot,receipt.use_at,PURPOSE,STRATEGY);
  const packet=signed(packetBody(receipt,snapshot,p,o),'BrainPacket');packets.set(packet.content_hash,clone(packet));event('PACKET_LOCAL_REFERENCE','P1B_POINT_IN_TIME_ONLY',[refOf(packet),refOf(receipt)]);return clone(packet);
 }
 function verifyPacket(args){
  keys(args,['packet','receipt','snapshot','use_at','purpose','strategy_id']);const {packet,receipt,snapshot,use_at,purpose,strategy_id}=clone(args);
  validateP1B('BrainPacket',packet);verifyTrustedProof(packet,publicKey);const {p,o}=inspectReceipt(receipt,snapshot,use_at,purpose,strategy_id);
  fail(same(seal(packetBody(receipt,snapshot,p,o)),seal(packet)),'P1B_PROJECTION_MISMATCH');
  fail(packets.has(packet.content_hash)&&same(packets.get(packet.content_hash),packet),'P1B_RECEIPT_UNKNOWN');
  event('PACKET_VERIFIED','P1B_POINT_IN_TIME_ONLY',[refOf(packet),refOf(receipt)]);return {verification:'VERIFIED',admission:'ADMITTED',scope:'SPECIFIC_CALENDAR_REFERENCE_ONLY',packet_ref:refOf(packet),receipt_ref:refOf(receipt),production_enabled:false};
 }
 function revokeReceipt(content_hash){fail(receipts.has(content_hash),'P1B_RECEIPT_UNKNOWN');revokedReceipts.add(content_hash);event('RECEIPT_REVOKED','P1B_RECEIPT_REVOKED',[refOf(receipts.get(content_hash))]);return true;}
 function revokePolicy(content_hash){fail(policies.has(content_hash),'P1B_SOURCE_UNAPPROVED');revokedPolicies.add(content_hash);event('POLICY_REVOKED','P1B_POLICY_REVOKED',[refOf(policies.get(content_hash))]);return true;}
 function assertTransfer(packet,target){
  const p=clone(packet);validateP1B('BrainPacket',p);verifyTrustedProof(p,publicKey);
  fail(target==='LOCAL_REVIEW_ONLY','P1B_PERMISSION_SCOPE');fail(packets.has(p.content_hash)&&same(p,packets.get(p.content_hash)),'P1B_RECEIPT_UNKNOWN');
  const r=receipts.get(p.receipt_ref.content_hash);fail(r,'P1B_RECEIPT_UNKNOWN');
  fail(!revokedReceipts.has(r.content_hash),'P1B_RECEIPT_REVOKED');policyFor(r.policy_ref);return true;
 }
 function audited(name,operation){return (...args)=>{try{return operation(...args);}catch(error){
  // Rejection records contain no caller object/URI/trace/ref. Only fixed action/reason and parent epoch.
  const reason=typeof error.message==='string'&&error.message.startsWith('P1B_')?error.message:'P1B_SOURCE_FACT_MISMATCH';
  event(name+'_REJECTED',reason,[]);throw error;
 }};}
 // Public methods have only deterministic reference capabilities; no DB, signer, raw path or raw bytes.
 return Object.freeze(Object.fromEntries(Object.entries({observationFor,buildPolicy,registerPolicy,createSnapshot,admit,buildPacket,verifyPacket,revokeReceipt,revokePolicy,assertTransfer}).map(([name,fn])=>[name,audited(name,fn)]).concat([['auditEvents',()=>clone(events)],['trustPublicKeyDer',()=>publicKey]])));
}
