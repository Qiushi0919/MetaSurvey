import {spawnSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const python=process.env.P1B_DIAGNOSTIC_PYTHON||path.resolve(process.execPath,'../../../python/bin/python3');
const args=process.argv.slice(2);if(args.length>1||args.some(x=>x!=='--new-only'))throw Error('WH_ARGUMENT_INVALID');
function run(bin,args){const r=spawnSync(bin,args,{cwd:root,stdio:'inherit',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});if(r.status!==0)process.exit(r.status??1);}
if(!args.includes('--new-only'))run(process.execPath,['wave_g/check.mjs']);
run(python,['-B','-c','from wave_h.run import verify_saved; print(verify_saved())']);
run(python,['-B','-m','unittest','discover','-s','wave_h/tests','-p','test_*.py','-v']);
run(process.execPath,['--test','--test-concurrency=1','wave_h/tests/boundaries.test.mjs']);
console.log('Wave H-A offline complete. Actual capture, Snapshot B and Forward Day 1 await NEW Owner H-B authorization. STOP.');
