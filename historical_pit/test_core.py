"""Real-original read-only audit plus explicitly synthetic adverse fixtures."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from dual_track.common import ref,write_new,reopen,sha,canonical
from historical_pit import core as c

MANIFEST=Path('/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/public-calendar/Calendar-Originals-Manifest.json')


class HistoricalPITTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory,cls.dates,cls.coverage,cls.originals=c.read_current_originals()
        cls.calendar=c.calendar_structure(ref(MANIFEST))

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()

    def snapshot(self,records=None,cutoff='2025-06-03T15:30:00+08:00',mode='OBSERVED_AT_TIME'):
        return c.candidate_snapshot('603993.SH','2025-06-03',cutoff,self.inventory if records is None else records,mode)

    def matrix(self,policy=c.UNSET):
        cal=write_new(self.root/'calendar.json',self.calendar)
        return c.closure_matrix(cal,policy)

    def test_originals_reopened_and_rows_bound(self):
        self.assertEqual(len(self.inventory),3740);self.assertEqual(len(self.originals),131)
        self.assertTrue(all(r['raw_original_refs'] for r in self.inventory))

    def test_327_dates_per_symbol_not_1260(self):
        self.assertEqual({len(d) for d in self.dates.values()},{327})
        self.assertTrue(all(d[0]=='2025-06-03' and d[-1]=='2026-09-30' for d in self.dates.values()))

    def test_request_aliases_preserved(self):
        self.assertGreater(sum(r['actual_API']=='daily' for r in self.inventory),3*327)
        self.assertTrue(all(x['identical_duplicate_dates']==3 for x in self.coverage.values()))

    def test_current_available_never_historical_available(self):
        self.assertTrue(all(r['historical_available_at'] is None and r['first_visible_at'] is None for r in self.inventory))
        self.assertTrue(all(r['revision_chain']=='NOT_PROVEN' for r in self.inventory))

    def test_new_owner_conditional_scope_not_reported_as_absent(self):
        matrix=self.matrix()
        self.assertTrue(matrix['conditional_backtest_owner_authorized'])
        self.assertTrue(any('SEPARATE_FORMAL_RESEARCH_AUTHORIZATION_NOT_GRANTED' in r['baseline_reasons_preserved'] for r in matrix['rows']))
        self.assertTrue(all('SEPARATE_FORMAL_RESEARCH_AUTHORIZATION_NOT_GRANTED' not in r['reason_codes'] for r in matrix['rows']))

    def test_unknown_cutoff_no_midnight(self):
        self.assertIsNone(c.cutoff_for('2025-06-03',c.UNSET))
        self.assertEqual(self.snapshot(cutoff=None)['cutoff_state'],c.UNSET)

    def test_explicit_shanghai_cutoff(self):
        self.assertEqual(c.cutoff_for('2025-06-03','15:30'),'2025-06-03T15:30:00+08:00')

    def test_invalid_cutoff_rejected(self):
        for time in ['latest','25:00','15:60','2025-06-03','15:30Z']:
            with self.assertRaises(ValueError):c.cutoff_for('2025-06-03',time)

    def test_cutoff_wrong_local_day_rejected(self):
        with self.assertRaisesRegex(ValueError,'CUTOFF_SESSION'):
            self.snapshot(cutoff='2025-06-03T18:00:00Z')

    def test_equivalent_timezone_same_snapshot(self):
        self.assertEqual(self.snapshot(),self.snapshot(cutoff='2025-06-03T07:30:00Z'))

    def test_explicit_time_is_not_owner_attestation(self):
        self.assertEqual(self.snapshot()['cutoff_state'],'EXPLICIT_TIME_INPUT_NOT_OWNER_ATTESTATION')
        self.assertFalse(self.snapshot()['observed_at_the_time'])

    def test_candidate_semantic_hash_verified(self):
        self.assertTrue(c.verify_candidate(self.snapshot()))

    def test_self_rehashed_future_metadata_rejected(self):
        value=self.snapshot();value['visible_records']=[{'future':'LEAK'}]
        value['snapshot_sha256']=c.sha(c.canonical({k:v for k,v in value.items() if k!='snapshot_sha256'}))
        with self.assertRaisesRegex(ValueError,'SEMANTIC_HASH'):c.verify_candidate(value)

    def test_self_rehashed_duplicate_reason_rejected(self):
        value=self.snapshot();value['reason_codes']*=2
        value['snapshot_sha256']=c.sha(c.canonical({k:v for k,v in value.items() if k!='snapshot_sha256'}))
        with self.assertRaisesRegex(ValueError,'SEMANTIC_HASH'):c.verify_candidate(value)

    def test_built_epoch_readback_and_pending_ledger_mutation_rejected(self):
        from historical_pit.run import build,verify_saved
        output=self.root/'own-test-audit-epoch'
        status=build(output,MANIFEST)
        self.assertEqual(status['admitted_snapshots'],0)
        self.assertEqual(verify_saved(output)['verified_candidate_snapshots'],981)
        ledger=output/'Trade-Ledger-PENDING.jsonl'
        ledger.chmod(0o600);ledger.write_bytes(b'FAKE_TRADE')
        with self.assertRaises(ValueError):verify_saved(output)

    def test_future_ids_values_counts_hashes_do_not_change_payload(self):
        baseline=self.snapshot()
        future={'published_at':'2026-10-05T12:00:00Z','title':'FUTURE','revision_id':'X','values':object()}
        self.assertEqual(baseline,self.snapshot(self.inventory+[future]))
        self.assertEqual(baseline['visible_records'],[])

    def test_latest_history_cannot_backfill(self):
        s=self.snapshot()
        self.assertEqual(s['domains'],{k:'UNKNOWN' for k in ['PRICE','CALENDAR','STATUS','ACTION']})
        self.assertIs(s['historical_visibility_proven'],False)

    def test_self_declared_admitted_proof_not_authority(self):
        forged=[{'historical_visibility_proven':True,'source_admission':'ADMITTED','available_at':'2020-01-01T00:00:00Z'}]
        self.assertEqual(self.snapshot(forged),self.snapshot())

    def test_reconstruction_requires_independent_actual_issuer(self):
        self.assertEqual(self.snapshot(mode='HISTORICAL_AVAILABILITY_RECONSTRUCTION')['formal_admission'],'BLOCKED')

    def test_event_three_namespace_rejected(self):
        with self.assertRaises(ValueError):c.candidate_snapshot('EVENT_3','2025-06-03',None,[])

    def test_981_daily_views_not_admitted(self):
        views=[c.candidate_snapshot(s,d,None,self.inventory) for s in c.SYMBOLS for d in self.dates[s]]
        self.assertEqual(len(views),981);self.assertTrue(all(v['decision']=='NO_DECISION' for v in views))

    def test_calendar_six_years_bound_to_raw(self):
        self.assertEqual([r['year'] for r in self.calendar['rows']],list(range(2021,2027)))
        self.assertEqual([len(r['holiday_intervals']) for r in self.calendar['rows']],[7,7,6,7,6,7])

    def test_calendar_cross_year_holiday(self):
        first=self.calendar['rows'][3]['holiday_intervals'][0]
        self.assertEqual((first['start_date'],first['end_date']),('2023-12-30','2024-01-01'))

    def test_calendar_date_only_not_first_visibility(self):
        self.assertTrue(all(r['available_at'] is r['published_at'] is r['first_visible_at'] is None for r in self.calendar['rows']))
        self.assertIs(self.calendar['historical_visibility_proven'],False)

    def test_calendar_changed_hash_stops(self):
        m=c._json(reopen(ref(MANIFEST)));m['captures'][0]['source_version']='sha256:'+'f'*64
        p=write_new(self.root/'bad.json',m)
        with self.assertRaisesRegex(ValueError,'ORIGINAL_CHANGED'):
            c.calendar_structure(p)

    def test_calendar_midnight_promotion_stops(self):
        m=c._json(reopen(ref(MANIFEST)));m['captures'][0]['published_at']='2020-12-24T00:00:00+08:00'
        p=write_new(self.root/'bad.json',m)
        with self.assertRaisesRegex(ValueError,'CLOCK_PROMOTION'):
            c.calendar_structure(p)

    def test_matrix_exact_60_and_no_closure(self):
        m=self.matrix();self.assertEqual(len(m['rows']),60)
        self.assertEqual(m['continuous_domains_closed'],0)
        self.assertTrue(all(r['formal_admission']=='BLOCKED' for r in m['rows']))

    def test_new_calendar_evidence_only_three_calendar_rows(self):
        m=self.matrix()
        self.assertEqual(sum(r['calendar_structural_evidence_ref'] is not None for r in m['rows']),3)
        self.assertTrue(all(r['baseline_reasons_preserved'] for r in m['rows']))

    def test_engine_never_called_with_unclosed_pit(self):
        matrix=write_new(self.root/'matrix.json',self.matrix())
        attempt=c.backtest_attempt(self.coverage,matrix)
        self.assertIs(attempt['engine_called'],False);self.assertIsNone(attempt['ledger_ref'])
        self.assertTrue(all(v is None for v in attempt['metrics'].values()))
        self.assertEqual(attempt['protocol']['minimum_sessions'],1260)
        self.assertEqual(attempt['protocol']['minimum_complete_trades'],100)

    def test_forged_closure_not_self_hash_authority(self):
        matrix=self.matrix();matrix['continuous_domains_closed']=20
        r=write_new(self.root/'fake.json',matrix)
        with self.assertRaisesRegex(ValueError,'UNREVIEWED_CLOSURE_PROMOTION'):
            c.backtest_attempt(self.coverage,r)

    def test_frozen_family_and_unset_cost_policies(self):
        spec,r=c.frozen_spec();self.assertEqual(r['sha256'],c.SPEC_HASH)
        self.assertEqual(len(spec['families']),2)
        self.assertTrue(all(v==c.UNSET for v in spec['required_research_policy_decisions'].values()))

    def test_strategy_file_replacement_stops(self):
        with patch.object(c,'ref',return_value={'path':'/fake','bytes':1,'sha256':'sha256:'+'f'*64}), \
             self.assertRaisesRegex(ValueError,'STRATEGY_CHANGED'):
            c.frozen_spec()


if __name__=='__main__':unittest.main()
