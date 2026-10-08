import test from 'node:test';
import assert from 'node:assert/strict';
import config from '../config/semantics.v1.json' with {type:'json'};
import {assessSemantics} from '../src/semantics.mjs';
import {ingestDiscoveredEvidence} from '../src/evidence.mjs';
import {hash,refOf,validateP1B,seal} from '../src/contracts.mjs';

const scope='SYNTHETIC_SEMANTIC_TEST_ONLY';
const fixtureRef=id=>({object_id:id,object_version:1,content_hash:hash({fixture_id:id,scope})});
const evidence=fixtureRef('synthetic:semantics:admitted-local-example'),block=fixtureRef('synthetic:semantics:hard-block-example');
const input=(mutations={})=>({dimensions:Object.fromEntries(config.dimensions.map(k=>[k,'PASS'])),evidence_refs:[structuredClone(evidence)],hard_block_refs:[],research_card_ref:null,scope,...mutations});
const withDimensions=changes=>input({dimensions:{...input().dimensions,...changes}});

test('P1-B all-PASS illustrative template is S REQUEST_REVIEW, with real suitability/edge/sizing/probability blocked',()=>{
 const a=assessSemantics(input());validateP1B('ResearchAssessment',a);assert.equal(a.actionability_grade,'S');assert.equal(a.next_action,'REQUEST_REVIEW');assert.equal(a.research_grade,'HIGH');assert.equal(a.grade_meaning,'PROVISIONAL_ACTIONABILITY_TEMPLATE_NOT_RECOMMENDATION');
 assert.equal(a.real_account_suitability,'BLOCKED');for(const k of ['real_net_edge','real_sizing','probability_claim'])assert.equal(a[k],'UNSET_REQUIRED');for(const k of ['calibrated','can_produce_order','production_enabled'])assert.equal(a[k],false);
 assert.deepEqual(a,assessSemantics(input()));assert.ok(Object.isFrozen(a)&&Object.isFrozen(a.dimensions)&&Object.isFrozen(a.hard_block_refs));
});

test('P1-B ten independent dimensions preserve HIGH quality with unmet timing/cost/account/tradeability as A WATCH',()=>{
 for(const key of ['timing','cost','account_suitability','tradeability'])for(const state of ['GAP','UNSET_REQUIRED','NOT_APPLICABLE']){
  const a=assessSemantics(withDimensions({[key]:state}));assert.equal(a.research_grade,'HIGH');assert.equal(a.actionability_grade,'A');assert.equal(a.next_action,'WATCH');assert.equal(a.dimensions[key],state);assert.equal(a.dimensions.company_quality,'PASS');assert.equal(a.real_account_suitability,'BLOCKED');
 }
 const timing=assessSemantics(withDimensions({timing:'GAP'}));assert.ok(timing.reasons.includes('P1B_TIMING_UNSATISFIED'));assert.equal(timing.dimensions.cost,'PASS');
});

test('P1-B unknown or NOT_APPLICABLE in every dimension fails S, and required unknowns remain explicit',()=>{
 for(const key of config.dimensions)for(const state of ['UNSET_REQUIRED','NOT_APPLICABLE'])assert.notEqual(assessSemantics(withDimensions({[key]:state})).actionability_grade,'S');
 for(const key of ['company_quality','evidence_quality','risk']){const a=assessSemantics(withDimensions({[key]:'UNSET_REQUIRED'}));assert.equal(a.research_grade,'UNSET_REQUIRED');assert.equal(a.actionability_grade,'UNSET_REQUIRED');assert.equal(a.next_action,'UNKNOWN');}
 const noEvidence=assessSemantics(input({evidence_refs:[]}));assert.equal(noEvidence.actionability_grade,'UNSET_REQUIRED');assert.ok(noEvidence.reasons.includes('P1B_SOURCE_UNAPPROVED'));
});

test('P1-B Hard Block has precedence, B logic gaps differ from C observe-only and A cannot override X',()=>{
 const x=assessSemantics(input({hard_block_refs:[block]}));assert.equal(x.research_grade,'HIGH');assert.equal(x.actionability_grade,'X');assert.equal(x.next_action,'BLOCKED');assert.ok(x.reasons.includes('P1B_HARD_BLOCK'));
 assert.equal(assessSemantics({...withDimensions({timing:'GAP'}),hard_block_refs:[block]}).actionability_grade,'X');assert.equal(assessSemantics(withDimensions({risk:'GAP'})).actionability_grade,'X');
 const b=assessSemantics(withDimensions({sector_quality:'GAP',valuation:'GAP'}));assert.equal(b.research_grade,'MIXED');assert.equal(b.actionability_grade,'B');assert.equal(b.next_action,'NO_ACTIVE_TRADE');
 const c=assessSemantics(withDimensions({company_quality:'GAP',sector_quality:'GAP',catalyst:'NOT_APPLICABLE',valuation:'GAP',timing:'GAP',cost:'UNSET_REQUIRED',account_suitability:'UNSET_REQUIRED',tradeability:'UNSET_REQUIRED'}));assert.equal(c.research_grade,'OBSERVE_ONLY');assert.equal(c.actionability_grade,'C');assert.equal(c.next_action,'RESEARCH_ONLY');
});

