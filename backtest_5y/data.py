"""Import all relevant indexed raw rows, retaining versions and current clocks."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
from .interface import SYMBOLS, digest, frozen_spec
from .sources import API_DOMAINS


def iso_day(value):
    from datetime import date
    if value in (None, ''):
        return None
    text = str(value)
    if len(text) == 8 and text.isdigit():
        text = text[:4] + '-' + text[4:6] + '-' + text[6:]
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _lexical(raw):
    return json.loads(raw, parse_float=str, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_RAW')))


def _identity(api, symbol, fields, ordinal):
    keys = {
        'daily': ('trade_date',), 'trade_cal': ('exchange', 'cal_date'),
        'adj_factor': ('trade_date',), 'daily_basic': ('trade_date',),
        'income': ('end_date', 'report_type', 'comp_type'),
        'balancesheet': ('end_date', 'report_type', 'comp_type'),
        'cashflow': ('end_date', 'report_type', 'comp_type'),
        'fina_indicator': ('end_date',), 'dividend': ('end_date', 'ex_date', 'div_proc'),
        'index_member_all': ('in_date', 'out_date', 'l3_code'),
        'stock_basic': ('ts_code',), 'sse_announcement': ('document_url',),
    }[api]
    values = [str(fields.get(k) or '') for k in keys]
    if not any(values):
        values = ['UNRECORDED_IDENTITY', str(ordinal)]
    return ':'.join((api, symbol, *values))


def _record(api, symbol, fields, ordinal, source, refs):
    source = {**source, 'row_ordinal': ordinal}
    fields = {k: None if v is None else str(v) for k, v in fields.items()}
    day = iso_day(next((fields.get(k) for k in ('trade_date', 'cal_date', 'end_date', 'ex_date', 'in_date', 'published_date') if fields.get(k)), None))
    return {'identity': _identity(api, symbol, fields, ordinal), 'event_date': day,
            'published_at': source.get('published_at'), 'available_at': None,
            'first_visible_at': None, 'revision_id': None, 'fields': fields,
            'units': {'state': 'SOURCE_DECLARED_NOT_INDEPENDENTLY_VERIFIED'},
            'provenance': {'actual_API': api, 'row_ordinal': ordinal,
                           'raw_sha256': source['raw_sha256'], 'raw_original_refs': refs,
                           'original_source_ref': source,
                           'current_available_at': source.get('available_at'),
                           'publication_date_fields': {k: fields[k] for k in ('ann_date', 'f_ann_date', 'published_date') if k in fields},
                           'publication_precision': 'DATE_ONLY_OR_UNRECORDED',
                           'source_version_semantics': 'CAPTURE_CONTENT_HASH_NOT_VENDOR_REVISION',
                           'historical_visibility_proven': False,
                           'revision_chain': 'NOT_PROVEN', 'quarantined': True,
                           'financial_period_semantics': 'SOURCE_REPORT_PERIOD_POSSIBLY_YTD_NOT_QUARTER' if api in ('income', 'cashflow', 'balancesheet', 'fina_indicator') else None}}


def batches_from_inputs(inputs, originals):
    """Bind observed rows, then import full relevant API responses, not just old3740."""
    by_hash = defaultdict(list)
    for r in originals:
        by_hash[r['sha256']].append(r)
    observations = defaultdict(list)
    for symbol in SYMBOLS:
        for key in ('wave-c_input', 'wave-d_input'):
            body = inputs[symbol].get(key, {}).get('body', {})
            for collection in ('observations', 'excluded'):
                for o in body.get(collection, []):
                    if o['api_name'] in API_DOMAINS:
                        observations[(symbol, o['api_name'], o['source_ref']['raw_sha256'])].append(
                            {**o, 'legacy_collection': collection})
    batches = []
    for (symbol, api, expected_hash), obs in sorted(observations.items()):
        candidates = by_hash[expected_hash]
        if not candidates:
            raise ValueError('INDEXED_RAW_ORIGINAL_MISSING')
        for rr in candidates:
            raw = Path(rr['path']).read_bytes()
            if 'sha256:' + digest(raw) != expected_hash or ('bytes' in rr and len(raw) != rr['bytes']):
                raise ValueError('INDEXED_RAW_HASH_CONFLICT_STOP')
            body = _lexical(raw)
            if api == 'sse_announcement':
                # The original index is metadata; normalized values cite it, not PDF bodies.
                rows = body.get('result') or body.get('pageHelp', {}).get('data', [])
                if not isinstance(rows, list):
                    raise ValueError('INDEXED_ANNOUNCEMENT_SHAPE')
                source = obs[0]['source_ref']
                records = []
                for o in obs:
                    idx = o['source_ref']['row_ordinal']
                    if not 0 <= idx < len(rows):
                        raise ValueError('INDEXED_RAW_ROW_ORDINAL')
                    item = rows[idx]
                    values = o.get('values', {})
                    if not values:
                        raise ValueError('INDEXED_ANNOUNCEMENT_EXCLUDED_UNNORMALIZED')
                    if str(item.get('TITLE')) != str(values.get('title')) or str(item.get('SECURITY_CODE')) != symbol[:6]:
                        raise ValueError('INDEXED_ANNOUNCEMENT_ROW_CONFLICT')
                    rec = _record(api, symbol, values, idx, o['source_ref'], candidates)
                    rec['provenance']['body_status'] = 'INDEX_METADATA_ONLY_NOT_ISSUER_BODY'
                    records.append(rec)
            else:
                data = body.get('data', {})
                if not isinstance(data, dict) or not isinstance(data.get('items'), list) or not isinstance(data.get('fields'), list):
                    raise ValueError('INDEXED_RAW_RESPONSE_SHAPE')
                if len(set(data['fields'])) != len(data['fields']) or any(
                        not isinstance(row, list) or len(row) != len(data['fields']) for row in data['items']):
                    raise ValueError('INDEXED_RAW_FIELD_ROW_BINDING_SHAPE')
                rows = [dict(zip(data['fields'], row)) for row in data['items']]
                for o in obs:
                    idx = o['source_ref']['row_ordinal']
                    if not 0 <= idx < len(rows):
                        raise ValueError('INDEXED_RAW_ROW_ORDINAL')
                    if any((None if rows[idx].get(k) is None else str(rows[idx][k])) !=
                           (None if v is None else str(v)) for k, v in o.get('values', {}).items()):
                        raise ValueError('INDEXED_RAW_ROW_CONFLICT_STOP')
                filename = Path(rr['path']).name.removesuffix('.response.json')
                matching = [o for o in obs if o['source_ref']['request_id'] == filename]
                source = (matching or obs)[0]['source_ref']
                records = []
                for idx, row in enumerate(rows):
                    if api != 'trade_cal' and str(row.get('ts_code')) != symbol:
                        continue
                    if api == 'trade_cal' and str(row.get('exchange')) != 'SSE':
                        continue
                    record = _record(api, symbol, row, idx, source, candidates)
                    exclusions = sorted({o['reason_code'] for o in obs
                                         if o['source_ref']['row_ordinal'] == idx and o.get('reason_code')})
                    record['provenance']['legacy_exclusion_reasons'] = exclusions
                    record['provenance']['legacy_exclusion_preserved'] = bool(exclusions)
                    record['provenance']['capture_import_state'] = 'CAPTURE_ONLY_RETAIN_LEGACY_BLOCKS'
                    records.append(record)
            batches.append({'source': 'EXISTING_INDEXED_QUARANTINED', 'domain': API_DOMAINS[api],
                            'symbol': symbol, 'request': {'api_name': api, 'raw_path': rr['path'],
                            'original_request_ids': sorted({o['source_ref']['request_id'] for o in obs}),
                            'request_fingerprints': sorted({o['source_ref']['request_fingerprint'] for o in obs}),
                            'clock_binding': 'MATCHED_REQUEST_ID' if api != 'sse_announcement' and matching else 'INDEXED_CONTENT_ALIAS_CAPTURE_CLOCK_NOT_HISTORICAL',
                            'retained_versions': True, 'all_raw_response_fields_imported': True,
                            'legacy_exclusion_reasons': sorted({o['reason_code'] for o in obs if o.get('reason_code')})},
                            'retrieved_at': source['retrieved_at'], 'raw_bytes': raw,
                            'source_url': 'https://www.sse.com.cn/' if api == 'sse_announcement' else 'http://118.89.117.77:8030/',
                            'records': records, 'license_state': 'EXISTING_QUARANTINED_PROVIDER_LICENSE_UNVERIFIED'})
    return batches


def read_existing():
    frozen_spec()
    from wave_g.diagnostic import _read_inputs
    inputs, refs = _read_inputs()
    return batches_from_inputs(inputs, refs)
