"""Bounded official public product references and SSE announcement originals."""
import urllib.request,urllib.error,urllib.parse,json,re,importlib.util
from pathlib import Path
from .probe import ARCHIVE,ROOT,private_write,clock
from wave_b.probe import NoRedirect
from wave_c.core import canonical,sha,require,SYMBOLS,day
REFERENCES={**{'tushare-'+str(n):'https://tushare.pro/document/2?doc_id='+str(n) for n in [25,32,33,36,44,79,214,397,146]},'sse-legal':'https://www.sse.com.cn/home/legal/','sse-holiday':'https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml'}
INDEX='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
START='2026-04-08';END='2026-10-06'
def fetch(url,maxbytes):
 u=urllib.parse.urlparse(url);require(u.scheme=='https' and u.hostname in {'tushare.pro','www.sse.com.cn','query.sse.com.cn'} and not u.username and not u.password and u.port is None,'WAVE_D_PUBLIC_URL_FORBIDDEN')
 req=urllib.request.Request(url,headers={'User-Agent':'AshareLocalReference/1.0','Referer':'https://www.sse.com.cn/'})
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
 try:r=opener.open(req,timeout=20)
 except urllib.error.HTTPError as e:
  require(not 300<=e.code<400,'WAVE_D_PUBLIC_REDIRECT_FORBIDDEN');r=e
 with r:
  require(r.geturl()==url,'WAVE_D_PUBLIC_REDIRECT_FORBIDDEN');b=r.read(maxbytes+1);status=int(r.code)
 require(len(b)<=maxbytes,'WAVE_D_PUBLIC_RESPONSE_SIZE');return status,b

def index_url(symbol):
 return INDEX+'?'+urllib.parse.urlencode({'isPagination':'true','productId':symbol[:6],'keyWord':'','securityType':'0101,120100,020100,020200,120200','reportType2':'','reportType':'ALL','beginDate':START,'endDate':END,'pageHelp.pageSize':'5','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.endPage':'1'})

def normalize_index(raw,symbol):
 d=json.loads(raw);code=symbol[:6]
 require(type(d) is dict and d.get('productId')==code and d.get('beginDate')==START and d.get('endDate')==END and d.get('isPagination')=='true','SSE_INDEX_SCOPE_MISMATCH')
 require(d.get('pageHelp',{}).get('pageNo')==1 and d['pageHelp'].get('pageSize')==5 and type(d.get('result')) is list and len(d['result'])<=100,'SSE_INDEX_PAGINATION_INVALID')
 out=[]
 for n,row in enumerate(d['result'][:5]):
  date=row.get('SSEDATE');require(type(date) is str and START<=date<=END,'SSE_ANNOUNCEMENT_DATE_INVALID');day(date.replace('-',''))
  require(row.get('SECURITY_CODE')==code,'SSE_ANNOUNCEMENT_SYMBOL_MISMATCH')
  title=row.get('TITLE');require(type(title) is str and 0<len(title)<=300 and not re.search(r'[<>\x00-\x1f]',title),'SSE_TITLE_INVALID')
  uri=urllib.parse.urljoin('https://www.sse.com.cn',row.get('URL',''));u=urllib.parse.urlparse(uri)
  require(u.scheme=='https' and u.netloc=='www.sse.com.cn' and not u.query and not u.fragment and re.fullmatch(r'/disclosure/listedinfo/announcement/c/new/'+re.escape(date)+'/'+code+'_'+date.replace('-','')+r'_[A-Z0-9]{4}\.pdf',u.path),'SSE_DOCUMENT_URL_INVALID')
  out.append({'symbol':symbol,'date':date,'title':title,'uri':uri,'row_ordinal':n})
 return out

