"""Evidence-only historical rules: six new official originals, no history issuer.

The 2020 general rule and December risk-board revision fill dated structural
rule gaps. They do not determine a security's status, an unbroken applicable
rule interval, or the first-visible instant of any historical observation.
Network capture has stopped. Runtime projections reopen immutable originals.
"""
from copy import deepcopy
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
import json

from .common import (ARCHIVE, ROOT, BASELINE_ROOT, SYMBOLS, require, canonical,
                     sha, digest, keys, timestamp, checked_file, reopen, ref,
                     metadata, blocked)
from wave_f.pit import DOMAINS
from wave_g import pit as prior

EVIDENCE_PATH=ARCHIVE/'public/pit/evidence-H1.json'
EVIDENCE_HASH='sha256:38e9cf1044eb72b6a0c89a6ec6217dcc4db6849e6ee52043e5a943e193dac535'
CAPTURE_URLS={
 'sse-rule-2020-notice':'https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/c_20230217_5716494.shtml',
 'sse-rule-2020-full':'https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/10118619/files/b39b8db2daa74eac916d8b3d6907af51.docx',
 'sse-rule-2020-delayed':'https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/10118619/files/b79c255874ea49679c46eca9ff1f3aed.docx',
 'sse-rule-repeal-index':'https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/',
 'sse-risk-2020-notice':'https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/c_20230217_5716497.shtml',
 'sse-risk-2020-full':'https://www.sse.com.cn/lawandrules/sselawsrules/repeal/rules/c/10118613/files/cb9b184718b74e92aea04159ed2f82e5.doc',
}
FACT_DATES={
 'SSE_2020_GENERAL_RULE_DATED_NOTICE':('2020-03-13','2020-03-13'),
 'SSE_2020_GENERAL_LIMIT_AND_TICK':('2020-03-13','2020-03-13'),
 'SSE_2020_FIRST_DAY_EXCEPTIONS':('2020-03-13','2020-03-13'),
 'SSE_2020_DELAYED_PROVISIONS':('2020-03-13',None),
 'SSE_2020_EX_DIVIDEND_REFERENCE_STRUCTURE':('2020-03-13','2020-03-13'),
 'SSE_2020_RISK_BOARD_DATED_NOTICE':('2020-12-31','2020-12-31'),
 'SSE_2020_RISK_BOARD_LIMIT_EXCEPTIONS':('2020-12-31','2020-12-31'),
 'SSE_2020_RISK_BOARD_ST_MARKER_SEMANTICS':('2020-12-31','2020-12-31'),
}
PUBLIC=ARCHIVE/'public/pit'
VALIDATION=ARCHIVE/'validation/pit'
PREDECESSOR_GIT=(BASELINE_ROOT/'docs/wave-g/Historical-PIT-Three-Symbol-Matrix.json',
                 BASELINE_ROOT/'docs/wave-g/Historical-PIT-Closure-Progress.json')


def _json(raw):
    def unique(pairs):
        x={}
        for k,v in pairs:
            require(k not in x,'WH_PIT_DUPLICATE_JSON_KEY');x[k]=v
        return x
    x=json.loads(raw,object_pairs_hook=unique)
    canonical(x);return x


def _ref(r):
    keys(r,('path','sha256','bytes'))
    p=Path(r['path'])
    if p.is_relative_to(ARCHIVE):
        require(p.is_relative_to(PUBLIC) or p.is_relative_to(VALIDATION),'WH_PIT_OWNED_REFERENCE_ONLY')
        return reopen(r,private=True)
    require(p in PREDECESSOR_GIT or p==prior.EVIDENCE_PATH,'WH_PIT_PREDECESSOR_REFERENCE_ONLY')
    return reopen(r,private=p==prior.EVIDENCE_PATH)


def _day(x):
    if x is None:return
    require(type(x) is str and date.fromisoformat(x).isoformat()==x,'WH_PIT_DATE_ONLY_REQUIRED')


