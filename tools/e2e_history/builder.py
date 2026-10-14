"""Evidence-derived BaoStock history adapter. No network, credentials or writes.

A successful technical response is insufficient: pinned provider use documents,
all nine fixed identities, full civil/exchange dates and execution domains are
required. Derived limits are labelled, raw suspension rows never become trades.
"""
from pathlib import Path
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal,ROUND_HALF_UP
from hashlib import sha256
import json
import re
from experiments.e2e_history_v2.engine import RULES,digest
ROOT=Path(__file__).resolve().parents[2]
SOURCE_POLICY=ROOT/'docs/e2e-history-v2/Source-Policy.json'
PROTOCOL=ROOT/'experiments/e2e_history_v2/protocol.json'
INPUT_POLICY=ROOT/'experiments/e2e_history_v2/input-policy.json'
METHOD=ROOT/'experiments/e2e_pilot_v1/method.json'
D=Decimal
class InputError(ValueError):pass
def rawhash(p):return 'sha256:'+sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def dec(v):
 if type(v) is not str:raise InputError('DECIMAL_STRING_REQUIRED')
 x=D(v)
 if not x.is_finite():raise InputError('FINITE_DECIMAL_REQUIRED')
 return x
def clock(v):
 x=datetime.fromisoformat(v.replace('Z','+00:00'))
 if not x.tzinfo:raise InputError('TIMEZONE_REQUIRED')
 return x
def safe_child(folder,name):
 p=folder/name
 if p.is_symlink() or not p.is_file() or p.resolve().parent!=folder.resolve():raise InputError('CAPTURE_PATH_NOT_FLAT_OR_SYMLINK')
 return p
def source_authority():
 policy=read(SOURCE_POLICY)
 required={'baostock-home.md','baostock-stockKData.md','baostock-dividInfo.md','baostock-factorInfo.md','baostock-pythonAPI.md','baostock-StockBasicInfoAPI.md','sse-trade2026.docx','sse-deferred2026.docx','sse-trade2023.docx','sse-deferred2023.docx','szse-trade2023.pdf','szse-trade2026.pdf'}
 if not required.issubset(set(policy.get('documents',{}))):raise InputError('REQUIRED_SOURCE_DOCUMENT_SET_INCOMPLETE')
 if policy.get('kind')!='BoundedLocalSourcePolicy' or policy.get('version')!='1.0.0' or policy.get('historical_pit_admitted') is not False:raise InputError('SOURCE_POLICY_SCHEMA')
 if policy['source']!='BaoStock' or policy['purpose']!='LOCAL_HISTORICAL_DIAGNOSTIC' or policy['public_raw_distribution'] or policy['cloud_transfer']:raise InputError('SOURCE_USE_SCOPE_MISMATCH')
 folder=Path(policy['raw_document_root']);pins={}
 for name,value in policy['documents'].items():
  path=safe_child(folder,name)
  if rawhash(path)!=value:raise InputError('SOURCE_TERMS_PIN_MISMATCH:'+name)
  pins[str(path)]=value
 text=(folder/'baostock-home.md').read_text()
 if '全部保存到本地后进行分析' not in text:raise InputError('LOCAL_RESEARCH_BASIS_MISSING')
 return {'source':'BaoStock','purpose':policy['purpose'],'policy_hash':rawhash(SOURCE_POLICY),'document_pins':pins,'historical_pit_admitted':False}
def indexed_capture(folder):
 manifest=read(safe_child(folder,'Manifest.json'));index={};pins={str(folder/'Manifest.json'):rawhash(folder/'Manifest.json')}
 if manifest.get('state')=='LOGIN_FAILED':raise InputError('ANONYMOUS_SOURCE_LOGIN_FAILED')
 if manifest.get('scope')!='registered-nine':raise InputError('REGISTERED_NINE_CAPTURE_REQUIRED')
 for item in manifest['sources']:
  path=safe_child(folder,item['path']);pins[str(path)]=rawhash(path)
  if pins[str(path)]!='sha256:'+item['sha256']:raise InputError('RAW_CAPTURE_PIN_MISMATCH')
  obj=read(path)
  if obj.get('source')!='BaoStock' or obj.get('error_code')!='0':raise InputError('API_ERROR:'+item['path'])
  if obj['product']!=item['product'] or obj['request']!=item['request'] or obj['row_count']!=len(obj['rows']):raise InputError('CAPTURE_MANIFEST_BINDING_MISMATCH')
  clock(obj['retrieved_at']);clock(obj['started_at'])
  if clock(obj['retrieved_at'])<clock(obj['started_at']):raise InputError('CAPTURE_CLOCK_INVALID')
  fields=obj['fields']
  if len(set(fields))!=len(fields) or any(len(row)!=len(fields) for row in obj['rows']):raise InputError('RESPONSE_SCHEMA_INVALID')
  req=obj['request'];key=(obj['product'],req.get('code'),req.get('year'))
  if key in index:raise InputError('DUPLICATE_PRODUCT_REQUEST')
  index[key]=(obj,[dict(zip(fields,row)) for row in obj['rows']],str(path),pins[str(path)])
 return index,pins

