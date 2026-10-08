"""Synthetic math and actual preparation gates; no live parameters."""
import unittest,json,tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from post_wave_e.common import *
from post_wave_e import action,strategy,provider,preflight,core

def action_fixture():
    return {'provenance':'SYNTHETIC_NOT_OWNER_POLICY','symbol':SYMBOLS[0],'treatment':'RAW_UNADJUSTED','raw_price':'10.25','factor':'2','anchor_factor':'1','cash_dividend_per_share':'0.25','share_multiplier':'1.1','money_unit':'CNY_DECIMAL','rounding':'ROUND_HALF_EVEN','tolerance':'0.0001','source_refs':[digest({'fixture':True})],'credits_applied':False}
def evidence_fixture():
    return {'version':VERSION,'kind':'ORDER','provenance':'SYNTHETIC_FIXTURE','provider_id':'HYPOTHETICAL_VENDOR','product_name':'HYPOTHETICAL_MONTH','valid_from':'2026-10-01T12:00:00+08:00','valid_until':'2026-11-01T12:00:00+08:00','purpose':'HYPOTHETICAL_LOCAL_RESEARCH','retention':UNSET,'storage':UNSET,'transfer':UNSET,'endpoint':'https://example.invalid/','independent_verification':'UNVERIFIED'}
