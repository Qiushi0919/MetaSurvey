"""No signer, credential lookup, capture, G-store mutation or scheduler here.

The existing G validator remains the sole authority for actual accepted days.
This separate research journal requires its complete accepted signature chain.
"""
from __future__ import annotations

import fcntl
import json
import os
import re
from pathlib import Path

from dual_track.common import (FORWARD_V1_REF, SYMBOLS, canonical, closed,
    decimal, instant, now, precision80, ref, reopen, require, sha, text)
from dual_track.forward import validate_prediction
from dual_track.reviewed import score_actual_snapshot
from wave_h.auth import ensure_actual_enrolled, fixture_signature_verify
from wave_h.forward import _anchor, _json, inspect_actual_store

SESSION = '2026-10-08'
EOD = '2026-10-08T15:00:00+08:00'
NAMESPACE = 'FORWARD_RESEARCH_ONLY:CORE_40:DAY1_REVEAL'
ROOT = Path(__file__).resolve().parents[1]
SOURCE_HASH = 'sha256:f990215f49d5b572f17c7b4eacbf203243268783b324b7dadd02637f48f95b60'


def prediction():
    from .integrity import check_day0
    check_day0()
    raw = reopen(FORWARD_V1_REF)
    result = validate_prediction(_json(raw))
    require(result['source_ref']['sha256'] == SOURCE_HASH and
            sha(reopen(result['source_ref'])) == SOURCE_HASH, 'D1_SOURCE_CHANGED')
    return result


def verify_base():
    """Reopen fixed Reference A, without upgrading historical PIT or license."""
    pred = prediction()
    anchor_ref = _json((ROOT/'config/wave-h/snapshot-a-reference.json').read_bytes())['snapshot_a_ref']
    anchor = _anchor(anchor_ref, SESSION, True)
    rows = []
    for symbol, raw_ref in zip(SYMBOLS, anchor['source_original_refs']):
        source = _json(reopen(raw_ref), True)['data']
        matches = [dict(zip(source['fields'], row)) for row in source['items']
                   if dict(zip(source['fields'], row))['ts_code'] == symbol and
                   dict(zip(source['fields'], row))['trade_date'] == '20260930']
        require(len(matches) == 1, 'D1_BASE_SESSION_NOT_UNIQUE')
        actual = decimal(str(matches[0]['close']))
        expected = decimal(next(e['base_close_cny'] for e in pred['entries'] if e['symbol'] == symbol))
        require(actual == expected, 'BASE_ASSUMPTION_DISPROVED')
        rows.append({'symbol':symbol,'base_session':'2026-09-30',
                     'base_close_cny':text(actual),'assumption_matches':True,'raw_ref':raw_ref})
    return {'version':'1.0.0','kind':'BaseReferenceAVerification',
            'prediction_sha256':FORWARD_V1_REF['sha256'],'anchor_ref':anchor_ref,
            'rows':rows,'state':'PASS_CURRENT_RAW_REFERENCE_MATCH',
            'source_admission':'BLOCKED','historical_visibility_proven':False,
            'prediction_rewritten':False,'verified_at':now()}


def attestation_body(role):
    """Unsigned late research acknowledgment, NEVER a Wave H capability."""
    prediction()
    require(role in ('HUMAN_USER','INDEPENDENT_REVIEWER'), 'D1_ATTESTATION_ROLE')
    reg = ensure_actual_enrolled()
    require(instant(now()) >= instant('2026-10-08T09:30:00+08:00'), 'D1_LATE_ATTESTATION_CLOCK')
    return {'version':'1.0.0','kind':'PREDICTION_HASH_LATE_ATTESTATION',
            'namespace':NAMESPACE,'role':role,'key_id':reg['roles'][role]['key_id'],
            'prediction_sha256':FORWARD_V1_REF['sha256'],'source_sha256':SOURCE_HASH,
            'enrollment_id':reg['enrollment_id'],'prepared_at':now(),
            'timing_class':'POST_OPEN/LATE_ATTESTATION','preopen_signature':False,
            'independent_timestamp':False,'actual_authority':False,
            'statement':'ACKNOWLEDGE_EXISTING_HASH_ONLY_NO_CAPTURE_REVIEW_FORWARD_OR_TRADING_GRANT'}


