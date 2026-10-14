"""Capture planning only; no secret or network access."""
import unittest
from tools.e2e_gateway.capture import plan,FIELDS
class CapturePlanTests(unittest.TestCase):
 def test_exact_nine_and_two_calendars(self):
  symbols,requests=plan();self.assertEqual(len(set(symbols)),9);self.assertEqual(len(requests),65)
  self.assertEqual([p['exchange'] for a,p in requests if a=='trade_cal'],['SSE','SZSE'])
 def test_scope_unchanged_and_no_credential_in_plan(self):
  symbols,requests=plan()
  for api,p in requests:
   self.assertNotIn('token',p)
   if api in ('daily','stk_limit','adj_factor','suspend_d'):self.assertEqual((p['start_date'],p['end_date']),('20250603','20260930'))
   if api in ('dividend','namechange'):self.assertEqual(set(p),{'ts_code'})
 def test_required_actual_execution_fields(self):
  self.assertIn('div_listdate',FIELDS['dividend']);self.assertIn('cash_div_tax',FIELDS['dividend'])
  self.assertEqual(FIELDS['stk_limit'],'ts_code,trade_date,pre_close,up_limit,down_limit')
if __name__=='__main__':unittest.main()
