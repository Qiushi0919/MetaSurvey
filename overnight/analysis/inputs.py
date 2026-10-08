"""Read-only diagnostic guards, with no source/admission authority."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from zoneinfo import ZoneInfo
import hashlib
import json
import re

SYMBOLS = ('603993.SH', '600312.SH', '603228.SH')
APIS = ('stock_basic', 'suspend_d', 'trade_cal', 'daily', 'adj_factor', 'dividend', 'fina_indicator', 'index_member_all')

class AnalysisError(ValueError):
    pass

def require(ok, reason):
    if not ok:
        raise AnalysisError(reason)

def canonical_hash(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def date_only(value):
    require(type(value) is str and re.fullmatch(r'\d{8}', value), 'DATE_ONLY_LITERAL_REQUIRED')
    try:
        result = datetime.strptime(value, '%Y%m%d').date()
    except ValueError:
        raise AnalysisError('DATE_ONLY_LITERAL_INVALID') from None
    require(result.strftime('%Y%m%d') == value, 'DATE_ONLY_LITERAL_INVALID')
    return result

def instant(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|[+-]\d\d:\d\d)', value), 'CLOCK_INSTANT_REQUIRED')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise AnalysisError('CLOCK_INSTANT_INVALID') from None

def instant_ns(value):
    parsed = instant(value).replace(microsecond=0).astimezone(timezone.utc)
    delta = parsed - datetime(1970, 1, 1, tzinfo=timezone.utc)
    fraction = re.search(r'\.(\d{1,9})', value)
    ns = int(fraction.group(1).ljust(9, '0')) if fraction else 0
    return (delta.days * 86400 + delta.seconds) * 1000000000 + ns

def number(value):
    require(type(value) is str and len(value) <= 160, 'DECIMAL_STRING_REQUIRED')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise AnalysisError('DECIMAL_LITERAL_INVALID') from None
    require(result.is_finite() and abs(result.as_tuple().exponent) <= 64 and len(result.as_tuple().digits) <= 100, 'DECIMAL_LITERAL_INVALID')
    return result

def value(row, field):
    obj = row.get('typed_fields', {}).get(field)
    return obj.get('value') if type(obj) is dict else None

def row_ref(request, row):
    return {'request_fingerprint': request['request_fingerprint'], 'raw_sha256': request['raw_sha256'],
            'report_sha256': request['report_sha256'], 'row_ordinal': row['row_ordinal']}

def rational(value):
    result = Fraction(value)
    return {'numerator': str(result.numerator), 'denominator': str(result.denominator)}

def assert_dataset(dataset):
    require(type(dataset) is dict and dataset.get('namespace') == 'CORE_40', 'STRATEGY_NAMESPACE_INVALID')
    require(dataset.get('state') == 'QUARANTINED' and dataset.get('source_admission') == 'BLOCKED' and
            dataset.get('historical_visibility_proven') is False and type(dataset.get('fixture')) is bool, 'QUARANTINE_STATE_INVALID')
    requests = dataset.get('requests')
    require(type(requests) is list and 1 <= len(requests) <= 44, 'REQUEST_INVENTORY_INVALID')
    require(dataset['fixture'] or len(requests) == 44, 'REAL_CAPTURE_INVENTORY_INVALID')
    if not dataset['fixture']:
        # Exact in-process registration binds these bytes to the closed G2 loader.
        # A 44-request copy or caller-resealed sidecar is not a verified source.
        from ..data.dataset import validate_dataset, DataError
        try:
            validate_dataset(dataset)
        except DataError:
            raise AnalysisError('REAL_DATASET_UNREGISTERED_OR_MUTATED') from None
    else:
        require(dataset.get('provenance') == 'SYNTHETIC' and dataset.get('productionGate') is False,
                'FIXTURE_AUTHORITY_INVALID')
    seen = set()
    selected_pairs = set()
    for request in requests:
        require(request.get('api_name') in APIS and request.get('scope') in ('SMOKE', 'COVERAGE'), 'REQUEST_SCOPE_INVALID')
        require(request.get('request_fingerprint') not in seen, 'DUPLICATE_REQUEST_INVALID')
        seen.add(request['request_fingerprint'])
        pair = (request['scope'], request['api_name'], request.get('ts_code'))
        require(pair not in selected_pairs, 'DUPLICATE_API_SYMBOL_SCOPE')
        selected_pairs.add(pair)
        require(request.get('ts_code') in (None, *SYMBOLS), 'SYMBOL_CROSSOVER')
        started = instant_ns(request.get('request_started_at'))
        completed = instant(request.get('response_completed_at'))
        require(started <= instant_ns(request['response_completed_at']) and request.get('available_at') == request['response_completed_at'] and
                request.get('retrieved_at') == request['response_completed_at'] and request.get('published_at') is None, 'CAPTURE_CLOCK_SPOOF')
        observed_day = completed.astimezone(ZoneInfo('Asia/Shanghai')).date()
        if request['api_name'] == 'daily':
            require(request.get('price_adjustment') == 'RAW_UNADJUSTED_OHLC_PROVIDER_PRE_CLOSE_EX_RIGHTS', 'RAW_ADJUSTED_CONTAMINATION')
        if request['api_name'] == 'adj_factor':
            require(request.get('price_adjustment') == 'FACTOR_ONLY_NO_ADJUSTED_PRICES', 'RAW_ADJUSTED_CONTAMINATION')
        for row in request.get('rows', []):
            require(row.get('state') == 'QUARANTINED', 'ROW_ADMISSION_PROMOTION')
            symbol = value(row, 'ts_code')
            require(symbol is None or symbol in SYMBOLS, 'SYMBOL_CROSSOVER')
            require(request.get('ts_code') is None or symbol == request['ts_code'], 'SYMBOL_CROSSOVER')
            for field in ('ann_date', 'f_ann_date', 'imp_ann_date'):
                literal = value(row, field)
                if literal not in (None, ''):
                    require(date_only(literal) <= observed_day, 'FUTURE_PUBLICATION')
    return dataset

def diagnostic_header(dataset, kind):
    return {'version': '1.0.0-diagnostic', 'kind': kind, 'fixture': dataset['fixture'],
            'namespace': 'CORE_40', 'state': 'QUARANTINED', 'source_admission': 'BLOCKED',
            'historical_visibility_proven': False, 'admitted_policy_count': 0,
            'productionGate': False, 'input_content_hash': canonical_hash(dataset),
            'consumer_authority': 'READONLY_DIAGNOSTIC_INPUT_NOT_AN_ADMISSION_OR_CARD'}
