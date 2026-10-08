import {readFileSync,readdirSync} from 'node:fs';
import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {validateCostProfile} from '../cost/index.mjs';
import {requireThat,contentHash,hashValue} from '../contracts/validate.mjs';
const directory=new URL('../../contracts/p1a/',import.meta.url);
const ajv=new Ajv2020({allErrors:true,strict:true,coerceTypes:false,useDefaults:false});addFormats(ajv);ajv.addKeyword('x-unit');ajv.addKeyword('x-contract');
for(const name of readdirSync(directory).filter(x=>x.endsWith('.schema.json')))ajv.addSchema(JSON.parse(readFileSync(new URL(name,directory),'utf8')));
export function validateP1AContract(name,object){const validate=ajv.getSchema(`urn:ashare:contracts:p1a:${name}`);requireThat(validate,'P1A_UNSUPPORTED_CONTRACT');requireThat(validate(object),'P1A_CONTRACT_SCHEMA_INVALID',validate.errors?.map(e=>({path:e.instancePath,keyword:e.keyword})));
  if(name==='CostProfile')validateCostProfile(object,{mode:'PAPER',trade_date:object.effective_from});
  if('content_hash' in object)requireThat(contentHash(object)===object.content_hash,'P1A_CONTRACT_HASH_MISMATCH');
  if(name==='DeterministicReplayResult'){const{economic_result_hash,diagnostics,production_enabled,...body}=object;requireThat(hashValue(body)===economic_result_hash,'REPLAY_RESULT_HASH_MISMATCH');}
  if(name==='AuditChainEvent'){const{event_hash,...body}=object;requireThat(hashValue(body)===event_hash,'AUDIT_CHAIN_MISMATCH');}
  if(['P1ACostEstimate','CostAttribution'].includes(name)){
    const sum=['commission_cents','stamp_tax_cents','exchange_fee_cents','other_fee_cents','slippage_cents'].reduce((n,k)=>n+BigInt(object[k]),0n);
    requireThat(sum.toString()===object.total_friction_cents&&BigInt(object.proportional_commission_cents)+BigInt(object.minimum_commission_effect_cents)===BigInt(object.commission_cents),'COST_ATTRIBUTION_DOUBLE_COUNT');
    if(name==='CostAttribution')requireThat(BigInt(object.gross_pnl_cents)-sum===BigInt(object.net_pnl_cents),'RECONCILIATION_FAILED');
  }
  if(name==='SourceObservation'&&object.tradeability==='OFFLINE_ELIGIBLE')requireThat(object.source_policy.source_class==='SYNTHETIC'&&object.source_policy.allowed_use.includes('SYNTHETIC_TEST')&&object.clock_proof!==null&&object.available_at!==null,'UNKNOWN_SOURCE_ADMISSION_FORBIDDEN');
  if(name==='SourceObservation')requireThat(object.available_at!==null||(object.data_quality_status==='QUARANTINED'&&object.tradeability==='NON_TRADEABLE'),'UNKNOWN_SOURCE_ADMISSION_FORBIDDEN');return object;
}
export function p1aContractNames(){return readdirSync(directory).filter(x=>x.endsWith('.schema.json')).map(x=>x.replace('.schema.json','')).sort();}
