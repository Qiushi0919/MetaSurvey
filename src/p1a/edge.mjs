import Decimal from 'decimal.js';
import { requireThat } from '../contracts/validate.mjs';
const D=Decimal.clone({precision:100,rounding:Decimal.ROUND_HALF_UP});
export const PRODUCTION_EDGE_POLICY=Object.freeze({safety_multiple:'UNSET_REQUIRED',minimum_net_edge_cents:'UNSET_REQUIRED',minimum_edge_cost_ratio:'UNSET_REQUIRED',production_enabled:false});
const money=x=>{requireThat(typeof x==='string'&&/^(0|[1-9][0-9]{0,37})$/.test(x),'EDGE_INTEGER_MONEY_REQUIRED');return new D(x);};
export function incrementalEdge({mode,policy,incremental_expected_benefit_cents,cost}) {
  requireThat(['DEV','PAPER'].includes(mode),'PRODUCTION_DISABLED_P1A');
  requireThat(policy?.scope==='SYNTHETIC_EXPERIMENTAL'&&policy.production_enabled===false,'EDGE_POLICY_UNSET_REQUIRED');
  for(const k of ['safety_multiple','minimum_edge_cost_ratio'])requireThat(typeof policy[k]==='string'&&/^(0|[1-9][0-9]{0,9})(\.[0-9]{1,10})?$/.test(policy[k])&&new D(policy[k]).gte(1),'EDGE_POLICY_UNSET_REQUIRED');
  const benefit=money(incremental_expected_benefit_cents),minimum=money(policy.minimum_net_edge_cents);
  const actual=money(cost.commission_cents),proportional=money(cost.proportional_commission_cents),effect=money(cost.minimum_commission_effect_cents);
  requireThat(actual.eq(proportional.plus(effect)),'COST_ATTRIBUTION_DOUBLE_COUNT');
  const friction=['commission_cents','stamp_tax_cents','exchange_fee_cents','other_fee_cents','slippage_cents'].reduce((s,k)=>s.plus(money(cost[k])),new D(0));
  requireThat(friction.eq(money(cost.total_friction_cents)),'COST_ATTRIBUTION_DOUBLE_COUNT');
  const net=benefit.minus(friction),reasons=[];
  if(benefit.lt(friction.times(policy.safety_multiple)))reasons.push('REJECT_INSUFFICIENT_INCREMENTAL_EDGE');
  if(net.lt(minimum))reasons.push('REJECT_INSUFFICIENT_NET_EDGE');
  if(friction.gt(0)&&benefit.lt(friction.times(policy.minimum_edge_cost_ratio)))reasons.push('REJECT_INSUFFICIENT_EDGE_COST_RATIO');
  return {accepted:!reasons.length,reason_codes:reasons,incremental_expected_benefit_cents:benefit.toFixed(0),incremental_transaction_cost_cents:friction.toFixed(0),incremental_net_edge_cents:net.toFixed(0),edge_cost_ratio:friction.eq(0)?null:benefit.div(friction).toDecimalPlaces(10).toFixed(),scope:'SYNTHETIC_EXPERIMENTAL',production_enabled:false};
}
