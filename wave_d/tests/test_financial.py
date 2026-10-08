"""Synthetic-only independent financial boundary regression cases."""
from copy import deepcopy
from decimal import getcontext, ROUND_DOWN
import unittest

from wave_d.financial import financial_features


SYMBOL = '603993.SH'


def observation(api, ordinal=0, period='20260630', **fields):
    """Deliberately synthetic values/refs, never production/account defaults."""
    values = {'ts_code': SYMBOL}
    if api == 'daily_basic':
        values['trade_date'] = period
    else:
        values.update(end_date=period, ann_date='20260701')
    if api in ('income', 'balancesheet', 'cashflow'):
        values.update(report_type='1', comp_type='1', update_flag='0')
    values.update(fields)
    return {
        'api_name': api, 'values': values,
        'source_ref': {
            'origin': 'SYNTHETIC_FINANCIAL_REGRESSION_NOT_PRODUCTION',
            'request_id': 'synthetic-' + api,
            'request_fingerprint': 'a' * 64,
            'raw_sha256': 'b' * 64, 'row_ordinal': ordinal,
            'retrieved_at': '2026-10-06T04:00:00.000000001Z',
            'available_at': '2026-10-06T04:00:00.000000001Z',
            'published_at': None,
        },
    }


def run(rows):
    features, conflicts, warnings = financial_features(rows, SYMBOL)
    return {feature['name']: feature for feature in features}, conflicts, warnings


def matched():
    return [
        observation('income', revenue='200', total_revenue='240', oper_cost='120',
                    n_income='100', n_income_attr_p='70'),
        observation('cashflow', n_cashflow_act='120', net_profit='100',
                    c_pay_acq_const_fiolta='30'),
        observation('balancesheet', total_assets='500', total_liab='200',
                    total_hldr_eqy_inc_min_int='300', accounts_receiv='40',
                    inventories='60', money_cap='80'),
        observation('income', 1, '20250630', revenue='100', n_income='80',
                    ann_date='20250701'),
    ]


