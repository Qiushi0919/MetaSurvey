"""Network-free synthetic collector contract and source conflict tests."""
import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from backtest_5y import collectors as c
from backtest_5y.interface import SYMBOLS, HISTORY_END


def sina_raw(items, metadata=None):
    return json.dumps({'result': {'data': {'report_list': {'20240331':
        {'data': items, 'publish_date': '2024-04-29', 'update_time': '2026-09-29',
         'rCurrency': 'CNY', **(metadata or {})}}}}}, ensure_ascii=False).encode()


class PublicCollectorTests(unittest.TestCase):
    def test_tencent_raw_row_binding_and_no_adjusted_fallback(self):
        row = ['2024-03-01', '1.1', '1.2', '1.3', '1.0', '11.00', '', '0.01', '12.00']
        raw = ('kline_day2024=' + json.dumps({'data': {'sh603993': {'day': [row]}}})).encode()
        rec = c.parse_tencent(raw, SYMBOLS[0])[0]
        self.assertEqual(rec['fields']['close'], '1.2')
        self.assertEqual(rec['provenance']['raw_row'], row)
        self.assertIsNone(rec['first_visible_at'])
        with self.assertRaisesRegex(ValueError, 'NO_ADJUSTED_FALLBACK'):
            c.parse_tencent(b'{"data":{"sh603993":{"qfqday":[]}}}', SYMBOLS[0])

    def test_sina_canonical_literal_lineage_and_ytd_ambiguity(self):
        items = [{'item_title': '营业收入', 'item_value': '123.4500'},
                 {'item_title': '净利润', 'item_value': '10'},
                 {'item_title': '经营活动产生的现金流量净额', 'item_value': '20'}]
        rec = c.parse_sina(sina_raw(items), SYMBOLS[0], 'lrb')[0]
        self.assertEqual(rec['fields']['revenue'], '123.4500')
        self.assertEqual(rec['fields']['n_income'], '10')
        self.assertEqual(rec['provenance']['canonical_field_lineage']['revenue'][0]['position'], 0)
        self.assertEqual(rec['fields']['raw_items'], items)
        self.assertIsNone(rec['published_at'])
        self.assertIsNone(rec['available_at'])
        self.assertIn('METHOD_AMBIGUITY', rec['provenance']['method_state'])
        self.assertIn('YTD_NOT_QUARTER', rec['provenance']['financial_period_semantics'])

    def test_sina_duplicate_title_conflict_unknown_and_missing_not_zero(self):
        items = [{'item_title': '营业收入', 'item_value': '100'},
                 {'item_title': '营业收入', 'item_value': '200'},
                 {'item_title': '净债务', 'item_value': '--'}]
        rec = c.parse_sina(sina_raw(items), SYMBOLS[0], 'lrb')[0]
        self.assertIsNone(rec['fields']['revenue'])
        self.assertIsNone(rec['fields']['net_debt'])
        self.assertEqual(rec['provenance']['canonical_conflicts'], ['revenue'])
        self.assertEqual(rec['fields']['营业收入#0'], '100')
        self.assertEqual(rec['fields']['营业收入#1'], '200')

    def test_hk_currency_retained_no_conversion(self):
        rec = c.parse_sina(sina_raw([{'item_title': '营业收入', 'item_value': '10'}],
                                  {'rCurrency': 'HKD', 'rType': 'HK'}), SYMBOLS[0], 'lrb')[0]
        self.assertEqual(rec['fields']['currency'], 'HKD')
        self.assertIn('CURRENCY', rec['provenance']['method_state'])

    def test_cninfo_date_path_is_date_only(self):
        raw = json.dumps({'totalAnnouncement': 10, 'announcements': [{'secCode': '603993',
            'announcementId': 'a', 'adjunctUrl': 'finalpage/2024-04-29/a.PDF',
            'announcementTime': 1714348800000}]}).encode()
        records, total = c.parse_cninfo(raw, SYMBOLS[0])
        self.assertEqual(total, 10)
        self.assertEqual(records[0]['event_date'], '2024-04-29')
        self.assertIsNone(records[0]['published_at'])
        self.assertEqual(records[0]['provenance']['reported_announcementTime'], 1714348800000)
        with self.assertRaisesRegex(ValueError, 'SECURITY_MISMATCH'):
            c.parse_cninfo(raw, SYMBOLS[1])

    def test_cninfo_identity_conflict_unknown(self):
        raw = b'[{"code":"603993","orgId":"a"},{"code":"603993","orgId":"b"}]'
        with self.assertRaisesRegex(ValueError, 'CONFLICT_UNKNOWN'):
            c.parse_cninfo_identity(raw, SYMBOLS[0])

    def test_explicit_update_after_history_keeps_null_visibility_and_default_cutoff(self):
        raw = b'{"data":{"sh603993":{"day":[["2026-10-08","1","2","3","1","10"]]}}}'
        self.assertEqual(c.parse_tencent(raw, SYMBOLS[0]), [])
        rec = c.parse_tencent(raw, SYMBOLS[0], start='2026-10-01', end='2026-10-08')[0]
        self.assertEqual(rec['event_date'], '2026-10-08')
        self.assertIsNone(rec['available_at'])
        self.assertIsNone(rec['first_visible_at'])
        financial = sina_raw([{'item_title': '营业收入', 'item_value': '1'}]).replace(b'20240331', b'20260930')
        self.assertEqual(c.parse_sina(financial, SYMBOLS[0], 'lrb', end='2026-06-30'), [])
        self.assertEqual(len(c.parse_sina(financial, SYMBOLS[0], 'lrb', end='2026-10-08')), 1)

    def test_allowlist_and_redirect_reject_credentials_or_nonpublic_host(self):
        for url in ('http://quotes.sina.cn/x', 'https://user:pass@quotes.sina.cn/x',
                    'https://localhost/x', 'https://quotes.sina.cn:8443/x'):
            with self.assertRaises(ValueError): c.allowed_url(url)
        with self.assertRaises(ValueError):
            c._BoundedRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com/x')

    def test_fetch_completion_clock_and_one_attempt(self):
        opener = MagicMock()
        opener.open.side_effect = TimeoutError('synthetic timeout')
        with patch.object(c, 'build_opener', return_value=opener), patch.object(c, 'utc_now',
                side_effect=['2026-10-08T00:00:00Z', '2026-10-08T00:00:20Z']):
            result = c._fetch('https://quotes.sina.cn/x')
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 20)
        self.assertEqual(result['requested_at'], '2026-10-08T00:00:00Z')
        self.assertEqual(result['retrieved_at'], result['completed_at'])
        self.assertEqual(result['error']['type'], 'TimeoutError')

    def test_http_error_raw_body_and_size_limit_keep_failures(self):
        opener = MagicMock()
        opener.open.side_effect = c.HTTPError('https://quotes.sina.cn/x', 404, 'missing',
                                            {'Content-Type': 'application/json'}, io.BytesIO(b'{"error":"missing"}'))
        with patch.object(c, 'build_opener', return_value=opener):
            result = c._fetch('https://quotes.sina.cn/x')
        self.assertEqual(result['raw_bytes'], b'{"error":"missing"}')
        self.assertEqual(result['http_status'], 404)
        self.assertEqual(opener.open.call_count, 1)
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        response.headers = {'Content-Type': 'application/pdf'}
        response.url = 'https://static.cninfo.com.cn/x'
        response.read.return_value = b'123456789'
        with patch.object(c, 'build_opener', return_value=opener):
            result = c._fetch('https://static.cninfo.com.cn/x', max_bytes=8)
        self.assertEqual(result['raw_bytes'], b'123456789')
        self.assertEqual(result['error']['message'], 'PUBLIC_BODY_SIZE_LIMIT')
        self.assertEqual(opener.open.call_count, 1)

    def test_ranges_canonical_and_compat_clamp(self):
        plan = {'rows': [{'domain': 'PRICE', 'symbol': SYMBOLS[0],
                         'requested_intervals': [{'start': '2026-09-01', 'end': '2026-10-20'}],
                         'intervals': [['2020-01-01', '2020-12-31']]}]}
        self.assertEqual(c.requested_ranges(plan, 'PRICE', SYMBOLS[0], HISTORY_END, '2016-01-01'),
                         [('2026-09-01', '2026-09-30')])
        self.assertEqual(c.requested_ranges(plan, 'PRICE', SYMBOLS[1], HISTORY_END, '2016-01-01'), [])

    def test_incremental_collector_consumes_plan_and_records_blocked_domains(self):
        c.PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='synthetic-collector-test-', dir=c.PRIVATE_ROOT) as directory:
            plan = {'rows': [{'domain': 'PRICE', 'symbol': SYMBOLS[0],
                     'requested_intervals': [{'start': '2026-09-01', 'end': '2026-09-30'}]},
                    {'domain': 'VALUATION', 'symbol': SYMBOLS[0],
                     'requested_intervals': [{'start': '2016-01-01', 'end': HISTORY_END}]}]}
            raw = b'{"data":{"sh603993":{"day":[["2026-09-01","1","2","3","1","10"],["2026-08-31","1","2","3","1","10"]]}}}'
            result = {'url': 'https://proxy.finance.qq.com/x', 'method': 'GET', 'parameters': {},
                      'requested_at': '2026-10-08T00:00:00Z', 'retrieved_at': '2026-10-08T00:00:01Z',
                      'completed_at': '2026-10-08T00:00:01Z', 'http_status': 200, 'content_type': 'application/json',
                      'error': None, 'raw_bytes': raw, 'elapsed_seconds': 1}
            with patch.object(c, 'DOCUMENTS', ()), patch.object(c, '_fetch', side_effect=lambda *a, **k: dict(result)) as fetch:
                output = c.collect_public(directory, plan)
            self.assertEqual(fetch.call_count, 1)
            self.assertIn('2026-09-01,2026-09-30', fetch.call_args.args[1]['param'])
            self.assertEqual(len(output['batches'][0]['records']), 1)
            self.assertEqual(output['blocked_source_requests'][0]['state'], 'BLOCKED_SOURCE_ACCESS')
            self.assertEqual(Path(output['attempts'][0]['raw_ref']['path']).read_bytes(), raw)
            self.assertEqual(Path(output['attempts'][0]['raw_ref']['path']).stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
