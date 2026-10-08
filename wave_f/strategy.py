"""Two predeclared CORE_40 research candidates, never Owner execution policy.

No actual source reader, result loader, model, optimizer or native signal issuer.
Fixture feature bundles require exact synthetic provenance, per-feature clocks,
units, immutable hashes and financial periods. They produce only hypothetical
research labels. Unknown evidence is NO_DECISION. Historical data already seen
in earlier waves remains exposed; only prospectively captured evidence can be
called unseen. The candidate JSON is frozen by release pins before reveal.
"""
from copy import deepcopy
from datetime import datetime
import json
from .common import *

SPEC = ROOT / 'docs/wave-f/Frozen-StrategySpec-v1.json'
FEATURE_UNITS = {
    'ttm_revenue_growth': 'RATIO', 'gross_margin_change': 'RATIO',
    'operating_cash_to_net_income': 'RATIO', 'net_income_positive': 'BOOLEAN',
    'roic_above_cost_of_capital': 'BOOLEAN', 'net_debt_to_ebitda': 'RATIO',
    'valuation_percentile': 'RATIO', 'official_catalyst_unexpired': 'BOOLEAN',
    'evidence_complete': 'BOOLEAN', 'hard_risk': 'BOOLEAN',
    'historical_tradeable': 'BOOLEAN', 'net_edge_bps': 'BPS',
    'gross_expected_bps': 'BPS', 'round_trip_cost_bps': 'BPS',
    'uncertainty_buffer_bps': 'BPS',
    'edge_to_cost_ratio': 'RATIO', 'close_above_ma60': 'BOOLEAN',
    'ma60_slope_20': 'PRICE_PER_SESSION', 'sector_rs20': 'RATIO',
    'distance_ma20_atr': 'ATR_MULTIPLE', 'volume3_to_volume20': 'RATIO',
    'close_above_previous3_high': 'BOOLEAN', 'breakout60_ratio': 'RATIO',
    'volume_to_volume20': 'RATIO', 'extension_from_breakout': 'RATIO',
}
FINANCIAL = set(FEATURE_UNITS) & {'ttm_revenue_growth', 'gross_margin_change',
    'operating_cash_to_net_income', 'net_income_positive',
    'roic_above_cost_of_capital', 'net_debt_to_ebitda', 'valuation_percentile'}

def load_spec():
    from .core import frozen_context
    frozen_context()  # Re-read all frozen code, policy and original source bytes.
    return json.loads(checked_file(SPEC))

def freeze_fixture(case):
    keys(case, ('provenance', 'rules', 'evaluation', 'frozen_at', 'reveal_at'))
    require(case['provenance'] == LABEL, 'WF_NOT_OWNER_POLICY')
    require(timestamp(case['frozen_at']) < timestamp(case['reveal_at']), 'WF_FREEZE_AFTER_REVEAL')
    require(type(case['rules']) is dict and case['rules'] and
            type(case['evaluation']) is dict and case['evaluation'], 'WF_EMPTY_POLICY')
    require(UNSET not in str(case), 'WF_UNSET_POLICY')
    return seal({'provenance': LABEL, 'frozen': deepcopy(case), 'live_authority': False})

def verify_freeze(frozen, expected_hash):
    hash_value(expected_hash)
    require(type(frozen) is dict and frozen.get('content_hash') == expected_hash and
            digest({k:v for k,v in frozen.items() if k != 'content_hash'}) == expected_hash,
            'WF_HIDDEN_POLICY_MUTATION')
    require(freeze_fixture(frozen['frozen']) == frozen, 'WF_FREEZE_FORGED')
    return deepcopy(frozen['frozen'])

