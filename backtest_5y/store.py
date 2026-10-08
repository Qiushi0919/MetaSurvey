"""Append-only SQLite capture evidence with exact content-addressed raw bytes.

Current retrieval, repeated captures and vendor revisions remain separate. This
store does not promote any source to historical PIT or trading admission.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import stat

from .interface import LABELS, canonical, digest
from .maintenance import _clock, validate_records

VERSION = '1.0.0-sidecar-only'
SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE captures (
  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
  capture_id TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL, domain TEXT NOT NULL, symbol TEXT NOT NULL,
  request_json TEXT NOT NULL, retrieved_at TEXT NOT NULL,
  source_url TEXT NOT NULL, license_state TEXT NOT NULL,
  raw_sha256 TEXT NOT NULL, raw_ref TEXT NOT NULL,
  records_sha256 TEXT NOT NULL, record_count INTEGER NOT NULL
);
CREATE TABLE record_versions (
  source TEXT NOT NULL, domain TEXT NOT NULL, symbol TEXT NOT NULL,
  record_sha256 TEXT NOT NULL, identity TEXT NOT NULL, event_date TEXT,
  revision_id TEXT, fields_sha256 TEXT NOT NULL, units_sha256 TEXT NOT NULL,
  record_json TEXT NOT NULL,
  PRIMARY KEY(source, domain, symbol, record_sha256)
);
CREATE TABLE captured_records (
  capture_id TEXT NOT NULL REFERENCES captures(capture_id),
  row_ordinal INTEGER NOT NULL,
  source TEXT NOT NULL, domain TEXT NOT NULL, symbol TEXT NOT NULL,
  record_sha256 TEXT NOT NULL,
  PRIMARY KEY(capture_id,row_ordinal),
  FOREIGN KEY(source,domain,symbol,record_sha256)
    REFERENCES record_versions(source,domain,symbol,record_sha256)
);
CREATE INDEX captured_domain_symbol ON captured_records(domain,symbol);
CREATE TRIGGER captures_no_update BEFORE UPDATE ON captures BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER captures_no_delete BEFORE DELETE ON captures BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER versions_no_update BEFORE UPDATE ON record_versions BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER versions_no_delete BEFORE DELETE ON record_versions BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER records_no_update BEFORE UPDATE ON captured_records BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER records_no_delete BEFORE DELETE ON captured_records BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
PRAGMA user_version=1;
"""


