import { requireThat } from '../contracts/validate.mjs';
export const STRATEGY_NAMESPACES=Object.freeze({CORE_40:{lifecycle_only:true,target_horizon:{minimum:20,maximum:40}},EVENT_3:{placeholder_only:true,strategy_enabled:false},RESEARCH_6_18M:{order_enabled:false}});
const early=new Set(['THESIS_INVALIDATED','RISK_INVALIDATED','MATERIAL_EVENT','PRICE_STRUCTURE_INVALIDATED']);
const weak=new Set(['FLAT_TODAY','NEXT_DAY_MINUS_ONE_PERCENT','SHORT_TERM_FLOW_WEAK']);
export function coreLifecycle({state='OPEN',elapsed_sessions,reason=null}) {
  requireThat(state==='OPEN'&&Number.isSafeInteger(elapsed_sessions)&&elapsed_sessions>=0,'CORE_LIFECYCLE_INPUT_INVALID');
  requireThat(reason===null||early.has(reason)||weak.has(reason)||reason==='TARGET_HORIZON_REVIEW','CORE_EXIT_REASON_INVALID');
  return {strategy_id:'CORE_40',state:early.has(reason)?'EXIT_ELIGIBLE':'OPEN',elapsed_sessions,target_horizon:{minimum:20,maximum:40},mandatory_minimum:false,review_due:elapsed_sessions>=20,reason_codes:early.has(reason)?[reason]:[],production_enabled:false};
}
