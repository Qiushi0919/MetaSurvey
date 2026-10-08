"""Wave F actual public evidence closure, not a historical source issuer.

No runtime network or caller-supplied actual facts. The fixed private manifest
binds 10 new official credential-free GET captures (including three preserved
301 responses), 10 discovery queries, and reused official product/calendar
documents. Every original/capture/text reference is reopened against a fixed
version, size and canonical private path. Source versions identify captured
content; they never claim an exchange dataset revision or first availability.

Three listing anchors improve structural evidence: a dated SSE listing notice,
an official HKEX-hosted issuer A-share listing document, and a current issuer
retrospective claim. None proves a continuous listed/delisted interval or a
historical constituent universe. The 2026 SSE rule and delayed clauses establish
date-only rule structure; the 2023 notice requires a first-registered-mainboard-
IPO trigger, so its web-page generic effective date is not adopted. Do not
backfill 2026 limits, current names, ST state or missing bars into earlier days.

Actual price/financial observations remain current-retrieved QUARANTINED. Dates
are metadata, not midnight instants. The financial ann_date/f_ann_date product
definitions and update flag do not prove revision chronology/first visibility.
The pure fixture selector delegates to the already frozen strict selector and
has no independent actual authority. Both matrix and minimum gate are closed
no-argument metadata projections, LOCAL_ONLY/NON_TRADEABLE, always blocked for
formal backtest/Signal/Order. Public transport capture does not verify the
separate authenticated gateway's provider/license/transport.
"""
from copy import deepcopy
from pathlib import Path
import json
import re

from .common import SYMBOLS, ARCHIVE, UNSET, require, canonical, digest, sha, checked_file, metadata

EVIDENCE_PATH = ARCHIVE / 'public/pit/evidence-G2.json'
EVIDENCE_HASH = 'sha256:4b161027d943b15c8f125c94de4bf4665791805791acbe74e187cc65be06d80d'
DOMAINS = (
    'listing_anchor', 'listing_delisting_history', 'st_history',
    'name_status_history', 'suspension_history', 'historical_price_limit_regime',
    'exchange_calendar_version', 'corporate_actions',
    'adjustment_factor_semantics', 'dividend_action_reconciliation',
    'financial_ann_fann_date', 'revision_chronology_first_visibility',
    'industry_history', 'historical_universe_completeness',
)
REQUIRED_PRICE_DOMAINS = (
    'listing_delisting_history', 'st_history', 'name_status_history',
    'suspension_history', 'historical_price_limit_regime',
    'exchange_calendar_version', 'corporate_actions',
    'adjustment_factor_semantics', 'dividend_action_reconciliation',
    'historical_universe_completeness',
)


def _ref(ref):
    require(type(ref) is dict and set(ref) == {'path', 'sha256', 'bytes'}, 'WF_PIT_REF_SHAPE')
    p = Path(ref['path'])
    require(p.is_relative_to(ARCHIVE.parent) and p.stat().st_mode & 0o777 == 0o600,
            'WF_PIT_PRIVATE_PATH_OR_MODE')
    b = checked_file(p, ref['sha256'])
    require(type(ref['bytes']) is int and ref['bytes'] == len(b), 'WF_PIT_REF_BYTES')
    return b


def evidence():
    """Reopen actual fixed originals; returned copies cannot issue anything."""
    b = checked_file(EVIDENCE_PATH, EVIDENCE_HASH)
    require(EVIDENCE_PATH.stat().st_mode & 0o777 == 0o600, 'WF_PIT_PRIVATE_PATH_OR_MODE')
    x = json.loads(b)
    canonical(x)
    require(x['exact_symbols'] == list(SYMBOLS) and len(x['captures']) == 10 and
            x['actual_public_GET_requests'] == 10 and x['discovery_query_count'] == 10 and
            x['discovery_tool_calls'] == 3 and x['authenticated_requests'] == 0 and
            x['credential_lookups'] == 0 and x['redirect_followed_count'] == 0 and
            x['search_results_used_as_original_evidence'] is False,
            'WF_PIT_EVIDENCE_SCOPE')
    require(x['historical_visibility_proven'] is False and x['live_authority'] is False and
            x['formal_source_admission'] == 'BLOCKED' and x['productionGate'] is False,
            'WF_PIT_EVIDENCE_PROMOTION')
    _ref(x['old_report_ref'])
    names = set()
    for c in x['captures']:
        require(c['capture_id'] not in names, 'WF_PIT_DUPLICATE_CAPTURE')
        names.add(c['capture_id'])
        body = _ref(c['body_ref'])
        cap = json.loads(_ref(c['capture_ref']))
        require(c['source_version'] == sha(body) == cap['sha256'] and
                c['url'] == cap['url'] and c['retrieved_at'] == cap['retrieved_at'] and
                c['http_status'] == cap['http_status'] and c['available_at'] is None and
                c['published_at'] is None and c['credentials_attached'] is False and
                c['redirect_followed'] is False and cap['auth_used'] is False and
                cap['redirect_followed'] is False, 'WF_PIT_CAPTURE_BINDING')
        if c['parsed_ref'] is not None:
            _ref(c['parsed_ref'])
        require(c['pdf_signature'] is body.startswith(b'%PDF'), 'WF_PIT_PDF_SIGNATURE')
    for r in x['reused_document_refs']:
        for field in ('raw_ref', 'decoded_ref', 'text_ref'):
            _ref(r[field])
        require(r['available_at'] is None and r['published_at'] is None and
                r['historical_visibility_proven'] is False, 'WF_PIT_REUSED_CLOCK_PROMOTION')
    require(sorted(x['failed_capture_ids']) == ['action-603228', 'financial-600312', 'financial-600312-www'],
            'WF_PIT_FAILURE_PRESERVATION')
    return deepcopy(x)


