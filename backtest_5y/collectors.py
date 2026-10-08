"""Bounded public research collection with raw/error retention, no credentials."""
from __future__ import annotations
import json
import os
import re
import socket
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener
from .data import iso_day, _lexical
from .interface import SYMBOLS, HISTORY_START, FINANCIAL_START, HISTORY_END, digest, utc_now, write_new
from .sources import DOCUMENTS, catalog

TIMEOUT_SECONDS = 20
MAX_BODY_BYTES = 16 * 1024 * 1024
PRIVATE_ROOT = Path('/Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/data')
ALLOWED_HOSTS = frozenset(('tushare.pro', 'raw.githubusercontent.com', 'english.sse.com.cn',
                         'www.cninfo.com.cn', 'static.cninfo.com.cn',
                         'proxy.finance.qq.com', 'quotes.sina.cn'))
LICENSE = 'PUBLIC_RESEARCH_ACCESS_UPSTREAM_LICENSE_UNVERIFIED'
SINA_FIELDS = {
    'revenue': ('营业收入',), 'total_revenue': ('营业总收入',), 'oper_cost': ('营业成本',),
    'n_income': ('净利润',), 'n_income_attr_p': ('归属于母公司所有者的净利润', '归属于母公司股东的净利润'),
    'n_cashflow_act': ('经营活动产生的现金流量净额',), 'money_cap': ('货币资金',),
    'total_liab': ('负债合计',), 'total_assets': ('资产总计', '资产合计'),
    'total_hldr_eqy_inc_min_int': ('所有者权益合计',),
    'roic': ('投入资本回报率', '投入资本收益率'), 'ebitda': ('EBITDA', '息税折旧摊销前利润'),
    'net_debt': ('净债务',), 'grossprofit_margin': ('销售毛利率', '毛利率'),
}


def sina_canonical_fields(items):
    fields, lineage, conflicts = {}, {}, []
    for key, titles in SINA_FIELDS.items():
        matched = [{'position': i, 'title': item.get('item_title'), 'raw_value': item.get('item_value'),
                    'unit_state': 'UNVERIFIED_SOURCE_FINANCIAL_UNIT'}
                   for i, item in enumerate(items) if item.get('item_title') in titles]
        if not matched: continue
        lineage[key] = matched
        values = {str(item['raw_value']) for item in matched}
        if len(values) > 1:
            fields[key] = None; conflicts.append(key)
        else:
            value = matched[0]['raw_value']
            fields[key] = None if value in (None, '', '--', 'null', 'NaN') else str(value)
    return fields, lineage, conflicts


def allowed_url(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname not in ALLOWED_HOSTS or p.username or p.password or p.port not in (None, 443):
        raise ValueError('PUBLIC_URL_NOT_ALLOWLISTED')
    return url


class _BoundedRedirect(HTTPRedirectHandler):
    max_redirections = 2
    max_repeats = 1

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url, params=None, method='GET', max_bytes=MAX_BODY_BYTES):
    """One attempt, verified TLS, allowlisted redirects, no auth/cookie handlers."""
    allowed_url(url)
    encoded = urlencode(params or {}).encode()
    target = url + ('?' + encoded.decode() if method == 'GET' and encoded else '')
    headers = {'User-Agent': 'MetaSurvey-private-research/1.0', 'Accept': '*/*'}
    if method == 'POST':
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    request = Request(target, data=encoded if method == 'POST' else None, headers=headers, method=method)
    result = {'url': target, 'method': method, 'parameters': params or {}, 'requested_at': utc_now(),
              'http_status': None, 'content_type': None, 'error': None, 'raw_bytes': b''}
    start = time.monotonic()
    try:
        with build_opener(ProxyHandler({}), _BoundedRedirect()).open(request, timeout=TIMEOUT_SECONDS) as response:
            result['http_status'] = response.status
            result['content_type'] = response.headers.get('Content-Type')
            result['final_url'] = response.url
            chunks = []
            size = 0
            while True:
                remaining = TIMEOUT_SECONDS - (time.monotonic() - start)
                if remaining <= 0:
                    raise TimeoutError('PUBLIC_TOTAL_DEADLINE')
                # Reduce each body read timeout to the remaining total deadline.
                try:
                    response.fp.raw._sock.settimeout(remaining)
                except AttributeError:
                    pass
                chunk = response.read(min(65536, max_bytes + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk); size += len(chunk)
                result['raw_bytes'] = b''.join(chunks)
                if size > max_bytes:
                    raise ValueError('PUBLIC_BODY_SIZE_LIMIT')
            result['raw_bytes'] = b''.join(chunks)
    except HTTPError as exc:
        result['http_status'] = exc.code
        result['content_type'] = exc.headers.get('Content-Type')
        result['error'] = {'type': 'HTTPError', 'message': str(exc)}
        remaining = TIMEOUT_SECONDS - (time.monotonic() - start)
        if remaining > 0:
            try:
                try: exc.fp.raw._sock.settimeout(remaining)
                except AttributeError: pass
                result['raw_bytes'] = exc.read(min(max_bytes, 65536))
            except Exception as read_error:
                result['error_body_capture_error'] = type(read_error).__name__
    except Exception as exc:
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)[:500]}
    result['elapsed_seconds'] = round(time.monotonic() - start, 3)
    result['completed_at'] = utc_now()
    result['retrieved_at'] = result['completed_at']
    return result


