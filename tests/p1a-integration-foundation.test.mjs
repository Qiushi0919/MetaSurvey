import test from 'node:test';
import assert from 'node:assert/strict';
import Decimal from 'decimal.js';
import { pathMetrics } from '../src/p1a/metrics.mjs';
import { incrementalEdge,PRODUCTION_EDGE_POLICY } from '../src/p1a/edge.mjs';
import { coreLifecycle,STRATEGY_NAMESPACES } from '../src/p1a/core-skeleton.mjs';
import { redact,appendAudit,verifyAudit } from '../src/p1a/audit.mjs';
import { PGlite } from '@electric-sql/pglite';
import { readFile } from 'node:fs/promises';
import { hashValue } from '../src/contracts/validate.mjs';
const dates=Array.from({length:41},(_,i)=>new Date(Date.UTC(2024,0,1+i)).toISOString().slice(0,10)); // Explicit SYNTHETIC sessions, including weekends on purpose.
const bars=dates.map((trade_date,i)=>({trade_date,low:i<3?'9':'10',high:i===6?'13':'11',close:i<3?'9':i===4?'11':'10'}));
test('daily MAE/MFE uses explicit sessions and reports approximation, missing windows, and no fabricated minute timing',()=>{
  const m=pathMetrics({entry_price:'10',entry_date:dates[0],entry_timing:'SESSION_OPEN',bars,calendar_dates:dates});
  assert.equal(m.MAE_5D,'-1000');assert.equal(m.MFE_10D,'3000');assert.equal(m.days_to_positive,5);assert.equal(m.days_to_MFE,7);assert.equal(m.max_underwater_days,3);assert.equal(m.mae_resolution,'DAILY_APPROXIMATION');assert.equal(m.mfe_resolution,'DAILY_APPROXIMATION');assert.equal(m.usage,'RETROSPECTIVE_OUTCOME_ONLY');
  const short=pathMetrics({entry_price:'10',entry_date:dates[0],entry_timing:'SESSION_OPEN',bars:bars.slice(0,4),calendar_dates:dates});assert.equal(short.MAE_5D,null);assert.equal(short.MFE_40D,null);assert.equal(short.sample_sessions,4);assert.equal(short.window_status['5D'],'INCOMPLETE');
  const intraday=pathMetrics({entry_price:'10',entry_date:dates[0],entry_timing:'INTRADAY_UNKNOWN',bars:[{...bars[0],low:'1',high:'99'},...bars.slice(1)],calendar_dates:dates});assert.equal(intraday.MFE_5D,'1000');assert.equal(intraday.MAE_5D,'-1000');
  const gap=pathMetrics({entry_price:'10',entry_date:dates[0],entry_timing:'SESSION_OPEN',bars:bars.filter(b=>b.trade_date!==dates[2]),calendar_dates:dates});assert.equal(gap.sample_sessions,2);assert.equal(gap.MAE_5D,null);
  assert.throws(()=>pathMetrics({entry_price:'10',entry_date:dates[0],entry_timing:'SESSION_OPEN',bars:[bars[0],bars[0]],calendar_dates:dates}),/DUPLICATE/);
});
const policy={scope:'SYNTHETIC_EXPERIMENTAL',production_enabled:false,safety_multiple:'2',minimum_net_edge_cents:'1',minimum_edge_cost_ratio:'2'};
const cost={commission_cents:'250',proportional_commission_cents:'10',minimum_commission_effect_cents:'240',stamp_tax_cents:'0',exchange_fee_cents:'2',other_fee_cents:'3',slippage_cents:'20',total_friction_cents:'275'};
test('new tranche pays its independent minimum; benefit must cover all costs and experimental safety multiple',()=>{
  assert.equal(PRODUCTION_EDGE_POLICY.safety_multiple,'UNSET_REQUIRED');
  const reject=incrementalEdge({mode:'PAPER',policy,incremental_expected_benefit_cents:'200',cost});assert.equal(reject.accepted,false);assert.deepEqual(reject.reason_codes,['REJECT_INSUFFICIENT_INCREMENTAL_EDGE','REJECT_INSUFFICIENT_NET_EDGE','REJECT_INSUFFICIENT_EDGE_COST_RATIO']);assert.equal(reject.incremental_transaction_cost_cents,'275');
  assert.equal(incrementalEdge({mode:'PAPER',policy,incremental_expected_benefit_cents:'550',cost}).accepted,true);
  assert.throws(()=>incrementalEdge({mode:'PROD',policy,incremental_expected_benefit_cents:'550',cost}),/PRODUCTION_DISABLED/);
  assert.throws(()=>incrementalEdge({mode:'PAPER',policy:PRODUCTION_EDGE_POLICY,incremental_expected_benefit_cents:'550',cost}),/UNSET_REQUIRED/);
  assert.throws(()=>incrementalEdge({mode:'PAPER',policy,incremental_expected_benefit_cents:'550',cost:{...cost,total_friction_cents:'515'}}),/DOUBLE_COUNT/);
  Decimal.set({precision:3,rounding:Decimal.ROUND_DOWN});assert.equal(incrementalEdge({mode:'PAPER',policy,incremental_expected_benefit_cents:'550',cost}).accepted,true);Decimal.set({precision:20,rounding:Decimal.ROUND_HALF_UP});
});
test('CORE target 20–40 is a review horizon; thesis invalidation permits day 1 exit, weak daily moves do not',()=>{
  for(const reason of ['THESIS_INVALIDATED','RISK_INVALIDATED','MATERIAL_EVENT','PRICE_STRUCTURE_INVALIDATED'])assert.equal(coreLifecycle({elapsed_sessions:1,reason}).state,'EXIT_ELIGIBLE');
  for(const reason of ['FLAT_TODAY','NEXT_DAY_MINUS_ONE_PERCENT','SHORT_TERM_FLOW_WEAK',null])assert.equal(coreLifecycle({elapsed_sessions:40,reason}).state,'OPEN');
  assert.equal(coreLifecycle({elapsed_sessions:20}).mandatory_minimum,false);assert.equal(STRATEGY_NAMESPACES.EVENT_3.strategy_enabled,false);assert.equal(STRATEGY_NAMESPACES.RESEARCH_6_18M.order_enabled,false);
});
test('persisted audit chain links source/hash/time/security/version/trace and redacts nested sensitive fields',async()=>{
  const db=new PGlite();try{for(const n of ['001_schema_v1.sql','002_contract_registry.sql','004_p1a_paper.sql','005_p1a_replay_audit.sql'])await db.exec(await readFile(new URL('../migrations/'+n,import.meta.url),'utf8'));
    const ref={object_id:'fixture',object_version:1,content_hash:hashValue('fixture')};
    for(const [i,event_type] of ['MARKET_DATA','SNAPSHOT','FEATURE','COST','REPLAY'].entries())await appendAudit(db,{chain_id:'synthetic-audit',event_type,event_time:'2024-01-01T10:00:00Z',source_id:'SYNTHETIC_FIXTURE',source_hash:hashValue('source'),security_id:'synthetic-security',version:'fixture-v1',trace_id:'diagnostic-only',object_ref:ref,parent_refs:i?[ref]:[],payload:{broker_token:'test-token',nested:{account_number:'test-account',api_secret:'test-secret'},safe:'okay'}});
    const chain=await verifyAudit(db,'synthetic-audit');assert.equal(chain.events.length,5);assert.deepEqual(chain.events.map(e=>e.event_type),['MARKET_DATA','SNAPSHOT','FEATURE','COST','REPLAY']);assert.equal(chain.events[0].payload.nested.account_number,'[REDACTED]');assert.equal(chain.events[0].payload.broker_token,'[REDACTED]');assert(!JSON.stringify(chain).includes('test-secret'));
    const args={chain_id:'synthetic-audit',event_type:'ATTACK',event_time:'2024-01-01T10:00:00Z',source_id:'SYNTHETIC',source_hash:hashValue('source'),security_id:'fixture',version:'v1',trace_id:'trace',object_ref:ref};
    for(const attack of [{object_ref:{...ref,broker_token:'synthetic-secret'}},{parent_refs:[{...ref,account_number:'synthetic-number'}]},{object_ref:{...ref,content_hash:'x'}}])await assert.rejects(appendAudit(db,{...args,...attack}),/AUDIT_REF_INVALID/);
    const safe=await appendAudit(db,{...args,payload:{message:'Authorization: Bearer synthetic_secret',nested:[{description:'broker password=synthetic_secret'}]}});assert.equal(safe.payload.message,'[REDACTED]');assert.equal(safe.payload.nested[0].description,'[REDACTED]');
    await assert.rejects(db.exec("UPDATE p1a_replay.audit SET event_type='fake'"),/APPEND_ONLY/);
    await assert.rejects(db.exec('DELETE FROM p1a_replay.audit'),/APPEND_ONLY/);
    for(const table of ['p1a_paper.fills','p1a_paper.ledger','p1a_paper.requests','p1a_replay.audit','p1a_replay.results'])await assert.rejects(db.exec(`TRUNCATE ${table} CASCADE`),/APPEND_ONLY/);
  }finally{await db.close();}
  assert.equal(redact({a:[{password:'p'}]}).a[0].password,'[REDACTED]');
});
