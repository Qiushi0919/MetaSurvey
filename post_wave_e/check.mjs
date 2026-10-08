import fs from 'node:fs';import path from 'node:path';import {spawnSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..'),python=process.env.TUSHARE_DIAGNOSTIC_PYTHON||path.resolve(process.execPath,'../../../python/bin/python3');
const args=process.argv.slice(2);if(args.length>1||args.some(x=>x!=='--new-only'))throw Error('PREP_ARGUMENT_INVALID');
function run(bin,args){const r=spawnSync(bin,args,{cwd:root,stdio:'inherit',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});if(r.status!==0)process.exit(r.status??1);}
if(!args.includes('--new-only'))run(process.execPath,['wave_e/check.mjs']);
run(python,['-B','-c','from post_wave_e.run import verify_saved; print(verify_saved())']);
run(python,['-B','-m','unittest','discover','-s','post_wave_e/tests','-p','test_*.py','-v']);
run(process.execPath,['--test','--test-concurrency=1',...fs.readdirSync(path.join(root,'post_wave_e/tests')).filter(x=>x.endsWith('.test.mjs')).map(x=>'post_wave_e/tests/'+x)]);
console.log('Post-Wave-E offline preparation verified. Actual Snapshot B/Paper/formal history/cloud/production remain BLOCKED.');
