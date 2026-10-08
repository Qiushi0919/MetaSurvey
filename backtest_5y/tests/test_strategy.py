"""Prerequisite diagnostics use explicit fixtures, never a trading engine."""
import copy
import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from backtest_5y.interface import FAMILIES, SPEC_PATH, SPEC_SHA256, canonical, digest, frozen_spec
from backtest_5y.strategy import diagnose, financial_quarters


def prices(count=80):
    rows=[]
    for i in range(count):
        day=(date(2024,1,1)+timedelta(days=i)).isoformat()
        value=str(100+i)
        rows.append(dict(symbol='600312.SH',domain='PRICE',identity=day,event_date=day,
            retrieved_at='2026-10-08T08:00:00+00:00',published_at=None,available_at=None,first_visible_at=None,
            revision_id=None,raw_sha256='a'*64,raw_ref='FIXTURE_MEMORY',capture_id='fixture',row_ordinal=i,
            fields=dict(trade_date=day.replace('-',''),open=value,high=str(101+i),low=str(99+i),close=value,vol='100'),
            units={'state':'UNVERIFIED'},provenance={'classification':'SYNTHETIC_FIXTURE'}))
    return rows


def financial(periods):
    rows=[]
    for end,value in periods:
        rows.append(dict(symbol='600312.SH',domain='FINANCIAL_INCOME',identity=end,event_date=end,
            published_at=end+'T16:00:00+08:00',available_at=end+'T16:01:00+08:00',
            first_visible_at=end+'T16:02:00+08:00',revision_id='FIXTURE_V1',
            fields=dict(revenue=value,oper_cost=value,n_income=value,n_cashflow_act=value,ebitda=value,
                reporting_basis='CUMULATIVE_YTD'),
            units={k:'CNY' for k in ('currency','revenue','oper_cost','net_income','operating_cashflow','ebitda')},
            provenance={'classification':'SYNTHETIC_FIXTURE'}))
    return rows


