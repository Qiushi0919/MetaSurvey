"""Immutable bounded context. Shape/hash validation is display-only."""
import json
from .common import *

NAMES = ('Historical-PIT-Three-Symbol-Matrix.json', 'Price-Backtest-Minimum-PIT-Gate.json',
         'Backtest-Engine-Readiness.json', 'Snapshot-B-Activation-Readiness.json',
         'Forward-Paper-Activation-Readiness.json')
_ISSUED = {}

def frozen_context():
    from post_wave_e.core import frozen_context as previous
    old = previous()
    base_path = ROOT / 'docs/wave-f/baseline-pins.json'
    base_raw = checked_file(base_path); base = json.loads(base_raw)
    require(base['baseline_commit'] == 'afb102f2f10ceb4330d837b17ab580c478b42fbb' and
            len(base['tracked_files']) == 725 and base['immutable_count'] == 722 and
            base['allowed_navigation_updates'] == ['AGENTS.md','README.md','docs/source-of-truth.json'], 'WF_BASELINE')
    start = base['checkpoint_ref']; start_bytes = checked_file(start['path'], start['sha256'])
    require(len(start_bytes) == start['bytes'] and
            json.loads(start_bytes)['tracked_files'] == base['tracked_files'], 'WF_BASELINE_CHECKPOINT')
    dependencies = {str(p):h for p,h in old['pins']}
    dependencies[str(base_path)] = sha(base_raw)
    dependencies[start['path']] = start['sha256']
    for r in base['tracked_files']:
        if r['path'] not in base['allowed_navigation_updates']:
            dependencies[str(ROOT/r['path'])] = r['sha256']
    release_path = ROOT/'docs/wave-f/release.json'
    raw = checked_file(release_path); release = json.loads(raw)
    require(release['version'] == VERSION+'-wave-f-preparation' and
            release['productionGate'] is False and release['actual_forward_days'] == 0 and
            release['formal_backtest_authorized'] is False, 'WF_RELEASE_AUTHORITY')
    declared = sorted(r['path'] for r in release['code_pins'])
    inventory = sorted(str(p.relative_to(ROOT)) for p in (ROOT/'wave_f').rglob('*') if p.is_file() and '__pycache__' not in str(p))
    fixed = ['docs/wave-f/Interface-Freeze.md','docs/wave-f/baseline-pins.json',
             'docs/wave-f/Frozen-StrategySpec-v1.json','docs/wave-f/Owner-Policy-Decision-Sheet.md',
             'docs/wave-f/Snapshot-B-Runbook.md','docs/authorizations/P1B-WAVE-F-20261006.md',
             'docs/adr/ADR-032-predeclared-research-candidates.md']
    require(declared == sorted(inventory + fixed), 'WF_CODE_INVENTORY')
    dependencies[str(release_path)] = sha(raw)
    for r in release['code_pins']:
        dependencies[str(ROOT/r['path'])] = r['sha256']
    prereg = release['preregistration_ref']
    prereg_bytes = checked_file(prereg['path'], prereg['sha256'])
    require(len(prereg_bytes)==prereg['bytes'], 'WF_PREREGISTRATION_SIZE')
    pr = json.loads(prereg_bytes); spec = json.loads(checked_file(ROOT/'docs/wave-f/Frozen-StrategySpec-v1.json'))
    require(pr['spec_file_sha256'] == sha(checked_file(ROOT/'docs/wave-f/Frozen-StrategySpec-v1.json')) and
            pr['spec_json_digest'] == digest(spec) and pr['families']==2 and
            pr['new_performance_results_revealed']==0 and spec['family_count']==2 and
            spec['productionGate'] is False and spec['formal_backtest_authorized'] is False and
            spec['actual_account_parameters']=='30_UNSET_REQUIRED', 'WF_PREREGISTRATION_CHANGED')
    dependencies[prereg['path']] = prereg['sha256']
    from .pit import source_pins
    for r in source_pins():
        p = Path(r['path'])
        require(p.is_relative_to(ARCHIVE.parent) and len(checked_file(p,r['sha256']))==r['bytes'], 'WF_PUBLIC_EVIDENCE_INVALID')
        dependencies[str(p)] = r['sha256']
    for p,h in dependencies.items(): checked_file(p,h)
    pins = [{'path':p,'sha256':h} for p,h in sorted(dependencies.items())]
    identities = [{'identity': 'git:'+str(Path(r['path']).relative_to(ROOT))
                   if Path(r['path']).is_relative_to(ROOT) else 'archive:'+r['path'],
                   'sha256':r['sha256']} for r in pins]
    identities.sort(key=lambda r:r['identity'])
    return {'context_hash':digest(identities), 'code_hash':digest(release['code_pins']),
            'spec_hash':digest(spec), 'source_dependencies':pins,
            'prior_source_identity':old['source_identity'], 'baseline_commit':base['baseline_commit']}

def payloads():
    from .pit import three_symbol_matrix, minimum_price_gate
    from .backtest import readiness as backtest_readiness
    from .activation import snapshot_readiness, forward_readiness
    c = frozen_context()
    bodies = [three_symbol_matrix(),minimum_price_gate(),backtest_readiness(),snapshot_readiness(),forward_readiness()]
    result = {}
    for name,body in zip(NAMES,bodies):
        if 'body' in body:
            require(body['live_authority'] is False and body['actual_forward_days']==0 and
                    body['productionGate'] is False, 'WF_BODY_AUTHORITY')
            body=body['body']
        if name == 'Historical-PIT-Three-Symbol-Matrix.json':
            body = dict(body, requested_research_window={
                'from':'2021-10-08','through':'2026-09-30',
                'minimum_actual_sessions_proposed':1260,
                'role':'FROZEN_RESEARCH_CANDIDATE_NOT_OWNER_POLICY',
                'complete_historical_coverage_proven':False,
                'actual_owner_window':UNSET})
        obj = metadata(body)
        obj.pop('content_hash')
        obj.update({'artifact_name':name, 'context_hash':c['context_hash'],
                    'code_hash':c['code_hash'], 'strategy_spec_hash':c['spec_hash'],
                    'source_admission':'BLOCKED', 'provider_license_transport_verified':False,
                    'formal_backtest_authorized':False, 'snapshot_b_authorized':False,
                    'forward_paper_authorized':False, 'symbols':list(SYMBOLS)})
        obj = seal(obj)
        _ISSUED[id(obj)] = (obj,digest(obj),c['context_hash'])
        result[name] = obj
    require(frozen_context()['context_hash']==c['context_hash'], 'WF_CONTEXT_DRIFT')
    return result

def display(obj):
    issued = _ISSUED.get(id(obj)); require(issued is not None and issued[0] is obj and
        issued[1]==digest(obj) and issued[2]==frozen_context()['context_hash'],'WF_NOT_ISSUED_OR_MUTATED')
    return obj

def transition(obj,target):
    display(obj); require(target=='LOCAL_PREPARATION_DISPLAY','WF_NO_NATIVE_PROMOTION'); return obj

def run_formal(*args,**kwargs): unavailable('WF_FORMAL_BACKTEST_NOT_AUTHORIZED')
def actual_snapshot_b(*args,**kwargs): unavailable('WF_ACTUAL_SNAPSHOT_B_NOT_AUTHORIZED')
def actual_forward(*args,**kwargs): unavailable('WF_ACTUAL_FORWARD_NOT_AUTHORIZED')
def production_execute(*args,**kwargs): unavailable('WF_PRODUCTION_NOT_AUTHORIZED')
