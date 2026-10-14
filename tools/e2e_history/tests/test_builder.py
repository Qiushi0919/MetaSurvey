"""Synthetic captured-response adapter tests, never investment evidence."""
import json,tempfile,unittest,hashlib
from pathlib import Path
from datetime import date,timedelta
from unittest.mock import patch
from tools.e2e_history import builder as b

def fixture(folder):
 target=b.read(b.PROTOCOL)['target_window'];start=date.fromisoformat(target['warmup_start']);end=date.fromisoformat(target['end'])
 days=[start+timedelta(days=i) for i in range((end-start).days+1)];sessions=[str(x) for x in days if x.weekday()<5]
 manifest={'scope':'registered-nine','sources':[]}
 def add(product,params,rows,fields=None):
  fields=fields or list(rows[0]);obj={'source':'BaoStock','product':product,'request':params,'fields':fields,'rows':[[str(x.get(k,'')) for k in fields] for x in rows],'error_code':'0','row_count':len(rows),'started_at':'2026-10-14T09:00:00+00:00','retrieved_at':'2026-10-14T09:01:00+00:00'}
  p=folder/(str(len(manifest['sources']))+'.json');p.write_text(json.dumps(obj));manifest['sources'].append({'path':p.name,'product':product,'request':params,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'row_count':len(rows),'error_code':'0'})
 add('query_trade_dates',{'start_date':str(start),'end_date':str(end)},[{'calendar_date':str(x),'is_trading_day':'1' if x.weekday()<5 else '0'} for x in days])
 for group in b.read(b.METHOD)['universe']:
  for member in group['members']:
   sym=member['symbol'];code=sym.split('.')[1].lower()+'.'+sym.split('.')[0]
   add('query_stock_basic',{'code':code},[{'code':code,'type':'1','ipoDate':'2010-01-01','outDate':''}])
   add('query_history_k_data_plus',{'code':code,'start_date':str(start),'end_date':str(end),'frequency':'d','adjustflag':'3'},[dict(date=d,code=code,open='10.00',high='10.50',low='9.50',close='10.00',preclose='10.00',volume='100000',amount='1000000',tradestatus='1',adjustflag='3',isST='0') for d in sessions])
   for year in ('2025','2026'):add('query_dividend_data',{'code':code,'year':year,'yearType':'operate'},[],['code','dividOperateDate'])
   add('query_adjust_factor',{'code':code,'start_date':str(start),'end_date':str(end)},[],['code','dividOperateDate'])
 (folder/'Manifest.json').write_text(json.dumps(manifest));return sessions

class BuilderTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name);self.sessions=fixture(self.folder)
  self.mock=patch.object(b,'source_authority',return_value={'SYNTHETIC_TEST_ONLY':True});self.mock.start();self.addCleanup(self.mock.stop)
  self.exceptions=patch.object(b,'require_exception_coverage',return_value={'SYNTHETIC_ONLY':True});self.exceptions.start();self.addCleanup(self.exceptions.stop)
 def build(self):return b.build_case(self.folder,'SYNTHETIC-ADAPTER-ONLY','2026-10-14T10:00:00+00:00')
 def edit(self,n,fn,repin=True):
  p=self.folder/f'{n}.json';x=json.loads(p.read_text());fn(x);x['row_count']=len(x['rows']);p.write_text(json.dumps(x))
  if repin:
   m=json.loads((self.folder/'Manifest.json').read_text());m['sources'][n]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();m['sources'][n]['row_count']=len(x['rows']);(self.folder/'Manifest.json').write_text(json.dumps(m))
 def assert_blocked(self,reason):
  r,c=self.build();self.assertIsNone(c);self.assertIn(reason,r['errors'][0]['detail'])
 def test_complete_synthetic_responses_build_nine_fixed_members(self):
  r,c=self.build();self.assertEqual(len(c['universe']),9);self.assertEqual(len(c['bars']),9*len(self.sessions));self.assertFalse(r['historical_visibility_proven']);self.assertEqual(c['calendar'][0]['decision_at'][-14:],'18:00:00+08:00')
 def test_real_exception_domain_cannot_be_admitted_by_basic_data(self):
  self.exceptions.stop();self.assert_blocked('RULE_EXCEPTION_COVERAGE_UNPROVEN')
 def test_raw_hash_tamper_rejected(self):self.edit(2,lambda x:x.update(error_code='oops'),False);self.assert_blocked('RAW_CAPTURE_PIN_MISMATCH')
 def test_duplicate_bar_rejected(self):self.edit(2,lambda x:x['rows'].append(x['rows'][0]));self.assert_blocked('DAILY_MISSING_DUPLICATE')
 def test_missing_row_not_imputed(self):self.edit(2,lambda x:x['rows'].pop(3));self.assert_blocked('DAILY_MISSING_DUPLICATE')
 def test_identity_conflict_rejected(self):self.edit(2,lambda x:x['rows'][0].__setitem__(1,'sh.000000'));self.assert_blocked('ROW_IDENTITY')
 def test_adjusted_prices_rejected(self):self.edit(2,lambda x:x['rows'][0].__setitem__(x['fields'].index('adjustflag'),'2'));self.assert_blocked('PRICE_VERSION')
 def test_st_unknown_or_rule_exception_rejected(self):self.edit(2,lambda x:x['rows'][0].__setitem__(x['fields'].index('isST'),'1'));self.assert_blocked('UNSUPPORTED_STATUS')
 def test_fractional_share_volume_rejected(self):self.edit(2,lambda x:x['rows'][0].__setitem__(x['fields'].index('volume'),'1.25'));self.assert_blocked('UNITS_INVALID')
 def test_suspension_normalized_null_never_trade(self):
  def mutate(x):
   for k,v in [('tradestatus','0'),('volume','0'),('amount','0')]:x['rows'][0][x['fields'].index(k)]=v
  self.edit(2,mutate);r,c=self.build();self.assertIsNone(c['bars'][0]['close']);self.assertEqual(c['bars'][0]['status'],'SUSPENDED')
 def test_suspended_nonzero_volume_rejected(self):self.edit(2,lambda x:x['rows'][0].__setitem__(x['fields'].index('tradestatus'),'0'));self.assert_blocked('SUSPENSION_WITH_TRADES')
 def test_calendar_closed_day_gap_rejected(self):self.edit(0,lambda x:x['rows'].pop(4));self.assert_blocked('CIVIL_CALENDAR')
 def test_actual_clock_not_backfilled(self):
  r,c=self.build();self.assertEqual(c['evidence']['2.json']['available_at'],'2026-10-14T09:01:00+00:00');self.assertIsNone(c['evidence']['2.json']['published_at'])
 def test_unknown_factor_event_blocks_not_none(self):
  def mutate(x):
   x['fields']=['code','dividOperateDate','foreAdjustFactor','backAdjustFactor','adjustFactor'];x['rows']=[['sh.603228',self.sessions[8],'1','1','1']]
  self.edit(5,mutate);self.assert_blocked('UNMATCHED_ACTION_FACTOR')
 def action(self,description='10派5元',reference='9.50'):
  ex=self.sessions[8]
  def dividend(x):
   x['fields']=['code','dividOperateDate','dividCashStock','dividCashPsBeforeTax','dividStocksPs','dividReserveToStockPs','dividPayDate','dividStockMarketDate','dividRegistDate']
   x['rows']=[['sh.603228',ex,description,'0.5','0','0',ex,'',self.sessions[7]]]
  self.edit(3,dividend)
  def factor(x):
   x['fields']=['code','dividOperateDate','foreAdjustFactor','backAdjustFactor','adjustFactor'];x['rows']=[['sh.603228',ex,'1','1','1.0526315789']]
  self.edit(5,factor)
  self.edit(2,lambda x:x['rows'][8].__setitem__(x['fields'].index('preclose'),reference))
 def test_cash_action_checked_against_gross_reference(self):
  self.action();r,c=self.build();self.assertIsNotNone(c);self.assertEqual(c['actions'][0]['cash_per_share'],'0.5')
 def test_action_date_match_cannot_hide_wrong_economic_bridge(self):
  self.action(reference='8.00');self.assert_blocked('UNEXPLAINED_PRECLOSE')
 def test_rights_action_not_accepted_as_dividend(self):
  self.action(description='10派5元并配股');self.assert_blocked('COMPLEX_OR_UNDESCRIBED')
 def test_no_action_cannot_hide_preclose_revision(self):
  self.edit(2,lambda x:x['rows'][8].__setitem__(x['fields'].index('preclose'),'9.50'));self.assert_blocked('UNEXPLAINED_PRECLOSE')
 def test_missing_cash_pay_date_blocks(self):
  self.action();self.edit(3,lambda x:x['rows'][0].__setitem__(x['fields'].index('dividPayDate'),''));self.assert_blocked('CASH_PAYMENT_DATE_REQUIRED')
 def test_symlink_manifest_rejected(self):
  target=self.folder/'real.json';(self.folder/'Manifest.json').rename(target);(self.folder/'Manifest.json').symlink_to(target);self.assert_blocked('SYMLINK')
 def test_missing_product_rejected(self):
  p=self.folder/'Manifest.json';x=json.loads(p.read_text());x['sources'].pop();p.write_text(json.dumps(x));self.assert_blocked('REQUIRED_PRODUCT_CAPTURE_MISSING')
 def test_no_production_boolean_admits_missing_calendar(self):
  p=self.folder/'Manifest.json';x=json.loads(p.read_text());x['sources']=[];x['admitted']=True;p.write_text(json.dumps(x));self.assert_blocked('REQUIRED_PRODUCT_CAPTURE_MISSING')
 def test_receipt_bound_to_rebuilt_case(self):
  _,c=self.build();proof=b.verify_provenance(c,self.folder);self.assertEqual(proof['case_hash'],b.digest(c));c['bars'][0]['close']='999'
  with self.assertRaisesRegex(b.InputError,'REBUILD'):b.verify_provenance(c,self.folder)

if __name__=='__main__':unittest.main()
