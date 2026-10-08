"""Unapproved synthetic formula acceptance/rejection cases, not strategy results."""
import unittest
from decimal import Decimal
from .reference_math import (SCOPE,D,wacc,normal_ebitda,weak_percentile,
    fair_equity_price,scenario_expectation,uncertainty,edge,incremental,
    score,grade,mature_label,probability_bucket,nearest_rank,joint_block_indices,research_only_score,instant)


def calc(fn,*args,**kwargs):
    if fn is wacc:
        kw = {'nci_value':'0','nci_cost_of_equity':None,**kwargs}
    elif fn is score:
        kw = {'probability_applicable':True,'probability_calibrated':True,**kwargs}
    else:kw=kwargs
    return fn(*args,scope=SCOPE,**kw)


class Arithmetic(unittest.TestCase):
    def test_scope_cannot_be_actual(self):
        with self.assertRaises(ValueError):
            edge('610','70','120',scope='ACTUAL')

    def test_unapproved_scope_required(self):
        with self.assertRaises(ValueError):edge('610','70','120')

    def test_decimal_not_float(self):
        with self.assertRaises(ValueError):D(0.1)

    def test_nonfinite_decimal_rejected(self):
        for v in ['NaN','Infinity','-Infinity']:
            with self.assertRaises(ValueError):D(v)

    def test_wacc_with_tax_shield(self):
        r=calc(wacc,'.03','1.3','.05','.01','70','30','.25')
        self.assertEqual(r['beta'],D('1.2'))
        self.assertEqual(r['wacc'],D('.072'))

    def test_zero_debt_not_a_broker_default(self):
        self.assertEqual(calc(wacc,'.03','1.3','.05','.01','100','0','.25')['wacc'],D('.09'))

    def test_missing_real_tax_not_zero(self):
        with self.assertRaises(Exception):calc(wacc,'.03','1.3','.05','.01','70','30','UNSET_REQUIRED')

    def test_negative_shrunk_beta_rejects(self):
        with self.assertRaises(ValueError):calc(wacc,'.03','-2','.05','.01','70','30','.25')

    def test_cycle_includes_loss(self):
        r=calc(normal_ebitda,['100']*5,['-10','10','15','20','30'],'1000')
        self.assertEqual(r['median_margin'],D('.15'))
        self.assertEqual(r['normalized_ebitda'],D('150'))

    def test_cycle_requires_full_five_years(self):
        with self.assertRaises(ValueError):calc(normal_ebitda,['100']*4,['10']*4,'1000')

    def test_cycle_nonpositive_does_not_force_positive(self):
        with self.assertRaises(ValueError):calc(normal_ebitda,['100']*5,['-10']*5,'1000')

    def test_cycle_zero_revenue_rejected(self):
        with self.assertRaises(ValueError):calc(normal_ebitda,['100','100','0','100','100'],['10']*5,'1000')

    def test_percentile_ties_are_weak_rank_one(self):
        self.assertEqual(calc(weak_percentile,['2']*1260,'2'),1)

    def test_percentile_cannot_collect_1259_valid_values(self):
        with self.assertRaises(ValueError):calc(weak_percentile,['2']*1259,'2')

    def test_percentile_current_session_in_window(self):
        self.assertEqual(calc(weak_percentile,['2']*1259+['1.5'],'1.5'),
                         D('0.00079365079365079365079365079365079365079365079365079'))

    def test_percentile_current_not_in_window_rejected(self):
        with self.assertRaises(ValueError):calc(weak_percentile,['2']*1260,'1.5')

    def test_enterprise_equity_bridge(self):
        r=calc(fair_equity_price,'8','150','80','20','0','10','100')
        self.assertEqual(r['fair_equity'],1110)
        self.assertEqual(r['fair_price'],D('11.1'))

    def test_cash_rich_net_debt_not_clipped(self):
        r=calc(fair_equity_price,'8','150','-80','20','0','10','100')
        self.assertEqual(r['fair_equity'],1270)

    def test_no_fake_positive_fair_value(self):
        with self.assertRaises(ValueError):calc(fair_equity_price,'1','10','100','0','0','0','100')

    def test_integer_shares_required(self):
        with self.assertRaises(ValueError):calc(fair_equity_price,'8','150','80','20','0','10','100.5')

    def test_expected_return_can_include_downside(self):
        self.assertEqual(calc(scenario_expectation,['.5','.3','.2'],['1400','100','-600']),610)

    def test_bad_probability_sum_not_normalized_silently(self):
        with self.assertRaises(ValueError):calc(scenario_expectation,['.5','.3','.3'],['1400','100','-600'])

    def test_probability_negative_rejected(self):
        with self.assertRaises(ValueError):calc(scenario_expectation,['1.2','-.2','0'],['1400','100','-600'])

    def test_buffer_components_explicit(self):
        self.assertEqual(calc(uncertainty,'610','530','40'),120)

    def test_no_negative_buffer_for_pessimistic_validation(self):
        self.assertEqual(calc(uncertainty,'610','630','-10'),0)

    def test_net_ratio_differs_from_gross_ratio(self):
        r=calc(edge,'610','70','120')
        self.assertEqual(r['net_bps'],420)
        self.assertEqual(r['net_to_cost'],6)
        self.assertFalse(r['actual_authority'])
        self.assertNotEqual(r['net_to_cost'],D('610')/70)

    def test_zero_cost_is_not_infinite_pass(self):
        with self.assertRaises(ValueError):calc(edge,'610','0','120')

    def test_buffer_missing_or_negative_rejected(self):
        with self.assertRaises(ValueError):calc(edge,'610','70','-1')

    def test_incremental_equality_rejected(self):
        r=calc(incremental,'100','120','10','25','5','10')
        self.assertEqual(r['delta_net'],0)
        self.assertFalse(r['strict_cash_comparison'])

    def test_incremental_not_all_price_improvement_is_profit(self):
        r=calc(incremental,'100','120','10','26','5','10')
        self.assertEqual(r['delta_net'],-1)
        self.assertFalse(r['strict_cash_comparison'])

    def test_negative_incremental_cost_has_null_ratio(self):
        r=calc(incremental,'100','110','20','15','5','5')
        self.assertEqual(r['delta_net'],15)
        self.assertIsNone(r['gross_to_incremental_cost'])

    def test_handoff_score_cost_units_are_bps(self):
        r=calc(score,{k:'90' for k in 'FSCTVLE'},'0','1000','35')
        self.assertEqual(r['research'],90)
        self.assertEqual(r['cost_penalty'],D('3.5'))
        self.assertEqual(r['final'],D('86.5'))

    def test_unknown_dimension_not_zero(self):
        with self.assertRaises(Exception):calc(score,{k:None for k in 'FSCTVLE'},'0','1000','35')


