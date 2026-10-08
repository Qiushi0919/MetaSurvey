"""New bounded official originals; no continuous PIT closure or runtime network.

Eight credential-free GETs yielded four dated issuer PDFs and four SSE calendar
pages. A-share dividend cash and ex-reference amounts are distinct. Report-period
name/unit anchors, later implementation claims, and no-correction statements are
partial structural facts only. Date-only publication and present retrieval never
become historical availability. All failures and reused originals are pinned.
"""
from copy import deepcopy
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
import json

from .common import ARCHIVE, ROOT, SYMBOLS, require, canonical, sha, digest, checked_file, metadata, timestamp, unavailable, locate_reference
from wave_f.pit import DOMAINS, REQUIRED_PRICE_DOMAINS

EVIDENCE_PATH=ARCHIVE/'public/pit/evidence-G3.json'
EVIDENCE_HASH='sha256:76fc78400d3f251b45f1e31f07b9c01d8bddc076546e36b32c625fb469650f9d'
ALLOWED_HOSTS=('www.sse.com.cn','big5.sse.com.cn','www1.hkexnews.hk')
PRESERVED_REFS=(
 ('validation/pit/module-G1-failed.py','sha256:ef8afafde768ebee9660d6217859a1b553ec2327374c380066a632cb996d8cf3',14470),
 ('validation/pit/module-G1-failure.txt','sha256:0e9f7b3d4d401ff40769aab29368110f452b2ef22f1f3df7d5e4803e8ffd7dab',323),
 ('validation/pit/metadata-G1-failure.json','sha256:32edb6627d9730857fc06b70969264717cf7e33b96506c2c61759cd336f0156c',536),
 ('validation/pit/metadata-G2-failure.json','sha256:e868674a643508a4cf51ad247e3241377aa0b7c2725468f7df0e2b659081536f',494),
 ('validation/pit/runtime-discovery-G0-failure.txt','sha256:e7755d8bb19d9b21f8ce410602821d5d14210bda237712178c806eccab9c8b2d',341),
 ('validation/pit/pdf-QA-warning-G1.txt','sha256:e3ce9c1dcb65594b015bb2ec4897376b844bbaa356ee2202b850033483bacb95',249),
 ('public/pit/evidence-G1.json','sha256:694ee17853aa5001f34fd1d65a24c851ec3cdd12484d15bdc4809982772c639e',36993),
 ('public/pit/evidence-G2.json','sha256:1f8ec8d4dce59f98bdde191b947be65c6c30b7afc7f99f36952930317442be37',37167),
)


def preserved_refs():
    return [{'path':str(ARCHIVE/p),'sha256':h,'bytes':n} for p,h,n in PRESERVED_REFS]


def _ref(r,private=True):
    require(type(r) is dict and set(r)=={'path','sha256','bytes'},'WG_PIT_REF_SHAPE')
    p=Path(r['path'])
    if private:
        require(p.is_relative_to(ARCHIVE.parent) and p.stat().st_mode&0o777==0o600,'WG_PIT_PRIVATE_REF')
    else:
        # Keep frozen reference identities; validate bytes in the calling checkout.
        p=locate_reference(p)
        require(p in (ROOT/'docs/wave-f/Historical-PIT-Three-Symbol-Matrix.json',
                      ROOT/'docs/wave-f/Price-Backtest-Minimum-PIT-Gate.json'),'WG_PIT_PREDECESSOR_PATH')
    b=checked_file(p,r['sha256'])
    require(type(r['bytes']) is int and r['bytes']==len(b),'WG_PIT_REF_BYTES')
    return b


