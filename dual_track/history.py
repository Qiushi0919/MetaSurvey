"""Retrospective price-prefix reconstruction, NEVER admitted historical PIT.

No current fundamental, classification, name or announcement enters this path.
The parameter-free reference forecast is not either frozen MetaSurvey family.
Every forecast is persisted before this run's labels are revealed, while the
predecessor's full historical sample exposure remains explicitly disclosed.
"""
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path
from statistics import median

from wave_g.diagnostic import _group, _read_inputs, price_features, validate_calendar, FAMILIES
from .common import BOUNDARIES, HORIZONS, SYMBOLS, ROOT, canonical, now, ratio, ref, reopen, require, sha, text, write_new

COST_GRID_BPS = (0, 5, 10, 25, 50)


def prefix_forecast(rows, cutoff, horizon, calendar, symbol):
    """Completed past h-session close changes only; no tuning or future labels."""
    require(type(horizon) is int and horizon in HORIZONS, 'DT_HORIZON')
    require(calendar['state'] == 'COMPLETE_CURRENT_REFERENCE_RECONSTRUCTION', 'DT_REFERENCE_CALENDAR_REQUIRED')
    unique, conflicts, duplicates = _group(rows, cutoff=cutoff, symbol=symbol)
    dates = [d for d in calendar['open_dates'] if d <= cutoff and d >= min(calendar['open_dates'])]
    # Limit to the observed dataset span; earlier calendar-only dates are not data.
    if unique:
        dates = [d for d in dates if d >= min(unique)]
    out = {'symbol': symbol, 'logical_cutoff_date': cutoff, 'horizon': horizon,
        'method': 'EXPANDING_PAST_HORIZON_MEAN_RAW_RETURN_REFERENCE_ONLY',
        'training_start': dates[0] if dates else None, 'training_end_max': None, 'training_pairs': 0,
        'parameter_selection': 'NONE', 'center_return_ratio': None,
        'missing_gates': 'FULL_STRATEGY_NOT_ACTIVE', 'decision': 'NO_DECISION',
        'historical_visibility_proven': False, 'logical_date_prefix_only': True,
        'state': 'WARMUP', 'reason_codes': ['PREDECESSOR_SAMPLE_ALREADY_EXPOSED', 'CURRENT_RECONSTRUCTION_NOT_HISTORICAL_PIT'],
        'prefix_hash': sha(canonical([{k: text(v) if isinstance(v, Decimal) else v for k,v in unique[d].items()
                                      if k in ('trade_date', 'open', 'high', 'low', 'close', 'vol', 'source_refs')}
                                     for d in sorted(unique)])), 'identical_duplicate_dates': len(duplicates)}
    if conflicts or any(d not in unique for d in dates) or cutoff not in unique:
        out['state'] = 'BLOCKED'; out['reason_codes'].append('PRICE_PREFIX_CONFLICT_OR_GAP'); return out
    with localcontext() as ctx:
        ctx.prec = 80
        training = [ratio(unique[dates[j+horizon]]['close'], unique[dates[j]]['close'])
                    for j in range(len(dates)-horizon)]
        if training:
            out.update(center_return_ratio=text(sum(training, Decimal(0))/Decimal(len(training))),
                       training_pairs=len(training), training_end_max=dates[-1], state='FROZEN_REFERENCE_FORECAST')
    return out


def reveal_label(rows, cutoff, horizon, calendar, symbol):
    require(type(horizon) is int and horizon in HORIZONS, 'DT_HORIZON')
    require(calendar['state'] == 'COMPLETE_CURRENT_REFERENCE_RECONSTRUCTION', 'DT_REFERENCE_CALENDAR_REQUIRED')
    unique, conflicts, _ = _group(rows, symbol=symbol)
    dates = calendar['open_dates']
    out = {'symbol': symbol, 'logical_cutoff_date': cutoff, 'horizon': horizon,
        'state': 'PENDING', 'endpoint_date': None, 'raw_return_ratio': None,
        'mae_ratio': None, 'mfe_ratio': None, 'close_path_max_drawdown_ratio': None,
        'source_hashes': [], 'historical_visibility_proven': False,
        'basis': 'CURRENT_REFERENCE_RAW_CLOSE_LABEL_NOT_EXECUTION', 'reason_codes': []}
    if cutoff not in dates or dates.index(cutoff)+horizon >= len(dates):
        out['reason_codes'] = ['ENDPOINT_NOT_OBSERVED']; return out
    pathdates = dates[dates.index(cutoff):dates.index(cutoff)+horizon+1]
    out['endpoint_date'] = pathdates[-1]
    if any(d not in unique for d in pathdates) or any(c['trade_date'] in pathdates for c in conflicts):
        out['state'] = 'BLOCKED'; out['reason_codes'] = ['LABEL_PATH_GAP_OR_CONFLICT']; return out
    path = [unique[d] for d in pathdates]; base = path[0]['close']
    with localcontext() as ctx:
        ctx.prec = 80
        peak = base; maxdd = Decimal(0)
        for bar in path:
            peak = max(peak, bar['close']); maxdd = max(maxdd, 1 - bar['close']/peak)
        out.update(state='OBSERVED_RAW_LABEL', raw_return_ratio=text(ratio(path[-1]['close'], base)),
            mae_ratio=text(min(Decimal(0), min(ratio(b['low'], base) for b in path[1:]))),
            mfe_ratio=text(max(Decimal(0), max(ratio(b['high'], base) for b in path[1:]))),
            close_path_max_drawdown_ratio=text(maxdd))
    out['source_hashes'] = sorted({s['raw_sha256'] for b in path for s in b['source_refs']})
    out['reason_codes'] = ['ACTION_STATUS_UNIT_LICENSE_UNVERIFIED', 'NO_EXECUTION_OR_TOTAL_RETURN']
    return out


