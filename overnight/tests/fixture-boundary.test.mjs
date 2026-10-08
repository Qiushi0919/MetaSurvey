import test,{before,after} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {produceFixture,verifyProducedFixture,fixtureProof} from '../fixture/chain.mjs';
let directory,produced;
before(async()=>{directory=await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(),'ashare-overnight-fixture-')));produced=await produceFixture({directory,fixture_case:'BASE'});});
after(async()=>{await fs.rm(directory,{recursive:true,force:true});});
test('actual quarantine dataset cannot enter the fixture producer through ignored input properties',async()=>{
 const quarantine={fixture:false,state:'QUARANTINED',source_admission:'BLOCKED',namespace:'CORE_40'};
 for(const key of ['dataset','raw','packet','response','account','policy','approval','model_result']){
  await assert.rejects(produceFixture({directory,fixture_case:'BASE',[key]:quarantine}),/OVERNIGHT_REAL_INPUT_FORBIDDEN/);
 }
 await assert.rejects(produceFixture({directory,fixture_case:'REAL_STOCK'}),/OVERNIGHT_FIXTURE_CASE_INVALID/);
});
test('registered synthetic result cannot be copied or mutated into real company or production authority',()=>{
 assert.equal(verifyProducedFixture(produced),true);
 assert.throws(()=>verifyProducedFixture(structuredClone(produced)),/OVERNIGHT_FIXTURE_UNREGISTERED_OR_MUTATED/);
 const original=produced.card.symbol;produced.card.symbol='603993.SH';
 assert.throws(()=>fixtureProof(produced),/OVERNIGHT_FIXTURE_UNREGISTERED_OR_MUTATED/);produced.card.symbol=original;
 assert.equal(verifyProducedFixture(produced),true);
});
test('synthetic proof carries zero real cards, actual forward days, model calls and execution rights',()=>{
 const proof=fixtureProof(produced);assert.equal(proof.fixture,true);assert.equal(proof.real_card_count,0);
 assert.equal(proof.model_calls,0);assert.equal(proof.execution_writes,0);assert.equal(proof.productionGate,false);
 assert.equal(proof.real_snapshot_B_exists,false);assert.equal(proof.fixture_time_is_not_actual_forward_paper_day,true);
 assert.deepEqual(proof.phase_order,['COST_ESTIMATED','SUITABILITY_EVALUATED']);
});
test('directory symlink and normalized traversal fail before invoking the producer',async()=>{
 const link=path.join(directory,'link');await fs.symlink(directory,link);
 await assert.rejects(produceFixture({directory:link,fixture_case:'BASE'}),/OVERNIGHT_FIXTURE_DIRECTORY_INVALID/);
 await assert.rejects(produceFixture({directory:directory+'/../'+path.basename(directory),fixture_case:'BASE'}),/OVERNIGHT_FIXTURE_DIRECTORY_INVALID/);
});
test('dynamic option getter cannot switch the validated directory before producer use',async()=>{
 let calls=0;
 const options={fixture_case:'BASE',get directory(){calls++;return calls<8?directory:directory+'/link';}};
 await assert.rejects(produceFixture(options),/OVERNIGHT_OPTIONS_ACCESSOR_FORBIDDEN/);
 assert.equal(calls,0);
 const fixtureGetter={directory,get fixture_case(){throw new Error('GETTER_MUST_NOT_RUN');}};
 await assert.rejects(produceFixture(fixtureGetter),/OVERNIGHT_OPTIONS_ACCESSOR_FORBIDDEN/);
});
