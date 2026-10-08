import {readFile} from 'node:fs/promises';
import {PGlite} from '@electric-sql/pglite';
import {hashValue} from '../src/contracts/validate.mjs';
import {sealCostProfile} from '../src/cost/index.mjs';
import {createPaperService,sealReferenceObject,orderTermsHash} from '../src/paper/index.mjs';
export const fixture=JSON.parse(await readFile(new URL('./fixtures/p1a-paper/baseline.json',import.meta.url),'utf8'));
export const T=fixture.event_time,DAY2='2025-04-11T02:00:00Z';
export const profile=sealCostProfile(fixture.cost_profile);
export const calendar=sealReferenceObject({...fixture.calendar,source:{...fixture.calendar.source,source_hash:hashValue({fixture:'calendar'})}});
export const security=sealReferenceObject(fixture.security);
export async function database(directory){const db=new PGlite(directory);await db.waitReady;for(const n of ['001_schema_v1.sql','002_contract_registry.sql','004_p1a_paper.sql'])await db.exec(await readFile(new URL(`../migrations/${n}`,import.meta.url),'utf8'));return db;}
export function createIntent({id='o1',account_id='SYNTHETIC_ACCOUNT',side='BUY',strategy='CORE_40',quantity=200,limit_price='10',time=T,trade_date=time.slice(0,10),cost=profile,calendar_ref=calendar,security_ref=security,...rest}={}){
  return{contract_name:'PaperReplayOrderIntent',contract_version:'1.0.0',fixture_scope:'SYNTHETIC_TEST_ONLY',mode:'PAPER',account_id,order_id:id,client_order_id:`client-${id}`,strategy,symbol:security_ref.canonical_symbol,side,quantity,limit_price,trade_date,rule_version:'SYNTHETIC_RULE_1',snapshot_hash:hashValue({snapshot:1}),feature_hash:hashValue({feature:1}),cost_version:cost.object_version,cost_profile_hash:cost.content_hash,calendar_hash:calendar_ref.content_hash,security_hash:security_ref.content_hash,market_data_at:time,valid_until:'2025-04-17T00:00:00Z',...rest};
}
export function reserveInput(intent,{cost_profile=profile,security_ref=security,calendar_ref=calendar,time=intent.market_data_at,key=`reserve-${intent.order_id}`,trace_id='fixture-trace'}={}){
  const a=hashValue({kind:'decision',id:intent.order_id}),b=hashValue({kind:'confirmation',terms:orderTermsHash(intent)});
  return{mode:'PAPER',account_id:intent.account_id,idempotency_key:key,event_time:time,trace_id,intent,cost_profile,security:security_ref,calendar:calendar_ref,authorization:{kind:'FIXTURE_HUMAN_CONFIRMATION',scope:'SYNTHETIC_TEST_ONLY',actor_type:'HUMAN_USER',order_terms_hash:orderTermsHash(intent),decision_approval_hash:a,final_confirmation_hash:b},authority:{scope:'SYNTHETIC_TEST_ONLY',actor_type:'HUMAN_USER',verified_approval_hashes:new Set([a,b])}};
}
export function operation(intent,{key,event_time=intent.market_data_at,...rest}={}){return{mode:'PAPER',account_id:intent.account_id,order_id:intent.order_id,strategy:intent.strategy,symbol:intent.symbol,idempotency_key:key,event_time,trace_id:'fixture-trace',...rest};}
export async function open(service,{account_id='SYNTHETIC_ACCOUNT',opening_cash_cents=fixture.opening_cash_cents,event_time=T}={}){return service.openAccount({mode:'PAPER',account_id,opening_cash_cents,event_time,trace_id:'fixture-trace',fixture_scope:'SYNTHETIC_TEST_ONLY',source_ref:{content_hash:hashValue({opening:'synthetic'})}});}
export async function setup(options={}){const db=await database();const service=createPaperService({db});await open(service,options);return{db,service};}
export {createPaperService};
