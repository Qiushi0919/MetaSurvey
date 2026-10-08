"""One finite SDK-wire-compatible Python REST facade; no endpoint discovery."""
import ctypes, json, os, time, urllib.request, urllib.error
from pathlib import Path
from datetime import timezone, timedelta
from decimal import Decimal
from .primitives import ROOT, ARCHIVE, SYMBOLS, START, END, VERSION, require, sha, canonical, clock, date_literal, safe_body
from overnight.data.dataset import _load_verifier, _number

BASE = 'http://118.89.117.77:8030/'
RUN_ID = 'WAVE-B-PROBE-20261006-G2'
DEST = ARCHIVE/'captures'/RUN_ID
ALLOWLIST = ('stock_basic','trade_cal','daily','adj_factor','stock_st','namechange','suspend_d','dividend','fina_indicator','index_member_all')
PERIODS = ('20250630','20250930','20251231','20260331','20260630','20260930')
FIELD_MAP = {
 'stock_basic':('ts_code','symbol','name','exchange','curr_type','list_status','list_date','delist_date'),
 'stock_st':('ts_code','name','trade_date','type','type_name'),
 'namechange':('ts_code','name','start_date','end_date','ann_date','change_reason'),
 'suspend_d':('ts_code','trade_date','suspend_timing','suspend_type'),
 'dividend':('ts_code','end_date','ann_date','div_proc','stk_div','stk_bo_rate','stk_co_rate','cash_div','cash_div_tax','record_date','ex_date','pay_date','imp_ann_date','div_listdate','base_date','base_share'),
 'adj_factor':('ts_code','trade_date','adj_factor'),
 'fina_indicator':('ts_code','ann_date','end_date','eps','roe','debt_to_assets','netprofit_yoy','update_flag'),
 'index_member_all':('ts_code','name','l1_code','l1_name','l2_code','l2_name','l3_code','l3_name','in_date','out_date','is_new')}
_PROBE = None
_NETWORK_REQUESTS = 0

def _old_probe():
    global _PROBE
    if _PROBE is None: _PROBE = _load_verifier()[0].probe
    return _PROBE

CAPS = {'stock_basic':1,'stock_st':512,'namechange':32,'suspend_d':512,'dividend':64,'adj_factor':1,'fina_indicator':100,'index_member_all':32}

def fixed_plan():
    # Changes come solely from the frozen, byte-pinned previous factor report.
    evidence=json.loads((ROOT/'docs/overnight/evidence.json').read_bytes())
    ref=next(x for x in evidence['artifacts'] if x['object']=='factor')
    raw=Path(ref['path']).read_bytes();require(sha(raw)==ref['sha256'],'PREVIOUS_FACTOR_REPORT_CHANGED')
    factor=json.loads(raw);changes=[(s['ts_code'] if 'ts_code' in s else s['symbol'],c['trade_date']) for s in factor['symbols'] for c in s['change_points']]
    require(len(changes)==8 and all(s in SYMBOLS and START<=d<=END for s,d in changes),'FACTOR_PROBE_SCOPE_INVALID')
    out=[]
    def add(api,symbol,suffix,extra=(),date_key=None,begin=START,end=END):
        out.append({'request_id':api+'-'+symbol+'-'+suffix,'api_name':api,'ts_code':symbol,
            'params':{'ts_code':symbol,**dict(extra),'ts_type_name':BASE},'fields':list(FIELD_MAP[api]),
            'max_rows':CAPS[api],'date_scope':{'key':date_key,'start':begin,'end':end},'scope':'WAVE_B'})
    for s in SYMBOLS:
        add('stock_basic',s,'CURRENT',date_key=None)
        for api,key in [('stock_st','trade_date'),('namechange','ann_date'),('suspend_d','trade_date')]:
            add(api,s,'WINDOW',(('start_date',START),('end_date',END)),key)
        add('fina_indicator',s,'RANGE',(('start_date',START),('end_date',END)),'end_date')
        for p in PERIODS:add('fina_indicator',s,'PERIOD-'+p,(('period',p),),'end_date',p,p)
        for current in ('Y','N'):add('index_member_all',s,'ISNEW-'+current,(('is_new',current),),None)
    for s,d in changes:
        add('dividend',s,'EX-'+d,(('ex_date',d),),'ex_date',d,d)
        add('adj_factor',s,'CHANGE-'+d,(('trade_date',d),),'trade_date',d,d)
    require(len(out)==55 and len({q['request_id'] for q in out})==55,'REQUEST_BUDGET_INVALID')
    return out

