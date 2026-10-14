"""Synthetic archives only. No market requests, credentials or private evidence."""
import copy
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.e2e_gateway import builder as b

STAMP = '2026-10-14T09:00:00+00:00'
RUN = '2026-10-14T09:01:00+00:00'

def dump(path, obj): path.write_text(json.dumps(obj,ensure_ascii=False))

class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve(); self.folder = self.root/'capture'; self.folder.mkdir()
        self.owner = self.root/'Owner.md'; self.owner.write_text('SYNTHETIC_TEST_ONLY')
        self.source = self.root/'Source.json'; self.connection = self.root/'Connection.json'
        self.input = self.root/'Input.json'; dump(self.input, {'synthetic': True})
        dump(self.connection, {'endpoint':'http://synthetic.invalid','source_classification':'OWNER_PROVIDED_MONTHLY_GATEWAY'})
        dump(self.source, {'kind':'GatewayLocalResearchPolicy','fixture_scope':'SYNTHETIC_TEST_ONLY','version':'3.0.0','purpose':'LOCAL_HISTORICAL_DIAGNOSTIC','permission_state':b.PERMISSION,'source_classification':'OWNER_PROVIDED_MONTHLY_GATEWAY','endpoint':'http://synthetic.invalid','owner_authorization_ref':b.rawhash(self.owner),'connection_config_hash':b.rawhash(self.connection),'supplier_identity_verified':False,'license_verified':False,'historical_visibility_proven':False,'public_raw_distribution':False,'cloud_transfer':False})
        for key,value in [('SOURCE_POLICY',self.source),('CONNECTION',self.connection),('OWNER',self.owner),('INPUT_POLICY',self.input)]:
            p=patch.object(b,key,value);p.start();self.addCleanup(p.stop)
        proto=b.read(b.PROTOCOL);target=proto['target_window']; self.start=target['warmup_start'];self.end=target['end']
        self.days=[];d=date.fromisoformat(self.start)
        while d<=date.fromisoformat(self.end): self.days.append(d.isoformat());d+=timedelta(days=1)
        self.open=[d for d in self.days if date.fromisoformat(d).weekday()<5]
        self.symbols=[m['symbol'] for g in b.read(b.METHOD)['universe'] for m in g['members']]
        self.manifest={'kind':'GatewayCaptureManifest','version':'1.0.0','scope':{'symbols':self.symbols,'start_date':self.start.replace('-',''),'end_date':self.end.replace('-','')},'endpoint':'http://synthetic.invalid','owner_authorization_ref':b.rawhash(self.owner),'provider_license_status':'OWNER_AUTHORIZED_LOCAL_USE_UNVERIFIED_PROVIDER_LICENSE','started_at':STAMP,'retrieved_at':STAMP,'sources':[],'historical_visibility_proven':False,'public_raw_distribution':False,'cloud_transfer':False,'state':'CAPTURE_COMPLETE'}
        for exchange in ('SSE','SZSE'):
            self.add('trade_cal',exchange,[{'exchange':exchange,'cal_date':d.replace('-',''),'is_open':int(d in self.open)} for d in self.days])
        for sym in self.symbols:
            self.add('stock_basic',sym,[{'ts_code':sym,'exchange':'SSE' if sym.endswith('SH') else 'SZSE','market':'主板','list_status':'L','list_date':'20000101','delist_date':None}])
            self.add('daily',sym,[{'ts_code':sym,'trade_date':d.replace('-',''),'open':'10','high':'10','low':'10','close':'10','pre_close':'10','vol':'10000','amount':'10000'} for d in self.open])
            self.add('stk_limit',sym,[{'ts_code':sym,'trade_date':d.replace('-',''),'pre_close':'10','up_limit':'11','down_limit':'9'} for d in self.open])
            self.add('adj_factor',sym,[{'ts_code':sym,'trade_date':d.replace('-',''),'adj_factor':'1'} for d in self.open])
            self.add('suspend_d',sym,[],['ts_code','trade_date','suspend_timing','suspend_type'])
            self.add('dividend',sym,[],['ts_code','div_proc','ex_date'])
            self.add('namechange',sym,[],['ts_code','name'])
        self.flush()
    def add(self,api,sym,rows,fields=None):
        fields=sorted(set(fields or list(rows[0])) | b.REQUIRED_FIELDS[api]);params={'exchange' if api=='trade_cal' else 'ts_code':sym}
        if api in ('trade_cal','daily','stk_limit','suspend_d','adj_factor'):params.update(start_date=self.start.replace('-',''),end_date=self.end.replace('-',''))
        name=api+'-'+sym;raw=self.folder/(name+'.raw.json');obj={'api_name':api,'params':params,'request_fields':','.join(fields),'fields':fields,'items':[[r.get(k) for k in fields] for r in rows],'row_count':len(rows),'error_code':0,'state':'SUCCESS' if rows else 'EMPTY_RESPONSE','http_status':200,'request_started_at':STAMP,'retrieved_at':STAMP,'raw_path':raw.name}
        path=self.folder/(name+'.json');self.write_pair(path,obj)
        self.manifest['sources'].append(self.entry(path,obj))
    def entry(self,path,obj):return dict(path=path.name,sha256=b.rawhash(path),**{k:obj[k] for k in ('api_name','params','fields','row_count','error_code','state')})
    def write_pair(self,path,obj):
        raw=self.folder/obj['raw_path'];dump(raw,{'code':0,'msg':None,'data':{'fields':obj['fields'],'items':obj['items']}});obj['raw_sha256']=b.rawhash(raw);dump(path,obj)
    def flush(self):dump(self.folder/'Manifest.json',self.manifest)
    def mutate(self,api,fn,sym=None):
        sym=sym or self.symbols[0];path=self.folder/(api+'-'+sym+'.json');obj=b.read(path)
        rows=[dict(zip(obj['fields'],r)) for r in obj['items']];result=fn(rows)
        if result is not None: rows=result
        fields=sorted(set(obj['fields']) | (set(rows[0]) if rows else set()));obj.update(fields=fields,items=[[r.get(k) for k in fields] for r in rows],row_count=len(rows),state='SUCCESS' if rows else 'EMPTY_RESPONSE')
        self.write_pair(path,obj)
        for i,entry in enumerate(self.manifest['sources']):
            if entry['path']==path.name:self.manifest['sources'][i]=self.entry(path,obj)
        self.flush()
    def build(self):return b.build_case(self.folder,'synthetic-fixture',RUN)
    def blocked(self,reason):
        report,case=self.build();self.assertIsNone(case);self.assertEqual(report['status'],'DATA_BLOCKED');self.assertIn(reason,str(report['errors']))
    def action(self,bonus='0'):
        ex=self.open[40];record=self.open[39];cash='0.2';den=1+b.D(bonus);price=str((b.D('10')-b.D(cash))/den)
        self.mutate('dividend',lambda rows:[{'ts_code':self.symbols[0],'div_proc':'实施','ex_date':ex.replace('-',''),'record_date':record.replace('-',''),'pay_date':'20271001','div_listdate':'20271001' if bonus!='0' else None,'cash_div_tax':cash,'stk_div':bonus,'stk_bo_rate':bonus,'stk_co_rate':'0'}])
        def adjust(rows):
            for r in rows:
                if r['trade_date']>=ex.replace('-',''):
                    for key in ('open','high','low','close','pre_close'):r[key]=price
        self.mutate('daily',adjust)
        def limit(rows):
            for r in rows:
                if r['trade_date']>=ex.replace('-',''):r.update(pre_close=price,up_limit='11',down_limit='7')
        self.mutate('stk_limit',limit)
        self.mutate('adj_factor',lambda rows:[dict(r,adj_factor='2' if r['trade_date']>=ex.replace('-','') else '1') for r in rows])
        return ex
    def test_valid_rebuild_units_and_v2_identity(self):
        report,case=self.build();self.assertIsNotNone(case,report);self.assertEqual(case['namespace'],'EXPERIMENT:CORE40:E2E_HISTORY_V2');self.assertEqual(case['bars'][0]['volume_shares'],'1000000');self.assertEqual(case['bars'][0]['amount_CNY'],'10000000');self.assertFalse(report['provider_license_independently_verified']);self.assertTrue(b.verify_provenance(case,self.folder)['verified'])
    def test_synthetic_archive_calls_unchanged_engine(self):
        from experiments.e2e_history_v2.engine import run_diagnostic
        report,case=self.build();self.assertIsNotNone(case,report)
        result=run_diagnostic(case,lambda c:b.verify_provenance(c,self.folder))
        self.assertEqual(result['status'],'RUN_NO_TRADES',result.get('errors'));self.assertTrue(result['engine_called'])
    def test_zero_limits(self):self.mutate('stk_limit',lambda rows:rows[0].update(up_limit='0'));self.blocked('ACTUAL_LIMIT_INVALID')
    def test_null_limits(self):self.mutate('stk_limit',lambda rows:rows[0].update(up_limit=None));self.blocked('EXACT_DECIMAL_REQUIRED')
    def test_missing_limits(self):self.mutate('stk_limit',lambda rows:rows[1:]);self.blocked('ACTUAL_LIMIT_MISSING')
    def test_missing_daily_empty_suspension_is_insufficient(self):self.mutate('daily',lambda rows:rows[1:]);self.blocked('MISSING_BAR_WITHOUT_FULL_DAY_SUSPENSION')
    def test_explicit_full_day_suspension_no_synthetic_price(self):
        self.mutate('daily',lambda rows:rows[1:]);self.mutate('suspend_d',lambda rows:[{'ts_code':self.symbols[0],'trade_date':self.open[0].replace('-',''),'suspend_type':'S','suspend_timing':None}]);report,case=self.build();self.assertIsNotNone(case,report);self.assertEqual(case['bars'][0]['status'],'SUSPENDED');self.assertIsNone(case['bars'][0]['close']);self.assertEqual(case['bars'][0]['volume_shares'],'0')
    def test_intraday_suspension_blocks(self):self.mutate('suspend_d',lambda rows:[{'ts_code':self.symbols[0],'trade_date':self.open[0].replace('-',''),'suspend_type':'S','suspend_timing':'09:30-10:00'}]);self.blocked('INTRADAY_SUSPENSION')
    def test_contradictory_halt_blocks(self):self.mutate('suspend_d',lambda rows:[{'ts_code':self.symbols[0],'trade_date':self.open[0].replace('-',''),'suspend_type':'S','suspend_timing':None}]);self.blocked('SUSPENSION_WITH_TRADING_BAR')
    def test_calendar_cannot_crop(self):self.mutate('trade_cal',lambda rows:rows[1:],'SSE');self.blocked('FULL_CIVIL_CALENDAR_REQUIRED')
    def test_calendar_exchange_mismatch(self):self.mutate('trade_cal',lambda rows:rows[0].update(is_open=0),'SZSE');self.blocked('EXCHANGE_SESSION_MISMATCH')
    def test_security_identity(self):self.mutate('stock_basic',lambda rows:rows[0].update(ts_code='000001.SZ'));self.blocked('MATURE_MAINBOARD_IDENTITY')
    def test_action_causal_bridge_and_future_receivable(self):self.action();report,case=self.build();self.assertIsNotNone(case,report);self.assertEqual(case['actions'][0]['pay_date'],'2027-10-01');self.assertIsNone(case['actions'][0]['shares_available_date'])
    def test_missing_payment_blocks(self):self.action();self.mutate('dividend',lambda rows:rows[0].update(pay_date=None));self.blocked('CASH_PAYMENT_DATE_REQUIRED')
    def test_missing_bonus_listing_blocks(self):self.action('0.4');self.mutate('dividend',lambda rows:rows[0].update(div_listdate=None));self.blocked('BONUS_MARKET_DATE_REQUIRED')
    def test_component_conflict_blocks(self):self.action();self.mutate('dividend',lambda rows:rows[0].update(stk_div='0.1'));self.blocked('ACTION_COMPONENTS_INVALID')
    def test_unexplained_factor_change_blocks(self):self.mutate('adj_factor',lambda rows:rows[-1].update(adj_factor='2'));self.blocked('UNMATCHED_FACTOR_ACTION')
    def test_unexplained_exright_reference_blocks(self):
        self.mutate('daily',lambda rows:rows[-1].update(pre_close='9.8'));self.mutate('stk_limit',lambda rows:rows[-1].update(pre_close='9.8'));self.blocked('UNEXPLAINED_PRECLOSE')
    def test_raw_tamper_blocks(self):
        p=self.folder/('daily-'+self.symbols[0]+'.raw.json');p.write_text('{}');self.blocked('RAW_PIN_MISMATCH')
    def test_wrapper_rehash_cannot_replace_original(self):
        p=self.folder/('daily-'+self.symbols[0]+'.json');obj=b.read(p);obj['items'][0][2]='11';dump(p,obj)
        for entry in self.manifest['sources']:
            if entry['path']==p.name:entry['sha256']=b.rawhash(p)
        self.flush();self.blocked('ORIGINAL_WRAPPER_CONTENT_MISMATCH')
    def test_raw_symlink_blocks(self):
        p=self.folder/('daily-'+self.symbols[0]+'.raw.json');target=self.root/'elsewhere.json';p.rename(target);p.symlink_to(target);self.blocked('CAPTURE_ALIAS_OR_MISSING')
    def test_case_boolean_cannot_admit(self):
        report,case=self.build();case['provider_license_independently_verified']=True
        with self.assertRaises(b.InputError):b.verify_provenance(case,self.folder)
    def test_scope_and_request_pins(self):self.manifest['scope']['symbols']=self.symbols[:-1];self.flush();self.blocked('CAPTURE_SCOPE_OR_AUTHORIZATION')
    def test_owner_source_policy_no_license_promotion(self):
        p=b.read(self.source);p['permission_state']='INDEPENDENTLY_VERIFIED';dump(self.source,p);self.blocked('OWNER_SOURCE_POLICY_SCOPE_MISMATCH')
    def test_source_policy_kind_strict(self):
        p=b.read(self.source);p['kind']='UnknownPolicy';dump(self.source,p);self.blocked('OWNER_SOURCE_POLICY_SCOPE_MISMATCH')
    def test_source_policy_version_strict(self):
        p=b.read(self.source);p['version']='999';dump(self.source,p);self.blocked('OWNER_SOURCE_POLICY_SCOPE_MISMATCH')
    def test_capture_clock_after_run(self):report,case=b.build_case(self.folder,'synthetic-fixture','2026-10-14T08:59:59+00:00');self.assertIsNone(case);self.assertIn('SOURCE_RETRIEVED_AFTER_RUN',str(report['errors']))
    def test_duplicate_daily(self):self.mutate('daily',lambda rows:rows+[rows[0]]);self.blocked('DUPLICATE_DATE')
    def test_unknown_numeric_float_not_accepted(self):self.assertRaises(b.InputError,b.dec,1.2)
    def predecessor(self):
        import shutil
        prior=self.root/'capture-01';self.folder.rename(prior)
        self.folder=self.root/'capture-02';shutil.copytree(prior,self.folder)
        self.manifest['predecessor']={'path':str(prior/'Manifest.json'),'sha256':b.rawhash(prior/'Manifest.json')}
        self.manifest['started_at']='2026-10-14T09:00:10+00:00'
        self.manifest['retrieved_at']='2026-10-14T09:00:20+00:00'
        self.flush();return prior
    def test_inherited_capture_bytes_prove_old_clocks(self):
        self.predecessor();report,case=self.build();self.assertIsNotNone(case,report)
    def test_old_clocks_without_predecessor_rejected(self):
        self.predecessor();self.manifest.pop('predecessor');self.flush();self.blocked('UNPROVEN_INHERITED_CAPTURE_CLOCK')
    def test_inherited_raw_tamper_rejected(self):
        prior=self.predecessor();(prior/('daily-'+self.symbols[0]+'.raw.json')).write_text('{}');self.blocked('RAW_PIN_MISMATCH')
    def test_predecessor_cycle_rejected(self):
        self.predecessor();self.manifest['predecessor']={'path':str(self.folder/'Manifest.json'),'sha256':'sha256:bad'};self.flush();self.blocked('PREDECESSOR_PATH_OR_HASH_INVALID')
    def test_partial_capture_reports_existing_rows(self):
        self.manifest['sources']=[e for e in self.manifest['sources'] if e['api_name'] in ('trade_cal','stock_basic','daily','stk_limit')]
        self.manifest['state']='CAPTURE_PARTIAL';self.flush()
        report,case=self.build();self.assertIsNone(case);self.assertEqual(report['real_input_rows'],len(self.open)*9);self.assertTrue(report['field_coverage']);self.assertTrue(report['missing_products']);self.assertEqual(report['normalized_execution_rows'],0)
    def test_api_failure_reports_exact_products_and_existing_rows(self):
        path=self.folder/('adj_factor-'+self.symbols[0]+'.json');obj=b.read(path)
        raw=self.folder/obj['raw_path'];dump(raw,{'code':-1,'msg':'synthetic limited','data':None})
        obj.update(error_code=-1,state='IP_CONCURRENCY_LIMIT',items=[],fields=[],row_count=0,raw_sha256=b.rawhash(raw));dump(path,obj)
        for i,e in enumerate(self.manifest['sources']):
            if e['path']==path.name:self.manifest['sources'][i]=self.entry(path,obj)
        self.flush();report,case=self.build();self.assertIsNone(case);self.assertIn('IP_CONCURRENCY_LIMIT',str(report['errors']));self.assertEqual(report['captured_daily_rows'],len(self.open)*9)
    def test_empty_fields_are_not_empty_event_proof(self):
        for api in ('suspend_d','dividend','namechange'):
            path=self.folder/(api+'-'+self.symbols[0]+'.json');obj=b.read(path);obj['fields']=[]
            self.write_pair(path,obj)
            for i,e in enumerate(self.manifest['sources']):
                if e['path']==path.name:self.manifest['sources'][i]=self.entry(path,obj)
        self.flush();report,case=self.build();self.assertIsNone(case)
        for api in ('suspend_d','dividend','namechange'):self.assertIn('REQUIRED_RESPONSE_FIELDS_MISSING:'+api,str(report['errors']))
    def test_known_total_with_null_component_not_inferred_zero(self):
        self.action();self.mutate('dividend',lambda rows:rows[0].update(stk_bo_rate=None,stk_co_rate=None));report,case=self.build();self.assertIsNotNone(case,report)
        self.assertEqual(case['actions'][0]['bonus_ratio'],'0');self.assertEqual(report['action_inventory'][0]['disclosures'][0]['stock_components']['stk_bo_rate'],'NOT_REPORTED')
    def test_missing_total_is_not_zero(self):
        self.action();self.mutate('dividend',lambda rows:rows[0].update(stk_div=None));self.blocked('EXACT_DECIMAL_REQUIRED')
    def test_known_positive_total_without_component_breakdown(self):
        self.action('0.4');self.mutate('dividend',lambda rows:rows[0].update(stk_bo_rate=None,stk_co_rate=None));report,case=self.build();self.assertIsNotNone(case,report);self.assertEqual(case['actions'][0]['bonus_ratio'],'0.4')
    def test_nonzero_component_conflicts_with_explicit_zero_total(self):
        self.action();self.mutate('dividend',lambda rows:rows[0].update(stk_bo_rate='0.1',stk_co_rate=None));self.blocked('ACTION_COMPONENTS_INVALID')
    def test_disclosures_merge_once_keep_original_rows(self):
        self.action();self.mutate('dividend',lambda rows:[dict(rows[0],ann_date='20250301'),dict(rows[0],ann_date='20250302')]);report,case=self.build();self.assertIsNotNone(case,report);self.assertEqual(len(case['actions']),1);disclosures=report['action_inventory'][0]['disclosures'];self.assertEqual(len(disclosures),2);self.assertNotEqual(disclosures[0]['source_row_hash'],disclosures[1]['source_row_hash'])
    def test_conflicting_payment_disclosure_blocks(self):
        self.action();self.mutate('dividend',lambda rows:[rows[0],dict(rows[0],pay_date='20271002')]);self.blocked('CONFLICTING_ECONOMIC_ACTION_DISCLOSURES')
    def test_stopped_implementation_preserved_but_not_executed(self):
        self.mutate('dividend',lambda rows:[{'ts_code':self.symbols[0],'div_proc':'停止实施','ex_date':None}]);report,case=self.build();self.assertIsNotNone(case,report);self.assertEqual(case['actions'],[]);self.assertEqual(report['action_inventory'][0]['div_proc'],'停止实施')
    def name_row(self):
        return {'ts_code':self.symbols[0],'name':'SYNTHETIC','start_date':'20000101','end_date':None,'ann_date':None,'change_reason':'synthetic fixture'}
    def test_name_reference_is_not_status_admission(self):
        self.mutate('namechange',lambda rows:[self.name_row()]);report,case=self.build();self.assertIsNotNone(case,report)
        self.assertEqual(report['field_coverage']['namechange:'+self.symbols[0]]['status'],'REFERENCE_ONLY_NOT_HISTORY_STATUS_CERTIFICATION')
    def test_name_identity_conflict(self):
        row=self.name_row();row['ts_code']='000001.SZ';self.mutate('namechange',lambda rows:[row]);self.blocked('NAMECHANGE_IDENTITY_CONFLICT')
    def test_name_invalid_date(self):
        row=self.name_row();row['ann_date']='20009999';self.mutate('namechange',lambda rows:[row]);self.blocked('month must be in')
    def test_name_reversed_dates(self):
        row=self.name_row();row['end_date']='19990101';self.mutate('namechange',lambda rows:[row]);self.blocked('NAMECHANGE_DATE_ORDER_INVALID')
    def test_exact_name_duplicate_preserves_originals(self):
        self.mutate('namechange',lambda rows:[self.name_row(),self.name_row()]);report,case=self.build();self.assertIsNotNone(case,report);info=report['field_coverage']['namechange:'+self.symbols[0]];self.assertEqual(info['observed_rows'],2);self.assertEqual(info['unique_reference_rows'],1);self.assertEqual(info['duplicate_count'],1);self.assertEqual(len(info['disclosures']),2)
    def test_conflicting_name_record_blocks(self):
        self.mutate('namechange',lambda rows:[self.name_row(),dict(self.name_row(),change_reason='different')]);self.blocked('NAMECHANGE_CONFLICTING_RECORD')
    def test_name_rowcap_requires_separate_pagination(self):
        self.mutate('namechange',lambda rows:[self.name_row()]*b.NAMECHANGE_LOCAL_ROW_CAP);self.blocked('NAMECHANGE_LOCAL_ROW_CAP_PAGINATION_REQUIRED')
    def empty_suspend(self, updates=None, raw_code=0):
        path=self.folder/('suspend_d-'+self.symbols[0]+'.json');obj=b.read(path)
        obj.update(fields=[],items=[],row_count=0,state='EMPTY_RESPONSE',request_fields='ts_code,trade_date,suspend_timing,suspend_type')
        obj.update(updates or {})
        self.write_pair(path,obj)
        raw=self.folder/obj['raw_path'];content=b.read(raw);content['code']=raw_code;dump(raw,content);obj['raw_sha256']=b.rawhash(raw);dump(path,obj)
        for i,e in enumerate(self.manifest['sources']):
            if e['path']==path.name:self.manifest['sources'][i]=self.entry(path,obj)
        self.flush()
    def test_exact_empty_suspend_compatibility_retains_uncertainty(self):
        self.empty_suspend();report,case=self.build();self.assertIsNotNone(case,report)
        info=report['field_coverage']['suspend_d:'+self.symbols[0]]
        self.assertEqual(info['schema_status'],'EMPTY_TABLE_SCHEMA_NOT_RETURNED');self.assertIs(info['schema_verified'],False);self.assertIs(info['intraday_halt_absence_proven'],False)
        self.assertEqual(case['input_limitations']['empty_suspension_schema_symbols'],[self.symbols[0]]);self.assertIs(case['bars'][0]['suspension_schema_verified'],False)
        from experiments.e2e_history_v2.engine import run_diagnostic
        result=run_diagnostic(case,lambda c:b.verify_provenance(c,self.folder));self.assertEqual(result['status'],'RUN_NO_TRADES',result.get('errors'))
    def test_empty_suspend_boolean_code_is_not_integer_zero(self):
        self.empty_suspend({'error_code':False},raw_code=False);self.blocked('API_PRODUCT_FAILED')
    def test_empty_suspend_raw_boolean_cannot_match_wrapper_zero(self):
        self.empty_suspend(raw_code=False);self.blocked('ORIGINAL_ERROR_CODE_MISMATCH')
    def test_empty_suspend_string_zero_is_not_integer_zero(self):
        self.empty_suspend({'error_code':'0'},raw_code='0');self.blocked('API_PRODUCT_FAILED')
    def test_empty_suspend_wrong_http_status(self):
        self.empty_suspend({'http_status':201});self.blocked('API_PRODUCT_FAILED')
    def test_empty_suspend_missing_requested_field(self):
        self.empty_suspend({'request_fields':'ts_code,trade_date,suspend_type'});self.blocked('REQUIRED_RESPONSE_FIELDS_MISSING')
    def test_empty_suspend_wrong_requested_field(self):
        self.empty_suspend({'request_fields':'ts_code,trade_date,suspend_timing,unexpected'});self.blocked('REQUIRED_RESPONSE_FIELDS_MISSING')
    def test_empty_suspend_partial_response_schema(self):
        self.empty_suspend({'fields':['ts_code']});self.blocked('REQUIRED_RESPONSE_FIELDS_MISSING')
    def test_empty_suspend_nonempty_bad_response_schema(self):
        self.empty_suspend({'fields':[],'items':[[]],'row_count':1,'state':'SUCCESS'});self.blocked('REQUIRED_RESPONSE_FIELDS_MISSING')
    def test_empty_suspend_missing_actual_daily_blocks(self):
        self.empty_suspend();self.mutate('daily',lambda rows:rows[1:]);self.blocked('EMPTY_SUSPENSION_REQUIRES_FULL_DAILY_LIMIT_FACTOR_COVERAGE')
    def test_empty_suspend_missing_actual_limit_blocks(self):
        self.empty_suspend();self.mutate('stk_limit',lambda rows:rows[1:]);self.blocked('EMPTY_SUSPENSION_REQUIRES_FULL_DAILY_LIMIT_FACTOR_COVERAGE')
    def test_empty_suspend_missing_factor_blocks(self):
        self.empty_suspend();self.mutate('adj_factor',lambda rows:rows[1:]);self.blocked('FULL_FACTOR_CALENDAR_REQUIRED')
    def test_empty_suspend_zero_volume_blocks(self):
        self.empty_suspend();self.mutate('daily',lambda rows:rows[0].update(vol='0'));self.blocked('DAILY_VOLUME_AMOUNT_INVALID')
    def test_empty_suspend_unauthorized_scope_blocks(self):
        self.empty_suspend();path=self.folder/('suspend_d-'+self.symbols[0]+'.json');obj=b.read(path);obj['params']['start_date']='20260101';dump(path,obj)
        for i,e in enumerate(self.manifest['sources']):
            if e['path']==path.name:self.manifest['sources'][i]=self.entry(path,obj)
        self.flush();self.blocked('EXACT_REQUEST_SCOPE_REQUIRED')
    def test_predisclosure_is_audited_not_executed(self):
        self.mutate('dividend',lambda rows:[{'ts_code':self.symbols[0],'div_proc':'预披露','end_date':'20260630','ann_date':'20260820','ex_date':None}]);report,case=self.build();self.assertIsNotNone(case,report);self.assertEqual(case['actions'],[])
        row=report['action_inventory'][0];self.assertEqual(row['div_proc'],'预披露');self.assertEqual(row['disclosure_times']['ann_date'],'2026-08-20');self.assertIsNone(row['disclosure_times']['ex_date']);self.assertTrue(row['source_row_hash'].startswith('sha256:'))
    def test_predisclosure_with_execution_date_conflicts(self):
        self.mutate('dividend',lambda rows:[{'ts_code':self.symbols[0],'div_proc':'预披露','ann_date':'20260820','ex_date':'20260821'}]);self.blocked('PREDISCLOSURE_WITH_EXECUTION_DATES_CONFLICT')
    def test_predisclosure_with_implementation_announcement_conflicts(self):
        self.mutate('dividend',lambda rows:[{'ts_code':self.symbols[0],'div_proc':'预披露','ann_date':'20260820','imp_ann_date':'20260821'}]);self.blocked('PREDISCLOSURE_WITH_EXECUTION_DATES_CONFLICT')
    def test_run_id_rejects_path(self):self.assertIsNone(b.build_case(self.folder,'../escape',RUN)[1])

if __name__=='__main__':unittest.main()
