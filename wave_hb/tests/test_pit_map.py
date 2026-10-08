"""Historical cutoff/adversarial original tests; fixtures never actual evidence."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest
from unittest.mock import patch

from wave_hb import pit_map as p


class MapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.map=p.build_map()

    def test_exact_three_no_expansion(self):
        self.assertEqual(self.map['symbols'],['603993.SH','600312.SH','603228.SH'])
        self.assertEqual({d['symbol'] for d in self.map['domains']},set(self.map['symbols']))

    def test_every_existing_report_feature_preserved_without_values(self):
        nodes=self.map['current_report_inputs']
        self.assertEqual(len(nodes),174)
        for symbol in self.map['symbols']:
            own=[n for n in nodes if n['symbol']==symbol]
            self.assertEqual(len(own),58)
            self.assertEqual(len({n['field'] for n in own}),58)
            self.assertTrue(all('value' not in n for n in own))
        parent=[n for n in nodes if n['field']=='source_parent_net_profit']
        self.assertTrue(all('financial_ann_fann_date' in n['required_domains'] for n in parent))

    def test_both_frozen_families_and_all_timing_inputs_present(self):
        family=[n for n in self.map['declared_decision_inputs'] if 'family_id' in n]
        self.assertEqual(len(family),10)
        self.assertEqual({n['family_id'] for n in family},{'CORE40_Q_PULLBACK_V1','CORE40_Q_BREAKOUT_V1'})
        self.assertEqual({n['field'] for n in family if n['family_id']=='CORE40_Q_PULLBACK_V1'},
          {'close_above_ma60','ma60_slope_20','sector_rs20','distance_ma20_atr','volume3_to_volume20','close_above_previous3_high'})
        self.assertTrue(all(n['declaration_scope']=='FROZEN_RESEARCH_PROPOSAL_NOT_OWNER_POLICY' for n in family))

    def test_hidden_financial_cost_action_benchmark_inputs_explicit(self):
        fields={n.get('field') for n in self.map['declared_decision_inputs']}
        self.assertTrue({'TTM_revenue','previous_comparable_TTM_revenue','TTM_EBITDA','net_debt','ROIC',
          'scenario_probability','contemporaneous_cost_of_capital','sector_total_return','benchmark_total_return',
          'revision_first_visible','cash_entitlement','cash_release_ordering','fillability_and_order_rejection'}<=fields)

    def test_domains_and_cutoff_are_requirements_not_invented_history(self):
        self.assertGreaterEqual(len(self.map['domain_groups']),11)
        self.assertEqual(self.map['historical_decision_time'],None)
        self.assertEqual(self.map['cutoff_state'],'REQUIRED_PER_DECISION_NOT_SUPPLIED')
        required={'decision_time','event_time','published_at','available_at','retrieved_at',
                  'first_visible_evidence','revision_version_chain','rule_effective_interval',
                  'security_applicability','original_refs','license_status'}
        self.assertTrue(required<=set(self.map['per_decision_field_requirements']))
        for n in self.map['declared_decision_inputs']+self.map['current_report_inputs']:
            self.assertIsNone(n['decision_time']);self.assertIsNone(n['historical_first_visible'])
            self.assertEqual(n['covered_historical_intervals'],[])

    def test_current_report_retrieval_cannot_be_historical_available_at(self):
        n=next(n for n in self.map['current_report_inputs'] if n['field']=='last_raw_close')
        self.assertTrue(n['current_observation_original_refs'])
        self.assertTrue(n['current_observation_clocks'])
        self.assertTrue(all(c['available_at']==c['retrieved_at'] for c in n['current_observation_clocks']))
        self.assertIsNone(n['historical_available_at'])
        self.assertEqual(n['formal_admission'],'BLOCKED')

    def test_generic_rule_and_listing_originals_do_not_close_intervals(self):
        structural=[d for d in self.map['domains'] if d['domain'] in ('listing_anchor','historical_price_limit_regime')]
        self.assertTrue(any(d.get('facts') or d.get('wave_h_new_facts') for d in structural))
        self.assertTrue(all(d['covered_intervals']==[] and d['formal_admission']=='BLOCKED' for d in structural))
        self.assertEqual(self.map['continuous_historical_domains_closed'],0)

    def test_all_source_and_execution_boundaries_remain_false(self):
        self.assertEqual(len(self.map['provider_license_transport']),8)
        self.assertEqual(set(self.map['provider_license_transport'].values()),{'UNKNOWN'})
        for k in ('historical_visibility_proven','native_signal_order_broker','safe_to_trade','productionGate',
                  'cloud_export','actual_authority','is_authority'):self.assertIs(self.map[k],False)
        self.assertEqual(self.map['actual_forward_days'],0)
        self.assertEqual(self.map['network_requests'],0)
        with self.assertRaisesRegex(ValueError,'NOT_ADMITTED'):p.run_formal(self.map)

    def test_output_self_hash_changes_and_cannot_issue_authority(self):
        forged=deepcopy(self.map);forged['productionGate']=True
        with self.assertRaisesRegex(ValueError,'INVALIDATED'):p.render_map(forged)
        forged['content_hash']=p.digest({k:v for k,v in forged.items() if k!='content_hash'})
        # A recomputed metadata hash still cannot grant formal authority.
        with self.assertRaisesRegex(ValueError,'SCOPE_PROMOTION'):p.render_map(forged)
        with self.assertRaisesRegex(ValueError,'NOT_ADMITTED'):p.run_formal(forged)

    def test_fixed_missing_original_stops_build(self):
        with patch.object(p,'reopen',side_effect=ValueError('TEST_MISSING_IMMUTABLE_ORIGINAL')):
            with self.assertRaisesRegex(ValueError,'MISSING_IMMUTABLE'):p.build_map()

    def test_h_a_context_drift_stops_projection(self):
        with patch.object(p,'frozen_context',return_value={'context_hash':'sha256:'+'0'*64,'source_dependencies':[]}):
            with self.assertRaisesRegex(ValueError,'CONTEXT_CHANGED'):p.build_map()


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        # macOS /var aliases /private/var. Fixtures must meet the same immutable
        # canonical-original path requirement; do not relax the parser guard.
        self.base=Path(self.tmp.name).resolve()
        self.r={'kind':'SYNTHETIC_PIT_RECORD','namespace':p.FIXTURE_NAMESPACE,'symbol':'603993.SH','field':'revenue',
          'event_time':'2024-03-31T00:00:00Z','published_at':'2024-04-30T12:00:00Z',
          'first_visible':'2024-04-30T12:00:00Z','available_at':'2024-04-30T12:00:00Z',
          'retrieved_at':'2026-10-07T12:00:00Z','effective_from':'2024-04-30T12:00:00Z',
          'effective_to':'2027-01-01T00:00:00Z','revision_id':'synthetic-r1','supersedes_revision_id':None,
          'source_version':None,'security_applicability':['603993.SH'],
          'original_ref':None,'first_visible_original_ref':None,
          'revision_original_ref':None,'license_state':'SYNTHETIC_ONLY_NO_ACTUAL_LICENSE'}
        self.bind(self.r)
        self.cutoff='2024-05-01T00:00:00Z'

    def bind(self,r):
        def original(suffix,body):
            raw=p.canonical(body);f=self.base/(r['revision_id']+suffix);f.write_bytes(raw);os.chmod(f,0o600)
            return {'path':str(f),'bytes':len(raw),'sha256':p.sha(raw)}
        common={'namespace':p.FIXTURE_NAMESPACE,'symbol':r['symbol'],'field':r['field'],'revision_id':r['revision_id']}
        r['original_ref']=original('-value.json',dict(common,kind='SYNTHETIC_PIT_VALUE_ORIGINAL',event_time=r['event_time']))
        h=r['original_ref']['sha256'];r['source_version']=h
        r['first_visible_original_ref']=original('-visible.json',dict(common,kind='SYNTHETIC_PIT_FIRST_VISIBLE_ORIGINAL',
          original_sha256=h,published_at=r['published_at'],first_visible=r['first_visible'],available_at=r['available_at']))
        r['revision_original_ref']=original('-revision.json',dict(common,kind='SYNTHETIC_PIT_REVISION_ORIGINAL',
          original_sha256=h,supersedes_revision_id=r['supersedes_revision_id']))
        return r

    def assess(self,r=None,cutoff=None,**kw):
        return p.assess_fixture_record(r or self.r,cutoff or self.cutoff,symbol=kw.get('symbol','603993.SH'),field=kw.get('field','revenue'))

    def second(self):
        r=deepcopy(self.r);r['revision_id']='synthetic-r2';r['supersedes_revision_id']='synthetic-r1'
        for k in ('published_at','first_visible','available_at','effective_from'):r[k]='2024-06-01T12:00:00Z'
        return self.bind(r)

    def select(self,rs,cutoff=None):return p.select_fixture_revision(rs,cutoff or self.cutoff,symbol='603993.SH',field='revenue')

    def test_consistent_fixture_with_later_retrieval_has_no_actual_history(self):
        x=self.assess();self.assertTrue(x['consistent_at_cutoff'])
        self.assertFalse(x['historical_visibility_proven']);self.assertFalse(x['actual_authority'])
        self.assertEqual(x['formal_admission'],'BLOCKED')

    def test_today_query_cannot_backfill_before_first_visible(self):
        x=self.assess(cutoff='2024-04-29T23:59:59Z')
        self.assertFalse(x['consistent_at_cutoff']);self.assertIn('FUTURE_AVAILABLE_AT',x['reason_codes'])

    def test_exact_cutoff_boundary_is_inclusive_at_nanosecond_precision(self):
        self.assertTrue(self.assess(cutoff=self.r['available_at'])['consistent_at_cutoff'])
        r=deepcopy(self.r)
        for k in ('published_at','first_visible','available_at','effective_from'):r[k]='2024-04-30T12:00:00.000000001Z'
        self.bind(r)
        x=self.assess(r,cutoff='2024-04-30T12:00:00Z');self.assertIn('FUTURE_AVAILABLE_AT',x['reason_codes'])

    def test_date_only_publication_cannot_be_midnight(self):
        r=deepcopy(self.r);r['published_at']='2024-04-30'
        with self.assertRaisesRegex(ValueError,'INSTANT_REQUIRED'):self.assess(r)

    def test_clock_reversal_is_rejected(self):
        r=deepcopy(self.r);r['first_visible']='2024-04-29T12:00:00Z'
        with self.assertRaisesRegex(ValueError,'CLOCK_ORDER'):self.assess(r)

    def test_retrieval_before_available_is_rejected(self):
        r=deepcopy(self.r);r['retrieved_at']='2024-04-30T11:59:59Z'
        with self.assertRaisesRegex(ValueError,'CLOCK_ORDER'):self.assess(r)

    def test_effective_end_is_exclusive(self):
        x=self.assess(cutoff=self.r['effective_to'])
        self.assertIn('NOT_EFFECTIVE_AT_DECISION',x['reason_codes'])

    def test_inverted_interval_rejected(self):
        r=deepcopy(self.r);r['effective_to']=r['effective_from']
        with self.assertRaisesRegex(ValueError,'INTERVAL_INVALID'):self.assess(r)

    def test_wrong_security_and_global_rule_are_not_applicability(self):
        for applicability in (['600312.SH'],list(p.SYMBOLS),[]):
            r=deepcopy(self.r);r['security_applicability']=applicability
            with self.subTest(applicability=applicability):
                with self.assertRaisesRegex(ValueError,'SECURITY_OR_FIELD'):self.assess(r)

    def test_namespace_and_actual_record_forgery_rejected(self):
        for namespace in ('PIT_EVIDENCE_SYNTHETIC:EVENT_3','PIT_EVIDENCE_SYNTHETIC:RESEARCH_6_18M','ACTUAL_FORWARD_NO_DECISION',p.NAMESPACE):
            r=deepcopy(self.r);r['namespace']=namespace
            with self.subTest(namespace=namespace):
                with self.assertRaisesRegex(ValueError,'FIXTURE_NAMESPACE_ONLY'):self.assess(r)
        r=deepcopy(self.r);r['kind']='ACTUAL_PIT_RECORD'
        with self.assertRaisesRegex(ValueError,'FIXTURE_NAMESPACE_ONLY'):self.assess(r)

    def test_missing_original_rejected(self):
        Path(self.r['first_visible_original_ref']['path']).unlink()
        with self.assertRaisesRegex(ValueError,'ORIGINAL_MISSING'):self.assess()

    def test_original_hash_tamper_rejected(self):
        Path(self.r['original_ref']['path']).write_bytes(b'TAMPERED')
        with self.assertRaisesRegex(ValueError,'DEPENDENCY_INVALIDATED'):self.assess()

    def test_source_version_does_not_bind_original_rejected(self):
        r=deepcopy(self.r);r['source_version']='sha256:'+'0'*64
        with self.assertRaisesRegex(ValueError,'SOURCE_VERSION'):self.assess(r)

    def test_symlink_original_rejected(self):
        f=self.base/'alias.txt';f.symlink_to(self.r['original_ref']['path'])
        r=deepcopy(self.r);r['original_ref']['path']=str(f)
        with self.assertRaisesRegex(ValueError,'ALIAS'):self.assess(r)

    def test_nonprivate_original_rejected(self):
        os.chmod(self.r['original_ref']['path'],0o644)
        with self.assertRaisesRegex(ValueError,'PRIVATE'):self.assess()

    def test_unknown_license_blocks_even_synthetic_consistency(self):
        r=deepcopy(self.r);r['license_state']='UNKNOWN'
        x=self.assess(r);self.assertFalse(x['consistent_at_cutoff'])
        self.assertIn('FIXTURE_LICENSE_SCOPE_INVALID',x['reason_codes'])

    def test_future_restatement_not_selected_at_older_cutoff(self):
        later=self.second();x=self.select([later,self.r])
        self.assertEqual(x['selected_revision_id'],'synthetic-r1');self.assertEqual(x['excluded_revision_ids'],['synthetic-r2'])
        later_x=self.select([self.r,later],'2024-06-02T00:00:00Z')
        self.assertEqual(later_x['selected_revision_id'],'synthetic-r2');self.assertFalse(later_x['actual_authority'])

    def test_revision_predecessor_missing_rejected(self):
        with self.assertRaisesRegex(ValueError,'PREDECESSOR_MISSING'):self.select([self.second()])

    def test_duplicate_revision_id_rejected(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE_REVISION'):self.select([self.r,deepcopy(self.r)])

    def test_revision_chain_ambiguous_roots_rejected(self):
        r=self.second();r['supersedes_revision_id']=None
        self.bind(r)
        with self.assertRaisesRegex(ValueError,'ROOT_AMBIGUOUS'):self.select([self.r,r])

    def test_revision_chronology_reversal_rejected(self):
        r=self.second()
        for k in ('published_at','first_visible','available_at','effective_from'):r[k]=self.r[k]
        self.bind(r)
        with self.assertRaisesRegex(ValueError,'CHRONOLOGY_INVALID'):self.select([self.r,r])

    def test_revision_branch_rejected(self):
        r2=self.second();r3=deepcopy(r2);r3['revision_id']='synthetic-r3'
        for k in ('published_at','first_visible','available_at','effective_from'):r3[k]='2024-07-01T12:00:00Z'
        self.bind(r3)
        with self.assertRaisesRegex(ValueError,'BRANCH_AMBIGUOUS'):self.select([self.r,r2,r3])

    def test_no_visible_revision_returns_none_not_latest(self):
        x=self.select([self.r,self.second()],'2024-04-01T00:00:00Z')
        self.assertIsNone(x['selected_revision_id']);self.assertFalse(x['historical_visibility_proven'])

    def test_extra_authority_field_and_float_rejected(self):
        r=deepcopy(self.r);r['productionGate']=True
        with self.assertRaisesRegex(ValueError,'SHAPE_INVALID'):self.assess(r)
        r=deepcopy(self.r);r['revision_id']=1.5
        with self.assertRaisesRegex(ValueError,'NON_JSON_OR_FLOAT'):self.assess(r)

    def test_resealed_first_visible_original_must_bind_revision_and_clock(self):
        r=deepcopy(self.r)
        raw=Path(r['first_visible_original_ref']['path']).read_bytes().replace(b'synthetic-r1',b'other-rev-id')
        Path(r['first_visible_original_ref']['path']).write_bytes(raw)
        r['first_visible_original_ref']['sha256']=p.sha(raw);r['first_visible_original_ref']['bytes']=len(raw)
        with self.assertRaisesRegex(ValueError,'PROOF_METADATA_BINDING'):self.assess(r)


if __name__=='__main__':unittest.main()
