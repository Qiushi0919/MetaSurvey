"""Wave D closed version-chain authority over fixed current-observed originals."""
from pathlib import Path
from copy import deepcopy
import json
from wave_c.core import canonical,sha,digest,seal,ref,require,SYMBOLS,checked_file
from overnight.analysis.inputs import instant_ns
from .probe import ROOT,ARCHIVE,verify_capture
from .public_probe import normalize_index
from .public_enrich import allowed_target,parse_pdf
_REGISTRY={}
_UPSTREAMS={}

def private_ref(r):
 p=Path(r['path']);require(p.is_relative_to(ARCHIVE) and p.resolve()==p and not p.is_symlink() and p.stat().st_mode&0o777==0o600,'WAVE_D_PRIVATE_REF_INVALID')
 b=checked_file(p,r['sha256']);require(len(b)==r['bytes'],'WAVE_D_REF_SIZE_INVALID');return b

def frozen_context():
 baseline_p=ROOT/'docs/wave-d/baseline-pins.json';baseline_raw=checked_file(baseline_p);b=json.loads(baseline_raw)
 require(len(b['tracked_files'])==566 and b['allowed_navigation_updates']==['AGENTS.md','README.md','docs/source-of-truth.json'],'WAVE_D_BASELINE_SCOPE_INVALID')
 pins=[(ROOT/x['path'],x['sha256']) for x in b['tracked_files'] if x['path'] not in b['allowed_navigation_updates']]
 cp=ARCHIVE/'start/checkpoint.json';cr=checked_file(cp,b['checkpoint_sha256']);require(json.loads(cr)['tracked_files']==b['tracked_files'],'WAVE_D_BASELINE_UNBOUND')
 rp=ROOT/'docs/wave-d/release.json';rr=checked_file(rp);release=json.loads(rr);require(release['version']=='2.0.0-wave-d-local-loop','WAVE_D_VERSION_INVALID')
 pins.extend((ROOT/x['path'],x['sha256']) for x in release['code_pins'])
 rulep=ROOT/'docs/wave-d/rules.json';ruleb=checked_file(rulep);rules=json.loads(ruleb)
 require(rules['symbols']==list(SYMBOLS) and rules['historical_visibility_proven'] is False and rules['productionGate'] is False and rules['current_observed_only'] is True,'WAVE_D_RULE_PROMOTION')
 for p,h in pins:checked_file(p,h)
 pins.extend([(baseline_p,sha(baseline_raw)),(cp,sha(cr)),(rp,sha(rr)),(rulep,sha(ruleb))])
 old=json.loads((ROOT/'docs/wave-c/evidence.json').read_bytes())
 for x in old['artifacts']:
  p=Path(x['path']);checked_file(p,x['sha256']);pins.append((p,x['sha256']))
 public=[]
 for f in ('capture-ref.json','public-ref.json','sse-enrich-ref.json','full-statements-ref.json'):
  p=ROOT/'docs/wave-d'/f;r=json.loads(checked_file(p));raw=private_ref(r);pins.extend([(p,sha(p.read_bytes())),(Path(r['path']),r['sha256'])]);public.append(json.loads(raw))
 capture,official,enrich,full=public
 require(capture['code_hash']==sha((ROOT/'wave_d/probe.py').read_bytes()) and official['code_hash']==sha((ROOT/'wave_d/public_probe.py').read_bytes()) and enrich['code_hash']==sha((ROOT/'wave_d/public_enrich.py').read_bytes()),'WAVE_D_CAPTURE_CODE_MUTATED')
 for obj in public:
  require(obj['historical_visibility_proven'] is False and obj['productionGate'] is False and obj['formal_source_admission']=='BLOCKED','WAVE_D_SOURCE_PROMOTION')
 def add(r):
  if r:private_ref(r);pins.append((Path(r['path']),r['sha256']))
 for q in capture['requests']+full['requests']:
  if q['raw_ref']:add({'path':q['raw_ref'],'sha256':q['raw_sha256'],'bytes':q['raw_bytes']})
 for q in official['references']:add(q['raw_ref'])
 for q in official['announcements']:
  add(q['raw_ref'])
  if not q['blocked']:require(normalize_index(private_ref(q['raw_ref']),q['symbol'])==q['facts'],'WAVE_D_SSE_PROJECTION_INVALID')
  for d in q['documents']:add(d['raw_ref']);add(d['text_ref'])
 for d in enrich['documents']:
  add(d['origin_index_ref']);add(d['redirect']['raw_ref'] if d['redirect'] else None);add(d['raw_ref']);add(d['text_ref'])
  if d['body_verified']:
   allowed_target(d['fact']['uri'],d['redirect']['location']);text,pages,snippet=parse_pdf(private_ref(d['raw_ref']),d['fact'])
   require(private_ref(d['text_ref'])==text.encode() and pages==d['pages'] and snippet==d['snippet'],'WAVE_D_PDF_PROJECTION_INVALID')
 return {'rules':rules,'rules_hash':sha(ruleb),'code_hash':digest(release['code_pins']),'release_hash':sha(rr),'pins':pins,'official':official,'enrich':enrich}