class Grades(unittest.TestCase):
    def grade(self, final, **kw):
        kw.setdefault('probability_calibrated',True)
        kw.setdefault('probability_applicable',True)
        kw.setdefault('common_pass',True)
        kw.setdefault('all_timing_pass',True)
        return calc(grade,final,'90','90','100','100',**kw)

    def test_continuous_score_no_gap(self):
        for final,expected in [('54.9999','X'),('55','C'),('67.9999','C'),('68','B'),
                               ('77.9999','B'),('78','A'),('84.9999','A'),('85','A')]:
            self.assertEqual(self.grade(final),expected)

    def test_unknown_separate_from_x(self):
        self.assertEqual(self.grade('99',known=False),'UNSET_REQUIRED')

    def test_trusted_hard_block_dominates_high_score(self):
        self.assertEqual(self.grade('99',trusted_hard_block=True),'X')

    def test_trusted_hard_block_and_other_unknown(self):
        self.assertEqual(self.grade('99',trusted_hard_block=True,known=False),'X')

    def test_s_requires_all_actual_rule_booleans_in_synthetic_example(self):
        self.assertEqual(self.grade('85',common_pass=True,all_timing_pass=True,edge_criteria_pass=True),'S')

    def test_high_timing_partial_match_does_not_make_s(self):
        self.assertEqual(calc(grade,'90','90','90','83.333','100',common_pass=True,
                              all_timing_pass=False,edge_criteria_pass=True,probability_calibrated=True,probability_applicable=True),'UNSET_REQUIRED')

    def test_incomplete_quality_cap_even_high_final(self):
        self.assertEqual(calc(grade,'90','79','90','100','100',common_pass=True,
                              all_timing_pass=True,edge_criteria_pass=True,probability_calibrated=True,probability_applicable=True),'B')

    def test_known_calibrated_but_small_edge_not_s(self):
        self.assertEqual(self.grade('99',common_pass=True,all_timing_pass=True,edge_criteria_pass=False),'A')

    def test_uncalibrated_probability_not_computable_grade(self):
        self.assertEqual(self.grade('99',common_pass=True,all_timing_pass=True,
                                    edge_criteria_pass=True,probability_calibrated=False),'UNSET_REQUIRED')


