"""Owned store tests: exact bytes, captures, revisions and atomic rollback."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
import unittest

from backtest_5y.interface import canonical
from backtest_5y.maintenance import validate_records
from backtest_5y.store import EvidenceStore

PRIVATE = Path('/Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/maintenance')


def record(identity='p:2026-01-02', close='10.10', revision='r1'):
    return {'identity': identity, 'event_date': '2026-01-02',
            'published_at': None, 'first_visible_at': None, 'available_at': None,
            'revision_id': revision, 'fields': {'trade_date': '20260102', 'open': '10.00',
                'high': '11.00', 'low': '9.00', 'close': close, 'vol': '100'},
            'units': {'open': 'CNY_PER_SHARE', 'high': 'CNY_PER_SHARE',
                'low': 'CNY_PER_SHARE', 'close': 'CNY_PER_SHARE', 'vol': 'LOTS_100_SHARES'},
            'provenance': {'test_only': True, 'historical_visibility_proven': False}}


def batch(records=None, raw=b'\xef\xbb\xbfexact raw \x00 bytes\n', retrieved='2026-10-08T01:00:00+00:00'):
    return {'source': 'FIXTURE_PUBLIC', 'domain': 'PRICE', 'symbol': 'S',
            'request': {'start': '2026-01-01', 'end': '2026-01-10'},
            'retrieved_at': retrieved, 'raw_bytes': raw, 'source_url': 'https://fixture.invalid/raw',
            'records': [record()] if records is None else records,
            'license_state': 'FIXTURE_ONLY_NO_SOURCE_ADMISSION'}


class StoreTests(unittest.TestCase):
    def setUp(self):
        PRIVATE.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='store-fixture-', dir=PRIVATE)
        self.path = Path(self.temp.name) / 'capture.sqlite'
        self.store = EvidenceStore(self.path)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_exact_bytes_private_modes_and_repeated_capture_idempotent(self):
        b = batch()
        first = self.store.ingest(b)
        second = self.store.ingest(deepcopy(b))
        self.assertEqual(first['capture_id'], second['capture_id'])
        self.assertTrue(second['duplicate_capture'])
        self.assertEqual((second['new_record_count'], second['new_version_count']), (0, 0))
        self.assertEqual(second['total_captures'], 1)
        raw = Path(first['raw_ref'])
        self.assertEqual(raw.read_bytes(), b['raw_bytes'])
        self.assertEqual(first['raw_sha256'], sha256(b['raw_bytes']).hexdigest())
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(raw.stat().st_mode & 0o777, 0o600)
        self.assertEqual(raw.parent.stat().st_mode & 0o777, 0o700)
        stored = self.store.records()[0]
        self.assertEqual(stored['record_body'], b['records'][0])
        self.assertEqual(stored['fields_sha256'], sha256(canonical(b['records'][0]['fields'])).hexdigest())
        self.assertEqual(stored['units_sha256'], sha256(canonical(b['records'][0]['units'])).hexdigest())
        self.assertFalse(stored['source_admitted'])
        self.assertFalse(stored['historical_visibility_proven'])

    def test_new_capture_preserves_rows_with_content_deduplicated_blob_only(self):
        a = self.store.ingest(batch())
        b = self.store.ingest(batch(retrieved='2026-10-08T02:00:00+00:00'))
        self.assertNotEqual(a['capture_id'], b['capture_id'])
        self.assertEqual(a['raw_ref'], b['raw_ref'])
        self.assertEqual((b['total_captures'], b['total_record_count'], b['total_version_count']), (2, 2, 1))
        rows = self.store.records('PRICE', 'S')
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r['capture_id'] for r in rows}), 2)
        self.assertEqual(self.store.records(symbol='ABSENT'), [])
        self.assertEqual(self.store.summary()['actual_pit_admitted_records'], 0)

    def test_valid_same_revision_conflict_is_preserved_and_reported(self):
        self.store.ingest(batch())
        receipt = self.store.ingest(batch([record(close='10.20')], raw=b'revised raw'))
        self.assertEqual(receipt['total_version_count'], 2)
        self.assertEqual([r['fields']['close'] for r in self.store.records()], ['10.10', '10.20'])
        dq = validate_records(self.store.records())
        self.assertEqual(dq['error_count'], 0)
        self.assertEqual(dq['state'], 'VERSION_CONFLICT')
        self.assertEqual(dq['conflicts'][0]['code'], 'SAME_REVISION_CONFLICT')

    def test_empty_attempt_preserved_and_exact_repeat_not_recounted(self):
        receipt = self.store.ingest(batch([], raw=b'{"items":[]}'))
        self.assertTrue(receipt['new_capture'])
        self.assertEqual(receipt['empty_capture_count'], 1)
        self.assertEqual(receipt['new_record_count'], 0)
        repeat = self.store.ingest(batch([], raw=b'{"items":[]}'))
        self.assertTrue(repeat['duplicate_capture'])
        self.assertEqual(repeat['empty_capture_count'], 1)
        self.assertEqual(self.store.records(), [])

    def test_malformed_numeric_rejects_entire_batch_without_raw_or_rows(self):
        bad = record('bad')
        bad['fields']['close'] = 'not-a-number'
        with self.assertRaisesRegex(ValueError, 'INVALID_BATCH_RECORDS'):
            self.store.ingest(batch([record(), bad]))
        self.assertEqual(self.store.summary()['total_captures'], 0)
        self.assertEqual(list(self.store.raw_dir.iterdir()), [])

    def test_sqlite_failure_rolls_back_batch_and_new_blob_only(self):
        self.store.ingest(batch())
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TRIGGER reject_boom BEFORE INSERT ON record_versions "
                       "WHEN NEW.identity='boom' BEGIN SELECT RAISE(ABORT,'test reject'); END")
        old_files = set(self.store.raw_dir.iterdir())
        with self.assertRaisesRegex(sqlite3.IntegrityError, 'test reject'):
            self.store.ingest(batch([record('first'), record('boom')], raw=b'atomic failed batch'))
        self.assertEqual(self.store.summary()['total_captures'], 1)
        self.assertEqual(self.store.summary()['total_record_count'], 1)
        self.assertEqual(self.store.summary()['total_version_count'], 1)
        self.assertEqual(set(self.store.raw_dir.iterdir()), old_files)

    def test_append_only_triggers_and_raw_tamper_detection(self):
        receipt = self.store.ingest(batch())
        with sqlite3.connect(self.path) as db:
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'APPEND_ONLY'):
                db.execute("UPDATE captures SET license_state='ADMITTED'")
            with self.assertRaisesRegex(sqlite3.IntegrityError, 'APPEND_ONLY'):
                db.execute('DELETE FROM captured_records')
        Path(receipt['raw_ref']).write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError, 'RAW_CONTENT_HASH_CONFLICT_STOP'):
            self.store.ingest(batch())
        self.assertEqual(self.store.summary()['total_captures'], 1)

    def test_reopen_and_admission_claim_stays_original_evidence_only(self):
        rec = record()
        rec['historical_visibility_proven'] = True
        rec['source_admitted'] = True
        self.store.ingest(batch([rec]))
        with EvidenceStore(self.path) as reopened:
            row = reopened.records()[0]
            self.assertTrue(row['record_body']['source_admitted'])
            self.assertFalse(row['source_admitted'])
            self.assertFalse(row['historical_visibility_proven'])

    def test_reaudit_bound_blob_hash_record_and_empty_capture_integrity(self):
        receipt = self.store.ingest(batch())
        self.store.ingest(batch([], raw=b'empty capture'))
        good = self.store.audit_raw()
        self.assertEqual(good['state'], 'PASS_INTEGRITY_ONLY')
        self.assertEqual(good['checked_blobs'], 2)
        self.assertEqual(good['checked_record_versions'], 1)
        Path(receipt['raw_ref']).write_bytes(b'changed after ingestion')
        failed = self.store.audit_raw()
        self.assertEqual(failed['state'], 'FAIL_INTEGRITY_STOP')
        self.assertEqual(failed['failures'][0]['reason'], 'RAW_CONTENT_HASH_CONFLICT_STOP')
        self.assertFalse(failed['source_admitted'])


if __name__ == '__main__':
    unittest.main()
