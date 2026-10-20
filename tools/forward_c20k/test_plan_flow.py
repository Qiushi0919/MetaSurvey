"""Positive plan integration regression with explicitly synthetic source data."""
import unittest
from tools.account20k_review.plan_flow import review

class PlanFlow(unittest.TestCase):
    def test_non_fen_protection_input_through_partial_fills(self):
        result=review()
        self.assertTrue(result['passed'],[x['name'] for x in result['checks'] if not x['passed']])
        order=result['artifacts']['prepare_return']['orders'][0]
        self.assertEqual(order['limit_price'],'12.34')
