"""New SSE PDF epoch: recorded official 301 target, bounded public-host validation.

No redirects followed automatically; gateway credentials never enter this module.
Original failed public-probe evidence stays immutable.
"""
import urllib.request,urllib.error,urllib.parse,json,re,io,contextlib
from pathlib import Path
from pypdf import PdfReader,__version__ as parser_version
from .probe import ARCHIVE,ROOT,private_write,clock
from .public_probe import normalize_index
from wave_c.core import canonical,sha,require
class RejectRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'AshareLocalReference/1.0','Referer':'https://www.sse.com.cn/'})
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),RejectRedirect())
 try:r=opener.open(req,timeout=20)
 except urllib.error.HTTPError as e:r=e
 with r:
  b=r.read(16777217);require(len(b)<=16777216,'SSE_PDF_SIZE_LIMIT');return int(r.code),b,r.headers.get('Location')

def allowed_target(origin,target):
 a=urllib.parse.urlparse(origin);b=urllib.parse.urlparse(target or '')
 require(a.scheme=='https' and a.hostname=='www.sse.com.cn' and b.scheme=='https' and b.netloc=='static.sse.com.cn' and b.path==a.path and not b.query and not b.fragment and not b.username and not b.password,'SSE_REDIRECT_TARGET_FORBIDDEN')
 return target

def parse_pdf(raw,fact):
 require(raw.startswith(b'%PDF-'),'SSE_PDF_FORMAT_INVALID')
 warnings=io.StringIO()
 with contextlib.redirect_stderr(warnings):
  reader=PdfReader(io.BytesIO(raw));require(0<len(reader.pages)<=500,'SSE_PDF_PAGE_LIMIT')
  pages=[p.extract_text() or '' for p in reader.pages]
 text='\n'.join(pages);compact=re.sub(r'\s+','',text)
 require(fact['symbol'][:6] in compact and re.sub(r'\s+','',fact['title'])[:4] in compact and len(compact)>50,'SSE_PDF_IDENTITY_UNPROVEN')
 # Limited document observations only, not effect/forecast or a company ranking.
 lines=[re.sub(r'\s+','',s) for s in text.splitlines()]
 candidates=[s for s in lines if any(w in s for w in ('本公司','董事会','股东','报告','公告','减持','投资','合同','经营')) and len(s)>=12]
 snippet=(candidates[0] if candidates else compact[:40])[:40]
 return text,len(pages),snippet

def enrich():
 origin_ref=json.loads((ROOT/'docs/wave-d/public-ref.json').read_bytes());origin=json.loads(Path(origin_ref['path']).read_bytes());out=[]
 for q in origin['announcements']:
  if q['blocked']:continue
  require(normalize_index(Path(q['raw_ref']['path']).read_bytes(),q['symbol'])==q['facts'],'SSE_ORIGINAL_INDEX_CHANGED')
  for i,fact in enumerate(q['facts'][:2]):
   d={'symbol':q['symbol'],'fact':fact,'origin_index_ref':q['raw_ref'],'origin_index_retrieved_at':q['retrieved_at'],'redirect':None,'raw_ref':None,'text_ref':None,'retrieved_at':None,'available_at':None,'published_at':None,'pages':None,'body_verified':False,'snippet':None,'reason':None}
   try:
    status,raw,location=get(fact['uri']);at=clock();rp=ARCHIVE/'captures'/'SSE-G2'/(q['symbol']+'-'+str(i)+'.origin.response');private_write(rp,raw)
    d['redirect']={'status':status,'location':location,'retrieved_at':at,'raw_ref':{'path':str(rp),'sha256':sha(raw),'bytes':len(raw)}}
    require(status in (301,302,307,308),'SSE_EXPECTED_OFFICIAL_REDIRECT_MISSING');target=allowed_target(fact['uri'],location)
    status,pdf,_=get(target);end=clock();p=ARCHIVE/'captures'/'SSE-G2'/(q['symbol']+'-'+str(i)+'.pdf');private_write(p,pdf)
    d.update(raw_ref={'path':str(p),'sha256':sha(pdf),'bytes':len(pdf)},retrieved_at=end,available_at=end,static_uri=target,http_status=status)
    require(status==200,'SSE_STATIC_HTTP_FAILURE');text,pages,snippet=parse_pdf(pdf,fact);tp=p.with_suffix('.txt');private_write(tp,text.encode());d.update(text_ref={'path':str(tp),'sha256':sha(text.encode()),'bytes':len(text.encode())},pages=pages,snippet=snippet,body_verified=True)
   except Exception as e:d['reason']=str(e) if str(e).startswith('SSE_') else 'SSE_PDF_BODY_NOT_PROVEN'
   out.append(d)
 report={'version':'1.0.0','origin_public_ref':origin_ref,'documents':out,'parser':'pypdf','parser_version':parser_version,'code_hash':sha(Path(__file__).read_bytes()),'current_observed_only':True,'historical_visibility_proven':False,'formal_source_admission':'BLOCKED','productionGate':False,'completed_at':clock()}
 p=ARCHIVE/'captures'/'SSE-G2'/'report.json';private_write(p,canonical(report)+b'\n');(ROOT/'docs/wave-d/sse-enrich-ref.json').write_bytes(canonical({'path':str(p),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})+b'\n')
 print(json.dumps({'documents':len(out),'body_verified':sum(d['body_verified'] for d in out),'failure_reasons':sorted(set(d['reason'] for d in out if d['reason'])),'parser':parser_version,'productionGate':False}))
if __name__=='__main__':enrich()
