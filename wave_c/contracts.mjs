// Closed local schemas validate display artifacts, never admission or execution.
import fs from 'node:fs';
import Ajv from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {contentHash} from '../src/contracts/validate.mjs';
import {timestampNs} from '../p1b/src/contracts.mjs';
const ajv=new Ajv({strict:true,allErrors:true,coerceTypes:false,useDefaults:false});
addFormats(ajv);ajv.addKeyword('x-contract');
const names=['RealResearchSandboxInput','RealResearchSandboxAssessment','RealResearchSandboxReport'];
const validators=new Map(names.map(n=>[n,ajv.compile(JSON.parse(fs.readFileSync(new URL('../contracts/wave-c/'+n+'.schema.json',import.meta.url))))]));
export function validateSandbox(value){
 const validator=validators.get(value?.contract_name);
 if(!validator||!validator(value))throw Error('WAVE_C_SANDBOX_SCHEMA_INVALID');
 if(value.content_hash!==contentHash(value))throw Error('WAVE_C_SANDBOX_HASH_INVALID');
 if(timestampNs(value.retrieval_cutoff)>timestampNs(value.decision_cutoff))throw Error('WAVE_C_CURRENT_CUTOFF_BEFORE_CAPTURE');
 return value;
}
export function assertSandboxTransition(value,target){
 validateSandbox(value);
 if(target!=='LOCAL_SANDBOX_DISPLAY')throw Error('WAVE_C_SANDBOX_FORMAL_OR_EXECUTION_FORBIDDEN');
 return value;
}
