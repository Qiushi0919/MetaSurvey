import path from 'node:path';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
const python=process.env.TUSHARE_DIAGNOSTIC_PYTHON||path.resolve(process.execPath,'../../../python/bin/python3');
const args=process.argv.slice(2);
if(args.length>1||args.some(x=>x!=='--new-only'))throw Error('WAVE_B_ARGUMENT_INVALID');
function run(bin,params){const r=spawnSync(bin,params,{cwd:root,stdio:'inherit',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});if(r.status!==0)process.exit(r.status??1);}
if(!args.includes('--new-only'))run(process.execPath,['overnight/check.mjs']);
run(python,['-B','-m','wave_b.verify']);
run(python,['-B','-m','unittest','discover','-s','wave_b/tests','-p','test_*.py','-v']);
run(process.execPath,['--test','--test-concurrency=1',...fs.readdirSync(path.join(root,'wave_b/tests')).filter(x=>x.endsWith('.test.mjs')).map(x=>'wave_b/tests/'+x)]);
console.log('Wave B candidate engineering verified; source, history, research and production BLOCKED.');
