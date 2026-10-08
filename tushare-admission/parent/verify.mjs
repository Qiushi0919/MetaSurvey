import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import Ajv from 'ajv/dist/2020.js';
import formats from 'ajv-formats';
import {createHash} from 'node:crypto';
import {hashValue} from '../../src/contracts/validate.mjs';

export const root=path.resolve(import.meta.dirname,'../..');
const directory=path.join(root,'contracts/tushare-admission');
const schema=JSON.parse(fs.readFileSync(path.join(directory,'AdmissionVerification.schema.json'),'utf8'));
const ajv=new Ajv({strict:false,allErrors:true,coerceTypes:false,useDefaults:false});formats(ajv);
const validate=ajv.compile(schema);
const sha=bytes=>'sha256:'+createHash('sha256').update(bytes).digest('hex');
export function verifyAdmissionVerification(report,{verifyEvidence=true}={}) {
  if(!validate(report))throw new Error('DIAGNOSTIC_SCHEMA_INVALID');
  const {content_hash,...body}=report;
  if(content_hash!==hashValue(body))throw new Error('DIAGNOSTIC_HASH_INVALID');
  if(report.credential_lookup.lookup_from_chat||report.credential_lookup.persisted)throw new Error('DIAGNOSTIC_CREDENTIAL_RULE_VIOLATED');
  if(['BLOCKED_CREDENTIAL_AND_ENTITLEMENT','BLOCKED_PROVIDER_PREREQUISITES'].includes(report.verification_conclusion)) {
    if(report.credential_lookup.presence)throw new Error('DIAGNOSTIC_CREDENTIAL_STATE_INCONSISTENT');
    if(Object.values(report.category_matrix).some(c=>c.authenticated_request_count!==0||c.observed_row_count!==0))throw new Error('DIAGNOSTIC_CAPTURE_STATE_INCONSISTENT');
  }
  if(verifyEvidence)for(const entry of report.evidence_refs) {
    const p=path.resolve(entry.path),archive=path.resolve(root,'../.p1b-archives/tushare-admission-20261005');
    const authorizations=['TUSHARE15000-local-admission-20261005.md','TUSHARE-monthly-gateway-probe-20261005.md'].map(n=>path.join(root,'docs/authorizations',n));
    if(!authorizations.includes(p)&&!p.startsWith(archive+path.sep))throw new Error('DIAGNOSTIC_EVIDENCE_PATH_UNAPPROVED');
    if(fs.realpathSync(p)!==p||sha(fs.readFileSync(p))!==entry.sha256)throw new Error('DIAGNOSTIC_EVIDENCE_MISMATCH');
  }
  return structuredClone(report);
}
export function verifyDiagnosticRelease() {
  const release=JSON.parse(fs.readFileSync(path.join(root,'contracts/release.tushare-admission.json'),'utf8'));
  for(const f of release.files)if(sha(fs.readFileSync(path.join(root,f.path)))!==f.sha256)throw new Error('DIAGNOSTIC_CONTRACT_RELEASE_MISMATCH');
  if(release.schema_version!==6||release.new_migrations.length||release.approved_tushare_policy_count!==0||release.production_enabled!==false)throw new Error('DIAGNOSTIC_SCOPE_UPGRADE');
  return release;
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===path.resolve(process.argv[1])) {
  verifyDiagnosticRelease();
  const r=verifyAdmissionVerification(JSON.parse(fs.readFileSync(path.join(root,'docs/tushare-admission/Gate.json'),'utf8')));
  console.log(JSON.stringify({contract:'AdmissionVerification1.0.0',verification:r.verification_conclusion,closed_conditions:r.closed_condition_ids,approved_tushare_policies:0}));
}
