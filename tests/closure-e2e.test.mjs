import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs/promises';import os from 'node:os';import path from 'node:path';
import {runClosureRoundTrip,buildClosureFixture,executionState} from '../src/closure/fixture.mjs';import {isolationAvailable} from '../src/closure/isolation.mjs';import {buildBrainPacket} from '../src/closure/export.mjs';import {importResearchResult,assertDraftTransition} from '../src/closure/import.mjs';import {closureRef,validateClosure} from '../src/closure/contracts.mjs';import {productionGate} from '../src/baseline/gates.mjs';

test('R01-R12 closure: actual isolated manual roundtrip repeats exact identities; zero execution writes',async t=>{
 if(!await isolationAvailable()){t.skip('Real sandbox positive E2E requires macOS; unsupported platform has fail-closed tests, never claimed as positive isolation.');return;}
 const directory=await fs.mkdtemp(path.join(os.tmpdir(),'closure-e2e-'));try{
 const a=await runClosureRoundTrip({directory}),b=await runClosureRoundTrip({directory});assert.deepEqual(a.identity,b.identity);assert.equal(a.replay_hash,b.replay_hash);assert.deepEqual(a.execution_state_before,a.execution_state_after);assert.equal(Object.keys(a.execution_state_before).filter(k=>k.startsWith('p1a_paper.')).length,7);assert(a.isolation.deny_default);assert.equal(a.draft.validation_status,'NON_TRADEABLE');assert.equal(a.draft.can_produce_order,false);assert.deepEqual(a.phase_order,['COST_ESTIMATED','SUITABILITY_EVALUATED']);for(const name of ['BrainPacket','AdmissionReceipt','ResearchDraft'])validateClosure(name,name==='BrainPacket'?a.packet:name==='AdmissionReceipt'?a.receipt:a.draft);
 }finally{await fs.rm(directory,{recursive:true,force:true});}
});
test('R05 R06 R08 R09 R10: hostile model returns and missing Cost do not write any execution state',async()=>{
 const f=await buildClosureFixture();try{
 const packet=await buildBrainPacket({service:f.service,snapshot:f.snapshot,receipt:f.receipt,now:f.now}),before=await executionState(f.db);
 const clean={packet_ref:closureRef(packet),receipt_ref:closureRef(f.receipt),strategy_id:packet.strategy_id,purpose:packet.purpose,observations:[{evidence_ref:closureRef(packet.evidence[0]),statement:'Synthetic close is descriptive only.',classification:'DESCRIPTIVE_ONLY'}]};
 for(const injected of ['BUY','APPROVE','HUMAN_USER','OrderIntent','REAL_ACCOUNT_SUITABLE','REAL_NET_EDGE','REAL_SIZING','TRADEABLE']){const result=structuredClone(clean);result.observations[0].statement=injected;await assert.rejects(importResearchResult({...f,packet,result}),/CLOSURE_LLM_EXECUTION_INJECTION/);assert.deepEqual(await executionState(f.db),before);}
 await assert.rejects(importResearchResult({...f,packet,result:{...clean,OrderIntent:{side:'BUY'}}}),/CLOSURE_IMPORT_INVALID/);
 await assert.rejects(importResearchResult({...f,packet,result:clean,costProfile:null}),/CLOSURE_COST_REQUIRED_FIRST/);
 const imported=await importResearchResult({...f,packet,result:clean});assert.deepEqual(imported.phase_order,['COST_ESTIMATED','SUITABILITY_EVALUATED']);assert.equal(imported.draft.real_account_suitability,'BLOCKED');assert.equal(imported.draft.real_net_edge,'UNSET_REQUIRED');assert.equal(imported.draft.real_sizing,'UNSET_REQUIRED');assert.equal(productionGate(f.realAccountProfile).allowed,false);
 for(const target of ['CandidateTradeable','CandidateEligibility','Signal','SignalEvent','Approval','OrderIntent','Order','Fill'])assert.throws(()=>assertDraftTransition(imported.draft,target),/CLOSURE_DRAFT_NON_EXECUTABLE/);
 assert.deepEqual(await executionState(f.db),before);
 }finally{await f.db.close();}
});
