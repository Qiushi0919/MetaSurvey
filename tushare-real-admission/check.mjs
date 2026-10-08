import {spawnSync} from 'node:child_process';
import path from 'node:path';

const root=path.resolve(import.meta.dirname,'..');
const python=process.env.TUSHARE_DIAGNOSTIC_PYTHON||path.resolve(process.execPath,'../../../python/bin/python3');
const run=(bin,args)=>{const p=spawnSync(bin,args,{cwd:root,stdio:'inherit',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});if(p.status!==0)process.exit(p.status??1);};
if(!process.argv.includes('--new-only'))run(process.execPath,['tushare-admission/check.mjs']);
run(process.execPath,['tushare-real-admission/parent/verify.mjs']);
run(process.execPath,['--test','tushare-real-admission/parent/contracts.test.mjs']);
run(python,['-B','-m','unittest','discover','-s','tushare-real-admission/tests','-v']);
