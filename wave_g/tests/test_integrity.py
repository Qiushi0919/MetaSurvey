import unittest,json,tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from wave_g import core,common
from wave_g.run import verify_saved,produce

class IntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.objects=core.payloads();cls.context=core.frozen_context()
    def test_saved_summaries_reopen_context_and_originals(self):self.assertEqual(verify_saved()['metadata_artifacts'],7)
    def test_baseline_and_all_direct_dependencies_have_exact_bytes(self):
        self.assertEqual(self.context['immutable_baseline_files'],764)
        for r in self.context['source_dependencies']:self.assertEqual(len(common.checked_reference(r)),r['bytes'])
    def test_factory_is_display_only(self):
        for x in self.objects.values():self.assertIs(core.display(x),x);self.assertFalse(x['productionGate']);self.assertEqual(x['actual_forward_days'],0)
    def test_caller_copy_reseal_has_no_process_issuance(self):
        v=deepcopy(next(iter(self.objects.values())))
        with self.assertRaises(ValueError):core.display(common.seal(v))
    def test_mutation_of_issued_object_rejected(self):
        v=next(iter(self.objects.values()));old=v['body'];v['body']={'caller_approved':True}
        try:
            with self.assertRaises(ValueError):core.display(v)
        finally:v['body']=old
    def test_metadata_has_no_native_transition(self):
        for v in self.objects.values():
            for target in ('SignalEvent','Approval','OrderIntent','Fill','BROKER','PRODUCTION','CLOUD','EVENT_3','RESEARCH_6_18M','HISTORICAL_BACKTEST'):
                with self.assertRaises(ValueError):core.transition(v,target)
    def test_forbidden_actual_paths_stop_before_original_io(self):
        with patch.object(core,'checked_file',side_effect=AssertionError('must not read')),patch.object(core,'frozen_context',side_effect=AssertionError('must not read')):
            for f in (core.run_formal,core.actual_snapshot_b,core.actual_forward,core.production_execute,core.issue_native,core.cloud_export):
                for caller in ({'kind':'HUMAN','APPROVE':True},{'kind':'LLM','APPROVE':True},{'OwnerApproved':True,'license':'PASS','fees':'0','capital':10000}):
                    with self.assertRaises(ValueError):f(caller)
    def test_release_authority_bit_rejected(self):
        old=core.checked_file
        def changed(p,*args):
            raw=old(p,*args)
            if Path(p)==core.ROOT/'docs/wave-g/release.json':
                x=json.loads(raw);x['actual_activation_authorized']=True;return common.canonical(x)
            return raw
        with patch.object(core,'checked_file',side_effect=changed):
            with self.assertRaises(ValueError):core.frozen_context()
    def test_changed_release_code_pin_rejected(self):
        old=core.checked_file
        def changed(p,*args):
            raw=old(p,*args)
            if Path(p)==core.ROOT/'docs/wave-g/release.json':
                x=json.loads(raw);x['code_pins'][0]['sha256']='sha256:'+'0'*64;return common.canonical(x)
            return raw
        with patch.object(core,'checked_file',side_effect=changed):
            with self.assertRaises(ValueError):core.frozen_context()
    def test_checkout_reference_reads_target_and_detects_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d).resolve();(p/'target').write_bytes(b'unchanged')
            r={'path':str(common.BASELINE_ROOT/'target'),'sha256':common.sha(b'unchanged'),'bytes':9}
            with patch.object(common,'ROOT',p):
                self.assertEqual(common.checked_reference(r),b'unchanged')
                (p/'target').write_bytes(b'changed')
                with self.assertRaises(ValueError):common.checked_reference(r)
                (p/'target').unlink()
                with self.assertRaises(ValueError):common.checked_reference(r)
    def test_private_reference_never_relocated(self):
        p=common.ARCHIVE/'start/Diagnostic-Preregistration-G2.json'
        with patch.object(common,'ROOT',Path('/unavailable-clone')):self.assertEqual(common.locate_reference(p),p)
    def test_exclusive_epoch_never_overwrites_saved_results(self):
        with patch('wave_g.run.projected',side_effect=AssertionError('no calculation on existing epoch')):
            with self.assertRaises(ValueError):produce('PREPARATION-G1')
    def test_bad_epoch_blocked_before_context(self):
        with patch('wave_g.run.frozen_context',side_effect=AssertionError('no context')):
            for name in ('../x','G1','PREPARATION-G0',1):
                with self.assertRaises(ValueError):produce(name)

if __name__=='__main__':unittest.main()
