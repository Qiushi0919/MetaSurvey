"""Eight-category evidence inventory, never an admission authority."""
from copy import deepcopy
from .core import (ROOT, SYMBOLS, START, END, require_inputs, require_result,
                   make_result, sha, canonical, request_views)
from . import status, action, financial, industry
import json

CATEGORIES=('SECURITY_STATUS','CALENDAR_RULES','RAW_BARS','CORPORATE_ACTIONS',
    'ADJUSTMENT_VERSIONS','FINANCIAL_REVISIONS','ANNOUNCEMENTS','INDUSTRY_MEMBERSHIP')
ZERO_COUNTS=('source_policies','admitted_source_observations','admitted_clock_evidence','real_snapshots',
    'real_receipts','real_packets','real_assessments','real_cards','real_candidates','real_signals',
    'real_approvals','real_orders','model_calls','broker_calls','execution_writes')
GATES=('REAL_DATA_ADMISSION_GATE','LOCAL_REAL_RESEARCH_GATE','P1B_RESEARCH_PILOT_GATE',
    'CLOUD_RESEARCH_EXPORT_GATE','HISTORICAL_BACKTEST_GATE','PRODUCTION_DATA_GATE','REDISTRIBUTION_GATE',
    'CLOUD_MODEL_GATE','SIGNAL_ORDER_GATE','BROKER_GATE')