def _semantics(captures,facts):
    cs={c['capture_id']:_ref(c['parsed_ref']).decode('utf-8') for c in captures}
    require(all(t in cs['sse-rule-2020-notice'] for t in ('上证发〔2020〕17号','2020年3月13日','暂缓实施')),
            'WH_PIT_GENERAL_NOTICE_SOURCE_MISMATCH')
    require(all(t in cs['sse-rule-2020-full'] for t in ('3.4.13','10%','四舍五入','0.01元人民币','4.3.2','参考价')),
            'WH_PIT_GENERAL_RULE_SOURCE_MISMATCH')
    require(all(t in cs['sse-rule-2020-delayed'] for t in ('附件3','暂缓实施条文','3.7.2','3.7.3','3.7.4','3.7.9','3.7.10','4.2.5')),
            'WH_PIT_DELAYED_SOURCE_MISMATCH')
    require(all(t in cs['sse-risk-2020-notice'] for t in ('上证发〔2020〕103号','2020-12-31','自发布之日起施行','上证发〔2020〕42号','上证发〔2020〕46号')),
            'WH_PIT_RISK_NOTICE_SOURCE_MISMATCH')
    require(all(t in cs['sse-risk-2020-full'] for t in ('5%','10%','0.1元人民币','0.05元人民币','0.01元人民币','首个交易日无价格涨跌幅限制','*ST')),
            'WH_PIT_RISK_RULE_SOURCE_MISMATCH')
    fs={f['fact_id']:f for f in facts}
    v=fs['SSE_2020_GENERAL_RULE_DATED_NOTICE']['value']
    require(v['notice_number']=='上证发〔2020〕17号' and v['rule_version']=='2020_SECOND_REVISION' and
            v['effective_date_basis']=='NOTICE_BODY_LITERAL' and v['delayed_clauses_exist'] is True and
            v['all_clauses_implemented_on_notice_date'] is False and v['end_date']=='UNKNOWN' and
            v['url_directory_date']=='2023-02-17' and v['url_directory_date_is_publication_proof'] is False,
            'WH_PIT_RULE_VERSION_DATE_AMBIGUITY')
    v=fs['SSE_2020_GENERAL_LIMIT_AND_TICK']['value']
    require(v['general_stock_limit_ratio']=='0.10' and v['a_share_tick_cny']=='0.01' and
            v['source_rounding_label']=='四舍五入' and v['per_security_applicability']=='UNKNOWN' and
            v['special_rules_and_status_override_possible'] is True and v['three_symbol_limit_backfill_permitted'] is False,
            'WH_PIT_RULE_STATUS_BACKFILL')
    v=fs['SSE_2020_FIRST_DAY_EXCEPTIONS']['value']
    require(v['rule_is_first_session_not_five_sessions'] is True and v['per_security_trigger_sessions']=='UNKNOWN' and
            v['2023_five_session_rule_backfill_permitted'] is False,'WH_PIT_FIRST_DAY_TRIGGER_AMBIGUITY')
    v=fs['SSE_2020_DELAYED_PROVISIONS']['value']
    require(type(v['delayed_rows']) is int and v['delayed_rows']==6 and
            v['clause_ids']==['3.7.2','3.7.3','3.7.4','3.7.9','3.7.10','4.2.5'] and
            v['later_implementation_dates']=='UNKNOWN' and v['future_implementation_notice_required'] is True and
            v['general_limit_clause_in_this_delayed_list'] is False and
            v['not_in_delayed_list_does_not_prove_continuous_security_applicability'] is True,
            'WH_PIT_DELAYED_CLAUSE_PROMOTION')
    v=fs['SSE_2020_EX_DIVIDEND_REFERENCE_STRUCTURE']['value']
    require(v['displayed_pre_close_on_ex_date']=='EX_REFERENCE_PRICE' and
            v['price_limit_baseline_on_ex_date']=='EX_REFERENCE_PRICE_UNLESS_OTHERWISE_SPECIFIED' and
            v['issuer_adjusted_formula_application_possible'] is True and
            v['provider_adj_factor_method_proven'] is v['dividend_cash_receipt_proven'] is
            v['raw_previous_close_equals_ex_reference'] is v['factor_plus_cash_double_count_permitted'] is False and
            v['per_security_action_chain']=='UNKNOWN','WH_PIT_PRICE_ACTION_FACTOR_CONFLATION')
    v=fs['SSE_2020_RISK_BOARD_DATED_NOTICE']['value']
    require(v['notice_number']=='上证发〔2020〕103号' and v['rule_version']=='2020_DECEMBER_REVISION' and
            v['effective_date_basis']=='NOTICE_BODY_LITERAL' and v['superseded_versions']==['2020_MAY_REVISION_42','2020_NOTICE_46'] and
            v['historical_initial_implementation_header']=='2013-01-01' and v['end_date']=='UNKNOWN' and
            v['initial_header_is_current_revision_effective_date'] is False and
            v['url_directory_date_is_publication_proof'] is False,'WH_PIT_INITIAL_REVISION_DATE_CONFLATION')
    v=fs['SSE_2020_RISK_BOARD_LIMIT_EXCEPTIONS']['value']
    for field,val in (('risk_warning_limit_ratio','0.05'),('risk_warning_a_share_low_price_threshold_cny','0.10'),
                      ('risk_warning_low_price_absolute_change_cny','0.01'),('delisting_period_limit_ratio','0.10'),
                      ('delisting_a_share_low_price_threshold_cny','0.05'),('delisting_low_price_absolute_change_cny','0.01'),
                      ('a_share_min_order_price_cny','0.01')):
        require(v[field]==val,'WH_PIT_RISK_RULE_NUMERIC_SEMANTICS')
    require(v['first_delisting_session_unlimited'] is True and v['per_security_status_or_trigger']=='UNKNOWN' and
            v['new_rule_ratio_backfill_permitted'] is False,'WH_PIT_RISK_STATUS_TRIGGER_UNPROVEN')
    v=fs['SSE_2020_RISK_BOARD_ST_MARKER_SEMANTICS']['value']
    require(v['delisting_risk_marker']=='*ST' and v['other_risk_marker']=='ST' and
            v['per_security_start_and_withdrawal_dates']==v['three_symbol_historical_ST_status']=='UNKNOWN' and
            v['present_day_name_backfill_permitted'] is False,'WH_PIT_NAME_STATUS_HISTORY_UNKNOWN')