class FinancialBoundaryTests(unittest.TestCase):
    def test_empty_is_unknown_and_contains_no_account_defaults(self):
        features, conflicts, warnings = run([])
        self.assertTrue(all(f['state'] == 'UNKNOWN' and f['value'] is None for f in features.values()))
        self.assertFalse(conflicts)
        self.assertIn('WAVE_D_CURRENT_OBSERVED_NOT_HISTORICAL_PIT', warnings)
        self.assertEqual(len(features), 34)
        self.assertTrue({'real_account_capital', 'account_profile', 'commission_rate',
                         'risk_limit', 'order_amount'}.isdisjoint(features))

    def test_matching_cumulative_statements_independent_expected_results(self):
        features, _, _ = run(matched())
        expected = {
            'derived_revenue_yoy': '100.000000',
            'derived_consolidated_profit_yoy': '25.000000',
            'cash_conversion_ratio': '1.200000',
            'cash_after_capex_proxy': '90.000000',
            'debt_ratio_pct': '40.000000',
            'receivables_to_revenue_ratio': '0.200000',
            'inventory_to_revenue_ratio': '0.300000',
        }
        for name, value in expected.items():
            with self.subTest(name=name):
                self.assertEqual(features[name]['value'], value)
                self.assertEqual(features[name]['state'], 'DERIVED')
                self.assertEqual(features[name]['period'], '20260630')

    def test_latest_valuation_is_source_ttm_and_not_synthesized(self):
        rows = [observation('daily_basic', period='20260929', pe_ttm='12'),
                observation('daily_basic', 1, '20260930', pe_ttm='14', total_mv='123', total_share='42')]
        features, _, _ = run(rows)
        self.assertEqual(features['source_pe_ttm']['value'], '14.000000')
        self.assertEqual(features['source_pe_ttm']['state'], 'OBSERVED')
        self.assertIn('NOT_INDEPENDENTLY_CONSTRUCTED', features['source_pe_ttm']['formula'])
        self.assertEqual(features['source_total_mv']['unit'], 'SOURCE_DECLARED_WAN_CNY_UNVERIFIED_GATEWAY')
        self.assertEqual(features['source_total_share']['unit'], 'SOURCE_DECLARED_WAN_SHARES_UNVERIFIED_GATEWAY')

    def test_distinct_revision_blocks_entire_statement_period(self):
        rows = matched() + [observation('income', 2, revenue='201', n_income='100', update_flag='1')]
        features, conflicts, _ = run(rows)
        self.assertEqual(features['source_revenue']['state'], 'CONFLICT')
        self.assertEqual(features['source_consolidated_net_profit']['state'], 'CONFLICT')
        self.assertEqual(features['cash_conversion_ratio']['state'], 'CONFLICT')
        self.assertTrue(any(':income:20260630:1:1:revenue' in c for c in conflicts))

    def test_equal_decimal_lexical_variants_are_not_revision_conflict(self):
        rows = [observation('income', revenue='100'),
                observation('income', 1, revenue='100.000', update_flag='1')]
        features, conflicts, _ = run(rows)
        self.assertEqual(features['source_revenue']['value'], '100.000000')
        self.assertFalse(conflicts)
        self.assertEqual(len(features['source_revenue']['source_refs']), 2)

    def test_narrower_legacy_indicator_fields_do_not_erase_new_fields(self):
        rows = [observation('fina_indicator', roe='8', netprofit_yoy='5'),
                observation('fina_indicator', 1, roe='8', netprofit_yoy='5', or_yoy='7', grossprofit_margin='20')]
        features, conflicts, _ = run(rows)
        self.assertFalse(conflicts)
        self.assertEqual(features['source_revenue_yoy']['value'], '7.000000')
        self.assertEqual(features['source_gross_margin']['value'], '20.000000')

    def test_null_history_does_not_replace_observed_non_null(self):
        rows = [observation('income', revenue=None), observation('income', 1, revenue='100')]
        features, conflicts, _ = run(rows)
        self.assertFalse(conflicts)
        self.assertEqual(features['source_revenue']['value'], '100.000000')
        self.assertEqual(len(features['source_revenue']['source_refs']), 2)

    def test_update_flag_is_never_revision_order(self):
        rows = [observation('fina_indicator', roe='8', update_flag='0'),
                observation('fina_indicator', 1, roe='10', update_flag='1')]
        forward = run(rows)
        reverse = run(list(reversed(rows)))
        self.assertEqual(forward, reverse)
        self.assertEqual(forward[0]['source_roe']['state'], 'CONFLICT')

    def test_historical_conflict_is_preserved_without_replacing_latest(self):
        rows = [observation('income', revenue='200'),
                observation('income', 1, '20250630', revenue='100', ann_date='20250701'),
                observation('income', 2, '20250630', revenue='101', ann_date='20250701')]
        features, conflicts, _ = run(rows)
        self.assertEqual(features['source_revenue']['state'], 'OBSERVED')
        self.assertEqual(features['derived_revenue_yoy']['state'], 'CONFLICT')
        self.assertTrue(any('20250630' in code for code in conflicts))

    def test_input_refs_and_rows_are_not_mutated_or_exposed_by_alias(self):
        rows = matched()
        before = deepcopy(rows)
        features, _, _ = run(rows)
        features['source_revenue']['source_refs'][0]['origin'] = 'changed-output-only'
        self.assertEqual(rows, before)

    def test_wrong_symbol_does_not_contribute_or_conflict(self):
        rows = [observation('income', revenue='100'),
                observation('income', 1, ts_code='600312.SH', revenue='999')]
        features, conflicts, warnings = run(rows)
        self.assertEqual(features['source_revenue']['value'], '100.000000')
        self.assertFalse(conflicts)
        self.assertIn('WAVE_D_SYMBOL_MISMATCH:income', warnings)

    def test_non_consolidated_and_company_type_versions_are_preserved_but_excluded(self):
        rows = [observation('income', revenue='100'),
                observation('income', 1, revenue='999', report_type='2'),
                observation('income', 2, revenue='888', comp_type='2')]
        saved = deepcopy(rows)
        features, conflicts, warnings = run(rows)
        self.assertEqual(features['source_revenue']['value'], '100.000000')
        self.assertFalse(conflicts)
        self.assertEqual(rows, saved)
        self.assertIn('WAVE_D_NON_PRIMARY_STATEMENT_SCOPE_PRESERVED:income', warnings)

    def test_latest_income_and_cash_period_mismatch_blocks_cash_ratio(self):
        rows = [observation('income', n_income='100'),
                observation('cashflow', 1, '20260331', net_profit='20', n_cashflow_act='30')]
        feature = run(rows)[0]['cash_conversion_ratio']
        self.assertEqual(feature['state'], 'UNKNOWN')
        self.assertIn('WAVE_D_STATEMENT_PERIOD_MISMATCH', feature['reason_codes'])

    def test_zero_profit_denominator_is_unknown(self):
        feature = run([observation('cashflow', net_profit='0', n_cashflow_act='100')])[0]['cash_conversion_ratio']
        self.assertIsNone(feature['value'])
        self.assertIn('WAVE_D_NON_POSITIVE_CONSOLIDATED_PROFIT', feature['reason_codes'])

    def test_negative_profit_denominator_is_unknown(self):
        feature = run([observation('cashflow', net_profit='-10', n_cashflow_act='100')])[0]['cash_conversion_ratio']
        self.assertEqual(feature['state'], 'UNKNOWN')

    def test_parent_attributable_profit_is_not_cash_conversion_denominator(self):
        rows = [observation('income', n_income='100', n_income_attr_p='1'),
                observation('cashflow', net_profit='100', n_cashflow_act='120')]
        feature = run(rows)[0]['cash_conversion_ratio']
        self.assertEqual(feature['value'], '1.200000')
        self.assertIn('NEVER_PARENT_PROFIT', feature['formula'])

    def test_cross_product_profit_mismatch_is_explicit_conflict(self):
        rows = [observation('income', n_income='100'),
                observation('cashflow', net_profit='80', n_cashflow_act='120')]
        features, conflicts, _ = run(rows)
        self.assertEqual(features['cash_conversion_ratio']['state'], 'CONFLICT')
        self.assertTrue(any('CROSS_PRODUCT_CONSOLIDATED_PROFIT_MISMATCH' in code for code in conflicts))

    def test_missing_cash_profit_uses_only_matched_consolidated_income(self):
        rows = [observation('income', n_income='100', n_income_attr_p='1'),
                observation('cashflow', net_profit=None, n_cashflow_act='120')]
        features, _, warnings = run(rows)
        self.assertEqual(features['cash_conversion_ratio']['value'], '1.200000')
        self.assertIn('WAVE_D_CASHFLOW_PROFIT_ABSENT_MATCHED_INCOME_DENOMINATOR', warnings)

    def test_cash_only_ratio_is_labeled_cross_product_check_unavailable(self):
        features, _, warnings = run([observation('cashflow', net_profit='100', n_cashflow_act='120')])
        self.assertEqual(features['cash_conversion_ratio']['value'], '1.200000')
        self.assertIn('WAVE_D_CROSS_PRODUCT_PROFIT_CHECK_UNAVAILABLE', warnings)

    def test_only_parent_profit_does_not_fill_missing_consolidated_profit(self):
        features, _, _ = run([observation('income', n_income_attr_p='100'),
                             observation('cashflow', n_cashflow_act='120')])
        self.assertEqual(features['cash_conversion_ratio']['state'], 'UNKNOWN')

    def test_capital_payment_proxy_is_not_declared_free_cash_flow(self):
        features, _, _ = run(matched())
        self.assertIn('PROXY_NOT_FREE_CASH_FLOW', features['cash_after_capex_proxy']['formula'])
        feature = run([observation('cashflow', n_cashflow_act='100', c_pay_acq_const_fiolta='-1')])[0]['cash_after_capex_proxy']
        self.assertIsNone(feature['value'])

    def test_negative_cfo_is_a_real_negative_ratio_with_positive_profit(self):
        feature = run([observation('cashflow', net_profit='100', n_cashflow_act='-25')])[0]['cash_conversion_ratio']
        self.assertEqual(feature['value'], '-0.250000')

    def test_negative_or_zero_prior_year_base_does_not_get_fake_growth(self):
        for prior in ('0', '-100'):
            with self.subTest(prior=prior):
                rows = [observation('income', revenue='100'),
                        observation('income', 1, '20250630', revenue=prior, ann_date='20250701')]
                feature = run(rows)[0]['derived_revenue_yoy']
                self.assertEqual(feature['state'], 'UNKNOWN')
                self.assertIn('WAVE_D_NON_POSITIVE_PRIOR_YEAR_BASE', feature['reason_codes'])

    def test_future_publication_literal_is_not_eligible(self):
        features, _, warnings = run([observation('income', revenue='100', ann_date='20261007')])
        self.assertIsNone(features['source_revenue']['value'])
        self.assertIn('WAVE_D_FUTURE_SOURCE_DATE:income', warnings)

    def test_invalid_calendar_date_is_not_eligible(self):
        features, _, warnings = run([observation('income', period='20260230', revenue='100')])
        self.assertIsNone(features['source_revenue']['value'])
        self.assertIn('WAVE_D_SOURCE_DATE_OR_CLOCK_INVALID:income', warnings)

    def test_naive_capture_clock_does_not_get_timezone_assumption(self):
        row = observation('income', revenue='100')
        row['source_ref']['retrieved_at'] = '2026-10-06T04:00:00'
        self.assertIsNone(run([row])[0]['source_revenue']['value'])

    def test_missing_capture_clock_is_not_defaulted(self):
        row = observation('income', revenue='100')
        del row['source_ref']['retrieved_at']
        self.assertIsNone(run([row])[0]['source_revenue']['value'])

    def test_non_standard_financial_period_does_not_become_ytd(self):
        feature = run([observation('income', period='20260629', revenue='100')])[0]['source_revenue']
        self.assertIsNone(feature['value'])

    def test_future_financial_period_is_not_eligible(self):
        feature = run([observation('income', period='20261231', revenue='100')])[0]['source_revenue']
        self.assertIsNone(feature['value'])

    def test_cumulative_quarter_fact_is_never_promoted_to_ttm(self):
        feature = run([observation('income', revenue='100')])[0]['source_revenue']
        self.assertIn('CUMULATIVE_YTD', feature['formula'])
        self.assertIn('NOT_TTM', feature['formula'])
        self.assertEqual(feature['unit'], 'PROVIDER_FINANCIAL_SCALE_UNVERIFIED')

    def test_stock_flow_ratio_requires_same_balance_and_income_end_date(self):
        rows = [observation('income', revenue='100'),
                observation('balancesheet', period='20260331', accounts_receiv='50')]
        feature = run(rows)[0]['receivables_to_revenue_ratio']
        self.assertEqual(feature['state'], 'UNKNOWN')
        self.assertIn('WAVE_D_STATEMENT_PERIOD_MISMATCH', feature['reason_codes'])

    def test_zero_assets_denominator_is_unknown_not_zero_debt_ratio(self):
        feature = run([observation('balancesheet', total_assets='0', total_liab='100')])[0]['debt_ratio_pct']
        self.assertIsNone(feature['value'])

    def test_reported_growth_remains_separate_from_derived_comparable_growth(self):
        rows = matched() + [observation('fina_indicator', or_yoy='99', netprofit_yoy='88')]
        features, _, _ = run(rows)
        self.assertEqual(features['source_revenue_yoy']['value'], '99.000000')
        self.assertEqual(features['derived_revenue_yoy']['value'], '100.000000')
        self.assertEqual(features['source_netprofit_yoy']['value'], '88.000000')
        self.assertEqual(features['derived_consolidated_profit_yoy']['value'], '25.000000')

    def test_binary_float_and_nonfinite_source_numbers_block_feature(self):
        for number in (0.1, True, 100, 'NaN', 'Infinity', 'not-a-number'):
            with self.subTest(type=type(number).__name__):
                feature = run([observation('income', revenue=number)])[0]['source_revenue']
                self.assertIsNone(feature['value'])
                self.assertIn('WAVE_D_INVALID_SOURCE_DECIMAL', feature['reason_codes'])

    def test_decimal_context_is_isolated_from_caller_precision_and_rounding(self):
        ctx = getcontext()
        old_precision, old_rounding = ctx.prec, ctx.rounding
        try:
            ctx.prec, ctx.rounding = 3, ROUND_DOWN
            rows = [observation('cashflow', net_profit='3', n_cashflow_act='1')]
            self.assertEqual(run(rows)[0]['cash_conversion_ratio']['value'], '0.333333')
            self.assertEqual((ctx.prec, ctx.rounding), (3, ROUND_DOWN))
        finally:
            ctx.prec, ctx.rounding = old_precision, old_rounding

    def test_half_even_display_and_negative_zero_are_explicit(self):
        rows = [observation('income', revenue='1.2345665', n_income='-0.0000001')]
        features, _, _ = run(rows)
        self.assertEqual(features['source_revenue']['value'], '1.234566')
        self.assertEqual(features['source_consolidated_net_profit']['value'], '0.000000')

    def test_conflict_detection_precedes_six_decimal_display_rounding(self):
        rows = [observation('income', revenue='1.00000001'),
                observation('income', 1, revenue='1.00000002')]
        self.assertEqual(run(rows)[0]['source_revenue']['state'], 'CONFLICT')

    def test_derived_display_range_failure_is_unknown_without_fake_zero(self):
        rows = [observation('cashflow', net_profit='1e-64', n_cashflow_act='1')]
        feature = run(rows)[0]['cash_conversion_ratio']
        self.assertEqual(feature['state'], 'UNKNOWN')
        self.assertIn('WAVE_D_DERIVED_DECIMAL_RANGE_INVALID', feature['reason_codes'])

    def test_cross_product_invalid_decimal_cannot_be_ignored(self):
        rows = [observation('cashflow', net_profit='100', n_cashflow_act='120'),
                observation('income', n_income='NaN')]
        feature = run(rows)[0]['cash_conversion_ratio']
        self.assertIsNone(feature['value'])

    def test_yoy_refs_include_both_comparable_period_evidence(self):
        features, _, _ = run(matched())
        refs = features['derived_revenue_yoy']['source_refs']
        self.assertEqual({r['row_ordinal'] for r in refs}, {0, 1})

    def test_unknown_symbol_and_non_list_input_are_not_accepted(self):
        with self.assertRaisesRegex(ValueError, 'WAVE_D_FINANCIAL_SCOPE_INVALID'):
            financial_features([], '000001.SZ')
        with self.assertRaisesRegex(ValueError, 'WAVE_D_FINANCIAL_SCOPE_INVALID'):
            financial_features((), SYMBOL)


if __name__ == '__main__':
    unittest.main()
