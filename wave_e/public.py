"""Credential-free finite official evidence capture; no authenticated transport."""
import contextlib,gzip,io,json,os,re,urllib.request,urllib.error,urllib.parse,zlib
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
from hashlib import sha256
from pypdf import PdfReader,__version__ as parser_version
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path('/Users/qiushi/投资研究/.p1b-archives/wave-e-20261006')
SYMBOLS=('603993.SH','600312.SH','603228.SH')
DOCS={**{'tushare-'+str(n):'https://tushare.pro/document/'+str(level)+'?doc_id='+str(n) for n,level in [(405,1),(409,1),(290,2),(27,2),(44,2),(32,2),(33,2),(36,2),(79,2)]},'sse-holiday':'https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml'}
MAX=16777216
HEADERS={'User-Agent':'AshareLocalOfficialEvidence/1.0','Accept':'application/pdf,text/html,application/json;q=0.9','Accept-Encoding':'identity','Referer':'https://www.sse.com.cn/'}
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(raw):return 'sha256:'+sha256(raw).hexdigest()
def now():return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
def require(c,reason):
 if not c:raise ValueError(reason)
def private_write(p,raw):
 require(p.is_relative_to(ARCHIVE) and p.resolve()==p and not p.exists(),'WAVE_E_PRIVATE_PATH_INVALID');p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 with os.fdopen(os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw)
def ref(p):b=p.read_bytes();return {'path':str(p),'sha256':sha(b),'bytes':len(b)}
def checked_ref(r):
 p=Path(r['path']);require(p.is_relative_to(ARCHIVE) and p.resolve()==p and not p.is_symlink() and p.stat().st_mode&0o777==0o600,'WAVE_E_PUBLIC_REF_INVALID');b=p.read_bytes();require(sha(b)==r['sha256'] and len(b)==r['bytes'],'WAVE_E_PUBLIC_REF_CHANGED');return b
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.skip=0
 def handle_starttag(self,t,a):
  if t in ('script','style'):self.skip+=1
 def handle_endtag(self,t):
  if t in ('script','style') and self.skip:self.skip-=1
 def handle_data(self,s):
  if not self.skip:self.parts.append(s)
def html_text(raw):p=Text();p.feed(raw.decode('utf-8','replace'));return '\n'.join(p.parts)
def origins():
 from wave_d.public_probe import normalize_index
 v=json.loads((ROOT/'docs/wave-d/public-ref.json').read_bytes());p=Path(v['path']);b=p.read_bytes();require(sha(b)==v['sha256'],'WAVE_E_PREDECESSOR_PUBLIC_CHANGED');old=json.loads(b);out=[]
 for q in old['announcements']:
  require(q['symbol'] in SYMBOLS and not q['blocked'],'WAVE_E_PREDECESSOR_SSE_SCOPE')
  raw=Path(q['raw_ref']['path']).read_bytes();require(sha(raw)==q['raw_ref']['sha256'] and normalize_index(raw,q['symbol'])==q['facts'],'WAVE_E_PREDECESSOR_INDEX_CHANGED')
  for fact in q['facts'][:2]:out.append({'fact':fact,'index_ref':q['raw_ref'],'index_retrieved_at':q['retrieved_at']})
 require(len(out)==6,'WAVE_E_SSE_PLAN_INVALID');return out

def validate_origin(f):
 u=urllib.parse.urlsplit(f['uri']);code=f['symbol'][:6];date=f['date']
 require(f['symbol'] in SYMBOLS and u.scheme=='https' and u.netloc=='www.sse.com.cn' and not u.query and not u.fragment and re.fullmatch('/disclosure/listedinfo/announcement/c/new/'+re.escape(date)+'/'+code+'_'+date.replace('-','')+r'_[A-Z0-9]{4}\.pdf',u.path),'WAVE_E_SSE_IDENTITY_URL_INVALID');return f['uri']
def allowed_redirect(origin,target):
 a=urllib.parse.urlsplit(origin);b=urllib.parse.urlsplit(target or '')
 require(a.scheme=='https' and a.netloc=='www.sse.com.cn' and b.scheme=='https' and b.netloc=='static.sse.com.cn' and b.path==a.path and not b.query and not b.fragment,'WAVE_E_UNEXPECTED_PUBLIC_TARGET');return target

def decode(raw,encoding):
 require(len(raw)<=MAX,'WAVE_E_PUBLIC_SIZE_LIMIT')
 if encoding in ('','identity',None):out=raw
 elif encoding=='gzip':
  with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:out=f.read(MAX+1)
 elif encoding=='deflate':
  dz=zlib.decompressobj();out=dz.decompress(raw,MAX+1);require(dz.eof and not dz.unconsumed_tail,'WAVE_E_PUBLIC_ENCODING_LIMIT')
 else:raise ValueError('WAVE_E_PUBLIC_UNSUPPORTED_ENCODING')
 require(len(out)<=MAX,'WAVE_E_PUBLIC_DECODED_LIMIT');return out