def source_pins():
    """Complete new evidence dependency inventory for parent release binding."""
    x = evidence()
    refs = [{'path': str(EVIDENCE_PATH), 'sha256': EVIDENCE_HASH,
             'bytes': len(checked_file(EVIDENCE_PATH, EVIDENCE_HASH))}, x['old_report_ref']]
    for c in x['captures']:
        refs.extend([c['body_ref'], c['capture_ref']])
        if c['parsed_ref'] is not None:
            refs.append(c['parsed_ref'])
    for r in x['reused_document_refs']:
        refs.extend(r[f] for f in ('raw_ref', 'decoded_ref', 'text_ref'))
    by_path = {r['path']: r for r in refs}
    return [deepcopy(by_path[p]) for p in sorted(by_path)]


def evidence_refs():
    """New scoped originals/metadata; predecessor already binds reused documents."""
    root = ARCHIVE / 'public/pit'
    return [r for r in source_pins() if Path(r['path']).is_relative_to(root)]


def _date_range(observations, api, symbol, field):
    rows = [r for r in observations if r['api_name'] == api and
            r['values'].get('ts_code') == symbol]
    days = sorted({r['values'].get(field) for r in rows
                   if type(r['values'].get(field)) is str and
                   re.fullmatch(r'\d{8}', r['values'][field])})
    return {'api_name': api, 'observation_count': len(rows), 'distinct_date_count': len(days),
            'range_from': days[0] if days else None, 'range_to': days[-1] if days else None,
            'date_precision': 'DATE_ONLY', 'continuous_session_coverage_proven': False,
            'current_retrieved_only': True, 'historical_available_at': None,
            'raw_versions': sorted({r['source_ref']['raw_sha256'] for r in rows}),
            'retrieval_instants': sorted({r['source_ref']['retrieved_at'] for r in rows}),
            'unknown_date_observation_count': sum(type(r['values'].get(field)) is not str or
                re.fullmatch(r'\d{8}', r['values'].get(field, '')) is None for r in rows)}


