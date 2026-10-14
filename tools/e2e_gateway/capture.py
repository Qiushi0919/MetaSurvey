"""Owner-authorized fixed-nine local compatible-gateway capture; RAM-only credential.
No endpoint fallback, redirect, credential log, public raw publication or trading.
"""
from pathlib import Path
from datetime import datetime,timezone
from contextlib import redirect_stdout,redirect_stderr
import argparse,hashlib,io,json,sys,time,urllib.request,urllib.error,shutil
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from backtest_5y.gateway import _credential_module,NoRedirect
ARCHIVE=ROOT.parent/'.p1b-archives/e2e-gateway-v3-20261014'
START,END='20250603','20260930'
FIELDS={
 'stock_basic':'ts_code,symbol,name,area,industry,market,exchange,curr_type,list_status,list_date,delist_date',
 'daily':'ts_code,trade_date,open,high,low,close,pre_close,vol,amount',
 'stk_limit':'ts_code,trade_date,pre_close,up_limit,down_limit',
 'suspend_d':'ts_code,trade_date,suspend_timing,suspend_type',
 'adj_factor':'ts_code,trade_date,adj_factor',
 'dividend':'ts_code,end_date,ann_date,div_proc,stk_div,stk_bo_rate,stk_co_rate,cash_div,cash_div_tax,record_date,ex_date,pay_date,div_listdate,imp_ann_date,base_date,base_share',
 'namechange':'ts_code,name,start_date,end_date,ann_date,change_reason',
 'trade_cal':'exchange,cal_date,is_open,pretrade_date'}
def stamp():return datetime.now(timezone.utc).isoformat()
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
 p.chmod(0o600)
def plan():
 method=json.loads((ROOT/'experiments/e2e_pilot_v1/method.json').read_text());symbols=[m['symbol'] for g in method['universe'] for m in g['members']]
 rows=[('trade_cal',{'exchange':e,'start_date':START,'end_date':END}) for e in ('SSE','SZSE')]
 for sym in symbols:
  for api in ('stock_basic','daily','stk_limit','suspend_d','adj_factor','dividend','namechange'):
   params={'ts_code':sym}
   if api in ('daily','stk_limit','suspend_d','adj_factor'):params.update(start_date=START,end_date=END)
   rows.append((api,params))
 return symbols,rows

