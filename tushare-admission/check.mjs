import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const root=path.resolve(import.meta.dirname,'..');
const bundledPython=path.resolve(path.dirname(process.execPath),'../../python/bin/python3');
const python=process.env.TUSHARE_DIAGNOSTIC_PYTHON??(fs.existsSync(bundledPython)?bundledPython:'python3');
function run(command,args){const r=spawnSync(command,args,{cwd:root,stdio:'inherit'});if(r.status!==0)process.exit(r.status??1);}
if(!process.argv.includes('--diagnostic-only'))run(process.execPath,['real-slice/scripts/check.mjs']);
run(process.execPath,['tushare-admission/parent/verify.mjs']);
run(process.execPath,['--test','tushare-admission/parent/contracts.test.mjs']);
run(python,['-B','-m','unittest','discover','-s','tushare-admission/tests','-v']);
console.log('Bounded gateway diagnostic checks passed. No credential lookup or authenticated network execution enabled.');
