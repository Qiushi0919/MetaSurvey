import test from 'node:test';
import assert from 'node:assert/strict';
import { PGlite } from '@electric-sql/pglite';
import { migrate } from '../src/baseline/migrate.mjs';
import { experimentFixture as fixture,buildReplayData } from '../src/p1a/fixture.mjs';
import {fixtureCostProfile,runReplay,replayManifest,assertReplayBinding,assertApprovalBinding} from '../src/p1a/replay.mjs';
import {loadCodeProvenance,verifyCodeProvenance} from '../src/p1a/code-provenance.mjs';
import {validateP1AContract,p1aContractNames} from '../src/p1a/contracts.mjs';
import {verifyDataSnapshot,readObject} from '../src/data/index.mjs';
import {sealReferenceObject} from '../src/paper/index.mjs';
import {sealContract} from '../src/contracts/validate.mjs';
import {hashValue} from '../src/contracts/validate.mjs';
const code=await loadCodeProvenance();
async function replay({inputFixture=fixture,profileName='BASE_FRICTION',version=1,rule_version=fixture.rule_version,edge_enabled=false,trace_id='test-trace',wall_clock='2026-10-05T04:00:00Z',byteMutation=false}={}){
 const db=new PGlite();try{const migration=await migrate(db);assert.equal(migration.schemaVersion,6);const data=await buildReplayData(db,{fixture:inputFixture,byteMutation});const cost_profile=fixtureCostProfile(inputFixture,profileName,version);const result=await runReplay({db,fixture:inputFixture,...data,cost_profile,...code,rule_version,edge_enabled,trace_id,wall_clock});return {...result,data,cost_profile};}finally{await db.close();}
}
const checkEconomicEqual=(a,b)=>{for(const key of ['order_sequence','fill_sequence','ledger_entries','daily_nav','cost_breakdown','path_metrics','economic_result_hash','ledger_chain_hash'])assert.deepEqual(a[key],b[key],key);};
test('Experiment A: actual committed source + immutable snapshot replay twice, trace/wall time do not change economics',async()=>{
 const a=await replay(),b=await replay({trace_id:'random-diagnostic-trace',wall_clock:'2026-10-05T05:17:00Z'});checkEconomicEqual(a.result,b.result);assert.equal(a.reconciliation.passed,true);assert.equal(b.reconciliation.passed,true);assert.notEqual(a.audit.audit_chain_hash,b.audit.audit_chain_hash);
 for(const [name,value] of [['DeterministicReplayResult',a.result],['CostProfile',a.cost_profile],['ReplayInputManifest',a.result.input],['PaperCalendarProjection',a.data.calendar],['PaperSecurityProjection',a.data.security],['SnapshotLineageBundle',a.data.snapshot.lineage_bundle],['CostAttribution',a.result.cost_breakdown]])validateP1AContract(name,value);
 a.result.order_sequence.forEach(o=>validateP1AContract('PaperReplayOrderIntent',o));a.result.path_metrics.forEach(({signal_id,...m})=>validateP1AContract('PathMetrics',m));a.audit.events.forEach(e=>validateP1AContract('AuditChainEvent',e));validateP1AContract('CodeProvenance',code);
 assert.deepEqual(a.audit.events.map(e=>e.event_type),['MARKET_DATA','SNAPSHOT','FEATURE','COST','REPLAY']);assert(a.result.path_metrics.every(m=>m.mae_resolution==='DAILY_APPROXIMATION'&&m.mfe_resolution==='DAILY_APPROXIMATION'));
});
test('Experiment A mutations: cost version only/rule version only/source byte only change identity and invalidate old approval/result',async()=>{
 const a=await replay(),cost=await replay({version:2}),rule=await replay({rule_version:'SYNTHETIC_PREDETERMINED_CORE_EXIT_RISK_V2'}),bytes=await replay({byteMutation:true});
 for(const r of [cost,rule,bytes])assert.notEqual(a.result.economic_result_hash,r.result.economic_result_hash);
 assert.deepEqual(a.result.cost_breakdown,cost.result.cost_breakdown);assert.deepEqual(a.result.cost_breakdown,rule.result.cost_breakdown);
 assert.notEqual(a.data.snapshot.manifest.data_hash,bytes.data.snapshot.manifest.data_hash);assert.equal(a.data.bar.payload_sha256,bytes.data.bar.payload_sha256);assert.notEqual(a.data.bar.raw_sha256,bytes.data.bar.raw_sha256);
 const oldApproval={scope:'SYNTHETIC_TEST_ONLY',actor_type:'HUMAN_USER',input_hash:a.result.input.content_hash,snapshot_hash:a.data.snapshot.manifest.content_hash};assert.equal(assertApprovalBinding(oldApproval,a.result.input),true);assert.throws(()=>assertApprovalBinding(oldApproval,bytes.result.input),/APPROVAL_INPUT_INVALIDATED/);assert.throws(()=>assertApprovalBinding({...oldApproval,actor_type:'LLM'},a.result.input),/APPROVAL_INPUT_INVALIDATED/);
 const binding={fixture,...bytes.data,cost_profile:bytes.cost_profile,rule_version:fixture.rule_version,...code,signals_hash:hashValue(fixture.signals),edge_enabled:false,edge_policy_hash:hashValue(fixture.edge_policy)};assert.throws(()=>assertReplayBinding(a.result.input,binding),/REPLAY_INPUT_INVALIDATED/);
});
test('snapshot persisted closure rejects caller byte mutation and SourceObservation schema cannot admit unknown availability',async()=>{
 const db=new PGlite();try{await migrate(db);const data=await buildReplayData(db);const mutated=structuredClone(data.snapshot);mutated.manifest.data_hash=hashValue('forged');await assert.rejects(verifyDataSnapshot(db,mutated),/SNAPSHOT_MUTATION|HASH_MISMATCH/);
 const obs=await readObject(db,data.bar.lineage_refs[0]);validateP1AContract('SourceObservation',obs);
 const unknown={...obs,available_at:null,data_quality_status:'PASS',tradeability:'OFFLINE_ELIGIBLE'};const {content_hash,...body}=unknown;unknown.content_hash=hashValue(body);assert.throws(()=>validateP1AContract('SourceObservation',unknown),/UNKNOWN_SOURCE_ADMISSION_FORBIDDEN/);
 }finally{await db.close();}
});
test('Experiment B: fixed fills/gross, strict friction/net ordering; Edge counts monotonic and all rejections coded',async()=>{
 const off=[],on=[];for(const profileName of ['LOW_FRICTION','BASE_FRICTION','HIGH_FRICTION']){off.push((await replay({profileName})).result);on.push((await replay({profileName,edge_enabled:true})).result);}
 const pre=r=>r.fill_sequence.map(f=>({fill_id:f.fill_id,quantity:f.quantity,price:f.price,trade_date:f.trade_date}));
 for(const r of off.slice(1)){assert.deepEqual(r.signals,off[0].signals);assert.deepEqual(pre(r),pre(off[0]));assert.equal(r.cost_breakdown.gross_pnl_cents,off[0].cost_breakdown.gross_pnl_cents);}
 const friction=off.map(r=>BigInt(r.cost_breakdown.total_friction_cents)),net=off.map(r=>BigInt(r.cost_breakdown.net_pnl_cents));assert(friction[0]<friction[1]&&friction[1]<friction[2]);assert(net[0]>net[1]&&net[1]>net[2]);assert(on[2].trade_count<=on[1].trade_count&&on[1].trade_count<=on[0].trade_count);assert.deepEqual(on.map(r=>r.round_trip_count),[3,2,1]);assert(on.flatMap(r=>r.rejections).every(r=>r.reason_codes.length>0));
 for(const r of [...off,...on]){assert.equal(BigInt(r.cost_breakdown.gross_pnl_cents)-BigInt(r.cost_breakdown.total_friction_cents),BigInt(r.cost_breakdown.net_pnl_cents));assert.equal(r.cost_breakdown.minimum_commission_effect_is_subset,true);}
});
test('code provenance rejects valid-looking historical SHA and unbound source tree',async()=>{
 await verifyCodeProvenance(code);await assert.rejects(verifyCodeProvenance({code_version:'433a2e96482e5db6e2a0ea452727baf61f4c4426',source_tree_hash:code.source_tree_hash}),/CODE_BINDING_MISMATCH/);await assert.rejects(verifyCodeProvenance({...code,source_tree_hash:hashValue('wrong')}),/CODE_BINDING_MISMATCH/);assert(p1aContractNames().length>=12);
});

