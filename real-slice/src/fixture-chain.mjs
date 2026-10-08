// Synthetic composition only. No new grade, cost, admission or approval algorithm.
import fs from 'node:fs/promises';
import {canonical,hashValue,reference,sealContract,validateContract} from '../../src/contracts/validate.mjs';
import {buildClosureFixture,executionState} from '../../src/closure/fixture.mjs';
import {buildBrainPacket,writeManualExport} from '../../src/closure/export.mjs';
import {runIsolatedConsumer} from '../../src/closure/isolation.mjs';
import {importResearchResult} from '../../src/closure/import.mjs';
import {closureRef,validateClosure} from '../../src/closure/contracts.mjs';
import {assessSemantics} from '../../p1b/src/semantics.mjs';
import {validateP1B} from '../../p1b/src/contracts.mjs';
import semantics from '../../p1b/config/semantics.v1.json' with {type:'json'};
import fixtureCases from '../tests/fixtures/chain/cases.json' with {type:'json'};
import {validate as validateSlice,timestampNs} from './contracts.mjs';

const cases=structuredClone(fixtureCases),dimensionNames=[...semantics.dimensions];
const issued=new Map();
const currentHeads=new Map();
const revokedParentRefs=new Set();
const SCOPE='SYNTHETIC_SEMANTIC_TEST_ONLY';
const CHAIN_ID='synthetic:fixture-research-chain:CORE_40';
const CARD_ID='synthetic:fixture-research-card:CORE_40';
const check=(ok,code)=>{if(!ok)throw new Error(code);};
const equal=(a,b)=>canonical(a)===canonical(b);
const fixtureRef=id=>({object_id:id,object_version:1,content_hash:hashValue({fixture_id:id,scope:SCOPE})});

function exactFixtureTimestamp(value){
 // Frozen timestampNs retains all 9 fractional digits, but Date.parse inside
 // that parser normalizes impossible calendar dates. Validate the local ISO
 // components first; Date.parse here checks the calendar, never clock ordering.
 check(typeof value==='string','SLICE_CARD_INVALIDATED');
 const match=value.match(/^(\d{4}-\d\d-\d\d)T(\d\d):(\d\d):(\d\d)(?:\.(\d{1,9}))?(Z|[+-]\d\d:\d\d)$/);
 check(match,'SLICE_CARD_INVALIDATED');
 const calendarMs=Date.parse(match[1]+'T00:00:00Z');
 check(Number.isFinite(calendarMs)&&new Date(calendarMs).toISOString().slice(0,10)===match[1]&&Number(match[2])<=23&&Number(match[3])<=59&&Number(match[4])<=59,'SLICE_CARD_INVALIDATED');
 try{return timestampNs(value);}catch{throw new Error('SLICE_CARD_INVALIDATED');}
}

function semanticInput(selected){
 return {dimensions:{...Object.fromEntries(dimensionNames.map(k=>[k,'PASS'])),...selected.dimension_changes},evidence_refs:[fixtureRef('synthetic:semantics:admitted-local-example')],hard_block_refs:selected.hard_block?[fixtureRef('synthetic:semantics:hard-block-example')]:[],research_card_ref:null,scope:SCOPE};
}

