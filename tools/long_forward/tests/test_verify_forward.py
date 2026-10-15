"""Temporary synthetic Forward bundles; capture and credential access forbidden."""
from copy import deepcopy
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from tools.long_forward import builder,run,runtime,reporting,verify_forward as v
from tools.long_forward.tests.test_forward import fixture

class VerifyForwardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.archive=Path(self.tmp.name).resolve()
        self.p=fixture()[1];self.p['forward']['review_sessions']=[5,20,40];self.proto=self.archive/'Protocol.json';run.write(self.proto,self.p)
        self.cases={};self.now='2025-01-22T18:00:00+08:00';self.fakepins={'synthetic.py':'sha256:'+'0'*64}
        def build(folder,run_id,run_at,mode='HISTORY',prior=None):
            case=deepcopy(self.cases[Path(folder).name]);case.update(run_id=run_id,run_at=run_at)
            return {'status':'ADMITTED_CURRENT_OBSERVATION_ONLY','case_hash':builder.digest(case),'errors':[]},case
        for module,name,value in [(run,'ARCHIVE',self.archive),(runtime,'ARCHIVE',self.archive),(reporting,'ARCHIVE',self.archive),(v,'ARCHIVE',self.archive),
            (builder,'PROTOCOL',self.proto),(builder,'protocol',lambda:deepcopy(self.p)),(builder,'build_case',build),
            (builder,'verify_provenance',lambda *a,**k:{'fixture':'SYNTHETIC_ONLY'}),(run,'pins',lambda:deepcopy(self.fakepins)),
            (run,'check_freeze',lambda:None),(run,'stamp',lambda:self.now),
            (runtime,'capture',lambda *a,**k:(_ for _ in ()).throw(AssertionError('NO_NETWORK')) )]:
            patcher=patch.object(module,name,value);patcher.start();self.addCleanup(patcher.stop)
    def attempt(self,end=21,name='FIRST',case_change=None):
        c,_=fixture(end=end);c['protocol_ref']=builder.digest(self.p);self.now=c['run_at'];capture=self.archive/('capture-'+name.lower());capture.mkdir()
        if case_change:case_change(c)
        self.cases[capture.name]=c
        return runtime.execute(capture,name)
    def rewrite(self,folder,name,value):
        path=folder/name;path.unlink();run.write(path,value);(folder/'Bundle.json').unlink();run.seal(folder)
    def test_initial_and_two_step_forward_replayed_exactly(self):
        first,event=self.attempt();self.assertEqual(event['status'],'PLAN_FROZEN')
        d=v.verify_folder(first);self.assertEqual(d['State.json']['result']['daily'],[])
        second,event=self.attempt(22,'SECOND');self.assertEqual(event['status'],'PLAN_FROZEN')
        d=v.verify_folder(second);self.assertEqual(len(d['State.json']['result']['daily']),1);self.assertEqual(len(d['Transitions.json']),2)
    def test_modified_state_resealed_still_rejected(self):
        folder,_=self.attempt();data=reporting.bundle(folder);state=data['State.json'];state['runtime']['cash_cents']+=1
        from tools.long_forward.forward import _sealed
        self.rewrite(folder,'State.json',_sealed(state))
        with self.assertRaisesRegex(ValueError,'FINAL_STATE_REPLAY'):v.verify_folder(folder)
    def test_codepins_change_rejected(self):
        folder,_=self.attempt();self.fakepins['synthetic.py']='sha256:'+'1'*64
        with self.assertRaisesRegex(ValueError,'CODE_PROTOCOL'):v.verify_folder(folder)
    def test_prior_case_path_outside_archive_rejected(self):
        self.attempt();folder,_=self.attempt(22,'SECOND');event=reporting.bundle(folder)['Event.json'];event['prior_case']='/tmp/unrelated.json';self.rewrite(folder,'Event.json',event)
        with self.assertRaisesRegex(ValueError,'PRIOR_CASE_BINDING'):v.verify_folder(folder)
    def test_missing_transition_cannot_claim_valid_freeze(self):
        folder,_=self.attempt();self.rewrite(folder,'Transitions.json',[])
        with self.assertRaisesRegex(ValueError,'MISSING_REQUIRED_TRANSITION'):v.verify_folder(folder)
    def test_rehashed_plan_mutation_rejected(self):
        folder,_=self.attempt();plan=reporting.bundle(folder)['Plan.json'];plan['pending_buys']=[]
        from tools.long_forward.forward import _sealed
        self.rewrite(folder,'Plan.json',_sealed(plan))
        with self.assertRaisesRegex(ValueError,'FINAL_PLAN_REPLAY'):v.verify_folder(folder)
    def test_manifest_symlink_rejected(self):
        folder,_=self.attempt();p=folder/'Bundle.json';outside=self.archive/'copy.json';p.rename(outside);p.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'MANIFEST_ALIAS'):v.verify_folder(folder)
    def test_same_execution_waiting_keeps_original_plan(self):
        first,_=self.attempt();folder,event=self.attempt(21,'WAIT')
        self.assertEqual(event['status'],'WAITING_EXECUTION_SESSION');d=v.verify_folder(folder)
        self.assertEqual(d['Plan.json'],reporting.bundle(first)['Plan.json']);self.assertEqual(d['Transitions.json'],[])
    def test_recorded_real_prepare_failure_replayed(self):
        def change(c):c['execution_calendar']=[]
        folder,event=self.attempt(case_change=change)
        self.assertEqual(event['status'],'FORWARD_BLOCKED');self.assertEqual(event['failed_operation'],'prepare')
        self.assertEqual(v.verify_folder(folder)['Event.json']['status'],'FORWARD_BLOCKED')
    def test_successful_settle_then_prepare_failure_preserves_completed_state(self):
        first,_=self.attempt();original=reporting.bundle(first)['State.json']
        folder,event=self.attempt(22,'FAIL_AFTER_SETTLE',lambda c:c.update(execution_calendar=c['execution_calendar'][:1]))
        self.assertEqual(event['status'],'SETTLED_PREPARE_BLOCKED');self.assertEqual(event['failed_operation'],'prepare')
        self.assertTrue(event['completed_state_preserved'])
        data=v.verify_folder(folder);self.assertEqual(len(data['Transitions.json']),1)
        self.assertEqual(data['Transitions.json'][0]['operation'],'settle')
        self.assertNotEqual(data['State.json'],original)
        self.assertEqual(data['State.json'],data['Transitions.json'][0]['result']['state'])
        self.assertEqual(len(data['State.json']['result']['daily']),1);self.assertIsNone(data['State.json']['active_plan'])
        active=run.read(self.archive/'forward/ACTIVE/CURRENT.json');self.assertEqual(active['directory'],folder.name)
    def test_retry_after_completed_settlement_only_prepares_no_duplicate_fill(self):
        self.attempt();failed,event=self.attempt(22,'FAIL_AFTER_SETTLE',lambda c:c.update(execution_calendar=c['execution_calendar'][:1]))
        completed=v.verify_folder(failed)['State.json'];folder,event=self.attempt(22,'RESUME_PREPARE')
        self.assertEqual(event['status'],'PLAN_FROZEN');data=v.verify_folder(folder)
        self.assertEqual([t['operation'] for t in data['Transitions.json']],['prepare'])
        self.assertEqual(data['State.json']['result']['ledger'],completed['result']['ledger'])
        self.assertEqual(data['State.json']['result']['fills'],completed['result']['fills'])
        self.assertEqual(len(data['State.json']['result']['daily']),1)
        self.assertEqual(data['State.json']['active_plan']['execution_session'],fixture(end=22)[0]['execution_calendar'][0]['date'])
    def test_next_day_after_prepare_failure_marks_missed_not_expired_old_plan(self):
        self.attempt();failed,_=self.attempt(22,'FAIL_AFTER_SETTLE',lambda c:c.update(execution_calendar=c['execution_calendar'][:1]))
        completed=v.verify_folder(failed)['State.json'];folder,event=self.attempt(23,'NEXT_DAY')
        self.assertEqual(event['status'],'PLAN_FROZEN');data=v.verify_folder(folder)
        self.assertEqual([t['operation'] for t in data['Transitions.json']],['settle_mark_only','prepare'])
        self.assertEqual(data['State.json']['result']['fills'],completed['result']['fills'])
        self.assertEqual(data['State.json']['result']['daily'][-1]['observation_status'],'MISSED_NO_PLAN_MARK_ONLY')
    def test_missed_mark_then_prepare_failure_also_preserves_completed_mark(self):
        self.attempt();self.attempt(22,'FAIL_AFTER_SETTLE',lambda c:c.update(execution_calendar=c['execution_calendar'][:1]))
        folder,event=self.attempt(23,'FAIL_AFTER_MARK',lambda c:c.update(execution_calendar=c['execution_calendar'][:1]))
        self.assertEqual(event['status'],'MISSED_MARK_PREPARE_BLOCKED')
        self.assertEqual(event['completed_transition_status'],'MISSED_NO_PLAN_MARK_ONLY')
        data=v.verify_folder(folder);self.assertIsNone(data['State.json']['active_plan'])
        self.assertEqual(data['State.json']['result']['daily'][-1]['observation_status'],'MISSED_NO_PLAN_MARK_ONLY')
        self.assertEqual(sum(d['observation_status']=='FROZEN_PLAN_SETTLED' for d in data['State.json']['result']['daily']),1)
        self.assertEqual(run.read(self.archive/'forward/ACTIVE/CURRENT.json')['directory'],folder.name)
    def test_resealed_rollback_after_successful_settlement_is_rejected(self):
        first,_=self.attempt();original=reporting.bundle(first)['State.json'];failed,_=self.attempt(22,'FAIL_AFTER_SETTLE',lambda c:c.update(execution_calendar=c['execution_calendar'][:1]))
        self.rewrite(failed,'State.json',original)
        with self.assertRaisesRegex(ValueError,'FINAL_STATE_REPLAY'):v.verify_folder(failed)
    def test_partial_failure_missing_exact_failure_clock_is_unverifiable(self):
        self.attempt();folder,event=self.attempt(22,'FAIL_AFTER_SETTLE',lambda c:c.update(execution_calendar=c['execution_calendar'][:1]))
        event.pop('failed_at');self.rewrite(folder,'Event.json',event)
        with self.assertRaisesRegex(ValueError,'FAILURE_OPERATION_CLOCK_REQUIRED'):v.verify_folder(folder)
    def test_failed_source_attempt_keeps_prior_state_and_active_pointer(self):
        first,_=self.attempt();original=builder.build_case
        def blocked(folder,*args,**kwargs):
            if Path(folder).name=='capture-blocked':return {'status':'DATA_BLOCKED','errors':[{'detail':'SYNTHETIC_MISSING_INPUT'}]},None
            return original(folder,*args,**kwargs)
        with patch.object(builder,'build_case',side_effect=blocked):
            folder,event=self.attempt(22,'BLOCKED');self.assertEqual(event['status'],'SOURCE_OR_INPUT_BLOCKED')
            self.assertEqual(v.verify_folder(folder)['State.json'],reporting.bundle(first)['State.json'])
        self.assertEqual(run.read(self.archive/'forward/ACTIVE/CURRENT.json')['directory'],first.name)
    def test_claimed_failure_that_would_succeed_rejected(self):
        folder,_=self.attempt();data=reporting.bundle(folder);event=data['Event.json'];event.update(status='FORWARD_BLOCKED',failed_operation='prepare',failed_at=self.now,errors=[{'type':'ValueError','detail':'CLAIMED_FAILURE_DID_NOT_OCCUR'}])
        self.rewrite(folder,'Event.json',event);self.rewrite(folder,'Transitions.json',[])
        with self.assertRaisesRegex(ValueError,'CLAIMED_FAILURE_DID_NOT_OCCUR'):v.verify_folder(folder)
    def test_invalid_capture_path_rejected_before_builder(self):
        folder,_=self.attempt();event=reporting.bundle(folder)['Event.json'];event['capture_dir']='/tmp/capture-foreign';self.rewrite(folder,'Event.json',event)
        with self.assertRaisesRegex(ValueError,'CAPTURE_SCOPE'):v.verify_folder(folder)

if __name__=='__main__':unittest.main()
