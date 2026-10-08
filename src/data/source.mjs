import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { canonical, hashValue, requireThat, timestampMs, rawHash, putObject, checkObject } from './core.mjs';

const clockPath = (payload,p) => p.split('.').reduce((o,k)=>o?.[k],payload);
const captures=new WeakMap();
function proveClocks(bytes,source,clocks,retrieved_at) {
  const c={event_time:clocks.event_time??null,published_at:clocks.published_at??null,available_at:null,retrieved_at,publication_precision:clocks.publication_precision??'UNKNOWN',clock_basis:'UNKNOWN',clock_proof:clocks.clock_proof??null};
  if(c.event_time) timestampMs(c.event_time);
  if(c.publication_precision==='SECOND')timestampMs(c.published_at);
  if(c.publication_precision==='DATE_ONLY')requireThat(/^\d{4}-\d{2}-\d{2}$/.test(c.published_at),'PUBLICATION_DATE_INVALID');
  const proof=c.clock_proof;
  if(proof?.type==='SOURCE_FIELD') {
    requireThat(source.source_class==='SYNTHETIC','OFFICIAL_CLOCK_MAPPING_NOT_AUTHORIZED');
    requireThat(source.clock_policy?.type==='SOURCE_FIELD'&&proof.available_path===source.clock_policy.available_path&&proof.published_path===source.clock_policy.published_path,'CLOCK_POLICY_MISMATCH');
    const raw=JSON.parse(bytes.toString('utf8'));
    requireThat(clockPath(raw,proof.published_path)===c.published_at,'PUBLISHED_AT_FALSIFIED');
    const available=clockPath(raw,proof.available_path);timestampMs(available);
    requireThat(clocks.available_at===undefined||clocks.available_at===available,'AVAILABLE_AT_FALSIFIED');
    c.available_at=available;c.clock_basis=source.source_class==='SYNTHETIC'?'SYNTHETIC':'SOURCE_FIELD';
  } else if(proof?.type==='RETRIEVAL_OBSERVATION') {
    requireThat(source.clock_policy?.type==='RETRIEVAL_OBSERVATION'&&source.data_class==='REFERENCE_DOCUMENT','CLOCK_POLICY_MISMATCH');
    requireThat(clocks.available_at===undefined||clocks.available_at===retrieved_at,'AVAILABLE_AT_FALSIFIED');
    c.available_at=retrieved_at;c.clock_basis='RETRIEVAL_OBSERVATION';
    if(c.publication_precision==='DATE_ONLY')requireThat(bytes.toString('utf8').replace(/\s/g,'').includes(c.published_at)||bytes.toString('utf8').replace(/\s/g,'').includes(c.published_at.replace(/^(\d{4})-(\d{2})-(\d{2})$/,'$1年$2月$3日')),'PUBLISHED_AT_FALSIFIED');
    // Market publication/availability remains unproven; this represents an observed reference copy only.
  } else requireThat(clocks.available_at===undefined||clocks.available_at===null,'AVAILABLE_AT_UNPROVEN');
  if(c.available_at){
    requireThat(timestampMs(c.available_at)<=timestampMs(retrieved_at),'AVAILABLE_AFTER_RETRIEVAL');
    if(c.publication_precision==='SECOND')requireThat(timestampMs(c.published_at)<=timestampMs(c.available_at),'PUBLICATION_AFTER_AVAILABILITY');
  }
  return c;
}
export async function capturePublicSource({url,source,rawDirectory,maxBytes=1048576,fetchImpl=globalThis.fetch,...unsupported}) {
  requireThat(!Object.keys(unsupported).length,'CAPTURE_CLOCK_OVERRIDE_FORBIDDEN');
  requireThat(fetchImpl===globalThis.fetch||source.source_class==='SYNTHETIC','REAL_FETCH_OVERRIDE_FORBIDDEN');
  const u=new URL(url);
  requireThat(u.protocol==='https:'&&!u.username&&!u.password&&source.allowed_hosts.includes(u.hostname),'PUBLIC_SOURCE_URL_REJECTED');
  requireThat(!/(?:token|password|secret|credential|api_key|account)/i.test(u.search),'PUBLIC_SOURCE_URL_REJECTED');
  requireThat(Number.isSafeInteger(maxBytes)&&maxBytes>0&&maxBytes<=1048576,'CAPTURE_LIMIT_REQUIRED');
  const response=await fetchImpl(url,{redirect:'error',signal:AbortSignal.timeout(15000),headers:{Accept:'application/json,text/html'}});
  requireThat(response.ok,'PUBLIC_SOURCE_HTTP_FAILURE');
  const chunks=[];let count=0;
  for await(const chunk of response.body){count+=chunk.length;requireThat(count<=maxBytes,'RAW_TOO_LARGE');chunks.push(Buffer.from(chunk));}
  const rawBytes=Buffer.concat(chunks),retrieved_at=new Date().toISOString(),raw_sha256=rawHash(rawBytes);
  let raw_uri=`sha256-object:${raw_sha256.slice(7)}`;
  if(rawDirectory){await mkdir(rawDirectory,{recursive:true});raw_uri=path.join(rawDirectory,raw_sha256.slice(7));await writeFile(raw_uri,rawBytes,{flag:'wx'}).catch(e=>{if(e.code!=='EEXIST')throw e;});requireThat(rawHash(await readFile(raw_uri))===raw_sha256,'RAW_EXISTING_FILE_MISMATCH');}
  const capture={rawBytes,source,url,retrieved_at,raw_sha256,raw_uri,http_status:response.status,capture_scope:'PUBLIC_REFERENCE',collector_version:'p1a-public-bounded-1'};
  captures.set(capture,{retrieved_at,raw_sha256,source_hash:hashValue(source)});return capture;
}
export async function ingestSourceObservation(db,{rawBytes,source,clocks={},retrieved_at,capture=null,archived_reference=false,object_id,object_version=1,payload,original_symbol=null,trace_id}) {
  requireThat(Buffer.isBuffer(rawBytes)||rawBytes instanceof Uint8Array,'RAW_BYTES_REQUIRED');const bytes=Buffer.from(rawBytes);
  requireThat(bytes.length>0&&bytes.length<=1048576,'RAW_SIZE_INVALID');timestampMs(retrieved_at);
  requireThat(source && ['OFFICIAL','PUBLIC','SYNTHETIC'].includes(source.source_class),'SOURCE_CLASS_REQUIRED');
  if(source.source_class!=='SYNTHETIC') {
    if(archived_reference){requireThat(!clocks.available_at&&!clocks.clock_proof,'ARCHIVE_CLOCK_UNPROVEN');}
    else {const proof=captures.get(capture);requireThat(proof&&proof.retrieved_at===retrieved_at&&proof.raw_sha256===rawHash(bytes)&&proof.source_hash===hashValue(source),'REAL_CAPTURE_REQUIRED');}
  }
  requireThat(source.license_type&&Array.isArray(source.allowed_use)&&source.terms_version&&source.source_id&&source.source_version,'SOURCE_POLICY_REQUIRED');
  const p=payload??JSON.parse(bytes.toString('utf8')),c=proveClocks(bytes,source,clocks,retrieved_at),raw_sha256=rawHash(bytes);
  if(source.source_class==='SYNTHETIC')requireThat(hashValue(JSON.parse(bytes.toString('utf8')).fact)===hashValue(p),'SOURCE_PAYLOAD_RAW_MISMATCH');
  const permitted=source.allowed_use.includes('SYNTHETIC_TEST')&&source.source_class==='SYNTHETIC';
  const reasons=[...(!c.available_at?['AVAILABILITY_UNKNOWN']:[]),...(!permitted?['REFERENCE_ONLY_NOT_TRADING_LICENSE']:[])];
  await db.query("INSERT INTO p1a_data_raw(raw_sha256,raw_bytes,byte_length) VALUES($1,decode($2,'hex'),$3) ON CONFLICT(raw_sha256) DO NOTHING",[raw_sha256,bytes.toString('hex'),bytes.length]);
  return putObject(db,{object_id:object_id??`observation:${raw_sha256.slice(7)}`,object_version,kind:'SOURCE_OBSERVATION',...c,source_id:source.source_id,source_version:source.source_version,source_hash:hashValue(source),source_policy:structuredClone(source),raw_sha256,payload_sha256:hashValue(p),raw_uri:capture?.raw_uri??`sha256-object:${raw_sha256.slice(7)}`,scope:source.source_class==='SYNTHETIC'?'SYNTHETIC':'PUBLIC_REFERENCE',data_quality_status:c.available_at?'PASS':'QUARANTINED',tradeability:permitted&&c.available_at?'OFFLINE_ELIGIBLE':'NON_TRADEABLE',reason_codes:reasons,original_symbol,security_id:null,canonical_symbol:null,lineage_refs:[],trace_id,payload:p});
}
export async function verifyObservation(db,o) {
  checkObject(o);requireThat(o.kind==='SOURCE_OBSERVATION','SOURCE_OBSERVATION_REQUIRED');
  const {rows}=await db.query("SELECT encode(raw_bytes,'hex') AS hex FROM p1a_data_raw WHERE raw_sha256=$1",[o.raw_sha256]);requireThat(rows.length===1,'RAW_MISSING');
  const bytes=Buffer.from(rows[0].hex,'hex');requireThat(rawHash(bytes)===o.raw_sha256,'RAW_HASH_MISMATCH');
  if(o.source_policy.source_class==='SYNTHETIC')requireThat(hashValue(JSON.parse(bytes.toString('utf8')).fact)===o.payload_sha256,'SOURCE_PAYLOAD_RAW_MISMATCH');
  requireThat(hashValue(o.source_policy)===o.source_hash,'SOURCE_POLICY_HASH_MISMATCH');
  const c=proveClocks(bytes,o.source_policy,o,o.retrieved_at);
  requireThat(c.available_at===o.available_at&&c.clock_basis===o.clock_basis,'AVAILABLE_AT_FALSIFIED');
  requireThat(hashValue(o.payload)===o.payload_sha256,'PAYLOAD_HASH_MISMATCH');return o;
}