def _record(identity, event_date, fields, ordinal, *, units=None, provenance=None):
    return {'identity': identity, 'event_date': event_date, 'published_at': None,
            'available_at': None, 'first_visible_at': None, 'revision_id': None,
            'fields': fields, 'units': units or {'state': 'UNVERIFIED'},
            'provenance': {'row_ordinal': ordinal, 'historical_visibility_proven': False,
                           'revision_chain': 'NOT_PROVEN', 'quarantined': True,
                           **(provenance or {})}}


def parse_tencent(raw, symbol, start=HISTORY_START, end=HISTORY_END):
    if iso_day(start) != start or iso_day(end) != end or start > end:
        raise ValueError('TENCENT_INTERVAL_INVALID')
    key = 'sh' + symbol[:6]
    text = raw.decode('utf-8')
    if '={' in text:
        text = text[text.index('={') + 1:]
    value = _lexical(text.rstrip(';\n '))
    data = value.get('data', {}).get(key, {})
    if 'day' not in data:
        # Do not silently substitute adjusted data.
        raise ValueError('TENCENT_RAW_DAY_MISSING_NO_ADJUSTED_FALLBACK')
    records = []
    for i, row in enumerate(data['day']):
        if not isinstance(row, list) or len(row) < 6:
            raise ValueError('TENCENT_RAW_ROW_SHAPE')
        day = iso_day(row[0])
        if day is None:
            raise ValueError('TENCENT_DATE_INVALID')
        if not start <= day <= end:
            continue
        fields = {'ts_code': symbol, 'trade_date': day.replace('-', ''),
                  'open': str(row[1]), 'close': str(row[2]), 'high': str(row[3]),
                  'low': str(row[4]), 'vol': str(row[5])}
        if len(row) > 7: fields['turnover_source_percent'] = str(row[7])
        if len(row) > 8: fields['amount'] = str(row[8])
        records.append(_record('daily:' + symbol + ':' + day.replace('-', ''), day, fields, i,
                       units={'price': 'SOURCE_CNY_PER_SHARE_NOT_INDEPENDENTLY_VERIFIED',
                              'vol': 'SOURCE_LOTS_PER_AKSHARE_MAINBOARD_DOC_UNVERIFIED',
                              'amount': 'SOURCE_TEN_THOUSAND_CNY_PER_AKSHARE_DOC_UNVERIFIED'},
                       provenance={'actual_API': 'tencent.newfqkline', 'raw_or_adjusted': 'RAW',
                                   'source_selector': ['data', key, 'day', i], 'raw_row': row}))
    return records


