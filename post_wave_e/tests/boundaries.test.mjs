import fs from 'node:fs';import test from 'node:test';import assert from 'node:assert/strict';
import {validatePreparation,transitionPreparation,issueActual} from '../contracts.mjs';
import {contentHash} from '../../src/contracts/validate.mjs';
const names=['Historical-PIT-Gap','Tradeability-History-Readiness','Financial-Revision-Readiness','Action-Adjustment-Reconciliation','Frozen-StrategySpec','Forward-Paper-Real-Adapter-Readiness','Snapshot-B-Preflight','Provider-License-Transport-Gap'];
const values=names.map(n=>JSON.parse(fs.readFileSync(new URL('../../docs/post-wave-e/'+n+'.json',import.meta.url))));
function reseal(v){v.content_hash=contentHash(v);return v;}
test('eight current preparation contracts validate for DISPLAY',()=>{for(const v of values)assert.equal(validatePreparation(v),v);});
test('display cannot promote to native authority',()=>{for(const v of values)for(const t of ['OrderIntent','Fill','SignalEvent','Approval','ResearchCard','BROKER','ADMITTED','EVENT_3','RESEARCH_6_18M'])assert.throws(()=>transitionPreparation(v,t));});
test('caller reseal can display but never issue',()=>{const v=structuredClone(values[0]);v.trace_id='post-e:'+ 'a'.repeat(64);reseal(v);validatePreparation(v);assert.throws(()=>issueActual(v));});
test('all privilege booleans are closed false',()=>{for(const key of ['productionGate','historical_visibility_proven','provider_identity_verified','license_verified','transport_integrity_verified','cloud_transfer','live_authority','can_produce_order','tradeable','production_eligible']){const v=structuredClone(values[0]);v[key]=true;assert.throws(()=>validatePreparation(reseal(v)));}});
test('actual days cannot be synthetic counts',()=>{const v=structuredClone(values[0]);v.actual_forward_days=1;assert.throws(()=>validatePreparation(reseal(v)));});
test('namespace and symbol set isolated',()=>{for(const mutate of [v=>v.namespace='CORE_40',v=>v.namespace='EVENT_3',v=>v.symbols.reverse(),v=>v.symbols.push('000001.SZ')]){const v=structuredClone(values[0]);mutate(v);assert.throws(()=>validatePreparation(reseal(v)));}});
test('extra money or native authority fields reject',()=>{for(const extra of [{capital:100000},{OrderIntent:{}},{owner_approved:true}])assert.throws(()=>validatePreparation(reseal({...structuredClone(values[0]),...extra})));});
test('hash mismatch rejects',()=>{const v=structuredClone(values[0]);v.content_hash='sha256:'+'0'.repeat(64);assert.throws(()=>validatePreparation(v));});
test('retrieval after cutoff nanosecond rejects',()=>{const v=structuredClone(values[0]);v.decision_cutoff='2026-10-06T23:00:00.000000001+08:00';v.retrieval_cutoff='2026-10-06T23:00:00.000000002+08:00';assert.throws(()=>validatePreparation(reseal(v)));});
test('date-only clock and contract/version drift rejects',()=>{for(const [k,x] of [['decision_cutoff','2026-10-06'],['contract_name','OrderIntent'],['contract_version','2.0.0'],['object_version',2]]){const v=structuredClone(values[0]);v[k]=x;assert.throws(()=>validatePreparation(reseal(v)));}});
test('strategy diagnostic cannot become final rule by edit',()=>{const v=structuredClone(values[4]);v.body.owner_strategy_selected=true;assert.throws(()=>validatePreparation(reseal(v)));});
test('provider license shape cannot be admitted by edit',()=>{const v=structuredClone(values[7]);v.body.source_admission='ADMITTED';assert.throws(()=>validatePreparation(reseal(v)));});
