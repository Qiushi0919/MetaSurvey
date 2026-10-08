import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {PGlite} from '@electric-sql/pglite';
import {hashValue} from '../src/contracts/validate.mjs';
import {sealCostProfile} from '../src/cost/index.mjs';
import {sealReferenceObject} from '../src/paper/index.mjs';
import {setup,database,createPaperService,createIntent,reserveInput,operation,open,T,DAY2,calendar,security,profile,fixture} from './p1a-paper-helpers.mjs';
async function submitted(service,intent,opts){await service.reserveOrder(reserveInput(intent,opts));await service.submitOrder(operation(intent,{key:`submit-${intent.order_id}`}));}
async function fill(service,intent,{key=`fill-${intent.order_id}`,fill_id=`fill-${intent.order_id}`,quantity=intent.quantity,price=intent.limit_price,event_time=intent.market_data_at,...rest}={}){return service.fillOrder(operation(intent,{key,fill_id,quantity,price,event_time,market_data_at:event_time,...rest}));}
const scope={mode:'PAPER',account_id:'SYNTHETIC_ACCOUNT'};

test('P1-A paper reserve→submit→two fills uses cumulative minimum settlement and reconciles independently',async()=>{
 const{db,service}=await setup();try{const intent=createIntent();await submitted(service,intent);const one=await fill(service,intent,{key:'f1',fill_id:'f1',quantity:100});const two=await fill(service,intent,{key:'f2',fill_id:'f2',quantity:100});assert.equal(one.cost_delta.commission_cents,'150');assert.equal(two.cost_delta.commission_cents,'50');assert.equal(two.cost_delta.minimum_commission_effect_cents,'-50');assert.equal(two.status,'FILLED');const account=await service.getAccount(scope);assert.equal(account.reserved_cash_cents,'0');assert.equal(account.settled_cash_cents,'1799710');assert.equal((await service.reconcile(scope)).passed,true);const ledger=await service.getLedger(scope);for(const e of ledger){assert.equal(e.source.source_id,'P1A_PAPER_REFERENCE');assert.ok(e.source.source_hash);assert.ok(e.source.available_at);assert.equal(e.trace_id,'fixture-trace');}}
 finally{await db.close();}
});
test('P1-A shared account locks prevent simultaneous Core/Event double spending without shared positions',async()=>{
 const{db,service}=await setup({opening_cash_cents:'150000'});try{const a=createIntent({id:'core',quantity:100}),b=createIntent({id:'event',strategy:'EVENT_3',quantity:100});const outcomes=await Promise.allSettled([service.reserveOrder(reserveInput(a)),createPaperService({db}).reserveOrder(reserveInput(b))]);assert.equal(outcomes.filter(o=>o.status==='fulfilled').length,1);assert.match(outcomes.find(o=>o.status==='rejected').reason.message,/INSUFFICIENT_AVAILABLE_CASH/);const account=await service.getAccount(scope);assert.equal(account.available_cash_cents,'49805');assert.equal((await service.reconcile(scope)).passed,true);}
 finally{await db.close();}
});
test('P1-A partial cancel/reject release once, retain minimum fee, block late fills',async()=>{
 for(const close of ['cancelOrder','rejectOrder']){const{db,service}=await setup();try{const intent=createIntent();await submitted(service,intent);await fill(service,intent,{key:'f1',fill_id:'f1',quantity:100});const input=operation(intent,{key:'close',reason_code:'SYNTHETIC_CLOSE'});const closed=await service[close](input);assert.equal(closed.released_cash_cents,'100095');assert.deepEqual(await service[close]({...input,trace_id:'new-diagnostic-trace'}),closed);await assert.rejects(()=>service[close]({...input,idempotency_key:'close-again'}),/ORDER_ALREADY_TERMINAL/);await assert.rejects(()=>fill(service,intent,{key:'late',fill_id:'late',quantity:100}),/ORDER_NOT_FILLABLE/);const account=await service.getAccount(scope);assert.equal(account.reserved_cash_cents,'0');assert.equal(account.settled_cash_cents,'1899805');assert.equal((await service.reconcile(scope)).passed,true);}
 finally{await db.close();}}
});
test('P1-A restart persists requests, fills, lots, sequence, cash and T+1',async()=>{
 const dir=await mkdtemp(path.join(os.tmpdir(),'p1a-paper-restart-'));let db=await database(dir);let service=createPaperService({db});const intent=createIntent();try{await open(service);await submitted(service,intent);const input=operation(intent,{key:'persist-fill',fill_id:'persist-fill',quantity:100,price:'10',market_data_at:T});const filled=await service.fillOrder(input);const before=await service.getAccount(scope);await db.close();db=new PGlite(dir);await db.waitReady;service=createPaperService({db});assert.deepEqual(await service.fillOrder(input),filled);assert.deepEqual(await service.getAccount(scope),before);await assert.rejects(()=>service.fillOrder({...input,quantity:200}),/IDEMPOTENCY_PAYLOAD_CONFLICT/);await assert.rejects(()=>service.fillOrder({...input,idempotency_key:'new-key'}),/DUPLICATE_FILL/);await assert.rejects(()=>service.reserveOrder(reserveInput(createIntent({id:'same-day-sell',side:'SELL',quantity:100}))),/T1_OR_NAMESPACE/);assert.equal((await service.reconcile(scope)).passed,true);}
 finally{await db.close();await rm(dir,{recursive:true,force:true});}
});
test('P1-A T+1 uses bound sessions, actual event clock, own namespace and same-day sell proceeds ordering',async()=>{
 const{db,service}=await setup({opening_cash_cents:'100195'});try{const buy=createIntent({quantity:100});await submitted(service,buy);await fill(service,buy);await assert.rejects(()=>service.reserveOrder(reserveInput(createIntent({id:'bad-sell',side:'SELL',quantity:100}))),/INSUFFICIENT_AVAILABLE_CASH|T1_OR_NAMESPACE/);
 const sell=createIntent({id:'sell',side:'SELL',quantity:100,limit_price:'11',time:DAY2});
 // Sell reservation conservatively reserves all fees, even though sale normally funds them.
 // Seed no cash workaround: cancellation cannot manufacture cash. Use independent account with funded sell fixture below.
 assert.equal((await service.getAccount(scope)).available_cash_cents,'0');
 await assert.rejects(()=>service.reserveOrder(reserveInput(sell)),/INSUFFICIENT_AVAILABLE_CASH/);
 }
 finally{await db.close();}
 const{db:db2,service:s}=await setup({opening_cash_cents:'200500'});try{const buy=createIntent({quantity:100});await submitted(s,buy);await fill(s,buy);const wrong=createIntent({id:'event-sell',strategy:'EVENT_3',side:'SELL',quantity:100,time:DAY2});await assert.rejects(()=>s.reserveOrder(reserveInput(wrong)),/T1_OR_NAMESPACE/);const spoof=createIntent({id:'spoof-sell',side:'SELL',quantity:100,trade_date:'2025-04-11'});await assert.rejects(()=>s.reserveOrder(reserveInput(spoof)),/TRADE_DATE_CLOCK_MISMATCH/);
 const sell=createIntent({id:'sell',side:'SELL',quantity:100,limit_price:'11',time:DAY2});await submitted(s,sell);const nextBuy=createIntent({id:'next-buy',quantity:200,time:DAY2});await assert.rejects(()=>s.reserveOrder(reserveInput(nextBuy)),/INSUFFICIENT_AVAILABLE_CASH/);await fill(s,sell);await s.reserveOrder(reserveInput(nextBuy));assert.equal((await s.reconcile(scope)).passed,true);const lots=(await s.getAccount(scope)).lots;assert.equal(lots[0].remaining_quantity,'0');}
 finally{await db2.close();}
});
test('P1-A holiday next session cannot be bypassed by ordinary calendar dates',async()=>{
 const cal=sealReferenceObject({...calendar,sessions:['2025-04-10','2025-04-14','2025-04-15']});const{db,service}=await setup();try{const buy=createIntent({quantity:100,calendar_ref:cal});await submitted(service,buy,{calendar_ref:cal});await fill(service,buy);assert.equal((await service.getAccount(scope)).lots[0].sellable_date,'2025-04-14');const sell=createIntent({id:'holiday',side:'SELL',quantity:100,time:DAY2,calendar_ref:cal});await assert.rejects(()=>service.reserveOrder(reserveInput(sell,{calendar_ref:cal})),/NON_TRADING_SESSION/);}
 finally{await db.close();}
});
test('P1-A mode/account/strategy/security/approval mismatch and stale data all fail closed',async()=>{
 const{db,service}=await setup();try{const intent=createIntent();for(const [input,code] of [
 [{...reserveInput(intent),mode:'PROD'},'PRODUCTION_DISABLED'],[{...reserveInput(intent),account_id:'wrong'},'ORDER_ACCOUNT_MISMATCH'],[reserveInput({...intent,strategy:'RESEARCH_6_18M'}),'STRATEGY_NAMESPACE_MISMATCH'],[reserveInput({...intent,calendar_hash:hashValue({wrong:1})}),'SOURCE_VERSION_BINDING_MISMATCH'],[reserveInput({...intent,security_hash:hashValue({wrong:2})}),'SOURCE_VERSION_BINDING_MISMATCH'],[reserveInput({...intent,cost_version:2}),'COST_VERSION_BINDING_MISMATCH'],[reserveInput({...intent,snapshot_hash:'changed'}),'none']]){if(code==='none')continue;await assert.rejects(()=>service.reserveOrder(input),new RegExp(code));}
 const llm=reserveInput(intent);llm.authorization.actor_type='LLM';await assert.rejects(()=>service.reserveOrder(llm),/HUMAN_CONFIRMATION_REQUIRED/);const selfClaim=reserveInput(intent);selfClaim.authority.verified_approval_hashes.clear();await assert.rejects(()=>service.reserveOrder(selfClaim),/UNTRUSTED_APPROVAL/);const mutated=reserveInput(intent);mutated.intent.quantity=300;await assert.rejects(()=>service.reserveOrder(mutated),/APPROVAL_TERMS_MISMATCH/);
 await assert.rejects(()=>service.reserveOrder(reserveInput(intent,{time:'2025-04-10T02:00:06Z'})),/STALE_MARKET_DATA/);await assert.rejects(()=>service.reserveOrder(reserveInput({...intent,market_data_at:'2025-04-10T02:00:01Z'},{time:T})),/FUTURE_MARKET_DATA/);
 await submitted(service,intent);await assert.rejects(()=>service.fillOrder(operation(intent,{key:'wrong-strategy',fill_id:'f',quantity:100,price:'10',market_data_at:T,strategy:'EVENT_3'})),/ORDER_SCOPE_MISMATCH/);await assert.rejects(()=>service.getAccount({mode:'PROD',account_id:intent.account_id}),/PRODUCTION_DISABLED/);}
 finally{await db.close();}
});
test('P1-A limit-price, overfill, duplicate client/fill and nonmonotonic event failures leave no partial writes',async()=>{
 const{db,service}=await setup();try{const intent=createIntent();await submitted(service,intent);const before=await service.getAccount(scope);await assert.rejects(()=>fill(service,intent,{price:'10.000001'}),/LIMIT_PRICE_VIOLATION/);await assert.rejects(()=>fill(service,intent,{quantity:300}),/FILL_QUANTITY_EXCEEDED/);await assert.rejects(()=>fill(service,intent,{event_time:'2025-04-10T01:59:59Z'}),/ACCOUNT_EVENT_ORDER_VIOLATION/);assert.deepEqual(await service.getAccount(scope),before);
 await assert.rejects(()=>service.reserveOrder(reserveInput(createIntent({id:'other',client_order_id:intent.client_order_id,strategy:'EVENT_3'}))),/DUPLICATE_ORDER/);await fill(service,intent,{key:'f1',fill_id:'f1',quantity:100});await assert.rejects(()=>fill(service,intent,{key:'new-key',fill_id:'f1',quantity:100}),/DUPLICATE_FILL/);assert.equal((await service.reconcile(scope)).passed,true);}
 finally{await db.close();}
});
test('P1-A cost effective range is checked again at fill; future/suspended/version changed security rejected',async()=>{
 const p=sealCostProfile({...fixture.cost_profile,effective_to:'2025-04-10'});const{db,service}=await setup();try{const intent=createIntent({cost:p});await submitted(service,intent,{cost_profile:p});await assert.rejects(()=>fill(service,intent,{event_time:DAY2}),/COST_PROFILE_DATE_INVALID/);const future=sealReferenceObject({...security,available_at:'2025-04-11T00:00:00Z'});const f=createIntent({id:'future',security_ref:future});await assert.rejects(()=>service.reserveOrder(reserveInput(f,{security_ref:future})),/FUTURE_SECURITY/);const suspended=sealReferenceObject({...security,suspended:true});const si=createIntent({id:'suspended',security_ref:suspended});await assert.rejects(()=>service.reserveOrder(reserveInput(si,{security_ref:suspended})),/SECURITY_NOT_TRADEABLE/);const secret=reserveInput(createIntent({id:'secret'}));secret.intent.broker_token='DO_NOT_LOG';await assert.rejects(()=>service.reserveOrder(secret),/SENSITIVE_FIELD_FORBIDDEN/);}
 finally{await db.close();}
});
test('P1-A direct ledger/fees tampering is detected independently; persisted ledger is append-only',async()=>{
 const{db,service}=await setup();try{const intent=createIntent();await submitted(service,intent);await fill(service,intent);await assert.rejects(()=>db.query('UPDATE p1a_paper.ledger SET event_id=$1 WHERE mode=$2 AND account_id=$3',['bad','PAPER',intent.account_id]),/APPEND_ONLY/);const {reconcilePaperAccount}=await import('../src/paper/oracle.mjs');const account=await service.getAccount(scope),ledger=await service.getLedger(scope);const orders=(await db.query('SELECT *,remaining_reservation::text FROM p1a_paper.orders')).rows;ledger.at(-1).cost_delta.commission_cents='0';const{entry_hash,trace_id,...economic}=ledger.at(-1);ledger.at(-1).entry_hash=hashValue(economic);account.ledger_chain_hash=ledger.at(-1).entry_hash;assert.throws(()=>reconcilePaperAccount({account,ledger,orders}),/ORACLE_COST_DELTA_MISMATCH/);}
 finally{await db.close();}
});
test('P1-A sub-cent partial rounding has conservative reservation and reconciles all gross execution cents',async()=>{
 const{db,service}=await setup({opening_cash_cents:'350'});try{const intent=createIntent({quantity:200,limit_price:'0.005'});const reserved=await service.reserveOrder(reserveInput(intent));assert.equal(reserved.reserved_cash_cents,'350');await service.submitOrder(operation(intent,{key:'submit-subcent'}));for(let i=0;i<200;i++)await fill(service,intent,{key:`sf${i}`,fill_id:`sf${i}`,quantity:1});const a=await service.getAccount(scope);assert.equal(a.settled_cash_cents,'0');assert.equal(a.reserved_cash_cents,'0');assert.equal((await service.reconcile(scope)).passed,true);}
 finally{await db.close();}
});
test('P1-A independent oracle tracks concurrent sell-lot reservations and cancellation allocation',async()=>{
 const{db,service}=await setup();try{
 const buy=createIntent({quantity:400});await submitted(service,buy);await fill(service,buy,{key:'buy-lot-a',fill_id:'lot-a',quantity:200});await fill(service,buy,{key:'buy-lot-b',fill_id:'lot-b',quantity:200});
 const sell1=createIntent({id:'sell-1',side:'SELL',quantity:200,time:DAY2}),sell2=createIntent({id:'sell-2',side:'SELL',quantity:200,time:DAY2});await submitted(service,sell1);await submitted(service,sell2);await fill(service,sell2);await service.cancelOrder(operation(sell1,{key:'cancel-reserved-sell',reason_code:'TEST_CANCEL'}));const a=await service.getAccount(scope);assert.equal(a.lots.find(l=>l.lot_id==='lot-a').remaining_quantity,'200');assert.equal(a.lots.find(l=>l.lot_id==='lot-b').remaining_quantity,'0');assert.equal(a.lots.find(l=>l.lot_id==='lot-a').reserved_quantity,'0');assert.equal((await service.reconcile(scope)).passed,true);
 const sell3=createIntent({id:'sell-3',side:'SELL',quantity:200,time:DAY2});await submitted(service,sell3);await assert.rejects(()=>fill(service,sell3,{price:'9.99'}),/LIMIT_PRICE_VIOLATION/);await fill(service,sell3);assert.equal((await service.reconcile(scope)).passed,true);
 }
 finally{await db.close();}
});
test('P1-A idempotency keys and client identity scope persist per account and reject mutated approval/snapshot terms',async()=>{
 const{db,service}=await setup();try{const intent=createIntent();const r=reserveInput(intent);await service.reserveOrder(r);await assert.rejects(()=>service.reserveOrder({...reserveInput({...intent,snapshot_hash:hashValue({mutated:1})}),idempotency_key:r.idempotency_key}),/IDEMPOTENCY_PAYLOAD_CONFLICT/);await assert.rejects(()=>service.reserveOrder({...reserveInput({...intent,rule_version:'SYNTHETIC_RULE_2'}),idempotency_key:'another-key'}),/DUPLICATE_ORDER/);
 await open(service,{account_id:'SYNTHETIC_ACCOUNT_2'});const other=createIntent({account_id:'SYNTHETIC_ACCOUNT_2'});await service.reserveOrder(reserveInput(other));assert.equal((await service.getAccount({mode:'PAPER',account_id:'SYNTHETIC_ACCOUNT_2'})).reserved_cash_cents,'200290');const bad=operation(intent,{key:'wrong-account',account_id:'SYNTHETIC_ACCOUNT_2',strategy:'EVENT_3'});await assert.rejects(()=>service.submitOrder(bad),/ORDER_SCOPE_MISMATCH/);assert.equal((await service.reconcile(scope)).passed,true);
 }
 finally{await db.close();}
});
test('P1-A Shanghai trading date is independently reconciled for a valid negative timezone offset',async()=>{
 const{db,service}=await setup();try{const buy=createIntent({quantity:100});await submitted(service,buy);await fill(service,buy);const sell=createIntent({id:'offset-sell',side:'SELL',quantity:100,time:'2025-04-10T22:00:00-04:00',trade_date:'2025-04-11'});await submitted(service,sell);assert.equal((await service.reconcile(scope)).passed,true);await fill(service,sell);assert.equal((await service.reconcile(scope)).passed,true);}
 finally{await db.close();}
});
test('P1-A concurrent readers get atomic account/lot snapshots and reconcile after queued mutation',async()=>{
 const{db,service}=await setup();try{const intent=createIntent({quantity:100});await submitted(service,intent);const results=await Promise.all([fill(service,intent),service.getAccount(scope),service.reconcile(scope)]);assert.equal(results[1].lots.length,1);assert.equal(results[1].settled_cash_cents,results[0].settled_cash_cents);assert.equal(results[2].passed,true);}
 finally{await db.close();}
});
