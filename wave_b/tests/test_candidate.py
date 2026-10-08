import copy,unittest
from pathlib import Path
from unittest.mock import patch
from wave_b.core import fixture_inputs,require_result,require_inputs,reject_real_consumer
from wave_b.candidate import analyze,CATEGORIES,GATES,ZERO_COUNTS

class CandidateTests(unittest.TestCase):
    def test_eight_categories_are_in_order_and_never_admitted(self):
        r=analyze(fixture_inputs());self.assertEqual(tuple(c['category'] for c in r['body']['coverage_matrix_v2']),CATEGORIES)
        self.assertTrue(all(c['business_admission']=='BLOCKED' for c in r['body']['coverage_matrix_v2']))
    def test_absent_owner_supplier_evidence_is_blocking(self):
        r=analyze(fixture_inputs());self.assertEqual(r['body']['supplier_evidence'],'ABSENT_BY_EXPLICIT_OWNER_REPLY');self.assertEqual(r['body']['owner_admission_recommendation'],'NOT_READY')
    def test_technical_access_is_not_entitlement(self):
        i=fixture_inputs([{'api_name':'stock_st','rows':[],'technical_access_observed':True}]);r=analyze(i)
        m=next(v for v in r['body']['api_access_matrix'] if v['api']=='stock_st')
        self.assertEqual(m['technical_access_observed_new_requests'],1);self.assertFalse(m['entitlement_inventory_verified'])
    def test_all_higher_gates_and_real_counts_are_blocked(self):
        b=analyze(fixture_inputs())['body'];self.assertEqual(b['counts'],{k:0 for k in ZERO_COUNTS});self.assertEqual(b['gates'],{k:'BLOCKED' for k in GATES})
    def test_actual_config_remains_unset_not_legacy_defaults(self):
        b=analyze(fixture_inputs())['body'];self.assertEqual(b['unknown_account_parameters'],{'count':30,'state':'UNSET_REQUIRED'});self.assertEqual(b['real_sizing'],'UNSET_REQUIRED')
    def test_history_and_business_conditions_remain_unclosed(self):
        r=analyze(fixture_inputs());self.assertFalse(r['historical_visibility_proven']);self.assertEqual(r['body']['conditions_delta']['closed_ids'],[])
    def test_all_five_real_consumers_reject_even_valid_diagnostic(self):
        r=analyze(fixture_inputs());require_result(r)
        for c in ['BrainPacket','ResearchAssessment','ResearchCard','Candidate','Signal']:
            with self.assertRaisesRegex(ValueError,'QUARANTINED'):reject_real_consumer(r,c)
    def test_resealed_copy_is_not_registered_admission(self):
        r=analyze(fixture_inputs());x=copy.deepcopy(r);x['source_admission']='ADMITTED'
        with self.assertRaises(ValueError):require_result(x)
    def test_mutated_permission_flags_invalidate_object(self):
        r=analyze(fixture_inputs());r['productionGate']=True
        with self.assertRaises(ValueError):require_result(r)
    def test_any_component_code_change_invalidates_candidate(self):
        r=analyze(fixture_inputs());original=Path.read_bytes
        def changed(p):return original(p)+(b'changed' if p.name=='industry.py' and p.parent.name=='wave_b' else b'')
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'SOURCE_OR_CODE_CHANGED'):require_result(r)
    def test_changed_raw_identity_and_request_hash_changes_candidates(self):
        q={'api_name':'stock_st','rows':[]};a=analyze(fixture_inputs([q]));q['raw_sha256']='sha256:'+'1'*64;b=analyze(fixture_inputs([q]));self.assertNotEqual(a['input_identity'],b['input_identity'])
    def test_deterministic_replay_has_equal_hash_and_no_input_mutation(self):
        i=fixture_inputs();before=copy.deepcopy(i);a=analyze(i);b=analyze(i);self.assertEqual(a['content_hash'],b['content_hash']);self.assertEqual(i,before)

if __name__=='__main__':unittest.main()

class ActualRuleBindingRegression(unittest.TestCase):
    def test_actual_conditions_byte_change_invalidates_registered_candidate(self):
        from wave_b.core import load_inputs
        i=load_inputs();r=analyze(i);original=Path.read_bytes
        def changed(p):return original(p)+(b' ' if p.name=='conditions.json' and p.parent.name=='overnight' else b'')
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'SOURCE_OR_CODE_CHANGED'):require_result(r)
    def test_original_contract_rule_change_invalidates_registered_input(self):
        from wave_b.core import load_inputs
        i=load_inputs();original=Path.read_bytes
        def changed(p):return original(p)+(b' ' if p.name=='AccountProfile.schema.json' and p.parent.name=='v1' else b'')
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'SOURCE_OR_CODE_CHANGED'):require_inputs(i)
    def test_new_schema_rule_change_invalidates_registered_input(self):
        from wave_b.core import load_inputs
        i=load_inputs();original=Path.read_bytes
        def changed(p):return original(p)+(b' ' if p.name=='AdmissionCandidate.schema.json' else b'')
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'SOURCE_OR_CODE_CHANGED'):require_inputs(i)
    def test_changed_baseline_file_rejects_new_loading_without_repinning(self):
        from wave_b.core import load_inputs
        original=Path.read_bytes
        def changed(p):return original(p)+(b' ' if p.name=='conditions.json' and p.parent.name=='overnight' else b'')
        with patch.object(Path,'read_bytes',changed):
            with self.assertRaisesRegex(ValueError,'BASELINE_OR_RELEASE_CHANGED'):load_inputs()
