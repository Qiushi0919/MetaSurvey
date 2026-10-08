"""Nine bounded full-field statement requests from captured official schemas.

Research projections remain explicit selected fields; all full originals private.
"""
import json,ctypes,urllib.request,urllib.error,time
from html.parser import HTMLParser
from pathlib import Path
from .probe import ROOT,ARCHIVE,BASE,FIELDS,private_write,clock,analyze
from wave_b.probe import _old_probe,NoRedirect
from wave_c.core import canonical,sha,require,SYMBOLS
DEST=ARCHIVE/'captures'/'FULL-G1'
class Tables(HTMLParser):
 def __init__(self):super().__init__();self.tables=[];self.table=None;self.row=None;self.cell=None
 def handle_starttag(self,t,a):
  if t=='table':self.table=[]
  elif t=='tr' and self.table is not None:self.row=[]
  elif t in ('td','th') and self.row is not None:self.cell=''
 def handle_data(self,d):
  if self.cell is not None:self.cell+=d
 def handle_endtag(self,t):
  if t in ('td','th') and self.cell is not None:self.row.append(self.cell.strip());self.cell=None
  elif t=='tr' and self.row is not None:self.table.append(self.row);self.row=None
  elif t=='table' and self.table is not None:self.tables.append(self.table);self.table=None

def plan():
 out=[]
 for api,doc in [('income',33),('balancesheet',36),('cashflow',44)]:
  p=ARCHIVE/'public-reference'/('tushare-'+str(doc)+'.html');parser=Tables();parser.feed(p.read_text());tables=[t for t in parser.tables if t and '默认显示' in t[0]];require(len(tables)==1,'FULL_OFFICIAL_SCHEMA_AMBIGUOUS');fields=[r[0] for r in tables[0][1:]]
  require(len(fields)==len(set(fields)) and all(k in fields for k in FIELDS[api].split(',')),'FULL_OFFICIAL_FIELDS_INVALID')
  for symbol in SYMBOLS:out.append({'request_id':'FULL-'+api+'-'+symbol,'api_name':api,'symbol':symbol,'params':{'ts_code':symbol,'start_date':'20230101','end_date':'20261006','ts_type_name':BASE},'fields':fields,'max_rows':200,'kind':'THREE_STOCK_FULL_STATEMENT','official_schema_hash':sha(p.read_bytes())})
 return out

def send(spec,credential):
 require(canonical(spec) in [canonical(s) for s in plan()],'FULL_REQUEST_SCOPE_INVALID');old=_old_probe();require(type(credential) is old.Credential,'FULL_CREDENTIAL_TYPE_INVALID')
 url=BASE+'/'+spec['api_name'];wire={'api_name':spec['api_name'],'token':credential._value,'params':spec['params'],'fields':','.join(spec['fields'])}
 req=urllib.request.Request(url,data=canonical(wire),method='POST',headers={'Content-Type':'application/json'});opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 try:r=opener.open(req,timeout=20)
 except urllib.error.HTTPError as e:
  require(not 300<=e.code<400,'FULL_AUTH_REDIRECT_FORBIDDEN');r=e
 except Exception:raise ValueError('FULL_TRANSPORT_FAILURE') from None
 with r:require(r.geturl()==url,'FULL_AUTH_REDIRECT_FORBIDDEN');raw=r.read(old.MAX_BYTES+1);status=int(r.code)
 require(len(raw)<=old.MAX_BYTES,'FULL_RESPONSE_SIZE_LIMIT');old._secret_check(raw,credential);return status,raw

