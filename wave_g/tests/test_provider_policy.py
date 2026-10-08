import unittest,json,tempfile
from pathlib import Path
from unittest.mock import patch
from wave_g import provider,policy
from wave_g.common import ARCHIVE,ROOT,UNSET

class ProviderPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ARCHIVE/'provider/materials').mkdir(mode=0o700,exist_ok=True)
    def material(self):return {'version':'1.0.0','redacted':True,'dimensions':{n:{'statement':None,'evidence_paths':[]} for n in provider.DIMENSIONS}}
    def inspect(self,d):
        with tempfile.TemporaryDirectory(dir=ARCHIVE/'provider/materials') as root:
            p=Path(root)/'explicit.json';p.write_text(json.dumps(d));return provider.inspect_redacted_material(p)
    def test_public_product_docs_do_not_close_eight_account_dimensions(self):
        r=provider.evidence_pack();b=r['body'];self.assertEqual(len(b['dimensions']),8)
        self.assertTrue(all(d['state']=='UNKNOWN' for d in b['dimensions']))
        self.assertEqual(b['actual_materials_supplied_this_phase'],0);self.assertEqual(b['actual_expiry'],UNSET)
        for k in ['verified_provider_identity','license_admitted','transport_integrity_verified','cloud_transfer_permitted','redistribution_permitted']:self.assertIs(b[k],False)
    def test_supplied_claims_only_return_presence_not_license(self):
        d=self.material();d['dimensions']['purpose_license']['statement']='Redacted vendor claim, independent verification pending'
        r=self.inspect(d);self.assertEqual(r['body']['dimensions_supplied'],['purpose_license'])
        self.assertEqual(r['body']['state'],'SUPPLIED_NOT_VERIFIED');self.assertFalse(r['body']['seller_license_entitlement_transport_verified'])
        self.assertNotIn('Redacted vendor claim',json.dumps(r));self.assertFalse(r['productionGate'])
    def test_unverified_file_mentions_are_not_opened(self):
        d=self.material();d['dimensions']['validity']['evidence_paths']=['/not-opened/missing.json']
        r=self.inspect(d);self.assertEqual(r['body']['dimensions_supplied'],['validity'])
    def test_unknown_dimensions_or_human_approved_extras_cannot_admit(self):
        for mutation in ('missing','extra','approved'):
            with self.subTest(mutation=mutation):
                d=self.material()
                if mutation=='missing':del d['dimensions']['transport']
                if mutation=='extra':d['dimensions']['entitlement_PASS']=True
                if mutation=='approved':d['HUMAN_APPROVED']=True
                with self.assertRaises(ValueError):self.inspect(d)
    def test_sensitive_key_rejected_before_hash(self):
        d=self.material();d['token']='SYNTHETIC_CREDENTIAL_NOT_REAL'
        with patch.object(provider,'sha',side_effect=AssertionError('sensitive payload must not be hashed')):
            with self.assertRaisesRegex(ValueError,'WG_SENSITIVE_MATERIAL_REJECTED'):self.inspect(d)
    def test_sensitive_statement_rejected_before_hash(self):
        for text in ['https://example.invalid/?token=synthetic','Bearer SYNTHETIC','password=synthetic']:
            with self.subTest(text=text):
                d=self.material();d['dimensions']['endpoint_identity']['statement']=text
                with patch.object(provider,'sha',side_effect=AssertionError('not hashed')):
                    with self.assertRaisesRegex(ValueError,'WG_SENSITIVE_MATERIAL_REJECTED'):self.inspect(d)
    def test_duplicate_keys_cannot_hide_first_material_text(self):
        with tempfile.TemporaryDirectory(dir=ARCHIVE/'provider/materials') as root:
            p=Path(root)/'duplicate.json';p.write_text('{"version":"1.0.0","version":"1.0.0"}')
            with self.assertRaisesRegex(ValueError,'WG_DUPLICATE_MATERIAL_KEYS'):provider.inspect_redacted_material(p)
    def test_material_redacted_boolean_and_version_strict(self):
        for key,value in [('redacted',1),('redacted',False),('version','2.0.0')]:
            with self.subTest(key=key,value=value):
                d=self.material();d[key]=value
                with self.assertRaises(ValueError):self.inspect(d)
    def test_material_not_staged_no_arbitrary_file_read(self):
        with self.assertRaisesRegex(ValueError,'WG_MATERIAL_NOT_STAGED'):provider.inspect_redacted_material(ROOT/'docs/wave-g/Provider-Redacted-Material-Template.json')
    def test_material_float_rejected(self):
        d=self.material();d['dimensions']['order_product']['statement']=1.5
        with self.assertRaises(ValueError):self.inspect(d)
    def test_all_thirty_actual_settings_are_unset(self):
        r=policy.owner_settings();self.assertEqual(len(r),30);self.assertTrue(all(x['status']==UNSET and x['offline_engineering_blocked'] is False for x in r))
    def test_small_live_percentages_are_pending_no_policy_adoption(self):
        r=policy.small_live_policy();d=r['body']['draft'];self.assertFalse(d['adopted_by_owner']);self.assertFalse(d['execution_allowed'])
        self.assertEqual(d['parameters']['pilot_absolute_cap_cny_cents'],UNSET)
        self.assertEqual(r['body']['acceptance'],'OWNER_PENDING');self.assertFalse(r['body']['parameters_are_executable_defaults'])
    def test_each_actual_path_blocks_human_llm_source_money_flags(self):
        for f in [provider.admit_source,provider.cloud_export,policy.execute_small_live,policy.approve_order]:
            for actor in ['HUMAN','LLM','OWNER']:
                with self.subTest(function=f.__name__,actor=actor):
                    with self.assertRaises(ValueError):f(actor=actor,approved=True,PIT_PASS=True,productionGate=True,verified_source=True)
    def test_account_supplied_numbers_cannot_silently_change_baseline(self):
        account=json.loads((ROOT/'config/account-profile.unconfigured.v1.json').read_text());account['settings']['capital_cents']='1'
        original=policy.checked_file
        def file(p,*a,**k):return json.dumps(account).encode() if p==ROOT/'config/account-profile.unconfigured.v1.json' else original(p,*a,**k)
        with patch.object(policy,'checked_file',side_effect=file):
            with self.assertRaisesRegex(ValueError,'WG_OWNER_SETTINGS_BASELINE_CHANGED'):policy.owner_settings()
    def test_policy_accepted_boolean_cannot_turn_draft_into_authority(self):
        d=json.loads((ROOT/'docs/wave-g/Small-Live-Pilot-Policy-v0.json').read_text());d['adopted_by_owner']=True
        original=policy.checked_file
        def file(p,*a,**k):return json.dumps(d).encode() if p==ROOT/'docs/wave-g/Small-Live-Pilot-Policy-v0.json' else original(p,*a,**k)
        with patch.object(policy,'checked_file',side_effect=file):
            with self.assertRaisesRegex(ValueError,'WG_POLICY_CANNOT_BE_ACCEPTED_BY_CALLER'):policy.small_live_policy()

if __name__=='__main__':unittest.main()
