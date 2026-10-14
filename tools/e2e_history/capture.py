"""Bounded anonymous BaoStock capture. No credential reads or gateway calls.
Install the official SDK in an isolated directory; call with --sdk and fresh --out.
Only fixed registered nine symbols/date scope. Never prints response rows.
"""
from pathlib import Path
from datetime import datetime,timezone
from contextlib import redirect_stdout,redirect_stderr
import argparse,hashlib,io,json,socket,sys,time
ROOT=Path(__file__).resolve().parents[2]
def stamp():return datetime.now(timezone.utc).isoformat()
def dump(p,x):
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('--sdk',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--dns-evidence',type=Path);p.add_argument('--scope',choices=['probe','registered-nine'],default='probe');a=p.parse_args()
 if a.out.resolve().is_relative_to(ROOT):raise SystemExit('CAPTURE_MUST_BE_OUTSIDE_GIT')
 a.out.mkdir(parents=True,exist_ok=False);sys.path.insert(0,str(a.sdk));socket.setdefaulttimeout(20)
 import baostock as bs
 import baostock.common.contants as c
 assert c.BAOSTOCK_SERVER_IP=='public-api.baostock.com'
 route='SYSTEM_DNS'
 if a.dns_evidence:
  evidence=json.loads(a.dns_evidence.read_text())
  if evidence.get('url')!='https://dns.google/resolve?name=public-api.baostock.com&type=A':raise SystemExit('OFFICIAL_HOST_DNS_REQUIRED')
  ips=[x['data'] for x in evidence['response']['Answer'] if x['type']==1 and x['name']=='public-api.baostock.com.']
  if len(ips)!=1:raise SystemExit('EXACTLY_ONE_DNS_ANSWER_REQUIRED')
  c.BAOSTOCK_SERVER_IP=ips[0];route={'same_official_host_resolved_ip':ips[0],'dns_evidence_sha256':hashlib.sha256(a.dns_evidence.read_bytes()).hexdigest(),'system_settings_changed':False}

 rows=[];log=io.StringIO();start=stamp()
 with redirect_stdout(log),redirect_stderr(log):
  login=bs.login()
 dump(a.out/'login.json',{'source':'BaoStock anonymous public SDK','endpoint':'public-api.baostock.com:10030','sdk_version':'0.9.4','route':route,'started_at':start,'retrieved_at':stamp(),'error_code':login.error_code,'error_msg':login.error_msg,'credential_lookup':False})
 if login.error_code!='0':
  dump(a.out/'Manifest.json',{'kind':'BoundedBaoStockCapture','scope':a.scope,'finished_at':stamp(),'sources':[],'state':'LOGIN_FAILED','route':route,'error_code':login.error_code,'secret_access':False})
  print(json.dumps({'scope':a.scope,'state':'LOGIN_FAILED','error_code':login.error_code}));return 2
 def capture(kind,params):
  begin=stamp();response_rows=[];error=None;fields=[];code=None
  try:
   with redirect_stdout(log),redirect_stderr(log):
    rs=getattr(bs,kind)(**params);fields=list(rs.fields);code=rs.error_code
    while rs.error_code=='0' and rs.next():response_rows.append(rs.get_row_data())
    code=rs.error_code;error=rs.error_msg
  except Exception as exc:error=type(exc).__name__;code='CLIENT_EXCEPTION'
  name=f'{len(rows):03d}-{kind}.json';result={'source':'BaoStock','product':kind,'request':params,'started_at':begin,'retrieved_at':stamp(),'available_at_basis':'ACTUAL_RETRIEVAL_NOT_HISTORICAL_FIRST_VISIBLE','fields':fields,'rows':response_rows,'error_code':code,'error_msg':error,'row_count':len(response_rows),'evidence_grade':'SUPPLIER_RECONSTRUCTED_HISTORY','historical_visibility_proven':False}
  dump(a.out/name,result);rows.append({'path':name,'sha256':hashlib.sha256((a.out/name).read_bytes()).hexdigest(),'product':kind,'request':params,'row_count':len(response_rows),'error_code':code});print(json.dumps({k:rows[-1][k] for k in ('path','row_count','error_code')},ensure_ascii=False),flush=True)
  return code=='0'
 method=json.loads((ROOT/'experiments/e2e_pilot_v1/method.json').read_text());symbols=[m['symbol'] for g in method['universe'] for m in g['members']]
 codes=[s.split('.')[1].lower()+'.'+s.split('.')[0] for s in symbols]
 fields='date,code,open,high,low,close,preclose,volume,amount,adjustflag,tradestatus,isST'
 try:
  capture('query_trade_dates',{'start_date':'2025-06-03' if a.scope=='registered-nine' else '2026-09-28','end_date':'2026-09-30'})
  for code in (codes if a.scope=='registered-nine' else codes[:1]):
   if not capture('query_stock_basic',{'code':code}):break
   if not capture('query_history_k_data_plus',{'code':code,'fields':fields,'start_date':'2025-06-03' if a.scope=='registered-nine' else '2026-09-28','end_date':'2026-09-30','frequency':'d','adjustflag':'3'}):break
   for year in ('2025','2026'):capture('query_dividend_data',{'code':code,'year':year,'yearType':'operate'})
   capture('query_adjust_factor',{'code':code,'start_date':'2025-06-03','end_date':'2026-09-30'})
 finally:
  with redirect_stdout(log),redirect_stderr(log):bs.logout()
  dump(a.out/'Manifest.json',{'kind':'BoundedBaoStockCapture','scope':a.scope,'started_at':start,'finished_at':stamp(),'sdk_version':'0.9.4','sources':rows,'secret_access':False,'endpoint':'public-api.baostock.com:10030','transport':'OFFICIAL_SDK_PLAINTEXT_PUBLIC_ENDPOINT_NO_TLS_OR_SOURCE_SIGNATURE','source_identity_basis':'official website linked PyPI SDK default endpoint','no_historical_pit_claim':True})
 return 0 if all(x['error_code']=='0' for x in rows) else 1
if __name__=='__main__':raise SystemExit(main())
