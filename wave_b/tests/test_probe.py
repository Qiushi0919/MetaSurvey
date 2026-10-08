import copy, unittest
from unittest.mock import patch
from wave_b import probe
from wave_b.core import canonical, SYMBOLS, START, END

class ProbeTests(unittest.TestCase):
    def setUp(self): self.plan=probe.fixed_plan()
    def spec(self,api):return next(q for q in self.plan if q['api_name']==api)
    def payload(self,spec,rows):return canonical({'code':0,'msg':'SYNTHETIC','data':{'fields':spec['fields'],'items':[[r.get(k) for k in spec['fields']] for r in rows]}})
    def test_finite_novel_plan_preserves_window_and_does_not_repeat_daily_or_calendar(self):
        self.assertEqual(len(self.plan),55);self.assertEqual({q['ts_code'] for q in self.plan},set(SYMBOLS))
        self.assertFalse(any(q['api_name'] in ('daily','trade_cal') for q in self.plan))
        self.assertTrue(all(START<=q['date_scope']['start']<=q['date_scope']['end']<=END for q in self.plan))
    def test_endpoint_api_symbol_scope_and_extra_parameter_rejected_before_transport(self):
        for change in ({'api_name':'anns_d'},{'ts_code':'000001.SZ'},{'max_rows':True},{'params':{'ts_code':SYMBOLS[0],'ts_type_name':'https://example.invalid/'}},{'extra':'unapproved'}):
            s=copy.deepcopy(self.plan[0]);s.update(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'UNAPPROVED_REQUEST_SCOPE'):probe.validate_spec(s)
    def test_financial_ann_date_does_not_replace_report_period_filter(self):
        s=self.spec('fina_indicator');r={'ts_code':s['ts_code'],'ann_date':'20250825','end_date':'20221231','eps':'0.1'}
        a=probe.analyze(s,self.payload(s,[r]),'2026-10-06T03:00:00Z')
        self.assertTrue(a['response_blocked']);self.assertIn('ROW_DATE_OUT_OF_SCOPE_OR_UNKNOWN',a['reason_codes']);self.assertEqual(a['rows'][0]['values']['end_date'],'20221231')
    def test_one_bad_symbol_quarantines_whole_response_and_retains_valid_sibling(self):
        s=self.spec('stock_st');rows=[{'ts_code':s['ts_code'],'trade_date':START},{'ts_code':'000001.SZ','trade_date':START}]
        a=probe.analyze(s,self.payload(s,rows),'2026-10-06T03:00:00Z');self.assertTrue(a['response_blocked']);self.assertEqual(len(a['rows']),2)
    def test_empty_status_is_access_not_complete_negative_proof(self):
        for api in ('stock_st','suspend_d'):
            s=self.spec(api);a=probe.analyze(s,self.payload(s,[]),'2026-10-06T03:00:00Z')
            self.assertFalse(a['negative_status_proven']);self.assertFalse(a['scope_complete']);self.assertTrue(a['technical_access_observed'])
    def test_future_implementation_publication_is_blocked_not_deleted(self):
        s=self.spec('dividend');r={'ts_code':s['ts_code'],'ex_date':s['params']['ex_date'],'imp_ann_date':'20261007'}
        a=probe.analyze(s,self.payload(s,[r]),'2026-10-06T03:00:00Z');self.assertTrue(a['response_blocked']);self.assertEqual(a['row_count'],1)
    def test_blank_industry_end_date_preserved_invalid_not_null_or_infinity(self):
        s=self.spec('index_member_all');r={'ts_code':s['ts_code'],'in_date':'20200101','out_date':'','is_new':s['params']['is_new']}
        a=probe.analyze(s,self.payload(s,[r]),'2026-10-06T03:00:00Z');self.assertIn('INVALID_MEMBERSHIP_DATE_LITERAL',a['reason_codes']);self.assertEqual(a['rows'][0]['values']['out_date'],'')
    def test_json_numbers_retained_as_exact_decimal_strings(self):
        s=self.spec('adj_factor');raw=self.payload(s,[{'ts_code':s['ts_code'],'trade_date':s['params']['trade_date'],'adj_factor':'1.000000000000000001'}])
        self.assertEqual(probe.analyze(s,raw,'2026-10-06T03:00:00Z')['rows'][0]['values']['adj_factor'],'1.000000000000000001')
    def test_redirect_handler_denies_without_new_request(self):
        with self.assertRaisesRegex(ValueError,'AUTH_REDIRECT_BLOCKED'):probe.NoRedirect().redirect_request(None,None,302,'Found',{},'https://example.invalid/')
    def test_fingerprint_changes_for_authorized_distinct_period_or_source_raw_bytes(self):
        a,b=[q for q in self.plan if q['api_name']=='fina_indicator'][:2]
        self.assertNotEqual(probe.fingerprint(a),probe.fingerprint(b))
        self.assertNotEqual(probe.sha(b'{"x":1}'),probe.sha(b'{"x":2}'))

if __name__=='__main__':unittest.main()

class ProducerIdentityRegression(unittest.TestCase):
    def test_loader_reuses_same_credential_class_without_reading_secret(self):
        import wave_b.probe as p
        self.assertIs(p._old_probe().Credential,p._old_probe().Credential)
    def test_invalid_credential_does_not_increment_network_counter(self):
        import wave_b.probe as p
        before=p._NETWORK_REQUESTS
        with self.assertRaisesRegex(ValueError,'CREDENTIAL_TYPE_INVALID'):p._send(p.fixed_plan()[0],object())
        self.assertEqual(p._NETWORK_REQUESTS,before)