def _validate_manifest(x):
    canonical(x)
    require(x['exact_symbols']==list(SYMBOLS),'WG_PIT_EXACT_SYMBOLS')
    require(x['actual_public_GET_requests']==len(x['captures'])<=16 and
            x['discovery_query_count']==len(x['discovery_queries'])<=12 and
            x['discovery_tool_calls']==len(x['discovery_refs'])<=4,'WG_PIT_NETWORK_BUDGET')
    require(x['authenticated_requests']==x['credential_lookups']==x['redirect_followed_count']==0 and
            x['search_results_used_as_original_evidence'] is False,'WG_PIT_SOURCE_SCOPE')
    require(x['historical_visibility_proven'] is x['productionGate'] is x['live_authority'] is
            x['formal_backtest_authorized'] is False and x['source_admission']=='BLOCKED' and
            x['actual_forward_days']==x['continuous_historical_domains_closed']==0,'WG_PIT_PROMOTION')
    ids=[c['capture_id'] for c in x['captures']]
    require(len(ids)==len(set(ids)),'WG_PIT_DUPLICATE_CAPTURE')
    failures=[]
    for c in x['captures']:
        u=urlsplit(c['url'])
        require(u.scheme=='https' and u.hostname in ALLOWED_HOSTS and not u.username and not u.password,
                'WG_PIT_HOST_SCOPE')
        body=_ref(c['body_ref']);cap=json.loads(_ref(c['capture_ref']));_ref(c['parsed_ref'])
        require(c['source_version']==sha(body)==cap['sha256'] and
                c['url']==cap['url'] and c['http_status']==cap['http_status'] and
                c['retrieved_at']==cap['retrieved_at'] and cap['bytes']==len(body), 'WG_PIT_CAPTURE_BINDING')
        require(timestamp(cap['request_started_at'])<=timestamp(cap['retrieved_at']),'WG_PIT_CAPTURE_CLOCK_ORDER')
        require(c['available_at'] is c['published_at'] is cap['available_at'] is cap['published_at'] is None and
                c['credentials_attached'] is c['redirect_followed'] is cap['auth_used'] is
                cap['credentials_attached'] is cap['cookies_attached'] is cap['redirect_followed'] is False and
                c['historical_visibility_proven'] is False and c['path_date_is_publication_proof'] is False,
                'WG_PIT_CAPTURE_CLOCK_PROMOTION')
        require(c['pdf_signature'] is body.startswith(b'%PDF'),'WG_PIT_PDF_SIGNATURE')
        require(c['publication_precision']==('DATE_ONLY' if c['publication_date'] else 'UNKNOWN'),
                'WG_PIT_PUBLICATION_PRECISION')
        if c['http_status']!=200 or c['error'] is not None:failures.append(c['capture_id'])
    require(sorted(failures)==sorted(x['failed_capture_ids']),'WG_PIT_FAILURE_PRESERVATION')
    fact_ids=set()
    for f in x['new_facts']:
        require(f['fact_id'] not in fact_ids,'WG_PIT_DUPLICATE_FACT');fact_ids.add(f['fact_id'])
        require(f['domain'] in DOMAINS and (f.get('symbol') in SYMBOLS or f.get('symbols')==list(SYMBOLS)),
                'WG_PIT_FACT_SCOPE')
        require(f['historical_available_at'] is None and
                f['observed_at_the_time'] is f['historical_visibility_proven'] is f['can_trade'] is False and
                f['interpretation']=='STRUCTURAL_FACT_CURRENTLY_RETRIEVED_NOT_OBSERVED_AT_TIME',
                'WG_PIT_FACT_CLOCK_PROMOTION')
        require(f['publication_precision']==('DATE_ONLY' if f['publication_date'] else 'UNKNOWN') and
                f['effective_precision']==('DATE_ONLY' if f['effective_date'] else 'UNKNOWN'),
                'WG_PIT_FACT_DATE_PRECISION')
        require(f['evidence_capture_ids'] or f['evidence_refs'],'WG_PIT_FACT_WITHOUT_ORIGINAL')
        require(all(cid in ids for cid in f['evidence_capture_ids']),'WG_PIT_FACT_CAPTURE_MISSING')
        for r in f['evidence_refs']:_ref(r)
        if f.get('symbol')==SYMBOLS[2]:
            require(f.get('issuer_name')=='深圳市景旺电子股份有限公司' and f['fact_id'].startswith('JINGWANG_'),
                    'WG_PIT_ISSUER_LABEL')
    for field in ('reused_direct_refs','discovery_refs','capture_epoch_refs','qa_refs'):
        for r in x[field]:_ref(r)
    for field in ('predecessor_matrix_ref','predecessor_price_gate_ref'):_ref(x[field],False)
    for r in preserved_refs():_ref(r)
    require(sorted(x['predecessor_failed_capture_ids'])==['action-603228','financial-600312','financial-600312-www'],
            'WG_PIT_PREDECESSOR_FAILURES')
    # Exact source text confirms the material semantic distinction and source labels.
    cs={c['capture_id']:c for c in x['captures']}
    action=_ref(cs['action-603993-2025']['parsed_ref']).decode()
    require(all(s in action for s in ('0.255','0.2535','2025/6/26','2025/6/27','2025-038')),
            'WG_PIT_CMOC_SOURCE_SEMANTICS')
    jingwang=_ref(cs['action-603228-2025']['parsed_ref']).decode()
    require('2025-071' in jingwang and '景旺' in jingwang,'WG_PIT_JINGWANG_SOURCE_HEADER')
    af=next(f for f in x['new_facts'] if f['fact_id']=='JINGWANG_2024_ACTION_RETROSPECTIVE_CLAIM')
    require(af['value']['announcement_number']=='2025-071' and
            af['value']['primary_implementation_notice_captured'] is False,'WG_PIT_ACTION_CLAIM_SCOPE')
    cf=next(f for f in x['new_facts'] if f['fact_id']=='CMOC_2024_DIFFERENTIAL_EX_REFERENCE')
    require(cf['value']['gross_cash_cny_per_share']=='0.255' and
            cf['value']['ex_reference_cash_cny_per_share']=='0.2535' and
            cf['value']['factor_plus_cash_double_count_permitted'] is False,'WG_PIT_CASH_FACTOR_CONFLATION')
    cal=next(f for f in x['new_facts'] if f['fact_id']=='SSE_2026_OCT8_PLANNED_REOPEN_VERIFIED')
    raw=_ref(x['reused_calendar']['decoded_ref']).decode()
    require('2026-09-17' in raw and '2026年9月17日' in raw and '10月8日' in raw and
            cal['publication_date']=='2026-09-17' and cal['value']['url_directory_date']=='2026-09-15' and
            cal['value']['actual_open_or_eod_proven'] is False and
            cal['value']['generation_time_is_publication_or_availability_proof'] is False,
            'WG_PIT_CALENDAR_CLOCK_CONFLATION')
    return deepcopy(x)


