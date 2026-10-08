import { createHash } from 'node:crypto';
import { canonical, hashValue, requireThat, timestampMs } from '../contracts/validate.mjs';

export { canonical, hashValue, requireThat, timestampMs };
export const rawHash = bytes => `sha256:${createHash('sha256').update(bytes).digest('hex')}`;
export const ref = o => ({object_id:o.object_id,object_version:o.object_version,content_hash:o.content_hash});
export const reseal = object => { const copy=structuredClone(object);delete copy.content_hash;return {...copy,content_hash:hashValue(copy)}; };
export function checkObject(o) {requireThat(o&&o.content_hash===reseal(o).content_hash,'DATA_CONTENT_HASH_MISMATCH');return o;}
export function assertFacts(observation,facts) {for(const [key,value] of Object.entries(facts))requireThat(observation.payload[key]!==undefined&&canonical(observation.payload[key])===canonical(value),'NORMALIZED_FACT_SOURCE_MISMATCH');}
export function assertPositiveDecimal(value) {requireThat(typeof value==='string'&&value.length<=42&&/^(0|[1-9]\d*)(\.\d{1,10})?$/.test(value)&&/[1-9]/.test(value),'ADJUSTMENT_FACTOR_INVALID');}
export function assertDate(value) {requireThat(typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(`${value}T00:00:00Z`))&&new Date(`${value}T00:00:00Z`).toISOString().slice(0,10)===value,'CALENDAR_DATE_INVALID');}
export function rejectSensitive(value) {
  if (!value || typeof value!=='object') return;
  for(const [key,item] of Object.entries(value)) {
    requireThat(!/(?:password|token|credential|secret|api_key|account_number)/i.test(key),'SENSITIVE_DATA_REJECTED');rejectSensitive(item);
  }
}
export async function readObject(db,r) {
  requireThat(r && Number.isSafeInteger(r.object_version) && r.object_version>0,'LINEAGE_REF_INVALID');
  const {rows}=await db.query('SELECT payload FROM p1a_data_objects WHERE object_id=$1 AND object_version=$2',[r.object_id,r.object_version]);
  requireThat(rows.length===1,'LINEAGE_MISSING');const o=checkObject(rows[0].payload);
  requireThat(o.content_hash===r.content_hash,'LINEAGE_REF_HASH_MISMATCH');return o;
}
export async function readRaw(db,o) {
  const {rows}=await db.query("SELECT encode(raw_bytes,'hex') AS hex FROM p1a_data_raw WHERE raw_sha256=$1",[o.raw_sha256]);
  requireThat(rows.length===1,'RAW_MISSING');const bytes=Buffer.from(rows[0].hex,'hex');
  requireThat(rawHash(bytes)===o.raw_sha256,'RAW_HASH_MISMATCH');return bytes;
}
export async function audit(db,type,o,reasons=[]) {
  const event={event_type:type,object_ref:o?ref(o):null,source_id:o?.source_id??'p1a:data',source_hash:o?.source_hash??hashValue('p1a:data'),event_time:o?.retrieved_at??new Date().toISOString(),security_id:o?.security_id??null,version:String(o?.object_version??1),trace_id:o?.trace_id??'p1a:data',reason_codes:reasons};
  const event_hash=hashValue(event);
  await db.query(`INSERT INTO p1a_data_audit(event_hash,event_type,object_ref,source_id,source_hash,event_time,security_id,version,trace_id,reason_codes,event) VALUES ($1,$2,$3::jsonb,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb) ON CONFLICT(event_hash) DO NOTHING`,[event_hash,type,canonical(event.object_ref),event.source_id,event.source_hash,event.event_time,event.security_id,event.version,event.trace_id,canonical(reasons),canonical(event)]);
}
export async function putObject(db,input) {
  rejectSensitive(input);const o=reseal(input);checkObject(o);
  requireThat(Number.isSafeInteger(o.object_version)&&o.object_version>0,'OBJECT_VERSION_INVALID');
  timestampMs(o.retrieved_at);if(o.available_at)requireThat(timestampMs(o.available_at)<=timestampMs(o.retrieved_at),'AVAILABLE_AFTER_RETRIEVAL');
  const {rows}=await db.query('SELECT content_hash FROM p1a_data_objects WHERE object_id=$1 AND object_version=$2',[o.object_id,o.object_version]);
  if(rows.length){requireThat(rows[0].content_hash===o.content_hash,'OBJECT_VERSION_CONFLICT');return o;}
  await db.query(`INSERT INTO p1a_data_objects(object_id,object_version,content_hash,kind,source_id,source_version,source_hash,raw_sha256,payload_sha256,event_time,published_at,available_at,retrieved_at,publication_precision,clock_basis,scope,security_id,canonical_symbol,original_symbol,data_quality_status,tradeability,reason_codes,lineage_refs,trace_id,payload) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22::jsonb,$23::jsonb,$24,$25::jsonb)`,[o.object_id,o.object_version,o.content_hash,o.kind,o.source_id,o.source_version,o.source_hash,o.raw_sha256,o.payload_sha256,o.event_time,o.published_at,o.available_at,o.retrieved_at,o.publication_precision,o.clock_basis,o.scope,o.security_id??null,o.canonical_symbol??null,o.original_symbol??null,o.data_quality_status,o.tradeability,canonical(o.reason_codes),canonical(o.lineage_refs),o.trace_id,canonical(o)]);
  await audit(db,`${o.kind}_PERSISTED`,o,o.reason_codes);return o;
}
export function derived(observation,{kind,object_id,object_version=1,payload,lineage_refs=[],...fields}) {
  checkObject(observation);const {content_hash,...base}=observation;
  return {...base,kind,object_id,object_version,payload,payload_sha256:hashValue(payload),lineage_refs:[ref(observation),...lineage_refs],...fields};
}
export async function allKind(db,kind) {const {rows}=await db.query('SELECT payload FROM p1a_data_objects WHERE kind=$1 ORDER BY object_id,object_version',[kind]);return rows.map(r=>checkObject(r.payload));}
