"""Read-only exact-byte verification and deterministic candidate reproduction."""
import json
from pathlib import Path
from .primitives import ROOT,sha,canonical,require
from .evidence_root import ARCHIVE
from .core import load_inputs,require_inputs,require_result
from .run import replay,SECTIONS

def verify():
    pins=json.loads((ROOT/'docs/wave-b/baseline-pins.json').read_bytes())
    immutable=0
    for ref in pins['tracked_files']:
        if ref['path'] in pins['allowed_navigation_updates']:continue
        p=ROOT/ref['path'];require(p.resolve()==p and not p.is_symlink() and sha(p.read_bytes())==ref['sha256'],'BASELINE_BYTES_CHANGED');immutable+=1
    release=json.loads((ROOT/'docs/wave-b/release.json').read_bytes())
    require(release['productionGate'] is False and release['source_admission']=='BLOCKED','RELEASE_PERMISSION_INVALID')
    for ref in release['code_pins']:
        p=ROOT/ref['path'];require(p.resolve()==p and not p.is_symlink() and sha(p.read_bytes())==ref['sha256'],'RELEASE_CODE_CHANGED')
    manifest=json.loads((ROOT/'docs/wave-b/evidence.json').read_bytes());expected={}
    for ref in manifest['artifacts']:
        p=Path(ref['path']);require(p.is_relative_to(ARCHIVE/'results') and p.resolve()==p and not p.is_symlink() and (p.stat().st_mode&0o777)==0o600,'ARTIFACT_PATH_INVALID')
        raw=p.read_bytes();require(len(raw)==ref['bytes'] and sha(raw)==ref['sha256'],'ARTIFACT_BYTES_CHANGED');expected[ref['object']]=json.loads(raw)
    inputs=load_inputs();require(canonical(inputs)==canonical(expected['typed_inputs']),'TYPED_REPLAY_CHANGED')
    actual=replay(inputs)
    for name,result in actual.items():
        require_result(result)
        for section in SECTIONS[name]:
            old=expected[section];body={k:v for k,v in old.items() if k!='content_hash'}
            require(sha(canonical(body))==old['content_hash'] and old['parent_result_hash']==result['content_hash'] and canonical(old['body'])==canonical(result['body'][section]),'SECTION_REPLAY_CHANGED')
    require(canonical(actual['candidate'])==canonical(expected['candidate']),'CANDIDATE_REPLAY_CHANGED');require_inputs(inputs)
    return {'immutable_files_verified':immutable,'artifacts_verified':len(expected),'deterministic':True,'source_admission':'BLOCKED','productionGate':False}

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False))
