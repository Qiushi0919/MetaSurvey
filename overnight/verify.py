"""Closed offline engineering verifier. No credentials, network or source grants."""
import hashlib
import json
import os
from pathlib import Path
from .data.dataset import canonical, load_verified_dataset, sha, require
from .data.coverage import analyze_coverage
from .analysis.reconcile import analyze_reconciliation
from .analysis.financial import analyze_financial
from .admission.dry_run import build_readiness

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path('/Users/qiushi/投资研究/.p1b-archives/overnight-20261005')
NAVIGATION = ['AGENTS.md','README.md','docs/source-of-truth.json']

def checked_bytes(path, expected, root, maximum=10*1024*1024):
    require(isinstance(path,Path) and path.is_absolute() and '..' not in path.parts and
            str(path).startswith(str(root)+'/'), 'OVERNIGHT_EVIDENCE_PATH_INVALID')
    require(root.resolve()==root and path.resolve()==path and path.is_file() and not path.is_symlink(), 'OVERNIGHT_EVIDENCE_PATH_INVALID')
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(fd)
            require(before.st_size<=maximum, 'OVERNIGHT_EVIDENCE_SIZE_INVALID')
            with os.fdopen(fd,'rb',closefd=False) as stream: raw=stream.read(maximum+1)
            after=os.fstat(fd)
            require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                    (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns) and
                    path.resolve()==path, 'OVERNIGHT_EVIDENCE_CHANGED')
        finally: os.close(fd)
    except OSError:
        raise ValueError('OVERNIGHT_EVIDENCE_FILE_UNAVAILABLE') from None
    require(sha(raw)==expected,'OVERNIGHT_EVIDENCE_HASH_MISMATCH')
    return raw

def verify_release():
    release=json.loads((ROOT/'contracts/release.overnight.1_8_2.json').read_bytes())
    require(set(release)=={'version','scope','schema_version','new_migrations','admitted_policy_count',
                          'historical_visibility_proven','production_enabled','files','contract_versions'},'OVERNIGHT_RELEASE_FIELDS_INVALID')
    require(release['version']=='1.8.2-offline' and release['scope']=='OFFLINE_ENGINEERING_DIAGNOSTICS_ONLY' and
            release['schema_version']==6 and release['new_migrations']==[] and release['admitted_policy_count']==0 and
            release['historical_visibility_proven'] is False and release['production_enabled'] is False and
            release['contract_versions']=={'AdmissionReadinessDryRun':'1.0.0-diagnostic'},'OVERNIGHT_RELEASE_AUTHORITY_INVALID')
    expected={str(p.relative_to(ROOT)) for root in (ROOT/'overnight',ROOT/'contracts/overnight')
              for p in root.rglob('*') if p.is_file() and p.suffix in ('.py','.mjs','.json')}
    expected.update(['docs/overnight/evidence.json','docs/overnight/baseline-pins.json'])
    refs=release['files']
    require(type(refs) is list and len(refs)==len(expected) and {r['path'] for r in refs}==expected,
            'OVERNIGHT_RELEASE_INVENTORY_INVALID')
    for ref in refs:
        require(set(ref)=={'path','sha256'},'OVERNIGHT_RELEASE_FIELDS_INVALID')
        checked_bytes(ROOT/ref['path'],ref['sha256'],ROOT)
    return release

def verify_baseline():
    baseline=json.loads((ROOT/'docs/overnight/baseline-pins.json').read_bytes())
    require(baseline['baseline_commit']=='456242752ec0a78c26b945d04bbc117a4fba6e20' and
            len(baseline['tracked_files'])==433 and baseline['allowed_navigation_updates']==NAVIGATION,
            'OVERNIGHT_BASELINE_INVALID')
    before=json.loads(checked_bytes(ARCHIVE/'start/checkpoint.json',baseline['checkpoint_sha256'],ARCHIVE))
    require(baseline['tracked_files']==before['tracked_files'] and baseline['allowed_navigation_updates']==before['allowed_navigation_updates'],
            'OVERNIGHT_BASELINE_CHANGED')
    unchanged=0
    for ref in baseline['tracked_files']:
        if ref['path'] in NAVIGATION: continue
        checked_bytes(ROOT/ref['path'],ref['sha256'],ROOT)
        unchanged+=1
    return {'baseline_tracked_files':433,'immutable_files_verified':unchanged,'navigation_only_allowed':NAVIGATION}

