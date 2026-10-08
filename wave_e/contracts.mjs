import fs from 'node:fs';
import Ajv from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {contentHash} from '../src/contracts/validate.mjs';
import {timestampNs} from '../p1b/src/contracts.mjs';
const ajv=new Ajv({strict:true,allErrors:true,coerceTypes:false,useDefaults:false});addFormats(ajv);ajv.addKeyword('x-contract');
const names=['HistoricalBacktestReadiness','DiagnosticBacktestResult','SnapshotBPreflight','ForwardPaperReadiness'];
const schemas=new Map(names.map(n=>[n,ajv.compile(JSON.parse(fs.readFileSync(new URL('../contracts/wave-e/'+n+'.schema.json',import.meta.url))))]));
export function validateDiagnostic(v){const c=schemas.get(v?.contract_name);if(!c||!c(v))throw Error('WAVE_E_SCHEMA_INVALID');if(v.content_hash!==contentHash(v))throw Error('WAVE_E_HASH_INVALID');if(timestampNs(v.retrieval_cutoff)>timestampNs(v.decision_cutoff))throw Error('WAVE_E_CUTOFF_INVALID');return v;}
// JSON/schema validation permits display only, never live issuance or promotion.
export function transitionDiagnostic(v,target){validateDiagnostic(v);if(target!=='LOCAL_DIAGNOSTIC_DISPLAY')throw Error('WAVE_E_FORMAL_OR_EXECUTION_FORBIDDEN');return v;}
