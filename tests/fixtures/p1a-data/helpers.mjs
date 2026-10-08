import {PGlite} from '@electric-sql/pglite';
import {readFile} from 'node:fs/promises';
import {migrate} from '../../../src/baseline/migrate.mjs';
import {hashValue} from '../../../src/contracts/validate.mjs';
import {ingestSourceObservation,registerSecurity,ingestCalendar,ingestBar,freezeDataSnapshot,ref} from '../../../src/data/index.mjs';

export async function dataDb(){const db=new PGlite();await migrate(db);return db;}
export async function observation(db,{id,payload,at='2026-09-20T00:00:00+08:00',available=at,retrieved=available,unknown=false,version=1}={}) {
  const source={source_id:'synthetic:p1a-data',source_version:'synthetic-source-1',source_class:'SYNTHETIC',license_type:'SYNTHETIC_TEST',allowed_use:['SYNTHETIC_TEST'],terms_version:'synthetic-test-only-1',data_class:'SYNTHETIC',allowed_hosts:[],clock_policy:{type:'SOURCE_FIELD',available_path:'available_at',published_path:'published_at'}};
  const rawBytes=Buffer.from(JSON.stringify({published_at:at,available_at:available,fact:payload}));
  return ingestSourceObservation(db,{rawBytes,source,object_id:id,object_version:version,retrieved_at:retrieved,payload,trace_id:'synthetic-data-fixture',clocks:{event_time:at,published_at:at,publication_precision:'SECOND',...(unknown?{}:{clock_proof:{type:'SOURCE_FIELD',available_path:'available_at',published_path:'published_at'}})}});
}
export async function createDataFixture(db,{suffix='',barClose='10.00',barDate='2026-09-29',cutoff='2026-09-30T16:00:00+08:00',feature_version='synthetic-feature-1'}={}) {
  const securityFacts={fixture_kind:'SYNTHETIC',original_symbol:'sh.600000',name:'Synthetic security',listing_status:'LISTED',list_date:'1999-11-10',delist_date:null,board:'MAIN',lot_size:100,st_status:'NORMAL',suspension_status:'TRADING',effective_from:'2026-09-20T00:00:00+08:00',effective_to:null};
  const securityObservation=await observation(db,{id:`source:security${suffix}`,payload:securityFacts});
  const security=await registerSecurity(db,{observation:securityObservation,security_id:`synthetic:600000${suffix}`,original_symbol:'sh.600000',listing_status:'LISTED',list_date:'1999-11-10',board:'MAIN',lot_size:100,st_status:'NORMAL',suspension_status:'TRADING',effective_from:'2026-09-20T00:00:00+08:00',name:'Synthetic security'});
  const sessions=[{kind:'AM',open:'09:30:00',close:'11:30:00'},{kind:'PM',open:'13:00:00',close:'15:00:00'}];
  const days=[];for(let ms=Date.parse('2026-09-20T00:00:00Z');ms<=Date.parse('2026-10-11T00:00:00Z');ms+=86400000){const d=new Date(ms),date=d.toISOString().slice(0,10),non=[0,6].includes(d.getUTCDay())||(date>='2026-09-25'&&date<='2026-09-27')||(date>='2026-10-01'&&date<='2026-10-07');days.push({date,status:non?'NON_TRADING':'TRADING',sessions:non?[]:sessions,reason:'SYNTHETIC_EXPLICIT_FIXTURE'});}
  const calendarObservation=await observation(db,{id:`source:calendar${suffix}`,payload:{fixture_kind:'SYNTHETIC',days,exchange:'SSE',coverage_start:'2026-09-20',coverage_end:'2026-10-11',session_rule_version:'synthetic-sessions-1'}});
  const calendar=await ingestCalendar(db,{observation:calendarObservation,calendar_id:`synthetic:calendar${suffix}`,exchange:'SSE',days,coverage_start:'2026-09-20',coverage_end:'2026-10-11',session_rule_version:'synthetic-sessions-1'});
  const barPayload={fixture_kind:'SYNTHETIC',canonical_symbol:security.canonical_symbol,trade_date:barDate,open:'10.00',high:'12.00',low:'8.00',close:barClose,preclose:'10.00',volume:1000,amount_cents:'1000000',price_basis:'RAW'};
  const barObservation=await observation(db,{id:`source:bar${suffix}`,payload:barPayload,at:`${barDate}T15:01:00+08:00`});
  const bar=await ingestBar(db,{observation:barObservation,security,calendar,...barPayload,object_id:`synthetic:bar${suffix}`});
  const snapshot=await freezeDataSnapshot(db,{root_refs:[ref(bar)],decision_cutoff:cutoff,feature_version,rules_hash:hashValue('synthetic-rule-1'),scope:'SYNTHETIC',trace_id:'synthetic-snapshot-fixture',frozen_at:cutoff});
  return {securityObservation,security,calendarObservation,calendar,barObservation,bar,snapshot,cutoff};
}
export async function archivedPublicObservation(db,{name,id,payload,original_symbol=null}) {
  const manifest=JSON.parse(await readFile(new URL('./public-capture.json',import.meta.url))),entry=manifest.captures.find(x=>x.name===name),rawBytes=await readFile(new URL(`./${entry.raw_file}`,import.meta.url));
  return ingestSourceObservation(db,{rawBytes,source:entry.source,object_id:id??`archived:${name}`,payload:payload??entry.payload,original_symbol,trace_id:'archived-public-reference',retrieved_at:entry.retrieved_at,archived_reference:true,clocks:{event_time:null,published_at:entry.published_at??null,publication_precision:entry.published_at?'DATE_ONLY':'UNKNOWN'}});
}
