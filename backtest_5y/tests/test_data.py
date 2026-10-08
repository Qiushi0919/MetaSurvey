"""Synthetic binding cases; they are never market evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from backtest_5y.data import batches_from_inputs, iso_day
from backtest_5y.interface import SYMBOLS, digest
from backtest_5y.collectors import PRIVATE_ROOT


class ExistingDataTests(unittest.TestCase):
    def setUp(self):
        PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-data-test-', dir=PRIVATE_ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, values=None, excluded=False, raw_value='100.10', name='income.response.json'):
        raw = json.dumps({'data': {'fields': ['ts_code', 'end_date', 'report_type', 'comp_type', 'revenue', 'unprojected'],
                                  'items': [[SYMBOLS[0], '20240331', '1', '1', raw_value, 'retained']]}}).encode()
        path = self.root / name
        path.write_bytes(raw)
        source = {'raw_sha256': 'sha256:' + digest(raw), 'row_ordinal': 0,
                  'request_id': name.removesuffix('.response.json'), 'request_fingerprint': 'sha256:SYNTHETIC',
                  'retrieved_at': '2026-10-08T00:00:01Z', 'available_at': '2026-10-08T00:00:01Z',
                  'published_at': None}
        entry = {'api_name': 'income', 'source_ref': source}
        if excluded:
            entry['reason_code'] = 'WHOLE_RESPONSE_DQ_BLOCKED'
        else:
            entry['values'] = values or {'ts_code': SYMBOLS[0], 'end_date': '20240331', 'revenue': raw_value}
        inputs = {s: {} for s in SYMBOLS}
        inputs[SYMBOLS[0]] = {'wave-d_input': {'body': {'excluded' if excluded else 'observations': [entry]}}}
        return inputs, [{'path': str(path), 'bytes': len(raw), 'sha256': source['raw_sha256']}]

    def test_full_raw_fields_and_no_retrieval_visibility(self):
        batches = batches_from_inputs(*self.fixture())
        rec = batches[0]['records'][0]
        self.assertEqual(rec['fields']['unprojected'], 'retained')
        self.assertEqual(rec['fields']['revenue'], '100.10')
        self.assertEqual(rec['event_date'], '2024-03-31')
        self.assertIsNone(rec['first_visible_at'])
        self.assertIsNone(rec['available_at'])
        self.assertIsNone(rec['revision_id'])
        self.assertEqual(rec['provenance']['current_available_at'], '2026-10-08T00:00:01Z')

    def test_legacy_excluded_import_preserves_failure(self):
        rec = batches_from_inputs(*self.fixture(excluded=True))[0]['records'][0]
        self.assertEqual(rec['provenance']['legacy_exclusion_reasons'], ['WHOLE_RESPONSE_DQ_BLOCKED'])
        self.assertTrue(rec['provenance']['quarantined'])
        self.assertFalse(rec['provenance']['historical_visibility_proven'])

    def test_raw_hash_change_stops(self):
        inputs, refs = self.fixture()
        Path(refs[0]['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'HASH_CONFLICT'):
            batches_from_inputs(inputs, refs)

    def test_projected_row_conflict_stops(self):
        with self.assertRaisesRegex(ValueError, 'ROW_CONFLICT'):
            batches_from_inputs(*self.fixture(values={'revenue': '999'}))

    def test_ordinal_outside_raw_stops(self):
        inputs, refs = self.fixture()
        inputs[SYMBOLS[0]]['wave-d_input']['body']['observations'][0]['source_ref']['row_ordinal'] = 3
        with self.assertRaisesRegex(ValueError, 'ROW_ORDINAL'):
            batches_from_inputs(inputs, refs)

    def test_raw_versions_same_logical_identity_retained(self):
        inputs1, refs1 = self.fixture(name='v1.response.json')
        inputs2, refs2 = self.fixture(raw_value='101.20', name='v2.response.json')
        inputs1[SYMBOLS[0]]['wave-d_input']['body']['observations'].extend(
            inputs2[SYMBOLS[0]]['wave-d_input']['body']['observations'])
        batches = batches_from_inputs(inputs1, refs1 + refs2)
        records = [b['records'][0] for b in batches]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]['identity'], records[1]['identity'])
        self.assertNotEqual(records[0]['provenance']['raw_sha256'], records[1]['provenance']['raw_sha256'])

    def test_date_only_never_becomes_midnight(self):
        self.assertEqual(iso_day('20240331'), '2024-03-31')
        self.assertIsNone(iso_day('2024-03-31T00:00:00Z'))
        self.assertIsNone(iso_day('20240230'))


if __name__ == '__main__':
    unittest.main()
