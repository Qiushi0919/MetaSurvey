"""Frozen price-rule observations and raw labels; never a trading decision.

Two clocks are deliberately separate: historical trade_date bounds the logical
price prefix, while actual available/retrieved instants describe the CURRENT
reconstruction. Neither is rewritten into historical first availability.
Future labels have a separate function and never enter price_features.
"""
from __future__ import annotations

import csv
import io
import json
import os
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path

from wave_g.common import (ARCHIVE, ROOT, SYMBOLS, canonical, checked_file,
                           checked_reference, locate_reference, decimal_string, digest, metadata, protocol, reference,
                           require, sha, timestamp)

FAMILIES = ('CORE40_Q_PULLBACK_V1', 'CORE40_Q_BREAKOUT_V1')
DEST = ARCHIVE / 'diagnostic' / 'G1'
ZERO, ONE = Decimal('0'), Decimal('1')
MISSING_GATES = ['COMPANY_QUALITY_PIT_UNKNOWN', 'SECTOR_TOTAL_RETURN_RS_UNKNOWN',
                 'VALUATION_PIT_POLICY_UNKNOWN', 'CATALYST_PIT_UNKNOWN',
                 'HISTORICAL_STATUS_UNKNOWN', 'ACTION_RECONCILIATION_UNKNOWN',
                 'DATED_COST_EDGE_POLICY_UNSET_REQUIRED', 'HISTORICAL_VISIBILITY_UNKNOWN']


def _day(value):
    require(type(value) is str and len(value) == 8 and value.isdigit(), 'WG_DIAG_DATE')
    require(datetime.strptime(value, '%Y%m%d').strftime('%Y%m%d') == value, 'WG_DIAG_DATE')
    return value


def _dec(value, positive=False):
    result = decimal_string(value)
    require(len(result.as_tuple().digits) <= 50 and result.adjusted() < 50 and
            (not positive or result > ZERO), 'WG_DIAG_DECIMAL_RANGE')
    return result


def _text(value):
    require(value.is_finite(), 'WG_DIAG_NONFINITE')
    return format(value, 'f')


def _ratio_text(numerator, denominator):
    with localcontext() as ctx:
        ctx.prec = 100
        return _text(Decimal(numerator)/Decimal(denominator))


def _normal(row):
    require(type(row) is dict, 'WG_DIAG_ROW')
    _day(row['trade_date'])
    prices = {k: _dec(row[k], True) for k in ('open', 'high', 'low', 'close')}
    require(prices['low'] <= min(prices['open'], prices['close']) <=
            max(prices['open'], prices['close']) <= prices['high'], 'WG_DIAG_OHLC')
    volume = _dec(row['vol'])
    source = row.get('source_ref')
    require(type(source) is dict and source, 'WG_DIAG_SOURCE_REQUIRED')
    canonical(source)
    return {**prices, 'vol': volume, 'trade_date': row['trade_date'], 'source_ref': deepcopy(source)}


def _group(rows, cutoff=None, symbol=None, reconstruction_cutoff=None):
    """Retain conflicts; collapse only identical price/volume duplicates for arithmetic."""
    if cutoff is not None: _day(cutoff)
    reconstruction_ns=timestamp(reconstruction_cutoff) if reconstruction_cutoff is not None else None
    clock_parses={}
    def clock_ns(value):
        if value not in clock_parses:clock_parses[value]=timestamp(value)
        return clock_parses[value]
    grouped = defaultdict(list)
    for row in rows:
        # Filter dates BEFORE parsing future numeric payloads. A future corrupt
        # row/revision cannot contaminate an earlier logical prefix.
        date = _day(row['trade_date'])
        if cutoff is not None and date > cutoff: continue
        if symbol is not None and row.get('ts_code', symbol) != symbol: continue
        if reconstruction_cutoff is not None:
            source = row.get('source_ref', {})
            require(source.get('available_at') is not None and source.get('retrieved_at') is not None,
                    'WG_DIAG_RECONSTRUCTION_CLOCK_REQUIRED')
            if any(clock_ns(source[k]) > reconstruction_ns
                   for k in ('available_at', 'retrieved_at')): continue
        grouped[date].append(_normal(row))
    unique, conflicts, duplicates = {}, [], []
    for date, group in sorted(grouped.items()):
        shapes = {tuple(r[k] for k in ('open', 'high', 'low', 'close', 'vol')) for r in group}
        if len(shapes) > 1:
            conflicts.append({'trade_date': date, 'observations': [deepcopy(r['source_ref']) for r in group]})
        else:
            # Every identical version remains in lineage, no last-write winner.
            unique[date] = {**group[0], 'source_refs': [deepcopy(r['source_ref']) for r in group]}
            if len(group) > 1: duplicates.append({'trade_date': date, 'count': len(group),
                                                 'source_refs': unique[date]['source_refs']})
    return unique, conflicts, duplicates


def validate_calendar(rows):
    """Only complete explicit CURRENT reference civil-date grids prove target mapping."""
    grouped = defaultdict(list)
    for row in rows:
        values = row.get('values', row)
        _day(values['cal_date'])
        require(values['exchange'] == 'SSE' and values['is_open'] in ('0', '1'), 'WG_DIAG_CALENDAR_LITERAL')
        source = row.get('source_ref')
        require(type(source) is dict and source.get('raw_sha256') and
                source.get('available_at') and source.get('retrieved_at'), 'WG_DIAG_CALENDAR_LINEAGE')
        grouped[values['cal_date']].append(row)
    if not grouped:
        return {'state': 'UNKNOWN', 'open_dates': [], 'reason': 'CALENDAR_ABSENT'}
    first, last = min(grouped), max(grouped)
    civil = []
    day = datetime.strptime(first, '%Y%m%d')
    while day.strftime('%Y%m%d') <= last:
        civil.append(day.strftime('%Y%m%d')); day += timedelta(days=1)
    conflicts = [d for d, rs in grouped.items() if len({(r.get('values', r)['exchange'],
                   r.get('values', r)['is_open']) for r in rs}) != 1]
    missing = sorted(set(civil) - set(grouped))
    state = 'COMPLETE_CURRENT_REFERENCE_RECONSTRUCTION' if not missing and not conflicts else 'UNKNOWN'
    return {'state': state, 'first_date': first, 'last_date': last,
            'civil_date_count': len(grouped), 'observation_count': len(rows),
            'missing_civil_dates': missing, 'conflicting_dates': sorted(conflicts),
            'open_dates': sorted(d for d, rs in grouped.items() if rs[0].get('values', rs[0])['is_open'] == '1')
                         if state != 'UNKNOWN' else [],
            'source_refs': [deepcopy(r['source_ref']) for r in rows],
            'historical_visibility_proven': False, 'exchange_historical_authority': False,
            'meaning': 'CURRENT_QUARANTINED_SSE_REFERENCE_TARGET_MAPPING_ONLY'}


