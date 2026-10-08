import copy, unittest
from wave_b.core import fixture_inputs, observations, require_cutoff, reject_real_consumer
from wave_b.industry import analyze

def fixture(out='20260101',entered='20250601',new='N',blocked=False,rows=None):
    return fixture_inputs([{'api_name':'index_member_all','params':{'is_new':new},'response_blocked':blocked,
        'rows':rows if rows is not None else [{'ts_code':'603993.SH','in_date':entered,'out_date':out,'is_new':new,'l1_name':'SYNTHETIC'}]}])

class IndustryTests(unittest.TestCase):
    def test_valid_interval_remains_non_historical_candidate(self):
        r=analyze(fixture())['body']['industry_membership_candidate']['observations'][0]
        self.assertTrue(r['effective_interval']['ordering_known']);self.assertFalse(r['historical_label_issued']);self.assertIsNone(r['published_at'])
    def test_blank_end_preserved_not_infinity(self):
        r=analyze(fixture(out=''))['body']['industry_membership_candidate']['observations'][0]
        self.assertEqual(r['membership_status'],'UNKNOWN');self.assertEqual(r['reported_values']['out_date'],'');self.assertFalse(r['empty_out_date_is_infinity'])
    def test_null_end_preserved_unknown(self):
        self.assertIsNone(analyze(fixture(out=None))['body']['industry_membership_candidate']['observations'][0]['reported_values']['out_date'])
    def test_reversed_boundary_is_ambiguous(self):
        self.assertEqual(analyze(fixture(out='20250101'))['body']['industry_membership_candidate']['observations'][0]['membership_status'],'AMBIGUOUS')
    def test_current_flag_does_not_backfill_cutoff(self):
        i=fixture(new='Y');o=observations(i,'index_member_all')[0]
        with self.assertRaisesRegex(ValueError,'OBSERVATION_NOT_AVAILABLE_AT_CUTOFF'):require_cutoff(o,'2025-06-01T00:00:00Z')
    def test_empty_history_no_negative_proof(self):
        r=analyze(fixture(rows=[]))['body'];self.assertEqual(r['industry_membership_candidate']['observation_count'],0);self.assertFalse(r['industry_pit_known_gaps']['history_negative_or_completeness_proven'])
    def test_blocked_siblings_retained(self):
        rows=[{'ts_code':'603993.SH','in_date':'20250601','out_date':v,'is_new':'N'} for v in ['20260101','']]
        r=analyze(fixture(blocked=True,rows=rows))['body']['industry_membership_candidate']['observations']
        self.assertEqual(len(r),2);self.assertTrue(all(x['response_blocked'] for x in r))
    def test_current_filter_mismatch_blocks_without_deleting(self):
        r=analyze(fixture(rows=[{'ts_code':'603993.SH','in_date':'20250601','out_date':'20260101','is_new':'Y'}]))['body']['industry_membership_candidate']['observations'][0]
        self.assertTrue(r['response_blocked'])
    def test_versions_and_ordinals_are_not_collapsed(self):
        row={'ts_code':'603993.SH','in_date':'20250601','out_date':'20260101','is_new':'N'}
        r=analyze(fixture(rows=[row,copy.deepcopy(row)]))['body']['industry_membership_candidate']['observations']
        self.assertEqual(len(r),2);self.assertNotEqual(r[0]['source_ref']['row_ordinal'],r[1]['source_ref']['row_ordinal'])
    def test_all_real_consumers_reject_quarantine(self):
        r=analyze(fixture())
        for c in ['BrainPacket','ResearchAssessment','ResearchCard','Candidate','Signal']:
            with self.assertRaisesRegex(ValueError,'QUARANTINED'):reject_real_consumer(r,c)
    def test_copy_or_mutation_is_not_registered_authority(self):
        i=fixture()
        with self.assertRaises(ValueError):analyze(copy.deepcopy(i))
        i['new'][0]['rows'][0]['out_date']='20261005'
        with self.assertRaises(ValueError):analyze(i)
    def test_input_stays_lossless_after_repeat(self):
        i=fixture(out='');before=copy.deepcopy(i);a=analyze(i);b=analyze(i)
        self.assertEqual(i,before);self.assertEqual(a['content_hash'],b['content_hash'])

if __name__=='__main__':unittest.main()
