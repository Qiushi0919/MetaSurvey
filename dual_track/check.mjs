// Explicit offline entry. Existing project locks and test scripts stay frozen.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const python='/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const result=spawnSync(python,['-B','-m','unittest','dual_track.test_validation','-v'],{
  cwd:root,encoding:'utf8',env:{PATH:'/usr/bin:/bin',PYTHONDONTWRITEBYTECODE:'1',LANG:'en_US.UTF-8'}});
process.stdout.write(result.stdout||''); process.stdout.write(result.stderr||'');
assert.equal(result.status,0,'dual track Python tests failed');
const ajv=new Ajv({allErrors:true,strict:true});addFormats(ajv);
for (const name of ['ForwardPrediction','ForwardOutcome']) {
  const schema=JSON.parse(fs.readFileSync(path.join(root,'contracts/dual-track',name+'-v1.schema.json')));
  const check=ajv.compile(schema);assert.equal(check({}),false);
}
const generated=spawnSync(python,['-B','-c',`
import json,tempfile
from pathlib import Path
from unittest.mock import patch
from dual_track.common import ref,write_new
from dual_track.forward import owner_text_prediction,synthetic_score,append_fixture_outcome,fixture_head
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'source.txt';p.write_text('SYNTHETIC FIXTURE')
 with patch('dual_track.forward.now',return_value='2026-10-07T15:00:00Z'):
  prediction=owner_text_prediction(ref(p))
 pr=write_new(Path(d)/'prediction.json',prediction)
 bar={'mode':'SYNTHETIC_FIXTURE','symbol':'603993.SH','session':'2026-10-08','open':'16.88','close':'16.88','high':'17','low':'16'}
 store=Path(d)/'store';head,_=fixture_head(store,pr)
 out=append_fixture_outcome(store,pr,head,'603993.SH',1,[bar])
 print(json.dumps({'prediction':prediction,'outcome':json.loads(Path(out['path']).read_bytes())}))
`],{cwd:root,encoding:'utf8',env:{PATH:'/usr/bin:/bin',PYTHONDONTWRITEBYTECODE:'1',LANG:'en_US.UTF-8'}});
assert.equal(generated.status,0,generated.stderr);
const data=JSON.parse(generated.stdout);
let assertions=0;
for (const [name,object] of [['ForwardPrediction',data.prediction],['ForwardOutcome',data.outcome]]) {
  const check=ajv.getSchema('urn:metasurvey:dual-track:'+name+':1.0.0');
  assert(check(object),JSON.stringify(check.errors));assertions++;
  for (const field of Object.keys(object)) {const copy=structuredClone(object);delete copy[field];assert.equal(check(copy),false);assertions++;}
  const extra={...object,order_intent:'BUY'};assert.equal(check(extra),false);assertions++;
}
const realPromotion=structuredClone(data.outcome);realPromotion.mode='ACTUAL_RESEARCH_ONLY';
assert.equal(ajv.getSchema('urn:metasurvey:dual-track:ForwardOutcome:1.0.0')(realPromotion),false);assertions++;
console.log('Schema validation atomic assertions: '+assertions+' PASS (not additional test cases)');
console.log('DUAL_TRACK_OFFLINE_CHECKS_PASS');
