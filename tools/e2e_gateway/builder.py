"""Local read-only compatible-gateway adapter; never grants verified provider/PIT status.

Original response bytes, table wrappers, request receipts and the Owner's bounded
source policy are verified before building an unchanged V2 strategy case.
"""
from pathlib import Path
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from experiments.e2e_history_v2.engine import RULES, digest
ROOT = Path(__file__).resolve().parents[2]
SOURCE_POLICY = ROOT / 'docs/e2e-gateway-v3/Source-Policy.json'
INPUT_POLICY = ROOT / 'experiments/e2e_gateway_v3/input-policy.json'
OWNER = ROOT / 'docs/e2e-gateway-v3/Owner-Authorization.md'
CONNECTION = ROOT / 'config/provider/tushare-monthly-gateway.json'
PROTOCOL = ROOT / 'experiments/e2e_history_v2/protocol.json'
METHOD = ROOT / 'experiments/e2e_pilot_v1/method.json'
D = Decimal
PERMISSION = 'OWNER_AUTHORIZED_LOCAL_RECONSTRUCTED_UNVERIFIED_PROVIDER'

REQUIRED_FIELDS = {
    'trade_cal': {'exchange','cal_date','is_open'},
    'stock_basic': {'ts_code','exchange','market','list_status','list_date','delist_date'},
    'daily': {'ts_code','trade_date','open','high','low','close','pre_close','vol','amount'},
    'stk_limit': {'ts_code','trade_date','pre_close','up_limit','down_limit'},
    'suspend_d': {'ts_code','trade_date','suspend_timing','suspend_type'},
    'adj_factor': {'ts_code','trade_date','adj_factor'},
    'dividend': {'ts_code','end_date','ann_date','imp_ann_date','div_proc','ex_date','record_date','pay_date','div_listdate','cash_div_tax','stk_div','stk_bo_rate','stk_co_rate'},
    'namechange': {'ts_code','name','start_date','end_date','ann_date','change_reason'},
}
NAMECHANGE_LOCAL_ROW_CAP = 1000  # engineering bound, not a claimed supplier API limit

class InputError(ValueError): pass

def rawhash(path): return 'sha256:' + sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())
def dec(value):
    if type(value) not in (str, int): raise InputError('EXACT_DECIMAL_REQUIRED')
    result = D(value)
    if not result.is_finite(): raise InputError('FINITE_DECIMAL_REQUIRED')
    return result

