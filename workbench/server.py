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
 'account20k-registry':'docs/forward-c20k/Registry.json',
 'account20k-history':'docs/account20k-history/Results.json',
 'account20k-status':'docs/forward-c20k/Status.json',
 'account20k-report':'docs/forward-c20k/Acceptance-Report.md',
 'account20k-method':'docs/forward-c20k/Method.md',
 'param-opt-registry':'docs/param-opt-v1/Registry.json',
 'param-opt-results':'docs/param-opt-v1/Results.json',
 'param-opt-report':'docs/param-opt-v1/Acceptance-Report.md',
 'param-opt-preregistration':'experiments/param_opt_v1/Registration.json',
 'long-forward-registry':'workbench/long-forward-registry.json',
 'long-forward-protocol':'experiments/long_forward_v1/protocol.json',
 'long-forward-report':'docs/long-forward/Acceptance-Report.md',
 'performance-registry':'docs/v3-performance/Registry.json',
 'performance-report':'docs/v3-performance/Acceptance-Report.md',
 'performance-benchmark':'docs/v3-performance/Benchmark-Protocol.json',
 'performance-research':'docs/v3-performance/Research-Increment.json',
 'gateway-registry':'docs/e2e-gateway-v3/Registry.json',
 'gateway-report':'docs/e2e-gateway-v3/Acceptance-Report.md',
 'gateway-source':'docs/e2e-gateway-v3/Source-Review.md',
 'gateway-inputs':'docs/e2e-gateway-v3/Input-Plan.md',
 'gateway-policy':'docs/e2e-gateway-v3/Source-Policy.json',
 'history-registry':'docs/e2e-history-v2/Registry.json',
 'history-report':'docs/e2e-history-v2/Acceptance-Report.md',
 'history-protocol':'experiments/e2e_history_v2/protocol.json',
 'history-source':'docs/e2e-history-v2/Source-Review.md',
 'history-inputs':'docs/e2e-history-v2/Research-Factors.md',
 'history-method':'experiments/e2e_history_v2/research-method.json',
 'e2e-config':'experiments/e2e_pilot_v1/method.json',
 'e2e-protocol':'experiments/e2e_pilot_v1/protocol.json',
 'e2e-registry':'docs/e2e-pilot-v1/Registry.json',
 'e2e-report':'docs/e2e-pilot-v1/Acceptance-Report.md',
 'e2e-data':'docs/e2e-pilot-v1/Data-Feasibility.md',
 'e2e-fields':'docs/e2e-pilot-v1/Field-Matrix.md',
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
 'scoring-config': 'experiments/sector_stock_v0/config.json',
 'scoring-status': 'docs/sector-stock-v0/Status.json',
 'scoring-rules': 'docs/sector-stock-v0/Scoring-Rules.md',
 'preregistration': 'docs/sector-stock-v0/Preregistration.json',
 'scoring-acceptance': 'docs/sector-stock-v0/Acceptance-Report.md',
 'previous-ui-checks': 'docs/workbench-v0/Checks.json',
 'research-gate': 'docs/wave-d/Gate.json',
 'score-review-registry':'docs/score-review-v01/Sample-Registry.json',
 'score-review-decisions':'docs/score-review-v01/Owner-Decisions.md',
 'score-review-config':'experiments/sector_stock_v01/config.json',
 'score-review-fields':'docs/score-review-v01/Field-Matrix.md',
 'score-review-acceptance':'docs/score-review-v01/Acceptance-Report.md',
 'score-review-preregistration':'docs/score-review-v01/Preregistration.json',
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
  state={'adapter_version':'1.1.0-workbench-readonly','read_at':now(),'mode':'LOCAL_READ_ONLY','task_runtime':'NOT_CONNECTED_NO_LIVE_HEARTBEAT','errors':[],'panels':{},'studies':[],'formal_candidates':{'state':'NOT_AVAILABLE','reason':'No admitted formal candidate producer is connected. Research objects are not recommendations.'}}
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
  try:
   experiment,emeta=self.json('scoring-status','SectorStockWorkbenchStatus')
   cfg,cmeta=self.json('scoring-config','SectorStockExperimentConfig','0.1.0-candidate')
   if experiment.get('scoring_state')!='BLOCKED_MISSING_ADMITTED_INPUT_BUNDLES' or experiment.get('optimization_state')!='PREREGISTRATION_ONLY_NOT_RUN': raise ReadError('UNKNOWN_STATUS','scoring-status')
   if any(experiment.get(k)!=[] for k in ('real_sector_scores','real_stock_scores','formal_candidates')): raise ReadError('UNADMITTED_SCORE_PAYLOAD','scoring-status')
   if cfg.get('experiment_id')!='CORE40_SECTOR_STOCK_BASELINE_V0' or cfg.get('productionGate') is not False or len(cfg.get('sector_metrics',[]))!=9 or [f.get('weight_percent') for f in cfg.get('stock_factors',[])]!=[25,20,15,15,10,10,5]: raise ReadError('INVALID_EXPERIMENT_CONFIG','scoring-config')
   if any(k not in cfg.get('metrics',{}) for k in cfg['sector_metrics']): raise ReadError('INVALID_EXPERIMENT_CONFIG','scoring-config')
   for metric in cfg['metrics'].values():
    if type(metric) is not dict or any(type(metric.get(k)) is not str for k in ('label','definition','evidence_source','window','score_zero','score_hundred','unit')): raise ReadError('INVALID_EXPERIMENT_CONFIG','scoring-config')
   for factor in cfg['stock_factors']:
    if type(factor.get('label')) is not str or type(factor.get('id')) is not str or type(factor.get('inputs')) is not list or any(k not in cfg['metrics'] for k in factor['inputs']): raise ReadError('INVALID_EXPERIMENT_CONFIG','scoring-config')
   if type(experiment.get('reasons')) is not list or any(type(x) is not str for x in experiment['reasons']) or experiment.get('method_state')!='CANDIDATE_RULES_OWNER_PENDING': raise ReadError('INVALID_SHAPE','scoring-status')
   state['experiment']={'data':experiment,'config':cfg,'provenance':emeta,'config_provenance':cmeta,'result_type':'EXPERIMENT_SPEC_NOT_REAL_SCORE'}
  except (ReadError,KeyError,TypeError) as e: state['errors'].append({'panel':'experiment','code':getattr(e,'code','INVALID_SHAPE'),'source':getattr(e,'source','scoring-config')})
  try:
   from workbench.score_reader import load
   state['score_review']=load(self)
  except (ReadError,ValueError,KeyError,TypeError) as e: state['errors'].append({'panel':'score-review','code':getattr(e,'code','INVALID_SCORE_PACKAGE'),'source':getattr(e,'source','score-review-registry')})
  try:
   from workbench.e2e_reader import load as load_e2e
   state['e2e']=load_e2e(self)
  except (ReadError,ValueError,KeyError,TypeError) as e: state['errors'].append({'panel':'e2e','code':getattr(e,'code','INVALID_E2E_PACKAGE'),'source':getattr(e,'source','e2e-registry')})
  try:
   from workbench.history_reader import load as load_history
   state['history_v2']=load_history(self)
  except (ReadError,ValueError,KeyError,TypeError) as e: state['errors'].append({'panel':'history-v2','code':getattr(e,'code','INVALID_HISTORY_PACKAGE'),'source':getattr(e,'source','history-registry')})
  try:
   from workbench.gateway_reader import load as load_gateway
   state['gateway_v3']=load_gateway(self)
  except (ReadError,ValueError,KeyError,TypeError,ImportError) as e: state['errors'].append({'panel':'gateway-v3','code':getattr(e,'code','INVALID_GATEWAY_PACKAGE'),'source':getattr(e,'source','gateway-registry')})
  if state.get('gateway_v3',{}).get('status')=='VERIFIED':
   try:
    from workbench.performance_reader import load as load_performance
    state['gateway_v3']['performance']=load_performance(self,state['gateway_v3'])
   except (ReadError,ValueError,KeyError,TypeError,ImportError,ArithmeticError) as e:
    state['gateway_v3']['performance']={'status':'BLOCKED','reason':getattr(e,'code','INVALID_PERFORMANCE_PACKAGE')}
    state['errors'].append({'panel':'v3-performance','code':getattr(e,'code','INVALID_PERFORMANCE_PACKAGE'),'source':getattr(e,'source','performance-registry')})
  try:
   from workbench.long_forward_reader import load as load_long_forward
   state['long_forward']=load_long_forward(self)
  except (ReadError,ValueError,KeyError,TypeError,ImportError,ArithmeticError,OSError) as e:
   state['long_forward']={'status':'INTEGRITY_ERROR','reason':getattr(e,'code','LONG_FORWARD_INTEGRITY_ERROR')}
   state['errors'].append({'panel':'long-forward','code':getattr(e,'code','LONG_FORWARD_INTEGRITY_ERROR'),'source':'long-forward-registry'})
  try:
   from workbench.param_opt_reader import load as load_param_opt
   state['param_opt']=load_param_opt(self)
  except (ReadError,ValueError,KeyError,TypeError,ImportError,ArithmeticError,OSError) as e:
   state['param_opt']={'status':'INTEGRITY_ERROR','reason':getattr(e,'code','PARAM_OPT_INVALID')}
  try:
   from workbench.account20k_reader import load as load_account20k
   state['account20k']=load_account20k(self)
  except (ReadError,ValueError,KeyError,TypeError,ImportError,ArithmeticError,OSError) as e:
   state['account20k']={'status':'INTEGRITY_ERROR','reason':getattr(e,'code','ACCOUNT20K_INVALID')}
  state['task_records']=[]
  for key,label in [('research-gate','三股封存研究交付'),('integration','五年专项主控集成记录'),('previous-ui-checks','上一轮工作台检查记录')]:
   try:
    doc=self.document(key)
    data=json.loads(doc['content'])
    if type(data) is not dict: raise ReadError('INVALID_SHAPE',key)
    code=data.get('integrated_code_commit') or data.get('release') or ('baseline:'+data['baseline_commit'] if data.get('baseline_commit') else None)
    state['task_records'].append({'label':label,'evidence_id':key,'provenance':{k:v for k,v in doc.items() if k!='content'},'status':'ARCHIVED_RECORD_NOT_LIVE_TASK','recorded_at':data.get('recorded_at',data.get('checked_at')),'code_version':code})
   except (ReadError,ValueError) as e: state['errors'].append({'panel':'task-records','code':getattr(e,'code','INVALID_JSON'),'source':getattr(e,'source',key)})
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
