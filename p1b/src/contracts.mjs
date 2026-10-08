import {readFileSync,readdirSync} from 'node:fs';
import {createHash,generateKeyPairSync,sign,verify,createPublicKey} from 'node:crypto';
import Ajv from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import {hashValue} from '../../src/contracts/validate.mjs';
const dir=new URL('../../contracts/p1b/',import.meta.url),ajv=new Ajv({strict:false,allErrors:true});addFormats(ajv);
const validators=new Map();for(const name of readdirSync(dir).filter(x=>x.endsWith('.schema.json'))){const s=JSON.parse(readFileSync(new URL(name,dir),'utf8'));validators.set(name.replace('.schema.json',''),ajv.compile(s));}
export const hash=hashValue;
export const sha=bytes=>`sha256:${createHash('sha256').update(bytes).digest('hex')}`;
export const bodyOf=x=>Object.fromEntries(Object.entries(x).filter(([k])=>k!=='content_hash'&&k!=='proof'));
export const seal=body=>({...structuredClone(bodyOf(body)),content_hash:hash(bodyOf(body))});
export const refOf=x=>({object_id:x.object_id,object_version:x.object_version,content_hash:x.content_hash});
export function requireP1B(ok,code){if(!ok)throw new Error(code);}
export function assertPublicPayload(x){
 function scan(v){if(Array.isArray(v))return v.forEach(scan);if(v&&typeof v==='object')return Object.values(v).forEach(scan);if(typeof v!=='string')return;
  requireP1B(!/(?:file:\/\/|postgres(?:ql)?:\/\/|sqlite:\/\/|-----BEGIN .*PRIVATE KEY|\bBearer\s+\S+|\bsk-[A-Za-z0-9]{20,}|(?:api[_-]?key|password|secret|broker[_-]?token)\s*[:=]\s*\S+|(?:^|\s)\/(?:Users|home|etc|private|tmp|var)(?:\/|$))/i.test(v),'P1B_SECRET_OR_PATH');
 }scan(x);return x;
}
export function validateP1B(name,x){const validator=validators.get(name);requireP1B(validator&&validator(x),'P1B_ARBITRARY_PAYLOAD');requireP1B(x.content_hash===hash(bodyOf(x)),'P1B_HASH_MISMATCH');assertPublicPayload(x);if(name!=='DiscoveredEvidence')assertNoOutcomeMetadata(x);return x;}
export function makeDevelopmentAuthority(){
 const {privateKey,publicKey}=generateKeyPairSync('ed25519'),der=publicKey.export({format:'der',type:'spki'}),publicKeyDer=der.toString('base64'),issuerHash=sha(der);
 return Object.freeze({publicKeyDer,issuerHash,sign(contentHash){return {algorithm:'ED25519',public_key_der_sha256:issuerHash,signature:sign(null,Buffer.from(contentHash,'utf8'),privateKey).toString('base64')};}});
}
export function verifyTrustedProof(object,publicKeyDer){
 try {const der=Buffer.from(publicKeyDer,'base64'),proof=object.proof;requireP1B(object.content_hash===hash(bodyOf(object)),'P1B_HASH_MISMATCH');requireP1B(proof?.algorithm==='ED25519'&&proof.public_key_der_sha256===sha(der),'P1B_SIGNATURE_INVALID');requireP1B(verify(null,Buffer.from(object.content_hash,'utf8'),createPublicKey({key:der,format:'der',type:'spki'}),Buffer.from(proof.signature,'base64')),'P1B_SIGNATURE_INVALID');return true;}catch(e){if(e.message?.startsWith('P1B_'))throw e;throw new Error('P1B_SIGNATURE_INVALID');}
}
export function timestampNs(value){
 requireP1B(typeof value==='string','P1B_FUTURE_DATA');const m=value.match(/^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?(Z|[+-]\d\d:\d\d)$/);requireP1B(m,'P1B_FUTURE_DATA');const ms=Date.parse(m[1]+m[3]);requireP1B(Number.isFinite(ms),'P1B_FUTURE_DATA');return BigInt(ms)*1000000n+BigInt((m[2]??'').padEnd(9,'0'));
}

function assertNoOutcomeMetadata(object){
 const opaque=new Set(['content_hash','raw_sha256','terms_raw_sha256','signature','public_key_der_sha256','data_hash','projection_hash']);
 function scan(v,key=''){if(opaque.has(key))return;if(Array.isArray(v))return v.forEach(x=>scan(x));if(v&&typeof v==='object')return Object.entries(v).forEach(([k,x])=>{requireP1B(!/(?:^|[_:\s-])(?:MAE|MFE)(?:[_0-9:\s-]|$)|future[_ -]?(?:profit|outcome)|net[_ -]?pnl|days[_ -]?to[_ -]?positive/i.test(k),'P1B_FUTURE_DATA');scan(x,k);});if(typeof v==='string')requireP1B(!/(?:^|[_:\s-])(?:MAE|MFE)(?:[_0-9:\s-]|$)|future[_ -]?(?:profit|outcome)|net[_ -]?pnl|days[_ -]?to[_ -]?positive/i.test(v),'P1B_FUTURE_DATA');}
 scan(object);
}
