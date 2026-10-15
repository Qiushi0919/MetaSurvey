"""Synthetic reader tamper tests; derive is isolated, no market/private archive."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from workbench.server import Reader, ReadError, digest
from workbench.performance_reader import load
from tools.v3_review.package import CODE_PATHS

class PerformanceReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name).resolve()
        self.root=base/'repo';self.root.mkdir()
        self.archive=base/'review';self.original=base/'old'
        self.out=self.archive/'runs/V3-REVIEW-01';self.out.mkdir(parents=True)
        self.run=self.original/'runs/SYNTHETIC';self.run.mkdir(parents=True)
        def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d));return digest(p.read_bytes())
        self.write=write
        for path in CODE_PATHS:write(self.root/path,{})
        self.checked={'performance':{'run_id':'SYNTHETIC'},'benchmarks':[]}
        self.result={'run_id':'SYNTHETIC'}
        ch=write(self.run/'Case.json',{});eh=write(self.run/'EngineResult.json',self.result)
        self.gateway={'status':'VERIFIED','run':{'run_id':'SYNTHETIC','case_hash':ch,'engine_result_hash':eh},'diagnostic':self.result}
        self.pins={p:digest((self.root/p).read_bytes()) for p in CODE_PATHS}
        self.payload={'kind':'V3PerformancePackage','version':'1.0.0','run_id':'SYNTHETIC','case_hash':ch,'engine_result_hash':eh,'run_hash':'sha256:'+'a'*64,'code_pins':self.pins,'production_enabled':False,'result_type':'EXPOSED_HISTORY_DIAGNOSTIC_ANALYSIS',**self.checked}
        ah=write(self.out/'Analysis.json',self.payload)
        self.registry={'kind':'V3PerformanceRegistry','version':'1.0.0','run_id':'SYNTHETIC','analysis_directory':str(self.out),'analysis_hash':ah,'case_hash':ch,'engine_result_hash':eh,'run_hash':self.payload['run_hash'],'code_pins':self.pins}
        write(self.root/'docs/v3-performance/Registry.json',self.registry)
        write(self.root/'docs/e2e-gateway-v3/Registry.json',{'kind':'E2EGatewayRegistry','version':'1.0.0','run_directory':str(self.run),'run_sha256':self.payload['run_hash']})
        self.reader=Reader(self.root)
    def call(self):
        with patch('workbench.performance_reader.derive',return_value=self.checked):
            return load(self.reader,self.gateway,self.archive,self.original)
    def test_valid_bound_package(self):self.assertEqual(self.call()['status'],'VERIFIED')
    def test_reject_changed_analysis(self):
        self.write(self.out/'Analysis.json',{'changed':True})
        with self.assertRaises(ReadError) as c:self.call()
        self.assertEqual(c.exception.code,'PERFORMANCE_ANALYSIS_HASH')
    def test_reject_changed_original(self):
        self.write(self.run/'Case.json',{'fake':True})
        with self.assertRaises(ReadError) as c:self.call()
        self.assertEqual(c.exception.code,'PERFORMANCE_CASE_CHANGED')
    def test_reject_resealed_wrong_computation(self):
        self.payload['benchmarks']=[{'invented':True}]
        self.registry['analysis_hash']=self.write(self.out/'Analysis.json',self.payload)
        self.write(self.root/'docs/v3-performance/Registry.json',self.registry)
        with self.assertRaises(ReadError) as c:self.call()
        self.assertEqual(c.exception.code,'PERFORMANCE_RECOMPUTATION_MISMATCH')
    def test_reject_upstream_run_mismatch(self):
        self.gateway['run']['run_id']='OTHER'
        with self.assertRaises(ReadError) as c:self.call()
        self.assertEqual(c.exception.code,'PERFORMANCE_UPSTREAM_BINDING')
    def test_reject_outside_archive(self):
        self.registry['analysis_directory']=str(self.root)
        self.write(self.root/'docs/v3-performance/Registry.json',self.registry)
        with self.assertRaises(ReadError) as c:self.call()
        self.assertEqual(c.exception.code,'PERFORMANCE_PATH_SCOPE')
    def test_reject_code_drift(self):
        (self.root/CODE_PATHS[0]).write_text('drift')
        with self.assertRaises(ReadError) as c:self.call()
        self.assertEqual(c.exception.code,'PERFORMANCE_CODE_CHANGED')
    def test_reject_self_asserted_production(self):
        self.payload['production_enabled']=True
        self.registry['analysis_hash']=self.write(self.out/'Analysis.json',self.payload)
        self.write(self.root/'docs/v3-performance/Registry.json',self.registry)
        with self.assertRaises(ReadError) as c:self.call()
        self.assertEqual(c.exception.code,'PERFORMANCE_PACKAGE_BOUNDARY')
