// Offline verification only; schemas do not grant historical execution authority.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
const root=path.resolve(import.meta.dirname,'..');
const python='/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const opts={cwd:root,encoding:'utf8',env:{PATH:'/usr/bin:/bin',PYTHONDONTWRITEBYTECODE:'1',LANG:'en_US.UTF-8'}};
const tests=spawnSync(python,['-B','-m','unittest','historical_pit.test_core','-v'],opts);
process.stdout.write(tests.stdout||'');process.stdout.write(tests.stderr||'');
assert.equal(tests.status,0,'Historical PIT offline tests failed');
const samples=spawnSync(python,['-B','-c',`
import json,tempfile
from pathlib import Path
from historical_pit import core as c
from dual_track.common import ref,write_new
records,dates,coverage,originals=c.read_current_originals()
calendar=c.calendar_structure(ref('/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/public-calendar/Calendar-Originals-Manifest.json'))
with tempfile.TemporaryDirectory() as d:
 cr=write_new(Path(d)/'calendar.json',calendar)
 matrix=c.closure_matrix(cr,c.UNSET)
 mr=write_new(Path(d)/'matrix.json',matrix)
 print(json.dumps({'HistoricalPITCandidateSnapshot':c.candidate_snapshot('603993.SH','2025-06-03',None,records),'HistoricalPITClosureMatrix':matrix,'HistoricalBacktestPrerequisiteAttempt':c.backtest_attempt(coverage,mr)}))
`],opts);
assert.equal(samples.status,0,samples.stderr);
const data=JSON.parse(samples.stdout),ajv=new Ajv({allErrors:true,strict:true});addFormats(ajv);
let atomic=0;
for (const [name,value] of Object.entries(data)) {
 const schema=JSON.parse(fs.readFileSync(path.join(root,'contracts/historical-pit',name+'-v1.schema.json')));
 const validate=ajv.compile(schema);
 assert(validate(value),JSON.stringify(validate.errors));atomic++;
 for (const field of Object.keys(value)) {
  const changed=structuredClone(value);delete changed[field];assert.equal(validate(changed),false);atomic++;
 }
 for (const change of [{productionGate:true},{namespace:'EVENT_3'},{order_intent:'BUY'}]) {
  assert.equal(validate({...value,...change}),false);atomic++;
 }
 if (name==='HistoricalPITCandidateSnapshot') {
  for (const change of [{historical_visibility_proven:true},{visible_records:[{future:'LEAK'}]},{formal_admission:'ADMITTED'},{decision_time:'2025-06-03T15:30:00+08:00'},{snapshot_sha256:'NOT_A_HASH'}]) {
   assert.equal(validate({...value,...change}),false);atomic++;
  }
 }
 if (name==='HistoricalPITClosureMatrix') {
  for (const change of [{continuous_domains_closed:1},{rows:value.rows.slice(1)},{actual_forward_days_increment:1}]) {
   assert.equal(validate({...value,...change}),false);atomic++;
  }
 }
 if (name==='HistoricalBacktestPrerequisiteAttempt') {
  for (const change of [{engine_called:true},{metrics:{...value.metrics,net:0}},{real_strategy_complete_trades:1},{untouched_oos:true}]) {
   assert.equal(validate({...value,...change}),false);atomic++;
  }
 }
}
console.log('Historical PIT schema atomic assertions: '+atomic+' PASS (not additional test cases)');
console.log('HISTORICAL_PIT_OFFLINE_CHECKS_PASS; formal historical execution BLOCKED');
