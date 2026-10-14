"""Synthetic temporary files only; never read production archives or credentials."""
import copy
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from workbench.server import Reader, ReadError, FILES, digest
from workbench.e2e_reader import load, CODE, SOURCE_NAMES


class E2EReaderTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name).resolve()
        self.root = self.base / 'repo'
        self.archive = self.base / 'SYNTHETIC_ARCHIVE'
        self.root.mkdir()
        self.archive.mkdir()
        self.reader = Reader(self.root, self.archive)
        scope = patch.dict(FILES, {'e2e-registry': 'docs/e2e-pilot-v1/Registry.json'})
        scope.start()
        self.addCleanup(scope.stop)
        for relative in CODE:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('SYNTHETIC CODE PIN\n')
        self.inputs = {'kind': 'SYNTHETIC_NOT_MARKET_DATA', 'facts': [], 'sources': []}
        self.case = {'kind': 'SYNTHETIC_NOT_MARKET_DATA', 'bars': []}
        self.audit = {'kind': 'SYNTHETIC_COVERAGE_AUDIT', 'actual_sessions': 0}
        for name in SOURCE_NAMES:
            path = self.archive / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == '.pdf':
                path.write_bytes(b'%PDF-SYNTHETIC-NOT-MARKET-DATA\x00\xff')
            else:
                value = self.inputs if path.name == 'Financial-Inputs.json' else self.audit if path.name == 'Historical-Coverage-Audit.json' else self.case
                path.write_text(json.dumps(value))
        for name in SOURCE_NAMES:
            path = self.archive / name
            if path.suffix != '.pdf':
                continue
            self.inputs['sources'].append({
                'symbol': path.name.split('-')[0], 'path': str(path),
                'sha256': digest(path.read_bytes()).removeprefix('sha256:'),
                'bytes': path.stat().st_size, 'url': 'https://example.invalid/synthetic.pdf',
                'final_url': 'https://example.invalid/synthetic.pdf',
                'retrieved_at': '2026-10-14T08:00:00+00:00',
                'available_at': '2026-10-14T08:00:00+00:00'})
        self.captures = copy.deepcopy(self.inputs['sources'])
        (self.archive / 'data/Financial-Inputs.json').write_text(json.dumps(self.inputs))
        (self.archive / 'data/Official-Disclosure-Captures.json').write_text(json.dumps(self.captures))
        self.pins = [{'path': str(self.archive / name),
                      'sha256': digest((self.archive / name).read_bytes()),
                      'bytes': (self.archive / name).stat().st_size}
                     for name in SOURCE_NAMES]
        self.package = {'source_pins': self.pins, 'content_hash': 'SYNTHETIC_HASH',
                        'financial_inputs': self.inputs, 'diagnostic_case': self.case,
                        'historical_coverage_audit': self.audit,
                        'financial_inputs_sha256': self.pins[0]['sha256'],
                        'historical_coverage_audit_sha256': self.pins[-2]['sha256'],
                        'diagnostic_case_sha256': self.pins[-1]['sha256']}
        self.package_path = self.archive / 'Run.json'
        self.package_path.write_text(json.dumps(self.package))
        self.registry = {'kind': 'E2EPilotRegistry', 'version': '1.0.0',
                         'package_path': str(self.package_path),
                         'package_sha256': digest(self.package_path.read_bytes()),
                         'package_content_hash': self.package['content_hash'],
                         'source_pins': self.pins,
                         'code_pins': {p: digest((self.root / p).read_bytes()) for p in CODE}}
        self.write_registry()
        self.calls = []

        def validate(package, root):
            self.calls.append((copy.deepcopy(package), root))
            return {'experiment_id': 'SYNTHETIC_READER_TEST', 'sectors': [],
                    'companies': [], 'diagnostic': {'state': 'DATA_BLOCKED', 'engine_called': False}}

        # This suite tests the reader trust boundary, not the research calculator.
        # The calculator's real graph/recomputation tests live in its own suite.
        stub = types.ModuleType('experiments.e2e_pilot_v1.research')
        stub.validate_run = validate
        self.stub = stub
        module = patch.dict(sys.modules, {'experiments.e2e_pilot_v1.research': stub})
        module.start()
        self.addCleanup(module.stop)

    def write_registry(self):
        path = self.root / FILES['e2e-registry']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.registry))

    def write_package(self):
        self.package_path.write_text(json.dumps(self.package))
        self.registry['package_sha256'] = digest(self.package_path.read_bytes())
        self.write_registry()

    def repin_source(self, name, value):
        """Deliberately update outer hashes to test semantic cross-binding."""
        path = self.archive / name
        path.write_text(json.dumps(value))
        pin = next(row for row in self.pins if row['path'] == str(path))
        pin.update(sha256=digest(path.read_bytes()), bytes=path.stat().st_size)
        if name == 'data/Financial-Inputs.json':
            self.package['financial_inputs'] = value
            self.package['financial_inputs_sha256'] = pin['sha256']
        self.write_package()

    def read(self):
        return load(self.reader, self.archive)

    def reject(self, reason):
        with self.assertRaises(ReadError) as caught:
            self.read()
        self.assertEqual(reason, caught.exception.code)

    def test_only_validator_projection_is_exposed(self):
        value = self.read()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1], self.root)
        self.assertEqual(value['diagnostic']['state'], 'DATA_BLOCKED')
        self.assertNotIn('financial_inputs', value)
        self.assertNotIn('source_pins', value)
        self.assertNotIn('content_hash', value)

    def test_changed_pdf_blocks_before_calculator(self):
        (self.archive / SOURCE_NAMES[2]).write_bytes(b'%PDF-changed')
        self.reject('E2E_PIN_MISMATCH')
        self.assertEqual(self.calls, [])

    def test_binary_pdf_hashing_does_not_require_utf8(self):
        self.assertEqual(self.read()['integrity'], 'PINNED_FILES_AND_RECOMPUTED_EXPERIMENT_MATCH')

    def test_source_json_change_blocks(self):
        (self.archive / SOURCE_NAMES[0]).write_text('{}')
        self.reject('E2E_PIN_MISMATCH')

    def test_missing_pdf_blocks(self):
        (self.archive / SOURCE_NAMES[2]).unlink()
        self.reject('FILE_MISSING')

    def test_pdf_symlink_blocks_even_with_matching_bytes(self):
        path = self.archive / SOURCE_NAMES[2]
        path.unlink()
        path.symlink_to(self.archive / SOURCE_NAMES[3])
        self.reject('UNSAFE_PATH')

    def test_registry_cannot_choose_other_source(self):
        self.registry['source_pins'][0]['path'] = '/tmp/not-allowed'
        self.write_registry()
        self.reject('E2E_SOURCE_SCOPE')

    def test_duplicate_source_pin_blocks(self):
        self.registry['source_pins'].append(self.registry['source_pins'][0])
        self.write_registry()
        self.reject('E2E_SOURCE_SCOPE')

    def test_registry_cannot_choose_other_package(self):
        self.registry['package_path'] = '/tmp/other.json'
        self.write_registry()
        self.reject('E2E_REGISTRY_SCOPE')

    def test_missing_code_pin_blocks(self):
        self.registry['code_pins'].pop(CODE[0])
        self.write_registry()
        self.reject('E2E_REGISTRY_SCOPE')

    def test_changed_code_blocks(self):
        (self.root / CODE[0]).write_text('changed')
        self.reject('E2E_PIN_MISMATCH')

    def test_unknown_registry_version_blocks(self):
        self.registry['version'] = '99'
        self.write_registry()
        self.reject('UNSUPPORTED_VERSION')

    def test_changed_package_blocks(self):
        self.package_path.write_text('{}')
        self.reject('E2E_PIN_MISMATCH')

    def test_rehashed_wrong_input_binding_blocks(self):
        self.package['financial_inputs'] = {'facts': ['invented']}
        self.write_package()
        self.reject('E2E_EVIDENCE_BINDING')

    def test_rehashed_wrong_diagnostic_binding_blocks(self):
        self.package['diagnostic_case'] = {'bars': ['invented']}
        self.write_package()
        self.reject('E2E_EVIDENCE_BINDING')

    def test_calculator_rejection_cannot_become_display(self):
        def reject(*args, **kwargs):
            raise ValueError('recomputation mismatch')
        self.stub.validate_run = reject
        self.reject('E2E_VALIDATION_FAILED')

    def test_rehashed_wrong_pdf_reference_blocks(self):
        self.inputs['sources'][0]['sha256'] = '0' * 64
        self.repin_source('data/Financial-Inputs.json', self.inputs)
        self.reject('E2E_SOURCE_CROSS_BINDING')

    def test_rehashed_capture_clock_disagreement_blocks(self):
        self.captures[0]['retrieved_at'] = '2026-10-13T08:00:00+00:00'
        self.repin_source('data/Official-Disclosure-Captures.json', self.captures)
        self.reject('E2E_SOURCE_CROSS_BINDING')

    def test_rehashed_capture_url_disagreement_blocks(self):
        self.captures[0]['url'] = 'https://example.invalid/other.pdf'
        self.repin_source('data/Official-Disclosure-Captures.json', self.captures)
        self.reject('E2E_SOURCE_CROSS_BINDING')

    def test_rehashed_matching_but_false_pdf_size_blocks(self):
        self.inputs['sources'][0]['bytes'] += 1
        self.captures[0]['bytes'] += 1
        self.repin_source('data/Financial-Inputs.json', self.inputs)
        self.repin_source('data/Official-Disclosure-Captures.json', self.captures)
        self.reject('E2E_SOURCE_CROSS_BINDING')

    def test_duplicate_capture_identity_blocks(self):
        self.captures[-1] = copy.deepcopy(self.captures[0])
        self.repin_source('data/Official-Disclosure-Captures.json', self.captures)
        self.reject('E2E_SOURCE_CROSS_BINDING')

    def test_rehashed_wrong_coverage_audit_binding_blocks(self):
        self.package['historical_coverage_audit'] = {'actual_sessions': 999}
        self.write_package()
        self.reject('E2E_EVIDENCE_BINDING')

    def test_read_preserves_all_files(self):
        files = [p for p in self.base.rglob('*') if p.is_file()]
        before = {p: digest(p.read_bytes()) for p in files}
        self.read()
        self.assertEqual(before, {p: digest(p.read_bytes()) for p in files})