def distribution(pairs):
    if not pairs:
        return {'count': 0, 'direction_hit_fraction': None, 'median_raw_label_ratio': None,
                'mean_raw_label_ratio': None, 'mean_absolute_forecast_error_ratio': None,
                'median_mae_ratio': None, 'median_mfe_ratio': None, 'max_close_path_drawdown_ratio': None,
                'cost_sensitivity': [], 'dependence': 'OVERLAPPING_TARGET_WINDOWS_NOT_INDEPENDENT_TRADES'}
    with localcontext() as ctx:
        ctx.prec = 80
        returns = [Decimal(label['raw_return_ratio']) for forecast,label in pairs]
        forecast_values = [Decimal(forecast['center_return_ratio']) for forecast,label in pairs]
        sign = lambda x: (x > 0) - (x < 0)
        return {'count': len(pairs),
            'direction_hit_fraction': text(Decimal(sum(sign(a)==sign(b) for a,b in zip(returns,forecast_values)))/len(pairs)),
            'median_raw_label_ratio': text(median(returns)), 'mean_raw_label_ratio': text(sum(returns)/len(pairs)),
            'mean_absolute_forecast_error_ratio': text(sum(abs(a-b) for a,b in zip(returns,forecast_values))/len(pairs)),
            'median_mae_ratio': text(median(Decimal(l['mae_ratio']) for _,l in pairs)),
            'median_mfe_ratio': text(median(Decimal(l['mfe_ratio']) for _,l in pairs)),
            'max_close_path_drawdown_ratio': text(max(Decimal(l['close_path_max_drawdown_ratio']) for _,l in pairs)),
            'cost_sensitivity': [{'roundtrip_bps': bps, 'basis': 'SYNTHETIC_SCENARIO_SUBTRACTION_NOT_BROKER_COST',
                'median_label_minus_cost_ratio': text(median(returns)-Decimal(bps)/10000),
                'positive_label_minus_cost_fraction': text(Decimal(sum(r>Decimal(bps)/10000 for r in returns))/len(pairs))}
                for bps in COST_GRID_BPS],
            'dependence': 'OVERLAPPING_TARGET_WINDOWS_NOT_INDEPENDENT_TRADES'}