function compatibilityCard({packet,draft,assessment,trace_id,version,valid_until}){
 // Mandatory V1 account and symbol fields carry explicit non-identities. Native
 // grade remains unknown: the assessment's illustrative S is a separate sidecar.
 const refs=[closureRef(packet),closureRef(draft),reference(assessment)];
 const card=sealContract({contract_name:'ResearchCard',contract_version:'1.0.0',object_id:CARD_ID,object_version:version,trace_id,recorded_at:packet.decision_cutoff,business_timezone:'Asia/Shanghai',provenance:{event_time:packet.decision_cutoff,published_at:null,available_at:packet.decision_cutoff,retrieved_at:packet.decision_cutoff,publication_precision:'NOT_APPLICABLE',source_id:'synthetic:fixture-chain-composition',source_version:'fixture-chain-1.0.0',source_hash:hashValue(refs),visibility_basis:'SYNTHETIC'},reason_codes:['SYNTHETIC_FIXTURE_ONLY','UNSET_REQUIRED_CONFIG','EDGE_NOT_VERIFIED','USER_APPROVAL_REQUIRED'],invalidation:{status:'ACTIVE',valid_until,invalidated_at:null,conditions:['Any packet, draft, assessment, snapshot or receipt exact version/hash changes invalidate this compatibility card.','The current in-process composition head supersedes previous compatibility versions.','Expiry invalidates the compatibility card.'],reason_code:null},notes:'SYNTHETIC_FIXTURE identity only. Mandatory horizon fields exercise CORE_40 V1 structural compatibility. Illustrative assessment statuses are not real stock evidence or calibrated grades. No research, execution or human approval granted.',mode:'PAPER',account_id:cases.compatibility_account_id,strategy_id:'CORE_40',symbol:cases.compatibility_symbol,snapshot_ref:structuredClone(packet.snapshot_ref),decision_cutoff:packet.decision_cutoff,grade:'UNSET_REQUIRED',research:{thesis:'Synthetic imported descriptive evidence is available for composition testing only.',strongest_counterevidence:'Illustrative semantic coordinates do not prove company quality, timing, suitability or expected returns.',unknowns:['Actual security identity and account are absent.','All real grades, fee suitability, net edge, probability and sizing remain unresolved.'],evidence_refs:refs,horizon_months:{minimum:6,maximum:18}},price:{reference_price:null,entry_rules:[],no_trade_rules:[]},trade:{target_holding_sessions:{minimum:20,maximum:40},invalidation_rules:[],thesis_invalidation:['Upstream exact version/hash changes.'],sizing_policy_version:'UNSET_REQUIRED',can_produce_order:false},probability:{scenarios:[],calibrated:false,calibration_ref:null,expected_mae_bps:'UNSET_REQUIRED',net_edge_bps:'UNSET_REQUIRED',edge_policy_version:'UNSET_REQUIRED'},scores:Object.fromEntries(['fundamental','sector','catalyst','trend','valuation','liquidity','evidence','risk','research','quality','timing','raw','final'].map(k=>[k,'UNSET_REQUIRED'])),scoring_policy_version:'UNSET_REQUIRED',hard_blocks:['SYNTHETIC_FIXTURE_ONLY','UNSET_REQUIRED_CONFIG','EDGE_NOT_VERIFIED','USER_APPROVAL_REQUIRED'],rule_version:'synthetic:fixture-chain-compatibility-1.0.0'});
 validateContract('ResearchCard',card);return card;
}

function assertArtifacts({packet,draft,assessment,card}){
 validateClosure('BrainPacket',packet);validateClosure('ResearchDraft',draft);validateP1B('ResearchAssessment',assessment);validateContract('ResearchCard',card);
 check(packet.fixture_scope==='SYNTHETIC_TEST_ONLY'&&draft.fixture_scope==='SYNTHETIC_TEST_ONLY'&&assessment.scope===SCOPE,'SLICE_SCOPE_MISMATCH');
 check([packet.strategy_id,draft.strategy_id,assessment.strategy_id,card.strategy_id].every(x=>x==='CORE_40'),'SLICE_SCOPE_MISMATCH');
 check(equal(draft.packet_ref,closureRef(packet))&&equal(draft.receipt_ref,closureRef(packet.receipt))&&equal(draft.snapshot_ref,packet.snapshot_ref),'SLICE_REF_INVALIDATED');
 check(equal(card.snapshot_ref,packet.snapshot_ref)&&card.decision_cutoff===packet.decision_cutoff&&draft.decision_cutoff===packet.decision_cutoff,'SLICE_REF_INVALIDATED');
 check(equal(card.research.evidence_refs,[closureRef(packet),closureRef(draft),reference(assessment)]),'SLICE_REF_INVALIDATED');
 check(card.provenance.source_hash===hashValue(card.research.evidence_refs)&&card.provenance.visibility_basis==='SYNTHETIC','SLICE_REF_INVALIDATED');
 check(card.symbol===cases.compatibility_symbol&&card.account_id===cases.compatibility_account_id&&card.mode==='PAPER'&&card.grade==='UNSET_REQUIRED','SLICE_SCOPE_MISMATCH');
 check(card.trade.can_produce_order===false&&card.price.reference_price===null&&card.probability.scenarios.length===0&&card.probability.calibrated===false&&card.probability.calibration_ref===null,'SLICE_PERMISSION_DENIED');
 for(const x of [card.probability.net_edge_bps,card.probability.expected_mae_bps,card.probability.edge_policy_version,card.trade.sizing_policy_version,card.scoring_policy_version,...Object.values(card.scores)])check(x==='UNSET_REQUIRED','SLICE_PERMISSION_DENIED');
 check(draft.can_produce_order===false&&draft.tradeable===false&&draft.production_enabled===false&&assessment.can_produce_order===false&&assessment.production_enabled===false,'SLICE_PERMISSION_DENIED');
 check(assessment.real_account_suitability==='BLOCKED'&&assessment.real_net_edge==='UNSET_REQUIRED'&&assessment.real_sizing==='UNSET_REQUIRED'&&assessment.probability_claim==='UNSET_REQUIRED'&&assessment.research_card_ref===null,'SLICE_PERMISSION_DENIED');
 check(assessment.actionability_grade!=='S'||assessment.next_action==='REQUEST_REVIEW','SLICE_PERMISSION_DENIED');
 check(card.invalidation.status==='ACTIVE','SLICE_CARD_INVALIDATED');
}

