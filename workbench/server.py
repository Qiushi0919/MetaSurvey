"""Loopback-only workbench. Every endpoint is a fixed, read-only projection."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse, hashlib, json, re, subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path('/Users/qiushi/投资研究/.p1b-archives/wave-d-20261006/results/REPORTS-G4')
SYMBOLS = ('603993.SH', '600312.SH', '603228.SH')
FILES = {
 'integration': 'docs/backtest-5y-integration/Status.json',
 'integration-report': 'docs/backtest-5y-integration/Acceptance-Report.md',
 'contract-gaps': 'docs/backtest-5y-integration/Remaining-Contract-Gaps-v1.json',
 'methods': 'docs/core40-method-proposal/Owner-Decisions.md',
 'forward': 'docs/day1-reveal/Status.json',
 'manifest': 'docs/wave-d/evidence.json',
 'handoff': 'docs/handoff/MetaSurvey-Handoff.md',
 'readback': 'docs/handoff/Evidence-Index-20261008.json',
 'strategy': 'docs/wave-f/Frozen-StrategySpec-v1.json',
 'account-template': 'config/account-profile.unconfigured.v1.json',
 'latest': 'docs/review/LATEST.md',
 'architecture': 'docs/review/ARCHITECTURE.md',
}
SECRET = re.compile(r'-----BEGIN (?:ENCRYPTED |RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:ghp_|github_pat_|sk-proj-)[\w-]{20,}|[?&](?:token|api_key)=[\w-]{20,}|pro_api\([\"\x27][\w-]{20,}', re.I)

class ReadError(Exception):
 def __init__(self, code, source): self.code, self.source = code, source

def now(): return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
def digest(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()

class Reader:
 def __init__(self, root=ROOT, private=PRIVATE): self.root, self.private = Path(root), Path(private)
 def read_path(self, p, base):
  if not p.is_relative_to(base) or p.resolve() != p or p.is_symlink(): raise ReadError('UNSAFE_PATH', p.name)
  try:
   with p.open('rb') as f: raw = f.read(4_000_001)
  except FileNotFoundError: raise ReadError('FILE_MISSING', p.name)
  except OSError: raise ReadError('FILE_UNREADABLE', p.name)
  if len(raw)>4_000_000: raise ReadError('FILE_TOO_LARGE', p.name)
  try: text=raw.decode('utf-8')
  except UnicodeError: raise ReadError('INVALID_UTF8', p.name)
  if SECRET.search(text) or re.search(r'''(?:token|api_key|access_token|password)\s*[=:]\s*["']([A-Za-z0-9_-]{24,})["']''',text,re.I): raise ReadError('SENSITIVE_CONTENT_BLOCKED', p.name)
  return raw, text
 def document(self, key):
  if key not in FILES: raise ReadError('NOT_ALLOWLISTED', key)
  p=self.root/FILES[key]; raw,text=self.read_path(p,self.root)
  if key=='account-template':
   try: profile=json.loads(text)
   except ValueError: raise ReadError('INVALID_JSON',FILES[key])
   if type(profile) is not dict or profile.get('profile_kind')!='UNCONFIGURED' or profile.get('account_id')!='UNSET_REQUIRED': raise ReadError('RUNTIME_ACCOUNT_NOT_EXPOSED',FILES[key])
  return {'id':key,'source':FILES[key],'sha256':digest(raw),'bytes':len(raw),'read_at':now(),'content':text,'visibility':'REVIEW_METADATA','result_type':'DOCUMENT_NOT_EXECUTION'}
 def json(self, key, kind=None, version='1.0.0'):
  doc=self.document(key)
  try: data=json.loads(doc['content'])
  except ValueError: raise ReadError('INVALID_JSON', FILES[key])
  if type(data) is not dict: raise ReadError('INVALID_SHAPE', FILES[key])
  if data.get('version')!=version: raise ReadError('UNSUPPORTED_VERSION',FILES[key])
  if kind and data.get('kind')!=kind: raise ReadError('UNSUPPORTED_KIND',FILES[key])
  return data, {k:v for k,v in doc.items() if k!='content'}
 def research(self, symbol):
  if symbol not in SYMBOLS: raise ReadError('NOT_ALLOWLISTED',symbol)
  manifest,meta=self.json('manifest')
  name=symbol+'.report.md'
  matches=[r for r in manifest.get('artifacts',[]) if r.get('name')==name]
  if len(matches)!=1: raise ReadError('MANIFEST_ENTRY_INVALID',name)
  row=matches[0]; path=self.private/name
  # A new base is only an internal test injection. The manifest never supplies the file path.
  if Path(row.get('path','')).name!=name: raise ReadError('MANIFEST_PATH_INVALID',name)
  if self.private==PRIVATE and row.get('path')!=str(path): raise ReadError('MANIFEST_PATH_INVALID',name)
  raw,text=self.read_path(path,self.private)
  if row.get('sha256')!=digest(raw) or type(row.get('bytes')) is not int or row['bytes']!=len(raw): raise ReadError('HASH_MISMATCH',name)
  title=text.splitlines()[0].lstrip('# ')
  if not title.endswith('— 本地真实研究报告 2.0') or symbol not in title: raise ReadError('UNSUPPORTED_REPORT_VERSION',name)
  observation=re.search(r'本轮观察截止：([^；\n]+)',text)
  return {'id':'research:'+symbol,'symbol':symbol,'title':title,'source':str(path),'manifest_source':meta,'sha256':digest(raw),'expected_sha256':row['sha256'],'integrity':'MATCH','bytes':len(raw),'read_at':now(),'data_cutoff':observation.group(1) if observation else None,'code_version':'Wave D report 2.0 / sealed manifest 1.0.0','result_type':'LOCAL_EXPERIMENTAL_REAL_RESEARCH','scope':'LOCAL_ONLY / NON_TRADEABLE / UNVERIFIED_GATEWAY','formal_grade':None,'formal_candidate':False,'content':text}
 def state(self):
  state={'adapter_version':'1.0.0-workbench-readonly','read_at':now(),'mode':'LOCAL_READ_ONLY','task_runtime':'NOT_CONNECTED_NO_LIVE_HEARTBEAT','errors':[],'panels':{},'studies':[],'formal_candidates':{'state':'NOT_AVAILABLE','reason':'No admitted formal candidate producer is connected. Research objects are not recommendations.'}}
  for key,kind in [('integration','RootP1HistoricalIntegrationGate'),('forward','Day1RevealStatus')]:
   try:
    data,meta=self.json(key,kind)
    allowed=(key=='integration' and data.get('engineering_integration') in ['PASS_WITH_CONDITIONS','PASS','FAIL','BLOCKED']) or (key=='forward' and data.get('actual_D1') in ['BLOCKED','PASS','PENDING','NOT_RUN'])
    if not allowed: raise ReadError('UNKNOWN_STATUS',FILES[key])
    if key=='integration':
     for field in ['actual_PIT_admitted','formal_windows_executed']:
      if type(data.get('strategy',{}).get(field)) is not int: raise ReadError('INVALID_SHAPE',FILES[key])
     if data.get('strategy',{}).get('engine') not in ['ENGINE_NOT_RUN','ENGINE_FAILED','ENGINE_RUN']: raise ReadError('UNKNOWN_STATUS',FILES[key])
    else:
     if type(data.get('actual_forward_days')) is not int: raise ReadError('INVALID_SHAPE',FILES[key])
    state['panels'][key]={'data':data,'provenance':meta,'result_type':'RECORDED_ENGINEERING_STATUS_NOT_LIVE_RUNTIME','report_cutoff':data.get('recorded_at'),'code_commit':data.get('integrated_code_commit',data.get('code_candidate_commit'))}
   except ReadError as e: state['errors'].append({'panel':key,'code':e.code,'source':e.source})
  for symbol in SYMBOLS:
   try:
    report=self.research(symbol); state['studies'].append({k:v for k,v in report.items() if k!='content'})
   except ReadError as e: state['studies'].append({'symbol':symbol,'error':e.code,'source':e.source})
  try:
   report=self.document('integration-report'); text=report['content']; m=re.search(r'([\d,]+)股票价格日期、([\d,]+)财务报告期记录',text)
   state['coverage']={'price_dates':int(m[1].replace(',','')) if m else None,'financial_period_records':int(m[2].replace(',','')) if m else None,'provenance':{k:v for k,v in report.items() if k!='content'},'result_type':'COUNTS_RECORDED_IN_REPORT_NOT_PIT_ADMISSION'}
  except ReadError as e: state['errors'].append({'panel':'coverage','code':e.code,'source':e.source})
  try:
   index,_=self.json('readback','MetaSurveyHandoffReadOnlyEvidenceIndex')
   differences=[]
   for baseline in index['read_only_replay']['old_pin_differences']:
    for pin in baseline['mismatches']:
     rel=pin['path']
     if rel not in ('.github/workflows/p0.yml','.github/workflows/real-slice.yml'): raise ReadError('UNSAFE_REFERENCE','readback')
     actual=digest(self.read_path(self.root/rel,self.root)[0])
     if actual!=pin['expected_sha256']: differences.append({'source':rel,'expected':pin['expected_sha256'],'actual':actual})
   state['compatibility']={'state':'WAVE_C_DEPENDENCY_INVALIDATED' if differences else 'REQUIRES_FULL_REPLAY_VERIFICATION','source':FILES['readback'],'differences':differences,'result_type':'DEPENDENCY_HASH_CHECK_NOT_RESEARCH_RUN'}
  except (ReadError,KeyError,TypeError) as e: state['errors'].append({'panel':'compatibility','code':getattr(e,'code','INVALID_SHAPE'),'source':'readback'})
  try:
   git='/opt/homebrew/bin/git' if Path('/opt/homebrew/bin/git').exists() else 'git'
   state['code']={k:subprocess.check_output([git,'-C',str(self.root),*args],text=True,stderr=subprocess.DEVNULL,timeout=3).strip() for k,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('changes',['status','--porcelain'])]}
  except (OSError,subprocess.SubprocessError): state['code']={'error':'GIT_METADATA_UNAVAILABLE'}
  return state

class Handler(BaseHTTPRequestHandler):
 server_version='MetaSurveyReadOnly/1.0'
 def log_message(self,*args): pass  # no query, paths, private data or credentials in logs
 def reply(self,status,body,ctype='application/json; charset=utf-8'):
  raw=json.dumps(body,ensure_ascii=False).encode() if isinstance(body,(dict,list)) else body
  self.send_response(status)
  self.send_header('Content-Type',ctype); self.send_header('Content-Length',str(len(raw)))
  self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('Content-Security-Policy',"default-src 'self'; connect-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
  self.send_header('Referrer-Policy','no-referrer'); self.end_headers(); self.wfile.write(raw)
 def trusted(self):
  host=self.headers.get('Host',''); expected=f'127.0.0.1:{self.server.server_port}'
  return host==expected and self.headers.get('Origin',f'http://{expected}')==f'http://{expected}' and self.headers.get('Sec-Fetch-Site','same-origin') in ('same-origin','none')
 def do_GET(self):
  if not self.trusted(): return self.reply(403,{'error':'LOCAL_ORIGIN_REQUIRED'})
  url=urlsplit(self.path)
  if url.query: return self.reply(400,{'error':'QUERY_NOT_SUPPORTED'})
  path=unquote(url.path)
  try:
   if path=='/api/state': return self.reply(200,self.server.reader.state())
   if path.startswith('/api/research/'): return self.reply(200,self.server.reader.research(path.removeprefix('/api/research/')))
   if path.startswith('/api/evidence/'):
    key=path.removeprefix('/api/evidence/')
    result=self.server.reader.research(key[9:]) if key.startswith('research:') else self.server.reader.document(key)
    return self.reply(200,result)
   assets={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
   if path not in assets: return self.reply(404,{'error':'NOT_ALLOWLISTED'})
   p=Path(__file__).parent/'static'/assets[path]
   return self.reply(200,p.read_bytes(),{'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[p.suffix[1:]])
  except ReadError as e: return self.reply(422,{'error':e.code,'source':e.source,'read_at':now()})
  except Exception: return self.reply(500,{'error':'READ_FAILED_NO_RESULT','read_at':now()})
 def do_POST(self): self.reply(405,{'error':'READ_ONLY'})
 do_PUT=do_POST; do_DELETE=do_POST; do_PATCH=do_POST; do_OPTIONS=do_POST

def main():
 parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); args=parser.parse_args()
 if not 1024<=args.port<=65535: parser.error('Use a nonprivileged local port')
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler); server.reader=Reader()
 print(f'MetaSurvey 本地只读工作台：http://127.0.0.1:{args.port}',flush=True)
 print('只读服务已启动；不会执行采集、研究、回测、Forward或订单。按 Ctrl+C 停止。',flush=True)
 try: server.serve_forever()
 except KeyboardInterrupt: pass
 finally: server.server_close()
if __name__=='__main__': main()