def analyze(inputs):
    require_inputs(inputs)
    parts={'status':status.analyze(inputs),'action':action.analyze(inputs),
           'financial':financial.analyze(inputs),'industry':industry.analyze(inputs)}
    for p in parts.values():require_result(p)
    inventory=[]
    for api in ('stock_basic','stock_st','namechange','suspend_d','trade_cal','daily','dividend','adj_factor','fina_indicator','index_member_all'):
        views=request_views(inputs,api)
        inventory.append({'api':api,'request_count':len(views),'new_request_count':sum(v['origin']=='new' for v in views),
            'physical_typed_row_count':sum(v['row_count'] for v in views),
            'new_typed_row_count':sum(v['row_count'] for v in views if v['origin']=='new'),
            'blocked_response_count':sum(v['response_blocked'] for v in views),
            'empty_response_count':sum(not v['row_count'] for v in views),
            'technical_access_observed_new_requests':sum(v.get('technical_access_observed',False) for v in views if v['origin']=='new'),
            'entitlement_inventory_verified':False,'license_verified':False,
            'product_identity_verified':False,'independent_permissions_required':'UNKNOWN_NO_PURCHASE_DECISION'})
    a=parts['action']['body'];f=parts['financial']['body'];i=parts['industry']['body'];s=parts['status']['body']
    categories=[
        {'category':'SECURITY_STATUS','engineering_state':s['c12_technical_coverage']['engineering_state'],'evidence_count':s['c12_technical_coverage']['physical_status_observation_count'],'gap':'HISTORICAL_STATUS_COMPLETENESS_AND_NEGATIVE_EVENTS_UNPROVEN'},
        {'category':'CALENDAR_RULES','engineering_state':'READY' if s['c12_technical_coverage']['calendar']['observed_open_sessions']==327 else 'PARTIAL','evidence_count':s['c12_technical_coverage']['calendar']['distinct_valid_civil_dates'],'gap':'BOARD_RULES_AUTHORITY_AND_SOURCE_ADMISSION_UNPROVEN'},
        {'category':'RAW_BARS','engineering_state':'PARTIAL','evidence_count':sum(q['row_count'] for q in request_views(inputs,'daily','legacy') if q.get('scope')=='COVERAGE'),'gap':'UNIT_AUTHORITY_AND_INDEPENDENT_NUMERIC_SOURCE_UNPROVEN'},
        {'category':'CORPORATE_ACTIONS','engineering_state':'AMBIGUOUS' if a['ambiguous_action_cases']['case_count'] else 'PARTIAL','evidence_count':a['factor_action_reconciliation']['change_point_count'],'gap':'ORIGINAL_ROW_SEMANTICS_AND_ENTITLEMENT_LEDGER_UNPROVEN'},
        {'category':'ADJUSTMENT_VERSIONS','engineering_state':'PARTIAL','evidence_count':a['adjustment_known_gaps']['nonzero_reference_delta_count'],'gap':'AUTHORITATIVE_REFERENCE_AND_ROUNDING_POLICY_UNSET_REQUIRED'},
        {'category':'FINANCIAL_REVISIONS','engineering_state':'PARTIAL','evidence_count':f['financial_revision_candidate']['combined_observation_count'],'gap':'REVISION_CHRONOLOGY_FULL_STATEMENTS_AND_HISTORICAL_VISIBILITY_UNPROVEN'},
        {'category':'ANNOUNCEMENTS','engineering_state':'BLOCKED','evidence_count':0,'gap':'NO_ENTITLEMENT_PROOF_NO_NEW_DISCLOSURE_API_PROBE_SSE_CHAIN_PRESERVED'},
        {'category':'INDUSTRY_MEMBERSHIP','engineering_state':'UNKNOWN','evidence_count':i['industry_membership_candidate']['observation_count'],'gap':'BLANK_BOUNDARIES_HISTORY_COMPLETENESS_AND_FIRST_VISIBILITY_UNKNOWN'}]
    for c in categories:c.update({'candidate_state':'CANDIDATE_FOR_OWNER_REVIEW','business_admission':'BLOCKED','historical_visibility_proven':False})
    baseline=json.loads((ROOT/'docs/overnight/conditions.json').read_bytes())
    delta={'baseline_hash':sha((ROOT/'docs/overnight/conditions.json').read_bytes()),'closed_ids':[],
        'conditions':[{'id':c['id'],'subject':c['subject'],'baseline_status_preserved':c['baseline_status_preserved'],
                       'this_phase_closure':'NOT_CLOSED','engineering_progress':'NEW_QUARANTINE_CANDIDATE_EVIDENCE_ONLY',
                       'remaining':c['remaining']} for c in baseline['conditions']]}
    return make_result(inputs,'REAL_DATA_ADMISSION_CANDIDATE',{
        'coverage_matrix_v2':categories,'api_access_matrix':inventory,'conditions_delta':delta,
        'component_hashes':{k:p['content_hash'] for k,p in parts.items()},
        'component_code_hashes':{k:p['code_hash'] for k,p in parts.items()},
        'supplier_evidence':'ABSENT_BY_EXPLICIT_OWNER_REPLY','entitlement_state':'TECHNICAL_ACCESS_ONLY_NOT_VERIFIED_PRODUCT_OR_ACCOUNT_TIER',
        'authorization_scope':{'symbols':list(SYMBOLS),'start':START,'end':END,'namespace':'CORE_40'},
        'units':{'raw_price':'PROVIDER_CNY_UNVERIFIED','raw_price_basis':'UNADJUSTED_DOCUMENTED_GATEWAY_UNVERIFIED',
            'vol':'HAND_DOCUMENTATION_ONLY','amount':'THOUSAND_CNY_DOCUMENTATION_ONLY',
            'independent_numeric_verification':False,'prices_or_units_calibrated':False},
        'counts':{k:0 for k in ZERO_COUNTS},'gates':{k:'BLOCKED' for k in GATES},
        'unknown_account_parameters':{'count':30,'state':'UNSET_REQUIRED'},
        'real_net_edge':'UNSET_REQUIRED','real_sizing':'UNSET_REQUIRED','real_probability':'UNSET_REQUIRED',
        'C30':'AT_LEAST_20_ACTUAL_FORWARD_PAPER_TRADING_DAYS_REMAINS_UNSATISFIED',
        'real_snapshot_B_ready':False,'owner_admission_recommendation':'NOT_READY',
        'next_phase_authorized':False},__file__)
