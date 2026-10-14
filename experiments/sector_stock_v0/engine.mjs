import fs from 'node:fs';
import crypto from 'node:crypto';
import Ajv from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import Decimal from 'decimal.js';

const D = Decimal.clone({precision:40, rounding:Decimal.ROUND_HALF_UP});
const rawConfig = fs.readFileSync(new URL('./config.json', import.meta.url));
const freeze = x => { if (x && typeof x === 'object') { Object.values(x).forEach(freeze); Object.freeze(x); } return x; };
export const config = freeze(JSON.parse(rawConfig));
export const sha = bytes => 'sha256:' + crypto.createHash('sha256').update(bytes).digest('hex');
export const configHash = sha(rawConfig);
export const engineHash = sha(fs.readFileSync(new URL(import.meta.url)));
export function canonical(x) {
  if (Array.isArray(x)) return '[' + x.map(canonical).join(',') + ']';
  if (x && typeof x === 'object') return '{' + Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',') + '}';
  return JSON.stringify(x);
}
export function seal(x) { const {content_hash, ...body} = x; return {...body, content_hash:sha(canonical(body))}; }
export const ref = x => ({kind:x.kind, object_id:x.object_id, object_version:x.object_version, content_hash:x.content_hash});
const ajv = new Ajv({allErrors:true, strict:true}); addFormats(ajv);
const validators = Object.fromEntries(['EvidenceBundle','ResearchHypothesis','ScoreInput','ScoreResult','CandidateSet','ValidationResult'].map(name=>[name,ajv.compile(JSON.parse(fs.readFileSync(new URL('../../contracts/sector-stock-v0/'+name+'.schema.json',import.meta.url))))]));
export class ContractError extends Error { constructor(code) { super(code); this.code=code; } }
const requireThat = (ok,code) => {if(!ok) throw new ContractError(code);};
const sameRef = (r,x) => canonical(r)===canonical(ref(x));
export function validate(x) {
  requireThat(x && validators[x.kind]?.(x),'SCHEMA_INVALID');
  requireThat(x.content_hash===seal(x).content_hash,'CONTENT_HASH_MISMATCH');
  requireThat(x.config_hash===configHash,'CONFIG_HASH_MISMATCH');
  requireThat(Date.parse(x.recorded_at)>=Date.parse(x.decision_cutoff),'RECORDED_BEFORE_CUTOFF');
  if(x.kind==='ScoreResult') {
    requireThat(x.state==='BLOCKED' ? x.raw_score===null && x.final_score===null && x.risk_deduction===null && x.reason_codes.length>0 : x.raw_score!==null && x.final_score!==null && x.risk_deduction!==null && x.reason_codes.length===0, 'RESULT_STATE_INVALID');
    for(const s of [x.raw_score,x.final_score,...Object.values(x.components)]) if(s!==null) requireThat(new D(s).gte(0)&&new D(s).lte(100),'SCORE_RANGE');
  }
  if(x.kind==='CandidateSet') requireThat(x.state==='EXPERIMENTAL_ONLY' ? x.members.length>0 && x.score_refs.length===x.members.length && x.hypothesis_refs.length===x.members.length : x.members.length===0 && x.score_refs.length===0, 'CANDIDATE_STATE_INVALID');
  if(x.kind==='ValidationResult' && x.scope==='NOT_RUN') requireThat(x.checks_passed===0&&x.checks_failed===0,'NOT_RUN_HAS_RESULTS');
  return x;
}
const compatible = (x,y) => requireThat(x.decision_cutoff===y.decision_cutoff && x.result_type===y.result_type && x.trace_id===y.trace_id, 'CROSS_CONTEXT_REFERENCE');
function bind(r,x,owner) { validate(x); requireThat(sameRef(r,x),'REFERENCE_MISMATCH'); compatible(owner,x); }
function evidenceChecks(bundle, input, reasons) {
  const facts=new Map(); const cutoff=Date.parse(input.decision_cutoff);
  for(const f of bundle.facts) {
    requireThat(!facts.has(f.evidence_id),'DUPLICATE_EVIDENCE_ID'); facts.set(f.evidence_id,f);
    requireThat(f.subject_id===input.subject_id,'EVIDENCE_SUBJECT_MISMATCH');
    const times=['event_time','published_at','available_at','retrieved_at'].map(k=>Date.parse(f[k]));
    if(times.some(t=>t>cutoff)) reasons.add('FUTURE_EVIDENCE');
    // This contract is current observation only: retrieval is a conservative availability floor.
    if(times[1]>times[2] || times[3]>times[2]) reasons.add('INVALID_CLOCK_ORDER');
    if(Date.parse(f.expires_at)<cutoff) reasons.add('STALE_EVIDENCE');
    if(f.clock_basis!==(input.result_type==='SYNTHETIC'?'SYNTHETIC_FIXTURE':'CURRENT_OBSERVATION_ONLY')) reasons.add('EVIDENCE_TYPE_MISMATCH');
  }
  return facts;
}
export function evaluate(input, bundle, sectorContext=null) {
  validate(input); requireThat(input.kind==='ScoreInput','WRONG_INPUT_KIND');
  bind(input.evidence_bundle_ref,bundle,input); requireThat(bundle.kind==='EvidenceBundle' && bundle.subject_id===input.subject_id,'BUNDLE_SUBJECT_MISMATCH');
  const reasons=new Set(), facts=evidenceChecks(bundle,input,reasons);
  const keys=input.level==='SECTOR' ? config.sector_metrics : config.stock_factors.flatMap(f=>f.inputs);
  requireThat(Object.keys(input.metrics).sort().join('|')===[...keys].sort().join('|'),'METRIC_SET_MISMATCH');
  const supported = (ids,metric,value,unit) => ids.length>0 && ids.every(id=>{
    const f=facts.get(id);
    return f && f.metric===metric && f.value===value && f.unit===unit;
  });
  for(const [key,item] of Object.entries(input.hard_gates)) {
    if(item.state!=='PASS') reasons.add('HARD_GATE_'+key.toUpperCase()+'_'+item.state);
    if(item.state!=='UNKNOWN'&&!supported(item.evidence_ids,'gate:'+key,item.state==='PASS'?'1':'0','BOOLEAN')) reasons.add('RISK_EVIDENCE_MISSING');
  }
  let penalty=new D(0);
  for(const [key,item] of Object.entries(input.risk_flags)) {
    if(item.state==='UNKNOWN') reasons.add('RISK_UNKNOWN');
    else if(!supported(item.evidence_ids,'risk:'+key,item.state==='PRESENT'?'1':'0','BOOLEAN')) reasons.add('RISK_EVIDENCE_MISSING');
    if(item.state==='PRESENT') penalty=penalty.plus(config.risk_penalties[key]);
  }
  const normalized={};
  for(const key of keys) {
    const m=input.metrics[key], rule=config.metrics[key];
    if(m.value===null) { reasons.add('MISSING_'+key.toUpperCase()); normalized[key]=null; continue; }
    const value=new D(m.value);
    if(m.unit!==rule.unit) reasons.add('UNIT_MISMATCH');
    if(!supported(m.evidence_ids,key,m.value,m.unit)) reasons.add('METRIC_EVIDENCE_MISMATCH');
    if(rule.domain && (value.lt(rule.domain[0])||value.gt(rule.domain[1]))) reasons.add('METRIC_OUT_OF_DOMAIN');
    if(rule.unit==='SIGNED_COUNT' && (!value.isInteger() || m.evidence_ids.some(id=>!facts.get(id)?.coding_record))) reasons.add('CODING_RECORD_REQUIRED');
    normalized[key]=D.max(0,D.min(100,value.minus(rule.score_zero).div(new D(rule.score_hundred).minus(rule.score_zero)).times(100)));
  }
  let sector=null;
  if(input.level==='STOCK') {
    if(!sectorContext || !input.sector_result_ref || !input.sector_id) reasons.add('SECTOR_RESULT_REQUIRED');
    else {
      // Always recompute upstream result; a hand-edited score with a fresh hash is not accepted.
      requireThat(sectorContext.input.level==='SECTOR','SECTOR_KIND_REQUIRED');
      sector=evaluate(sectorContext.input,sectorContext.bundle);
      bind(input.sector_result_ref,sector,input);
      requireThat(sector.subject_id===input.sector_id,'SECTOR_MEMBERSHIP_MISMATCH');
      if(sector.state!=='COMPUTED_EXPERIMENTAL') reasons.add('SECTOR_BLOCKED');
    }
  } else requireThat(input.sector_id===null&&input.sector_result_ref===null,'UNEXPECTED_SECTOR_REFERENCE');
  const components=input.level==='SECTOR' ? normalized : Object.fromEntries(config.stock_factors.map(f=>{
    if(f.id==='sector_benefit') return [f.id,sector?.final_score!==null && sector && normalized.sector_revenue_share!==null ? new D(sector.final_score).times(input.metrics.sector_revenue_share.value) : null];
    const values=f.inputs.map(k=>normalized[k]);
    return [f.id, values.includes(null)?null:values.reduce((a,b)=>a.plus(b),new D(0)).div(values.length)];
  }));
  const blocked=reasons.size>0 || Object.values(components).includes(null);
  let raw=null;
  if(!blocked) raw=input.level==='SECTOR' ? Object.values(components).reduce((a,b)=>a.plus(b),new D(0)).div(9) : config.stock_factors.reduce((a,f)=>a.plus(components[f.id].times(f.weight_percent).div(100)),new D(0));
  const result=seal({kind:'ScoreResult',engine_sha256:engineHash,contract_version:input.contract_version,experiment_id:input.experiment_id,namespace:input.namespace,object_id:input.object_id+':score',object_version:input.object_version,trace_id:input.trace_id,recorded_at:input.recorded_at,decision_cutoff:input.decision_cutoff,result_type:input.result_type,config_hash:configHash,productionGate:false,native_refs:input.native_refs,level:input.level,subject_id:input.subject_id,input_ref:ref(input),evidence_bundle_ref:ref(bundle),sector_result_ref:input.sector_result_ref,state:blocked?'BLOCKED':'COMPUTED_EXPERIMENTAL',raw_score:raw?.toFixed(2)??null,risk_deduction:blocked?null:penalty.toFixed(2),final_score:raw===null?null:D.max(0,raw.minus(penalty)).toFixed(2),components:Object.fromEntries(Object.entries(components).map(([k,v])=>[k,v?.toFixed(2)??null])),reason_codes:[...reasons].sort(),probability:null,formal_candidate:false,can_produce_order:false});
  return validate(result);
}

