import {spawnSync} from 'node:child_process';
import {readdirSync} from 'node:fs';
import {root,verifyProvenance} from './provenance.mjs';
await verifyProvenance();
function run(args){const r=spawnSync(process.execPath,args,{cwd:root,stdio:'inherit',env:process.env});if(r.status!==0)process.exit(r.status??1);}
run(['p1b/scripts/check.mjs']);
run(['--test','--test-concurrency=1',...readdirSync(root+'/real-slice/tests').filter(x=>x.endsWith('.test.mjs')).map(x=>'real-slice/tests/'+x)]);
