import fs from 'node:fs';
import Ajv from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {contentHash} from '../src/contracts/validate.mjs';
import {timestampNs} from '../p1b/src/contracts.mjs';
const ajv=new Ajv({strict:true,allErrors:true,coerceTypes:false,useDefaults:false});addFormats(ajv);ajv.addKeyword('x-contract');
const names=['RealResearchSandboxInput','RealResearchSandboxAssessment','RealResearchSandboxReport','ResearchComparison'];
const schemas=new Map(names.map(n=>[n,ajv.compile(JSON.parse(fs.readFileSync(new URL('../contracts/wave-d/'+n+'.schema.json',import.meta.url))))]));
export function validateLocalResearch(v){const check=schemas.get(v?.contract_name);if(!check||!check(v))throw Error('WAVE_D_SCHEMA_INVALID');if(v.content_hash!==contentHash(v))throw Error('WAVE_D_HASH_INVALID');if(timestampNs(v.retrieval_cutoff)>timestampNs(v.decision_cutoff))throw Error('WAVE_D_CUTOFF_INVALID');return v;}
export function transitionLocalResearch(v,target){validateLocalResearch(v);if(target!=='LOCAL_SANDBOX_DISPLAY')throw Error('WAVE_D_FORMAL_OR_EXECUTION_FORBIDDEN');return v;}