def parse_sina(raw, symbol, statement, start=FINANCIAL_START, end=HISTORY_END):
    if iso_day(start) != start or iso_day(end) != end or start > end:
        raise ValueError('SINA_INTERVAL_INVALID')
    value = _lexical(raw)
    data = value.get('result', {}).get('data', {})
    reports = data.get('report_list')
    if not isinstance(reports, dict):
        raise ValueError('SINA_REPORT_LIST_MISSING')
    records = []
    for i, (period, report) in enumerate(sorted(reports.items())):
        day = iso_day(period)
        if day is None or not start <= day <= end:
            continue
        raw_items = report.get('data')
        if not isinstance(raw_items, list):
            raise ValueError('SINA_FINANCIAL_ITEMS_SHAPE')
        fields = {'ts_code': symbol, 'end_date': day.replace('-', ''),
                  'source_statement': statement, 'raw_items': raw_items,
                  'publish_date': report.get('publish_date'), 'update_time': report.get('update_time'),
                  'currency': report.get('rCurrency'), 'report_type': report.get('rType'),
                  'data_source': report.get('data_source'), 'is_audit': report.get('is_audit')}
        # Repeated item titles remain distinct. No YTD -> quarter calculation.
        for j, item in enumerate(raw_items):
            fields[str(item.get('item_title')) + '#' + str(j)] = item.get('item_value')
        mapped, mapping, conflicts = sina_canonical_fields(raw_items)
        fields.update(mapped)
        fields['canonical_mapping_state'] = 'UNKNOWN_DUPLICATE_CONFLICT' if conflicts else 'LITERAL_TITLE_MAPPING_UNITS_METHOD_UNVERIFIED'
        records.append(_record('sina:' + statement + ':' + symbol + ':' + day, day, fields, i,
                       units={'state': 'SOURCE_FINANCIAL_UNITS_AND_METHOD_UNVERIFIED', 'currency': report.get('rCurrency')},
                       provenance={'actual_API': 'sina.CompanyFinanceService.getFinanceReport2022',
                                   'source_selector': ['result', 'data', 'report_list', period],
                                   'source_report_metadata': {k: v for k, v in report.items() if k != 'data'},
                                   'publication_precision': 'SOURCE_LITERAL_NOT_PROMOTED_TO_INSTANT',
                                   'financial_period_semantics': 'POSSIBLY_CUMULATIVE_YTD_NOT_QUARTER',
                                   'version_sweep_state': 'ALL_CAPTURED_REPORT_PERIODS_VENDOR_VERSION_CHAIN_NOT_EXPOSED',
                                   'canonical_field_lineage': mapping, 'canonical_conflicts': conflicts,
                                   'method_state': 'METHOD_AMBIGUITY_REVENUE_NET_INCOME_CURRENCY_AND_YTD_POLICY_UNFROZEN',
                                   'issuer_original': False}))
    return records


def parse_cninfo(raw, symbol):
    value = _lexical(raw)
    items = value.get('announcements')
    if items is None:
        return [], value.get('totalAnnouncement', 0)
    if not isinstance(items, list):
        raise ValueError('CNINFO_ANNOUNCEMENT_SHAPE')
    records = []
    for i, item in enumerate(items):
        if item.get('secCode') != symbol[:6]:
            raise ValueError('CNINFO_SECURITY_MISMATCH')
        adjunct = item.get('adjunctUrl', '')
        day = iso_day(adjunct.split('/')[1]) if adjunct.startswith('finalpage/') else None
        fields = {**item, 'ts_code': symbol, 'body_status': 'INDEX_METADATA_ONLY',
                  'document_url': 'https://static.cninfo.com.cn/' + adjunct}
        records.append(_record('cninfo:' + symbol + ':' + str(item.get('announcementId')), day, fields, i,
                       provenance={'actual_API': 'cninfo.hisAnnouncement.query', 'source_selector': ['announcements', i],
                                   'reported_announcementTime': item.get('announcementTime'),
                                   'publication_precision': 'DATE_ONLY_DOCUMENT_PATH_AND_UNINTERPRETED_PROVIDER_TIMESTAMP',
                                   'issuer_original': False}))
    return records, value.get('totalAnnouncement')


