"""Explicit refresh planning and structural DQ; neither grants PIT admission.

The 30 calendar day overlap is a collector policy, not a signal window or a
guarantee that old revisions will be caught. Versioned domains are swept in full.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json

from .interface import LABELS, canonical
from .clocks import exact_clock

VERSION = '1.0.0-sidecar-only'
FULL_SWEEP_DOMAINS = frozenset({
    'FINANCIAL_INCOME', 'FINANCIAL_BALANCE', 'FINANCIAL_CASHFLOW',
    'FINANCIAL_INDICATOR', 'STATUS', 'INDUSTRY_MEMBERSHIP', 'CATALYST', 'UNIVERSE',
})
SESSION_DOMAINS = frozenset({'PRICE', 'VALUATION', 'ACTION', 'BENCHMARK', 'SECTOR_TOTAL_RETURN'})
DATE_FIELDS = frozenset({
    'trade_date', 'cal_date', 'end_date', 'ann_date', 'f_ann_date', 'report_end',
    'list_date', 'delist_date', 'in_date', 'out_date', 'ex_date', 'record_date',
    'pay_date', 'imp_ann_date', 'published_date',
})
NUMBER_FIELDS = frozenset({
    'open', 'high', 'low', 'close', 'pre_close', 'vol', 'volume', 'amount',
    'adj_factor', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 'total_mv', 'circ_mv',
    'revenue', 'oper_cost', 'n_income', 'money_cap', 'total_liab', 'n_cashflow_act',
    'roic', 'ebitda', 'netdebt', 'total_return_index', 'is_open',
})
CLOCKS = ('published_at', 'first_visible_at', 'available_at')


def _day(value):
    if value in (None, ''):
        return None
    if not isinstance(value, str):
        raise ValueError('DATE_NOT_STRING')
    if len(value) == 8 and value.isdigit():
        value = value[:4] + '-' + value[4:6] + '-' + value[6:]
    return date.fromisoformat(value)


def _clock(value):
    if value is None:
        return None
    return exact_clock(value)


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError('NUMBER_INVALID_TYPE')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('NUMBER_INVALID') from exc
    if not result.is_finite():
        raise ValueError('NUMBER_NONFINITE')
    if len(result.as_tuple().digits) > 50 or abs(result.as_tuple().exponent) > 100 or result.adjusted() > 50:
        raise ValueError('NUMBER_PRECISION_OR_EXPONENT_UNSUPPORTED')
    return result


def _usable(value):
    return value not in (None, '', 'UNSET_REQUIRED', 'UNKNOWN', 'NOT_COMPUTABLE')


def _unit_known(value):
    return isinstance(value, str) and _usable(value) and value not in (
        'UNVERIFIED', 'SOURCE_DECLARED_NOT_INDEPENDENTLY_VERIFIED')


def _exact_clock_present(value):
    try:
        return _clock(value) is not None
    except (ValueError, TypeError):
        return False


def _semantic(record):
    # Source/capture clock and provenance are deliberately not vendor revisions.
    return {k: record.get(k) for k in ('event_date', 'published_at', 'available_at',
                                      'first_visible_at', 'revision_id', 'fields', 'units')}


def validate_records(records):
    """Report malformed data, valid conflicting versions, and unresolved clocks.

    A conflict is retained evidence, not a malformed record. Store ingestion uses
    errors to reject the entire batch, and keeps conflicts for later reconciliation.
    Missing data remains unknown. No date-only timestamp is upgraded to an exact
    clock, and no current capture is treated as historical visibility.
    """
    if not isinstance(records, (list, tuple)):
        raise ValueError('RECORDS_LIST_REQUIRED')
    errors, warnings, conflicts, duplicates, versions = [], [], [], [], []
    grouped = defaultdict(list)
    price_groups = defaultdict(list)

    def issue(target, index, code, field=None, detail=None):
        row = {'row': index, 'code': code}
        if field is not None:
            row['field'] = field
        if detail is not None:
            row['detail'] = detail
        target.append(row)

    for i, record in enumerate(records):
        if not isinstance(record, dict):
            issue(errors, i, 'RECORD_OBJECT_REQUIRED')
            continue
        required = ('identity', 'event_date', *CLOCKS, 'revision_id', 'fields', 'units', 'provenance')
        for key in required:
            if key not in record:
                issue(errors, i, 'RECORD_FIELD_REQUIRED', key)
        if not isinstance(record.get('identity'), str) or not record['identity']:
            issue(errors, i, 'IDENTITY_REQUIRED', 'identity')
        if record.get('revision_id') is not None and not isinstance(record['revision_id'], str):
            issue(errors, i, 'REVISION_ID_INVALID', 'revision_id')
        for key in ('fields', 'units', 'provenance'):
            if not isinstance(record.get(key), dict):
                issue(errors, i, 'OBJECT_REQUIRED', key)
        for key in ('domain', 'source', 'symbol'):
            if key in record and (not isinstance(record[key], str) or not record[key]):
                issue(errors, i, 'METADATA_STRING_REQUIRED', key)
        try:
            canonical(record)
        except (ValueError, TypeError):
            issue(errors, i, 'JSON_NONFINITE_OR_UNSUPPORTED')
        fields = record.get('fields') if isinstance(record.get('fields'), dict) else {}
        numbers = {}
        for key in NUMBER_FIELDS.intersection(fields):
            if not _usable(fields[key]):
                issue(warnings, i, 'NUMERIC_VALUE_UNKNOWN', key)
                continue
            try:
                numbers[key] = _decimal(fields[key])
            except ValueError as exc:
                issue(errors, i, str(exc), key)
        for key in ('open', 'high', 'low', 'close', 'pre_close', 'adj_factor', 'total_return_index'):
            if key in numbers and numbers[key] <= 0:
                issue(errors, i, 'POSITIVE_VALUE_REQUIRED', key)
        for key in ('vol', 'volume', 'amount', 'total_mv', 'circ_mv'):
            if key in numbers and numbers[key] < 0:
                issue(errors, i, 'NEGATIVE_VOLUME_OR_NOTIONAL', key)
        if 'is_open' in numbers and numbers['is_open'] not in (0, 1):
            issue(errors, i, 'CALENDAR_OPEN_FLAG_INVALID', 'is_open')
        if 'high' in numbers:
            for key in ('low', 'open', 'close'):
                if key in numbers and numbers['high'] < numbers[key]:
                    issue(errors, i, 'OHLC_HIGH_BELOW_COMPONENT', key)
        if 'low' in numbers:
            for key in ('high', 'open', 'close'):
                if key in numbers and numbers['low'] > numbers[key]:
                    issue(errors, i, 'OHLC_LOW_ABOVE_COMPONENT', key)
        dates = {}
        for key, value in [('event_date', record.get('event_date')), *fields.items()]:
            if key != 'event_date' and key not in DATE_FIELDS:
                continue
            if not _usable(value):
                continue
            try:
                dates[key] = _day(value)
            except (ValueError, TypeError):
                issue(errors, i, 'INVALID_DATE', key)
        if record.get('event_date') is None:
            issue(warnings, i, 'EVENT_DATE_UNKNOWN', 'event_date')
        for key in ('trade_date', 'cal_date'):
            if key in dates and 'event_date' in dates and dates[key] != dates['event_date']:
                issue(errors, i, 'EVENT_DATE_FIELD_MISMATCH', key)
        for start, end in (('in_date', 'out_date'), ('list_date', 'delist_date')):
            if start in dates and end in dates and dates[start] > dates[end]:
                issue(errors, i, 'INTERVAL_REVERSED', end)
        domain = record.get('domain', '')
        if not isinstance(domain, str):
            domain = ''
        if domain.startswith('FINANCIAL_'):
            period = dates.get('end_date') or dates.get('report_end') or dates.get('event_date')
            for key in ('ann_date', 'f_ann_date'):
                if period and key in dates and dates[key] < period:
                    issue(errors, i, 'FINANCIAL_ANNOUNCEMENT_BEFORE_REPORT_END', key)
            if not period or not any(k in dates for k in ('ann_date', 'f_ann_date')):
                issue(warnings, i, 'FINANCIAL_PUBLICATION_DATE_UNRESOLVED')
            issue(warnings, i, 'FINANCIAL_QUARTER_YTD_SEMANTICS_NOT_ACCEPTED')
        clocks = {}
        for key in (*CLOCKS, 'retrieved_at'):
            value = record.get(key)
            if value is None:
                if key in CLOCKS:
                    issue(warnings, i, 'HISTORICAL_CLOCK_UNKNOWN', key)
                continue
            # A source date is useful evidence but lacks intraday precision.
            if isinstance(value, str) and len(value) in (8, 10):
                try:
                    _day(value)
                    issue(warnings, i, 'DATE_ONLY_CLOCK_NOT_EXACT', key)
                except ValueError:
                    issue(errors, i, 'INVALID_CLOCK', key)
                if key == 'retrieved_at':
                    issue(errors, i, 'RETRIEVAL_EXACT_CLOCK_REQUIRED', key)
                continue
            try:
                clocks[key] = _clock(value)
            except (ValueError, TypeError):
                issue(errors, i, 'INVALID_CLOCK', key)
        # Availability and first visibility are separate source namespaces; their
        # relative ordering needs an admitted clock definition, not an inference.
        clock_pairs = [('published_at', 'available_at'), ('published_at', 'first_visible_at'),
                       ('published_at', 'retrieved_at'), ('available_at', 'retrieved_at'),
                       ('first_visible_at', 'retrieved_at')]
        for left, right in clock_pairs:
            if left in clocks and right in clocks and clocks[left] > clocks[right]:
                issue(errors, i, 'CLOCK_ORDER_REVERSED', right, left)
        units = record.get('units') if isinstance(record.get('units'), dict) else {}
        for key in numbers:
            if not _unit_known(units.get(key)):
                issue(warnings, i, 'FIELD_UNIT_UNRESOLVED', key)
        if record.get('historical_visibility_proven') or record.get('source_admitted'):
            issue(warnings, i, 'ADMISSION_CLAIM_NOT_ACCEPTED_BY_DQ')
        try:
            payload_hash = hashlib.sha256(canonical(_semantic(record))).hexdigest()
            values_hash = hashlib.sha256(canonical({'fields': fields, 'units': units})).hexdigest()
        except (ValueError, TypeError):
            continue
        if any(record.get(key) is not None and not isinstance(record.get(key), str)
               for key in ('source', 'domain', 'symbol', 'identity', 'event_date', 'revision_id')):
            continue
        key = (record.get('source'), domain, record.get('symbol'),
               record.get('identity'), record.get('event_date'))
        grouped[key].append((i, record.get('revision_id'), payload_hash, values_hash))
        if domain == 'PRICE' and dates.get('event_date') is not None:
            price_groups[(record.get('symbol'), dates['event_date'].isoformat())].append(
                (i, str(record.get('source')), numbers, units))

    for key, rows in grouped.items():
        semantic = defaultdict(list)
        revisions = defaultdict(list)
        for i, revision, payload_hash, values_hash in rows:
            semantic[payload_hash].append(i)
            revisions[revision].append((i, values_hash))
        for payload_hash, indexes in semantic.items():
            if len(indexes) > 1:
                duplicates.append({'identity': list(key), 'rows': indexes, 'semantic_sha256': payload_hash})
        if len(semantic) > 1:
            versions.append({'identity': list(key), 'rows': [r[0] for r in rows],
                             'version_count': len(semantic), 'state': 'RECONCILIATION_REQUIRED'})
        for revision, rrows in revisions.items():
            if len({r[1] for r in rrows}) > 1:
                conflicts.append({'identity': list(key), 'revision_id': revision,
                                  'rows': [r[0] for r in rrows],
                                  'code': 'SAME_REVISION_CONFLICT' if revision is not None else 'UNVERSIONED_VALUE_CONFLICT'})
    cross_price, cross_volume = [], []
    for (symbol, day), group in price_groups.items():
        if len({row[1] for row in group}) < 2:
            continue
        for field in ('open', 'high', 'low', 'close'):
            source_values = defaultdict(set)
            row_indexes = []
            for index, source, values, _ in group:
                if field in values:
                    source_values[source].add(values[field])
                    row_indexes.append(index)
            if len(source_values) > 1 and len(set().union(*source_values.values())) > 1:
                cross_price.append({'domain': 'PRICE', 'symbol': symbol, 'event_date': day,
                    'field': field, 'rows': row_indexes, 'code': 'CROSS_SOURCE_OHLC_CONFLICT',
                    'source_values': {s: [format(v, 'f') for v in sorted(vs)] for s, vs in sorted(source_values.items())},
                    'raw_adjustment_currency_and_source_method_reconciliation': 'REQUIRED',
                    'preferred_source_automatically_selected': False})
        volumes = []
        for index, source, values, units in group:
            for field in ('vol', 'volume'):
                if field in values:
                    unit = units.get(field)
                    known = _unit_known(unit)
                    volumes.append((index, source, values[field], unit if known else None))
        if len({r[1] for r in volumes}) > 1:
            unit_values = {r[3] for r in volumes}
            comparable = None not in unit_values and len(unit_values) == 1
            different = len({r[2] for r in volumes}) > 1
            cross_volume.append({'domain': 'PRICE', 'symbol': symbol, 'event_date': day,
                'rows': [r[0] for r in volumes],
                'state': 'UNKNOWN_UNITS_NOT_COMPARABLE' if not comparable else
                         ('CROSS_SOURCE_VOLUME_CONFLICT' if different else 'COMPARABLE_MATCH'),
                'unit': next(iter(unit_values)) if comparable else None,
                'absolute_values_compared': comparable,
                'units_conversion_inferred': False})
    has_conflict = bool(conflicts or cross_price or any(r['state'] == 'CROSS_SOURCE_VOLUME_CONFLICT' for r in cross_volume))
    state = 'INVALID_RECORDS' if errors else ('VERSION_CONFLICT' if has_conflict else 'STRUCTURAL_PASS_PIT_UNPROVEN')
    return {'version': VERSION, 'labels': list(LABELS), 'state': state,
            'record_count': len(records), 'error_count': len(errors), 'warning_count': len(warnings),
            'errors': errors, 'warnings': warnings, 'conflicts': conflicts,
            'multiple_versions': versions, 'duplicate_captures_or_rows': duplicates,
            'cross_source_price_conflicts': cross_price, 'cross_source_volume_checks': cross_volume,
            'cross_source_volume_comparability': 'UNKNOWN_OR_CHECKED_PER_DATE_NO_INFERRED_CONVERSION',
            'available_vs_first_visible_order': 'SOURCE_CLOCK_DEFINITION_UNSET_NO_RELATION_INFERRED',
            'actual_pit_admitted_records': 0, 'historical_visibility_proven': False,
            'full_strategy_data_pass': False, 'productionGate': False}


def _ranges(days):
    """Compact only adjacent calendar dates; never infer business weekdays."""
    result = []
    for day in sorted(set(days)):
        if result and day == result[-1][1] + timedelta(days=1):
            result[-1][1] = day
        else:
            result.append([day, day])
    return [{'start': a.isoformat(), 'end': b.isoformat()} for a, b in result]


def build_update_plan(records, requirements, through):
    """Return deterministic, repeatable requests for every configured domain.

    Presence counts distinct logical dates rather than raw responses/captures.
    Calendar gaps require explicit calendar rows, including closed dates. Financial
    and interval domains always request full history/all available revisions.
    """
    cutoff = _day(through)
    if cutoff is None:
        raise ValueError('THROUGH_DATE_REQUIRED')
    dq = validate_records(records)
    invalid = {row['row'] for row in dq['errors']}
    good = [r for i, r in enumerate(records) if i not in invalid]
    rows = []
    for req in requirements:
        start = _day(req['start'])
        end = min(cutoff, _day(req['end']))
        overlap = req.get('revision_lookback_days', 30)
        if isinstance(overlap, bool) or not isinstance(overlap, int) or overlap < 0:
            raise ValueError('REVISION_LOOKBACK_CALENDAR_DAYS_INVALID')
        requested_mode = req.get('refresh_mode', 'INCREMENTAL_WITH_OVERLAP')
        if requested_mode not in ('FULL_VERSION_SWEEP', 'INCREMENTAL_WITH_OVERLAP'):
            raise ValueError('REFRESH_MODE_INVALID')
        mode = 'FULL_VERSION_SWEEP' if req['domain'] in FULL_SWEEP_DOMAINS else requested_mode
        for symbol in req['symbols']:
            matched = [r for r in good if r.get('domain') == req['domain'] and
                       r.get('symbol') in (symbol, '*', 'ALL', 'SSE')]
            dated = []
            for r in matched:
                day = _day(r.get('event_date'))
                if day is not None and start <= day <= end:
                    dated.append((day, r))
            dates = sorted({day for day, _ in dated})
            by_date = defaultdict(list)
            for day, record in dated:
                by_date[day].append(record)
            # A date needs one complete observation, not fields assembled across
            # incompatible captures or revisions.
            complete_dates = {day for day, rs in by_date.items()
                              if any(all(_usable(r.get('fields', {}).get(f)) for f in req['fields']) for r in rs)}
            conflict_dates = set()
            for conflict in dq['conflicts']:
                _, domain, csymbol, _, cdate = conflict['identity']
                if domain == req['domain'] and csymbol in (symbol, '*', 'ALL', 'SSE') and _usable(cdate):
                    conflict_dates.add(_day(cdate))
            if req['domain'] == 'PRICE':
                for conflict in dq['cross_source_price_conflicts']:
                    if conflict['symbol'] in (symbol, '*', 'ALL', 'SSE'):
                        conflict_dates.add(_day(conflict['event_date']))
                for conflict in dq['cross_source_volume_checks']:
                    if conflict['symbol'] in (symbol, '*', 'ALL', 'SSE') and conflict['state'] == 'CROSS_SOURCE_VOLUME_CONFLICT':
                        conflict_dates.add(_day(conflict['event_date']))
            conflict_dates = {d for d in conflict_dates if start <= d <= end}
            complete_dates -= conflict_dates
            missing_fields = [f for f in req['fields']
                              if not any(_usable(r.get('fields', {}).get(f)) for _, r in dated)]
            field_dates = {f: len({d for d, r in dated if _usable(r.get('fields', {}).get(f))}) for f in req['fields']}
            unit_dates = {f: len({d for d, r in dated if _unit_known(r.get('units', {}).get(f))}) for f in req['fields']
                          if f in NUMBER_FIELDS}
            clock_counts = {key: len({day for day, r in dated if _exact_clock_present(r.get(key))}) for key in CLOCKS}
            first, last = (dates[0], dates[-1]) if dates else (None, None)
            plans = []
            if start <= end:
                if mode == 'FULL_VERSION_SWEEP':
                    plans.append({'kind': 'FULL_VERSION_SWEEP', 'start': start.isoformat(), 'end': end.isoformat(),
                                  'all_available_revisions': True, 'full_valid_intervals': req['domain'] in
                                  ('STATUS', 'INDUSTRY_MEMBERSHIP', 'UNIVERSE'),
                                  'event_only_safe': False})
                elif not dates:
                    plans.append({'kind': 'INITIAL_BACKFILL', 'start': start.isoformat(), 'end': end.isoformat()})
                else:
                    if first > start:
                        plans.append({'kind': 'INITIAL_HISTORY_GAP', 'start': start.isoformat(),
                                      'end': (first-timedelta(days=1)).isoformat()})
                    if last < end:
                        plans.append({'kind': 'INCREMENTAL', 'start': (last + timedelta(days=1)).isoformat(),
                                      'end': end.isoformat()})
                    plans.append({'kind': 'REVISION_OVERLAP', 'start': max(start, last-timedelta(days=overlap)).isoformat(),
                                  'end': end.isoformat(), 'lookback_unit': 'CALENDAR_DAYS',
                                  'lookback_days': overlap, 'purpose': 'COLLECTOR_OVERLAP_NOT_PIT_GUARANTEE'})
            calendar_by_date = defaultdict(set)
            for r in good:
                if r.get('domain') != 'CALENDAR' or r.get('symbol') not in (symbol, '*', 'ALL', 'SSE'):
                    continue
                cfields = r.get('fields', {})
                cday = _day(cfields.get('cal_date') or r.get('event_date'))
                if cday is not None and start <= cday <= end and _usable(cfields.get('is_open')):
                    calendar_by_date[cday].add(int(_decimal(cfields['is_open'])))
            calendar_conflicts = sorted(d for d, flags in calendar_by_date.items() if len(flags) > 1)
            open_days = {d for d, flags in calendar_by_date.items() if flags == {1}}
            missing_sessions = sorted(open_days - complete_dates) if req['domain'] in SESSION_DOMAINS else []
            incomplete_dates = sorted(set(dates)-complete_dates)
            for interval in _ranges(missing_sessions):
                plans.append({'kind': 'EXPLICIT_CALENDAR_GAP', **interval})
            for interval in _ranges(incomplete_dates):
                plans.append({'kind': 'FIELD_REPAIR', **interval})
            calendar_required = req['domain'] in SESSION_DOMAINS or req['domain'] == 'CALENDAR'
            span = max(0, (end-start).days+1)
            calendar_complete = bool(span and len(calendar_by_date) == span and not calendar_conflicts)
            reasons = []
            if not matched:
                reasons.append('DOMAIN_ABSENT')
            if not dates:
                reasons.append('DATED_OBSERVATIONS_ABSENT')
            if missing_fields:
                reasons.append('FIELDS_ABSENT')
            if incomplete_dates:
                reasons.append('FIELDS_INCOMPLETE_BY_DATE')
            if conflict_dates:
                reasons.append('OBSERVATION_VERSION_CONFLICT_UNRECONCILED')
            if calendar_required and not calendar_complete:
                reasons.append('EXPLICIT_CALENDAR_COVERAGE_INCOMPLETE')
            if missing_sessions:
                reasons.append('EXPLICIT_OPEN_SESSION_OBSERVATIONS_MISSING')
            if calendar_conflicts:
                reasons.append('CALENDAR_VERSION_CONFLICT')
            if any(clock_counts[key] < len(dates) for key in CLOCKS):
                reasons.append('HISTORICAL_CLOCKS_INSUFFICIENT')
            if any(count < len(dates) for count in unit_dates.values()):
                reasons.append('NUMERIC_FIELD_UNITS_INSUFFICIENT')
            reasons.extend(['SOURCE_ADMISSION_UNACCEPTED', 'HISTORICAL_PIT_UNPROVEN'])
            # Canonical collector ranges are a union of diagnostic requests. Keep
            # reasons separately, but never request the same span twice per refresh.
            intervals = []
            for item in sorted(plans, key=lambda p: (p['start'], p['end'])):
                a, b = _day(item['start']), _day(item['end'])
                if intervals and a <= _day(intervals[-1]['end']) + timedelta(days=1):
                    intervals[-1]['end'] = max(b, _day(intervals[-1]['end'])).isoformat()
                else:
                    intervals.append({'start': a.isoformat(), 'end': b.isoformat()})
            rows.append({'requirement_id': req['id'], 'domain': req['domain'], 'symbol': symbol,
                         'start': start.isoformat(), 'through': end.isoformat(), 'refresh_mode': mode,
                         'required_fields': list(req['fields']), 'window': req.get('window', ''),
                         'pit_requirements': list(req.get('pit_requirements', [])),
                         'revision_lookback_days': overlap, 'lookback_unit': 'CALENDAR_DAYS',
                         'collector_overlap_is_pit_guarantee': False, 'requests': plans,
                         'requested_intervals': intervals,
                         'raw_record_versions': len(matched), 'distinct_event_dates': len(dates),
                         'complete_field_dates': len(complete_dates), 'field_date_counts': field_dates,
                         'unit_date_counts': unit_dates,
                         'missing_fields': missing_fields, 'incomplete_field_dates': [d.isoformat() for d in incomplete_dates],
                         'unreconciled_conflict_dates': [d.isoformat() for d in sorted(conflict_dates)],
                         'first_observed': first.isoformat() if first else None,
                         'last_observed': last.isoformat() if last else None,
                         'clock_date_counts': clock_counts,
                         'calendar_state': 'EXPLICIT_COMPLETE' if calendar_complete else
                            ('EXPLICIT_PARTIAL' if calendar_by_date else 'UNKNOWN_NO_CALENDAR'),
                         'calendar_is_historical_pit_admitted': False,
                         'calendar_conflict_dates': [d.isoformat() for d in calendar_conflicts],
                         'missing_open_session_dates': [d.isoformat() for d in missing_sessions],
                         'gap_detection_complete': calendar_complete if calendar_required else False,
                         'reason_codes': reasons, 'pit_state': 'NOT_ACCEPTED',
                         'full_strategy_data_pass': False})
    return {'version': VERSION, 'labels': list(LABELS), 'through': cutoff.isoformat(),
            'state': 'EXPLICIT_REFRESH_PLAN_NON_PIT', 'rows': rows, 'requirement_count': len(rows),
            'deterministic_given_inputs': True, 'calendar_weekday_inference': False,
            'latest_survivor_universe_assumption': False, 'automatic_scheduling': False,
            'dq_state': dq['state'], 'actual_pit_admitted_records': 0,
            'full_strategy_data_pass': False, 'productionGate': False}