def require_exception_coverage(index,members,target):
 # Known remaining adapter gap: current basic/IPO date/isST is not a historical
 # exchange exception feed. No caller boolean or hand-written policy grants it.
 # A future official-event decoder requires a successor code/config freeze.
 raise InputError('RULE_EXCEPTION_COVERAGE_UNPROVEN: relisting, delisting-first-day and exchange-specific no-limit history need an official scoped event decoder')

def build_case(folder,run_id,run_at):
 folder=Path(folder).resolve();report={'kind':'HistoricalInputBuild','version':'2.0.0','run_id':run_id,'recorded_at':run_at,'status':'DATA_BLOCKED','errors':[],'field_coverage':{},'case_hash':None,'real_input_rows':0,'source_policy_hash':rawhash(SOURCE_POLICY),'protocol_hash':rawhash(PROTOCOL),'input_policy_hash':rawhash(INPUT_POLICY),'capture_directory':str(folder),'historical_visibility_proven':False}
 try:
  report['source_authority']=source_authority();index,pins=indexed_capture(folder);report['raw_pins']=pins
  protocol=read(PROTOCOL);method=read(METHOD);target=protocol['target_window'];evidence={}
  members=[{'symbol':m['symbol'],'sector':g['id'],'selection_evidence_ref':'fixed-current-sample'} for g in method['universe'] for m in g['members']]
  def take(product,code=None,year=None):
   key=(product,code,year)
   if key not in index:raise InputError('REQUIRED_PRODUCT_CAPTURE_MISSING:'+str(key))
   obj,rows,path,h=index[key];req=obj['request'];ref=Path(path).name
   if clock(obj['retrieved_at'])>clock(run_at):raise InputError('SOURCE_RETRIEVED_AFTER_RUN')
   evidence[ref]={'source':'BaoStock/'+product,'source_version':h,'raw_sha256':h,'published_at':None,'available_at':obj['retrieved_at'],'retrieved_at':obj['retrieved_at'],'visibility_assumption':'RECONSTRUCTED_END_OF_DAY_ASSUMED_AVAILABLE_BY_SIMULATED_1800; NOT_ORIGINAL_PIT','path':path}
   report['field_coverage'][str(key)]={'rows':len(rows),'raw_sha256':h,'source_ref':ref}
   return rows,req,ref
  days,req,calref=take('query_trade_dates')
  if req!={'start_date':target['warmup_start'],'end_date':target['end']}:raise InputError('CALENDAR_REQUEST_SCOPE_MISMATCH')
  start,end=date.fromisoformat(target['warmup_start']),date.fromisoformat(target['end']);expected=[(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1)]
  if [x['calendar_date'] for x in days]!=expected or any(x['is_trading_day'] not in ('0','1') for x in days):raise InputError('FULL_CIVIL_CALENDAR_REQUIRED')
  coverage={'start':str(start),'end':str(end),'days':[{'date':x['calendar_date'],'is_open':x['is_trading_day']=='1','evidence_ref':calref} for x in days]}
  opened=[x['date'] for x in coverage['days'] if x['is_open']]
  calendar=[{'date':day,'open_at':day+'T09:30:00+08:00','close_at':day+'T15:00:00+08:00','decision_at':day+'T18:00:00+08:00','decision_clock_label':'SIMULATED_POST_CLOSE_DECISION_TIME','evidence_ref':calref} for day in opened]
  evidence['fixed-current-sample']={'source':'OWNER_CURRENT_SAMPLE_SELECTION','source_version':rawhash(METHOD),'raw_sha256':rawhash(METHOD),'published_at':None,'available_at':protocol['frozen_at'],'retrieved_at':protocol['frozen_at'],'visibility_assumption':'CURRENT_SELECTION_BIAS_EXPLICIT; NO_HISTORICAL_UNIVERSE_CLAIM'}
  bars=[];actions=[];action_audit=[]
  for member in members:
   symbol=member['symbol'];code=symbol.split('.')[1].lower()+'.'+symbol.split('.')[0]
   basic,_,basicref=take('query_stock_basic',code)
   if len(basic)!=1 or basic[0]['code']!=code or basic[0]['type']!='1' or not symbol.startswith(('00','60')):raise InputError('MAINBOARD_SECURITY_IDENTITY_REQUIRED:'+symbol)
   identity=basic[0]
   if date.fromisoformat(identity['ipoDate'])>start-timedelta(days=40) or (identity.get('outDate') and identity['outDate']<=str(end)):raise InputError('IPO_DELIST_OR_RELST_EXCEPTION_UNSUPPORTED:'+symbol)
   rows,req,ref=take('query_history_k_data_plus',code)
   if req['start_date']!=str(start) or req['end_date']!=str(end) or req['frequency']!='d' or req['adjustflag']!='3':raise InputError('RAW_DAILY_REQUEST_SCOPE_REQUIRED')
   if [x['date'] for x in rows]!=opened:raise InputError('DAILY_MISSING_DUPLICATE_OR_OUT_OF_ORDER:'+symbol)
   for row in rows:
    if row['code']!=code or row['adjustflag']!='3':raise InputError('ROW_IDENTITY_OR_PRICE_VERSION_CONFLICT')
    if row['tradestatus'] not in ('0','1') or row['isST']!='0':raise InputError('UNKNOWN_OR_UNSUPPORTED_STATUS:'+symbol+':'+row['date'])
    volume=dec(row['volume']);amount=dec(row['amount'])
    if volume<0 or volume!=int(volume) or amount<0:raise InputError('VOLUME_AMOUNT_UNITS_INVALID')
    suspended=row['tradestatus']=='0'
    if suspended and (volume!=0 or amount!=0):raise InputError('SUSPENSION_WITH_TRADES')
    pre=dec(row['preclose'])
    if pre<=0:raise InputError('PRECLOSE_REFERENCE_UNKNOWN')
    rowout={'session':row['date'],'symbol':symbol,'status':'SUSPENDED' if suspended else 'TRADABLE','price_kind':'RAW','volume_shares':str(volume),'amount_CNY':str(amount),'lot_size':100,'evidence_ref':ref,'identity_evidence_ref':basicref,'limit_kind':'DERIVED_NORMAL_MAINBOARD_10PCT_PRECLOSE_HALF_UP','limit_basis':str(pre)}
    for k in ('open','high','low','close'):
     value=dec(row[k])
     if value<=0 or value%D('.01'):raise InputError('RAW_PRICE_UNIT_OR_TICK_INVALID')
     rowout[k]=None if suspended else str(value)
    rowout['lower_limit']=None if suspended else str((pre*D('.9')).quantize(D('.01'),rounding=ROUND_HALF_UP))
    rowout['upper_limit']=None if suspended else str((pre*D('1.1')).quantize(D('.01'),rounding=ROUND_HALF_UP))
    bars.append(rowout)
   seen=set();exdates=set();bydate={row['date']:row for row in rows};symbol_actions={}
   for year in ('2025','2026'):
    div,req,ref=take('query_dividend_data',code,year)
    if req.get('yearType')!='operate':raise InputError('ACTION_OPERATE_YEAR_REQUIRED')
    for row in div:
     if row['code']!=code:raise InputError('ACTION_IDENTITY_CONFLICT')
     ex=row.get('dividOperateDate')
     if not ex:raise InputError('ACTION_IMPLEMENTATION_DATE_UNKNOWN')
     if not str(start)<=ex<=str(end):continue
     if ex in seen:raise InputError('DUPLICATE_OR_MULTIPLE_ACTIONS')
     seen.add(ex);exdates.add(ex)
     description=row.get('dividCashStock','')
     if not description or not re.search('[派送转]',description) or re.search('配股|缩股|合并|拆分|认购|回购注销',description):raise InputError('COMPLEX_OR_UNDESCRIBED_ACTION')
     cash=dec(row['dividCashPsBeforeTax']);bonus=dec(row['dividStocksPs'])+dec(row['dividReserveToStockPs'])
     if min(cash,bonus)<0:raise InputError('ACTION_NEGATIVE_UNSUPPORTED')
     if cash==0 and bonus==0:raise InputError('ACTION_EMPTY_OR_COMPLEX')
     pay=row.get('dividPayDate') or None;share=row.get('dividStockMarketDate') or None
     if cash>0 and not pay:raise InputError('CASH_PAYMENT_DATE_REQUIRED')
     if bonus>0 and not share:raise InputError('BONUS_MARKET_DATE_REQUIRED')
     a={'id':code+':'+ex,'symbol':symbol,'record_date':row['dividRegistDate'],'ex_date':ex,'pay_date':pay if cash>0 else None,'shares_available_date':share if bonus>0 else None,'cash_per_share':str(cash),'bonus_ratio':str(bonus),'split_ratio':'1','tax_rate':'0.20','evidence_ref':ref};actions.append(a);symbol_actions[ex]=a
     action_audit.append({'symbol':symbol,'ex_date':ex,'kind':'CASH_AND_BONUS' if bonus else 'CASH_DIVIDEND','source_ref':ref})
   factors,req,factorref=take('query_adjust_factor',code)
   if req['start_date']!=str(start) or req['end_date']!=str(end):raise InputError('ACTION_FACTOR_SCOPE_REQUIRED')
   factor_dates=[]
   for row in factors:
    if row['code']!=code:raise InputError('FACTOR_IDENTITY_CONFLICT')
    day=row['dividOperateDate']
    if any(dec(row[k])<=0 for k in ('foreAdjustFactor','backAdjustFactor','adjustFactor')):raise InputError('FACTOR_VALUES_MISSING_OR_INVALID')
    if str(start)<=day<=str(end):factor_dates.append(day)
   if len(set(factor_dates))!=len(factor_dates) or set(factor_dates)!=exdates:raise InputError('UNMATCHED_ACTION_FACTOR_EVENT:'+symbol)
   # Never infer action type from date alone. Check gross economic bridge against
   # source ex-right reference and retain the provider's raw factors, not as PIT.
   for before,current in zip(rows,rows[1:]):
    oldclose=dec(before['close']);reference=dec(current['preclose']);action=symbol_actions.get(current['date'])
    expected=(oldclose-dec(action['cash_per_share']))/(D(1)+dec(action['bonus_ratio'])) if action else oldclose
    rounded=expected.quantize(D('.01'),rounding=ROUND_HALF_UP)
    if reference.quantize(D('.01'),rounding=ROUND_HALF_UP)!=rounded:raise InputError('UNEXPLAINED_PRECLOSE_ACTION_OR_VERSION_CHANGE:'+symbol+':'+current['date'])
  report['field_coverage']['exchange_rule_exceptions']={'symbols':[m['symbol'] for m in members],'start':target['warmup_start'],'end':target['end'],'status':'UNPROVEN_NO_OFFICIAL_EVENT_DECODER'}
  report['exception_evidence']=require_exception_coverage(index,members,target)
  active=[d for d in opened if target['start']<=d<=target['end']]
  if not active:raise InputError('NO_TARGET_SESSIONS')
  case={'namespace':protocol['namespace'],'strategy_id':protocol['strategy_id'],'run_id':run_id,'run_at':run_at,'evidence_grade':'RECONSTRUCTED_HISTORY_DIAGNOSTIC','protocol_ref':rawhash(PROTOCOL),'method_ref':rawhash(METHOD),'input_policy_ref':rawhash(INPUT_POLICY),'rules':RULES,'rules_hash':digest(RULES),'fee_schedule':protocol['fee_schedule'],'calendar':calendar,'calendar_coverage':coverage,'universe':members,'window':{'first_session':active[0],'last_session':active[-1]},'evidence':evidence,'bars':bars,'actions':sorted(actions,key=lambda a:(a['ex_date'],a['symbol']))}
  report.update(status='ADMITTED_RECONSTRUCTED_DIAGNOSTIC_ONLY',case_hash=digest(case),real_input_rows=len(bars),action_inventory=action_audit,market_sessions=len(opened),target_sessions=len(active),limitations=['fixed contemporary sample','supplier reconstruction not original PIT','derived limits and simulated decision18:00','simulated fees/tax, no investment validation'])
  return report,case
 except (ValueError,KeyError,TypeError,OSError,ArithmeticError) as exc:
  report['errors'].append({'type':type(exc).__name__,'detail':str(exc)});return report,None

def verify_provenance(case,folder):
 report,recomputed=build_case(folder,case['run_id'],case['run_at'])
 if report['status']!='ADMITTED_RECONSTRUCTED_DIAGNOSTIC_ONLY' or recomputed!=case:raise InputError('REBUILD_OR_ADMISSION_MISMATCH')
 return {'verified':True,'case_hash':digest(case),'receipt_hash':digest(report),'purpose':'LOCAL_HISTORICAL_DIAGNOSTIC'}