def run(directory, protocol_ref):
    directory = Path(directory)
    directory.mkdir(mode=0o700)
    protocol = json.loads(reopen(protocol_ref))
    require(protocol['horizons'] == list(HORIZONS) and protocol['cost_grid_roundtrip_bps'] == list(COST_GRID_BPS), 'DT_PROTOCOL_CHANGED')
    inputs, direct_refs = _read_inputs()  # Original raw bodies independently hash reopened.
    daily, calendars, forecasts, timing = {}, {}, [], []
    for symbol in SYMBOLS:
        observations = inputs[symbol]['wave-d_input']['body']['observations']
        rows = [{**deepcopy(o['values']), 'source_ref': deepcopy(o['source_ref'])} for o in observations if o['api_name'] == 'daily']
        cal = validate_calendar([o for o in observations if o['api_name'] == 'trade_cal'])
        unique, conflicts, _ = _group(rows, symbol=symbol)
        require(not conflicts and len(unique) == 327, 'DT_FROZEN_PRICE_DATA_CHANGED')
        daily[symbol], calendars[symbol] = rows, cal
        for cutoff in sorted(unique):
            # Current calendar may bound prefix windows; it is not PIT evidence.
            features = price_features(rows, cutoff, symbol=symbol, calendar=cal)
            timing.append({'symbol': symbol, 'cutoff': cutoff, 'components': features['price_component'],
                           'full_family_decision': features['full_family_decision']})
            for horizon in HORIZONS:
                forecasts.append(prefix_forecast(rows, cutoff, horizon, cal, symbol))
    frozen_ref = write_new(directory / 'Historical-Predictions-FROZEN.json', {'version': '1.0.0',
        'kind': 'HistoricalLitePredictionFreeze', 'namespace': 'RETROSPECTIVE_DIAGNOSTIC_ONLY:CORE_40:PRICE_PREFIX',
        'protocol_ref': protocol_ref, 'frozen_at': now(), 'boundaries': deepcopy(BOUNDARIES),
        'sample_previously_exposed': True, 'untouched_oos': False, 'predictions': forecasts,
        'timing_components': timing, 'direct_source_refs': direct_refs})
    # Reopen the immutable bytes; labels are computed ONLY after freeze persisted.
    frozen = json.loads(reopen(frozen_ref))
    labels, pairs = [], []
    for forecast in frozen['predictions']:
        label = reveal_label(daily[forecast['symbol']], forecast['logical_cutoff_date'], forecast['horizon'],
                             calendars[forecast['symbol']], forecast['symbol'])
        labels.append(label)
        if forecast['state'] == 'FROZEN_REFERENCE_FORECAST' and label['state'] == 'OBSERVED_RAW_LABEL':
            pairs.append((forecast, label))
    label_ref = write_new(directory / 'Historical-Labels-AFTER-FREEZE.json', {'version': '1.0.0',
        'kind': 'RetrospectiveRawLabels', 'prediction_ref': frozen_ref, 'revealed_at': now(), 'labels': labels})
    states = {f: Counter(t['components'][f] for t in timing) for f in FAMILIES}
    timing_map = {(t['symbol'],t['cutoff']):t['components'] for t in timing}
    board = {'version': '1.0.0', 'kind': 'HistoricalLiteScoreboard',
        'state': 'RETROSPECTIVE_RECONSTRUCTION_COMPLETE_FORMAL_OOS_BLOCKED', 'boundaries': deepcopy(BOUNDARIES),
        'protocol_ref': protocol_ref, 'prediction_ref': frozen_ref, 'label_ref': label_ref,
        'scored_at': now(), 'symbols': list(SYMBOLS), 'observed_sessions_per_symbol': 327,
        'forecast_method': protocol['forecast_method'], 'parameter_selection': 'NONE',
        'sample_previously_exposed': True, 'untouched_oos': False, 'formal_price_pit': False,
        'forecast_rows': len(forecasts), 'scored_rows': len(pairs),
        'forecast_states': dict(Counter(f['state'] for f in forecasts)), 'label_states': dict(Counter(l['state'] for l in labels)),
        'reference_forecast_distribution': distribution(pairs),
        'by_horizon': {str(h): distribution([(f,l) for f,l in pairs if f['horizon']==h]) for h in HORIZONS},
        'by_symbol_horizon': {s: {str(h): distribution([(f,l) for f,l in pairs if f['symbol']==s and f['horizon']==h])
                                 for h in HORIZONS} for s in SYMBOLS},
        'timing_component_counts': {f: dict(states[f]) for f in FAMILIES},
        'timing_component_label_distributions': {f: {str(h): {state: distribution([(p,l) for p,l in pairs
            if p['horizon']==h and timing_map[(p['symbol'],p['logical_cutoff_date'])][f]==state])
            for state in ('TRUE','FALSE','UNKNOWN')} for h in HORIZONS} for f in FAMILIES},
        'full_family_decisions': {'NO_DECISION': len(timing)*2},
        'execution_metrics': {'gross_portfolio_return': None, 'actual_fee_net_return': None,
            'portfolio_max_drawdown': None, 'turnover': None, 'strategy_trade_count': 0,
            'benchmark_excess_return': None, 'S_A_B_C_X_layers': None,
            'reason_codes': ['NO_PORTFOLIO_OR_FILLS_SIMULATED', 'ACTUAL_COST_ACCOUNT_RISK_UNSET_REQUIRED',
                'BENCHMARK_POLICY_UNSET_REQUIRED', 'GRADE_EDGE_CALIBRATION_UNSET_REQUIRED']},
        'missing_validations': ['INDEPENDENT_HISTORICAL_FIRST_VISIBILITY', 'COMPLETE_ACTION_STATUS_CHRONOLOGY',
            'UNBIASED_HISTORICAL_UNIVERSE', 'SOURCE_PROVIDER_LICENSE', 'UNTOUCHED_OOS', 'EXECUTABLE_STRATEGY_AND_LEDGER'],
        'cost_grid_scope': 'SYNTHETIC_LABEL_SENSITIVITY_NOT_FEE_INCLUSIVE_AFFORDABILITY_OR_PROFIT'}
    return write_new(directory / 'Historical-Lite-Scoreboard.json', board)
