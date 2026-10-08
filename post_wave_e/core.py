"""Closed preparation factory; every adopted private original is rechecked."""
from pathlib import Path
from copy import deepcopy
import json
from .common import *
ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=Path('/Users/qiushi/投资研究/.p1b-archives/post-wave-e-20261006')
NAMES=('HistoricalPITGap','TradeabilityHistoryReadiness','FinancialRevisionReadiness','ActionAdjustmentReconciliation','FrozenStrategySpec','ForwardPaperRealAdapterReadiness','SnapshotBPreparation','ProviderLicenseTransportGap')
FILES=dict(zip(NAMES,('Historical-PIT-Gap.json','Tradeability-History-Readiness.json','Financial-Revision-Readiness.json','Action-Adjustment-Reconciliation.json','Frozen-StrategySpec.json','Forward-Paper-Real-Adapter-Readiness.json','Snapshot-B-Preflight.json','Provider-License-Transport-Gap.json')))
REASONS=['NO_HISTORICAL_PIT','UNKNOWN_STATUS','UNSET_REQUIRED','NO_EXECUTION_AUTHORITY','SOURCE_QUARANTINED','LICENSE_UNVERIFIED','SEPARATE_HUMAN_OWNER_AUTHORIZATION_REQUIRED','PREPARATION_ONLY','NOT_STRATEGY_EVIDENCE']
_REGISTRY={}
FROZEN_PATHS=('contracts/post-wave-e/ActionAdjustmentReconciliation.schema.json', 'contracts/post-wave-e/FinancialRevisionReadiness.schema.json', 'contracts/post-wave-e/ForwardPaperRealAdapterReadiness.schema.json', 'contracts/post-wave-e/FrozenStrategySpec.schema.json', 'contracts/post-wave-e/HistoricalPITGap.schema.json', 'contracts/post-wave-e/ProviderLicenseTransportGap.schema.json', 'contracts/post-wave-e/SnapshotBPreparation.schema.json', 'contracts/post-wave-e/TradeabilityHistoryReadiness.schema.json', 'docs/adr/ADR-029-historical-pit-preparation.md', 'docs/adr/ADR-030-strategy-evaluation-freeze.md', 'docs/adr/ADR-031-durable-forward-and-provider-boundary.md', 'docs/authorizations/P1B-POST-WAVE-E-20261006.md', 'docs/post-wave-e/Interface-Freeze.md', 'docs/post-wave-e/Snapshot-B-Runbook.md', 'docs/post-wave-e/adopted-private-pins.json', 'docs/post-wave-e/baseline-acceptance.json', 'docs/post-wave-e/baseline-pins.json', 'docs/post-wave-e/contract-matrix.json', 'docs/post-wave-e/observation-original-map.json', 'docs/post-wave-e/rules.json', 'post_wave_e/__init__.py', 'post_wave_e/action.py', 'post_wave_e/check.mjs', 'post_wave_e/common.py', 'post_wave_e/contracts.mjs', 'post_wave_e/core.py', 'post_wave_e/forward.py', 'post_wave_e/pit.py', 'post_wave_e/preflight.py', 'post_wave_e/provider.py', 'post_wave_e/real_adapter.py', 'post_wave_e/run.py', 'post_wave_e/strategy.py', 'post_wave_e/tests/boundaries.test.mjs', 'post_wave_e/tests/test_boundaries.py', 'post_wave_e/tests/test_forward.py', 'post_wave_e/tests/test_pit.py')
def private_ref(r):
    keys(r,('path','sha256','bytes'))
    p=Path(r['path']);require(p.is_relative_to(ARCHIVE.parent) and p.stat().st_mode&0o777==0o600,'PREP_PRIVATE_PATH_INVALID')
    b=checked_file(p,r['sha256']);require(type(r['bytes']) is int and len(b)==r['bytes'],'PREP_REF_SIZE');return b
def dependency_key(p):
    if p.is_relative_to(ROOT):return 'GIT:'+p.relative_to(ROOT).as_posix()
    require(p.is_relative_to(ARCHIVE.parent),'PREP_DEPENDENCY_ROOT');return 'FIXED_PRIVATE_ARCHIVE:'+p.relative_to(ARCHIVE.parent).as_posix()
