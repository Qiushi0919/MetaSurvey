// SYNTHETIC ONLY: invented subjects/facts, no production defaults or real recommendations.
import {config, configHash, seal, ref, evaluate} from '../engine.mjs';
export const common=(kind,id)=>({kind,contract_version:'0.1.0-candidate',experiment_id:config.experiment_id,namespace:config.namespace,object_id:id,object_version:'1',trace_id:'synthetic-case-1',recorded_at:'2026-10-14T17:00:00+08:00',decision_cutoff:'2026-10-14T16:00:00+08:00',result_type:'SYNTHETIC',config_hash:configHash,productionGate:false,native_refs:[]});
export function fixture(level='SECTOR') {
 const subject=level==='SECTOR'?'SYNTHETIC_SECTOR':'SYNTHETIC_STOCK';const metrics={},facts=[];
 const keys=level==='SECTOR'?config.sector_metrics:config.stock_factors.flatMap(f=>f.inputs);
 const values={sector_valuation_percentile:'0.5',sector_adverse_share:'0.5',cash_conversion:'0.75',sector_revenue_share:'0.8',stock_valuation_percentile:'0.5',median_turnover_cny:'50000000',verified_fact_share:'1'};
 function add(metric,value,unit){const id='synthetic:'+metric;facts.push({evidence_id:id,subject_id:subject,source:'SYNTHETIC_FIXTURE_NOT_MARKET_DATA',source_version:'fixture-1',raw_hash:'sha256:'+'a'.repeat(64),revision_id:'synthetic-r1',locator:'synthetic:test-row:'+metric,event_time:'2026-10-13T00:00:00+08:00',published_at:'2026-10-14T14:00:00+08:00',available_at:'2026-10-14T15:00:00+08:00',retrieved_at:'2026-10-14T15:00:00+08:00',expires_at:'2026-10-15T16:00:00+08:00',clock_basis:'SYNTHETIC_FIXTURE',metric,value,unit,coding_record:'SYNTHETIC_TWO_CODER_RECORD'});return [id];}
 for(const key of keys){const value=values[key]??'0',unit=config.metrics[key].unit;metrics[key]={value,unit,evidence_ids:add(key,value,unit)};}
 const hard_gates=Object.fromEntries(config.hard_gates.map(k=>[k,{state:'PASS',evidence_ids:add('gate:'+k,'1','BOOLEAN')}]));
 const risk_flags=Object.fromEntries(Object.keys(config.risk_penalties).map(k=>[k,{state:'ABSENT',evidence_ids:add('risk:'+k,'0','BOOLEAN')}]));
 const bundle=seal({...common('EvidenceBundle',subject+':evidence'),subject_id:subject,facts,historical_visibility_proven:false});
 const input=seal({...common('ScoreInput',subject+':input'),level,subject_id:subject,sector_id:level==='STOCK'?'SYNTHETIC_SECTOR':null,sector_result_ref:null,evidence_bundle_ref:ref(bundle),metrics,hard_gates,risk_flags});
 return {input,bundle};
}
export function pair(){const sector=fixture();const stock=fixture('STOCK');stock.input=seal({...stock.input,sector_result_ref:ref(evaluate(sector.input,sector.bundle))});return {sector,stock};}
export function change(f,metric,value){f.input.metrics[metric].value=value;f.bundle.facts.find(x=>x.metric===metric).value=value;return reseal(f);}
export function reseal(f){f.bundle=seal(f.bundle);f.input=seal({...f.input,evidence_bundle_ref:ref(f.bundle)});return f;}