def price_features(rows, cutoff, *, symbol=None, calendar=None, reconstruction_cutoff=None):
    """Exact frozen price-only inequalities on an isolated prefix, Decimal100.

    Calendarless quantities have OBSERVED_BAR_WINDOW_DIAGNOSTIC scope. With a
    complete current-reference calendar, missing open-date bars block the window.
    UNKNOWN action semantics remain explicit even when RAW arithmetic exists.
    """
    unique, conflicts, duplicates = _group(rows, cutoff, symbol, reconstruction_cutoff)
    dates = sorted(unique)
    base = {'logical_diagnostic_cutoff': cutoff, 'symbol': symbol,
            'classification': 'RAW_PRICE_COMPONENT_OBSERVATION_ONLY',
            'historical_visibility_proven': False, 'full_family_decision': 'NO_DECISION',
            'full_family_reason_codes': MISSING_GATES.copy(),
            'actions': 'UNKNOWN_NOT_RECONCILED', 'status': 'UNKNOWN',
            'unit': 'PROVIDER_RAW_PRICE_AND_VOLUME_SCALE_UNVERIFIED',
            'window_basis': 'OBSERVED_BAR_WINDOW_DIAGNOSTIC',
            'source_reconstruction_cutoff': reconstruction_cutoff,
            'prefix_date_count': len(dates), 'conflicts': conflicts,
            'duplicate_dates': duplicates, 'values': {}, 'conditions': {},
            'price_component': {f: 'UNKNOWN' for f in FAMILIES}, 'source_refs': []}
    if conflicts:
        base['reason_codes'] = ['CONFLICTING_PRICE_PREFIX_NO_ARITHMETIC']; return base
    if cutoff not in unique:
        base['reason_codes'] = ['ANCHOR_BAR_MISSING']; return base
    if calendar is not None and calendar.get('state') == 'COMPLETE_CURRENT_REFERENCE_RECONSTRUCTION':
        dates = [d for d in calendar['open_dates'] if d <= cutoff]
        base['window_basis'] = 'CURRENT_REFERENCE_SESSION_WINDOW_RECONSTRUCTION'
        if cutoff not in dates:
            base['reason_codes'] = ['ANCHOR_NOT_OPEN_IN_REFERENCE']; return base
    pullback_missing=[d for d in dates[-80:] if d not in unique]
    breakout_missing=[d for d in dates[-61:] if d not in unique]
    pullback_complete=len(dates)>=80 and not pullback_missing
    breakout_complete=len(dates)>=61 and not breakout_missing
    base['family_window_completeness']={FAMILIES[0]:{'required_dates':80,'complete':pullback_complete,
         'missing_dates':pullback_missing},FAMILIES[1]:{'required_dates':61,'complete':breakout_complete,
         'missing_dates':breakout_missing}}
    if not breakout_complete:
        base['missing_window_bars']=breakout_missing
        base['reason_codes']=['REQUIRED_REFERENCE_SESSION_BAR_MISSING' if breakout_missing
                              else 'BREAKOUT_PRIOR60_REQUIRES61_OBSERVATIONS']; return base
    # Breakout is independently valid at61 observations. Pullback's MA60(t-20)
    # requires80; it must not silently delay or fill the other family's window.
    window = [unique[d] for d in dates[-80:]] if pullback_complete else [unique[d] for d in dates[-61:]]
    base['source_refs'] = [{'trade_date': r['trade_date'], 'versions': deepcopy(r['source_refs'])} for r in window]
    require(all(r['trade_date'] <= cutoff for r in window), 'WG_DIAG_FUTURE_PREFIX')
    with localcontext() as ctx:
        ctx.prec = 100
        close = window[-1]['close']
        mean = lambda xs, field: sum((x[field] for x in xs), ZERO) / Decimal(len(xs))
        ma20, ma60 = mean(window[-20:], 'close'), mean(window[-60:], 'close')
        old_ma60 = mean(window[:60], 'close') if pullback_complete else None
        true_ranges = [max(window[i]['high'] - window[i]['low'],
                           abs(window[i]['high'] - window[i-1]['close']),
                           abs(window[i]['low'] - window[i-1]['close'])) for i in range(len(window)-20,len(window))]
        atr20 = sum(true_ranges, ZERO) / Decimal(20)
        prev3 = max(r['high'] for r in window[-4:-1])
        prev60 = max(r['high'] for r in window[-61:-1])
        v20, pv20 = mean(window[-20:], 'vol'), mean(window[-21:-1], 'vol')
        distance = abs(close-ma20)/atr20 if atr20 > ZERO else None
        v3ratio = mean(window[-3:], 'vol')/v20 if v20 > ZERO else None
        bvratio = window[-1]['vol']/pv20 if pv20 > ZERO else None
        brratio = close/prev60-ONE
        values = {'close': close, 'ma20': ma20, 'ma60': ma60,
                  'ma60_slope_20': ma60-old_ma60 if old_ma60 is not None else None, 'atr20': atr20,
                  'distance_ma20_atr': distance, 'volume3_to_volume20': v3ratio,
                  'previous3_high': prev3, 'previous60_high': prev60,
                  'breakout60_ratio': brratio, 'volume_to_previous20': bvratio,
                  'extension_from_breakout': brratio}
        base['values'] = {k: _text(v) if v is not None else None for k,v in values.items()}
        c = {'close_above_ma60': close>ma60, 'ma60_slope_positive': ma60>old_ma60 if old_ma60 is not None else None,
             'distance_ma20_atr_lt1': distance<ONE if distance is not None else None,
             'volume3_to_volume20_lt0.8': v3ratio<Decimal('0.8') if v3ratio is not None else None,
             'close_above_previous3_high': close>prev3,
             'breakout60_gt0.005': brratio>Decimal('0.005'),
             'volume_to_previous20_ge1.5': bvratio>=Decimal('1.5') if bvratio is not None else None,
             'extension_from_breakout_0_to0.03': ZERO<=brratio<=Decimal('0.03')}
        base['conditions'] = c
        for family, names in [(FAMILIES[0], list(c)[:5]), (FAMILIES[1], list(c)[5:])]:
            tests = [c[n] for n in names]
            base['price_component'][family] = 'UNKNOWN' if None in tests else ('TRUE' if all(tests) else 'FALSE')
    base['reason_codes'] = ['CURRENT_RECONSTRUCTION_NOT_HISTORICAL_VISIBLE',
                            'RAW_ACTION_COMPARABILITY_UNKNOWN']
    if not pullback_complete:
        base['reason_codes'].append('PULLBACK_MA60_SLOPE_REQUIRES80_COMPLETE_OBSERVATIONS')
    return base


