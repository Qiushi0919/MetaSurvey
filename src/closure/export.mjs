import {mkdir,open,lstat,writeFile,rename,unlink} from 'node:fs/promises';
import {constants} from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {canonical,requireThat,sealContract,validateContract} from '../contracts/validate.mjs';
import {projectDataEnvelope} from '../data/snapshot.mjs';
import {ref} from '../data/core.mjs';
import {assertSanitized,closureRef,sha,validateClosure} from './contracts.mjs';

const BAR_KEYS=['trade_date','open','high','low','close','preclose','volume','amount_cents','price_basis','adjustment_version','corporate_action_lineage','calendar_ref','security_ref'].sort();
const REF_KEYS=['object_id','object_version','content_hash'].sort();
function exactKeys(o,keys){requireThat(o&&canonical(Object.keys(o).sort())===canonical(keys),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');}
function strictRef(r){exactKeys(r,REF_KEYS);requireThat(typeof r.object_id==='string'&&Number.isSafeInteger(r.object_version)&&r.object_version>0&&/^sha256:[a-f0-9]{64}$/.test(r.content_hash),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');}

/** Called only with a closure independently verified against the trusted data DB. */
export function projectSanitizedBarEvidence(closure,rootRefs){
 requireThat(Array.isArray(rootRefs)&&rootRefs.length>0,'CLOSURE_SOURCE_LINEAGE_INCOMPLETE');
 return rootRefs.map(r=>{
  const o=closure.find(c=>canonical(ref(c))===canonical(r));
  requireThat(o?.kind==='BAR_1D'&&o.scope==='SYNTHETIC','CLOSURE_EXPORT_FIELDS_FORBIDDEN');
  exactKeys(o.payload,BAR_KEYS);strictRef(o.payload.calendar_ref);strictRef(o.payload.security_ref);
  requireThat(Array.isArray(o.payload.corporate_action_lineage),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');o.payload.corporate_action_lineage.forEach(strictRef);
  // Original source observations never leave this boundary. Paths are replaced by an opaque content address.
  const projected=sealContract({...projectDataEnvelope(o),raw_uri:`sha256-object:${o.raw_sha256.slice(7)}`});validateContract('DataEnvelope',projected);
  assertSanitized(projected);return projected;
 });
}

export async function buildBrainPacket({service,snapshot,receipt,now}){
 return service.signPacket({snapshot,receipt,now});
}

export async function writeManualExport({service,packet,snapshot,directory,now}){
 packet=structuredClone(packet);snapshot=structuredClone(snapshot);
 // Verify before creating directories or writing bytes. No rejected data reaches an artifact.
 try{
  await service.verifyPacket({packet,snapshot,purpose:packet?.purpose,strategy_id:packet?.strategy_id,now});
  validateClosure('BrainPacket',packet);assertSanitized(packet);
  requireThat(typeof directory==='string'&&directory.length>0,'CLOSURE_IMPORT_INVALID');
  const bytes=Buffer.from(canonical(packet)+'\n'),filename=`brain-packet-${packet.content_hash.slice(7)}.json`,target=path.resolve(directory,filename);
  await mkdir(directory,{recursive:true,mode:0o700});
  requireThat((await lstat(directory)).isDirectory()&&!(await lstat(directory)).isSymbolicLink(),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');
  let created=false;
  return await service.withPacketUse({packet,snapshot,purpose:packet.purpose,strategy_id:packet.strategy_id,now,operation:async()=>{
  try{
  try{
   const stat=await lstat(target);requireThat(stat.isFile()&&!stat.isSymbolicLink(),'CLOSURE_EXPORT_FIELDS_FORBIDDEN');
   const handle=await open(target,constants.O_RDONLY|constants.O_NOFOLLOW);
   try{const existing=await handle.readFile();requireThat(existing.equals(bytes),'CLOSURE_DUPLICATE_CONFLICT');}finally{await handle.close();}
  }
  catch(e){
   if(e.code!=='ENOENT')throw e;
   const temporary=path.join(path.dirname(target),`.${filename}.${randomUUID()}.tmp`);
   try{await writeFile(temporary,bytes,{flag:'wx',mode:0o600});await rename(temporary,target);created=true;}finally{await unlink(temporary).catch(e=>{if(e.code!=='ENOENT')throw e;});}
  }
  await service.audit({chain_id:`export:${packet.object_id}`,event_type:'EXPORT_ACCEPTED',event_time:now,refs:[closureRef(packet),closureRef(packet.receipt)],reason_codes:[]});
  return {path:target,byte_hash:sha(bytes),packet_ref:closureRef(packet)};
  }catch(error){if(created)await unlink(target);throw error;}
  }});
 }catch(error){
  await service.audit({chain_id:'closure:export-rejections',event_type:'EXPORT_REJECTED',event_time:now,refs:[],reason_codes:[error.code?.startsWith('CLOSURE_')?error.code:'CLOSURE_IMPORT_INVALID']});
  throw error;
 }
}
