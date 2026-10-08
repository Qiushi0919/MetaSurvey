"""Execute frozen-family prerequisites and available raw price components.

This module never emits a trade, ranks a winner, chooses an alternative strategy,
or substitutes a synthetic decision for incomplete actual inputs.
"""
from __future__ import annotations

from collections import defaultdict
from bisect import bisect_right
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext

from wave_g.diagnostic import price_features, validate_calendar

from .interface import (EVALUATION_START, FAMILIES, HISTORY_END, LABELS, SPEC_SHA256,
    SYMBOLS, UNSET, canonical, digest, frozen_spec)
from .pit import event_day, exact_clock


def _number(value):
    if value is None or isinstance(value, bool): return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and len(number.as_tuple().digits) <= 50 and number.adjusted() < 50 else None
    except (InvalidOperation, ValueError):
        return None


def _ref(record):
    keys = ('source', 'domain', 'symbol', 'identity', 'capture_id', 'row_ordinal',
            'record_hash', 'raw_sha256', 'raw_ref', 'source_url', 'retrieved_at',
            'published_at', 'available_at', 'first_visible_at', 'revision_id')
    return {k: record.get(k) for k in keys}


def _wg_row(record, ref_id):
    fields = record.get('fields', {})
    return dict(ts_code=record.get('symbol'), trade_date=event_day(record['event_date']).replace('-', ''),
        **{k: str(fields[k]) if fields.get(k) is not None else None for k in ('open','high','low','close','vol')},
        source_ref={'lineage_ref': ref_id, 'raw_sha256': record.get('raw_sha256'),
                    'available_at': record.get('available_at') or record.get('provenance',{}).get('current_available_at') or record.get('retrieved_at'),
                    'retrieved_at': record.get('retrieved_at'), 'clock_meaning':'CURRENT_CAPTURE_ONLY_NOT_HISTORICAL_VISIBILITY'})


def _calendar_prefix_lookup(rows):
    """A future conflicting calendar revision cannot corrupt an earlier window."""
    grouped = defaultdict(list)
    for row in rows: grouped[row['values']['cal_date']].append(row)
    dates = sorted(grouped); invalid=[]; open_dates=[]
    for day, versions in sorted(grouped.items()):
        literals = all(type(r['values'].get(k)) is str for r in versions for k in ('exchange','is_open'))
        shapes = {(r['values'].get('exchange'),r['values'].get('is_open')) for r in versions} if literals else set()
        valid = len(shapes) == 1 and next(iter(shapes)) in (('SSE','0'),('SSE','1')) and all(
            r['source_ref'].get('raw_sha256') and r['source_ref'].get('available_at') and
            r['source_ref'].get('retrieved_at') for r in versions)
        if not valid: invalid.append(day)
        elif versions[0]['values']['is_open']=='1': open_dates.append(day)
    def prefix(cutoff):
        n = bisect_right(dates,cutoff)
        if not n: return {'state':'UNKNOWN','open_dates':[],'reason':'CALENDAR_PREFIX_ABSENT'}
        first = date.fromisoformat(event_day(dates[0])); last = date.fromisoformat(event_day(cutoff))
        complete = n == (last-first).days+1 and not bisect_right(invalid,cutoff)
        return dict(state='COMPLETE_CURRENT_REFERENCE_RECONSTRUCTION' if complete else 'UNKNOWN',
            open_dates=open_dates[:bisect_right(open_dates,cutoff)] if complete else [],
            historical_visibility_proven=False,exchange_historical_authority=False,
            meaning='CURRENT_QUARANTINED_SSE_REFERENCE_TARGET_MAPPING_ONLY')
    return prefix


