import copy
import unittest
from overnight.data.dataset import load_verified_dataset, DataError
from overnight.admission.dry_run import build_readiness, CATEGORIES

class AdmissionTests(unittest.TestCase):
    def test_all_eight_categories_separate_engineering_readiness_from_permission(self):
        result=build_readiness(load_verified_dataset())
        self.assertEqual([r['category'] for r in result['categories']],list(CATEGORIES))
        self.assertTrue(all(r['admission_status']=='BLOCKED' and r['state']=='QUARANTINED' for r in result['categories']))
        self.assertEqual(result['closed_business_condition_ids'],[])
        self.assertFalse(result['real_snapshot_B_ready']); self.assertFalse(result['pilot_ready'])
        self.assertEqual(sum(r['observed_physical_rows'] for r in result['categories']),2786)

    def test_physical_overlap_and_unknown_fields_do_not_gain_authority(self):
        result=build_readiness(load_verified_dataset()); categories={r['category']:r for r in result['categories']}
        self.assertEqual(categories['RAW_BARS']['observed_physical_rows'],990)
        self.assertEqual(categories['RAW_BARS']['coverage_physical_rows'],981)
        self.assertEqual(categories['ANNOUNCEMENTS']['actual_apis'],[])
        self.assertEqual(categories['FINANCIAL_REVISIONS']['observed_physical_rows'],63)
        self.assertIn('BLANK_EFFECTIVE_END_DATE_SEMANTICS_UNSET_REQUIRED',categories['INDUSTRY_MEMBERSHIP']['blocking_reasons'])

    def test_copied_or_mutated_source_cannot_become_a_dry_run_authority(self):
        source=load_verified_dataset()
        with self.assertRaises(DataError): build_readiness(copy.deepcopy(source))
        for field,value in (('productionGate',True),('source_admission','ADMITTED'),('historical_visibility_proven',True)):
            source=load_verified_dataset(); source[field]=value
            with self.assertRaises(DataError): build_readiness(source)

    def test_repeat_dry_run_hash_is_deterministic_without_any_admission_or_signer(self):
        first=build_readiness(load_verified_dataset()); second=build_readiness(load_verified_dataset())
        self.assertEqual(first,second)
        for k in ('new_source_policies','new_source_observations','admitted_clock_evidence_issued','real_snapshots_issued',
                  'real_receipts_issued','real_packets_issued','real_cards_issued','authenticated_requests_this_run','credential_lookups_this_run'):
            self.assertEqual(first[k],0)
        self.assertEqual(first['all_actual_account_parameters'],'UNSET_REQUIRED')
        self.assertIn('20_ACTUAL',first['C30'])

if __name__ == '__main__': unittest.main()
