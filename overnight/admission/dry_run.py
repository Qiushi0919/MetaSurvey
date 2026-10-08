"""Eight-category preparation report. Deliberately has no admission/signer API."""
from ..data.dataset import validate_dataset
from ..data.coverage import analyze_coverage
from ..analysis.inputs import canonical_hash
from ..analysis.reconcile import analyze_reconciliation
from ..analysis.financial import analyze_financial

CATEGORIES = ('SECURITY_STATUS','CALENDAR_RULES','RAW_BARS','CORPORATE_ACTIONS',
              'ADJUSTMENT_VERSIONS','FINANCIAL_REVISIONS','ANNOUNCEMENTS','INDUSTRY_MEMBERSHIP')
API_CATEGORIES = {'stock_basic':'SECURITY_STATUS','suspend_d':'SECURITY_STATUS','trade_cal':'CALENDAR_RULES',
                  'daily':'RAW_BARS','dividend':'CORPORATE_ACTIONS','adj_factor':'ADJUSTMENT_VERSIONS',
                  'fina_indicator':'FINANCIAL_REVISIONS','index_member_all':'INDUSTRY_MEMBERSHIP'}
COMMON = ('PROVIDER_CHANNEL_IDENTITY_UNVERIFIED','ACCOUNT_PRODUCT_ENTITLEMENT_UNVERIFIED',
          'LOCAL_PURPOSE_STORAGE_RETENTION_LICENSE_UNVERIFIED','TRANSPORT_INTEGRITY_UNVERIFIED',
          'HISTORICAL_FIRST_AVAILABILITY_UNPROVEN')

def build_readiness(dataset):
    validate_dataset(dataset)
    coverage = analyze_coverage(dataset)
    factor = analyze_reconciliation(dataset)
    financial = analyze_financial(dataset)
    categories = []
    for category in CATEGORIES:
        requests = [q for q in dataset['requests'] if API_CATEGORIES[q['api_name']] == category]
        covered = [q for q in requests if q['scope'] == 'COVERAGE']
        reasons = list(COMMON)
        engineering = 'TYPED_QUARANTINE_READY'
        if not requests:
            engineering = 'NOT_CAPTURED'
            reasons += ['REQUIRED_CATEGORY_NOT_CAPTURED']
        if category == 'SECURITY_STATUS':
            reasons += ['CURRENT_STATUS_NOT_HISTORICAL_ST_OR_SUSPENSION_PROOF']
        elif category == 'CALENDAR_RULES':
            reasons += ['COMPLETE_BOARD_SESSION_RULES_NOT_ADMITTED']
            engineering = 'BOUNDED_CALENDAR_DIAGNOSTIC_READY' if coverage['calendar']['complete_bounded_calendar'] else 'CALENDAR_GAPS_OR_INVALID'
        elif category == 'RAW_BARS':
            reasons += ['GATEWAY_UNITS_UNVERIFIED','NUMERIC_SECOND_SOURCE_UNAVAILABLE']
            engineering = 'BOUNDED_RAW_DIAGNOSTIC_READY' if coverage['diagnostic_result'] == 'PASS_BOUNDED_ENGINEERING_ONLY' else 'BAR_CALENDAR_OR_IDENTITY_GAPS'
        elif category in ('CORPORATE_ACTIONS','ADJUSTMENT_VERSIONS'):
            reasons += ['ACTION_ORIGINAL_AND_REVISION_AUTHORITY_UNVERIFIED','ACTION_ENTITLEMENT_LEDGER_NOT_RECONSTRUCTED',
                        'ROUNDING_TOLERANCE_UNSET_REQUIRED','NUMERIC_SECOND_SOURCE_UNAVAILABLE']
            engineering = 'EXACT_FACTOR_DIAGNOSTIC_PARTIAL' if factor['symbols'] else 'FACTOR_BAR_INPUT_MISSING'
            if any(x['action_required_gaps'] for x in factor['symbols']):
                reasons += ['ACTION_LINK_MISSING_OR_AMBIGUOUS']
        elif category == 'FINANCIAL_REVISIONS':
            reasons += ['REPORT_PERIOD_SCOPE_ANOMALY_NOT_PROVIDER_REPAIRED','DATE_ONLY_IS_NOT_PUBLICATION_INSTANT',
                        'HISTORICAL_REVISION_VISIBILITY_UNPROVEN','FINANCIAL_STATEMENTS_NOT_COMPLETE']
            engineering = 'APPEND_ONLY_OBSERVED_VERSION_PARSER_READY' if financial['observations'] else 'FINANCIAL_INPUT_MISSING'
        elif category == 'ANNOUNCEMENTS':
            reasons += ['EXISTING_SSE_REFERENCE_ONLY_NO_GATEWAY_ANNOUNCEMENT_PROBE','COMPLETE_180_DAY_ANNOUNCEMENT_REVISION_CORPUS_MISSING']
            engineering = 'EXISTING_SSE_REFERENCE_PRESERVED'
        elif category == 'INDUSTRY_MEMBERSHIP':
            reasons += ['BLANK_EFFECTIVE_END_DATE_SEMANTICS_UNSET_REQUIRED','MEMBERSHIP_REVISION_PIT_UNPROVEN']
            engineering = 'INVALID_DATE_PRESERVED_NOT_NORMALIZED_TO_INFINITY'
        categories.append({'category':category,'actual_apis':sorted({q['api_name'] for q in requests}),
                           'requests':len(requests),'observed_physical_rows':sum(q['row_count'] for q in requests),
                           'coverage_physical_rows':sum(q['row_count'] for q in covered),
                           'request_refs':[{'request_fingerprint':q['request_fingerprint'],'raw_sha256':q['raw_sha256'],
                                            'report_sha256':q['report_sha256'],'scope':q['scope'],
                                            'response_dq':q['response_dq']} for q in requests],
                           'engineering_readiness':engineering,'state':'QUARANTINED','admission_status':'BLOCKED',
                           'historical_visibility_proven':False,'blocking_reasons':reasons,
                           'next_action':'INDEPENDENT_SOURCE_EVIDENCE_AND_SEPARATE_OWNER_GATE_REQUIRED'})
    result = {'version':'1.0.0-diagnostic','kind':'ADMISSION_READINESS_DRY_RUN','fixture':dataset['fixture'],
              'namespace':'CORE_40','state':'QUARANTINED','source_admission':'BLOCKED',
              'historical_visibility_proven':False,'productionGate':False,
              'new_source_policies':0,'new_source_observations':0,'admitted_clock_evidence_issued':0,
              'real_snapshots_issued':0,'real_receipts_issued':0,'real_packets_issued':0,'real_cards_issued':0,
              'authenticated_requests_this_run':0,'credential_lookups_this_run':0,
              'real_snapshot_B_ready':False,'pilot_ready':False,'cloud_export_permitted':False,
              'historical_backtest_permitted':False,'redistribution_permitted':False,'broker_permitted':False,
              'all_actual_account_parameters':'UNSET_REQUIRED',
              'input_hashes':{'dataset':canonical_hash(dataset),'coverage':canonical_hash(coverage),
                              'factor':canonical_hash(factor),'financial':canonical_hash(financial)},
              'categories':categories,'closed_business_condition_ids':[],
              'C30':'AT_LEAST_20_ACTUAL_FORWARD_PAPER_TRADING_DAYS_NOT_SATISFIED_BY_FIXTURES'}
    result['content_hash'] = canonical_hash(result)
    return result