def _financial_amount_unit(units, name, alias):
    """Only explicitly declared base CNY amounts have implemented arithmetic.

    Currency metadata alone does not declare a field's numeric unit. No FX or
    thousand/million conversion is inferred; an explicit unknown or conflicting
    declaration cannot fall back to another, more convenient declaration.
    """
    if type(units) is not dict:
        return None
    if 'currency' in units and units['currency'] != 'CNY':
        return None
    declarations = [units[k] for k in dict.fromkeys((name, alias)) if k in units]
    if not declarations or any(type(value) is not str or value != 'CNY' for value in declarations):
        return None
    for key, value in units.items():
        if key in ('unit','amount_unit','monetary_unit','value_unit') and value != 'CNY':
            return None
        if type(key) is str and (key == 'scale' or key.endswith('_scale')):
            if type(value) not in (str,int) or _number(value) != Decimal(1):
                return None
    return 'CNY'


def financial_quarters(records, *, symbol, cutoff):
    """PIT-clock-eligible flow quarters; YTD requires same-year prior YTD.

    This arithmetic does not itself verify issuer authority. A missing clock,
    revision conflict, unknown reporting basis or currency stays a blocker.
    Never treat four cumulative statements as four standalone quarters.
    """
    eligible, reasons = [], set()
    stop = exact_clock(cutoff)
    for r in records:
        if r.get('symbol') != symbol or not r.get('domain', '').startswith('FINANCIAL_'): continue
        try:
            end = event_day(r['event_date'])
        except (ValueError, TypeError, KeyError):
            reasons.add('FINANCIAL_PERIOD_INVALID'); continue
        if end > cutoff[:10]: continue
        try:
            visible = exact_clock(r.get('first_visible_at'))
            # A later observation is outside this prefix even when its other
            # clocks or values are malformed. Do not inspect future payloads.
            if visible > stop: continue
            clocks = [exact_clock(r.get(k)) for k in ('published_at','available_at')] + [visible]
            if not clocks[0] <= clocks[1] <= clocks[2]:
                reasons.add('FINANCIAL_CLOCK_ORDER_CONFLICT'); continue
        except (ValueError, TypeError):
            reasons.add('FINANCIAL_HISTORICAL_CLOCK_MISSING'); continue
        if not r.get('revision_id'):
            reasons.add('FINANCIAL_SOURCE_VERSION_MISSING'); continue
        eligible.append((end, r))
    aliases = {'revenue': ('revenue',), 'oper_cost': ('oper_cost','cost_of_revenue'),
        'net_income': ('n_income','net_income'), 'operating_cashflow': ('n_cashflow_act','operating_cashflow'),
        'ebitda': ('ebitda',)}
    # Keep the report-period inventory independently of successful numeric
    # cells. A visible report with no usable fields must still occupy its slot.
    period_ends = set()
    cells = defaultdict(list)
    conflicts = defaultdict(set)
    def invalidate(end, name, code):
        conflicts[(end,name)].add(code)
        reasons.add(code)

    # Track omissions only within one source/report subdomain/period. Income,
    # cashflow and indicator reports legitimately expose different flow fields.
    versions = defaultdict(lambda:defaultdict(list))
    for end,r in eligible:
        if end[5:] in ('03-31','06-30','09-30','12-31'):
            versions[(r.get('source'),r.get('domain'),end)][exact_clock(r['first_visible_at'])].append(r)
    for (_,_,end), clocks in versions.items():
        prior_fields = set()
        for _,observations in sorted(clocks.items()):
            present = [{name for name,names in aliases.items() if any(r.get('fields',{}).get(k) is not None for k in names)} for r in observations]
            same_clock_fields = set().union(*present)
            # Reusing a revision ID cannot resolve incompatible shapes at the
            # same instant; no iteration order may choose a convenient shape.
            expected = prior_fields | same_clock_fields
            for fields in present:
                for name in expected-fields:
                    invalidate(end,name,'FINANCIAL_VISIBLE_VERSION_FIELD_REMOVAL')
            prior_fields |= same_clock_fields
    for end, r in eligible:
        if end[5:] not in ('03-31','06-30','09-30','12-31'):
            reasons.add('FINANCIAL_COMPLETE_QUARTER_END_REQUIRED'); continue
        period_ends.add(end)
        for name, names in aliases.items():
            present = [k for k in names if r.get('fields', {}).get(k) is not None]
            if not present: continue
            fields = r['fields']
            basis = fields['reporting_basis'] if 'reporting_basis' in fields else r.get('provenance', {}).get('reporting_basis')
            units = [_financial_amount_unit(r.get('units'), name, alias) for alias in present]
            numbers = [_number(fields[alias]) for alias in present]
            if None in units:
                reasons.add('FINANCIAL_MONETARY_UNIT_UNKNOWN_UNSUPPORTED_OR_CONFLICTING')
                reasons.add('FINANCIAL_NUMERIC_OR_UNIT_UNKNOWN')
                invalidate(end,name,'FINANCIAL_VISIBLE_VERSION_UNIT_CONFLICT')
            if basis not in ('CUMULATIVE_YTD','DISCRETE_QUARTER'):
                reasons.add('FINANCIAL_YTD_OR_DISCRETE_BASIS_UNPROVEN')
                invalidate(end,name,'FINANCIAL_VISIBLE_VERSION_BASIS_CONFLICT')
            if None in numbers:
                reasons.add('FINANCIAL_NUMERIC_OR_UNIT_UNKNOWN')
                invalidate(end,name,'FINANCIAL_VISIBLE_VERSION_NUMERIC_CONFLICT')
            elif len(set(numbers)) != 1:
                invalidate(end,name,'FINANCIAL_VISIBLE_VERSION_ALIAS_CONFLICT')
            if (end,name) not in conflicts:
                cells[(end,name)].append((numbers[0],basis,units[0]))
    unique = {}
    for key, values in cells.items():
        if key in conflicts:
            continue
        elif len(set(values)) != 1:
            invalidate(*key,'FINANCIAL_VISIBLE_VERSION_CONFLICT')
        else: unique[key] = values[0]
    quarters = {end:{} for end in period_ends}
    prior = {'06-30': '03-31','09-30': '06-30','12-31': '09-30'}
    for (end, name), (numeric, basis, unit) in sorted(unique.items()):
        suffix = end[5:]
        if suffix not in ('03-31','06-30','09-30','12-31'):
            reasons.add('FINANCIAL_COMPLETE_QUARTER_END_REQUIRED'); continue
        if basis == 'CUMULATIVE_YTD' and suffix != '03-31':
            previous = unique.get((end[:5]+prior[suffix], name))
            if previous is None or previous[1:] != (basis, unit):
                reasons.add('FINANCIAL_YTD_PRIOR_SAME_YEAR_OR_UNIT_MISSING'); continue
            with localcontext() as ctx:
                ctx.prec = 100
                numeric -= previous[0]
        quarters[end][name] = format(numeric, 'f')
    dates = sorted(quarters)
    required = tuple(aliases)
    complete = [d for d in dates if all(k in quarters[d] for k in required)]
    latest = dates[-8:]
    missing_fields = {d:[k for k in required if k not in quarters[d]] for d in latest if d not in complete}
    if missing_fields: reasons.add('FINANCIAL_VISIBLE_QUARTER_FLOW_FIELDS_MISSING')
    # Eight complete quarters must also be consecutive; an omitted quarter is
    # not replaced by an older one just to satisfy a row count.
    indices = [int(d[:4])*4 + ('03-31','06-30','09-30','12-31').index(d[5:]) for d in latest]
    contiguous = len(indices) == 8 and all(b-a == 1 for a,b in zip(indices,indices[1:])) and all(d in complete for d in latest)
    if not contiguous: reasons.add('FINANCIAL_LATEST4_PLUS_PREVIOUS4_COMPLETE_QUARTERS_MISSING')
    ttm = None
    if contiguous:
        with localcontext() as ctx:
            ctx.prec = 100
            ttm = {k: format(sum(Decimal(quarters[d][k]) for d in latest[-4:]), 'f') for k in required}
            ttm['previous4_revenue'] = format(sum(Decimal(quarters[d]['revenue']) for d in latest[:4]), 'f')
    return dict(state='RAW_CLOCK_ELIGIBLE_ARITHMETIC_ONLY' if ttm else 'NOT_COMPUTABLE',
        historical_visibility_proven=False, source_authority_verified=False,
        eligible_versions=len(eligible), complete_quarters=len(complete), quarter_dates=latest,
        missing_fields_by_quarter=missing_fields,ttm_amount_unit='CNY' if ttm else None,
        cell_conflicts={d:{name:sorted(codes) for (end,name),codes in sorted(conflicts.items()) if end==d}
            for d in sorted({key[0] for key in conflicts})},
        ttm=ttm, reason_codes=sorted(reasons))


