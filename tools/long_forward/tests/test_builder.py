"""Synthetic archived captures only; no market, credential or private archive use."""
from copy import deepcopy
from datetime import date,timedelta
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.e2e_gateway.tests import test_builder as legacy_fixture
from tools.e2e_gateway.tests.test_builder import RUN, STAMP, dump
from tools.e2e_gateway.capture import FIELDS
from tools.long_forward import builder as b
from experiments.long_forward_v1.engine import RULES,digest

class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.f=legacy_fixture.BuilderTests(methodName='test_valid_rebuild_units_and_v2_identity');self.f.setUp();self.addCleanup(self.f.doCleanups)
        p=deepcopy(b.old.read(b.old.PROTOCOL));p.update(namespace='EXPERIMENT:CORE40:LONG_FORWARD_V1',strategy_id='CORE40_FIXED_NINE_LONG_FORWARD_V1',rules_hash=digest(RULES),method_ref=b.old.rawhash(b.old.METHOD),members={m['symbol']:g['id'] for g in b.old.read(b.old.METHOD)['universe'] for m in g['members']})
        p['forward']={'warmup_start':self.f.start,'first_decision_session':p['target_window']['start'],'bootstrap_delayed_entry':True}
        policy=b.old.read(self.f.source);policy['allowed_purposes']=['LOCAL_HISTORICAL_DIAGNOSTIC','LOCAL_FORWARD_VIRTUAL_LEDGER'];dump(self.f.source,policy)
        self.p=p;self.proto=self.f.root/'Protocol.json';dump(self.proto,p)
        for name,value in [('PROTOCOL',self.proto),('POLICY',self.f.source),('OWNER',self.f.owner)]:
            patcher=patch.object(b,name,value);patcher.start();self.addCleanup(patcher.stop)
        original=b._adapter
        def adapted(protocol):
            module=original(protocol);module.CONNECTION=self.f.connection;module.INPUT_POLICY=self.f.input;return module
        patcher=patch.object(b,'_adapter',side_effect=adapted);patcher.start();self.addCleanup(patcher.stop)
        self.aux()
    def aux(self):
        self.f.manifest['auxiliary_calendar']=[]
        first=date.fromisoformat(self.f.end);end=first+timedelta(days=10)
        for exchange in ('SSE','SZSE'):
            fields=FIELDS['trade_cal'].split(',');rows=[]
            for offset in range(11):
                day=first+timedelta(days=offset);row={'exchange':exchange,'cal_date':day.strftime('%Y%m%d'),'is_open':int(day.weekday()<5),'pretrade_date':None};rows.append([row.get(k) for k in fields])
            raw=self.f.folder/('aux-'+exchange+'.raw.json');path=self.f.folder/('aux-'+exchange+'.json')
            obj={'api_name':'trade_cal','params':{'exchange':exchange,'start_date':first.strftime('%Y%m%d'),'end_date':end.strftime('%Y%m%d')},
                'request_fields':FIELDS['trade_cal'],'fields':fields,'items':rows,'row_count':len(rows),'state':'SUCCESS','error_code':0,'http_status':200,
                'raw_path':raw.name,'request_started_at':STAMP,'retrieved_at':STAMP}
            self.f.write_pair(path,obj);self.f.manifest['auxiliary_calendar'].append(self.f.entry(path,obj))
        self.f.flush()
    def build(self,mode='FORWARD_A',prior=None):return b.build_case(self.f.folder,'SYNTHETIC-LF',RUN,mode,prior)
    def blocked(self,contains=None):
        report,case=self.build();self.assertTrue(case is None, {'status':report['status'],'errors':report['errors']})
        self.assertEqual(report['status'],'DATA_BLOCKED')
        if contains:self.assertIn(contains,str(report['errors']))
    def mutate_aux(self,fn,raw_fn=None):
        path=self.f.folder/'aux-SSE.json';obj=b.old.read(path);fn(obj);self.f.write_pair(path,obj)
        if raw_fn:
            raw=self.f.folder/obj['raw_path'];value=b.old.read(raw);raw_fn(value);dump(raw,value);obj['raw_sha256']=b.old.rawhash(raw);dump(path,obj)
        self.f.manifest['auxiliary_calendar'][0]=self.f.entry(path,obj);self.f.flush()
    def future_action(self,**changes):
        dates=[date.fromisoformat(self.f.end)+timedelta(days=n) for n in range(1,11)]
        opened=[d for d in dates if d.weekday()<5];record,ex=opened[:2]
        row={'ts_code':self.f.symbols[0],'div_proc':'实施','record_date':record.strftime('%Y%m%d'),'ex_date':ex.strftime('%Y%m%d'),
            'pay_date':ex.strftime('%Y%m%d'),'div_listdate':None,'cash_div_tax':'0.20','stk_div':'0','stk_bo_rate':None,'stk_co_rate':None,
            'ann_date':'20260920','imp_ann_date':'20260925','end_date':'20260630'}
        row.update(changes);self.f.mutate('dividend',lambda rows:[row]);return row
    def test_history_success_and_isolated_parser_does_not_mutate_old_module(self):
        before=(b.old.PROTOCOL,b.old.SOURCE_POLICY,b.old.OWNER,b.old.read,b.old.rawhash)
        report,case=self.build('HISTORY');self.assertIsNotNone(case,report['errors']);self.assertEqual(case['protocol_ref'],digest(self.p))
        self.assertEqual((b.old.PROTOCOL,b.old.SOURCE_POLICY,b.old.OWNER,b.old.read,b.old.rawhash),before)
        self.assertEqual(b.old.build_case(self.f.folder,'legacy-still-original',RUN)[1]['namespace'],'EXPERIMENT:CORE40:E2E_HISTORY_V2')
    def test_forward_purpose_must_be_explicitly_authorized(self):
        policy=b.old.read(self.f.source);policy['allowed_purposes']=['LOCAL_HISTORICAL_DIAGNOSTIC'];dump(self.f.source,policy)
        with self.assertRaisesRegex(ValueError,'MODE_PURPOSE_NOT_AUTHORIZED'):self.build()
    def test_forward_auxiliary_calendar_actual_proof_and_prefix(self):
        report,c=self.build();self.assertIsNotNone(c,report['errors']);self.assertEqual(c['mode'],'FORWARD_A');self.assertTrue(c['execution_calendar'])
        self.assertTrue(all(key.startswith(self.f.folder.name+'/') for key in c['evidence']))
        self.assertEqual(c['evidence_grade'],'CURRENT_OBSERVED_FORWARD')
    def test_auxiliary_raw_tamper_rejected(self):
        (self.f.folder/'aux-SSE.raw.json').write_text('{}');self.blocked('AUX_RAW_HASH')
    def test_auxiliary_symlink_rejected(self):
        raw=self.f.folder/'aux-SSE.raw.json';outside=self.f.root/'outside.json';raw.rename(outside);raw.symlink_to(outside);self.blocked('CAPTURE_ALIAS')
    def test_auxiliary_false_code_is_not_integer_zero(self):
        self.mutate_aux(lambda o:o.update(error_code=False),lambda r:r.update(code=False));self.blocked()
    def test_auxiliary_rowcount_must_match_real_rows(self):
        self.mutate_aux(lambda o:o.update(row_count=999));self.blocked()
    def test_auxiliary_request_fields_must_match_frozen_fields(self):
        self.mutate_aux(lambda o:o.update(request_fields='cal_date'));self.blocked()
    def test_auxiliary_duplicate_fields_rejected(self):
        def change(o):
            o['fields'].append(o['fields'][-1])
            for row in o['items']:row.append(row[-1])
        self.mutate_aux(change);self.blocked()
    def test_auxiliary_long_row_cannot_be_silently_truncated(self):
        self.mutate_aux(lambda o:o['items'][0].append('IGNORED_EXTRA'));self.blocked()
    def test_auxiliary_unknown_request_parameter_rejected(self):
        self.mutate_aux(lambda o:o['params'].update(unknown_scope='anything'));self.blocked()
    def test_future_action_known_total_nullable_breakdown(self):
        row=self.future_action();report,c=self.build();self.assertIsNotNone(c,report['errors'])
        self.assertEqual(c['actions'][0]['cash_per_share'],'0.20');self.assertTrue(c['actions'][0]['ex_date']>c['calendar'][-1]['date'])
    def test_future_action_missing_cash_blocks(self):self.future_action(cash_div_tax=None);self.blocked()
    def test_future_action_missing_payment_blocks(self):self.future_action(pay_date=None);self.blocked()
    def test_future_action_nonzero_component_conflicts_with_zero_total(self):self.future_action(stk_bo_rate='0.1');self.blocked()
    def test_future_action_negative_component_rejected(self):self.future_action(stk_co_rate='-1');self.blocked()
    def test_future_action_payment_before_ex_rejected(self):self.future_action(pay_date='20260901');self.blocked()
    def test_unknown_future_action_process_rejected(self):self.future_action(div_proc='UNKNOWN');self.blocked('ACTION_PROCESS_UNKNOWN')
    def test_implemented_unknown_future_ex_date_rejected(self):self.future_action(ex_date=None);self.blocked('IMPLEMENTED_ACTION_EX_DATE_MISSING')
    def test_prefix_merge_preserves_source_refs_and_rejects_revised_price(self):
        report,c=self.build();self.assertIsNotNone(c,report['errors']);prior=deepcopy(c);new=deepcopy(c);new['bars'][0]['close']='999'
        with self.assertRaisesRegex(ValueError,'PREVIOUS_OBSERVATION_REVISED'):b._merge_prefix(new,prior)
        new=deepcopy(c);b._merge_prefix(new,prior);self.assertEqual(new,prior)
    def test_prefix_civil_calendar_open_status_change_rejected(self):
        report,c=self.build();self.assertIsNotNone(c,report['errors']);prior=deepcopy(c);new=deepcopy(c)
        new['calendar_coverage']['days'][0]['is_open']=not new['calendar_coverage']['days'][0]['is_open']
        with self.assertRaisesRegex(ValueError,'PREVIOUS_'):b._merge_prefix(new,prior)
    def test_prefix_evidence_key_collision_cannot_overwrite_new_proof(self):
        report,c=self.build();self.assertIsNotNone(c,report['errors']);prior=deepcopy(c);new=deepcopy(c)
        key=next(iter(new['evidence']));new['evidence'][key]['source_version']='changed'
        with self.assertRaisesRegex(ValueError,'EVIDENCE'):b._merge_prefix(new,prior)


