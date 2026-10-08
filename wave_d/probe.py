"""Finite Owner-authorized three-stock augmentation. Runtime secret never persisted."""
import ctypes,json,os,time,re,urllib.request,urllib.error
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
from wave_c.core import canonical,sha,require,SYMBOLS,day
from wave_b.probe import _old_probe,NoRedirect
from wave_b.primitives import safe_body
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path('/Users/qiushi/投资研究/.p1b-archives/wave-d-20261006')
DEST=ARCHIVE/'captures'/'G1'
BASE='http://118.89.117.77:8030/'
FIELDS={
 'daily_basic':'ts_code,trade_date,close,pe_ttm,pb,ps_ttm,total_mv,circ_mv,total_share,turnover_rate',
 'stock_basic':'ts_code,symbol,name,industry,exchange,curr_type,list_status,list_date,delist_date',
 'income':'ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,revenue,total_revenue,oper_cost,n_income,n_income_attr_p,update_flag',
 'balancesheet':'ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,total_assets,total_liab,total_hldr_eqy_inc_min_int,accounts_receiv,inventories,money_cap,update_flag',
 'cashflow':'ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,net_profit,n_cashflow_act,c_pay_acq_const_fiolta,update_flag',
 'fina_indicator':'ts_code,ann_date,end_date,roe,debt_to_assets,netprofit_yoy,or_yoy,grossprofit_margin,update_flag',
 'stock_st':'ts_code,name,trade_date,type,type_name',
 'suspend_d':'ts_code,trade_date,suspend_timing,suspend_type'}
STATUS_DAY='20260930'
def clock():return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
def plan():
 out=[]
 for symbol in SYMBOLS:
  for api in ('stock_basic','daily_basic','income','balancesheet','cashflow','fina_indicator'):
   params={'ts_code':symbol,'ts_type_name':BASE}
   if api=='daily_basic':params['trade_date']=STATUS_DAY
   elif api in ('income','balancesheet','cashflow','fina_indicator'):params.update(start_date='20230101',end_date='20261006')
   out.append({'request_id':api+'-'+symbol,'api_name':api,'symbol':symbol,'params':params,'fields':FIELDS[api].split(','),'max_rows':1 if api in ('stock_basic','daily_basic') else 200,'kind':'THREE_STOCK_AUGMENTATION'})
 for api,cap in [('stock_st',1000),('suspend_d',5000)]:
  for epoch,offset in [('MAIN',0),('TERMINAL',cap),('REPEAT',0)]:
   params={'trade_date':STATUS_DAY,'limit':cap,'offset':offset,'ts_type_name':BASE}
   if api=='suspend_d':params['suspend_type']='S'
   out.append({'request_id':api+'-'+STATUS_DAY+'-'+epoch,'api_name':api,'symbol':None,'params':params,'fields':FIELDS[api].split(','),'max_rows':cap,'kind':'ONE_DAY_STATUS_COMPLETENESS_ONLY'})
 return out

def private_write(p,raw):
 require(p.is_relative_to(ARCHIVE) and p.resolve()==p and not p.exists(),'WAVE_D_PRIVATE_PATH_INVALID')
 os.umask(0o077);p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw)

def _send(spec,credential):
 require(canonical(spec) in [canonical(s) for s in plan()],'WAVE_D_SCOPE_FORBIDDEN')
 old=_old_probe();require(type(credential) is old.Credential,'WAVE_D_CREDENTIAL_TYPE_INVALID')
 url=BASE+'/'+spec['api_name']
 wire={'api_name':spec['api_name'],'token':credential._value,'params':spec['params'],'fields':','.join(spec['fields'])}
 req=urllib.request.Request(url,data=canonical(wire),method='POST',headers={'Content-Type':'application/json'})
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 try:response=opener.open(req,timeout=20)
 except urllib.error.HTTPError as e:
  if 300<=e.code<400:raise ValueError('WAVE_D_REDIRECT_FORBIDDEN') from None
  response=e
 except Exception:raise ValueError('WAVE_D_TRANSPORT_FAILURE') from None
 with response:
  require(response.geturl()==url,'WAVE_D_REDIRECT_FORBIDDEN');raw=response.read(old.MAX_BYTES+1);status=int(response.code)
 require(len(raw)<=old.MAX_BYTES,'WAVE_D_RESPONSE_LIMIT');old._secret_check(raw,credential)
 return status,raw

