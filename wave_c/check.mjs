import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
const python=process.env.TUSHARE_DIAGNOSTIC_PYTHON||path.resolve(process.execPath,'../../../python/bin/python3');
const args=process.argv.slice(2);
if(args.length>1||args.some(x=>x!=='--new-only'))throw Error('WAVE_C_ARGUMENT_INVALID');
function run(bin,params){const r=spawnSync(bin,params,{cwd:root,stdio:'inherit',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});if(r.status!==0)process.exit(r.status??1);}
if(!args.includes('--new-only'))run(process.execPath,['wave_b/check.mjs']);
run(python,['-B','-m','wave_c.verify']);
run(python,['-B','-m','unittest','discover','-s','wave_c/tests','-p','test_*.py','-v']);
run(process.execPath,['--test','--test-concurrency=1',...fs.readdirSync(path.join(root,'wave_c/tests')).filter(x=>x.endsWith('.test.mjs')).map(x=>'wave_c/tests/'+x)]);
console.log('Wave C local reports verified; formal admission/Pilot/history/cloud/production remain BLOCKED.');