def forward_label(rows, observation_date, horizon, *, calendar=None, symbol=None,
                  reconstruction_cutoff=None):
    """Close(t+h)/close(t)-1 and close-path drawdown, not execution/total return."""
    require(type(horizon) is int and horizon in (5,20,60), 'WG_DIAG_HORIZON')
    _day(observation_date)
    unique, conflicts, _ = _group(rows, symbol=symbol, reconstruction_cutoff=reconstruction_cutoff)
    conflictdates = {r['trade_date'] for r in conflicts}
    dates = sorted(set(unique) | conflictdates)
    session = calendar is not None and calendar.get('state') == 'COMPLETE_CURRENT_REFERENCE_RECONSTRUCTION'
    target_dates = calendar['open_dates'] if session else dates
    out = {'observation_date': observation_date, 'horizon': horizon,
           'label_name': 'CURRENT_REFERENCE_SESSION_RAW_CLOSE_CHANGE' if session else 'OBSERVED_BAR_OFFSET_RAW_CLOSE_CHANGE',
           'session_label_state': 'CURRENT_REFERENCE_RECONSTRUCTION' if session else 'UNKNOWN',
           'historical_visibility_proven': False, 'classification': 'RAW_PRICE_DESCRIPTIVE_ONLY',
           'anchor': 'OBSERVATION_CLOSE_NOT_EXECUTION_PRICE', 'state': 'UNKNOWN',
           'raw_price_change_ratio': None, 'raw_close_path_max_drawdown_ratio': None,
           'endpoint_date': None, 'source_refs': [], 'actions': 'UNKNOWN', 'costs': 'UNKNOWN',
           'total_return': False, 'fee_inclusive_strategy_profit': False}
    if observation_date not in target_dates:
        out['reason_codes'] = ['ANCHOR_NOT_IN_LABEL_DATE_GRID']; return out
    index = target_dates.index(observation_date)
    if index+horizon >= len(target_dates):
        out['reason_codes'] = ['FUTURE_REFERENCE_OR_OBSERVED_ENDPOINT_NOT_CAPTURED']; return out
    pathdates = target_dates[index:index+horizon+1]
    out['endpoint_date'] = pathdates[-1]
    if any(d in conflictdates for d in pathdates):
        out['reason_codes'] = ['CONFLICTING_LABEL_PATH']; return out
    if any(d not in unique for d in pathdates):
        out['reason_codes'] = ['LABEL_PATH_REFERENCE_SESSION_BAR_MISSING']; return out
    with localcontext() as ctx:
        ctx.prec=100
        path = [unique[d] for d in pathdates]
        anchor = path[0]['close']; peak=anchor; maxdd=ZERO
        for row in path:
            peak=max(peak,row['close']); maxdd=max(maxdd, ONE-row['close']/peak)
        out['raw_price_change_ratio'] = _text(path[-1]['close']/anchor-ONE)
        out['raw_close_path_max_drawdown_ratio'] = _text(maxdd)
    out['source_refs'] = [{'trade_date': r['trade_date'], 'versions': deepcopy(r['source_refs'])} for r in path]
    out['state'] = 'OBSERVED_RAW_LABEL'; out['reason_codes'] = ['ACTION_AND_STATUS_BIAS_UNRESOLVED', 'NO_EXECUTION_SIMULATED']
    return out


def annotate_action_overlap(label, actions):
    """Downstream limitation annotation only, never modifies raw numbers/features."""
    result=deepcopy(label)
    result['known_action_discontinuities']=[deepcopy(a) for a in actions if
        label['endpoint_date'] is not None and label['observation_date']<a['ex_date']<=label['endpoint_date']]
    result['continuous_action_history']='UNKNOWN'
    result['known_action_cash_or_adjustment_applied']=False
    return result