def _blockers(spec):
    gates = {
        'QUALITY': ['FINANCIAL_TTM8_VISIBLE_QUARTERS_REQUIRED','TTM_REVENUE_GROWTH_AND_GROSS_MARGIN_REQUIRED',
                    'CONTEMPORANEOUS_ROIC_AND_WACC_REQUIRED'],
        'FINANCIAL_QUALITY': ['POSITIVE_TTM_NET_INCOME_REQUIRED','TTM_OCF_TO_NET_INCOME_GE0_8_REQUIRED',
                    'DATED_NET_DEBT_TO_POSITIVE_TTM_EBITDA_LE3_REQUIRED'],
        'VALUATION': ['1260_VALID_POSITIVE_PIT_MULTIPLES_REQUIRED','VALUATION_WEAK_RANK_LE0_6_REQUIRED',
                    '603993_NORMALIZED_CYCLE_EARNINGS_EVIDENCE_REQUIRED'],
        'CATALYST': ['OFFICIAL_HUMAN_CODED_EVENT_AND_EXACT_CLOCK_REQUIRED',
                    'LAST60_ACTUAL_SESSIONS_WITH_RESCISSION_EXPIRY_REQUIRED'],
        'TIMING_RS': ['HISTORICAL_INDUSTRY_MEMBERSHIP_REQUIRED','ACTION_RECONCILED_STOCK_TOTAL_RETURN_REQUIRED',
                    'CONTEMPORANEOUS_SECTOR_TOTAL_RETURN_RS20_REQUIRED'],
        'RISK_STATUS_ACTIONS': ['COMPLETE_HISTORICAL_STATUS_RULES_REQUIRED','OFFICIAL_COMPLETE_ACTION_RECONCILIATION_REQUIRED',
                    'HARD_NEGATIVE_THESIS_AND_TRADABILITY_EVIDENCE_REQUIRED'],
        'EVIDENCE_QUALITY': ['INDEPENDENT_HISTORICAL_PUBLICATION_VERSION_UNITS_LICENSE_REQUIRED',
                    'COMPLETE_ACTUAL_EXCHANGE_CALENDAR_REQUIRED'],
        'NET_EDGE': ['PREDECLARED_EXPECTED_GROSS_RETURN_SCENARIOS_REQUIRED','DATED_ROUND_TRIP_FEES_SLIPPAGE_REQUIRED',
                    'UNCERTAINTY_BUFFER_AND_NET_EDGE_400BPS_COST_RATIO5_REQUIRED'],
        'ECONOMIC_EVALUATION': ['BENCHMARK_LICENSED_TOTAL_RETURN_REQUIRED','LEDGER_COMPLETE_TRADE_PATHS_REQUIRED',
                    'ACTUAL1260_SESSIONS_AND100_COMPLETE_TRADES_NOT_AUTOMATIC', 'UNSEEN_OOS_AND_ALL_WINDOW_REPORTING_REQUIRED']}
    policy = dict(spec['required_research_policy_decisions'])
    policy.update(valuation_estimation=spec['metric_definitions']['Valuation']['required_valuation_estimation_policy'],
        edge_calibration=spec['metric_definitions']['Edge']['calibration_policy'],
        candidate_grades='NOT_DEFINED_IN_FROZEN_SPEC', actual_account=spec['actual_account_parameters'],
        owner_stop=spec['exit_rule']['owner_stop_policy'], owner_flat=spec['allow_flat_rule']['owner_policy'],
        owner_rebalance=spec['rebalance_frequency']['owner_policy'])
    return dict(state='NOT_COMPUTABLE', data_and_evidence_requirements=gates,
        undefined_or_unaccepted_policies=policy,
        meaning='Presence does not close a gate; no WACC/cycle/edge/grade formula inferred')


