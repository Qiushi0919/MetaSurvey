"""Synthetic local input receipts only. Never call a strategy engine/network."""
from copy import deepcopy
from datetime import date,timedelta
from pathlib import Path
import unittest
from unittest.mock import patch
from tools.e2e_gateway.tests import test_builder as fixture
from tools.long_forward import history_raw_input as h
from tools.e2e_gateway import builder as sealed
from tools.e2e_gateway.tests.test_builder import RUN,dump

class HistoryRawInputTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.BuilderTests(methodName='test_valid_rebuild_units_and_v2_identity');self.f.setUp();self.addCleanup(self.f.doCleanups)
        p=deepcopy(sealed.read(sealed.PROTOCOL));p.update(namespace='EXPERIMENT:CORE40:LONG_FORWARD_V1',strategy_id='CORE40_FIXED_NINE_LONG_FORWARD_V1')
        self.proto=self.f.root/'Protocol.json';dump(self.proto,p)
        policy=sealed.read(self.f.source);policy['allowed_purposes']=['LOCAL_HISTORICAL_DIAGNOSTIC'];dump(self.f.source,policy)
        dump(self.f.input,h.INPUT_RULES)
        for name,value in [('PROTOCOL',self.proto),('SOURCE_POLICY',self.f.source),('OWNER',self.f.owner),('CONNECTION',self.f.connection),('INPUT_POLICY',self.f.input)]:
            pat=patch.object(h,name,value);pat.start();self.addCleanup(pat.stop)
    def build(self):return h.build_case(self.f.folder,'SYNTHETIC-RAW',RUN)
    def blocked(self,reason):
        report,c=self.build();self.assertIsNone(c);self.assertEqual(report['status'],'DATA_BLOCKED');self.assertIn(reason,str(report['errors']));return report
    def boundary(self,**changes):
        first=self.f.open[0];record=(date.fromisoformat(self.f.start)-timedelta(days=1)).strftime('%Y%m%d')
        row={'ts_code':self.f.symbols[0],'div_proc':'实施','ex_date':first.replace('-',''),'record_date':record,'pay_date':first.replace('-',''),'div_listdate':None,'cash_div_tax':'0.20','stk_div':'0','stk_bo_rate':None,'stk_co_rate':None}
        row.update(changes);self.f.mutate('dividend',lambda rows:[row]);return row
    def test_copy_is_independent_and_no_engine_invocation(self):
        before=(sealed.PROTOCOL,sealed.read,sealed.build_case)
        with patch('experiments.long_forward_v1.engine.run_diagnostic',side_effect=AssertionError('NO ENGINE')):
            report,c=self.build()
        self.assertIsNotNone(c,report['errors']);self.assertEqual(c['mode'],'HISTORY');self.assertEqual(before,(sealed.PROTOCOL,sealed.read,sealed.build_case))
    def test_forward_or_prior_portfolio_rejected(self):
        for kwargs in ({'mode':'FORWARD_A'},{'prior':{}},{'mode':'UNKNOWN'}):
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(ValueError,'HISTORY_ONLY'):
                h.build_case(Path('/not-read'),'x',RUN,**kwargs)
    def test_policy_exact_required(self):
        policy=deepcopy(h.INPUT_RULES);policy['raw_bridge']='TOLERATE';dump(self.f.input,policy);self.blocked('POLICY_MISMATCH')
    def test_permission_not_inferred(self):
        p=sealed.read(self.f.source);p['allowed_purposes']=[];dump(self.f.source,p);self.blocked('PURPOSE_NOT_AUTHORIZED')
    def test_factor_quarantined_full_inventory_and_anomaly(self):
        self.f.mutate('adj_factor',lambda rows:rows[-1].update(adj_factor='1.001'))
        report,c=self.build();self.assertIsNotNone(c,report['errors']);self.assertEqual(len(report['factor_inventory']),9)
        self.assertEqual(len(report['factor_action_anomalies']),1);self.assertEqual(c['factor_status'],'QUARANTINED_NOT_USED')
        self.assertEqual(len(report['factor_inventory'][0]['rows']),len(self.f.open));self.assertEqual(c['actions'],[])
        self.assertTrue(all(b['factor_status']=='QUARANTINED_NOT_USED' for b in c['bars']))
    def test_factor_anomalies_all_symbols_survive_raw_bridge_failure(self):
        for sym in self.f.symbols:self.f.mutate('adj_factor',lambda rows:rows[-1].update(adj_factor='1.001'),sym)
        self.f.mutate('daily',lambda rows:rows[-1].update(pre_close='9.8'))
        self.f.mutate('stk_limit',lambda rows:rows[-1].update(pre_close=None))
        report=self.blocked('UNEXPLAINED_PRECLOSE');self.assertEqual(len(report['factor_action_anomalies']),9)
    def test_factor_cannot_invent_cash_action_or_bridge(self):
        self.f.mutate('adj_factor',lambda rows:rows[-1].update(adj_factor='2'))
        self.f.mutate('daily',lambda rows:rows[-1].update(pre_close='9.9'))
        self.f.mutate('stk_limit',lambda rows:rows[-1].update(pre_close='9.9'));self.blocked('UNEXPLAINED_PRECLOSE')
    def test_factor_raw_tamper_still_rejected(self):
        (self.f.folder/('adj_factor-'+self.f.symbols[0]+'.raw.json')).write_text('{}');self.blocked('RAW_PIN_MISMATCH')
    def test_invalid_factor_shape_not_silently_discarded(self):
        self.f.mutate('adj_factor',lambda rows:rows[-1].update(adj_factor='NaN'));self.blocked('FINITE_DECIMAL')
    def test_missing_limit_reference_is_null_not_daily_copy(self):
        self.f.mutate('stk_limit',lambda rows:rows[1].update(pre_close=None))
        report,c=self.build();self.assertIsNotNone(c,report['errors']);b=c['bars'][1]
        self.assertIsNone(b['limit_pre_close']);self.assertFalse(b['limit_reference_crosscheck_verified']);self.assertEqual(b['pre_close'],'10')
        self.assertEqual(b['lower_limit'],'9');self.assertEqual(b['upper_limit'],'11')
        self.assertIsNone(report['limit_pre_close_semantic_inventory'][0]['limit_pre_close'])
    def test_null_reference_cannot_admit_null_actual_bound(self):
        self.f.mutate('stk_limit',lambda rows:rows[1].update(pre_close=None,up_limit=None));self.blocked('EXACT_DECIMAL')
    def test_null_reference_cannot_admit_zero_actual_bound(self):
        self.f.mutate('stk_limit',lambda rows:rows[1].update(pre_close=None,down_limit='0'));self.blocked('ACTUAL_LIMIT_INVALID')
    def test_nonnull_wrong_limit_reference_still_rejected(self):
        self.f.mutate('stk_limit',lambda rows:rows[1].update(pre_close='9.99'));self.blocked('LIMIT_DAILY_PRECLOSE_CONFLICT')
    def test_null_reference_missing_bar_not_suspension_evidence(self):
        self.f.mutate('stk_limit',lambda rows:rows[1].update(pre_close=None));self.f.mutate('daily',lambda rows:rows[:1]+rows[2:]);self.blocked('MISSING_BAR_WITHOUT_FULL_DAY_SUSPENSION')
    def test_boundary_retains_complete_event_no_executable_entitlement(self):
        row=self.boundary();report,c=self.build();self.assertIsNotNone(c,report['errors'])
        self.assertEqual(c['actions'],[]);self.assertEqual(c['initial_positions'],[]);self.assertEqual(c['initial_receivables'],[])
        event=c['boundary_prehistory_actions'][0];self.assertEqual(event['status'],'BOUNDARY_PREHISTORY')
        self.assertEqual(event['action']['cash_per_share'],'0.20');self.assertEqual(event['action']['record_date'],h.day(row['record_date']))
        self.assertFalse(event['previous_price_bridge_observed']);self.assertEqual(event['disclosures'][0]['source_row_hash'],h.digest({k:row.get(k) for k in sorted(set(row)|sealed.REQUIRED_FIELDS['dividend'])}))
        self.assertEqual(len(c['bars']),9*len(self.f.open));self.assertEqual(report['boundary_prehistory_actions'],c['boundary_prehistory_actions'])
    def test_boundary_not_allowed_later_than_first_captured_session(self):
        self.boundary(ex_date=self.f.open[1].replace('-',''),pay_date=self.f.open[1].replace('-',''));self.blocked('ACTION_RECORD_EX_BOUNDARY_UNSUPPORTED')
    def test_boundary_payment_after_target_rejected(self):
        self.boundary(pay_date='20271001');self.blocked('PREHISTORY_ACTION_NOT_SETTLED')
    def test_boundary_bonus_listing_after_target_rejected(self):
        self.boundary(stk_div='0.2',div_listdate='20271001');self.blocked('PREHISTORY_ACTION_NOT_SETTLED')
    def test_boundary_payment_equal_target_start_rejected(self):
        target=sealed.read(self.proto)['target_window']['start'].replace('-','')
        self.boundary(pay_date=target);self.blocked('PREHISTORY_ACTION_NOT_SETTLED')
    def test_boundary_bonus_listing_equal_target_start_rejected(self):
        target=sealed.read(self.proto)['target_window']['start'].replace('-','')
        self.boundary(stk_div='0.2',div_listdate=target);self.blocked('PREHISTORY_ACTION_NOT_SETTLED')
    def test_boundary_missing_required_payment_still_rejected(self):
        self.boundary(pay_date=None);self.blocked('CASH_PAYMENT_DATE_REQUIRED')
    def test_action_without_factor_change_keeps_actual_cash_and_exact_bridge(self):
        self.f.action();self.f.mutate('adj_factor',lambda rows:[dict(r,adj_factor='1') for r in rows])
        report,c=self.build();self.assertIsNotNone(c,report['errors']);self.assertEqual(len(c['actions']),1);self.assertEqual(c['actions'][0]['cash_per_share'],'0.2');self.assertEqual(len(report['factor_action_anomalies']),1)
    def test_differentiated_cash_not_inferred_from_price(self):
        self.f.action();ex=self.f.open[40].replace('-','')
        self.f.mutate('daily',lambda rows:[dict(r,pre_close='9.81') if r['trade_date']==ex else r for r in rows])
        self.f.mutate('stk_limit',lambda rows:[dict(r,pre_close=None) if r['trade_date']==ex else r for r in rows]);self.blocked('UNEXPLAINED_PRECLOSE')
    def reference_fixture(self):
        ex=self.f.action();record=self.f.open[39]
        self.f.mutate('daily',lambda rows:[dict(r,pre_close='9.81') if r['trade_date']==ex.replace('-','') else r for r in rows])
        self.f.mutate('stk_limit',lambda rows:[dict(r,pre_close=None) if r['trade_date']==ex.replace('-','') else r for r in rows])
        item={'symbol':self.f.symbols[0],'ex_date':ex,'record_date':record,'pay_date':'2027-10-01',
              'cash_per_share':'0.2','bonus_ratio':'0','reference_cash_per_share':'0.19',
              'source_sha256':'sha256:'+'a'*64,'receipt_sha256':'sha256:'+'b'*64,
              'source_url':'https://synthetic.invalid/official.pdf','source_page_1based':4}
        policy=deepcopy(h.INPUT_RULES);policy['official_reference_adjustments']=[item];dump(self.f.input,policy)
        return {(item['symbol'],ex):dict(item,evidence_ref='synthetic-official-pdf')}
    def test_official_reference_only_changes_raw_bridge_not_real_cash(self):
        refs=self.reference_fixture();report,c=h.build_case(self.f.folder,'reference-fixture',RUN,reference_adjustments=refs)
        self.assertIsNotNone(c,report['errors']);self.assertEqual(c['actions'][0]['cash_per_share'],'0.2')
        self.assertNotIn('reference_cash_per_share',c['actions'][0]);self.assertEqual(report['official_reference_adjustments_applied'][0]['reference_cash_per_share'],'0.19')
        bar=next(b for b in c['bars'] if b['symbol']==self.f.symbols[0] and b['session']==self.f.open[40])
        self.assertEqual(bar['pre_close'],'9.81');self.assertEqual(bar['reference_adjustment_evidence_ref'],'synthetic-official-pdf')
    def test_declared_reference_not_auto_applied_without_evidence_map(self):
        self.reference_fixture();self.blocked('UNEXPLAINED_PRECLOSE')
    def test_reference_wrong_original_hash_rejected(self):
        refs=self.reference_fixture();next(iter(refs.values()))['source_sha256']='sha256:'+'f'*64
        report,c=h.build_case(self.f.folder,'reference-fixture',RUN,reference_adjustments=refs);self.assertIsNone(c);self.assertIn('POLICY_BINDING',str(report['errors']))
    def test_reference_actual_action_cash_mismatch_rejected(self):
        refs=self.reference_fixture();self.f.mutate('dividend',lambda rows:rows[0].update(cash_div_tax='0.21'))
        report,c=h.build_case(self.f.folder,'reference-fixture',RUN,reference_adjustments=refs);self.assertIsNone(c);self.assertIn('ACTION_IDENTITY',str(report['errors']))
    def test_reference_record_date_mismatch_rejected(self):
        refs=self.reference_fixture();item=next(iter(refs.values()));item['record_date']=self.f.open[38]
        policy=deepcopy(h.INPUT_RULES);policy['official_reference_adjustments']=[{k:v for k,v in item.items() if k!='evidence_ref'}];dump(self.f.input,policy)
        report,c=h.build_case(self.f.folder,'reference-fixture',RUN,reference_adjustments=refs);self.assertIsNone(c);self.assertIn('ACTION_IDENTITY',str(report['errors']))
    def test_reference_cannot_change_other_raw_price_bridge(self):
        refs=self.reference_fixture();self.f.mutate('daily',lambda rows:rows[-1].update(pre_close='9.79'));self.f.mutate('stk_limit',lambda rows:rows[-1].update(pre_close=None))
        report,c=h.build_case(self.f.folder,'reference-fixture',RUN,reference_adjustments=refs);self.assertIsNone(c);self.assertIn('UNEXPLAINED_PRECLOSE',str(report['errors']))
    def test_unused_reference_does_not_silently_claim_application(self):
        refs=self.reference_fixture();item=next(iter(refs.values()));item['ex_date']='2099-01-01';refs={(item['symbol'],item['ex_date']):item}
        policy=deepcopy(h.INPUT_RULES);policy['official_reference_adjustments']=[{k:v for k,v in item.items() if k!='evidence_ref'}];dump(self.f.input,policy)
        # Restore normal source reference so the unused-map guard is reached.
        ex=self.f.open[40].replace('-','');self.f.mutate('daily',lambda rows:[dict(r,pre_close='9.8') if r['trade_date']==ex else r for r in rows])
        report,c=h.build_case(self.f.folder,'reference-fixture',RUN,reference_adjustments=refs);self.assertIsNone(c);self.assertIn('NOT_APPLIED',str(report['errors']))
    def test_scope_and_dates_cannot_be_cropped(self):
        self.f.mutate('trade_cal',lambda rows:rows[1:],'SSE');self.blocked('FULL_CIVIL_CALENDAR_REQUIRED')

if __name__=='__main__':unittest.main()