def _current_limitations():
    refs=[]
    def read(ref):
        require(Path(ref['path']).is_relative_to(ARCHIVE/'public'), 'WG_DIAG_LIMITATION_SOURCE_SCOPE')
        raw=checked_file(ref['path'],ref['sha256'])
        if 'bytes' in ref:require(len(raw)==ref['bytes'],'WG_DIAG_LIMITATION_SIZE')
        refs.append({'path':ref['path'],'sha256':sha(raw),'bytes':len(raw)})
        return raw
    pitref={'path':str(ARCHIVE/'public/pit/evidence-G3.json'),
            'sha256':'sha256:76fc78400d3f251b45f1e31f07b9c01d8bddc076546e36b32c625fb469650f9d'}
    providerref={'path':str(ARCHIVE/'public/provider/manifest-G1.json'),
                 'sha256':'sha256:91968c80ff9f745641967263cf88efa71b4585f55ded55ce4a2cad465b74bf19'}
    pit=json.loads(read(pitref));provider=json.loads(read(providerref))
    require(pit['credential_lookups']==0 and pit['authenticated_requests']==0 and
            pit['historical_visibility_proven'] is False and pit['productionGate'] is False,
            'WG_DIAG_LIMITATION_AUTHORITY')
    daily=next(c for c in provider['captures'] if c['url']=='https://tushare.pro/document/2?doc_id=27')
    require(daily['authenticated'] is False and daily['http_status']==200, 'WG_DIAG_DAILY_DOCUMENT')
    dailytext=read(daily).decode('utf-8')
    require('除权价' in dailytext and 'pre_close' in dailytext, 'WG_DIAG_PRECLOSE_DOCUMENT_SEMANTIC')
    fact=next(f for f in pit['new_facts'] if f['fact_id']=='CMOC_2024_A_SHARE_DISTRIBUTION_NOTICE')
    companion=next(f for f in pit['new_facts'] if f['fact_id']=='CMOC_2024_DIFFERENTIAL_EX_REFERENCE')
    require(fact['historical_available_at'] is None and fact['effective_precision']=='DATE_ONLY' and
            fact['symbol']=='603993.SH' and fact['value']['ex_date']=='2025-06-27' and
            fact['value']['gross_cash_cny_per_share']=='0.255' and
            companion['value']['ex_reference_cash_cny_per_share']=='0.2535', 'WG_DIAG_ACTION_FACT_BINDING')
    capture=next(c for c in pit['captures'] if c['capture_id']=='action-603993-2025')
    require(capture['http_status']==200 and capture['credentials_attached'] is False, 'WG_DIAG_ACTION_ORIGINAL')
    for k in ('body_ref','capture_ref'):read(capture[k])
    text=read(capture['parsed_ref']).decode('utf-8')
    require(all(word in text for word in ('603993','2025-038','0.255','0.2535','2025/6/26','2025/6/27')),
            'WG_DIAG_ACTION_ORIGINAL_SEMANTIC')
    action={'symbol':'603993.SH','ex_date':'20250627','record_date':'20250626',
            'gross_cash_cny_per_share':'0.255','ex_reference_cash_cny_per_share':'0.2535',
            'share_class':'A_SHARE_ONLY_H_SHARE_EXCLUDED','original_ref':capture['body_ref'],
            'text_ref':capture['parsed_ref'],'retrieved_at':capture['retrieved_at'],
            'publication_date':'2025-06-23','publication_precision':'DATE_ONLY','historical_available_at':None,
            'continuous_action_history':'UNKNOWN','cash_adjustment_or_total_return_applied':False}
    semantics={'daily_document_ref':{k:daily[k] for k in ('path','sha256','bytes')},
               'pre_close':'SOURCE_EX_RIGHTS_REFERENCE_PRICE_NOT_PREVIOUS_RAW_CLOSE',
               'pct_chg':'SOURCE_REFERENCE_BASED_PERCENT_NOT_COMPOUNDED_TOTAL_RETURN',
               'atr20':'TRUE_RANGE_USES_PREVIOUS_RAW_CLOSE; NO_PRE_CLOSE_SUBSTITUTION',
               'raw_labels':'CLOSE_ENDPOINT_DIVIDED_BY_OBSERVATION_RAW_CLOSE_MINUS1'}
    return [action],semantics,refs


def _read_inputs():
    # Frozen predecessor validation rechecks all hashes; we then directly reread
    # every original that is actually referenced by our normalized inputs/reports.
    from wave_f.core import frozen_context
    dependencies = frozen_context()['source_dependencies']
    refs = {}
    byhash = defaultdict(list)
    for r in dependencies: byhash[r['sha256']].append(r)
    def read(path, expected=None):
        # Stable Git identity, but ALWAYS read the calling checkout's bytes.
        # Fixed private originals continue to resolve to their original paths.
        p=locate_reference(path)
        r=reference(p)
        if expected is not None:require(r['sha256']==expected,'WG_DIAG_FROZEN_REFERENCE_CHANGED')
        raw=checked_reference(r); refs[r['path']]=r
        return json.loads(raw)
    # Predecessor runtime adopted sealed normalized inputs and intentionally
    # omitted some excluded originals. They still occur in our full lineage:
    # bind the original capture inventories and reread those bodies directly.
    legacy_path=ROOT/'docs/p1b-real-admission/Gate.json'
    legacy=read(legacy_path)
    for r in legacy['raw_inventory']:byhash[r['sha256']].append(r)
    wb=read(ROOT/'docs/wave-b/capture-evidence.json')
    capture=read(wb['report']['path'],wb['report']['sha256'])
    for request in capture['requests']:
        if request.get('raw_ref'):
            byhash[request['raw_sha256']].append({'path':request['raw_ref'],'sha256':request['raw_sha256']})
    docs={}
    for wave in ('wave-c','wave-d'):
        path=ROOT/'docs'/wave/'evidence.json'; e=read(path)
        docs[wave]={r['name']:r for r in e['artifacts']}
    result={}; sourcehashes=set()
    def hashes(v):
        if type(v) is dict:
            if 'raw_sha256' in v: sourcehashes.add(v['raw_sha256'])
            for x in v.values(): hashes(x)
        elif type(v) is list:
            for x in v: hashes(x)
    for symbol in SYMBOLS:
        values={}
        for wave in ('wave-c','wave-d'):
            for kind in (('input','assessment','report') if wave=='wave-c' else ('input','report')):
                r=docs[wave][symbol+'.'+kind+'.json']; values[wave+'_'+kind]=read(r['path'],r['sha256'])
                hashes(values[wave+'_'+kind])
        result[symbol]=values
    originals={}
    for h in sorted(sourcehashes):
        candidates=byhash[h]
        require(candidates, 'WG_DIAG_DIRECT_ORIGINAL_NOT_FOUND')
        originals[h]=[]
        for r in candidates:
            p=Path(r['path'])
            if not p.is_relative_to(ARCHIVE.parent): continue
            raw=checked_file(p,h); refs[str(p)]={'path':str(p),'sha256':h,'bytes':len(raw)}
            # Numeric lexemes are retained exactly; never JSON float coercion.
            obj=json.loads(raw,parse_float=str)
            if type(obj) is dict and type(obj.get('data')) is dict and 'fields' in obj['data']:
                data=obj['data']; originals[h].extend(dict(zip(data['fields'],row)) for row in data.get('items',[]))
        require(any(r['path'].startswith(str(ARCHIVE.parent)+'/') for r in candidates), 'WG_DIAG_ORIGINAL_ARCHIVE_SCOPE')
    for symbol, values in result.items():
        for row in values['wave-d_input']['body']['observations']:
            if row['api_name'] not in ('daily','trade_cal','adj_factor','fina_indicator'): continue
            candidates=originals[row['source_ref']['raw_sha256']]
            require(any(all(str(candidate.get(k)) == str(v) for k,v in row['values'].items())
                        for candidate in candidates), 'WG_DIAG_NORMALIZATION_ORIGINAL_MISMATCH')
    for p in (ROOT/'docs/wave-g/Diagnostic-Protocol-v1.1.json', ROOT/'docs/wave-f/Frozen-StrategySpec-v1.json',
              ARCHIVE/'start/Diagnostic-Preregistration-G2.json',ROOT/'docs/wave-g/Diagnostic-Protocol-v1.json',
              ARCHIVE/'start/Diagnostic-Preregistration.json'):
        read(p)
    return result, [refs[p] for p in sorted(refs)]


