"""Synthetic reader-boundary tests; no SDK, market archives or credentials.

The runner is stubbed: actual build/provenance/engine replay belongs to runner
integration tests. Research arithmetic uses its real pure evaluator here.
"""
import copy
import hashlib
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
from workbench.history_reader import load, CODE_PATHS, RESEARCH_CODE, RESEARCH_METHOD, SYMBOLS
from tools.e2e_history.research_factors import evaluate, seal


class HistoryReaderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / 'repo'; self.root.mkdir()
        self.archive = self.base / 'SYNTHETIC_ARCHIVE'; self.archive.mkdir()
        self.old = self.base / 'SYNTHETIC_OLD_DATA'; self.old.mkdir()
        self.run_dir = self.archive / 'runs/synthetic-run-01'; self.run_dir.mkdir(parents=True)
        self.capture = self.archive / 'baostock-synthetic'; self.capture.mkdir()
        self.reader = Reader(self.root, self.archive)
        scope = patch.dict(FILES, {'history-registry': 'docs/e2e-history-v2/Registry.json'})
        scope.start(); self.addCleanup(scope.stop)
        for name in (*CODE_PATHS, RESEARCH_CODE): self.write(self.root / name, 'SYNTHETIC CODE\n', raw=True)
        self.write(self.root / 'docs/e2e-history-v2/Source-Policy.json', {'raw_document_root': str(self.archive / 'source-review')})
        self.method = {'frozen_at': '2026-10-14T08:00:00+00:00'}
        self.write(self.root / RESEARCH_METHOD, self.method)
        self.pins = {name: self.hash(self.root / name) for name in CODE_PATHS}
        self.run = {'kind': 'HistoricalDiagnosticRun', 'version': '2.0.0', 'run_id': self.run_dir.name,
                    'recorded_at': '2026-10-14T09:00:00+00:00', 'capture_dir': str(self.capture),
                    'code_pins': self.pins, 'engine_called': False, 'status': 'SOURCE_OR_INPUT_BLOCKED'}
        for field, name in [('protocol_hash', 'experiments/e2e_history_v2/protocol.json'),
                            ('input_policy_hash', 'experiments/e2e_history_v2/input-policy.json'),
                            ('source_policy_hash', 'docs/e2e-history-v2/Source-Policy.json')]:
            self.run[field] = self.pins[name]
        self.prior = {'sources': []}
        for symbol in SYMBOLS:
            path = self.old / (symbol + '-2025.pdf'); path.write_bytes(b'%PDF-SYNTHETIC\x00\xff')
            self.prior['sources'].append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size})
        self.write(self.old / 'Financial-Inputs.json', self.prior)
        self.inputs = {'kind': 'E2ENewResearchFactorInputs', 'version': '1.0.0', 'productionGate': False,
                       'historical_visibility_proven': False, 'recorded_at': '2026-10-14T09:00:00+00:00',
                       'method_frozen_at': self.method['frozen_at'], 'method_hash': self.hash(self.root / RESEARCH_METHOD),
                       'prior_inputs_path': str(self.old / 'Financial-Inputs.json'), 'prior_inputs_hash': self.hash(self.old / 'Financial-Inputs.json'),
                       'source_files': [{**x, 'sha256': 'sha256:' + x['sha256']} for x in self.prior['sources']],
                       'companies': [{'symbol': 'SYNTHETIC', 'name': 'SYNTHETIC',
                                      'business': {'state': 'UNKNOWN', 'reason': 'SYNTHETIC_MISSING'},
                                      'concentration': {'state': 'UNKNOWN', 'reason': 'SYNTHETIC_MISSING'},
                                      'audit_opinion': {'state': 'UNKNOWN'}}]}
        self.inputs['content_hash'] = seal(self.inputs)
        self.research = evaluate(self.inputs)
        self.registry = {'kind': 'E2EHistoryRegistry', 'version': '1.0.0', 'run_directory': str(self.run_dir),
                         'code_pins': self.pins, 'research': {}}
        self.refresh_research(); self.refresh_run()
        self.report = {'kind': 'HistoricalInputBuild', 'status': 'DATA_BLOCKED', 'errors': ['SYNTHETIC_MISSING'], 'raw_bars': ['DO_NOT_EXPOSE']}
        self.result = None
        self.calls = []
        stub = types.ModuleType('tools.e2e_history.run')
        def verify(directory):
            self.calls.append(directory)
            return {'run': copy.deepcopy(self.run), 'build_report': copy.deepcopy(self.report), 'engine_result': copy.deepcopy(self.result)}
        stub.verify_existing = verify; self.stub = stub
        modules = patch.dict(sys.modules, {'tools.e2e_history.run': stub})
        modules.start(); self.addCleanup(modules.stop)

    def write(self, path, value, raw=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if raw else json.dumps(value))

    def hash(self, path): return digest(path.read_bytes())
    def write_registry(self): self.write(self.root / FILES['history-registry'], self.registry)
    def refresh_run(self):
        self.write(self.run_dir / 'Run.json', self.run)
        self.registry['run_sha256'] = self.hash(self.run_dir / 'Run.json'); self.write_registry()
    def refresh_research(self):
        a = self.archive / 'research/Research-Factor-Inputs.json'; b = self.archive / 'research/Research-Factors.json'
        self.write(a, self.inputs); self.write(b, self.research)
        self.registry['research'] = {'input_path': str(a), 'input_sha256': self.hash(a), 'result_path': str(b), 'result_sha256': self.hash(b),
                                     'code_sha256': self.hash(self.root / RESEARCH_CODE), 'method_sha256': self.hash(self.root / RESEARCH_METHOD)}
        self.write_registry()
    def load(self): return load(self.reader, archive=self.archive, old_data=self.old)
    def error(self, code):
        with self.assertRaises(ReadError) as caught: self.load()
        self.assertEqual(caught.exception.code, code)

    def test_source_blocked_read_only_and_no_raw_bars(self):
        before = {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        result = self.load()
        self.assertFalse(result['run']['engine_called']); self.assertIsNone(result['diagnostic'])
        self.assertNotIn('raw_bars', result['build_report'])
        self.assertIsNone(result['research']['companies'][0]['complete_seven_factor_score'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file()})

    def test_legitimate_engine_preflight_blocked_result(self):
        self.run['status'] = 'DATA_BLOCKED'; self.refresh_run()
        self.result = {'status': 'DATA_BLOCKED', 'engine_called': False, 'errors': ['SYNTHETIC_PREFLIGHT']}
        self.assertEqual(self.load()['diagnostic'], self.result)

    def test_legitimate_engine_called_no_trades(self):
        self.run.update(status='NO_TRADES', engine_called=True); self.refresh_run()
        self.result = {'status': 'NO_TRADES', 'engine_called': True, 'fills': [], 'ledger': []}
        self.assertEqual(self.load()['diagnostic']['fills'], [])

    def test_engine_claim_conflict(self):
        self.result = {'status': self.run['status'], 'engine_called': True}
        self.error('HISTORY_ENGINE_STATE_CONFLICT')

    def test_engine_called_missing_result(self):
        self.run['engine_called'] = True; self.refresh_run(); self.error('HISTORY_ENGINE_STATE_CONFLICT')

    def test_changed_code_rejected_before_import(self):
        self.write(self.root / CODE_PATHS[0], 'CHANGED', raw=True)
        self.error('HISTORY_PIN_MISMATCH'); self.assertEqual(self.calls, [])

    def test_extra_code_scope(self):
        self.registry['code_pins']['bad.py'] = 'sha256:x'; self.write_registry(); self.error('HISTORY_CODE_SCOPE')

    def test_run_outside_scope(self):
        self.registry['run_directory'] = str(self.base / 'arbitrary'); self.write_registry(); self.error('HISTORY_RUN_SCOPE')

    def test_run_symlink(self):
        alias = self.archive / 'runs/alias'; alias.symlink_to(self.run_dir, target_is_directory=True)
        self.registry['run_directory'] = str(alias); self.write_registry(); self.error('UNSAFE_PATH')

    def test_capture_outside_scope(self):
        self.run['capture_dir'] = str(self.base / 'baostock-outside'); self.refresh_run(); self.error('HISTORY_CAPTURE_SCOPE')

    def test_changed_run_identity(self):
        self.run['run_id'] = 'different'; self.refresh_run(); self.error('HISTORY_RUN_BINDING')

    def test_runner_recomputation_error(self):
        self.stub.verify_existing = lambda _: (_ for _ in ()).throw(ValueError('BROKEN_PROVENANCE'))
        self.error('HISTORY_RECOMPUTATION_FAILED')

    def test_research_recomputation_rejects_resealed_result(self):
        self.research['companies'][0]['complete_seven_factor_score'] = '90'
        self.research['content_hash'] = seal(self.research); self.refresh_research()
        self.error('HISTORY_RESEARCH_RECOMPUTATION_FAILED')

    def test_research_external_path(self):
        self.registry['research']['input_path'] = str(self.base / 'outside.json'); self.write_registry(); self.error('HISTORY_RESEARCH_SCOPE')

    def test_changed_original_rejected(self):
        (self.old / '603228-2025.pdf').write_bytes(b'CHANGED')
        self.error('HISTORY_RESEARCH_ORIGINAL_BINDING')

    def test_missing_original_rejected(self):
        (self.old / '603228-2025.pdf').unlink(); self.error('FILE_MISSING')

    def test_original_symlink_rejected(self):
        target = self.old / '603228-2025.pdf'; target.unlink(); target.symlink_to(self.old / '002463-2025.pdf')
        self.error('UNSAFE_PATH')

    def test_duplicate_original_list_rejected(self):
        self.inputs['source_files'][-1] = self.inputs['source_files'][0]
        self.refresh_research(); self.error('HISTORY_RESEARCH_ORIGINAL_SCOPE')

    def test_malformed_prior_fails_safely(self):
        self.write(self.old / 'Financial-Inputs.json', [])
        self.inputs['prior_inputs_hash'] = self.hash(self.old / 'Financial-Inputs.json')
        self.refresh_research(); self.error('HISTORY_RESEARCH_ORIGINAL_BINDING')

    def test_malformed_method_fails_safely(self):
        self.write(self.root / RESEARCH_METHOD, [])
        self.refresh_research(); self.error('HISTORY_RESEARCH_BINDING')

    def test_local_http_projects_verified_fields_without_writes(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); server.reader = self.reader
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        before = {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        try:
            with patch('workbench.history_reader.load', side_effect=lambda _: self.load()):
                c = http.client.HTTPConnection('127.0.0.1', server.server_port)
                c.request('GET', '/api/state'); response = c.getresponse()
                self.assertEqual(response.status, 200); state = json.loads(response.read()); c.close()
                self.assertEqual(state['history_v2']['run'], self.run)
                self.assertEqual(state['history_v2']['research'], self.research)
                self.assertNotIn('raw_bars', state['history_v2']['build_report'])
            self.assertEqual(before, {str(p): p.read_bytes() for p in self.base.rglob('*') if p.is_file()})
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_local_http_post_cannot_run_verifier(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); server.reader = self.reader
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            c = http.client.HTTPConnection('127.0.0.1', server.server_port)
            c.request('POST', '/api/state'); response = c.getresponse()
            self.assertEqual(response.status, 405); response.read(); c.close()
            self.assertEqual(self.calls, [])
        finally:
            server.shutdown(); server.server_close(); thread.join()