def evaluate_fixture(family_id, bundle, spec_hash):
    """Return NO_DECISION/HYPOTHETICAL_RESEARCH_MATCH; never native Signal."""
    spec = load_spec()
    require(digest(spec) == hash_value(spec_hash), 'WF_SPEC_MUTATED')
    require(family_id in {x['family_id'] for x in spec['families']}, 'WF_FAMILY_NOT_PREDECLARED')
    keys(bundle, ('provenance', 'symbol', 'decision_at', 'features'))
    require(bundle['provenance'] == LABEL and bundle['symbol'] in SYMBOLS, 'WF_FIXTURE_SCOPE')
    cutoff = timestamp(bundle['decision_at'])
    keys(bundle['features'], tuple(FEATURE_UNITS))
    values = {}; reasons = []; visible = {}
    for name, unit in FEATURE_UNITS.items():
        rec = bundle['features'][name]
        keys(rec, ('value','unit','available_at','retrieved_at','source_hash','period_end'))
        hash_value(rec['source_hash'])
        require(rec['unit'] == unit, 'WF_FEATURE_UNIT')
        if rec['available_at'] is None or rec['retrieved_at'] is None:
            reasons.append('UNKNOWN_CLOCK'); continue
        available = timestamp(rec['available_at']); retrieved = timestamp(rec['retrieved_at'])
        if available > cutoff or retrieved > cutoff:
            reasons.append('FUTURE_FEATURE'); continue
        require(available <= retrieved, 'WF_FEATURE_CLOCK_ORDER')
        if name in FINANCIAL:
            if rec['period_end'] is None:
                reasons.append('UNKNOWN_FINANCIAL_PERIOD'); continue
            period = session_date(rec['period_end'])
            shanghai = datetime.fromisoformat(bundle['decision_at'].replace('Z','+00:00')).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Shanghai')).date()
            if period > shanghai:
                reasons.append('FUTURE_FINANCIAL_PERIOD'); continue
        else:
            require(rec['period_end'] is None, 'WF_NONFINANCIAL_PERIOD')
        if rec['value'] is None:
            reasons.append('UNKNOWN_FEATURE'); continue
        if unit == 'BOOLEAN':
            require(type(rec['value']) is bool, 'WF_BOOLEAN_REQUIRED')
            values[name] = rec['value']
        else:
            values[name] = decimal_string(rec['value'], nonnegative=False)
            require(len(values[name].as_tuple().digits) <= 100 and
                    abs(values[name].adjusted()) <= 96, 'WF_FEATURE_DECIMAL_PRECISION')
        visible[name] = deepcopy(rec)
    base = {'family_id': family_id, 'symbol': bundle['symbol'], 'spec_hash': spec_hash,
            'feature_hash': digest({'symbol':bundle['symbol'], 'decision_at':bundle['decision_at'],
                                    'visible_features':visible}), 'decision_at': bundle['decision_at'],
            'provenance': LABEL, 'live_authority': False, 'native_signal_issued': False}
    if reasons:
        return seal(base | {'decision':'NO_DECISION', 'reason_codes':sorted(set(reasons))})
    v = values
    require(0 <= v['valuation_percentile'] <= 1, 'WF_PERCENTILE_RANGE')
    require(v['round_trip_cost_bps'] > 0 and v['uncertainty_buffer_bps'] >= 0,
            'WF_COST_OR_UNCERTAINTY_OMITTED')
    from decimal import localcontext
    with localcontext() as context:
        context.prec = 100
        require(v['net_edge_bps'] == v['gross_expected_bps'] - v['round_trip_cost_bps'] - v['uncertainty_buffer_bps'], 'WF_NET_EDGE_RECONCILIATION')
        require(v['edge_to_cost_ratio'] == v['net_edge_bps'] / v['round_trip_cost_bps'], 'WF_EDGE_COST_RECONCILIATION')
    common = (v['ttm_revenue_growth'] > 0 and v['gross_margin_change'] >= 0 and
        v['operating_cash_to_net_income'] >= decimal_string('0.8') and v['net_income_positive'] and
        v['roic_above_cost_of_capital'] and v['net_debt_to_ebitda'] <= 3 and
        v['valuation_percentile'] <= decimal_string('0.6') and v['official_catalyst_unexpired'] and
        v['evidence_complete'] and not v['hard_risk'] and v['historical_tradeable'] and
        v['net_edge_bps'] >= 400 and v['edge_to_cost_ratio'] >= 5)
    if family_id == 'CORE40_Q_PULLBACK_V1':
        timing = (v['close_above_ma60'] and v['ma60_slope_20'] > 0 and
            v['sector_rs20'] > decimal_string('0.03') and
            0 <= v['distance_ma20_atr'] < 1 and
            0 <= v['volume3_to_volume20'] < decimal_string('0.8') and
            v['close_above_previous3_high'])
    else:
        timing = (v['breakout60_ratio'] > decimal_string('0.005') and
            v['volume_to_volume20'] >= decimal_string('1.5') and v['sector_rs20'] > 0 and
            0 <= v['extension_from_breakout'] <= decimal_string('0.03'))
    return seal(base | {'decision':'HYPOTHETICAL_RESEARCH_MATCH' if common and timing else 'NO_DECISION',
                        'reason_codes':['PREDECLARED_FIXTURE_RULE_MATCH' if common and timing else 'RULE_NOT_MET',
                                        'NOT_OWNER_POLICY', 'NO_EXECUTION_AUTHORITY']})

def run_actual_strategy(*args, **kwargs):
    unavailable('WF_ACTUAL_STRATEGY_EVALUATION_NOT_AUTHORIZED')

def optimize(*args, **kwargs):
    unavailable('WF_PARAMETER_SEARCH_FORBIDDEN')