def evidence():
    require(EVIDENCE_PATH.stat().st_mode&0o777==0o600,'WG_PIT_PRIVATE_MANIFEST')
    return _validate_manifest(json.loads(checked_file(EVIDENCE_PATH,EVIDENCE_HASH)))


def source_pins():
    x=evidence()
    refs=[{'path':str(EVIDENCE_PATH),'sha256':EVIDENCE_HASH,'bytes':len(checked_file(EVIDENCE_PATH,EVIDENCE_HASH))},
          x['predecessor_matrix_ref'],x['predecessor_price_gate_ref']]+preserved_refs()
    for c in x['captures']:refs += [c['body_ref'],c['capture_ref'],c['parsed_ref']]
    for field in ('reused_direct_refs','discovery_refs','capture_epoch_refs','qa_refs'):refs+=x[field]
    by={r['path']:r for r in refs}
    return [deepcopy(by[p]) for p in sorted(by)]


def evidence_refs():
    return [r for r in source_pins() if Path(r['path']).is_relative_to(ARCHIVE)]


def evidence_matrix():
    x=evidence();prior=json.loads(_ref(x['predecessor_matrix_ref'],False))['body']
    require(prior['symbols']==list(SYMBOLS) and prior['closed_formal_historical_domains']==0,
            'WG_PIT_PREDECESSOR_PROMOTION')
    rows=deepcopy(prior['rows'])
    for row in rows:
        for d in row['domains']:
            new=[deepcopy(f) for f in x['new_facts'] if f['domain']==d['domain'] and
                 (f.get('symbol')==row['symbol'] or row['symbol'] in f.get('symbols',[]))]
            d['wave_g_new_facts']=new
            require(d['absence_means']=='UNKNOWN' and d['can_trade'] is False and
                    d['covered_intervals']==[],'WG_PIT_PREDECESSOR_STATUS_PROMOTION')
            if new:
                d['independent_structural_evidence']='SOURCE_BOUND_PARTIAL_WITH_NEW_OFFICIAL_ORIGINALS_OR_DATED_REUSED_CALENDAR'
                d['reason_codes']+=['SINGLE_DOCUMENT_OR_CLAIM_NOT_CONTINUOUS_HISTORY',
                                    'DATE_ONLY_PUBLICATION_NOT_HISTORICAL_AVAILABILITY_INSTANT']
            if d['domain']!='listing_anchor':d['historical_coverage']='UNKNOWN'
        row['wave_g_interpretation']='PARTIAL_STRUCTURAL_FACTS_NOT_HISTORICAL_AVAILABILITY_RECONSTRUCTION'
    return metadata('HISTORICAL_PIT_EVIDENCE_MATRIX',{
        'symbols':list(SYMBOLS),'rows':rows,'new_structural_facts':x['new_facts'],
        'manifest_ref':{'path':str(EVIDENCE_PATH),'sha256':EVIDENCE_HASH},
        'direct_source_refs':source_pins(),'source_dependency_hash':digest(source_pins()),
        'new_official_original_GET_count':x['actual_public_GET_requests'],
        'failed_capture_ids':x['failed_capture_ids'],'preserved_predecessor_failed_capture_ids':x['predecessor_failed_capture_ids'],
        'preserved_preparation_failure_refs':preserved_refs(),
        'continuous_historical_domains_closed':0,'historical_available_at':None,'observed_at_the_time':False,
        'formal_price_backtest':'BLOCKED','formal_fundamental_pit_backtest':'BLOCKED',
        'provider_license_transport':'BLOCKED_INDEPENDENT_GATE','absence_means':'UNKNOWN','safe_to_trade':False})


