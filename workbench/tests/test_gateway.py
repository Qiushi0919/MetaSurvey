"""Temporary synthetic artifacts only; runner stubbed, no market or credentials."""
import copy
import http.client
import json
import sys
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench.server import Reader, ReadError, FILES, Handler, ThreadingHTTPServer, digest
from workbench.gateway_reader import load, CODE_PATHS


class GatewayReaderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve(); self.root = self.base / 'repo'; self.root.mkdir()
        self.archive = self.base / 'SYNTHETIC_GATEWAY'; self.archive.mkdir()
        self.folder = self.archive / 'runs/SYNTHETIC-01'; self.folder.mkdir(parents=True)
        self.capture = self.archive / 'capture-synthetic'; self.capture.mkdir()
        self.reader = Reader(self.root, self.archive)
        for relative in CODE_PATHS:
            p = self.root / relative; p.parent.mkdir(parents=True, exist_ok=True); p.write_text('SYNTHETIC NOT EXECUTED\n')
        self.pins = {p: digest((self.root / p).read_bytes()) for p in CODE_PATHS}
        self.run = {'kind': 'HistoricalGatewayDiagnosticRun', 'version': '3.0.0', 'run_id': self.folder.name,
                    'recorded_at': '2026-10-14T10:00:00+00:00', 'capture_dir': str(self.capture),
                    'code_pins': self.pins, 'engine_called': False, 'status': 'SOURCE_OR_INPUT_BLOCKED',
                    'evidence_grade': 'RECONSTRUCTED_HISTORY_DIAGNOSTIC', 'historical_visibility_proven': False,
                    'production_enabled': False, 'source_epoch': 'COMPATIBLE_GATEWAY_V3'}
        for key, path in [('protocol_hash', 'experiments/e2e_history_v2/protocol.json'),
                          ('input_policy_hash', 'experiments/e2e_gateway_v3/input-policy.json'),
                          ('source_policy_hash', 'docs/e2e-gateway-v3/Source-Policy.json')]: self.run[key] = self.pins[path]
        self.registry = {'kind': 'E2EGatewayRegistry', 'version': '1.0.0', 'run_directory': str(self.folder), 'code_pins': self.pins}
        self.refresh_run()
        self.report = {'kind': 'SyntheticBuildReport', 'status': 'DATA_BLOCKED', 'errors': ['SYNTHETIC_SOURCE_FAILURE'], 'raw_bars': ['PRIVATE_RAW_NOT_FOR_PROJECTION']}
        self.result = None
        self.matrix = [{'api_name': 'daily', 'params': {'ts_code': '603228.SH'}, 'row_count': 3, 'state': 'SUCCESS', 'raw_rows': ['PRIVATE_RAW_NOT_FOR_PROJECTION'], 'retrieved_at': '2026-10-14T09:00:00+00:00', 'error_code': 0},
                       {'api_name': 'stk_limit', 'params': {'ts_code': '603228.SH'}, 'row_count': 0, 'state': 'IP_CONCURRENCY_LIMIT', 'error_code': 'SYNTHETIC'},
                       {'api_name': 'dividend', 'params': {'ts_code': '603228.SH'}, 'row_count': None, 'state': 'NOT_CALLED'}]
        self.calls = []
        stub = types.ModuleType('tools.e2e_gateway.run')
        def verify(directory):
            self.calls.append(directory)
            return {'run': copy.deepcopy(self.run), 'build_report': copy.deepcopy(self.report), 'engine_result': copy.deepcopy(self.result), 'api_matrix': copy.deepcopy(self.matrix)}
        stub.verify_existing = verify; self.stub = stub
        modules = patch.dict(sys.modules, {'tools.e2e_gateway.run': stub}); modules.start(); self.addCleanup(modules.stop)

    def write_registry(self):
        p = self.root / FILES['gateway-registry']; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(self.registry))
    def refresh_run(self):
        p = self.folder / 'Run.json'; p.write_text(json.dumps(self.run)); self.registry['run_sha256'] = digest(p.read_bytes()); self.write_registry()
    def load(self): return load(self.reader, archive=self.archive)
    def error(self, code):
        with self.assertRaises(ReadError) as c: self.load()
        self.assertEqual(c.exception.code, code)
    def test_partial_api_success_not_promoted_to_engine_success(self):
        v = self.load(); self.assertFalse(v['run']['engine_called']); self.assertIsNone(v['diagnostic'])
        self.assertEqual([r['row_count'] for r in v['api_matrix']], [3, 0, None]); self.assertNotIn('raw_rows', v['api_matrix'][0]); self.assertNotIn('raw_bars', v['build_report'])
    def test_reads_do_not_modify_artifacts(self):
        before = {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file()}; self.load()
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file()})
    def test_built_case_engine_preflight_failure_preserved(self):
        self.run['status'] = 'DATA_BLOCKED'; self.refresh_run(); self.result = {'status': 'DATA_BLOCKED', 'engine_called': False}
        self.assertEqual(self.load()['diagnostic'], self.result)
    def test_engine_run_no_trades_preserved(self):
        self.run.update(status='RUN_NO_TRADES', engine_called=True); self.refresh_run(); self.result = {'status': 'RUN_NO_TRADES', 'engine_called': True, 'fills': []}
        self.assertEqual(self.load()['diagnostic']['fills'], [])
    def test_engine_state_conflict(self):
        self.result = {'status': self.run['status'], 'engine_called': True}; self.error('GATEWAY_ENGINE_STATE_CONFLICT')
    def test_engine_called_missing_result(self):
        self.run['engine_called'] = True; self.refresh_run(); self.error('GATEWAY_ENGINE_STATE_CONFLICT')
    def test_code_scope(self):
        self.registry['code_pins']['unexpected.py'] = 'sha256:x'; self.write_registry(); self.error('GATEWAY_CODE_SCOPE')
    def test_changed_code_before_verifier(self):
        (self.root / CODE_PATHS[0]).write_text('CHANGED'); self.error('GATEWAY_CODE_PIN_MISMATCH'); self.assertEqual(self.calls, [])
    def test_changed_run_bytes(self):
        (self.folder / 'Run.json').write_text('{}'); self.error('GATEWAY_RUN_PIN_MISMATCH')
    def test_run_scope(self):
        self.registry['run_directory'] = str(self.base / 'elsewhere'); self.write_registry(); self.error('GATEWAY_RUN_SCOPE')
    def test_run_symlink(self):
        alias = self.archive / 'runs/ALIAS'; alias.symlink_to(self.folder, target_is_directory=True)
        self.registry['run_directory'] = str(alias); self.write_registry(); self.error('UNSAFE_PATH')
    def test_capture_scope(self):
        self.run['capture_dir'] = str(self.archive / 'baostock-other'); self.refresh_run(); self.error('GATEWAY_CAPTURE_SCOPE')
    def test_capture_symlink(self):
        alias = self.archive / 'capture-alias'; alias.symlink_to(self.capture, target_is_directory=True)
        self.run['capture_dir'] = str(alias); self.refresh_run(); self.error('UNSAFE_PATH')
    def test_current_observation_cannot_become_proven_pit(self):
        self.run['historical_visibility_proven'] = True; self.refresh_run(); self.error('GATEWAY_BOUNDARY_MISMATCH')
    def test_wrong_run_version(self):
        self.run['version'] = '2.0.0'; self.refresh_run(); self.error('GATEWAY_RUN_BINDING')
    def test_changed_policy_reference(self):
        self.run['protocol_hash'] = 'sha256:other'; self.refresh_run(); self.error('GATEWAY_POLICY_BINDING')
    def test_verifier_failure(self):
        self.stub.verify_existing = lambda _: (_ for _ in ()).throw(ValueError('RAW_PIN_MISMATCH'))
        self.error('GATEWAY_RECOMPUTATION_FAILED')
    def test_unknown_api_state(self):
        self.matrix[0]['state'] = 'MAGIC'; self.error('GATEWAY_API_MATRIX_INVALID')
    def test_uncalled_not_zero_rows(self):
        self.matrix[-1]['row_count'] = 0; self.error('GATEWAY_API_MATRIX_INVALID')
    def test_duplicate_matrix_identity(self):
        self.matrix.append(copy.deepcopy(self.matrix[0])); self.error('GATEWAY_API_MATRIX_DUPLICATE')
    def test_unapproved_params_not_exposed(self):
        self.matrix[0]['params']['token'] = 'SYNTHETIC'; self.error('GATEWAY_API_MATRIX_INVALID')
    def test_local_http_uses_new_verified_projection(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); server.reader = self.reader
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with patch('workbench.gateway_reader.load', side_effect=lambda _: self.load()):
                c = http.client.HTTPConnection('127.0.0.1', server.server_port); c.request('GET', '/api/state')
                r = c.getresponse(); self.assertEqual(r.status, 200); result = json.loads(r.read()); c.close()
                self.assertEqual(result['gateway_v3']['run'], self.run); self.assertIsNone(result['gateway_v3']['diagnostic'])
        finally: server.shutdown(); server.server_close(); thread.join()
