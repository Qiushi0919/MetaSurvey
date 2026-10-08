import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {captureApprovedReferences} from './capture.mjs';
import {normalizeCapture} from '../src/providers.mjs';
import {createAdmissionService,SECURITIES} from '../src/core.mjs';
import {refOf,hash,canonical,sha,requireSlice} from '../src/contracts.mjs';
import {verifyProvenance,epochOf,root} from './provenance.mjs';
import {verifyProvenance as verifyPrevious} from '../../p1b/scripts/provenance.mjs';
import {loadCodeProvenance,verifyCodeProvenance} from '../../src/p1a/code-provenance.mjs';

export async function createLiveSlice({archiveDirectory}={}){
 requireSlice(typeof archiveDirectory==='string'&&path.isAbsolute(archiveDirectory)&&!path.resolve(archiveDirectory).startsWith(root+path.sep),'SLICE_PERMISSION_DENIED');
 const pin=await verifyProvenance();await verifyPrevious();const old=await loadCodeProvenance();await verifyCodeProvenance(old);
 const codeEpoch=epochOf(pin),capture=await captureApprovedReferences({archiveDirectory,capturePdfOriginals:false});
 const use_at=new Date().toISOString(),{collector,handles}=capture,termsHandle=handles[0],sourceHandles=handles.slice(1);
 const config={collector,normalize:normalizeCapture,termsHandle,codeEpoch};
 const planner=createAdmissionService(config),observations=[],policies=[];
 for(const handle of sourceHandles){const o=await planner.observe(handle);observations.push(o);policies.push(await planner.policyFor(o,use_at));}
 // Exact finite policy hashes are accepted by the trusted parent under the
 // owner's captured official-website-reference decision. No consumer mutator.
 const service=createAdmissionService({...config,approvedPolicyHashes:policies.map(p=>p.content_hash)});
 for(let i=0;i<sourceHandles.length;i++){const actual=await service.observe(sourceHandles[i]);requireSlice(canonical(actual)===canonical(observations[i]),'SLICE_REF_INVALIDATED');await service.registerPolicy(policies[i]);}
 const stocks=[];
 for(const symbol of SECURITIES){const indices=observations.map((o,i)=>o.data_type==='CALENDAR_RULES'||o.coverage.symbols.includes(symbol)?i:null).filter(i=>i!==null),request={observation_refs:indices.map(i=>refOf(observations[i])),policy_refs:indices.map(i=>refOf(policies[i])),use_at};
  const snapshot=await service.snapshot(request),receipt=await service.admit(snapshot),packet=await service.packet(snapshot,receipt),context={snapshot,receipt,packet,use_at};await service.verifyPacket(context);await service.transfer(context,'LOCAL_REVIEW_ONLY');
  const replay=await service.snapshot(request),replayReceipt=await service.admit(replay),replayPacket=await service.packet(replay,replayReceipt);requireSlice(canonical({snapshot,receipt,packet})===canonical({snapshot:replay,receipt:replayReceipt,packet:replayPacket}),'SLICE_REF_INVALIDATED');
  stocks.push({symbol,snapshot,receipt,packet,deterministic_same_capture_replay:true});
 }
 const evidence={version:'1.0.0',stage:'P1B_REAL_STOCK_SLICE',scope:'ACTUAL_CURRENT_OBSERVED_REFERENCE_ONLY',code_version:pin.code_version,source_tree_hash:pin.source_tree_hash,code_epoch:codeEpoch,actual_capture_date_shanghai:new Date(Date.parse(use_at)+8*3600000).toISOString().slice(0,10),decision_cutoff:use_at,capture_manifest_hash:hash(capture.manifest),collector_public_key_der:collector.publicKeyDer,issuer_public_key_der:service.publicKeyDer,observations,approved_policy_hashes:policies.map(p=>p.content_hash),policies,stocks,
  counts:{captured_originals:capture.manifest.records.length,admitted_source_identities:new Set(observations.map(o=>o.source_id)).size,admitted_products:new Set(observations.map(o=>o.product)).size,admitted_stock_reference_count:stocks.length,stock_snapshot_count:stocks.length,admission_receipt_count:stocks.length,sanitized_local_brainpacket_count:stocks.length,announcement_reference_count:observations.filter(o=>o.data_type==='ANNOUNCEMENTS').reduce((n,o)=>n+o.facts.length,0),parsed_market_rows:0,parsed_financial_rows:0,model_calls:0,broker_calls:0,execution_writes:0},
  LOCAL_REAL_RESEARCH_GATE:'PARTIAL',CLOUD_RESEARCH_EXPORT_GATE:'BLOCKED',HISTORICAL_BACKTEST_GATE:'BLOCKED',PRODUCTION_DATA_GATE:'BLOCKED',redistribution:'DENIED',TUSHARE:'BLOCKED_NO_VERIFIABLE_ENTITLEMENT',historical_visibility_proven:false,research_pilot_authorized:false,production_enabled:false,archival_proof_restores_live_authority:false,snapshot_B:{status:'PENDING_ACTUAL_POST_HOLIDAY_DATA',actual_comparison_performed:false},latest_trading_session_reason:'NO_ADMITTED_COMPLETE_SESSION_CALENDAR',raw_originals_in_git:false};
 const evidencePath=path.join(archiveDirectory,'real-slice-evidence.json');await fs.writeFile(evidencePath,JSON.stringify(evidence,null,2)+'\n',{flag:'wx'});
 // Only trusted parent/reviewer code gets live capability. Evidence records are
 // deliberately insufficient to reconstruct issuer authority after exit.
 return {evidence,evidencePath,capture,service,config,observations,policies,stocks,use_at};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const archiveDirectory=process.argv[2]??path.resolve(root,'../.p1b-archives/real-stock-slice-20261005/final-A-'+new Date().toISOString().replaceAll(':','').replaceAll('.',''));
 const result=await createLiveSlice({archiveDirectory});console.log(JSON.stringify({evidence_path:result.evidencePath,evidence_sha256:sha(await fs.readFile(result.evidencePath)),...result.evidence.counts,LOCAL_REAL_RESEARCH_GATE:result.evidence.LOCAL_REAL_RESEARCH_GATE,snapshot_A_market_state:result.stocks.map(s=>s.snapshot.market_state),snapshot_B:result.evidence.snapshot_B},null,2));
}
