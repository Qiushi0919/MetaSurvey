"""Data acceptance inventory derived from the unchanged two-family definition.

Presence, arithmetic coverage, historical availability and source admission are
different checks. This inventory never issues PIT or trading authority.
"""
from collections import Counter
from .interface import *

def requirements(spec=None):
    spec = frozen_spec() if spec is None else spec
    if tuple(x['family_id'] for x in spec['families']) != FAMILIES:
        raise ValueError('STRATEGY_FAMILY_CONFLICT_STOP')
    def row(id, domain, fields, start=HISTORY_START, symbols=SYMBOLS, window='', api='', **extra):
        return dict(id=id, domain=domain, fields=fields, symbols=list(symbols), start=start,
                    end=HISTORY_END, window=window, api_candidates=api.split(','),
                    pit_requirements=['original_source_binding','historical_available_version',
                        'publication_precision','revision_chain','units_and_license'],
                    revision_lookback_days=30, refresh_mode='INCREMENTAL_WITH_OVERLAP', **extra)
    rows = [
        row('raw_daily', 'PRICE', ['trade_date','open','high','low','close','vol'],
            window='Pullback80 / breakout61 actual contiguous comparable sessions; no same-bar execution', api='daily'),
        row('actual_calendar', 'CALENDAR', ['cal_date','exchange','is_open'],
            window='Actual sessions, extraordinary closures and publication evidence', api='trade_cal'),
        row('income_versions', 'FINANCIAL_INCOME', ['end_date','ann_date','revenue','oper_cost','n_income'],
            start=FINANCIAL_START, window='Latest4+previous4 complete PIT-visible quarters, YTD converted without future values',
            api='income', refresh_mode_override='FULL_VERSION_SWEEP'),
        row('balance_versions', 'FINANCIAL_BALANCE', ['end_date','ann_date','money_cap','total_liab'],
            start=FINANCIAL_START, window='Dated cash and interest-bearing debt components, not total liabilities as debt proxy',
            api='balancesheet', refresh_mode_override='FULL_VERSION_SWEEP'),
        row('cashflow_versions', 'FINANCIAL_CASHFLOW', ['end_date','ann_date','n_cashflow_act'],
            start=FINANCIAL_START, window='Latest4 complete PIT-visible quarters; actual disclosure and all revisions',
            api='cashflow', refresh_mode_override='FULL_VERSION_SWEEP'),
        row('roic_ebitda_versions', 'FINANCIAL_INDICATOR', ['end_date','ann_date','roic','ebitda','netdebt'],
            start=FINANCIAL_START, window='ROIC and net debt/positiveTTM EBITDA need accepted definitions and units',
            api='fina_indicator', refresh_mode_override='FULL_VERSION_SWEEP'),
        row('positive_pe_ttm', 'VALUATION', ['trade_date','pe_ttm'], symbols=SYMBOLS[1:],
            window='1260 positive valid PIT observations at EACH decision; weak rank count(x<=current)/N', api='daily_basic'),
        row('ev_ebitda_inputs', 'VALUATION', ['trade_date','total_mv'], symbols=SYMBOLS[:1],
            window='1260 PIT-visible EV/normalizedEBITDA values; marketcap+dated netdebt+accepted cycle method', api='daily_basic'),
        row('corporate_actions', 'ACTION', ['trade_date','adj_factor'],
            window='Factors are only reconciliation input; official ex/record/payment/rights/split history also required', api='adj_factor,dividend'),
        row('historical_status', 'STATUS', ['list_date','delist_date'],
            start=HISTORY_START, window='Complete effective ST/halt/resume/delist/board/limit/lot intervals; current stock_basic insufficient',
            api='stock_basic,namechange,stock_st,suspend_d,stk_limit', refresh_mode_override='FULL_VERSION_SWEEP'),
        row('industry_history', 'INDUSTRY_MEMBERSHIP', ['in_date','out_date','l1_code','l2_code','l3_code'],
            window='Historical members including removed/delisted, classification versions, known interval endpoints',
            api='index_member_all,index_classify', refresh_mode_override='FULL_VERSION_SWEEP'),
        row('sector_total_return', 'SECTOR_TOTAL_RETURN', ['trade_date','total_return_index'],
            window='StockTR20 minus contemporaneous sectorTR20; price-only sw_daily cannot substitute', api='sw_daily,ci_daily'),
        row('official_events', 'CATALYST', ['event_type','published_at','rescinded_at','expires_at'],
            start='2021-01-01', window='Official ORDER_AWARD/CAPACITY_COMMISSIONING/POSITIVE_PROFIT_GUIDANCE; last60 actual sessions; exact intraday clocks',
            api='issuer_exchange_announcements', refresh_mode_override='FULL_VERSION_SWEEP'),
        row('market_benchmark', 'BENCHMARK', ['trade_date','total_return_index'],
            window='CSI300 TR proposed; identifier/tax/action methodology and Owner choice UNSET', api='licensed_total_return_series'),
        row('historical_universe', 'UNIVERSE', ['ts_code','list_date','delist_date'],
            window='Before any expansion: historical all-listed/paused/delisted membership and identifier changes; never latest survivors',
            api='stock_basic:list_status=L,D,P,bak_basic', refresh_mode_override='FULL_VERSION_SWEEP'),
    ]
    for r in rows:
        if 'refresh_mode_override' in r:
            r['refresh_mode'] = r.pop('refresh_mode_override')
    return rows