def pit_progress():
    m=evidence_matrix();x=evidence()
    blockers=[{'symbol':r['symbol'],'domain':d['domain'],'reason_codes':d['reason_codes']}
              for r in m['body']['rows'] for d in r['domains'] if d['domain']!='listing_anchor']
    return metadata('HISTORICAL_PIT_PROGRESS',{
        'symbols':list(SYMBOLS),'matrix_hash':m['content_hash'],'state':'PARTIAL_STRUCTURAL_ADVANCE_HISTORY_BLOCKED',
        'new_official_GET_requests':x['actual_public_GET_requests'],'discovery_query_count':x['discovery_query_count'],
        'discovery_tool_calls':x['discovery_tool_calls'],'authenticated_requests':0,'credential_lookups':0,
        'redirect_followed_count':0,'new_structural_fact_count':len(x['new_facts']),
        'continuous_historical_domains_closed':0,'remaining_domain_blockers':blockers,
        'oct8_planned_resume_verified':True,'oct8_actual_session_or_eod_verified':False,
        'new_source_failures':x['failed_capture_ids'],'preserved_predecessor_source_failures':x['predecessor_failed_capture_ids'],
        'preserved_preparation_failure_refs':preserved_refs(),'formal_price_backtest_ready':False,
        'formal_fundamental_pit_ready':False,'source_admission':'BLOCKED','safe_to_trade':False,
        'separate_blockers':['PROVIDER_LICENSE_TRANSPORT_UNVERIFIED','RAW_BARS_CURRENT_RETRIEVED_NOT_OBSERVED_AT_TIME',
                             'FIVE_YEAR_SECURITY_STATUS_ACTION_EXCEPTION_HISTORY_INCOMPLETE',
                             'FINANCIAL_FIRST_VISIBILITY_AND_REVISION_ORIGINALS_UNPROVEN',
                             'INDUSTRY_AND_HISTORICAL_UNIVERSE_COMPLETENESS_UNKNOWN',
                             'DATED_COSTS_BENCHMARK_AND_SEPARATE_HUMAN_FORMAL_AUTHORIZATION_MISSING']})


def planned_calendar_day(day):
    """A descriptive public schedule lookup; actual session/status always UNKNOWN."""
    require(type(day) is str,'WG_PIT_DATE_REQUIRED')
    try:q=date.fromisoformat(day)
    except ValueError:raise ValueError('WG_PIT_DATE_REQUIRED') from None
    require(day==q.isoformat() and q.year in (2025,2026),'WG_PIT_PLANNED_YEAR_SCOPE')
    x=evidence();f=next(f for f in x['new_facts'] if f['fact_id']=='SSE_PLANNED_HOLIDAYS_'+str(q.year))
    closures=f['value']['announced_holiday_closures_inclusive']
    status='PLANNED_OPEN'
    if q.weekday()>=5:status='WEEKEND_CLOSED'
    if any(a<=day<=b for a,b in closures):status='HOLIDAY_CLOSED'
    return metadata('DESCRIPTIVE_PLANNED_CALENDAR_DAY',{'date':day,'planned_status':status,
                    'schedule_fact_id':f['fact_id'],'actual_session':'UNKNOWN','eod_complete':'UNKNOWN',
                    'historical_available_at':None,'safe_to_trade':False,'status_history':'UNKNOWN'})


def select_history(records,symbol,effective_at,cutoff,mode):
    """Strict pure synthetic fixture selector reused; no actual authority."""
    from post_wave_e.pit import select_tradeability
    return select_tradeability(records,symbol,effective_at,cutoff,mode)


def select_financial_fixture(records,symbol,period,cutoff,mode):
    from post_wave_e.pit import select_financial
    return select_financial(records,symbol,period,cutoff,mode)


def run_formal(*args,**kwargs):
    unavailable()
