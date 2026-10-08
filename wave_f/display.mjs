// Closed metadata display only. No native issuer or activation mechanism.
import {canonical,contentHash} from '../src/contracts/validate.mjs';
const fields=['version','namespace','body','productionGate','live_authority','actual_forward_days','historical_visibility_proven','artifact_name','context_hash','code_hash','strategy_spec_hash','source_admission','provider_license_transport_verified','formal_backtest_authorized','snapshot_b_authorized','forward_paper_authorized','symbols','content_hash'].sort();
const names=['Historical-PIT-Three-Symbol-Matrix.json','Price-Backtest-Minimum-PIT-Gate.json','Backtest-Engine-Readiness.json','Snapshot-B-Activation-Readiness.json','Forward-Paper-Activation-Readiness.json'];
const hashes=['content_hash','context_hash','code_hash','strategy_spec_hash'];
export function validateDisplay(v){
  canonical(v);
  if(Object.keys(v).sort().join('|')!==fields.join('|')||v.version!=='1.0.0'||v.namespace!=='LOCAL_ONLY_NON_TRADEABLE:CORE_40'||!names.includes(v.artifact_name)||v.source_admission!=='BLOCKED'||v.actual_forward_days!==0||JSON.stringify(v.symbols)!==JSON.stringify(['603993.SH','600312.SH','603228.SH'])||!v.body||Object.getPrototypeOf(v.body)!==Object.prototype)throw Error('WF_METADATA_INVALID');
  for(const k of ['productionGate','live_authority','historical_visibility_proven','provider_license_transport_verified','formal_backtest_authorized','snapshot_b_authorized','forward_paper_authorized'])if(v[k]!==false)throw Error('WF_AUTHORITY_FORBIDDEN');
  if(hashes.some(k=>typeof v[k]!=='string'||!/^sha256:[a-f0-9]{64}$/.test(v[k]))||v.content_hash!==contentHash(v))throw Error('WF_METADATA_HASH');
  return v;
}
export function transitionDisplay(v,target){validateDisplay(v);if(target!=='LOCAL_PREPARATION_DISPLAY')throw Error('WF_NATIVE_AUTHORITY_FORBIDDEN');return v;}
export function issueActual(){throw Error('WF_ACTUAL_ISSUANCE_FORBIDDEN');}
