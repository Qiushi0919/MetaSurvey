import {canonical,hashValue,requireThat,timestampMs} from '../contracts/validate.mjs';
import {lineageClosure,verifyDataSnapshot} from '../data/snapshot.mjs';
import {readObject,ref,readRaw} from '../data/core.mjs';
import {assertSanitized,closureRef,projectionHash,validateClosure,verifyClosureSignature} from './contracts.mjs';
import {savePolicy,readPolicy,saveReceipt,readReceipt,assertNotRevoked,revoke,closureAudit,withAdmissionUse} from './store.mjs';
import {projectSanitizedBarEvidence} from './export.mjs';

const PURPOSE='FIXTURE_MANUAL_EXPORT',STRATEGIES=['CORE_40','EVENT_3','RESEARCH_6_18M'];
const unknown=v=>typeof v!=='string'||!v||/(?:^|[\s:._-])(?:UNKNOWN|UNSET_REQUIRED|UNVERIFIED)(?=$|[\s:._-])/i.test(v);
const same=(a,b)=>canonical(a)===canonical(b);
const sorted=a=>[...new Set(a)].sort();
const FACT_KEYS={
 SECURITY:['original_symbol','name','listing_status','list_date','delist_date','board','lot_size','st_status','suspension_status','effective_from','effective_to'],
 STATUS:['canonical_symbol','effective_from','effective_to','st_status','suspension_status'],
 CALENDAR:['days','exchange','coverage_start','coverage_end','session_rule_version'],
 BAR_1D:['canonical_symbol','trade_date','open','high','low','close','preclose','volume','amount_cents','price_basis'],
 CORPORATE_ACTION:['canonical_symbol','action_type','ex_date','effective_date','adjustment_factor','terms'],
 ADJUSTMENT:['canonical_symbol','factor','method','effective_date'],
 FINANCIAL:['canonical_symbol','period','statement_type','revision_kind','values_cents']
};
function scopeRequest(purpose,strategy){requireThat(purpose===PURPOSE,'CLOSURE_PURPOSE_MISMATCH');requireThat(STRATEGIES.includes(strategy),'CLOSURE_NAMESPACE_MISMATCH');}
function checkIssuer(o,issuer){requireThat(same(o.issuer,issuer),'CLOSURE_POLICY_UNTRUSTED');}
function checkScope(o){requireThat(o&&o.fixture_scope==='SYNTHETIC_TEST_ONLY'&&o.production_enabled===false&&['DEV','PAPER'].includes(o.mode),'CLOSURE_SYNTHETIC_SCOPE_ESCALATION');}
function checkWindow(from,to,now,code){requireThat(timestampMs(from)<timestampMs(to)&&timestampMs(now)>=timestampMs(from)&&timestampMs(now)<timestampMs(to),code);}
function mapDataFailure(e){
 if(e.code?.startsWith('CLOSURE_'))throw e;
 if(/AFTER_CUTOFF|AFTER_AVAILABILITY|NOT_EFFECTIVE|FREEZE_BEFORE|AVAILABLE_AFTER|FUTURE/.test(e.code??''))requireThat(false,'CLOSURE_FUTURE_DATA');
 if(/QUARANTINED|NON_TRADEABLE|PUBLICATION_UNKNOWN/.test(e.code??''))requireThat(false,'CLOSURE_DATA_QUARANTINED');
 if(/RAW_|FALSIFIED|SOURCE_POLICY|SOURCE_PAYLOAD|PAYLOAD_HASH|PROVENANCE|CONTENT_HASH|LINEAGE/.test(e.code??''))requireThat(false,'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');
 requireThat(false,'CLOSURE_SNAPSHOT_INVALID');
}

