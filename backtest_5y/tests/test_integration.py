"""Input corruption and frozen-state checks at the runnable sidecar boundary."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from backtest_5y.interface import frozen_spec,SPEC_SHA256,digest,SPEC_PATH
from backtest_5y.requirements import requirements,policy_gaps,evaluate_coverage
from backtest_5y.gateway import plan,_records
from backtest_5y.run import load_packets
from backtest_5y.dto import clock,candidate,validate_candidate,walk_forward_plan

class Integration(unittest.TestCase):
    def packet(self,root):
        request=plan(['daily'])[0]
        body={'code':0,'data':{'fields':['ts_code','trade_date','open','high','low','close','vol'],
             'items':[['603993.SH','20260930','10.00','10.10','9.90','10.05','100']]}}
        raw=json.dumps(body).encode();p=root/'raw.json';p.write_bytes(raw)
        batch={'source':'OWNER_PROVIDED_MONTHLY_GATEWAY','symbol':'603993.SH','domain':'PRICE',
            'request':request,'retrieved_at':'2026-10-08T10:00:00+00:00','source_url':'http://118.89.117.77:8030/',
            'license_state':'UNVERIFIED','raw_ref':{'path':str(p),'sha256':digest(raw)},
            'records':_records(body['data'],request)}
        path=root/'packet.json';path.write_text(json.dumps([batch]));return path,batch,p
    def test_frozen_definition_and_optional_metrics(self):
        self.assertEqual(digest(SPEC_PATH.read_bytes()),SPEC_SHA256)
        spec=frozen_spec();self.assertEqual(len(spec['families']),2)
        self.assertEqual(policy_gaps(spec)['optional_not_entry_gates'],['ROE','PB'])
        self.assertEqual(next(r for r in requirements() if r['id']=='positive_pe_ttm')['symbols'],['600312.SH','603228.SH'])
        self.assertFalse(evaluate_coverage([])['full_strategy_data_pass'])
    def test_packet_reparses_original_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,b,p=self.packet(Path(tmp));self.assertEqual(len(load_packets(path)),1)
            b['records'][0]['fields']['close']='10.06';path.write_text(json.dumps([b]))
            with self.assertRaisesRegex(ValueError,'RAW_ROW_BINDING'):load_packets(path)
    def test_packet_raw_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,b,p=self.packet(Path(tmp));p.write_bytes(p.read_bytes()+b' ')
            with self.assertRaisesRegex(ValueError,'RAW_HASH'):load_packets(path)
    def test_caller_cannot_promote_historical_clock(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,b,p=self.packet(Path(tmp));b['records'][0]['available_at']='2026-09-30T15:10:00+08:00';path.write_text(json.dumps([b]))
            with self.assertRaisesRegex(ValueError,'PROMOTION'):load_packets(path)
    def test_gateway_repairs_old_gap_along_with_tail(self):
        update={'rows':[{'domain':'PRICE','symbol':'603993.SH','requested_intervals':[
            {'start':'2017-01-03','end':'2017-01-04'},{'start':'2026-09-01','end':'2026-10-08'}]}]}
        r=plan(['daily'],update,through='2026-10-08')[0]
        self.assertEqual(r['params']['start_date'],'20170103');self.assertEqual(r['params']['end_date'],'20261008')
    def test_financial_full_sweep_not_tail(self):
        r=plan(['income'],{'rows':[]},through='2026-10-08')[0]
        self.assertEqual(r['params']['start_date'],'20140101')
    def test_clock_precision_keeps_date_only_and_offset(self):
        self.assertEqual(clock(None,'20210430'),{'value':'2021-04-30','precision':'DATE_ONLY','timezone':None,'source_literal':'20210430'})
        self.assertEqual(clock('2026-10-08T10:00:00+00:00')['timezone'],'+00:00')
    def test_unrun_metrics_cannot_be_zero(self):
        v=candidate('AuditableSimulationRun',{'engine_state':'ENGINE_NOT_RUN','strategy_state':'NOT_COMPUTABLE','metrics':{'return':None},'ledger_state':'BLOCKED','nav_state':'BLOCKED','productionGate':False})
        self.assertTrue(validate_candidate(v));v['metrics']['return']=0
        with self.assertRaisesRegex(ValueError,'METRIC_NULL'):validate_candidate(v)
    def test_formal_window_not_inferred_from_buffer(self):
        p=walk_forward_plan();self.assertTrue(validate_candidate(p));self.assertIsNone(p['anchor'])
        p['productionGate']=True
        with self.assertRaisesRegex(ValueError,'DTO_CONST'):validate_candidate(p)

if __name__=='__main__':unittest.main()
