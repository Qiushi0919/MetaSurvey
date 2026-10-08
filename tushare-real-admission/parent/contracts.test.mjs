import test from 'node:test';
import assert from 'node:assert/strict';
import {verifyGate} from './verify.mjs';
import {hashValue} from '../../src/contracts/validate.mjs';

const categories=['SECURITY_STATUS','CALENDAR_RULES','RAW_BARS','CORPORATE_ACTIONS','ADJUSTMENT_VERSIONS','FINANCIAL_REVISIONS','ANNOUNCEMENTS','INDUSTRY_MEMBERSHIP'];
const apis=['stock_basic','suspend_d','trade_cal','daily','adj_factor','dividend','fina_indicator','index_member_all'];
const ref={path:'/external/SYNTHETIC_NOT_REAL',sha256:'sha256:'+'a'.repeat(64)};
function fixture() {
  return {gate_version:'1.0.0',report_kind:'P1B_TUSHARE_REAL_ADMISSION_PROBE_GATE',run_id:'SYNTHETIC_NOT_REAL',engineering_gate:'PASS_WITH_CONDITIONS',provider_id:'TUSHARE_MONTHLY_GATEWAY',source_classification:'OWNER_PROVIDED_MONTHLY_GATEWAY',namespace:'CORE_40',purpose:'LOCAL_REAL_RESEARCH_ADMISSION_PROBE',symbols:['603993.SH','600312.SH','603228.SH'],provider_identity_verified:false,license_verified:false,transport_integrity_verified:false,historical_visibility_proven:false,productionGate:false,REAL_DATA_ADMISSION_GATE:'BLOCKED',LOCAL_REAL_RESEARCH_GATE:'BLOCKED',GLOBAL_LOCAL_EXISTING_SSE_GATE:'PARTIAL',P1B_RESEARCH_PILOT_GATE:'BLOCKED',other_gates:Object.fromEntries(['CLOUD_RESEARCH_EXPORT_GATE','HISTORICAL_BACKTEST_GATE','PRODUCTION_DATA_GATE','CLOUD_MODEL','REDISTRIBUTION','SIGNAL_ORDER','BROKER_PRODUCTION'].map(k=>[k,'BLOCKED'])),credential:{lookup_result:'CREDENTIAL_REFERENCE_MISSING',presence:false,storage:'MACOS_KEYCHAIN',rotation_required:false,exposure_risk:'OWNER_ACCEPTED',secret_logged:false,credential_digest_created:false},entitlement_matrix:Object.fromEntries(apis.map(a=>[a,{requests:0,success:0,denied:0,failed:0,rows:0,status:'NOT_QUERIED'}])),categories:Object.fromEntries(categories.map(c=>[c,{probe_status:'NOT_RUN',entitlement_status:'UNKNOWN',provider_identity_status:'UNVERIFIED',license_status:'UNVERIFIED',transport_status:'HTTP_OWNER_EXCEPTION_NOT_INTEGRITY_VERIFIED',raw_integrity:'NOT_CAPTURED',clock_status:'NOT_OBSERVED',coverage_status:'NOT_MEASURED',DQ_status:'NOT_RUN',historical_visibility_proven:false,admission_status:'BLOCKED',observed_rows:0,reason_codes:['PROVIDER_AUTHORIZATION_EVIDENCE_MISSING'],next_action:'Supply independent channel/license evidence'}])),authenticated_requests:0,raw_captures:0,observed_rows:0,raw_inventory:[],probe_report_refs:[ref],source_object_refs:Object.fromEntries(['policy','SourceObservation','ClockEvidence_admitted','StockSnapshot','AdmissionReceipt','BrainPacket','ResearchCard'].map(k=>[k,null])),closed_condition_ids:[],snapshot_b:'PENDING_REAL_DATA_AND_ADMITTED_LINEAGE',code_provenance_ref:{...ref,path:'docs/p1b-real-admission/code-provenance.json'}};
}
function seal(g){const {content_hash,...body}=g;return {...body,content_hash:hashValue(body)};}
test('synthetic blocked no-credential decision is internally coherent',()=>verifyGate(seal(fixture()),{verifyEvidence:false}));
for(const field of ['provider_identity_verified','license_verified','transport_integrity_verified','historical_visibility_proven','productionGate'])test(`reject ${field} escalation`,()=>{const g=fixture();g[field]=true;assert.throws(()=>verifyGate(seal(g),{verifyEvidence:false}));});
for(const field of ['REAL_DATA_ADMISSION_GATE','LOCAL_REAL_RESEARCH_GATE','P1B_RESEARCH_PILOT_GATE'])test(`reject ${field} escalation`,()=>{const g=fixture();g[field]='PASS_FOR_EXACT_SCOPE';assert.throws(()=>verifyGate(seal(g),{verifyEvidence:false}));});
for(const [name,mutate] of [
 ['wrong strategy',g=>g.namespace='EVENT_3'],
 ['expanded securities',g=>g.symbols.push('000001.SZ')],
 ['unknown gateway relabel',g=>g.source_classification='OFFICIAL_TUSHARE_ENDPOINT'],
 ['Receipt issuance',g=>g.source_object_refs.AdmissionReceipt='receipt:fake'],
 ['condition closed without evidence',g=>g.closed_condition_ids=['C15']],
 ['cloud purpose escalation',g=>g.purpose='CLOUD_RESEARCH'],
 ['Model capability',g=>g.other_gates.CLOUD_MODEL='PASS'],
 ['secret digest identifier',g=>g.credential.credential_digest_created=true],
 ['missing credential with request',g=>{g.entitlement_matrix.daily={requests:1,success:1,denied:0,failed:0,rows:0,status:'ACCESS_OBSERVED'};g.authenticated_requests=1;}],
 ['success with no actual query',g=>g.entitlement_matrix.daily.status='ACCESS_OBSERVED'],
 ['rows without success',g=>g.entitlement_matrix.daily.rows=1],
 ['claimed DQ observations without request',g=>g.categories.RAW_BARS.probe_status='SUCCESS_NONEMPTY'],
 ['omitted license blocking reason',g=>g.categories.RAW_BARS.reason_codes=['DQ_PASS']],
 ['category admitted',g=>g.categories.RAW_BARS.admission_status='ADMITTED'],
 ['raw inventory double use',g=>{g.raw_inventory=[ref,ref];g.raw_captures=2;}],
 ['credential tuple contradiction',g=>g.credential.presence=true],
])test(`reject ${name}`,()=>{const g=fixture();mutate(g);assert.throws(()=>verifyGate(seal(g),{verifyEvidence:false}));});
test('reject content mutation without reseal',()=>{const g=seal(fixture());g.run_id='MUTATED';assert.throws(()=>verifyGate(g,{verifyEvidence:false}),/HASH/);});
test('synthetic fixture paths cannot be accepted as real evidence',()=>assert.throws(()=>verifyGate(seal(fixture())),/EVIDENCE_PATH/));