def _domain(domain, facts, observations, symbol):
    fs = [deepcopy(f) for f in facts if f['domain'] == domain and
          (f.get('symbol') == symbol or symbol in f.get('symbols', []))]
    result = {'domain': domain, 'historical_coverage': 'UNKNOWN',
              'formal_admission': 'BLOCKED', 'facts': fs,
              'independent_structural_evidence': 'SOURCE_BOUND_PARTIAL' if fs else 'NOT_CAPTURED',
              'covered_intervals': [], 'unfilled_range': 'REQUESTED_HISTORICAL_WINDOW_UNSET_REQUIRED',
              'historical_available_at': None, 'observed_at_the_time': False,
              'absence_means': 'UNKNOWN', 'can_trade': False,
              'reason_codes': ['HISTORICAL_VISIBILITY_UNPROVEN', 'CONTINUOUS_HISTORY_INCOMPLETE']}
    if domain == 'listing_anchor':
        result['historical_coverage'] = 'SINGLE_DATE_ANCHOR_ONLY'
        result['reason_codes'] = ['LISTING_DATE_NOT_LISTED_OR_DELISTED_INTERVAL',
                                  'CURRENT_ISSUER_CLAIM_NOT_CONTEMPORANEOUS' if symbol == SYMBOLS[1]
                                  else 'DATE_ONLY_HISTORICAL_AVAILABLE_AT_UNKNOWN']
    elif domain == 'historical_price_limit_regime':
        result['reason_codes'].extend(['RULE_2026_NOT_BACKFILLED', 'PER_SECURITY_STATUS_AND_EXCEPTION_HISTORY_MISSING',
                                       'RULE_2023_EFFECTIVE_TRIGGER_SESSION_UNPROVEN', 'PRE_2023_RULE_VERSION_COVERAGE_MISSING'])
    elif domain == 'exchange_calendar_version':
        result['independent_structural_evidence'] = 'REUSED_2026_HOLIDAY_NOTICE_ONLY'
        result['reason_codes'].extend(['FIVE_YEAR_EXCHANGE_SESSION_EXCEPTION_HISTORY_MISSING',
                                       'PLANNED_OPEN_DAY_NOT_ACTUAL_SESSION'])
    elif domain in ('st_history', 'name_status_history', 'listing_delisting_history',
                    'suspension_history', 'historical_universe_completeness', 'industry_history'):
        result['reason_codes'].append('NO_CURRENT_STATUS_OR_SURVIVORSHIP_BACKFILL')
        if domain == 'suspension_history':
            result['reason_codes'].append('MISSING_DAILY_BAR_NOT_SUSPENSION_PROOF')
    elif domain == 'corporate_actions':
        result['current_metadata'] = _date_range(observations, 'dividend', symbol, 'ex_date')
        result['reason_codes'].extend(['ACTION_IMPLEMENTATION_AND_PAYMENT_ORIGINALS_MISSING',
                                       'FAILED_OR_REDIRECTED_PDF_NOT_VERIFIED_BODY'])
    elif domain == 'adjustment_factor_semantics':
        result['current_metadata'] = _date_range(observations, 'adj_factor', symbol, 'trade_date')
        result['reason_codes'].extend(['SAME_PROVIDER_FACTOR_NOT_INDEPENDENT_AUTHORITY',
                                       'FACTOR_PRODUCT_METHOD_AND_VERSION_UNPROVEN'])
    elif domain == 'dividend_action_reconciliation':
        result['reason_codes'].extend(['RAW_ACTION_FACTOR_RECONCILIATION_AMBIGUITIES_RETAINED',
                                       'ENTITLEMENT_PAYMENT_UNITS_ROUNDING_UNKNOWN', 'NO_FACTOR_PLUS_CASH_DOUBLE_COUNT'])
    elif domain in ('financial_ann_fann_date', 'revision_chronology_first_visibility'):
        result['current_metadata'] = [_date_range(observations, api, symbol, 'end_date')
                                      for api in ('income', 'balancesheet', 'cashflow', 'fina_indicator')]
        result['independent_structural_evidence'] = 'REUSED_OFFICIAL_PRODUCT_FIELD_DEFINITIONS_ONLY'
        result['reason_codes'].extend(['ANN_DATE_F_ANN_DATE_DATE_ONLY_NOT_INSTANT',
                                       'UPDATE_FLAG_NOT_REVISION_CHAIN', 'FINANCIAL_FIRST_VISIBILITY_UNPROVEN',
                                       'FINANCIAL_REVISED_ORIGINALS_INCOMPLETE', 'FINANCIAL_UNITS_UNVERIFIED'])
    return result


