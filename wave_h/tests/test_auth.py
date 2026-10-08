"""Offline signature verification never installs an actual authority root."""
import copy,json,subprocess,unittest
from wave_h import auth
from wave_h.common import canonical,ROOT,SYMBOLS,bindings,digest,sha

FIXTURE_JS=r'''
import {createPrivateKey,createPublicKey,sign} from 'node:crypto';
let s='';for await(const c of process.stdin)s+=c;const x=JSON.parse(s);
const seed=Buffer.alloc(32,81);const key=createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),seed]),type:'pkcs8',format:'der'});
process.stdout.write(JSON.stringify({public_der:createPublicKey(key).export({type:'spki',format:'der'}).toString('hex'),signature:sign(null,Buffer.from(x.message,'base64'),key).toString('hex')}));
'''
def fixture(body):
    import base64
    p=subprocess.run([auth._node(),'--input-type=module','-e',FIXTURE_JS],input=canonical({'message':base64.b64encode(canonical(body)).decode()}),stdout=subprocess.PIPE,check=True)
    return json.loads(p.stdout)

class AuthenticationTests(unittest.TestCase):
    def test_valid_crypto_is_not_capability(self):
        body={'kind':'OFFLINE_TEST_SIGNATURE','role':'TEST_HUMAN','actual_forward_days':0};f=fixture(body)
        self.assertTrue(auth.fixture_signature_verify(f['public_der'],body,f['signature']))
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.capture_capability({'body':body,**f})
    def test_signature_mutated_body(self):
        body={'kind':'OFFLINE_TEST_SIGNATURE','actual_forward_days':0};f=fixture(body)
        self.assertFalse(auth.fixture_signature_verify(f['public_der'],dict(body,actual_forward_days=1),f['signature']))
    def test_signature_mutated_key(self):
        body={'role':'TEST_REVIEWER'};f=fixture(body)
        bad=f['public_der'][:-2]+('00' if f['public_der'][-2:]!='00' else '01')
        self.assertFalse(auth.fixture_signature_verify(bad,body,f['signature']))
    def test_signature_mutated_signature(self):
        body={'kind':'TEST'};f=fixture(body)
        self.assertFalse(auth.fixture_signature_verify(f['public_der'],body,'0'*128))
    def test_no_private_key_input(self):
        with self.assertRaises(ValueError):auth.fixture_signature_verify('private-key',{},'0'*128)
    def test_non_hex_signature(self):
        with self.assertRaises(ValueError):auth.fixture_signature_verify('0'*88,{},'x'*128)
    def test_float_body_rejected(self):
        with self.assertRaises(ValueError):auth.fixture_signature_verify('0'*88,{'rate':0.3},'0'*128)
    def test_duplicate_signed_json_rejected(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):auth._json(b'{"role":"HUMAN_USER","role":"LLM"}')
    def test_enrollment_is_not_producer_argument(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.ensure_actual_enrolled()
    def test_capture_before_untrusted_io(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.capture_capability({'path':'/never-read','role':'HUMAN_USER'})
    def test_forward_before_untrusted_io(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.forward_capability({'path':'/never-read','role':'HUMAN_USER'})
    def test_review_before_untrusted_io(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.review_capability({'path':'/never-read','role':'INDEPENDENT_REVIEWER'})
    def test_llm_human_label(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.capture_capability({'actor':'HUMAN_USER','issuer':'LLM','approved':True})
    def test_producer_selfhash(self):
        obj={'actor':'INDEPENDENT_REVIEWER','approved':True};obj['hash']=digest(obj)
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.review_capability(obj)
    def test_fixture_capture_handle(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.require_capture({'kind':'TEST_CAPTURE'},sha(b'p'))
    def test_capture_not_forward(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.require_forward({'kind':'CAPTURE'},sha(b's'))
    def test_forward_not_review(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.require_review({'kind':'FORWARD'},sha(b'c'))
    def test_persisted_capture_without_root(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.verify_persisted_capture({'valid_at':'2026-10-08'})
    def test_persisted_review_without_root(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.verify_persisted_review({'signed':True})
    def test_persisted_forward_without_root(self):
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.verify_persisted_forward({'signed':True})
    def test_opaque_copy_not_registered(self):
        h=auth._Capability();self.assertIsNot(h,copy.copy(h));self.assertIsNot(h,copy.deepcopy(h))
        with self.assertRaisesRegex(ValueError,'NOT_ENROLLED'):auth.require_capture(h,sha(b'p'))
    def test_caller_clock_cannot_authorize_yesterday(self):
        with self.assertRaisesRegex(ValueError,'CLOCK_FORBIDDEN'):auth.capture_capability({},'2026-10-08T08:00:00Z')
    def test_native_forbidden(self):
        with self.assertRaisesRegex(ValueError,'NATIVE'):auth.issue_native({'approved':True})
    def test_trade_forbidden(self):
        with self.assertRaisesRegex(ValueError,'TRADE'):auth.execute_trade({'forward_permit':True})
    def test_broker_forbidden(self):
        with self.assertRaisesRegex(ValueError,'BROKER'):auth.connect_broker({})
    def test_cloud_forbidden(self):
        with self.assertRaisesRegex(ValueError,'CLOUD'):auth.cloud_export({})

class SignedBodyShapeTests(unittest.TestCase):
    def body(self,kind='CAPTURE'):
        role,perms,scope=auth._KINDS[kind]
        return {'version':'1.0.0','kind':kind,'phase':'H_B_FRESH_OWNER_AUTH','role':role,
          'namespace':'ACTUAL_FORWARD_NO_DECISION','permissions':list(perms),'session':'2026-10-08','symbols':list(SYMBOLS),
          'bindings':bindings(),'source_identity':'OWNER_PROVIDED_MONTHLY_GATEWAY_UNVERIFIED','source_schema_version':'TUSHARE_NATIVE_EOD_REQUEST_FIELDS_V1',
          'issued_at':'2026-10-08T08:00:00Z','not_before':'2026-10-08T07:59:00Z','expires_at':'2026-10-08T09:00:00Z',
          'nonce':'OFFLINE_TEST_NONCE_123456','scope':{k:('2026-10-08' if k=='session' else sha(k.encode())) for k in scope}}
    def test_capture_valid_shape_not_authority(self):auth._shape(self.body(),'CAPTURE')
    def test_review_valid_shape_not_authority(self):auth._shape(self.body('REVIEW'),'REVIEW')
    def test_forward_valid_shape_not_authority(self):auth._shape(self.body('FORWARD'),'FORWARD')
    def test_wrong_permissions(self):
        x=self.body();x['permissions'].append('ORDER')
        with self.assertRaises(ValueError):auth._shape(x,'CAPTURE')
    def test_wrong_strategy(self):
        x=self.body();x['bindings']['strategy_hash']=sha(b'wrong')
        with self.assertRaisesRegex(ValueError,'INVALIDATED'):auth._shape(x,'CAPTURE')
    def test_wrong_policy(self):
        x=self.body();x['bindings']['policy_hash']=sha(b'wrong')
        with self.assertRaisesRegex(ValueError,'INVALIDATED'):auth._shape(x,'CAPTURE')
    def test_wrong_code(self):
        x=self.body();x['bindings']['code_hash']=sha(b'wrong')
        with self.assertRaisesRegex(ValueError,'INVALIDATED'):auth._shape(x,'CAPTURE')
    def test_wrong_symbols(self):
        x=self.body();x['symbols']=['000001.SZ']
        with self.assertRaises(ValueError):auth._shape(x,'CAPTURE')
    def test_wrong_source(self):
        x=self.body();x['source_identity']='VERIFIED'
        with self.assertRaises(ValueError):auth._shape(x,'CAPTURE')
    def test_wrong_namespace(self):
        x=self.body();x['namespace']='STAGING'
        with self.assertRaises(ValueError):auth._shape(x,'CAPTURE')
    def test_wrong_role(self):
        x=self.body();x['role']='LLM'
        with self.assertRaises(ValueError):auth._shape(x,'CAPTURE')
    def test_capture_as_forward(self):
        with self.assertRaises(ValueError):auth._shape(self.body(),'FORWARD')
    def test_review_scope_missing_originals(self):
        x=self.body('REVIEW');del x['scope']['originals_digest']
        with self.assertRaises(ValueError):auth._shape(x,'REVIEW')
    def test_forward_wrong_session(self):
        x=self.body('FORWARD');x['scope']['session']='2026-10-09'
        with self.assertRaises(ValueError):auth._shape(x,'FORWARD')
    def test_date_only_authority_clock(self):
        x=self.body();x['issued_at']='2026-10-08'
        with self.assertRaises(ValueError):auth._shape(x,'CAPTURE')
    def test_cross_day_expiry(self):
        x=self.body();x['expires_at']='2026-10-09T09:00:00Z'
        with self.assertRaises(ValueError):auth._shape(x,'CAPTURE')
    def test_reversed_expiry(self):
        x=self.body();x['expires_at']='2026-10-08T07:00:00Z'
        with self.assertRaises(ValueError):auth._shape(x,'CAPTURE')
    def test_missing_nonce(self):
        x=self.body();x['nonce']=''
        with self.assertRaises(ValueError):auth._shape(x,'CAPTURE')
    def test_extra_approval_field(self):
        x=self.body();x['nativeApproval']=True
        with self.assertRaises(ValueError):auth._shape(x,'CAPTURE')
    def test_future_review_issued_time_cannot_act_early(self):
        x=self.body('REVIEW')
        with self.assertRaisesRegex(ValueError,'NOT_ISSUED'):auth.validate_time_window(x,'REVIEW','2026-10-08T07:59:30Z')
    def test_future_forward_issued_time_cannot_act_early(self):
        x=self.body('FORWARD')
        with self.assertRaisesRegex(ValueError,'NOT_ISSUED'):auth.validate_time_window(x,'FORWARD','2026-10-08T07:59:30Z')
    def test_future_capture_issued_time_cannot_act_early(self):
        x=self.body()
        with self.assertRaisesRegex(ValueError,'NOT_ISSUED'):auth.validate_time_window(x,'CAPTURE','2026-10-08T07:59:30Z')
    def test_nanosecond_before_issuance_is_not_valid(self):
        x=self.body('REVIEW');x['issued_at']='2026-10-08T08:00:00.000000002Z'
        with self.assertRaisesRegex(ValueError,'NOT_ISSUED'):auth.validate_time_window(x,'REVIEW','2026-10-08T08:00:00.000000001Z')
    def test_nanosecond_before_expiry_remains_valid(self):
        x=self.body();x['expires_at']='2026-10-08T08:00:00.000000002Z'
        self.assertTrue(auth.validate_time_window(x,'CAPTURE','2026-10-08T08:00:00.000000001Z'))
    def test_exact_nanosecond_expiry_rejected(self):
        x=self.body();x['expires_at']='2026-10-08T08:00:00.000000002Z'
        with self.assertRaisesRegex(ValueError,'EXPIRED'):auth.validate_time_window(x,'CAPTURE','2026-10-08T08:00:00.000000002Z')
    def test_persisted_old_valid_grant_does_not_expire(self):
        self.assertTrue(auth.validate_time_window(self.body('FORWARD'),'FORWARD',persisted=True))
    def test_current_wall_clock_date_cannot_use_old_grant(self):
        with self.assertRaises(ValueError):auth.validate_time_window(self.body(),'CAPTURE','2026-10-09T08:00:00Z')
