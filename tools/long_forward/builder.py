"""Successor adapter: reuse sealed parser on an isolated module instance.

Historical observations retain real retrieval clocks. Forward appends captures;
previously consumed inputs cannot be replaced by a revised current download.
"""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import importlib.util, json
from tools.e2e_gateway import builder as old
from experiments.long_forward_v1.engine import RULES, digest
ROOT=Path(__file__).resolve().parents[2]
PROTOCOL=ROOT/'experiments/long_forward_v1/protocol.json'
POLICY=ROOT/'docs/long-forward/Source-Policy.json'
OWNER=ROOT/'docs/long-forward/Authorization.md'

def protocol():return old.read(PROTOCOL)

def _adapter(p):
    spec=importlib.util.spec_from_file_location('_long_forward_sealed_parser',ROOT/'tools/e2e_gateway/builder.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.SOURCE_POLICY=POLICY;module.OWNER=OWNER;module.PROTOCOL=PROTOCOL
    original_read=module.read;original_hash=module.rawhash
    module.read=lambda path:deepcopy(p) if path==PROTOCOL else original_read(path)
    module.rawhash=lambda path:digest(p) if path==PROTOCOL else original_hash(path)
    return module

def _aux(folder,manifest,case,report):
    calendars={};evidence=case['evidence'];refs={}
    for entry in manifest.get('auxiliary_calendar',[]):
        path=old.safe_child(folder,entry['path'])
        if old.rawhash(path)!=entry['sha256']:raise ValueError('AUX_WRAPPER_HASH')
        obj=old.read(path);rawpath=old.safe_child(folder,obj['raw_path'])
        if old.rawhash(rawpath)!=obj['raw_sha256']:raise ValueError('AUX_RAW_HASH')
        raw=json.loads(rawpath.read_bytes(),parse_float=str)
        for k in ('api_name','params','fields','row_count','error_code','state'):
            if obj[k]!=entry[k]:raise ValueError('AUX_WRAPPER_MANIFEST')
        if obj.get('request_fields') != 'exchange,cal_date,is_open,pretrade_date' or len(set(obj['fields']))!=len(obj['fields']) or obj['row_count']!=len(obj['items']) or any(len(r)!=len(obj['fields']) for r in obj['items']):raise ValueError('AUX_TABLE_SCHEMA')
        if type(obj['error_code']) is not int or type(raw.get('code')) is not int:raise ValueError('AUX_INTEGER_CODE')
        if obj['api_name']!='trade_cal' or obj['state']!='SUCCESS' or obj['error_code']!=0 or obj['http_status']!=200 or raw.get('code')!=0 or raw.get('data')!={'fields':obj['fields'],'items':obj['items']}:raise ValueError('AUX_CALENDAR_NOT_SUCCESS')
        if not old.clock(manifest['started_at'])<=old.clock(obj['request_started_at'])<=old.clock(obj['retrieved_at'])<=old.clock(manifest['retrieved_at'])<=old.clock(case['run_at']):raise ValueError('AUX_CLOCK')
        if set(obj['params'])!={'exchange','start_date','end_date'}:raise ValueError('AUX_PARAMS')
        exchange=obj['params']['exchange']
        if exchange not in ('SSE','SZSE') or exchange in calendars or obj['params']['start_date']!=manifest['scope']['end_date']:raise ValueError('AUX_SCOPE')
        rows=[dict(zip(obj['fields'],r)) for r in obj['items']]
        idx=old.date_index(rows,'cal_date');start=old.day(obj['params']['start_date']);end=old.day(obj['params']['end_date'])
        from datetime import date
        expected={(date.fromisoformat(start)+timedelta(days=n)).isoformat() for n in range((date.fromisoformat(end)-date.fromisoformat(start)).days+1)}
        if set(idx)!=expected or any(r['exchange']!=exchange or str(r['is_open']) not in ('0','1') for r in rows):raise ValueError('AUX_FULL_CIVIL_CALENDAR_REQUIRED')
        calendars[exchange]=[d for d in sorted(idx) if str(idx[d]['is_open'])=='1'];refs[exchange]=rawpath.name
        evidence[rawpath.name]=dict(source='OWNER_COMPATIBLE_GATEWAY/trade_cal',source_version=obj['raw_sha256'],raw_sha256=obj['raw_sha256'],published_at=None,available_at=obj['retrieved_at'],retrieved_at=obj['retrieved_at'],visibility_assumption='ACTUAL_CAPTURED_FUTURE_CALENDAR_METADATA_NOT_FUTURE_PRICES',path=str(rawpath))
        report['raw_pins'].update({str(path):old.rawhash(path),str(rawpath):old.rawhash(rawpath)})
    if set(calendars)!={'SSE','SZSE'} or calendars['SSE']!=calendars['SZSE']:raise ValueError('AUX_EXCHANGE_CALENDAR_REQUIRED')
    case['execution_calendar']=[dict(date=d,open_at=d+'T09:30:00+08:00',close_at=d+'T15:00:00+08:00',evidence_ref=refs['SSE']) for d in calendars['SSE']]

def _future_actions(folder,manifest,case,report):
    all_dates=sorted({m['date'] for m in case['calendar']+case['execution_calendar']});asof=case['calendar'][-1]['date'];seen={a['id']:a for a in case['actions']}
    for entry in manifest['sources']:
        if entry['api_name']!='dividend':continue
        obj=old.read(folder/entry['path']);ref=obj['raw_path'];symbol=obj['params']['ts_code']
        for row in [dict(zip(obj['fields'],r)) for r in obj['items']]:
            if row.get('div_proc')!='实施' or not row.get('ex_date'):continue
            ex=old.day(row['ex_date'])
            if ex<=asof or ex>all_dates[-1]:continue
            cash,bonus=old.dec(row['cash_div_tax']),old.dec(row['stk_div']);record=old.day(row['record_date'])
            components=[old.dec(row[k]) for k in ('stk_bo_rate','stk_co_rate') if row.get(k) is not None]
            if cash<0 or bonus<0 or cash+bonus<=0 or any(v<0 or v>bonus for v in components) or (len(components)==2 and sum(components)!=bonus):raise ValueError('FUTURE_ACTION_COMPONENTS')
            if record not in all_dates or ex not in all_dates or all_dates.index(ex)!=all_dates.index(record)+1:raise ValueError('FUTURE_ACTION_CALENDAR')
            a=dict(id=symbol+':'+ex,symbol=symbol,record_date=record,ex_date=ex,pay_date=old.day(row['pay_date']) if cash>0 else None,shares_available_date=old.day(row['div_listdate']) if bonus>0 else None,cash_per_share=str(cash),bonus_ratio=str(bonus),split_ratio='1',tax_rate='0.20',evidence_ref=ref)
            if any(a[k] and a[k]<ex for k in ('pay_date','shares_available_date')):raise ValueError('FUTURE_ACTION_SETTLEMENT_BEFORE_EX')
            if a['id'] in seen and seen[a['id']]!=a:raise ValueError('FUTURE_ACTION_REVISION_CONFLICT')
            seen[a['id']]=a
    case['actions']=sorted(seen.values(),key=lambda a:(a['ex_date'],a['symbol']))

def _prefix(case,prefix):
    mapping={k:prefix+'/'+k for k in case['evidence']};case['evidence']={mapping[k]:v for k,v in case['evidence'].items()}
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if (k=='evidence_ref' or k.endswith('_evidence_ref')) and v in mapping:x[k]=mapping[v]
                else:walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(case)

def _merge_prefix(case,prior):
    def economic(row):return {k:v for k,v in row.items() if not k.endswith('evidence_ref')}
    bars={(b['session'],b['symbol']):b for b in case['bars']}
    for b in prior['bars']:
        key=(b['session'],b['symbol'])
        if key not in bars or economic(b)!=economic(bars[key]):raise ValueError('PREVIOUS_OBSERVATION_REVISED:'+str(key))
        bars[key]=deepcopy(b)
    case['bars']=[bars[b['session'],b['symbol']] for b in case['bars']]
    previous_days={d['date']:d for d in prior['calendar']}
    for i,d in enumerate(case['calendar']):
        if d['date'] in previous_days:
            if economic(d)!=economic(previous_days[d['date']]):raise ValueError('PREVIOUS_CALENDAR_REVISED')
            case['calendar'][i]=deepcopy(previous_days[d['date']])
    cov={d['date']:d for d in prior['calendar_coverage']['days']}
    incoming={d['date']:d for d in case['calendar_coverage']['days']}
    if any(d not in incoming or cov[d]['is_open']!=incoming[d]['is_open'] for d in cov):raise ValueError('PREVIOUS_CIVIL_CALENDAR_REVISED')
    case['calendar_coverage']['days']=[deepcopy(cov.get(d['date'],d)) for d in case['calendar_coverage']['days']]
    acts={a['id']:a for a in case['actions']}
    for a in prior['actions']:
        if a['id'] not in acts or economic(a)!=economic(acts[a['id']]):raise ValueError('PREVIOUS_ACTION_REVISED')
        acts[a['id']]=deepcopy(a)
    case['actions']=sorted(acts.values(),key=lambda a:(a['ex_date'],a['symbol']))
    case['universe']=deepcopy(prior['universe'])
    if any(k in case['evidence'] and case['evidence'][k]!=v for k,v in prior['evidence'].items()):raise ValueError('PRIOR_EVIDENCE_COLLISION')
    case['evidence'].update(deepcopy(prior['evidence']))
    for proof in prior['evidence'].values():
        if proof.get('path') and old.rawhash(Path(proof['path']))!=proof['raw_sha256']:raise ValueError('PRIOR_RAW_CHANGED')

def build_case(folder,run_id,run_at,mode='HISTORY',prior=None):
    folder=Path(folder);p=protocol();effective=deepcopy(p)
    purpose='LOCAL_FORWARD_VIRTUAL_LEDGER' if mode=='FORWARD_A' else 'LOCAL_HISTORICAL_DIAGNOSTIC'
    if purpose not in old.read(POLICY).get('allowed_purposes',[]):raise ValueError('MODE_PURPOSE_NOT_AUTHORIZED')
    if mode=='FORWARD_A':
        m=old.read(folder/'Manifest.json');end=old.day(m['scope']['end_date'])
        effective['target_window']={'warmup_start':p['forward']['warmup_start'],'start':p['forward']['first_decision_session'],'end':end}
    report,case=_adapter(effective).build_case(folder,run_id,run_at)
    report.update(kind='LongForwardInputBuild',version='1.0.0',mode=mode,source_epoch='LONG_FORWARD_V1',authorized_purpose=purpose)
    if case is None:return report,None
    try:
        case.update(mode=mode,source_epoch='LONG_FORWARD_V1',protocol_ref=digest(p),rules=deepcopy(RULES),rules_hash=digest(RULES))
        if mode=='FORWARD_A':
            case['forward_scope']=effective['target_window'];case['evidence_grade']='CURRENT_OBSERVED_FORWARD'
            # Warmup metadata remains a historical clock convention, never a plan.
            # Only forward.prepare records actual freeze time.
            _aux(folder,m,case,report);_future_actions(folder,m,case,report)
            _prefix(case,folder.name)
            if prior is not None:_merge_prefix(case,prior)
        elif mode!='HISTORY':raise ValueError('UNKNOWN_MODE')
        report.update(status='ADMITTED_RECONSTRUCTED_DIAGNOSTIC_ONLY' if mode=='HISTORY' else 'ADMITTED_CURRENT_OBSERVATION_ONLY',case_hash=digest(case),protocol_hash=old.rawhash(PROTOCOL))
        return report,case
    except (ValueError,KeyError,TypeError,OSError,ArithmeticError) as exc:
        report['status']='DATA_BLOCKED';report['errors'].append({'type':type(exc).__name__,'detail':str(exc)});return report,None

def verify_provenance(case,folder,prior=None):
    report,repeated=build_case(folder,case['run_id'],case['run_at'],case['mode'],prior)
    if repeated!=case or not report['status'].startswith('ADMITTED_'):raise ValueError('LONG_FORWARD_PROVENANCE_REBUILD_MISMATCH')
    return dict(verified=True,case_hash=digest(case),receipt_hash=digest(report),purpose='LOCAL_FORWARD_VIRTUAL_LEDGER' if case['mode']=='FORWARD_A' else 'LOCAL_HISTORICAL_DIAGNOSTIC')
