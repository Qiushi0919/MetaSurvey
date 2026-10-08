import path from 'node:path';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import Ajv from 'ajv/dist/2020.js';
import {hashValue} from '../src/contracts/validate.mjs';
const root=path.resolve(import.meta.dirname,'..');
const python=process.env.TUSHARE_DIAGNOSTIC_PYTHON||path.resolve(process.execPath,'../../../python/bin/python3');
const args=process.argv.slice(2);
if(args.length>1||args.some(a=>a!=='--new-only')){console.error('OVERNIGHT_ARGUMENT_INVALID');process.exit(1);}
const run=(bin,params)=>{const r=spawnSync(bin,params,{cwd:root,stdio:'inherit',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});if(r.status!==0)process.exit(r.status??1);};
if(!args.includes('--new-only'))run(process.execPath,['verification-portability/check.mjs']);
run(python,['-B','-m','overnight.verify']);
const evidence=JSON.parse(fs.readFileSync(path.join(root,'docs/overnight/evidence.json')));
const readiness=JSON.parse(fs.readFileSync(evidence.artifacts.find(r=>r.object==='readiness').path));
const schema=JSON.parse(fs.readFileSync(path.join(root,'contracts/overnight/AdmissionReadinessDryRun.schema.json')));
const ajv=new Ajv({strict:true,allErrors:true});
const validate=ajv.compile(schema);
if(!validate(readiness)){console.error('OVERNIGHT_READINESS_SCHEMA_INVALID');process.exit(1);}
const {content_hash,...body}=readiness;
const categories=['SECURITY_STATUS','CALENDAR_RULES','RAW_BARS','CORPORATE_ACTIONS','ADJUSTMENT_VERSIONS','FINANCIAL_REVISIONS','ANNOUNCEMENTS','INDUSTRY_MEMBERSHIP'];
if(content_hash!==hashValue(body)||JSON.stringify(readiness.categories.map(c=>c.category))!==JSON.stringify(categories)){
 console.error('OVERNIGHT_READINESS_HASH_OR_CATEGORY_INVALID');process.exit(1);
}
run(python,['-B','-m','unittest','discover','-s','overnight/tests','-p','test_*.py','-v']);
run(process.execPath,['--test','--test-concurrency=1',...fs.readdirSync(path.join(root,'overnight/tests')).filter(p=>p.endsWith('.test.mjs')).map(p=>'overnight/tests/'+p)]);
console.log('Overnight offline engineering verified; all real data and execution gates remain BLOCKED.');