def _distribution(labels):
    values=sorted(Decimal(x['raw_price_change_ratio']) for x in labels if x['state']=='OBSERVED_RAW_LABEL')
    dd=[Decimal(x['raw_close_path_max_drawdown_ratio']) for x in labels if x['state']=='OBSERVED_RAW_LABEL']
    # Fixed lower order statistics, no interpolation or bootstrap selection.
    with localcontext() as ctx:
        ctx.prec=100
        quantiles={name:_text(values[((len(values)-1)*n)//100]) if values else None
                   for name,n in [('min',0),('q05',5),('q25',25),('median',50),('q75',75),('q95',95),('max',100)]}
    return {'observed_count':len(values),'unknown_count':len(labels)-len(values),
            'raw_close_change_distribution':quantiles,
            'quantile_method':'LOWER_ORDER_STATISTIC_FLOOR((N-1)*P)',
            'max_raw_close_path_drawdown_ratio':_text(max(dd)) if dd else None,
            'unit':'UNADJUSTED_RAW_PRICE_RATIO_NOT_STRATEGY_RETURN'}


def _rank(values):
    # Competition rank with exact ties retained; no lexical winner.
    return {s: 1+sum(v>values[s] for v in values.values()) for s in values}


def coordinate_sensitivity(components, omitted=None):
    """Equal surviving-field mean only; no missing-zero or lexical tie winner."""
    values={};unknown=[]
    with localcontext() as ctx:
        ctx.prec=100
        for symbol,fields in components.items():
            remaining=[_dec(v) for key,v in fields.items() if key!=omitted and v is not None]
            if not remaining:unknown.append(symbol)
            else:values[symbol]=sum(remaining,ZERO)/Decimal(len(remaining))
    return {'omitted_component':omitted,'scores':{s:_text(v) for s,v in values.items()},
            'competition_ranks':_rank(values),'unknown_symbols':unknown,'tied_scores_preserved':True,
            'missing_imputed_zero':False,
            'meaning':'EXPLORATORY_CURRENT_COORDINATE_FIELD_REMOVAL_NOT_NEW_QUALITY_POLICY'}


def _quality(inputs):
    rows=[];components={}
    for s in SYMBOLS:
        c=inputs[s]['wave-c_assessment']; d=inputs[s]['wave-d_report']; q=d['body']['wave_c_quality']
        components[s]={x['feature_name']:x['value'] for x in q['component_scores']['components']}
        financial=[deepcopy(x) for x in d['body']['features'] if x['name'].startswith(('source_', 'derived_')) or
                   x['name'] in ('cash_conversion_ratio','cash_after_capex_proxy','debt_ratio_pct',
                                  'receivables_to_revenue_ratio','inventory_to_revenue_ratio')]
        rows.append({'symbol':s,'wave_c_quality':deepcopy(c['body']['quality_score']),
                     'wave_d_preserved_wave_c_quality':deepcopy(q),
                     'coordinates_unchanged': c['body']['quality_score']['value']==q['value'],
                     'wave_c_report_ref':reference(Path(inputs[s]['_c_report_path'])) if '_c_report_path' in inputs[s] else {'content_hash':c['content_hash']},
                     'wave_d_report_content_hash':d['content_hash'],
                     'current_financial_fields':financial,'current_unknowns':deepcopy(d['body']['unknowns']),
                     'historical_quality_eligibility':'UNKNOWN_NO_SAME_DAY_BACKFILL',
                     'forecast_probability_or_company_rating':'UNSET_REQUIRED'})
    scenarios=[]
    for omit in (None,'roe','netprofit_yoy','debt_to_assets'):
        scenarios.append(coordinate_sensitivity(components,omit))
    return {'classification':'CURRENT_QUALITY_DESCRIPTIVE_STABILITY_ONLY','symbols':rows,
            'leave_one_field_out':scenarios,
            'all_missing_counterexample':coordinate_sensitivity({s:{k:None for k in components[s]} for s in SYMBOLS}),
            'historical_same_day_quality_backfilled':False,'quality_to_future_predictive_claim':False,
            'cross_company_comparability':'THREE_CURRENT_PRESELECTED_SURVIVORS_NOT_MARKET_RATING',
            'TTM_ROIC_COST_OF_CAPITAL_FROZEN_QUALITY_gate':'UNKNOWN_NOT_REPLACED_BY_WAVE_C_COORDINATE',
            'limitations':['ORIGINAL_WAVE_C_PARTIAL_THREE_FIELD_COORDINATE_PRESERVED',
                           'WAVE_D_YTD_CURRENT_FINANCIALS_NOT_COMPLETE_PIT_TTM',
                           'REMOVING_FIELDS_CAN_CHANGE_RANK_AND_TIES_WITHOUT_PREDICTIVE_INFORMATION']}


def projected():
    p=protocol(); require(p['horizons']==[5,20,60] and p['families']==list(FAMILIES), 'WG_DIAG_PROTOCOL_SCOPE')
    inputs, direct=_read_inputs()
    actions,semantics,newrefs=_current_limitations()
    direct=sorted({r['path']:r for r in direct+newrefs}.values(),key=lambda r:r['path'])
    source_clocks=[r['source_ref']['retrieved_at'] for s in SYMBOLS for r in inputs[s]['wave-d_input']['body']['observations']
                   if r['source_ref'].get('retrieved_at')]
    reconstruction=max(source_clocks,key=timestamp)
    datasets={};calendars={};features={};labels={};lineage=[];exclusions=[];blocks=[];summaries=[];sensitivity=[]
    endpoints=p['chronological_price_diagnostics']['prefix_end_open_session_counts']
    require(endpoints==[126,252,327], 'WG_DIAG_BLOCKS_MUST_BE_PREREGISTERED')
    csvstream=io.StringIO(newline=''); writer=csv.writer(csvstream,lineterminator='\n')
    writer.writerow(['symbol','logical_diagnostic_cutoff','family','price_component_observation','full_family_decision',
                     'raw_close','ma20','ma60','ma60_slope20','atr20','distance_ma20_atr','volume3_to_volume20',
                     'breakout60_ratio','volume_to_previous20','extension_from_breakout','unknown_reason_codes'])
    prefix_checks=0;future_checks=0
    for s in SYMBOLS:
        obs=inputs[s]['wave-d_input']['body']['observations']
        rows=[{**r['values'],'source_ref':deepcopy(r['source_ref'])} for r in obs if r['api_name']=='daily']
        datasets[s]=rows;calendar=validate_calendar([r for r in obs if r['api_name']=='trade_cal']);calendars[s]=calendar
        unique,conflicts,duplicates=_group(rows);dates=sorted(set(unique)|{r['trade_date'] for r in conflicts})
        require(len(rows)==330 and len(dates)==327, 'WG_DIAG_FROZEN_BAR_COUNTS')
        exclusions.append({'symbol':s,'original_observation_count':len(rows),'distinct_dates':len(dates),
                           'identical_duplicate_observations':len(rows)-len(dates),
                           'duplicate_dates':duplicates,'conflicts':conflicts,
                           'all_full_family_decisions':'NO_DECISION','missing_gates':MISSING_GATES,
                           'calendar_state':calendar['state'],'selection_bias':'OWNER_PRESELECTED_CONTEMPORARY_SURVIVORS_ALL_EXPOSED',
                           'no_bar_means':'UNKNOWN_NEVER_NORMAL_OR_SUSPENDED_OR_FLAT'})
        features[s]=[];labels[s]={h:[] for h in p['horizons']}
        for d in dates:
            feature=price_features(rows,d,symbol=s,calendar=calendar,reconstruction_cutoff=reconstruction)
            truncated=price_features([r for r in rows if r['trade_date']<=d],d,symbol=s,calendar=calendar,reconstruction_cutoff=reconstruction)
            require(canonical(feature)==canonical(truncated),'WG_DIAG_PREFIX_NONINTERFERENCE');prefix_checks+=1
            # Future price and future-source revision mutation must not affect the prefix.
            changed=deepcopy(rows)
            for r in changed:
                if r['trade_date']>d: r['close']='FUTURE_CORRUPTION_ISOLATED'
            require(canonical(feature)==canonical(price_features(changed,d,symbol=s,calendar=calendar,
                    reconstruction_cutoff=reconstruction)), 'WG_DIAG_FUTURE_NONINTERFERENCE');future_checks+=1
            features[s].append(feature);lineage.append(feature)
            values=feature['values']
            for family in FAMILIES:
                writer.writerow([s,d,family,feature['price_component'][family],'NO_DECISION']+
                                 [values.get(k,'') for k in ('close','ma20','ma60','ma60_slope_20','atr20','distance_ma20_atr',
                                  'volume3_to_volume20','breakout60_ratio','volume_to_previous20','extension_from_breakout')]+
                                 ['|'.join(MISSING_GATES+feature['reason_codes'])])
            for h in p['horizons']:
                label=forward_label(rows,d,h,calendar=calendar,symbol=s,reconstruction_cutoff=reconstruction)
                label=annotate_action_overlap(label,[a for a in actions if a['symbol']==s])
                labels[s][h].append(label)
        for family in FAMILIES:
            fs=features[s];eligible=[i for i,f in enumerate(fs) if f['price_component'][family]=='TRUE']
            summaries.append({'symbol':s,'family':family,'date_count':len(fs),
                              'classification':'PRICE_COMPONENT_OBSERVATION_ONLY_COMPLETE_FAMILY_NO_DECISION',
                              'price_component_true_count':len(eligible),
                              'price_component_false_count':sum(f['price_component'][family]=='FALSE' for f in fs),
                              'price_component_unknown_count':sum(f['price_component'][family]=='UNKNOWN' for f in fs),
                              'full_family_no_decision_count':len(fs),
                              'all_dates_raw_label_descriptive':{str(h):_distribution(labels[s][h]) for h in p['horizons']},
                              'price_component_true_raw_label_descriptive':{str(h):_distribution([labels[s][h][i] for i in eligible]) for h in p['horizons']}})
            for end in endpoints:
                tail_start=max(0,end-60); retained=[i for i in eligible if i<tail_start]
                block={'symbol':s,'family':family,'expanding_prefix_count':end,'start':dates[0],'end':dates[end-1],
                       'label_terminal60_purge_dates':dates[tail_start:end],
                       'retained_price_component_true_observation_dates':[dates[i] for i in retained],
                       'purged_price_component_true_observation_dates':[dates[i] for i in eligible if tail_start<=i<end],
                       'scope':'EXPOSED_PRICE_ONLY_EXPANDING_PREFIX_NO_TRAINING_OR_OPTIMIZATION',
                       'raw_label_descriptive':{},'all_retained_anchor_dates':dates[:tail_start],
                       'all_retained_anchor_raw_label_descriptive':{}}
                for h in p['horizons']:
                    retained_labels=[labels[s][h][i] for i in retained]
                    require(all(x['endpoint_date'] is None or x['endpoint_date']<=dates[end-1] for x in retained_labels),
                            'WG_DIAG_BLOCK_LABEL_LEAK')
                    block['raw_label_descriptive'][str(h)]=_distribution(retained_labels)
                    all_retained_labels=labels[s][h][:tail_start]
                    require(all(x['endpoint_date'] is None or x['endpoint_date']<=dates[end-1] for x in all_retained_labels),
                            'WG_DIAG_ALL_ANCHOR_BLOCK_LABEL_LEAK')
                    block['all_retained_anchor_raw_label_descriptive'][str(h)]=_distribution(all_retained_labels)
                blocks.append(block)
            thresholds=p['sensitivity']['pullback_volume3_to_volume20_thresholds' if family==FAMILIES[0]
                                            else 'breakout_volume_to_previous20_thresholds']
            for threshold in thresholds:
                memberships=[];unknown=[]
                for f in fs:
                    cond=f['conditions'];v=f['values'];d=f['logical_diagnostic_cutoff']
                    if not cond:unknown.append(d);continue
                    if family==FAMILIES[0]:
                        names=list(cond)[:5];changed=dict(cond)
                        val=v['volume3_to_volume20'];changed[names[3]]=Decimal(val)<Decimal(threshold) if val is not None else None
                    else:
                        names=list(cond)[5:];changed=dict(cond)
                        val=v['volume_to_previous20'];changed[names[1]]=Decimal(val)>=Decimal(threshold) if val is not None else None
                    tests=[changed[n] for n in names]
                    if None in tests: unknown.append(d)
                    elif all(tests): memberships.append(d)
                base_dates=[dates[i] for i in eligible]
                sensitivity.append({'symbol':s,'family':family,'threshold':threshold,'true_count':len(memberships),
                                    'true_dates':memberships,'unknown_dates':unknown,
                                    'coverage_ratio':_ratio_text(len(fs)-len(unknown),len(fs)),
                                    'membership_added_vs_frozen':[d for d in memberships if d not in base_dates],
                                    'membership_removed_vs_frozen':[d for d in base_dates if d not in memberships],
                                    'selected_as_winner':False,'candidate_mutated':False})
    audit={'state':'PASS','prefix_truncation_equal_checks':prefix_checks,'future_payload_mutation_equal_checks':future_checks,
           'source_reconstruction_cutoff':reconstruction,'future_labels_entered_features':False,
           'historical_source_available_at_invented':False,'current_quality_entered_historical_price_features':False,
           'observations_not_native_signals':True,'actual_forward_days':0,
           'label_units':'RAW_UNADJUSTED_CLOSE_CHANGE_NO_FEES_NO_EXECUTION',
           'chronological_block_label_boundary_checks':len(blocks)*3,
           'limitations':['ACTUAL_AVAILABLE_RETRIEVED_ARE_CURRENT_CAPTURE_NOT_HISTORICAL_AVAILABILITY',
                          'ACTION_STATUS_SECTOR_COMPANY_GATES_UNKNOWN', 'ALL327_SESSIONS_RETROSPECTIVELY_EXPOSED']}
    timing={'classification':'RETROSPECTIVE_DIAGNOSTIC_ONLY','not_formal_backtest':True,'all_exposed_not_oos':True,
            'family_summaries':summaries,'chronological_blocks':blocks,'univariate_volume_sensitivity':sensitivity,
            'labels_by_symbol':{s:{str(h):labels[s][h] for h in p['horizons']} for s in SYMBOLS},
            'known_action_structural_facts':actions,'raw_field_semantics':semantics,
            'no_pooled_edge_or_win_rate_or_buy_claim':True,'no_portfolio_or_cost_simulation':True}
    quality=_quality(inputs)
    lineagedoc={'classification':'RETROSPECTIVE_DIAGNOSTIC_ONLY','features':lineage,
                'calendar_by_symbol':calendars,'direct_input_refs':direct,
                'raw_field_semantics':semantics,'known_action_structural_facts':actions,
                'logical_cutoff_and_current_source_clocks_are_separate':True,
                'source_reconstruction_cutoff':reconstruction,'units':{'price':'PROVIDER_CNY_PER_SHARE_UNVERIFIED',
                'volume':'PROVIDER_REPORTED_VOLUME_SCALE_UNVERIFIED','ratios':'DIMENSIONLESS_RAW_RATIO'}}
    reportlines=['# 三股受限回顾性价格诊断','',
                 'RETROSPECTIVE_DIAGNOSTIC_ONLY / LOCAL_ONLY / NON_TRADEABLE。所有327日期均已暴露。',
                 '两个冻结 family 只计算原始价格子条件；每个完整 family 每日均为 NO_DECISION。',
                 '未来标签为观察日收盘至后续5/20/60参考开市日收盘的原始价格变化及收盘路径回撤。',
                 '未模拟买卖、资金、费用、分红或可交易性，不能解释成策略利润、总回报或 Edge。',
                 '参考日历由当前已留存网关原件重建，日期网格完整，但未证明历史当时可见性。','',
                 '|股票|价格子条件|TRUE|FALSE|UNKNOWN|完整规则 NO_DECISION|',
                 '|---|---|---:|---:|---:|---:|']
    for r in summaries:
        reportlines.append('|'+ '|'.join(str(r[k]) for k in ('symbol','family','price_component_true_count',
                          'price_component_false_count','price_component_unknown_count','full_family_no_decision_count'))+'|')
    reportlines += ['', '所有股票、两个 family、三个 horizon、三个扩展前缀和每个预先冻结单变量阈值均逐项保留。',
                    '每个扩展前缀清除末尾60个标签锚点；没有训练、优化或选出赢家。',
                    '原始330观察中3条重复观察具有相同价格和量；全部保留来源，没有覆盖冲突或填造平盘。',
                    'pullback前79日期需80日期斜率窗口而UNKNOWN；breakout前60日期需61日期窗口而UNKNOWN。末尾5/20/60标签无端点时 UNKNOWN。',
                    '状态、公司行动、公司质量、行业相对收益、估值、催化和经济政策缺口拒绝完整规则。','',
                    'Quality 是 Wave C 现有当前三字段坐标；Wave D 保留它并补充当前财务字段。',
                    '逐项移除字段会改变坐标、排名和并列关系；全缺失反例保留 UNKNOWN，未以零代替。',
                    '今日财务未填入历史价格观察。TTM/ROIC/资本成本等冻结公司质量条件仍未完成。',
                    '603993于2025-06-27的A股分派：gross0.255元/股，差异化除息参考0.2535元/股；跨此日期标签显式标记。',
                    '该原件只证明单次事件的结构事实，公告仅DATE_ONLY，连续公司行动与当时可见性仍UNKNOWN。',
                    'ATR采用前一条原始收盘；供应商pre_close为除权参考价，pct_chg未被拼成累计收益。',
                    '三股为 Owner 当前预选存续样本，不能推广至全市场或作预测评级。',
                    '详细数值分布、所有标签、尾部、覆盖、敏感性和真实来源哈希见同目录 JSON。',
                    '前缀隔离检查：'+str(prefix_checks)+'；未来负载变更隔离检查：'+str(future_checks)+'。',
                    'actual Forward days=0；native Signal/Order/Broker/Production 均未启用。','']
    out={'signal-date.csv':csvstream.getvalue().encode(),'diagnostic-report.md':'\n'.join(reportlines).encode()}
    for name,body in [('feature-lineage.json',lineagedoc),('lookahead-audit.json',audit),
                      ('timing-forward-return-diagnostic.json',timing),('quality-stability.json',quality),
                      ('exclusions.json',{'symbols':exclusions,'missing_gates':MISSING_GATES,
                       'all_exposed_not_oos':True,'actions_costs_status':'UNKNOWN'})]:
        out[name]=canonical(metadata(name,body))+b'\n'
    summary={'requested_files':7,'symbols':list(SYMBOLS),'families':list(FAMILIES),'horizons':[5,20,60],
             'original_observations_per_symbol':330,'dates_per_symbol':327,'csv_observation_rows':1962,
             'full_family_no_decision_rows':1962,'chronological_blocks':len(blocks),
             'sensitivity_rows':len(sensitivity),'family_counts':[{k:v for k,v in r.items() if not k.endswith('descriptive')} for r in summaries],
             'direct_input_refs':direct,'protocol_sha256':sha(checked_file(ROOT/'docs/wave-g/Diagnostic-Protocol-v1.1.json')),
             'scope':'RETROSPECTIVE_DIAGNOSTIC_ONLY_LOCAL_ONLY_NON_TRADEABLE','actual_forward_days':0,
             'productionGate':False,'live_authority':False,'tests_embedded':audit}
    out['diagnostic-summary.json']=canonical(summary)+b'\n'
    return out


def _private_write(path, raw):
    os.umask(0o077)
    require(path.is_relative_to(ARCHIVE/'diagnostic') and path.resolve()==path and
            not path.exists(), 'WG_DIAG_OUTPUT_PATH')
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    require(path.parent.stat().st_mode&0o777==0o700, 'WG_DIAG_OUTPUT_DIR_MODE')
    with path.open('xb') as f:f.write(raw)
    require(path.stat().st_mode&0o777==0o600,'WG_DIAG_OUTPUT_MODE')


def run_diagnostic(output_dir=DEST):
    """Exclusive G1 epoch with two physical byte-identical deterministic replays."""
    output_dir=Path(output_dir)
    require(not output_dir.exists(), 'WG_DIAG_EPOCH_EXISTS')
    first=projected();second=projected()
    # Preserve two actual replays, rather than overwriting evidence.
    for epoch,outputs in [('replay-1',first),('replay-2',second)]:
        for name,raw in outputs.items():_private_write(output_dir/epoch/name,raw)
    equal=first==second
    manifest={'equal':equal,'replays':2,'requested_files_per_replay':7,'summary_per_replay':1,
              'artifacts':[{'name':epoch+'/'+name,**reference(output_dir/epoch/name)}
                           for epoch,outputs in [('replay-1',first),('replay-2',second)] for name in sorted(outputs)],
              'direct_input_refs':json.loads(first['diagnostic-summary.json'])['direct_input_refs'],
              'scope':'RETROSPECTIVE_DIAGNOSTIC_ONLY_LOCAL_ONLY_NON_TRADEABLE','productionGate':False,
              'delta_report':{'replay_byte_deltas':[] if equal else sorted(n for n in first if first[n]!=second[n]),
                              'wave_c_quality_coordinates_changed':False,'frozen_families_changed':False,
                              'new_strategy_profit_claims':0,'actual_forward_days_added':0}}
    _private_write(output_dir/'artifact-manifest.json',canonical(manifest)+b'\n')
    require(equal,'WG_DIAG_REPLAY_CHANGED_FAILURE_PRESERVED')
    return {**json.loads(first['diagnostic-summary.json']),'manifest_ref':reference(output_dir/'artifact-manifest.json'),
            'replays':2,'equal':True}


def evidence():
    manifest=json.loads(checked_file(DEST/'artifact-manifest.json'))
    for r in manifest['artifacts']+manifest['direct_input_refs']:
        checked_reference(r)
    return manifest


def report():
    evidence()
    summary=json.loads(checked_file(DEST/'replay-1/diagnostic-summary.json'))
    return metadata('Retrospective-Diagnostic-Summary',summary)