// A consumer cannot establish authority by resealing hashes or supplying refs.
// Only artifacts actually emitted by runFixtureChain enter this private registry.
export function verifyFixtureChain(chain,{packet,draft,assessment,card,use_at=chain?.decision_cutoff}={}){
 validateSlice('FixtureResearchChain',chain);
 const record=issued.get(chain.content_hash);check(record&&equal(record.chain,chain),'SLICE_REF_INVALIDATED');
 check(!record.revoked_reason&&!revokedParentRefs.has('receipt:'+canonical(chain.receipt_ref))&&!revokedParentRefs.has('policy:'+canonical(record.packet.receipt.policy_ref)),'SLICE_CARD_INVALIDATED');
 assertArtifacts({packet,draft,assessment,card});
 for(const name of ['packet','draft','assessment','card'])check(equal(record[name],{packet,draft,assessment,card}[name]),'SLICE_REF_INVALIDATED');
 for(const [name,object] of [['packet',packet],['draft',draft],['assessment',assessment],['card',card]])check(equal(chain[name+'_ref'],reference(object)),'SLICE_REF_INVALIDATED');
 check(currentHeads.get(CHAIN_ID)?.content_hash===chain.content_hash,'SLICE_CARD_INVALIDATED');
 use_at??=packet.decision_cutoff;
 const useNs=exactFixtureTimestamp(use_at),cutoffNs=exactFixtureTimestamp(packet.decision_cutoff),expiryNs=exactFixtureTimestamp(card.invalidation.valid_until);
 check(useNs>=cutoffNs&&useNs<=expiryNs,'SLICE_CARD_INVALIDATED');
 check(chain.max_action===assessment.next_action&&equal(chain.receipt_ref,closureRef(packet.receipt))&&equal(chain.snapshot_ref,packet.snapshot_ref),'SLICE_REF_INVALIDATED');
 check(equal(chain.source_evidence_refs,packet.evidence.map(closureRef))&&chain.semantics_input_hash===hashValue(record.input),'SLICE_REF_INVALIDATED');
 check(equal(chain.invalidation.parent_refs,[closureRef(packet),closureRef(draft),reference(assessment),reference(card),structuredClone(packet.snapshot_ref),closureRef(packet.receipt)])&&chain.invalidation.valid_until===card.invalidation.valid_until,'SLICE_REF_INVALIDATED');
 return true;
}

// Revocation narrows existing fixture authority only. There is deliberately no
// clear-revocation, grant, restore-from-archive or real-receipt API.
export function invalidateFixtureChain(chain,{reason}={}){
 const record=issued.get(chain?.content_hash);check(record&&equal(record.chain,chain),'SLICE_REF_INVALIDATED');
 check(['RECEIPT_REVOKED','POLICY_REVOKED','CARD_SUPERSEDED'].includes(reason),'SLICE_PERMISSION_DENIED');
 record.revoked_reason??=reason;
 if(reason==='RECEIPT_REVOKED')revokedParentRefs.add('receipt:'+canonical(chain.receipt_ref));
 if(reason==='POLICY_REVOKED')revokedParentRefs.add('policy:'+canonical(record.packet.receipt.policy_ref));
 return {scope:'SYNTHETIC_TEST_ONLY',chain_ref:reference(chain),card_ref:structuredClone(chain.card_ref),invalidation_reason:record.revoked_reason,can_produce_order:false,production_enabled:false};
}

export function compareFixtureChains(previous,next){
 for(const chain of [previous,next]){const record=issued.get(chain?.content_hash);check(record&&equal(record.chain,chain),'SLICE_REF_INVALIDATED');}
 const changed_ref_names=['packet_ref','draft_ref','assessment_ref','card_ref','snapshot_ref','receipt_ref'].filter(k=>!equal(previous[k],next[k]));
 return {scope:'SYNTHETIC_TEST_ONLY',changed_ref_names,invalidated_card_refs:changed_ref_names.length?[structuredClone(previous.card_ref)]:[],unaffected_ref_names:['packet_ref','draft_ref','assessment_ref','snapshot_ref','receipt_ref'].filter(k=>equal(previous[k],next[k])),real_snapshot_B_exists:false};
}