def main():
 p=argparse.ArgumentParser();p.add_argument('--epoch',required=True);p.add_argument('--resume',type=Path);p.add_argument('--interval',type=int,default=15);a=p.parse_args()
 if not 3<=a.interval<=60:raise SystemExit('INTERVAL_OUT_OF_RANGE')
 import re
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,80}',a.epoch):raise SystemExit('SAFE_EPOCH_REQUIRED')
 folder=ARCHIVE/a.epoch;folder.mkdir(parents=True,exist_ok=False);folder.chmod(0o700)
 cfg=json.loads((ROOT/'config/provider/tushare-monthly-gateway.json').read_text());old=_credential_module()
 if cfg['endpoint']!=old.BASE_URL or cfg['source_classification']!='OWNER_PROVIDED_MONTHLY_GATEWAY':raise SystemExit('EXISTING_CONNECTION_CONFLICT')
 symbols,requests=plan();begin=stamp();sources=[]
 manifest={'kind':'GatewayCaptureManifest','version':'1.0.0','scope':{'symbols':symbols,'start_date':START,'end_date':END},'endpoint':old.BASE_URL,'connection_kind':'COMPATIBLE_GATEWAY_NOT_VERIFIED_OFFICIAL_TUSHARE','owner_authorization_ref':sha(ROOT/'docs/e2e-gateway-v3/Owner-Authorization.md'),'provider_license_status':'OWNER_AUTHORIZED_LOCAL_USE_UNVERIFIED_PROVIDER_LICENSE','started_at':begin,'sources':sources,'historical_visibility_proven':False,'public_raw_distribution':False,'cloud_transfer':False,'request_interval_seconds':a.interval}
 if a.resume:
  previous=a.resume
  if previous.parent!=ARCHIVE or previous.resolve()!=previous or previous.is_symlink():raise SystemExit('RESUME_SCOPE_MISMATCH')
  previous_manifest=json.loads((previous/'Manifest.json').read_text())
  if previous_manifest['scope']!=manifest['scope'] or previous_manifest['endpoint']!=manifest['endpoint'] or previous_manifest['owner_authorization_ref']!=manifest['owner_authorization_ref']:raise SystemExit('RESUME_SCOPE_OR_AUTH_CHANGED')
  manifest['predecessor']={'path':str(previous/'Manifest.json'),'sha256':sha(previous/'Manifest.json')}
  for entry in previous_manifest['sources']:
   if entry['state'] not in ('SUCCESS','EMPTY_RESPONSE'):continue
   src=previous/entry['path']
   if src.parent!=previous or src.is_symlink() or sha(src)!=entry['sha256']:raise SystemExit('RESUME_PIN_MISMATCH')
   wrapper=json.loads(src.read_text());raw=previous/wrapper['raw_path']
   if raw.parent!=previous or raw.is_symlink() or sha(raw)!=wrapper['raw_sha256']:raise SystemExit('RESUME_RAW_PIN_MISMATCH')
   shutil.copyfile(raw,folder/raw.name);shutil.copyfile(src,folder/src.name);sources.append(entry)
 credential,lookup=old.lookup_credential();dump(folder/'credential-lookup.json',lookup)
 if credential is None:
  manifest.update(state='SECRET_NOT_AVAILABLE',retrieved_at=stamp());dump(folder/'Manifest.json',manifest);print(json.dumps(lookup));return 2
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 try:
  for i,(api,params) in enumerate(requests):
   if any(x['api_name']==api and x['params']==params for x in sources):continue
   start=stamp();fields=FIELDS[api];url=old.BASE_URL+'/'+api;name=f'{i:03d}-{api}-{params.get("ts_code",params.get("exchange"))}'
   wrapper={'api_name':api,'params':params,'request_fields':fields,'request_started_at':start,'retrieved_at':None,'fields':[],'items':[],'error_code':None,'row_count':0,'state':'REQUEST_FAILED','raw_path':None,'raw_sha256':None}
   try:
    body=old._canonical({'api_name':api,'token':credential._value,'params':dict(params,ts_type_name=old.BASE_URL),'fields':fields})
    req=urllib.request.Request(url,data=body,method='POST',headers={'Content-Type':'application/json'})
    try:response=opener.open(req,timeout=25)
    except urllib.error.HTTPError as err:
     if 300<=err.code<400:raise ValueError('AUTH_REDIRECT_BLOCKED') from None
     response=err
    with response:
     if response.geturl()!=url:raise ValueError('AUTH_REDIRECT_BLOCKED')
     status=response.code;raw=response.read(old.MAX_BYTES+1)
    old._secret_check(raw,credential)
    rawfile=folder/(name+'.raw.json')
    with rawfile.open('xb') as f:f.write(raw)
    rawfile.chmod(0o600);table=json.loads(raw,parse_float=str);data=table.get('data')
    wrapper.update(raw_path=rawfile.name,raw_sha256=sha(rawfile),http_status=status,error_code=table.get('code'))
    if status==200 and table.get('code')==0 and isinstance(data,dict):
     keys=data.get('fields',[]);items=data.get('items',[])
     if len(set(keys))!=len(keys) or any(len(v)!=len(keys) for v in items):raise ValueError('RESPONSE_TABLE_INVALID')
     wrapper.update(fields=keys,items=items,row_count=len(items),state='SUCCESS' if items else 'EMPTY_RESPONSE')
    else:
     msg=str(table.get('msg') or '')
     wrapper['state']='IP_CONCURRENCY_LIMIT' if 'IP' in msg.upper() and any(w in msg for w in ('限制','超限','多个')) else ('ENTITLEMENT_NOT_GRANTED' if any(w in msg for w in ('权限','积分','无权')) else 'API_ERROR')
   except Exception as exc:wrapper['error_type']=type(exc).__name__
   wrapper['retrieved_at']=stamp();file=folder/(name+'.json');dump(file,wrapper)
   entry={'path':file.name,'sha256':sha(file),'api_name':api,'params':params,'fields':wrapper['fields'],'row_count':wrapper['row_count'],'error_code':wrapper['error_code'],'state':wrapper['state']};sources.append(entry)
   print(json.dumps({k:entry[k] for k in ('api_name','params','row_count','error_code','state')},ensure_ascii=False),flush=True)
   if wrapper['state']=='IP_CONCURRENCY_LIMIT':break
   if i+1<len(requests):time.sleep(a.interval)
 finally:
  manifest.update(retrieved_at=stamp(),state='CAPTURE_COMPLETE' if len(sources)==len(requests) else 'CAPTURE_PARTIAL',planned_requests=len(requests));dump(folder/'Manifest.json',manifest)
 return 0
if __name__=='__main__':raise SystemExit(main())