def verify_attestation(body_ref, signature_ref, role):
    """Verify exact prepared body bytes with installed public key; no issuance."""
    prediction()
    body_raw = reopen(body_ref); body = _json(body_raw)
    closed(body, ('version','kind','namespace','role','key_id','prediction_sha256',
                 'source_sha256','enrollment_id','prepared_at','timing_class',
                 'preopen_signature','independent_timestamp','actual_authority','statement'))
    reg = ensure_actual_enrolled()
    require(role in reg['roles'], 'D1_ATTESTATION_ROLE')
    require(body_raw == canonical(body) and body['version']=='1.0.0' and
            body['kind']=='PREDICTION_HASH_LATE_ATTESTATION' and body['namespace']==NAMESPACE and
            body['role']==role and body['key_id']==reg['roles'][role]['key_id'] and
            body['enrollment_id']==reg['enrollment_id'] and
            body['prediction_sha256']==FORWARD_V1_REF['sha256'] and body['source_sha256']==SOURCE_HASH and
            body['statement']=='ACKNOWLEDGE_EXISTING_HASH_ONLY_NO_CAPTURE_REVIEW_FORWARD_OR_TRADING_GRANT' and
            body['timing_class']=='POST_OPEN/LATE_ATTESTATION' and body['preopen_signature'] is False and
            body['independent_timestamp'] is False and body['actual_authority'] is False,
            'D1_ATTESTATION_SCOPE')
    require(instant('2026-10-08T09:30:00+08:00') <= instant(body['prepared_at']) <= instant(now()),
            'D1_ATTESTATION_CLOCK')
    sig = reopen(signature_ref)
    require(len(sig)==64 and fixture_signature_verify(reg['roles'][role]['public_der'],body,sig.hex()),
            'D1_ATTESTATION_SIGNATURE_REJECTED')
    return {'kind':'VerifiedLatePredictionAttestation','role':role,'body_ref':body_ref,
            'signature_ref':signature_ref,'timing_class':'POST_OPEN/LATE_ATTESTATION',
            'signature_verified':True,'preopen_signature':False,'actual_authority':False,
            'independent_timestamp':False,'signature_time':'NOT_INDEPENDENTLY_PROVEN'}


@precision80
def score_day1(actual_store, snapshot_ref, symbol, scored_at=None):
    """Read existing full G chain FIRST. Snapshot with only two signatures is insufficient."""
    require(symbol in SYMBOLS, 'D1_SYMBOL')
    at = now() if scored_at is None else scored_at
    require(instant(EOD) <= instant(at) <= instant(now()), 'D1_EOD_OR_FUTURE_CLOCK')
    pred = prediction()
    verify_base()
    status = inspect_actual_store(actual_store)  # Reopens CAPTURE, REVIEW and separate FORWARD.
    require(status['namespace']=='ACTUAL_FORWARD_NO_DECISION' and
            status['accepted_session_count']==status['actual_forward_days']==1 and
            len(status['records'])==1, 'D1_EXACTLY_ONE_ACTUAL_SESSION_REQUIRED')
    record = status['records'][0]
    snap = _json(reopen(snapshot_ref))
    require(record['snapshot']==snap and snap['body']['session']==SESSION and
            record['decision']=='NO_DECISION' and record['safe_to_trade'] is False and
            record['forward_authorization'] is not None, 'D1_ACCEPTED_SNAPSHOT_REQUIRED')
    score = score_actual_snapshot(pred, snapshot_ref, symbol, 1, at)
    data = _json(reopen(score['outcome_raw_ref']), True)['data']
    require(len(data['items'])==1, 'D1_TARGET_ORIGINAL_REQUIRED')
    bar = dict(zip(data['fields'],data['items'][0]))
    require(bar['ts_code']==symbol and bar['trade_date']=='20261008', 'D1_TARGET_SYMBOL_DATE')
    return {'version':'1.0.0','kind':'Day1RevealOutcome','namespace':NAMESPACE,
            'symbol':symbol,'horizon':1,'target_session':SESSION,
            'prediction_sha256':FORWARD_V1_REF['sha256'],
            'base_close_verified':next(r['base_close_cny'] for r in verify_base()['rows'] if r['symbol']==symbol),
            'target_close':text(decimal(str(bar['close']))),
            'target_day_low':text(decimal(str(bar['low']))),'target_day_high':text(decimal(str(bar['high']))),
            'realized_return':score['realized_return_percent'],
            'direction_hit':score['direction_hit'],'range_hit':score['range_hit'],
            'center_forecast_error':score['forecast_error_percent_points'],
            'MAE':score['mae_percent'],'MFE':score['mfe_percent'],
            'units':{'prices':'CNY_PER_SHARE','returns':'PERCENT','error':'PERCENTAGE_POINTS'},
            'mae_mfe_convention':'MAE_MIN_0_AND_LOW_RETURN_MFE_MAX_0_AND_HIGH_RETURN',
            'capture_signature_verified':True,'independent_review_signature_verified':True,
            'forward_signature_verified':True,'scored_at':at,
            'snapshot_ref':snapshot_ref,'base_raw_ref':score['base_raw_ref'],
            'outcome_raw_ref':score['outcome_raw_ref'],'clock_ref':score['clock_ref'],
            'actual_store_path':str(Path(actual_store).resolve()),
            'actual_store_record_hash':record['record_hash'],'actual_store_head':status['head_hash'],
            'forward_expected_head':record['forward_authorization']['body']['scope']['expected_head'],
            'actual_forward_days':1,'actual_forward_days_increment':0,
            'source_admission':'BLOCKED','action_reconciliation':'UNKNOWN',
            'metric_scope':'CURRENT_REVIEWED_RAW_PRICE_NOT_EXECUTION_PNL',
            'productionGate':False,'actual_authority':False,
            'reason_codes':['SOURCE_PROVIDER_LICENSE_ACTIONS_UNRESOLVED','NO_EXECUTION_OR_PROFIT_AUTHORITY']}


