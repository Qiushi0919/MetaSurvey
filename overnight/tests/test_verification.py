import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from overnight.data.dataset import DataError, sha
from overnight.verify import checked_bytes, verify_baseline, verify_outputs, ROOT

class VerificationTests(unittest.TestCase):
    def test_original_430_immutable_files_and_all_seven_private_outputs_reverify(self):
        self.assertEqual(verify_baseline()['immutable_files_verified'],430)
        self.assertEqual(verify_outputs()['verified_artifacts'],7)

    def test_byte_mutation_and_wrong_hash_fail_without_source_rewriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();path=root/'fixture';path.write_bytes(b'SYNTHETIC')
            expected=sha(path.read_bytes());path.write_bytes(b'SYNTHETIC_CHANGED')
            with self.assertRaisesRegex(DataError,'OVERNIGHT_EVIDENCE_HASH_MISMATCH'):
                checked_bytes(path,expected,root)

    def test_file_and_parent_symlink_and_traversal_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();path=root/'fixture';path.write_bytes(b'SYNTHETIC')
            (root/'link').symlink_to(path);(root/'directory').mkdir();(root/'parent_link').symlink_to(root/'directory')
            for bad in (root/'link',root/'parent_link'/'anything',root/'directory'/'..'/'fixture'):
                with self.assertRaisesRegex(DataError,'OVERNIGHT_EVIDENCE_PATH_INVALID'):
                    checked_bytes(bad,sha(b'SYNTHETIC'),root)

    def test_evidence_document_cannot_promote_source_or_production_authority(self):
        original=Path.read_bytes;target=ROOT/'docs/overnight/evidence.json'
        def spoof(path):
            raw=original(path)
            if path==target:
                doc=json.loads(raw);doc['productionGate']=True;return json.dumps(doc).encode()
            return raw
        with patch.object(Path,'read_bytes',spoof):
            with self.assertRaisesRegex(DataError,'OVERNIGHT_OUTPUT_AUTHORITY_INVALID'):verify_outputs()

if __name__=='__main__':unittest.main()