def frozen_context():
    from wave_e.core import frozen_context as previous
    old=previous();pins=list(old['pins'])
    bp=ROOT/'docs/post-wave-e/baseline-pins.json';bb=checked_file(bp);base=json.loads(bb)
    require(base['baseline_commit']=='9f975258b0c8f88770eebacd841573e492bdbc48' and len(base['tracked_files'])==666 and base['immutable_count']==663 and base['allowed_navigation_updates']==['AGENTS.md','README.md','docs/source-of-truth.json'],'PREP_BASELINE_INVALID')
    cp=private_ref(base['checkpoint_ref']);require(json.loads(cp)['tracked_files']==base['tracked_files'],'PREP_START_UNBOUND')
    pins.extend((ROOT/r['path'],r['sha256']) for r in base['tracked_files'] if r['path'] not in base['allowed_navigation_updates'])
    ap=ROOT/'docs/post-wave-e/baseline-acceptance.json';ab=checked_file(ap);accept=json.loads(ab);prior=private_ref(accept['previous_delivery_checkpoint']);q=json.loads(prior)
    require(q['final_head']==base['baseline_commit'] and q['productionGate'] is False and q['actual_forward_days']==0,'PREP_PRIOR_DELIVERY_INVALID')
    require(accept['current_human_decision']=={'Wave_D':'ACCEPTED_WITH_CONDITIONS','Wave_E':'ACCEPTED_WITH_CONDITIONS'} and accept['historical_gate_bytes_unchanged'] is True,'PREP_OWNER_ACCEPTANCE_INVALID')
    rawp=ROOT/'docs/post-wave-e/adopted-private-pins.json';rawb=checked_file(rawp);adopt=json.loads(rawb)
    require(len(adopt['pins'])==293,'PREP_ADOPTED_SOURCE_SCOPE')
    for r in adopt['pins']:private_ref(r);pins.append((Path(r['path']),r['sha256']))
    mapping=json.loads(checked_file(ROOT/'docs/post-wave-e/observation-original-map.json'))
    require(mapping['authority']=='RAW_INTEGRITY_ONLY_NOT_CLOCK_LICENSE_ADMISSION' and mapping['historical_visibility_proven'] is False and mapping['productionGate'] is False,'PREP_ORIGINAL_MAP_AUTHORITY')
    fields=('api_name','origin','scope','request_id','request_fingerprint','raw_sha256','retrieved_at')
    expected={canonical({'api_name':o['api_name'],**{k:o['source_ref'][k] for k in fields[1:]}}) for x in old['inputs'] for o in x['body']['observations']}
    mapped=set();adopted={r['path']:r for r in adopt['pins']}
    for q in mapping['observation_originals']:
        keys(q,fields+('original_refs',));key=canonical({k:q[k] for k in fields});require(key not in mapped,'PREP_ORIGINAL_IDENTITY_DUPLICATE');mapped.add(key)
        require(type(q['original_refs']) is list and q['original_refs'],'PREP_ORIGINAL_PATH_MISSING')
        for r in q['original_refs']:
            require(r['sha256']==q['raw_sha256'] and adopted.get(r['path'])==r,'PREP_ORIGINAL_RAW_UNBOUND');private_ref(r)
    require(mapped==expected and len(mapped)==94,'PREP_ORIGINAL_COVERAGE_INCOMPLETE')
    rp=ROOT/'docs/post-wave-e/release.json';rb=checked_file(rp);release=json.loads(rb)
    require(release['version']=='1.0.1-post-wave-e-preparation' and release['productionGate'] is False and release['formal_source_admission']=='BLOCKED','PREP_RELEASE_PROMOTION')
    require(tuple(r['path'] for r in release['code_pins'])==FROZEN_PATHS,'PREP_RELEASE_INVENTORY_INVALID')
    pins.extend((ROOT/r['path'],r['sha256']) for r in release['code_pins'])
    rulep=ROOT/'docs/post-wave-e/rules.json';ruleb=checked_file(rulep);rules=json.loads(ruleb)
    require(rules['symbols']==list(SYMBOLS) and rules['namespace']=='LOCAL_PREPARATION_ONLY:CORE_40' and rules['labels']==['LOCAL_ONLY','NON_TRADEABLE','NOT_STRATEGY_EVIDENCE','NO_HISTORICAL_PIT','PREPARATION_ONLY'] and rules['actual_account_parameters']=='30_UNSET_REQUIRED','PREP_RULE_SCOPE')
    require(all(rules[k] is False for k in ('historical_visibility_proven','productionGate','strategy_optimization','actual_snapshot_b_authorized','actual_forward_authorized','schedule_authorized','live_authority')) and all(rules[k]==0 and type(rules[k]) is int for k in ('actual_forward_days','authenticated_requests','credential_lookups','new_public_requests')) and rules['formal_source_admission']=='BLOCKED','PREP_RULE_PROMOTION')
    pins.extend([(bp,sha(bb)),(ap,sha(ab)),(rawp,sha(rawb)),(rp,sha(rb)),(rulep,sha(ruleb)),(Path(base['checkpoint_ref']['path']),sha(cp)),(Path(accept['previous_delivery_checkpoint']['path']),sha(prior))])
    uniq={dependency_key(p):(p,h) for p,h in pins}
    for p,h in uniq.values():checked_file(p,h)
    return {'rules':rules,'rules_hash':sha(ruleb),'code_hash':digest(release['code_pins']),'schema_hash':digest([r for r in release['code_pins'] if r['path'].startswith('contracts/post-wave-e/')]),'predecessor_hash':sha(prior),'source_identity':digest([[k,h] for k,(p,h) in sorted(uniq.items())]),'pins':list(uniq.values()),'inputs':old['inputs'],'retrieval_cutoff':old['retrieval_cutoff']}
