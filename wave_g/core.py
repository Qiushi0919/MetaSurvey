"""Frozen local diagnostic context. No hash or display object grants authority."""
from .common import *

NAMES=('Provider-License-Transport-Evidence-Pack.json','Historical-PIT-Three-Symbol-Matrix.json',
       'Historical-PIT-Closure-Progress.json','Retrospective-Diagnostic-Summary.json',
       'Snapshot-B-Activation-Readiness.json','Forward-Paper-Activation-Readiness.json',
       'Small-Live-Pilot-Policy-Summary.json')
FIXED=('docs/wave-g/Interface-Freeze.md','docs/wave-g/baseline-pins.json',
       'docs/wave-g/Diagnostic-Protocol-v1.json','docs/wave-g/Diagnostic-Protocol-v1.1.json',
       'docs/wave-g/Provider-License-Transport-Evidence.md','docs/wave-g/Provider-Redacted-Material-Template.json',
       'docs/wave-g/Small-Live-Pilot-Policy-v0.json','docs/wave-g/Small-Live-Pilot-Policy-v0.md',
       'docs/wave-g/Snapshot-B-Day-1-Runbook.md',
       'docs/authorizations/P1B-WAVE-G-20261007.md','docs/adr/ADR-033-retrospective-diagnostic-and-preflight.md')
_ISSUED={}

def frozen_context():
    from wave_f.core import frozen_context as previous
    from .pit import source_pins
    from .provider import public_evidence
    from .diagnostic import evidence
    old=previous(); refs={}
    def add(r):
        raw=checked_reference(r); p=Path(r['path']); actual=locate_reference(p)
        require(actual.is_relative_to(ROOT) or actual.is_relative_to(ARCHIVE.parent),'WG_DEPENDENCY_ROOT')
        identity=str(BASELINE_ROOT/actual.relative_to(ROOT)) if actual.is_relative_to(ROOT) else str(actual)
        r=dict(r,path=identity)
        require(identity not in refs or refs[identity]==r,'WG_DEPENDENCY_CONFLICT')
        refs[identity]=r
    for r in old['source_dependencies']:add(reference(locate_reference(r['path'])))
    baseline_raw=checked_file(ROOT/'docs/wave-g/baseline-pins.json');b=json.loads(baseline_raw)
    require(b['baseline_commit']=='1346ca34c6dee58a809c26e69edc338a2de35603' and
            len(b['tracked_files'])==767 and b['immutable_count']==764 and
            b['allowed_navigation_updates']==['AGENTS.md','README.md','docs/source-of-truth.json'],'WG_BASELINE')
    start_raw=checked_file(b['checkpoint_ref']['path'],b['checkpoint_ref']['sha256'])
    start=json.loads(start_raw)
    require(start['tracked_files']==b['tracked_files'],'WG_START_CHECKPOINT')
    add(dict(b['checkpoint_ref'],bytes=len(start_raw)))
    for r in b['tracked_files']:
        if r['path'] not in b['allowed_navigation_updates']:add(dict(r,path=str(BASELINE_ROOT/r['path'])))
    release=json.loads(checked_file(ROOT/'docs/wave-g/release.json'))
    require(release['version']=='1.0.0-wave-g-local-diagnostic' and release['actual_forward_days']==0 and
            release['productionGate'] is False and release['actual_activation_authorized'] is False,'WG_RELEASE_AUTHORITY')
    inventory=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'wave_g').rglob('*') if p.is_file() and '__pycache__' not in str(p))
    require(sorted(r['path'] for r in release['code_pins'])==sorted(inventory+list(FIXED)),'WG_CODE_INVENTORY')
    add(reference(ROOT/'docs/wave-g/release.json'))
    for r in release['code_pins']:add(dict(r,path=str(BASELINE_ROOT/r['path'])))
    for r in release['private_pins']:add(r)
    for r in source_pins():add(r)
    for r in public_evidence()[1]:add(r)
    d=evidence()
    for r in d['direct_input_refs']+d['artifacts']:add({k:r[k] for k in ('path','sha256','bytes')})
    protocol()
    from .policy import owner_settings
    owner_settings()
    pins=sorted(refs.values(),key=lambda r:r['path'])
    return {'context_hash':digest(pins),'code_hash':digest(release['code_pins']),
            'spec_hash':old['spec_hash'],'protocol_hash':sha(checked_file(ROOT/'docs/wave-g/Diagnostic-Protocol-v1.1.json')),
            'source_dependencies':pins,'immutable_baseline_files':764,'prior_context_hash':old['context_hash']}

def payloads():
    from .provider import evidence_pack
    from .pit import evidence_matrix,pit_progress
    from .diagnostic import report
    from .activation import snapshot_readiness,forward_readiness
    from .policy import small_live_policy
    c=frozen_context();result={}
    for name,factory in zip(NAMES,(evidence_pack,evidence_matrix,pit_progress,report,snapshot_readiness,forward_readiness,small_live_policy)):
        obj=factory();require(obj['productionGate'] is False and obj['actual_forward_days']==0 and obj['live_authority'] is False,'WG_BODY_AUTHORITY')
        obj.pop('content_hash');obj.update(artifact_name=name,context_hash=c['context_hash'],code_hash=c['code_hash'],
            strategy_spec_hash=c['spec_hash'],protocol_hash=c['protocol_hash'],symbols=list(SYMBOLS),
            provider_license_transport_verified=False,formal_backtest_authorized=False,
            snapshot_b_authorized=False,forward_paper_authorized=False)
        obj=seal(obj);_ISSUED[id(obj)]=(obj,digest(obj),c['context_hash']);result[name]=obj
    require(frozen_context()['context_hash']==c['context_hash'],'WG_CONTEXT_DRIFT')
    return result

def display(obj):
    issued=_ISSUED.get(id(obj))
    require(issued is not None and issued[0] is obj and issued[1]==digest(obj) and
            issued[2]==frozen_context()['context_hash'],'WG_NOT_ISSUED_OR_MUTATED')
    return obj

def transition(obj,target):
    display(obj);require(target=='LOCAL_DIAGNOSTIC_DISPLAY','WG_NO_NATIVE_PROMOTION');return obj

def run_formal(*args,**kwargs):blocked('WG_FORMAL_BACKTEST_NOT_AUTHORIZED')
def actual_snapshot_b(*args,**kwargs):blocked('WG_ACTUAL_SNAPSHOT_B_NOT_AUTHORIZED')
def actual_forward(*args,**kwargs):blocked('WG_ACTUAL_FORWARD_NOT_AUTHORIZED')
def production_execute(*args,**kwargs):blocked('WG_PRODUCTION_NOT_AUTHORIZED')
def issue_native(*args,**kwargs):blocked('WG_NATIVE_ISSUANCE_NOT_AUTHORIZED')
def cloud_export(*args,**kwargs):blocked('WG_CLOUD_EXPORT_NOT_AUTHORIZED')