def _validate_manifest(x):
    keys(x,('version','kind','namespace','exact_symbols','captures','new_facts','actual_public_GET_requests',
            'discovery_query_count','discovery_tool_calls','discovery_queries','discovery_refs','qa_refs','preparation_refs',
            'failed_capture_ids','failed_discovery_calls','absent_targets_not_inferred','authenticated_requests',
            'credential_lookups','redirect_followed_count','proxy_used_count','search_results_used_as_original_evidence',
            'continuous_historical_domains_closed','historical_visibility_proven','source_admission','productionGate',
            'actual_forward_days','formal_backtest_authorized','actual_capture_authorized','universe_expansion',
            'absence_means','network_stopped','predecessor_manifest_ref','predecessor_matrix_ref','predecessor_progress_ref','created_at'))
    require(x['version']=='1.0.0' and x['kind']=='WAVE_H_PUBLIC_PIT_ORIGINALS' and
            x['namespace']=='EVIDENCE_ONLY:CORE_40' and x['exact_symbols']==list(SYMBOLS),'WH_PIT_VERSION_NAMESPACE_SCOPE')
    for name,n in (('actual_public_GET_requests',6),('discovery_query_count',8),('discovery_tool_calls',3)):
        require(type(x[name]) is int and x[name]==n,'WH_PIT_NETWORK_BUDGET')
    require(len(x['captures'])==6 and len(x['discovery_queries'])==8 and len(x['discovery_refs'])==3 and
            x['network_stopped'] is True,'WH_PIT_NETWORK_BUDGET')
    for name in ('authenticated_requests','credential_lookups','redirect_followed_count','proxy_used_count',
                 'continuous_historical_domains_closed','actual_forward_days'):
        require(type(x[name]) is int and x[name]==0,'WH_PIT_SOURCE_OR_HISTORY_PROMOTION')
    for name in ('historical_visibility_proven','productionGate','formal_backtest_authorized',
                 'actual_capture_authorized','universe_expansion','search_results_used_as_original_evidence'):
        require(x[name] is False,'WH_PIT_SOURCE_OR_HISTORY_PROMOTION')
    require(x['source_admission']=='BLOCKED' and x['absence_means']=='UNKNOWN','WH_PIT_SOURCE_OR_HISTORY_PROMOTION')
    timestamp(x['created_at']);ids=set();failed=[]
    for c in x['captures']:
        keys(c,('capture_id','url','http_status','error','body_ref','capture_ref','parsed_ref','source_version',
                'retrieved_at','publication_date','publication_precision','published_at','available_at',
                'historical_visibility_proven','observed_at_the_time','url_directory_date_is_publication_proof','status'))
        cid=c['capture_id'];require(cid in CAPTURE_URLS and cid not in ids,'WH_PIT_CAPTURE_IDENTITIES');ids.add(cid)
        u=urlsplit(c['url'])
        require(c['url']==CAPTURE_URLS[cid] and u.scheme=='https' and u.hostname=='www.sse.com.cn' and
                not u.query and not u.username and not u.password,'WH_PIT_FROZEN_OFFICIAL_URL_ONLY')
        for field,suffix in (('body_ref','.response'),('capture_ref','.capture.json'),('parsed_ref','.txt')):
            require(c[field]['path']==str(PUBLIC/(cid+suffix)),'WH_PIT_CAPTURE_ORIGINAL_IDENTITY')
        raw=_ref(c['body_ref']);cap=_json(_ref(c['capture_ref']));_ref(c['parsed_ref'])
        require(c['source_version']==cap['sha256']==sha(raw) and c['url']==cap['url'] and
                c['retrieved_at']==cap['retrieved_at'] and c['http_status']==cap['http_status'] and
                c['error']==cap['error'] and type(cap['bytes']) is int and cap['bytes']==len(raw),'WH_PIT_RAW_CAPTURE_BINDING')
        require(timestamp(cap['request_started_at'])<=timestamp(cap['retrieved_at']),'WH_PIT_CURRENT_CLOCK_ORDER')
        require(cap['published_at'] is cap['available_at'] is c['published_at'] is c['available_at'] is None and
                c['historical_visibility_proven'] is c['observed_at_the_time'] is
                c['url_directory_date_is_publication_proof'] is False,'WH_PIT_DATE_ONLY_NOT_FIRST_VISIBLE')
        require(all(cap[f] is False for f in ('auth_used','credentials_attached','cookies_attached','redirect_followed','proxy_used')),
                'WH_PIT_CREDENTIAL_REDIRECT_PROXY_FORBIDDEN')
        _day(c['publication_date'])
        require(c['publication_precision']==('DATE_ONLY' if c['publication_date'] else 'UNKNOWN'),'WH_PIT_PUBLICATION_PRECISION')
        if c['http_status']!=200 or c['error'] is not None:
            failed.append(cid);require(c['status']=='FAILED_ORIGINAL_NOT_ADMITTED','WH_PIT_FAILED_ORIGINAL_PROMOTED')
        else:
            require(c['status']=='CURRENTLY_RETRIEVED_OFFICIAL_ORIGINAL','WH_PIT_CAPTURE_LABEL')
            if cid in ('sse-rule-2020-full','sse-rule-2020-delayed'):require(raw.startswith(b'PK'),'WH_PIT_DOCX_SIGNATURE')
            if cid=='sse-risk-2020-full':require(raw.startswith(bytes.fromhex('d0cf11e0a1b11ae1')),'WH_PIT_DOC_SIGNATURE')
    require(ids==set(CAPTURE_URLS) and sorted(failed)==sorted(x['failed_capture_ids']),'WH_PIT_FAILED_ORIGINAL_PRESERVATION')
    fact_ids=set()
    for f in x['new_facts']:
        keys(f,('fact_id','domain','symbols','scope','publication_date','publication_precision','effective_date',
                'effective_precision','historical_available_at','observed_at_the_time','historical_visibility_proven',
                'actual_session_proven','can_trade','evidence_capture_ids','value','interpretation'))
        fid=f['fact_id'];require(fid in FACT_DATES and fid not in fact_ids,'WH_PIT_FACT_IDENTITIES');fact_ids.add(fid)
        require(f['domain'] in DOMAINS and f['symbols']==list(SYMBOLS) and
                f['scope']=='EXCHANGE_RULE_STRUCTURE_NOT_SECURITY_HISTORY','WH_PIT_FACT_SCOPE')
        require((f['publication_date'],f['effective_date'])==FACT_DATES[fid],'WH_PIT_EFFECTIVE_DATE_SOURCE')
        _day(f['publication_date']);_day(f['effective_date'])
        require(f['publication_precision']==('DATE_ONLY' if f['publication_date'] else 'UNKNOWN') and
                f['effective_precision']==('DATE_ONLY' if f['effective_date'] else 'UNKNOWN'),'WH_PIT_FACT_DATE_PRECISION')
        require(f['historical_available_at'] is None and all(f[n] is False for n in
                ('observed_at_the_time','historical_visibility_proven','actual_session_proven','can_trade')) and
                f['interpretation']=='STRUCTURAL_FACT_CURRENTLY_RETRIEVED_NOT_OBSERVED_AT_TIME','WH_PIT_FACT_PROMOTION')
        require(f['evidence_capture_ids'] and len(f['evidence_capture_ids'])==len(set(f['evidence_capture_ids'])) and
                all(cid in ids and cid not in failed for cid in f['evidence_capture_ids']),'WH_PIT_FACT_FAILED_OR_MISSING_ORIGINAL')
    require(fact_ids==set(FACT_DATES),'WH_PIT_FACT_IDENTITIES')
    _semantics(x['captures'],x['new_facts'])
    require(x['failed_discovery_calls']==['discovery-G1-3_EMPTY_SEARCH_RESULTS'] and
            x['absent_targets_not_inferred']==['JINGWANG_2024_PRIMARY_IMPLEMENTATION_NOTICE',
                '2023_FIRST_REGISTERED_MAINBOARD_IPO_EFFECTIVE_TRIGGER_SESSION','2026_ST_LATER_EFFECTIVE_VERSION_ORIGINAL'],
            'WH_PIT_ABSENCE_OR_DISCOVERY_FAILURE_PRESERVATION')
    for field in ('discovery_refs','qa_refs','preparation_refs'):
        for r in x[field]:_ref(r)
    for field,path in (('predecessor_manifest_ref',prior.EVIDENCE_PATH),
                       ('predecessor_matrix_ref',PREDECESSOR_GIT[0]),('predecessor_progress_ref',PREDECESSOR_GIT[1])):
        require(x[field]['path']==str(path),'WH_PIT_PREDECESSOR_REFERENCE_ONLY');_ref(x[field])
    require(x['predecessor_manifest_ref']['sha256']==prior.EVIDENCE_HASH,'WH_PIT_PREDECESSOR_MANIFEST_VERSION')
    return deepcopy(x)


