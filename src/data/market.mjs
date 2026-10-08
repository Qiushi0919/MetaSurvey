import Decimal from 'decimal.js';
import { hashValue,requireThat,timestampMs,derived,putObject,ref,allKind,readRaw,assertFacts,assertPositiveDecimal,assertDate } from './core.mjs';
const D=Decimal.clone({precision:100,rounding:Decimal.ROUND_HALF_UP});
const price = value => {requireThat(typeof value==='string'&&/^(0|[1-9]\d{0,13})(\.\d{1,6})?$/.test(value),'PRICE_DECIMAL_REQUIRED');return new D(value);};
export async function ingestBar(db,{observation,security,calendar,status=null,trade_date,open,high,low,close,preclose=null,volume,amount_cents,price_basis='RAW',adjustment=null,object_id,object_version=1}) {
  assertDate(trade_date);
  const p=[open,high,low,close].map(price);const validOHLC=p[1].gte(D.max(...p))&&p[2].lte(D.min(...p));
  requireThat(Number.isSafeInteger(volume)&&volume>=0&&typeof amount_cents==='string'&&/^(0|[1-9]\d{0,37})$/.test(amount_cents),'BAR_INTEGER_REQUIRED');
  requireThat(['RAW','ADJUSTED'].includes(price_basis)&&(price_basis==='RAW'?adjustment===null:adjustment?.kind==='ADJUSTMENT'),'ADJUSTMENT_VERSION_REQUIRED');
  requireThat(security.kind==='SECURITY'&&calendar.kind==='CALENDAR'&&security.payload.exchange===calendar.payload.exchange,'BAR_IDENTITY_CALENDAR_MISMATCH');
  if(adjustment)requireThat(adjustment.security_id===security.security_id,'ADJUSTMENT_SECURITY_MISMATCH');
  const day=calendar.payload.days.find(d=>d.date===trade_date),validDay=day?.status==='TRADING';
  const knownStatus=security.payload.listing_status==='LISTED'&&security.payload.suspension_status==='TRADING'&&security.payload.st_status!=='UNKNOWN'&&security.payload.lot_size!==null;
  const reasons=[...observation.reason_codes,...(!validOHLC?['OHLC_INVALID']:[]),...(!validDay?['CALENDAR_DAY_NON_TRADEABLE']:[]),...(!knownStatus?['SECURITY_STATUS_UNKNOWN']:[]),...(preclose===null?['PRECLOSE_UNAVAILABLE']:[])];
  if(preclose!==null)price(preclose);
  if(observation.scope==='SYNTHETIC')assertFacts(observation,{canonical_symbol:security.canonical_symbol,trade_date,open,high,low,close,preclose,volume,amount_cents,price_basis});
  const pass=validOHLC&&validDay&&knownStatus&&preclose!==null&&observation.data_quality_status==='PASS';
  const payload={trade_date,open,high,low,close,preclose,volume,amount_cents,price_basis,adjustment_version:adjustment?`${adjustment.object_id}:${adjustment.object_version}`:'NOT_APPLICABLE',corporate_action_lineage:adjustment?.payload.action_refs??[],calendar_ref:ref(calendar),security_ref:ref(security)};
  if(status)requireThat(status.kind==='STATUS'&&status.security_id===security.security_id,'STATUS_SECURITY_MISMATCH');
  const out=await putObject(db,derived(observation,{kind:'BAR_1D',object_id:object_id??`bar:${security.security_id}:${trade_date}:${price_basis}:${observation.object_id}`,object_version,payload,security_id:security.security_id,canonical_symbol:security.canonical_symbol,original_symbol:observation.original_symbol??security.original_symbol,event_time:`${trade_date}T15:00:00+08:00`,lineage_refs:[ref(security),ref(calendar),...(status?[ref(status)]:[]),...(adjustment?[ref(adjustment)]:[])],data_quality_status:pass?'PASS':'QUARANTINED',tradeability:pass&&security.tradeability==='OFFLINE_ELIGIBLE'&&calendar.tradeability==='OFFLINE_ELIGIBLE'?observation.tradeability:'NON_TRADEABLE',reason_codes:reasons}));
  await db.query(`INSERT INTO p1a_data_staging(observation_id,observation_version,observation_hash,parser_version,normalized_ref,dq_status,reason_codes) VALUES($1,$2,$3,$4,$5::jsonb,$6,$7::jsonb) ON CONFLICT(observation_id,observation_version,parser_version) DO NOTHING`,[observation.object_id,observation.object_version,observation.content_hash,`bar-normalizer-1:${out.object_id}`,JSON.stringify(ref(out)),out.data_quality_status,JSON.stringify(out.reason_codes)]);return out;
}
export function parseSseDayKPayload(bytes) {
  const text=Buffer.from(bytes).toString('utf8'),header=JSON.parse(text);
  requireThat(typeof header.code==='string'&&[header.total,header.begin,header.end].every(Number.isSafeInteger),'SSE_DAYK_FORMAT_CHANGED');
  const inner=/"kline"\s*:\s*\[([\s\S]*)\]\s*\}\s*$/.exec(text)?.[1];requireThat(inner!==undefined,'SSE_DAYK_FORMAT_CHANGED');
  const rows=[...inner.matchAll(/\[([^\[\]]+)\]/g)].map(m=>m[1].split(',').map(t=>t.trim()));
  requireThat(rows.length===header.kline.length&&rows.length<=5,'SSE_DAYK_FORMAT_CHANGED');
  return {parser_version:'sse-dayk-lexemes-1',code:header.code,total:header.total,begin:header.begin,end:header.end,bars:rows.map(tokens=>{
    requireThat(tokens.length===7&&/^\d{8}$/.test(tokens[0])&&tokens.slice(1,5).every(v=>/^(0|[1-9]\d*)(\.\d{1,6})?$/.test(v))&&/^\d+$/.test(tokens[5])&&/^(0|[1-9]\d*)(\.\d{1,2})?$/.test(tokens[6]),'SSE_DAYK_FORMAT_CHANGED');
    const volume=Number(tokens[5]);requireThat(Number.isSafeInteger(volume),'SSE_DAYK_INTEGER_OVERFLOW');
    return {trade_date:tokens[0].replace(/^(\d{4})(\d{2})(\d{2})$/,'$1-$2-$3'),open:tokens[1],high:tokens[2],low:tokens[3],close:tokens[4],volume,amount_yuan:tokens[6]};
  })};
}
/** SSE display endpoint has no publish/available/preclose clocks: never fabricate them. */
export async function ingestSseDayK(db,{observation,security,calendar}) {
  requireThat(observation.source_policy.source_class==='OFFICIAL'&&new URL(observation.source_policy.url).hostname==='yunhq.sse.com.cn','SSE_DAYK_SOURCE_REQUIRED');
  const raw=parseSseDayKPayload(await readRaw(db,observation));
  requireThat(hashValue(raw)===observation.payload_sha256,'SOURCE_PAYLOAD_PARSER_MISMATCH');
  requireThat(raw.code===security.payload.code&&security.payload.exchange==='SSE','SSE_DAYK_IDENTITY_MISMATCH');
  const out=[];for(const row of raw.bars){const amount_cents=new D(row.amount_yuan).mul(100).toFixed(0);out.push(await ingestBar(db,{observation,security,calendar,...row,preclose:null,amount_cents}));}
  return out;
}
export async function ingestCorporateAction(db,{observation,security,object_id,object_version=1,action_type,ex_date,effective_date,adjustment_factor=null,terms}) {
  requireThat(['DIVIDEND','SPLIT','BONUS','RIGHTS'].includes(action_type),'ACTION_TYPE_INVALID');
  assertDate(ex_date);assertDate(effective_date);
  if(adjustment_factor!==null)assertPositiveDecimal(adjustment_factor);
  assertFacts(observation,{canonical_symbol:security.canonical_symbol,action_type,ex_date,effective_date,adjustment_factor,terms});
  return putObject(db,derived(observation,{kind:'CORPORATE_ACTION',object_id,object_version,payload:{action_type,ex_date,effective_date,adjustment_factor,terms},security_id:security.security_id,canonical_symbol:security.canonical_symbol,lineage_refs:[ref(security)],event_time:`${effective_date}T00:00:00+08:00`}));
}
export async function ingestAdjustment(db,{observation,security,object_id,object_version=1,actions,factor,method,effective_date}) {
  requireThat(Array.isArray(actions)&&actions.length>0&&actions.every(a=>a.kind==='CORPORATE_ACTION'&&a.security_id===security.security_id),'ADJUSTMENT_ACTIONS_REQUIRED');
  assertPositiveDecimal(factor);requireThat(method,'ADJUSTMENT_METHOD_REQUIRED');
  assertDate(effective_date);requireThat(actions.every(a=>effective_date>=a.payload.ex_date),'ADJUSTMENT_PRE_EX_DATE_FORBIDDEN');
  assertFacts(observation,{canonical_symbol:security.canonical_symbol,factor,method,effective_date});
  return putObject(db,derived(observation,{kind:'ADJUSTMENT',object_id,object_version,payload:{factor,method,effective_date,action_refs:actions.map(ref)},security_id:security.security_id,canonical_symbol:security.canonical_symbol,lineage_refs:[ref(security),...actions.map(ref)],event_time:`${effective_date}T00:00:00+08:00`}));
}
export async function ingestFinancialRevision(db,{observation,security,object_id,object_version=1,period,statement_type,revision_kind,values_cents,previous_revision=null}) {
  requireThat(['ORIGINAL','RESTATEMENT','SOURCE_CORRECTION'].includes(revision_kind),'FINANCIAL_REVISION_KIND_INVALID');
  assertDate(period);requireThat(statement_type&&values_cents&&Object.values(values_cents).every(v=>typeof v==='string'&&/^-?(0|[1-9]\d{0,37})$/.test(v)&&v!=='-0'),'FINANCIAL_CENTS_REQUIRED');
  if(previous_revision)requireThat(previous_revision.kind==='FINANCIAL'&&previous_revision.security_id===security.security_id&&previous_revision.object_id===object_id&&previous_revision.object_version<object_version&&previous_revision.payload.period===period&&previous_revision.payload.statement_type===statement_type,'FINANCIAL_REVISION_CHAIN_MISMATCH');
  requireThat(revision_kind==='ORIGINAL'?previous_revision===null:previous_revision!==null,'FINANCIAL_PREDECESSOR_REQUIRED');
  assertFacts(observation,{canonical_symbol:security.canonical_symbol,period,statement_type,revision_kind,values_cents});
  return putObject(db,derived(observation,{kind:'FINANCIAL',object_id,object_version,payload:{period,statement_type,revision_kind,currency:'CNY',unit:'CNY_CENTS',values_cents,previous_revision:previous_revision?ref(previous_revision):null},security_id:security.security_id,canonical_symbol:security.canonical_symbol,lineage_refs:[ref(security),...(previous_revision?[ref(previous_revision)]:[])],event_time:`${period}T00:00:00+08:00`}));
}
export async function financialsAsOf(db,{security_id,period,statement_type,decision_cutoff,verifyVisible}) {
  const cutoff=timestampMs(decision_cutoff),rows=[];
  for(const row of await allKind(db,'FINANCIAL')){
    if(row.security_id!==security_id||row.payload.period!==period||row.payload.statement_type!==statement_type||!row.available_at||timestampMs(row.available_at)>cutoff||timestampMs(row.retrieved_at)>cutoff)continue;
    try{await verifyVisible(db,row,decision_cutoff);rows.push(row);}catch{continue;}
  }
  rows.sort((a,b)=>timestampMs(b.available_at)-timestampMs(a.available_at)||b.object_version-a.object_version);
  if(rows.length>1&&rows[0].available_at===rows[1].available_at&&rows[0].object_version===rows[1].object_version&&rows[0].object_id!==rows[1].object_id)requireThat(false,'FINANCIAL_REVISION_CONFLICT');
  return rows[0]??null;
}