class LabelMaturity(unittest.TestCase):
    def test_fully_matured_at_fit(self):
        self.assertTrue(calc(mature_label,'2020-01-01T00:00:00Z','2020-03-01T00:00:00Z',
                             '2020-03-02T00:00:00Z','2020-03-02T00:00:00Z'))

    def test_delayed_exit_crosses_fit_cutoff(self):
        self.assertFalse(calc(mature_label,'2020-01-01T00:00:00Z','2020-03-01T00:00:00Z',
                              '2020-03-02T00:00:00Z','2020-02-20T00:00:00Z'))

    def test_exited_but_not_available_at_fit(self):
        self.assertFalse(calc(mature_label,'2020-01-01T00:00:00Z','2020-03-01T00:00:00Z',
                              '2020-03-03T00:00:00Z','2020-03-02T00:00:00Z'))

    def test_date_only_not_midnight(self):
        with self.assertRaises(ValueError):calc(mature_label,'2020-01-01','2020-03-01','2020-03-02','2020-03-02')

    def test_equivalent_timezone_cutoff(self):
        self.assertTrue(calc(mature_label,'2020-01-01T00:00:00Z','2020-03-01T00:00:00Z',
                             '2020-03-02T08:00:00+08:00','2020-03-02T00:00:00Z'))



class ReviewRepairs(unittest.TestCase):
    def test_nci_capital_changes_quality_comparison(self):
        r=calc(wacc,'.03','1.3','.05','.01','70','30','.25',
               nci_value='70',nci_cost_of_equity='.09')
        self.assertGreater(r['wacc'],D('.075'))
        self.assertEqual(r['wacc'],D('0.079411764705882352941176470588235294117647058823529'))

    def test_nonzero_nci_unknown_cost_blocks(self):
        with self.assertRaises(ValueError):calc(wacc,'.03','1.3','.05','.01','70','30','.25',
                                                 nci_value='70',nci_cost_of_equity=None)

    def test_missing_nci_cannot_default_zero(self):
        with self.assertRaises(TypeError):wacc('.03','1.3','.05','.01','70','30','.25',scope=SCOPE)

    def test_zero_nci_has_no_implied_capital_cost(self):
        with self.assertRaises(ValueError):calc(wacc,'.03','1.3','.05','.01','70','30','.25',
                                                nci_value='0',nci_cost_of_equity='.09')

    def test_negative_nci_blocks(self):
        with self.assertRaises(ValueError):calc(wacc,'.03','1.3','.05','.01','70','30','.25',
                                                nci_value='-1',nci_cost_of_equity='.09')

    def test_one_nanosecond_future_label_is_not_mature(self):
        self.assertFalse(calc(mature_label,'2020-01-01T00:00:00Z','2020-03-01T00:00:00Z',
                              '2020-03-02T00:00:00.000000001Z','2020-03-02T00:00:00.000000000Z'))

    def test_nanosecond_equality_with_other_offset(self):
        self.assertTrue(calc(mature_label,'2020-01-01T00:00:00Z','2020-03-01T00:00:00Z',
                             '2020-03-02T08:00:00.123456789+08:00','2020-03-02T00:00:00.123456789Z'))

    def test_unsupported_precision_is_not_truncated(self):
        with self.assertRaises(ValueError):calc(mature_label,'2020-01-01T00:00:00Z','2020-03-01T00:00:00Z',
                                                '2020-03-02T00:00:00.0000000001Z','2020-03-02T00:00:00Z')

    def test_unknown_offset_rejected(self):
        with self.assertRaises(ValueError):calc(mature_label,'2020-01-01T00:00:00Z','2020-03-01T00:00:00Z',
                                                '2020-03-02T00:00:00-00:00','2020-03-02T00:00:00Z')

    def test_off_domain_score_has_only_research_axis(self):
        r=calc(score,{k:'90' for k in 'FSCTVLE'},'0',None,None,probability_applicable=False)
        self.assertEqual(r['research'],90)
        self.assertIsNone(r['final']);self.assertIsNone(r['cost_penalty'])

    def test_domain_unknown_is_not_implicit_true(self):
        with self.assertRaises(ValueError):calc(score,{k:'90' for k in 'FSCTVLE'},'0','1000','35',
                                                probability_applicable=None)

    def test_calibrated_probability_does_not_prove_new_domain(self):
        self.assertEqual(calc(grade,'99','90','90','100','100',probability_calibrated=True,
                              probability_applicable=False,common_pass=True,all_timing_pass=True),
                         'UNSET_REQUIRED')

    def test_timing_failure_has_no_actionability_a(self):
        self.assertEqual(calc(grade,'99','90','90','0','100',probability_calibrated=True,
                              probability_applicable=True,common_pass=True,all_timing_pass=False),
                         'UNSET_REQUIRED')

    def test_research_gate_failure_has_no_actionability_a(self):
        self.assertEqual(calc(grade,'99','90','90','100','100',probability_calibrated=True,
                              probability_applicable=True,common_pass=False,all_timing_pass=True),
                         'UNSET_REQUIRED')