def parse_cninfo_identity(raw, symbol):
    items = _lexical(raw)
    if not isinstance(items, list):
        raise ValueError('CNINFO_IDENTITY_SHAPE')
    orgs = {str(item['orgId']) for item in items
            if str(item.get('code')) == symbol[:6] and item.get('orgId')}
    if len(orgs) > 1:
        raise ValueError('CNINFO_IDENTITY_CONFLICT_UNKNOWN')
    return next(iter(orgs), None)


def requested_ranges(update_plan, domain, symbol, through, default_start):
    if update_plan is None:
        return [(default_start, through)]
    rows = update_plan.get('rows', [])
    if not isinstance(rows, list):
        raise ValueError('UPDATE_PLAN_ROWS_REQUIRED')
    ranges = []
    for row in rows:
        if row.get('domain') != domain or row.get('symbol') != symbol:
            continue
        for interval in row.get('requested_intervals', row.get('intervals', [])):
            if isinstance(interval, dict):
                start = iso_day(interval.get('start', interval.get('start_date')))
                end = iso_day(interval.get('end', interval.get('end_date')))
            elif isinstance(interval, (list, tuple)) and len(interval) == 2:
                start, end = map(iso_day, interval)
            else:
                raise ValueError('UPDATE_PLAN_INTERVAL_SHAPE')
            if start is None or end is None or start > end:
                raise ValueError('UPDATE_PLAN_INTERVAL_DATE')
            start, end = max(start, default_start), min(end, through)
            if start <= end: ranges.append((start, end))
    return sorted(set(ranges))


