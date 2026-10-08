import { requireThat,timestampMs,derived,putObject,allKind,audit,ref,assertFacts } from './core.mjs';

export function parseSecuritySymbol(original_symbol,exchange=null) {
  requireThat(typeof original_symbol==='string','SECURITY_SYMBOL_INVALID');const input=original_symbol.trim();
  let m=/^(sh|sz)[.:]?(\d{6})$/i.exec(input), ex=m?({sh:'SSE',sz:'SZSE'}[m[1].toLowerCase()]):null,code=m?.[2];
  if(!m){m=/^(SSE|SZSE):(\d{6})$/i.exec(input);if(m){ex=m[1].toUpperCase();code=m[2];}}
  if(!m){m=/^(\d{6})\.(SH|SS|SZ)$/i.exec(input);if(m){ex=m[2].toUpperCase()==='SZ'?'SZSE':'SSE';code=m[1];}}
  if(!m&&/^\d{6}$/.test(input)){code=input;requireThat(exchange==='SSE'||exchange==='SZSE','SECURITY_EXCHANGE_AMBIGUOUS');ex=exchange;}
  requireThat(code&&['SSE','SZSE'].includes(ex),'SECURITY_SYMBOL_INVALID');
  requireThat(!exchange||exchange===ex,'SECURITY_EXCHANGE_CONFLICT');
  return {canonical_symbol:`${ex}:${code}`,exchange:ex,code,original_symbol};
}
export async function registerSecurity(db,{observation,security_id,object_version=1,original_symbol,exchange,listing_status,list_date,delist_date=null,board,lot_size,st_status,suspension_status,effective_from,effective_to=null,name}) {
  let identity;
  try{identity=parseSecuritySymbol(original_symbol,exchange);}catch(e){await audit(db,'SECURITY_QUARANTINED',observation,[e.code??e.message]);throw e;}
  requireThat(security_id&&name,'SECURITY_FIELDS_REQUIRED');
  requireThat(['LISTED','DELISTED','UNKNOWN'].includes(listing_status)&&['NORMAL','ST','SPECIAL','UNKNOWN'].includes(st_status)&&['TRADING','SUSPENDED','UNKNOWN'].includes(suspension_status),'SECURITY_STATUS_INVALID');
  requireThat(lot_size===null||(Number.isSafeInteger(lot_size)&&lot_size>0),'LOT_SIZE_INVALID');timestampMs(effective_from);
  if(effective_to)requireThat(timestampMs(effective_to)>timestampMs(effective_from),'EFFECTIVE_RANGE_INVALID');
  const records=await allKind(db,'SECURITY');
  const conflict=records.some(o=>o.data_quality_status==='PASS'&&((o.canonical_symbol===identity.canonical_symbol&&o.security_id!==security_id)||(o.security_id===security_id&&o.canonical_symbol!==identity.canonical_symbol)));
  const unknown=[listing_status,st_status,suspension_status,board,list_date].includes('UNKNOWN')||lot_size===null;
  const reasons=[...(conflict?['SECURITY_IDENTITY_CONFLICT']:[]),...(unknown?['SECURITY_STATUS_UNKNOWN']:[])];
  const payload={...identity,security_id,name,listing_status,list_date,delist_date,board,lot_size,st_status,suspension_status,effective_from,effective_to};
  requireThat(parseSecuritySymbol(observation.payload.original_symbol).canonical_symbol===identity.canonical_symbol,'SECURITY_SOURCE_IDENTITY_MISMATCH');
  assertFacts(observation,{name,listing_status,list_date,delist_date,board,lot_size,st_status,suspension_status,effective_from,effective_to});
  const o=await putObject(db,derived(observation,{kind:'SECURITY',object_id:`security:${security_id}`,object_version,payload,security_id,...identity,data_quality_status:conflict?'QUARANTINED':observation.data_quality_status,tradeability:conflict||unknown?'NON_TRADEABLE':observation.tradeability,reason_codes:[...observation.reason_codes,...reasons]}));
  if(conflict)await audit(db,'SECURITY_IDENTITY_QUARANTINED',o,reasons);return o;
}
export async function resolveSecurity(db,symbol,{exchange=null,decision_cutoff,allow_reference=false}={}) {
  let parsed;try{parsed=parseSecuritySymbol(symbol,exchange);}catch(e){await audit(db,'SECURITY_RESOLUTION_QUARANTINED',null,[e.code??e.message]);throw e;}
  const cutoff=timestampMs(decision_cutoff);
  requireThat(!await identityConflictVisible(db,parsed.canonical_symbol,decision_cutoff),'SECURITY_IDENTITY_CONFLICT');
  const rows=(await allKind(db,'SECURITY')).filter(o=>o.canonical_symbol===parsed.canonical_symbol&&o.data_quality_status==='PASS'&&o.available_at&&timestampMs(o.available_at)<=cutoff&&timestampMs(o.retrieved_at)<=cutoff&&timestampMs(o.payload.effective_from)<=cutoff&&(!o.payload.effective_to||timestampMs(o.payload.effective_to)>cutoff));
  const ids=new Set(rows.map(r=>r.security_id));requireThat(ids.size===1,'SECURITY_IDENTITY_UNRESOLVED');
  rows.sort((a,b)=>timestampMs(b.payload.effective_from)-timestampMs(a.payload.effective_from)||b.object_version-a.object_version);const o=rows[0];
  const status=await latestStatus(db,o.security_id,decision_cutoff);
  requireThat(allow_reference||o.tradeability==='OFFLINE_ELIGIBLE','SECURITY_NON_TRADEABLE');
  if(status)requireThat(status.payload.suspension_status==='TRADING'&&status.payload.st_status!=='UNKNOWN','SECURITY_NON_TRADEABLE');
  requireThat(allow_reference||(o.payload.suspension_status==='TRADING'&&o.payload.st_status!=='UNKNOWN'&&o.payload.listing_status==='LISTED'),'SECURITY_NON_TRADEABLE');return o;
}
export async function identityConflictVisible(db,canonical_symbol,decision_cutoff){const cutoff=timestampMs(decision_cutoff);return (await allKind(db,'SECURITY')).some(o=>o.canonical_symbol===canonical_symbol&&o.reason_codes.includes('SECURITY_IDENTITY_CONFLICT')&&o.available_at&&timestampMs(o.available_at)<=cutoff&&timestampMs(o.retrieved_at)<=cutoff);}
export async function latestSecurity(db,security_id,decision_cutoff){const cutoff=timestampMs(decision_cutoff);const rows=(await allKind(db,'SECURITY')).filter(o=>o.security_id===security_id&&o.data_quality_status==='PASS'&&o.available_at&&timestampMs(o.available_at)<=cutoff&&timestampMs(o.retrieved_at)<=cutoff&&timestampMs(o.payload.effective_from)<=cutoff&&(!o.payload.effective_to||timestampMs(o.payload.effective_to)>cutoff));rows.sort((a,b)=>timestampMs(b.payload.effective_from)-timestampMs(a.payload.effective_from)||b.object_version-a.object_version);return rows[0]??null;}
export async function latestStatus(db,security_id,decision_cutoff){const cutoff=timestampMs(decision_cutoff);const rows=(await allKind(db,'STATUS')).filter(o=>o.security_id===security_id&&o.available_at&&timestampMs(o.available_at)<=cutoff&&timestampMs(o.retrieved_at)<=cutoff&&timestampMs(o.payload.effective_from)<=cutoff&&(!o.payload.effective_to||timestampMs(o.payload.effective_to)>cutoff));rows.sort((a,b)=>timestampMs(b.payload.effective_from)-timestampMs(a.payload.effective_from)||b.object_version-a.object_version);if(rows.length>1&&rows[0].payload.effective_from===rows[1].payload.effective_from&&rows[0].object_version===rows[1].object_version)requireThat(false,'SECURITY_STATUS_CONFLICT');return rows[0]??null;}
export async function ingestSecurityStatus(db,{observation,security,effective_from,effective_to=null,st_status,suspension_status,object_id,object_version=1}) {
  requireThat(['NORMAL','ST','SPECIAL','UNKNOWN'].includes(st_status)&&['TRADING','SUSPENDED','UNKNOWN'].includes(suspension_status),'SECURITY_STATUS_INVALID');
  const unknown=st_status==='UNKNOWN'||suspension_status==='UNKNOWN';
  timestampMs(effective_from);if(effective_to)requireThat(timestampMs(effective_to)>timestampMs(effective_from),'EFFECTIVE_RANGE_INVALID');
  assertFacts(observation,{effective_from,effective_to,st_status,suspension_status});
  assertFacts(observation,{canonical_symbol:security.canonical_symbol});
  return putObject(db,derived(observation,{kind:'STATUS',object_id,object_version,payload:{effective_from,effective_to,st_status,suspension_status},security_id:security.security_id,canonical_symbol:security.canonical_symbol,lineage_refs:[ref(security)],tradeability:unknown?'NON_TRADEABLE':observation.tradeability,reason_codes:[...observation.reason_codes,...(unknown?['SECURITY_STATUS_UNKNOWN']:[])]}));
}