def three_symbol_matrix():
    """Actual immutable three-symbol evidence report, no supplied admission flags."""
    from post_wave_e.core import frozen_context
    public = evidence()
    context = frozen_context()
    by_symbol = {i['symbol']: i for i in context['inputs']}
    require(set(by_symbol) == set(SYMBOLS), 'WF_PIT_ACTUAL_INPUT_SYMBOLS')
    rows = []
    for symbol in SYMBOLS:
        x = by_symbol[symbol]
        require(x['historical_visibility_proven'] is False and x['formal_source_admission'] == 'BLOCKED',
                'WF_PIT_OLD_SOURCE_PROMOTION')
        obs = x['body']['observations']
        rows.append({'symbol': symbol, 'input_content_hash': x['content_hash'],
                     'raw_bars': _date_range(obs, 'daily', symbol, 'trade_date'),
                     'domains': [_domain(d, public['facts'], obs, symbol) for d in DOMAINS],
                     'formal_price_backtest': 'BLOCKED', 'formal_fundamental_pit_backtest': 'BLOCKED',
                     'reconstruction_mode': 'SOURCE_BOUND_DATE_ONLY_FACTS_NOT_COMPLETE_RECONSTRUCTION',
                     'observed_at_the_time': False, 'historical_visibility_proven': False})
    return metadata({'kind': 'HISTORICAL_PIT_THREE_SYMBOL_MATRIX',
                     'state': 'PARTIAL_STRUCTURAL_EVIDENCE_WITH_BLOCKED_HISTORY',
                     'symbols': list(SYMBOLS), 'rows': rows,
                     'public_evidence_ref': {'path': str(EVIDENCE_PATH), 'sha256': EVIDENCE_HASH},
                     'captured_official_evidence': public['captures'],
                     'reused_product_calendar_documents': public['reused_document_refs'],
                     'structural_facts': public['facts'],
                     'source_dependency_hash': digest(source_pins()),
                     'actual_public_GET_requests': 10, 'discovery_query_count': 10, 'discovery_tool_calls': 3,
                     'authenticated_requests': 0, 'credential_lookups': 0,
                     'preserved_failed_capture_ids': public['failed_capture_ids'],
                     'closed_formal_historical_domains': 0, 'closed_c12_c22': 0,
                     'source_provider_license_transport': 'BLOCKED_INDEPENDENT_GATE',
                     'actual_account_parameters': '30_UNSET_REQUIRED',
                     'source_admission': 'BLOCKED', 'Signal': 'BLOCKED', 'Order': 'BLOCKED',
                     'broker_write': False, 'productionGate': False})


def minimum_price_gate():
    matrix = three_symbol_matrix()
    blockers = [{'symbol': row['symbol'], 'domain': domain,
                 'reason_codes': next(d['reason_codes'] for d in row['domains'] if d['domain'] == domain)}
                for row in matrix['body']['rows'] for domain in REQUIRED_PRICE_DOMAINS]
    return metadata({'kind': 'PRICE_BACKTEST_MINIMUM_PIT_GATE',
                     'PRICE_BACKTEST_MINIMUM_PIT_READY': 'BLOCKED',
                     'formal_price_backtest_can_start': False,
                     'formal_fundamental_pit_backtest_can_start': False,
                     'matrix_hash': matrix['content_hash'], 'symbols': list(SYMBOLS),
                     'structural_improvements': ['603993_A_SHARE_DATED_LISTING_DOCUMENT',
                         '603228_DATED_SSE_LISTING_NOTICE', '600312_CURRENT_ISSUER_LISTING_DATE_CLAIM',
                         '2026_SSE_RULE_AND_DELAYED_CLAUSE_ORIGINALS', '2023_EFFECTIVE_TRIGGER_NOT_PUBLICATION_DATE'],
                     'per_security_history_blockers': blockers,
                     'additional_formal_blockers': ['PROVIDER_LICENSE_TRANSPORT_UNVERIFIED',
                         'RAW_BARS_CURRENT_RETRIEVED_NOT_HISTORICAL_AVAILABLE',
                         'DATED_ACTUAL_COST_SCHEDULE_UNSET_REQUIRED', 'FAIR_EVALUATION_OWNER_ACCEPTANCE_PENDING',
                         'FIVE_YEAR_DATED_SECURITY_ACTION_HISTORY_MISSING',
                         'BENCHMARK_TOTAL_RETURN_EVIDENCE_MISSING', 'SEPARATE_HUMAN_BACKTEST_AUTHORIZATION_REQUIRED'],
                     'fundamental_additional_blockers': ['FIRST_VISIBILITY_INSTANT_UNPROVEN',
                         'REVISION_CHAIN_ORIGINALS_INCOMPLETE', 'FINANCIAL_UNITS_UNVERIFIED', 'INDUSTRY_HISTORY_UNKNOWN'],
                     'reason': 'PARTIAL_RULE_AND_LISTING_FACTS_DO_NOT_COMPLETE_HISTORICAL_TRADEABILITY_OR_PIT',
                     'historical_gate_auto_close': False, 'formal_execution': 'BLOCKED',
                     'Signal': 'BLOCKED', 'Order': 'BLOCKED', 'broker_write': False, 'productionGate': False})


def select_history(records, symbol, effective_at, cutoff, mode):
    """Pure explicit fixture selection; quarantined actual rows remain UNKNOWN."""
    from post_wave_e.pit import select_tradeability
    return select_tradeability(records, symbol, effective_at, cutoff, mode)


def run_formal(*args, **kwargs):
    from .common import unavailable
    unavailable('WF_PIT_FORMAL_HISTORY_NOT_ADMITTED')
