"""Runner archive checks using temporary synthetic captures only.

Source authority is mocked at the test boundary. No secret, original private
archive, network, actual data provider or production bypass is accessed.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.e2e_history import run as runner
from tools.e2e_history import builder
from tools.e2e_history.tests.test_builder import fixture


class FixedClock:
    @staticmethod
    def now(tz=None):
        return datetime(2026,10,15,12,0,0,tzinfo=timezone.utc)


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.archive=Path(self.temp.name).resolve()
        self.capture=self.archive/'baostock-SYNTHETIC';self.capture.mkdir()
        fixture(self.capture)
        for mocked in (patch.object(runner,'ARCHIVE',self.archive),
                       patch.object(runner,'datetime',FixedClock),
                       patch.object(builder,'require_exception_coverage',return_value={'SYNTHETIC_ONLY':True}),
                       patch.object(builder,'source_authority',return_value={'SYNTHETIC_TEST_ONLY':True})):
            mocked.start();self.addCleanup(mocked.stop)

    def execute(self,name='SYNTHETIC-run'):
        return runner.execute(self.capture,name)

    def rewrite_run(self,directory,change):
        path=directory/'Run.json';value=json.loads(path.read_text());change(value)
        value['content_hash']=runner.digest({k:v for k,v in value.items() if k!='content_hash'})
        path.write_text(json.dumps(value))

    def blocked(self):
        (self.capture/'Manifest.json').write_text(json.dumps({'state':'LOGIN_FAILED'}))
        return self.execute()

    def replace_with_symlink(self,path):
        target=self.archive/('external-'+path.name)
        target.write_bytes(path.read_bytes());path.unlink();path.symlink_to(target)

    def test_success_recompute_without_writes(self):
        directory,run=self.execute()
        self.assertTrue(run['engine_called']);self.assertEqual(run['status'],'RUN_NO_TRADES')
        before={str(p):p.read_bytes() for p in self.archive.rglob('*') if p.is_file()}
        verified=runner.verify_existing(directory)
        self.assertEqual(verified['run'],run)
        self.assertEqual(verified['engine_result']['status'],'RUN_NO_TRADES')
        after={str(p):p.read_bytes() for p in self.archive.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_failed_capture_preserved_and_recomputed(self):
        directory,run=self.blocked()
        self.assertFalse(run['engine_called']);self.assertEqual(run['status'],'SOURCE_OR_INPUT_BLOCKED')
        self.assertTrue((directory/'BuildReport.json').is_file())
        self.assertFalse((directory/'Case.json').exists())
        self.assertIsNone(runner.verify_existing(directory)['engine_result'])
        original=(directory/'Run.json').read_bytes()
        with self.assertRaises(FileExistsError):self.execute()
        self.assertEqual(original,(directory/'Run.json').read_bytes())

    def test_run_content_change_rejected(self):
        directory,_=self.blocked();path=directory/'Run.json'
        value=json.loads(path.read_text());value['status']='PASS';path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'RUN_CONTENT_HASH_MISMATCH'):runner.verify_existing(directory)

    def test_code_pin_change_even_with_resealed_run_rejected(self):
        directory,_=self.blocked()
        self.rewrite_run(directory,lambda x:x['code_pins'].update({'tools/e2e_history/run.py':'sha256:'+'0'*64}))
        with self.assertRaisesRegex(ValueError,'RUN_CODE_PINS_MISMATCH'):runner.verify_existing(directory)

    def test_forged_engine_boolean_rejected(self):
        directory,_=self.blocked()
        self.rewrite_run(directory,lambda x:x.update(engine_called=True))
        with self.assertRaisesRegex(ValueError,'RUN_STATUS_MISMATCH'):runner.verify_existing(directory)

    def test_integer_is_not_engine_boolean(self):
        directory,_=self.blocked()
        self.rewrite_run(directory,lambda x:x.update(engine_called=0))
        with self.assertRaisesRegex(ValueError,'RUN_ENGINE_CALLED_BOOLEAN_REQUIRED'):runner.verify_existing(directory)

    def test_case_symlink_rejected_even_identical_content(self):
        directory,_=self.execute();self.replace_with_symlink(directory/'Case.json')
        with self.assertRaisesRegex(ValueError,'METADATA_ALIAS_OR_SYMLINK'):runner.verify_existing(directory)

    def test_manifest_symlink_rejected_even_identical_content(self):
        directory,_=self.blocked();self.replace_with_symlink(self.capture/'Manifest.json')
        with self.assertRaisesRegex(ValueError,'METADATA_ALIAS_OR_SYMLINK'):runner.verify_existing(directory)

    def test_manifest_symlink_rejected_before_execution(self):
        self.replace_with_symlink(self.capture/'Manifest.json')
        with self.assertRaisesRegex(ValueError,'METADATA_ALIAS_OR_SYMLINK'):self.execute()
        self.assertFalse((self.archive/'runs').exists())

    def test_report_symlink_rejected(self):
        directory,_=self.blocked();self.replace_with_symlink(directory/'BuildReport.json')
        with self.assertRaisesRegex(ValueError,'METADATA_ALIAS_OR_SYMLINK'):runner.verify_existing(directory)

    def test_engine_result_symlink_rejected(self):
        directory,_=self.execute();self.replace_with_symlink(directory/'EngineResult.json')
        with self.assertRaisesRegex(ValueError,'METADATA_ALIAS_OR_SYMLINK'):runner.verify_existing(directory)

    def test_run_metadata_symlink_rejected(self):
        directory,_=self.blocked();self.replace_with_symlink(directory/'Run.json')
        with self.assertRaisesRegex(ValueError,'METADATA_ALIAS_OR_SYMLINK'):runner.verify_existing(directory)

    def test_optional_dangling_case_symlink_rejected(self):
        directory,_=self.blocked();(directory/'Case.json').symlink_to(self.archive/'missing-target')
        with self.assertRaisesRegex(ValueError,'METADATA_ALIAS_OR_SYMLINK'):runner.verify_existing(directory)

    def test_regular_file_required_not_directory(self):
        directory,_=self.blocked();(directory/'BuildReport.json').unlink();(directory/'BuildReport.json').mkdir()
        with self.assertRaisesRegex(ValueError,'METADATA_REGULAR_FILE_REQUIRED'):runner.verify_existing(directory)

    def test_capture_content_mutation_rejected(self):
        directory,_=self.execute();path=self.capture/'2.json';path.write_text(path.read_text()+' ')
        with self.assertRaisesRegex(ValueError,'BUILD_REPORT_RECOMPUTATION_MISMATCH'):runner.verify_existing(directory)

    def test_engine_result_tamper_rejected(self):
        directory,_=self.execute();path=directory/'EngineResult.json'
        value=json.loads(path.read_text());value['engine_called']=False;path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'ENGINE_RECOMPUTATION_MISMATCH'):runner.verify_existing(directory)

    def test_run_id_matches_readers_length_and_first_character(self):
        for name in ('_hidden','.hidden','-dash','a'*97,'../escape',''):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'SAFE_RUN_ID_REQUIRED'):
                self.execute(name)
        directory,_=self.blocked()
        self.assertIsNotNone(runner.RUN_ID_RE.fullmatch('A'+'x'*95))
        self.assertIsNotNone(runner.RUN_ID_RE.fullmatch('A.b_c-1'))
        self.assertEqual(runner.validate_dir(directory,'run'),directory)

    def test_parent_alias_rejected(self):
        directory,_=self.blocked()
        alias=directory/'..'/directory.name
        with self.assertRaisesRegex(ValueError,'PRIVATE_PATH_ALIAS_OR_SYMLINK'):runner.verify_existing(alias)


if __name__=='__main__':unittest.main()
