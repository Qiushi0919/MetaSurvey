from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json, unittest
from tools.param_opt import run
from tools.param_opt.tests.test_engine import case
REG=json.loads((Path(run.__file__).parents[2]/'experiments/param_opt_v1/Registration.json').read_text())

def table():
 return [dict(config_id=c['id'],partition=w,bps=bp,valid=True,net_return='0.02' if c['id']=='P029' else '0.03',max_drawdown='0.10',turnover='1') for c in REG['configs'] for w in ('development','selection') for bp in ('10','30')]
class SelectionTests(unittest.TestCase):
 def test_108_unique_configurations_with_frozen_hashes(self):
  self.assertEqual(len({json.dumps(c['parameters'],sort_keys=True) for c in REG['configs']}),108)
  for c in REG['configs']:self.assertEqual(c['hash'],run.engine.digest(c['parameters']))
 def test_neighbours_change_one_adjacent_axis(self):
  c=next(c for c in REG['configs'] if c['id']=='P029');ns=run.neighbors(c,REG['configs'])
  self.assertTrue(ns);self.assertNotIn('P029',ns)
  for n in ns:
   p=next(c['parameters'] for c in REG['configs'] if c['id']==n)
   self.assertEqual(sum(p[k]!=c['parameters'][k] for k in p),1)
 def test_isolated_high_return_rejected(self):
  t=table()
  for r in t:
   if r['config_id']=='P001' and r['partition']=='selection':r['net_return']='0.50'
  lock=run.lock_candidates(REG,t)
  self.assertNotIn('P001',lock['qualified']);self.assertIn('P001',lock['locked_ids']);self.assertIn('NOT_RECOMMENDED',lock['roles']['P001'])
 def test_no_winner_does_not_force_recommendation(self):
  t=table()
  for r in t:r['net_return']='0.01'
  lock=run.lock_candidates(REG,t)
  self.assertEqual(lock['qualified'],[]);self.assertEqual(len(lock['locked_ids']),3)
  self.assertTrue(all('NOT_RECOMMENDED' in x for x in lock['roles'].values()))
 def test_check_rows_cannot_change_training_selection(self):
  t=table();a=run.lock_candidates(REG,t)
  t.extend([dict(r,partition='check',net_return='999') for r in t])
  b=run.lock_candidates(REG,t)
  self.assertEqual(a['locked_ids'],b['locked_ids']);self.assertEqual(a['qualified'],b['qualified'])
 def test_failed_stress_trial_disqualifies(self):
  t=table()
  for r in t:
   if r['config_id']=='P001' and r['bps']=='30':r['valid']=False
  self.assertNotIn('P001',run.lock_candidates(REG,t)['qualified'])
 def test_short_window_clips_future_and_preserves_warmup(self):
  c,p=case();reg=deepcopy(REG);reg['windows']={'test':{'start':c['calendar'][80]['date'],'end':c['calendar'][120]['date']}}
  with patch.object(run,'registration',return_value=reg),patch.object(run.history_v2,'protocol',return_value=p):
   new,proto=run.derive(c,REG['configs'][0],'test','30','2030-01-01T00:00:00+00:00')
  self.assertEqual(new['window']['first_session'],c['calendar'][80]['date'])
  self.assertEqual(new['calendar'][0],c['calendar'][0]);self.assertEqual(len(new['calendar']),121)
  self.assertTrue(all(b['session']<=new['window']['last_session'] for b in new['bars']))
  self.assertEqual(new['portfolio'],c['portfolio']) if 'portfolio' in c else None
  self.assertTrue(all(f['slippage_bps']=='30' for f in proto['fee_schedule']))