def evidence():
    r={'path':str(EVIDENCE_PATH),'sha256':EVIDENCE_HASH,'bytes':23356}
    return _validate_manifest(_json(_ref(r)))


def source_pins():
    x=evidence();refs=prior.source_pins()+[ref(EVIDENCE_PATH),x['predecessor_matrix_ref'],x['predecessor_progress_ref']]
    for c in x['captures']:refs.extend([c['body_ref'],c['capture_ref'],c['parsed_ref']])
    for field in ('discovery_refs','qa_refs','preparation_refs'):refs.extend(x[field])
    by={}
    for r in refs:
        require(r['path'] not in by or by[r['path']]==r,'WH_PIT_DEPENDENCY_CONFLICT');by[r['path']]=r
    return [deepcopy(by[p]) for p in sorted(by)]


def evidence_matrix():
    x=evidence();old=_json(_ref(x['predecessor_matrix_ref']))
    require(old['body']['symbols']==list(SYMBOLS) and old['body']['continuous_historical_domains_closed']==0,
            'WH_PIT_PREDECESSOR_DOMAIN_PROMOTION')
    prior.evidence()
    rows=deepcopy(old['body']['rows'])
    for row in rows:
        require(row['symbol'] in SYMBOLS and row['historical_visibility_proven'] is False,'WH_PIT_PRIOR_ROW_PROMOTION')
        for d in row['domains']:
            require(d['covered_intervals']==[] and d['absence_means']=='UNKNOWN' and d['can_trade'] is False,
                    'WH_PIT_PRIOR_HISTORY_PROMOTION')
            new=[deepcopy(f) for f in x['new_facts'] if f['domain']==d['domain']]
            d['wave_h_new_facts']=new
            d['predecessor_reason_codes_preserved']=True
            if new:
                d['independent_structural_evidence']='SOURCE_BOUND_PARTIAL_2020_RULE_ORIGINALS_ADDED'
                d['reason_codes']+=['DATED_RULE_STRUCTURE_NOT_CONTINUOUS_APPLICABLE_INTERVAL',
                                    'PER_SECURITY_STATUS_AND_TRIGGER_HISTORY_UNKNOWN',
                                    'CURRENT_RETRIEVAL_NOT_HISTORICAL_FIRST_VISIBILITY']
            if d['domain']!='listing_anchor':d['historical_coverage']='UNKNOWN'
        row['wave_h_interpretation']='EXCHANGE_RULE_STRUCTURE_ADDED_NO_SECURITY_HISTORY_BACKFILL'
    return metadata('HISTORICAL_PIT_EVIDENCE_MATRIX',{
        'symbols':list(SYMBOLS),'rows':rows,'wave_h_new_structural_facts':x['new_facts'],
        'wave_h_manifest_ref':ref(EVIDENCE_PATH),'predecessor_matrix_ref':x['predecessor_matrix_ref'],
        'direct_source_refs':source_pins(),'source_dependency_hash':digest(source_pins()),
        'new_official_original_GET_count':6,'new_structural_fact_count':8,'failed_capture_ids':x['failed_capture_ids'],
        'failed_discovery_calls':x['failed_discovery_calls'],'absent_targets_not_inferred':x['absent_targets_not_inferred'],
        'preserved_predecessor_failed_capture_ids':old['body']['preserved_predecessor_failed_capture_ids'],
        'continuous_historical_domains_closed':0,'historical_available_at':None,'observed_at_the_time':False,
        'formal_price_backtest':'BLOCKED','formal_fundamental_pit_backtest':'BLOCKED',
        'provider_license_transport':'BLOCKED_INDEPENDENT_GATE','absence_means':'UNKNOWN','safe_to_trade':False,
        'rule_dates_and_ratios_are_evidence_not_default_runtime_parameters':True})