def collect_public(output_root, update_plan=None, through=HISTORY_END):
    if iso_day(through) != through:
        raise ValueError('THROUGH_DATE_INVALID')
    root = Path(output_root).resolve()
    if not root.is_relative_to(PRIVATE_ROOT):
        raise ValueError('PUBLIC_OUTPUT_OUTSIDE_OWNED_PRIVATE_DATA_ROOT')
    root.mkdir(parents=True, exist_ok=True)
    run = root / ('public-' + uuid.uuid4().hex)
    run.mkdir(mode=0o700)
    batches, attempts, processing_gaps = [], [], []

    def attempt(name, source, domain, symbol, url, params=None, method='GET', parser=None):
        result = _fetch(url, params, method)
        raw = result.pop('raw_bytes')
        path = run / (name + '.raw')
        with path.open('xb') as f: f.write(raw)
        path.chmod(0o600)
        result.update({'name': name, 'source': source, 'domain': domain, 'symbol': symbol,
                       'raw_ref': {'path': str(path), 'bytes': len(raw), 'sha256': digest(raw)},
                       'license_state': LICENSE, 'records': 0, 'parse_error': None})
        records = []
        if result['error'] is None and parser:
            try:
                records = parser(raw)
            except Exception as exc:
                result['parse_error'] = {'type': type(exc).__name__, 'message': str(exc)[:500]}
        result['records'] = len(records)
        write_new(run / (name + '.attempt.json'), result)
        batch = None
        if records:
            for record in records:
                record['provenance'].update({'raw_sha256': digest(raw), 'raw_ref': result['raw_ref'],
                                           'retrieved_at': result['retrieved_at']})
            batch = {'source': source, 'domain': domain, 'symbol': symbol,
                     'request': {'url': url, 'method': method, 'params': params or {},
                                 'attempt_ref': str(run / (name + '.attempt.json'))},
                     'retrieved_at': result['retrieved_at'], 'raw_bytes': raw,
                     'source_url': url, 'records': records, 'license_state': LICENSE}
        return result, batch, raw

    # Technical primary source pages are evidence only, never market records.
    def document_work(item):
        name, url = item
        a, _, _ = attempt('doc-' + name, name, 'SOURCE_DOCUMENTATION', None, url)
        return a
    with ThreadPoolExecutor(max_workers=3) as pool:
        attempts.extend(pool.map(document_work, DOCUMENTS))

    def security_work(symbol):
        own_attempts, own_batches = [], []
        def take(*args, **kwargs):
            a, b, raw = attempt(*args, **kwargs)
            own_attempts.append(a)
            if b: own_batches.append(b)
            return a, b, raw
        key = 'sh' + symbol[:6]
        # Independent yearly requests, no retry; all versions/duplicates remain.
        intervals = requested_ranges(update_plan, 'PRICE', symbol, through, HISTORY_START)
        price_windows = []
        for start, end in intervals:
            for year in range(int(start[:4]), int(end[:4]) + 1):
                price_windows.append((max(start, f'{year}-01-01'), min(end, f'{year}-12-31')))
        for window_id, (start, end) in enumerate(sorted(set(price_windows))):
            year = start[:4]
            def price_parser(raw, lower=start, upper=end):
                return parse_tencent(raw, symbol, start=lower, end=upper)
            take(f'{symbol}-price-{year}-{window_id}', 'TENCENT_PUBLIC_RAW_PRICE', 'PRICE', symbol,
                 'https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get',
                 {'_var': f'kline_day{year}', 'param': f'{key},day,{start},{end},640,', 'r': '0.8205512681390605'},
                 parser=price_parser)
        for statement, domain in [('lrb', 'FINANCIAL_INCOME'), ('fzb', 'FINANCIAL_BALANCE'),
                                  ('llb', 'FINANCIAL_CASHFLOW'), ('gjzb', 'FINANCIAL_INDICATOR')]:
            if not requested_ranges(update_plan, domain, symbol, through, FINANCIAL_START):
                continue
            take(f'{symbol}-financial-{statement}', 'SINA_PUBLIC_FINANCIAL', domain, symbol,
                 'https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022',
                 {'paperCode': key, 'source': statement, 'type': '0', 'page': '1', 'num': '1000'},
                 parser=lambda raw, s=statement: parse_sina(raw, symbol, s, end=through))
        # Resolve exact issuer ID rather than fabricating one. Query only issuer annuals.
        catalyst_requested = bool(requested_ranges(update_plan, 'CATALYST', symbol, through, FINANCIAL_START))
        if not catalyst_requested:
            return own_attempts, own_batches
        a, _, raw = take(f'{symbol}-cninfo-identity', 'CNINFO_ISSUER_DISCLOSURES', 'SOURCE_IDENTITY', symbol,
                        'https://www.cninfo.com.cn/new/information/topSearch/query',
                        {'keyWord': symbol[:6], 'maxNum': '10'}, method='POST')
        org = None
        if not a['error']:
            try:
                org = parse_cninfo_identity(raw, symbol)
            except Exception as exc:
                processing_gaps.append({'symbol': symbol, 'domain': 'CATALYST',
                    'state': 'UNKNOWN_IDENTITY', 'attempt_ref': a['raw_ref'],
                    'reason': str(exc)})
        if not org:
            processing_gaps.append({'symbol': symbol, 'domain': 'CATALYST',
                'state': 'BLOCKED_SOURCE_ACCESS', 'attempt_ref': a['raw_ref'],
                'reason': 'No unambiguous exact issuer identifier from public response'})
        if org:
            a, batch, _ = take(f'{symbol}-cninfo-annuals', 'CNINFO_ISSUER_DISCLOSURES', 'CATALYST', symbol,
                              'https://www.cninfo.com.cn/new/hisAnnouncement/query',
                              {'stock': symbol[:6] + ',' + org, 'tabName': 'fulltext', 'pageSize': '50',
                               'pageNum': '1', 'column': 'sse', 'plate': 'sh',
                               'category': 'category_ndbg_szsh', 'seDate': FINANCIAL_START + '~' + through,
                               'isHLtitle': 'true'}, method='POST',
                              parser=lambda raw: parse_cninfo(raw, symbol)[0])
            if batch:
                original = _lexical(batch['raw_bytes'])
                processing_gaps.append({'symbol': symbol, 'domain': 'CATALYST',
                    'state': 'BOUNDED_PARTIAL_ANNUAL_ONLY_NOT_FULL_CATALYST_HISTORY',
                    'total_announcements_reported': original.get('totalAnnouncement'),
                    'captured_index_rows': len(batch['records']), 'pages_requested': 1,
                    'issuer_pdfs_requested_maximum': 2, 'raw_ref': a['raw_ref']})
                # Up to2 genuine issuer financial-report documents per security.
                candidates = [r for r in batch['records'] if '年度报告' in str(r['fields'].get('announcementTitle'))
                              and '摘要' not in str(r['fields'].get('announcementTitle'))]
                for j, rec in enumerate(candidates[:2]):
                    url = rec['fields']['document_url']
                    def pdf_record(raw, original=rec):
                        if not raw.startswith(b'%PDF-'):
                            raise ValueError('ISSUER_DOCUMENT_NOT_PDF')
                        return [_record(original['identity'] + ':body', original['event_date'],
                                        {**original['fields'], 'body_status': 'PDF_BYTES_CAPTURED_NOT_NUMERICALLY_EXTRACTED'}, 0,
                                        provenance={'actual_API': 'CNINFO_ISSUER_PDF', 'issuer_original': True,
                                                    'numeric_extraction_complete': False,
                                                    'parent_index_provenance': original['provenance']})]
                    take(f'{symbol}-issuer-pdf-{j}', 'CNINFO_ISSUER_DISCLOSURES', 'CATALYST', symbol,
                         url, parser=pdf_record)
        return own_attempts, own_batches

    with ThreadPoolExecutor(max_workers=3) as pool:
        for own_attempts, own_batches in pool.map(security_work, SYMBOLS):
            attempts.extend(own_attempts); batches.extend(own_batches)
    supported = {'PRICE', 'FINANCIAL_INCOME', 'FINANCIAL_BALANCE', 'FINANCIAL_CASHFLOW', 'FINANCIAL_INDICATOR', 'CATALYST'}
    blocked = list(processing_gaps)
    rows = update_plan.get('rows', []) if update_plan is not None else [
        {'domain': d, 'symbol': s, 'requested_intervals': [{'start': HISTORY_START, 'end': through}]}
        for d in ('CALENDAR', 'VALUATION', 'ACTION', 'STATUS', 'INDUSTRY_MEMBERSHIP',
                  'SECTOR_TOTAL_RETURN', 'BENCHMARK', 'UNIVERSE') for s in SYMBOLS]
    for row in rows:
        if row.get('domain') not in supported and row.get('requested_intervals', row.get('intervals', [])):
            blocked.append({'domain': row['domain'], 'symbol': row['symbol'],
                            'state': 'BLOCKED_SOURCE_ACCESS',
                            'requested_intervals': row.get('requested_intervals', row.get('intervals', [])),
                            'reason': 'No complete permitted unauthenticated historical source established; no implicit endpoint, credential or proxy substitution'})
    summary = {'version': '1.0.0-sidecar', 'created_at': utc_now(), 'scope': list(SYMBOLS),
               'source_catalog': catalog(), 'attempts': attempts, 'batches': len(batches),
               'imported_records': sum(len(b['records']) for b in batches),
               'no_credentials': True, 'historical_visibility_proven': False, 'formal_admission': False,
               'source_license_admitted': False, 'productionGate': False,
               'update_plan_consumed': update_plan is not None, 'through': through,
               'historical_diagnostic_cutoff_unchanged': HISTORY_END,
               'blocked_source_requests': blocked,
               'timeouts_seconds': TIMEOUT_SECONDS, 'retries_per_request': 0,
               'missing': ['licensed historical valuation2016-2026', 'independent status/action/calendar continuity',
                           'PIT financial revisions/first-visible', 'historical industry/sector total return',
                           'licensed Owner benchmark total return', 'full issuer quarterly originals/numeric extraction'],
               'labels': ['NON_PIT_DIAGNOSTIC', 'NOT_FORMAL_OOS', 'NON_TRADEABLE']}
    write_new(run / 'Collection-Report.json', summary)
    return {'batches': batches, 'attempts': attempts, 'blocked': blocked,
            'blocked_source_requests': blocked,
            'report_path': str(run / 'Collection-Report.json')}
