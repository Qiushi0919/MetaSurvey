import json,signal,unittest,copy,time
from unittest.mock import patch
from wave_hb import preflight,authority,owner_inputs,budget
from wave_hb.common import ROOT,UNSET

class PreflightTests(unittest.TestCase):
 def test_plan_is_not_actual_session_witness(self):
  x=preflight.build_preflight();self.assertFalse(x['is_authority']);self.assertEqual(x['actual_forward_days'],0)
  self.assertFalse(x['body']['planned_session_is_actual_evidence']);self.assertEqual(x['body']['state'],'PASS_OFFLINE_HOLD_ACTUAL')
 def test_calendar_plus_three_each_not_suspension_eight_requests(self):
  jobs=preflight.request_manifest();self.assertEqual(len(jobs),13)
  self.assertEqual([j['api_name'] for j in jobs].count('suspend_d'),3)
  self.assertTrue(all(j['max_rows']==8 for j in jobs if j['api_name']=='suspend_d'))
 def test_scope_increase_rejected(self):
  x=preflight.request_manifest();x.append(copy.deepcopy(x[-1]))
  with self.assertRaisesRegex(ValueError,'HB_REQUEST_MANIFEST_DRIFT'):preflight.verify_manifest(x,'2026-10-08')
 def test_changed_symbol_rejected(self):
  x=preflight.request_manifest();x[1]['params']['ts_code']='000001.SZ'
  with self.assertRaises(ValueError):preflight.verify_manifest(x,'2026-10-08')
 def test_changed_session_rejected(self):
  x=preflight.request_manifest();x[1]['params']['trade_date']='20261007'
  with self.assertRaises(ValueError):preflight.verify_manifest(x,'2026-10-08')
 def test_changed_endpoint_scope_rejected(self):
  x=preflight.request_manifest();x[1]['params']['endpoint']='https://invalid.example'
  with self.assertRaises(ValueError):preflight.verify_manifest(x,'2026-10-08')
 def test_only_definitions_no_network_secret_actual_api(self):
  with patch.object(preflight.collector,'build_plan',side_effect=AssertionError('actual plan forbidden')),patch.object(preflight.collector,'execute_capture',side_effect=AssertionError('actual capture forbidden')),patch.object(preflight.collector,'_source_module',side_effect=AssertionError('credential adapter forbidden')):
   self.assertEqual(len(preflight.build_preflight()['body']['request_manifest']),13)
 def test_no_missing_witness_fabrication(self):
  x=preflight.build_preflight()['body'];self.assertNotIn('session_witness',x)
  self.assertIn('MISSING_ACTUAL_OPEN_EOD',x['stop_conditions'])
 def test_reviewer_and_forward_are_separate_in_order(self):
  s=preflight.STEPS
  self.assertLess(s.index('EXTERNAL_REVIEW_GRANT'),s.index('ISSUE_CURRENT_SNAPSHOT_B'))
  self.assertLess(s.index('EXCLUSIVE_EMPTY_STORE_OR_EXISTING_VERIFIED_HEAD'),s.index('SEPARATE_HUMAN_FORWARD_GRANT'))
 def test_no_night_or_day2_automation(self):self.assertTrue(preflight.build_preflight()['body']['no_scheduler'])
 def test_display_selfhash_cannot_promote(self):
  for target in ('ACTUAL_CAPTURE','SignalEvent','FORWARD_DAY1','CLOUD','PRODUCTION'):
   with self.assertRaises(ValueError):preflight.promote(preflight.build_preflight(),target)

