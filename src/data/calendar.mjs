import { requireThat,timestampMs,derived,putObject,ref,readRaw,checkObject,assertFacts,assertDate } from './core.mjs';

export async function ingestCalendar(db,{observation,calendar_id,object_version=1,exchange,days,coverage_start,coverage_end,session_rule_version,lineage=[]}) {
  requireThat(['SSE','SZSE'].includes(exchange)&&calendar_id&&session_rule_version,'CALENDAR_IDENTITY_REQUIRED');
  requireThat(Array.isArray(days)&&days.length>0,'CALENDAR_DAYS_REQUIRED');
  assertDate(coverage_start);assertDate(coverage_end);requireThat(coverage_end>=coverage_start&&days.length<=3660,'CALENDAR_COVERAGE_INVALID');
  const seen=new Set();
  for(const d of days){assertDate(d.date);requireThat(!seen.has(d.date),'CALENDAR_DUPLICATE_OR_INVALID_DAY');seen.add(d.date);requireThat(['TRADING','NON_TRADING','UNKNOWN'].includes(d.status),'CALENDAR_DAY_STATUS_INVALID');requireThat(Array.isArray(d.sessions),'CALENDAR_SESSIONS_REQUIRED');if(d.status==='TRADING')requireThat(d.sessions.length>0,'CALENDAR_SESSIONS_REQUIRED');for(const s of d.sessions)requireThat(/^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$/.test(s.open)&&/^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$/.test(s.close)&&s.open<s.close&&s.kind,'CALENDAR_SESSION_INVALID');}
  let cursor=coverage_start;while(cursor<=coverage_end){requireThat(seen.has(cursor),'CALENDAR_COVERAGE_GAP');cursor=new Date(`${cursor}T00:00:00Z`).toISOString();cursor=new Date(Date.parse(cursor)+86400000).toISOString().slice(0,10);}
  requireThat(days.every(d=>d.date>=coverage_start&&d.date<=coverage_end),'CALENDAR_OUTSIDE_COVERAGE');
  if(observation.scope==='SYNTHETIC')assertFacts(observation,{days,exchange,coverage_start,coverage_end,session_rule_version});
  return putObject(db,derived(observation,{kind:'CALENDAR',object_id:calendar_id,object_version,payload:{exchange,coverage_start,coverage_end,days:[...days].sort((a,b)=>a.date.localeCompare(b.date)),session_rule_version,calendar_basis:observation.scope==='SYNTHETIC'?'SYNTHETIC_EXPLICIT':'OFFICIAL_BOUNDED_REFERENCE'},lineage_refs:lineage.map(ref)}));
}
export function nextTradingSession(calendar,date,{securityStatus=null,decision_cutoff=null,allow_reference=false}={}) {
  checkObject(calendar);requireThat(calendar.kind==='CALENDAR','CALENDAR_REQUIRED');
  requireThat(date>=calendar.payload.coverage_start&&date<calendar.payload.coverage_end,'CALENDAR_COVERAGE_UNKNOWN');
  if(decision_cutoff){requireThat(calendar.available_at&&timestampMs(calendar.available_at)<=timestampMs(decision_cutoff)&&timestampMs(calendar.retrieved_at)<=timestampMs(decision_cutoff),'CALENDAR_NOT_VISIBLE');}
  requireThat(allow_reference||calendar.tradeability==='OFFLINE_ELIGIBLE','CALENDAR_REFERENCE_ONLY');
  if(securityStatus)requireThat(securityStatus.payload.suspension_status==='TRADING'&&securityStatus.payload.st_status!=='UNKNOWN','SECURITY_NON_TRADEABLE');
  const next=calendar.payload.days.find(d=>d.date>date&&d.status!=='NON_TRADING');requireThat(next&&next.status==='TRADING','CALENDAR_NEXT_SESSION_UNKNOWN');
  return {date:next.date,sessions:structuredClone(next.sessions),calendar_ref:ref(calendar),reference_only:calendar.scope!=='SYNTHETIC'};
}
/** Only a bounded, checked official announcement plus checked session-rule text can construct this reference calendar. */
export async function officialAutumn2026Calendar(db,{announcement,sessionRule,exchange,object_version=1}) {
  requireThat(announcement.source_policy.source_class==='OFFICIAL'&&sessionRule.source_policy.source_class==='OFFICIAL','OFFICIAL_SOURCE_REQUIRED');
  const hosts=exchange==='SSE'?['www.sse.com.cn','one.sse.com.cn']:['www.szse.cn','investor.szse.cn'];
  requireThat(hosts.includes(new URL(announcement.source_policy.url).hostname)&&hosts.includes(new URL(sessionRule.source_policy.url).hostname),'OFFICIAL_SOURCE_HOST_MISMATCH');
  const a=(await readRaw(db,announcement)).toString('utf8').replace(/<[^>]*>/g,'').replace(/\s/g,''),s=(await readRaw(db,sessionRule)).toString('utf8').replace(/<[^>]*>/g,'').replace(/\s/g,'');
  requireThat(a.includes('9月25日')&&a.includes('9月27日')&&a.includes('9月28日')&&a.includes('10月1日')&&a.includes('10月7日')&&a.includes('10月8日'),'OFFICIAL_ANNOUNCEMENT_PARSE_FAILURE');
  requireThat(s.includes('9:15')&&s.includes('9:25')&&s.includes('9:30')&&s.includes('11:30')&&s.includes('13:00')&&s.includes('14:57')&&s.includes('15:00'),'OFFICIAL_SESSION_PARSE_FAILURE');
  requireThat(exchange==='SSE'?s.includes('每周一至周五'):s.includes('交易规则'),'OFFICIAL_WEEK_RULE_REQUIRED');
  const sessions=[{kind:'OPEN_AUCTION',open:'09:15:00',close:'09:25:00'},{kind:'CONTINUOUS_AM',open:'09:30:00',close:'11:30:00'},{kind:'CONTINUOUS_PM',open:'13:00:00',close:'14:57:00'},{kind:'CLOSE_AUCTION',open:'14:57:00',close:'15:00:00'}];
  const days=[];for(let ms=Date.parse('2026-09-20T00:00:00Z');ms<=Date.parse('2026-10-11T00:00:00Z');ms+=86400000){const dt=new Date(ms),date=dt.toISOString().slice(0,10),weekend=[0,6].includes(dt.getUTCDay()),holiday=(date>='2026-09-25'&&date<='2026-09-27')||(date>='2026-10-01'&&date<='2026-10-07');const status=weekend||holiday?'NON_TRADING':'TRADING';days.push({date,status,sessions:status==='TRADING'?sessions:[],reason:holiday?'OFFICIAL_HOLIDAY':weekend?'OFFICIAL_WEEK_RULE':'OFFICIAL_WEEK_RULE'});}
  return ingestCalendar(db,{observation:announcement,calendar_id:`calendar:${exchange}:autumn2026`,object_version,exchange,days,coverage_start:'2026-09-20',coverage_end:'2026-10-11',session_rule_version:`official-session:${sessionRule.content_hash}`,lineage:[sessionRule]});
}
