"""Read original evidence before considering any formal backtest invocation.

Current vendor history is an audit input, never a historically visible record.
Audit inventories and decision payloads are intentionally separate artifacts.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from copy import deepcopy
from datetime import date,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dual_track.common import SYMBOLS,canonical,closed,instant,now,ref,reopen,require,sha,write_new
from dual_track.pit import PIN
from wave_g.diagnostic import _read_inputs,_group
from wave_h.forward import _json

ROOT=Path(__file__).resolve().parents[1]
UNSET='UNSET_REQUIRED'
NAMESPACE='HISTORICAL_PIT_PREPARATION:CORE_40'
SPEC_HASH='sha256:d4eb866d6675e52f4b5158374f94a3152e4ae406c62add22a8c807762b0215da'
APIS={'daily':'PRICE','trade_cal':'CALENDAR','stock_basic':'STATUS',
      'dividend':'ACTION','adj_factor':'ACTION'}


def frozen_spec():
    p=ROOT/'docs/wave-f/Frozen-StrategySpec-v1.json'
    r=ref(p);require(r['sha256']==SPEC_HASH,'HP_STRATEGY_CHANGED_STOP')
    return _json(reopen(r)),r


def cutoff_for(session,time_policy):
    require(type(session) is str and date.fromisoformat(session).isoformat()==session,'HP_DATE')
    if time_policy==UNSET:return None
    require(type(time_policy) is str and re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?',time_policy),
            'HP_CUTOFF_EXPLICIT_LOCAL_TIME_REQUIRED')
    return instant(session+'T'+time_policy+('' if len(time_policy)==8 else ':00')+'+08:00').isoformat()


def read_current_originals():
    """Real read-only adapter, expressly QUARANTINED, no actual admission path."""
    inputs,originals=_read_inputs()
    by_hash={}
    for r in originals:
        reopen(r);by_hash.setdefault(r['sha256'],[]).append(r)
    inventory=[];dates={};counts={}
    for symbol in SYMBOLS:
        observations=inputs[symbol]['wave-d_input']['body']['observations']
        prices=[{**deepcopy(o['values']),'source_ref':deepcopy(o['source_ref'])}
                for o in observations if o['api_name']=='daily']
        unique,conflicts,duplicates=_group(prices,symbol=symbol)
        require(not conflicts and len(unique)==327,'HP_REFERENCE_PRICE_DRIFT_STOP')
        dates[symbol]=sorted(d[:4]+'-'+d[4:6]+'-'+d[6:] for d in unique)
        counts[symbol]={'distinct_observed_bar_dates':len(unique),
                        'identical_duplicate_dates':len(duplicates),
                        'first':dates[symbol][0],'last':dates[symbol][-1]}
        for o in observations:
            if o['api_name'] not in APIS:continue
            source=o['source_ref'];h=source['raw_sha256']
            refs=by_hash.get(h,[]);require(bool(refs),'HP_RAW_HASH_UNBOUND_STOP')
            matching=[]
            for rr in refs:
                raw=_json(reopen(rr),True)
                if type(raw) is dict and type(raw.get('data')) is dict and 'items' in raw['data']:
                    data=raw['data'];idx=source['row_ordinal']
                    if 0<=idx<len(data['items']):
                        row=dict(zip(data['fields'],data['items'][idx]))
                        normal={k:None if v is None else str(v) for k,v in row.items()}
                        expected={k:None if v is None else str(v) for k,v in o['values'].items()}
                        if normal==expected:matching.append(rr)
            require(bool(matching),'HP_RAW_ROW_CHANGED_STOP')
            inventory.append({'symbol':symbol,'domain_group':APIS[o['api_name']],
                'actual_API':o['api_name'],'request_id':source['request_id'],
                'request_fingerprint':source['request_fingerprint'],'row_ordinal':source['row_ordinal'],
                'raw_original_refs':matching,'raw_sha256':h,
                'event_time':source.get('event_time'),'event_date':o['values'].get('trade_date',o['values'].get('ex_date')),
                'event_precision':'DATE_ONLY_OR_UNRECORDED','published_at':source.get('published_at'),
                'current_available_at':source.get('available_at'),'retrieved_at':source['retrieved_at'],
                'historical_available_at':None,'first_visible_at':None,'revision_id':UNSET,
                'source_version':h,'source_version_semantics':'CAPTURED_CONTENT_HASH_NOT_VENDOR_REVISION_ID',
                'revision_chain':'NOT_PROVEN','source_admission':'QUARANTINED',
                'provider_license_transport':'BLOCKED','historical_visibility_proven':False,
                'units':'SOURCE_DECLARED_UNITS_NOT_INDEPENDENTLY_ADMITTED',
                'values':deepcopy(o['values']),
                'reason_codes':['CURRENT_RETRIEVAL_NOT_HISTORICAL_VISIBILITY','FIRST_VISIBLE_AND_REVISION_CHAIN_UNPROVEN']})
    return inventory,dates,counts,originals


def candidate_snapshot(symbol,session,cutoff,inventory,mode='OBSERVED_AT_TIME'):
    """Actual decision payload contains no IDs/counts/hash from unseen audit rows.

    No actual first-visible issuer exists. Caller-supplied flags cannot upgrade
    this quarantine adapter. Any positive selection belongs to old synthetic
    selector tests, never this actual research entry.
    """
    require(symbol in SYMBOLS and mode in ('OBSERVED_AT_TIME','HISTORICAL_AVAILABILITY_RECONSTRUCTION'),
            'HP_NAMESPACE_OR_MODE')
    require(date.fromisoformat(session).isoformat()==session,'HP_DATE')
    if cutoff is not None:
        cutoff_in_shanghai=instant(cutoff).astimezone(ZoneInfo('Asia/Shanghai'))
        require(cutoff_in_shanghai.date().isoformat()==session,
                'HP_CUTOFF_SESSION')
        cutoff=cutoff_in_shanghai.isoformat()
    # Deliberately do not hash, count or inspect any future/unknown audit body.
    # Current rows cannot prove first visibility, including forged provenance.
    payload={'version':'1.0.0','kind':'HistoricalPITCandidateSnapshot','namespace':NAMESPACE,
        'symbol':symbol,'logical_session_date':session,'decision_time':cutoff,
        'cutoff_state':UNSET if cutoff is None else 'EXPLICIT_TIME_INPUT_NOT_OWNER_ATTESTATION',
        'mode':mode,'decision':'NO_DECISION','visible_records':[],
        'visible_records_hash':sha(canonical([])),
        'domains':{k:'UNKNOWN' for k in ('PRICE','CALENDAR','STATUS','ACTION')},
        'reason_codes':['DECISION_CUTOFF_UNSET_REQUIRED' if cutoff is None else 'INDEPENDENT_HISTORICAL_PROOF_NOT_ADMITTED',
                        'CURRENT_LATEST_BACKFILL_FORBIDDEN'],
        'historical_visibility_proven':False,'formal_admission':'BLOCKED',
        'observed_at_the_time':False,'productionGate':False,'safe_to_trade':False}
    payload['snapshot_sha256']=sha(canonical(payload))
    return payload


def verify_candidate(payload):
    """Check semantic hash and the exact blocked contract; cannot grant admission."""
    require(type(payload) is dict,'HP_CANDIDATE_TYPE')
    expected=candidate_snapshot(payload.get('symbol'),payload.get('logical_session_date'),
                                payload.get('decision_time'),[],payload.get('mode'))
    require(payload==expected,'HP_CANDIDATE_SEMANTIC_HASH_OR_SCOPE_CHANGED_STOP')
    return True


def calendar_structure(manifest_ref):
    """Only dated planned holiday intervals; not actual open/exception proof."""
    manifest=_json(reopen(manifest_ref));captures=manifest['captures']
    require([c['year'] for c in captures]==list(range(2021,2027)),'HP_CALENDAR_YEAR_SET')
    rows=[]
    # Date expressions retain literal year/month/day precision, never midnight.
    date_expr=r'(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日(?:（[^）]*）)?'
    pattern=re.compile(date_expr+r'(?:\s*至\s*'+date_expr+r')?\s*休市')
    for cap in captures:
        raw=reopen(cap['response_ref']);txt=reopen(cap['parsed_text_ref']).decode()
        require(sha(raw)==cap['source_version'] and cap['http_status']==200 and cap['title_date_content_match'] is True,
                'HP_CALENDAR_ORIGINAL_CHANGED_STOP')
        require(cap['available_at'] is None and cap['published_at'] is None and cap['first_visible_at'] is None and
                cap['historical_visibility_proven'] is False,'HP_CALENDAR_CLOCK_PROMOTION')
        intervals=[]
        for m in pattern.finditer(txt):
            a,b,c,d,e,f=m.groups();start=date(int(a or cap['year']),int(b),int(c))
            end=date(int(d or cap['year']),int(e),int(f)) if e else start
            require(start<=end and (end-start).days<=15,'HP_CALENDAR_RANGE')
            intervals.append({'start_date':start.isoformat(),'end_date':end.isoformat(),
                              'literal':m.group(0),'precision':'DATE_ONLY'})
        require(6<=len(intervals)<=8,'HP_CALENDAR_HOLIDAY_PARSE_COUNT')
        rows.append({'year':cap['year'],'holiday_intervals':intervals,'source_url':cap['url'],
            'response_ref':cap['response_ref'],'source_version':cap['source_version'],
            'publication_date':cap['publication_date'],'published_at':None,'available_at':None,
            'first_visible_at':None,'retrieved_at':cap['retrieved_at'],'revision_chain':'NOT_PROVEN',
            'coverage':'PLANNED_HOLIDAYS_ONLY_ACTUAL_EXCEPTIONS_UNPROVEN','formal_admission':'BLOCKED'})
    return {'version':'1.0.0','kind':'DatedCalendarStructure','rows':rows,
            'source_manifest_ref':manifest_ref,'continuous_domain_closed':False,
            'historical_visibility_proven':False,'productionGate':False}


def closure_matrix(calendar_ref,cutoff_policy):
    original=_json(reopen(PIN));spec,spec_ref=frozen_spec()
    rows=[]
    for baseline in original['domains']:
        # Preserve the old row verbatim below, but do not report the old lack
        # of Owner authorization as a current blocker after this conditional grant.
        reasons=[r for r in baseline['reason_codes']
                 if r!='SEPARATE_FORMAL_RESEARCH_AUTHORIZATION_NOT_GRANTED']
        if cutoff_policy!=UNSET:
            reasons=[r for r in reasons if r not in ('PER_DECISION_CUTOFF_NOT_SUPPLIED',)]
        if baseline['domain']=='exchange_calendar_version':
            reasons.extend(['SIX_DATED_ANNUAL_NOTICES_NOT_ACTUAL_EXCEPTION_HISTORY','DATE_ONLY_FIRST_VISIBLE_NOT_PROVEN'])
        # A new Owner authorization is recorded separately, not by rewriting old reasons.
        rows.append({'symbol':baseline['symbol'],'domain':baseline['domain'],
            'baseline_row_ref':{'map_ref':PIN,'symbol':baseline['symbol'],'domain':baseline['domain']},
            'baseline_reasons_preserved':baseline['reason_codes'],
            'required_per_decision_fields':baseline['required_per_decision_fields'],
            'decision_time_policy':cutoff_policy,'available_at':None,'first_visible_at':None,
            'revision_chain':'NOT_PROVEN','formal_admission':'BLOCKED','continuous_closed':False,
            'calendar_structural_evidence_ref':calendar_ref if baseline['domain']=='exchange_calendar_version' else None,
            'reason_codes':sorted(set(reasons)),
            'new_owner_scope':'PIT_PREPARATION_NOW_BACKTEST_ONLY_AFTER_FULL_PREREQUISITES_PASS'})
    require(len(rows)==60 and len({(x['symbol'],x['domain']) for x in rows})==60,'HP_CLOSURE_MATRIX_SET')
    return {'version':'1.0.0','kind':'HistoricalPITClosureMatrix','namespace':NAMESPACE,
        'baseline_map_ref':PIN,'frozen_strategy_ref':spec_ref,'rows':rows,
        'domain_count':20,'symbol_domain_rows':60,'continuous_domains_closed':0,
        'conditional_backtest_owner_authorized':True,'formal_execution':'BLOCKED',
        'productionGate':False,'actual_forward_days_increment':0}


def backtest_attempt(coverage,closure_ref):
    """Record a failed prerequisite evaluation, NOT a zero-profit backtest."""
    spec,spec_ref=frozen_spec();closure=_json(reopen(closure_ref))
    require(closure['continuous_domains_closed']==0,'HP_UNREVIEWED_CLOSURE_PROMOTION')
    return {'version':'1.0.0','kind':'HistoricalBacktestPrerequisiteAttempt',
        'namespace':NAMESPACE,'recorded_at':now(),'state':'BLOCKED_BEFORE_ENGINE',
        'owner_scope':'CONDITIONALLY_AUTHORIZED_AFTER_PIT_AND_ECONOMIC_POLICIES',
        'protocol':{'training':'EXPANDING_FROM_36_MONTH_INITIAL_IS','validation_months':12,
            'sealed_test_months':6,'step_months':6,'purge_sessions':40,'embargo_sessions':40,
            'minimum_sessions':1260,'minimum_complete_trades':100,
            'family_ids':[f['family_id'] for f in spec['families']],
            'exact_anchor_and_boundary_implementation':UNSET,
            'label':'FROZEN_PROTOCOL_PARAMETERS_OWNER_ACCEPTED_IN_THIS_SCOPE_NOT_NEW_POLICY_DEFAULTS'},
        'strategy_spec_ref':spec_ref,'closure_matrix_ref':closure_ref,'current_coverage':coverage,
        'economic_and_execution_policy':spec['required_research_policy_decisions'],
        'reason_codes':['PIT_DOMAINS_NOT_CLOSED','INSUFFICIENT_1260_SESSION_HISTORY',
            'CURRENT_SAMPLE_EXPOSED_NOT_UNTOUCHED_OOS','DATED_ACCOUNT_COST_SLIPPAGE_RISK_UNSET',
            'BENCHMARK_TOTAL_RETURN_AND_INDEPENDENT_REVIEW_UNPROVEN',
            'SEALED_WINDOW_BOUNDARY_IMPLEMENTATION_UNREVIEWED'],
        'engine_called':False,'real_strategy_complete_trades':0,'sealed_windows_executed':0,
        'metrics':{k:None for k in ('gross','net','fees','slippage','turnover','MDD','benchmark_excess','MAE','MFE')},
        'ledger_ref':None,'untouched_oos':False,'historical_visibility_proven':False,
        'productionGate':False,'native_orders':0,'actual_forward_days_increment':0,
        'failures_preserved':True,'parameter_optimization':False}
