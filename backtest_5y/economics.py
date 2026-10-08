"""Explicit hypothetical cost quotes and blocking economic guards.

Only Wave F's pure fee arithmetic is reused. No fixture runner or synthetic gate
is invoked, and actual account assumptions remain UNSET_REQUIRED.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext

from wave_f.backtest import _fees
from .interface import UNSET

VERSION = '1.0.0-sidecar-only'
SCOPE = 'HYPOTHETICAL_DIAGNOSTIC'
MAX_INTEGER = 9007199254740991
CENT = Decimal('0.01')
REQUIRED_COST = (
    'version', 'effective_from', 'effective_until', 'commission_rate',
    'minimum_commission_cents', 'exchange_rate', 'exchange_included',
    'other_buy_rate', 'other_sell_rate', 'other_included', 'sell_tax_rate',
    'slippage_bps', 'currency', 'rate_unit', 'money_rounding', 'commission_scope',
    'slippage_treatment',
)
RATES = ('commission_rate', 'exchange_rate', 'other_buy_rate', 'other_sell_rate', 'sell_tax_rate')


def _unknown(value):
    return value is None or value in ('', UNSET, 'UNKNOWN', 'NOT_COMPUTABLE')


def _exact(value, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
        raise ValueError('EXACT_DECIMAL_REQUIRED_NO_FLOAT')
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('INVALID_DECIMAL') from exc
    if not result.is_finite() or len(result.as_tuple().digits) > 50 or \
       abs(result.as_tuple().exponent) > 50 or result.adjusted() > 50:
        raise ValueError('DECIMAL_PRECISION_OR_FINITE')
    if minimum is not None and result < minimum:
        raise ValueError('DECIMAL_BELOW_MINIMUM')
    if maximum is not None and result > maximum:
        raise ValueError('DECIMAL_ABOVE_MAXIMUM')
    return result


def _integer(value, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError('EXACT_INTEGER_REQUIRED')
    if isinstance(value, str) and (not value.isdigit() or value.startswith('+')):
        raise ValueError('EXACT_INTEGER_REQUIRED')
    number = int(value)
    if not minimum <= number <= MAX_INTEGER:
        raise ValueError('JSON_INTEGER_RANGE')
    return number


def _result(state, *reasons, **extra):
    return {'version': VERSION, 'state': state, 'reason_codes': list(reasons),
            'profile_scope': SCOPE, 'labels': [SCOPE, 'NOT_FORMAL_OOS', 'NON_TRADEABLE'],
            'actual_account_parameters': UNSET, 'actual_account_computable': False,
            'historical_pit_admitted': False, 'native_orders': False,
            'productionGate': False, **extra}


def quote_hypothetical(price, quantity, side, trade_date, cost, raw_price=None,
                       profile_scope=SCOPE):
    """Quote one complete hypothetical order, with embedded slippage exactly once.

    With no raw_price, price is the raw reference and the explicit slippage policy
    produces the proxy fill price. With raw_price, price is that already rounded
    proxy fill and must match the declared policy. No commission/slippage default
    is selected. PER_ORDER is the Wave F minimum commission scope; partial-fill
    aggregation requires a separate reviewed adapter and cannot be quoted here.
    """
    if profile_scope != SCOPE or (isinstance(cost, dict) and
                                 cost.get('profile_scope', SCOPE) != SCOPE):
        return _result('NOT_COMPUTABLE', 'ACTUAL_OR_UNAPPROVED_PROFILE_SCOPE_BLOCKED')
    if not isinstance(cost, dict):
        return _result('NOT_COMPUTABLE', 'EXPLICIT_COST_POLICY_REQUIRED', missing_fields=list(REQUIRED_COST))
    missing = [key for key in REQUIRED_COST if key not in cost or _unknown(cost[key])]
    if missing:
        return _result('NOT_COMPUTABLE', 'EXPLICIT_COST_POLICY_REQUIRED', missing_fields=missing)
    if cost['money_rounding'] != 'HALF_EVEN':
        return _result('NOT_COMPUTABLE', 'ROUNDING_BRIDGE_NOT_APPROVED',
                       supplied_rounding=cost['money_rounding'], helper_rounding='HALF_EVEN',
                       bridge_difference='Wave F HALF_EVEN; H-B/P1A HALF_UP are different at half-cent ties')
    expected_policy = {'currency': 'CNY', 'rate_unit': 'FRACTION_OF_NOTIONAL',
                       'commission_scope': 'PER_ORDER',
                       'slippage_treatment': 'INCLUDED_IN_EXECUTION_PRICE'}
    unsupported = [key for key, value in expected_policy.items() if cost[key] != value]
    if unsupported:
        return _result('NOT_COMPUTABLE', 'UNSUPPORTED_COST_POLICY', unsupported_fields=unsupported)
    if not isinstance(cost['version'], str) or not cost['version']:
        return _result('NOT_COMPUTABLE', 'COST_VERSION_REQUIRED')
    if side not in ('BUY', 'SELL'):
        return _result('NOT_COMPUTABLE', 'SIDE_INVALID')
    try:
        day = date.fromisoformat(trade_date)
        effective_from = date.fromisoformat(cost['effective_from'])
        effective_until = date.fromisoformat(cost['effective_until'])
        if effective_from > effective_until:
            raise ValueError('COST_DATE_RANGE_INVALID')
        if not effective_from <= day <= effective_until:
            return _result('NOT_COMPUTABLE', 'COST_POLICY_NOT_EFFECTIVE_ON_TRADE_DATE',
                           cost_version=cost['version'])
        qty = _integer(quantity, minimum=1)
        policy = dict(cost)
        policy['minimum_commission_cents'] = _integer(cost['minimum_commission_cents'])
        for key in ('exchange_included', 'other_included'):
            if type(cost[key]) is not bool:
                raise ValueError('INCLUSION_BOOLEAN_REQUIRED')
        for key in RATES:
            # The underlying Wave F helper accepts exact lexical rates.
            policy[key] = format(_exact(cost[key], minimum=0, maximum=1), 'f')
        slip = _exact(cost['slippage_bps'], minimum=0, maximum=1000)
        policy['slippage_bps'] = format(slip, 'f')
        supplied = _exact(price, minimum=CENT, maximum=Decimal('1000000000000'))
        reference = supplied if raw_price is None else _exact(raw_price, minimum=CENT,
                                                               maximum=Decimal('1000000000000'))
        with localcontext() as ctx:
            ctx.prec = 100
            if reference % CENT != 0 or supplied % CENT != 0:
                raise ValueError('PRICE_CNY_CENT_TICK_REQUIRED')
            direction = Decimal(1 if side == 'BUY' else -1)
            execution = (reference * (1 + direction * slip / 10000)).quantize(CENT, rounding=ROUND_HALF_EVEN)
            if execution <= 0:
                raise ValueError('NONPOSITIVE_EXECUTION_PRICE')
            if raw_price is not None and supplied != execution:
                return _result('NOT_COMPUTABLE', 'SLIPPAGE_PRICE_POLICY_MISMATCH',
                               expected_execution_price=format(execution, 'f'),
                               cost_version=cost['version'])
            fees = _fees(execution, reference, qty, side, policy)
        if any(abs(number) > MAX_INTEGER for number in fees.values()):
            raise ValueError('JSON_INTEGER_RANGE')
        # Minimum uplift is part of commission. Slippage is already in notional.
        cash_delta = -fees['notional_cents']-fees['total_fee_cents'] if side == 'BUY' else \
            fees['notional_cents']-fees['total_fee_cents']
        total_friction = fees['total_fee_cents'] + fees['slippage_cents']
        if abs(cash_delta) > MAX_INTEGER or total_friction > MAX_INTEGER:
            raise ValueError('JSON_INTEGER_RANGE')
        with localcontext() as ctx:
            ctx.prec = 100
            friction_bps = Decimal(total_friction) / fees['raw_notional_cents'] * 10000
        return _result('COMPUTABLE_HYPOTHETICAL', cost_version=cost['version'],
                       helper='wave_f.backtest._fees', helper_money_rounding='HALF_EVEN',
                       money_rounding=cost['money_rounding'], commission_scope=cost['commission_scope'],
                       currency='CNY', money_unit='INTEGER_CENTS', rate_unit=cost['rate_unit'],
                       effective_from=cost['effective_from'], effective_until=cost['effective_until'],
                       date_endpoint_policy='INCLUSIVE', trade_date=day.isoformat(), side=side,
                       quantity=qty, raw_price=format(reference, 'f'),
                       execution_price=format(execution, 'f'), fees=fees,
                       cash_delta_cents=cash_delta, total_friction_cents=total_friction,
                       friction_bps=format(friction_bps, 'f'),
                       slippage_treatment=cost['slippage_treatment'],
                       slippage_added_to_cash_twice=False, minimum_uplift_is_additional_fee=False,
                       partial_fill_scope='NOT_SUPPORTED_REQUIRES_ORDER_AGGREGATION_ADAPTER',
                       rounding_bridge_state='WAVE_F_HALF_EVEN_ONLY_ACTUAL_HALF_UP_UNSET',
                       historical_visibility_proven=False)
    except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
        return _result('NOT_COMPUTABLE', 'INVALID_EXPLICIT_COST_INPUT', detail=str(exc),
                       cost_version=cost.get('version'))


def net_edge_guard(expected_gross_bps, round_trip_cost_bps, uncertainty_buffer_bps,
                   min_net_edge_bps=None, min_edge_cost_ratio=None):
    """Apply supplied policy thresholds to a supplied expected benefit.

    This helper cannot estimate benefit, choose policy, or issue trade authority.
    A zero/unknown cost cannot be used to manufacture an infinite edge ratio.
    """
    inputs = {'expected_gross_bps': expected_gross_bps,
              'round_trip_cost_bps': round_trip_cost_bps,
              'uncertainty_buffer_bps': uncertainty_buffer_bps,
              'min_net_edge_bps': min_net_edge_bps, 'min_edge_cost_ratio': min_edge_cost_ratio}
    missing = [key for key, value in inputs.items() if _unknown(value)]
    if missing:
        return _result('NOT_COMPUTABLE', 'BENEFIT_COST_OR_POLICY_UNSET', missing_fields=missing)
    try:
        with localcontext() as ctx:
            ctx.prec = 100
            gross = _exact(expected_gross_bps)
            cost = _exact(round_trip_cost_bps, minimum=0)
            buffer = _exact(uncertainty_buffer_bps, minimum=0)
            minimum_edge = _exact(min_net_edge_bps, minimum=0)
            minimum_ratio = _exact(min_edge_cost_ratio, minimum=0)
            if cost == 0:
                return _result('NOT_COMPUTABLE', 'ZERO_COST_EDGE_RATIO_UNDEFINED')
            net = gross-cost-buffer
            ratio = net/cost
            passes = net >= minimum_edge and ratio >= minimum_ratio
            return _result('ACCEPT_HYPOTHETICAL_GUARD' if passes else 'REJECT',
                           *([] if passes else ['NET_EDGE_OR_EDGE_COST_RATIO_BELOW_EXPLICIT_POLICY']),
                           expected_gross_bps=format(gross, 'f'), round_trip_cost_bps=format(cost, 'f'),
                           uncertainty_buffer_bps=format(buffer, 'f'), net_edge_bps=format(net, 'f'),
                           edge_cost_ratio=format(ratio, 'f'), min_net_edge_bps=format(minimum_edge, 'f'),
                           min_edge_cost_ratio=format(minimum_ratio, 'f'),
                           benefit_model='SUPPLIED_ONLY_NOT_ESTIMATED', policy_source='EXPLICIT_ARGUMENTS')
    except (ValueError, TypeError, InvalidOperation) as exc:
        return _result('NOT_COMPUTABLE', 'INVALID_EXPLICIT_GUARD_INPUT', detail=str(exc))


def micro_ladder_guard(expected_benefit_cents, incremental_cost_cents):
    """Reject benefit <= incremental cost; unknown benefit never becomes zero."""
    missing = [key for key, value in (('expected_benefit_cents', expected_benefit_cents),
                                     ('incremental_cost_cents', incremental_cost_cents)) if _unknown(value)]
    if missing:
        return _result('NOT_COMPUTABLE', 'EXPECTED_BENEFIT_OR_INCREMENTAL_COST_UNSET', missing_fields=missing)
    try:
        benefit = _integer(expected_benefit_cents)
        cost = _integer(incremental_cost_cents)
    except (ValueError, TypeError) as exc:
        return _result('NOT_COMPUTABLE', 'INVALID_EXPLICIT_GUARD_INPUT', detail=str(exc))
    passes = benefit > cost
    return _result('ACCEPT_HYPOTHETICAL_GUARD' if passes else 'REJECT',
                   *([] if passes else ['EXPECTED_BENEFIT_NOT_ABOVE_INCREMENTAL_COST']),
                   expected_benefit_cents=benefit, incremental_cost_cents=cost,
                   expected_incremental_net_cents=benefit-cost,
                   benefit_model='SUPPLIED_ONLY_NOT_ESTIMATED')
