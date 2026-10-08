import config from '../config/semantics.v1.json' with {type:'json'};
import {hash,seal,validateP1B,assertPublicPayload} from './contracts.mjs';

function ensure(ok,code){if(!ok)throw new Error(code);}
const sameKeys=(o,keys)=>o&&Object.getPrototypeOf(o)===Object.prototype&&JSON.stringify(Object.keys(o).sort())===JSON.stringify([...keys].sort());
const SCOPE='SYNTHETIC_SEMANTIC_TEST_ONLY';
const EVIDENCE_ID='synthetic:semantics:admitted-local-example',BLOCK_ID='synthetic:semantics:hard-block-example';
const statuses=['PASS','GAP','UNSET_REQUIRED','NOT_APPLICABLE'];
const researchAxes=['company_quality','sector_quality','evidence_quality','valuation','risk'];
const entryAxes=['timing','cost','account_suitability','tradeability'];
const mandatoryAxes=['company_quality','evidence_quality','risk'];
function fixtureRefs(refs,id){
 ensure(Array.isArray(refs)&&refs.length<=1,'P1B_CLOUD_EVIDENCE_UNTRUSTED');
 for(const r of refs)ensure(sameKeys(r,['object_id','object_version','content_hash'])&&r.object_id===id&&r.object_version===1&&r.content_hash===hash({fixture_id:id,scope:SCOPE}),'P1B_CLOUD_EVIDENCE_UNTRUSTED');
 return structuredClone(refs);
}

// These exact illustrative refs are semantic test coordinates, NOT verification
// of real evidence. No caller cloud object, citation, numeric score or self-reported
// trust assertion can reach this pure template API.
export function assessSemantics(input){
 ensure(sameKeys(input,['dimensions','evidence_refs','hard_block_refs','research_card_ref','scope']),'P1B_ARBITRARY_PAYLOAD');
 ensure(input.scope===SCOPE,'P1B_SEMANTICS_SCOPE');
 ensure(sameKeys(input.dimensions,config.dimensions)&&Object.values(input.dimensions).every(x=>statuses.includes(x)),'P1B_ARBITRARY_PAYLOAD');
 const evidence_refs=fixtureRefs(input.evidence_refs,EVIDENCE_ID),hard_block_refs=fixtureRefs(input.hard_block_refs,BLOCK_ID),dimensions=structuredClone(input.dimensions);
 ensure(input.research_card_ref===null,'P1B_SEMANTICS_SCOPE');
 assertPublicPayload(input);
 const unproven=mandatoryAxes.some(k=>['UNSET_REQUIRED','NOT_APPLICABLE'].includes(dimensions[k]))||evidence_refs.length===0;
 const high=researchAxes.every(k=>dimensions[k]==='PASS')&&!unproven;
 const logic=dimensions.company_quality==='PASS'||dimensions.catalyst==='PASS';
 const research_grade=unproven?'UNSET_REQUIRED':high?'HIGH':logic?'MIXED':'OBSERVE_ONLY';
 let actionability_grade,next_action;
 // Hard blocks have precedence over all quality/timing claims. A missing check
 // can never satisfy the S template, including a caller's NOT_APPLICABLE claim.
 if(hard_block_refs.length||dimensions.risk==='GAP'){actionability_grade='X';next_action='BLOCKED';}
 else if(unproven){actionability_grade='UNSET_REQUIRED';next_action='UNKNOWN';}
 else if(config.dimensions.every(k=>dimensions[k]==='PASS')){actionability_grade='S';next_action='REQUEST_REVIEW';}
 else if(high&&entryAxes.some(k=>dimensions[k]!=='PASS')){actionability_grade='A';next_action='WATCH';}
 else if(logic){actionability_grade='B';next_action='NO_ACTIVE_TRADE';}
 else{actionability_grade='C';next_action='RESEARCH_ONLY';}
 const reasons=['P1B_GRADE_UNCALIBRATED','P1B_EDGE_UNSET','P1B_UNKNOWN_REAL_ACCOUNT','P1B_NON_EXECUTABLE','P1B_REAL_STOCK_PILOT_BLOCKED'];
 if(actionability_grade==='X')reasons.push('P1B_HARD_BLOCK');
 if(dimensions.timing!=='PASS')reasons.push('P1B_TIMING_UNSATISFIED');
 if(evidence_refs.length===0)reasons.push('P1B_SOURCE_UNAPPROVED');
 const inputHash=hash({dimensions,evidence_refs,hard_block_refs,research_card_ref:null,scope:SCOPE});
 const assessment=seal({contract_name:'ResearchAssessment',contract_version:'1.0.0',object_id:'semantic-assessment:'+inputHash.slice(7),object_version:1,trace_id:'semantics:'+inputHash.slice(7),scope:SCOPE,strategy_id:'CORE_40',dimensions,research_grade,actionability_grade,grade_meaning:'PROVISIONAL_ACTIONABILITY_TEMPLATE_NOT_RECOMMENDATION',next_action,reasons,hard_block_refs,research_card_ref:null,real_account_suitability:'BLOCKED',real_net_edge:'UNSET_REQUIRED',real_sizing:'UNSET_REQUIRED',calibrated:false,probability_claim:'UNSET_REQUIRED',can_produce_order:false,production_enabled:false});
 validateP1B('ResearchAssessment',assessment);Object.freeze(assessment.dimensions);Object.freeze(assessment.reasons);assessment.hard_block_refs.forEach(Object.freeze);Object.freeze(assessment.hard_block_refs);
 return Object.freeze(assessment);
}
