import {dataDb,createDataFixture} from '../p1a-data/helpers.mjs';
import {lineageClosure} from '../../../src/data/snapshot.mjs';
import {createFixtureAuthority,sealClosure,closureRef} from '../../../src/closure/contracts.mjs';
import {createAdmissionService} from '../../../src/closure/admission.mjs';

/** Explicit synthetic policy factory; none of these values is a production default. */
export async function createClosurePolicy({db,snapshot,authority,overrides={}}){
 const closure=await lineageClosure(db,snapshot.lineage_bundle.root_refs,snapshot.manifest.decision_cutoff),observations=closure.filter(o=>o.kind==='SOURCE_OBSERVATION'),groups=new Map();
 for(const o of observations){const key=o.source_id+'@'+o.source_version+'@'+o.source_hash;const binding=groups.get(key)??{source_id:o.source_id,source_version:o.source_version,source_hash:o.source_hash,source_class:'SYNTHETIC',license_type:'SYNTHETIC_TEST',terms_version:o.source_policy.terms_version,allowed_use:['SYNTHETIC_TEST'],raw_hashes:[]};binding.raw_hashes.push(o.raw_sha256);groups.set(key,binding);}
 const roots=snapshot.lineage_bundle.root_refs.map(r=>closure.find(o=>o.content_hash===r.content_hash)),dates=roots.map(o=>o.payload.trade_date).sort(),kinds=[...new Set(closure.map(o=>o.kind))].sort();
 const p={contract_name:'SourceAdmissionPolicy',contract_version:'1.0.0',object_id:'synthetic:closure-policy',object_version:1,fixture_scope:'SYNTHETIC_TEST_ONLY',purpose:'FIXTURE_MANUAL_EXPORT',mode:'PAPER',production_enabled:false,issuer:structuredClone(authority.issuer),source_bindings:[...groups.values()].map(b=>({...b,raw_hashes:[...new Set(b.raw_hashes)].sort()})),coverage:{symbols:[...new Set(roots.map(o=>o.canonical_symbol))].sort(),exchanges:[...new Set(roots.map(o=>o.canonical_symbol.split(':')[0]))].sort(),from_date:dates[0],to_date:dates.at(-1),object_kinds:kinds},freshness_seconds_by_kind:Object.fromEntries(kinds.map(k=>[k,30*86400])),valid_from:snapshot.manifest.frozen_at,valid_until:'2026-10-02T16:00:00+08:00',clock_basis:'SYNTHETIC_SOURCE_FIELD',allow_cloud_model_call:false,allow_real_data:false,allowed_projection:'FIXTURE_BAR_ENVELOPE_V1',version_chain_parent:null,...structuredClone(overrides)};
 return sealClosure(p);
}

export async function createClosureDataFixture({db,now='2026-09-30T16:00:00+08:00',strategy_id='RESEARCH_6_18M',dataOptions={},policyOverrides={}}={}){
 db??=await dataDb();const fixture=await createDataFixture(db,dataOptions),authority=createFixtureAuthority(),policy=await createClosurePolicy({db,snapshot:fixture.snapshot,authority,overrides:policyOverrides}),service=createAdmissionService({db,authority,approvedPolicyHashes:new Set([policy.content_hash])}),purpose='FIXTURE_MANUAL_EXPORT';
 await service.registerPolicy(policy);const receipt=await service.admit({snapshot:fixture.snapshot,policy_ref:closureRef(policy),strategy_id,purpose,now,expires_at:policy.valid_until});
 return {db,...fixture,authority,policy,service,receipt,now,purpose,strategy_id};
}