def capture():
 require(not DEST.exists(),'FULL_CAPTURE_ALREADY_EXISTS');old=_old_probe();fw=ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security');f=fw.SecKeychainSetUserInteractionAllowed;f.argtypes=(ctypes.c_bool,);f.restype=ctypes.c_int32;require(f(False)==0,'FULL_NO_UI_LOOKUP_FAILED');credential,lookup=old.lookup_credential();qs=[];calls=0
 for spec in plan():
  q={**spec,'request_fingerprint':sha(canonical(spec)),'request_started_at':None,'retrieved_at':None,'available_at':None,'published_at':None,'event_time':None,'raw_ref':None,'raw_sha256':None,'raw_bytes':None,'http_status':None,'rows':[],'excluded':[],'row_count':0,'response_fields':[],'provider_code':None,'technical_access_observed':False,'response_blocked':True,'reason_codes':['SECRET_NOT_AVAILABLE']}
  if credential:
   q['request_started_at']=clock();calls+=1
   try:
    status,raw=send(spec,credential);end=clock();p=DEST/(spec['request_id']+'.response.json');private_write(p,raw);q.update(analyze(spec,raw,end));q.update(retrieved_at=end,available_at=end,raw_ref=str(p),raw_sha256=sha(raw),raw_bytes=len(raw),http_status=status)
    if status!=200:q['response_blocked']=True;q['reason_codes'].append('HTTP_STATUS_NOT_SUCCESS')
   except Exception:q['reason_codes']=['CONTROLLED_FULL_CAPTURE_FAILURE']
   time.sleep(3)
  qs.append(q)
 r={'version':'1.0.0','fixture':False,'requests':qs,'network_requests':calls,'credential_lookup':lookup,'code_hash':sha(Path(__file__).read_bytes()),'historical_visibility_proven':False,'formal_source_admission':'BLOCKED','productionGate':False,'completed_at':clock()};p=DEST/'report.json';private_write(p,canonical(r)+b'\n');(ROOT/'docs/wave-d/full-statements-ref.json').write_bytes(canonical({'path':str(p),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})+b'\n');print(json.dumps({'requests':calls,'raw_captures':sum(q['raw_ref'] is not None for q in qs),'blocked':sum(q['response_blocked'] for q in qs),'field_counts':sorted(set(len(q['fields']) for q in qs)),'productionGate':False}))

def verify():
 ref=json.loads((ROOT/'docs/wave-d/full-statements-ref.json').read_bytes());p=Path(ref['path']);require(p==DEST/'report.json' and p.resolve()==p and p.stat().st_mode&0o777==0o600,'FULL_REF_INVALID');raw=p.read_bytes();require(sha(raw)==ref['sha256'] and len(raw)==ref['bytes'],'FULL_MANIFEST_CHANGED');r=json.loads(raw);require(r['fixture'] is False and not r['productionGate'] and not r['historical_visibility_proven'] and r['formal_source_admission']=='BLOCKED' and r['code_hash']==sha(Path(__file__).read_bytes()),'FULL_PROMOTION_OR_CODE_CHANGED')
 require(len(r['requests'])==9,'FULL_BUDGET_INVALID')
 from overnight.analysis.inputs import instant_ns
 for q,s in zip(r['requests'],plan()):
  require(all(q[k]==v for k,v in s.items()) and q['request_fingerprint']==sha(canonical(s)),'FULL_SCOPE_CHANGED')
  if q['raw_ref'] is None:require(not q['rows'] and q['response_blocked'],'FULL_UNBACKED_ROWS');continue
  p=Path(q['raw_ref']);require(p==DEST/(s['request_id']+'.response.json') and p.resolve()==p and p.stat().st_mode&0o777==0o600,'FULL_RAW_PATH_INVALID');b=p.read_bytes();require(sha(b)==q['raw_sha256'] and len(b)==q['raw_bytes'],'FULL_RAW_CHANGED')
  require(q['event_time'] is None and q['published_at'] is None and q['available_at']==q['retrieved_at'] and instant_ns(q['request_started_at'])<=instant_ns(q['retrieved_at'])<=instant_ns(r['completed_at']),'FULL_CLOCK_BACKFILL')
  actual=analyze(s,b,q['retrieved_at'])
  if q['http_status']!=200:actual['response_blocked']=True;actual['reason_codes'].append('HTTP_STATUS_NOT_SUCCESS')
  require(all(q[k]==v for k,v in actual.items()),'FULL_PROJECTION_CHANGED')
 return r
if __name__=='__main__':
 try:capture()
 except Exception:print('FULL_CAPTURE_FAILED_NO_ADMISSION');raise SystemExit(1)