def verify_outputs():
    evidence=json.loads((ROOT/'docs/overnight/evidence.json').read_bytes())
    require(evidence['version']=='1.0.0-diagnostic' and evidence['source_admission']=='BLOCKED' and
            evidence['historical_visibility_proven'] is False and evidence['productionGate'] is False,
            'OVERNIGHT_OUTPUT_AUTHORITY_INVALID')
    bodies={}
    for ref in evidence['artifacts']:
        require(set(ref)=={'object','path','sha256','bytes'},'OVERNIGHT_EVIDENCE_REF_INVALID')
        require(ref['object'] not in bodies,'OVERNIGHT_EVIDENCE_DUPLICATE')
        raw=checked_bytes(Path(ref['path']),ref['sha256'],ARCHIVE)
        require(len(raw)==ref['bytes'],'OVERNIGHT_EVIDENCE_SIZE_INVALID')
        bodies[ref['object']]=raw
    expected={'typed_dataset','coverage','factor','financial','fixture_proof','fixture_artifacts','readiness'}
    require(set(bodies)==expected,'OVERNIGHT_OUTPUT_INVENTORY_INVALID')
    dataset=load_verified_dataset()
    for key,obj in [('typed_dataset',dataset),('coverage',analyze_coverage(dataset)),('factor',analyze_reconciliation(dataset)),
                    ('financial',analyze_financial(dataset)),('readiness',build_readiness(dataset))]:
        require(bodies[key]==canonical(obj)+b'\n','OVERNIGHT_DIAGNOSTIC_REPLAY_DIFFERED')
    proof=json.loads(bodies['fixture_proof'])
    require(proof['fixture'] is True and proof['base_and_revision_replays_equal'] is True and
            proof['source_admission']=='BLOCKED' and proof['productionGate'] is False and
            proof['real_card_count']==0 and proof['model_calls']==0 and proof['execution_writes']==0 and
            proof['broker_transport_calls']==0 and len(proof['cases'])==4 and
            all(x['result']=='BLOCKED_AS_REQUIRED' for x in proof['invalidation_attacks']),
            'OVERNIGHT_FIXTURE_PROOF_INVALID')
    artifacts=json.loads(bodies['fixture_artifacts'])
    require(set(artifacts)=={'base','revision','timing','hard_block'},'OVERNIGHT_FIXTURE_PROOF_INVALID')
    for name in artifacts:
        card=artifacts[name]['card']
        require(card['symbol']=='SYNTHETIC:NON_SECURITY_FIXTURE' and card['account_id']=='SYNTHETIC_FIXTURE:NON_ACCOUNT' and
                card['grade']=='UNSET_REQUIRED' and card['trade']['can_produce_order'] is False,'OVERNIGHT_REAL_CARD_FORBIDDEN')
    return {'verified_artifacts':len(bodies),'requests':len(dataset['requests']),
            'physical_rows':sum(q['row_count'] for q in dataset['requests']),'source_admission':'BLOCKED',
            'authenticated_requests_this_run':0,'credential_lookups_this_run':0,'productionGate':False}

def main():
    try:
        verify_release(); result={'baseline':verify_baseline(),'outputs':verify_outputs()}
        print(json.dumps(result,ensure_ascii=False));return 0
    except Exception:
        print('OVERNIGHT_VERIFICATION_FAILED_NO_PERMISSION');return 1

if __name__=='__main__':raise SystemExit(main())
