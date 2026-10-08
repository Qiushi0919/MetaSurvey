"""Frozen H-A offline context and readiness display; no actual activation."""
import json
from pathlib import Path
from .common import *
NAMES=('Actual-Collector-Readiness.json','Snapshot-B-Readiness.json',
       'Forward-Paper-Readiness.json','Owner-Activation-Report.json',
       'Historical-PIT-Three-Symbol-Matrix.json','Historical-PIT-Closure-Progress.json')
_DISPLAY={}

def frozen_context():
    from wave_g.core import frozen_context as old
    from .pit import source_pins
    c=old();refs={}
    def add(r):
        reopen(r);p=locate(r['path']);identity=str(BASELINE_ROOT/p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
        item=dict(r,path=identity);require(identity not in refs or refs[identity]==item,'WH_CONTEXT_REFERENCE_CONFLICT');refs[identity]=item
    for r in c['source_dependencies']:add(r)
    b=json.loads(checked_file(ROOT/'docs/wave-h/baseline-pins.json'))
    require(b['baseline_commit']=='43e75c6411c482596844a48267cdf728de05e527' and len(b['tracked_files'])==815 and
            b['immutable_count']==812 and b['allowed_navigation_updates']==['AGENTS.md','README.md','docs/source-of-truth.json'] and
            b['H_A_only'] is True and b['actual_forward_days']==0 and b['productionGate'] is False,'WH_BASELINE_DRIFT')
    start=json.loads(checked_file(ARCHIVE/'start/Start-Checkpoint.json'))
    require(start==b,'WH_START_CHECKPOINT_DRIFT');add(ref(ARCHIVE/'start/Start-Checkpoint.json'))
    add(b['wave_g_checkpoint_ref'])
    for r in b['tracked_files']:
        if r['path'] not in b['allowed_navigation_updates']:add(dict(r,path=str(BASELINE_ROOT/r['path'])))
    release=json.loads(checked_file(ROOT/'docs/wave-h/release.json'))
    require(release['version']=='1.0.0-wave-h-actual-preparation' and release['code_pins']==code_manifest() and
            release['actual_activation_authorized'] is False and release['actual_forward_days']==0 and
            release['authenticated_requests']==0 and release['credential_lookups']==0 and
            release['productionGate'] is False and release['schema_version']==6 and release['new_native_contracts']==0,'WH_RELEASE_DRIFT')
    add(ref(ROOT/'docs/wave-h/release.json'))
    for r in release['code_pins']:add(dict(r,path=str(BASELINE_ROOT/r['path'])))
    for r in release['private_pins']:add(r)
    for r in source_pins():add(r)
    a=json.loads(checked_file(ROOT/'config/wave-h/snapshot-a-reference.json'));add(a['snapshot_a_ref'])
    pins=sorted(refs.values(),key=lambda r:r['path'])
    return {'context_hash':digest(pins),'code_hash':code_hash(),'bindings':bindings(),
            'source_dependencies':pins,'immutable_baseline_files':812,
            'prior_context_hash':c['context_hash'],'prior_dependency_count':len(c['source_dependencies'])}

def _readiness():
    return {'symbols':list(SYMBOLS),'H_A':'OFFLINE_ENGINEERING_ONLY','H_B':'NEW_OWNER_AUTH_REQUIRED_NOT_AUTORUN',
            'actual_collector':'READY_FOR_ONE_SHOT_OWNER_AUTH','actual_snapshot_b':'NOT_YET_RUN',
            'actual_forward_days':0,'actual_authority_enrollment':'NOT_ENROLLED',
            'credential_presence':'NOT_RECHECKED_IN_H_A','provider_license_transport':'UNKNOWN_BLOCKED',
            'formal_price_pit':'BLOCKED','formal_fundamental_pit':'BLOCKED','safe_to_trade':False,
            'decision':'NO_DECISION','native_order_broker_cloud_production':False,
            'actual_runtime_prerequisites':['FRESH_OWNER_H_B_AUTHORIZATION','OWNER_INSTALLED_DISTINCT_PUBLIC_TRUST_ROOTS',
              'REAL_OBSERVED_OPEN_AND_EOD_WITH_ORIGINALS','FRESH_EXACT_THREE_CURRENT_RESPONSES',
              'FIXED_NAMED_KEYCHAIN_CREDENTIAL_AVAILABLE','EXTERNAL_INDEPENDENT_REVIEW_SIGNATURE',
              'SEPARATE_HUMAN_FORWARD_SIGNATURE_BOUND_SNAPSHOT_AND_HEAD'],
            'limits':'implemented code and offline verification; no actual positive live run or provider/PIT/trading certification'}

def payloads():
    from .forward import store_configuration
    from .pit import evidence_matrix,progress
    from wave_g.policy import owner_settings
    c=frozen_context();base=_readiness()
    factories=(lambda:metadata('ACTUAL_COLLECTOR_CODE_READINESS',dict(base,request_budget=13,
                  source_schema_version=policy()['source_schema_version'],policy=policy(),
                  credentials_read_now=False,actual_request_count=0)),
               lambda:metadata('ACTUAL_SNAPSHOT_B_CODE_READINESS',dict(base,
                  source_exception='LOCAL_ONLY_CURRENT_CAPTURE_NOT_SOURCE_ADMISSION',
                  reference_a=json.loads(checked_file(ROOT/'config/wave-h/snapshot-a-reference.json')),
                  producer_self_approval=False,calendar_only_actual_session=False)),
               lambda:metadata('ACTUAL_FORWARD_CODE_READINESS',dict(base,actual_store=store_configuration(True),
                  simulation_store=store_configuration(False),actual_store_created=False,
                  staging_bool_promotion=False,actual_signing_keys_in_product=False)),
               lambda:metadata('OWNER_ACTIVATION_REPORT',dict(base,account_parameters=owner_settings(),
                  source_exception_version='1.0.0',contracts_version='1.0.0',
                  STOP=True,no_scheduler=True,code_ready_does_not_mean_activated=True)),
               evidence_matrix,progress)
    result={}
    for name,factory in zip(NAMES,factories):
        x=factory();x.pop('content_hash');x.update(context_hash=c['context_hash'],code_hash=c['code_hash'],artifact_name=name)
        require(x['actual_forward_days']==0 and x['productionGate'] is False,'WH_METADATA_PROMOTION')
        x=seal(x);_DISPLAY[id(x)]=(x,digest(x),c['context_hash']);result[name]=x
    require(frozen_context()==c,'WH_CONTEXT_CHANGED_DURING_PROJECT');return result

def display(x):
    item=_DISPLAY.get(id(x));require(item is not None and item[0] is x and item[1]==digest(x) and
            item[2]==frozen_context()['context_hash'],'WH_DISPLAY_NOT_ISSUED_OR_INVALIDATED');return x

def transition(x,target):
    display(x);require(target=='LOCAL_READINESS_DISPLAY','WH_DISPLAY_NO_AUTHORITY_PROMOTION');return x
def issue_native(*a,**k):blocked('WH_NATIVE_ISSUANCE_FORBIDDEN')
def execute_trade(*a,**k):blocked('WH_TRADE_FORBIDDEN')
def cloud_export(*a,**k):blocked('WH_CLOUD_EXPORT_FORBIDDEN')
def production_execute(*a,**k):blocked('WH_PRODUCTION_FORBIDDEN')
def run_formal(*a,**k):blocked('WH_FORMAL_PIT_BACKTEST_FORBIDDEN')
