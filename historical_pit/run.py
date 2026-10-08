"""Exclusive local audit epoch. No network, credential, signer or engine call."""
import argparse
import json
from pathlib import Path
from collections import Counter
from .core import *
from .core import _json


def build(output,calendar_manifest,cutoff_policy=UNSET):
    out=Path(output);out.mkdir(mode=0o700)  # Never overwrite a prior run, incl failed epochs.
    spec,spec_ref=frozen_spec()
    records,dates,coverage,originals=read_current_originals()
    calendar=calendar_structure(ref(calendar_manifest))
    calendar_ref=write_new(out/'Dated-Calendar-Structure.json',calendar)
    inventory_ref=write_new(out/'Current-Originals-Audit-Inventory.json',{
        'version':'1.0.0','kind':'HistoricalOriginalsAuditInventory','namespace':NAMESPACE,
        'scope':'AUDIT_ONLY_NEVER_DECISION_PAYLOAD','records':records,'originals':originals,
        'current_API_row_counts':dict(Counter(r['actual_API'] for r in records)),
        'historical_visibility_proven':False,'formal_admission':'BLOCKED','productionGate':False})
    views=[]
    for symbol in SYMBOLS:
        for day in dates[symbol]:
            cutoff=cutoff_for(day,cutoff_policy)
            views.append(candidate_snapshot(symbol,day,cutoff,records))
    # Inventory/source hashes stay OUTSIDE each model-facing per-cutoff payload.
    payload={'version':'1.0.0','kind':'DailyPITCandidateSnapshots','namespace':NAMESPACE,
        'cutoff_policy':cutoff_policy,'snapshots':views,'formal_admission':'BLOCKED',
        'decision':'NO_DECISION','historical_visibility_proven':False,'productionGate':False}
    snapshot_ref=write_new(out/'Daily-PIT-Candidate-Snapshots.json',payload)
    matrix=closure_matrix(calendar_ref,cutoff_policy)
    matrix_ref=write_new(out/'PIT-Closure-Matrix-60.json',matrix)
    attempt=backtest_attempt(coverage,matrix_ref)
    attempt_ref=write_new(out/'Backtest-Prerequisite-Attempt-BLOCKED.json',attempt)
    # Empty data are clearly pending, never reported as a zero-return backtest.
    ledger=out/'Trade-Ledger-PENDING.jsonl';ledger.touch(mode=0o600);ledger.chmod(0o400)
    status={'version':'1.0.0','kind':'HistoricalPITOwnerStatus','recorded_at':now(),
        'engineering':'PIT_ORIGINAL_READER_AND_DAILY_AUDIT_READY_NOT_FORMAL_ADMISSION',
        'owner_P0_PIT':'IMPLEMENTED_FOR_CURRENT_AUDIT_SCOPE_CLOSURE_BLOCKED',
        'owner_P0_BT':'CONDITIONALLY_AUTHORIZED_NOT_EXECUTED',
        'owner_P0_AUDIT':'MANIFEST_AND_BLOCKED_ATTEMPT_RETAINED_REAL_TRADE_METRICS_UNAVAILABLE',
        'coverage':coverage,'source_audit_rows':len(records),'per_day_candidate_snapshots':len(views),
        'admitted_snapshots':0,'complete_history_target_sessions':1260,
        'minimum_additional_observed_sessions_per_symbol':1260-327,
        'cutoff_policy':cutoff_policy,'closure_rows':60,'closed_continuous_domains':0,
        'new_dated_calendar_documents':6,'actual_session_exception_history':'UNKNOWN',
        'strategy_spec_ref':spec_ref,'original_inventory_ref':inventory_ref,'calendar_ref':calendar_ref,
        'snapshots_ref':snapshot_ref,'closure_matrix_ref':matrix_ref,'backtest_attempt_ref':attempt_ref,
        'ledger_ref':ref(ledger),'ledger_state':'EMPTY_PENDING_NO_ACTUAL_TRADES_NOT_ZERO_PROFIT',
        'real_complete_trades':0,'formal_backtest':'BLOCKED','formal_OOS':'BLOCKED','untouched_oos':False,
        'source_provider_license_transport':'BLOCKED','actual_account_cost_risk':'UNSET_REQUIRED',
        'historical_visibility_proven':False,'productionGate':False,
        'this_run_market_requests':0,'this_run_credential_lookups':0,'this_run_engine_calls':0,
        'native_orders':0,'broker_calls':0,'actual_forward_days_increment':0,'model_calls':0,
        'old_forward_prediction_changed':False,'auto_run':False,'stop_after_delivery':True}
    write_new(out/'Historical-PIT-Owner-Status.json',status)
    manifest={'version':'1.0.0','kind':'HistoricalPITRunManifest','recorded_at':now(),
        'files':[ref(p) for p in sorted(out.iterdir()) if p.is_file()],
        'new_code_and_contract_refs':[ref(p) for d in ('historical_pit','contracts/historical-pit')
                                      for p in sorted((ROOT/d).iterdir()) if p.is_file()],
        'adopted_baseline_map_ref':PIN,'frozen_strategy_spec_ref':spec_ref,
        'formal_execution':'BLOCKED','all_failed_attempts_retained':True,'productionGate':False}
    write_new(out/'Run-Manifest.json',manifest)
    return status


def verify_saved(output):
    out=Path(output)
    manifest=_json(reopen(ref(out/'Run-Manifest.json')))
    for r in manifest['files']+manifest['new_code_and_contract_refs']:
        reopen(r)
    reopen(manifest['adopted_baseline_map_ref']);reopen(manifest['frozen_strategy_spec_ref'])
    frozen_spec()
    views=_json(reopen(ref(out/'Daily-PIT-Candidate-Snapshots.json')))
    for snapshot in views['snapshots']:verify_candidate(snapshot)
    require(len(views['snapshots'])==981,'HP_SNAPSHOT_COUNT')
    matrix=_json(reopen(ref(out/'PIT-Closure-Matrix-60.json')))
    require(len({(r['symbol'],r['domain']) for r in matrix['rows']})==60 and
            matrix['continuous_domains_closed']==0 and
            all(r['continuous_closed'] is False for r in matrix['rows']),'HP_MATRIX_PROMOTION_STOP')
    attempt=_json(reopen(ref(out/'Backtest-Prerequisite-Attempt-BLOCKED.json')))
    require(attempt['engine_called'] is False and all(v is None for v in attempt['metrics'].values()) and
            attempt['state']=='BLOCKED_BEFORE_ENGINE','HP_ATTEMPT_PROMOTION_STOP')
    require((out/'Trade-Ledger-PENDING.jsonl').stat().st_size==0,'HP_PENDING_LEDGER_NOT_EMPTY')
    return {'verified_candidate_snapshots':981,'verified_closure_rows':60,
            'continuous_domains_closed':0,'formal_backtest':'BLOCKED','engine_called':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('calendar_manifest')
    p.add_argument('--cutoff-time',default=UNSET,help='Owner explicit Asia/Shanghai HH:MM[:SS], never invented')
    a=p.parse_args();print(json.dumps(build(a.output,a.calendar_manifest,a.cutoff_time),ensure_ascii=False))
