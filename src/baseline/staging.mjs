import { validateContract, requireThat, canonical, hashValue, sealContract } from '../contracts/validate.mjs';

function rejectSensitive(value) {
  if (!value || typeof value!=='object') return;
  for (const [key,item] of Object.entries(value)) {
    if (key==='contains_account_identity_or_credentials' && item===false) continue;
    requireThat(!/(?:credential|password|access_token|api_key|private_key|secret)/i.test(key),'SENSITIVE_FIXTURE_REJECTED');
    rejectSensitive(item);
  }
}

/** Explicit fixture import only; it cannot write normalized orders/fills/positions/ledger. */
export async function stageContractFixture(db, object, {fixtureKind, calendar=[]} = {}) {
  requireThat(['SYNTHETIC','LEGACY'].includes(fixtureKind),'FIXTURE_KIND_REQUIRED');
  validateContract(object?.contract_name,object,{calendar}); rejectSensitive(object);
  requireThat(object.mode!=='PROD','PRODUCTION_DISABLED_P0');
  requireThat(fixtureKind!=='SYNTHETIC' || object.provenance.visibility_basis==='SYNTHETIC','SYNTHETIC_FIXTURE_ONLY');
  requireThat(fixtureKind!=='LEGACY' || object.provenance.source_id.startsWith('legacy:'),'LEGACY_EXPERIMENT_ONLY');
  const p=object.provenance;
  await db.query(`INSERT INTO contract_records (
    contract_name,contract_version,object_id,object_version,content_hash,trace_id,recorded_at,business_timezone,
    mode,account_id,strategy_id,event_time,published_at,publication_precision,available_at,retrieved_at,
    source_id,source_version,source_hash,visibility_basis,reason_codes,fixture_kind,payload
  ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21::jsonb,$22,$23::jsonb)`,[
    object.contract_name,object.contract_version,object.object_id,object.object_version,object.content_hash,object.trace_id,object.recorded_at,object.business_timezone,
    object.mode??null,object.account_id??null,object.strategy_id??null,p.event_time,p.published_at,p.publication_precision,p.available_at,p.retrieved_at,
    p.source_id,p.source_version,p.source_hash,p.visibility_basis,canonical(object.reason_codes),fixtureKind,canonical(object),
  ]);
  return {status:'QUARANTINED',normalized_tables_written:false,production_execution_enabled:false,content_hash:object.content_hash};
}

export async function readContractFixture(db,name,id,version,context={}) {
  const {rows}=await db.query('SELECT payload FROM contract_records WHERE contract_name=$1 AND object_id=$2 AND object_version=$3',[name,id,version]);
  requireThat(rows.length===1,'MISSING_EVIDENCE');
  return validateContract(name,rows[0].payload,context);
}

/** Preserve a legacy payload as opaque evidence, without assigning a trading namespace. */
export function legacyEvidenceEnvelope({base,assetId,sourceHash,locator,payload}) {
  requireThat(base.provenance.source_id.startsWith('legacy:'),'LEGACY_EXPERIMENT_ONLY');
  rejectSensitive(payload);
  return sealContract({...base,contract_name:'DataEnvelope',entity_id:assetId,data_kind:'LEGACY_FIXTURE',symbols:[],raw_uri:locator,raw_hash:sourceHash,payload,payload_hash:hashValue(payload),data_quality:'UNKNOWN',adjustment:'NOT_APPLICABLE',adjustment_version:'NOT_APPLICABLE',source_revision:base.provenance.source_version});
}
