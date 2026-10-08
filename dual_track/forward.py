"""Owner-text freeze, fixture scorer and separate reviewed-evidence entry.

Actual research outcomes must reopen the existing H-A signed Snapshot B chain.
Neither path can create a Snapshot B, a trading authority or an actual forward day.
"""
from __future__ import annotations

import json
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .common import (BOUNDARIES, ORIGINAL_HASH, SYMBOLS, canonical, closed, day,
                     decimal, instant, now, precision80, ratio, ref, reopen, require, sha, text, write_new)

TARGETS = {1: '2026-10-08', 5: '2026-10-14', 10: '2026-10-21'}
PREOPEN = '2026-10-08T09:30:00+08:00'
PREDICTION_FIELDS = ('version', 'kind', 'prediction_id', 'namespace', 'boundaries',
    'producer', 'source_ref', 'original_artifact_sha256_claim', 'original_artifact_state',
    'frozen_at', 'timestamp_evidence', 'base_session', 'base_price_evidence',
    'target_mapping_evidence', 'entries', 'd10_ordinal_order', 'd10_centers_tied',
    'probability_calibrated', 'bands_calibrated', 'version_parent', 'invalidation', 'reason_codes')
ENTRY_FIELDS = ('symbol', 'horizon', 'target_session', 'base_close_cny', 'low_return_percent',
    'high_return_percent', 'center_return_percent', 'd10_positive_probability_percent',
    'quoted_d10_center_price_cny', 'derived_center_price_cny')