def ctx_hash(ctx):return digest({**{k:v for k,v in ctx.items() if k!='pins'},'pins':[(str(p),h) for p,h in ctx['pins']]})
def source_ref(q,n):
 return {'origin':'WAVE_D','scope':'LOCAL_CURRENT_OBSERVED_AUGMENTATION','request_id':q['request_id'],'request_fingerprint':q['request_fingerprint'],'raw_sha256':q['raw_sha256'],'row_ordinal':n,'event_time':None,'published_at':None,'available_at':q['available_at'],'retrieved_at':q['retrieved_at']}
def check_ref_clock(r,cutoff):
 require(r['event_time'] is None and r['published_at'] is None and r['available_at']==r['retrieved_at'] and instant_ns(r['retrieved_at'])<=instant_ns(cutoff),'WAVE_D_CLOCK_OR_CUTOFF_INVALID')

def _prepare():
 ctx=frozen_context();capture=deepcopy(verify_capture())
 from .full_statements import verify as verify_full
 from .probe import FIELDS
 full=verify_full()
 require(full['code_hash']==sha((ROOT/'wave_d/full_statements.py').read_bytes()),'WAVE_D_FULL_CODE_CHANGED')
 for q in full['requests']:
  projection=deepcopy(q);projection['rows']=[{**x,'values':{k:x['values'].get(k) for k in FIELDS[q['api_name']].split(',')}} for x in q['rows']]
  capture['requests'].append(projection)
 from wave_c.run import replay
 old_inputs,old_assessments,old_reports=replay()
 upstream={'old_inputs':old_inputs,'old_assessments':old_assessments,'old_reports':old_reports,'capture':capture}
 _UPSTREAMS[id(upstream)]={'value':upstream,'hash':digest(upstream)}
 return ctx,upstream

def _input_body(symbol,ctx,up):
 i=SYMBOLS.index(symbol);old=up['old_inputs'][i];obs=[];excluded=[]
 for r in old['body']['observations']:
  rr=deepcopy(r);rr['source_ref']['event_time']=None;obs.append(rr)
 for e in old['body']['excluded']:
  rr=deepcopy(e);rr['source_ref']['event_time']=None;excluded.append(rr)
 for q in up['capture']['requests']:
  if q['symbol'] not in (None,symbol):continue
  if q['retrieved_at']:require(instant_ns(q['retrieved_at'])<=instant_ns(ctx['rules']['decision_cutoff']),'WAVE_D_CUTOFF_BEFORE_CAPTURE')
  if q['response_blocked']:continue
  for r in q['rows']:
   if r['values'].get('ts_code')==symbol:obs.append({'api_name':q['api_name'],'values':deepcopy(r['values']),'source_ref':source_ref(q,r['row_ordinal'])})
  for e in q['excluded']:
   if e['values'].get('ts_code')==symbol:excluded.append({'api_name':q['api_name'],'source_ref':source_ref(q,e['row_ordinal']),'reason_code':','.join(e['reason_codes'])})
 announcements=[]
 for q in ctx['official']['announcements']:
  if q['symbol']!=symbol or q['blocked']:continue
  for f in q['facts']:
   sr={'origin':'OFFICIAL_SSE_REFERENCE','scope':'LOCAL_CURRENT_OBSERVED_ANNOUNCEMENT_REFERENCE','request_id':'SSE-'+symbol,'request_fingerprint':sha(q['uri'].encode()),'raw_sha256':q['raw_ref']['sha256'],'row_ordinal':f['row_ordinal'],'event_time':None,'published_at':None,'available_at':q['available_at'],'retrieved_at':q['retrieved_at']}
   docs=[d for d in ctx['enrich']['documents'] if d['fact']==f];d=docs[0] if docs else None
   status='BODY_VERIFIED' if d and d['body_verified'] else 'INDEX_METADATA_ONLY'
   announcements.append({'date':f['date'],'title':f['title'],'uri':f['uri'],'body_status':status,'snippet':d['snippet'] if d and d['body_verified'] else None,'source_ref':sr,'body_hash':d['raw_ref']['sha256'] if d and d['raw_ref'] else None})
   obs.append({'api_name':'sse_announcement','values':{'ts_code':symbol,'published_date':f['date'],'title':f['title'],'document_url':f['uri'],'body_status':status},'source_ref':sr})
 for r in obs:check_ref_clock(r['source_ref'],ctx['rules']['decision_cutoff'])
 return {'observations':obs,'excluded':excluded,'announcements':announcements,'wave_c_input_ref':ref(old),'wave_c_assessment_ref':ref(up['old_assessments'][i]),'wave_c_report_ref':ref(up['old_reports'][i])}