/** Trusted parent facade. Private signer and DB capability remain in this lexical scope. */
export function createAdmissionService({db,authority,approvedPolicyHashes}){
 requireThat(db&&authority?.fixture_scope==='SYNTHETIC_TEST_ONLY'&&approvedPolicyHashes instanceof Set,'CLOSURE_POLICY_UNTRUSTED');
 // Copy all constructor inputs that could later widen trust. The private capability itself is never returned.
 const approved=new Set(approvedPolicyHashes),issuer=structuredClone(authority.issuer),publicKey=Buffer.from(authority.publicKeyDer),signObject=authority.signObject.bind(authority);
 async function policyAt(policy_ref,now){
  requireThat(policy_ref&&typeof policy_ref.object_id==='string'&&Number.isSafeInteger(policy_ref.object_version)&&/^sha256:[a-f0-9]{64}$/.test(policy_ref.content_hash),'CLOSURE_POLICY_UNTRUSTED');
  const policy=await readPolicy(db,policy_ref?.content_hash);
  validateClosure('SourceAdmissionPolicy',policy);checkScope(policy);checkIssuer(policy,issuer);assertSanitized(policy);
  requireThat(approved.has(policy.content_hash)&&same(closureRef(policy),policy_ref),'CLOSURE_POLICY_UNTRUSTED');
  checkWindow(policy.valid_from,policy.valid_until,now,'CLOSURE_RECEIPT_EXPIRED');await assertNotRevoked(db,'POLICY',policy.content_hash,now);
  const{rows}=await db.query("SELECT policy_json FROM p1a_closure.policies WHERE policy_json->>'object_id'=$1",[policy.object_id]);
  requireThat(rows.every(r=>r.policy_json.object_version<=policy.object_version),'CLOSURE_RECEIPT_INVALIDATED');
  return policy;
 }
 async function inspect(snapshot,policy,now){
  requireThat(snapshot?.status==='FROZEN'&&snapshot.manifest&&snapshot.lineage_bundle&&snapshot.snapshot_ref,'CLOSURE_SNAPSHOT_INVALID');
  requireThat(snapshot.manifest.scope==='SYNTHETIC'&&snapshot.lineage_bundle.scope==='SYNTHETIC'&&snapshot.manifest.provenance.visibility_basis==='SYNTHETIC','CLOSURE_SYNTHETIC_SCOPE_ESCALATION');
  requireThat(snapshot.production_execution_enabled===false&&snapshot.lineage_bundle.production_execution_enabled===false,'CLOSURE_PRODUCTION_DISABLED');
  requireThat(timestampMs(now)>=timestampMs(snapshot.manifest.frozen_at)&&timestampMs(now)>=timestampMs(snapshot.manifest.decision_cutoff),'CLOSURE_FUTURE_DATA');
  let closure;
  try{
   // Inspect persisted objects before old validation, so admission reason codes identify this boundary.
   for(const r of snapshot.lineage_bundle.closure_refs){
    const o=await readObject(db,r);requireThat(o.scope==='SYNTHETIC','CLOSURE_REAL_SOURCE_BLOCKED');
    assertSanitized(o.payload);requireThat(o.data_quality_status==='PASS'&&o.tradeability==='OFFLINE_ELIGIBLE','CLOSURE_DATA_QUARANTINED');
    if(o.kind==='SOURCE_OBSERVATION'){
     const s=o.source_policy;requireThat(s?.source_class==='SYNTHETIC','CLOSURE_REAL_SOURCE_BLOCKED');
     requireThat(!unknown(s.license_type)&&s.license_type==='SYNTHETIC_TEST','CLOSURE_LICENSE_UNKNOWN');
     requireThat(!unknown(s.terms_version),'CLOSURE_TERMS_UNVERIFIED');
     requireThat(s.allowed_use?.length===1&&s.allowed_use[0]==='SYNTHETIC_TEST'&&o.clock_basis==='SYNTHETIC'&&s.clock_policy?.type==='SOURCE_FIELD','CLOSURE_SOURCE_NOT_APPROVED');
     // The synthetic observation's event clock is its byte-proven publication clock. Caller event_time cannot refresh old evidence.
     requireThat(o.publication_precision==='SECOND'&&o.event_time===o.published_at,'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');
    }
   }
   await verifyDataSnapshot(db,snapshot);closure=await lineageClosure(db,snapshot.lineage_bundle.root_refs,snapshot.manifest.decision_cutoff);
  }catch(e){mapDataFailure(e);}
  requireThat(snapshot.lineage_bundle.tradeability==='OFFLINE_ELIGIBLE','CLOSURE_DATA_QUARANTINED');
  const observations=closure.filter(o=>o.kind==='SOURCE_OBSERVATION');requireThat(observations.length>0,'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');
  for(const o of observations){
   const children=closure.filter(c=>c.kind!=='SOURCE_OBSERVATION'&&c.lineage_refs?.some(r=>same(r,ref(o))));
   requireThat(children.length>0,'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');
   for(const child of children){
    const required=FACT_KEYS[child.kind];requireThat(required,'CLOSURE_EXPORT_FIELDS_FORBIDDEN');
    const allowed=[...required,...(Object.hasOwn(o.payload,'fixture_kind')?['fixture_kind']:[])];
    requireThat(same(Object.keys(o.payload).sort(),allowed.sort())&&(!Object.hasOwn(o.payload,'fixture_kind')||o.payload.fixture_kind==='SYNTHETIC'),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');
   }
   const binding=policy.source_bindings.find(s=>s.source_id===o.source_id&&s.source_version===o.source_version&&s.source_hash===o.source_hash);
   requireThat(binding&&binding.source_class===o.source_policy.source_class&&binding.license_type===o.source_policy.license_type&&binding.terms_version===o.source_policy.terms_version&&same(binding.allowed_use,o.source_policy.allowed_use)&&binding.raw_hashes.includes(o.raw_sha256),'CLOSURE_SOURCE_NOT_APPROVED');
   await readRaw(db,o); // Original bytes are rechecked on every use, never trusted from a caller assertion.
  }
  requireThat(policy.source_bindings.every(b=>observations.some(o=>o.source_id===b.source_id&&o.source_version===b.source_version&&o.source_hash===b.source_hash)&&b.raw_hashes.every(h=>observations.some(o=>o.raw_sha256===h&&o.source_hash===b.source_hash))),'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');
  const rootRefs=snapshot.lineage_bundle.root_refs,roots=rootRefs.map(r=>closure.find(o=>same(ref(o),r)));
  requireThat(roots.every(o=>o?.kind==='BAR_1D'),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');
  const symbols=sorted(roots.map(o=>o.canonical_symbol)),exchanges=sorted(roots.map(o=>o.canonical_symbol.split(':')[0])),kinds=sorted(closure.map(o=>o.kind)),dates=sorted(roots.map(o=>o.payload.trade_date)),c=policy.coverage;
  requireThat(same(sorted(c.symbols),symbols)&&same(sorted(c.exchanges),exchanges)&&same(sorted(c.object_kinds),kinds)&&c.from_date===dates[0]&&c.to_date===dates.at(-1),'CLOSURE_COVERAGE_INCOMPLETE');
  for(const symbol of symbols){
   const calendar=closure.find(o=>o.kind==='CALENDAR'&&o.payload.exchange===symbol.split(':')[0]);
   requireThat(calendar&&calendar.payload.coverage_start<=c.from_date&&calendar.payload.coverage_end>=c.to_date,'CLOSURE_COVERAGE_INCOMPLETE');
   const days=calendar.payload.days.filter(d=>d.date>=c.from_date&&d.date<=c.to_date);requireThat(days.length>0&&days.every(d=>d.status!=='UNKNOWN'),'CLOSURE_COVERAGE_INCOMPLETE');
   for(const day of days.filter(d=>d.status==='TRADING'))requireThat(roots.some(o=>o.canonical_symbol===symbol&&o.payload.trade_date===day.date),'CLOSURE_COVERAGE_INCOMPLETE');
  }
  for(const o of closure){
   const seconds=policy.freshness_seconds_by_kind[o.kind];requireThat(Number.isSafeInteger(seconds)&&seconds>=0,'CLOSURE_STALE_DATA');
   requireThat(o.event_time&&timestampMs(now)-timestampMs(o.event_time)<=seconds*1000,'CLOSURE_STALE_DATA');
  }
  // Projection refusal is part of admission, rather than a later opportunity to trim dangerous fields.
  const evidence=projectSanitizedBarEvidence(closure,rootRefs);
  return {closure,evidence};
 }
 async function verifyReceipt({receipt,snapshot,purpose,strategy_id,now}){
  receipt=structuredClone(receipt);snapshot=structuredClone(snapshot);
  scopeRequest(purpose,strategy_id);checkScope(receipt);requireThat(receipt.purpose===purpose,'CLOSURE_PURPOSE_MISMATCH');requireThat(receipt.strategy_id===strategy_id,'CLOSURE_NAMESPACE_MISMATCH');
  validateClosure('AdmissionReceipt',receipt);checkIssuer(receipt,issuer);verifyClosureSignature(receipt,publicKey);assertSanitized(receipt);
  const stored=await readReceipt(db,receipt.content_hash);requireThat(same(stored,receipt),'CLOSURE_RECEIPT_INVALIDATED');
  checkWindow(receipt.issued_at,receipt.expires_at,now,'CLOSURE_RECEIPT_EXPIRED');await assertNotRevoked(db,'RECEIPT',receipt.content_hash,now);
  const policy=await policyAt(receipt.policy_ref,now);requireThat(receipt.mode===policy.mode&&timestampMs(receipt.expires_at)<=timestampMs(policy.valid_until),'CLOSURE_RECEIPT_INVALIDATED');
  const {evidence}=await inspect(snapshot,policy,now);
  const b=snapshot.lineage_bundle,m=snapshot.manifest;
  requireThat(same(receipt.snapshot_ref,snapshot.snapshot_ref)&&receipt.data_hash===m.data_hash&&receipt.closure_hash===hashValue(b.closure_refs)&&same(receipt.root_refs,b.root_refs)&&same(receipt.closure_refs,b.closure_refs)&&receipt.decision_cutoff===m.decision_cutoff&&same(receipt.coverage,policy.coverage)&&receipt.feature_version===b.feature_version&&receipt.rules_hash===m.rules_hash,'CLOSURE_RECEIPT_INVALIDATED');
  return {verification:'VERIFIED',admission:'ADMITTED',receipt_ref:closureRef(receipt),policy_ref:closureRef(policy),projection_hash:projectionHash({snapshot_ref:snapshot.snapshot_ref,data_hash:m.data_hash,decision_cutoff:m.decision_cutoff,feature_version:b.feature_version,rules_hash:m.rules_hash,evidence})};
 }
 async function approvedPacket({snapshot,receipt,now}){
  requireThat(receipt,'CLOSURE_IMPORT_INVALID');
  await verifyReceipt({receipt,snapshot,purpose:receipt.purpose,strategy_id:receipt.strategy_id,now});
  const policy=await policyAt(receipt.policy_ref,now),{evidence}=await inspect(snapshot,policy,now),b=snapshot.lineage_bundle,m=snapshot.manifest;
  const core={contract_name:'BrainPacket',contract_version:'1.1.0',object_version:1,fixture_scope:'SYNTHETIC_TEST_ONLY',purpose:PURPOSE,mode:receipt.mode,production_enabled:false,transfer_mode:'MANUAL_EXPORT',strategy_id:receipt.strategy_id,receipt:structuredClone(receipt),snapshot_ref:structuredClone(snapshot.snapshot_ref),decision_cutoff:m.decision_cutoff,data_hash:m.data_hash,feature_version:b.feature_version,rules_hash:m.rules_hash,evidence,contains_account_identity_or_credentials:false,can_produce_order:false,issuer:structuredClone(issuer)};
  return {...core,object_id:`brain:${hashValue(core).slice(7)}`,projection_hash:projectionHash(core)};
 }
 const facade=Object.freeze({
  async registerPolicy(policy){
   policy=structuredClone(policy);
   return withAdmissionUse(db,async()=>{checkScope(policy);validateClosure('SourceAdmissionPolicy',policy);checkIssuer(policy,issuer);assertSanitized(policy);requireThat(approved.has(policy.content_hash),'CLOSURE_POLICY_UNTRUSTED');
   requireThat(timestampMs(policy.valid_from)<timestampMs(policy.valid_until),'CLOSURE_IMPORT_INVALID');
   requireThat(new Set(policy.source_bindings.map(s=>s.source_id+'@'+s.source_version+'@'+s.source_hash)).size===policy.source_bindings.length,'CLOSURE_SOURCE_NOT_APPROVED');
   requireThat(policy.source_bindings.every(s=>!unknown(s.terms_version)),'CLOSURE_TERMS_UNVERIFIED');
   const {rows}=await db.query("SELECT policy_json FROM p1a_closure.policies WHERE policy_json->>'object_id'=$1",[policy.object_id]);
   if(policy.version_chain_parent){const parent=await readPolicy(db,policy.version_chain_parent.content_hash);requireThat(same(closureRef(parent),policy.version_chain_parent)&&parent.object_id===policy.object_id&&parent.object_version+1===policy.object_version&&parent.mode===policy.mode,'CLOSURE_POLICY_UNTRUSTED');}
   else requireThat(policy.object_version===1,'CLOSURE_POLICY_UNTRUSTED');
   requireThat(rows.every(r=>r.policy_json.object_version!==policy.object_version||r.policy_json.content_hash===policy.content_hash),'CLOSURE_DUPLICATE_CONFLICT');
   await savePolicy(db,structuredClone(policy));return closureRef(policy);});
  },
  async admit({snapshot,policy_ref,strategy_id,purpose,now,expires_at}){
   snapshot=structuredClone(snapshot);policy_ref=structuredClone(policy_ref);
   scopeRequest(purpose,strategy_id);const policy=await policyAt(policy_ref,now);await inspect(snapshot,policy,now);
   requireThat(timestampMs(now)<timestampMs(expires_at)&&timestampMs(expires_at)<=timestampMs(policy.valid_until),'CLOSURE_RECEIPT_EXPIRED');
   const m=snapshot.manifest,b=snapshot.lineage_bundle,core={contract_name:'AdmissionReceipt',contract_version:'1.0.0',object_version:1,fixture_scope:'SYNTHETIC_TEST_ONLY',purpose:PURPOSE,mode:policy.mode,production_enabled:false,verification:'VERIFIED',admission:'ADMITTED',strategy_id,policy_ref:structuredClone(policy_ref),snapshot_ref:structuredClone(snapshot.snapshot_ref),data_hash:m.data_hash,closure_hash:hashValue(b.closure_refs),root_refs:structuredClone(b.root_refs),closure_refs:structuredClone(b.closure_refs),decision_cutoff:m.decision_cutoff,coverage:structuredClone(policy.coverage),feature_version:b.feature_version,rules_hash:m.rules_hash,issued_at:now,expires_at,issuer:structuredClone(issuer)};
   const receipt=signObject({...core,object_id:`admission:${hashValue(core).slice(7)}`});validateClosure('AdmissionReceipt',receipt);verifyClosureSignature(receipt,publicKey);assertSanitized(receipt);await saveReceipt(db,receipt);return receipt;
  },
  verifyReceipt,
  async signPacket({snapshot,receipt,now,body}){snapshot=structuredClone(snapshot);receipt=structuredClone(receipt);body=body===undefined?undefined:structuredClone(body);const approvedBody=await approvedPacket({snapshot,receipt,now});if(body!==undefined)requireThat(same(body,approvedBody),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');const packet=signObject(approvedBody);validateClosure('BrainPacket',packet);assertSanitized(packet);return packet;},
  async verifyPacket({packet,snapshot,purpose,strategy_id,now}){
   packet=structuredClone(packet);snapshot=structuredClone(snapshot);
   scopeRequest(purpose,strategy_id);checkScope(packet);requireThat(packet.purpose===purpose,'CLOSURE_PURPOSE_MISMATCH');requireThat(packet.strategy_id===strategy_id,'CLOSURE_NAMESPACE_MISMATCH');
   validateClosure('BrainPacket',packet);checkIssuer(packet,issuer);verifyClosureSignature(packet,publicKey);assertSanitized(packet);
   requireThat(packet.receipt.strategy_id===strategy_id&&packet.receipt.purpose===purpose,'CLOSURE_NAMESPACE_MISMATCH');
   const expected=await approvedPacket({snapshot,receipt:packet.receipt,now});const{proof,content_hash,...body}=packet;requireThat(same(body,expected),'CLOSURE_HASH_MISMATCH');
   return {verification:'VERIFIED',admission:'ADMITTED',packet_ref:closureRef(packet),receipt_ref:closureRef(packet.receipt),can_produce_order:false};
  },
  async withPacketUse({packet,snapshot,purpose,strategy_id,now,operation}){packet=structuredClone(packet);snapshot=structuredClone(snapshot);requireThat(typeof operation==='function','CLOSURE_IMPORT_INVALID');return withAdmissionUse(db,async()=>{await facade.verifyPacket({packet,snapshot,purpose,strategy_id,now});return operation();});},
  revokeReceipt:({hash,now,reason_code})=>withAdmissionUse(db,()=>revoke(db,{kind:'RECEIPT',hash,now,reason_code})),
  revokePolicy:({hash,now,reason_code})=>withAdmissionUse(db,()=>revoke(db,{kind:'POLICY',hash,now,reason_code})),
  audit:input=>closureAudit(db,input),
  trustPublicKeyDer:()=>Buffer.from(publicKey)
 });
 return facade;
}
