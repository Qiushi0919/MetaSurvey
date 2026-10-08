"""Append-only observed financial versions, without historical PIT inference."""
from .inputs import assert_dataset, diagnostic_header, date_only, value, row_ref, canonical_hash, require, number

METRICS = ('eps', 'roe', 'debt_to_assets', 'netprofit_yoy')

def analyze_financial(dataset):
    assert_dataset(dataset)
    result = diagnostic_header(dataset, 'FINANCIAL_OBSERVED_REVISION_DIAGNOSTIC')
    observations, groups, scopes = [], {}, []
    for request in dataset['requests']:
        if request['api_name'] != 'fina_indicator':
            continue
        scope = request.get('date_scope', {})
        require(scope.get('key') == 'end_date', 'FINANCIAL_PERIOD_SCOPE_REQUIRED')
        start, end = scope.get('start'), scope.get('end')
        date_only(start); date_only(end)
        require(start <= end, 'FINANCIAL_PERIOD_SCOPE_INVALID')
        out_of_scope = []
        for row in request['rows']:
            report_period = value(row, 'end_date'); date_only(report_period)
            announcement = value(row, 'ann_date')
            if announcement is not None:
                date_only(announcement)
            literal = value(row, 'f_ann_date')
            if literal is not None:
                date_only(literal)
            metrics = {}
            for field in METRICS:
                v = value(row, field)
                if v is not None:
                    number(v)
                metrics[field] = v
            outside = not start <= report_period <= end
            ref = row_ref(request, row)
            record = {'ts_code': request['ts_code'], 'report_period': report_period,
                      'ann_date': announcement, 'f_ann_date': literal, 'publication_precision': 'DATE_ONLY' if announcement else 'UNKNOWN',
                      'published_at': None, 'available_at': request['available_at'], 'retrieved_at': request['retrieved_at'],
                      'availability_basis': 'FIRST_OBSERVED_COMPLETE_RESPONSE_ONLY',
                      'update_flag': value(row, 'update_flag'), 'metrics': metrics,
                      'metric_units': {field: row['typed_fields'].get(field, {}).get('unit', 'UNSET_REQUIRED') for field in METRICS},
                      'observed_version_hash': canonical_hash(row['typed_fields']), 'metric_hash': canonical_hash(metrics),
                      'raw_row_ref': ref, 'request_stage': request['scope'], 'request_dq': request['response_dq'],
                      'period_within_requested_scope': not outside, 'state': 'QUARANTINED',
                      'historical_revision_visibility_proven': False,
                      'diagnostic_reasons': (['PERIOD_OUTSIDE_REQUEST'] if outside else []) +
                      ['SOURCE_ADMISSION_BLOCKED', 'DATE_ONLY_NOT_AN_INSTANT', 'REVISION_HISTORY_NOT_PROVEN']}
            observations.append(record)
            groups.setdefault((request['ts_code'], report_period), []).append(record)
            if outside:
                out_of_scope.append(ref)
        scopes.append({'request_fingerprint': request['request_fingerprint'], 'ts_code': request['ts_code'],
                       'stage': request['scope'], 'start': start, 'end': end, 'filter_semantics': 'REPORT_PERIOD_NOT_ANN_DATE',
                       'observed_rows': len(request['rows']), 'out_of_scope_refs': out_of_scope,
                       'response_remains_quarantined': True, 'response_dq_preserved': request['response_dq']})
    result['observations'] = observations
    result['requests'] = scopes
    result['revision_groups'] = [{'ts_code': symbol, 'report_period': period,
                                  'observation_count': len(rows), 'distinct_observed_versions': len({r['observed_version_hash'] for r in rows}),
                                  'distinct_metric_versions': len({r['metric_hash'] for r in rows}),
                                  'source_flags_observed': sorted({str(r['update_flag']) for r in rows}),
                                  'versions': [{'version_hash': r['observed_version_hash'], 'metric_hash': r['metric_hash'],
                                                'ann_date': r['ann_date'], 'f_ann_date': r['f_ann_date'], 'raw_row_ref': r['raw_row_ref']} for r in rows],
                                  'version_chronology_proven': False, 'older_versions_overwritten': False,
                                  'availability_inferred_from_flag_or_date': False} for (symbol, period), rows in sorted(groups.items())]
    result['scope_anomaly_resolution'] = 'CLASSIFIED_OFFLINE_NOT_PROVIDER_FILTER_REPAIRED'
    result['financial_statements_complete'] = False
    result['status'] = 'PARTIAL_PARSER_READY_ADMISSION_AND_HISTORICAL_REVISIONS_BLOCKED'
    return result
