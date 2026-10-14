// Bounded read-only admission. No new economic rule is adopted here.
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {assess,unknownRisks,candidateHash,applicabilityHash} from './applicability.mjs';
export function applicability(){return ['SECTOR','STOCK'].map(level=>assess(level,unknownRisks(level)));}
export {candidateHash,applicabilityHash};
import {config,configHash,engineHash,seal,sha,canonical,evaluate,validateGraph,ref} from '../sector_stock_v0/engine.mjs';
export {seal,sha,configHash,engineHash};
export const adapterHash=sha(fs.readFileSync(new URL(import.meta.url)));
function need(ok,code){if(!ok)throw new Error(code);}
export function blockedGraph(meta){
 const common=(kind,id)=>({kind,contract_version:'0.1.0-candidate',experiment_id:config.experiment_id,namespace:config.namespace,object_id:id,object_version:'1',trace_id:meta.trace_id,recorded_at:meta.recorded_at,decision_cutoff:meta.decision_cutoff,result_type:'CURRENT_OBSERVED_RESEARCH_ONLY',config_hash:configHash,productionGate:false,native_refs:[]});
 function entry(level,subject,sector=null){
  const bundle=seal({...common('EvidenceBundle',subject+':evidence'),subject_id:subject,facts:[{evidence_id:'local-coverage-audit',subject_id:subject,source:'LOCAL_REVIEW_METADATA_NOT_MARKET_DATA',source_version:'score-review-v01',raw_hash:sha(canonical(meta.field_matrix)),revision_id:'1',locator:'package:field_matrix',event_time:meta.decision_cutoff,published_at:meta.decision_cutoff,available_at:meta.decision_cutoff,retrieved_at:meta.decision_cutoff,expires_at:meta.decision_cutoff,clock_basis:'CURRENT_OBSERVATION_ONLY',metric:'admitted_score_inputs_complete',value:'0',unit:'BOOLEAN',coding_record:null}],historical_visibility_proven:false});
  const keys=level==='SECTOR'?config.sector_metrics:config.stock_factors.flatMap(f=>f.inputs);
  const input=seal({...common('ScoreInput',subject+':input'),level,subject_id:subject,sector_id:sector?.subject_id??null,sector_result_ref:sector?ref(sector):null,evidence_bundle_ref:ref(bundle),metrics:Object.fromEntries(keys.map(k=>[k,{value:null,unit:config.metrics[k].unit,evidence_ids:[]}])),hard_gates:Object.fromEntries(config.hard_gates.map(k=>[k,{state:'UNKNOWN',evidence_ids:[]}])),risk_flags:Object.fromEntries(Object.keys(config.risk_penalties).map(k=>[k,{state:'UNKNOWN',evidence_ids:[]}]))});
  return {input,bundle};
 }
 const sector=entry('SECTOR',meta.sector_id);const sr=evaluate(sector.input,sector.bundle);const stock=entry('STOCK',meta.symbol,sr);const tr=evaluate(stock.input,stock.bundle,sector);
 return [sector.bundle,sector.input,sr,stock.bundle,stock.input,tr];
}
export function validatePackage(p){
 need(p?.kind==='CurrentObservationScoreReviewPackage'&&p.version==='0.1.0-admission','PACKAGE_VERSION');
 need(p.content_hash===seal(p).content_hash,'PACKAGE_HASH');
 need(p.candidate_sha256===candidateHash&&p.applicability_sha256===applicabilityHash&&canonical(p.applicability)===canonical(applicability()),'APPLICABILITY_BINDING');
 need(p.config_sha256===configHash&&p.engine_sha256===engineHash&&p.adapter_sha256===adapterHash,'CODE_CONFIG_MISMATCH');
 need(p.method_state==='OWNER_PENDING'&&p.formal_candidate===false&&p.can_produce_order===false,'METHOD_NOT_APPROVED');
 need(p.symbol==='603228.SH'&&p.sector_id==='PROPOSED:PCB_MANUFACTURING'&&p.peer_count===1,'SCOPE_MISMATCH');
 // Raw facts with unknown clocks/units never masquerade as score-ready EvidenceBundle facts.
 // Exactly the expected blocked graph, including upstream sector ref, is recomputed.
 validateGraph(p.objects);
 need(canonical(p.objects)===canonical(blockedGraph(p)),'UNAPPROVED_SCORE_OR_INPUT');
 need(Array.isArray(p.field_matrix)&&p.field_matrix.length===18,'FIELD_COVERAGE');
 const expected=[...config.sector_metrics,...config.stock_factors.flatMap(f=>f.inputs)].sort();
 need(canonical(p.field_matrix.map(f=>f.metric).sort())===canonical(expected),'FIELD_SET');
 for(const f of p.field_matrix)need(f.score_input_value===null&&f.status==='BLOCKED'&&Array.isArray(f.gaps)&&f.gaps.length>0,'UNADMITTED_FIELD');
 need(p.historical_visibility_proven===false&&p.local_only===true,'SOURCE_PROMOTION');
 return {kind:p.kind,version:p.version,package_hash:p.content_hash,recorded_at:p.recorded_at,decision_cutoff:p.decision_cutoff,symbol:p.symbol,sector_id:p.sector_id,peer_count:p.peer_count,method_state:p.method_state,result_type:'CURRENT_OBSERVED_RESEARCH_ONLY',label:'当前观察研究 / 候选方法 / 非交易建议',candidate_version:'0.2.0-candidate',applicability:p.applicability,scores:p.objects.filter(x=>x.kind==='ScoreResult'),fields:p.field_matrix.map(({metric,unit,status,gaps,calculation})=>({metric,unit,status,gaps,calculation})),raw_values_exported:false,formal_candidate:false,can_produce_order:false};
}
if(process.argv[1]&&fileURLToPath(import.meta.url)===process.argv[1]){
 try {const p=JSON.parse(fs.readFileSync(0,'utf8'));process.stdout.write(JSON.stringify(validatePackage(p)));}
 catch(e){process.stderr.write(e.message+'\n');process.exitCode=1;}
}
