"""Zero-argument registered replay and immutable, Git-external diagnostic output."""
import json
from .evidence_root import ARCHIVE
from .core import load_inputs,require_inputs,require_result
from .primitives import ROOT,VERSION,canonical,sha,require
from .probe import private_write
from . import status,action,financial,industry,candidate

DEST=ARCHIVE/'results'/'CANDIDATE-G4'
SECTIONS={
 'status':{'c12_technical_coverage':'C12-technical-coverage.json','security_status_timeline':'security-status-timeline.json','status_known_gaps':'status-known-gaps.json'},
 'action':{'factor_action_reconciliation':'factor-action-reconciliation.json','ambiguous_action_cases':'ambiguous-action-cases.json','adjustment_known_gaps':'adjustment-known-gaps.json'},
 'financial':{'financial_revision_candidate':'financial-revision-candidate.json','financial_range_semantics':'financial-range-semantics.json','financial_known_gaps':'financial-known-gaps.json'},
 'industry':{'industry_membership_candidate':'industry-membership-candidate.json','industry_pit_known_gaps':'industry-pit-known-gaps.json'},
 'candidate':{'coverage_matrix_v2':'coverage-matrix-v2.json','api_access_matrix':'actual-access-matrix.json','conditions_delta':'C12-C22-delta.json'}}

def replay(inputs):
    return {name:module.analyze(inputs) for name,module in
        [('status',status),('action',action),('financial',financial),('industry',industry),('candidate',candidate)]}

def produce():
    inputs=load_inputs();first=replay(inputs);second=replay(inputs)
    for name in first:
        require_result(first[name]);require_result(second[name]);require(canonical(first[name])==canonical(second[name]),'REPLAY_CHANGED')
    refs=[]
    def save(name,value,kind):
        raw=canonical(value)+b'\n';p=DEST/name;private_write(p,raw)
        refs.append({'object':kind,'path':str(p),'sha256':sha(raw),'bytes':len(raw)})
    save('verified-typed-inputs.json',inputs,'typed_inputs')
    for component,result in first.items():
        for section,filename in SECTIONS[component].items():
            body={k:v for k,v in result.items() if k not in {'body','content_hash'}}
            body.update({'kind':section.upper(),'parent_result_hash':result['content_hash'],'body':result['body'][section]})
            body['content_hash']=sha(canonical(body));save(filename,body,section)
    save('admission-candidate-matrix.json',first['candidate'],'candidate')
    proof={'version':VERSION,'fixture':False,'source_admission':'BLOCKED','historical_visibility_proven':False,
        'productionGate':False,'input_identity':inputs['source_identity'],'component_hashes':{k:v['content_hash'] for k,v in first.items()},
        'replays':2,'same_frozen_inputs_rules_and_code':True,'deterministic':True,'real_outputs_issued':0}
    save('deterministic-replay.json',proof,'replay_proof');require_inputs(inputs)
    manifest={'version':VERSION,'source_admission':'BLOCKED','productionGate':False,'artifacts':refs}
    private_write(DEST/'artifact-manifest.json',canonical(manifest)+b'\n')
    (ROOT/'docs/wave-b/evidence.json').write_bytes(canonical(manifest)+b'\n')
    print(json.dumps({'artifacts':len(refs),'replay_equal':True,'source_admission':'BLOCKED','productionGate':False}))

if __name__=='__main__':produce()