def day(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{8}', value): raise InputError('YYYYMMDD_REQUIRED')
    return date.fromisoformat(value[:4] + '-' + value[4:6] + '-' + value[6:]).isoformat()

def clock(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None: raise InputError('TIMEZONE_REQUIRED')
    return parsed

def safe_child(folder, name):
    if not isinstance(name, str) or Path(name).name != name: raise InputError('FLAT_CAPTURE_PATH_REQUIRED')
    path = folder / name
    if path.is_symlink() or not path.is_file() or path.resolve().parent != folder.resolve(): raise InputError('CAPTURE_ALIAS_OR_MISSING')
    return path

def source_authority():
    policy = read(SOURCE_POLICY)
    cfg = read(CONNECTION)
    if (policy.get('purpose') != 'LOCAL_HISTORICAL_DIAGNOSTIC'
        or policy.get('permission_state') != PERMISSION
        or policy.get('source_classification') != 'OWNER_PROVIDED_MONTHLY_GATEWAY'
        or policy.get('endpoint') != cfg['endpoint']
        or cfg['source_classification'] != 'OWNER_PROVIDED_MONTHLY_GATEWAY'
        or policy.get('owner_authorization_ref') != rawhash(OWNER)
        or policy.get('connection_config_hash') != rawhash(CONNECTION)
        or policy.get('supplier_identity_verified') is not False
        or policy.get('license_verified') is not False
        or policy.get('kind') != 'GatewayLocalResearchPolicy' or policy.get('version') != '3.0.0'
        or any(policy.get(k) is not False for k in ('historical_visibility_proven', 'public_raw_distribution', 'cloud_transfer'))):
        raise InputError('OWNER_SOURCE_POLICY_SCOPE_MISMATCH')
    return {'purpose': policy['purpose'], 'permission_state': PERMISSION,
            'endpoint': policy['endpoint'], 'owner_authorization_ref': policy['owner_authorization_ref'],
            'policy_hash': rawhash(SOURCE_POLICY), 'provider_license_independently_verified': False,
            'historical_visibility_proven': False}

def empty_suspend_schema_not_returned(obj):
    """Only after independent original/raw/receipt checks in indexed_capture.

    This identifies transport compatibility, not absence of intraday halts.
    """
    return (obj.get('api_name') == 'suspend_d'
            and type(obj.get('http_status')) is int and obj['http_status'] == 200
            and type(obj.get('error_code')) is int and obj['error_code'] == 0
            and obj.get('state') == 'EMPTY_RESPONSE'
            and obj.get('request_fields') == 'ts_code,trade_date,suspend_timing,suspend_type'
            and obj.get('fields') == [] and obj.get('items') == []
            and type(obj.get('row_count')) is int and obj['row_count'] == 0)

def indexed_capture(folder, authority, symbols, start, end, report=None, _seen=None, _inherited=False):
    seen = set() if _seen is None else set(_seen)
    manifest_path = safe_child(folder, 'Manifest.json')
    if manifest_path.resolve() in seen or len(seen) >= 8: raise InputError('PREDECESSOR_CYCLE_OR_DEPTH')
    seen.add(manifest_path.resolve())
    manifest = read(manifest_path)
    if (manifest.get('kind') != 'GatewayCaptureManifest' or manifest.get('version') != '1.0.0'
        or manifest.get('state') not in ('CAPTURE_COMPLETE', 'CAPTURE_PARTIAL')
        or manifest.get('scope') != {'symbols': symbols, 'start_date': start, 'end_date': end}
        or manifest.get('endpoint') != authority['endpoint']
        or manifest.get('owner_authorization_ref') != authority['owner_authorization_ref']
        or manifest.get('provider_license_status') != 'OWNER_AUTHORIZED_LOCAL_USE_UNVERIFIED_PROVIDER_LICENSE'
        or any(manifest.get(k) is not False for k in ('historical_visibility_proven', 'public_raw_distribution', 'cloud_transfer'))):
        raise InputError('CAPTURE_SCOPE_OR_AUTHORIZATION_MISMATCH')
    begin, finish = clock(manifest['started_at']), clock(manifest['retrieved_at'])
    if finish < begin: raise InputError('CAPTURE_CLOCK_INVALID')
    index, pins, paths, successful_receipts, failures = {}, {str(manifest_path): rawhash(manifest_path)}, set(), set(), []
    inherited_receipts = set()
    predecessor = manifest.get('predecessor')
    if predecessor is not None:
        prior = Path(predecessor['path'])
        if (prior.name != 'Manifest.json' or prior.parent.parent.resolve() != folder.parent.resolve()
            or not re.fullmatch(r'capture-[A-Za-z0-9][A-Za-z0-9._-]*', prior.parent.name)
            or prior.parent.is_symlink() or prior.is_symlink() or not prior.is_file()
            or rawhash(prior) != predecessor['sha256']): raise InputError('PREDECESSOR_PATH_OR_HASH_INVALID')
        _, prior_pins, inherited_receipts = indexed_capture(prior.parent, authority, symbols, start, end, _seen=seen, _inherited=True)
        pins.update(prior_pins)
    if report is not None: report['raw_pins'] = pins
    for entry in manifest['sources']:
        path = safe_child(folder, entry['path'])
        if path.name in paths: raise InputError('DUPLICATE_CAPTURE_PATH')
        paths.add(path.name)
        if rawhash(path) != entry['sha256']: raise InputError('WRAPPER_PIN_MISMATCH')
        pins[str(path)] = rawhash(path)
        obj = read(path)
        for field in ('api_name', 'params', 'fields', 'row_count', 'error_code', 'state'):
            if entry.get(field) != obj.get(field): raise InputError('MANIFEST_WRAPPER_MISMATCH:' + field)
        started, retrieved = clock(obj['request_started_at']), clock(obj['retrieved_at'])
        if not started <= retrieved <= finish: raise InputError('CAPTURE_CLOCK_INVALID')
        if started < begin and (path.name, entry['sha256']) not in inherited_receipts: raise InputError('UNPROVEN_INHERITED_CAPTURE_CLOCK')
        params = obj['params']
        if not isinstance(params, dict) or set(params) - {'ts_code', 'exchange', 'start_date', 'end_date'}: raise InputError('REQUEST_SCOPE_FIELDS_INVALID')
        key = (obj['api_name'], params.get('ts_code') or params.get('exchange'))
        if key in index: raise InputError('DUPLICATE_PRODUCT_REQUEST')
        # Retain failed product receipt without pretending it supplied a table.
        success = type(obj.get('error_code')) is int and obj.get('error_code') == 0 and obj.get('state') in ('SUCCESS', 'EMPTY_RESPONSE') and obj.get('http_status') == 200
        rawpath = None
        if obj.get('raw_path') is not None:
            rawpath = safe_child(folder, obj['raw_path'])
            if rawpath.name in paths: raise InputError('DUPLICATE_RAW_PATH')
            paths.add(rawpath.name)
            if rawhash(rawpath) != obj['raw_sha256']: raise InputError('RAW_PIN_MISMATCH')
            pins[str(rawpath)] = rawhash(rawpath)
            raw = json.loads(rawpath.read_bytes(), parse_float=str)
            if type(raw.get('code')) is not type(obj['error_code']) or raw.get('code') != obj['error_code']: raise InputError('ORIGINAL_ERROR_CODE_MISMATCH')
            if success and raw.get('data') != {'fields': obj['fields'], 'items': obj['items']}: raise InputError('ORIGINAL_WRAPPER_CONTENT_MISMATCH')
        elif success: raise InputError('SUCCESS_WITHOUT_ORIGINAL')
        fields, items = obj['fields'], obj['items']
        if (len(set(fields)) != len(fields) or obj['row_count'] != len(items)
            or any(not isinstance(row, list) or len(row) != len(fields) for row in items)
            or (success and obj['state'] != ('SUCCESS' if items else 'EMPTY_RESPONSE'))): raise InputError('RESPONSE_TABLE_INVALID')
        if report is not None:
            report['field_coverage'][key[0]+':'+str(key[1])] = {'rows':len(items), 'state':obj['state'], 'raw_sha256':obj.get('raw_sha256'), 'source_ref':path.name}
            if success and key[0] == 'daily': report['captured_daily_rows'] = report.get('captured_daily_rows', 0) + len(items)
        schema_missing = REQUIRED_FIELDS.get(obj['api_name'], set()) - set(fields)
        empty_suspension = success and empty_suspend_schema_not_returned(obj)
        if not success or (schema_missing and not empty_suspension):
            failures.append(('REQUIRED_RESPONSE_FIELDS_MISSING:' + obj['api_name'] + ':' + ','.join(sorted(schema_missing))) if success else ('API_PRODUCT_FAILED:' + str(obj.get('api_name')) + ':' + str(obj.get('state'))))
            index[key] = None
            continue
        if empty_suspension and report is not None:
            report['field_coverage'][key[0]+':'+str(key[1])].update(schema_status='EMPTY_TABLE_SCHEMA_NOT_RETURNED',schema_verified=False,intraday_halt_absence_proven=False)
        successful_receipts.add((path.name,entry['sha256']))
        index[key] = (obj, [dict(zip(fields, item)) for item in items], str(rawpath), obj['raw_sha256'])
    expected = {('trade_cal', e) for e in ('SSE', 'SZSE')} | {(api, symbol) for symbol in symbols for api in ('stock_basic', 'daily', 'stk_limit', 'suspend_d', 'adj_factor', 'dividend', 'namechange')}
    if set(index)-expected: raise InputError('UNEXPECTED_PRODUCT_CAPTURE')
    missing = expected-set(index)
    if report is not None:
        report['missing_products'] = [api+':'+sym for api,sym in sorted(missing)]
        report['failed_products'] = failures
        report['real_input_rows'] = report.get('captured_daily_rows',0)
        report['normalized_execution_rows'] = 0
    if not _inherited:
        if failures: raise InputError('; '.join(failures))
        if missing or manifest['state'] != 'CAPTURE_COMPLETE': raise InputError('EXACT_PRODUCT_CAPTURE_SET_REQUIRED:' + ','.join(api+':'+sym for api,sym in sorted(missing)))
    return index, pins, successful_receipts

def date_index(rows, field, symbol=None):
    result = {}
    for row in rows:
        if symbol and row.get('ts_code') != symbol: raise InputError('ROW_SECURITY_IDENTITY_CONFLICT')
        key = day(row[field])
        if key in result: raise InputError('DUPLICATE_DATE:' + key)
        result[key] = row
    return result

def build_case(folder, run_id, run_at):
    folder = Path(folder)
    report = {'kind': 'GatewayHistoricalInputBuild', 'version': '3.0.0', 'source_epoch': 'GATEWAY_V3',
              'run_id': run_id, 'recorded_at': run_at, 'status': 'DATA_BLOCKED', 'errors': [],
              'field_coverage': {}, 'case_hash': None, 'real_input_rows': 0,
              'capture_directory': str(folder), 'historical_visibility_proven': False,
              'provider_license_independently_verified': False}
    try:
        if folder.is_symlink(): raise InputError('CAPTURE_DIRECTORY_ALIAS')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}', run_id): raise InputError('RUN_ID_INVALID')
        clock(run_at)
        report.update(source_policy_hash=rawhash(SOURCE_POLICY), input_policy_hash=rawhash(INPUT_POLICY), protocol_hash=rawhash(PROTOCOL))
        authority = source_authority(); report['source_authority'] = authority
        protocol, method = read(PROTOCOL), read(METHOD)
        target = protocol['target_window']
        members = [{'symbol': m['symbol'], 'sector': g['id'], 'selection_evidence_ref': 'fixed-current-sample'} for g in method['universe'] for m in g['members']]
        symbols = [m['symbol'] for m in members]
        start, end = target['warmup_start'], target['end']
        compact_start, compact_end = start.replace('-', ''), end.replace('-', '')
        index, pins, _ = indexed_capture(folder, authority, symbols, compact_start, compact_end, report=report)
        report['raw_pins'] = pins
        evidence = {}
        def take(api, symbol):
            obj, rows, path, hashed = index[(api, symbol)]
            params = {'exchange' if api == 'trade_cal' else 'ts_code': symbol}
            if api in ('trade_cal', 'daily', 'stk_limit', 'suspend_d', 'adj_factor'): params.update(start_date=compact_start, end_date=compact_end)
            if obj['params'] != params: raise InputError('EXACT_REQUEST_SCOPE_REQUIRED:' + api)
            if clock(obj['retrieved_at']) > clock(run_at): raise InputError('SOURCE_RETRIEVED_AFTER_RUN')
            ref = Path(path).name
            evidence[ref] = {'source': 'OWNER_COMPATIBLE_GATEWAY/' + api, 'source_version': hashed,
                             'raw_sha256': hashed, 'published_at': None, 'available_at': obj['retrieved_at'],
                             'retrieved_at': obj['retrieved_at'], 'visibility_assumption': 'RECONSTRUCTED_SUPPLIER_HISTORY; SIMULATED_1800_DECISIONS; NOT_ORIGINAL_PIT', 'path': path}
            report['field_coverage'][api + ':' + symbol] = {'rows': len(rows), 'raw_sha256': hashed, 'source_ref': ref}
            if empty_suspend_schema_not_returned(obj):
                report['field_coverage'][api + ':' + symbol].update(schema_status='EMPTY_TABLE_SCHEMA_NOT_RETURNED',schema_verified=False,intraday_halt_absence_proven=False)
            return rows, ref
        days = []
        for offset in range((date.fromisoformat(end) - date.fromisoformat(start)).days + 1): days.append((date.fromisoformat(start) + timedelta(days=offset)).isoformat())
        calendars = {}; calrefs = {}
        for exchange in ('SSE', 'SZSE'):
            rows, ref = take('trade_cal', exchange); byday = date_index(rows, 'cal_date')
            if set(byday) != set(days) or any(r.get('exchange') != exchange or str(r.get('is_open')) not in ('0','1') for r in rows): raise InputError('FULL_CIVIL_CALENDAR_REQUIRED')
            calendars[exchange] = [d for d in days if str(byday[d]['is_open']) == '1']; calrefs[exchange] = ref
        opened = calendars['SSE']
        if opened != calendars['SZSE']: raise InputError('EXCHANGE_SESSION_MISMATCH')
        if len(opened) < 21: raise InputError('WARMUP_SESSIONS_INSUFFICIENT')
        calref = calrefs['SSE']
        coverage = {'start': start, 'end': end, 'days': [{'date': d, 'is_open': d in opened, 'evidence_ref': calref} for d in days]}
        calendar = [{'date': d, 'open_at': d+'T09:30:00+08:00', 'close_at': d+'T15:00:00+08:00', 'decision_at': d+'T18:00:00+08:00', 'decision_clock_label': 'SIMULATED_POST_CLOSE_DECISION_TIME', 'evidence_ref': calref} for d in opened]
        evidence['fixed-current-sample'] = {'source': 'OWNER_CURRENT_SAMPLE_SELECTION', 'source_version': rawhash(METHOD), 'raw_sha256': rawhash(METHOD), 'published_at': None, 'available_at': protocol['frozen_at'], 'retrieved_at': protocol['frozen_at'], 'visibility_assumption': 'CURRENT_SELECTION_BIAS; NO_HISTORICAL_UNIVERSE_CLAIM'}
        bars, actions, action_audit = [], [], []
        for member in members:
            symbol = member['symbol']; exchange = 'SSE' if symbol.endswith('.SH') else 'SZSE'
            rows, basicref = take('stock_basic', symbol)
            if len(rows) != 1: raise InputError('ONE_SECURITY_IDENTITY_REQUIRED')
            identity = rows[0]
            if (identity.get('ts_code') != symbol or identity.get('exchange') != exchange
                or identity.get('market') != '主板' or identity.get('list_status') != 'L'
                or day(identity['list_date']) > (date.fromisoformat(start)-timedelta(days=40)).isoformat()
                or identity.get('delist_date')): raise InputError('MATURE_MAINBOARD_IDENTITY_REQUIRED:' + symbol)
            names, nameref = take('namechange', symbol)
            if len(names) >= NAMECHANGE_LOCAL_ROW_CAP: raise InputError('NAMECHANGE_LOCAL_ROW_CAP_PAGINATION_REQUIRED')
            seen_names = {}; name_disclosures = []
            for row in names:
                if row.get('ts_code') != symbol: raise InputError('NAMECHANGE_IDENTITY_CONFLICT')
                if not isinstance(row.get('name'), str) or not row['name'].strip(): raise InputError('NAMECHANGE_NAME_REQUIRED')
                began = day(row['start_date'])
                ended = day(row['end_date']) if row.get('end_date') else None
                announced = day(row['ann_date']) if row.get('ann_date') else None
                if ended is not None and ended < began: raise InputError('NAMECHANGE_DATE_ORDER_INVALID')
                identity = (began, ended, row['name'])
                row_hash = digest(row)
                if identity in seen_names and seen_names[identity] != row_hash: raise InputError('NAMECHANGE_CONFLICTING_RECORD')
                seen_names[identity] = row_hash
                name_disclosures.append({'row_index':len(name_disclosures),'source_row_hash':row_hash,'ann_date':announced,'source_ref':nameref})
            report['field_coverage']['namechange:'+symbol].update(
                status='REFERENCE_ONLY_NOT_HISTORY_STATUS_CERTIFICATION',
                completeness='UNVERIFIED_REFERENCE_ONLY', local_row_cap=NAMECHANGE_LOCAL_ROW_CAP,
                observed_rows=len(names), unique_reference_rows=len(seen_names), duplicate_count=len(names)-len(seen_names), disclosures=name_disclosures, source_ref=nameref)
            # Neither current identity nor name history certifies historical ST,
            # relisting or every exchange exception. Actual per-day limits are used.
            rows, divref = take('dividend', symbol); symbol_actions = {}; economic_versions = {}; audits_by_ex = {}
            for row_number, row in enumerate(rows):
                if row.get('ts_code') != symbol: raise InputError('ACTION_IDENTITY_CONFLICT')
                ex = day(row['ex_date']) if row.get('ex_date') else None
                if row.get('div_proc') not in ('实施','预案','股东大会通过','不分配','停止实施','预披露','股东大会未通过','未通过'):
                    raise InputError('ACTION_PROCESS_UNKNOWN')
                if row.get('div_proc') != '实施':
                    execution_dates = ('record_date','ex_date','pay_date','div_listdate','imp_ann_date')
                    if row['div_proc'] == '预披露' and any(row.get(k) not in (None,'') for k in execution_dates):
                        raise InputError('PREDISCLOSURE_WITH_EXECUTION_DATES_CONFLICT')
                    if row['div_proc'] in ('股东大会未通过','未通过') and any(row.get(k) not in (None,'') for k in execution_dates):
                        raise InputError('NONIMPLEMENTED_WITH_EXECUTION_DATES_CONFLICT')
                    disclosure_times = {k:day(row[k]) if row.get(k) else None for k in ('end_date','ann_date',*execution_dates)}
                    action_audit.append({'symbol': symbol, 'ex_date': ex, 'status': 'EXCLUDED_UNIMPLEMENTED', 'div_proc':row.get('div_proc'),'source_row_hash':digest(row),'row_index':row_number,'source_ref': divref,'disclosure_times':disclosure_times}); continue
                if ex is None: raise InputError('IMPLEMENTED_ACTION_EX_DATE_MISSING')
                if not start <= ex <= end: continue
                cash, bonus = [dec(row[k]) for k in ('cash_div_tax','stk_div')]
                sent = dec(row['stk_bo_rate']) if row['stk_bo_rate'] is not None else None
                converted = dec(row['stk_co_rate']) if row['stk_co_rate'] is not None else None
                reported = [v for v in (sent,converted) if v is not None]
                if min(cash,bonus) < 0 or cash+bonus <= 0 or any(v < 0 or v > bonus for v in reported) or (len(reported)==2 and sum(reported)!=bonus): raise InputError('ACTION_COMPONENTS_INVALID')
                record = day(row['record_date'])
                if ex not in opened or record not in opened or opened.index(ex) != opened.index(record)+1: raise InputError('ACTION_RECORD_EX_BOUNDARY_UNSUPPORTED')
                pay = day(row['pay_date']) if cash > 0 and row.get('pay_date') else None
                listing = day(row['div_listdate']) if bonus > 0 and row.get('div_listdate') else None
                if cash > 0 and not pay: raise InputError('CASH_PAYMENT_DATE_REQUIRED')
                if bonus > 0 and not listing: raise InputError('BONUS_MARKET_DATE_REQUIRED')
                if (pay and pay < ex) or (listing and listing < ex): raise InputError('ACTION_SETTLEMENT_BEFORE_EX')
                action = {'id': symbol+':'+ex, 'symbol': symbol, 'record_date': record, 'ex_date': ex, 'pay_date': pay, 'shares_available_date': listing, 'cash_per_share': str(cash), 'bonus_ratio': str(bonus), 'split_ratio': '1', 'tax_rate': '0.20', 'evidence_ref': divref}
                disclosure = {'row_index':row_number,'source_row_hash':digest(row),
                              'ann_date':day(row['ann_date']) if row.get('ann_date') else None,
                              'imp_ann_date':day(row['imp_ann_date']) if row.get('imp_ann_date') else None,
                              'source_ref':divref,
                              'stock_components':{'stk_bo_rate':str(sent) if sent is not None else 'NOT_REPORTED','stk_co_rate':str(converted) if converted is not None else 'NOT_REPORTED'}}
                economic = {**action, 'end_date':day(row['end_date']) if row.get('end_date') else None,
                            'imp_ann_date':disclosure['imp_ann_date'], 'sent':str(sent) if sent is not None else None,
                            'converted':str(converted) if converted is not None else None}
                if ex in symbol_actions:
                    if economic_versions[ex] != economic: raise InputError('CONFLICTING_ECONOMIC_ACTION_DISCLOSURES')
                    audits_by_ex[ex]['disclosures'].append(disclosure)
                else:
                    symbol_actions[ex] = action; economic_versions[ex] = economic; actions.append(action)
                    audit = {'symbol':symbol,'ex_date':ex,'status':'RECONSTRUCTED_IMPLEMENTED','source_ref':divref,'disclosures':[disclosure]}
                    action_audit.append(audit); audits_by_ex[ex] = audit
            rows, factorref = take('adj_factor', symbol); factors = date_index(rows, 'trade_date', symbol)
            if set(factors) != set(opened): raise InputError('FULL_FACTOR_CALENDAR_REQUIRED')
            previous_factor = None
            for d in opened:
                factor = dec(factors[d]['adj_factor'])
                if factor <= 0: raise InputError('FACTOR_INVALID')
                if previous_factor is not None and ((factor != previous_factor) != (d in symbol_actions)): raise InputError('UNMATCHED_FACTOR_ACTION:' + symbol + ':' + d)
                previous_factor = factor
            rows, ref = take('daily', symbol); daily = date_index(rows, 'trade_date', symbol)
            rows, limitref = take('stk_limit', symbol); limits = date_index(rows, 'trade_date', symbol)
            rows, suspendref = take('suspend_d', symbol); suspension = {}
            empty_suspension = empty_suspend_schema_not_returned(index[('suspend_d', symbol)][0])
            if empty_suspension and (set(daily) != set(opened) or set(limits) != set(opened) or set(factors) != set(opened)):
                raise InputError('EMPTY_SUSPENSION_REQUIRES_FULL_DAILY_LIMIT_FACTOR_COVERAGE:' + symbol)
            for row in rows:
                if row.get('ts_code') != symbol: raise InputError('SUSPENSION_IDENTITY_CONFLICT')
                d = day(row['trade_date'])
                if d not in opened: raise InputError('SUSPENSION_OUTSIDE_OPEN_CALENDAR')
                if row.get('suspend_type') not in ('S','R'): raise InputError('SUSPENSION_TYPE_UNKNOWN')
                if row.get('suspend_timing'): raise InputError('INTRADAY_SUSPENSION_UNSUPPORTED')
                if d in suspension: raise InputError('DUPLICATE_OR_CONFLICTING_SUSPENSION')
                suspension[d] = row['suspend_type']
            if set(daily)-set(opened) or set(limits)-set(opened): raise InputError('PRICE_OR_LIMIT_OUTSIDE_CALENDAR')
            previous_close = None; previous_raw_close = None
            for d in opened:
                action = symbol_actions.get(d)
                if action and previous_close is not None: previous_close = (previous_close-dec(action['cash_per_share']))/(1+dec(action['bonus_ratio']))
                base = {'session': d, 'symbol': symbol, 'price_kind': 'RAW', 'lot_size': 100,
                        'evidence_ref': ref, 'identity_evidence_ref': basicref, 'limit_evidence_ref': limitref,
                        'status_evidence_ref': suspendref, 'factor_evidence_ref': factorref,
                        'limit_kind': 'CAPTURED_STK_LIMIT_RECONSTRUCTED_NOT_EXCHANGE_ORIGINAL',
                        'suspension_schema_verified': not empty_suspension, 'intraday_halt_absence_proven': False}
                if d not in daily:
                    if suspension.get(d) != 'S': raise InputError('MISSING_BAR_WITHOUT_FULL_DAY_SUSPENSION:' + symbol + ':' + d)
                    bars.append(dict(base, status='SUSPENDED', open=None, high=None, low=None, close=None, volume_shares='0', amount_CNY='0', lower_limit=None, upper_limit=None)); continue
                if suspension.get(d) == 'S': raise InputError('SUSPENSION_WITH_TRADING_BAR')
                row = daily[d]
                if d not in limits: raise InputError('ACTUAL_LIMIT_MISSING:' + symbol + ':' + d)
                lo, hi = dec(limits[d]['down_limit']), dec(limits[d]['up_limit'])
                if not 0 < lo < hi or lo%D('.01') or hi%D('.01'): raise InputError('ACTUAL_LIMIT_INVALID')
                volume, amount = dec(row['vol'])*100, dec(row['amount'])*1000
                if volume <= 0 or volume != int(volume) or amount <= 0: raise InputError('DAILY_VOLUME_AMOUNT_INVALID')
                values = {k: dec(row[k]) for k in ('open','high','low','close')}
                if any(v <= 0 or v%D('.01') or not lo <= v <= hi for v in values.values()) or not values['low'] <= min(values['open'],values['close']) <= max(values['open'],values['close']) <= values['high']: raise InputError('RAW_OHLC_OR_LIMIT_CONFLICT')
                pre = dec(row['pre_close'])
                if pre <= 0: raise InputError('PRECLOSE_INVALID')
                if limits[d].get('pre_close') is None: raise InputError('LIMIT_PRECLOSE_MISSING')
                limit_pre = dec(limits[d]['pre_close'])
                limit_pre_kind = 'DAILY_REFERENCE'
                if limit_pre != pre:
                    if action is None or previous_raw_close is None or limit_pre != previous_raw_close:
                        raise InputError('LIMIT_DAILY_PRECLOSE_CONFLICT')
                    limit_pre_kind = 'PREVIOUS_RAW_CLOSE_ON_CONFIRMED_EX_DATE'
                    report.setdefault('limit_pre_close_semantic_inventory', []).append({'symbol':symbol,'session':d,
                        'kind':limit_pre_kind,'daily_pre_close':str(pre),'limit_pre_close':str(limit_pre),
                        'action_id':action['id'],'daily_evidence_ref':ref,'limit_evidence_ref':limitref})
                if previous_close is not None and pre.quantize(D('.01'),rounding=ROUND_HALF_UP) != previous_close.quantize(D('.01'),rounding=ROUND_HALF_UP): raise InputError('UNEXPLAINED_PRECLOSE_ACTION_OR_VERSION_CHANGE:' + symbol + ':' + d)
                bars.append(dict(base, status='TRADABLE', **{k:str(v) for k,v in values.items()}, volume_shares=str(volume), amount_CNY=str(amount), lower_limit=str(lo), upper_limit=str(hi), pre_close=str(pre), limit_pre_close=str(limit_pre), limit_pre_close_kind=limit_pre_kind))
                previous_close = values['close']; previous_raw_close = values['close']
        active = [d for d in opened if target['start'] <= d <= target['end']]
        if not active or sum(d < active[0] for d in opened) < 20: raise InputError('TARGET_OR_WARMUP_INCOMPLETE')
        case = {'namespace': protocol['namespace'], 'strategy_id': protocol['strategy_id'], 'run_id': run_id,
                'run_at': run_at, 'source_epoch': 'GATEWAY_V3', 'evidence_grade': 'RECONSTRUCTED_HISTORY_DIAGNOSTIC',
                'protocol_ref': rawhash(PROTOCOL), 'method_ref': rawhash(METHOD), 'input_policy_ref': rawhash(INPUT_POLICY),
                'source_policy_ref': rawhash(SOURCE_POLICY), 'permission_state': PERMISSION,
                'input_limitations': {'intraday_halt_absence_proven':False, 'empty_suspension_schema_symbols':[m['symbol'] for m in members if empty_suspend_schema_not_returned(index[('suspend_d',m['symbol'])][0])]},
                'rules': RULES, 'rules_hash': digest(RULES), 'fee_schedule': protocol['fee_schedule'],
                'calendar': calendar, 'calendar_coverage': coverage, 'universe': members,
                'window': {'first_session': active[0], 'last_session': active[-1]}, 'evidence': evidence,
                'bars': bars, 'actions': sorted(actions,key=lambda a:(a['ex_date'],a['symbol']))}
        report.update(status='ADMITTED_RECONSTRUCTED_DIAGNOSTIC_ONLY', case_hash=digest(case), real_input_rows=report.get('captured_daily_rows',0), normalized_execution_rows=len(bars), action_inventory=action_audit, market_sessions=len(opened), target_sessions=len(active), limitations=['Owner-authorized local purpose; provider/license not independently certified', 'current fixed sample, reconstructed supplier history, NOT_ORIGINAL_PIT', 'actual supplier limits, simulated costs/tax and 18:00 decision clock'])
        return report, case
    except (ValueError, KeyError, TypeError, OSError, ArithmeticError) as exc:
        report['errors'].append({'type': type(exc).__name__, 'detail': str(exc)})
        return report, None

def verify_provenance(case, folder):
    report, recomputed = build_case(folder, case['run_id'], case['run_at'])
    if report['status'] != 'ADMITTED_RECONSTRUCTED_DIAGNOSTIC_ONLY' or recomputed != case: raise InputError('REBUILD_OR_ADMISSION_MISMATCH')
    return {'verified': True, 'case_hash': digest(case), 'receipt_hash': digest(report), 'purpose': 'LOCAL_HISTORICAL_DIAGNOSTIC'}
