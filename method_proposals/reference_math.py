"""Synthetic arithmetic oracle for an UNAPPROVED methods proposal.

No market reader, calibrator, ledger, strategy adapter, proof issuer or order API.
Calling these pure formulas does not establish empirical inputs or authority.
"""
from decimal import Decimal, localcontext, ROUND_HALF_EVEN, ROUND_CEILING, InvalidOperation
from datetime import datetime, timezone
from functools import wraps
import re
import random

SCOPE = 'SYNTHETIC_METHOD_PROPOSAL_ONLY'


def D(value):
    if not isinstance(value, str):
        raise ValueError('DECIMAL_STRING_REQUIRED')
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('VALID_DECIMAL_STRING_REQUIRED') from exc
    if not result.is_finite():
        raise ValueError('FINITE_DECIMAL_REQUIRED')
    return result


def oracle(fn):
    @wraps(fn)
    def wrapped(*args, scope=None, **kwargs):
        if scope != SCOPE:
            raise ValueError('UNAPPROVED_SYNTHETIC_SCOPE_ONLY')
        with localcontext() as ctx:
            ctx.prec = 50
            ctx.rounding = ROUND_HALF_EVEN
            return fn(*args, **kwargs)
    return wrapped


def positive(x):
    if x <= 0:
        raise ValueError('NONPOSITIVE_DENOMINATOR')
    return x


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        raise ValueError('EMPTY_SAMPLE')
    return xs[n//2] if n % 2 else (xs[n//2-1]+xs[n//2])/2


@oracle
def wacc(rf, beta_raw, erp_cn_total, credit_spread, equity, debt, tax_shield,
         *, nci_value, nci_cost_of_equity):
    rf,beta,erp,spread,e,d,t = map(D,(rf,beta_raw,erp_cn_total,credit_spread,equity,debt,tax_shield))
    if not (rf >= 0 and erp > 0 and spread >= 0 and e > 0 and d >= 0 and 0 <= t <= 1):
        raise ValueError('WACC_INPUT_RANGE')
    beta = (Decimal(2)*beta+1)/3
    if beta < 0:
        raise ValueError('NEGATIVE_SHRUNK_BETA')
    ke = rf+beta*erp
    kd = rf+spread
    nci = D(nci_value)
    if nci < 0:
        raise ValueError('NEGATIVE_NCI_CAPITAL')
    if nci > 0:
        kn = D(nci_cost_of_equity)
        if kn < rf:
            raise ValueError('NCI_COST_BELOW_SAME_CURRENCY_RF')
    elif nci_cost_of_equity is not None:
        raise ValueError('ZERO_NCI_COST_MUST_BE_NOT_APPLICABLE')
    else:
        kn = Decimal(0)  # Algebraic zero weight; never a default for nonzero NCI.
    return {'beta':beta, 'ke':ke, 'kd':kd,
            'nci_value':nci, 'nci_cost_of_equity':kn if nci else None,
            'wacc':(e*ke+nci*kn+d*kd*(1-t))/(e+nci+d)}


@oracle
def normal_ebitda(annual_revenues, annual_ebitdas, ttm_revenue):
    if len(annual_revenues) != 5 or len(annual_ebitdas) != 5:
        raise ValueError('FIVE_COMPARABLE_VISIBLE_YEARS_REQUIRED')
    # Comparability, visibility, currency and EBIT/D&A bridges are external
    # prerequisite evidence, not implied by this mathematical example.
    margins = [D(e)/positive(D(r)) for r,e in zip(annual_revenues,annual_ebitdas)]
    m = median(margins)
    value = positive(D(ttm_revenue))*m
    if value <= 0:
        raise ValueError('NONPOSITIVE_NORMALIZED_EBITDA')
    return {'median_margin':m, 'normalized_ebitda':value}


@oracle
def weak_percentile(history, current):
    if len(history) != 1260:
        raise ValueError('EXACT_1260_VALID_SESSION_VALUES_REQUIRED')
    c=positive(D(current))
    h=[positive(D(x)) for x in history]
    if h[-1] != c:
        raise ValueError('CURRENT_SESSION_VALUE_MUST_END_WINDOW')
    return Decimal(sum(x <= c for x in h))/1260


@oracle
def fair_equity_price(multiple, earnings, net_debt, nci, preferred, nonoperating, shares):
    m,earn,nd,nci,pref,nonop,n=map(D,(multiple,earnings,net_debt,nci,preferred,nonoperating,shares))
    if min(nci,pref,nonop) < 0:
        raise ValueError('NEGATIVE_CAPITAL_BRIDGE_COMPONENT')
    e=positive(m)*positive(earn)-nd-nci-pref+nonop
    if e <= 0:
        raise ValueError('NONPOSITIVE_FAIR_EQUITY')
    if n != n.to_integral_value():
        raise ValueError('INTEGER_SHARES_REQUIRED')
    return {'fair_equity':e,'fair_price':e/positive(n)}


@oracle
def scenario_expectation(probabilities, returns_bps):
    if len(probabilities) != 3 or len(returns_bps) != 3:
        raise ValueError('THREE_SCENARIOS_REQUIRED')
    ps=list(map(D,probabilities));rs=list(map(D,returns_bps))
    if any(p < 0 or p > 1 for p in ps) or sum(ps) != 1:
        raise ValueError('PROBABILITY_SUM_OR_RANGE')
    return sum(p*r for p,r in zip(ps,rs))


@oracle
def probability_bucket(probability):
    p=D(probability)
    if not 0 <= p <= 1:
        raise ValueError('PROBABILITY_RANGE')
    return min(9,int(p*10))  # [0,.1), ... [.9,1], exact Decimal boundaries.


@oracle
def nearest_rank(values, q):
    xs=sorted(map(D,values));p=D(q)
    if not xs or not 0 < p <= 1:
        raise ValueError('QUANTILE_RANGE_OR_EMPTY_SAMPLE')
    rank=int((p*len(xs)).to_integral_value(rounding=ROUND_CEILING))
    return xs[rank-1]


@oracle
def joint_block_indices(session_count, block_length, draws, seed):
    if any(type(x) is not int for x in (session_count,block_length,draws,seed)):
        raise ValueError('INTEGER_INDEX_PARAMETERS_REQUIRED')
    if not 1 <= block_length <= session_count or draws <= 0:
        raise ValueError('BLOCK_INDEX_RANGE')
    rng=random.Random(seed)
    result=[]
    for _ in range(draws):
        indices=[]
        for _ in range((session_count+block_length-1)//block_length):
            start=rng.randrange(0,session_count-block_length+1)
            indices.extend(range(start,start+block_length))
        # One shared sequence indexes complete session rows of all symbols;
        # this function cannot establish row integrity or label eligibility.
        result.append(tuple(indices[:session_count]))
    return result


@oracle
def uncertainty(mu_point, bootstrap_lcb, validation_overprediction):
    mu,lcb,over=map(D,(mu_point,bootstrap_lcb,validation_overprediction))
    return max(Decimal(0),mu-lcb)+max(Decimal(0),over)


@oracle
def edge(mu_bps, cost_bps, buffer_bps):
    mu,c,u=map(D,(mu_bps,cost_bps,buffer_bps))
    if c <= 0 or u < 0:
        raise ValueError('KNOWN_POSITIVE_COST_AND_NONNEGATIVE_BUFFER_REQUIRED')
    net=mu-c-u
    return {'net_bps':net,'net_to_cost':net/c,
            'numeric_example_gates':net >= 400 and net/c >= 5,
            'actual_authority':False,'owner_approval':'PENDING'}


@oracle
def incremental(gross0, gross1, cost0, cost1, buffer0, buffer1):
    g0,g1,c0,c1,u0,u1=map(D,(gross0,gross1,cost0,cost1,buffer0,buffer1))
    if min(c0,c1,u0,u1) < 0:
        raise ValueError('NEGATIVE_TOTAL_COST_OR_BUFFER')
    dg,dc,du=g1-g0,c1-c0,u1-u0
    net=dg-dc-du
    return {'delta_net':net,'strict_cash_comparison':net>0,
            'gross_to_incremental_cost':dg/dc if dc>0 else None,
            'net_to_incremental_cost':net/dc if dc>0 else None,
            'actual_authority':False}


@oracle
def research_only_score(dimensions):
    if set(dimensions) != set('FSCVE'):
        raise ValueError('EXACT_FIVE_RESEARCH_DIMENSIONS_REQUIRED')
    ds={k:D(v) for k,v in dimensions.items()}
    if any(v < 0 or v > 100 for v in ds.values()):
        raise ValueError('RESEARCH_SCORE_RANGE')
    weights={'F':'.25','S':'.20','C':'.15','V':'.10','E':'.05'}
    result=sum(D(weights[k])*ds[k] for k in weights)/D('.75')
    return {'research':result,'research_priority':
            'RESEARCH_PRIORITY_A' if result>=80 else
            'RESEARCH_PRIORITY_B' if result>=68 else 'RESEARCH_PRIORITY_C',
            'actionability_grade':'UNSET_REQUIRED','actual_authority':False}


@oracle
def score(dimensions, risk, mu_bps, cost_bps, *, probability_applicable,
          probability_calibrated):
    if set(dimensions) != set('FSCTVLE'):
        raise ValueError('EXACT_SEVEN_DIMENSIONS_REQUIRED')
    ds={k:D(v) for k,v in dimensions.items()}
    risk=D(risk)
    if any(v < 0 or v > 100 for v in ds.values()) or not 0<=risk<=100:
        raise ValueError('SCORE_RANGE_OR_COST')
    if type(probability_applicable) is not bool or type(probability_calibrated) is not bool:
        raise ValueError('BOOLEAN_REQUIRED')
    weights={'F':'.25','S':'.20','C':'.15','T':'.15','V':'.10','L':'.10','E':'.05'}
    raw=sum(D(weights[k])*ds[k] for k in weights)
    research=sum(D(weights[k])*ds[k] for k in 'FSCVE')/D('.75')
    if not probability_applicable or not probability_calibrated:
        return {'raw':raw,'research':research,'cost_penalty':None,'final':None,
                'reason':'PROBABILITY_NOT_APPLICABLE' if not probability_applicable
                         else 'PROBABILITY_NOT_CALIBRATED'}
    mu,c=map(D,(mu_bps,cost_bps))
    positive(c)
    penalty=min(D('15'),100*c/max(mu,D('50')))
    final=max(D('0'),min(D('100'),raw-D('.20')*risk-penalty))
    return {'raw':raw,'research':research,'cost_penalty':penalty,'final':final}


@oracle
def grade(final, fundamental, research, timing, evidence, *, known=True,
          trusted_hard_block=False, common_pass=False, all_timing_pass=False,
          edge_criteria_pass=False, probability_calibrated, probability_applicable):
    for b in (known,trusted_hard_block,common_pass,all_timing_pass,edge_criteria_pass,
              probability_calibrated,probability_applicable):
        if type(b) is not bool:
            raise ValueError('BOOLEAN_REQUIRED')
    # This remains SYNTHETIC: caller booleans are never real evidence/grants.
    if trusted_hard_block:
        return 'X'
    if (not known or not probability_calibrated or not probability_applicable
            or not common_pass or not all_timing_pass):
        return 'UNSET_REQUIRED'
    f,q,r,t,e=map(D,(final,fundamental,research,timing,evidence))
    if any(x < 0 or x > 100 for x in (f,q,r,t,e)):
        raise ValueError('GRADE_SCORE_RANGE')
    if f<55:return 'X'
    if f<68:return 'C'
    if f<78:return 'B'
    result='A' if q>=80 and r>=80 else 'B'
    if f>=85 and r>=85 and t>=80 and e>=80 and common_pass and all_timing_pass and edge_criteria_pass:
        # S must also satisfy the candidate high-Quality A precursor.
        if q>=80:return 'S'
    return result


def instant(x):
    if not isinstance(x,str):
        raise ValueError('EXACT_OFFSET_TIMESTAMP_REQUIRED')
    match=re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})',x)
    if match is None or match.group(3)=='-00:00':
        raise ValueError('EXACT_OFFSET_TIMESTAMP_MAX_NANOSECOND_PRECISION_REQUIRED')
    base,frac,offset=match.groups()
    if offset!='Z' and (int(offset[1:3])>23 or int(offset[4:6])>59):
        raise ValueError('INVALID_OFFSET_HOUR_OR_MINUTE')
    dt=datetime.fromisoformat(base+offset.replace('Z','+00:00')).astimezone(timezone.utc)
    delta=dt-datetime(1970,1,1,tzinfo=timezone.utc)
    seconds=delta.days*86400+delta.seconds
    # No float timestamp or microsecond truncation at the PIT boundary.
    return seconds*1_000_000_000+int((frac or '').ljust(9,'0'))


@oracle
def mature_label(entry, exit_at, label_available_at, fit_cutoff):
    start,end,avail,fit=map(instant,(entry,exit_at,label_available_at,fit_cutoff))
    if end<start or avail<end:
        raise ValueError('LABEL_TIME_ORDER')
    return end <= fit and avail <= fit