class PublicCandidateTests(unittest.TestCase):
 def candidate(self,byte,key):
  return {'public_der':'302a300506032b6570032100'+byte*32,'key_id':key,'fixture_key':False,
   'provenance':{'identity_label':'SYNTHETIC_SHAPE_ONLY','outside_producer':True,
    'owner_attestation_ref':{'path':'/synthetic/public-attestation-not-installed.txt','sha256':'sha256:'+'a'*64,'bytes':10}}}
 def test_missing_keys_hold_without_fingerprints_or_installs(self):
  x=authority.audit_public_roots();self.assertEqual(x['body']['state'],'HOLD_MISSING_PUBLIC_ROOTS')
  self.assertEqual(x['body']['roles']['HUMAN_USER']['public_key_sha256'],UNSET);self.assertFalse(x['body']['actual_root_installed'])
 def test_distinct_synthetic_shapes_are_only_candidates(self):
  x=authority.audit_public_roots(self.candidate('01','synthetic_owner_0001'),self.candidate('02','synthetic_review_0001'))
  self.assertFalse(x['is_authority']);self.assertFalse(x['body']['actual_authority_issued'])
  self.assertIn('CANDIDATE_REQUIRES',x['body']['state'])
 def test_same_der_different_role_labels_rejected(self):
  with self.assertRaisesRegex(ValueError,'HB_PUBLIC_KEYS_NOT_INDEPENDENT'):authority.audit_public_roots(self.candidate('01','synthetic_owner_0001'),self.candidate('01','synthetic_review_0001'))
 def test_explicit_fixture_key_rejected(self):
  x=self.candidate('01','synthetic_owner_0001');x['fixture_key']=True
  with self.assertRaisesRegex(ValueError,'HB_TEST_KEY_FORBIDDEN'):authority.audit_public_roots(x,None)
 def test_unidentified_key_rejected(self):
  x=self.candidate('01','synthetic_owner_0001');x['provenance']['identity_label']=''
  with self.assertRaisesRegex(ValueError,'HB_PUBLIC_KEY_PROVENANCE_REQUIRED'):authority.audit_public_roots(x,None)
 def test_producer_origin_key_rejected(self):
  x=self.candidate('01','synthetic_owner_0001');x['provenance']['outside_producer']=False
  with self.assertRaises(ValueError):authority.audit_public_roots(x,None)
 def test_no_provenance_reference_rejected(self):
  x=self.candidate('01','synthetic_owner_0001');x['provenance']['owner_attestation_ref']={}
  with self.assertRaises(ValueError):authority.audit_public_roots(x,None)
 def test_private_key_field_rejected_before_fingerprint(self):
  x=self.candidate('01','synthetic_owner_0001');x['private_key']='SYNTHETIC_FORBIDDEN_FIELD'
  with self.assertRaisesRegex(ValueError,'HB_PUBLIC_KEY_SHAPE'):authority.audit_public_roots(x,None)
 def test_pem_private_in_der_rejected(self):
  x=self.candidate('01','synthetic_owner_0001');x['public_der']='PRIVATE_KEY_NOT_A_PUBLIC_DER'
  with self.assertRaises(ValueError):authority.audit_public_roots(x,None)
 def test_candidate_does_not_install_or_sign(self):
  for f in (authority.install,authority.sign):
   with self.assertRaises(ValueError):f({'kind':'LLM','role':'HUMAN_USER','APPROVE':True})

class OwnerTemplateTests(unittest.TestCase):
 def test_thirty_originals_remain_unset(self):
  x=owner_inputs.build_template();self.assertEqual(len(x['body']['original_fields']),30)
  self.assertTrue(all(f['value']==UNSET for f in x['body']['original_fields']))
 def test_supplemental_approval_killswitch_no_default(self):
  d=owner_inputs.build_template()['body']['additional_required_fields']
  for f in ('available_cash_cents','human_order_approval_policy','kill_switch_policy','leverage_allowed','shorting_allowed'):
   self.assertEqual(d[f]['value'],UNSET)
 def test_no_native_profile_or_execution_authority(self):
  x=owner_inputs.build_template();self.assertFalse(x['is_authority']);self.assertFalse(x['body']['native_AccountProfile']);self.assertFalse(x['productionGate'])
 def test_public_rates_not_inherited_as_broker_defaults(self):self.assertFalse(owner_inputs.build_template()['body']['known_public_rates_are_account_defaults'])
 def test_legacy_capital_fill_rejected(self):
  original=owner_inputs.checked_file
  def changed(p,*args):
   raw=original(p,*args)
   if p==ROOT/'config/account-profile.unconfigured.v1.json':
    x=json.loads(raw);x['settings']['capital_cents']='500000';return json.dumps(x).encode()
   return raw
  with patch.object(owner_inputs,'checked_file',side_effect=changed):
   with self.assertRaisesRegex(ValueError,'HB_ORIGINAL_REAL_CONFIG_MUST_REMAIN_UNSET'):owner_inputs.build_template()

