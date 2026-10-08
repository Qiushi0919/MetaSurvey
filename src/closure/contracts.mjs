import fs from 'node:fs';
import {createHash,createPrivateKey,createPublicKey,sign,verify} from 'node:crypto';
import Ajv from 'ajv/dist/2020.js';
import formats from 'ajv-formats';
import {hashValue,requireThat,validateContract} from '../contracts/validate.mjs';
const ajv=new Ajv({strict:true,allErrors:true,coerceTypes:false,useDefaults:false});formats(ajv);ajv.addKeyword('x-contract');ajv.addKeyword('x-unit');
for(const n of fs.readdirSync(new URL('../../contracts/v1/',import.meta.url)).filter(n=>n.endsWith('.schema.json')))ajv.addSchema(JSON.parse(fs.readFileSync(new URL('../../contracts/v1/'+n,import.meta.url),'utf8')));
for(const n of fs.readdirSync(new URL('../../contracts/closure/',import.meta.url)).filter(n=>n.endsWith('.schema.json')))ajv.addSchema(JSON.parse(fs.readFileSync(new URL('../../contracts/closure/'+n,import.meta.url),'utf8')));
export const reasons=JSON.parse(fs.readFileSync(new URL('../../contracts/reason-codes.closure.json',import.meta.url),'utf8')).reason_codes;
export const sha=bytes=>'sha256:'+createHash('sha256').update(bytes).digest('hex');
export function closureHash(value){const{content_hash,proof,...body}=value;return hashValue(body);}
export function sealClosure(value){const{content_hash,proof,...body}=value;return {...structuredClone(body),content_hash:hashValue(body)};}
export function closureRef(o){return {object_id:o.object_id,object_version:o.object_version,content_hash:o.content_hash};}
export function projectionHash(p){return hashValue(Object.fromEntries(['snapshot_ref','data_hash','decision_cutoff','feature_version','rules_hash','evidence'].map(k=>[k,p[k]])));}
export function validateClosure(name,o){const v=ajv.getSchema('urn:ashare:contracts:closure:'+name);requireThat(v&&v(o),'CLOSURE_IMPORT_INVALID',v?.errors);requireThat(o.content_hash===closureHash(o),'CLOSURE_HASH_MISMATCH');
 if(name==='BrainPacket'){requireThat(projectionHash(o)===o.projection_hash,'CLOSURE_HASH_MISMATCH');for(const e of o.evidence)validateContract('DataEnvelope',e);}
 return o;
}
// Synthetic key material only. Constructor capability is held by the trusted parent, never exported to consumer.
export function createFixtureAuthority(seed=Buffer.alloc(32,73)){
 requireThat(Buffer.isBuffer(seed)&&seed.length===32,'CLOSURE_POLICY_UNTRUSTED');
 const privateKey=createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),seed]),format:'der',type:'pkcs8'}),publicKey=createPublicKey(privateKey),der=publicKey.export({format:'der',type:'spki'});
 const issuer={issuer_id:'SYNTHETIC_CLOSURE_ISSUER',key_id:'SYNTHETIC_ED25519_FIXTURE_KEY',public_key_hash:sha(der)};
 return {fixture_scope:'SYNTHETIC_TEST_ONLY',issuer,publicKeyDer:Buffer.from(der),signObject(o){requireThat(o.fixture_scope==='SYNTHETIC_TEST_ONLY'&&o.purpose==='FIXTURE_MANUAL_EXPORT'&&o.production_enabled===false,'CLOSURE_SYNTHETIC_SCOPE_ESCALATION');const body=sealClosure(o);return {...body,proof:{algorithm:'ED25519',signature:sign(null,Buffer.from(body.content_hash),privateKey).toString('base64')}};}};
}
export function verifyClosureSignature(o,trustedPublicKeyDer){requireThat(sha(trustedPublicKeyDer)===o.issuer.public_key_hash,'CLOSURE_SIGNATURE_INVALID');requireThat(o.content_hash===closureHash(o),'CLOSURE_HASH_MISMATCH');requireThat(o.proof?.algorithm==='ED25519'&&verify(null,Buffer.from(o.content_hash),createPublicKey({key:trustedPublicKeyDer,format:'der',type:'spki'}),Buffer.from(o.proof.signature,'base64')),'CLOSURE_SIGNATURE_INVALID');return true;}
export function assertSanitized(value){
 const text=JSON.stringify(value);
 requireThat(!/(?:-----BEGIN|\bsk-[A-Za-z0-9]{20,}|\bAKIA[A-Z0-9]{16}\b|Bearer\s+\S+|file:\/\/|(?:\/Users\/|\/tmp\/|\/private\/|postgres(?:ql)?:\/\/)|[A-Z]:\\|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})/i.test(text),'CLOSURE_SECRET_OR_PATH_LEAKAGE');
 const walk=(v)=>{if(!v||typeof v!=='object')return;for(const[k,x]of Object.entries(v)){if(k==='contains_account_identity_or_credentials'&&x===false)continue;requireThat(!/password|token|secret|credential|raw_path|db_path|broker_capability|future_|mae|mfe|daily_nav|outcome/i.test(k),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');if(typeof x==='string'&&!/^sha256:[a-f0-9]{64}$/.test(x)&&!/^sha256-object:[a-f0-9]{64}$/.test(x)&&k!=='signature'){if(!k.endsWith('_cents')&&!/^(?:brain|admission|draft|snapshot):[a-f0-9]{64}$/.test(x)&&!/^synthetic:closure-policy:[a-f0-9]{40}:schema6:packet1\.1\.0:receipt1\.0\.0$/.test(x))requireThat(!/(?<![0-9])[0-9]{12,}(?![0-9])/.test(x),'CLOSURE_SECRET_OR_PATH_LEAKAGE');requireThat(!/(?:(?:^|[:._/\s-])(?:MAE|MFE|outcome)(?:$|[:._/\s-])|future[_ -]|daily[_ -]?nav)/i.test(x),'CLOSURE_OUTCOME_LEAKAGE');}walk(x);}};walk(value);return true;
}
