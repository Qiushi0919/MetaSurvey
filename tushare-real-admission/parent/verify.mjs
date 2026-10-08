import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import Ajv from 'ajv/dist/2020.js';
import formats from 'ajv-formats';
import {hashValue} from '../../src/contracts/validate.mjs';

export const root=path.resolve(import.meta.dirname,'../..');
// Owner-approved external evidence store is independent of the checkout used for validation.
export const archive='/Users/qiushi/投资研究/.p1b-archives/tushare-real-admission-20261005';
const sha=bytes=>'sha256:'+createHash('sha256').update(bytes).digest('hex');
const schema=JSON.parse(fs.readFileSync(path.join(root,'contracts/tushare-real-admission/ProbeGate.schema.json'),'utf8'));
const ajv=new Ajv({strict:false,allErrors:true,coerceTypes:false,useDefaults:false});formats(ajv);
const validate=ajv.compile(schema);

export function deriveEvidence(refs) {
  if(!Array.isArray(refs)||refs.length<1||refs.length>2||new Set(refs.map(r=>r.path)).size!==refs.length)throw new Error('REPORT_INVENTORY_INVALID');
  for(const ref of refs)checkedFile(ref,archive);
  const python=process.env.TUSHARE_DIAGNOSTIC_PYTHON||path.resolve(process.execPath,'../../../python/bin/python3');
  const p=spawnSync(python,['-B',path.join(root,'tushare-real-admission/parent/evidence.py'),...refs.map(r=>r.path)],{encoding:'utf8',maxBuffer:16*1024*1024,env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
  if(p.status!==0)throw new Error('CAPTURE_REPLAY_FAILED');
  const {reports,raw_inventory}=JSON.parse(p.stdout),requests=reports.flatMap(r=>r.requests);
  if(new Set(reports.flatMap(r=>r.requests.slice(0,1).map(q=>q.scope))).size!==reports.length)throw new Error('PROBE_STAGE_REUSED');
  const apis=['stock_basic','suspend_d','trade_cal','daily','adj_factor','dividend','fina_indicator','index_member_all'];
  const entitlement_matrix=Object.fromEntries(apis.map(api=>{
    const rows=requests.filter(r=>r.api_name===api&&r.status!=='BLOCKED_SECRET_NOT_AVAILABLE');
    const success=rows.filter(r=>r.http_status===200&&r.provider_code===0).length;
    const denied=rows.filter(r=>r.provider_msg_classification==='ENTITLEMENT_NOT_GRANTED').length;
    const failed=rows.length-success-denied;
    const status=!rows.length?'NOT_QUERIED':success===rows.length?'ACCESS_OBSERVED':denied===rows.length?'DENIAL_OBSERVED':failed===rows.length?'FAILED':'MIXED';
    return [api,{requests:rows.length,success,denied,failed,rows:rows.filter(r=>r.http_status===200&&r.provider_code===0).reduce((n,r)=>n+(r.row_count??0),0),status}];
  }));
  const categories=Object.fromEntries(['SECURITY_STATUS','CALENDAR_RULES','RAW_BARS','CORPORATE_ACTIONS','ADJUSTMENT_VERSIONS','FINANCIAL_REVISIONS','ANNOUNCEMENTS','INDUSTRY_MEMBERSHIP'].map(category=>{
    const rs=requests.filter(r=>r.category===category&&r.status!=='BLOCKED_SECRET_NOT_AVAILABLE');
    const successes=rs.filter(r=>r.http_status===200&&r.provider_code===0),raw=rs.filter(r=>r.raw_ref),count=rs.reduce((n,r)=>n+(r.row_count??0),0),existing=category==='ANNOUNCEMENTS';
    const nonempty=successes.filter(r=>r.row_count>0).length;
    const validRows=successes.filter(r=>r.row_count>0),dq=validRows.filter(r=>r.dq_status==='PASS').length;
    const cov=rs.filter(r=>r.scope==='COVERAGE');
    const target=['RAW_BARS','ADJUSTMENT_VERSIONS','FINANCIAL_REVISIONS'].includes(category)?cov.length===3&&cov.every(r=>r.coverage?.target_counts_met&&r.dq_status==='PASS'):category==='CALENDAR_RULES'?cov.length===1&&cov[0].coverage?.target_counts_met:false;
    return [category,{probe_status:existing?'EXISTING_SSE_REFERENCE_ONLY':!rs.length?'NOT_RUN':successes.length===rs.length?(nonempty?'SUCCESS_NONEMPTY':'SUCCESS_EMPTY'):!successes.length?'FAILED':'MIXED',entitlement_status:existing?'NOT_PROBED_EXISTING_SSE':!rs.length?'UNKNOWN':successes.length===rs.length?'ACCESS_OBSERVED':rs.every(r=>r.provider_msg_classification==='ENTITLEMENT_NOT_GRANTED')?'DENIAL_OBSERVED':'MIXED',provider_identity_status:'UNVERIFIED',license_status:'UNVERIFIED',transport_status:'HTTP_OWNER_EXCEPTION_NOT_INTEGRITY_VERIFIED',raw_integrity:existing?'EXISTING_SSE_NOT_NEW_CAPTURE':raw.length===rs.length&&raw.length?'PASS':!raw.length?'NOT_CAPTURED':'MIXED',clock_status:existing?'EXISTING_SSE_NOT_NEW_CAPTURE':raw.length?'CURRENT_OBSERVED_ONLY':'NOT_OBSERVED',coverage_status:existing?'EXISTING_SSE_PARTIAL':target?'TARGET_MET_NOT_ADMITTED':rs.length?'PARTIAL':'NOT_MEASURED',DQ_status:existing?'EXISTING_SSE_PARTIAL':!validRows.length?'NOT_RUN':dq===validRows.length?'PASS_FOR_OBSERVED_ROWS':!dq?'FAIL':'MIXED',historical_visibility_proven:false,admission_status:'BLOCKED',observed_rows:count,reason_codes:['PROVIDER_AUTHORIZATION_EVIDENCE_MISSING','TRANSPORT_INTEGRITY_UNVERIFIED',...(existing?['SSE_EXISTING_REFERENCE_ONLY_NO_TUSHARE_ANNOUNCEMENT_PROBE']:[])],next_action:existing?'Preserve existing SSE reference policy; no silent substitution':'Supply independent provider/channel/purpose/license evidence; validate remaining coverage and units'}];
  }));
  const present=reports.every(r=>r.credential_lookup.secret_presence===true);
  return {entitlement_matrix,categories,authenticated_requests:reports.reduce((n,r)=>n+r.network_requests,0),raw_captures:raw_inventory.length,observed_rows:Object.values(entitlement_matrix).reduce((n,e)=>n+e.rows,0),raw_inventory,credential:{lookup_result:present?'FOUND':'CREDENTIAL_REFERENCE_MISSING',presence:present,storage:'MACOS_KEYCHAIN',rotation_required:false,exposure_risk:'OWNER_ACCEPTED',secret_logged:false,credential_digest_created:false}};
}

function checkedFile(ref,base) {
  const p=path.resolve(ref.path);
  if(!p.startsWith(base+path.sep)||fs.realpathSync(p)!==p||!fs.lstatSync(p).isFile())throw new Error('EVIDENCE_PATH_INVALID');
  const bytes=fs.readFileSync(p);
  if(sha(bytes)!==ref.sha256)throw new Error('EVIDENCE_HASH_MISMATCH');
  return bytes;
}
export function verifyGate(g,{verifyEvidence=true}={}) {
  if(!validate(g))throw new Error('PROBE_GATE_SCHEMA_INVALID');
  const {content_hash,...body}=g;
  if(hashValue(body)!==content_hash)throw new Error('PROBE_GATE_HASH_INVALID');
  if((g.credential.lookup_result==='FOUND')!==g.credential.presence)throw new Error('CREDENTIAL_STATE_INCONSISTENT');
  const es=Object.values(g.entitlement_matrix);
  if(es.some(e=>e.requests!==e.success+e.denied+e.failed))throw new Error('ENTITLEMENT_COUNTS_INVALID');
  for(const e of es) {
    const expected=e.requests===0?'NOT_QUERIED':e.success===e.requests?'ACCESS_OBSERVED':e.denied===e.requests?'DENIAL_OBSERVED':e.failed===e.requests?'FAILED':'MIXED';
    if(e.status!==expected||(!e.success&&e.rows!==0))throw new Error('ENTITLEMENT_STATUS_INVALID');
  }
  if(g.authenticated_requests!==es.reduce((n,e)=>n+e.requests,0)||g.observed_rows!==es.reduce((n,e)=>n+e.rows,0))throw new Error('PROBE_TOTALS_INVALID');
  if(!g.credential.presence&&(g.authenticated_requests||g.raw_captures||g.observed_rows))throw new Error('MISSING_CREDENTIAL_CAPTURE');
  if(g.raw_captures!==g.raw_inventory.length||new Set(g.raw_inventory.map(r=>r.path)).size!==g.raw_captures)throw new Error('RAW_INVENTORY_INVALID');
  if(g.raw_captures>g.authenticated_requests)throw new Error('RAW_COUNT_INVALID');
  for(const c of Object.values(g.categories)) {
    if(!c.reason_codes.includes('PROVIDER_AUTHORIZATION_EVIDENCE_MISSING'))throw new Error('PROVIDER_BLOCK_REASON_MISSING');
    if(!g.authenticated_requests&&!['NOT_RUN','EXISTING_SSE_REFERENCE_ONLY'].includes(c.probe_status))throw new Error('CATEGORY_OBSERVATION_SPOOF');
  }
  if(verifyEvidence) {
    for(const ref of [...g.probe_report_refs,...g.raw_inventory])checkedFile(ref,archive);
    if(g.code_provenance_ref.path!=='docs/p1b-real-admission/code-provenance.json')throw new Error('PROVENANCE_PATH_INVALID');
    const provenance=JSON.parse(checkedFile({...g.code_provenance_ref,path:path.join(root,g.code_provenance_ref.path)},path.join(root,'docs/p1b-real-admission')));
    for(const ref of provenance.files)checkedFile({path:path.join(root,ref.path),sha256:ref.sha256},root);
    if(provenance.production_enabled!==false||provenance.approved_policy_count!==0)throw new Error('CODE_AUTHORITY_ESCALATION');
    const derived=deriveEvidence(g.probe_report_refs);
    for(const [key,value] of Object.entries(derived))if(hashValue(g[key])!==hashValue(value))throw new Error('GATE_NOT_BOUND_TO_REPLAYED_EVIDENCE');
  }
  return structuredClone(g);
}
export function verifyRelease() {
  const release=JSON.parse(fs.readFileSync(path.join(root,'contracts/release.tushare-real-admission.json'),'utf8'));
  if(release.schema_version!==6||release.new_migrations.length||release.approved_policy_count!==0||release.production_enabled!==false)throw new Error('RELEASE_AUTHORITY_ESCALATION');
  for(const ref of release.files)checkedFile({path:path.join(root,ref.path),sha256:ref.sha256},root);
  return release;
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===path.resolve(process.argv[1])) {
  verifyRelease();
  const g=verifyGate(JSON.parse(fs.readFileSync(path.join(root,'docs/p1b-real-admission/Gate.json'),'utf8')));
  console.log(JSON.stringify({engineering:g.engineering_gate,source:g.REAL_DATA_ADMISSION_GATE,requests:g.authenticated_requests,rows:g.observed_rows,productionGate:g.productionGate}));
}