def diagnose(records, coverage):
    spec = frozen_spec()
    if tuple(x['family_id'] for x in spec['families']) != FAMILIES:
        raise ValueError('STRATEGY_FAMILY_CONFLICT_STOP')
    records = list(records)
    lineage, grouped, calendar_rows, errors = {}, defaultdict(list), [], []
    for r in records:
        if r.get('domain') not in ('PRICE','CALENDAR'): continue
        try:
            day = event_day(r['event_date'])
            if day > HISTORY_END: continue
            ref = _ref(r); refid = 'sha256:'+digest(canonical(ref)); lineage[refid] = ref
            if r['domain'] == 'PRICE' and r.get('symbol') in SYMBOLS:
                grouped[r['symbol']].append((day, r, refid))
            elif r['domain'] == 'CALENDAR':
                f = r.get('fields', {})
                calendar_rows.append(dict(values=dict(cal_date=day.replace('-',''), exchange=f.get('exchange'),
                    is_open=str(f.get('is_open'))), source_ref=dict(lineage_ref=refid,
                    raw_sha256=r.get('raw_sha256'),
                    available_at=r.get('available_at') or r.get('provenance',{}).get('current_available_at') or r.get('retrieved_at'),
                    retrieved_at=r.get('retrieved_at'),clock_meaning='CURRENT_CAPTURE_ONLY_NOT_HISTORICAL_VISIBILITY')))
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(dict(domain=r.get('domain'), identity=r.get('identity'), reason=str(exc)))
    try:
        calendar = validate_calendar(calendar_rows)
    except (ValueError, TypeError, KeyError, AssertionError) as exc:
        calendar = dict(state='UNKNOWN',open_dates=[],reason='CALENDAR_RECONSTRUCTION_INVALID:'+str(exc))
    calendar.pop('source_refs', None)
    calendar_at = _calendar_prefix_lookup(calendar_rows)
    common = _blockers(spec)
    common_id = 'sha256:'+digest(canonical(common))
    candidates, prerequisite_snapshots = [], {}
    coverage_ids = {s: [r.get('requirement_id') for r in coverage.get('rows', []) if r.get('symbol') == s] for s in SYMBOLS}
    prerequisite_records = {s:[r for r in records if r.get('domain') not in ('PRICE','CALENDAR') and
        r.get('symbol') in (s,'*','ALL','SSE')] for s in SYMBOLS}
    # Keep raw references once. Each dated feature points to at most80 sessions.
    for symbol in SYMBOLS:
        source = sorted(grouped[symbol], key=lambda x:x[0])
        byday = defaultdict(list)
        for day, r, refid in source: byday[day].append((r,refid))
        alldates = sorted(byday)
        for index, day in enumerate(alldates):
            if not EVALUATION_START <= day <= HISTORY_END: continue
            dates = alldates[max(0,index-79):index+1]
            rows = []
            try:
                rows = [_wg_row(r,refid) for d in dates for r,refid in byday[d]]
                feature = price_features(rows, day.replace('-',''), symbol=symbol, calendar=calendar_at(day.replace('-','')))
                feature['prefix_date_count'] = index+1
            except (ValueError, TypeError, KeyError, AssertionError) as exc:
                feature = dict(classification='RAW_PRICE_COMPONENT_OBSERVATION_ONLY',values={},conditions={},
                    price_component={f:'UNKNOWN' for f in FAMILIES},reason_codes=['INVALID_RAW_PRICE_WINDOW:'+str(exc)],
                    historical_visibility_proven=False,full_family_decision='NO_DECISION')
            # Wave G repeats version refs inside duplicate/conflict structures;
            # reduce those to the same shared resolvable lineage catalog.
            feature['window_lineage_refs'] = sorted({refid for d in dates for _,refid in byday[d]})
            feature.pop('source_refs', None)
            for section in ('duplicate_dates','conflicts'):
                for item in feature.get(section, []):
                    refs = item.pop('source_refs', item.pop('observations', []))
                    item['lineage_refs'] = [r['lineage_ref'] for r in refs]
            feature['historical_visibility_proven'] = False
            feature['classification'] = 'RAW_PRICE_COMPONENT_OBSERVATION_ONLY'
            feature['strategy_or_ablation_simulation'] = False
            snapshot = _prerequisite_presence(prerequisite_records[symbol], symbol, day)
            snapshot_id = 'sha256:'+digest(canonical(snapshot))
            prerequisite_snapshots.setdefault(snapshot_id,snapshot)
            candidates.append(dict(symbol=symbol,decision_date=day,classification='FULL_FROZEN_FAMILY_PREREQUISITE_DIAGNOSTIC',
                prerequisite_ref=snapshot_id, common_blocker_ref=common_id, coverage_requirement_ids=coverage_ids[symbol],
                families={family:dict(state='NO_DECISION',reason='FULL_FAMILY_PREREQUISITES_NOT_ACCEPTED',
                    raw_price_component=feature['price_component'][family]) for family in FAMILIES}, price_features=feature))
    return dict(labels=list(LABELS),state='ENGINE_NOT_RUN',execution_state='ENGINE_NOT_RUN',
        prerequisite_state='NOT_COMPUTABLE',economic_state='NOT_COMPUTABLE', engine_called=False,
        families=list(FAMILIES),strategy_sha256=SPEC_SHA256,timing_ablation_authorized=False,
        candidate_count=len(candidates),candidates=candidates,
        common_blockers={common_id:common},prerequisite_snapshots=prerequisite_snapshots,
        lineage_catalog=lineage,calendar_reconstruction=calendar,input_errors=errors,
        coverage_state=coverage.get('state'),historical_visibility_proven=False,untouched_oos=False,
        economic_metrics={k:None for k in ('net_profit','total_return','annualized_return','sharpe','max_drawdown',
            'benchmark_excess_return','complete_trades','hypothetical_execution_count','win_rate','mae','mfe')},
        productionGate=False, native_orders=False)


