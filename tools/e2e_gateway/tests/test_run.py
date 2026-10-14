"""Gateway Run replay tests on temporary synthetic archives, never live data."""
from pathlib import Path
from unittest.mock import patch
import json,unittest
from datetime import datetime,timezone
from tools.e2e_gateway import run as r
from tools.e2e_gateway.tests import test_builder as fixture_module
class FixedClock:
 @staticmethod
 def now(tz=None):return datetime(2026,10,15,12,0,0,tzinfo=timezone.utc)
class GatewayRunTests(unittest.TestCase):
 def setUp(self):
  self.fixture=fixture_module.BuilderTests('test_valid_rebuild_units_and_v2_identity');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
  self.archive=self.fixture.root.resolve();self.folder=self.archive/'capture-SYNTHETIC';self.fixture.folder.rename(self.folder);self.fixture.folder=self.folder
  for p in (patch.object(r,'ARCHIVE',self.archive),patch.object(r,'datetime',FixedClock),patch.object(r,'SOURCE_POLICY',self.fixture.source),patch.object(r,'INPUT_POLICY',self.fixture.input)):
   p.start();self.addCleanup(p.stop)
 def test_real_shape_replayed_from_synthetic_capture(self):
  directory,run=r.execute(self.folder,'SYNTHETIC-ONLY');result=r.verify_existing(directory)
  self.assertEqual(run['version'],'3.0.0');self.assertTrue(run['engine_called']);self.assertEqual(result['engine_result']['status'],'RUN_NO_TRADES');self.assertEqual(len(result['api_matrix']),65)
 def test_unexecuted_matrix_is_not_zero_rows(self):
  manifest=self.folder/'Manifest.json';x=json.loads(manifest.read_text());x['sources']=x['sources'][:4];x['state']='CAPTURE_PARTIAL';manifest.write_text(json.dumps(x))
  directory,run=r.execute(self.folder,'SYNTHETIC-PARTIAL');result=r.verify_existing(directory)
  self.assertFalse(run['engine_called']);self.assertTrue(any(v['state']=='NOT_CALLED' and v['row_count'] is None for v in result['api_matrix']))
 def test_report_symlink_refused(self):
  directory,run=r.execute(self.folder,'SYNTHETIC-SYMLINK');p=directory/'BuildReport.json';target=self.archive/'outside.json';p.rename(target);p.symlink_to(target)
  with self.assertRaisesRegex(ValueError,'SYMLINK'):r.verify_existing(directory)
 def test_rehashed_false_execution_claim_rejected(self):
  directory,run=r.execute(self.folder,'SYNTHETIC-TAMPER');p=directory/'Run.json';x=json.loads(p.read_text());x['engine_called']=False;x['content_hash']=r.digest({k:v for k,v in x.items() if k!='content_hash'});p.write_text(json.dumps(x))
  with self.assertRaisesRegex(ValueError,'STATUS'):r.verify_existing(directory)
 def test_resealed_license_label_cannot_be_promoted(self):
  directory,run=r.execute(self.folder,'SYNTHETIC-LABEL');p=directory/'Run.json';x=json.loads(p.read_text());x['provider_license_status']='LICENSE_VERIFIED';x['content_hash']=r.digest({k:v for k,v in x.items() if k!='content_hash'});p.write_text(json.dumps(x))
  with self.assertRaisesRegex(ValueError,'FROZEN_LABEL'):r.verify_existing(directory)
if __name__=='__main__':unittest.main()
