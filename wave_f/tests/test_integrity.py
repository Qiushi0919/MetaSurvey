import json, unittest
from copy import deepcopy
from unittest.mock import patch
from wave_f import core as c
from wave_f.common import *
from wave_f.run import verify_saved, produce

class IntegrityTests(unittest.TestCase):
    def test_baseline_all722_originals(self):
        b=json.loads(checked_file(ROOT/'docs/wave-f/baseline-pins.json'))
        self.assertEqual(722,b['immutable_count'])
        for r in b['tracked_files']:
            if r['path'] not in b['allowed_navigation_updates']:self.assertEqual(r['sha256'],sha(checked_file(ROOT/r['path'])))
    def test_context_is_frozen_and_reread(self):self.assertEqual(c.frozen_context(),c.frozen_context())
    def test_all_new_metadata_issued_display(self):
        for x in c.payloads().values():self.assertIs(x,c.display(x))
    def test_copy_and_reseal_not_issued(self):
        x=next(iter(c.payloads().values()))
        for y in (deepcopy(x),seal({k:v for k,v in x.items() if k!='content_hash'})):
            with self.assertRaises(ValueError):c.display(y)
    def test_payload_mutation_invalidates(self):
        x=next(iter(c.payloads().values()));x['body']={'forged':'ready'}
        with self.assertRaises(ValueError):c.display(x)
    def test_metadata_never_native(self):
        x=next(iter(c.payloads().values()))
        for t in ('SignalEvent','Approval','OrderIntent','Fill','ResearchCard','ADMITTED','BROKER','EVENT_3','RESEARCH_6_18M'):
            with self.assertRaises(ValueError):c.transition(x,t)
    def test_actual_entrypoints_unconditional_block(self):
        for fn in (c.run_formal,c.actual_snapshot_b,c.actual_forward,c.production_execute):
            with self.assertRaises(ValueError):fn(owner_approved=True,actor='HUMAN_USER',gate='PASS',license_verified=True)
    def test_code_pin_mismatch_rejected(self):
        original=c.checked_file
        def intercepted(path,expected=None):
            if str(path)==str(ROOT/'wave_f/strategy.py') and expected:raise ValueError('TEST_CODE_TAMPER')
            return original(path,expected)
        with patch.object(c,'checked_file',intercepted):
            with self.assertRaisesRegex(ValueError,'TEST_CODE_TAMPER'):c.frozen_context()
    def test_source_pin_mismatch_rejected(self):
        original=c.checked_file
        def intercepted(path,expected=None):
            if '/public/pit/' in str(path) and expected:raise ValueError('TEST_SOURCE_TAMPER')
            return original(path,expected)
        with patch.object(c,'checked_file',intercepted):
            with self.assertRaisesRegex(ValueError,'TEST_SOURCE_TAMPER'):c.frozen_context()
    def test_no_private_evidence_relocated(self):
        ctx=c.frozen_context()
        self.assertTrue(all(Path(r['path']).is_absolute() for r in ctx['source_dependencies']))
        self.assertTrue(any('/.p1b-archives/wave-f-' in r['path'] for r in ctx['source_dependencies']))
    def test_no_credential_authority_in_metadata(self):
        for obj in c.payloads().values():
            for key in ('productionGate','live_authority','provider_license_transport_verified','formal_backtest_authorized','snapshot_b_authorized','forward_paper_authorized','historical_visibility_proven'):self.assertIs(False,obj[key])
            self.assertEqual(0,obj['actual_forward_days'])
    def test_readiness_deterministic(self):self.assertEqual(c.payloads(),c.payloads())
    def test_saved_replay_verified(self):self.assertTrue(verify_saved()['byte_identical'])
    def test_epoch_invalid_never_overwrite(self):
        for v in ('','../old','PREPARATION-G0','PREPARATION-G1/../old'):
            with self.assertRaises(ValueError):produce(v)

if __name__=='__main__':unittest.main()
