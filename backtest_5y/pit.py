"""Read-only price evidence verification; current retrieval is never past visibility.

The trust boundary is an independently reviewed, code-pinned manifest, not a
boolean supplied by a collector. There are deliberately no approved manifests
in this first epoch. The same structural checks can be exercised with explicitly
synthetic evidence, whose successful result cannot admit actual data.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlparse

from .interface import canonical, digest, frozen_spec
from .clocks import exact_clock, source_day

# Populating this registry requires a later independent evidence review. A raw
# capture digest proves byte integrity, not historical publication or authority.
APPROVED_HISTORICAL_MANIFESTS: dict[str, str] = {}
MODES = ('observed_at_time', 'historical_reconstruction', 'synthetic_fixture')
OFFICIAL_HOSTS = ('sse.com.cn', 'szse.cn', 'cninfo.com.cn')


def event_day(value):
    return source_day(value)


def _sha(value):
    return str(value).removeprefix('sha256:')


def _official(url):
    parsed = urlparse(url or '')
    return parsed.scheme == 'https' and any(parsed.hostname == h or
        (parsed.hostname or '').endswith('.'+h) for h in OFFICIAL_HOSTS)


def _raw_rows(raw):
    def unique_keys(pairs):
        result = {}
        for k,v in pairs:
            if k in result: raise ValueError('RAW_DUPLICATE_JSON_KEY')
            result[k] = v
        return result
    def nonfinite(_):
        raise ValueError('RAW_NONFINITE_JSON_NUMBER')
    body = json.loads(raw, parse_float=str, parse_constant=nonfinite, object_pairs_hook=unique_keys)
    if isinstance(body, list):
        return body
    if isinstance(body, dict) and isinstance(body.get('rows'), list):
        return body['rows']
    data = body.get('data', {}) if isinstance(body, dict) else {}
    if isinstance(data, dict) and isinstance(data.get('fields'), list) and isinstance(data.get('items'), list):
        return [dict(zip(data['fields'], item, strict=True)) for item in data['items']]
    raise ValueError('UNSUPPORTED_RAW_ROW_FORMAT')


def _field_shape(fields):
    return {k: None if v is None else str(v) for k,v in fields.items()}


def load_approved_evidence(path):
    """No caller-supplied digest/issuer flag can enroll a historical manifest."""
    path = str(Path(path).resolve())
    expected = APPROVED_HISTORICAL_MANIFESTS.get(path)
    if expected is None:
        raise ValueError('HISTORICAL_MANIFEST_NOT_IN_INDEPENDENT_REVIEW_PINS')
    raw = Path(path).read_bytes()
    if digest(raw) != _sha(expected):
        raise ValueError('HISTORICAL_MANIFEST_HASH_CONFLICT')
    manifest = json.loads(raw)
    documents = {}
    for ref in manifest.get('raw_documents', []):
        original = Path(ref['path']).read_bytes()
        if digest(original) != _sha(ref['sha256']):
            raise ValueError('RAW_DOCUMENT_HASH_CONFLICT')
        documents[digest(original)] = original
    return manifest, documents


def verify_price_admission(records, *, cutoff, evidence=None, mode='observed_at_time'):
    """Validate independent historical proofs AND every price/window dependency.

    Actual evidence is a path to an already independently reviewed manifest.
    A fixture may supply {manifest, raw_documents}, only in synthetic_fixture
    mode. No mode runs an engine or licenses the full frozen strategy.
    """
    frozen_spec()
    reasons = []
    result = dict(state='BLOCKED', mode=mode, admitted=False,
        historical_visibility_proven=False, engine_called=False,
        full_strategy_admitted=False, productionGate=False, checked_records=0,
        classification='PRICE_PREREQUISITE_VERIFICATION_ONLY', reason_codes=reasons)
    if mode not in MODES:
        reasons.append('UNSUPPORTED_PIT_MODE'); return result
    try:
        decision = exact_clock(cutoff)
    except (ValueError, TypeError):
        reasons.append('DECISION_EXACT_CLOCK_REQUIRED'); return result
    if mode == 'historical_reconstruction':
        result['state'] = 'RECONSTRUCTION_ONLY'
        reasons.append('RETRIEVAL_AND_EVENT_DATE_DO_NOT_PROVE_HISTORICAL_AVAILABILITY')
        return result
    fixture = mode == 'synthetic_fixture'
    try:
        if fixture:
            if not isinstance(evidence, dict) or evidence.get('manifest', {}).get('classification') != 'SYNTHETIC_FIXTURE':
                raise ValueError('EXPLICIT_SYNTHETIC_EVIDENCE_REQUIRED')
            manifest, documents = evidence['manifest'], evidence['raw_documents']
        else:
            if not isinstance(evidence, (str, Path)):
                raise ValueError('INDEPENDENT_HISTORICAL_MANIFEST_REQUIRED')
            manifest, documents = load_approved_evidence(evidence)
            if manifest.get('classification') != 'INDEPENDENTLY_REVIEWED_OFFICIAL_HISTORICAL_EVIDENCE':
                raise ValueError('MANIFEST_AUTHORITY_CLASS_INVALID')
    except (ValueError, OSError, KeyError, TypeError) as exc:
        reasons.append(str(exc)); return result
    proof_rows = manifest.get('proofs', [])
    proofs = {p.get('record_key'): p for p in proof_rows}
    if len(proofs) != len(proof_rows):
        reasons.append('INDEPENDENT_MANIFEST_PROOF_VERSION_CONFLICT')
    seen = set()
    selected = []
    # Filter an event prefix before looking at payloads or numeric future data.
    for record in records:
        try:
            day = event_day(record.get('event_date'))
        except (ValueError, TypeError):
            reasons.append('INVALID_EVENT_DATE'); continue
        if day > cutoff[:10]:
            continue
        key = record.get('record_hash') or digest(canonical(record))
        if key in seen:
            reasons.append('DUPLICATE_RECORD_VERSION'); continue
        seen.add(key); selected.append(record)
        proof = proofs.get(key)
        if not proof:
            reasons.append('INDEPENDENT_RECORD_PROOF_MISSING'); continue
        try:
            if not _official(proof.get('source_url')):
                raise ValueError('OFFICIAL_HISTORICAL_PUBLICATION_REQUIRED')
            if proof.get('evidence_kind') != 'OFFICIAL_ARCHIVED_PUBLICATION_WITH_VERSION':
                raise ValueError('INDEPENDENT_HISTORICAL_VERSION_PROOF_REQUIRED')
            if not record.get('revision_id') or record['revision_id'] != proof.get('revision_id'):
                raise ValueError('SOURCE_VERSION_BINDING_REQUIRED')
            published, available, visible = (exact_clock(record.get(k)) for k in
                ('published_at', 'available_at', 'first_visible_at'))
            retrieved = exact_clock(record.get('retrieved_at'))
            if not published <= available <= visible <= decision:
                raise ValueError('HISTORICAL_CLOCK_ORDER_OR_CUTOFF_CONFLICT')
            if retrieved < visible:
                raise ValueError('RETRIEVAL_PRECEDES_VISIBILITY')
            if any(record.get(k) != proof.get(k) for k in
                   ('published_at', 'available_at', 'first_visible_at')):
                raise ValueError('INDEPENDENT_PUBLICATION_CLOCK_BINDING_CONFLICT')
            if proof.get('availability_basis') == 'CURRENT_RETRIEVAL':
                raise ValueError('CURRENT_RETRIEVAL_IS_NOT_HISTORICAL_VISIBILITY')
            if proof.get('availability_basis') != 'INDEPENDENT_HISTORICAL_PUBLICATION_ARCHIVE':
                raise ValueError('HISTORICAL_AVAILABILITY_BASIS_REQUIRED')
            if record.get('license_state') != 'VERIFIED_FOR_LOCAL_HISTORICAL_RESEARCH':
                raise ValueError('HISTORICAL_RESEARCH_LICENSE_NOT_VERIFIED')
            rawsha = _sha(record.get('raw_sha256'))
            raw = documents.get(rawsha)
            if not isinstance(raw, bytes) or digest(raw) != rawsha or rawsha != _sha(proof.get('raw_sha256')):
                raise ValueError('RAW_BYTES_BINDING_REQUIRED')
            ordinal = record.get('row_ordinal')
            if type(ordinal) is not int or ordinal < 0 or ordinal != proof.get('row_ordinal'):
                raise ValueError('RAW_ROW_ORDINAL_BINDING_REQUIRED')
            rawrow = _raw_rows(raw)[ordinal]
            # Entire original field dictionary is bound, not just a caller hash.
            if canonical(_field_shape(rawrow)) != canonical(_field_shape(record.get('fields', {}))):
                raise ValueError('RAW_ROW_FIELDS_BINDING_CONFLICT')
            if proof.get('domain') != record.get('domain') or proof.get('symbol') != record.get('symbol') or proof.get('identity') != record.get('identity'):
                raise ValueError('INDEPENDENT_RECORD_IDENTITY_BINDING_CONFLICT')
            if not record.get('units') or canonical(record['units']) != canonical(proof.get('units')):
                raise ValueError('INDEPENDENT_UNITS_BINDING_REQUIRED')
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            reasons.append(str(exc))
    result['checked_records'] = len(selected)
    prices = [r for r in selected if r.get('domain') == 'PRICE']
    calendar = [r for r in selected if r.get('domain') == 'CALENDAR']
    statuses = [r for r in selected if r.get('domain') == 'STATUS']
    actions = [r for r in selected if r.get('domain') == 'ACTION']
    if not prices:
        reasons.append('PRICE_RECORDS_REQUIRED')
    prices_by_identity = {}
    for r in prices:
        f = r.get('fields', {})
        try:
            values = [Decimal(str(f[k])) for k in ('open','high','low','close','vol')]
            op, high, low, close, vol = values
            if not all(v.is_finite() and len(v.as_tuple().digits) <= 50 and v.adjusted() < 50 for v in values) or min(op,high,low,close) <= 0 or vol < 0 or not low <= min(op,close) <= max(op,close) <= high:
                raise ValueError('PRICE_NUMERIC_OR_OHLC_CONFLICT')
            if event_day(f.get('trade_date')) != event_day(r['event_date']):
                raise ValueError('PRICE_EVENT_DATE_RAW_BINDING_CONFLICT')
            if exact_clock(r.get('published_at')) < exact_clock(event_day(r['event_date'])+'T15:00:00+08:00'):
                raise ValueError('PRICE_PUBLICATION_PRECEDES_EOD_BAR')
            if r.get('units', {}).get('price') != 'CNY_PER_SHARE' or r.get('units', {}).get('volume') != 'SHARES':
                raise ValueError('PRICE_AND_VOLUME_VERIFIED_UNIT_REQUIRED')
            key = (r.get('symbol'),event_day(r['event_date']))
            if key in prices_by_identity and prices_by_identity[key] != values:
                raise ValueError('PRICE_VISIBLE_VERSION_CONFLICT')
            prices_by_identity[key] = values
        except (ValueError, InvalidOperation, TypeError, KeyError) as exc:
            reasons.append(str(exc))
    for symbol in sorted({r.get('symbol') for r in prices}, key=str):
        ps = [r for r in prices if r.get('symbol') == symbol]
        dates = sorted({event_day(r['event_date']) for r in ps})
        if len(dates) < 80:
            reasons.append('PRICE_FULL_PULLBACK_WINDOW_REQUIRES80_ACTUAL_SESSIONS')
        c = {}
        for r in calendar:
            f = r.get('fields', {})
            if f.get('exchange') != 'SSE' or str(f.get('is_open')) not in ('0', '1'):
                reasons.append('CALENDAR_LITERAL_CONFLICT'); continue
            d = event_day(r['event_date'])
            if d in c and c[d] != str(f['is_open']): reasons.append('CALENDAR_VERSION_CONFLICT')
            c[d] = str(f['is_open'])
        if dates:
            cursor, end = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
            while cursor <= end:
                day = cursor.isoformat()
                if day not in c: reasons.append('OFFICIAL_CIVIL_CALENDAR_COVERAGE_MISSING')
                elif (c[day] == '1') != (day in dates): reasons.append('ACTUAL_OPEN_SESSION_BAR_COVERAGE_CONFLICT')
                cursor += timedelta(days=1)
        for d in dates:
            matching = [r for r in statuses if r.get('symbol') == symbol and
                r.get('fields', {}).get('effective_from', '9999') <= d <=
                r.get('fields', {}).get('effective_to', '0000')]
            if len(matching) != 1:
                reasons.append('OFFICIAL_HISTORICAL_STATUS_INTERVAL_MISSING_OR_CONFLICTING'); continue
            f = matching[0]['fields']
            if any(type(f.get(k)) is not bool for k in ('tradeable', 'st', 'halted')) or not f['tradeable'] or f['halted']:
                reasons.append('HISTORICAL_STATUS_UNKNOWN_OR_UNTRADEABLE')
            try:
                lot = int(f.get('lot_size'))
            except (TypeError, ValueError):
                lot = 0
            if not all(type(f.get(k)) is str and f[k] for k in ('board', 'limit_rule_version')) or lot < 1:
                reasons.append('HISTORICAL_STATUS_RULE_FIELDS_MISSING')
        matching = [r for r in actions if r.get('symbol') == symbol and dates and
            r.get('fields', {}).get('coverage_start', '9999') <= dates[0] and
            r.get('fields', {}).get('coverage_end', '0000') >= dates[-1]]
        if len(matching) != 1 or matching[0]['fields'].get('action_inventory') != 'COMPLETE' or matching[0]['fields'].get('price_basis') != 'RAW_COMPARABLE_ACTION_RECONCILED':
            reasons.append('OFFICIAL_COMPLETE_ACTION_RECONCILIATION_REQUIRED')
        elif dates:
            try:
                if exact_clock(matching[0].get('available_at')) < exact_clock(dates[-1]+'T15:00:00+08:00'):
                    reasons.append('ACTION_COMPLETE_HISTORY_PRECEDES_COVERAGE_END')
            except (ValueError, TypeError):
                reasons.append('ACTION_COMPLETE_HISTORY_EXACT_CLOCK_REQUIRED')
    reasons[:] = sorted(set(reasons))
    if not reasons:
        result['state'] = 'FIXTURE_PRICE_VERIFIED' if fixture else 'PRICE_PREREQUISITES_VERIFIED'
        result['admitted'] = not fixture
        result['historical_visibility_proven'] = not fixture
        result['classification'] = 'SYNTHETIC_FIXTURE' if fixture else 'PRICE_ONLY_NOT_FULL_STRATEGY'
    return result