def normalized(v):
 if v is None:return None
 if type(v) in (int,Decimal):
  x=Decimal(v);require(x.is_finite(),'WAVE_D_NONFINITE');return format(x,'f')
 require(type(v) is str,'WAVE_D_SOURCE_TYPE');safe_body(v);return v

def analyze(spec,raw,retrieved):
 reasons=[];excluded=[];rows=[];code=None;fields=[]
 try:
  doc=_old_probe()._old.parse_response(raw)
  require(type(doc) is dict and type(doc.get('code')) is int,'RESPONSE_SCHEMA_INVALID');code=doc['code']
  if code!=0:reasons.append('ENTITLEMENT_NOT_GRANTED' if code in (-2002,2002) else 'API_ACCESS_NOT_PROVEN')
  else:
   data=doc.get('data');require(type(data) is dict and set(data)=={'fields','items'},'RESPONSE_SCHEMA_INVALID')
   fields=data['fields'];items=data['items'];require(fields==spec['fields'] and type(items) is list and len(items)<=spec['max_rows'],'RESPONSE_SCHEMA_OR_LIMIT_INVALID')
   today=datetime.fromisoformat(retrieved.replace('Z','+00:00')).astimezone(timezone(__import__('datetime').timedelta(hours=8))).strftime('%Y%m%d')
   for n,item in enumerate(items):
    require(type(item) is list and len(item)==len(fields),'RESPONSE_VECTOR_INVALID')
    v={k:normalized(x) for k,x in zip(fields,item)};rr=[]
    if spec['symbol'] is not None and v.get('ts_code')!=spec['symbol']:rr.append('ROW_SYMBOL_OUT_OF_SCOPE')
    if spec['symbol'] is None and not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)',v.get('ts_code') or ''):rr.append('STATUS_SYMBOL_INVALID')
    for k in ('ann_date','f_ann_date','end_date','trade_date','list_date','delist_date'):
     if v.get(k) not in (None,''):
      try:day(v[k])
      except ValueError:rr.append('INVALID_DATE_LITERAL');continue
      if k in ('ann_date','f_ann_date','end_date','trade_date','list_date') and v[k]>today:rr.append('FUTURE_DATE_LITERAL')
    if spec['api_name'] in ('daily_basic','stock_st','suspend_d') and v.get('trade_date')!=STATUS_DAY:rr.append('ROW_DAY_OUT_OF_SCOPE')
    if spec['api_name'] in ('income','balancesheet','cashflow','fina_indicator'):
     if not '20230101'<=v.get('end_date','')<=STATUS_DAY:rr.append('REPORT_PERIOD_OUT_OF_SCOPE')
     if not v.get('ann_date') or not '20230101'<=v['ann_date']<='20261006':rr.append('PUBLICATION_DATE_OUT_OF_REQUEST')
    if spec['api_name']=='suspend_d' and v.get('suspend_type')!='S':rr.append('STATUS_TYPE_FILTER_MISMATCH')
    row={'row_ordinal':n,'values':v}
    if rr:excluded.append({**row,'reason_codes':sorted(set(rr))})
    else:rows.append(row)
 except Exception as e:reasons.append(str(e) if str(e) in {'RESPONSE_SCHEMA_INVALID','RESPONSE_SCHEMA_OR_LIMIT_INVALID','RESPONSE_VECTOR_INVALID'} else 'SOURCE_SCHEMA_OR_CELL_INVALID')
 return {'provider_code':code,'response_fields':fields,'row_count':len(rows),'rows':rows,'excluded':excluded,'response_blocked':bool(reasons),'reason_codes':sorted(set(reasons)),'technical_access_observed':code==0}

