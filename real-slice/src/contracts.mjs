import fs from 'node:fs';
import Ajv from 'ajv/dist/2020.js';
import formats from 'ajv-formats';
import { generateKeyPairSync,createHash,sign,verify,createPublicKey } from 'node:crypto';
import {hashValue,canonical} from '../../src/contracts/validate.mjs';
import {timestampNs} from '../../p1b/src/contracts.mjs';
export const hash=hashValue;
export {canonical,timestampNs};
export const sha=b=>'sha256:'+createHash('sha256').update(b).digest('hex');
export const body=x=>Object.fromEntries(Object.entries(x).filter(([k])=>k!=='content_hash'&&k!=='proof'));
export const seal=x=>({...structuredClone(body(x)),content_hash:hash(body(x))});
export const refOf=x=>({object_id:x.object_id,object_version:x.object_version,content_hash:x.content_hash});
export function requireSlice(ok,code){if(!ok)throw Object.assign(new Error(code),{code});}
const ajv=new Ajv({strict:false,allErrors:true,coerceTypes:false,useDefaults:false});formats(ajv);
const directory=new URL('../../contracts/real-slice/',import.meta.url),ids=new Map();
for(const n of fs.readdirSync(directory).filter(n=>n.endsWith('.schema.json'))){const s=JSON.parse(fs.readFileSync(new URL(n,directory),'utf8'));ajv.addSchema(s);ids.set(n.replace('.schema.json',''),s.$id);}
export function validate(name,value){const v=ajv.getSchema(ids.get(name));requireSlice(v&&v(value),'SLICE_DQ_FAILED');requireSlice(value.content_hash===hash(body(value)),'SLICE_REF_INVALIDATED');assertPublic(value);return value;}
export function assertPublic(value){
 function scan(x){if(Array.isArray(x))return x.forEach(scan);if(x&&typeof x==='object')return Object.entries(x).forEach(([k,v])=>{
  requireSlice(!/(?:^|_)(?:token|password|secret|credentials|raw_path|db_connection|broker|future_return|future_outcome|MAE|MFE)(?:_|$)/i.test(k),'SLICE_SECRET_OR_PATH');scan(v);
 });if(typeof x==='string'){
  requireSlice(!/(?:file:\/\/|postgres(?:ql)?:\/\/|-----BEGIN .*PRIVATE KEY|\bBearer\s+\S+|\bsk-[A-Za-z0-9]{20,}|(?:token|password|api[_-]?key)\s*[:=]\s*\S+|(?:^|\s)\/(?:Users|home|etc|private|tmp|var)(?:\/|$))/i.test(x),'SLICE_SECRET_OR_PATH');
  requireSlice(!/(?:^|[_:\s-])(?:MAE|MFE|future[_ -]?(?:return|outcome)|backtest[_ -]?outcome)(?:[_0-9:\s-]|$)/i.test(x),'SLICE_OUTCOME_LEAKAGE');
 }}scan(value);return value;
}
export function makeAuthority(){const {privateKey,publicKey}=generateKeyPairSync('ed25519'),der=publicKey.export({format:'der',type:'spki'});return Object.freeze({publicKeyDer:der.toString('base64'),sign(h){return {algorithm:'ED25519',public_key_der_sha256:sha(der),signature:sign(null,Buffer.from(h),privateKey).toString('base64')};}});}
export function verifyProof(x,key){try{const der=Buffer.from(key,'base64');requireSlice(x.content_hash===hash(body(x))&&x.proof?.public_key_der_sha256===sha(der)&&x.proof.algorithm==='ED25519'&&verify(null,Buffer.from(x.content_hash),createPublicKey({key:der,format:'der',type:'spki'}),Buffer.from(x.proof.signature,'base64')),'SLICE_CAPTURE_UNTRUSTED');}catch(e){if(e.code?.startsWith('SLICE_'))throw e;throw new Error('SLICE_CAPTURE_UNTRUSTED');}}
