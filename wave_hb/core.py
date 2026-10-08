"""Frozen A–F evidence-only delivery context; all actual transitions blocked."""
import json
from pathlib import Path
from .common import *
from wave_h.core import frozen_context as previous_context

NAMES=('Owner-Acceptance-Candidate.json','H-B-Preflight.json','Actual-Authority-Enrollment-Candidate.json',
       'Owner-Trading-Inputs.template.json','Historical-PIT-Blocker-Map.json','CostModel-v1.json')
def context():
    old=previous_context();b=baseline();release=json.loads(checked_file(ROOT/'docs/wave-hb/release.json'))
    require(release['version']=='1.0.0-hb-offline-preparation' and release['code_pins']==inventory() and
      release['actual_days']==0 and release['authenticated_requests']==0 and release['credentials_read']==False and
      release['productionGate']==False,'HB_RELEASE_DRIFT')
    refs={}
    def add(r):
        reopen(r);require(r['path'] not in refs or refs[r['path']]==r,'HB_REFERENCE_CONFLICT');refs[r['path']]=r
    for r in old['source_dependencies']:add(r)
    for r in b['tracked_files']:
        if r['path'].removeprefix('/Users/qiushi/投资研究/ashare-trading-v1/') not in b['allowed_navigation_updates']:add(r)
    for r in release['code_pins']:add(ref(ROOT/r['path']))
    for r in release['private_pins']:add(r)
    add(ref(ROOT/'docs/wave-hb/release.json'))
    return dict(context_hash=digest(sorted(refs.values(),key=lambda r:r['path'])),
      code_hash=code_hash(),source_dependencies=sorted(refs.values(),key=lambda r:r['path']),
      baseline_commit=b['baseline_commit'],immutable_predecessors=857,
      H_A_context_hash=old['context_hash'],H_A_code_hash=old['code_hash'])

def payloads():
    from .preflight import build_preflight
    from .authority import audit_public_roots
    from .owner_inputs import build_template
    from .pit_map import build_map
    c=context();a=json.loads(reopen(ref(ARCHIVE/'results/PREPARATION-G1/Owner-Acceptance-Candidate.json')))
    items={NAMES[0]:a,NAMES[1]:build_preflight(),NAMES[2]:audit_public_roots(),NAMES[3]:build_template(),
      NAMES[4]:build_map(),NAMES[5]:json.loads(checked_file(ROOT/'docs/wave-hb/CostModel-v1.json'))}
    out={}
    for name,body in items.items():
        out[name]=metadata('H_B_A_F_FROZEN_EVIDENCE',{'artifact_name':name,'payload':body,
          'context_hash':c['context_hash'],'code_hash':c['code_hash'],
          'actual_G':'HOLD_EXTERNAL_KEYS_CURRENT_FACTS_SIGNATURES','actual_snapshot_b':'NOT_YET_RUN',
          'mode':'OFFLINE_PREPARATION_ONLY','no_scheduler':True,'no_actual_credential_lookup':True})
    require(context()==c,'HB_CONTEXT_CHANGED_DURING_PROJECTION');return out

def actual_capture(*a,**k):raise ValueError('HB_PREPARATION_NO_ACTUAL_CAPTURE')
def forward_append(*a,**k):raise ValueError('HB_PREPARATION_NO_ACTUAL_APPEND')
def native_issue(*a,**k):raise ValueError('HB_NATIVE_ISSUANCE_FORBIDDEN')
def production(*a,**k):raise ValueError('HB_PRODUCTION_FORBIDDEN')
def export(*a,**k):raise ValueError('HB_CLOUD_EXPORT_FORBIDDEN')