def dependency_key(p):
 # Git checkout location is operational, not source identity. Private archives
 # remain explicitly fixed; relocation of those archives is not supported.
 if p.is_relative_to(ROOT):return 'GIT:'+p.relative_to(ROOT).as_posix()
 require(p.is_relative_to(ARCHIVE.parent),'WAVE_D_DEPENDENCY_ROOT_INVALID')
 return 'FIXED_PRIVATE_ARCHIVE:'+p.relative_to(ARCHIVE.parent).as_posix()

def header(kind,symbol,ctx,up,parents):
 roots=up['capture']['requests'];times=[q['retrieved_at'] for q in roots if q['retrieved_at']]+[q['retrieved_at'] for q in ctx['official']['announcements'] if q['retrieved_at']]+[d['retrieved_at'] for d in ctx['enrich']['documents'] if d['retrieved_at']]
 identity=digest({'rules':ctx['rules_hash'],'release':ctx['release_hash'],'raw':[(dependency_key(p),h) for p,h in ctx['pins']],'old':up['old_inputs'][0]['source_identity']})
 return {'contract_name':'ResearchComparison' if kind=='Comparison' else 'RealResearchSandbox'+kind,'contract_version':'1.0.0' if kind=='Comparison' else '2.0.0','object_version':1 if kind=='Comparison' else 2,'object_id':'wave-d:'+kind.lower()+':'+symbol+':'+identity[7:23],'trace_id':'wave-d:'+identity[7:],'symbol':symbol,'strategy_id':'CORE_40','namespace':'LOCAL_EXPERIMENTAL_REAL_RESEARCH:CORE_40','trust_tier':'LOCAL_EXPERIMENTAL_REAL_RESEARCH','purpose':'LOCAL_EXPERIMENTAL_RESEARCH','source_admission':'UNVERIFIED_GATEWAY','formal_source_admission':'BLOCKED','provider_identity_verified':False,'license_verified':False,'transport_integrity_verified':False,'historical_visibility_proven':False,'current_observed':True,'decision_cutoff':ctx['rules']['decision_cutoff'],'retrieval_cutoff':max(times,key=instant_ns),'rules_hash':ctx['rules_hash'],'code_hash':ctx['code_hash'],'code_version':'2.0.0-wave-d-local-loop','source_identity':identity,'local_only':True,'cloud_transfer':False,'tradeable':False,'validation_status':'NON_TRADEABLE','can_produce_order':False,'production_eligible':False,'productionGate':False,'real_account_settings':'UNSET_REQUIRED','reason_codes':['UNVERIFIED_GATEWAY','CURRENT_OBSERVED_ONLY','NON_TRADEABLE','UNCALIBRATED','NO_HISTORICAL_PIT'],'invalidation_conditions':['RAW_SOURCE_CHANGED','RULE_CODE_SCHEMA_CHANGED','CUTOFF_NAMESPACE_CHANGED','PARENT_VERSION_CHANGED','CALLER_COPY_RESEAL']}