def context_hash(c):return digest({k:v for k,v in c.items() if k not in ('pins','inputs')}|{'pins':[[dependency_key(p),h] for p,h in c['pins']]})
def historical_gap():
    from wave_e.research import PRICE_DOMAINS,FUNDAMENTAL_DOMAINS
    domains=list(PRICE_DOMAINS+FUNDAMENTAL_DOMAINS)+['listing_delisting_history','revision_first_visibility','historical_universe_completeness','dated_fee_rounding_units','owner_risk_kill_policy','benchmark_total_return_policy','evaluation_oos_freeze','announcement_body_identity','snapshot_b_fresh_session','independent_entitlement_per_api']
    return {'state':'BLOCKED','engine_diagnostic_ready':'READY','formal_price_backtest':'BLOCKED','formal_fundamental_pit_backtest':'BLOCKED','historical_visibility_proven':False,'domains':[{'domain':d,'state':'BLOCKED','required_evidence':'INDEPENDENT_VERSIONED_SOURCE_CLOCK_POLICY_EVIDENCE','absence_means':'UNKNOWN','auto_close_from_interface_tests':False} for d in domains],'price_domains':list(PRICE_DOMAINS),'fundamental_additional_domains':list(FUNDAMENTAL_DOMAINS),'closed_c12_c22':0,'actual_account_unset_count':30,'observed_at_time_requires':'AVAILABLE_AND_RETRIEVED_LE_CUTOFF','reconstruction_requires':'INDEPENDENT_HISTORICAL_AVAILABLE_AT_PROOF_NOT_OBSERVED_THEN','date_only_publication':'UNKNOWN_NO_MIDNIGHT_IMPUTATION','live_authority':False}
def bodies(ctx):
    from .pit import financial_readiness,tradeability_readiness
    from .action import actual_readiness
    from .strategy import frozen_spec
    from .forward import readiness
    from .preflight import readiness as snapshot
    from .provider import gap_matrix
    from .real_adapter import _project
    p=ARCHIVE.parent/'wave-e-20261006/results/DIAGNOSTIC-G1/action-adjustment-sensitivity.json'
    b=checked_file(p);require(any(q==p and h==sha(b) for q,h in ctx['pins']),'PREP_ACTION_UNPINNED')
    forward=readiness();forward['actual_source_projection']=_project(ctx)
    return dict(zip(NAMES,(historical_gap(),tradeability_readiness(ctx['inputs']),financial_readiness(ctx['inputs']),actual_readiness(json.loads(b)),frozen_spec(),forward,snapshot(),gap_matrix())))
def register(*a,**k):blocked('PREP_DIRECT_ISSUE_FORBIDDEN')
def derive(*a,**k):blocked('PREP_DIRECT_ISSUE_FORBIDDEN')
def objects():
    c=frozen_context();out=[]
    for name,body in bodies(c).items():
        h={'contract_name':name,'contract_version':VERSION,'object_version':1,'object_id':'post-e:'+name+':'+c['source_identity'][7:23],'trace_id':'post-e:'+c['source_identity'][7:],'namespace':c['rules']['namespace'],'symbols':list(SYMBOLS),'labels':c['rules']['labels'],'decision_cutoff':c['rules']['decision_cutoff'],'retrieval_cutoff':c['retrieval_cutoff'],'timezone':'Asia/Shanghai','source_identity':c['source_identity'],'rules_hash':c['rules_hash'],'code_hash':c['code_hash'],'schema_hash':c['schema_hash'],'predecessor_hash':c['predecessor_hash'],'formal_source_admission':'BLOCKED','actual_forward_days':0,'reason_codes':REASONS,'invalidation_conditions':['ADOPTED_RAW_SOURCE_CHANGED','PREDECESSOR_BYTES_CHANGED','RULE_CODE_SCHEMA_CHANGED','CUTOFF_NAMESPACE_CHANGED','PRIVATE_PATH_SUBSTITUTION','CALLER_COPY_RESEAL','AUTHORITY_PROMOTION'],'body':body}
        h.update({k:False for k in ('provider_identity_verified','license_verified','transport_integrity_verified','historical_visibility_proven','cloud_transfer','live_authority','tradeable','production_eligible','can_produce_order','productionGate')})
        v=seal(h);_REGISTRY[id(v)]={'value':v,'hash':digest(v),'context':context_hash(c)};out.append(v)
    return out
def assert_registered(v):
    r=_REGISTRY.get(id(v));require(r is not None and r['value'] is v and r['hash']==digest(v),'PREP_UNREGISTERED_OR_MUTATED')
    require(r['context']==context_hash(frozen_context()),'PREP_CONTEXT_INVALIDATED');return True
def transition(v,target):
    assert_registered(v);require(target=='LOCAL_PREPARATION_DISPLAY','PREP_NATIVE_PROMOTION_FORBIDDEN');return deepcopy(v)
def production_execute(*a,**k):blocked('PREP_PRODUCTION_NOT_AUTHORIZED')
