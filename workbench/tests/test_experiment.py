import json, unittest
from workbench.server import ROOT, FILES
import test_readonly

class ExperimentViewTests(unittest.TestCase):
 setUpBase=test_readonly.AdapterTests.setUp
 write=test_readonly.AdapterTests.write
 def setUp(self):
  self.setUpBase()
  self.cfg=json.loads((ROOT/FILES['scoring-config']).read_text())
  self.status=json.loads((ROOT/FILES['scoring-status']).read_text())
  self.write('scoring-config',self.cfg);self.write('scoring-status',self.status)
 def error(self,code): self.assertTrue(any(e['panel']=='experiment' and e['code']==code for e in self.reader.state()['errors']))
 def test_config_comes_from_file(self):
  state=self.reader.state();self.assertEqual(state['experiment']['config'],self.cfg);self.assertEqual(state['experiment']['data']['real_sector_scores'],[])
 def test_refresh_reads_updated_candidate_definition(self):
  self.cfg['metrics']['demand_growth_bps']['definition']='SYNTHETIC_CHANGED_DEFINITION';self.write('scoring-config',self.cfg)
  self.assertEqual(self.reader.state()['experiment']['config']['metrics']['demand_growth_bps']['definition'],'SYNTHETIC_CHANGED_DEFINITION')
 def test_missing_config_shows_error(self):
  (self.root/FILES['scoring-config']).unlink();self.error('FILE_MISSING');self.assertNotIn('experiment',self.reader.state())
 def test_unsupported_experiment_version(self):
  self.cfg['version']='99';self.write('scoring-config',self.cfg);self.error('UNSUPPORTED_VERSION')
 def test_unknown_experiment_status(self):
  self.status['scoring_state']='PASS';self.write('scoring-status',self.status);self.error('UNKNOWN_STATUS')
 def test_fabricated_real_score_cannot_be_displayed(self):
  self.status['real_stock_scores']=[{'symbol':'FAKE','score':99}];self.write('scoring-status',self.status);self.error('UNADMITTED_SCORE_PAYLOAD')
 def test_malformed_factor_is_error(self):
  self.cfg['stock_factors'][0]['inputs']=['MAGIC'];self.write('scoring-config',self.cfg);self.error('INVALID_EXPERIMENT_CONFIG')
 def test_changed_owner_weights_are_not_silently_accepted(self):
  self.cfg['stock_factors'][0]['weight_percent']=26;self.write('scoring-config',self.cfg);self.error('INVALID_EXPERIMENT_CONFIG')
 def test_browsing_does_not_compute_or_write_scores(self):
  before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
  self.reader.state();self.reader.document('scoring-config');self.reader.document('scoring-status')
  self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
 def test_task_records_are_archived_not_agent_heartbeat(self):
  state=self.reader.state();self.assertEqual(state['task_runtime'],'NOT_CONNECTED_NO_LIVE_HEARTBEAT')
  self.assertTrue(all(x['status']=='ARCHIVED_RECORD_NOT_LIVE_TASK' for x in state['task_records']))

if __name__=='__main__': unittest.main()
