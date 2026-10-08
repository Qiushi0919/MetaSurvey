"""Independent rational cent oracle, including half-even ties and slip once."""
from copy import deepcopy
from decimal import localcontext
from fractions import Fraction
import unittest

from backtest_5y.economics import quote_hypothetical, net_edge_guard, micro_ladder_guard


def policy(**changes):
    # Deliberate test-only hypothetical assumptions, never actual account defaults.
    return {'version': 'TEST_EXPLICIT_POLICY_V1', 'effective_from': '2026-01-01',
            'effective_until': '2026-01-31', 'commission_rate': '0.0003',
            'minimum_commission_cents': 500, 'exchange_rate': '0.00001',
            'exchange_included': False, 'other_buy_rate': '0.00002',
            'other_sell_rate': '0.00003', 'other_included': False,
            'sell_tax_rate': '0.0005', 'slippage_bps': '10', 'currency': 'CNY',
            'rate_unit': 'FRACTION_OF_NOTIONAL', 'money_rounding': 'HALF_EVEN',
            'commission_scope': 'PER_ORDER', 'slippage_treatment': 'INCLUDED_IN_EXECUTION_PRICE',
            **changes}


def round_even(value):
    """Rational integer oracle; does not call Decimal or Wave F helpers."""
    quotient, remainder = divmod(value.numerator, value.denominator)
    twice = remainder * 2
    return quotient + (twice > value.denominator or
                       (twice == value.denominator and quotient % 2 == 1))


def oracle(raw, quantity, side, cost):
    reference = Fraction(raw)
    direction = 1 if side == 'BUY' else -1
    execution_cents = round_even(reference * (1 + direction*Fraction(cost['slippage_bps'])/10000)*100)
    notional = execution_cents*quantity
    raw_notional = round_even(reference*quantity*100)
    proportional = round_even(Fraction(notional)*Fraction(cost['commission_rate']))
    commission = max(proportional, cost['minimum_commission_cents'])
    exchange = 0 if cost['exchange_included'] else round_even(Fraction(notional)*Fraction(cost['exchange_rate']))
    rate = cost['other_buy_rate'] if side == 'BUY' else cost['other_sell_rate']
    other = 0 if cost['other_included'] else round_even(Fraction(notional)*Fraction(rate))
    tax = round_even(Fraction(notional)*Fraction(cost['sell_tax_rate'])) if side == 'SELL' else 0
    return {'notional_cents': notional, 'raw_notional_cents': raw_notional,
            'commission_cents': commission, 'minimum_commission_uplift_cents': commission-proportional,
            'exchange_cents': exchange, 'other_cents': other, 'sell_tax_cents': tax,
            'total_fee_cents': commission+exchange+other+tax,
            'slippage_cents': abs(notional-raw_notional)}


