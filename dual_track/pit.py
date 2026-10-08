"""Gap register derived from the frozen H-B evidence map; closes no PIT gaps."""
import json
from pathlib import Path
from .common import now, ref, reopen, require, write_new

PIN = {'path':'/Users/qiushi/投资研究/.p1b-archives/wave-hb-20261007/results/MAP-G2/Historical-PIT-Blocker-Map.json',
       'bytes':1732906,'sha256':'sha256:f00f773af8cf12361d5105ac07089a700f13240c0a74985fb3f5d6f7ab89132e'}


def build(path):
    original=json.loads(reopen(PIN))
    require(original['continuous_historical_domains_closed']==0 and original['historical_visibility_proven'] is False, 'DT_PIT_BASELINE_DRIFT')
    domain_rows=[]
    for domain in original['domains']:
        domain_rows.append({'symbol':domain['symbol'],'domain':domain['domain'],
            'published_at':None,'first_seen_at':None,'historical_available_at':None,
            'historical_decision_time':None,'revision_chronology':'NOT_PROVEN',
            'source_hash_state':'CURRENT_REFERENCE_HASHES_EXIST_HISTORICAL_VERSION_CHAIN_NOT_PROVEN',
            'source_evidence_pointer':{'map_ref':PIN,'selector':{'domain':domain['domain'],'symbol':domain['symbol']}},
            'current_independent_structural_evidence':domain.get('independent_structural_evidence','UNRECORDED_IN_BASELINE'),
            'current_historical_coverage':domain.get('historical_coverage','UNRECORDED_IN_BASELINE'),
            'required_per_decision_fields':domain['required_per_decision_fields'],
            'preserved_reason_codes':domain['reason_codes'],'formal_admission':'BLOCKED',
            'meaning':'NULL_IS_UNPROVEN_REQUIRED_HISTORICAL_INSTANT_NOT_ERASURE_OF_DATE_ONLY_ORIGINAL_FACTS'})
    return write_new(path, {'version':'1.0.0','kind':'FormalHistoricalPITGapRegister',
        'created_at':now(),'source_map_ref':PIN,'namespace':'FORMAL_HISTORICAL_PIT_PREPARATION:CORE_40',
        'historical_visibility_proven':False,'continuous_domains_closed':0,
        'domain_count':len(original['domain_groups']),'symbol_domain_rows':len(domain_rows),
        'priority_domains':{'financial':['financial_ann_fann_date','revision_chronology_first_visibility'],
            'announcement':['catalyst_originals'],'industry':['industry_history'],
            'status':['name_status_history','st_history','suspension_history','listing_delisting_history','historical_price_limit_regime'],
            'corporate_action':['corporate_actions','dividend_action_reconciliation','adjustment_factor_semantics']},
        'closure_requirements':original['closure_requirements'],'entries':domain_rows,
        'expansion':{'state':'PROPOSAL_REQUIRED_NO_DOWNLOAD_AUTHORITY','needed':'LONGER_RAW_HISTORY_AND_DATED_CALENDAR_ACTIONS_STATUS_UNIVERSE_AND_LICENSE',
            'source':'UNSET_REQUIRED','license':'UNSET_REQUIRED','minimum_years':'UNSET_REQUIRED'},
        'formal_backtest':'BLOCKED','productionGate':False,'network_requests':0,'credential_lookups':0})
