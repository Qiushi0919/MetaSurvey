import {hash,seal,refOf,validateP1B,requireP1B,timestampNs} from './contracts.mjs';
export function createLocalEvidenceAdapter({service}){
 const registered=new Map();
 function resolve({lead,packet,receipt,snapshot,use_at}){
  const l=structuredClone(lead),p=structuredClone(packet),r=structuredClone(receipt),s=structuredClone(snapshot);validateP1B('DiscoveredEvidence',l);requireP1B(timestampNs(l.discovered_at)<=timestampNs(use_at),'P1B_FUTURE_DATA');
  service.verifyPacket({packet:p,receipt:r,snapshot:s,use_at,purpose:'LOCAL_NONCOMMERCIAL_CALENDAR_REFERENCE',strategy_id:'CORE_40'});
  const observation=service.observationFor(p.evidence[0].source_id);requireP1B(l.original_uri===observation.original_uri,'P1B_SOURCE_UNAPPROVED');
  const body={contract_name:'EvidenceResolution',contract_version:'1.0.0',object_id:'resolution:'+hash({lead_ref:refOf(l),packet_ref:refOf(p)}).slice(7),object_version:1,trace_id:'p1b-local-reference-resolution',strategy_id:'CORE_40',purpose:p.purpose,coverage:p.coverage,permissions:p.permissions,production_enabled:false,trust_class:'ADMITTED_LOCAL_EVIDENCE',status:'ADMITTED_LOCAL_SOURCE_FACTS_ONLY',lead_ref:refOf(l),observation_ref:p.evidence[0].observation_ref,receipt_ref:refOf(r),packet_ref:refOf(p),original_uri:observation.original_uri,lead_claims_admitted:false,usable_for_hard_block:false,usable_for_grade:false,usable_for_sizing:false,can_produce_order:false};
  const result=seal(body);validateP1B('EvidenceResolution',result);registered.set(result.content_hash,{result:structuredClone(result),packet:p,receipt:r,snapshot:s,use_at});return structuredClone(result);
 }
 function assertUse(resolution,purpose){const x=structuredClone(resolution);validateP1B('EvidenceResolution',x);const entry=registered.get(x.content_hash);requireP1B(entry&&hash(x)===hash(entry.result),'P1B_RECEIPT_UNKNOWN');requireP1B(purpose==='LOCAL_CALENDAR_REFERENCE','P1B_PERMISSION_SCOPE');service.verifyPacket({packet:entry.packet,receipt:entry.receipt,snapshot:entry.snapshot,use_at:entry.use_at,purpose:entry.packet.purpose,strategy_id:'CORE_40'});return true;}
 return Object.freeze({resolve,assertUse});
}
