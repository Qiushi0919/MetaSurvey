import unittest,json
from pathlib import Path
from unittest.mock import patch
from wave_hb import core,common,run

class FrozenEvidenceTests(unittest.TestCase):
 def test_cost_schema_and_companion_are_code_pinned(self):
  files={r['path'] for r in common.inventory()}
  self.assertIn('docs/wave-hb/CostModel-v1.json',files);self.assertIn('docs/wave-hb/CostModel-v1.md',files)
 def test_mutated_schema_invalidates_release_without_repinning(self):
  old=common.checked_file
  def changed(p,*args):
   raw=old(p,*args)
   if Path(p)==common.ROOT/'docs/wave-hb/CostModel-v1.json':
    x=json.loads(raw);x['actual_profiles_computable']=True;return common.canonical(x)
   return raw
  with patch.object(common,'checked_file',side_effect=changed):
   with self.assertRaisesRegex(ValueError,'HB_RELEASE_DRIFT'):core.context()
 def test_all_actual_native_export_paths_stop_before_source_io(self):
  with patch.object(core,'context',side_effect=AssertionError('no IO permitted')):
   for f in (core.actual_capture,core.forward_append,core.native_issue,core.production,core.export):
    for actor in ({'role':'HUMAN_USER','APPROVE':True},{'role':'LLM','kind':'SIGNED_HASH','actual_days':1}):
     with self.assertRaises(ValueError):f(actor)
 def test_saved_context_cannot_be_self_promoted(self):
  old=run.checked_file
  def changed(p,*args):
   raw=old(p,*args)
   if Path(p)==common.ROOT/'docs/wave-hb/evidence.json':
    x=json.loads(raw);x['context_hash']='sha256:'+'0'*64;return common.canonical(x)
   return raw
  with patch.object(run,'checked_file',side_effect=changed):
   with self.assertRaisesRegex(ValueError,'HB_SAVED_CONTEXT_DRIFT'):run.verify_saved()
 def test_new_epoch_is_bounded_before_any_projection(self):
  with patch.object(run,'payloads',side_effect=AssertionError('no generation')):
   for epoch in ('../escape','FROZEN-G99','ACTUAL-DAY1',1):
    with self.assertRaisesRegex(ValueError,'HB_EPOCH_NOT_BOUNDED'):run.produce(epoch)
 def test_existing_frozen_epoch_never_overwritten(self):
  with patch.object(run,'payloads',side_effect=AssertionError('no generation')):
   with self.assertRaisesRegex(ValueError,'HB_EXCLUSIVE_EPOCH'):run.produce('FROZEN-G1')

if __name__=='__main__':unittest.main()
