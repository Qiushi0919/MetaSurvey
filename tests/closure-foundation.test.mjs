import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs/promises';import {PGlite} from '@electric-sql/pglite';
import {migrate} from '../src/baseline/migrate.mjs';import {hashValue} from '../src/contracts/validate.mjs';import {sha,assertSanitized,createFixtureAuthority,verifyClosureSignature} from '../src/closure/contracts.mjs';import {closureAudit} from '../src/closure/store.mjs';

test('Closure W1 contracts and exact 006 remain frozen; old P0/P1A schemas/releases/gates remain original bytes',async()=>{
 const read=async p=>JSON.parse(await fs.readFile(new URL('../'+p,import.meta.url),'utf8'));
 const w=await read('docs/closure-implementation/W1-freeze.json');for(const f of w.schemas)assert.equal(sha(await fs.readFile(new URL('../'+f.path,import.meta.url))),f.sha256);
 assert.equal(sha(await fs.readFile(new URL('../migrations/006_closure_admission.sql',import.meta.url))),w.migration_sha256);
 for(const release of ['contracts/release.v1.json','contracts/release.p1a.json'])for(const f of (await read(release)).files)assert.equal(sha(await fs.readFile(new URL('../'+f.path,import.meta.url))),f.sha256,f.path);
});
test('Closure 006 empty→6/idempotent; all four exact persistence families block UPDATE DELETE TRUNCATE',async()=>{
 const db=new PGlite();try{assert.equal((await migrate(db)).schemaVersion,6);assert.equal((await migrate(db)).applied.length,0);
 assert.deepEqual((await db.query("SELECT tablename FROM pg_tables WHERE schemaname='p1a_closure' ORDER BY tablename")).rows.map(x=>x.tablename),['audit','policies','receipts','revocations']);
 const body={fixture_scope:'SYNTHETIC_TEST_ONLY',purpose:'FIXTURE_MANUAL_EXPORT',production_enabled:false,allow_real_data:false},hash=hashValue(body),at='2026-09-30T00:00:00Z',until='2026-10-01T00:00:00Z';
 await db.query('INSERT INTO p1a_closure.policies VALUES($1,$2,$3,$4)',[hash,body,at,until]);await db.query('INSERT INTO p1a_closure.receipts VALUES($1,$2,$3,$4,$5)',[hash,hash,body,at,until]);await db.query('INSERT INTO p1a_closure.revocations VALUES($1,$2,$3,$4)',['RECEIPT',hash,at,'CLOSURE_RECEIPT_REVOKED']);await closureAudit(db,{chain_id:'synthetic-foundation',event_type:'EXPORT_ACCEPTED',event_time:at});
 for(const name of ['policies','receipts','revocations','audit']){for(const sql of [`UPDATE p1a_closure.${name} SET ${name==='revocations'?'reason_code=reason_code':'content_hash=content_hash'}`,`DELETE FROM p1a_closure.${name}`,`TRUNCATE p1a_closure.${name} CASCADE`])await assert.rejects(db.exec(name==='audit'?sql.replace('content_hash=content_hash','event_hash=event_hash'):sql),/CLOSURE_APPEND_ONLY/);}
 }finally{await db.close();}
});
test('Closure audit refuses attacker refs/secrets; concurrent writes maintain verifiable ordered chain',async()=>{
 const db=new PGlite();try{await migrate(db);const params={chain_id:'fixture-concurrent',event_type:'IMPORT_REJECTED',event_time:'2026-09-30T00:00:00Z'};
 await assert.rejects(closureAudit(db,{...params,refs:[{object_id:'x',object_version:1,content_hash:hashValue('x'),payload:{future_MAE:'99'}}]}),/CLOSURE_IMPORT_INVALID/);
 await assert.rejects(closureAudit(db,{...params,refs:[{object_id:'/Users/fixture/raw',object_version:1,content_hash:hashValue('x')}]}),/CLOSURE_IMPORT_INVALID/);
 await Promise.all(Array.from({length:8},()=>closureAudit(db,params)));const rows=(await db.query('SELECT event_json FROM p1a_closure.audit ORDER BY sequence')).rows.map(x=>x.event_json);
 assert.equal(rows.length,8);let previous='sha256:'+'0'.repeat(64);for(const [i,r]of rows.entries()){const {event_hash,...body}=r;assert.equal(r.sequence,i+1);assert.equal(r.previous_hash,previous);assert.equal(event_hash,hashValue(body));previous=event_hash;}
 }finally{await db.close();}
});
test('Fixture signatures require constructor trusted key; sanitizer permits only false credentials marker',()=>{
 const a=createFixtureAuthority(),b=createFixtureAuthority(Buffer.alloc(32,7));const o=a.signObject({fixture_scope:'SYNTHETIC_TEST_ONLY',purpose:'FIXTURE_MANUAL_EXPORT',production_enabled:false,issuer:a.issuer});assert.equal(verifyClosureSignature(o,a.publicKeyDer),true);assert.throws(()=>verifyClosureSignature(o,b.publicKeyDer),/CLOSURE_SIGNATURE_INVALID/);assert.throws(()=>a.signObject({...o,production_enabled:true}),/CLOSURE_SYNTHETIC_SCOPE_ESCALATION/);
 assert.equal(assertSanitized({contains_account_identity_or_credentials:false}),true);assert.throws(()=>assertSanitized({contains_account_identity_or_credentials:true}),/CLOSURE_EXPORT_FIELDS_FORBIDDEN/);assert.throws(()=>assertSanitized({nested:{raw_path:'x'}}),/CLOSURE_EXPORT_FIELDS_FORBIDDEN/);
});