def register(*a,**k):raise ValueError('WAVE_D_DIRECT_ISSUE_FORBIDDEN')
def derive(*a,**k):raise ValueError('WAVE_D_DIRECT_ISSUE_FORBIDDEN')
def _mint(kind,symbol,ctx,up,parents=()):
 require(ctx_hash(ctx)==ctx_hash(frozen_context()),'WAVE_D_CONTEXT_FORGERY')
 live=_UPSTREAMS.get(id(up));require(live and live['value'] is up and live['hash']==digest(up),'WAVE_D_UPSTREAM_FORGERY')
 if kind=='Input':require(not parents and symbol in SYMBOLS,'WAVE_D_INPUT_SCOPE');body=_input_body(symbol,ctx,up)
 elif kind=='Assessment':
  require(tuple(p['symbol'] for p in parents)==SYMBOLS and all(p['contract_name']=='RealResearchSandboxInput' for p in parents),'WAVE_D_COHORT_INVALID')
  for p in parents:assert_registered(p)
  from .research import assessment_bodies
  body=assessment_bodies(list(parents),ctx,up)[SYMBOLS.index(symbol)]
 elif kind=='Report':
  require(len(parents)==1 and parents[0]['symbol']==symbol and parents[0]['contract_name']=='RealResearchSandboxAssessment','WAVE_D_PARENT_INVALID');assert_registered(parents[0]);body=deepcopy(parents[0]['body']);body['assessment_ref']=ref(parents[0])
 elif kind=='Comparison':
  require(symbol=='COHORT:THREE' and tuple(p['symbol'] for p in parents)==SYMBOLS and all(p['contract_name']=='RealResearchSandboxReport' for p in parents),'WAVE_D_COMPARISON_COHORT_INVALID')
  for p in parents:assert_registered(p)
  body={'reports':[{'symbol':p['symbol'],'report_ref':ref(p),'features':deepcopy(p['body']['features']),'wave_c_quality':deepcopy(p['body']['wave_c_quality']),'wave_c_timing':deepcopy(p['body']['wave_c_timing']),'coverage':deepcopy(p['body']['coverage']),'unknowns':deepcopy(p['body']['unknowns']),'conflicts':deepcopy(p['body']['conflicts'])} for p in parents],'comparison_method':'FACTS_AND_ORIGINAL_EXPERIMENTAL_COORDINATES_NO_TOTAL_RANK','total_score':'UNSET_REQUIRED','grade':'UNSET_REQUIRED','buy_sell':'FORBIDDEN'}
 else:raise ValueError('WAVE_D_KIND_INVALID')
 v=seal({**header(kind,symbol,ctx,up,parents),'body':body});_REGISTRY[id(v)]={'value':v,'hash':digest(v),'ctx':deepcopy(ctx),'ctx_hash':ctx_hash(ctx),'up':up,'up_hash':digest(up),'parents':parents};return v

def assert_registered(v):
 # Within ONE synchronous read-only validation, visit shared ancestors/source
 # bytes once. No result is cached across calls, stages or source mutations.
 seen=set();upseen=set();contexts=set()
 def visit(value):
  r=_REGISTRY.get(id(value));require(r and r['value'] is value and r['hash']==digest(value),'WAVE_D_UNREGISTERED_OR_MUTATED')
  if id(value) in seen:return
  seen.add(id(value));h=ctx_hash(r['ctx']);require(h==r['ctx_hash'],'WAVE_D_CONTEXT_OR_UPSTREAM_MUTATED')
  if h not in contexts:
   for p,expected in r['ctx']['pins']:checked_file(p,expected)
   contexts.add(h)
  uid=id(r['up'])
  if uid not in upseen:
   require(digest(r['up'])==r['up_hash'],'WAVE_D_CONTEXT_OR_UPSTREAM_MUTATED')
   from wave_c.core import assert_registered as old_registered
   for x in r['up']['old_inputs']+r['up']['old_assessments']+r['up']['old_reports']:old_registered(x)
   upseen.add(uid)
  for parent in r['parents']:visit(parent)
  require(value['namespace']=='LOCAL_EXPERIMENTAL_REAL_RESEARCH:CORE_40' and value['historical_visibility_proven'] is False and value['productionGate'] is False and value['tradeable'] is False,'WAVE_D_AUTHORITY_CHANGED')
 visit(v);return v

def load_inputs():
 ctx,up=_prepare();return [_mint('Input',s,ctx,up) for s in SYMBOLS]
def _context(v):assert_registered(v);r=_REGISTRY[id(v)];return deepcopy(r['ctx']),r['up']
def assess(inputs):
 require(type(inputs) is list and tuple(v['symbol'] for v in inputs)==SYMBOLS,'WAVE_D_COHORT_INVALID');ctx,up=_context(inputs[0]);return [_mint('Assessment',s,ctx,up,tuple(inputs)) for s in SYMBOLS]
def reports(assessments):
 require(type(assessments) is list and tuple(v['symbol'] for v in assessments)==SYMBOLS,'WAVE_D_COHORT_INVALID');ctx,up=_context(assessments[0]);return [_mint('Report',s,ctx,up,(v,)) for s,v in zip(SYMBOLS,assessments)]
def comparison(rs):ctx,up=_context(rs[0]);return _mint('Comparison','COHORT:THREE',ctx,up,tuple(rs))