def pdf_text(raw):
 require(raw.startswith(b'%PDF-'),'SSE_DOCUMENT_NOT_PDF')
 try:
  import fitz
  with fitz.open(stream=raw,filetype='pdf') as d:
   require(len(d)<=500,'SSE_PDF_PAGE_LIMIT');return '\n'.join(p.get_text() for p in d),len(d)
 except ImportError:raise ValueError('PDF_PARSER_UNAVAILABLE') from None

def capture_public():
 items=[];ann=[]
 for name,uri in REFERENCES.items():
  q={'name':name,'uri':uri,'status':None,'retrieved_at':None,'raw_ref':None,'reason':None}
  try:
   status,b=fetch(uri,2097152);p=ARCHIVE/'public-reference'/(name+'.html');private_write(p,b);q.update(status=status,retrieved_at=clock(),raw_ref={'path':str(p),'sha256':sha(b),'bytes':len(b)})
  except Exception:q['reason']='CONTROLLED_PUBLIC_CAPTURE_FAILURE'
  items.append(q)
 for symbol in SYMBOLS:
  uri=index_url(symbol);q={'symbol':symbol,'uri':uri,'status':None,'retrieved_at':None,'available_at':None,'published_at':None,'raw_ref':None,'facts':[],'documents':[],'blocked':True,'reason':None,'coverage_complete':False}
  try:
   status,b=fetch(uri,524288);at=clock();p=ARCHIVE/'captures'/('SSE-'+symbol+'.index.json');private_write(p,b);q.update(status=status,retrieved_at=at,available_at=at,raw_ref={'path':str(p),'sha256':sha(b),'bytes':len(b)})
   require(status==200,'SSE_INDEX_HTTP_FAILURE');facts=normalize_index(b,symbol);q.update(facts=facts,blocked=False)
   # First two approved recent documents only. Metadata/title is never body fact.
   for i,fact in enumerate(facts[:2]):
    doc={'fact':fact,'status':None,'retrieved_at':None,'raw_ref':None,'text_ref':None,'pages':None,'body_verified':False,'reason':None}
    try:
     status,pdf=fetch(fact['uri'],16777216);end=clock();p=ARCHIVE/'captures'/('SSE-'+symbol+'-'+str(i)+'.pdf');private_write(p,pdf);doc.update(status=status,retrieved_at=end,raw_ref={'path':str(p),'sha256':sha(pdf),'bytes':len(pdf)})
     require(status==200,'SSE_PDF_HTTP_FAILURE');text,pages=pdf_text(pdf);require(len(text)>50 and symbol[:6] in text and fact['title'][:4] in text.replace(' ','').replace('\n',''),'SSE_PDF_IDENTITY_UNPROVEN')
     tp=p.with_suffix('.txt');private_write(tp,text.encode());doc.update(text_ref={'path':str(tp),'sha256':sha(text.encode()),'bytes':len(text.encode())},pages=pages,body_verified=True)
    except Exception:doc['reason']='SSE_PDF_BODY_NOT_PROVEN'
    q['documents'].append(doc)
  except Exception as e:q['reason']=str(e) if str(e).startswith('SSE_') else 'CONTROLLED_SSE_CAPTURE_FAILURE'
  ann.append(q)
 report={'version':'1.0.0','current_observed_only':True,'historical_visibility_proven':False,'formal_source_admission':'BLOCKED','productionGate':False,'references':items,'announcements':ann,'code_hash':sha(Path(__file__).read_bytes()),'completed_at':clock()}
 p=ARCHIVE/'captures'/'public-report.json';private_write(p,canonical(report)+b'\n');(ROOT/'docs/wave-d/public-ref.json').write_bytes(canonical({'path':str(p),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})+b'\n')
 return {'public_references':len(items),'SSE_indexes':len(ann),'indexes_usable':sum(not q['blocked'] for q in ann),'PDFs_attempted':sum(len(q['documents']) for q in ann),'PDF_bodies_verified':sum(d['body_verified'] for q in ann for d in q['documents']),'productionGate':False}

if __name__=='__main__':print(json.dumps(capture_public()))
