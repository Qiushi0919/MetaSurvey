"""Synthetic arithmetic/scope cases only; no local PDFs or network."""
import copy
import unittest
from tools.e2e_history.research_factors import business_result, concentration_result, evaluate, independent_recompute


class ResearchFactorsTests(unittest.TestCase):
    def business(self):
        return {'state': 'VERIFIED_COMPATIBLE_REPORTED_SEGMENT', 'numerator': '60',
                'unit': 'CNY', 'period': 'FY2025', 'external_revenue_compatible': True,
                'denominator': {'value': '100', 'unit': 'CNY', 'period': 'FY2025'}}

    def customer(self, mode='REPORTED_LARGEST', percent='25.00'):
        return {'state': mode, 'reported_percent': percent, 'basis': 'SYNTHETIC_ANNUAL_SALES'}

    def test_business_share_is_not_complete_factor(self):
        row = business_result(self.business())
        self.assertEqual(row['exposure_subfactor'], '60.0000')
        self.assertIsNone(row['complete_sector_benefit_score'])

    def test_mixed_voltage_missing_not_zero(self):
        row = business_result({'state': 'UNKNOWN', 'reason': 'MIXED_VOLTAGE'})
        self.assertIsNone(row['share']); self.assertIsNone(row['exposure_subfactor'])

    def test_wrong_units_rejected(self):
        fact = self.business(); fact['unit'] = 'TEN_THOUSAND_CNY'
        with self.assertRaisesRegex(ValueError, 'INCOMPATIBLE'): business_result(fact)

    def test_wrong_period_rejected(self):
        fact = self.business(); fact['denominator']['period'] = 'FY2024'
        with self.assertRaisesRegex(ValueError, 'INCOMPATIBLE'): business_result(fact)

    def test_unresolved_eliminations_rejected(self):
        fact = self.business(); fact['external_revenue_compatible'] = False
        with self.assertRaisesRegex(ValueError, 'INCOMPATIBLE'): business_result(fact)

    def test_numerator_above_denominator_not_clipped(self):
        fact = self.business(); fact['numerator'] = '101'
        with self.assertRaisesRegex(ValueError, 'OUT_OF_RANGE'): business_result(fact)

    def test_float_money_rejected(self):
        fact = self.business(); fact['numerator'] = 60.0
        with self.assertRaisesRegex(ValueError, 'DECIMAL_STRING'): business_result(fact)

    def test_largest_above_threshold_deducts_ten(self):
        self.assertEqual(concentration_result(self.customer(percent='60.00'))['deduction'], '10')

    def test_top_five_above_threshold_does_not_prove_largest(self):
        result = concentration_result(self.customer('TOP5_UPPER_BOUND', '60.00'))
        self.assertEqual(result['state'], 'UNKNOWN'); self.assertIsNone(result['deduction'])

    def test_top_five_bound_keeps_exact_largest_unknown(self):
        result = concentration_result(self.customer('TOP5_UPPER_BOUND', '30.00'))
        self.assertEqual(result['deduction'], '0'); self.assertIsNone(result['largest_share'])

    def test_rounded_fifty_cannot_prove_strict_inequality(self):
        self.assertIsNone(concentration_result(self.customer(percent='50.00'))['deduction'])

    def test_missing_risk_not_absent(self):
        self.assertIsNone(concentration_result({'state': 'UNKNOWN', 'reason': 'NO_SOURCE'})['deduction'])

    def test_no_above_requires_direct_statement(self):
        with self.assertRaisesRegex(ValueError, 'DIRECT_STATEMENT'):
            concentration_result({'state': 'EXPLICIT_NO_ABOVE'})

    def test_only_current_scope_accepted(self):
        with self.assertRaisesRegex(ValueError, 'INPUT_SCOPE'):
            evaluate({'kind': 'E2ENewResearchFactorInputs', 'version': '1.0.0', 'historical_visibility_proven': True})

    def test_result_after_freeze_and_independent_fraction(self):
        pack = {'kind': 'E2ENewResearchFactorInputs', 'version': '1.0.0', 'productionGate': False,
                'historical_visibility_proven': False, 'recorded_at': '2026-10-14T09:00:00+00:00',
                'method_frozen_at': '2026-10-14T08:00:00+00:00', 'method_hash': 'SYNTHETIC',
                'companies': [{'symbol': 'SYNTHETIC', 'name': 'SYNTHETIC', 'business': self.business(),
                               'concentration': self.customer(), 'audit_opinion': {'state': 'UNKNOWN'}}]}
        result = evaluate(pack)
        reviewed = independent_recompute(pack, result)
        self.assertEqual(reviewed['companies'][0]['business_share_exact_fraction'], '3/5')
        self.assertIsNone(result['companies'][0]['complete_seven_factor_score'])
        damaged = copy.deepcopy(result); damaged['companies'][0]['customer_concentration']['deduction'] = '10'
        with self.assertRaisesRegex(ValueError, 'INDEPENDENT_CUSTOMER'):
            independent_recompute(pack, damaged)
        pack['recorded_at'] = '2026-10-14T07:00:00+00:00'
        with self.assertRaisesRegex(ValueError, 'METHOD_NOT_FROZEN'): evaluate(pack)
