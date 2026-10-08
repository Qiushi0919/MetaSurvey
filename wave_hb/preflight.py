"""Read-only preparation against frozen H-A; no credential, network or actual IO."""
import json
from pathlib import Path
from copy import deepcopy
from .common import ROOT,metadata,checked_file,hash_value,require,SYMBOLS,ref
from wave_h import collector
from wave_h.common import bindings,policy

STEPS=('OBSERVED_ACTUAL_OPEN_EOD_ORIGINALS','EXTERNAL_CAPTURE_GRANT','FIXED_KEYCHAIN_RAM_ONLY',
       'MAX_13_EXACT_THREE_READ_ONLY_REQUESTS','RAW_CLOCK_DURABLE_BEFORE_PARSE',
       'INDEPENDENT_ORIGINAL_REOPEN','EXTERNAL_REVIEW_GRANT','ISSUE_CURRENT_SNAPSHOT_B',
       'EXCLUSIVE_EMPTY_STORE_OR_EXISTING_VERIFIED_HEAD','SEPARATE_HUMAN_FORWARD_GRANT',
       'ATOMIC_EXACTLY_ONE_NO_DECISION_APPEND','REOPEN_VERIFY_PREVIOUS_PLUS_ONE','STOP')
STOP_REASONS=('MISSING_ACTUAL_OPEN_EOD','AUTHORITY_NOT_ENROLLED','MISSING_EXTERNAL_SIGNATURE',
 'MISSING_STALE_WRONG_SYMBOL_SESSION','SOURCE_SCHEMA_POLICY_BINDING_MISMATCH','RAW_CLOCK_PRECISION_MISMATCH',
 'UNSAFE_RESPONSE_OR_SECRET_ECHO','REVIEW_ORIGINAL_MISMATCH','DUPLICATE_OR_STALE_HEAD',
 'CROSS_NAMESPACE_PROMOTION','CAPTURE_TIMEOUT','REVIEW_TIMEOUT','APPEND_TIMEOUT','WHOLE_RUN_TIMEOUT')

def request_manifest(planned_session='2026-10-08'):
    # Pure definitions, not build_plan: no actual witness is invented or issued.
    jobs=collector._definitions(planned_session)
    require(len(jobs)==13 and len({j['job_id'] for j in jobs})==13,'HB_REQUEST_COUNT')
    return deepcopy(jobs)

def verify_manifest(jobs,session):
    require(type(jobs) is list and jobs==request_manifest(session),'HB_REQUEST_MANIFEST_DRIFT')
    return True

def build_preflight():
    p=policy();a=json.loads(checked_file(ROOT/'config/wave-h/snapshot-a-reference.json'))
    contracts=json.loads(checked_file(ROOT/'docs/wave-h/Contracts-v1.json'))
    return metadata('H_B_OFFLINE_PREFLIGHT',{
      'state':'PASS_OFFLINE_HOLD_ACTUAL','network_used':False,'credential_read':False,
      'planned_session':'2026-10-08','planned_session_is_actual_evidence':False,
      'request_manifest':request_manifest(),'exact_symbols':list(SYMBOLS),'max_requests':13,
      'endpoint':collector.ENDPOINT,'source_identity':collector.SOURCE_IDENTITY,
      'source_schema_version':collector.SCHEMA_VERSION,'H_A_bindings':bindings(),
      'source_exception':p,'reference_a':a,'witness_contract':contracts['contracts']['ActualSessionWitness'],
      'clock_precisions':['DATE_ONLY','SECOND','MILLISECOND','MICROSECOND','NANOSECOND','UNKNOWN'],
      'clock_rule':'literal observed precision; DATE_ONLY is event date only, no invented midnight or historical first-visible',
      'raw_first_rule':'clean JSON raw and literal clock durable before native semantic parse; secret echo/invalid JSON rejected before hash/archive',
      'quarantine_rule':'clean malformed original retained, fixed sanitized failure, no Snapshot/count; consumed request claims never auto-retried',
      'sequence':list(STEPS),'timeouts_seconds':{'capture':900,'independent_review':1800,'append':300,'whole_one_shot':3600},
      'timeout_requires_operator_enforcement':'phase wrapper must stop before next phase and never resume consumed capture; H-A transport still frozen',
      'no_retry':True,'no_redirect':True,'no_proxy':True,'no_fallback':True,'stop_conditions':list(STOP_REASONS),
      'actual_enrollment':'NOT_INSTALLED_BY_PREFLIGHT','human_grants':'CAPTURE_REVIEW_FORWARD_SEPARATE_EXTERNAL_SIGNATURES_REQUIRED',
      'actual_count_rule':'accepted fresh actual session + exact-three + reviewed B + separate Forward + atomic append only',
      'same_day_recovery':'read-only re-open/verify; no auto-repair or backdated day',
      'formal_PIT':'BLOCKED','provider_license_transport':'8_UNKNOWN_BLOCKED','account_parameters':'30_UNSET_REQUIRED',
      'inputs':[ref(ROOT/'docs/wave-h/One-Shot-Activation-Runbook.md'),ref(ROOT/'config/wave-h/source-exception.v1.json')],
      'STOP':True,'no_scheduler':True})

def promote(*args,**kwargs):raise ValueError('HB_PREFLIGHT_NO_ACTUAL_AUTHORITY')