class StrategyTests(unittest.TestCase):
    def eight_financial_quarters(self):
        return financial([(str(y)+'-'+end,str(v)) for y in (2022,2023) for end,v in
            (('03-31',10),('06-30',30),('09-30',60),('12-31',100))])

    def later_quarter_version(self, row):
        newer=copy.deepcopy(row)
        newer['revision_id']='NEW_BAD_BASIS_VERSION'
        newer.update(published_at='2024-01-15T16:00:00+08:00',available_at='2024-01-15T16:01:00+08:00',
                     first_visible_at='2024-01-15T16:02:00+08:00')
        return newer

    def test_real_price_components_without_decision_or_economics(self):
        result=diagnose(prices(), {'state':'NOT_COMPUTABLE','rows':[]})
        last=result['candidates'][-1]
        self.assertEqual(last['price_features']['values']['close'],'179')
        self.assertEqual(last['price_features']['values']['ma20'],'169.5')
        self.assertEqual(Decimal(last['price_features']['values']['ma60_slope_20']),Decimal('20'))
        self.assertEqual(set(last['families']),set(FAMILIES))
        self.assertTrue(all(f['state']=='NO_DECISION' for f in last['families'].values()))
        self.assertEqual(result['execution_state'],'ENGINE_NOT_RUN')
        self.assertEqual(result['economic_state'],'NOT_COMPUTABLE')
        self.assertTrue(all(v is None for v in result['economic_metrics'].values()))
        self.assertFalse(result['timing_ablation_authorized'])
        self.assertFalse(result['engine_called'])

    def test_future_poison_does_not_change_earlier_candidates(self):
        rows=prices()
        first=diagnose(rows,{'rows':[]})['candidates']
        poison=copy.deepcopy(rows[-1]);poison['event_date']='2024-04-01';poison['identity']='future'
        poison['fields']={'open':'NaN','secret_future_label':'WINNER'}
        after=diagnose(rows+[poison],{'rows':[]})['candidates'][:len(first)]
        self.assertEqual(first,after)
        self.assertNotIn('secret_future_label',str(after))

    def test_lineage_references_resolve_once(self):
        out=diagnose(prices(),{'rows':[]})
        self.assertEqual(len(out['lineage_catalog']),80)
        for c in out['candidates']:
            self.assertIn(c['common_blocker_ref'],out['common_blockers'])
            self.assertIn(c['prerequisite_ref'],out['prerequisite_snapshots'])
            self.assertTrue(set(c['price_features']['window_lineage_refs'])<=set(out['lineage_catalog']))

    def test_ytd_is_subtracted_and_consecutive_eight_required(self):
        periods=[(str(y)+'-'+end,str(v)) for y in (2022,2023) for end,v in
            (('03-31',10),('06-30',30),('09-30',60),('12-31',100))]
        out=financial_quarters(financial(periods),symbol='600312.SH',cutoff='2024-03-01T15:00:00+08:00')
        self.assertEqual(out['ttm']['revenue'],'100')
        self.assertEqual(out['ttm']['previous4_revenue'],'100')
        self.assertNotEqual(out['ttm']['revenue'],'200')
        self.assertFalse(out['historical_visibility_proven'])
        out=financial_quarters(financial(periods[1:]),symbol='600312.SH',cutoff='2024-03-01T15:00:00+08:00')
        self.assertIsNone(out['ttm'])
        self.assertIn('FINANCIAL_YTD_PRIOR_SAME_YEAR_OR_UNIT_MISSING',out['reason_codes'])

    def test_future_financial_publication_and_unknown_basis_are_not_used(self):
        rows=financial([('2023-03-31','10'),('2023-06-30','30')])
        rows[-1]['published_at']='2024-01-01T16:00:00+08:00'
        rows[-1]['available_at']='2024-01-01T16:01:00+08:00'
        rows[-1]['first_visible_at']='2024-01-01T16:02:00+08:00'
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2023-10-01T15:00:00+08:00')
        self.assertEqual(out['eligible_versions'],1)
        rows[0]['fields'].pop('reporting_basis')
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2023-10-01T15:00:00+08:00')
        self.assertIn('FINANCIAL_YTD_OR_DISCRETE_BASIS_UNPROVEN',out['reason_codes'])

    def test_recent_incomplete_quarter_cannot_be_replaced_by_older_complete_one(self):
        periods=[(str(y)+'-'+end,str(v)) for y in (2022,2023) for end,v in
            (('03-31',10),('06-30',30),('09-30',60),('12-31',100))]
        rows=financial(periods+[('2024-03-31','10')])
        for key in ('oper_cost','n_income','n_cashflow_act','ebitda'): rows[-1]['fields'].pop(key)
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertIsNone(out['ttm'])

    def test_latest_visible_quarter_with_no_flow_fields_cannot_disappear(self):
        rows=self.eight_financial_quarters()+financial([('2024-03-31','10')])
        rows[-1]['fields']={'reporting_basis':'CUMULATIVE_YTD'}
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertEqual(out['state'],'NOT_COMPUTABLE')
        self.assertIsNone(out['ttm'])
        self.assertEqual(out['quarter_dates'][-1],'2024-03-31')
        self.assertIn('FINANCIAL_LATEST4_PLUS_PREVIOUS4_COMPLETE_QUARTERS_MISSING',out['reason_codes'])

    def test_unknown_currency_reviewer_reproduction_cannot_compute(self):
        rows=self.eight_financial_quarters()
        for row in rows: row['units']={'currency':'UNKNOWN'}
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertEqual(out['state'],'NOT_COMPUTABLE')
        self.assertIsNone(out['ttm'])

    def test_discrete_quarter_mixed_currency_cannot_be_summed(self):
        rows=self.eight_financial_quarters()
        for row in rows:
            row['fields']['reporting_basis']='DISCRETE_QUARTER'
            row['units']={'currency':'CNY'}
        rows[-1]['units']={'currency':'USD'}
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertIsNone(out['ttm'])
        # Explicit field units must agree with the declared currency as well.
        rows=self.eight_financial_quarters();rows[-1]['units']['currency']='USD'
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertIsNone(out['ttm'])

    def test_unknown_unsupported_or_conflicting_field_units_block(self):
        for unit in ('UNKNOWN','USD','CNY_THOUSAND','CNY_MILLION','PERCENT','',None,{'currency':'CNY'}):
            with self.subTest(unit=unit):
                rows=self.eight_financial_quarters();rows[-1]['units']['revenue']=unit
                out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
                self.assertIsNone(out['ttm'])
        rows=self.eight_financial_quarters();rows[-1]['units'].update(net_income='CNY',n_income='USD')
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertIsNone(out['ttm'])

    def test_unknown_or_mixed_scale_cannot_compute(self):
        for scale in ('UNKNOWN','1000','1000000','0','-1',None,True):
            with self.subTest(scale=scale):
                rows=self.eight_financial_quarters();rows[-1]['units']['scale']=scale
                out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
                self.assertIsNone(out['ttm'])

    def test_valid_visible_version_does_not_hide_same_period_bad_unit(self):
        for bad in ({'revenue':'USD'}, {'scale':'UNKNOWN'}, {'currency':'USD'}):
            with self.subTest(bad=bad):
                rows=self.eight_financial_quarters();conflict=copy.deepcopy(rows[-1])
                conflict['units'].update(bad);conflict['revision_id']='FIXTURE_V2'
                rows.append(conflict)
                out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
                self.assertIsNone(out['ttm'])
                self.assertIn('FINANCIAL_VISIBLE_VERSION_UNIT_CONFLICT',out['reason_codes'])
        rows=self.eight_financial_quarters();conflict=copy.deepcopy(rows[-1])
        conflict['units']['revenue']='UNKNOWN';conflict['fields']['reporting_basis']='UNKNOWN'
        out=financial_quarters(rows+[conflict],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertIsNone(out['ttm'])

    def test_currency_alone_does_not_declare_field_amount_unit(self):
        rows=self.eight_financial_quarters()
        for row in rows: row['units']={'currency':'CNY'}
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertIsNone(out['ttm'])

    def test_supported_field_alias_units_and_explicit_base_scale(self):
        rows=self.eight_financial_quarters()
        for row in rows:
            row['units']={'revenue':'CNY','oper_cost':'CNY','n_income':'CNY','n_cashflow_act':'CNY','ebitda':'CNY','scale':'1'}
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertEqual(out['ttm']['revenue'],'100')
        self.assertFalse(out['historical_visibility_proven'])

    def test_future_unknown_units_do_not_taint_earlier_visible_window(self):
        rows=self.eight_financial_quarters()
        future=financial([('2024-03-31','10')])[0]
        future['units']={'currency':'UNKNOWN'}
        for key in ('published_at','available_at','first_visible_at'):
            future[key]='2024-06-02T16:00:00+08:00'
        before=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        after=financial_quarters(rows+[future],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertEqual(before,after)

    def test_later_unknown_basis_version_cannot_restore_old_good_cells(self):
        rows=self.eight_financial_quarters();bad=self.later_quarter_version(rows[-1])
        bad['fields'].update(reporting_basis='UNKNOWN',revenue='999')
        out=financial_quarters(rows+[bad],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertEqual(out['state'],'NOT_COMPUTABLE')
        self.assertIsNone(out['ttm'])
        self.assertIn('FINANCIAL_VISIBLE_VERSION_BASIS_CONFLICT',out['cell_conflicts']['2023-12-31']['revenue'])
        for value in (None,'',[],{}):
            with self.subTest(value=value):
                bad=self.later_quarter_version(rows[-1]);bad['fields']['reporting_basis']=value
                bad['provenance']['reporting_basis']='CUMULATIVE_YTD'
                out=financial_quarters(rows+[bad],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
                self.assertIsNone(out['ttm'])

    def test_later_nonnumeric_version_blocks_old_numeric_value(self):
        for value in ('INVALID','NaN','Infinity',True,{'amount':'100'},None):
            with self.subTest(value=value):
                rows=self.eight_financial_quarters();bad=self.later_quarter_version(rows[-1])
                bad['fields']['revenue']=value
                out=financial_quarters(rows+[bad],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
                self.assertIsNone(out['ttm'])
                self.assertIn('revenue',out['cell_conflicts']['2023-12-31'])

    def test_all_present_alias_values_must_agree(self):
        for value in ('999','NaN',{'amount':'100'}):
            with self.subTest(value=value):
                rows=self.eight_financial_quarters();bad=self.later_quarter_version(rows[-1])
                bad['fields']['net_income']=value
                out=financial_quarters(rows+[bad],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
                self.assertIsNone(out['ttm'])
                self.assertIn('net_income',out['cell_conflicts']['2023-12-31'])
        rows=self.eight_financial_quarters();rows[-1]['fields']['net_income']='100.0'
        out=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertEqual(out['ttm']['net_income'],'100')

    def test_later_same_source_domain_period_omission_blocks_cell(self):
        for replacement in ({'reporting_basis':'CUMULATIVE_YTD'},None):
            with self.subTest(replacement=replacement):
                rows=self.eight_financial_quarters();bad=self.later_quarter_version(rows[-1])
                if replacement is None: bad['fields'].pop('revenue')
                else: bad['fields']=replacement
                out=financial_quarters(rows+[bad],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
                self.assertIsNone(out['ttm'])
                self.assertIn('FINANCIAL_VISIBLE_VERSION_FIELD_REMOVAL',out['cell_conflicts']['2023-12-31']['revenue'])

    def test_same_clock_reused_revision_cannot_hide_incompatible_shapes(self):
        rows=self.eight_financial_quarters()
        for only_basis in (False,True):
            with self.subTest(only_basis=only_basis):
                partial=copy.deepcopy(rows[-1])
                if only_basis: partial['fields']={'reporting_basis':'CUMULATIVE_YTD'}
                else: partial['fields'].pop('revenue')
                out=financial_quarters(rows+[partial],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
                reversed_out=financial_quarters(rows[:-1]+[partial,rows[-1]],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
                self.assertIsNone(out['ttm'])
                self.assertEqual(out,reversed_out)
                self.assertIn('FINANCIAL_VISIBLE_VERSION_FIELD_REMOVAL',out['cell_conflicts']['2023-12-31']['revenue'])
        duplicate=copy.deepcopy(rows[-1])
        out=financial_quarters(rows+[duplicate],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertEqual(out['ttm']['revenue'],'100')
        self.assertEqual(out['cell_conflicts'],{})

    def test_sparse_other_financial_domains_are_not_field_removals(self):
        rows=[]
        for original in self.eight_financial_quarters():
            for domain,keys in [('FINANCIAL_INCOME',('revenue','oper_cost','n_income')),
                ('FINANCIAL_CASHFLOW',('n_cashflow_act',)),('FINANCIAL_INDICATOR',('ebitda',))]:
                r=copy.deepcopy(original);r.update(domain=domain,source='FIXTURE_SOURCE')
                r['fields']={k:original['fields'][k] for k in (*keys,'reporting_basis')}
                rows.append(r)
        newer=self.later_quarter_version(next(r for r in rows if r['domain']=='FINANCIAL_CASHFLOW' and r['event_date']=='2023-12-31'))
        out=financial_quarters(rows+[newer],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertEqual(out['ttm']['revenue'],'100')
        self.assertEqual(out['ttm']['operating_cashflow'],'100')
        self.assertEqual(out['cell_conflicts'],{})

    def test_future_bad_same_period_version_is_filtered_before_conflicts(self):
        rows=self.eight_financial_quarters();bad=self.later_quarter_version(rows[-1])
        bad['fields'].update(reporting_basis='UNKNOWN',revenue='NaN',net_income='999')
        bad['fields'].pop('oper_cost')
        for k in ('published_at','available_at','first_visible_at'): bad[k]='2024-06-02T16:00:00+08:00'
        before=financial_quarters(rows,symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        after=financial_quarters(rows+[bad],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertEqual(before,after)
        bad.update(published_at=None,available_at='INVALID_FUTURE_CLOCK',revision_id=None)
        after=financial_quarters(rows+[bad],symbol='600312.SH',cutoff='2024-06-01T15:00:00+08:00')
        self.assertEqual(before,after)

    def test_future_label_fields_do_not_enter_price_features(self):
        rows=prices();before=diagnose(rows,{})['candidates']
        rows[-1]['fields'].update(future_return='10000',next_day_buy='TRUE',winner_family=FAMILIES[0])
        after=diagnose(rows,{})['candidates']
        self.assertEqual(before,after)

    def test_future_calendar_conflict_does_not_change_prior_feature(self):
        rows=prices();calendar=[]
        for row in rows:
            c=copy.deepcopy(row);c.update(domain='CALENDAR',symbol='SSE')
            c['fields']={'cal_date':row['event_date'].replace('-',''),'exchange':'SSE','is_open':'1'}
            calendar.append(c)
        before=diagnose(rows+calendar,{})['candidates']
        future=copy.deepcopy(calendar[-1]);future['event_date']='2024-04-01';future['fields']['cal_date']='20240401'
        conflict=copy.deepcopy(future);conflict['fields']['is_open']='0'
        after=diagnose(rows+calendar+[future,conflict],{})['candidates']
        self.assertEqual(before,after)

    def test_policy_definitions_are_not_data_gaps(self):
        out=diagnose([],{})
        common=next(iter(out['common_blockers'].values()))
        policy=common['undefined_or_unaccepted_policies']
        self.assertEqual(policy['cost_of_capital_estimation'],'UNSET_REQUIRED')
        self.assertEqual(policy['normalized_cycle_earnings_method'],'UNSET_REQUIRED')
        self.assertEqual(policy['edge_calibration'],'UNSET_REQUIRED')
        self.assertEqual(policy['candidate_grades'],'NOT_DEFINED_IN_FROZEN_SPEC')
        self.assertNotEqual(out['state'],'NO_TRADES')

    def test_frozen_bytes_and_mutation_stop(self):
        self.assertEqual(digest(SPEC_PATH.read_bytes()),SPEC_SHA256)
        with patch('backtest_5y.interface.SPEC_SHA256','0'*64):
            with self.assertRaisesRegex(ValueError,'STRATEGY_HASH_CONFLICT_STOP'): diagnose([],{})

    def test_conflicting_price_versions_stay_unknown(self):
        rows=prices();other=copy.deepcopy(rows[-1]);other['fields']['close']='178'
        other['capture_id']='conflicting_version';rows.append(other)
        last=diagnose(rows,{})['candidates'][-1]
        self.assertEqual(last['price_features']['values'],{})
        self.assertEqual(set(last['price_features']['price_component'].values()),{'UNKNOWN'})


if __name__=='__main__': unittest.main()
