"""Synthetic temporary registry boundaries; dashboard verifier is explicitly stubbed."""
import copy
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
from workbench.server import Reader, ReadError, FILES, digest
from workbench.long_forward_reader import load, MINIMUM_CODE_PATHS, PROTOCOL


class LongForwardReaderTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.base=Path(temp.name).resolve();self.root=self.base/'repo';self.root.mkdir()
        self.archive=self.base/'.p1b-archives/long-forward-20261015';self.archive.mkdir(parents=True)
        self.addCleanup(self.cleanup_synthetic_archive)
        self.reader=Reader(self.root,self.archive)
        for rel in MINIMUM_CODE_PATHS|{PROTOCOL}:
            p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('SYNTHETIC NOT EXECUTED')
        self.registry={'kind':'LongForwardRegistry','version':'1.0.0','status':'LOCAL_ONLY','archive_root':str(self.archive),
          'code_pins':{p:digest((self.root/p).read_bytes()) for p in MINIMUM_CODE_PATHS},
          'protocol_ref':digest((self.root/PROTOCOL).read_bytes()),'history_run':None,'forward_state':None}
        self.checked={'status':'VERIFIED','history':None,'forward':None,'integrity':'SYNTHETIC_VERIFIED'}
        self.calls=[]
        stub=types.ModuleType('tools.long_forward.reporting')
        def verify(reg):self.calls.append(copy.deepcopy(reg));return copy.deepcopy(self.checked)
        stub.verify_dashboard=verify;self.stub=stub
        patches=[patch.dict(FILES,{'long-forward-registry':'workbench/long-forward-registry.json'}),patch.dict(sys.modules,{'tools.long_forward.reporting':stub})]
        for item in patches:item.start();self.addCleanup(item.stop)
        self.save()
    def cleanup_synthetic_archive(self):
        # Only these empty fixture directories (and one test symlink) exist here.
        # Remove them before TemporaryDirectory's recursive cleanup, which opens
        # directories and correctly trips the CI privacy guard for archive names.
        link=self.archive/'runs/A'
        if link.is_symlink():link.unlink()
        runs=self.archive/'runs'
        if runs.exists():runs.rmdir()
        self.archive.rmdir()
        self.archive.parent.rmdir()
    def save(self):
        p=self.root/'workbench/long-forward-registry.json';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(self.registry))
    def error(self,code):
        with self.assertRaises(ReadError) as e:load(self.reader)
        self.assertEqual(e.exception.code,code)
    def test_unconfigured_not_running(self):
        r=load(self.reader);self.assertIsNone(r['history']);self.assertIsNone(r['forward'])
    def test_reads_do_not_modify_files(self):
        before={str(p):p.read_bytes() for p in self.base.rglob('*') if p.is_file()};load(self.reader)
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.base.rglob('*') if p.is_file()})
    def test_wrong_version(self):self.registry['version']='2.0.0';self.save();self.error('UNSUPPORTED_VERSION')
    def test_not_local(self):self.registry['status']='PRODUCTION';self.save();self.error('LONG_FORWARD_BOUNDARY_MISMATCH')
    def test_foreign_archive(self):self.registry['archive_root']=str(self.base/'other');self.save();self.error('LONG_FORWARD_BOUNDARY_MISMATCH')
    def test_missing_code_pin(self):self.registry['code_pins'].pop(next(iter(MINIMUM_CODE_PATHS)));self.save();self.error('LONG_FORWARD_CODE_SCOPE')
    def test_foreign_pin_path(self):self.registry['code_pins']['secrets/account.json']='sha256:'+'a'*64;self.save();self.error('LONG_FORWARD_CODE_SCOPE')
    def test_code_change_blocks_before_verifier(self):
        (self.root/next(iter(MINIMUM_CODE_PATHS))).write_text('CHANGED');self.error('LONG_FORWARD_CODE_PIN_MISMATCH');self.assertEqual(self.calls,[])
    def test_protocol_change(self):(self.root/PROTOCOL).write_text('CHANGED');self.error('LONG_FORWARD_PROTOCOL_MISMATCH')
    def test_history_traversal(self):self.registry['history_run']='runs/../../other';self.save();self.error('LONG_FORWARD_ARTIFACT_SCOPE')
    def test_forward_wrong_prefix(self):self.registry['forward_state']='runs/A';self.save();self.error('LONG_FORWARD_ARTIFACT_SCOPE')
    def test_symlink_artifact(self):
        folder=self.archive/'runs';folder.mkdir();(folder/'A').symlink_to(self.base,target_is_directory=True)
        self.registry['history_run']='runs/A';self.save();self.error('UNSAFE_PATH')
    def test_verifier_failure(self):
        self.stub.verify_dashboard=lambda _:(_ for _ in ()).throw(ValueError('CHANGED_ARTIFACT'))
        self.error('LONG_FORWARD_INTEGRITY_ERROR')
    def test_verifier_unverified(self):self.checked['status']='UNVERIFIED';self.error('LONG_FORWARD_INTEGRITY_ERROR')
    def subprocess_error(self, exception):
        self.stub.verify_dashboard=lambda _:(_ for _ in ()).throw(exception)
        with self.assertRaises(ReadError) as caught:load(self.reader)
        self.assertEqual(caught.exception.code,'LONG_FORWARD_INTEGRITY_ERROR')
        self.assertNotIn('SYNTHETIC_PRIVATE_STDERR',str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)
    def test_frozen_verifier_timeout_is_safe_integrity_error(self):
        self.subprocess_error(subprocess.TimeoutExpired(['SYNTHETIC_COMMAND'],1,stderr='SYNTHETIC_PRIVATE_STDERR'))
    def test_frozen_verifier_exit_failure_is_safe_integrity_error(self):
        self.subprocess_error(subprocess.CalledProcessError(1,['SYNTHETIC_COMMAND'],stderr='SYNTHETIC_PRIVATE_STDERR'))
    def test_engine_flag_not_coerced(self):self.checked['history']={'engine_called':'false'};self.error('LONG_FORWARD_HISTORY_SHAPE')
    def test_blocked_result_not_no_trades(self):
        self.checked['history']={'run_id':'SYNTHETIC','status':'DATA_BLOCKED','engine_called':False,'overall':None,'raw_bars':['NOT_FOR_UI']}
        r=load(self.reader)['history'];self.assertEqual(r['status'],'DATA_BLOCKED');self.assertIsNone(r['overall']);self.assertNotIn('raw_bars',r)
    def test_forward_missed_and_candidate_block_preserved(self):
        self.checked['forward']={'strategy_a':{'status':'MISSED','observed_sessions':0,'plan':None},'strategy_b':{'status':'BLOCKED','module':'SYNTHETIC_B','reason':'MISSING_EVIDENCE'}}
        r=load(self.reader)['forward'];self.assertEqual(r,self.checked['forward'])
    def test_unknown_top_level_not_exposed(self):
        self.checked['case']={'raw':'SYNTHETIC'};self.assertNotIn('case',load(self.reader))