def _private_file(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
        raise ValueError('EVIDENCE_FILE_NOT_PRIVATE_REGULAR_0600')


class EvidenceStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path).absolute()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            fd = os.open(self.db_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            created = True
        except FileExistsError:
            pass
        _private_file(self.db_path)
        self.raw_dir = self.db_path.with_name(self.db_path.name + '.raw')
        try:
            self.raw_dir.mkdir(mode=0o700)
        except FileExistsError:
            info = self.raw_dir.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
                raise ValueError('RAW_DIRECTORY_NOT_PRIVATE_REGULAR_0700')
        self._db = sqlite3.connect(str(self.db_path), timeout=30, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute('PRAGMA foreign_keys=ON')
        self._db.execute('PRAGMA journal_mode=DELETE')
        self._db.execute('PRAGMA synchronous=FULL')
        try:
            if created:
                self._db.executescript('BEGIN IMMEDIATE;\n' + _SCHEMA + '\nCOMMIT;')
            elif self._db.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
                raise ValueError('STORE_SCHEMA_NOT_SUPPORTED_NO_AUTO_MIGRATION')
            names = {row[0] for row in self._db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'captures', 'record_versions', 'captured_records'} <= names:
                raise ValueError('STORE_SCHEMA_MISSING')
        except BaseException:
            self._db.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def close(self):
        self._db.close()

    def _counts(self):
        return {
            'total_captures': self._db.execute('SELECT count(*) FROM captures').fetchone()[0],
            'total_record_count': self._db.execute('SELECT count(*) FROM captured_records').fetchone()[0],
            'total_version_count': self._db.execute('SELECT count(*) FROM record_versions').fetchone()[0],
            'empty_capture_count': self._db.execute('SELECT count(*) FROM captures WHERE record_count=0').fetchone()[0],
        }

    def summary(self):
        rows = [dict(row) for row in self._db.execute(
            'SELECT source,domain,symbol,count(*) AS captures,sum(record_count) AS captured_rows '
            'FROM captures GROUP BY source,domain,symbol ORDER BY source,domain,symbol')]
        return {'version': VERSION, **self._counts(), 'domains': rows,
                'labels': list(LABELS), 'actual_pit_admitted_records': 0,
                'historical_visibility_proven': False, 'source_admitted': False,
                'productionGate': False}

    def audit_raw(self):
        """Re-read all capture-bound blobs and verify byte hashes and record hashes.

        An audit is evidence integrity only; a good hash cannot prove historical
        availability, provider rights, financial definitions, or source admission.
        """
        checked, failures = [], []
        blobs = self._db.execute('SELECT DISTINCT raw_sha256,raw_ref FROM captures ORDER BY raw_sha256').fetchall()
        for row in blobs:
            path = Path(row['raw_ref'])
            try:
                if path != self.raw_dir / (row['raw_sha256']+'.raw'):
                    raise ValueError('RAW_REFERENCE_OUTSIDE_CONTENT_ADDRESS')
                _private_file(path)
                raw = path.read_bytes()
                observed = digest(raw)
                if observed != row['raw_sha256']:
                    raise ValueError('RAW_CONTENT_HASH_CONFLICT_STOP')
                checked.append({'raw_sha256': observed, 'raw_ref': str(path), 'bytes': len(raw)})
            except (OSError, ValueError) as exc:
                failures.append({'raw_sha256': row['raw_sha256'], 'raw_ref': str(path), 'reason': str(exc)})
        records_checked = 0
        for row in self._db.execute('SELECT record_sha256,fields_sha256,units_sha256,record_json FROM record_versions'):
            try:
                record = json.loads(row['record_json'])
                if digest(canonical(record)) != row['record_sha256'] or \
                   digest(canonical(record['fields'])) != row['fields_sha256'] or \
                   digest(canonical(record['units'])) != row['units_sha256']:
                    raise ValueError('RECORD_OR_FIELD_HASH_CONFLICT_STOP')
                records_checked += 1
            except (ValueError, KeyError, TypeError) as exc:
                failures.append({'record_sha256': row['record_sha256'], 'reason': str(exc)})
        for capture in self._db.execute('SELECT * FROM captures'):
            bodies = [json.loads(r[0]) for r in self._db.execute(
                'SELECT v.record_json FROM captured_records cr JOIN record_versions v ON '
                'v.source=cr.source AND v.domain=cr.domain AND v.symbol=cr.symbol AND '
                'v.record_sha256=cr.record_sha256 WHERE cr.capture_id=? ORDER BY cr.row_ordinal', (capture['capture_id'],))]
            if len(bodies) != capture['record_count'] or digest(canonical(bodies)) != capture['records_sha256']:
                failures.append({'capture_id': capture['capture_id'], 'reason': 'CAPTURE_RECORD_BINDING_CONFLICT_STOP'})
            try:
                metadata = {key: capture[key] for key in ('source', 'domain', 'symbol', 'retrieved_at',
                                                         'source_url', 'license_state', 'raw_sha256', 'records_sha256')}
                metadata['request'] = json.loads(capture['request_json'])
                if digest(canonical(metadata)) != capture['capture_id']:
                    failures.append({'capture_id': capture['capture_id'], 'reason': 'CAPTURE_METADATA_HASH_CONFLICT_STOP'})
            except (ValueError, TypeError) as exc:
                failures.append({'capture_id': capture['capture_id'], 'reason': str(exc)})
        foreign_key_failures = self._db.execute('PRAGMA foreign_key_check').fetchall()
        if foreign_key_failures:
            failures.append({'reason': 'SQLITE_FOREIGN_KEY_CHECK_FAILED', 'count': len(foreign_key_failures)})
        return {'version': VERSION, 'state': 'PASS_INTEGRITY_ONLY' if not failures else 'FAIL_INTEGRITY_STOP',
                'checked_blobs': len(checked), 'checked_record_versions': records_checked,
                'blobs': checked, 'failures': failures, 'actual_pit_admitted_records': 0,
                'historical_visibility_proven': False, 'source_admitted': False,
                'productionGate': False}

    def ingest(self, batch):
        if not isinstance(batch, dict):
            raise ValueError('BATCH_OBJECT_REQUIRED')
        required = ('source', 'domain', 'symbol', 'request', 'retrieved_at',
                    'raw_bytes', 'source_url', 'records', 'license_state')
        if any(key not in batch for key in required):
            raise ValueError('BATCH_FIELD_REQUIRED')
        for key in ('source', 'domain', 'symbol', 'source_url', 'license_state'):
            if not isinstance(batch[key], str) or not batch[key]:
                raise ValueError('BATCH_STRING_REQUIRED:' + key)
        if not isinstance(batch['request'], dict) or not isinstance(batch['records'], list):
            raise ValueError('BATCH_REQUEST_OBJECT_AND_RECORDS_LIST_REQUIRED')
        if not isinstance(batch['raw_bytes'], bytes):
            raise ValueError('EXACT_RAW_BYTES_REQUIRED')
        _clock(batch['retrieved_at'])
        if batch['retrieved_at'] is None:
            raise ValueError('RETRIEVAL_EXACT_CLOCK_REQUIRED')
        request_raw = canonical(batch['request'])
        record_raw = canonical(batch['records'])
        enriched = [{**r, 'source': batch['source'], 'domain': batch['domain'],
                     'symbol': batch['symbol'], 'retrieved_at': batch['retrieved_at']}
                    if isinstance(r, dict) else r for r in batch['records']]
        dq = validate_records(enriched)
        if dq['errors']:
            codes = sorted({r['code'] for r in dq['errors']})
            raise ValueError('INVALID_BATCH_RECORDS:' + ','.join(codes))
        raw_sha256 = digest(batch['raw_bytes'])
        records_sha256 = digest(record_raw)
        meta = {key: batch[key] for key in required if key not in ('raw_bytes', 'records')}
        capture_id = digest(canonical({**meta, 'raw_sha256': raw_sha256,
                                       'records_sha256': records_sha256}))
        raw_path = self.raw_dir / (raw_sha256 + '.raw')
        new_blob = False
        self._db.execute('BEGIN IMMEDIATE')
        try:
            duplicate = self._db.execute('SELECT 1 FROM captures WHERE capture_id=?', (capture_id,)).fetchone()
            if duplicate:
                self._verify_raw(raw_path, raw_sha256, batch['raw_bytes'])
                self._db.execute('COMMIT')
                return {'capture_id': capture_id, 'raw_sha256': raw_sha256, 'raw_ref': str(raw_path),
                        'new_capture': False, 'duplicate_capture': True,
                        'new_record_count': 0, 'new_version_count': 0, **self._counts()}
            try:
                fd = os.open(raw_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                new_blob = True
                with os.fdopen(fd, 'wb') as raw_file:
                    raw_file.write(batch['raw_bytes'])
                    raw_file.flush()
                    os.fsync(raw_file.fileno())
                # Commit blob directory entries before persisting the capture.
                dfd = os.open(self.raw_dir, os.O_RDONLY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except FileExistsError:
                self._verify_raw(raw_path, raw_sha256, batch['raw_bytes'])
            self._db.execute(
                'INSERT INTO captures(capture_id,source,domain,symbol,request_json,retrieved_at,'
                'source_url,license_state,raw_sha256,raw_ref,records_sha256,record_count) '
                'VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (capture_id, batch['source'], batch['domain'], batch['symbol'], request_raw.decode(),
                 batch['retrieved_at'], batch['source_url'], batch['license_state'], raw_sha256,
                 str(raw_path), records_sha256, len(batch['records'])))
            new_versions = 0
            for ordinal, record in enumerate(batch['records']):
                body = canonical(record)
                record_sha = digest(body)
                cur = self._db.execute(
                    'INSERT OR IGNORE INTO record_versions(source,domain,symbol,record_sha256,identity,'
                    'event_date,revision_id,fields_sha256,units_sha256,record_json) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (batch['source'], batch['domain'], batch['symbol'], record_sha, record['identity'],
                     record['event_date'], record['revision_id'], digest(canonical(record['fields'])),
                     digest(canonical(record['units'])), body.decode()))
                new_versions += cur.rowcount
                self._db.execute(
                    'INSERT INTO captured_records(capture_id,row_ordinal,source,domain,symbol,record_sha256) '
                    'VALUES(?,?,?,?,?,?)', (capture_id, ordinal, batch['source'], batch['domain'], batch['symbol'], record_sha))
            self._db.execute('COMMIT')
        except BaseException:
            if self._db.in_transaction:
                self._db.execute('ROLLBACK')
            if new_blob:
                # This exclusive blob was created in the rolled-back transaction;
                # no committed capture can reference it while BEGIN held the lock.
                used = self._db.execute('SELECT 1 FROM captures WHERE raw_sha256=? LIMIT 1', (raw_sha256,)).fetchone()
                if not used:
                    raw_path.unlink(missing_ok=True)
            raise
        return {'capture_id': capture_id, 'raw_sha256': raw_sha256, 'raw_ref': str(raw_path),
                'new_capture': True, 'duplicate_capture': False,
                'new_record_count': len(batch['records']), 'new_version_count': new_versions,
                **self._counts()}

    @staticmethod
    def _verify_raw(path, expected_hash, expected_bytes):
        _private_file(path)
        raw = path.read_bytes()
        if digest(raw) != expected_hash or raw != expected_bytes:
            raise ValueError('RAW_CONTENT_HASH_CONFLICT_STOP')

    def records(self, domain=None, symbol=None):
        clauses, args = [], []
        if domain is not None:
            clauses.append('c.domain=?')
            args.append(domain)
        if symbol is not None:
            clauses.append('c.symbol=?')
            args.append(symbol)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        query = ('SELECT c.*,cr.row_ordinal,v.record_sha256,v.fields_sha256,v.units_sha256,v.record_json '
                 'FROM captures c JOIN captured_records cr ON cr.capture_id=c.capture_id '
                 'JOIN record_versions v ON v.source=cr.source AND v.domain=cr.domain AND '
                 'v.symbol=cr.symbol AND v.record_sha256=cr.record_sha256' + where +
                 ' ORDER BY c.sequence,cr.row_ordinal')
        out = []
        for row in self._db.execute(query, args):
            original = json.loads(row['record_json'])
            out.append({**original, 'record_body': original,
                        'source': row['source'], 'domain': row['domain'], 'symbol': row['symbol'],
                        'request': json.loads(row['request_json']), 'retrieved_at': row['retrieved_at'],
                        'source_url': row['source_url'], 'license_state': row['license_state'],
                        'raw_sha256': row['raw_sha256'], 'raw_ref': row['raw_ref'],
                        'capture_id': row['capture_id'], 'capture_sequence': row['sequence'],
                        'row_ordinal': row['row_ordinal'], 'record_hash': row['record_sha256'],
                        'fields_sha256': row['fields_sha256'], 'units_sha256': row['units_sha256'],
                        'historical_visibility_proven': False, 'source_admitted': False})
        return out
