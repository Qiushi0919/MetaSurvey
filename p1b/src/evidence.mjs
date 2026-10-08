import {hash,seal,validateP1B,assertPublicPayload} from './contracts.mjs';

function ensure(ok,code){if(!ok)throw new Error(code);}
const sameKeys=(o,keys)=>o&&Object.getPrototypeOf(o)===Object.prototype&&JSON.stringify(Object.keys(o).sort())===JSON.stringify([...keys].sort());
function safePublicReference(original_uri){
 ensure(typeof original_uri==='string'&&original_uri.length<=4000,'P1B_ARBITRARY_PAYLOAD');
 let u;try{u=new URL(original_uri);}catch{throw new Error('P1B_ARBITRARY_PAYLOAD');}
 ensure(['http:','https:'].includes(u.protocol)&&!u.username&&!u.password,'P1B_SECRET_OR_PATH');
 ensure(u.hostname&&!/^(?:localhost|127(?:\.|$)|0(?:\.|$)|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|169\.254\.|\[)/i.test(u.hostname)&&!/(?:\.local|\.internal)$/i.test(u.hostname),'P1B_SECRET_OR_PATH');
 for(const key of u.searchParams.keys())ensure(!/(?:token|password|secret|credential|api[_-]?key|signature|authorization)/i.test(key),'P1B_SECRET_OR_PATH');
 let decoded=original_uri;for(let i=0;i<2;i++){try{decoded=decodeURIComponent(decoded);}catch{break;}}
 assertPublicPayload(decoded);ensure(!/\/(?:Users|home|private|tmp|var)(?:\/|$)/i.test(decoded),'P1B_SECRET_OR_PATH');
 return original_uri;
}

// Pure lead recording: URL is a citation pointer, not a request, clock proof or
// trusted source. There is no network, raw capture, DB or promotion capability.
export function ingestDiscoveredEvidence(input){
 ensure(sameKeys(input,['original_uri','lead','discovered_at','origin']),'P1B_ARBITRARY_PAYLOAD');
 const facts=structuredClone(input);safePublicReference(facts.original_uri);assertPublicPayload(facts);
 const identity=hash(facts).slice(7);
 const evidence=seal({contract_name:'DiscoveredEvidence',contract_version:'1.0.0',object_id:'discovered:'+identity,object_version:1,trace_id:'cloud-lead:'+identity,trust_class:'CLOUD_DISCOVERED_EVIDENCE',status:'PENDING_VERIFICATION',...facts,admission_ref:null,usable_for_hard_block:false,usable_for_grade:false,usable_for_sizing:false,can_produce_order:false,production_enabled:false});
 validateP1B('DiscoveredEvidence',evidence);
 return Object.freeze(evidence);
}

export function assertEvidenceUse(evidence,purpose){
 // A caller cannot relabel a lead and rehash it into an admitted object. Actual
 // admission requires a different verified facade/adapter, absent from this API.
 ensure(evidence?.trust_class==='CLOUD_DISCOVERED_EVIDENCE'&&evidence.status==='PENDING_VERIFICATION'&&evidence.admission_ref===null,'P1B_CLOUD_EVIDENCE_UNTRUSTED');
 validateP1B('DiscoveredEvidence',evidence);safePublicReference(evidence.original_uri);
 ensure(['RESEARCH_LEAD','COUNTERARGUMENT'].includes(purpose),'P1B_CLOUD_EVIDENCE_UNTRUSTED');
 return true;
}

export function describeVerificationWorkflow(){
 return Object.freeze({version:'1.0.0',initial_trust_class:'CLOUD_DISCOVERED_EVIDENCE',initial_status:'PENDING_VERIFICATION',steps:Object.freeze(['CAPTURE_ORIGINAL_SOURCE','HASH_ORIGINAL_BYTES','VERIFY_EVENT_PUBLICATION_AVAILABILITY_RETRIEVAL_CLOCKS','VERIFY_SOURCE_AND_TERMS','VERIFY_PURPOSE_NAMESPACE_AND_COVERAGE','APPROVED_ADMISSION_POLICY','VERIFIED_ADMISSION_RECEIPT','EXPLICIT_VERSIONED_LOCAL_EVIDENCE_ADAPTER']),promotion_authority:'TRUSTED_LOCAL_ADMISSION_FACADE',citation_or_manual_assertion_can_promote:false,automatic_trust_promotion:false,current_general_promotion_entrypoint:false,production_enabled:false});
}
