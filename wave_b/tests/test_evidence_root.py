import json,unittest
from pathlib import Path
from unittest.mock import patch
from wave_b import probe,evidence_root
from wave_b.primitives import ROOT

class EvidenceRootTests(unittest.TestCase):
    def ref(self):return json.loads((ROOT/'docs/wave-b/capture-evidence.json').read_bytes())['report']
    def test_actual_byte_pinned_capture_validates(self):
        r=evidence_root.verify_registered_capture(self.ref());self.assertEqual(r['network_requests'],55);self.assertFalse(r['productionGate'])
    def test_checkout_path_constant_can_move_without_mutating_producer(self):
        before=probe.DEST
        with patch.object(probe,'DEST',Path('/SYNTHETIC_RELOCATED_CHECKOUT_NOT_EVIDENCE')):
            evidence_root.verify_registered_capture(self.ref());self.assertEqual(probe.DEST,Path('/SYNTHETIC_RELOCATED_CHECKOUT_NOT_EVIDENCE'))
        self.assertEqual(probe.DEST,before)
    def test_unapproved_capture_path_rejected(self):
        r=self.ref();r['path']=str(ROOT/'SYNTHETIC_UNAPPROVED.json')
        with self.assertRaisesRegex(ValueError,'EVIDENCE_ROOT'):evidence_root.verify_registered_capture(r)
    def test_report_hash_changed_rejected(self):
        r=self.ref();r['sha256']='sha256:'+'1'*64
        with self.assertRaisesRegex(ValueError,'HASH_INVALID'):evidence_root.verify_registered_capture(r)
    def test_root_alias_or_caller_permission_field_rejected(self):
        with patch.object(evidence_root,'ARCHIVE',Path('/SYNTHETIC_OTHER_ROOT')):
            with self.assertRaisesRegex(ValueError,'EVIDENCE_ROOT'):evidence_root.verify_registered_capture(self.ref())
        r=self.ref();r['admission']='ADMITTED'
        with self.assertRaisesRegex(ValueError,'EVIDENCE_ROOT'):evidence_root.verify_registered_capture(r)
    def test_binding_never_calls_live_collector_or_credential_lookup(self):
        with patch.object(probe,'capture',side_effect=AssertionError('NETWORK_FORBIDDEN')),patch.object(probe,'_send',side_effect=AssertionError('NETWORK_FORBIDDEN')):
            evidence_root.verify_registered_capture(self.ref())

if __name__=='__main__':unittest.main()