@precision80
def validate_prediction(prediction):
    closed(prediction, PREDICTION_FIELDS)
    require(prediction['version'] == '1.0.0' and prediction['kind'] == 'ForwardPrediction', 'DT_VERSION')
    require(prediction['namespace'] == 'FORWARD_RESEARCH_ONLY:CORE_40:OWNER_TEXT_V1', 'DT_NAMESPACE')
    require(canonical(prediction['boundaries']) == canonical(BOUNDARIES), 'DT_AUTHORITY_BOUNDARY')
    require(prediction['prediction_id'] == 'ForwardPrediction-v1-OWNER_TEXT_IMPORT', 'DT_PREDICTION_ID')
    require(prediction['producer'] == 'OWNER_TEXT_CHATGPT_ASSISTED_UNVERIFIED', 'DT_PRODUCER')
    require(prediction['original_artifact_state'] == 'ORIGINAL_NOT_PROVIDED_HASH_NOT_VERIFIED' and
            prediction['original_artifact_sha256_claim'] == 'sha256:' + ORIGINAL_HASH, 'DT_ORIGINAL_CLAIM')
    require(instant(prediction['frozen_at']) < instant(PREOPEN), 'DT_PREOPEN_DEADLINE_MISSED')
    require(prediction['timestamp_evidence'] == 'LOCAL_HOST_CLOCK_NO_INDEPENDENT_TIMESTAMP', 'DT_TIMESTAMP_EVIDENCE')
    require(prediction['base_session'] == '2026-09-30' and
            prediction['base_price_evidence'] == 'OWNER_SUPPLIED_RAW_CLOSE_ASSUMPTION_UNVERIFIED' and
            prediction['target_mapping_evidence'] == 'OWNER_PLANNED_SESSIONS_NOT_ACTUAL_OPEN_WITNESS', 'DT_SOURCE_EVIDENCE')
    require(prediction['bands_calibrated'] is False and prediction['probability_calibrated'] is False and
            prediction['version_parent'] is None, 'DT_CALIBRATION_OR_VERSION')
    closed(prediction['source_ref'], ('path', 'sha256', 'bytes'))
    require(type(prediction['entries']) is list and len(prediction['entries']) == 9, 'DT_COHORT')
    seen = set()
    for entry in prediction['entries']:
        closed(entry, ENTRY_FIELDS)
        symbol, horizon = entry['symbol'], entry['horizon']
        require(symbol in SYMBOLS and type(horizon) is int and horizon in TARGETS, 'DT_COHORT')
        require((symbol, horizon) not in seen and entry['target_session'] == TARGETS[horizon], 'DT_DUPLICATE_OR_TARGET')
        seen.add((symbol, horizon))
        base = decimal(entry['base_close_cny'])
        low, center, high = [decimal(entry[k]) for k in ('low_return_percent', 'center_return_percent', 'high_return_percent')]
        require(base > 0 and Decimal('-100') < low <= center <= high, 'DT_PRICE_OR_BAND')
        derived = (base * (1 + center / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        require(decimal(entry['derived_center_price_cny']) == derived, 'DT_ROUNDING')
        if horizon == 10:
            require(0 <= decimal(entry['d10_positive_probability_percent']) <= 100 and
                    decimal(entry['quoted_d10_center_price_cny']) == derived, 'DT_D10_FIELDS')
        else:
            require(entry['d10_positive_probability_percent'] is None and entry['quoted_d10_center_price_cny'] is None, 'DT_OPTIONAL_FIELDS')
    require(prediction['d10_ordinal_order'] == list(SYMBOLS) and
            prediction['d10_centers_tied'] == ['600312.SH', '603228.SH'], 'DT_RANK_TIE')
    require(prediction['invalidation'] == ['FILE_HASH_CHANGED', 'BASE_ASSUMPTION_DISPROVED', 'TARGET_SESSION_MAPPING_DISPROVED',
            'SOURCE_TEXT_CHANGED', 'BOUNDARY_CHANGED'], 'DT_INVALIDATION')
    require(prediction['reason_codes'] == ['ORIGINAL_ARTIFACT_MISSING', 'NEW_OWNER_TEXT_IMPORT',
            'SUBJECTIVE_PROBABILITY_NOT_WIN_RATE', 'NO_ACTUAL_MARKET_OUTCOMES'], 'DT_REASONS')
    canonical(prediction)
    return prediction


def owner_text_prediction(source_ref):
    # Exact numerical transcription of the Owner-supplied table; no new research.
    table = {
        '603993.SH': ('16.88', '64', '17.72', [('-1.0', '3.5', '1.2'), ('-2.5', '7.0', '3.5'), ('-3.5', '9.0', '5.0')]),
        '600312.SH': ('20.29', '60', '20.90', [('-1.0', '2.5', '0.7'), ('-2.0', '5.0', '2.0'), ('-3.0', '7.0', '3.0')]),
        '603228.SH': ('101.21', '55', '104.25', [('-2.5', '5.0', '1.5'), ('-7.0', '10.0', '2.0'), ('-10.0', '12.0', '3.0')])}
    entries = []
    for symbol in SYMBOLS:
        base, probability, quoted, bands = table[symbol]
        for horizon, band in zip(TARGETS, bands):
            low, high, center = band
            derived = (Decimal(base) * (1 + Decimal(center) / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            entries.append({'symbol': symbol, 'horizon': horizon, 'target_session': TARGETS[horizon],
                'base_close_cny': base, 'low_return_percent': low, 'high_return_percent': high,
                'center_return_percent': center, 'd10_positive_probability_percent': probability if horizon == 10 else None,
                'quoted_d10_center_price_cny': quoted if horizon == 10 else None, 'derived_center_price_cny': text(derived)})
    return validate_prediction({'version': '1.0.0', 'kind': 'ForwardPrediction',
        'prediction_id': 'ForwardPrediction-v1-OWNER_TEXT_IMPORT', 'namespace': 'FORWARD_RESEARCH_ONLY:CORE_40:OWNER_TEXT_V1',
        'boundaries': deepcopy(BOUNDARIES), 'producer': 'OWNER_TEXT_CHATGPT_ASSISTED_UNVERIFIED', 'source_ref': source_ref,
        'original_artifact_sha256_claim': 'sha256:' + ORIGINAL_HASH,
        'original_artifact_state': 'ORIGINAL_NOT_PROVIDED_HASH_NOT_VERIFIED', 'frozen_at': now(),
        'timestamp_evidence': 'LOCAL_HOST_CLOCK_NO_INDEPENDENT_TIMESTAMP', 'base_session': '2026-09-30',
        'base_price_evidence': 'OWNER_SUPPLIED_RAW_CLOSE_ASSUMPTION_UNVERIFIED',
        'target_mapping_evidence': 'OWNER_PLANNED_SESSIONS_NOT_ACTUAL_OPEN_WITNESS', 'entries': entries,
        'd10_ordinal_order': list(SYMBOLS), 'd10_centers_tied': ['600312.SH', '603228.SH'],
        'probability_calibrated': False, 'bands_calibrated': False, 'version_parent': None,
        'invalidation': ['FILE_HASH_CHANGED', 'BASE_ASSUMPTION_DISPROVED', 'TARGET_SESSION_MAPPING_DISPROVED', 'SOURCE_TEXT_CHANGED', 'BOUNDARY_CHANGED'],
        'reason_codes': ['ORIGINAL_ARTIFACT_MISSING', 'NEW_OWNER_TEXT_IMPORT', 'SUBJECTIVE_PROBABILITY_NOT_WIN_RATE', 'NO_ACTUAL_MARKET_OUTCOMES']})


def freeze_from_text(source, directory):
    directory = Path(directory)
    directory.mkdir(mode=0o700)  # No overwrite or silent resumed freeze.
    source_bytes = Path(source).read_bytes()
    source_copy = directory / 'Owner-Provided-Text.txt'
    with source_copy.open('xb') as stream:
        stream.write(source_bytes)
        stream.flush()
        import os
        os.fsync(stream.fileno())
    source_copy.chmod(0o400)
    prediction = owner_text_prediction(ref(source_copy))
    prediction_ref = write_new(directory / 'ForwardPrediction-v1-OWNER_TEXT_IMPORT.json', prediction)
    require(prediction_ref['sha256'] != 'sha256:' + ORIGINAL_HASH, 'DT_NOT_ORIGINAL')
    return write_new(directory / 'Freeze-Receipt.json', {'version': '1.0.0', 'kind': 'ForwardFreezeReceipt',
        'prediction_ref': prediction_ref, 'source_ref': ref(source_copy), 'recorded_at': now(),
        'original_hash_verified': False, 'new_hash_is_not_original': True,
        'preopen_by_local_host_clock': True, 'independent_timestamp': False,
        'human_execution_signature': False, 'actual_authority': False, 'outcome_count': 0})


@precision80
def synthetic_score(prediction, symbol, horizon, bars):
    """Fixture arithmetic only. Every path observation is required; no stale fill."""
    validate_prediction(prediction)
    entry = next((e for e in prediction['entries'] if e['symbol'] == symbol and e['horizon'] == horizon), None)
    require(entry is not None, 'DT_SCORE_SCOPE')
    require(type(bars) is list and len(bars) == horizon, 'DT_COMPLETE_PATH_REQUIRED')
    previous = prediction['base_session']
    for bar in bars:
        closed(bar, ('mode', 'symbol', 'session', 'open', 'high', 'low', 'close'))
        require(bar['mode'] == 'SYNTHETIC_FIXTURE', 'DT_REAL_EVIDENCE_ADAPTER_NOT_ADMITTED')
        require(bar['symbol'] == symbol and previous < day(bar['session']) <= TARGETS[horizon], 'DT_PATH_SCOPE_OR_ORDER')
        previous = bar['session']
        op, hi, lo, cl = [decimal(bar[k]) for k in ('open', 'high', 'low', 'close')]
        require(0 < lo <= min(op, cl) <= max(op, cl) <= hi, 'DT_OHLC')
    require(bars[-1]['session'] == TARGETS[horizon], 'DT_TARGET_NOT_OBSERVED')
    # Calendar completeness is NOT authenticated by len=h; fixture-only result.
    base, close = decimal(entry['base_close_cny']), decimal(bars[-1]['close'])
    realized = ratio(close, base) * 100
    center, low, high = [decimal(entry[k]) for k in ('center_return_percent', 'low_return_percent', 'high_return_percent')]
    sign = lambda value: (value > 0) - (value < 0)
    return {'symbol': symbol, 'horizon': horizon, 'target_session': TARGETS[horizon],
        'realized_return_percent': text(realized), 'forecast_error_percent_points': text(realized - center),
        'direction_hit': sign(realized) == sign(center), 'range_hit': low <= realized <= high,
        'mae_percent': text(min(Decimal(0), min(ratio(decimal(b['low']), base)*100 for b in bars))),
        'mfe_percent': text(max(Decimal(0), max(ratio(decimal(b['high']), base)*100 for b in bars))),
        'zero_direction_policy': 'THREE_WAY_SIGN_ZERO_IS_NEUTRAL', 'action_reconciliation': 'UNKNOWN',
        'metric_scope': 'SYNTHETIC_RAW_PRICE_PATH_NOT_EXECUTION_PNL'}


def d10_ranking(prediction, scores):
    validate_prediction(prediction)
    require(type(scores) is list and len(scores) == 3 and {s['symbol'] for s in scores} == set(SYMBOLS) and
            all(s['horizon'] == 10 for s in scores), 'DT_COMPLETE_D10_REQUIRED')
    scopes = {s['metric_scope'] for s in scores}
    require(len(scopes)==1 and scopes <= {'SYNTHETIC_RAW_PRICE_PATH_NOT_EXECUTION_PNL',
                                        'CURRENT_REVIEWED_RAW_PRICE_NOT_EXECUTION_PNL'}, 'DT_RANK_MODE')
    if 'CURRENT_REVIEWED_RAW_PRICE_NOT_EXECUTION_PNL' in scopes:
        from .reviewed import score_actual_snapshot
        for score in scores:
            actual = score_actual_snapshot(prediction, score['snapshot_ref'], score['symbol'], 10, score['scored_at'])
            require(canonical(actual)==canonical(score), 'DT_REAL_OUTCOME_REOPEN_CHANGED')
    values = {s['symbol']: decimal(s['realized_return_percent']) for s in scores}
    groups = [[s for s in SYMBOLS if values[s] == value] for value in sorted(set(values.values()), reverse=True)]
    comparisons = [values[a] > values[b] for i, a in enumerate(SYMBOLS) for b in SYMBOLS[i+1:]]
    return {'actual_tie_groups': groups, 'ordinal_order_hit': all(comparisons),
            'strict_pairwise_hits': sum(comparisons), 'strict_pairwise_count': 3,
            'center_prediction_tie_preserved': ['600312.SH', '603228.SH'],
            'ranking_scope': 'OWNER_EXPLICIT_ORDINAL_NOT_DERIVED_FROM_TIED_CENTERS'}


def fixture_head(store, prediction_ref, mode='SYNTHETIC_FIXTURE'):
    store = Path(store)
    frozen = json.loads(reopen(prediction_ref))
    validate_prediction(frozen)
    reopen(frozen['source_ref'])
    require(mode in ('SYNTHETIC_FIXTURE', 'ACTUAL_RESEARCH_ONLY'), 'DT_MODE')
    genesis = sha(canonical({'namespace': mode, 'store': str(store.resolve()), 'prediction_ref': prediction_ref}))
    if not store.exists(): return genesis, set()
    require(not store.is_symlink(), 'DT_STORE_SYMLINK')
    previous, seen = genesis, set()
    paths = sorted(store.glob('*.json'))
    require([p.name for p in paths] == [f'{i:03d}.json' for i in range(1, len(paths)+1)], 'DT_STORE_SEQUENCE')
    for index, path in enumerate(paths, 1):
        row = json.loads(path.read_bytes())
        closed(row, ('version', 'kind', 'mode', 'sequence', 'previous_hash', 'prediction_sha256', 'score', 'hash'))
        content = {k: v for k, v in row.items() if k != 'hash'}
        require(row['version'] == '1.0.0' and row['kind'] == 'ForwardOutcome' and row['mode'] == mode and
                row['sequence'] == index and row['previous_hash'] == previous and
                row['prediction_sha256'] == prediction_ref['sha256'] and row['hash'] == sha(canonical(content)), 'DT_STORE_CHAIN_CHANGED')
        key = (row['score']['symbol'], row['score']['horizon'])
        require(key not in seen, 'DT_DUPLICATE_OUTCOME')
        if mode == 'ACTUAL_RESEARCH_ONLY':
            from .reviewed import score_actual_snapshot
            expected = score_actual_snapshot(frozen, row['score']['snapshot_ref'], key[0], key[1], row['score']['scored_at'])
            require(canonical(expected) == canonical(row['score']), 'DT_REAL_OUTCOME_REOPEN_CHANGED')
        seen.add(key); previous = row['hash']
    return previous, seen


def append_fixture_outcome(store, prediction_ref, expected_head, symbol, horizon, bars):
    """One exclusive segment per append. No real store or day count mutation."""
    current, seen = fixture_head(store, prediction_ref)
    require(current == expected_head, 'DT_STALE_HEAD')
    require((symbol, horizon) not in seen, 'DT_DUPLICATE_OUTCOME')
    prediction = json.loads(reopen(prediction_ref))
    score = synthetic_score(prediction, symbol, horizon, bars)
    body = {'version': '1.0.0', 'kind': 'ForwardOutcome', 'mode': 'SYNTHETIC_FIXTURE',
        'sequence': len(seen)+1, 'previous_hash': current, 'prediction_sha256': prediction_ref['sha256'], 'score': score}
    body['hash'] = sha(canonical(body))
    return write_new(Path(store) / f'{len(seen)+1:03d}.json', body)


def append_actual_outcome(*args, **kwargs):
    from .reviewed import append_reviewed_outcome
    return append_reviewed_outcome(*args, **kwargs)