def capture():
 require(not DEST.exists(),'WAVE_D_CAPTURE_ALREADY_EXISTS');old=_old_probe()
 fw=ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security');f=fw.SecKeychainSetUserInteractionAllowed;f.argtypes=(ctypes.c_bool,);f.restype=ctypes.c_int32;require(f(False)==0,'WAVE_D_NO_UI_LOOKUP_FAILED')
 credential,lookup=old.lookup_credential();requests=[];calls=0
 for spec in plan():
  q={**spec,'request_fingerprint':sha(canonical(spec)),'request_started_at':None,'retrieved_at':None,'available_at':None,'published_at':None,'event_time':None,'raw_ref':None,'raw_sha256':None,'raw_bytes':None,'http_status':None,'rows':[],'excluded':[],'row_count':0,'response_fields':[],'provider_code':None,'technical_access_observed':False,'response_blocked':True,'reason_codes':['SECRET_NOT_AVAILABLE']}
  if credential is not None:
   q['request_started_at']=clock();calls+=1
   try:
    status,raw=_send(spec,credential);at=clock();path=DEST/(spec['request_id']+'.response.json');private_write(path,raw)
    q.update(analyze(spec,raw,at));q.update(retrieved_at=at,available_at=at,raw_ref=str(path),raw_sha256=sha(raw),raw_bytes=len(raw),http_status=status)
    if status!=200:q['response_blocked']=True;q['reason_codes'].append('HTTP_STATUS_NOT_SUCCESS')
   except Exception:q['reason_codes']=['CONTROLLED_CAPTURE_FAILURE']
   time.sleep(3)
  requests.append(q)
 report={'version':'1.0.0','fixture':False,'phase':'WAVE_D','provider_id':'TUSHARE_MONTHLY_GATEWAY','state':'QUARANTINED','formal_source_admission':'BLOCKED','provider_identity_verified':False,'license_verified':False,'transport_integrity_verified':False,'historical_visibility_proven':False,'productionGate':False,'credential_lookup':lookup,'network_requests':calls,'request_budget':len(plan()),'code_hash':sha(Path(__file__).read_bytes()),'requests':requests,'completed_at':clock()}
 p=DEST/'report.json';private_write(p,canonical(report)+b'\n');credential=None
 ref={'path':str(p),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size};(ROOT/'docs/wave-d/capture-ref.json').write_bytes(canonical(ref)+b'\n')
 return {'network_requests':calls,'raw_captures':sum(q['raw_ref'] is not None for q in requests),'rows_eligible':sum(q['row_count'] for q in requests),'blocked_responses':sum(q['response_blocked'] for q in requests),'credential_presence':lookup['secret_presence'],'productionGate':False}

def verify_capture():
 ref=json.loads((ROOT/'docs/wave-d/capture-ref.json').read_bytes());p=Path(ref['path']);require(p==DEST/'report.json' and p.resolve()==p and p.stat().st_mode&0o777==0o600,'WAVE_D_CAPTURE_REF_INVALID')
 raw=p.read_bytes();require(sha(raw)==ref['sha256'] and len(raw)==ref['bytes'],'WAVE_D_CAPTURE_MUTATED');r=json.loads(raw)
 require(r['fixture'] is False and r['phase']=='WAVE_D' and r['state']=='QUARANTINED' and r['formal_source_admission']=='BLOCKED','WAVE_D_CAPTURE_PROMOTION')
 require(all(r[k] is False for k in ('provider_identity_verified','license_verified','transport_integrity_verified','historical_visibility_proven','productionGate')),'WAVE_D_CAPTURE_PROMOTION')
 require(r['code_hash']==sha(Path(__file__).read_bytes()) and len(r['requests'])==len(plan()) and r['request_budget']==len(plan()),'WAVE_D_CAPTURE_CODE_CHANGED')
 for q,s in zip(r['requests'],plan()):
  require(all(q[k]==v for k,v in s.items()) and q['request_fingerprint']==sha(canonical(s)),'WAVE_D_CAPTURE_SCOPE_CHANGED')
  if q['raw_ref'] is None:require(q['rows']==[] and q['response_blocked'],'WAVE_D_UNBACKED_ROWS');continue
  p=Path(q['raw_ref']);require(p==DEST/(s['request_id']+'.response.json') and p.resolve()==p and not p.is_symlink() and p.stat().st_mode&0o777==0o600,'WAVE_D_RAW_REF_INVALID')
  b=p.read_bytes();require(sha(b)==q['raw_sha256'] and len(b)==q['raw_bytes'],'WAVE_D_RAW_MUTATED')
  from overnight.analysis.inputs import instant_ns
  require(q['event_time'] is None and q['published_at'] is None and q['retrieved_at']==q['available_at'] and instant_ns(q['request_started_at'])<=instant_ns(q['retrieved_at'])<=instant_ns(r['completed_at']),'WAVE_D_CLOCK_BACKFILL')
  actual=analyze(s,b,q['retrieved_at'])
  if q['http_status']!=200:actual['response_blocked']=True;actual['reason_codes'].append('HTTP_STATUS_NOT_SUCCESS')
  require(all(q[k]==v for k,v in actual.items()),'WAVE_D_RAW_PROJECTION_CHANGED')
 return r

if __name__=='__main__':
 try:print(json.dumps(capture()))
 except Exception:print('WAVE_D_CAPTURE_FAILED_NO_ADMISSION');raise SystemExit(1)
