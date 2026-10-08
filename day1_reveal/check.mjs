// Explicit offline tests; mocked positive examples never grant actual authority.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const python='/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const options={cwd:root,encoding:'utf8',env:{PATH:'/usr/bin:/bin',PYTHONDONTWRITEBYTECODE:'1',LANG:'en_US.UTF-8'}};
const tests=spawnSync(python,['-B','-m','unittest','day1_reveal.test_reveal','-v'],options);
process.stdout.write(tests.stdout||'');process.stdout.write(tests.stderr||'');
assert.equal(tests.status,0,'Day1 offline tests failed');
const sample=spawnSync(python,['-B','-c',`
import json
from day1_reveal.test_reveal import RevealTests
r=RevealTests();r.setUp()
try:
 data=r.mock_score()
 data.update({'sequence':1,'previous_hash':'sha256:'+'0'*64,'expected_head':'sha256:'+'0'*64,'outcome_sha256':'sha256:'+'0'*64})
 print(json.dumps(data))
finally:r.doCleanups()
`],options);
assert.equal(sample.status,0,sample.stderr);
const ajv=new Ajv({allErrors:true,strict:true});addFormats(ajv);
const check=ajv.compile(JSON.parse(fs.readFileSync(path.join(root,'contracts/day1-reveal/Day1RevealOutcome-v1.schema.json'))));
const data=JSON.parse(sample.stdout);let atomic=0;
assert(check(data),JSON.stringify(check.errors));atomic++;
for(const field of Object.keys(data)) {
 const copy=structuredClone(data);delete copy[field];assert.equal(check(copy),false);atomic++;
}
for(const change of [{productionGate:true},{forward_signature_verified:false},{namespace:'EVENT_3'},{horizon:20},{target_close:17.1},{order_intent:'BUY'},{actual_forward_days_increment:1}]) {
 assert.equal(check({...data,...change}),false);atomic++;
}
console.log('Day1 schema atomic assertions: '+atomic+' PASS (not additional cases)');
console.log('DAY1_REVEAL_OFFLINE_CHECKS_PASS');