def policy_gaps(spec=None):
    spec = frozen_spec() if spec is None else spec
    return {
        'research_methods': dict(spec['required_research_policy_decisions']),
        'valuation_estimation': spec['metric_definitions']['Valuation']['required_valuation_estimation_policy'],
        'edge_calibration': spec['metric_definitions']['Edge']['calibration_policy'],
        'actual_account': spec['actual_account_parameters'],
        'candidate_grades': 'S/A/B/C/X grade mapping and calibration not defined by frozen StrategySpec',
        'optional_not_entry_gates': ['ROE','PB'],
        'meaning': 'Data subscriptions cannot resolve absent business/method definitions; no new rule inferred',
    }

def _day(value):
    if not value: return None
    text = str(value)
    if len(text) == 8 and text.isdigit(): return text[:4]+'-'+text[4:6]+'-'+text[6:]
    return text[:10]

def evaluate_coverage(records):
    out=[]
    for req in requirements():
        for symbol in req['symbols']:
            rs=[r for r in records if r.get('domain')==req['domain'] and r.get('symbol') in (symbol,'*','ALL','SSE')]
            # Do not count documents/probes as numeric data or fill absent fields.
            dated=[r for r in rs if _day(r.get('event_date')) and req['start']<=_day(r['event_date'])<=req['end']]
            dates=sorted({_day(r['event_date']) for r in dated})
            field_counts={f:sum(r.get('fields',{}).get(f) is not None for r in dated) for f in req['fields']}
            missing=[f for f,n in field_counts.items() if not n]
            null_counts={f:sum(r.get('fields',{}).get(f) is None for r in dated) for f in req['fields']}
            clocks=Counter('EXACT_CLOCK_RECORDED_NOT_ADMISSION' if r.get('first_visible_at') else 'HISTORICAL_VISIBILITY_UNPROVEN' for r in dated)
            temporal=bool(dates and dates[0]<=req['start'] and dates[-1]>=req['end'])
            reasons=[]
            if not rs: reasons.append('DOMAIN_ABSENT')
            if missing: reasons.append('FIELDS_ABSENT')
            if not temporal: reasons.append('CONTINUOUS_TIME_RANGE_NOT_PROVEN')
            if any(null_counts.values()): reasons.append('FIELD_NULLS_OR_API_SUBTYPES_NEED_RECONCILIATION')
            if '1260' in req['window'] and len(dates)<1260: reasons.append('INSUFFICIENT_1260_VALID_PIT_OBSERVATIONS')
            reasons += ['SOURCE_ADMISSION_AND_REVISION_CHAIN_NOT_ACCEPTED','HISTORICAL_PIT_NOT_ACCEPTED']
            out.append(dict(requirement_id=req['id'],domain=req['domain'],symbol=symbol,
                required_fields=req['fields'],required_start=req['start'],required_end=req['end'],
                required_window=req['window'],record_versions=len(rs),dated_versions=len(dated),
                distinct_event_dates=len(dates),first=dates[0] if dates else None,last=dates[-1] if dates else None,
                field_nonnull_counts=field_counts,field_null_counts=null_counts,missing_fields=missing,
                source_names=sorted({str(r.get('source')) for r in rs}),
                last_collected=max((str(r.get('retrieved_at','')) for r in rs),default=None),
                clock_states=dict(clocks),raw_numeric_presence=bool(dated and not missing),
                pit_state='NOT_ACCEPTED',full_strategy_data_pass=False,reason_codes=reasons))
    return dict(labels=LABELS,state='NOT_COMPUTABLE',rows=out,requirements=len(out),
        full_strategy_data_pass=False,policy_gaps=policy_gaps(),
        actual_pit_admitted_records=0,untouched_oos=False,productionGate=False)
