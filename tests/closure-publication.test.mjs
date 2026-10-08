import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs/promises';import os from 'node:os';import path from 'node:path';
import {createClosureDataFixture} from './fixtures/closure/data-helpers.mjs';import {createAdmissionService} from '../src/closure/admission.mjs';import {buildBrainPacket,writeManualExport} from '../src/closure/export.mjs';import {closureRef,sealClosure} from '../src/closure/contracts.mjs';
async function setup(t){const f=await createClosureDataFixture(),directory=await fs.mkdtemp(path.join(os.tmpdir(),'closure-publish-'));t.after(async()=>{await f.db.close();await fs.rm(directory,{recursive:true,force:true});});return {...f,directory,packet:await buildBrainPacket(f)};}

test('Closure publication: real verification then revocation before publication leaves zero new files and zero accepted audits',async t=>{
 const f=await setup(t);const service={...f.service,verifyPacket:async args=>{const v=await f.service.verifyPacket(args);await f.service.revokeReceipt({hash:f.receipt.content_hash,now:f.now,reason_code:'CLOSURE_RECEIPT_REVOKED'});return v;}};
 await assert.rejects(writeManualExport({...f,service}),/CLOSURE_RECEIPT_REVOKED/);assert.deepEqual(await fs.readdir(f.directory),[]);assert.equal((await f.db.query("SELECT count(*) n FROM p1a_closure.audit WHERE event_type='EXPORT_ACCEPTED'")).rows[0].n,0);
});
test('Closure publication: rejected re-export preserves already committed historical artifact bytes',async t=>{
 const f=await setup(t),old=await writeManualExport(f),bytes=await fs.readFile(old.path);const service={...f.service,verifyPacket:async args=>{const v=await f.service.verifyPacket(args);await f.service.revokeReceipt({hash:f.receipt.content_hash,now:f.now,reason_code:'CLOSURE_RECEIPT_REVOKED'});return v;}};
 await assert.rejects(writeManualExport({...f,service}),/CLOSURE_RECEIPT_REVOKED/);assert.deepEqual(await fs.readFile(old.path),bytes);assert.equal((await fs.readdir(f.directory)).length,1);
});
for(const change of ['RECEIPT_REVOCATION','POLICY_VERSION'])test('Closure publication: '+change+' on another facade of same DB is ordered after publication acceptance',async t=>{
 const f=await setup(t);const policy=sealClosure({...f.policy,object_version:2,version_chain_parent:closureRef(f.policy)}),other=createAdmissionService({db:f.db,authority:f.authority,approvedPolicyHashes:new Set([f.policy.content_hash,policy.content_hash])});
 let entered,release;const enteredPromise=new Promise(r=>entered=r),barrier=new Promise(r=>release=r),events=[];
 const service={...f.service,audit:async e=>{if(e.event_type==='EXPORT_ACCEPTED'){entered();await barrier;events.push('EXPORT_ACCEPTED');}return f.service.audit(e);}};
 const publication=writeManualExport({...f,service});await enteredPromise;let changed=false;
 const mutation=(change==='RECEIPT_REVOCATION'?other.revokeReceipt({hash:f.receipt.content_hash,now:f.now,reason_code:'CLOSURE_RECEIPT_REVOKED'}):other.registerPolicy(policy)).then(()=>{changed=true;events.push(change);});
 await new Promise(r=>setImmediate(r));assert.equal(changed,false);release();const file=await publication;await mutation;assert.deepEqual(events,['EXPORT_ACCEPTED',change]);assert.equal((await fs.readFile(file.path)).length>0,true);
 await assert.rejects(f.service.verifyPacket({...f,purpose:f.purpose,strategy_id:f.strategy_id}),change==='RECEIPT_REVOCATION'?/CLOSURE_RECEIPT_REVOKED/:/CLOSURE_RECEIPT_INVALIDATED/);
});
