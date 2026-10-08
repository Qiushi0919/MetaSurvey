import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {dataDb,createDataFixture,observation,archivedPublicObservation} from './fixtures/p1a-data/helpers.mjs';
import {parseSecuritySymbol,registerSecurity,resolveSecurity,ingestSecurityStatus,ingestSourceObservation,ingestBar,ingestSseDayK,parseSseDayKPayload,nextTradingSession,officialAutumn2026Calendar,ingestCorporateAction,ingestAdjustment,ingestFinancialRevision,financialsAsOf,freezeDataSnapshot,verifyDataSnapshot,projectDataEnvelope,ref,rawHash,capturePublicSource} from '../src/data/index.mjs';
import {hashValue} from '../src/contracts/validate.mjs';
import {derived,putObject} from '../src/data/core.mjs';
const freeze=(db,root_refs,cutoff='2026-09-30T16:00:00+08:00')=>freezeDataSnapshot(db,{root_refs,decision_cutoff:cutoff,feature_version:'synthetic-feature-1',rules_hash:hashValue('synthetic-rule-1'),scope:'SYNTHETIC',trace_id:'attack-test',frozen_at:cutoff});
async function withDb(fn){const db=await dataDb();try{await fn(db);}finally{await db.close();}}

test('P1A data: canonical representations require exchange; conflicting registry quarantines and audits',async()=>withDb(async db=>{
  for(const symbol of ['sh.600000','sh600000','600000.SH','SSE:600000'])assert.equal(parseSecuritySymbol(symbol).canonical_symbol,'SSE:600000');
  assert.throws(()=>parseSecuritySymbol('600000'),/SECURITY_EXCHANGE_AMBIGUOUS/);
  assert.equal(parseSecuritySymbol('600000','SZSE').canonical_symbol,'SZSE:600000');
  assert.throws(()=>parseSecuritySymbol('sh600000','SZSE'),/SECURITY_EXCHANGE_CONFLICT/);
  const f=await createDataFixture(db);assert.equal((await resolveSecurity(db,'sh600000',{decision_cutoff:f.cutoff})).security_id,f.security.security_id);
  await assert.rejects(resolveSecurity(db,'600000',{decision_cutoff:f.cutoff}),/SECURITY_EXCHANGE_AMBIGUOUS/);
  const conflict=await registerSecurity(db,{observation:f.securityObservation,security_id:'synthetic:imposter',original_symbol:'sh600000',listing_status:'LISTED',list_date:'1999-11-10',board:'MAIN',lot_size:100,st_status:'NORMAL',suspension_status:'TRADING',effective_from:'2026-09-20T00:00:00+08:00',name:'Synthetic security'});
  assert.equal(conflict.data_quality_status,'QUARANTINED');assert.equal(conflict.tradeability,'NON_TRADEABLE');
  assert.ok((await db.query("SELECT event_type FROM p1a_data_audit WHERE event_type='SECURITY_IDENTITY_QUARANTINED'")).rows.length);
  await assert.rejects(resolveSecurity(db,'SSE:600000',{decision_cutoff:f.cutoff}),/SECURITY_IDENTITY_CONFLICT/);assert.equal((await freeze(db,[ref(f.bar)])).reason_codes[0],'SECURITY_IDENTITY_CONFLICT');
}));
test('P1A data: known future identity/status cannot backfill past registry',async()=>withDb(async db=>{
  const f=await createDataFixture(db),later=await observation(db,{id:'source:future-status',payload:{...f.securityObservation.payload,name:'Synthetic future state',st_status:'ST',suspension_status:'SUSPENDED',effective_from:'2026-10-08T10:00:00+08:00'},at:'2026-10-08T10:00:00+08:00'});
  const future=await registerSecurity(db,{observation:later,security_id:f.security.security_id,object_version:2,original_symbol:'sh600000',listing_status:'LISTED',list_date:'1999-11-10',board:'MAIN',lot_size:100,st_status:'ST',suspension_status:'SUSPENDED',effective_from:'2026-10-08T10:00:00+08:00',name:'Synthetic future state'});
  assert.equal((await resolveSecurity(db,'sh600000',{decision_cutoff:f.cutoff})).object_version,1);
  assert.equal((await freeze(db,[ref(future)],f.cutoff)).status,'BLOCKED');
}));
test('P1A data: calendar long holiday, sessions, bounded coverage and suspension fail closed',async()=>withDb(async db=>{
  const f=await createDataFixture(db);assert.equal(nextTradingSession(f.calendar,'2026-09-30',{decision_cutoff:f.cutoff}).date,'2026-10-08');
  assert.equal(nextTradingSession(f.calendar,'2026-09-24').date,'2026-09-28');
  assert.equal(nextTradingSession(f.calendar,'2026-09-30').calendar_ref.content_hash,f.calendar.content_hash);
  assert.throws(()=>nextTradingSession(f.calendar,'2026-10-11'),/CALENDAR_COVERAGE_UNKNOWN/);
  assert.throws(()=>nextTradingSession(f.calendar,'2026-09-30',{securityStatus:{payload:{suspension_status:'UNKNOWN',st_status:'NORMAL'}}}),/SECURITY_NON_TRADEABLE/);
}));
test('P1A data: unknown availability quarantines; raw source clocks cannot be resealed into earlier visibility',async()=>withDb(async db=>{
  const f=await createDataFixture(db),unknown=await observation(db,{id:'source:unknown',payload:{fixture_kind:'SYNTHETIC'},unknown:true});
  assert.equal(unknown.available_at,null);assert.equal(unknown.tradeability,'NON_TRADEABLE');assert.equal((await freeze(db,[ref(unknown)])).status,'BLOCKED');
  const source=f.barObservation.source_policy,rawBytes=Buffer.from(JSON.stringify({published_at:'2026-10-08T00:00:00+08:00',available_at:'2026-10-08T00:00:00+08:00',fact:'future'}));
  await assert.rejects(ingestSourceObservation(db,{rawBytes,source,object_id:'source:fakeclock',payload:{fact:'future'},retrieved_at:'2026-10-08T01:00:00+08:00',trace_id:'attack',clocks:{event_time:'2026-10-08T00:00:00+08:00',published_at:'2026-10-08T00:00:00+08:00',available_at:'2026-09-01T00:00:00+08:00',publication_precision:'SECOND',clock_proof:{type:'SOURCE_FIELD',published_path:'published_at',available_path:'available_at'}}}),/AVAILABLE_AT_FALSIFIED/);
  const altered=await putObject(db,derived(f.barObservation,{kind:'BAR_1D',object_id:'synthetic:altered-clock',payload:f.bar.payload,security_id:f.security.security_id,canonical_symbol:f.security.canonical_symbol,available_at:'2026-09-01T00:00:00+08:00',lineage_refs:[ref(f.security),ref(f.calendar)],event_time:f.bar.event_time}));
  assert.equal((await freeze(db,[ref(altered)])).reason_codes[0],'DERIVED_PROVENANCE_MISMATCH');
}));
test('P1A data: real collector clock cannot be caller supplied or forged; source clock mappings remain unauthorized',async()=>withDb(async db=>{
  await assert.rejects(capturePublicSource({url:'https://example.com',source:{allowed_hosts:['example.com']},retrievedAt:'2000-01-01T00:00:00Z'}),/CAPTURE_CLOCK_OVERRIDE_FORBIDDEN/);
  const source={source_id:'official:fake',source_version:'v1',source_class:'OFFICIAL',license_type:'UNKNOWN',allowed_use:['OFFLINE_REFERENCE'],terms_version:'UNKNOWN',allowed_hosts:['example.com'],clock_policy:{type:'SOURCE_FIELD',available_path:'available_at',published_path:'published_at'}};
  const rawBytes=Buffer.from('{"published_at":"2026-09-01T00:00:00Z","available_at":"2026-09-01T00:00:00Z"}');
  await assert.rejects(ingestSourceObservation(db,{rawBytes,source,retrieved_at:'2026-09-01T00:00:00Z',capture:{retrieved_at:'2026-09-01T00:00:00Z',raw_sha256:rawHash(rawBytes),source,collector_version:'p1a-public-bounded-1'},trace_id:'attack'}),/REAL_CAPTURE_REQUIRED/);
}));
test('P1A data: substituted facts cannot inherit old raw/source clocks even with a new seal',async()=>withDb(async db=>{
  const f=await createDataFixture(db);
  await assert.rejects(ingestBar(db,{observation:f.barObservation,security:f.security,calendar:f.calendar,...f.bar.payload,close:'11.99',object_id:'synthetic:substitute'}),/NORMALIZED_FACT_SOURCE_MISMATCH/);
  const altered=await putObject(db,derived(f.barObservation,{kind:'BAR_1D',object_id:'synthetic:forged-projection',payload:{...f.bar.payload,close:'11.99'},security_id:f.security.security_id,canonical_symbol:f.security.canonical_symbol,lineage_refs:[ref(f.security),ref(f.calendar)],event_time:f.bar.event_time}));
  assert.equal((await freeze(db,[ref(altered)])).reason_codes[0],'NORMALIZED_FACT_SOURCE_MISMATCH');
}));
test('P1A data: latest visible suspension blocks resolution and snapshot; future status does not contaminate historical closure',async()=>withDb(async db=>{
  const f=await createDataFixture(db),futureFacts={canonical_symbol:f.security.canonical_symbol,effective_from:'2026-10-08T09:00:00+08:00',effective_to:null,st_status:'NORMAL',suspension_status:'SUSPENDED'};
  const futureObs=await observation(db,{id:'source:future-suspension',payload:futureFacts,at:'2026-10-08T08:00:00+08:00'});await ingestSecurityStatus(db,{observation:futureObs,security:f.security,object_id:'synthetic:status',object_version:2,...futureFacts});
  await verifyDataSnapshot(db,f.snapshot);assert.equal((await freeze(db,[ref(f.bar)])).status,'FROZEN');
  const facts={...futureFacts,effective_from:'2026-09-29T09:00:00+08:00'},obs=await observation(db,{id:'source:suspension',payload:facts,at:'2026-09-29T08:00:00+08:00'});await ingestSecurityStatus(db,{observation:obs,security:f.security,object_id:'synthetic:status',...facts});
  await assert.rejects(resolveSecurity(db,'SSE:600000',{decision_cutoff:f.cutoff}),/SECURITY_NON_TRADEABLE/);assert.equal((await freeze(db,[ref(f.bar)])).reason_codes[0],'SECURITY_NON_TRADEABLE');await assert.rejects(verifyDataSnapshot(db,f.snapshot),/SECURITY_NON_TRADEABLE/);
}));
test('P1A data: real SSE raw->staging->normalized->DQ remains explicit non-tradeable; official holiday adapters prove reference dates',async()=>withDb(async db=>{
  const f=await createDataFixture(db),real=await archivedPublicObservation(db,{name:'sse-dayk',original_symbol:'600000'}),bars=await ingestSseDayK(db,{observation:real,security:f.security,calendar:f.calendar});
  assert.equal(bars.length,2);assert.equal(bars[0].payload.open,'9.1500');assert.equal(bars[1].payload.close,'9.4800');assert.equal(bars[0].payload.amount_cents,'73974098800');
  for(const bar of bars){assert.equal(bar.available_at,null);assert.equal(bar.data_quality_status,'QUARANTINED');assert.equal(bar.tradeability,'NON_TRADEABLE');assert.ok(bar.reason_codes.includes('AVAILABILITY_UNKNOWN'));assert.equal((await freeze(db,[ref(bar)])).status,'BLOCKED');}
  const count=await db.query('SELECT count(*)::int AS n FROM p1a_data_staging');assert.equal(count.rows[0].n,3);
  for(const [prefix,exchange] of [['sse','SSE'],['szse','SZSE']]){const announcement=await archivedPublicObservation(db,{name:`${prefix}-holiday`}),sessionRule=await archivedPublicObservation(db,{name:`${prefix}-session`}),calendar=await officialAutumn2026Calendar(db,{announcement,sessionRule,exchange});assert.equal(nextTradingSession(calendar,'2026-09-30',{allow_reference:true}).date,'2026-10-08');assert.equal(calendar.available_at,null);assert.throws(()=>nextTradingSession(calendar,'2026-09-30'),/CALENDAR_REFERENCE_ONLY/);}
}));
test('P1A data: public fixtures have original byte hashes and explicit unknown license/time provenance',async()=>{
  const manifest=JSON.parse(await readFile(new URL('./fixtures/p1a-data/public-capture.json',import.meta.url)));assert.equal(manifest.fixture_kind,'PUBLIC_REFERENCE');assert.equal(manifest.license_unverified,true);
  for(const capture of manifest.captures){const bytes=await readFile(new URL(`./fixtures/p1a-data/${capture.raw_file}`,import.meta.url));assert.equal(rawHash(bytes),capture.raw_sha256);assert.ok(bytes.length<1048576);assert.equal(capture.source.license_type,'UNKNOWN');}
  const raw=await readFile(new URL('./fixtures/p1a-data/sse-dayk.json',import.meta.url));assert.equal(parseSseDayKPayload(raw).bars[0].open,'9.1500');
});
test('P1A data: adjusted bar recursively binds source/actions/security/calendar; future factor and missing lineage rejected',async()=>withDb(async db=>{
  const f=await createDataFixture(db),actionFacts={fixture_kind:'SYNTHETIC',canonical_symbol:f.security.canonical_symbol,action_type:'DIVIDEND',ex_date:'2026-09-28',effective_date:'2026-09-28',adjustment_factor:null,terms:{dividend_cents_per_share:'10'}},actionObs=await observation(db,{id:'source:action',payload:actionFacts,at:'2026-09-22T10:00:00+08:00'}),action=await ingestCorporateAction(db,{observation:actionObs,security:f.security,object_id:'synthetic:action',...actionFacts});
  const factorFacts={fixture_kind:'SYNTHETIC',canonical_symbol:f.security.canonical_symbol,factor:'0.99',method:'SYNTHETIC_EXPLICIT_FACTOR',effective_date:'2026-09-28'},futureObs=await observation(db,{id:'source:factor-future',payload:factorFacts,at:'2026-10-08T10:00:00+08:00'}),future=await ingestAdjustment(db,{observation:futureObs,security:f.security,object_id:'synthetic:adjustment-future',actions:[action],...factorFacts});
  const adjustedObs=await observation(db,{id:'source:adjusted-bar',payload:{...f.barObservation.payload,price_basis:'ADJUSTED'},at:'2026-09-29T15:01:00+08:00'});
  const bad=await ingestBar(db,{observation:adjustedObs,security:f.security,calendar:f.calendar,...f.bar.payload,object_id:'synthetic:adjusted-future',price_basis:'ADJUSTED',adjustment:future});assert.equal((await freeze(db,[ref(bad)])).reason_codes[0],'LINEAGE_AFTER_CUTOFF');
  const factorObs=await observation(db,{id:'source:factor',payload:factorFacts,at:'2026-09-28T10:00:00+08:00'}),factor=await ingestAdjustment(db,{observation:factorObs,security:f.security,object_id:'synthetic:adjustment',actions:[action],...factorFacts}),adjusted=await ingestBar(db,{observation:adjustedObs,security:f.security,calendar:f.calendar,...f.bar.payload,object_id:'synthetic:adjusted',price_basis:'ADJUSTED',adjustment:factor});
  const snap=await freeze(db,[ref(adjusted)]);assert.equal(snap.status,'FROZEN');assert.ok(snap.lineage_bundle.closure_refs.some(r=>r.object_id===action.object_id));await verifyDataSnapshot(db,snap);
  assert.equal((await freeze(db,[ref(factor)],'2026-09-24T16:00:00+08:00')).status,'BLOCKED');
  const broken=await putObject(db,derived(adjustedObs,{kind:'BAR_1D',object_id:'synthetic:missing-adjustment',payload:adjusted.payload,security_id:f.security.security_id,canonical_symbol:f.security.canonical_symbol,lineage_refs:[ref(f.security),ref(f.calendar)],event_time:f.bar.event_time}));assert.equal((await freeze(db,[ref(broken)])).reason_codes[0],'ADJUSTMENT_LINEAGE_REQUIRED');
}));
test('P1A data: financial revision filters before selection; original immutable and future restatement hidden',async()=>withDb(async db=>{
  const f=await createDataFixture(db),facts={fixture_kind:'SYNTHETIC',canonical_symbol:f.security.canonical_symbol,period:'2026-06-30',statement_type:'INCOME',revision_kind:'ORIGINAL',values_cents:{net_profit:'1000'}},firstObs=await observation(db,{id:'source:financial-1',payload:facts,at:'2026-09-21T10:00:00+08:00'}),original=await ingestFinancialRevision(db,{observation:firstObs,security:f.security,object_id:'synthetic:financial',...facts});
  const revisedFacts={...facts,revision_kind:'RESTATEMENT',values_cents:{net_profit:'500'}},nextObs=await observation(db,{id:'source:financial-2',payload:revisedFacts,at:'2026-10-08T10:00:00+08:00'}),revision=await ingestFinancialRevision(db,{observation:nextObs,security:f.security,object_id:original.object_id,object_version:2,...revisedFacts,previous_revision:original});
  const query={security_id:f.security.security_id,period:'2026-06-30',statement_type:'INCOME'};assert.equal((await financialsAsOf(db,{...query,decision_cutoff:f.cutoff})).content_hash,original.content_hash);
  assert.equal((await financialsAsOf(db,{...query,decision_cutoff:'2026-10-08T12:00:00+08:00'})).content_hash,revision.content_hash);
  assert.equal((await freeze(db,[ref(revision)])).status,'BLOCKED');await assert.rejects(db.query('UPDATE p1a_data_objects SET content_hash=$1 WHERE object_id=$2',[hashValue('altered'),original.object_id]),/APPEND_ONLY_HISTORY/);
  assert.equal((await financialsAsOf(db,{...query,decision_cutoff:'2026-09-20T12:00:00+08:00'})),null);
}));
test('P1A data: factor wire values reject Infinity/NaN/exponents/overprecision and read-back forged values',async()=>withDb(async db=>{
  const f=await createDataFixture(db);
  for(const value of ['Infinity','NaN','1e0','-0','0','0.00000000001','9'.repeat(43)]){
    const facts={canonical_symbol:f.security.canonical_symbol,action_type:'DIVIDEND',ex_date:'2026-09-28',effective_date:'2026-09-28',adjustment_factor:value,terms:{}};
    const source=await observation(db,{id:`source:bad-factor:${value}`,payload:facts,at:'2026-09-22T10:00:00+08:00'});
    await assert.rejects(ingestCorporateAction(db,{observation:source,security:f.security,object_id:`synthetic:bad-factor:${value}`,...facts}),/ADJUSTMENT_FACTOR_INVALID/);
  }
  const facts={canonical_symbol:f.security.canonical_symbol,factor:'Infinity',method:'SYNTHETIC_FACTOR',effective_date:'2026-09-28'},obs=await observation(db,{id:'source:forged-factor',payload:facts,at:'2026-09-28T10:00:00+08:00'});
  const forged=await putObject(db,derived(obs,{kind:'ADJUSTMENT',object_id:'synthetic:forged-factor',payload:{...facts,action_refs:[]},security_id:f.security.security_id,canonical_symbol:f.security.canonical_symbol,lineage_refs:[ref(f.security)],event_time:'2026-09-28T00:00:00+08:00'}));
  assert.equal((await freeze(db,[ref(forged)])).reason_codes[0],'ADJUSTMENT_FACTOR_INVALID');
}));
test('P1A data: content addressed snapshot closes evidence; one byte mutation changes hash and rejects old snapshot',async()=>{
  const a=await dataDb(),b=await dataDb();try{const x=await createDataFixture(a),y=await createDataFixture(b,{barClose:'10.01'});assert.equal(x.snapshot.status,'FROZEN');assert.equal(y.snapshot.status,'FROZEN');assert.notEqual(x.barObservation.raw_sha256,y.barObservation.raw_sha256);assert.notEqual(x.snapshot.manifest.data_hash,y.snapshot.manifest.data_hash);await verifyDataSnapshot(a,x.snapshot);await assert.rejects(verifyDataSnapshot(b,x.snapshot),/LINEAGE_MISSING|LINEAGE_REF_HASH_MISMATCH/);const changed=structuredClone(x.snapshot);changed.lineage_bundle.feature_version='changed';await assert.rejects(verifyDataSnapshot(a,changed),/SNAPSHOT_MUTATION/);assert.equal(projectDataEnvelope(x.bar).payload_hash,x.bar.payload_sha256);}finally{await a.close();await b.close();}
});
test('P1A data: every new persistence family rejects truncation and retains actual source/hash/time/security/version/trace',async()=>withDb(async db=>{
  const f=await createDataFixture(db);
  for(const table of ['p1a_data_raw','p1a_data_objects','p1a_data_staging','p1a_data_audit'])await assert.rejects(db.exec(`TRUNCATE ${table} CASCADE`),/APPEND_ONLY_HISTORY/);
  const {rows}=await db.query("SELECT source_id,source_hash,event_time,retrieved_at,security_id,object_version,trace_id FROM p1a_data_objects WHERE kind='BAR_1D'");assert.equal(rows.length,1);for(const field of ['source_id','source_hash','event_time','retrieved_at','security_id','object_version','trace_id'])assert.ok(rows[0][field]);await verifyDataSnapshot(db,f.snapshot);
}));