def _prerequisite_presence(records, symbol, day):
    groups = defaultdict(list)
    for r in records:
        if r.get('symbol') not in (symbol,'*','ALL','SSE'): continue
        try:
            if event_day(r.get('event_date')) > day: continue
        except (ValueError, TypeError): continue
        groups[r.get('domain')].append(r)
    domains = ('FINANCIAL_INCOME','FINANCIAL_BALANCE','FINANCIAL_CASHFLOW','FINANCIAL_INDICATOR',
        'VALUATION','CATALYST','INDUSTRY_MEMBERSHIP','SECTOR_TOTAL_RETURN','STATUS','ACTION','BENCHMARK','UNIVERSE')
    presence = {d:dict(raw_versions=len(groups[d]),state='RAW_PRESENCE_NOT_PIT_ADMISSION' if groups[d] else 'DATA_ABSENT',
        observed_field_names=sorted({k for r in groups[d] for k,v in r.get('fields',{}).items() if v is not None})) for d in domains}
    multiple = 'ev_ebitda' if symbol == SYMBOLS[0] else 'pe_ttm'
    valid = {event_day(r['event_date']) for r in groups['VALUATION'] if (_number(r.get('fields',{}).get(multiple)) or Decimal(0)) > 0}
    presence['VALUATION'].update(chosen_multiple=multiple,positive_raw_distinct_dates=len(valid),required_valid_pit_observations=1260,
        valid_pit_observations=None, warmup_met=False, reason='1260_VALID_PIT_VALUES_NOT_PROVEN')
    fin = financial_quarters(records,symbol=symbol,cutoff=day+'T15:00:00+08:00')
    return dict(symbol=symbol,asof=day,domain_presence=presence,financial_quarter_check=fin,
        full_family_state='NO_DECISION', historical_visibility_proven=False,
        policy_state=UNSET, timing_rs20=None, quality=None, financial_quality=None,
        valuation_percentile=None,catalyst=None,risk=None,net_edge_bps=None)