class FixedCalibrationProtocol(unittest.TestCase):
    def test_probability_bucket_edges(self):
        for p,expected in [('0',0),('.099999999',0),('.1',1),('.89999999',8),('.9',9),('1',9)]:
            self.assertEqual(calc(probability_bucket,p),expected)

    def test_bad_probability_not_clipped_to_a_bucket(self):
        for p in ['-.01','1.01']:
            with self.assertRaises(ValueError):calc(probability_bucket,p)

    def test_nearest_rank_not_interpolated(self):
        self.assertEqual(calc(nearest_rank,['3','1','2','4'],'.05'),1)
        self.assertEqual(calc(nearest_rank,['3','1','2','4'],'.51'),3)
        self.assertEqual(calc(nearest_rank,['3','1','2','4'],'1'),4)

    def test_undefined_quantile_is_failure(self):
        with self.assertRaises(ValueError):calc(nearest_rank,[],'.05')

    def test_joint_blocks_have_whole_consecutive_rows(self):
        draws=calc(joint_block_indices,10,4,3,20261008)
        self.assertEqual(len(draws),3)
        for indices in draws:
            self.assertEqual(len(indices),10)
            for start in (0,4,8):
                block=indices[start:start+4]
                self.assertEqual(block,tuple(range(block[0],block[0]+len(block))))
                self.assertLessEqual(block[-1],9)

    def test_same_frozen_runtime_seed_repeats(self):
        self.assertEqual(calc(joint_block_indices,10,4,3,20261008),
                         calc(joint_block_indices,10,4,3,20261008))

    def test_single_full_length_block_cannot_wrap(self):
        self.assertEqual(calc(joint_block_indices,4,4,2,20261008),[(0,1,2,3)]*2)

    def test_float_index_is_not_rounded(self):
        with self.assertRaises(ValueError):calc(joint_block_indices,10,4.1,3,20261008)


class ResearchAxis(unittest.TestCase):
    def test_timing_unknown_does_not_need_trade_probability_for_research(self):
        r=calc(research_only_score,{k:'90' for k in 'FSCVE'})
        self.assertEqual(r['research_priority'],'RESEARCH_PRIORITY_A')
        self.assertEqual(r['actionability_grade'],'UNSET_REQUIRED')
        self.assertFalse(r['actual_authority'])

    def test_research_unknown_not_zero(self):
        with self.assertRaises(ValueError):calc(research_only_score,{k:'UNSET_REQUIRED' for k in 'FSCVE'})

    def test_nonzero_nci_cannot_use_zero_cost(self):
        with self.assertRaises(ValueError):calc(wacc,'.03','1.3','.05','.01','70','30','.25',
                                                nci_value='70',nci_cost_of_equity='0')


class StrictOffsetRepairs(unittest.TestCase):
    def test_invalid_offset_minutes_cannot_normalize(self):
        for offset in ['+08:60','+08:99','-00:99']:
            with self.assertRaises(ValueError):instant('2020-01-01T00:00:00'+offset)

    def test_invalid_offset_hours_reject(self):
        for offset in ['+24:00','-99:59']:
            with self.assertRaises(ValueError):instant('2020-01-01T00:00:00'+offset)

    def test_valid_offset_minute_boundary_preserved(self):
        self.assertEqual(instant('2020-01-01T08:59:00+08:59'),instant('2020-01-01T00:00:00Z'))


if __name__ == '__main__':unittest.main()
