import { validateContract,sealContract } from '../contracts/validate.mjs';
import { requireThat,timestampMs,hashValue,canonical,checkObject,readObject,readRaw,ref,derived,putObject,audit,assertFacts,assertPositiveDecimal } from './core.mjs';
import { verifyObservation } from './source.mjs';
import {latestSecurity,latestStatus,parseSecuritySymbol,identityConflictVisible} from './security.mjs';
const factKeys={SECURITY:['name','listing_status','list_date','delist_date','board','lot_size','st_status','suspension_status','effective_from','effective_to'],STATUS:['effective_from','effective_to','st_status','suspension_status'],BAR_1D:['trade_date','open','high','low','close','preclose','volume','amount_cents','price_basis'],CORPORATE_ACTION:['action_type','ex_date','effective_date','adjustment_factor','terms'],ADJUSTMENT:['factor','method','effective_date'],FINANCIAL:['period','statement_type','revision_kind','values_cents'],CALENDAR:['exchange','days','coverage_start','coverage_end','session_rule_version']};

function assertAtCutoff(o,cutoff) {
  requireThat(o.data_quality_status==='PASS'&&o.available_at,'DATA_QUARANTINED');
  requireThat(timestampMs(o.available_at)<=cutoff&&timestampMs(o.retrieved_at)<=cutoff,'LINEAGE_AFTER_CUTOFF');
  requireThat(o.publication_precision!=='UNKNOWN','PUBLICATION_UNKNOWN');
  if(o.publication_precision==='SECOND')requireThat(timestampMs(o.published_at)<=cutoff,'PUBLICATION_AFTER_CUTOFF');
  if(o.kind==='BAR_1D'||o.kind==='FINANCIAL'||o.kind==='ADJUSTMENT')requireThat(timestampMs(o.event_time)<=cutoff,'EVENT_AFTER_CUTOFF');
  if(o.kind==='ADJUSTMENT')requireThat(timestampMs(`${o.payload.effective_date}T00:00:00+08:00`)<=cutoff,'ADJUSTMENT_NOT_EFFECTIVE');
  if(o.kind==='ADJUSTMENT')assertPositiveDecimal(o.payload.factor);
  if(o.kind==='CORPORATE_ACTION'&&o.payload.adjustment_factor!==null)assertPositiveDecimal(o.payload.adjustment_factor);
  if(o.kind==='SECURITY'||o.kind==='STATUS'){requireThat(timestampMs(o.payload.effective_from)<=cutoff&&(!o.payload.effective_to||timestampMs(o.payload.effective_to)>cutoff),'SECURITY_STATUS_NOT_EFFECTIVE');}
  if(['BAR_1D','FINANCIAL','CORPORATE_ACTION','ADJUSTMENT','SECURITY','STATUS'].includes(o.kind))requireThat(o.tradeability==='OFFLINE_ELIGIBLE','DATA_NON_TRADEABLE');
}
export async function lineageClosure(db,rootRefs,decision_cutoff) {
  const cutoff=timestampMs(decision_cutoff),seen=new Map(),visiting=new Set();
  async function walk(r){const key=`${r.object_id}@${r.object_version}`;requireThat(!visiting.has(key),'LINEAGE_CYCLE');if(seen.has(key)){requireThat(seen.get(key).content_hash===r.content_hash,'LINEAGE_REF_HASH_MISMATCH');return seen.get(key);}
    const o=await readObject(db,r);assertAtCutoff(o,cutoff);visiting.add(key);
    requireThat(hashValue(o.payload)===o.payload_sha256,'PAYLOAD_HASH_MISMATCH');await readRaw(db,o);
    if(o.kind==='SOURCE_OBSERVATION')await verifyObservation(db,o);
    else {
      requireThat(Array.isArray(o.lineage_refs)&&o.lineage_refs.length>0,'SOURCE_LINEAGE_REQUIRED');
      const parents=[];for(const p of o.lineage_refs)parents.push(await walk(p));
      const source=parents.find(p=>p.kind==='SOURCE_OBSERVATION');requireThat(source,'SOURCE_LINEAGE_REQUIRED');
      if(o.scope==='SYNTHETIC'&&factKeys[o.kind])assertFacts(source,Object.fromEntries(factKeys[o.kind].map(k=>[k,o.payload[k]])));
      if(o.scope==='SYNTHETIC'&&['BAR_1D','FINANCIAL','CORPORATE_ACTION','ADJUSTMENT','STATUS'].includes(o.kind))assertFacts(source,{canonical_symbol:o.canonical_symbol});
      if(o.kind==='SECURITY'){requireThat(parseSecuritySymbol(source.payload.original_symbol).canonical_symbol===o.canonical_symbol,'SECURITY_SOURCE_IDENTITY_MISMATCH');requireThat(!await identityConflictVisible(db,o.canonical_symbol,decision_cutoff),'SECURITY_IDENTITY_CONFLICT');}
      if(o.kind==='BAR_1D')requireThat(o.event_time===`${o.payload.trade_date}T15:00:00+08:00`,'EVENT_TIME_SOURCE_MISMATCH');
      if(o.kind==='FINANCIAL')requireThat(o.event_time===`${o.payload.period}T00:00:00+08:00`,'EVENT_TIME_SOURCE_MISMATCH');
      if(['ADJUSTMENT','CORPORATE_ACTION'].includes(o.kind))requireThat(o.event_time===`${o.payload.effective_date}T00:00:00+08:00`,'EVENT_TIME_SOURCE_MISMATCH');
      for(const key of ['raw_sha256','source_id','source_version','source_hash','published_at','available_at','retrieved_at','publication_precision','clock_basis','scope'])requireThat(o[key]===source[key],'DERIVED_PROVENANCE_MISMATCH');
      if(['BAR_1D','FINANCIAL','CORPORATE_ACTION','ADJUSTMENT','STATUS'].includes(o.kind)){
        const security=parents.find(p=>p.kind==='SECURITY');requireThat(security&&security.security_id===o.security_id&&security.canonical_symbol===o.canonical_symbol,'SECURITY_LINEAGE_REQUIRED');
        requireThat(security.payload.listing_status==='LISTED'&&security.payload.suspension_status==='TRADING'&&security.payload.st_status!=='UNKNOWN'&&security.payload.lot_size!==null,'SECURITY_NON_TRADEABLE');
        if(o.kind==='BAR_1D'){
          const current=await latestSecurity(db,o.security_id,decision_cutoff);requireThat(current&&current.content_hash===security.content_hash,'SECURITY_VERSION_STALE_AT_CUTOFF');
          const status=await latestStatus(db,o.security_id,decision_cutoff);
          if(status){requireThat(status.data_quality_status==='PASS'&&status.payload.suspension_status==='TRADING'&&status.payload.st_status!=='UNKNOWN','SECURITY_NON_TRADEABLE');requireThat(parents.some(p=>p.kind==='STATUS'&&p.content_hash===status.content_hash),'SECURITY_STATUS_LINEAGE_REQUIRED');}
        }
      }
      if(o.kind==='BAR_1D'){
        const calendar=parents.find(p=>p.kind==='CALENDAR');requireThat(calendar&&calendar.payload.exchange===parents.find(p=>p.kind==='SECURITY').payload.exchange&&calendar.payload.days.some(d=>d.date===o.payload.trade_date&&d.status==='TRADING'),'CALENDAR_LINEAGE_REQUIRED');
        requireThat(canonical(o.payload.calendar_ref)===canonical(ref(calendar))&&canonical(o.payload.security_ref)===canonical(ref(parents.find(p=>p.kind==='SECURITY'))),'BAR_LINEAGE_BINDING_MISMATCH');
        if(o.payload.price_basis==='ADJUSTED'){const adjustment=parents.find(p=>p.kind==='ADJUSTMENT');requireThat(adjustment&&adjustment.security_id===o.security_id&&o.payload.adjustment_version===`${adjustment.object_id}:${adjustment.object_version}`,'ADJUSTMENT_LINEAGE_REQUIRED');requireThat(canonical(o.payload.corporate_action_lineage)===canonical(adjustment.payload.action_refs),'ACTION_LINEAGE_BINDING_MISMATCH');}
        else requireThat(!parents.some(p=>p.kind==='ADJUSTMENT')&&o.payload.adjustment_version==='NOT_APPLICABLE','RAW_ADJUSTED_LINEAGE_MIXED');
      }
      if(o.kind==='ADJUSTMENT'){const actions=parents.filter(p=>p.kind==='CORPORATE_ACTION');requireThat(actions.length>0&&actions.every(a=>a.security_id===o.security_id),'ACTION_LINEAGE_REQUIRED');requireThat(canonical(actions.map(ref))===canonical(o.payload.action_refs),'ACTION_LINEAGE_BINDING_MISMATCH');}
      if(o.kind==='FINANCIAL'&&o.payload.previous_revision){const previous=parents.find(p=>p.kind==='FINANCIAL');requireThat(previous&&canonical(ref(previous))===canonical(o.payload.previous_revision)&&previous.object_id===o.object_id&&previous.object_version<o.object_version,'FINANCIAL_REVISION_LINEAGE_REQUIRED');}
    }
    visiting.delete(key);seen.set(key,o);return o;
  }
  requireThat(Array.isArray(rootRefs)&&rootRefs.length>0,'SNAPSHOT_INPUT_EMPTY');
  for(const root of rootRefs)await walk(root);
  return [...seen.values()].sort((a,b)=>a.object_id.localeCompare(b.object_id)||a.object_version-b.object_version);
}
export async function verifyVisible(db,o,decision_cutoff){return lineageClosure(db,[ref(checkObject(o))],decision_cutoff);}
export function projectDataEnvelope(o) {
  checkObject(o);requireThat(o.data_quality_status==='PASS'&&o.available_at&&o.publication_precision!=='UNKNOWN','DATA_QUARANTINED');
  const map={BAR_1D:'BAR_1D',FINANCIAL:'FINANCIAL',CORPORATE_ACTION:'CORPORATE_ACTION',SECURITY:'SECURITY_STATUS',STATUS:'SECURITY_STATUS'};requireThat(map[o.kind],'DATA_ENVELOPE_KIND_UNSUPPORTED');
  requireThat(o.publication_precision==='SECOND'||o.publication_precision==='NOT_APPLICABLE','DATE_ONLY_PROJECTION_POLICY_REQUIRED');
  const envelope=sealContract({contract_name:'DataEnvelope',contract_version:'1.0.0',object_id:o.object_id,object_version:o.object_version,trace_id:o.trace_id,recorded_at:o.retrieved_at,business_timezone:'Asia/Shanghai',provenance:{event_time:o.event_time,published_at:o.published_at,available_at:o.available_at,retrieved_at:o.retrieved_at,publication_precision:o.publication_precision,source_id:o.source_id,source_version:o.source_version,source_hash:o.source_hash,visibility_basis:o.scope==='SYNTHETIC'?'SYNTHETIC':'OBSERVED_AT_TIME'},reason_codes:[],invalidation:{status:'ACTIVE',valid_until:null,invalidated_at:null,conditions:['SOURCE_REVISION_CHANGE','LINEAGE_MUTATION'],reason_code:null},entity_id:o.security_id,data_kind:map[o.kind],symbols:[o.canonical_symbol],raw_uri:o.raw_uri,raw_hash:o.raw_sha256,payload:o.payload,payload_hash:o.payload_sha256,data_quality:'PASS',adjustment:o.kind==='BAR_1D'?o.payload.price_basis:'NOT_APPLICABLE',adjustment_version:o.kind==='BAR_1D'?(o.payload.price_basis==='RAW'?'RAW':o.payload.adjustment_version):'NOT_APPLICABLE',source_revision:o.source_version});
  return validateContract('DataEnvelope',envelope);
}
export async function freezeDataSnapshot(db,{root_refs,decision_cutoff,feature_version,rules_hash,scope='SYNTHETIC',trace_id,frozen_at}) {
  requireThat(feature_version&&/^sha256:[a-f0-9]{64}$/.test(rules_hash),'SNAPSHOT_VERSION_REQUIRED');requireThat(timestampMs(frozen_at)>=timestampMs(decision_cutoff),'FREEZE_BEFORE_CUTOFF');
  let closure;try{closure=await lineageClosure(db,root_refs,decision_cutoff);}catch(e){await audit(db,'SNAPSHOT_BLOCKED',null,[e.code??e.message]);return {status:'BLOCKED',reason_codes:[e.code??e.message],manifest:null,lineage_bundle:null,production_execution_enabled:false};}
  requireThat(scope==='SYNTHETIC'?closure.every(o=>o.scope==='SYNTHETIC'):['OBSERVED','RECONSTRUCTED'].includes(scope),'SNAPSHOT_SCOPE_MISMATCH');
  const inputs={root_refs:structuredClone(root_refs),closure_refs:closure.map(ref),feature_version,decision_cutoff,rules_hash};
  const data_hash=hashValue(inputs),first=closure[0],snapshotId=`snapshot:${data_hash.slice(7)}`;
  const existing=await db.query("SELECT payload FROM p1a_data_objects WHERE kind='SNAPSHOT' AND object_id=$1 AND object_version=1",[snapshotId]);
  if(existing.rows.length){const previous=checkObject(existing.rows[0].payload);requireThat(previous.payload.lineage_bundle.data_hash===data_hash&&previous.payload.manifest.scope===scope,'SNAPSHOT_IDENTITY_CONFLICT');return {status:'FROZEN',reason_codes:[],...structuredClone(previous.payload),snapshot_ref:ref(previous),production_execution_enabled:false};}
  const manifest=sealContract({contract_name:'SnapshotManifest',contract_version:'1.0.0',object_id:snapshotId,object_version:1,trace_id,recorded_at:frozen_at,business_timezone:'Asia/Shanghai',provenance:{event_time:decision_cutoff,published_at:null,publication_precision:'NOT_APPLICABLE',available_at:frozen_at,retrieved_at:frozen_at,source_id:'p1a:closed-lineage',source_version:feature_version,source_hash:hashValue(inputs),visibility_basis:scope==='SYNTHETIC'?'SYNTHETIC':'DERIVED'},reason_codes:[],invalidation:{status:'ACTIVE',valid_until:null,invalidated_at:null,conditions:['INPUT_VERSION_HASH_CHANGE','CUTOFF_CHANGE','FEATURE_VERSION_CHANGE'],reason_code:null},snapshot_id:data_hash,decision_cutoff,data_hash,evidence_refs:closure.map(ref),rules_hash,scope,excluded_metadata_exported:false,frozen_at});
  validateContract('SnapshotManifest',manifest);
  const lineage_bundle={contract_version:'p1a-data-1.0.0',...inputs,data_hash,manifest_hash:manifest.content_hash,scope,tradeability:closure.every(o=>o.tradeability==='OFFLINE_ELIGIBLE')?'OFFLINE_ELIGIBLE':'NON_TRADEABLE',production_execution_enabled:false};
  const snapshot=await putObject(db,derived(first,{kind:'SNAPSHOT',object_id:manifest.object_id,payload:{manifest,lineage_bundle},trace_id,lineage_refs:closure.map(ref),event_time:decision_cutoff}));
  await audit(db,'SNAPSHOT_FROZEN',snapshot,[]);return {status:'FROZEN',reason_codes:[],manifest,lineage_bundle,snapshot_ref:ref(snapshot),production_execution_enabled:false};
}
export async function verifyDataSnapshot(db,snapshot){
  const persisted=await readObject(db,snapshot.snapshot_ref);requireThat(persisted.kind==='SNAPSHOT','SNAPSHOT_REQUIRED');
  const {manifest,lineage_bundle}=persisted.payload;validateContract('SnapshotManifest',manifest);
  requireThat(canonical(manifest)===canonical(snapshot.manifest)&&canonical(lineage_bundle)===canonical(snapshot.lineage_bundle),'SNAPSHOT_MUTATION');
  const closure=await lineageClosure(db,lineage_bundle.root_refs,manifest.decision_cutoff);
  requireThat(canonical(closure.map(ref))===canonical(lineage_bundle.closure_refs),'LINEAGE_CLOSURE_MISMATCH');
  const inputs={root_refs:lineage_bundle.root_refs,closure_refs:closure.map(ref),feature_version:lineage_bundle.feature_version,decision_cutoff:manifest.decision_cutoff,rules_hash:manifest.rules_hash};
  requireThat(hashValue(inputs)===manifest.data_hash&&manifest.snapshot_id===manifest.data_hash&&lineage_bundle.manifest_hash===manifest.content_hash,'SNAPSHOT_DATA_HASH_MISMATCH');return snapshot;
}
