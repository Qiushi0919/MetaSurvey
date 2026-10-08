import copy,json,unittest
from wave_h.common import *
from wave_h import core
class IntegrityTests(unittest.TestCase):
    def test_missing_private_original_is_fixed_rejection(self):
        with self.assertRaisesRegex(ValueError,'WH_PRIVATE_ORIGINAL_REQUIRED'):
            reopen({'path':str(ARCHIVE/'forward/never-created-original.json'),'sha256':sha(b'x'),'bytes':1},private=True)
    def test_immutable_predecessors(self):
        b=json.loads(checked_file(ROOT/'docs/wave-h/baseline-pins.json'));n=0
        for r in b['tracked_files']:
            if r['path'] not in b['allowed_navigation_updates']:
                raw=checked_file(ROOT/r['path'],r['sha256']);self.assertEqual(len(raw),r['bytes']);n+=1
        self.assertEqual(n,812)
    def test_previous_context_unchanged(self):
        c=core.frozen_context();self.assertEqual(c['prior_context_hash'],'sha256:cfe01c4e0d31b0bb4c21e73f77f8f7095054848b5820b9b34664ec86cb8e497d');self.assertEqual(c['prior_dependency_count'],1295)
    def test_complete_code_inventory(self):
        x=json.loads(checked_file(ROOT/'docs/wave-h/release.json'));self.assertEqual(x['code_pins'],code_manifest());self.assertTrue(all((ROOT/p).is_file() for p in FIXED))
    def test_saved_replay(self):
        from wave_h.run import verify_saved
        self.assertTrue(verify_saved()['byte_identical'])
    def test_all_metadata_blocked(self):
        for obj in core.payloads().values():self.assertFalse(obj['productionGate']);self.assertEqual(obj['actual_forward_days'],0)
    def test_copied_display_rejected(self):
        x=next(iter(core.payloads().values()))
        with self.assertRaises(ValueError):core.display(copy.deepcopy(x))
    def test_mutated_display_rejected(self):
        x=next(iter(core.payloads().values()));x['productionGate']=True
        with self.assertRaises(ValueError):core.display(x)
    def test_native_promotion_rejected(self):
        x=next(iter(core.payloads().values()))
        with self.assertRaises(ValueError):core.transition(x,'SignalEvent')
    def test_no_actual_root_installed(self):
        from wave_h.auth import AUTHORITY
        self.assertFalse(AUTHORITY.exists())
    def test_native_contracts_unchanged(self):
        from pathlib import Path
        self.assertEqual(len(list((ROOT/'migrations').glob('*.sql'))),6)
        self.assertEqual(json.loads(checked_file(ROOT/'docs/wave-h/release.json'))['new_native_contracts'],0)
    def test_provider_policy_unchanged_and_blocked(self):
        p=policy();self.assertFalse(p['provider_license_transport_verified']);self.assertFalse(p['productionGate']);self.assertFalse(p['historical_visibility_proven'])
    def test_real_money_unset(self):
        from wave_g.policy import owner_settings
        x=owner_settings();self.assertEqual(len(x),30);self.assertTrue(all(s['status']=='UNSET_REQUIRED' for s in x))
    def test_cloud_blocked(self):
        with self.assertRaises(ValueError):core.cloud_export({})
    def test_production_blocked(self):
        with self.assertRaises(ValueError):core.production_execute({})
    def test_formal_pit_blocked(self):
        with self.assertRaises(ValueError):core.run_formal({})
