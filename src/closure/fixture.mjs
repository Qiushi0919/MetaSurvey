// Fixture-only composition: never a source adapter or actual account configuration.
import fs from 'node:fs/promises';import {sealCostProfile} from '../cost/index.mjs';import {hashValue,canonical} from '../contracts/validate.mjs';
import {createClosureDataFixture} from '../../tests/fixtures/closure/data-helpers.mjs';import {buildBrainPacket,writeManualExport} from './export.mjs';import {runIsolatedConsumer} from './isolation.mjs';import {importResearchResult} from './import.mjs';
import {loadCodeProvenance,verifyCodeProvenance} from '../p1a/code-provenance.mjs';
export const closureFixture=JSON.parse(await fs.readFile(new URL('../../tests/fixtures/closure/e2e.json',import.meta.url),'utf8'));
export async function buildClosureFixture({db,now=closureFixture.now,strategy_id=closureFixture.strategy_id,dataOptions={}}={}){
 const code=await loadCodeProvenance();await verifyCodeProvenance(code);
 // Parent-approved policy epoch binds the actual validated implementation and schema versions.
 // No caller field can preserve or approve an old code/schema epoch automatically.
 const epoch='synthetic:closure-policy:'+code.code_version+':schema6:packet1.1.0:receipt1.0.0';
 const f=await createClosureDataFixture({db,now,strategy_id,dataOptions,policyOverrides:{object_id:epoch}});
 return {...f,costProfile:sealCostProfile(closureFixture.cost_profile),tradeTerms:structuredClone(closureFixture.trade_terms),realAccountProfile:JSON.parse(await fs.readFile(new URL('../../config/account-profile.unconfigured.v1.json',import.meta.url),'utf8'))};
}
export async function executionState(db){
 const names=(await db.query("SELECT schemaname,tablename FROM pg_tables WHERE schemaname IN ('public','p1a_paper') AND (schemaname='p1a_paper' OR tablename ~ '(order|fill|position|ledger|approval|signal|research_card)') ORDER BY schemaname,tablename")).rows;
 const out={};for(const r of names){if(!/^[a-z_0-9]+$/.test(r.schemaname+r.tablename))throw Error('UNSAFE_TABLE');out[r.schemaname+'.'+r.tablename]=(await db.query(`SELECT count(*)::text AS n FROM ${r.schemaname}.${r.tablename}`)).rows[0].n;}return out;
}
export async function runClosureRoundTrip({directory,probeOptions={}}){
 const f=await buildClosureFixture();try{
 const before=await executionState(f.db),packet=await buildBrainPacket({service:f.service,snapshot:f.snapshot,receipt:f.receipt,now:f.now});
 const file=await writeManualExport({service:f.service,packet,snapshot:f.snapshot,directory,now:f.now});
 const consumer=await runIsolatedConsumer({service:f.service,packet,snapshot:f.snapshot,export_path:file.path,now:f.now,probeOptions});
 const imported=await importResearchResult({...f,packet,result:consumer.result});
 const after=await executionState(f.db);if(canonical(before)!==canonical(after))throw Error('EXECUTION_STATE_CHANGED');
 const identity={fixture_scope:'SYNTHETIC_TEST_ONLY',source_raw_hashes:[f.securityObservation.raw_sha256,f.calendarObservation.raw_sha256,f.barObservation.raw_sha256],snapshot_ref:f.snapshot.snapshot_ref,data_hash:f.snapshot.manifest.data_hash,policy_ref:f.receipt.policy_ref,receipt_hash:f.receipt.content_hash,packet_hash:packet.content_hash,file_byte_hash:file.byte_hash,draft_hash:imported.draft.content_hash,cost_estimate:imported.cost_estimate,phase_order:imported.phase_order};
 const audit=(await f.db.query('SELECT event_json FROM p1a_closure.audit ORDER BY chain_id,sequence')).rows.map(r=>r.event_json);
 return {identity,replay_hash:hashValue(identity),packet,receipt:f.receipt,draft:imported.draft,cost_estimate:imported.cost_estimate,phase_order:imported.phase_order,isolation:consumer.isolation,probes:consumer.probes,execution_state_before:before,execution_state_after:after,audit,real_data_admission_gate:'BLOCKED',production_execution_enabled:false,p1b_research_enabled:false};
 }finally{await f.db.close();}
}
