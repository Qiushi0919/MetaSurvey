"""Original integrity and historical-rule ambiguity adversaries; no actual run."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import tempfile
import unittest

from wave_h import pit as mod
from wave_h import common
from wave_h.common import SYMBOLS, canonical


class HistoricalRulePITTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x=mod.evidence();cls.m=mod.evidence_matrix();cls.p=mod.progress()

    def fact(self,fid,x=None):
        return next(f for f in (x or self.x)['new_facts'] if f['fact_id']==fid)

    def test_actual_public_scope_budget_no_credentials_or_redirect(self):
        self.assertEqual((len(self.x['captures']),self.x['actual_public_GET_requests']), (6,6))
        self.assertEqual((self.x['discovery_query_count'],self.x['discovery_tool_calls']), (8,3))
        self.assertTrue(self.x['network_stopped'])
        for field in ('authenticated_requests','credential_lookups','redirect_followed_count','proxy_used_count'):
            self.assertEqual(self.x[field],0)
        self.assertTrue(all(c['http_status']==200 and c['error'] is None for c in self.x['captures']))
        self.assertEqual(set(mod.CAPTURE_URLS),{c['capture_id'] for c in self.x['captures']})

    def test_new_facts_are_distinct_from_preserved_eleven_wave_g_facts(self):
        old=mod.prior.evidence()
        self.assertEqual(len(old['new_facts']),11);self.assertEqual(len(self.x['new_facts']),8)
        self.assertTrue({f['fact_id'] for f in self.x['new_facts']}.isdisjoint({f['fact_id'] for f in old['new_facts']}))
        self.assertEqual(self.m['body']['new_structural_fact_count'],8)
        for row in self.m['body']['rows']:
            self.assertTrue(any(d['wave_g_new_facts'] for d in row['domains']))

    def test_notices_supply_revision_dates_instead_of_migrated_url_date(self):
        for fid,want in [('SSE_2020_GENERAL_RULE_DATED_NOTICE','2020-03-13'),
                         ('SSE_2020_RISK_BOARD_DATED_NOTICE','2020-12-31')]:
            f=self.fact(fid)
            self.assertEqual((f['publication_date'],f['effective_date']),(want,want))
            self.assertNotEqual(want,f['value']['url_directory_date'])
            self.assertFalse(f['value']['url_directory_date_is_publication_proof'])
            self.assertEqual(f['value']['end_date'],'UNKNOWN')

    def test_initial_2013_header_is_not_2020_revision_effective_date(self):
        f=self.fact('SSE_2020_RISK_BOARD_DATED_NOTICE')
        self.assertEqual(f['value']['historical_initial_implementation_header'],'2013-01-01')
        self.assertFalse(f['value']['initial_header_is_current_revision_effective_date'])
        self.assertEqual(f['effective_date'],'2020-12-31')

    def test_source_date_precision_never_first_visibility(self):
        for c in self.x['captures']:
            self.assertIsNone(c['published_at']);self.assertIsNone(c['available_at'])
            self.assertFalse(c['historical_visibility_proven']);self.assertFalse(c['observed_at_the_time'])
            self.assertEqual(c['publication_precision'],'DATE_ONLY' if c['publication_date'] else 'UNKNOWN')
        for f in self.x['new_facts']:
            self.assertIsNone(f['historical_available_at'])
            self.assertFalse(f['observed_at_the_time']);self.assertFalse(f['actual_session_proven'])
        self.assertFalse(self.p['historical_visibility_proven'])

    def test_general_limit_and_rounding_are_evidence_not_security_default(self):
        v=self.fact('SSE_2020_GENERAL_LIMIT_AND_TICK')['value']
        self.assertEqual((v['general_stock_limit_ratio'],v['a_share_tick_cny']),('0.10','0.01'))
        self.assertEqual(v['source_rounding_label'],'四舍五入')
        self.assertEqual(v['per_security_applicability'],'UNKNOWN')
        self.assertTrue(v['special_rules_and_status_override_possible'])
        self.assertFalse(v['three_symbol_limit_backfill_permitted'])
        self.assertTrue(self.m['body']['rule_dates_and_ratios_are_evidence_not_default_runtime_parameters'])

    def test_risk_board_low_price_absolute_limit_and_delisting_exception(self):
        v=self.fact('SSE_2020_RISK_BOARD_LIMIT_EXCEPTIONS')['value']
        self.assertEqual((v['risk_warning_limit_ratio'],v['risk_warning_a_share_low_price_threshold_cny'],
                          v['risk_warning_low_price_absolute_change_cny']),('0.05','0.10','0.01'))
        self.assertEqual((v['delisting_period_limit_ratio'],v['delisting_a_share_low_price_threshold_cny'],
                          v['delisting_low_price_absolute_change_cny']),('0.10','0.05','0.01'))
        self.assertTrue(v['first_delisting_session_unlimited'])
        self.assertEqual(v['per_security_status_or_trigger'],'UNKNOWN')

    def test_2020_first_session_exceptions_never_backfill_2023_five_session_rule(self):
        v=self.fact('SSE_2020_FIRST_DAY_EXCEPTIONS')['value']
        self.assertTrue(v['rule_is_first_session_not_five_sessions'])
        self.assertFalse(v['2023_five_session_rule_backfill_permitted'])
        self.assertEqual(v['per_security_trigger_sessions'],'UNKNOWN')
        self.assertEqual(len(v['unlimited_first_session_triggers']),5)

    def test_delayed_clause_appendix_blocks_blanket_implementation_claim(self):
        v=self.fact('SSE_2020_DELAYED_PROVISIONS')['value']
        self.assertEqual(v['delayed_rows'],6)
        self.assertEqual(v['later_implementation_dates'],'UNKNOWN')
        self.assertTrue(v['future_implementation_notice_required'])
        self.assertFalse(v['general_limit_clause_in_this_delayed_list'])
        self.assertFalse(self.fact('SSE_2020_GENERAL_RULE_DATED_NOTICE')['value']['all_clauses_implemented_on_notice_date'])

    def test_ex_reference_is_not_raw_previous_close_factor_method_or_cash_receipt(self):
        v=self.fact('SSE_2020_EX_DIVIDEND_REFERENCE_STRUCTURE')['value']
        self.assertEqual(v['displayed_pre_close_on_ex_date'],'EX_REFERENCE_PRICE')
        for n in ('provider_adj_factor_method_proven','dividend_cash_receipt_proven',
                  'raw_previous_close_equals_ex_reference','factor_plus_cash_double_count_permitted'):
            self.assertFalse(v[n])
        self.assertTrue(v['issuer_adjusted_formula_application_possible'])
        self.assertEqual(v['per_security_action_chain'],'UNKNOWN')

    def test_generic_st_markers_do_not_determine_three_security_history(self):
        v=self.fact('SSE_2020_RISK_BOARD_ST_MARKER_SEMANTICS')['value']
        self.assertEqual((v['delisting_risk_marker'],v['other_risk_marker']),('*ST','ST'))
        self.assertEqual(v['three_symbol_historical_ST_status'],'UNKNOWN')
        self.assertEqual(v['per_security_start_and_withdrawal_dates'],'UNKNOWN')
        self.assertFalse(v['present_day_name_backfill_permitted'])

    def test_domain_history_intervals_and_formal_gates_remain_unknown_blocked(self):
        self.assertEqual(self.m['body']['continuous_historical_domains_closed'],0)
        self.assertFalse(self.p['body']['formal_price_backtest_ready'])
        self.assertFalse(self.p['body']['formal_fundamental_pit_ready'])
        for row in self.m['body']['rows']:
            self.assertFalse(row['historical_visibility_proven'])
            for d in row['domains']:
                self.assertEqual(d['covered_intervals'],[])
                self.assertEqual(d['absence_means'],'UNKNOWN');self.assertFalse(d['can_trade'])
                if d['domain']!='listing_anchor':self.assertEqual(d['historical_coverage'],'UNKNOWN')

    def test_planned_oct8_calendar_never_proves_actual_or_eod(self):
        x=mod.planned_calendar_day('2026-10-08')
        self.assertEqual(x['body']['planned_status'],'PLANNED_OPEN')
        self.assertEqual(x['body']['actual_session'],'UNKNOWN')
        self.assertEqual(x['body']['eod_complete'],'UNKNOWN')
        self.assertFalse(x['body']['safe_to_trade'])

    def test_missing_primary_action_or_trigger_is_recorded_not_negative_status(self):
        self.assertIn('JINGWANG_2024_PRIMARY_IMPLEMENTATION_NOTICE',self.x['absent_targets_not_inferred'])
        self.assertIn('2023_FIRST_REGISTERED_MAINBOARD_IPO_EFFECTIVE_TRIGGER_SESSION',self.x['absent_targets_not_inferred'])
        self.assertEqual(self.x['absence_means'],'UNKNOWN')
        old=next(f for f in mod.prior.evidence()['new_facts'] if f['fact_id']=='JINGWANG_2024_ACTION_RETROSPECTIVE_CLAIM')
        self.assertFalse(old['value']['primary_implementation_notice_captured'])

    def test_new_empty_discovery_and_predecessor_301_failures_remain_preserved(self):
        self.assertEqual(self.x['failed_discovery_calls'],['discovery-G1-3_EMPTY_SEARCH_RESULTS'])
        self.assertEqual(self.x['failed_capture_ids'],[])
        self.assertEqual(sorted(self.m['body']['preserved_predecessor_failed_capture_ids']),
                         ['action-603228','financial-600312','financial-600312-www'])
        self.assertTrue(mod.prior.preserved_refs())

    def test_each_new_source_and_manifest_change_invalidates_before_projection(self):
        refs=[r for r in mod.source_pins() if Path(r['path']).is_relative_to(mod.ARCHIVE)]
        original=common.checked_file
        for r in refs:
            with self.subTest(path=Path(r['path']).name):
                def read(path,expected=None):
                    if str(path)==r['path']:raise ValueError('SYNTHETIC_ORIGINAL_MUTATION')
                    return original(path,expected)
                with patch.object(common,'checked_file',side_effect=read):
                    with self.assertRaisesRegex(ValueError,'SYNTHETIC_ORIGINAL_MUTATION'):mod.evidence_matrix()

    def test_predecessor_original_version_and_failed_source_bytes_are_pinned(self):
        x=deepcopy(self.x);x['predecessor_manifest_ref']['sha256']='sha256:'+'0'*64
        with self.assertRaisesRegex(ValueError,'DEPENDENCY_INVALIDATED'):mod._validate_manifest(x)
        original=mod.prior.checked_file
        r=mod.prior.preserved_refs()[0]
        def read(p,expected=None):
            if str(p)==r['path']:raise ValueError('SYNTHETIC_OLD_FAILURE_MUTATED')
            return original(p,expected)
        with patch.object(mod.prior,'checked_file',side_effect=read):
            with self.assertRaisesRegex(ValueError,'SYNTHETIC_OLD_FAILURE_MUTATED'):mod.evidence_matrix()

    def test_wrong_revision_effective_dates_and_url_publication_rejected(self):
        for fid,key,val in [('SSE_2020_GENERAL_RULE_DATED_NOTICE','effective_date','2023-02-17'),
                            ('SSE_2020_RISK_BOARD_DATED_NOTICE','effective_date','2013-01-01'),
                            ('SSE_2020_GENERAL_RULE_DATED_NOTICE','publication_date','2023-02-17')]:
            x=deepcopy(self.x);self.fact(fid,x)[key]=val
            with self.assertRaisesRegex(ValueError,'EFFECTIVE_DATE_SOURCE'):mod._validate_manifest(x)

    def test_rule_rate_or_security_applicability_backfill_rejected(self):
        changes=[('SSE_2020_RISK_BOARD_LIMIT_EXCEPTIONS','risk_warning_limit_ratio','0.10'),
                 ('SSE_2020_GENERAL_LIMIT_AND_TICK','three_symbol_limit_backfill_permitted',True),
                 ('SSE_2020_RISK_BOARD_ST_MARKER_SEMANTICS','three_symbol_historical_ST_status','NORMAL'),
                 ('SSE_2020_DELAYED_PROVISIONS','later_implementation_dates','2020-03-13')]
        for fid,key,value in changes:
            x=deepcopy(self.x);self.fact(fid,x)['value'][key]=value
            with self.assertRaises(ValueError):mod._validate_manifest(x)

    def test_historical_clock_or_production_or_actual_authority_promotions_rejected(self):
        changes=[lambda x:x.update(historical_visibility_proven=True),lambda x:x.update(continuous_historical_domains_closed=1),
                 lambda x:x.update(actual_forward_days=1),lambda x:x.update(source_admission='ADMITTED'),
                 lambda x:x.update(productionGate=True),lambda x:x.update(actual_capture_authorized=True),
                 lambda x:x['new_facts'][0].update(historical_available_at='2020-03-13T00:00:00+08:00'),
                 lambda x:x['captures'][0].update(published_at='2020-03-13T00:00:00+08:00')]
        for mutate in changes:
            x=deepcopy(self.x);mutate(x)
            with self.assertRaises(ValueError):mod._validate_manifest(x)

    def test_unapproved_source_host_redirect_proxy_cannot_replace_original(self):
        for url in ('http://www.sse.com.cn/example','https://example.com/rules','https://www.sse.com.cn/rules?token=synthetic'):
            x=deepcopy(self.x);x['captures'][0]['url']=url
            with self.assertRaisesRegex(ValueError,'FROZEN_OFFICIAL_URL_ONLY'):mod._validate_manifest(x)
        x=deepcopy(self.x);x['redirect_followed_count']=1
        with self.assertRaises(ValueError):mod._validate_manifest(x)

    def test_unlisted_predecessor_path_rejected_before_io(self):
        r=deepcopy(self.x['predecessor_matrix_ref']);r['path']=str(common.BASELINE_ROOT/'docs/wave-g/Gate.json')
        with patch.object(mod,'reopen',side_effect=AssertionError('UNAPPROVED_IO')):
            with self.assertRaisesRegex(ValueError,'PREDECESSOR_REFERENCE_ONLY'):mod._ref(r)
        r['path']='/tmp/synthetic-not-original'
        with self.assertRaisesRegex(ValueError,'PREDECESSOR_REFERENCE_ONLY'):mod._ref(r)

    def test_relocated_git_reference_reopens_calling_checkout_not_saved_origin(self):
        refs=[self.x['predecessor_matrix_ref'],self.x['predecessor_progress_ref']]
        originals={r['path']:common.reopen(r) for r in refs}
        with tempfile.TemporaryDirectory(dir=mod.VALIDATION,prefix='synthetic-checkout-') as tmp:
            checkout=Path(tmp)
            for r in refs:
                p=checkout/Path(r['path']).relative_to(common.BASELINE_ROOT)
                p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(originals[r['path']]);p.chmod(0o600)
            read=common.checked_file;seen=[]
            def local(p,expected=None):
                self.assertNotIn(str(p),originals);seen.append(str(p));return read(p,expected)
            with patch.object(common,'ROOT',checkout),patch.object(common,'checked_file',side_effect=local):
                for r in refs:
                    p=checkout/Path(r['path']).relative_to(common.BASELINE_ROOT)
                    self.assertEqual(mod._ref(r),originals[r['path']]);self.assertIn(str(p),seen)
                    p.write_bytes(originals[r['path']]+b'\nSYNTHETIC_TAMPER')
                    with self.assertRaisesRegex(ValueError,'DEPENDENCY_INVALIDATED'):mod._ref(r)
                    p.write_bytes(originals[r['path']])
            for r in refs:self.assertEqual(common.reopen(r),originals[r['path']])

    def test_private_originals_not_relocated_and_dependencies_are_unique(self):
        refs=mod.source_pins();self.assertEqual(len(refs),len({r['path'] for r in refs}))
        for r in refs:
            if Path(r['path']).is_relative_to(mod.ARCHIVE):
                p=Path(r['path']);self.assertEqual(common.locate(p),p)
                self.assertEqual(p.stat().st_mode&0o777,0o600)
                self.assertFalse(p.is_symlink());self.assertEqual(len(common.reopen(r,private=True)),r['bytes'])

    def test_duplicate_json_keys_floats_unknown_fields_and_bool_counts_rejected(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE_JSON_KEY'):mod._json(b'{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError,'NON_JSON_OR_FLOAT'):mod._json(b'{"a":0.1}')
        for mutate in (lambda x:x.update(HUMAN_USER=True),lambda x:x.update(actual_forward_days=False),
                       lambda x:x['captures'][0].update(published_at_precision='SECOND')):
            x=deepcopy(self.x);mutate(x)
            with self.assertRaises(ValueError):mod._validate_manifest(x)

    def test_fact_identity_duplicate_namespace_or_symbol_scope_promotions_rejected(self):
        changes=[lambda x:x.update(namespace='EVIDENCE_ONLY:EVENT_3'),
                 lambda x:x.update(exact_symbols=list(SYMBOLS)+['300322.SZ']),
                 lambda x:x['new_facts'][0].update(symbols=['600000.SH']),
                 lambda x:x['new_facts'].append(deepcopy(x['new_facts'][0])),
                 lambda x:x['captures'].append(deepcopy(x['captures'][0]))]
        for mutate in changes:
            x=deepcopy(self.x);mutate(x)
            with self.assertRaises(ValueError):mod._validate_manifest(x)

    def test_resealed_display_or_human_string_never_authorizes_formal_history(self):
        for fn in (mod.evidence_matrix,mod.progress):
            with self.assertRaises(TypeError):fn({'HUMAN_USER':True,'formal_price_pit':'PASS'})
        fake=deepcopy(self.p);fake.update(historical_visibility_proven=True,productionGate=True)
        with self.assertRaisesRegex(ValueError,'WH_FORMAL_HISTORICAL_PIT_NOT_ADMITTED'):
            mod.run_formal(fake,owner_approved=True,LLM='APPROVE')
        self.assertEqual(self.p['actual_forward_days'],0)

    def test_deterministic_deep_copies_do_not_change_fixed_evidence(self):
        self.assertEqual(mod.evidence_matrix(),self.m);self.assertEqual(mod.progress(),self.p)
        x=mod.evidence();x['new_facts'][0]['value']['end_date']='2023-04-10'
        self.assertEqual(mod.evidence(),self.x)
        canonical(self.m);canonical(self.p)


if __name__=='__main__':unittest.main()
