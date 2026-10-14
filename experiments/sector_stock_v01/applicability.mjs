import fs from 'node:fs';
import {sha} from '../sector_stock_v0/engine.mjs';
export const candidate=JSON.parse(fs.readFileSync(new URL('./config.json',import.meta.url)));
export const candidateHash=sha(fs.readFileSync(new URL('./config.json',import.meta.url)));
export const applicabilityHash=sha(fs.readFileSync(new URL(import.meta.url)));
export function assess(level,risks,priceOrders='UNKNOWN'){
 if(!['SECTOR','STOCK'].includes(level)||!['APPLICABLE','NOT_APPLICABLE','UNKNOWN'].includes(priceOrders))throw new Error('APPLICABILITY_ENUM');
 const rules=candidate.risk_by_level[level];
 if(Object.keys(risks).sort().join('|')!==Object.keys(rules).sort().join('|'))throw new Error('RISK_SET');
 const reasons=['OWNER_ECONOMIC_METHOD_PENDING'];const result={};
 for(const [key,rule] of Object.entries(rules)){
  const x=risks[key];
  if(!x||!['PRESENT','ABSENT','UNKNOWN','NOT_APPLICABLE'].includes(x.state)||!Array.isArray(x.evidence_ids))throw new Error('RISK_SHAPE');
  if(rule.applicability==='NOT_APPLICABLE'){
   if(x.state!=='NOT_APPLICABLE'||x.basis!==rule.basis)throw new Error('SECTOR_COMPANY_RATIO_NOT_APPLICABLE');
  }else{
   if(x.state==='NOT_APPLICABLE')throw new Error('APPLICABLE_RISK_CANNOT_BE_NA');
   if(x.state==='UNKNOWN')reasons.push('RISK_UNKNOWN:'+key);
   else if(!x.evidence_ids.length)reasons.push('RISK_EVIDENCE_REQUIRED:'+key);
  }
  result[key]={state:x.state,applicability:rule.applicability,deduction:null,basis:rule.basis??null};
 }
 if(level==='SECTOR'){
  reasons.push('SECTOR_RISK_METHOD_PENDING','COMPETITION_MEASURE_UNDEFINED');
  if(priceOrders!=='APPLICABLE')reasons.push('PRICE_ORDERS_'+priceOrders);
 }
 return {version:candidate.version,config_sha256:candidateHash,level,state:'BLOCKED',risks:result,price_orders_applicability:priceOrders,raw_score:null,final_score:null,risk_deduction:null,reason_codes:reasons,entry_timing:'NOT_DEFINED'};
}
export function unknownRisks(level){return Object.fromEntries(Object.entries(candidate.risk_by_level[level]).map(([key,r])=>[key,r.applicability==='NOT_APPLICABLE'?{state:'NOT_APPLICABLE',evidence_ids:[],basis:r.basis}:{state:'UNKNOWN',evidence_ids:[]} ]));}