def get(url,name):
 u=urllib.parse.urlsplit(url);approved=set(DOCS.values())|{validate_origin(x['fact']) for x in origins()}|{validate_origin(x['fact']).replace('https://www.sse.com.cn/','https://static.sse.com.cn/') for x in origins()}
 require(url in approved and u.scheme=='https' and u.netloc in {'tushare.pro','www.sse.com.cn','static.sse.com.cn'} and not u.username and not u.password and not u.fragment,'WAVE_E_UNEXPECTED_PUBLIC_TARGET')
 req=urllib.request.Request(url,headers=HEADERS);opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect());status=None;at=None;raw=None;meta={'request_url':url,'request_fingerprint':sha(canonical({'url':url,'headers':HEADERS,'method':'GET'})),'method':'GET','credentials_attached':False,'status':None,'content_type':None,'content_encoding':None,'retrieved_at':None,'available_at':None,'raw_ref':None,'decoded_ref':None,'redirect_location':None,'reason':None}
 try:
  try:response=opener.open(req,timeout=20)
  except urllib.error.HTTPError as e:response=e
  with response:
   require(response.geturl()==url,'WAVE_E_UNEXPECTED_PUBLIC_TARGET');raw=response.read(MAX+1);status=int(response.code);meta.update(status=status,content_type=response.headers.get('Content-Type',''),content_encoding=response.headers.get('Content-Encoding','').lower(),redirect_location=response.headers.get('Location'))
  require(len(raw)<=MAX,'WAVE_E_PUBLIC_SIZE_LIMIT');at=now();p=ARCHIVE/'public/G1'/(name+'.wire');private_write(p,raw);meta.update(retrieved_at=at,available_at=at,raw_ref=ref(p));decoded=decode(raw,meta['content_encoding']);dp=ARCHIVE/'public/G1'/(name+'.decoded');private_write(dp,decoded);meta['decoded_ref']=ref(dp);return meta,decoded
 except Exception as e:
  if str(e)=='WAVE_E_UNEXPECTED_PUBLIC_TARGET':raise
  meta['reason']=str(e) if str(e).startswith('WAVE_E_') else 'WAVE_E_PUBLIC_CAPTURE_FAILURE';return meta,None

def pdf_identity(raw,fact):
 validate_origin(fact);require(raw.startswith(b'%PDF-'),'WAVE_E_SSE_DECODED_RESPONSE_NOT_PDF');sink=io.StringIO()
 with contextlib.redirect_stderr(sink):
  pdf=PdfReader(io.BytesIO(raw));require(0<len(pdf.pages)<=500,'WAVE_E_PDF_PAGE_LIMIT');text='\n'.join(p.extract_text() or '' for p in pdf.pages)
 compact=re.sub(r'\s+','',text);title=re.sub(r'\s+','',fact['title']);code=fact['symbol'][:6]
 require(re.search(r'证券代码[:：]'+re.escape(code)+r'(?!\d)',compact) and title in compact and len(compact)>80,'WAVE_E_PDF_BODY_IDENTITY_UNPROVEN');return text,len(pdf.pages)

def capture():
 os.umask(0o077);items=[];docs=[]
 for name,url in DOCS.items():
  m,b=get(url,name);require(not m['redirect_location'],'WAVE_E_UNEXPECTED_PUBLIC_TARGET');m['reference_identity']='PUBLIC_DOCUMENT_ONLY_NO_ACCOUNT_ENTITLEMENT';m['text_ref']=None
  if b is not None and m['status']==200:
   text=html_text(b);p=ARCHIVE/'public/G1'/(name+'.txt');private_write(p,text.encode());m['text_ref']=ref(p)
  items.append(m)
 for i,x in enumerate(origins()):
  f=x['fact'];url=validate_origin(f);m,b=get(url,'sse-'+str(i)+'-origin');chain=[m];result={'symbol':f['symbol'],'index_fact':f,'index_ref':x['index_ref'],'index_retrieved_at':x['index_retrieved_at'],'redirect_chain':chain,'body_verified':False,'body_identity_checks':{'index_code_date_path_bound':True,'pdf_magic':False,'body_security_code':False,'full_index_title':False},'text_ref':None,'pages':None,'reason':None}
  if m['status'] in (301,302,307,308):
   target=allowed_redirect(url,m['redirect_location']);m,b=get(target,'sse-'+str(i)+'-static');chain.append(m)
  elif m['redirect_location']:raise ValueError('WAVE_E_UNEXPECTED_PUBLIC_TARGET')
  try:
   require(m['status']==200 and b is not None,'WAVE_E_SSE_HTTP_OR_CAPTURE_FAILURE');text,pages=pdf_identity(b,f);p=ARCHIVE/'public/G1'/('sse-'+str(i)+'.txt');private_write(p,text.encode());result.update(body_verified=True,text_ref=ref(p),pages=pages,body_identity_checks={'index_code_date_path_bound':True,'pdf_magic':True,'body_security_code':True,'full_index_title':True})
  except Exception as e:result['reason']=str(e) if str(e).startswith('WAVE_E_') else 'WAVE_E_SSE_BODY_NOT_PROVEN'
  docs.append(result)
 report={'version':'1.0.0','code_hash':sha(Path(__file__).read_bytes()),'parser':'pypdf','parser_version':parser_version,'references':items,'documents':docs,'public_GET_requests':len(items)+sum(len(x['redirect_chain']) for x in docs),'authenticated_requests':0,'credential_lookups':0,'current_observed_only':True,'historical_visibility_proven':False,'formal_source_admission':'BLOCKED','productionGate':False,'completed_at':now()}
 p=ARCHIVE/'public/G1/report.json';private_write(p,canonical(report)+b'\n');(ROOT/'docs/wave-e/public-ref.json').write_bytes(canonical(ref(p))+b'\n')
 print(json.dumps({'public_GET_requests':report['public_GET_requests'],'references':len(items),'SSE_documents':len(docs),'verified_bodies':sum(x['body_verified'] for x in docs),'failures':sorted(set(x['reason'] for x in docs if x['reason'])),'authenticated_requests':0,'credential_lookups':0,'productionGate':False}))
if __name__=='__main__':capture()
