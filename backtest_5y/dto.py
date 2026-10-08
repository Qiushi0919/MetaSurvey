"""Candidate metadata adapters for main-controller field review, not admission."""
from .interface import *
from .clocks import exact_clock, source_day
from .schema_subset import json_value, validate

VERSION='1.0.1-candidate'
KINDS = frozenset(('HistoricalEvidenceBundle','AdmittedHistoricalSnapshot',
    'StrategyFeatureDecision','DatedExecutionEconomics','WalkForwardWindowPlan',
    'AuditableSimulationRun'))

def clock(value, date_literal=None):
    value = date_literal if value is None else value
    if value is None: return {'value':None,'precision':'UNKNOWN','timezone':None}
    text=str(value)
    if type(value) is not str:
        return {'value':text,'precision':'UNINTERPRETED_SOURCE_LITERAL','timezone':None}
    try:
        day = source_day(text)
        out = {'value':day,'precision':'DATE_ONLY','timezone':None}
        if day != text: out['source_literal'] = text
        return out
    except ValueError: pass
    try:
        exact_clock(text)
        return {'value':text,'precision':'EXACT_SOURCE_RECORDED',
            'timezone':'+00:00' if text.endswith('Z') else text[-6:],
            'subsecond_precision':'AS_RECORDED_NOT_INFERRED'}
    except ValueError: pass
    return {'value':text,'precision':'UNINTERPRETED_SOURCE_LITERAL','timezone':None}

def evidence_bundle(records):
    items=[]
    for r in records:
        fields=r.get('fields',{});p=r.get('provenance',{})
        dates=p.get('publication_date_fields',{})
        published=r.get('published_at')
        original_date=dates.get('f_ann_date') or dates.get('ann_date') or fields.get('f_ann_date') or fields.get('ann_date') or fields.get('publish_date')
        items.append({'symbol':r['symbol'],'domain':r['domain'],'identity':r['identity'],
            'event':clock(r.get('event_date')),'published':clock(published,original_date),
            'available':clock(r.get('available_at')),'retrieved':clock(r.get('retrieved_at')),
            'first_visible':clock(r.get('first_visible_at')),
            'original_disclosure_fields':{k:fields[k] for k in ('ann_date','f_ann_date','publish_date','update_time') if k in fields},
            'effective_interval':{'from':fields.get('in_date',fields.get('list_date')),
                'until':fields.get('out_date',fields.get('delist_date')),'endpoint_semantics':'UNVERIFIED_SOURCE_NOT_ASSUMED_OPEN_ENDED'},
            'knowledge_interval':{'from':r.get('first_visible_at'),'until':None,'state':'UNKNOWN'},
            'source':{'id':r['source'],'url':r['source_url'],'raw_ref':r['raw_ref'],'raw_sha256':r['raw_sha256'],
                'record_hash':r['record_hash'],'row_ordinal':r['row_ordinal'],
                'row_selector':p.get('source_selector',p.get('row_ordinal')),
                'version':r['raw_sha256'],'version_semantics':'CAPTURE_CONTENT_HASH_NOT_VENDOR_REVISION',
                'revision_id':r.get('revision_id'),'revision_chain':'NOT_ACCEPTED',
                'license_state':r['license_state'],'technical_access':'CAPTURED_NOT_LICENSE_PROOF'},
            'units':r['units'],'fields':fields,'reason_codes':['HISTORICAL_VISIBILITY_UNPROVEN','SOURCE_ADMISSION_UNACCEPTED'],
            'invalidation':['RAW_OR_RECORD_HASH_CONFLICT','FUTURE_PUBLICATION','UNKNOWN_REQUIRED_CLOCK_OR_UNIT'],
            'formal_admitted':False})
    return {'kind':'HistoricalEvidenceBundle','version':VERSION,'labels':LABELS,'records':items,
        'historical_visibility_proven':False,'productionGate':False}

def candidate(kind,body):
    return {**body,'kind':kind,'version':VERSION}

def validate_candidate(value):
    """Current sidecar consumer checks; final JSON-Schema review stays external."""
    json_value(value)
    if type(value) is not dict: raise ValueError('DTO_OBJECT_REQUIRED')
    kind=value.get('kind')
    if type(kind) is not str or kind not in KINDS: raise ValueError('DTO_KIND_UNSUPPORTED')
    path=ROOT/'contracts/backtest-5y'/f'{kind}.schema.json'
    schema=__import__('json').loads(path.read_bytes())
    if kind=='AuditableSimulationRun' and type(value.get('metrics')) is dict and any(v is not None for v in value['metrics'].values()):
        raise ValueError('DTO_UNRUN_METRIC_NULL')
    validate(value, schema)
    if kind=='HistoricalEvidenceBundle':
        import re
        for r in value['records']:
            for name in schema['properties']['records']['items']['required']:
                if name not in r: raise ValueError('DTO_RECORD_REQUIRED:'+name)
            if r['formal_admitted'] is not False: raise ValueError('DTO_NO_ADMISSION')
            for name in ('event','published','available','retrieved','first_visible'):
                c=r[name]
                if not all(k in c for k in ('value','precision','timezone')): raise ValueError('DTO_CLOCK_REQUIRED')
                precision = c['precision']
                if precision=='DATE_ONLY':
                    if c['timezone'] is not None or source_day(c['value']) != c['value']:
                        raise ValueError('DTO_DATE_ONLY_NOT_MIDNIGHT')
                elif precision=='EXACT_SOURCE_RECORDED':
                    exact_clock(c['value'])
                    zone = '+00:00' if c['value'].endswith('Z') else c['value'][-6:]
                    if c['timezone'] != zone: raise ValueError('DTO_CLOCK_OFFSET_CONFLICT')
                elif precision=='UNKNOWN':
                    if c['value'] is not None or c['timezone'] is not None: raise ValueError('DTO_UNKNOWN_CLOCK_CONFLICT')
                elif c['timezone'] is not None: raise ValueError('DTO_UNINTERPRETED_CLOCK_OFFSET')
            for name in schema['properties']['records']['items']['properties']['source']['required']:
                if name not in r['source']: raise ValueError('DTO_SOURCE_REQUIRED:'+name)
            for name in ('raw_sha256','record_hash'):
                if not re.fullmatch('[a-f0-9]{64}',r['source'][name]): raise ValueError('DTO_SOURCE_HASH')
    if kind=='StrategyFeatureDecision' and value['families']!=list(FAMILIES): raise ValueError('DTO_FROZEN_FAMILIES')
    if kind=='AuditableSimulationRun' and any(v is not None for v in value['metrics'].values()): raise ValueError('DTO_UNRUN_METRIC_NULL')
    return True

def walk_forward_plan():
    p=__import__('json').loads((ROOT/'backtest_5y/protocol.json').read_bytes())
    return candidate('WalkForwardWindowPlan',{'state':'NOT_COMPUTABLE','parameters':p['split'],
        'anchor':None,'windows':[],'purge_objects':'UNSET_REQUIRED','embargo_origin':'UNSET_REQUIRED',
        'cross_window_positions_and_cash':'UNSET_REQUIRED','right_censoring_policy':'UNSET_REQUIRED',
        'reason_codes':['ACTUAL_SESSION_GRID_AND_BOUNDARY_POLICIES_UNACCEPTED','EXPOSED_HISTORY_NOT_SEALED_OOS'],
        'engineering_collection_buffer':HISTORY_START,'engineering_evaluation_start':EVALUATION_START,
        'untouched_oos':False,'formal_windows_executed':0,'productionGate':False})
