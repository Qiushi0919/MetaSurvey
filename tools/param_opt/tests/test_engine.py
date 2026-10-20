from copy import deepcopy
from pathlib import Path
from decimal import Decimal as D
import json, unittest
from experiments.param_opt_v1 import engine as e
from experiments.long_forward_v1 import engine as old
from tools.long_forward.tests.test_forward import fixture
from tools.param_opt.independent import audit, BASELINE

def case(params=BASELINE):
 c,p=fixture('HISTORY',total=170)
 p.update(parameters=deepcopy(params),allowed_parameters=[deepcopy(params)],rules_hash=e.digest(e.RULES))
 p['target_window']['start']=c['calendar'][80]['date'];c['window']['first_session']=c['calendar'][80]['date']
 c.update(parameters=deepcopy(params),rules=deepcopy(e.RULES),rules_hash=e.digest(e.RULES),protocol_ref=e.digest(p))
 return c,p

class EngineTests(unittest.TestCase):
 def test_all108_configurations_independently_reconstruct_synthetic_traces(self):
  configs=json.loads((Path(e.__file__).parent/'Registration.json').read_text())['configs']
  self.assertEqual(len(configs),108)
  for cfg in configs:
   with self.subTest(config=cfg['id']):
    c,p=case(cfg['parameters']);r=e.run_diagnostic(c,protocol=p)
    self.assertTrue(r['engine_called'],r['errors']);self.assertIn(r['status'],('SIMULATED_TRADES','RUN_NO_TRADES'))
    reviewed=audit(c,r,cfg['parameters']);self.assertTrue(reviewed['passed'],reviewed['failures'][:2])
 def test_baseline_economics_equal_preserved_engine(self):
  c,p=case();r=e.run_diagnostic(c,protocol=p);oc=deepcopy(c);op=deepcopy(p)
  oc['rules']=old.RULES;oc['rules_hash']=old.digest(old.RULES);op['rules_hash']=oc['rules_hash'];oc['protocol_ref']=old.digest(op)
  previous=old.run_diagnostic(oc,protocol=op)
  for key in ('decisions','fills','unfilled','ledger','daily','dividends','net_return','maximum_drawdown'):self.assertEqual(r[key],previous[key],key)
 def test_unregistered_parameters_block(self):
  c,p=case();c['parameters']['rs_window']=60
  self.assertFalse(e.run_diagnostic(c,protocol=p)['engine_called'])
 def test_protocol_tampering_blocks(self):
  c,p=case();p['parameters']['exit_ma']=60
  self.assertFalse(e.run_diagnostic(c,protocol=p)['engine_called'])
 def test_sixty_day_warmup_cannot_use21_requirement(self):
  c,p=case(dict(BASELINE,rs_window=60));p['target_window']['start']=c['calendar'][20]['date'];c['window']['first_session']=c['calendar'][20]['date'];c['protocol_ref']=e.digest(p)
  self.assertIn('WARMUP_INCOMPLETE',e.run_diagnostic(c,protocol=p)['reason_codes'])
 def test_sixty_day_feature_requires61_and_entry_atr_unchanged(self):
  h=[{k:D(10+i)/10 for k in ('close','high','low')} for i in range(61)]
  params=dict(BASELINE,rs_window=60)
  self.assertIsNone(e._feature(h[:60],params));a=e._feature(h,BASELINE);b=e._feature(h,params)
  for k in ('sma','atr','eligible'):self.assertEqual(a[k],b[k])
  self.assertNotEqual(a['rs'],b['rs'])
 def test_future_prices_cannot_change_earlier_decisions(self):
  c,p=case();r=e.run_diagnostic(c,protocol=p);cut=c['calendar'][120]['date']
  altered=deepcopy(c)
  for row in altered['bars']:
   if row['session']>cut:
    for key in ('open','high','low','close','lower_limit','upper_limit'):row[key]=str(D(row[key])*2)
  other=e.run_diagnostic(altered,protocol=p)
  self.assertEqual([d for d in r['decisions'] if d['session']<=cut],[d for d in other['decisions'] if d['session']<=cut])
 def test_larger_stop_changes_quantity_not_only_exit(self):
  from experiments.param_opt_v1.sizing import build_portfolio
  c,p=case();day=c['calendar'][80]['date'];q=[]
  for mult in ('1.5','2.0','2.5'):
   r=build_portfolio([dict(symbol='X',sector='S',price='10',atr20='2',lot_size=100,previous20_median_volume_shares='1000000')],10000000,[],10000000,c['fee_schedule'],day,mult)
   q.append(r['plans'][0]['quantity']);self.assertLessEqual(r['plans'][0]['planned_loss_cents'],100000)
  self.assertEqual(q,[300,200,100])

if __name__=='__main__':unittest.main()
