"""Small explicitly synthetic oracles; none are actual account defaults/data."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import json
import unittest

from wave_f.common import LABEL, SYMBOLS, canonical, digest
from wave_f import backtest as bt

DAYS = ['2026-10-05', '2026-10-08', '2026-10-09', '2026-10-12',
        '2026-10-13', '2026-10-14', '2026-10-15']
A, B, C = SYMBOLS


def clock(day, time='15:00:00', event=None):
    instant = day+'T'+time+'+08:00'
    return {'event_time': event or instant, 'published_at': instant,
            'available_at': instant, 'retrieved_at': instant,
            'source': 'SYNTHETIC_FIXTURE', 'source_version': 'synthetic-source-v1',
            'source_hash': digest({'label': LABEL, 'instant': instant})}


def decision(identifier, session=DAYS[0], symbol=A, side='BUY', qty=100, sequence=0):
    row = {'id': identifier, 'session': session,
           'cutoff': session+'T16:00:00+08:00',
           'frozen_at': session+'T17:00:00+08:00',
           'execute_session': DAYS[DAYS.index(session)+1], 'sequence': sequence,
           'symbol': symbol, 'side': side, 'qty': qty,
           'facts': [{'kind': 'PRICE', 'period_end': None, 'value': '10',
                      'clock': clock(session)}]}
    row['content_hash'] = digest(row)
    return row


def seal_decision(row):
    row['content_hash'] = digest({k: v for k, v in row.items() if k != 'content_hash'})


def freeze(case):
    case['freeze'] = {'policy_hash': digest(bt._policy_body(case)),
                     'decision_hash': digest(case['decisions']),
                     'market_hash': digest(case['market']),
                     'initial_hash': digest(case['initial']),
                     'action_hash': digest({'actions': case['actions'],
                                            'factors': case['factors']}),
                     'benchmark_hash': digest(case['benchmark'])}
    return case


def fixture():
    calendar = [{'date': day, 'open_at': day+'T09:30:00+08:00',
                 'close_at': day+'T15:00:00+08:00'} for day in DAYS]
    market = []
    for day in DAYS[1:5]:
        for symbol in SYMBOLS:
            price = '11' if day >= DAYS[2] and symbol == A else '10'
            market.append({'session': day, 'symbol': symbol, 'price_kind': 'RAW',
                'open': price, 'close': price, 'status': 'TRADABLE',
                'listing_status': 'ACTIVE', 'st_status': 'NORMAL',
                'lower_limit': '1', 'upper_limit': '100',
                'bar_clock': clock(day, '15:30:00'),
                'tradeability_clock': clock(day, '09:00:00')})
    case = {'version': '1.0.0', 'label': LABEL, 'namespace': 'SYNTHETIC:CORE_40',
        'account': 'fixture-account', 'symbols': list(SYMBOLS),
        'freeze_at': DAYS[0]+'T18:00:00+08:00', 'calendar': calendar,
        'window': {'first_session': DAYS[1], 'last_session': DAYS[4]},
        'policy': {'version': 'synthetic-policy-v1', 'label': LABEL,
            'money_rounding': 'HALF_EVEN', 'valuation_basis': 'RAW',
            'factor_application': 'NONE', 'buy_lot': 100, 'max_position_qty': 10000,
            'max_position_fraction': '1', 'max_exposure_fraction': '1',
            'max_drawdown_fraction': '0.50', 'max_turnover_per_session': '3',
            'manual_kill_sessions': []},
        'costs': [{'version': 'synthetic-cost-v1', 'label': LABEL,
            'effective_from': DAYS[1], 'effective_until': DAYS[4],
            'commission_rate': '0.001', 'minimum_commission_cents': 500,
            'exchange_rate': '0.0001', 'exchange_included': True,
            'other_buy_rate': '0.0002', 'other_sell_rate': '0.0003',
            'other_included': True, 'sell_tax_rate': '0.0005', 'slippage_bps': '0'}],
        'initial': {'cash_cents': 200000, 'positions': []},
        'decisions': [decision('buy'), decision('sell', DAYS[1], side='SELL')],
        'market': market, 'actions': [], 'factors': [],
        'benchmark': {'version': 'synthetic-total-return-index-v1', 'label': LABEL,
            'initial_level': '100', 'levels': [{'session': day, 'level': value,
                'clock': clock(day, '15:30:00')} for day, value in
                zip(DAYS[1:5], ['100', '101', '101', '102'])]}, 'freeze': {}}
    return freeze(case)


def price(case, day, symbol, opening, closing=None):
    row = next(row for row in case['market'] if (row['session'], row['symbol']) == (day, symbol))
    row['open'] = opening; row['close'] = closing or opening
    return row


def cash_action(identifier='dividend', record=DAYS[1], ex=DAYS[2], pay=DAYS[3]):
    return {'id': identifier, 'kind': 'CASH_DIVIDEND', 'symbol': A,
        'record_session': record, 'ex_session': ex, 'pay_session': pay,
        'cash_per_share_cents': 20, 'withholding_rate': '0.10',
        'ratio_numerator': None, 'ratio_denominator': None,
        'share_available_session': None,
        'clock': clock(DAYS[0], '12:00:00', event=ex+'T09:30:00+08:00')}


def share_action(kind='SPLIT', numerator=2, denominator=1, available=DAYS[2]):
    return {'id': 'share-action', 'kind': kind, 'symbol': A,
        'record_session': DAYS[1], 'ex_session': DAYS[2], 'pay_session': None,
        'cash_per_share_cents': None, 'withholding_rate': None,
        'ratio_numerator': numerator, 'ratio_denominator': denominator,
        'share_available_session': available,
        'clock': clock(DAYS[0], '12:00:00', event=DAYS[2]+'T09:30:00+08:00')}


class Backtest(unittest.TestCase):
    def run_case(self, case=None):
        return bt.run_fixture(freeze(case or fixture()))

    def reject(self, case, reason=None, reseal=True):
        if reseal: freeze(case)
        with self.assertRaises(ValueError) as caught: bt.run_fixture(case)
        if reason: self.assertEqual(str(caught.exception), reason)

    def test_01_exact_cash_fee_net_gross_oracle(self):
        out = self.run_case()
        self.assertEqual(out['terminal']['cash_cents'], 208945)
        self.assertEqual(out['metrics']['net_pnl_cents'], 8945)
        self.assertEqual(out['metrics']['gross_pnl_cents'], 10000)
        self.assertEqual(out['metrics']['fees']['total_fee_cents'], 1055)
        self.assertEqual(out['metrics']['fees']['commission_cents'], 1000)
        self.assertEqual(out['metrics']['fees']['sell_tax_cents'], 55)
        self.assertEqual(out['metrics']['fees']['minimum_commission_uplift_cents'], 790)

    def test_02_deterministic_and_no_caller_mutation(self):
        case = fixture(); before = canonical(case)
        first = bt.run_fixture(case); second = bt.run_fixture(json.loads(before))
        self.assertEqual(canonical(first), canonical(second))
        self.assertEqual(before, canonical(case))

    def test_03_hash_chain_and_money_share_reconcile(self):
        out = self.run_case(); previous = digest({'label': LABEL, 'genesis': out['freeze']})
        for entry in out['ledger']:
            self.assertEqual(entry['previous_hash'], previous)
            self.assertEqual(entry['content_hash'], digest({k: v for k, v in entry.items()
                                                            if k != 'content_hash'}))
            self.assertEqual(entry['after']['cash_cents'], entry['before']['cash_cents']+
                             entry['cash_delta_cents'])
            for symbol in SYMBOLS:
                self.assertEqual(entry['after']['quantities'][symbol],
                    entry['before']['quantities'][symbol]+entry['quantity_delta'][symbol])
            previous = entry['content_hash']
        self.assertEqual(out['ledger_head'], previous)

    def test_04_benchmark_excess_turnover_and_drawdown(self):
        out = self.run_case()
        self.assertEqual(out['metrics']['benchmark_return_fraction'], '0.02000000')
        self.assertEqual(out['metrics']['net_excess_fraction'], '0.02472500')
        self.assertEqual(out['metrics']['maximum_net_drawdown_fraction'], '0.00250000')
        self.assertEqual(out['metrics']['turnover_notional_cents'], 210000)
        # Frozen oracle: 210000 / ((199500 + 3*208945)/4).
        self.assertEqual(out['metrics']['turnover_fraction'], '1.01653688')

    def test_05_next_session_is_exchange_calendar_session(self):
        out = self.run_case()
        self.assertEqual(out['execution_proxies'][0]['decision_session'], DAYS[0])
        self.assertEqual(out['execution_proxies'][0]['execution_session'], DAYS[1])

    def test_06_same_bar_execution_blocked(self):
        case = fixture(); row = case['decisions'][0]; row['execute_session'] = row['session']
        seal_decision(row); self.reject(case, 'WF_BT_NEXT_CALENDAR_SESSION_REQUIRED')

    def test_07_missing_next_session_does_not_jump_to_observed_bar(self):
        case = fixture(); case['market'] = [r for r in case['market']
                                           if (r['session'], r['symbol']) != (DAYS[1], A)]
        self.reject(case, 'WF_BT_MISSING_SESSION_BAR')

    def test_08_suspension_no_next_available_bar_fill(self):
        case = fixture(); case['decisions'] = case['decisions'][:1]
        row = price(case, DAYS[1], A, '10'); row['status'] = 'SUSPENDED'; row['open'] = None
        out = self.run_case(case)
        self.assertEqual(len(out['execution_proxies']), 1)
        self.assertEqual(out['execution_proxies'][0]['reason'], 'WF_BT_SUSPENDED')
        self.assertEqual(out['metrics']['hypothetical_execution_count'], 0)
        self.assertEqual(out['terminal']['cash_cents'], 200000)

    def test_09_nontradeable_no_execution(self):
        case = fixture(); case['decisions'] = case['decisions'][:1]
        price(case, DAYS[1], A, '10')['status'] = 'NON_TRADEABLE'
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['reason'],
                         'WF_BT_NON_TRADEABLE')

    def test_10_unknown_suspension_status_blocks(self):
        case = fixture(); case['market'][0]['status'] = 'UNKNOWN'
        self.reject(case, 'WF_BT_UNKNOWN_TRADEABILITY')

    def test_11_unknown_st_status_blocks(self):
        case = fixture(); case['market'][0]['st_status'] = 'UNKNOWN'
        self.reject(case, 'WF_BT_UNKNOWN_TRADEABILITY')

    def test_12_unknown_listing_status_blocks(self):
        case = fixture(); case['market'][0]['listing_status'] = 'UNKNOWN'
        self.reject(case, 'WF_BT_UNKNOWN_TRADEABILITY')

    def test_13_delisted_session_cannot_execute(self):
        case = fixture(); case['market'][0]['listing_status'] = 'DELISTED'
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['reason'], 'WF_BT_DELISTED')

    def test_14_missing_limit_blocks(self):
        case = fixture(); case['market'][0]['upper_limit'] = None
        self.reject(case, 'PREP_DECIMAL_REQUIRED')

    def test_15_at_upper_limit_conservative_no_execution(self):
        case = fixture(); case['market'][0]['upper_limit'] = '10'
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['reason'],
                         'WF_BT_PRICE_LIMIT_PROXY_NO_EXECUTION')

    def test_16_at_lower_limit_sell_conservative_no_execution(self):
        case = fixture(); price(case, DAYS[2], A, '11')['lower_limit'] = '11'
        self.assertEqual(self.run_case(case)['execution_proxies'][1]['reason'],
                         'WF_BT_PRICE_LIMIT_PROXY_NO_EXECUTION')

    def test_17_slippage_exceeds_limit_no_execution(self):
        case = fixture(); case['costs'][0]['slippage_bps'] = '100'
        case['market'][0]['upper_limit'] = '10.05'
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['reason'],
                         'WF_BT_PRICE_LIMIT_PROXY_NO_EXECUTION')

    def test_18_t_plus_one_same_day_sell_rejected(self):
        case = fixture(); case['decisions'][1] = decision('same-day-sell', side='SELL', sequence=1)
        out = self.run_case(case)
        self.assertEqual(out['execution_proxies'][1]['reason'], 'WF_BT_T_PLUS_ONE_OR_NO_HOLDING')
        self.assertEqual(out['terminal']['quantities'][A], 100)

    def test_19_t_plus_one_next_calendar_session_sell_allowed(self):
        out = self.run_case()
        self.assertEqual(out['execution_proxies'][1]['status'], 'HYPOTHETICAL_EXECUTION')
        self.assertEqual(out['terminal']['quantities'][A], 0)

    def test_20_no_short_sale(self):
        case = fixture(); case['decisions'] = [decision('short', side='SELL')]
        out = self.run_case(case)
        self.assertEqual(out['execution_proxies'][0]['reason'], 'WF_BT_T_PLUS_ONE_OR_NO_HOLDING')
        self.assertEqual(out['terminal']['cash_cents'], 200000)

    def test_21_fee_inclusive_affordability_not_notional_only(self):
        case = fixture(); case['initial']['cash_cents'] = 100000
        out = self.run_case(case)
        self.assertEqual(out['execution_proxies'][0]['reason'], 'WF_BT_FEE_INCLUSIVE_AFFORDABILITY')
        self.assertEqual(out['metrics']['fees']['total_fee_cents'], 0)
        self.assertEqual(out['terminal']['cash_cents'], 100000)

    def test_22_exact_all_in_cash_boundary(self):
        case = fixture(); case['initial']['cash_cents'] = 100500
        case['decisions'] = case['decisions'][:1]
        out = self.run_case(case)
        self.assertEqual(out['daily'][0]['cash_cents'], 0)
        self.assertEqual(out['terminal']['quantities'][A], 100)

    def cash_order_case(self, sell_first):
        case = fixture(); case['initial'] = {'cash_cents': 2000, 'positions': [
            {'id': 'initial-lot', 'symbol': A, 'qty': 100, 'cost_cents': 100000,
             'acquired_session': DAYS[0], 'available_session': DAYS[1]}]}
        price(case, DAYS[1], A, '11')
        case['decisions'] = [decision('sell-initial', side='SELL', sequence=0 if sell_first else 1),
                             decision('buy-other', symbol=B, sequence=1 if sell_first else 0)]
        return case

    def test_23_same_day_sell_then_buy_cash_usable(self):
        out = self.run_case(self.cash_order_case(True))
        self.assertEqual([r['status'] for r in out['execution_proxies']],
                         ['HYPOTHETICAL_EXECUTION', 'HYPOTHETICAL_EXECUTION'])
        self.assertEqual(out['terminal']['cash_cents'], 10945)
        self.assertEqual(out['terminal']['quantities'][B], 100)

    def test_24_same_day_buy_before_sell_is_not_reordered(self):
        out = self.run_case(self.cash_order_case(False))
        self.assertEqual(out['execution_proxies'][0]['decision_id'], 'buy-other')
        self.assertEqual(out['execution_proxies'][0]['reason'], 'WF_BT_FEE_INCLUSIVE_AFFORDABILITY')
        self.assertEqual(out['terminal']['quantities'][B], 0)
        self.assertEqual(out['terminal']['cash_cents'], 111445)

    def test_25_duplicate_cash_sequence_blocks(self):
        case = self.cash_order_case(True); case['decisions'][1]['sequence'] = 0
        seal_decision(case['decisions'][1]); self.reject(case, 'WF_BT_CASH_SEQUENCE_AMBIGUOUS')

    def test_26_dated_cost_changes_apply_on_execution_date(self):
        case = fixture(); old = case['costs'][0]; old['effective_until'] = DAYS[1]
        new = deepcopy(old); new.update(version='synthetic-new-cost', effective_from=DAYS[2],
                                        effective_until=DAYS[4], minimum_commission_cents=700,
                                        sell_tax_rate='0.001')
        case['costs'].append(new); out = self.run_case(case)
        self.assertEqual(out['execution_proxies'][0]['fees']['commission_cents'], 500)
        self.assertEqual(out['execution_proxies'][1]['fees']['commission_cents'], 700)
        self.assertEqual(out['execution_proxies'][1]['fees']['sell_tax_cents'], 110)
        self.assertEqual(out['terminal']['cash_cents'], 208690)

    def test_27_missing_dated_fee_blocks(self):
        case = fixture(); case['costs'][0]['effective_until'] = DAYS[1]
        self.reject(case, 'WF_BT_DATED_COST_AMBIGUOUS_OR_MISSING')

    def test_28_overlapping_dated_fee_blocks(self):
        case = fixture(); case['costs'].append(deepcopy(case['costs'][0]))
        self.reject(case, 'WF_BT_DATED_COST_AMBIGUOUS_OR_MISSING')

    def test_29_unknown_minimum_commission_not_assumed(self):
        case = fixture(); case['costs'][0]['minimum_commission_cents'] = 'UNSET_REQUIRED'
        self.reject(case, 'WF_BT_INTEGER')

    def test_30_missing_cost_component_not_zeroed(self):
        case = fixture(); del case['costs'][0]['sell_tax_rate']
        self.reject(case, 'PREP_SHAPE_INVALID')

    def test_31_exchange_fee_inclusion_no_double_charge(self):
        case = fixture(); out = self.run_case(case)
        self.assertEqual(out['metrics']['fees']['exchange_cents'], 0)
        case['costs'][0]['exchange_included'] = False; out = self.run_case(case)
        self.assertEqual(out['metrics']['fees']['exchange_cents'], 21)
        self.assertEqual(out['terminal']['cash_cents'], 208924)

    def test_32_other_fee_buy_sell_explicit(self):
        case = fixture(); case['costs'][0]['other_included'] = False
        out = self.run_case(case)
        self.assertEqual(out['metrics']['fees']['other_cents'], 53)
        self.assertEqual(out['terminal']['cash_cents'], 208892)

    def test_33_fee_inclusion_unknown_blocks(self):
        case = fixture(); case['costs'][0]['exchange_included'] = 'UNKNOWN'
        self.reject(case, 'WF_BT_FEE_INCLUSION_UNKNOWN')

    def boundary_case(self, opening):
        case = fixture(); case['initial']['cash_cents'] = 2000000
        case['decisions'] = case['decisions'][:1]
        price(case, DAYS[1], A, opening)
        return case

    def test_34_minimum_commission_below_boundary(self):
        out = self.run_case(self.boundary_case('49.90'))
        self.assertEqual(out['execution_proxies'][0]['fees']['commission_cents'], 500)
        self.assertEqual(out['execution_proxies'][0]['fees']['minimum_commission_uplift_cents'], 1)

    def test_35_minimum_commission_at_boundary(self):
        out = self.run_case(self.boundary_case('50.00'))
        self.assertEqual(out['execution_proxies'][0]['fees']['commission_cents'], 500)
        self.assertEqual(out['execution_proxies'][0]['fees']['minimum_commission_uplift_cents'], 0)

    def test_36_minimum_commission_above_boundary(self):
        out = self.run_case(self.boundary_case('50.10'))
        self.assertEqual(out['execution_proxies'][0]['fees']['commission_cents'], 501)

    def test_37_half_even_fee_half_cent_rounds_down(self):
        case = self.boundary_case('50.00'); case['costs'][0].update(
            minimum_commission_cents=0, commission_rate='0.000001')
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['fees']['commission_cents'], 0)

    def test_38_half_even_fee_one_half_cent_rounds_up(self):
        case = self.boundary_case('50.00'); case['costs'][0].update(
            minimum_commission_cents=0, commission_rate='0.000003')
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['fees']['commission_cents'], 2)

    def test_39_slippage_charged_once_and_fees_use_proxy_price(self):
        case = fixture(); case['costs'][0]['slippage_bps'] = '100'
        out = self.run_case(case)
        self.assertEqual([r['proxy_price'] for r in out['execution_proxies']], ['10.10', '10.89'])
        self.assertEqual(out['metrics']['fees']['slippage_cents'], 2100)
        self.assertEqual(out['metrics']['gross_pnl_cents'], 10000)
        self.assertEqual(out['terminal']['cash_cents'], 206846)
        self.assertEqual(out['metrics']['fees']['sell_tax_cents'], 54)

    def test_40_float_prices_rejected(self):
        case = fixture(); case['market'][0]['open'] = 10.0
        with self.assertRaisesRegex(ValueError, 'PREP_NON_JSON_OR_FLOAT'): bt.run_fixture(case)

    def test_41_boolean_money_rejected(self):
        case = fixture(); case['initial']['cash_cents'] = True
        self.reject(case, 'WF_BT_INTEGER')

    def test_42_unknown_risk_parameter_blocks_fixture(self):
        case = fixture(); case['policy']['max_exposure_fraction'] = 'UNSET_REQUIRED'
        self.reject(case, 'PREP_DECIMAL_REQUIRED')

    def test_43_position_quantity_limit(self):
        case = fixture(); case['policy']['max_position_qty'] = 50
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['reason'],
                         'WF_BT_POSITION_QUANTITY_LIMIT')

    def test_44_position_value_limit_fee_aware(self):
        case = fixture(); case['policy']['max_position_fraction'] = '0.5'
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['reason'],
                         'WF_BT_POSITION_VALUE_LIMIT')

    def test_45_aggregate_exposure_limit(self):
        case = fixture(); case['policy']['max_exposure_fraction'] = '0.5'
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['reason'],
                         'WF_BT_EXPOSURE_LIMIT')

    def test_46_turnover_limit(self):
        case = fixture(); case['policy']['max_turnover_per_session'] = '0.4'
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['reason'], 'WF_BT_TURNOVER_LIMIT')

    def test_47_manual_kill_new_risk_but_sell_allowed(self):
        case = self.cash_order_case(True); case['policy']['manual_kill_sessions'] = [DAYS[1]]
        out = self.run_case(case)
        self.assertEqual(out['execution_proxies'][0]['status'], 'HYPOTHETICAL_EXECUTION')
        self.assertEqual(out['execution_proxies'][1]['reason'], 'WF_BT_KILL_BLOCKS_NEW_RISK')

    def test_48_drawdown_kill_blocks_later_new_risk(self):
        case = fixture(); case['policy']['max_drawdown_fraction'] = '0.05'
        price(case, DAYS[1], A, '10', '8')
        case['decisions'][1] = decision('later-buy', DAYS[1], symbol=B)
        out = self.run_case(case)
        self.assertTrue(out['daily'][0]['kill_active'])
        self.assertEqual(out['execution_proxies'][1]['reason'], 'WF_BT_KILL_BLOCKS_NEW_RISK')
        self.assertEqual(out['metrics']['maximum_net_drawdown_fraction'], '0.10250000')

    def test_49_opening_gap_kill_blocks_before_new_buy(self):
        case = fixture(); case['policy']['max_drawdown_fraction'] = '0.05'
        price(case, DAYS[2], A, '8')
        case['decisions'][1] = decision('gap-buy', DAYS[1], symbol=B)
        out = self.run_case(case)
        self.assertEqual(out['execution_proxies'][1]['reason'], 'WF_BT_KILL_BLOCKS_NEW_RISK')

    def test_50_terminal_open_positions_no_forced_sale(self):
        case = fixture(); case['decisions'] = case['decisions'][:1]
        out = self.run_case(case)
        self.assertFalse(out['terminal_liquidation'])
        self.assertEqual(out['terminal']['quantities'][A], 100)
        self.assertEqual(out['metrics']['hypothetical_execution_count'], 1)
        self.assertEqual(out['terminal']['cash_cents'], 99500)

    def test_51_terminal_next_session_decision_deferred(self):
        case = fixture(); case['decisions'].append(decision('terminal', DAYS[4], symbol=B))
        out = self.run_case(case)
        self.assertEqual(out['deferred_decisions'][0]['status'], 'DEFERRED_BEYOND_TERMINAL')
        self.assertEqual(out['metrics']['hypothetical_execution_count'], 2)

    def test_52_raw_adjusted_isolation(self):
        case = fixture(); case['market'][0]['price_kind'] = 'ADJUSTED'
        self.reject(case, 'WF_BT_ADJUSTED_PRICE_BLOCKED')

    def test_53_adjusted_valuation_basis_blocked(self):
        case = fixture(); case['policy']['valuation_basis'] = 'ADJUSTED'
        self.reject(case, 'WF_BT_ADJUSTED_PRICE_BLOCKED')

    def test_54_factor_plus_cash_application_blocked(self):
        case = fixture(); case['actions'] = [cash_action()]
        case['factors'] = [{'session': DAYS[2], 'symbol': A, 'value': '1.02'}]
        case['policy']['factor_application'] = 'APPLY'
        self.reject(case, 'WF_BT_FACTOR_CASH_DOUBLE_COUNT')

    def test_55_informational_factors_do_not_change_money(self):
        case = fixture(); baseline = self.run_case(case)
        case['factors'] = [{'session': DAYS[2], 'symbol': A, 'value': '123'}]
        out = self.run_case(case)
        self.assertEqual(out['metrics'], baseline['metrics'])
        self.assertEqual(out['terminal'], baseline['terminal'])

    def test_56_dividend_record_ex_pay_reconciliation(self):
        case = fixture(); case['actions'] = [cash_action()]
        out = self.run_case(case)
        entitlement = out['terminal']['entitlements']['dividend']
        self.assertEqual((entitlement['record_qty'], entitlement['gross_cents'],
                          entitlement['tax_cents'], entitlement['net_cents'], entitlement['state']),
                         (100, 2000, 200, 1800, 'PAID'))
        self.assertEqual(out['daily'][0]['receivable_cents'], 0)
        self.assertEqual(out['daily'][1]['receivable_cents'], 1800)
        self.assertEqual(out['daily'][2]['receivable_cents'], 0)
        self.assertEqual(out['terminal']['cash_cents'], 210745)
        self.assertEqual(out['metrics']['gross_pnl_cents'], 12000)

    def test_57_sold_on_ex_still_receives_recorded_dividend(self):
        case = fixture(); case['actions'] = [cash_action()]
        out = self.run_case(case)
        self.assertEqual(out['daily'][1]['market_value_cents'], 0)
        self.assertEqual(out['daily'][1]['receivable_cents'], 1800)
        self.assertEqual(out['terminal']['entitlements']['dividend']['record_qty'], 100)

    def test_58_bought_on_ex_not_entitled(self):
        case = fixture(); case['actions'] = [cash_action()]
        case['decisions'] = [decision('ex-buy', DAYS[1])]
        out = self.run_case(case)
        self.assertEqual(out['terminal']['entitlements']['dividend']['record_qty'], 0)
        self.assertEqual(out['terminal']['entitlements']['dividend']['net_cents'], 0)

    def test_59_sold_before_record_close_no_entitlement(self):
        case = self.cash_order_case(True); case['actions'] = [cash_action()]
        out = self.run_case(case)
        self.assertEqual(out['terminal']['entitlements']['dividend']['record_qty'], 0)

    def test_60_unpaid_entitlement_terminal_not_fake_cash(self):
        case = fixture(); case['actions'] = [cash_action(pay=DAYS[5])]
        out = self.run_case(case)
        self.assertEqual(out['terminal']['cash_cents'], 208945)
        self.assertEqual(out['metrics']['unpaid_receivable_cents'], 1800)
        self.assertEqual(out['terminal']['entitlements']['dividend']['state'], 'EX_RECEIVABLE')

    def test_61_receivable_not_spendable_cash(self):
        case = fixture(); case['initial']['cash_cents'] = 100500
        action = cash_action(); action['cash_per_share_cents'] = 1000
        action['withholding_rate'] = '0'; case['actions'] = [action]
        case['decisions'] = [case['decisions'][0], decision('ex-buy-other', DAYS[1], symbol=B)]
        out = self.run_case(case)
        self.assertEqual(out['execution_proxies'][1]['reason'], 'WF_BT_FEE_INCLUSIVE_AFFORDABILITY')
        self.assertEqual(out['daily'][1]['receivable_cents'], 100000)
        self.assertEqual(out['daily'][1]['cash_cents'], 0)

    def test_62_paid_dividend_cash_usable_before_same_day_decision(self):
        case = fixture(); case['initial']['cash_cents'] = 100500
        action = cash_action(); action['cash_per_share_cents'] = 1100
        action['withholding_rate'] = '0'; case['actions'] = [action]
        case['decisions'] = [case['decisions'][0], decision('pay-buy-other', DAYS[2], symbol=B)]
        out = self.run_case(case)
        self.assertEqual(out['execution_proxies'][1]['status'], 'HYPOTHETICAL_EXECUTION')
        self.assertEqual(out['daily'][2]['cash_cents'], 9500)

    def test_63_dividend_wrong_date_order_blocks(self):
        case = fixture(); action = cash_action(); action['pay_session'] = DAYS[1]
        case['actions'] = [action]; self.reject(case, 'WF_BT_DIVIDEND_DATES_OR_FIELDS')

    def test_64_dividend_unknown_withholding_not_assumed_zero(self):
        case = fixture(); action = cash_action(); action['withholding_rate'] = 'UNSET_REQUIRED'
        case['actions'] = [action]; self.reject(case, 'PREP_DECIMAL_REQUIRED')

    def test_65_split_exact_shares_and_book_cost_preserved(self):
        case = fixture(); case['decisions'] = case['decisions'][:1]
        case['actions'] = [share_action()]
        for day in DAYS[2:5]: price(case, day, A, '5.5')
        out = self.run_case(case)
        self.assertEqual(out['terminal']['quantities'][A], 200)
        self.assertEqual(out['terminal']['book_cost_cents'], 100500)
        self.assertEqual(out['metrics']['gross_pnl_cents'], 10000)

    def test_66_split_settlement_and_sale(self):
        case = fixture(); case['actions'] = [share_action()]
        case['decisions'][1]['qty'] = 200; seal_decision(case['decisions'][1])
        price(case, DAYS[2], A, '5.5')
        out = self.run_case(case)
        self.assertEqual(out['terminal']['cash_cents'], 208945)
        sold = next(e for e in out['ledger'] if e['kind'] == 'SELL_HYPOTHETICAL')
        self.assertEqual(sold['details']['book_cost_removed_cents'], 100500)

    def test_67_bonus_shares_do_not_settle_early(self):
        case = fixture(); case['actions'] = [share_action('BONUS_SHARE', 11, 10, DAYS[3])]
        case['decisions'][1]['qty'] = 110; seal_decision(case['decisions'][1])
        out = self.run_case(case)
        self.assertEqual(out['execution_proxies'][1]['reason'], 'WF_BT_T_PLUS_ONE_OR_NO_HOLDING')
        self.assertEqual(out['terminal']['quantities'][A], 110)

    def test_68_bonus_original_settled_shares_sell_first_odd_residual_later(self):
        case = fixture(); case['actions'] = [share_action('BONUS_SHARE', 11, 10, DAYS[3])]
        case['decisions'].append(decision('bonus-sell', DAYS[2], side='SELL', qty=10))
        out = self.run_case(case)
        self.assertEqual([r['status'] for r in out['execution_proxies']],
            ['HYPOTHETICAL_EXECUTION', 'HYPOTHETICAL_EXECUTION', 'HYPOTHETICAL_EXECUTION'])
        self.assertEqual(out['terminal']['quantities'][A], 0)
        self.assertEqual(out['terminal']['book_cost_cents'], 0)

    def test_69_fractional_share_action_explicitly_unsupported(self):
        case = fixture(); case['actions'] = [share_action('SPLIT', 101, 3)]
        self.reject(case, 'WF_BT_FRACTIONAL_SHARE_ACTION_UNSUPPORTED')

    def test_70_rights_action_explicitly_unsupported(self):
        case = fixture(); action = share_action(); action['kind'] = 'RIGHTS'
        case['actions'] = [action]; self.reject(case, 'WF_BT_UNSUPPORTED_ACTION')

    def test_71_nonadjacent_share_record_ex_not_guessed(self):
        case = fixture(); action = share_action(); action['ex_session'] = DAYS[3]
        action['share_available_session'] = DAYS[3]; case['actions'] = [action]
        self.reject(case, 'WF_BT_SHARE_ACTION_DATES_OR_FIELDS')

    def test_72_multiple_share_actions_same_security_ex_rejected(self):
        case = fixture(); second = share_action(); second['id'] = 'other-split'
        case['actions'] = [share_action(), second]
        self.reject(case, 'WF_BT_DUPLICATE_ECONOMIC_ACTION')

    def test_73_future_available_feature_blocks(self):
        case = fixture(); row = case['decisions'][0]; fact = row['facts'][0]
        fact['clock']['available_at'] = DAYS[1]+'T09:00:00+08:00'
        fact['clock']['retrieved_at'] = DAYS[1]+'T09:00:00+08:00'
        seal_decision(row); self.reject(case, 'WF_BT_PIT_VISIBILITY')

    def test_74_future_retrieved_feature_not_observed_at_time(self):
        case = fixture(); row = case['decisions'][0]
        row['facts'][0]['clock']['retrieved_at'] = DAYS[1]+'T09:00:00+08:00'
        seal_decision(row); self.reject(case, 'WF_BT_PIT_VISIBILITY')

    def test_75_future_financial_period_blocks_even_fake_early_clock(self):
        case = fixture(); row = case['decisions'][0]
        row['facts'][0].update(kind='FINANCIAL', period_end='2026-12-31')
        seal_decision(row); self.reject(case, 'WF_BT_FUTURE_FINANCIAL_PERIOD')

    def test_76_future_event_fact_blocks(self):
        case = fixture(); row = case['decisions'][0]
        row['facts'][0]['clock']['event_time'] = DAYS[1]+'T09:30:00+08:00'
        seal_decision(row); self.reject(case, 'WF_BT_FUTURE_EVENT')

    def test_77_date_only_clock_not_midnight_imputed(self):
        case = fixture(); row = case['decisions'][0]
        row['facts'][0]['clock']['available_at'] = DAYS[0]
        seal_decision(row); self.reject(case, 'PREP_INSTANT_REQUIRED')

    def test_78_policy_after_reveal_blocks(self):
        case = fixture(); case['freeze_at'] = DAYS[1]+'T16:00:00+08:00'
        self.reject(case, 'WF_BT_POLICY_AFTER_REVEAL')

    def test_79_decision_frozen_at_execution_open_is_too_late(self):
        case = fixture(); row = case['decisions'][0]
        row['frozen_at'] = DAYS[1]+'T09:30:00+08:00'; seal_decision(row)
        self.reject(case, 'WF_BT_FREEZE_BEFORE_REVEAL')

    def test_80_policy_mutation_invalidates_frozen_hash(self):
        case = fixture(); case['policy']['max_position_qty'] += 100
        self.reject(case, 'WF_BT_FREEZE_INVALIDATED', reseal=False)

    def test_81_decision_mutation_invalidates_seal(self):
        case = fixture(); case['decisions'][0]['qty'] = 200
        self.reject(case, 'WF_BT_DECISION_INVALIDATED')

    def test_82_market_mutation_invalidates_frozen_hash(self):
        case = fixture(); case['market'][0]['open'] = '10.01'
        self.reject(case, 'WF_BT_FREEZE_INVALIDATED', reseal=False)

    def test_83_actual_source_label_never_accepted(self):
        case = fixture(); case['market'][0]['bar_clock']['source'] = 'TUSHARE_MONTHLY_GATEWAY'
        self.reject(case, 'WF_BT_NOT_SYNTHETIC_SOURCE')

    def test_84_actual_fixture_label_never_accepted(self):
        case = fixture(); case['label'] = 'REAL'
        self.reject(case, 'WF_BT_FIXTURE_LABEL_REQUIRED')

    def test_85_strategy_namespace_isolation(self):
        case = fixture(); case['namespace'] = 'SYNTHETIC:EVENT_3'
        self.reject(case, 'WF_BT_NAMESPACE')

    def test_86_more_securities_not_accepted(self):
        case = fixture(); case['symbols'].append('000001.SZ')
        self.reject(case, 'WF_BT_NAMESPACE')

    def test_87_unknown_extra_authorization_field_rejected(self):
        case = fixture(); case['approval'] = {'actor': 'HUMAN', 'approved': True}
        self.reject(case, 'PREP_SHAPE_INVALID')

    def test_88_llm_or_caller_flags_never_unlock_formal_run(self):
        for authority in (None, 'HUMAN', {'actor': 'LLM', 'approved': True},
                          {'actor': 'HUMAN', 'approved': True}):
            with self.assertRaisesRegex(ValueError, 'WF_BT_FORMAL_BACKTEST_NOT_AUTHORIZED'):
                bt.run_formal(fixture(), authority=authority, productionGate=True)

    def test_89_results_never_native_order_or_live_authority(self):
        out = self.run_case()
        self.assertFalse(out['productionGate']); self.assertFalse(out['live_authority'])
        self.assertFalse(out['source_admitted']); self.assertEqual(out['actual_forward_days'], 0)
        self.assertTrue(all(r['native_order'] is False for r in out['execution_proxies']))
        self.assertFalse(set(out) & {'SignalEvent', 'Approval', 'OrderIntent', 'Fill'})

    def test_90_readiness_is_engineering_only_with_limits(self):
        out = bt.readiness(); body = out['body']
        self.assertEqual(body['fixture_execution'], 'AVAILABLE')
        self.assertEqual(body['formal_execution'], 'BLOCKED')
        self.assertEqual(body['account_cost_risk_policy'], 'UNSET_REQUIRED')
        self.assertIn('RIGHTS', body['unsupported_actions'])
        self.assertFalse(body['native_signal_order_broker_path'])

    def test_91_duplicate_market_and_benchmark_rows_not_deduped(self):
        case = fixture(); case['market'].append(deepcopy(case['market'][0]))
        self.reject(case, 'WF_BT_MARKET_IDENTITY')
        case = fixture(); case['benchmark']['levels'].append(deepcopy(case['benchmark']['levels'][0]))
        self.reject(case, 'WF_BT_BENCHMARK_IDENTITY')

    def test_92_sell_partials_keep_integer_book_cost_exact(self):
        case = fixture(); case['decisions'][0]['qty'] = 300; seal_decision(case['decisions'][0])
        case['initial']['cash_cents'] = 500000
        case['decisions'].append(decision('second-sale', DAYS[2], side='SELL', qty=200))
        out = self.run_case(case)
        sales = [e for e in out['ledger'] if e['kind'] == 'SELL_HYPOTHETICAL']
        self.assertEqual(sum(e['details']['book_cost_removed_cents'] for e in sales), 300500)
        self.assertEqual(out['terminal']['book_cost_cents'], 0)

    def test_93_buy_lot_and_odd_partial_sell_policy(self):
        case = fixture(); case['decisions'][0]['qty'] = 50; seal_decision(case['decisions'][0])
        self.assertEqual(self.run_case(case)['execution_proxies'][0]['reason'], 'WF_BT_BUY_LOT')
        case = fixture(); case['decisions'][1]['qty'] = 50; seal_decision(case['decisions'][1])
        self.assertEqual(self.run_case(case)['execution_proxies'][1]['reason'],
                         'WF_BT_ODD_LOT_PARTIAL_SELL')

    def test_94_initial_holdings_cannot_claim_early_settlement(self):
        case = self.cash_order_case(True); case['initial']['positions'][0]['available_session'] = DAYS[0]
        self.reject(case, 'WF_BT_INITIAL_T_PLUS_ONE')

    def test_95_missing_benchmark_not_silently_zero(self):
        case = fixture(); case['benchmark']['levels'].pop()
        self.reject(case, 'WF_BT_BENCHMARK_MISSING')

    def test_96_tradeability_future_retrieval_blocks(self):
        case = fixture(); case['market'][0]['tradeability_clock']['retrieved_at'] = DAYS[1]+'T16:00:00+08:00'
        self.reject(case, 'WF_BT_PIT_VISIBILITY')

    def test_97_long_1260_session_synthetic_exact_oracle_and_determinism(self):
        # This declared synthetic weekday calendar is not an actual SSE calendar.
        case = fixture(); days = []; day = date(2020, 1, 1)
        while len(days) < 1262:
            if day.weekday() < 5: days.append(day.isoformat())
            day += timedelta(days=1)
        active = days[1:1261]
        case['freeze_at'] = days[0]+'T18:00:00+08:00'
        case['calendar'] = [{'date': d, 'open_at': d+'T09:30:00+08:00',
                            'close_at': d+'T15:00:00+08:00'} for d in days]
        case['window'] = {'first_session': active[0], 'last_session': active[-1]}
        case['costs'][0].update(effective_from=active[0], effective_until=active[-1])
        template = deepcopy(case['market'][0]); case['market'] = []
        for d in active:
            for symbol in SYMBOLS:
                row = deepcopy(template); row.update(session=d, symbol=symbol,
                    bar_clock=clock(d, '15:30:00'), tradeability_clock=clock(d, '09:00:00'))
                case['market'].append(row)
        case['benchmark']['levels'] = [{'session': d, 'level': '100',
                                       'clock': clock(d, '15:30:00')} for d in active]
        buy, sell = decision('long-buy'), decision('long-sell', DAYS[1], side='SELL')
        for row, prior, execution in ((buy, days[0], days[1]),
                                      (sell, days[1259], days[1260])):
            row.update(session=prior, execute_session=execution,
                       cutoff=prior+'T16:00:00+08:00', frozen_at=prior+'T17:00:00+08:00',
                       facts=[{'kind': 'PRICE', 'period_end': None, 'value': '10',
                               'clock': clock(prior)}]); seal_decision(row)
        case['decisions'] = [buy, sell]; freeze(case)
        first, second = bt.run_fixture(case), bt.run_fixture(deepcopy(case))
        self.assertEqual(canonical(first), canonical(second))
        self.assertEqual(len(first['daily']), 1260)
        self.assertEqual(len(first['ledger']), 1262)
        self.assertEqual(first['terminal']['cash_cents'], 198950)
        self.assertEqual(first['metrics']['net_pnl_cents'], -1050)
        self.assertEqual(first['metrics']['gross_pnl_cents'], 0)
        self.assertEqual(first['metrics']['benchmark_return_fraction'], '0.00000000')
        self.assertEqual(first['metrics']['hypothetical_execution_count'], 2)

    def test_98_fractional_raw_tick_not_rounded_to_price_improvement(self):
        case = fixture(); case['market'][0]['open'] = '10.001'
        self.reject(case, 'WF_BT_PRICE_TICK')

    def test_99_bar_event_from_future_session_rejected(self):
        case = fixture(); case['market'][0]['bar_clock']['event_time'] = DAYS[2]+'T15:00:00+08:00'
        self.reject(case, 'WF_BT_OUTCOME_REVEAL_CLOCK')

    def test_100_future_tradeability_effective_event_rejected(self):
        case = fixture(); case['market'][0]['tradeability_clock']['event_time'] = DAYS[2]+'T09:30:00+08:00'
        self.reject(case, 'WF_BT_FUTURE_EVENT')

    def test_101_current_revision_metadata_not_implicitly_reused(self):
        case = fixture(); row = case['decisions'][0]
        row['facts'][0]['latest_revision'] = True
        seal_decision(row); self.reject(case, 'PREP_SHAPE_INVALID')

    def test_102_missing_action_clock_not_inferred(self):
        case = fixture(); action = cash_action(); action['clock']['available_at'] = None
        case['actions'] = [action]; self.reject(case, 'PREP_INSTANT_REQUIRED')

    def test_103_scheduled_future_action_event_valid_but_after_record_announcement_blocks(self):
        case = fixture(); case['actions'] = [cash_action()]
        self.assertEqual(self.run_case(case)['terminal']['entitlements']['dividend']['state'], 'PAID')
        case['actions'][0]['clock']['published_at'] = DAYS[1]+'T16:00:00+08:00'
        case['actions'][0]['clock']['available_at'] = DAYS[1]+'T16:00:00+08:00'
        case['actions'][0]['clock']['retrieved_at'] = DAYS[1]+'T16:00:00+08:00'
        self.reject(case, 'WF_BT_PIT_VISIBILITY')

    def test_104_later_announcement_supported_without_earlier_cash_position_effect(self):
        case = fixture(); case['decisions'] = case['decisions'][:1]
        baseline = self.run_case(case)
        action = cash_action(record=DAYS[3], ex=DAYS[4], pay=DAYS[5])
        action['clock'] = clock(DAYS[3], '10:00:00', event=DAYS[4]+'T09:30:00+08:00')
        case['actions'] = [action]; out = self.run_case(case)
        # Dataset/genesis hashes differ because this fixture includes a later
        # action; compare actual numerical observations, not that provenance.
        self.assertEqual([{k: v for k, v in d.items() if k != 'ledger_head'}
                          for d in out['daily'][:2]],
                         [{k: v for k, v in d.items() if k != 'ledger_head'}
                          for d in baseline['daily'][:2]])
        self.assertEqual([e['after'] for e in out['ledger'] if e['session'] < DAYS[3]],
                         [e['after'] for e in baseline['ledger'] if e['session'] < DAYS[3]])
        self.assertEqual(out['terminal']['cash_cents'], baseline['terminal']['cash_cents'])
        self.assertEqual(out['terminal']['quantities'], baseline['terminal']['quantities'])
        self.assertEqual(out['terminal']['entitlements']['dividend']['state'], 'EX_RECEIVABLE')
        self.assertEqual(out['daily'][-1]['receivable_cents'], 1800)
        self.assertTrue(all(e['session'] >= DAYS[3] for e in out['ledger']
                            if e['kind'].startswith(('ACTION_', 'DIVIDEND_'))))

    def test_105_duplicate_cash_economic_action_not_paid_twice(self):
        case = fixture(); duplicate = cash_action('copy-action')
        case['actions'] = [cash_action(), duplicate]
        self.reject(case, 'WF_BT_DUPLICATE_ECONOMIC_ACTION')

    def test_106_dynamic_dividend_tax_policy_is_not_silently_supported(self):
        case = fixture(); action = cash_action(); action['withholding_model'] = 'DYNAMIC_HOLDING_PERIOD'
        case['actions'] = [action]; self.reject(case, 'PREP_SHAPE_INVALID')

    def test_107_post_action_turnover_equity_includes_receivable(self):
        case = fixture(); case['actions'] = [cash_action()]
        price(case, DAYS[2], A, '9.80')
        out = self.run_case(case)
        # Pre-sale NAV = 99,500 cash + 98,000 raw holding + 1,800 receivable.
        self.assertEqual(out['daily'][1]['turnover_fraction'], '0.49172102')

    def test_108_json_integer_exact_safe_boundary_and_oversized_input(self):
        case = fixture(); case['initial']['cash_cents'] = bt.JSON_INTEGER_MAX
        case['decisions'] = []
        out = self.run_case(case)
        self.assertEqual(out['terminal']['cash_cents'], 9007199254740991)
        self.assertEqual(out['initial_equity_cents'], 9007199254740991)
        case['initial']['cash_cents'] += 1
        self.reject(case, 'WF_BT_JSON_INTEGER_RANGE')

    def test_109_individually_safe_inputs_reject_calculated_money_overflow(self):
        case = fixture(); case['initial']['cash_cents'] = bt.JSON_INTEGER_MAX-1000
        # Every input integer is safe; ordinary exact 8,945-cent fixture profit
        # would make terminal cash 7,945 cents larger than JSON's safe maximum.
        self.reject(case, 'WF_BT_JSON_INTEGER_RANGE')

    def test_110_decimal_significant_digits_are_bounded_without_rounding_input(self):
        case = fixture(); case['costs'][0]['commission_rate'] = '0.'+'1'*51
        self.reject(case, 'WF_BT_DECIMAL_PRECISION')


if __name__ == '__main__':
    unittest.main(verbosity=2)
