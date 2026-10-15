import unittest
from copy import deepcopy
from tools.long_forward.tests.test_forward import fixture
from experiments.long_forward_v1 import engine

class HistoryTests(unittest.TestCase):
    def test_frozen_history_runs_with_tail(self):
        c,p=fixture('HISTORY');r=engine.run_diagnostic(c,protocol=p)
        self.assertEqual(r['status'],'SIMULATED_TRADES',r)
        self.assertTrue(all(not d['ranked_buy_symbols'] for d in r['decisions'][-41:]))
    def test_parameterized_protocol_rejects_modified_universe(self):
        c,p=fixture('HISTORY');c['universe'][0]['sector']='FAKE';r=engine.run_diagnostic(c,protocol=p)
        self.assertFalse(r['engine_called']);self.assertIn('FROZEN_UNIVERSE_MISMATCH',r['reason_codes'])
    def test_protocol_required_and_hash_bound(self):
        c,p=fixture('HISTORY');p=deepcopy(p);p['target_window']['start']='2025-01-22'
        self.assertFalse(engine.run_diagnostic(c,protocol=p)['engine_called'])
    def test_forward_cannot_run_as_history(self):
        c,p=fixture();r=engine.run_diagnostic(c,protocol=p);self.assertFalse(r['engine_called'])
    def test_history_matches_sealed_v2_pure_execution_on_same_synthetic_data(self):
        from experiments.e2e_history_v2 import engine as previous
        from experiments.e2e_history_v2.tests.test_engine import case as original_case
        c,p=fixture('HISTORY');new=engine.run_diagnostic(c,protocol=p);old=previous.run_diagnostic(original_case(85))
        for key in ('fills','unfilled','ledger','decisions','daily','dividends','final_cash_cents','positions','net_return','maximum_drawdown'):
            self.assertEqual(new[key],old[key],key)
    def test_dated_fee_selection_respects_effective_day(self):
        c,p=fixture('HISTORY');first=deepcopy(c['fee_schedule'][0]);second=deepcopy(first)
        first['effective_until']='2025-01-31';first['sell_tax_rate']='0.001'
        second['effective_from']='2025-02-01';second['sell_tax_rate']='0.0005';second['version']='SYNTHETIC-2'
        schedule=[first,second]
        before=engine.quote('10',1000,'SELL','2025-01-31',engine.fee_for(schedule,'2025-01-31'))
        after=engine.quote('10',1000,'SELL','2025-02-01',engine.fee_for(schedule,'2025-02-01'))
        self.assertGreater(before['fees']['sell_tax_cents'],after['fees']['sell_tax_cents'])
        p['fee_schedule']=schedule;c['fee_schedule']=schedule;c['protocol_ref']=engine.digest(p)
        self.assertEqual(engine.run_diagnostic(c,protocol=p)['status'],'SIMULATED_TRADES')
    def test_real_cannot_use_synthetic_protocol(self):
        c,p=fixture('HISTORY');c['evidence_grade']=engine.GRADE
        r=engine.run_diagnostic(c,protocol=p);self.assertIn('REAL_CANNOT_USE_SYNTHETIC_PROTOCOL',r['reason_codes'])

if __name__=='__main__':unittest.main()