class BudgetTests(unittest.TestCase):
 def setUp(self):self.now=0;self.b=budget.OneShotBudget(clock=lambda:self.now)
 def test_phase_exact_boundary_fails_consumes_and_no_retry(self):
  s,_=self.b.begin('capture');self.now=900
  with self.assertRaisesRegex(ValueError,'HB_CAPTURE_TIMEOUT'):self.b.finish('capture',s)
  with self.assertRaises(ValueError):self.b.begin('capture')
 def test_below_phase_boundary_finishes(self):
  s,_=self.b.begin('capture');self.now=899;self.b.finish('capture',s);self.assertEqual(self.b.completed,['capture'])
 def test_phase_order_rejects_append_first(self):
  with self.assertRaises(ValueError):self.b.begin('append')
  self.assertTrue(self.b.failed)
  with self.assertRaises(ValueError):self.b.begin('capture')
 def test_invalid_phase_type_latches(self):
  with self.assertRaisesRegex(ValueError,'HB_PHASE_INVALID_OR_CONSUMED'):self.b.begin({'phase':'capture'})
  self.assertTrue(self.b.failed)
 def test_active_phase_cannot_overlap(self):
  self.b.begin('capture')
  with self.assertRaises(ValueError):self.b.begin('independent_review')
 def test_whole_budget_expires_in_wait_before_review(self):
  s,_=self.b.begin('capture');self.now=1;self.b.finish('capture',s);self.now=3600
  with self.assertRaisesRegex(ValueError,'HB_WHOLE_RUN_TIMEOUT'):self.b.begin('independent_review')
 def test_remaining_whole_time_caps_phase_timer(self):
  s,_=self.b.begin('capture');self.now=1;self.b.finish('capture',s);self.now=3500
  _,limit=self.b.begin('independent_review');self.assertEqual(limit,100)
 def test_begin_reads_one_valid_remaining_budget(self):
  times=iter([0,0,3601]);b=budget.OneShotBudget(clock=lambda:next(times))
  start,limit=b.begin('capture');self.assertEqual((start,limit),(0,900))
  with self.assertRaisesRegex(ValueError,'HB_WHOLE_RUN_TIMEOUT'):b.finish('capture',start)
 def test_clock_cross_before_arm_never_enters_body(self):
  times=iter([0,0,3601]);b=budget.OneShotBudget(clock=lambda:next(times))
  with self.assertRaisesRegex(ValueError,'HB_WHOLE_RUN_TIMEOUT'):
   with b.phase('capture'):self.fail('expired before timer arm')
  self.assertTrue(b.failed);self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
 def test_clock_rewind_fails(self):
  self.now=1;self.b.remaining();self.now=0
  with self.assertRaises(ValueError):self.b.remaining()
 def test_nan_clock_fails(self):
  self.now=float('nan')
  with self.assertRaises(ValueError):self.b.remaining()
 def test_clock_exception_latches(self):
  def bad():raise OSError('SYNTHETIC_CLOCK_FAILURE')
  self.b.clock=bad
  with self.assertRaises(OSError):self.b.remaining()
  self.assertTrue(self.b.failed)
 def test_finish_wrong_start_fails(self):
  s,_=self.b.begin('capture')
  with self.assertRaises(ValueError):self.b.finish('capture',s+1)
  self.assertTrue(self.b.failed)
 def test_existing_signal_timer_not_overwritten(self):
  signal.setitimer(signal.ITIMER_REAL,60)
  try:
   with self.assertRaisesRegex(ValueError,'HB_EXISTING_TIMER_CONFLICT'):
    with self.b.phase('capture'):self.fail('entered conflicting phase')
   self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0],0)
  finally:signal.setitimer(signal.ITIMER_REAL,0)
  self.assertTrue(self.b.failed)
  with self.assertRaises(ValueError):
   with self.b.phase('capture'):self.fail('timer conflict cannot be retried')
 def test_timer_setup_failure_latches_and_restores_handler(self):
  old=signal.getsignal(signal.SIGALRM);real=signal.setitimer
  def fail_setup(which,seconds,*args):
   if seconds>0:raise OSError('SYNTHETIC_TIMER_FAILURE')
   return real(which,seconds,*args)
  with patch.object(signal,'setitimer',side_effect=fail_setup):
   with self.assertRaises(OSError):
    with self.b.phase('capture'):self.fail('setup failure entered phase')
  self.assertTrue(self.b.failed);self.assertEqual(signal.getsignal(signal.SIGALRM),old)
  with self.assertRaises(ValueError):self.b.begin('capture')
 def test_supervisor_thread_failure_latches(self):
  with patch.object(budget.threading,'current_thread',return_value=object()):
   with self.assertRaisesRegex(ValueError,'HB_TIMEOUT_SUPERVISOR_UNAVAILABLE'):
    with self.b.phase('capture'):self.fail('unsupported supervisor entered phase')
  self.assertTrue(self.b.failed)
  with self.assertRaises(ValueError):self.b.begin('capture')
 def test_real_synthetic_interrupt_restores_handler(self):
  old=signal.getsignal(signal.SIGALRM)
  with patch.dict(budget.LIMITS,{'capture':0.005}):
   with self.assertRaisesRegex(ValueError,'HB_CAPTURE_TIMEOUT'):
    with self.b.phase('capture'):time.sleep(0.05)
  self.assertTrue(self.b.failed);self.assertEqual(signal.getsignal(signal.SIGALRM),old);self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
 def test_failure_inside_body_cannot_retry(self):
  with self.assertRaises(RuntimeError):
   with self.b.phase('capture'):raise RuntimeError('SYNTHETIC_BODY_FAILURE')
  with self.assertRaises(ValueError):self.b.begin('capture')
 def test_no_automatic_actual_runner(self):
  with self.assertRaisesRegex(ValueError,'HB_NO_IMPLICIT_ACTUAL_ORCHESTRATION'):budget.actual_run()

if __name__=='__main__':unittest.main()
