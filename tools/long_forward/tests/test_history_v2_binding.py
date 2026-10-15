"""Synthetic original/receipt tampering checks; no private data or network."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib,json,unittest
from tools.long_forward import history_v2 as h
class BindingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.d=self.root/'official-action';self.d.mkdir()
  self.pdf=self.d/'synthetic.pdf';self.pdf.write_bytes(b'SYNTHETIC PUBLICATION BYTES')
  self.receipt=self.d/'Receipt.json';self.r=dict(url='https://example.invalid/synthetic.pdf',sha256=h.run.sha(self.pdf),http_status=200,path=self.pdf.name,request_started_at='2026-01-01T00:00:00Z',retrieved_at='2026-01-01T00:01:00Z');self.receipt.write_text(json.dumps(self.r))
  self.item=dict(symbol='SYNTHETIC',ex_date='2025-01-01',source_relative_path='official-action/synthetic.pdf',receipt_relative_path='official-action/Receipt.json',source_sha256=h.run.sha(self.pdf),receipt_sha256=h.run.sha(self.receipt),source_url=self.r['url'],printed_issuer_date='2024-12-31')
  self.policy=self.root/'policy.json';self.save()
  self.patches=[patch.object(h.run,'ARCHIVE',self.root),patch.object(h,'INPUT_POLICY',self.policy)]
  for p in self.patches:p.start()
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def save(self):self.policy.write_text(json.dumps(dict(official_reference_adjustments=[self.item])))
 def refs(self):return h.references('2026-01-01T00:02:00Z')
 def test_exact_actual_clock_not_printed_date(self):
  mapping,proofs=self.refs();self.assertEqual(len(mapping),1);self.assertEqual(next(iter(proofs.values()))['available_at'],self.r['retrieved_at'])
 def test_changed_original_rejected(self):
  self.pdf.write_bytes(b'TAMPER');self.assertRaisesRegex(ValueError,'HASH',self.refs)
 def test_changed_receipt_rejected(self):
  self.receipt.write_text('{}');self.assertRaisesRegex(ValueError,'HASH',self.refs)
 def test_future_retrieval_even_with_matching_hash_rejected(self):
  self.r['retrieved_at']='2026-01-02T00:00:00Z';self.receipt.write_text(json.dumps(self.r));self.item['receipt_sha256']=h.run.sha(self.receipt);self.save();self.assertRaisesRegex(ValueError,'CLOCK',self.refs)
 def test_different_document_url_rejected(self):
  self.r['url']='https://example.invalid/other';self.receipt.write_text(json.dumps(self.r));self.item['receipt_sha256']=h.run.sha(self.receipt);self.save();self.assertRaisesRegex(ValueError,'RECEIPT',self.refs)
 def test_outside_path_rejected(self):
  self.item['source_relative_path']='other.pdf';self.save();self.assertRaisesRegex(ValueError,'PATH',self.refs)
 def test_forward_mode_rejected_before_any_read(self):self.assertRaisesRegex(ValueError,'MODE_ONLY',h.build_case,self.root,'synthetic','2026-01-01T00:00:00Z','FORWARD_A')
if __name__=='__main__':unittest.main()