def validate_spec(spec):
    require(type(spec) is dict and canonical(spec) in [canonical(q) for q in fixed_plan()],'UNAPPROVED_REQUEST_SCOPE')
    require(spec['api_name'] in ALLOWLIST and spec['ts_code'] in SYMBOLS,'UNAPPROVED_API_OR_SYMBOL')
    return spec

def fingerprint(spec):
    validate_spec(spec)
    return sha(canonical({'spec':spec,'provider_id':'TUSHARE_MONTHLY_GATEWAY','namespace':'CORE_40','endpoint':BASE,'rules':VERSION}))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise ValueError('AUTH_REDIRECT_BLOCKED')

def _send(spec,credential):
    global _NETWORK_REQUESTS
    validate_spec(spec);old=_old_probe()
    require(type(credential) is old.Credential,'CREDENTIAL_TYPE_INVALID')
    url=BASE+'/'+spec['api_name']
    wire={'api_name':spec['api_name'],'token':credential._value,'params':spec['params'],'fields':','.join(spec['fields'])}
    req=urllib.request.Request(url,data=canonical(wire),method='POST',headers={'Content-Type':'application/json'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    _NETWORK_REQUESTS += 1
    try: response=opener.open(req,timeout=20)
    except urllib.error.HTTPError as error:
        if 300<=error.code<400:raise ValueError('AUTH_REDIRECT_BLOCKED') from None
        response=error
    except Exception:raise ValueError('CONTROLLED_TRANSPORT_FAILURE') from None
    with response:
        require(response.geturl()==url,'AUTH_REDIRECT_BLOCKED')
        raw=response.read(old.MAX_BYTES+1);status=int(response.code)
    require(len(raw)<=old.MAX_BYTES,'RESPONSE_SIZE_EXCEEDED')
    old._secret_check(raw,credential)
    return status,raw

def _normalize(value):
    if value is None:return None
    if type(value) in (int,Decimal):return _number(value)
    require(type(value) is str,'SOURCE_CELL_TYPE_INVALID');safe_body(value);return value

def analyze(spec,raw,retrieved_at):
    validate_spec(spec);clock(retrieved_at);doc=_old_probe()._old.parse_response(raw)
    reasons=[];rows=[];fields=[];code=None
    if not isinstance(doc,dict) or type(doc.get('code')) is not int:reasons.append('RESPONSE_SCHEMA_INVALID')
    else:
        code=doc['code']
        if code!=0:reasons.append('ENTITLEMENT_NOT_GRANTED' if code in (-2002,2002) else 'API_ACCESS_NOT_PROVEN')
        else:
            data=doc.get('data')
            if not isinstance(data,dict) or set(data)!={'fields','items'}:reasons.append('RESPONSE_SCHEMA_INVALID')
            else:
                fields=data['fields'];items=data['items']
                if fields!=spec['fields'] or type(items) is not list or len(items)>spec['max_rows']:reasons.append('RESPONSE_SCHEMA_OR_LIMIT_INVALID')
                if type(items) is list and type(fields) is list and len(fields)==len(set(fields)):
                    day=clock(retrieved_at).astimezone(timezone(timedelta(hours=8))).strftime('%Y%m%d')
                    for n,vector in enumerate(items):
                        if type(vector) is not list or len(vector)!=len(fields):reasons.append('RESPONSE_VECTOR_INVALID');continue
                        try:values={k:_normalize(v) for k,v in zip(fields,vector)}
                        except Exception:reasons.append('UNSAFE_OR_INVALID_CELL');continue
                        rows.append({'row_ordinal':n,'values':values})
                        if values.get('ts_code')!=spec['ts_code']:reasons.append('ROW_SYMBOL_OUT_OF_SCOPE')
                        key=spec['date_scope']['key'];v=values.get(key) if key else None
                        if key and (not date_literal(v) or not spec['date_scope']['start']<=v<=spec['date_scope']['end']):reasons.append('ROW_DATE_OUT_OF_SCOPE_OR_UNKNOWN')
                        for k in ('ann_date','f_ann_date','imp_ann_date'):
                            v=values.get(k)
                            if v not in (None,'') and (not date_literal(v) or v>day):reasons.append('FUTURE_OR_INVALID_PUBLICATION')
                        if spec['api_name']=='index_member_all':
                            if values.get('is_new')!=spec['params']['is_new']:reasons.append('MEMBERSHIP_CURRENT_HISTORY_FILTER_MISMATCH')
                            for k in ('in_date','out_date'):
                                if values.get(k) is not None and not date_literal(values[k]):reasons.append('INVALID_MEMBERSHIP_DATE_LITERAL')
    reasons=sorted(set(reasons))
    return {'provider_code':code,'response_fields':fields,'row_count':len(rows),'rows':rows,
            'response_blocked':bool(reasons),'reason_codes':reasons,'technical_access_observed':code==0,
            'scope_complete':False,'negative_status_proven':False}

def private_write(path,raw):
    require(path.is_relative_to(ARCHIVE) and path.resolve()==path and not path.exists(),'PRIVATE_OUTPUT_PATH_INVALID')
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw)

def capture():
    global _NETWORK_REQUESTS
    _NETWORK_REQUESTS = 0
    old=_old_probe()
    framework=ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
    interaction=framework.SecKeychainSetUserInteractionAllowed;interaction.argtypes=(ctypes.c_bool,);interaction.restype=ctypes.c_int32
    require(interaction(False)==0,'NO_UI_CREDENTIAL_LOOKUP_UNAVAILABLE')
    credential,lookup=old.lookup_credential()
    report={'version':VERSION,'fixture':False,'run_id':RUN_ID,'provider_id':'TUSHARE_MONTHLY_GATEWAY',
        'source_classification':'OWNER_PROVIDED_MONTHLY_GATEWAY','namespace':'CORE_40','state':'QUARANTINED',
        'source_admission':'BLOCKED','provider_identity_verified':False,'license_verified':False,'transport_integrity_verified':False,
        'historical_visibility_proven':False,'productionGate':False,'request_budget':55,'network_requests':0,
        'credential_lookup':lookup,'adapter':'STRICT_PYTHON_SDK_WIRE_COMPATIBLE_RAW_REST','requests':[],
        'code_hash':sha(Path(__file__).read_bytes()),'generated_at':old._clock()}
    for spec in fixed_plan():
        q={**spec,'request_fingerprint':fingerprint(spec),'request_started_at':None,'response_completed_at':None,
           'retrieved_at':None,'available_at':None,'published_at':None,'available_at_basis':None,'raw_ref':None,'raw_sha256':None,
           'raw_bytes':None,'http_status':None,'response_blocked':True,'reason_codes':['SECRET_NOT_AVAILABLE'],
           'rows':[],'row_count':0,'provider_code':None,'technical_access_observed':False,'scope_complete':False,'negative_status_proven':False}
        if credential is not None:
            q['request_started_at']=old._clock()
            try:
                status,raw=_send(spec,credential);end=old._clock();analysis=analyze(spec,raw,end)
                path=DEST/(spec['request_id']+'.response.json');private_write(path,raw)
                q.update(analysis);q.update({'raw_ref':str(path),'raw_sha256':sha(raw),'raw_bytes':len(raw),'http_status':status,
                    'response_completed_at':end,'retrieved_at':end,'available_at':end,'available_at_basis':'FIRST_OBSERVED_BY_THIS_COLLECTOR'})
                if status!=200:q['response_blocked']=True;q['reason_codes']=sorted(set(q['reason_codes']+['HTTP_STATUS_NOT_SUCCESS']))
            except Exception:
                q['reason_codes']=['CONTROLLED_CAPTURE_FAILURE'];q['response_completed_at']=old._clock()
            time.sleep(3)
        report['network_requests']=_NETWORK_REQUESTS
        report['requests'].append(q)
    report['completed_at']=old._clock();private_write(DEST/'report.json',canonical(report)+b'\n')
    credential=None
    return {'report_path':str(DEST/'report.json'),'report_sha256':sha((DEST/'report.json').read_bytes()),
        'network_requests':report['network_requests'],'raw_capture_count':sum(q['raw_ref'] is not None for q in report['requests']),
        'source_admission':'BLOCKED','productionGate':False}

def verify_capture(ref):
    p=Path(ref['path']);require(p==DEST/'report.json' and p.resolve()==p and not p.is_symlink() and (p.stat().st_mode&0o777)==0o600,'CAPTURE_REPORT_PATH_INVALID')
    raw=p.read_bytes();require(sha(raw)==ref['sha256'] and len(raw)==ref['bytes'],'CAPTURE_REPORT_HASH_INVALID')
    r=json.loads(raw);require(r['fixture'] is False and r['namespace']=='CORE_40' and r['provider_id']=='TUSHARE_MONTHLY_GATEWAY' and
        r['source_classification']=='OWNER_PROVIDED_MONTHLY_GATEWAY' and r['source_admission']=='BLOCKED' and r['state']=='QUARANTINED','REPORT_SCOPE_INVALID')
    require(set(r)=={'version','fixture','run_id','provider_id','source_classification','namespace','state','source_admission',
        'provider_identity_verified','license_verified','transport_integrity_verified','historical_visibility_proven','productionGate',
        'request_budget','network_requests','credential_lookup','adapter','requests','code_hash','generated_at','completed_at'} and
        r['version']==VERSION and r['run_id']==RUN_ID,'REPORT_EXTRA_FIELDS_OR_VERSION')
    require(set(r['credential_lookup'])=={'secret_presence','lookup_result','credential_source'} and
        r['credential_lookup']['credential_source']=='EXPLICIT_KEYCHAIN','SECRET_REFERENCE_IN_REPORT')
    require(all(r[k] is False for k in ('provider_identity_verified','license_verified','transport_integrity_verified','historical_visibility_proven','productionGate')),'REPORT_PERMISSION_ESCALATION')
    require(r['code_hash']==sha(Path(__file__).read_bytes()) and r['request_budget']==55 and len(r['requests'])==55,'CAPTURE_CODE_OR_BUDGET_INVALID')
    begin,finish=clock(r['generated_at']),clock(r['completed_at']);require(begin<=finish,'CAPTURE_CLOCK_INVALID')
    for q,spec in zip(r['requests'],fixed_plan()):
        basekeys=set(spec)|{'request_fingerprint','request_started_at','response_completed_at','retrieved_at','available_at',
            'published_at','available_at_basis','raw_ref','raw_sha256','raw_bytes','http_status','response_blocked','reason_codes',
            'rows','row_count','provider_code','technical_access_observed','scope_complete','negative_status_proven'}
        require(set(q)==basekeys|({'response_fields'} if q['raw_ref'] is not None else set()),'REQUEST_EXTRA_FIELDS')
        require(all(q[k]==v for k,v in spec.items()) and q['request_fingerprint']==fingerprint(spec),'REQUEST_SCOPE_CHANGED')
        if q['raw_ref'] is None:
            require(q['response_blocked'] is True and q['rows']==[] and q['raw_sha256'] is None and not q['technical_access_observed'],'UNBACKED_RESPONSE_CLAIM');continue
        path=Path(q['raw_ref']);require(path==DEST/(spec['request_id']+'.response.json') and path.resolve()==path and not path.is_symlink() and (path.stat().st_mode&0o777)==0o600,'RAW_PATH_INVALID')
        b=path.read_bytes();require(sha(b)==q['raw_sha256'] and len(b)==q['raw_bytes'],'RAW_BYTES_MUTATED')
        require(begin<=clock(q['request_started_at'])<=clock(q['response_completed_at'])<=finish and
            q['retrieved_at']==q['available_at']==q['response_completed_at'] and q['published_at'] is None and
            q['available_at_basis']=='FIRST_OBSERVED_BY_THIS_COLLECTOR','CLOCK_BACKFILL_FORBIDDEN')
        a=analyze(spec,b,q['retrieved_at'])
        if q['http_status']!=200:a['response_blocked']=True;a['reason_codes']=sorted(set(a['reason_codes']+['HTTP_STATUS_NOT_SUCCESS']))
        require(all(q[k]==v for k,v in a.items()),'RAW_DIAGNOSTIC_CHANGED')
    require(r['network_requests']==(55 if r['credential_lookup']['secret_presence'] else 0),'NETWORK_INVENTORY_CHANGED')
    return r

if __name__=='__main__':
    try:print(json.dumps(capture(),ensure_ascii=False))
    except Exception:print('WAVE_B_CAPTURE_FAILED_NO_ADMISSION');raise SystemExit(1)