def progress():
    m=evidence_matrix();x=evidence()
    blockers=[{'symbol':r['symbol'],'domain':d['domain'],'reason_codes':d['reason_codes']}
              for r in m['body']['rows'] for d in r['domains'] if d['domain']!='listing_anchor']
    return metadata('HISTORICAL_PIT_PROGRESS',{
        'symbols':list(SYMBOLS),'matrix_hash':m['content_hash'],'state':'PARTIAL_2020_RULE_STRUCTURE_HISTORY_BLOCKED',
        'new_official_GET_requests':6,'discovery_query_count':8,'discovery_tool_calls':3,
        'authenticated_requests':0,'credential_lookups':0,'redirect_followed_count':0,'proxy_used_count':0,
        'new_structural_fact_count':8,'continuous_historical_domains_closed':0,
        'remaining_domain_blockers':blockers,'new_source_failures':x['failed_capture_ids'],
        'failed_discovery_calls':x['failed_discovery_calls'],'missing_targets':x['absent_targets_not_inferred'],
        'formal_price_backtest_ready':False,'formal_fundamental_pit_ready':False,
        'source_admission':'BLOCKED','safe_to_trade':False,'network_stopped':True,
        'separate_current_forward_capability_does_not_close_history':True,
        'separate_blockers':['PROVIDER_LICENSE_TRANSPORT_UNVERIFIED','RAW_BARS_CURRENT_RETRIEVED_NOT_OBSERVED_AT_TIME',
            'UNBROKEN_RULE_VERSION_AND_ACTUAL_EFFECTIVE_TRIGGER_HISTORY_MISSING',
            'PER_SECURITY_LISTING_ST_NAME_SUSPENSION_ACTION_EXCEPTION_HISTORY_INCOMPLETE',
            'EXCHANGE_ACTUAL_SESSION_AND_HISTORICAL_UNIVERSE_HISTORY_UNKNOWN',
            'FINANCIAL_FIRST_VISIBILITY_AND_REVISION_ORIGINALS_UNPROVEN',
            'ADJUSTMENT_METHOD_AND_VERSION_NOT_PROVEN_BY_EX_REFERENCE_RULE',
            'DATED_COSTS_BENCHMARK_AND_SEPARATE_HUMAN_FORMAL_AUTHORIZATION_MISSING']})


def planned_calendar_day(day):
    return prior.planned_calendar_day(day)


def run_formal(*args,**kwargs):
    blocked('WH_FORMAL_HISTORICAL_PIT_NOT_ADMITTED')
