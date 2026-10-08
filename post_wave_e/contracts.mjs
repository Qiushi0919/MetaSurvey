import fs from 'node:fs';
import Ajv from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {contentHash} from '../src/contracts/validate.mjs';
import {timestampNs} from '../p1b/src/contracts.mjs';
const names=['HistoricalPITGap','TradeabilityHistoryReadiness','FinancialRevisionReadiness','ActionAdjustmentReconciliation','FrozenStrategySpec','ForwardPaperRealAdapterReadiness','SnapshotBPreparation','ProviderLicenseTransportGap'];
const ajv=new Ajv({strict:true,allErrors:true,coerceTypes:false,useDefaults:false});addFormats(ajv);ajv.addKeyword('x-contract');
const validators=new Map(names.map(n=>[n,ajv.compile(JSON.parse(fs.readFileSync(new URL('../contracts/post-wave-e/'+n+'.schema.json',import.meta.url))))]));
export function validatePreparation(v){const check=validators.get(v?.contract_name);if(!check||!check(v))throw Error('PREP_SCHEMA_INVALID');if(v.content_hash!==contentHash(v))throw Error('PREP_HASH_INVALID');if(timestampNs(v.retrieval_cutoff)>timestampNs(v.decision_cutoff))throw Error('PREP_CUTOFF_INVALID');return v;}
export function transitionPreparation(v,target){validatePreparation(v);if(target!=='LOCAL_PREPARATION_DISPLAY')throw Error('PREP_NATIVE_OR_EXECUTION_FORBIDDEN');return v;}
export function issueActual(){throw Error('PREP_ACTUAL_ISSUANCE_FORBIDDEN');}