class CaptureGuardTests(unittest.TestCase):
    """Only invalid arguments, with credential loader hard-blocked by mock."""
    def setUp(self):
        import tempfile
        from tools.long_forward import capture
        self.c=capture;self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name).resolve();(root/'config/provider').mkdir(parents=True);(root/'experiments/long_forward_v1').mkdir(parents=True)
        dump(root/'config/provider/tushare-monthly-gateway.json',{'endpoint':'http://synthetic.invalid'})
        self.p={'target_window':{'warmup_start':'2021-06-01','start':'2021-10-01','end':'2026-09-30'},'members':{'SYNTHETIC':'GROUP'},
                'forward':{'warmup_start':'2026-06-01','first_decision_session':'2026-10-14','current_owner_asserted_source_validity_end':'2026-11-05'}}
        dump(root/'experiments/long_forward_v1/protocol.json',self.p)
        for key,value in [('ROOT',root),('ARCHIVE',root/'private'),('_credential_module',lambda:(_ for _ in ()).throw(AssertionError('CREDENTIAL_LOADER_MUST_NOT_BE_REACHED')))]:
            patcher=patch.object(capture,key,value);patcher.start();self.addCleanup(patcher.stop)
    def test_path_traversal_epoch_rejected_without_credential_access(self):
        with self.assertRaises(ValueError):self.c.capture('20210601','20260930','../escape')
    def test_pre_authorized_coverage_start_rejected_without_credential_access(self):
        with self.assertRaises(ValueError):self.c.capture('20200101','20260930','capture-invalid')
    def test_unknown_priority_rejected_before_credential_access(self):
        with self.assertRaises(ValueError):self.c.capture('20210601','20260930','capture-invalid',priority='unregistered')
    def test_history_scope_cannot_select_shorter_window_before_credential_access(self):
        with self.assertRaises(ValueError):self.c.capture('20220601','20260930','capture-invalid')
    def test_future_ohlc_scope_rejected_before_credential_access(self):
        with self.assertRaises(ValueError):self.c.capture('20260601','20990101','capture-invalid',priority='forward',future_end='20990105')
    def test_backward_future_calendar_scope_rejected_before_credential_access(self):
        with self.assertRaises(ValueError):self.c.capture('20260601','20261014','capture-invalid',priority='forward',future_end='20261001')

if __name__=='__main__':unittest.main()
