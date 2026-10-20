"""Synthetic projections only: no market, account archive or credential access."""
from pathlib import Path
import json,tempfile,unittest
from workbench.server import Reader,ReadError,digest,FILES
from workbench.account20k_reader import load

class Account20kProjection(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()/'repo';self.root.mkdir()
        self.reader=Reader(self.root)
        self.history={'kind':'Account20kHistoryReview','experiment':'CORE40_ACCOUNT20K_HISTORY_V1'}
        self.status={'kind':'Account20kPublicStatus','version':'1.0.0','nav_cents':2000000}
        self.write('account20k-history',self.history);self.write('account20k-status',self.status)
        self.registry={'kind':'Account20kRegistry','version':'1.0.0',
            'history_hash':self.hash('account20k-history'),'status_hash':self.hash('account20k-status'),'code_pins':{}}
        self.write('account20k-registry',self.registry)
    def tearDown(self):self.temp.cleanup()
    def write(self,key,value):
        p=self.root/FILES[key];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
    def hash(self,key):return digest((self.root/FILES[key]).read_bytes())
    def rejects(self,code):
        with self.assertRaises(ReadError) as ctx:load(self.reader)
        self.assertEqual(ctx.exception.code,code)
    def test_public_archive_is_not_live(self):
        v=load(self.reader);self.assertEqual(v['status'],'PUBLIC_ARCHIVED_METADATA_ONLY')
        self.assertEqual(v['account']['nav_cents'],2000000);self.assertNotIn('task_live',v)
    def test_history_tamper(self):
        self.history['net_return']='1';self.write('account20k-history',self.history)
        self.rejects('ACCOUNT20K_HISTORY_HASH')
    def test_status_tamper(self):
        self.status['nav_cents']=123;self.write('account20k-status',self.status)
        self.rejects('ACCOUNT20K_STATUS_HASH')
    def test_history_identity(self):
        self.history['experiment']='OTHER';self.write('account20k-history',self.history)
        self.rejects('ACCOUNT20K_HISTORY_EXPERIMENT')
    def test_unknown_history_version(self):
        self.history['version']='unknown';self.write('account20k-history',self.history)
        self.rejects('UNSUPPORTED_VERSION')
    def test_missing_history(self):
        (self.root/FILES['account20k-history']).unlink();self.rejects('FILE_MISSING')
    def test_code_path_escape(self):
        self.registry['code_pins']={'../outside':'sha256:bad'}
        self.write('account20k-registry',self.registry);self.rejects('ACCOUNT20K_CODE_PATH')
    def test_code_mismatch(self):
        (self.root/'example.py').write_text('synthetic fixture')
        self.registry['code_pins']={'example.py':'sha256:bad'}
        self.write('account20k-registry',self.registry);self.rejects('ACCOUNT20K_CODE_HASH')
    def test_source_preserved(self):
        before=self.hash('account20k-status');load(self.reader)
        self.assertEqual(before,self.hash('account20k-status'))