test('P1-B semantic scope rejects real stock/account/grade/probability claims and numerical threshold inputs',()=>{
 for(const s of ['REAL_RESEARCH','OBSERVED','PROD','SYNTHETIC','CORE_40'])assert.throws(()=>assessSemantics(input({scope:s})),/P1B_SEMANTICS_SCOPE/);
 for(const extra of [{productionGate:true},{real_account_suitability:'REAL_ACCOUNT_SUITABLE'},{probability:'0.85'},{scores:{quality:85}},{grade:'S'},{strategy_id:'EVENT_3'}])assert.throws(()=>assessSemantics({...input(),...extra}),/P1B_ARBITRARY_PAYLOAD/);
 for(const value of [85,'85','80','78','APPROVE',true,{},null])assert.throws(()=>assessSemantics(withDimensions({company_quality:value})),/P1B_ARBITRARY_PAYLOAD/);
 const missing=input();delete missing.dimensions.timing;assert.throws(()=>assessSemantics(missing),/P1B_ARBITRARY_PAYLOAD/);assert.throws(()=>assessSemantics(input({dimensions:{...input().dimensions,net_edge:'PASS'}})),/P1B_ARBITRARY_PAYLOAD/);
 assert.throws(()=>assessSemantics(input({research_card_ref:{object_id:'synthetic-ResearchCard',object_version:1,content_hash:hash('caller card')}})),/P1B_SEMANTICS_SCOPE/);
 assert.equal(config.thresholds.calibrated,false);assert.equal(config.thresholds.probability_interpretation_allowed,false);assert.equal(config.thresholds.mapping_to_grades,'UNSET_REQUIRED');
});

test('P1-B cloud citation/object/ref/caller trust claims cannot set/clear Hard Block or upgrade grade',()=>{
 const cloud=ingestDiscoveredEvidence({original_uri:'https://example.test/public/lead',lead:'Synthetic cloud claim: local review may find a risk.',discovered_at:'2026-10-05T12:00:00+08:00',origin:'LLM'});
 const attacks=[cloud,refOf(cloud),{...evidence,trust_class:'ADMITTED_LOCAL_EVIDENCE'},'https://example.test/citation',{...evidence,object_version:2},{...evidence,content_hash:hash('caller assertion')},seal({...cloud,object_id:evidence.object_id}),{...block,content_hash:evidence.content_hash}];
 for(const ref of attacks){assert.throws(()=>assessSemantics(input({evidence_refs:[ref]})),/P1B_CLOUD_EVIDENCE_UNTRUSTED/);assert.throws(()=>assessSemantics(input({hard_block_refs:[ref]})),/P1B_CLOUD_EVIDENCE_UNTRUSTED/);}
 assert.throws(()=>assessSemantics(input({evidence_refs:[evidence,evidence]})),/P1B_CLOUD_EVIDENCE_UNTRUSTED/);
 assert.throws(()=>assessSemantics({...input({hard_block_refs:[block]}),clear_hard_block_from_cloud:cloud}),/P1B_ARBITRARY_PAYLOAD/);
});

test('P1-B semantic A-to-S and A-to-X transitions depend on changed checks, never company quality alone',()=>{
 const aInput=withDimensions({timing:'GAP',tradeability:'GAP'}),a=assessSemantics(aInput);assert.equal(a.actionability_grade,'A');
 assert.equal(assessSemantics({...aInput,dimensions:{...aInput.dimensions,timing:'PASS'}}).actionability_grade,'A');
 const s=assessSemantics(input());assert.equal(s.actionability_grade,'S');assert.equal(s.next_action,'REQUEST_REVIEW');assert.notEqual(a.content_hash,s.content_hash);assert.equal(s.can_produce_order,false);
 const x=assessSemantics({...aInput,hard_block_refs:[block]});assert.equal(x.actionability_grade,'X');assert.notEqual(a.content_hash,x.content_hash);assert.equal(x.production_enabled,false);
});
