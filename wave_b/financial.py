"""Read-only observed financial graph; no source admission or historical PIT claim."""
from datetime import datetime
from copy import deepcopy
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from .core import observations, request_views, require_inputs, make_result

METRICS = ('eps', 'roe', 'debt_to_assets', 'netprofit_yoy')
NEW_PERIODS = ('20250630', '20250930', '20251231', '20260331', '20260630', '20260930')
NEW_START, NEW_END = '20250601', '20261005'


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _hash(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                               separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _date(value):
    _require(type(value) is str and re.fullmatch(r'\d{8}', value), 'FINANCIAL_DATE_ONLY_LITERAL_REQUIRED')
    try:
        parsed = datetime.strptime(value, '%Y%m%d').date()
    except ValueError:
        raise ValueError('FINANCIAL_DATE_ONLY_LITERAL_INVALID') from None
    _require(parsed.strftime('%Y%m%d') == value, 'FINANCIAL_DATE_ONLY_LITERAL_INVALID')
    return parsed


def _instant(value):
    _require(type(value) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)', value), 'FINANCIAL_CAPTURE_CLOCK_REQUIRED')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('FINANCIAL_CAPTURE_CLOCK_INVALID') from None
    return parsed


def _decimal(value):
    if value is None:
        return
    _require(type(value) is str and len(value) <= 160, 'FINANCIAL_DECIMAL_STRING_REQUIRED')
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise ValueError('FINANCIAL_DECIMAL_INVALID') from None
    _require(parsed.is_finite() and abs(parsed.as_tuple().exponent) <= 64 and len(parsed.as_tuple().digits) <= 100,
             'FINANCIAL_DECIMAL_INVALID')


def _fields(view):
    fields = view.get('fields', [])
    if type(fields) is str:
        return tuple(x.strip() for x in fields.split(',') if x.strip())
    _require(type(fields) in (tuple, list), 'FINANCIAL_FIELDS_INVALID')
    return tuple(fields)


def _scope(view):
    scope = view.get('date_scope', {})
    _require(scope.get('key') == 'end_date', 'FINANCIAL_REPORT_PERIOD_SCOPE_REQUIRED')
    start, end = scope.get('start'), scope.get('end')
    _date(start); _date(end)
    _require(start <= end, 'FINANCIAL_REPORT_PERIOD_SCOPE_INVALID')
    return start, end


def _probe_form(view):
    params = view.get('params', {})
    return 'NARROW_PERIOD' if 'period' in params else 'RANGE' if 'start_date' in params or 'end_date' in params else 'UNKNOWN'


def analyze(inputs):
    """Keep every row/raw reference, classify request scopes and observed metric changes."""
    require_inputs(inputs)
    all_records, scopes, grouped, per_origin = [], [], {}, {}
    for origin in ('legacy', 'new'):
        views = request_views(inputs, 'fina_indicator', origin=origin)
        obs = observations(inputs, 'fina_indicator', origin=origin)
        by_request = {}
        for observation in obs:
            ref = observation['ref']
            _require(type(ref.get('request_id')) is str, 'FINANCIAL_REQUEST_REF_REQUIRED')
            by_request.setdefault(ref['request_id'], []).append(observation)
        seen_requests = set()
        origin_records = []
        for view in views:
            request_id = view['request_id']
            _require(request_id not in seen_requests, 'FINANCIAL_DUPLICATE_REQUEST_VIEW')
            seen_requests.add(request_id)
            start, end = _scope(view)
            form = _probe_form(view)
            fields = _fields(view)
            if origin == 'new':
                params = view.get('params', {})
                _require((form == 'NARROW_PERIOD' and start == end and start in NEW_PERIODS and params.get('period') == start) or
                         (form == 'RANGE' and start == NEW_START and end == NEW_END and params.get('start_date') == start and params.get('end_date') == end),
                         'FINANCIAL_NEW_REQUEST_WINDOW_INVALID')
            row_obs = by_request.pop(request_id, [])
            outside_refs, future_publication_refs, local_records = [], [], []
            for observation in row_obs:
                values, ref = deepcopy(observation['values']), deepcopy(observation['ref'])
                symbol, report_period = values.get('ts_code'), values.get('end_date')
                _require(type(symbol) is str and symbol, 'FINANCIAL_SYMBOL_REQUIRED')
                _date(report_period)
                ann_date = values.get('ann_date')
                if ann_date not in (None, ''):
                    _date(ann_date)
                else:
                    ann_date = None
                f_ann = values.get('f_ann_date') if 'f_ann_date' in values else None
                if f_ann not in (None, ''):
                    _date(f_ann)
                else:
                    f_ann = None
                available, retrieved = ref['available_at'], ref['retrieved_at']
                _instant(available); _instant(retrieved)
                _require(available == retrieved, 'FINANCIAL_HISTORICAL_AVAILABILITY_FORBIDDEN')
                _require(ref.get('published_at') is None, 'FINANCIAL_DATE_ONLY_MIDNIGHT_FORBIDDEN')
                captured_day = _instant(retrieved).astimezone(ZoneInfo('Asia/Shanghai')).date()
                future_publication = any(_date(literal) > captured_day for literal in (ann_date, f_ann) if literal is not None)
                if future_publication:
                    future_publication_refs.append(ref)
                metrics = {name: values.get(name) for name in METRICS}
                for value in metrics.values():
                    _decimal(value)
                outside = not start <= report_period <= end
                if outside:
                    outside_refs.append(ref)
                record = {
                    'origin': origin, 'ts_code': symbol, 'report_period': report_period,
                    'source_ann_date': ann_date, 'source_ann_date_precision': 'DATE_ONLY' if ann_date else 'UNKNOWN',
                    'source_f_ann_date': f_ann,
                    'source_f_ann_date_precision': 'DATE_ONLY' if f_ann else 'UNKNOWN',
                    'source_future_publication_literal': future_publication,
                    'f_ann_date_state': 'SOURCE_LITERAL_PRESENT' if f_ann else 'NOT_REQUESTED_OR_NOT_PROVIDED',
                    'f_ann_date_requested': 'f_ann_date' in fields,
                    'published_at': None, 'available_at': available, 'retrieved_at': retrieved,
                    'availability_basis': 'ACTUAL_RESPONSE_CAPTURE_ONLY_NOT_HISTORICAL',
                    'metrics': metrics, 'metric_units': {
                        'eps': 'PROVIDER_CURRENCY_PER_SHARE_UNVERIFIED',
                        'roe': 'PROVIDER_RATIO_SCALE_UNVERIFIED',
                        'debt_to_assets': 'PROVIDER_RATIO_SCALE_UNVERIFIED',
                        'netprofit_yoy': 'PROVIDER_PERCENT_SCALE_UNVERIFIED'},
                    'source_update_flag': values.get('update_flag'),
                    'observation_id': _hash({'origin': origin, 'values': values, 'ref': ref}),
                    'observed_version_hash': _hash(values), 'metric_hash': _hash(metrics),
                    'raw_row_ref': ref, 'source_values': values,
                    'period_within_request_scope': not outside,
                    'period_within_current_wave_window': NEW_START <= report_period <= NEW_END,
                    'request_response_blocked': bool(view.get('response_blocked')),
                    'upstream_row_response_blocked': bool(observation.get('response_blocked')),
                    'historical_revision_visibility_proven': False, 'state': 'QUARANTINED',
                    'reason_codes': (['PERIOD_OUTSIDE_REQUEST'] if outside else []) + (['FUTURE_PUBLICATION_LITERAL'] if future_publication else []) +
                                    ['SOURCE_ADMISSION_BLOCKED', 'DATE_ONLY_NOT_AN_INSTANT', 'REVISION_CHRONOLOGY_UNKNOWN'],
                }
                all_records.append(record); origin_records.append(record); local_records.append(record)
                grouped.setdefault((symbol, report_period), []).append(record)
            derived_scope_failure = bool(outside_refs)
            upstream_blocked = bool(view.get('response_blocked'))
            # A scope failure blocks the complete response, never just the offending rows.
            complete_blocked = upstream_blocked or derived_scope_failure or bool(future_publication_refs)
            for record in local_records:
                record['whole_response_blocked'] = complete_blocked
            scopes.append({
                'origin': origin, 'request_id': request_id,
                'request_fingerprint': view.get('request_fingerprint'), 'raw_sha256': view.get('raw_sha256'),
                'ts_code': view.get('params', {}).get('ts_code', view.get('ts_code')),
                'probe_form': form, 'start': start, 'end': end,
                'filter_semantics': 'REPORT_PERIOD_END_DATE_NOT_ANNOUNCEMENT_DATE',
                'announcement_filter_proven': False, 'observed_rows': len(row_obs),
                'out_of_scope_row_count': len(outside_refs), 'out_of_scope_refs': outside_refs,
                'future_publication_literal_row_count': len(future_publication_refs), 'future_publication_literal_refs': future_publication_refs,
                'upstream_response_blocked_preserved': upstream_blocked,
                'upstream_reason_codes_preserved': list(view.get('reason_codes', [])),
                'whole_response_blocked': complete_blocked,
                'scope_evaluation': 'EMPTY_IS_NOT_FILTER_PROOF' if not row_obs else
                                    'OBSERVED_SCOPE_FAILURE' if derived_scope_failure else
                                    'FUTURE_PUBLICATION_LITERAL' if future_publication_refs else 'OBSERVED_ROWS_WITHIN_SCOPE_NOT_PROVIDER_SEMANTIC_PROOF',
                'source_admission': 'BLOCKED', 'historical_visibility_proven': False,
                'fields_requested': list(fields), 'f_ann_date_requested': 'f_ann_date' in fields,
            })
        _require(not by_request, 'FINANCIAL_OBSERVATION_REQUEST_ORPHAN')
        origin_scopes = [scope for scope in scopes if scope['origin'] == origin]
        per_origin[origin] = {
            'request_count': len(origin_scopes), 'observation_count': len(origin_records),
            'symbol_period_group_count': len({(r['ts_code'], r['report_period']) for r in origin_records}),
            'scope_failure_observation_count': sum(scope['out_of_scope_row_count'] for scope in origin_scopes),
            'whole_blocked_response_count': sum(scope['whole_response_blocked'] for scope in origin_scopes),
            'whole_blocked_observation_count': sum(r['whole_response_blocked'] for r in origin_records),
            'empty_response_count': sum(scope['observed_rows'] == 0 for scope in origin_scopes),
            'future_publication_literal_observation_count': sum(r['source_future_publication_literal'] for r in origin_records),
        }
    groups = []
    for (symbol, period), records in sorted(grouped.items()):
        relations = []
        for index, left in enumerate(records):
            for right in records[index + 1:]:
                relations.append({'left_observation_id': left['observation_id'], 'right_observation_id': right['observation_id'],
                                  'relation': 'SAME_OBSERVED_METRICS' if left['metric_hash'] == right['metric_hash'] else 'DIFFERENT_OBSERVED_METRICS',
                                  'revision_direction': 'UNKNOWN', 'historical_visibility_proven': False})
        groups.append({'ts_code': symbol, 'report_period': period, 'observation_count': len(records),
                       'distinct_observed_values_versions': len({r['observed_version_hash'] for r in records}),
                       'distinct_metric_versions': len({r['metric_hash'] for r in records}),
                       'observation_ids': [r['observation_id'] for r in records],
                       'versions': [{'observation_id': r['observation_id'], 'observed_version_hash': r['observed_version_hash'],
                                     'metric_hash': r['metric_hash'], 'origin': r['origin'], 'raw_row_ref': r['raw_row_ref'],
                                     'source_ann_date': r['source_ann_date'], 'source_f_ann_date': r['source_f_ann_date'],
                                     'source_update_flag': r['source_update_flag']} for r in records],
                       'observed_relations': relations, 'revision_chronology': 'UNKNOWN',
                       'update_flag_is_chronology': False, 'old_versions_overwritten': False,
                       'duplicate_source_references_collapsed': False})
    new_scopes = [r for r in scopes if r['origin'] == 'new']
    new_periods = [r['start'] for r in new_scopes if r['probe_form'] == 'NARROW_PERIOD' and r['start'] == r['end']]
    new_probe_coverage = []
    for symbol in sorted({scope['ts_code'] for scope in new_scopes if scope['ts_code'] is not None}):
        symbol_scopes = [scope for scope in new_scopes if scope['ts_code'] == symbol]
        requested = sorted({scope['start'] for scope in symbol_scopes if scope['probe_form'] == 'NARROW_PERIOD'})
        new_probe_coverage.append({'ts_code': symbol, 'requested_periods': requested,
                                   'missing_expected_period_probes': sorted(set(NEW_PERIODS) - set(requested)),
                                   'narrow_period_request_count': sum(scope['probe_form'] == 'NARROW_PERIOD' for scope in symbol_scopes),
                                   'range_request_count': sum(scope['probe_form'] == 'RANGE' for scope in symbol_scopes),
                                   'data_completeness_proven': False})
    f_ann_requested_count = sum(scope['f_ann_date_requested'] for scope in scopes)
    body = {
        'financial_revision_candidate': {
            'status': 'CANDIDATE_FOR_OWNER_REVIEW', 'origin_counts': per_origin,
            'combined_observation_count': len(all_records), 'combined_symbol_period_group_count': len(groups),
            'observations': all_records, 'observed_revision_graph': groups,
            'graph_semantics': 'UNDIRECTED_EXACT_SOURCE_LITERAL_RELATIONS_NOT_CONFIRMED_REVISION_CHRONOLOGY',
            'metric_hash_semantics': 'LOSSLESS_SOURCE_LITERALS_NOT_REFORMATTED_OR_UNIT_CALIBRATED',
            'historical_revision_visibility_proven': False,
            'historical_cutoff_query': {'allowed': False, 'state': 'UNKNOWN', 'reason_code': 'HISTORICAL_REVISION_VISIBILITY_UNPROVEN'},
        },
        'financial_range_semantics': {
            'status': 'PARTIAL', 'requests': scopes,
            'filter_key': 'end_date', 'filter_semantics': 'REPORT_PERIOD_NOT_ANN_DATE',
            'new_authorized_window': {'start': NEW_START, 'end': NEW_END},
            'new_expected_periods': list(NEW_PERIODS), 'new_observed_requested_periods': sorted(set(new_periods)),
            'new_narrow_period_request_count': sum(r['probe_form'] == 'NARROW_PERIOD' for r in new_scopes),
            'new_range_request_count': sum(r['probe_form'] == 'RANGE' for r in new_scopes),
            'new_probe_coverage_by_symbol': new_probe_coverage,
            'all_old_failed_rows_and_whole_responses_preserved': True,
            'provider_filter_repaired': False, 'announcement_time_filter_proven': False,
        },
        'financial_known_gaps': {
            'status': 'UNKNOWN', 'source_admission': 'BLOCKED', 'historical_visibility_proven': False,
            'real_policy_receipt_snapshot_packet_count': 0,
            'f_ann_date_current_requested_fields': 'OMITTED_IN_CAPTURE_PLAN_NO_INVENTED_LITERAL' if not f_ann_requested_count else 'SOURCE_REQUEST_FIELD_PRESENT_NO_INVENTED_LITERAL',
            'f_ann_date_requested_request_count': f_ann_requested_count,
            'f_ann_date_missing_observation_count': sum(r['source_f_ann_date'] is None for r in all_records),
            'missing_ann_date_observation_count': sum(r['source_ann_date'] is None for r in all_records),
            'published_at_exact_instant': 'UNKNOWN', 'date_only_midnight_inference_allowed': False,
            'available_at_basis': 'ACTUAL_RETRIEVED_CAPTURE_ONLY',
            'revision_order_by_update_flag_allowed': False, 'historical_visibility_by_ann_date_allowed': False,
            'full_statements_complete': False, 'provider_identity_verified': False,
            'license_verified': False, 'transport_integrity_verified': False,
            'unresolved': ['SOURCE_ADMISSION', 'EXACT_PUBLICATION_INSTANT', 'F_ANN_DATE_SOURCE_FIELD',
                           'REVISION_CHRONOLOGY', 'HISTORICAL_REVISION_VISIBILITY', 'PROVIDER_RANGE_FILTER_SEMANTICS',
                           'PROVIDER_METRIC_UNITS', 'COMPLETE_FINANCIAL_STATEMENTS'],
        },
    }
    return make_result(inputs, 'FINANCIAL_REVISION_CANDIDATE', body, 'wave_b/financial.py')