def _path(path):
    p = Path(path).absolute()
    require(p.resolve()==p and p.is_file() and not p.is_symlink(), 'D1_JOURNAL_PATH')
    require(p.stat().st_nlink==1 and p.stat().st_mode&0o777==0o600, 'D1_JOURNAL_PERMISSIONS')
    return p


def _head(p, raw):
    require(not raw or raw.endswith(b'\n'), 'D1_PARTIAL_JOURNAL_STOP_NO_REPAIR')
    head = sha(canonical({'namespace':NAMESPACE,'journal_path':str(p),
                          'prediction_sha256':FORWARD_V1_REF['sha256']}))
    seen = set()
    for line in raw.splitlines():
        row = _json(line)
        require(line==canonical(row), 'D1_JOURNAL_NONCANONICAL')
        expected = score_day1(row['actual_store_path'],row['snapshot_ref'],row['symbol'],row['scored_at']).copy()
        expected.update({'sequence':len(seen)+1,'previous_hash':head,'expected_head':head})
        expected['outcome_sha256']=sha(canonical(expected))
        require(row==expected, 'D1_JOURNAL_CHANGED')
        require(row['symbol'] not in seen, 'D1_DUPLICATE_OUTCOME')
        head=row['outcome_sha256'];seen.add(row['symbol'])
    return head,seen


def journal_head(path):
    prediction()
    p = _path(path)
    with p.open('rb') as stream:
        fcntl.flock(stream,fcntl.LOCK_SH)
        return _head(p,stream.read())


def append_day1(path, expected_head, actual_store, snapshot_ref, symbol):
    """Existing-only JSONL append, strict expected head, duplicate denial, fsync.

    A crash-truncated line is retained and blocks further appends; no repair or
    rewriting. This journal is not the authoritative G SQLite day counter.
    """
    prediction()
    require(re.fullmatch('sha256:[0-9a-f]{64}',expected_head or ''), 'D1_EXPECTED_HEAD')
    p = _path(path)
    with p.open('r+b') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX)
        current,seen = _head(p,stream.read())
        require(current==expected_head, 'D1_STALE_HEAD')
        require(symbol not in seen, 'D1_DUPLICATE_OUTCOME')
        row = score_day1(actual_store,snapshot_ref,symbol).copy()
        row.update({'sequence':len(seen)+1,'previous_hash':current,'expected_head':expected_head})
        row['outcome_sha256']=sha(canonical(row))
        stream.seek(0,os.SEEK_END)
        stream.write(canonical(row)+b'\n');stream.flush();os.fsync(stream.fileno())
        return row