export async function runFixtureChain({directory,fixture_case='BASE'}={}){
 check(Object.hasOwn(cases.cases,fixture_case),'SLICE_SCOPE_MISMATCH');
 const selected=structuredClone(cases.cases[fixture_case]);
 const f=await buildClosureFixture({strategy_id:'CORE_40',dataOptions:{barClose:selected.bar_close}});
 try{
  const before=await executionState(f.db);
  const packet=await buildBrainPacket({service:f.service,snapshot:f.snapshot,receipt:f.receipt,now:f.now});
  const exported=await writeManualExport({service:f.service,packet,snapshot:f.snapshot,directory,now:f.now});
  const consumer=await runIsolatedConsumer({service:f.service,packet,snapshot:f.snapshot,export_path:exported.path,now:f.now,probeOptions:{network:true,exec:true,capability_discovery:true}});
  const imported=await importResearchResult({...f,packet,result:consumer.result});
  const draft=imported.draft,input=semanticInput(selected),assessment=assessSemantics(input);
  // The packet is checked at the composition's final boundary, not solely export.
  await f.service.verifyPacket({packet,snapshot:f.snapshot,purpose:f.purpose,strategy_id:'CORE_40',now:f.now});
  const fingerprint=hashValue({packet_ref:closureRef(packet),draft_ref:closureRef(draft),assessment_ref:reference(assessment),semantics_input_hash:hashValue(input)});
  const head=currentHeads.get(CHAIN_ID),version=head?.fingerprint===fingerprint?head.object_version:(head?.object_version??0)+1;
  const trace_id='synthetic:fixture-chain:'+fingerprint.slice(7);
  const card=compatibilityCard({packet,draft,assessment,trace_id,version,valid_until:f.receipt.expires_at});
  assertArtifacts({packet,draft,assessment,card});
  const chain=sealContract({contract_name:'FixtureResearchChain',contract_version:'1.0.0',object_id:CHAIN_ID,object_version:version,trace_id,scope:'SYNTHETIC_TEST_ONLY',namespace:'CORE_40',packet_ref:closureRef(packet),draft_ref:closureRef(draft),assessment_ref:reference(assessment),card_ref:reference(card),snapshot_ref:structuredClone(packet.snapshot_ref),receipt_ref:closureRef(packet.receipt),source_evidence_refs:packet.evidence.map(closureRef),semantics_input_hash:hashValue(input),semantics_version:'1.0.0',max_action:assessment.next_action,real_grade:'UNSET_REQUIRED',tradeable:false,can_produce_order:false,production_enabled:false,real_account_suitability:'BLOCKED',real_net_edge:'UNSET_REQUIRED',real_sizing:'UNSET_REQUIRED',probability:'UNSET_REQUIRED',invalidation:{status:'ACTIVE',parent_refs:[closureRef(packet),closureRef(draft),reference(assessment),reference(card),structuredClone(packet.snapshot_ref),closureRef(packet.receipt)],valid_until:f.receipt.expires_at,conditions:['UPSTREAM_HASH_OR_VERSION_CHANGED','RECEIPT_REVOKED','POLICY_REVOKED','TTL_EXPIRED','CARD_SUPERSEDED']}});
  validateSlice('FixtureResearchChain',chain);
  const after=await executionState(f.db);check(equal(before,after),'SLICE_PERMISSION_DENIED');
  check(consumer.execution_writes===0&&consumer.broker_transport_calls===0,'SLICE_PERMISSION_DENIED');
  check(consumer.probes.network.denied&&consumer.probes.execution.every(x=>x.denied)&&consumer.probes.write.denied&&consumer.native_os_probes.network.denied&&consumer.native_os_probes.execution.every(x=>x.denied)&&consumer.native_os_probes.write.denied,'SLICE_PERMISSION_DENIED');
  check(!issued.get(chain.content_hash)?.revoked_reason&&!revokedParentRefs.has('receipt:'+canonical(chain.receipt_ref))&&!revokedParentRefs.has('policy:'+canonical(packet.receipt.policy_ref)),'SLICE_CARD_INVALIDATED');
  issued.set(chain.content_hash,structuredClone({chain,packet,draft,assessment,card,input}));
  currentHeads.set(CHAIN_ID,{content_hash:chain.content_hash,fingerprint,object_version:version});
  verifyFixtureChain(chain,{packet,draft,assessment,card,use_at:f.now});
  const identity={scope:'SYNTHETIC_TEST_ONLY',chain_ref:reference(chain),source_evidence_refs:packet.evidence.map(closureRef),source_raw_hashes:[f.securityObservation.raw_sha256,f.calendarObservation.raw_sha256,f.barObservation.raw_sha256],semantics_input_hash:hashValue(input),semantics_evidence_role:'ILLUSTRATIVE_FIXED_COORDINATE_NOT_DERIVED_COMPANY_FACT',draft_cost_test:structuredClone(draft.cost_test),phase_order:imported.phase_order,file_byte_hash:exported.byte_hash,execution_state_hash:hashValue(before)};
  return {chain,packet,draft,assessment,card,receipt:f.receipt,identity,replay_hash:hashValue(identity),isolation:consumer.isolation,probes:consumer.probes,native_os_probes:consumer.native_os_probes,execution_state_before:before,execution_state_after:after,execution_writes:consumer.execution_writes,broker_transport_calls:consumer.broker_transport_calls,real_stock_research_gate:'BLOCKED',production_enabled:false};
 }finally{await f.db.close();}
}