/** Resolve experimental lineage only. Native refs are pointers, never approval or evidence of admission. */
export function validateGraph(objects) {
  objects.forEach(validate); const map=new Map();
  for(const o of objects) { const k=o.kind+':'+o.object_id+':'+o.object_version; requireThat(!map.has(k),'DUPLICATE_OBJECT'); map.set(k,o); }
  const resolve=(r,owner,kind)=>{requireThat(r.kind===kind,'REFERENCE_KIND');const x=map.get(r.kind+':'+r.object_id+':'+r.object_version);requireThat(x,'REFERENCE_UNRESOLVED');bind(r,x,owner);return x;};
  for(const o of objects) {
    if(['ScoreInput','ResearchHypothesis'].includes(o.kind)) {const b=resolve(o.evidence_bundle_ref,o,'EvidenceBundle');requireThat(b.subject_id===o.subject_id,'BUNDLE_SUBJECT_MISMATCH');}
    if(o.kind==='ScoreResult') {
      const i=resolve(o.input_ref,o,'ScoreInput'),b=resolve(o.evidence_bundle_ref,o,'EvidenceBundle');let context=null;
      if(o.sector_result_ref){const s=resolve(o.sector_result_ref,o,'ScoreResult');context={input:resolve(s.input_ref,o,'ScoreInput'),bundle:resolve(s.evidence_bundle_ref,o,'EvidenceBundle')};}
      requireThat(o.content_hash===evaluate(i,b,context).content_hash,'RESULT_RECOMPUTATION_MISMATCH');
    }
    if(o.kind==='CandidateSet') {
      requireThat(new Set(o.members).size===o.members.length,'DUPLICATE_MEMBER');
      o.score_refs.forEach((r,n)=>{const s=resolve(r,o,'ScoreResult');requireThat(s.level==='STOCK'&&s.state==='COMPUTED_EXPERIMENTAL'&&s.subject_id===o.members[n],'CANDIDATE_SCORE_INVALID');});
      o.hypothesis_refs.forEach((r,n)=>requireThat(resolve(r,o,'ResearchHypothesis').subject_id===o.members[n],'HYPOTHESIS_MEMBER_MISMATCH'));
    }
    if(o.kind==='ValidationResult'&&o.candidate_set_ref) resolve(o.candidate_set_ref,o,'CandidateSet');
  }
  return {state:'VALID_EXPERIMENTAL_GRAPH',investment_effectiveness:'NOT_ESTABLISHED',productionGate:false};
}
