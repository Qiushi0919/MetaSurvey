"""Repeatable Owner acceptance inventory and prerequisite ledgers, never trades.

This read-only report adapter consumes the already executed sidecar diagnosis.
It does not perform admission, execute an engine, or invent policy defaults.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path

from .dto import clock
from .interface import *
from .requirements import evaluate_coverage, policy_gaps
from .sources import catalog
from .store import EvidenceStore
from .strategy import _ref
from .pit import event_day

PRIVATE = Path('/Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008')

# Dependencies are projections of the frozen spec, not additional entry gates.
# Raw vendor spelling and normalized names are both retained by the importer.
DEPENDENCIES = (
 ('Quality','TTM growth / gross margin','FINANCIAL_INCOME',('revenue','oper_cost','n_income'),FINANCIAL_START),
 ('Quality','positive NI / OCF to NI','FINANCIAL_CASHFLOW',('n_cashflow_act',),FINANCIAL_START),
 ('Quality','ROIC / net debt to positive EBITDA','FINANCIAL_INDICATOR',('roic','ebitda','netdebt'),FINANCIAL_START),
 ('Industry RS','stock TR20 minus sector TR20','SECTOR_TOTAL_RETURN',('trade_date','total_return_index'),HISTORY_START),
 ('Valuation','PE_TTM or EV / normalized cycle EBITDA','VALUATION',('trade_date','pe_ttm','total_mv'),HISTORY_START),
 ('Price / Volume Timing','unchanged Pullback / Breakout price components','PRICE',('trade_date','open','high','low','close','vol'),HISTORY_START),
 ('Catalyst','official human-coded last60 actual sessions','CATALYST',('event_type','published_at','rescinded_at','expires_at'), '2021-01-01'),
 ('Listing / Delisting','historical identity / eligibility','STATUS',('ts_code','list_date','delist_date','market'),HISTORY_START),
 ('Name / ST history','effective name / risk-warning intervals','STATUS',('name','start_date','end_date','is_st'),HISTORY_START),
 ('Suspension / Resume','tradability / next executable session','STATUS',('suspend_type','suspend_date','resume_date'),HISTORY_START),
 ('Historical price limits','dated up/down limits / executable fills','STATUS',('trade_date','up_limit','down_limit'),HISTORY_START),
 ('Exchange calendar','actual sessions / T+1 / hold20-40 / purge-embargo','CALENDAR',('cal_date','exchange','is_open'),HISTORY_START),
 ('Corporate actions','stock total return / cash and quantity reconciliation','ACTION',('ex_date','record_date','pay_date','cash_div','stk_div','rights_ratio','rights_price'),HISTORY_START),
 ('Adjustment factors','reconciliation input, not complete action proof','ACTION',('trade_date','adj_factor'),HISTORY_START),
 ('Financial statements','latest4+previous4 PIT flows / dated debt and cash','FINANCIAL_BALANCE',('end_date','money_cap','total_liab','st_borr','lt_borr','bond_payable'),FINANCIAL_START),
 ('Financial statements','income statement source / accepted NI definition','FINANCIAL_INCOME',('end_date','revenue','oper_cost','n_income'),FINANCIAL_START),
 ('Financial statements','cashflow source / cumulative versus discrete','FINANCIAL_CASHFLOW',('end_date','n_cashflow_act'),FINANCIAL_START),
 ('Financial announcement/revision chronology','actual original and restated publication chronology','FINANCIAL_INCOME',('ann_date','f_ann_date','report_type','update_flag'),FINANCIAL_START),
 ('Financial announcement/revision chronology','all balance statement versions','FINANCIAL_BALANCE',('ann_date','f_ann_date','report_type','update_flag'),FINANCIAL_START),
 ('Financial announcement/revision chronology','all cashflow statement versions','FINANCIAL_CASHFLOW',('ann_date','f_ann_date','report_type','update_flag'),FINANCIAL_START),
 ('Financial announcement/revision chronology','all indicator versions','FINANCIAL_INDICATOR',('ann_date','f_ann_date'),FINANCIAL_START),
 ('Historical industry membership','contemporaneous classification / removed members','INDUSTRY_MEMBERSHIP',('ts_code','in_date','out_date','l1_code','l2_code','l3_code'),HISTORY_START),
 ('Historical universe','include listed / paused / delisted, identifier changes','UNIVERSE',('ts_code','list_date','delist_date','list_status'),HISTORY_START),
 ('Benchmark total return','licensed Owner-selected total-return comparison','BENCHMARK',('trade_date','total_return_index','index_identifier','tax_action_method'),HISTORY_START),
 ('Dated transaction costs','explicit dated fee / minimum / slippage profile','POLICY',('commission_rate','minimum_commission_minor','stamp_tax_rate','regulatory_fee_rate','slippage','effective_from','effective_until','rounding','partial_fill_aggregation'),EVALUATION_START),
 ('Account/risk assumptions','capital / lots / T+1 / position / kill policies','POLICY',('initial_cash_minor','verified_lot','owner_position_limit','owner_maximum_exposure','owner_industry_limit','owner_stop_policy','owner_drawdown'),EVALUATION_START),
 ('Economic estimation policy','WACC / cycle / valuation / Edge / grades','POLICY',('cost_of_capital_estimation','normalized_cycle_earnings_method','valuation_estimation','scenario_probabilities','uncertainty_buffer','edge_calibration','grade_mapping'),EVALUATION_START),
)

OUTPUT_ITEMS = ('candidate_ledger','decision_ledger','order_execution_ledger','complete_trade_ledger',
 'daily_nav','gross_return','fees','slippage','net_return','turnover','max_drawdown','MAE_MFE_MAE40',
 'holding_period_distribution','benchmark_total_return','excess_return','grade_attribution',
 'family_attribution','market_regime_attribution','failed_blocked_reasons','data_quality_pit_exceptions')

def _clocks(rows, key):
    counts = Counter(clock(r.get(key))['precision'] for r in rows)
    literals = sorted({str(r[key]) for r in rows if r.get(key) is not None})
    return {'precision_counts':dict(counts),'sample_literals':literals[:3],
            'no_date_to_midnight':True,'historical_admission':False}

def build_matrix(records):
    records = list(records)
    matrix = []
    for category, feature, domain, fields, start in DEPENDENCIES:
        for field in fields:
            symbols = SYMBOLS[1:] if category=='Valuation' and field=='pe_ttm' else (
                SYMBOLS[:1] if category=='Valuation' and field=='total_mv' else SYMBOLS)
            rows = [r for r in records if r.get('domain')==domain and r.get('symbol') in (*symbols,'ALL','*','SSE')]
            present = [r for r in rows if r.get('fields',{}).get(field) is not None]
            missing = ['HISTORICAL_VISIBILITY_AND_REVISION_CHAIN_NOT_ACCEPTED','LICENSE_NOT_ACCEPTED',
                       'CONTINUOUS_HISTORY_AND_APPLICABLE_INTERVAL_NOT_PROVEN']
            if not present: missing.insert(0,'RAW_FIELD_ABSENT')
            if domain=='POLICY': missing=['UNSET_REQUIRED_NO_DEFAULTS']
            units=Counter(canonical(r.get('units',{})).decode() for r in present)
            refs=[{k:r.get(k) for k in ('raw_ref','raw_sha256','record_hash','row_ordinal')} for r in present[:3]]
            days=sorted({str(r['event_date']) for r in present if r.get('event_date') is not None})
            matrix.append({'category':category,'strategy_feature':feature,'domain':domain,
                'dependency_basis':'FROZEN_LOGICAL_REQUIREMENT_PROVIDER_FIELD_SPELLING_IS_CANDIDATE_NOT_NEW_ENTRY_GATE',
                'required_raw_fields':[field],'symbols':list(symbols),'source':sorted({r['source'] for r in rows}),
                'historical_range':{'start':start,'end':HISTORY_END,'formal_anchor':None},
                'captured_nonnull_rows':len(present),'counts_are_capture_bindings_not_independent_samples':True,
                'per_symbol':{s:sum(r.get('symbol')==s for r in present) for s in symbols},
                'observed_event_range':{'first':days[0] if days else None,'last':days[-1] if days else None,
                    'distinct_event_dates':len(days),'continuous_coverage_proven':False},
                'event_time':_clocks(present,'event_date'),'published_at':_clocks(present,'published_at'),
                'available_at':_clocks(present,'available_at'),'retrieved_at':_clocks(present,'retrieved_at'),
                'original_disclosure_fields':{k:sorted({str(r['fields'][k]) for r in present if r['fields'].get(k) is not None})[:3]
                    for k in ('ann_date','f_ann_date','publish_date','update_time')},
                'revision_version':{'vendor_revision_ids':sorted({str(r['revision_id']) for r in present if r.get('revision_id')}),
                    'content_versions':len({r.get('record_hash') for r in present}),
                    'content_hash_is_vendor_revision':False,'full_revision_chain':'NOT_ACCEPTED'},
                'first_visible_evidence':{'clocks':_clocks(present,'first_visible_at'),
                    'independent_historical_registry':'EMPTY_NOT_ACCEPTED','sample_raw_refs':refs},
                'applicable_interval':{'required_from':start,'required_until':HISTORY_END,
                    'observed_fields':{k:sorted({str(r['fields'][k]) for r in present if r['fields'].get(k) is not None})[:3]
                        for k in ('in_date','out_date','list_date','delist_date','effective_from','effective_until')},
                    'endpoint_semantics':'UNKNOWN_NOT_ASSUMED_OPEN_ENDED','accepted':False},
                'unit_rounding':{'observed_declarations':dict(units),'unit_accepted':False,
                    'money_convention':'CNY_MINOR_INTEGER_HALF_EVEN_ONLY_FOR_EXPLICIT_HYPOTHETICAL_PROFILE',
                    'no_fx_or_scale_conversion_inferred':True},
                'license':sorted({r.get('license_state','UNKNOWN') for r in rows}),
                'pit_status':'BLOCKED','strategy_state':'NOT_COMPUTABLE','missing_reason':missing})
    return {'state':'PASS','scope':'DEPENDENCY_INVENTORY_ONLY_NOT_DATA_ADMISSION','labels':LABELS,
        'strategy_spec_sha256':SPEC_SHA256,'categories':sorted({r['category'] for r in matrix}),
        'rows':matrix,'policy_gaps':policy_gaps(),'optional_not_entry_gates':['ROE','PB'],
        'full_strategy_data_pass':False,'productionGate':False}

def pin(path):
    path=Path(path);raw=path.read_bytes()
    return {'path':str(path),'sha256':digest(raw),'bytes':len(raw)}

def _jsonl(path, rows):
    with Path(path).open('xb') as f:
        for row in rows: f.write(canonical(row)+b'\n')
    Path(path).chmod(0o600)

def validate_parent(result, records, summary):
    """Reject promotion, scope drift and unresolved refs before writing outputs."""
    if result['strategy_sha256']!=SPEC_SHA256 or result['families']!=list(FAMILIES):
        raise ValueError('FROZEN_FAMILY_CONFLICT_STOP')
    if (result['engine_called'] is not False or result['state']!='ENGINE_NOT_RUN'
        or result['execution_state']!='ENGINE_NOT_RUN' or result['prerequisite_state']!='NOT_COMPUTABLE'
        or result['labels']!=LABELS or any(result.get(k) is not False for k in
            ('historical_visibility_proven','untouched_oos','productionGate','native_orders','timing_ablation_authorized'))
        or not result['economic_metrics'] or any(v is not None for v in result['economic_metrics'].values())):
        raise ValueError('ONLY_UNRUN_PREREQUISITE_REPORT_SUPPORTED')
    if result['candidate_count']!=len(result['candidates']):
        raise ValueError('CANDIDATE_COUNT_CONFLICT')
    seen=set()
    for c in result['candidates']:
        key=(c['symbol'],c['decision_date'])
        day=date.fromisoformat(c['decision_date']).isoformat()
        if c['decision_date']!=day or key in seen or c['symbol'] not in SYMBOLS or not EVALUATION_START<=day<=HISTORY_END:
            raise ValueError('CANDIDATE_SCOPE_CONFLICT')
        seen.add(key)
        if set(c['families'])!=set(FAMILIES) or any(f['state']!='NO_DECISION' for f in c['families'].values()):
            raise ValueError('PREREQUISITE_LEDGER_CANNOT_CONSUME_EXECUTED_DECISIONS')
        if c['prerequisite_ref'] not in result['prerequisite_snapshots'] or c['common_blocker_ref'] not in result['common_blockers']:
            raise ValueError('UNRESOLVED_PREREQUISITE_OR_BLOCKER')
        if any(ref not in result['lineage_catalog'] for ref in c['price_features'].get('window_lineage_refs',[])):
            raise ValueError('UNRESOLVED_PRICE_LINEAGE')
    for collection in ('lineage_catalog','prerequisite_snapshots','common_blockers'):
        if any(key!='sha256:'+digest(canonical(value)) for key,value in result[collection].items()):
            raise ValueError('PARENT_REFERENCE_HASH_CONFLICT')
    current_rows={(r.get('capture_id'),r.get('row_ordinal'),r.get('record_hash'),r.get('raw_sha256')):r for r in records}
    bound={}
    for refid,ref in result['lineage_catalog'].items():
        key=tuple(ref.get(k) for k in ('capture_id','row_ordinal','record_hash','raw_sha256'))
        if key not in current_rows:raise ValueError('DIAGNOSTIC_LINEAGE_NOT_IN_CURRENT_STORE')
        # Rehashing a fabricated clock/identity does not make it evidence.
        record=current_rows[key]
        if canonical(ref)!=canonical(_ref(record)):raise ValueError('DIAGNOSTIC_LINEAGE_METADATA_CONFLICT')
        bound[refid]=record
    for c in result['candidates']:
        feature=c['price_features']
        refs=feature.get('window_lineage_refs',[])
        if not isinstance(refs,list) or not refs:raise ValueError('PRICE_WINDOW_REFERENCES_REQUIRED')
        nested=[ref for section in ('duplicate_dates','conflicts') for item in feature.get(section,[])
                for ref in item.get('lineage_refs',[])]
        if any(ref not in refs for ref in nested):raise ValueError('NESTED_PRICE_REFERENCE_OUTSIDE_WINDOW')
        for refid in refs:
            record=bound[refid]
            if record.get('domain')!='PRICE' or record.get('symbol')!=c['symbol']:
                raise ValueError('PRICE_WINDOW_IDENTITY_CONFLICT')
            try:day=event_day(record.get('event_date'))
            except (ValueError,TypeError):raise ValueError('PRICE_WINDOW_EVENT_DATE_UNKNOWN')
            if day>c['decision_date']:raise ValueError('PRICE_WINDOW_FUTURE_EVENT')
        snapshot=result['prerequisite_snapshots'][c['prerequisite_ref']]
        if snapshot.get('symbol')!=c['symbol'] or snapshot.get('asof')!=c['decision_date']:
            raise ValueError('PREREQUISITE_SNAPSHOT_IDENTITY_CONFLICT')
    if summary.get('record_versions')!=len(records) or summary.get('domain_counts')!=dict(Counter(r['domain'] for r in records)):
        raise ValueError('DIAGNOSTIC_STORE_COUNTS_CONFLICT')

def emit(db_path, diagnostic_path, output_root):
    db=Path(db_path).resolve();diag=Path(diagnostic_path).resolve();out=Path(output_root).resolve()
    if not all(p.is_relative_to(PRIVATE) for p in (db,diag,out)) or out==PRIVATE:
        raise ValueError('ACCEPTANCE_PATH_OUTSIDE_NEW_PRIVATE_EPOCH')
    if not db.is_file(): raise ValueError('EXISTING_DB_REQUIRED_NO_CREATE')
    frozen_spec()
    before=pin(db)
    with EvidenceStore(db) as store:
        records=store.records();inventory=store.summary();audit=store.audit_raw()
    if pin(db)!=before: raise ValueError('REPORT_INPUT_DB_CHANGED_STOP')
    if audit['state']!='PASS_INTEGRITY_ONLY': raise ValueError('RAW_INTEGRITY_STOP')
    result=json.loads(diag.read_bytes())
    # This adapter supports the present unrun path only, never promotes results.
    summary_path=diag.parent/'summary.json'
    summary=json.loads(summary_path.read_bytes())
    validate_parent(result,records,summary)
    diagnostic_pin=pin(diag)
    out.mkdir(parents=True,exist_ok=False);out.chmod(0o700)
    matrix=build_matrix(records);coverage=evaluate_coverage(records)
    write_new(out/'CORE40-Data-Matrix.json',matrix)
    write_new(out/'Five-Year-Coverage.json',coverage)
    write_new(out/'PIT-Admission-Progress.json',{'state':'BLOCKED','priority_order':
        ['PRICE_VOLUME','CALENDAR','LISTING_STATUS','SUSPENSION_LIMIT','CORPORATE_ACTION','FINANCIAL',
         'VALUATION','INDUSTRY','CATALYST','UNIVERSE','BENCHMARK','LICENSE'],
        'actual_price_only_admitted':0,'actual_full_family_admitted':0,'domain_closures':[],
        'fixture_positive_is_real_admission':False,'untouched_oos':False,'productionGate':False})
    write_new(out/'Raw-Dataset-Inventory.json',{'state':'PASS','scope':'CAPTURE_INVENTORY_ONLY',
        'store':inventory,'db_pin':before,'raw_integrity':audit,'history_and_new_captures_unified':True})
    write_new(out/'Source-License-Matrix.json',{'state':'BLOCKED','sources':catalog(),
        'captured_source_states':inventory['domains'],'license_passed':False,'productionGate':False})
    _jsonl(out/'Candidate-Prerequisite-Ledger.jsonl',({'symbol':c['symbol'],'decision_date':c['decision_date'],
        'state':'NOT_COMPUTABLE','emitted_trade_candidate':False,'grade':None,
        'feature_values':c['price_features'].get('values'),'feature_conditions':c['price_features'].get('conditions'),
        'prerequisite_ref':c['prerequisite_ref'],'blocker_ref':c['common_blocker_ref'],
        'labels':LABELS} for c in result['candidates']))
    # The pinned parent resolves all shared lineage/prerequisite/blocker refs.
    _jsonl(out/'Decision-Prerequisite-Ledger.jsonl',({'symbol':c['symbol'],'decision_date':c['decision_date'],
        'family':family,'state':'NOT_COMPUTABLE','decision':f['state'],
        'reason':f['reason'],'raw_price_component':f['raw_price_component'],
        'prerequisite_ref':c['prerequisite_ref'],'blocker_ref':c['common_blocker_ref'],'labels':LABELS}
        for c in result['candidates'] for family,f in c['families'].items()))
    statuses={name:{'state':'ENGINE_NOT_RUN','value':None,
        'reason':'FULL_FROZEN_FAMILY_DATA_METHOD_EXECUTION_PREREQUISITES_BLOCKED'} for name in OUTPUT_ITEMS}
    statuses['candidate_ledger']={'state':'NOT_COMPUTABLE','path':str(out/'Candidate-Prerequisite-Ledger.jsonl'),
        'rows':len(result['candidates']),'scope':'PREREQUISITE_OBSERVATIONS_NOT_TRADE_CANDIDATES'}
    statuses['decision_ledger']={'state':'NOT_COMPUTABLE','path':str(out/'Decision-Prerequisite-Ledger.jsonl'),
        'rows':len(result['candidates'])*len(FAMILIES),'decision':'NO_DECISION'}
    statuses['failed_blocked_reasons']={'state':'BLOCKED','diagnostic_pin':diagnostic_pin,
        'blockers':result['common_blockers']}
    statuses['data_quality_pit_exceptions']={'state':'BLOCKED','coverage_pin':pin(out/'Five-Year-Coverage.json'),
        'historical_pit':'NOT_ACCEPTED'}
    write_new(out/'Required-Outputs-Status.json',{'state':'ENGINE_NOT_RUN','outputs':statuses,
        'MAE40':None,'account_terminal_value':None,'real_or_counterfactual_performance':None,
        'labels':LABELS,'untouched_oos':False,'productionGate':False})
    write_new(out/'Historical-Universe-Progress.json',{'state':'BLOCKED',
        'current_symbols':list(SYMBOLS),'historical_all_market_members':None,
        'expand_to_today_survivors':False,'reason':'COMPLETE_LISTED_PAUSED_DELISTED_EFFECTIVE_HISTORY_ABSENT'})
    write_new(out/'PIT-Engine-Adapter-Progress.json',{'state':'NOT_COMPUTABLE',
        'reused':['Wave G price feature functions','Wave F pure fee helper'],
        'engine_called':False,'actual_account':'UNSET_REQUIRED','shared_contract_final_approval':False,
        'remaining':['historical_admitted_snapshot','complete_family_methods','actual_execution_adapter',
            'dated_cost_profile','partial_fill_rounding_bridge','full_ledger_and_nav_reconciliation'],
        'scenario_names_allowed':['BASE','PESSIMISTIC','UPPER-BOUND'],'scenario_values':None,
        'scenario_defaults_inferred':False,'productionGate':False})
    write_new(out/'Owner-Prompt-Readback.json',{'state':'PASS','scope':'REQUEST_DELIVERABLE_MAPPING',
        'data_matrix_categories':len(matrix['categories']),'field_dependency_rows':len(matrix['rows']),
        'engine_state':'ENGINE_NOT_RUN','full_family_state':'NOT_COMPUTABLE',
        'no_trades_claim':False,'db_unchanged':True,'diagnostic_pin':diagnostic_pin,
        'owner_final_question_answer':None,'reason':'RAW_DATA_PIT_METHOD_ACCOUNT_ENGINE_AND_BENCHMARK_BLOCKERS'})
    files=[pin(p) for p in sorted(out.iterdir()) if p.is_file()]
    write_new(out/'Delivery-Package-Manifest.json',{'recorded_at':utc_now(),'db_pin':before,
        'diagnostic_pin':diagnostic_pin,'files':files,'labels':LABELS,'source_code_commit':'EXTERNAL_FIXED_CANDIDATE_MANIFEST',
        'admission_or_trading_authority':False,'productionGate':False})
    return {'output_root':str(out),'categories':len(matrix['categories']),'field_rows':len(matrix['rows']),
        'candidate_prerequisite_rows':len(result['candidates']),
        'decision_prerequisite_rows':len(result['candidates'])*len(FAMILIES),'engine_state':'ENGINE_NOT_RUN'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',required=True);p.add_argument('--diagnostic',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(emit(a.db,a.diagnostic,a.output),ensure_ascii=False))

if __name__=='__main__':main()