class MathAndEvidence(unittest.TestCase):
    def test_raw_preserves_decimal_without_actions(self):self.assertEqual(action.reconcile_fixture(action_fixture())['value'],'10.25')
    def test_factor_sensitivity_only(self):
        x=action_fixture();x['treatment']='FACTOR_SENSITIVITY';v=action.reconcile_fixture(x);self.assertEqual(v['value'],'20.50');self.assertFalse(v['authoritative_adjustment'])
    def test_explicit_raw_synthetic_credit(self):
        x=action_fixture();x.update(treatment='RAW_WITH_SYNTHETIC_ENTITLEMENT',credits_applied=True);self.assertEqual(action.reconcile_fixture(x)['value'],'11.525')
    def test_double_action_blocked(self):
        x=action_fixture();x.update(treatment='FACTOR_SENSITIVITY',credits_applied=True)
        with self.assertRaisesRegex(ValueError,'DOUBLE_ACTION'):action.reconcile_fixture(x)
    def test_credit_missing_blocked(self):
        x=action_fixture();x['treatment']='RAW_WITH_SYNTHETIC_ENTITLEMENT'
        with self.assertRaisesRegex(ValueError,'CREDIT_MISSING'):action.reconcile_fixture(x)
    def test_float_money_rejected(self):
        x=action_fixture();x['raw_price']=10.25
        with self.assertRaises(ValueError):action.reconcile_fixture(x)
    def test_unset_action_unit_blocked(self):
        x=action_fixture();x['money_unit']=UNSET
        with self.assertRaises(ValueError):action.reconcile_fixture(x)
    def test_negative_or_zero_factor_blocked(self):
        for k,v in [('factor','0'),('anchor_factor','-1'),('share_multiplier','0')]:
            x=action_fixture();x[k]=v
            with self.assertRaises(ValueError):action.reconcile_fixture(x)
    def test_fixture_math_never_actual_entitlement(self):self.assertFalse(action.reconcile_fixture(action_fixture())['actual_cash_entitlement'])
    def test_action_fixture_detached(self):
        x=action_fixture();v=action.reconcile_fixture(x);x['source_refs'].clear();self.assertEqual(len(v['source_refs']),1)
    def test_provider_document_intake_never_license(self):
        v=provider.parse_redacted_evidence(evidence_fixture());self.assertFalse(v['license_verified']);self.assertEqual(v['formal_source_admission'],'BLOCKED')
    def test_owner_claim_is_not_independent_verification(self):
        x=evidence_fixture();x['provenance']='OWNER_REDACTED_DOCUMENT';x['independent_verification']='VERIFIED';self.assertFalse(provider.parse_redacted_evidence(x)['provider_identity_verified'])
    def test_public_docs_do_not_prove_account_tier(self):self.assertFalse(provider.gap_matrix()['public_docs_are_account_entitlement'])
    def test_credential_key_and_query_rejected(self):
        for k,v in [('token','fixture'),('endpoint','http://example.invalid/?credential=fixture')]:
            x=evidence_fixture();x[k]=v
            with self.assertRaises(ValueError):provider.parse_redacted_evidence(x)
    def test_reversed_expiry_rejected(self):
        x=evidence_fixture();x['valid_until']=x['valid_from']
        with self.assertRaises(ValueError):provider.parse_redacted_evidence(x)
    def test_unset_expiry_stays_unverified(self):
        x=evidence_fixture();x['valid_until']=UNSET;self.assertFalse(provider.parse_redacted_evidence(x)['entitlement_verified'])
    def test_provider_ingest_cannot_read_arbitrary_path(self):
        with self.assertRaisesRegex(ValueError,'PATH_RESTRICTED'):provider.ingest_evidence('/tmp/fixture.json')
    def test_private_redacted_ingest_preserves_original_and_blocks_license(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();src=root/'input';dest=root/'staging';src.mkdir(mode=0o700);dest.mkdir(mode=0o700)
            x=evidence_fixture();x['provenance']='OWNER_REDACTED_DOCUMENT';p=src/'fixture.json';raw=canonical(x);p.write_bytes(raw);p.chmod(0o600)
            with patch.object(provider,'ROOT',src),patch.object(provider,'STAGING',dest):
                v=provider.ingest_evidence(p);self.assertFalse(v['license_verified']);saved=list(dest.iterdir());self.assertEqual(len(saved),1);self.assertEqual(saved[0].read_bytes(),raw);self.assertEqual(saved[0].stat().st_mode&0o777,0o600)
                with self.assertRaises(FileExistsError):provider.ingest_evidence(p)
    def test_ingest_symlink_cannot_substitute_source(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();p=root/'original.json';p.write_bytes(canonical(evidence_fixture()));link=root/'linked.json';link.symlink_to(p)
            with patch.object(provider,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'PATH_INVALID'):provider.ingest_evidence(link)
    def test_one_unknown_expiry_does_not_allow_invalid_other_clock(self):
        x=evidence_fixture();x.update(valid_until=UNSET,valid_from='2026-10-01')
        with self.assertRaisesRegex(ValueError,'INSTANT_REQUIRED'):provider.parse_redacted_evidence(x)
    def test_bearer_credential_marker_rejected_before_staging(self):
        x=evidence_fixture();x['purpose']='Bearer SYNTHETIC_CREDENTIAL_NOT_A_REAL_SECRET'
        with self.assertRaisesRegex(ValueError,'SECRET_OR_QUERY'):provider.parse_redacted_evidence(x)
    def test_duplicate_key_cannot_hide_raw_credential_marker(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();src=root/'input';dest=root/'staging';src.mkdir(mode=0o700);dest.mkdir(mode=0o700);x=evidence_fixture();x['provenance']='OWNER_REDACTED_DOCUMENT'
            raw=canonical(x).decode().replace('"endpoint":','"endpoint":"http://example.invalid/?token=SYNTHETIC_ONLY","endpoint":',1);p=src/'fixture.json';p.write_text(raw)
            with patch.object(provider,'ROOT',src),patch.object(provider,'STAGING',dest):
                with self.assertRaisesRegex(ValueError,'DUPLICATE_JSON_KEY'):provider.ingest_evidence(p)
            self.assertFalse(list(dest.iterdir()))
    def test_escaped_duplicate_json_key_is_also_rejected(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE_JSON_KEY'):json.loads('{"endpoint":"fixture","end\\u0070oint":"fixture2"}',object_pairs_hook=provider._unique_object)
    def test_hash_not_pit_or_transfer_permission(self):
        v=provider.parse_redacted_evidence(evidence_fixture());hash_value(v['document_hash']);self.assertFalse(v['historical_visibility_proven']);self.assertFalse(v['cloud_transfer_permitted'])
    def test_economic_requirements_remain_unset(self):
        v=strategy.frozen_spec();self.assertTrue(all(x['value']==UNSET for x in v['parameters'].values()));self.assertFalse(v['owner_strategy_selected'])
    def test_diagnostic_rule_not_selected_strategy(self):self.assertFalse(strategy.frozen_spec()['diagnostic_ma20_ma60_is_owner_strategy'])
    def test_profit_curve_never_unblocks_evaluation(self):
        with self.assertRaisesRegex(ValueError,'NOT_AUTHORIZED'):strategy.evaluate_strategy({'owner_approved':True},{'synthetic_profit':'999999'})
    def test_freeze_before_reveal(self):
        x={'provenance':'SYNTHETIC_NOT_OWNER_POLICY','rules':{'rule':'fixture'},'evaluation':{'benchmark':'fixture'},'frozen_at':'2026-10-01T12:00:00+08:00','reveal_at':'2026-10-02T12:00:00+08:00'}
        v=strategy.fixture_freeze(x);x['rules']['rule']='changed';self.assertEqual(v['spec']['rules']['rule'],'fixture')
        x['frozen_at']=x['reveal_at']
        with self.assertRaises(ValueError):strategy.fixture_freeze(x)
    def test_date_only_never_instant(self):
        with self.assertRaises(ValueError):timestamp('2026-10-08')
    def test_nanosecond_cutoff_order(self):self.assertGreater(timestamp('2026-10-08T15:00:00.000000002+08:00'),timestamp('2026-10-08T15:00:00.000000001+08:00'))
    def test_snapshot_planned_date_not_actual(self):
        v=preflight.readiness();self.assertFalse(v['actual_fresh_session_observed']);self.assertEqual(v['actual_forward_days'],0)
    def test_snapshot_owner_boolean_cannot_unlock(self):
        with self.assertRaisesRegex(ValueError,'NOT_AUTHORIZED'):preflight.run_snapshot_b(owner_approved=True,day='2026-10-08')
    def test_production_owner_boolean_cannot_unlock(self):
        with self.assertRaisesRegex(ValueError,'NOT_AUTHORIZED'):core.production_execute(owner_approved=True)
class ActualClosedBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.values=core.objects()
    def test_eight_closed_actual_objects(self):self.assertEqual({v['contract_name'] for v in self.values},set(core.NAMES))
    def test_actual_object_registration(self):self.assertTrue(core.assert_registered(self.values[0]))
    def test_copy_and_reseal_never_registry(self):
        x=deepcopy(self.values[0]);x['content_hash']=digest({k:v for k,v in x.items() if k!='content_hash'})
        with self.assertRaisesRegex(ValueError,'UNREGISTERED'):core.assert_registered(x)
    def test_mutation_invalidates_registered_object(self):
        x=core.objects()[0];x['actual_forward_days']=1
        with self.assertRaisesRegex(ValueError,'MUTATED'):core.assert_registered(x)
    def test_registered_only_display(self):
        x=self.values[0];self.assertEqual(core.transition(x,'LOCAL_PREPARATION_DISPLAY'),x)
        for target in ('ResearchCard','SignalEvent','Approval','OrderIntent','Fill','BROKER','CORE_40','EVENT_3','RESEARCH_6_18M','ADMITTED'):
            with self.assertRaisesRegex(ValueError,'PROMOTION'):core.transition(x,target)
    def test_direct_issue_and_derive_block(self):
        for f in (core.register,core.derive):
            with self.assertRaisesRegex(ValueError,'DIRECT_ISSUE'):f(self.values[0],owner_approved=True)
    def test_context_change_invalidates_handle(self):
        c=core.frozen_context();c['source_identity']=digest({'changed':True})
        with patch('post_wave_e.core.frozen_context',return_value=c):
            with self.assertRaisesRegex(ValueError,'CONTEXT_INVALIDATED'):core.assert_registered(self.values[0])
    def test_all_actual_gates_false(self):
        for v in self.values:
            for k in ('provider_identity_verified','license_verified','transport_integrity_verified','historical_visibility_proven','productionGate','live_authority','can_produce_order','cloud_transfer'):self.assertIs(v[k],False)
            self.assertEqual(v['actual_forward_days'],0)
    def test_adopted_original_pins_are_direct(self):
        c=core.frozen_context();adopt=json.loads((core.ROOT/'docs/post-wave-e/adopted-private-pins.json').read_bytes())['pins'];pins={str(p):h for p,h in c['pins']}
        self.assertTrue(all(pins[r['path']]==r['sha256'] for r in adopt));self.assertEqual(len(adopt),293)
    def test_every_observation_original_and_request_alias_is_direct(self):
        c=core.frozen_context();m=json.loads((core.ROOT/'docs/post-wave-e/observation-original-map.json').read_bytes());pins={str(p):h for p,h in c['pins']}
        expected={o['source_ref']['raw_sha256'] for x in c['inputs'] for o in x['body']['observations']};actual={h for p,h in c['pins'] if p.is_relative_to(core.ARCHIVE.parent)};self.assertTrue(expected<=actual);self.assertEqual(len(expected),85)
        self.assertEqual(len(m['observation_originals']),94)
        for q in m['observation_originals']:
            for r in q['original_refs']:self.assertEqual(pins[r['path']],q['raw_sha256'])
    def test_predecessor_baseline_not_rewritten(self):
        x=json.loads((core.ROOT/'docs/post-wave-e/baseline-pins.json').read_bytes());self.assertEqual(x['immutable_count'],663)
        for r in x['tracked_files']:
            if r['path'] not in x['allowed_navigation_updates']:self.assertEqual(sha((core.ROOT/r['path']).read_bytes()),r['sha256'])
    def test_historical_registry_has_all_e_domains(self):
        from wave_e.research import PRICE_DOMAINS,FUNDAMENTAL_DOMAINS
        d=core.historical_gap();names={x['domain'] for x in d['domains']};self.assertTrue(set(PRICE_DOMAINS+FUNDAMENTAL_DOMAINS)<=names);self.assertTrue(all(x['state']=='BLOCKED' for x in d['domains']))
    def test_no_actual_blocker_closed_by_interfaces(self):self.assertEqual(core.historical_gap()['closed_c12_c22'],0)
    def test_actual_adapter_adopts_three_frozen_observation_anchors_only(self):
        from post_wave_e.real_adapter import preview
        x=preview();p=x['projection'];self.assertEqual([r['symbol'] for r in p['source_refs']],list(SYMBOLS));self.assertIsNone(p['fresh_snapshot_b']);self.assertFalse(p['anchor_is_admitted_snapshot']);self.assertEqual(p['actual_forward_days'],0)
    def test_actual_paper_append_cannot_use_display_or_owner_boolean(self):
        from post_wave_e.real_adapter import preview,append_actual_session
        with self.assertRaisesRegex(ValueError,'NOT_AUTHORIZED'):append_actual_session(preview(),owner_approved=True)
