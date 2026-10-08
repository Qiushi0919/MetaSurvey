"""Pure PIT preparation selectors; shape/hash never confer source authority.

All records are closed JSON dictionaries. Common required fields are symbol,
event_time (nullable exact timezone instant), published_at/available_at (nullable
exact instants), retrieved_at (exact instant), publication_precision and
availability_precision (INSTANT/DATE_ONLY/UNKNOWN), date_only_fields (original
YYYYMMDD strings), clock_proof (UNPROVEN/SYNTHETIC_EXACT), provenance
(SYNTHETIC/QUARANTINED), source/source_version (nonempty strings), raw_hash
(sha256), and row_ordinal (nonnegative integer). DATE_ONLY clocks MUST remain
null. Event time is independent of publication and may describe a future event.

Financial required fields additionally: kind=FINANCIAL_REVISION, period
(YYYYMMDD), statement (INCOME/BALANCESHEET/CASHFLOW/INDICATOR), revision_id,
supersedes_revision_id (nullable), revision_coverage_complete (bool),
coverage_kind (HISTORICAL_REVISIONS/CURRENT_REVISION_SNAPSHOT), values (named
string-or-null observations), units (SYNTHETIC_DECLARED/UNVERIFIED_SOURCE_UNITS).
Revision IDs/links are explicit evidence; update flags or row ordering never
create revision chronology. Visible chains must be complete and unambiguous.
Reporting periods later than the cutoff's Asia/Shanghai calendar date are
UNKNOWN before any row metadata is inspected; no date-only midnight is created.

Tradeability required fields additionally: kind=TRADEABILITY_HISTORY,
component (ST/SUSPENSION/LIMIT/DELIST/LISTED/UNIVERSE), effective_from/to
(exact inclusive/exclusive instants, to nullable), coverage_complete (bool),
coverage_kind (HISTORICAL_INTERVAL/CURRENT_SNAPSHOT), and value. ST is NORMAL/ST;
SUSPENSION is ACTIVE/SUSPENDED; DELIST is NOT_DELISTED/DELISTED; LISTED is
LISTED/NOT_LISTED; UNIVERSE is MEMBER/NOT_MEMBER. Every component also accepts
UNKNOWN. LIMIT value is {regime: NO_LIMIT}, {regime: UNKNOWN}, or {regime:
BOUNDED, lower: Decimal string, upper: Decimal string, unit: CNY_PER_SHARE}.
Known limits never imply that an unprovided order price is inside the band.

Positive results require explicitly labelled synthetic exact clocks and complete
synthetic history. QUARANTINED inputs cannot declare SYNTHETIC_EXACT. These are
fixture selection results, not certified historical visibility, entitlement,
strategy membership or trade permission. All outputs remain FIXTURE_ONLY or
QUARANTINED with live_authority/historical_visibility_proven/productionGate
false. UNKNOWN and conflicting observations are preserved, never interpreted
as normal status. A complete synthetic status result still cannot trade.

Modes: OBSERVED_AT_TIME requires available AND retrieved <= cutoff.
HISTORICAL_AVAILABILITY_RECONSTRUCTION allows later retrieval only under
synthetic exact historical availability evidence and never says observed then.
Before inspecting revision IDs, values, coverage or hashing metadata, future
records are excluded using known availability/publication/retrieval clocks.
Consequently adding or changing a later visible revision cannot alter a prefix.
Readiness functions inspect sealed immutable Wave D input metadata only; they
never return financial amounts, actual selected revisions, or historical proof.
Each raw-source entry binds raw content version/hash, request ID/fingerprint,
and retrieval instant. Identical raw bytes in distinct observations remain
distinct sources. Row ordinals are a multiset: repeated observations are
preserved, never silently deduplicated to make a display schema pass.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from .common import (SYMBOLS, VERSION, canonical, digest, hash_value, keys,
                     require, timestamp, decimal_string)

MODES = ('OBSERVED_AT_TIME', 'HISTORICAL_AVAILABILITY_RECONSTRUCTION')
STATEMENTS = ('INCOME', 'BALANCESHEET', 'CASHFLOW', 'INDICATOR')
COMPONENTS = ('ST', 'SUSPENSION', 'LIMIT', 'DELIST', 'LISTED', 'UNIVERSE')
API_STATEMENTS = {'income': 'INCOME', 'balancesheet': 'BALANCESHEET',
                  'cashflow': 'CASHFLOW', 'fina_indicator': 'INDICATOR'}
_COMMON = ('symbol', 'event_time', 'published_at', 'available_at', 'retrieved_at',
           'publication_precision', 'availability_precision', 'date_only_fields',
           'clock_proof', 'provenance', 'source', 'source_version', 'raw_hash',
           'row_ordinal')
_FIN = ('kind', 'period', 'statement', 'revision_id', 'supersedes_revision_id',
        'revision_coverage_complete', 'coverage_kind', 'values', 'units')
_TRADE = ('kind', 'component', 'effective_from', 'effective_to',
          'coverage_complete', 'coverage_kind', 'value')


def _day(value):
    require(type(value) is str and len(value) == 8 and value.isdigit(),
            'PIT_DATE_INVALID')
    datetime.strptime(value, '%Y%m%d')
    return value


def _text(value):
    require(type(value) is str and bool(value.strip()), 'PIT_TEXT_REQUIRED')


def _arguments(records, symbol, cutoff, mode):
    require(type(records) is list, 'PIT_RECORD_LIST_REQUIRED')
    require(type(symbol) is str and symbol in SYMBOLS, 'PIT_SYMBOL_SCOPE')
    require(mode in MODES, 'PIT_MODE_INVALID')
    return timestamp(cutoff)


def _future(record, cutoff_ns, mode):
    # Do not validate/hash future bodies: even their IDs and titles are excluded.
    names = ('published_at', 'available_at')
    if mode == 'OBSERVED_AT_TIME':
        names += ('retrieved_at',)
    for name in names:
        value = record.get(name)
        if value is not None and timestamp(value) > cutoff_ns:
            return True
    return False


def _common(record):
    require(record['symbol'] in SYMBOLS, 'PIT_SYMBOL_SCOPE')
    require(record['provenance'] in ('SYNTHETIC', 'QUARANTINED'),
            'PIT_PROVENANCE_INVALID')
    require(record['clock_proof'] in ('UNPROVEN', 'SYNTHETIC_EXACT'),
            'PIT_CLOCK_PROOF_INVALID')
    require(record['provenance'] == 'SYNTHETIC' or
            record['clock_proof'] == 'UNPROVEN', 'PIT_ACTUAL_PROOF_FORBIDDEN')
    for name in ('source', 'source_version'):
        _text(record[name])
    hash_value(record['raw_hash'])
    require(type(record['row_ordinal']) is int and record['row_ordinal'] >= 0,
            'PIT_ORDINAL_INVALID')
    require(type(record['date_only_fields']) is dict, 'PIT_DATE_EVIDENCE_INVALID')
    for name, value in record['date_only_fields'].items():
        _text(name)
        _day(value)
    for clock, precision in (('published_at', 'publication_precision'),
                             ('available_at', 'availability_precision')):
        p = record[precision]
        require(p in ('INSTANT', 'DATE_ONLY', 'UNKNOWN'),
                'PIT_PRECISION_INVALID')
        if p == 'INSTANT':
            timestamp(record[clock])
        else:
            require(record[clock] is None, 'PIT_DATE_ONLY_OR_UNKNOWN_IMPUTED')
    retrieved = timestamp(record['retrieved_at'])
    if record['event_time'] is not None:
        timestamp(record['event_time'])
    if record['published_at'] is not None and record['available_at'] is not None:
        require(timestamp(record['published_at']) <= timestamp(record['available_at']),
                'PIT_PUBLICATION_AFTER_AVAILABILITY')
    if record['available_at'] is not None:
        require(timestamp(record['available_at']) <= retrieved,
                'PIT_AVAILABILITY_AFTER_RETRIEVAL')


def _proof_reasons(record):
    reasons = []
    if record['provenance'] != 'SYNTHETIC':
        reasons.append('QUARANTINED_SOURCE_NO_AUTHORITY')
    if record['clock_proof'] != 'SYNTHETIC_EXACT':
        reasons.append('HISTORICAL_VISIBILITY_UNPROVEN')
    if record['publication_precision'] != 'INSTANT':
        reasons.append('PUBLICATION_CLOCK_UNKNOWN_OR_DATE_ONLY')
    if record['availability_precision'] != 'INSTANT':
        reasons.append('AVAILABILITY_CLOCK_UNKNOWN_OR_DATE_ONLY')
    return reasons


def _output(kind, symbol, cutoff, mode, visible, reasons):
    return {'kind': kind, 'version': VERSION, 'symbol': symbol, 'cutoff': cutoff,
            'mode': mode, 'status': 'UNKNOWN', 'selected': {},
            'visible_count': len(visible),
            'visible_records_hash': digest(sorted(visible, key=canonical)),
            'reason_codes': sorted(set(reasons)),
            'purpose': 'FIXTURE_ONLY' if visible and all(
                r['provenance'] == 'SYNTHETIC' for r in visible) else 'QUARANTINED',
            'observed_at_cutoff': False,
            'live_authority': False, 'historical_visibility_proven': False,
            'formal_source_admission': 'BLOCKED', 'productionGate': False,
            'safe_to_trade': False}


def select_financial(records, symbol, period, cutoff, mode):
    """Select an unambiguous visible fixture revision per statement, fail closed."""
    cutoff_ns = _arguments(records, symbol, cutoff, mode)
    _day(period)
    # A statement reporting period is a calendar fact, not a midnight instant.
    # Compare it with the cutoff's Shanghai date before inspecting future rows.
    # This does not constrain independent future scheduled event_time facts.
    cutoff_day = datetime.fromisoformat(cutoff.replace('Z', '+00:00')).astimezone(
        ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d')
    if period > cutoff_day:
        return _output('FINANCIAL_PREFIX_SELECTION', symbol, cutoff, mode, [],
                       ['FUTURE_REPORTING_PERIOD_NOT_VISIBLE'])
    visible = []
    reasons = []
    groups = defaultdict(list)
    for record in records:
        require(type(record) is dict and 'symbol' in record and 'period' in record,
                'PIT_FINANCIAL_RECORD_INVALID')
        require(record['symbol'] in SYMBOLS, 'PIT_SYMBOL_SCOPE')
        if record['symbol'] != symbol or record['period'] != period:
            continue
        if _future(record, cutoff_ns, mode):
            continue
        keys(record, _COMMON + _FIN)
        _common(record)
        require(record['kind'] == 'FINANCIAL_REVISION' and
                record['statement'] in STATEMENTS, 'PIT_STATEMENT_INVALID')
        _day(record['period'])
        _text(record['revision_id'])
        if record['supersedes_revision_id'] is not None:
            _text(record['supersedes_revision_id'])
        require(type(record['revision_coverage_complete']) is bool,
                'PIT_REVISION_COVERAGE_INVALID')
        require(record['coverage_kind'] in
                ('HISTORICAL_REVISIONS', 'CURRENT_REVISION_SNAPSHOT'),
                'PIT_REVISION_COVERAGE_INVALID')
        require(type(record['values']) is dict and all(
                type(k) is str and bool(k) and (v is None or type(v) is str)
                for k, v in record['values'].items()), 'PIT_VALUE_FORMAT_INVALID')
        require(record['units'] in ('SYNTHETIC_DECLARED', 'UNVERIFIED_SOURCE_UNITS'),
                'PIT_UNITS_INVALID')
        visible.append(deepcopy(record))
        record_reasons = _proof_reasons(record)
        if not record['revision_coverage_complete']:
            record_reasons.append('FINANCIAL_REVISION_COVERAGE_INCOMPLETE')
        if record['coverage_kind'] != 'HISTORICAL_REVISIONS':
            record_reasons.append('CURRENT_REVISION_NOT_HISTORICAL')
        if record['units'] != 'SYNTHETIC_DECLARED':
            record_reasons.append('FINANCIAL_UNITS_UNVERIFIED')
        reasons.extend(record_reasons)
        groups[record['statement']].append(record)
    result = _output('FINANCIAL_PREFIX_SELECTION', symbol, cutoff, mode,
                     visible, reasons)
    if not visible:
        result['reason_codes'] = ['NO_VISIBLE_FINANCIAL_HISTORY']
        return result
    if reasons:
        return result
    selected = {}
    for statement, rows in sorted(groups.items()):
        versions = {}
        for row in rows:
            rid = row['revision_id']
            if rid in versions and canonical(versions[rid]) != canonical(row):
                reasons.append('FINANCIAL_REVISION_ID_CONFLICT')
            versions[rid] = row
        children = defaultdict(list)
        roots = []
        for rid, row in versions.items():
            parent = row['supersedes_revision_id']
            if parent is None:
                roots.append(rid)
            elif parent not in versions:
                reasons.append('FINANCIAL_REVISION_CHAIN_INCOMPLETE')
            else:
                children[parent].append(rid)
                if (timestamp(versions[parent]['available_at']) >=
                        timestamp(row['available_at']) or
                        timestamp(versions[parent]['published_at']) >=
                        timestamp(row['published_at'])):
                    reasons.append('FINANCIAL_REVISION_CHRONOLOGY_CONFLICT')
        if len(roots) != 1 or any(len(v) > 1 for v in children.values()):
            reasons.append('FINANCIAL_REVISION_CONFLICT')
        visited = set()
        node = roots[0] if len(roots) == 1 else None
        while node is not None and node not in visited:
            visited.add(node)
            next_nodes = children.get(node, [])
            if len(next_nodes) != 1:
                break
            node = next_nodes[0]
        if len(visited) != len(versions):
            reasons.append('FINANCIAL_REVISION_CHAIN_CONFLICT')
        if not reasons:
            selected[statement] = deepcopy(versions[node])
    if reasons:
        result['reason_codes'] = sorted(set(reasons))
        return result
    result['selected'] = selected
    result['status'] = 'SELECTED_FIXTURE_ONLY'
    result['observed_at_cutoff'] = all(timestamp(r['retrieved_at']) <= cutoff_ns
                                      for r in visible)
    result['reason_codes'] = ['SYNTHETIC_SELECTION_NO_LIVE_AUTHORITY']
    return result


def _trade_value(component, value):
    allowed = {'ST': ('NORMAL', 'ST', 'UNKNOWN'),
               'SUSPENSION': ('ACTIVE', 'SUSPENDED', 'UNKNOWN'),
               'DELIST': ('NOT_DELISTED', 'DELISTED', 'UNKNOWN'),
               'LISTED': ('LISTED', 'NOT_LISTED', 'UNKNOWN'),
               'UNIVERSE': ('MEMBER', 'NOT_MEMBER', 'UNKNOWN')}
    if component != 'LIMIT':
        require(type(value) is str and value in allowed[component],
                'PIT_COMPONENT_VALUE_INVALID')
        return value == 'UNKNOWN'
    require(type(value) is dict and value.get('regime') in
            ('BOUNDED', 'NO_LIMIT', 'UNKNOWN'), 'PIT_LIMIT_INVALID')
    if value['regime'] == 'BOUNDED':
        keys(value, ('regime', 'lower', 'upper', 'unit'))
        lower = decimal_string(value['lower'])
        upper = decimal_string(value['upper'])
        require(lower > 0 and upper >= lower and value['unit'] == 'CNY_PER_SHARE',
                'PIT_LIMIT_RANGE_INVALID')
    else:
        keys(value, ('regime',))
    return value['regime'] == 'UNKNOWN'


def select_tradeability(records, symbol, effective_at, cutoff, mode):
    """Historical status evidence selection, never trading-rule eligibility."""
    cutoff_ns = _arguments(records, symbol, cutoff, mode)
    effective_ns = timestamp(effective_at)
    visible = []
    reasons = []
    groups = defaultdict(list)
    for record in records:
        require(type(record) is dict and 'symbol' in record,
                'PIT_TRADEABILITY_RECORD_INVALID')
        require(record['symbol'] in SYMBOLS, 'PIT_SYMBOL_SCOPE')
        if record['symbol'] != symbol or _future(record, cutoff_ns, mode):
            continue
        keys(record, _COMMON + _TRADE)
        _common(record)
        require(record['kind'] == 'TRADEABILITY_HISTORY' and
                record['component'] in COMPONENTS, 'PIT_COMPONENT_INVALID')
        start = timestamp(record['effective_from'])
        end = timestamp(record['effective_to']) if record['effective_to'] else None
        require(end is None or start < end, 'PIT_EFFECTIVE_INTERVAL_INVALID')
        if effective_ns < start or (end is not None and effective_ns >= end):
            continue
        require(type(record['coverage_complete']) is bool and
                record['coverage_kind'] in ('HISTORICAL_INTERVAL', 'CURRENT_SNAPSHOT'),
                'PIT_STATUS_COVERAGE_INVALID')
        unknown = _trade_value(record['component'], record['value'])
        visible.append(deepcopy(record))
        reasons.extend(_proof_reasons(record))
        if not record['coverage_complete']:
            reasons.append('STATUS_HISTORY_COVERAGE_INCOMPLETE')
        if record['coverage_kind'] != 'HISTORICAL_INTERVAL':
            reasons.append('CURRENT_STATUS_NOT_HISTORICAL')
        if unknown:
            reasons.append('STATUS_VALUE_UNKNOWN:' + record['component'])
        groups[record['component']].append(record)
    missing = [c for c in COMPONENTS if not groups[c]]
    reasons.extend('STATUS_COMPONENT_MISSING:' + c for c in missing)
    result = _output('TRADEABILITY_PREFIX_SELECTION', symbol, cutoff, mode,
                     visible, reasons)
    result['effective_at'] = effective_at
    result['component_states'] = {c: 'UNKNOWN' for c in COMPONENTS}
    if reasons:
        return result
    for component in COMPONENTS:
        # Multiple distinct overlapping facts are ambiguity, not last-row-wins.
        rows = {canonical(r): r for r in groups[component]}
        if len(rows) != 1:
            reasons.append('STATUS_OVERLAPPING_VERSION_CONFLICT:' + component)
    if reasons:
        result['reason_codes'] = sorted(set(reasons))
        return result
    result['selected'] = {c: deepcopy(groups[c][0]) for c in COMPONENTS}
    result['component_states'] = {c: 'KNOWN_FIXTURE_ONLY' for c in COMPONENTS}
    result['status'] = 'SELECTED_FIXTURE_ONLY'
    result['observed_at_cutoff'] = all(timestamp(r['retrieved_at']) <= cutoff_ns
                                      for r in visible)
    blockers = {'SUSPENSION': 'SUSPENDED', 'DELIST': 'DELISTED',
                'LISTED': 'NOT_LISTED', 'UNIVERSE': 'NOT_MEMBER'}
    result['reason_codes'] = ['SYNTHETIC_SELECTION_NO_LIVE_AUTHORITY',
                              'TRADING_POLICY_UNSET_REQUIRED',
                              'ORDER_PRICE_NOT_PROVIDED']
    for component, blocked_value in blockers.items():
        if result['selected'][component]['value'] == blocked_value:
            result['status'] = 'BLOCKED_FIXTURE_ONLY'
            result['reason_codes'].append('STATUS_KNOWN_BLOCK:' + component)
    if result['selected']['ST']['value'] == 'ST':
        result['reason_codes'].append('ST_POLICY_UNSET_REQUIRED')
    result['reason_codes'] = sorted(result['reason_codes'])
    return result


def _inputs(inputs):
    require(type(inputs) is list and len(inputs) == len(SYMBOLS),
            'PIT_INPUT_COHORT_INVALID')
    require(tuple(x.get('symbol') for x in inputs if type(x) is dict) == SYMBOLS,
            'PIT_INPUT_COHORT_INVALID')
    for x in inputs:
        require(x.get('contract_name') == 'RealResearchSandboxInput' and
                x.get('namespace') == 'LOCAL_EXPERIMENTAL_REAL_RESEARCH:CORE_40' and
                x.get('formal_source_admission') == 'BLOCKED' and
                x.get('historical_visibility_proven') is False and
                x.get('productionGate') is False and
                x.get('license_verified') is False and
                x.get('provider_identity_verified') is False and
                x.get('transport_integrity_verified') is False,
                'PIT_INPUT_SOURCE_PROMOTION')
        hash_value(x.get('content_hash'))
        require(x['content_hash'] == digest({k: v for k, v in x.items()
                                            if k != 'content_hash'}),
                'PIT_INPUT_SEAL_INVALID')
        require(type(x.get('body')) is dict and
                type(x['body'].get('observations')) is list and
                type(x['body'].get('excluded')) is list, 'PIT_INPUT_BODY_INVALID')
        for row in x['body']['observations']:
            require(type(row) is dict and type(row.get('values')) is dict and
                    type(row.get('source_ref')) is dict and
                    type(row.get('api_name')) is str, 'PIT_INPUT_ROW_INVALID')
            ref = row['source_ref']
            hash_value(ref.get('raw_sha256'))
            _text(ref.get('request_id'))
            hash_value(ref.get('request_fingerprint'))
            require(type(ref.get('row_ordinal')) is int and ref['row_ordinal'] >= 0,
                    'PIT_ORDINAL_INVALID')
            timestamp(ref.get('retrieved_at'))
            require(ref.get('published_at') is None and ref.get('event_time') is None
                    and ref.get('available_at') == ref['retrieved_at'],
                    'PIT_INPUT_CLOCK_PROMOTION')
    return inputs


def _base_readiness(kind, inputs):
    return {'kind': kind, 'version': VERSION, 'status': 'BLOCKED',
            'symbols': list(SYMBOLS), 'input_hashes': [x['content_hash'] for x in inputs],
            'historical_visibility_proven': False, 'live_authority': False,
            'formal_source_admission': 'BLOCKED', 'productionGate': False,
            'actual_selected_versions': 0,
            'reason_codes': ['QUARANTINED_SOURCE_NO_AUTHORITY',
                             'HISTORICAL_VISIBILITY_UNPROVEN'], 'coverage': []}


def financial_readiness(inputs):
    """Describe current revision/date-field evidence without financial values."""
    inputs = _inputs(inputs)
    result = _base_readiness('FINANCIAL_REVISION_READINESS', inputs)
    result['reason_codes'] += ['FINANCIAL_UNITS_UNVERIFIED',
                               'FINANCIAL_FIRST_VISIBILITY_UNKNOWN',
                               'FINANCIAL_REVISION_CHRONOLOGY_UNPROVEN']
    for x in inputs:
        for api, statement in API_STATEMENTS.items():
            rows = [r for r in x['body']['observations'] if r['api_name'] == api]
            refs = defaultdict(list)
            for row in rows:
                ref = row['source_ref']
                identity = (ref['raw_sha256'], ref['request_id'],
                            ref['request_fingerprint'], ref['retrieved_at'])
                refs[identity].append(ref['row_ordinal'])
            dates = Counter()
            for row in rows:
                for field in ('ann_date', 'f_ann_date'):
                    val = row['values'].get(field)
                    if type(val) is str and len(val) == 8 and val.isdigit():
                        dates[field] += 1
            result['coverage'].append({
                'symbol': x['symbol'], 'statement': statement, 'api_name': api,
                'observed_rows': len(rows),
                'distinct_observed_periods': len({r['values'].get('end_date') for r in rows
                                                if r['values'].get('end_date') is not None}),
                'date_only_field_counts': dict(sorted(dates.items())),
                'revision_flag_field_present_rows': sum('update_flag' in r['values']
                                                       for r in rows),
                'raw_sources': [{'raw_hash': h, 'content_version': h,
                                 'request_id': request_id,
                                 'request_fingerprint': request_fingerprint,
                                 'retrieved_at': retrieved_at, 'row_count': len(ordinals),
                                 'row_ordinals': sorted(ordinals)}
                                for (h, request_id, request_fingerprint, retrieved_at),
                                ordinals in sorted(refs.items())],
                'first_visibility': 'UNKNOWN', 'revision_chronology': 'UNKNOWN',
                'publication_clock': 'UNKNOWN',
                'availability_basis': 'CURRENT_RETRIEVAL_ONLY',
                'units': 'UNVERIFIED_SOURCE_UNITS', 'status': 'BLOCKED',
                'update_flag_is_not_chronology': True,
                'posthoc_retrieval_does_not_prove_historical_visibility': True})
    return result


def tradeability_readiness(inputs):
    """No current stock_basic or index membership row becomes historical status."""
    inputs = _inputs(inputs)
    result = _base_readiness('TRADEABILITY_HISTORY_READINESS', inputs)
    result['reason_codes'] += ['STATUS_HISTORY_COVERAGE_INCOMPLETE',
                               'CURRENT_STATUS_NOT_HISTORICAL',
                               'CURRENT_UNIVERSE_NOT_HISTORICAL',
                               'ABSENT_STATUS_IS_UNKNOWN']
    for x in inputs:
        rows = x['body']['observations']
        result['coverage'].append({
            'symbol': x['symbol'],
            'current_security_rows': sum(r['api_name'] == 'stock_basic' for r in rows),
            'current_membership_rows': sum(r['api_name'] == 'index_member_all' for r in rows),
            'historical_components': {c: {'status': 'UNKNOWN',
                                         'complete_intervals': 0,
                                         'historical_visibility_proven': False}
                                      for c in COMPONENTS},
            'excluded_rows': len(x['body']['excluded']),
            'status': 'BLOCKED', 'absence_implies_safe': False,
            'current_universe_backfill': False, 'survivorship_free_universe': False})
    return result
