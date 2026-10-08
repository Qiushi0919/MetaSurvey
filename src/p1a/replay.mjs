import Decimal from 'decimal.js';
import { hashValue,sealContract,reference,requireThat,validateContract,contentHash,canonical } from '../contracts/validate.mjs';
import { sealCostProfile,estimateCost,grossNotionalCents } from '../cost/index.mjs';
import {createPaperService,sealReferenceObject,orderTermsHash} from '../paper/index.mjs';
import { verifyDataSnapshot,readObject } from '../data/index.mjs';
import { incrementalEdge } from './edge.mjs';
import { pathMetrics } from './metrics.mjs';
import {validateP1AContract} from './contracts.mjs';
import {verifyCodeProvenance} from './code-provenance.mjs';
import {coreLifecycle} from './core-skeleton.mjs';
import { appendAudit,verifyAudit } from './audit.mjs';
const D=Decimal.clone({precision:100,rounding:Decimal.ROUND_HALF_UP});
export function fixtureCostProfile(fixture,name,version=1){const rates=fixture.stress_profiles[name];requireThat(rates,'STRESS_PROFILE_REQUIRED');return sealCostProfile({contract_name:'CostProfile',contract_version:'1.0.0',object_id:`SYNTHETIC_REPLAY_${name}`,object_version:version,profile_scope:'SYNTHETIC_TEST_ONLY',production_enabled:false,currency:'CNY',money_unit:'INTEGER_CENTS_STRING',rounding_mode:'HALF_UP',commission_scope:'PER_ORDER',commission_rate:rates.commission_rate,minimum_commission_cents:rates.minimum_commission_cents,stamp_tax_sell_rate:rates.stamp_tax_sell_rate,exchange_fee:{rate:rates.exchange_rate,included_in:'EXCLUDED'},other_fee:{rate:rates.other_rate,included_in:'EXCLUDED'},slippage:{treatment:'SEPARATE_ESTIMATE',rate:rates.slippage_rate},effective_from:'2025-01-01',effective_to:'2025-12-31',source:{kind:'SYNTHETIC_FIXTURE',description:fixture.provenance}});}
const feeKeys=['commission_cents','proportional_commission_cents','minimum_commission_effect_cents','stamp_tax_cents','exchange_fee_cents','other_fee_cents','slippage_cents','total_friction_cents'];
export function sumCost(costs){return Object.fromEntries(feeKeys.map(k=>[k,costs.reduce((n,c)=>n+BigInt(c[k]),0n).toString()]));}
export function replayManifest({fixture,snapshot,feature,account_profile,cost_profile,rule_version,calendar,security,code_version,source_tree_hash,signals_hash,edge_enabled,edge_policy_hash}){
  validateContract('FeatureSet',feature);validateContract('AccountProfile',account_profile);
  requireThat(/^([a-f0-9]{40})$/.test(code_version)&&/^sha256:[a-f0-9]{64}$/.test(source_tree_hash),'ACTUAL_CODE_VERSION_REQUIRED');
  requireThat(feature.snapshot_ref.content_hash===snapshot.manifest.content_hash&&feature.decision_cutoff===snapshot.manifest.decision_cutoff,'FEATURE_SNAPSHOT_BINDING_MISMATCH');
  const body={contract_name:'ReplayInputManifest',contract_version:'1.0.0',fixture_scope:'SYNTHETIC_EXPERIMENTAL',mode:'PAPER',production_enabled:false,execution_fixture_hash:hashValue(fixture),snapshot_ref:reference(snapshot.manifest),data_hash:snapshot.manifest.data_hash,feature_ref:reference(feature),feature_version:feature.feature_version,account_profile_ref:reference(account_profile),cost_profile_ref:reference(cost_profile),rule_version,calendar_hash:calendar.content_hash,calendar_version:calendar.version,security_hash:security.content_hash,security_version:security.version,code_version,source_tree_hash,signals_hash,edge_enabled,edge_policy_hash};return {...body,content_hash:hashValue(body)};
}
export function assertReplayBinding(manifest,{fixture,snapshot,feature,account_profile,cost_profile,calendar,security,rule_version,code_version,source_tree_hash,signals_hash,edge_enabled,edge_policy_hash}){
  const expected=replayManifest({fixture,snapshot,feature,account_profile,cost_profile,calendar,security,rule_version,code_version,source_tree_hash,signals_hash,edge_enabled,edge_policy_hash});
  requireThat(manifest.content_hash===contentHash(manifest)&&manifest.content_hash===expected.content_hash,'REPLAY_INPUT_INVALIDATED');return true;
}
export function assertApprovalBinding(approval,manifest){requireThat(approval?.scope==='SYNTHETIC_TEST_ONLY'&&approval.actor_type==='HUMAN_USER'&&approval.input_hash===manifest.content_hash&&approval.snapshot_hash===manifest.snapshot_ref.content_hash,'APPROVAL_INPUT_INVALIDATED');return true;}
export async function runReplay({db,fixture,snapshot,feature,account_profile,cost_profile,calendar,security,code_version,source_tree_hash,rule_version=fixture.rule_version,edge_enabled=false,trace_id='diagnostic-replay',wall_clock=new Date().toISOString()}){
  requireThat(fixture.fixture_scope==='SYNTHETIC_EXPERIMENTAL'&&account_profile.profile_kind==='SYNTHETIC_FIXTURE'&&account_profile.mode==='PAPER','REPLAY_SYNTHETIC_ONLY');
  await verifyCodeProvenance({code_version,source_tree_hash});
  await verifyDataSnapshot(db,snapshot);
  requireThat(snapshot.status==='FROZEN'&&snapshot.manifest.scope==='SYNTHETIC'&&snapshot.lineage_bundle.tradeability==='OFFLINE_ELIGIBLE','REPLAY_SOURCE_ADMISSION_REQUIRED');
  const market=await readObject(db,snapshot.lineage_bundle.root_refs[0]);requireThat(market.kind==='BAR_1D','REPLAY_BAR_ROOT_REQUIRED');
  const registry=await readObject(db,market.payload.security_ref),sourceCalendar=await readObject(db,market.payload.calendar_ref);
  requireThat(canonical(security.source_ref)===canonical(reference(registry))&&security.canonical_symbol===registry.canonical_symbol&&security.security_id===registry.security_id&&security.lot_size===registry.payload.lot_size&&security.available_at===registry.available_at&&security.version===`${registry.object_id}@${registry.object_version}`&&security.original_symbol===registry.original_symbol,'REPLAY_SECURITY_PROJECTION_MISMATCH');
  requireThat(canonical(calendar.source_ref)===canonical(reference(sourceCalendar))&&calendar.available_at===sourceCalendar.available_at&&calendar.version===`${sourceCalendar.object_id}@${sourceCalendar.object_version}`&&calendar.source.kind==='SYNTHETIC_FIXTURE'&&calendar.source.source_hash===sourceCalendar.content_hash,'REPLAY_CALENDAR_PROJECTION_MISMATCH');
  const expectedSessions=sourceCalendar.payload.days.filter(d=>d.date>=fixture.sessions[0]&&d.status==='TRADING').map(d=>d.date);requireThat(canonical(calendar.sessions)===canonical(expectedSessions),'REPLAY_CALENDAR_PROJECTION_MISMATCH');
  requireThat(feature.symbol===market.canonical_symbol&&feature.strategy_id==='CORE_40'&&feature.recorded_at===fixture.decision_cutoff&&feature.provenance.available_at===fixture.decision_cutoff&&feature.provenance.retrieved_at===fixture.decision_cutoff&&feature.feature_version===snapshot.lineage_bundle.feature_version&&feature.provenance.source_hash===market.content_hash&&canonical(feature.features)===canonical({last_close:{value:market.payload.close,unit:'CNY_PER_SHARE',quality:'VALID'}})&&feature.data_quality==='PASS','REPLAY_FEATURE_DERIVATION_MISMATCH');
  for(const [name,value] of [['CostProfile',cost_profile],['PaperCalendarProjection',calendar],['PaperSecurityProjection',security]])validateP1AContract(name,value);

  requireThat(fixture.opening_cash_cents===account_profile.settings.capital_cents&&account_profile.provenance.source_hash===hashValue(fixture),'REPLAY_ACCOUNT_FIXTURE_MISMATCH');
  requireThat(canonical(fixture.sessions)===canonical(calendar.sessions)&&fixture.decision_cutoff===feature.decision_cutoff&&fixture.feature_version===feature.feature_version,'REPLAY_CALENDAR_FEATURE_FIXTURE_MISMATCH');
  requireThat(fixture.daily_marks.length===2&&fixture.daily_marks.every((m,i)=>m.trade_date===fixture.sessions[i]),'REPLAY_MARK_PATH_REQUIRED');
  const bindings={fixture,snapshot,feature,account_profile,cost_profile,calendar,security,rule_version,code_version,source_tree_hash,signals_hash:hashValue(fixture.signals),edge_enabled,edge_policy_hash:hashValue(fixture.edge_policy)};
  const input=replayManifest(bindings);assertReplayBinding(input,bindings);
  const account_id=account_profile.account_id,service=createPaperService({db}),mode='PAPER';
  const time=(day,second)=>`${day}T02:00:${String(second).padStart(2,'0')}Z`;
  await service.openAccount({mode,account_id,opening_cash_cents:fixture.opening_cash_cents,event_time:time(fixture.sessions[0],0),trace_id,fixture_scope:'SYNTHETIC_TEST_ONLY',source_ref:reference(account_profile)});
  const accepted=[],rejections=[],roundEstimates=[];
  for(const signal of fixture.signals){const trade_date=fixture.sessions[0];const costs=sumCost([estimateCost({mode,profile:cost_profile,side:'BUY',price:signal.entry_price,quantity:signal.quantity,trade_date}),estimateCost({mode,profile:cost_profile,side:'SELL',price:signal.exit_price,quantity:signal.quantity,trade_date:fixture.sessions[1]})]);roundEstimates.push(costs);const edge=incrementalEdge({mode,policy:fixture.edge_policy,incremental_expected_benefit_cents:signal.incremental_expected_benefit_cents,cost:costs});if(edge_enabled&&!edge.accepted)rejections.push({signal_id:signal.id,...edge});else accepted.push(signal);}
  const order_sequence=[],fill_sequence=[],daily_nav=[];let gross=0n;const actualCosts=[];
  for(const [dayIndex,side] of ['BUY','SELL'].entries()){
    const trade_date=fixture.sessions[dayIndex];let second=0;
    for(const signal of accepted){const p=side==='BUY'?signal.entry_price:signal.exit_price;const at=time(trade_date,second);const order_id=`${signal.id}-${side}`;
      if(side==='SELL')requireThat(coreLifecycle({elapsed_sessions:1,reason:signal.exit_reason}).state==='EXIT_ELIGIBLE','CORE_EXIT_INVALID');
      const intent={contract_name:'PaperReplayOrderIntent',contract_version:'1.0.0',fixture_scope:'SYNTHETIC_TEST_ONLY',mode,account_id,order_id,client_order_id:`client-${order_id}`,strategy:'CORE_40',symbol:security.canonical_symbol,side,quantity:signal.quantity,limit_price:p,trade_date,rule_version,snapshot_hash:snapshot.manifest.content_hash,feature_hash:feature.content_hash,cost_version:cost_profile.object_version,cost_profile_hash:cost_profile.content_hash,calendar_hash:calendar.content_hash,security_hash:security.content_hash,market_data_at:at,valid_until:`${trade_date}T07:00:00Z`};
      const decision=hashValue({kind:'SYNTHETIC_DECISION_APPROVAL',order_id,input_hash:input.content_hash}),confirmation=hashValue({kind:'SYNTHETIC_FINAL_CONFIRMATION',terms:orderTermsHash(intent)});
      const common={mode,account_id,order_id,strategy:'CORE_40',symbol:security.canonical_symbol,trace_id};
      await service.reserveOrder({...common,idempotency_key:`reserve-${order_id}`,event_time:at,intent,cost_profile,security,calendar,authorization:{kind:'FIXTURE_HUMAN_CONFIRMATION',scope:'SYNTHETIC_TEST_ONLY',actor_type:'HUMAN_USER',order_terms_hash:orderTermsHash(intent),decision_approval_hash:decision,final_confirmation_hash:confirmation},authority:{scope:'SYNTHETIC_TEST_ONLY',actor_type:'HUMAN_USER',verified_approval_hashes:new Set([decision,confirmation])}});
      await service.submitOrder({...common,idempotency_key:`submit-${order_id}`,event_time:time(trade_date,second+1)});
      for(const [j,quantity] of [100,signal.quantity-100].entries()){requireThat(quantity>0,'REPLAY_PARTIAL_QUANTITY_INVALID');const fill_id=`fill-${order_id}-${j+1}`,event_time=time(trade_date,second+2+j);const filled=await service.fillOrder({...common,idempotency_key:fill_id,fill_id,quantity,price:p,event_time,market_data_at:event_time});fill_sequence.push(filled);}
      const order=await service.getOrder({mode,account_id,order_id});actualCosts.push(order.cumulative_json);order_sequence.push(intent);second+=5;
      const g=BigInt(order.cumulative_json.notional_cents);gross+=side==='SELL'?g:-g;
    }
    const account=await service.getAccount({mode,account_id});const positionValue=account.lots.reduce((n,lot)=>n+(BigInt(lot.remaining_quantity)>0n?BigInt(grossNotionalCents(fixture.daily_marks[dayIndex].price,Number(lot.remaining_quantity))):0n),0n);
    daily_nav.push({trade_date,settled_cash_cents:account.settled_cash_cents,reserved_cash_cents:account.reserved_cash_cents,position_value_cents:positionValue.toString(),nav_cents:(BigInt(account.settled_cash_cents)+positionValue).toString()});
  }
  const ledger=await service.getLedger({mode,account_id}),ledger_entries=ledger.map(({trace_id,...economic})=>economic),reconciliation=await service.reconcile({mode,account_id});
  const cost=sumCost(actualCosts),net=gross-BigInt(cost.total_friction_cents),roundTrips=accepted.length,trades=actualCosts.length;
  const attribution={gross_pnl_cents:gross.toString(),...cost,net_pnl_cents:net.toString(),minimum_commission_effect_is_subset:true,friction_to_gross_profit_ratio:gross>0n?new D(cost.total_friction_cents).div(gross.toString()).toDecimalPlaces(10).toFixed():null,friction_per_trade_cents:trades?new D(cost.total_friction_cents).div(trades).toDecimalPlaces(10).toFixed():null,friction_per_round_trip_cents:roundTrips?new D(cost.total_friction_cents).div(roundTrips).toDecimalPlaces(10).toFixed():null,friction_per_strategy:{CORE_40:cost.total_friction_cents,EVENT_3:'0'}};
  const path=fixture.path_bars;
  const metrics=accepted.map(signal=>({signal_id:signal.id,...pathMetrics({entry_price:signal.entry_price,entry_date:fixture.sessions[0],entry_timing:'SESSION_OPEN',bars:path,calendar_dates:fixture.sessions})}));
  const economic={contract_name:'DeterministicReplayResult',contract_version:'1.0.0',input,signals:fixture.signals,edge_enabled,rejections,order_sequence,fill_sequence,ledger_entries,daily_nav,cost_breakdown:attribution,path_metrics:metrics,trade_count:trades,round_trip_count:roundTrips,ledger_chain_hash:reconciliation.ledger_chain_hash};
  const economic_result_hash=hashValue(economic),result={...economic,economic_result_hash,diagnostics:{trace_id,wall_clock},production_enabled:false};validateP1AContract('DeterministicReplayResult',result);
  await db.query('INSERT INTO p1a_replay.results(economic_result_hash,input_hash,mode,fixture_scope,code_version,result_json,metrics_json,mae_resolution,mfe_resolution) VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8,$8)',[economic_result_hash,input.content_hash,mode,'SYNTHETIC_EXPERIMENTAL',code_version,canonical(result),canonical(metrics),'DAILY_APPROXIMATION']);
  const auditChain=`replay:${economic_result_hash}`;const events=[['SNAPSHOT',reference(snapshot.manifest),snapshot.manifest.provenance.source_hash],['FEATURE',reference(feature),feature.provenance.source_hash],['COST',{object_id:`cost:${hashValue(cost).slice(7)}`,object_version:cost_profile.object_version,content_hash:hashValue(cost)},cost_profile.content_hash],['REPLAY',{object_id:economic_result_hash,object_version:1,content_hash:economic_result_hash},economic_result_hash]];
  requireThat(market?.kind==='BAR_1D','AUDIT_MARKET_DATA_MISSING');events.unshift(['MARKET_DATA',reference(market),market.source_hash]);let parents=[];
  for(const [event_type,object_ref,source_hash] of events){await appendAudit(db,{chain_id:auditChain,event_type,event_time:wall_clock,source_id:event_type==='MARKET_DATA'?market.source_id:'SYNTHETIC_P1A_REPLAY',source_hash,security_id:security.security_id,version:event_type==='COST'?String(cost_profile.object_version):code_version,trace_id,object_ref,parent_refs:parents,payload:{input_hash:input.content_hash,production_enabled:false,mode:'PAPER',...(event_type==='COST'?{cost_profile_ref:reference(cost_profile),cost_breakdown:cost}:{} )}});parents=[object_ref];}
  const audit=await verifyAudit(db,auditChain);return {result,reconciliation,audit};
}