class EconomicsTests(unittest.TestCase):
    def test_independent_cent_oracle_both_sides_and_inclusion(self):
        for side in ('BUY', 'SELL'):
            for included in (False, True):
                cost = policy(exchange_included=included, other_included=included)
                result = quote_hypothetical('13.37', 281, side, '2026-01-02', cost)
                self.assertEqual(result['state'], 'COMPUTABLE_HYPOTHETICAL')
                self.assertEqual(result['fees'], oracle('13.37', 281, side, cost))
                self.assertEqual(result['money_rounding'], 'HALF_EVEN')
                self.assertEqual(result['cost_version'], cost['version'])
                self.assertEqual(result['actual_account_parameters'], 'UNSET_REQUIRED')
                self.assertFalse(result['productionGate'])

    def test_slippage_changes_cash_once_and_minimum_uplift_is_not_extra(self):
        buy = quote_hypothetical('10.00', 100, 'BUY', '2026-01-02', policy())
        fees = buy['fees']
        self.assertEqual(fees['slippage_cents'], 100)
        self.assertGreater(fees['minimum_commission_uplift_cents'], 0)
        self.assertEqual(buy['cash_delta_cents'], -fees['raw_notional_cents']-
                         fees['slippage_cents']-fees['total_fee_cents'])
        sell = quote_hypothetical('10.00', 100, 'SELL', '2026-01-02', policy())
        fees = sell['fees']
        self.assertEqual(sell['cash_delta_cents'], fees['raw_notional_cents']-
                         fees['slippage_cents']-fees['total_fee_cents'])
        self.assertEqual(sell['total_friction_cents'], fees['slippage_cents']+fees['total_fee_cents'])
        self.assertFalse(sell['slippage_added_to_cash_twice'])
        self.assertFalse(sell['minimum_uplift_is_additional_fee'])

    def test_half_cent_commission_and_execution_ties_use_even_oracle(self):
        for rate, expected in [('0.005', 0), ('0.015', 2), ('0.025', 2)]:
            cost = policy(commission_rate=rate, minimum_commission_cents=0, slippage_bps='0',
                          exchange_included=True, other_included=True, sell_tax_rate='0')
            result = quote_hypothetical('1.00', 1, 'BUY', '2026-01-02', cost)
            self.assertEqual(result['fees']['commission_cents'], expected)
            self.assertEqual(result['fees'], oracle('1.00', 1, 'BUY', cost))
        for slip, expected in [('50', '1.00'), ('150', '1.02'), ('250', '1.02')]:
            cost = policy(slippage_bps=slip)
            result = quote_hypothetical('1.00', 1, 'BUY', '2026-01-02', cost)
            self.assertEqual(result['execution_price'], expected)
            self.assertEqual(result['fees'], oracle('1.00', 1, 'BUY', cost))

    def test_already_slipped_price_must_match_policy_and_is_not_slipped_again(self):
        a = quote_hypothetical('10.00', 100, 'BUY', '2026-01-02', policy())
        b = quote_hypothetical('10.01', 100, 'BUY', '2026-01-02', policy(), raw_price='10.00')
        self.assertEqual(a['fees'], b['fees'])
        self.assertEqual(a['cash_delta_cents'], b['cash_delta_cents'])
        bad = quote_hypothetical('10.02', 100, 'BUY', '2026-01-02', policy(), raw_price='10.00')
        self.assertEqual(bad['state'], 'NOT_COMPUTABLE')
        self.assertIn('SLIPPAGE_PRICE_POLICY_MISMATCH', bad['reason_codes'])

    def test_missing_policy_does_not_select_commission_or_slippage(self):
        for field in ('commission_rate', 'minimum_commission_cents', 'slippage_bps', 'commission_scope', 'money_rounding'):
            cost = policy()
            del cost[field]
            result = quote_hypothetical('10.00', 100, 'BUY', '2026-01-02', cost)
            self.assertEqual(result['state'], 'NOT_COMPUTABLE')
            self.assertIn(field, result['missing_fields'])
        self.assertEqual(quote_hypothetical('10.00', 100, 'BUY', '2026-01-02', None)['state'], 'NOT_COMPUTABLE')

    def test_actual_scope_half_up_partial_scope_float_and_money_overflow_blocked(self):
        for cost in (policy(profile_scope='ACTUAL_ACCOUNT'), policy(money_rounding='HALF_UP'),
                     policy(commission_scope='PER_FILL'), policy(currency='DPU')):
            result = quote_hypothetical('10.00', 100, 'BUY', '2026-01-02', cost)
            self.assertEqual(result['state'], 'NOT_COMPUTABLE')
        result = quote_hypothetical('10.00', 100, 'BUY', '2026-01-02', policy(money_rounding='HALF_UP'))
        self.assertEqual(result['helper_rounding'], 'HALF_EVEN')
        self.assertIn('ROUNDING_BRIDGE_NOT_APPROVED', result['reason_codes'])
        self.assertEqual(quote_hypothetical('10.00', 100, 'BUY', '2026-01-02', policy(),
                                          profile_scope='ACTUAL_ACCOUNT')['state'], 'NOT_COMPUTABLE')
        self.assertEqual(quote_hypothetical(10.0, 100, 'BUY', '2026-01-02', policy())['state'], 'NOT_COMPUTABLE')
        self.assertEqual(quote_hypothetical('10.00', True, 'BUY', '2026-01-02', policy())['state'], 'NOT_COMPUTABLE')
        self.assertEqual(quote_hypothetical('1000000000000.00', 100, 'BUY', '2026-01-02',
                                          policy(slippage_bps='0'))['state'], 'NOT_COMPUTABLE')

    def test_effective_date_endpoints_inclusive_and_outside_unknown(self):
        for day in ('2026-01-01', '2026-01-31'):
            self.assertEqual(quote_hypothetical('10.00', 100, 'BUY', day, policy())['state'],
                             'COMPUTABLE_HYPOTHETICAL')
        for day in ('2025-12-31', '2026-02-01'):
            result = quote_hypothetical('10.00', 100, 'BUY', day, policy())
            self.assertIn('COST_POLICY_NOT_EFFECTIVE_ON_TRADE_DATE', result['reason_codes'])

    def test_net_edge_policy_or_benefit_unknown_zero_cost_never_passes(self):
        self.assertEqual(net_edge_guard('700', '100', '100')['state'], 'NOT_COMPUTABLE')
        self.assertEqual(net_edge_guard(None, '100', '100', '400', '5')['state'], 'NOT_COMPUTABLE')
        self.assertEqual(net_edge_guard('UNSET_REQUIRED', '100', '100', '400', '5')['state'], 'NOT_COMPUTABLE')
        self.assertEqual(net_edge_guard('700', '0', '100', '400', '5')['state'], 'NOT_COMPUTABLE')
        result = net_edge_guard('700', '100', '100', '400', '5')
        self.assertEqual(result['state'], 'ACCEPT_HYPOTHETICAL_GUARD')
        self.assertEqual(result['net_edge_bps'], '500')
        self.assertEqual(result['edge_cost_ratio'], '5')
        self.assertEqual(net_edge_guard('699', '100', '100', '400', '5')['state'], 'REJECT')
        self.assertFalse(result['productionGate'])

    def test_micro_ladder_unknown_or_benefit_no_higher_than_cost(self):
        self.assertEqual(micro_ladder_guard(None, 500)['state'], 'NOT_COMPUTABLE')
        self.assertEqual(micro_ladder_guard('UNSET_REQUIRED', 500)['state'], 'NOT_COMPUTABLE')
        self.assertEqual(micro_ladder_guard(500, None)['state'], 'NOT_COMPUTABLE')
        for benefit in (0, 499, 500):
            self.assertEqual(micro_ladder_guard(benefit, 500)['state'], 'REJECT')
        self.assertEqual(micro_ladder_guard(0, 0)['state'], 'REJECT')
        result = micro_ladder_guard(501, 500)
        self.assertEqual(result['state'], 'ACCEPT_HYPOTHETICAL_GUARD')
        self.assertEqual(result['expected_incremental_net_cents'], 1)
        self.assertFalse(result['productionGate'])

    def test_external_decimal_context_does_not_change_cent_quote_and_extreme_input_blocked(self):
        expected = oracle('13.37', 281, 'SELL', policy())
        with localcontext() as ctx:
            ctx.prec = 2
            result = quote_hypothetical('13.37', 281, 'SELL', '2026-01-02', policy())
        self.assertEqual(result['fees'], expected)
        self.assertEqual(net_edge_guard('1e9999999', '100', '100', '400', '5')['state'], 'NOT_COMPUTABLE')


if __name__ == '__main__':
    unittest.main()
