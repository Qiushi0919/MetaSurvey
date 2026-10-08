"""Bounded current-observation collector; H-A performs offline simulations only.

Actual entry checks a distinct external capture capability before any file or secret
lookup. Its single fixed HTTP gateway is a LOCAL exception, never source admission.
Raw response identities are distinct from the stable request-schema version.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

from .common import (ARCHIVE, ROOT, SYMBOLS, VERSION, bindings, canonical, digest,
                     hash_value, keys, metadata, policy, ref, reopen, require, seal,
                     sha, timestamp, write_private)

ENDPOINT = 'http://118.89.117.77:8030/'
SOURCE_IDENTITY = 'OWNER_PROVIDED_MONTHLY_GATEWAY_UNVERIFIED'
SCHEMA_VERSION = 'TUSHARE_NATIVE_EOD_REQUEST_FIELDS_V1'
ACTUAL_MODE = 'LOCAL_ONLY_NON_TRADEABLE_CURRENT_OBSERVATION'
SIMULATION_MODE = 'OFFLINE_SIMULATION'
MAX_BYTES = 2 * 1024 * 1024
ZONE = ZoneInfo('Asia/Shanghai')
_PLAN_KEYS = ('version', 'kind', 'mode', 'session', 'symbols', 'endpoint',
              'source_identity', 'source_schema_version', 'bindings', 'jobs',
              'session_evidence_ref', 'snapshot_a_ref', 'plan_hash')
_WITNESS_KEYS = ('version', 'kind', 'session', 'symbols', 'actual_session_open',
                 'eod_observed', 'observed_at', 'precision', 'original_refs',
                 'witness_source')
_ANCHOR_KEYS = ('capture_id', 'session_date', 'retrieved_at', 'observed_universe',
                'raw_observation_hash', 'source_policy_hash', 'rules_hash',
                'version', 'kind', 'source_original_refs', 'source_admission',
                'historical_visibility_proven')
_CLOCK_KEYS = ('version', 'kind', 'mode', 'capture_id', 'job_id', 'request_identity',
               'source_identity', 'source_schema_version', 'session', 'started_at',
               'retrieved_at', 'retrieved_precision', 'event_time', 'event_precision',
               'published_at', 'published_precision', 'source_available_at',
               'source_available_precision', 'current_available_at',
               'current_available_precision', 'visibility_basis',
               'historical_visibility_proven', 'source_response_hash')
_MANIFEST_KEYS = ('version', 'kind', 'mode', 'capture_id', 'plan', 'plan_hash',
                  'policy_hash', 'strategy_hash', 'source_schema_version',
                  'source_identity', 'endpoint', 'session', 'symbols', 'started_at',
                  'completed_at', 'clock_precision', 'jobs',
                  'source_session_evidence_ref', 'snapshot_a_ref',
                  'capture_authorization', 'coverage', 'status_unknowns',
                  'source_admission', 'historical_visibility_proven',
                  'safe_to_trade', 'decision', 'actual_forward_days', 'content_hash')


def _json(raw):
    def pairs(items):
        d = {}
        for k, v in items:
            require(k not in d, 'WH_CAPTURE_DUPLICATE_JSON_KEY')
            d[k] = v
        return d
    def nonfinite(_):
        raise ValueError('WH_CAPTURE_NONFINITE_NUMBER')
    try:
        return json.loads(raw.decode('utf-8'), parse_float=str,
                          parse_constant=nonfinite, object_pairs_hook=pairs)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError('WH_CAPTURE_JSON_INVALID') from None
    except ValueError:
        raise
    except Exception:
        raise ValueError('WH_CAPTURE_JSON_INVALID') from None


def _date(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value),
            'WH_CAPTURE_SESSION_DATE_REQUIRED')
    date.fromisoformat(value)
    return value


def _precision(value):
    timestamp(value)
    m = re.search(r'\.(\d+)(?:Z|[+-]\d\d:\d\d)$', value)
    n = len(m.group(1)) if m else 0
    return 'SECOND' if n == 0 else ('MILLISECOND' if n <= 3 else
            'MICROSECOND' if n <= 6 else 'NANOSECOND')


def _local_day(value):
    timestamp(value)
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(ZONE).date().isoformat()


def _source_module():
    # Loading frozen code is deferred until after actual capability/session checks.
    spec = importlib.util.spec_from_file_location('_wave_h_frozen_probe',
                                                ROOT / 'tushare-admission/probe.py')
    require(spec is not None and spec.loader is not None, 'WH_CAPTURE_CREDENTIAL_ADAPTER_MISSING')
    module = importlib.util.module_from_spec(spec)
    # dataclasses require the module name during import. No credential lookup occurs.
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _definitions(session):
    ymd = _date(session).replace('-', '')
    definitions = [dict(job_id='trade_cal-SSE', api_name='trade_cal',
        params={'exchange': 'SSE', 'start_date': ymd, 'end_date': ymd},
        fields=['exchange', 'cal_date', 'is_open', 'pretrade_date'],
        max_rows=1, mandatory=True, symbol=None, units={'is_open': 'ENUM_0_1'},
        adjustment_state='NOT_APPLICABLE')]
    kinds = (
        ('daily', ['ts_code', 'trade_date', 'open', 'high', 'low', 'close',
                   'pre_close', 'change', 'pct_chg', 'vol', 'amount'], 1, True,
         {'open': 'CNY', 'high': 'CNY', 'low': 'CNY', 'close': 'CNY',
          'pre_close': 'PROVIDER_EX_RIGHTS_REFERENCE_CNY', 'change': 'CNY',
          'pct_chg': 'PERCENT', 'vol': 'LOT_HAND', 'amount': 'THOUSAND_CNY'},
         'RAW_UNADJUSTED_OHLC_PRE_CLOSE_EX_RIGHTS_REFERENCE'),
        ('stock_basic', ['ts_code', 'symbol', 'name', 'exchange', 'curr_type',
                         'list_status', 'list_date', 'delist_date'], 1, False,
         {}, 'NOT_APPLICABLE'),
        ('suspend_d', ['ts_code', 'trade_date', 'suspend_timing', 'suspend_type'],
         8, False, {}, 'EVENT_RECORD_NOT_COMPLETE_CURRENT_STATE'),
        ('stk_limit', ['ts_code', 'trade_date', 'pre_close', 'up_limit', 'down_limit'],
         1, False, {'pre_close': 'PROVIDER_REFERENCE_CNY', 'up_limit': 'CNY',
                    'down_limit': 'CNY'}, 'PROVIDER_LIMIT_OBSERVATION_NOT_REGIME_PROOF'),
    )
    for api, fields, cap, mandatory, units, adjustment in kinds:
        for symbol in SYMBOLS:
            params = {'ts_code': symbol}
            if api in ('daily', 'suspend_d', 'stk_limit'):
                params['trade_date'] = ymd
            definitions.append(dict(job_id=f'{api}-{symbol}', api_name=api,
                params=params, fields=fields, max_rows=cap, mandatory=mandatory,
                symbol=symbol, units=units, adjustment_state=adjustment))
    return definitions


def _witness(r, session, mode):
    doc = _json(reopen(r, private=True))
    keys(doc, _WITNESS_KEYS)
    expected = 'ACTUAL_SESSION_WITNESS' if mode == ACTUAL_MODE else 'OFFLINE_SIMULATION_SESSION_WITNESS'
    require(doc['version'] == VERSION and doc['kind'] == expected,
            'WH_CAPTURE_SESSION_WITNESS_MODE_INVALID')
    require(doc['session'] == session and doc['symbols'] == list(SYMBOLS),
            'WH_CAPTURE_SESSION_WITNESS_SCOPE_INVALID')
    require(doc['actual_session_open'] is True and doc['eod_observed'] is True,
            'WH_CAPTURE_ACTUAL_OPEN_EOD_REQUIRED')
    require(doc['precision'] == _precision(doc['observed_at']),
            'WH_CAPTURE_WITNESS_PRECISION_CONFLICT')
    require(_local_day(doc['observed_at']) == session, 'WH_CAPTURE_WITNESS_DATE_INVALID')
    require(type(doc['witness_source']) is str and 1 <= len(doc['witness_source']) <= 160,
            'WH_CAPTURE_WITNESS_SOURCE_REQUIRED')
    require(type(doc['original_refs']) is list and 1 <= len(doc['original_refs']) <= 4,
            'WH_CAPTURE_WITNESS_ORIGINALS_REQUIRED')
    require(len({x['path'] for x in doc['original_refs']}) == len(doc['original_refs']),
            'WH_CAPTURE_WITNESS_ORIGINAL_DUPLICATE')
    for original in doc['original_refs']:
        reopen(original, private=True)
    return doc


def _anchor(r, session, mode):
    doc = _json(reopen(r, private=True))
    keys(doc, _ANCHOR_KEYS)
    expected = 'CURRENT_OBSERVED_REFERENCE_A_NOT_ADMITTED' if mode == ACTUAL_MODE else 'OFFLINE_SIMULATION_REFERENCE_A'
    require(doc['version'] == VERSION and doc['kind'] == expected and
            doc['source_admission'] == 'BLOCKED' and doc['historical_visibility_proven'] is False,
            'WH_CAPTURE_ANCHOR_MODE_OR_SOURCE_PROMOTION')
    require(type(doc['capture_id']) is str and 1 <= len(doc['capture_id']) <= 160,
            'WH_CAPTURE_ANCHOR_ID_REQUIRED')
    require(doc['observed_universe'] == list(SYMBOLS) and _date(doc['session_date']) < session,
            'WH_CAPTURE_A_TO_B_LINEAGE_INVALID')
    timestamp(doc['retrieved_at'])
    require(type(doc['source_original_refs']) is list and len(doc['source_original_refs']) == 3 and
            digest(doc['source_original_refs']) == doc['raw_observation_hash'],
            'WH_CAPTURE_ANCHOR_ORIGINAL_LINEAGE_INVALID')
    if mode == ACTUAL_MODE:
        frozen = _json((ROOT / 'config/wave-h/snapshot-a-reference.json').read_bytes())
        require(r == frozen['snapshot_a_ref'], 'WH_CAPTURE_ACTUAL_REFERENCE_A_PIN_REQUIRED')
    for symbol, original in zip(SYMBOLS, doc['source_original_refs']):
        source = _json(reopen(original, private=True))
        require(type(source) is dict and source.get('code') == 0 and
                type(source.get('data')) is dict, 'WH_CAPTURE_ANCHOR_SOURCE_INVALID')
        fields, items = source['data'].get('fields'), source['data'].get('items')
        require(type(fields) is list and len(fields) == len(set(fields)) and
                'ts_code' in fields and 'trade_date' in fields and type(items) is list and items,
                'WH_CAPTURE_ANCHOR_SOURCE_FIELDS_INVALID')
        dates = []
        for row in items:
            require(type(row) is list and len(row) == len(fields) and
                    row[fields.index('ts_code')] == symbol,
                    'WH_CAPTURE_ANCHOR_SYMBOL_INVALID')
            ymd = row[fields.index('trade_date')]
            require(type(ymd) is str and re.fullmatch(r'\d{8}', ymd),
                    'WH_CAPTURE_ANCHOR_DATE_INVALID')
            dates.append(_date(f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}'))
        require(max(dates) == doc['session_date'], 'WH_CAPTURE_ANCHOR_LAST_SESSION_DRIFT')
    for field in ('raw_observation_hash', 'source_policy_hash', 'rules_hash'):
        hash_value(doc[field])
    return doc


def build_plan(session, session_evidence_ref, snapshot_a_ref):
    session = _date(session)
    raw = _json(reopen(session_evidence_ref, private=True))
    mode = (SIMULATION_MODE if raw.get('kind') == 'OFFLINE_SIMULATION_SESSION_WITNESS'
            else ACTUAL_MODE)
    _witness(session_evidence_ref, session, mode)
    _anchor(snapshot_a_ref, session, mode)
    p = policy()
    require(p['endpoint'] == ENDPOINT and p['source_identity'] == SOURCE_IDENTITY and
            p['source_schema_version'] == SCHEMA_VERSION and p['max_requests'] == 13 and
            p['allowed_apis'] == ['trade_cal', 'daily', 'stock_basic', 'suspend_d', 'stk_limit'] and
            p['redirects'] == 'REJECT' and p['proxy'] == 'DISABLED' and
            p['fallback'] == 'REJECT' and p['retries'] == 0,
            'WH_CAPTURE_SOURCE_POLICY_DRIFT')
    body = dict(version=VERSION, kind='BOUNDED_CURRENT_CAPTURE_PLAN', mode=mode,
        session=session, symbols=list(SYMBOLS), endpoint=ENDPOINT,
        source_identity=SOURCE_IDENTITY, source_schema_version=SCHEMA_VERSION,
        bindings=bindings(), jobs=_definitions(session),
        session_evidence_ref=session_evidence_ref, snapshot_a_ref=snapshot_a_ref)
    canonical(body)
    return dict(body, plan_hash=digest(body))


def validate_plan(plan, mode=None):
    keys(plan, _PLAN_KEYS)
    require(plan['version'] == VERSION and plan['kind'] == 'BOUNDED_CURRENT_CAPTURE_PLAN',
            'WH_CAPTURE_PLAN_VERSION_KIND_INVALID')
    require(plan['mode'] in (SIMULATION_MODE, ACTUAL_MODE) and
            (mode is None or plan['mode'] == mode), 'WH_CAPTURE_PLAN_MODE_INVALID')
    require(plan == build_plan(plan['session'], plan['session_evidence_ref'], plan['snapshot_a_ref']),
            'WH_CAPTURE_PLAN_SCOPE_OR_BINDING_DRIFT')
    return plan


def request_identity(plan, job):
    require(job in plan['jobs'] and job == _definitions(plan['session'])[plan['jobs'].index(job)],
            'WH_CAPTURE_JOB_SCOPE_INVALID')
    # Sanitized identity never includes request token or credential reference.
    return digest({'endpoint': ENDPOINT, 'source_identity': SOURCE_IDENTITY,
        'source_schema_version': SCHEMA_VERSION, 'session': plan['session'],
        'plan_hash': plan['plan_hash'], 'job': job})


def _decimal(v, *, positive=False):
    require(type(v) in (str, int) and type(v) is not bool,
            'WH_CAPTURE_DECIMAL_LITERAL_REQUIRED')
    s = str(v)
    require(re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.\d+)?', s),
            'WH_CAPTURE_DECIMAL_LITERAL_REQUIRED')
    d = Decimal(s)
    require(d.is_finite() and len(d.as_tuple().digits) <= 100 and
            abs(d.as_tuple().exponent) <= 100 and (not positive or d > 0),
            'WH_CAPTURE_DECIMAL_RANGE_INVALID')
    return d


def parse_native(job, raw, session):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, 'WH_CAPTURE_RESPONSE_SIZE_INVALID')
    doc = _json(raw)
    keys(doc, ('code', 'msg', 'data'))
    require(type(doc['code']) is int and (doc['msg'] is None or type(doc['msg']) is str),
            'WH_CAPTURE_NATIVE_CODE_INVALID')
    if doc['code'] != 0:
        # Native provider text may contain secrets; never copy messages into records.
        msg = (doc['msg'] or '').lower()
        denial = any(x in msg for x in ('没有权限', '无权限', '权限不足', '积分不足',
                     'permission denied', 'entitlement not granted', 'insufficient points'))
        return {'status': 'API_DENIED' if denial else 'API_ERROR',
                'reason_code': 'ENTITLEMENT_NOT_GRANTED' if denial else 'SOURCE_API_ERROR',
                'rows': [], 'row_count': None}
    keys(doc['data'], ('fields', 'items'))
    fields, items = doc['data']['fields'], doc['data']['items']
    require(type(fields) is list and all(type(x) is str for x in fields) and
            len(fields) == len(set(fields)), 'WH_CAPTURE_NATIVE_FIELDS_INVALID')
    require(set(fields) == set(job['fields']) or (not fields and not items),
            'WH_CAPTURE_NATIVE_FIELDS_DRIFT')
    require(type(items) is list and len(items) <= job['max_rows'], 'WH_CAPTURE_NATIVE_ROW_CAP')
    rows = []
    ymd = session.replace('-', '')
    seen = set()
    for values in items:
        require(type(values) is list and len(values) == len(fields), 'WH_CAPTURE_NATIVE_ROW_SHAPE')
        row = dict(zip(fields, values))
        identity = digest(row)
        require(identity not in seen, 'WH_CAPTURE_DUPLICATE_ROW')
        seen.add(identity)
        if job['api_name'] == 'trade_cal':
            require(row['exchange'] == 'SSE' and row['cal_date'] == ymd and
                    type(row['is_open']) is int and row['is_open'] == 1,
                    'WH_CAPTURE_CALENDAR_SESSION_CONFLICT')
        else:
            require(row['ts_code'] == job['symbol'], 'WH_CAPTURE_NATIVE_SYMBOL_DRIFT')
            if 'trade_date' in row:
                require(row['trade_date'] == ymd, 'WH_CAPTURE_NATIVE_STALE_SESSION')
        if job['api_name'] == 'daily':
            o, h, l, c = (_decimal(row[x], positive=True) for x in ('open', 'high', 'low', 'close'))
            require(l <= min(o, c) <= max(o, c) <= h, 'WH_CAPTURE_OHLC_INCONSISTENT')
            for name in ('pre_close', 'change', 'pct_chg', 'vol', 'amount'):
                d = _decimal(row[name], positive=name == 'pre_close')
                if name in ('vol', 'amount'):
                    require(d >= 0, 'WH_CAPTURE_VOLUME_AMOUNT_NEGATIVE')
        if job['api_name'] == 'stock_basic':
            require(row['symbol'] == job['symbol'].split('.')[0] and
                    type(row['name']) is str and 1 <= len(row['name']) <= 160 and
                    row['exchange'] == 'SSE' and row['curr_type'] == 'CNY' and
                    row['list_status'] in ('L', 'D', 'P'),
                    'WH_CAPTURE_SECURITY_BASIC_SCHEMA_INVALID')
            for field in ('list_date', 'delist_date'):
                value = row[field]
                if value is not None and value != '':
                    require(type(value) is str and re.fullmatch(r'\d{8}', value),
                            'WH_CAPTURE_SECURITY_BASIC_DATE_INVALID')
                    _date(f'{value[:4]}-{value[4:6]}-{value[6:]}')
        if job['api_name'] == 'suspend_d':
            require(row['suspend_type'] in ('S', 'R') and
                    (row['suspend_timing'] is None or type(row['suspend_timing']) is str),
                    'WH_CAPTURE_SUSPENSION_EVENT_SCHEMA_INVALID')
        if job['api_name'] == 'stk_limit':
            up, down = (_decimal(row[x], positive=True) for x in ('up_limit', 'down_limit'))
            require(up >= down and _decimal(row['pre_close'], positive=True),
                    'WH_CAPTURE_LIMIT_INCONSISTENT')
        rows.append(row)
    return {'status': 'SUCCESS' if rows else 'EMPTY',
            'reason_code': None if rows else 'SOURCE_EMPTY_NOT_COMPLETE_STATUS_PROOF',
            'rows': rows, 'row_count': len(rows)}


def _clock_record(plan, job, capture_id, raw, started_at, retrieved_at, mode):
    """Literal returned-response clock record; invalid semantics stay quarantine."""
    return dict(version=VERSION,
        kind='ACTUAL_CURRENT_CAPTURE_CLOCK' if mode == ACTUAL_MODE else 'OFFLINE_SIMULATION_CAPTURE_CLOCK',
        mode=mode, capture_id=capture_id, job_id=job['job_id'],
        request_identity=request_identity(plan, job), source_identity=SOURCE_IDENTITY,
        source_schema_version=SCHEMA_VERSION, session=plan['session'],
        started_at=started_at, retrieved_at=retrieved_at,
        retrieved_precision=_precision(retrieved_at), event_time=plan['session'],
        event_precision='DATE_ONLY', published_at=None, published_precision='UNKNOWN',
        source_available_at=None, source_available_precision='UNKNOWN',
        current_available_at=retrieved_at,
        current_available_precision=_precision(retrieved_at),
        visibility_basis='CURRENT_CAPTURE_COMPLETED_NOT_HISTORICAL_FIRST_VISIBLE',
        historical_visibility_proven=False, source_response_hash=sha(raw))


def _clock(plan, job, capture_id, raw, started_at, retrieved_at, mode):
    require(_local_day(started_at) == plan['session'] and _local_day(retrieved_at) == plan['session'] and
            timestamp(started_at) <= timestamp(retrieved_at), 'WH_CAPTURE_CLOCK_SESSION_CONFLICT')
    witness = _witness(plan['session_evidence_ref'], plan['session'], mode)
    require(timestamp(started_at) >= timestamp(witness['observed_at']),
            'WH_CAPTURE_BEFORE_OBSERVED_SESSION_WITNESS')
    return _clock_record(plan, job, capture_id, raw, started_at, retrieved_at, mode)


def validate_clock(clock, plan, job, capture_id, raw, mode):
    keys(clock, _CLOCK_KEYS)
    require(clock == _clock(plan, job, capture_id, raw, clock['started_at'],
                            clock['retrieved_at'], mode), 'WH_CAPTURE_CLOCK_BINDING_DRIFT')
    return clock


def _capture_dir(path, mode):
    p = Path(path)
    expected = ARCHIVE / 'capture' / ('actual' if mode == ACTUAL_MODE else 'simulation')
    require(p.is_absolute() and p.is_relative_to(expected) and p != expected and
            p.resolve() == p and not p.exists(), 'WH_CAPTURE_EXCLUSIVE_OUTPUT_REQUIRED')
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(p.parent.stat().st_mode & 0o777 == 0o700, 'WH_CAPTURE_PRIVATE_DIRECTORY_REQUIRED')
    p.mkdir(mode=0o700)
    return p


def _archive_returned_safe_response(plan, job, capture_id, raw, started_at,
                                    retrieved_at, mode, out, credential=None):
    """Retain returned originals before native semantics; never accepts a capture.

    Actual caller has already consumed its durable claim and completed credential
    echo checks in the fixed wire adapter. Rechecking here keeps secret echo and
    invalid JSON outside any hash/archive even if internal call order changes.
    Simulation uses its separate archive root and explicit synthetic clock kind.
    """
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, 'WH_CAPTURE_RESPONSE_SIZE_INVALID')
    require(mode in (ACTUAL_MODE, SIMULATION_MODE), 'WH_CAPTURE_PLAN_MODE_INVALID')
    if mode == ACTUAL_MODE:
        require(credential is not None, 'WH_CAPTURE_SAFE_RESPONSE_CREDENTIAL_REQUIRED')
    if credential is not None:
        require(not credential.body_contains_secret(raw), 'WH_CAPTURE_SECRET_ECHO_DISCARDED')
    doc = _json(raw)
    if credential is not None:
        require(not credential.object_contains_secret(doc), 'WH_CAPTURE_SECRET_ECHO_DISCARDED')
    expected = ARCHIVE / 'capture' / ('actual' if mode == ACTUAL_MODE else 'simulation')
    out = Path(out)
    require(out.is_relative_to(expected) and out != expected and out.resolve() == out and
            out.is_dir() and out.stat().st_mode & 0o777 == 0o700,
            'WH_CAPTURE_PRIVATE_RESPONSE_ARCHIVE_REQUIRED')
    clock = _clock_record(plan, job, capture_id, raw, started_at, retrieved_at, mode)
    rawpath = out / f'{job["job_id"]}.raw.json'
    clockpath = out / f'{job["job_id"]}.clock.json'
    write_private(rawpath, raw)
    write_private(clockpath, canonical(clock))
    return {'raw_ref': ref(rawpath), 'clock_ref': ref(clockpath),
            'source_response_hash': sha(raw)}


def _entry(plan, job, originals, parsed):
    return dict(job=job, request_identity=request_identity(plan, job),
        status=parsed['status'], reason_code=parsed['reason_code'],
        raw_ref=originals['raw_ref'], clock_ref=originals['clock_ref'],
        source_response_hash=originals['source_response_hash'], row_count=parsed['row_count'])


def _quarantine_failure(out, plan, capture_id, originals, mode, error, completed_job_count):
    code = str(error)
    if not re.fullmatch(r'(?:WH_CAPTURE|WH_AUTH|PREP)_[A-Z0-9_]{1,150}', code):
        code = 'WH_CAPTURE_FAILED_NO_RETRY'
    write_private(out / 'failure.json', canonical({
        'kind': 'ACTUAL_CAPTURE_FAILED' if mode == ACTUAL_MODE else 'OFFLINE_SIMULATION_CAPTURE_FAILED',
        'mode': mode, 'capture_id': capture_id, 'plan_hash': plan['plan_hash'],
        'reason_code': code, 'completed_job_count': completed_job_count,
        'quarantined_safe_response_originals': originals,
        'source_admission': 'BLOCKED', 'safe_to_trade': False,
        'positive_capture_manifest_issued': False, 'actual_forward_days': 0,
        'automatic_recovery_or_retry': False}))
    return code


def _finish(plan, capture_id, entries, started_at, completed_at, authorization, mode, out):
    complete = {x['job']['symbol'] for x in entries
                if x['job']['api_name'] == 'daily' and x['status'] == 'SUCCESS' and x['row_count'] == 1}
    cal = [x for x in entries if x['job']['api_name'] == 'trade_cal']
    require(complete == set(SYMBOLS) and len(cal) == 1 and cal[0]['status'] == 'SUCCESS' and
            cal[0]['row_count'] == 1, 'WH_CAPTURE_MANDATORY_EXACT_THREE_SESSION_REQUIRED')
    # Identical empty optional tables are legitimate across stocks. Duplicate raw
    # paths cannot stand for distinct captures; mandatory per-symbol daily bodies
    # must also have different hashes because each contains its requested ts_code.
    require(len({x['raw_ref']['path'] for x in entries}) == len(entries) and
            len({x['source_response_hash'] for x in entries if x['job']['api_name'] == 'daily'}) == 3,
            'WH_CAPTURE_DUPLICATE_RAW_RESPONSE')
    unknowns = []
    for symbol in SYMBOLS:
        for category in ('ST_NAME_HISTORY', 'SUSPENSION_COMPLETE_STATE',
                         'CORPORATE_ACTION_COMPLETENESS', 'PRICE_LIMIT_REGIME',
                         'PROVIDER_LICENSE_TRANSPORT'):
            unknowns.append(dict(symbol=symbol, field=category, state='UNKNOWN',
                                 reason_code='CURRENT_RESPONSE_NOT_COMPLETE_VERIFIED_STATE'))
    body = dict(version=VERSION,
        kind='ACTUAL_CURRENT_CAPTURE' if mode == ACTUAL_MODE else 'OFFLINE_SIMULATION_CAPTURE',
        mode=mode, capture_id=capture_id, plan=plan, plan_hash=plan['plan_hash'],
        policy_hash=plan['bindings']['policy_hash'], strategy_hash=plan['bindings']['strategy_hash'],
        source_schema_version=SCHEMA_VERSION, source_identity=SOURCE_IDENTITY, endpoint=ENDPOINT,
        session=plan['session'], symbols=list(SYMBOLS), started_at=started_at,
        completed_at=completed_at, clock_precision=_precision(completed_at), jobs=entries,
        source_session_evidence_ref=plan['session_evidence_ref'], snapshot_a_ref=plan['snapshot_a_ref'],
        capture_authorization=authorization,
        coverage={'requested_symbols': list(SYMBOLS), 'observed_daily_symbols': list(SYMBOLS),
                  'mandatory_daily_count': 3, 'session_calendar_consistent': True,
                  'planned_calendar_is_actual_session_proof': False},
        status_unknowns=unknowns, source_admission='BLOCKED', historical_visibility_proven=False,
        safe_to_trade=False, decision='NO_DECISION', actual_forward_days=0)
    manifest = seal(body)
    keys(manifest, _MANIFEST_KEYS)
    path = out / 'capture-manifest.json'
    write_private(path, canonical(manifest))
    return {'manifest': manifest, 'manifest_ref': ref(path)}


def simulate_capture(plan, responses, clock_fixture, output_dir):
    """Native-shaped synthetic originals with explicit simulation provenance only."""
    validate_plan(plan, SIMULATION_MODE)
    require(type(responses) is dict and set(responses) == {x['job_id'] for x in plan['jobs']},
            'WH_CAPTURE_SIMULATION_EXACT_JOB_SET_REQUIRED')
    keys(clock_fixture, ('started_at', 'retrieved_at'))
    _precision(clock_fixture['started_at']); _precision(clock_fixture['retrieved_at'])
    require(type(responses) is dict and all(type(x) is bytes for x in responses.values()),
            'WH_CAPTURE_SIMULATION_RAW_BYTES_REQUIRED')
    # Invalid JSON cannot complete an object-level secret scan and is discarded.
    # Valid JSON with bad native values is retained only as a failed quarantine.
    for raw in responses.values():
        require(0 < len(raw) <= MAX_BYTES, 'WH_CAPTURE_RESPONSE_SIZE_INVALID')
        _json(raw)
    capture_id = 'sim:' + digest({'plan_hash': plan['plan_hash'], 'clock': clock_fixture,
                               'raw_hashes': {k: sha(v) for k, v in responses.items()}}).split(':')[1]
    # Fixture clock conflicts are rejected before creating an output archive.
    clocks = {job['job_id']: _clock(plan, job, capture_id, responses[job['job_id']],
                  clock_fixture['started_at'], clock_fixture['retrieved_at'], SIMULATION_MODE)
              for job in plan['jobs']}
    out = _capture_dir(output_dir, SIMULATION_MODE)
    write_private(out / 'simulation-claim.json', canonical({'kind': 'OFFLINE_SIMULATION_CLAIM',
        'capture_id': capture_id, 'plan_hash': plan['plan_hash'], 'actual_forward_days': 0}))
    entries, returned_originals = [], []
    try:
        for job in plan['jobs']:
            raw = responses[job['job_id']]
            original = _archive_returned_safe_response(plan, job, capture_id, raw,
                clock_fixture['started_at'], clock_fixture['retrieved_at'], SIMULATION_MODE, out)
            returned_originals.append({'job_id': job['job_id'],
                'request_identity': request_identity(plan, job), **original})
            parsed = parse_native(job, raw, plan['session'])
            entries.append(_entry(plan, job, original, parsed))
        return _finish(plan, capture_id, entries, clock_fixture['started_at'],
                       clock_fixture['retrieved_at'], None, SIMULATION_MODE, out)
    except Exception as error:
        code = _quarantine_failure(out, plan, capture_id, returned_originals,
                                   SIMULATION_MODE, error, len(entries))
        raise ValueError(code) from None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('WH_CAPTURE_REDIRECT_REJECTED')


def _lookup_named_credential():
    """Future actual call only; never env/chat/files, no fallback or secret output."""
    p = policy()['credential_reference']
    require(p == {'storage': 'MACOS_KEYCHAIN',
                  'service': 'ashare-trading-v1/tushare-monthly-gateway',
                  'account': 'stock_api'}, 'WH_CAPTURE_CREDENTIAL_REFERENCE_DRIFT')
    module = _source_module()
    try:
        result = subprocess.run(['/usr/bin/security', 'find-generic-password',
            '-s', p['service'], '-a', p['account'], '-w'], capture_output=True,
            timeout=10, check=False)
        require(result.returncode == 0, 'WH_CAPTURE_NAMED_CREDENTIAL_UNAVAILABLE')
        value = result.stdout.decode('utf-8').strip()
        credential = module.Credential(value)
        return credential
    except Exception:
        raise ValueError('WH_CAPTURE_NAMED_CREDENTIAL_UNAVAILABLE') from None


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def _write_claim(path, body):
    """Exclusive consumed attempt, flushed before secret lookup / wire request."""
    write_private(path, canonical(body))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _fetch_native(job, credential):
    # Fixed source-specific actual wire path: no caller callback, env proxy or retry.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    wire = json.dumps({'api_name': job['api_name'], 'token': credential._wire_value(),
        'params': job['params'], 'fields': ','.join(job['fields'])},
        separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(ENDPOINT, data=wire,
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with opener.open(request, timeout=20) as response:
            require(response.geturl() == ENDPOINT and response.status == 200,
                    'WH_CAPTURE_HTTP_RESPONSE_REJECTED')
            raw = response.read(MAX_BYTES + 1)
            require(len(raw) <= MAX_BYTES and len(raw) > 0, 'WH_CAPTURE_RESPONSE_SIZE_INVALID')
            # No returned header/value is persisted. The raw echo check precedes SHA.
            require(not credential.body_contains_secret(raw), 'WH_CAPTURE_SECRET_ECHO_DISCARDED')
            doc = _json(raw)
            require(not credential.object_contains_secret(doc), 'WH_CAPTURE_SECRET_ECHO_DISCARDED')
            return raw
    except ValueError:
        raise
    except Exception:
        # Provider exception text/headers may contain credentials; fixed reason only.
        raise ValueError('WH_CAPTURE_TRANSPORT_FAILED_NO_RETRY') from None


def execute_capture(plan, capture_capability):
    """One future actual run only; pending external enrollment rejects H-A before IO."""
    from .auth import require_capture
    # Deliberately first: no validate_plan/reopen/stat/imported credential before auth.
    claimed_hash = plan.get('plan_hash') if type(plan) is dict else None
    claims = require_capture(capture_capability, claimed_hash)
    validate_plan(plan, ACTUAL_MODE)
    witness = _witness(plan['session_evidence_ref'], plan['session'], ACTUAL_MODE)
    a = _anchor(plan['snapshot_a_ref'], plan['session'], ACTUAL_MODE)
    require(claims['scope']['session_evidence_hash'] == plan['session_evidence_ref']['sha256'] and
            claims['scope']['snapshot_a_hash'] == plan['snapshot_a_ref']['sha256'] and
            claims['session'] == plan['session'] and claims['symbols'] == list(SYMBOLS) and
            timestamp(claims['issued_at']) >= timestamp(witness['observed_at']),
            'WH_CAPTURE_SIGNED_ORIGINAL_BINDING_REQUIRED')
    nonce = claims['nonce']
    require(type(nonce) is str and re.fullmatch(r'[A-Za-z0-9_-]{16,128}', nonce),
            'WH_CAPTURE_PERMIT_NONCE_REQUIRED')
    started_at = _now()
    require(_local_day(started_at) == plan['session'] and
            timestamp(started_at) >= timestamp(witness['observed_at']) and
            timestamp(started_at) >= timestamp(a['retrieved_at']) and
            timestamp(started_at) >= timestamp(claims['issued_at']),
            'WH_CAPTURE_CURRENT_ACTUAL_SESSION_REQUIRED')
    out = _capture_dir(ARCHIVE / 'capture' / 'actual' / nonce, ACTUAL_MODE)
    capture_id = 'actual:' + nonce
    # Durable claim before any secret lookup or request; crashes consume this nonce.
    _write_claim(out / 'capture-claim.json', {'kind': 'ACTUAL_CAPTURE_CONSUMED_CLAIM',
        'capture_id': capture_id, 'plan_hash': plan['plan_hash'], 'permit_nonce': nonce,
        'started_at': started_at, 'no_retry': True})
    entries, returned_originals = [], []
    try:
        credential = _lookup_named_credential()
        for job in plan['jobs']:
            require_capture(capture_capability, plan['plan_hash'])
            request_started = _now()
            # A claim is consumed even when the request/response fails.
            _write_claim(out / f'{job["job_id"]}.request-claim.json',
                {'job_id': job['job_id'], 'permit_nonce': nonce,
                    'request_identity': request_identity(plan, job),
                    'started_at': request_started, 'attempt': 1, 'no_retry': True})
            raw = _fetch_native(job, credential)
            completed = _now()
            original = _archive_returned_safe_response(plan, job, capture_id, raw,
                request_started, completed, ACTUAL_MODE, out, credential)
            returned_originals.append({'job_id': job['job_id'],
                'request_identity': request_identity(plan, job), **original})
            # The exact received body + literal clock survive semantic rejection.
            clock = _json(reopen(original['clock_ref'], private=True))
            validate_clock(clock, plan, job, capture_id, raw, ACTUAL_MODE)
            parsed = parse_native(job, raw, plan['session'])
            entries.append(_entry(plan, job, original, parsed))
            if job['mandatory']:
                require(parsed['status'] == 'SUCCESS' and parsed['row_count'] == 1,
                        'WH_CAPTURE_MANDATORY_RESPONSE_FAILED')
        completed_at = _now()
        require_capture(capture_capability, plan['plan_hash'])
        return _finish(plan, capture_id, entries, started_at, completed_at,
                       claims['signed_envelope'], ACTUAL_MODE, out)
    except Exception as error:
        # Never persist provider messages, credentials or arbitrary exception text.
        code = _quarantine_failure(out, plan, capture_id, returned_originals,
                                   ACTUAL_MODE, error, len(entries))
        raise ValueError(code) from None


def reopen_capture(manifest_ref, expected_plan, *, allow_simulation=False):
    """Original-reopen integrity API. Signature acceptance is independent in Forward."""
    manifest = _json(reopen(manifest_ref, private=True))
    keys(manifest, _MANIFEST_KEYS)
    mode = SIMULATION_MODE if allow_simulation else ACTUAL_MODE
    validate_plan(expected_plan, mode)
    require(manifest['mode'] == mode and manifest['plan'] == expected_plan and
            manifest['plan_hash'] == expected_plan['plan_hash'] and
            manifest['kind'] == ('OFFLINE_SIMULATION_CAPTURE' if allow_simulation else 'ACTUAL_CURRENT_CAPTURE'),
            'WH_CAPTURE_MANIFEST_MODE_PLAN_INVALID')
    require(manifest['content_hash'] == digest({k: v for k, v in manifest.items() if k != 'content_hash'}),
            'WH_CAPTURE_MANIFEST_HASH_INVALID')
    require(manifest['version'] == VERSION and manifest['source_schema_version'] == SCHEMA_VERSION and
            manifest['source_identity'] == SOURCE_IDENTITY and manifest['endpoint'] == ENDPOINT and
            manifest['symbols'] == list(SYMBOLS) and manifest['session'] == expected_plan['session'] and
            manifest['policy_hash'] == expected_plan['bindings']['policy_hash'] and
            manifest['strategy_hash'] == expected_plan['bindings']['strategy_hash'] and
            manifest['source_session_evidence_ref'] == expected_plan['session_evidence_ref'] and
            manifest['snapshot_a_ref'] == expected_plan['snapshot_a_ref'] and
            manifest['source_admission'] == 'BLOCKED' and
            manifest['historical_visibility_proven'] is False and
            manifest['safe_to_trade'] is False and manifest['decision'] == 'NO_DECISION' and
            type(manifest['actual_forward_days']) is int and manifest['actual_forward_days'] == 0,
            'WH_CAPTURE_MANIFEST_AUTHORITY_OR_BINDING_DRIFT')
    require(type(manifest['jobs']) is list and len(manifest['jobs']) == 13,
            'WH_CAPTURE_MANIFEST_JOB_COUNT_INVALID')
    paths, daily_hashes = set(), set()
    reconstructed = []
    for job, entry in zip(expected_plan['jobs'], manifest['jobs']):
        keys(entry, ('job', 'request_identity', 'status', 'reason_code', 'raw_ref',
                     'clock_ref', 'source_response_hash', 'row_count'))
        require(entry['job'] == job and entry['request_identity'] == request_identity(expected_plan, job),
                'WH_CAPTURE_MANIFEST_JOB_DRIFT')
        raw = reopen(entry['raw_ref'], private=True)
        require(sha(raw) == entry['source_response_hash'] and entry['raw_ref']['path'] not in paths,
                'WH_CAPTURE_RAW_HASH_OR_DUPLICATE')
        paths.add(entry['raw_ref']['path'])
        if job['api_name'] == 'daily':
            require(sha(raw) not in daily_hashes, 'WH_CAPTURE_RAW_HASH_OR_DUPLICATE')
            daily_hashes.add(sha(raw))
        clock = _json(reopen(entry['clock_ref'], private=True))
        validate_clock(clock, expected_plan, job, manifest['capture_id'], raw, mode)
        parsed = parse_native(job, raw, expected_plan['session'])
        require(entry['status'] == parsed['status'] and entry['reason_code'] == parsed['reason_code'] and
                entry['row_count'] == parsed['row_count'], 'WH_CAPTURE_PRODUCER_SUMMARY_DRIFT')
        if job['mandatory']:
            require(parsed['status'] == 'SUCCESS' and parsed['row_count'] == 1,
                    'WH_CAPTURE_MANDATORY_EXACT_THREE_SESSION_REQUIRED')
        reconstructed.append({'job': job, 'parsed': parsed, 'clock': clock})
    require(_precision(manifest['completed_at']) == manifest['clock_precision'] and
            _local_day(manifest['started_at']) == expected_plan['session'] and
            _local_day(manifest['completed_at']) == expected_plan['session'] and
            timestamp(manifest['started_at']) <= min(timestamp(x['clock']['started_at']) for x in reconstructed) and
            max(timestamp(x['clock']['retrieved_at']) for x in reconstructed) <= timestamp(manifest['completed_at']),
            'WH_CAPTURE_MANIFEST_CLOCK_CONFLICT')
    require((manifest['capture_authorization'] is None) == allow_simulation,
            'WH_CAPTURE_SIMULATION_AUTHORIZATION_DRIFT')
    require(manifest['capture_id'].startswith('sim:' if allow_simulation else 'actual:'),
            'WH_CAPTURE_CAPTURE_ID_NAMESPACE_DRIFT')
    return {'manifest': manifest, 'reconstructed': reconstructed}


def readiness():
    return metadata('WAVE_H_ACTUAL_COLLECTOR_READINESS', {
        'implementation': 'READY_FOR_ONE_SHOT_OWNER_AUTH',
        'actual_capture': 'NOT_YET_RUN', 'actual_forward_days': 0,
        'max_requests': 13, 'fixed_endpoint': ENDPOINT, 'exact_symbols': list(SYMBOLS),
        'source_schema_version': SCHEMA_VERSION, 'raw_response_hash_is_schema_version': False,
        'credential_lookup_in_H_A': 'NOT_ATTEMPTED', 'authenticated_requests_in_H_A': 0,
        'runtime_prerequisites': ['external_owner_public_key_enrollment',
            'fresh_signed_capture_grant', 'actual_session_eod_witness_with_originals',
            'named_keychain_credential_presence', 'independent_original_reopen_acceptance',
            'separate_forward_grant'],
        'provider_license_transport': 'UNKNOWN_NOT_ADMITTED',
        'historical_first_visible': 'NOT_ASSERTED',
        'no_retry_redirect_proxy_fallback': True,
        'native_signal_order_fill_broker_cloud_production': 'BLOCKED'})


def issue_order(*args, **kwargs):
    raise ValueError('WH_CAPTURE_NATIVE_ORDER_BROKER_FORBIDDEN')


def cloud_export(*args, **kwargs):
    raise ValueError('WH_CAPTURE_CLOUD_EXPORT_FORBIDDEN')