test('actual split-fill gross reconciliation and fixture cash/session binding reject hidden input changes',async()=>{
 const inputFixture=structuredClone(fixture);inputFixture.signals=[{...inputFixture.signals[0],entry_price:'10.000049',exit_price:'11.00005'}];
 const result=(await replay({inputFixture})).result;assert.equal(result.cost_breakdown.gross_pnl_cents,'20002');assert.equal(BigInt(result.daily_nav[1].nav_cents)-BigInt(inputFixture.opening_cash_cents),BigInt(result.cost_breakdown.net_pnl_cents));
 const db=new PGlite();try{await migrate(db);const data=await buildReplayData(db);const args={db,fixture,...data,cost_profile:fixtureCostProfile(fixture,'BASE_FRICTION'),...code};
 await assert.rejects(runReplay({...args,fixture:{...fixture,opening_cash_cents:'1234568'}}),/REPLAY_ACCOUNT_FIXTURE_MISMATCH/);
 await assert.rejects(runReplay({...args,fixture:{...fixture,sessions:fixture.sessions.slice(1)}}),/REPLAY_CALENDAR_PROJECTION_MISMATCH/);
 await assert.rejects(runReplay({...args,security:sealReferenceObject({...data.security,canonical_symbol:'SZSE:000001'})}),/REPLAY_SECURITY_PROJECTION_MISMATCH/);
 await assert.rejects(runReplay({...args,calendar:sealReferenceObject({...data.calendar,source:{...data.calendar.source,source_hash:hashValue('forged-source')}})}),/REPLAY_CALENDAR_PROJECTION_MISMATCH/);
 await assert.rejects(runReplay({...args,feature:sealContract({...data.feature,features:{last_close:{value:'99',unit:'CNY_PER_SHARE',quality:'VALID'}}})}),/REPLAY_FEATURE_DERIVATION_MISMATCH/);
 assert.equal((await db.query('SELECT count(*)::integer AS n FROM p1a_paper.orders')).rows[0].n,0);

 }finally{await db.close();}
});
