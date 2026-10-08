// Closed display shape. A caller-valid hash remains only display metadata.
import {canonical,contentHash} from '../src/contracts/validate.mjs';
const fields=['version','kind','namespace','body','trust','historical_visibility_proven','source_admission','actual_forward_days','productionGate','live_authority','native_signal_order_broker','artifact_name','context_hash','code_hash','strategy_spec_hash','protocol_hash','symbols','provider_license_transport_verified','formal_backtest_authorized','snapshot_b_authorized','forward_paper_authorized','content_hash'].sort();
const kinds={
 'Provider-License-Transport-Evidence-Pack.json':'PROVIDER_LICENSE_TRANSPORT_EVIDENCE_PACK',
 'Historical-PIT-Three-Symbol-Matrix.json':'HISTORICAL_PIT_EVIDENCE_MATRIX',
 'Historical-PIT-Closure-Progress.json':'HISTORICAL_PIT_PROGRESS',
 'Retrospective-Diagnostic-Summary.json':'Retrospective-Diagnostic-Summary',
 'Snapshot-B-Activation-Readiness.json':'WAVE_G_SNAPSHOT_B_ACTIVATION_READINESS',
 'Forward-Paper-Activation-Readiness.json':'WAVE_G_FORWARD_PAPER_ACTIVATION_READINESS',
 'Small-Live-Pilot-Policy-Summary.json':'SMALL_LIVE_POLICY_DRAFT'};
export function validateDisplay(v){
 canonical(v);
 if(Object.keys(v).sort().join('|')!==fields.join('|')||v.version!=='1.0.0'||v.namespace!=='RETROSPECTIVE_DIAGNOSTIC_ONLY:CORE_40'||v.kind!==kinds[v.artifact_name]||!kinds[v.artifact_name]||v.trust!=='LOCAL_ONLY_NON_TRADEABLE'||v.source_admission!=='BLOCKED'||v.actual_forward_days!==0||JSON.stringify(v.symbols)!==JSON.stringify(['603993.SH','600312.SH','603228.SH'])||!v.body||Object.getPrototypeOf(v.body)!==Object.prototype)throw Error('WG_METADATA_INVALID');
 for(const k of ['historical_visibility_proven','productionGate','live_authority','native_signal_order_broker','provider_license_transport_verified','formal_backtest_authorized','snapshot_b_authorized','forward_paper_authorized'])if(v[k]!==false)throw Error('WG_AUTHORITY_FORBIDDEN');
 for(const k of ['content_hash','context_hash','code_hash','strategy_spec_hash','protocol_hash'])if(typeof v[k]!=='string'||!/^sha256:[a-f0-9]{64}$/.test(v[k]))throw Error('WG_METADATA_HASH');
 if(v.content_hash!==contentHash(v))throw Error('WG_METADATA_HASH');return v;
}
export function transitionDisplay(v,target){validateDisplay(v);if(target!=='LOCAL_DIAGNOSTIC_DISPLAY')throw Error('WG_NATIVE_AUTHORITY_FORBIDDEN');return v;}
export function issueActual(){throw Error('WG_ACTUAL_ISSUANCE_FORBIDDEN');}
