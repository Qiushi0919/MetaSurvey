// Formal producer skeleton. No real-stock scope/receipt is admitted in this phase.
import {validateP1B} from '../p1b/src/contracts.mjs';
import {validateContract,canonical} from '../src/contracts/validate.mjs';
const inputs=new WeakMap(),assessments=new WeakMap(),cards=new WeakMap();
// Closed registry deliberately has no public registration or caller trust hook.
const admittedStockReceipts=new Map();
const fail=(ok,code)=>{if(!ok)throw Error(code);};
export const formalPipeline=Object.freeze({
 stages:Object.freeze(['RealResearchInput','ResearchAssessment','ResearchCard']),
 source_requirement:'INDEPENDENTLY_VERIFIED_AND_PURPOSE_ADMITTED_STOCK_SOURCE',
 receipt_registry:'EMPTY_NO_REAL_STOCK_SCOPE_GRANTED',
 shared_math:'wave_c/math.py PURE_FEATURE_METHODS; TRUST_ADAPTERS_SEPARATE',
 research_policy:'UNSET_REQUIRED',production_enabled:false,can_produce_order:false
});
function noSandbox(x){
 fail(x&&typeof x==='object'&&!JSON.stringify(x).includes('LOCAL_EXPERIMENTAL_REAL_RESEARCH')&&!String(x.contract_name).startsWith('RealResearchSandbox'),'WAVE_C_SANDBOX_FORMAL_PROMOTION_FORBIDDEN');
}
export function prepareRealResearchInput({packet,receipt,snapshot}={}){
 noSandbox(packet);noSandbox(receipt);noSandbox(snapshot);
 validateP1B('BrainPacket',packet);validateP1B('AdmissionReceipt',receipt);validateContract('SnapshotManifest',snapshot);
 fail(receipt.verification==='VERIFIED'&&receipt.admission==='ADMITTED','WAVE_C_FORMAL_VERIFIED_ADMITTED_REQUIRED');
 // A native calendar receipt, fixture proof, relabel or caller facade is not a
 // live verified stock-research admission. No boolean or fake signer can register it.
 const registered=admittedStockReceipts.get(receipt.content_hash);
 fail(registered&&registered.receipt===canonical(receipt)&&registered.packet===canonical(packet)&&registered.snapshot===canonical(snapshot),'WAVE_C_FORMAL_STOCK_RECEIPT_NOT_REGISTERED');
 throw Error('WAVE_C_FORMAL_RESEARCH_POLICY_UNSET');
}
export function assessFormalInput(input){noSandbox(input);fail(inputs.get(input)===canonical(input),'WAVE_C_FORMAL_INPUT_UNREGISTERED');throw Error('WAVE_C_FORMAL_RESEARCH_POLICY_UNSET');}
export function produceFormalCard(assessment){noSandbox(assessment);fail(assessments.get(assessment)===canonical(assessment),'WAVE_C_FORMAL_ASSESSMENT_UNREGISTERED');throw Error('WAVE_C_FORMAL_RESEARCH_POLICY_UNSET');}
export function formalProducerStatus(){return {input_count:0,assessment_count:0,card_count:0,live_stock_receipts:admittedStockReceipts.size,productionGate:false,policy:'UNSET_REQUIRED'};}
