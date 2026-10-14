import json, shutil, subprocess, unittest
from pathlib import Path
from workbench.server import ROOT, FILES, digest
from workbench.score_reader import load, CODE
import test_readonly

class ScoreReviewTests(unittest.TestCase):
 setUpBase=test_readonly.AdapterTests.setUp
 write=test_readonly.AdapterTests.write
 reject=test_readonly.AdapterTests.reject
 def setUp(self):
  self.setUpBase()
  for rel in CODE:
   p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ROOT/rel).read_bytes())
  (self.root/'node_modules').symlink_to(ROOT/'node_modules',target_is_directory=True)
  self.sources=tuple(self.private/f'synthetic-{n}.json' for n in range(5))
  for p in self.sources:p.write_text('{"SYNTHETIC_NOT_MARKET_DATA":true}')
  self.pins=[{'path':str(p),'sha256':digest(p.read_bytes()),'bytes':p.stat().st_size} for p in self.sources]
  self.sample=self.private/'Synthetic-Sample.json'
  node=shutil.which('node') or '/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
  script="""import fs from 'node:fs';import {config} from './experiments/sector_stock_v0/engine.mjs';import {blockedGraph,seal,adapterHash,engineHash,configHash,candidateHash,applicabilityHash,applicability} from './experiments/sector_stock_v01/admission.mjs';let p={kind:'CurrentObservationScoreReviewPackage',version:'0.1.0-admission',symbol:'603228.SH',sector_id:'PROPOSED:PCB_MANUFACTURING',peer_count:1,trace_id:'SYNTHETIC_HTTP_FIXTURE',recorded_at:'2026-10-14T08:00:00Z',decision_cutoff:'2026-10-14T08:00:00Z',source_files:JSON.parse(fs.readFileSync(0,'utf8')),config_sha256:configHash,engine_sha256:engineHash,adapter_sha256:adapterHash,candidate_sha256:candidateHash,applicability_sha256:applicabilityHash,applicability:applicability(),method_state:'OWNER_PENDING',formal_candidate:false,can_produce_order:false,historical_visibility_proven:false,local_only:true};p.field_matrix=[...config.sector_metrics,...config.stock_factors.flatMap(f=>f.inputs)].map(metric=>({metric,unit:config.metrics[metric].unit,score_input_value:null,status:'BLOCKED',calculation:'SYNTHETIC',gaps:['SYNTHETIC_MISSING']}));p.objects=blockedGraph(p);process.stdout.write(JSON.stringify(seal(p)));"""
  r=subprocess.run([node,'--input-type=module','-e',script],cwd=self.root,input=json.dumps(self.pins),text=True,capture_output=True,check=True);self.sample.write_text(r.stdout)
  self.reg={'kind':'LocalScoreReviewRegistry','version':'1.0.0','sample_path':str(self.sample),'sample_sha256':digest(self.sample.read_bytes()),'sample_content_hash':json.loads(r.stdout)['content_hash'],'code_pins':{p:digest((self.root/p).read_bytes()) for p in CODE},'source_files':self.pins,'archive_observation_cutoff':'SYNTHETIC'};self.write('score-review-registry',self.reg)
 def read(self):return load(self.reader,self.sample,self.sources)
 def test_verified_chain_returns_only_blocked_projection(self):
  v=self.read();self.assertEqual(len(v['scores']),2);self.assertTrue(all(s['final_score'] is None for s in v['scores']));self.assertNotIn('source_files',v);self.assertEqual(v['applicability'][0]['risks']['concentration']['state'],'NOT_APPLICABLE')
 def test_changed_raw_original_rejected(self):
  self.sources[0].write_text('{}');self.reject('SCORE_PIN_MISMATCH',self.read)
 def test_missing_original_rejected(self):
  self.sources[0].unlink();self.reject('FILE_MISSING',self.read)
 def test_original_symlink_rejected(self):
  self.sources[0].unlink();self.sources[0].symlink_to(self.sources[1]);self.reject('UNSAFE_PATH',self.read)
 def test_code_change_rejected(self):
  (self.root/CODE[0]).write_text('{}');self.reject('SCORE_PIN_MISMATCH',self.read)
 def test_registry_arbitrary_path_rejected(self):
  self.reg['source_files'][0]['path']='/tmp/not-allowed';self.write('score-review-registry',self.reg);self.reject('SCORE_SOURCE_SCOPE',self.read)
 def test_changed_package_rejected(self):
  self.sample.write_text('{}');self.reject('SCORE_PIN_MISMATCH',self.read)
 def test_resealed_changed_score_not_accepted_by_file_hash(self):
  p=json.loads(self.sample.read_text());p['objects'][5]['final_score']='99.00';self.sample.write_text(json.dumps(p));self.reg['sample_sha256']=digest(self.sample.read_bytes());self.write('score-review-registry',self.reg);self.reject('SCORE_VALIDATION_FAILED',self.read)
 def test_unknown_version_rejected(self):
  self.reg['version']='99';self.write('score-review-registry',self.reg);self.reject('UNSUPPORTED_VERSION',self.read)
 def test_read_does_not_modify_inputs(self):
  paths=[self.sample,*self.sources,*[self.root/x for x in CODE]];before=[digest(p.read_bytes()) for p in paths];self.read();self.assertEqual(before,[digest(p.read_bytes()) for p in paths])
