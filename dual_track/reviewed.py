"""Read-only adapter to the existing authenticated H-A Snapshot B validator.

No producer-provided normalised prices or fixture signatures are trusted.
This reopens the signed capture, independent review, all raw originals, actual
session witness and fixed Reference A. No grant, capture or forward day created.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from .common import FORWARD_V1_REF, SYMBOLS, canonical, decimal, instant, now, precision80, reopen, require, sha, text, ratio, write_new
from .forward import TARGETS, PREOPEN, validate_prediction, fixture_head


@precision80
def score_actual_snapshot(prediction, snapshot_ref, symbol, horizon, scored_at=None):
    validate_prediction(prediction)
    reopen(prediction['source_ref'])
    require(sha(canonical(prediction)) == FORWARD_V1_REF['sha256'], 'DT_V1_PREDICTION_NOT_REGISTERED')
    reopen(FORWARD_V1_REF)
    require(symbol in SYMBOLS and type(horizon) is int and horizon in TARGETS, 'DT_SCORE_SCOPE')
    scored_at = now() if scored_at is None else scored_at
    current = instant(now())
    require(instant(scored_at) <= current, 'DT_FUTURE_SCORING_CLOCK')
    # This is the frozen original validator, not a copied or relaxed replacement.
    from wave_h.forward import _validate_snapshot, _json
    from wave_h.common import reopen as original_reopen
    snapshot = _json(reopen(snapshot_ref))
    _validate_snapshot(snapshot, True, restart=True)
    body = snapshot['body']
    session = body['session']
    require(session == TARGETS[horizon], 'DT_TARGET_NOT_OBSERVED')
    eod = instant(session + 'T15:00:00+08:00')
    require(instant(prediction['frozen_at']) < instant(PREOPEN) and eod <= instant(scored_at), 'DT_REVEAL_BEFORE_EOD')
    manifest = _json(original_reopen(body['capture_manifest_ref'], private=True))
    witness = _json(original_reopen(body['expected_plan']['session_evidence_ref'], private=True))
    require(eod <= instant(witness['observed_at']) <= instant(manifest['started_at']) <=
            instant(manifest['completed_at']) <= instant(scored_at), 'DT_EOD_CAPTURE_CLOCK')
    entry = next(e for e in prediction['entries'] if e['symbol']==symbol and e['horizon']==horizon)
    # Verify the quoted base against the original pinned raw Reference A.
    anchor = _json(original_reopen(body['snapshot_a_ref'], private=True))
    require(anchor['session_date'] == prediction['base_session'], 'DT_BASE_SESSION_DRIFT')
    base_ref = anchor['source_original_refs'][list(SYMBOLS).index(symbol)]
    base_original = _json(original_reopen(base_ref, private=True), True)['data']
    base_rows = [dict(zip(base_original['fields'], row)) for row in base_original['items']]
    matching = [r for r in base_rows if r['trade_date']==prediction['base_session'].replace('-','') and r['ts_code']==symbol]
    require(len(matching)==1 and decimal(str(matching[0]['close']))==decimal(entry['base_close_cny']), 'DT_BASE_ASSUMPTION_DISPROVED')
    job = next(j for j in manifest['jobs'] if j['job']['api_name']=='daily' and j['job']['symbol']==symbol)
    source = _json(original_reopen(job['raw_ref'], private=True), True)['data']
    require(len(source['items'])==1, 'DT_DAILY_ROW_REQUIRED')
    bar = dict(zip(source['fields'], source['items'][0]))
    base = decimal(entry['base_close_cny']); realized = ratio(decimal(str(bar['close'])), base)*100
    center, low, high = [decimal(entry[k]) for k in ('center_return_percent','low_return_percent','high_return_percent')]
    sign = lambda v: (v > 0) - (v < 0)
    # D1 has one actual observed day. D5/D10 intrapath metrics remain unknown
    # until a separately proved complete session grid and all originals exist.
    mae = text(min(Decimal(0), ratio(decimal(str(bar['low'])), base)*100)) if horizon==1 else None
    mfe = text(max(Decimal(0), ratio(decimal(str(bar['high'])), base)*100)) if horizon==1 else None
    return {'symbol': symbol, 'horizon': horizon, 'target_session': session,
        'realized_return_percent': text(realized), 'forecast_error_percent_points': text(realized-center),
        'direction_hit': sign(realized)==sign(center), 'range_hit': low<=realized<=high,
        'mae_percent': mae, 'mfe_percent': mfe, 'zero_direction_policy': 'THREE_WAY_SIGN_ZERO_IS_NEUTRAL',
        'action_reconciliation': 'UNKNOWN', 'metric_scope': 'CURRENT_REVIEWED_RAW_PRICE_NOT_EXECUTION_PNL',
        'snapshot_ref': snapshot_ref, 'base_raw_ref': base_ref, 'outcome_raw_ref': job['raw_ref'],
        'clock_ref': job['clock_ref'], 'scored_at': scored_at,
        'capture_signature_verified': True, 'independent_review_signature_verified': True,
        'base_assumption_matches_pinned_raw': True, 'source_admission': 'BLOCKED',
        'path_metric_state': 'D1_RAW_PATH_OBSERVED' if horizon==1 else 'COMPLETE_PATH_CALENDAR_AND_ORIGINALS_REQUIRED',
        'horizon_mapping': 'OWNER_FIXED_TARGET_DATE_NOT_HISTORICAL_SESSION_AUTHORITY',
        'actual_authority': False, 'actual_forward_days_increment': 0,
        'reason_codes': ['SOURCE_PROVIDER_LICENSE_ACTIONS_UNRESOLVED', 'NO_EXECUTION_OR_PROFIT_AUTHORITY']}


def append_reviewed_outcome(store, prediction_ref, expected_head, snapshot_ref, symbol, horizon):
    current, seen = fixture_head(store, prediction_ref, 'ACTUAL_RESEARCH_ONLY')
    require(current==expected_head, 'DT_STALE_HEAD')
    require((symbol,horizon) not in seen, 'DT_DUPLICATE_OUTCOME')
    prediction = json.loads(reopen(prediction_ref))
    score = score_actual_snapshot(prediction, snapshot_ref, symbol, horizon)
    body = {'version':'1.0.0', 'kind':'ForwardOutcome', 'mode':'ACTUAL_RESEARCH_ONLY',
            'sequence':len(seen)+1, 'previous_hash':current, 'prediction_sha256':prediction_ref['sha256'], 'score':score}
    body['hash'] = sha(canonical(body))
    return write_new(Path(store)/f'{len(seen)+1:03d}.json',body)
