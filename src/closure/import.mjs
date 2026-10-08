import {canonical,hashValue,requireThat,validateContract} from '../contracts/validate.mjs';
import {estimateCost} from '../cost/index.mjs';
import {assertSanitized,closureRef,sealClosure,validateClosure} from './contracts.mjs';

const exactKeys=(value,keys)=>value&&Object.getPrototypeOf(value)===Object.prototype&&canonical(Object.keys(value).sort())===canonical([...keys].sort());
const validRef=r=>exactKeys(r,['object_id','object_version','content_hash'])&&typeof r.object_id==='string'&&Number.isSafeInteger(r.object_version)&&r.object_version>0&&/^sha256:[a-f0-9]{64}$/.test(r.content_hash);
const injection=/\b(?:BUY|SELL|APPROVE|APPROVED|HUMAN_USER|OrderIntent|Approval|REAL_ACCOUNT_SUITABLE|REAL_NET_EDGE|REAL_SIZING|TRADEABLE|broker|productionGate)\b/i;
const outcome=/\b(?:MAE|MFE|future[_ -]?return|future[_ -]?outcome|daily[_ -]?nav|outcome)\b/i;

function validateResult(result,packet){
 requireThat(exactKeys(result,['packet_ref','receipt_ref','strategy_id','purpose','observations']),'CLOSURE_IMPORT_INVALID');
 requireThat(validRef(result.packet_ref)&&canonical(result.packet_ref)===canonical(closureRef(packet))&&validRef(result.receipt_ref)&&canonical(result.receipt_ref)===canonical(closureRef(packet.receipt)),'CLOSURE_RECEIPT_INVALIDATED');
 requireThat(result.strategy_id===packet.strategy_id,'CLOSURE_NAMESPACE_MISMATCH');
 requireThat(result.purpose===packet.purpose,'CLOSURE_PURPOSE_MISMATCH');
 assertSanitized(result);
 requireThat(!injection.test(JSON.stringify(result)),'CLOSURE_LLM_EXECUTION_INJECTION');
 requireThat(!outcome.test(JSON.stringify(result)),'CLOSURE_OUTCOME_LEAKAGE');
 requireThat(Array.isArray(result.observations)&&result.observations.length>0&&result.observations.length<=100,'CLOSURE_IMPORT_INVALID');
 const admitted=new Set(packet.evidence.map(e=>canonical(closureRef(e))));
 for(const o of result.observations){
  requireThat(exactKeys(o,['evidence_ref','statement','classification'])&&validRef(o.evidence_ref)&&admitted.has(canonical(o.evidence_ref))&&typeof o.statement==='string'&&o.statement.length>0&&o.statement.length<=2000&&o.classification==='DESCRIPTIVE_ONLY','CLOSURE_IMPORT_INVALID');
 }
 requireThat(new Set(result.observations.map(canonical)).size===result.observations.length,'CLOSURE_IMPORT_INVALID');
 return structuredClone(result.observations);
}

// This trusted parent boundary invokes the actual synthetic Cost Engine. No DB,
// approval writer, execution gateway or broker transport is accepted or created.
export async function importResearchResult({service,packet,snapshot,result,realAccountProfile,costProfile,tradeTerms,now}){
 // Own JSON copies before the first async boundary; caller mutations cannot swap
 // the packet/result/cost terms after the trusted facade verifies them.
 packet=structuredClone(packet);snapshot=structuredClone(snapshot);result=structuredClone(result);costProfile=structuredClone(costProfile);tradeTerms=structuredClone(tradeTerms);
 let verified=false;
 const chain_id='closure-import:'+packet?.content_hash?.slice(7);
 try{
  await service.verifyPacket({packet,snapshot,purpose:'FIXTURE_MANUAL_EXPORT',strategy_id:packet.strategy_id,now});verified=true;
  const observations=validateResult(result,packet);
  requireThat(costProfile&&costProfile.profile_scope==='SYNTHETIC_TEST_ONLY','CLOSURE_COST_REQUIRED_FIRST');
  assertSanitized(costProfile);
  requireThat(exactKeys(tradeTerms,['side','price','quantity','trade_date']),'CLOSURE_COST_REQUIRED_FIRST');
  const cost_estimate=estimateCost({mode:'PAPER',profile:costProfile,...tradeTerms});
  const phase_order=['COST_ESTIMATED'];
  await service.audit({chain_id,event_type:'IMPORT_COST_ESTIMATED',event_time:now,refs:[closureRef(packet),closureRef(packet.receipt)],reason_codes:[]});
  // Validation is after cost, and even a caller's populated/VERIFIED real profile
  // cannot widen a fixture admission into a real suitability conclusion.
  if(realAccountProfile)validateContract('AccountProfile',JSON.parse(canonical(realAccountProfile)));
  phase_order.push('SUITABILITY_EVALUATED');
  const draft=sealClosure({contract_name:'ResearchDraft',contract_version:'1.0.0',object_id:'draft:'+hashValue({packet:closureRef(packet),observations,cost_estimate}).slice(7),object_version:1,fixture_scope:'SYNTHETIC_TEST_ONLY',purpose:'FIXTURE_MANUAL_EXPORT',mode:'PAPER',production_enabled:false,strategy_id:packet.strategy_id,packet_ref:closureRef(packet),receipt_ref:closureRef(packet.receipt),snapshot_ref:packet.snapshot_ref,decision_cutoff:packet.decision_cutoff,observations,can_produce_order:false,tradeable:false,grade:'UNSET_REQUIRED',scoring_policy_version:'UNSET_REQUIRED',probability_policy_version:'UNSET_REQUIRED',sizing_policy_version:'UNSET_REQUIRED',edge_policy_version:'UNSET_REQUIRED',real_account_suitability:'BLOCKED',real_net_edge:'UNSET_REQUIRED',real_sizing:'UNSET_REQUIRED',cost_test:{scope:'SYNTHETIC_TEST_ONLY',cost_profile_ref:cost_estimate.cost_profile_ref,estimate_hash:hashValue(cost_estimate),cost_before_suitability:true},reason_codes:['CLOSURE_UNKNOWN_REAL_COST_ACCOUNT','CLOSURE_DRAFT_NON_EXECUTABLE','CLOSURE_PRODUCTION_DISABLED'],validation_status:'NON_TRADEABLE'});
  validateClosure('ResearchDraft',draft);assertSanitized(draft);
  // The receipt is live at the final acceptance boundary too.
  await service.verifyPacket({packet,snapshot,purpose:'FIXTURE_MANUAL_EXPORT',strategy_id:packet.strategy_id,now});
  await service.audit({chain_id,event_type:'IMPORT_ACCEPTED',event_time:now,refs:[closureRef(packet),closureRef(draft)],reason_codes:draft.reason_codes});
  return {draft,cost_estimate,phase_order};
 }catch(error){
  if(verified)await service.audit({chain_id,event_type:'IMPORT_REJECTED',event_time:now,refs:[closureRef(packet)],reason_codes:[error.code?.startsWith('CLOSURE_')?error.code:'CLOSURE_IMPORT_INVALID']}).catch(()=>{});
  throw error;
 }
}

export function assertDraftTransition(draft,targetKind){
 validateClosure('ResearchDraft',draft);
 requireThat(!['CandidateTradeable','CandidateEligibility','Signal','SignalEvent','Approval','OrderIntent','Order','Fill'].includes(targetKind),'CLOSURE_DRAFT_NON_EXECUTABLE');
 requireThat(targetKind==='ResearchDraft','CLOSURE_DRAFT_NON_EXECUTABLE');
 return draft;
}
