"""Offline regressions. Mocked G-chain positives are NOT actual Human signatures."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dual_track.common import canonical, ref, write_new, sha
from day1_reveal import reveal as r, integrity as i


class RevealTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.snapshot = {'body':{'session':r.SESSION}}
        self.snap_ref = write_new(self.root/'SYNTHETIC-MOCK-snapshot.json',self.snapshot)
        self.raw = write_new(self.root/'SYNTHETIC-MOCK-daily.json',{
            'data':{'fields':['ts_code','trade_date','close','low','high'],
                    'items':[['603993.SH','20261008','17.10','16.50','17.40']]}})
        self.status = {'namespace':'ACTUAL_FORWARD_NO_DECISION',
            'accepted_session_count':1,'actual_forward_days':1,'head_hash':'sha256:'+'1'*64,
            'records':[{'snapshot':self.snapshot,'decision':'NO_DECISION','safe_to_trade':False,
                        'record_hash':'sha256:'+'1'*64,
                        'forward_authorization':{'body':{'scope':{'expected_head':'sha256:'+'0'*64}}}}]}
        self.prior_score = {'outcome_raw_ref':self.raw,'base_raw_ref':self.raw,'clock_ref':self.raw,
            'realized_return_percent':'1.3033175355450236966824644549763033175355450236966824644549763033175355450236967',
            'direction_hit':True,'range_hit':True,
            'forecast_error_percent_points':'0.1033175355450236966824644549763033175355450236966824644549763033175355450236967',
            'mae_percent':'-2.251184834123222748815165876777251184834123222748815165876777251184834123222749',
            'mfe_percent':'3.0805687203791469194312796208530805687203791469194312796208530805687203791469194'}

    def mock_score(self, status=None):
        with patch.object(r,'now',return_value='2026-10-08T07:05:00Z'), \
             patch.object(r,'inspect_actual_store',return_value=status or self.status), \
             patch.object(r,'score_actual_snapshot',return_value=self.prior_score):
            return r.score_day1(self.root/'NOT-AN-ACTUAL-G-STORE',self.snap_ref,'603993.SH')

    def journal(self):
        path = self.root/'SYNTHETIC-MOCK-ForwardOutcome-D1.jsonl'
        path.touch(mode=0o600)
        return path

    def test_registered_prediction_integrity(self):
        self.assertEqual(i.check_day0()['state'],'PASS')

    def test_wrong_zip_hash_stops(self):
        p=self.root/'changed.zip';p.write_bytes(b'CHANGED FIXTURE')
        with patch.object(i,'ZIP',p), self.assertRaisesRegex(ValueError,'ZIP_CHANGED'):
            i.check_day0()

    def test_changed_receipt_stops(self):
        original = i.reopen
        def altered(reference):
            value=original(reference)
            return value+b' ' if reference['path'].endswith('Freeze-Receipt.json') else value
        with patch.object(i,'reopen',side_effect=altered),self.assertRaisesRegex(ValueError,'RECEIPT_OR_SCHEMA'):
            i.check_day0()

    def test_base_raw_prices_exact(self):
        base=r.verify_base()
        self.assertEqual([x['base_close_cny'] for x in base['rows']],['16.88','20.29','101.21'])
        self.assertIs(base['historical_visibility_proven'],False)

    def test_disproved_base_blocks(self):
        fake=write_new(self.root/'SYNTHETIC-MOCK-base.json',{'data':{
            'fields':['ts_code','trade_date','close'],'items':[['603993.SH','20260930','99']]}})
        with patch.object(r,'_anchor',return_value={'source_original_refs':[fake]}), \
             self.assertRaisesRegex(ValueError,'BASE_ASSUMPTION_DISPROVED'):
            r.verify_base()

    def test_before_eod_no_store_or_scoring_io(self):
        with patch.object(r,'now',return_value='2026-10-08T06:59:59Z'), \
             patch.object(r,'inspect_actual_store') as inspect, \
             self.assertRaisesRegex(ValueError,'EOD_OR_FUTURE'):
            r.score_day1('absent',self.snap_ref,'603993.SH')
        inspect.assert_not_called()

    def test_future_score_clock_rejected(self):
        with patch.object(r,'now',return_value='2026-10-08T07:01:00Z'), \
             self.assertRaisesRegex(ValueError,'EOD_OR_FUTURE'):
            r.score_day1('absent',self.snap_ref,'603993.SH','2026-10-08T07:02:00Z')

    def test_snapshot_alone_without_verified_g_chain_blocks(self):
        with patch.object(r,'now',return_value='2026-10-08T07:05:00Z'), \
             patch.object(r,'inspect_actual_store',side_effect=ValueError('NO_FORWARD_SIGNATURE')), \
             patch.object(r,'score_actual_snapshot') as scorer, \
             self.assertRaisesRegex(ValueError,'NO_FORWARD_SIGNATURE'):
            r.score_day1('absent',self.snap_ref,'603993.SH')
        scorer.assert_not_called()

    def test_simulation_namespace_blocks(self):
        d=copy.deepcopy(self.status);d['namespace']='OFFLINE_SIMULATION_FORWARD_NO_DECISION'
        with self.assertRaisesRegex(ValueError,'EXACTLY_ONE'):
            self.mock_score(d)

    def test_second_actual_session_out_of_scope(self):
        d=copy.deepcopy(self.status);d['accepted_session_count']=d['actual_forward_days']=2
        with self.assertRaisesRegex(ValueError,'EXACTLY_ONE'):
            self.mock_score(d)

    def test_missing_forward_signature_blocks(self):
        d=copy.deepcopy(self.status);d['records'][0]['forward_authorization']=None
        with self.assertRaisesRegex(ValueError,'ACCEPTED_SNAPSHOT'):
            self.mock_score(d)

    def test_unaccepted_snapshot_blocks(self):
        d=copy.deepcopy(self.status);d['records'][0]['snapshot']={'body':{'session':'2026-10-09'}}
        with self.assertRaisesRegex(ValueError,'ACCEPTED_SNAPSHOT'):
            self.mock_score(d)

    def test_valid_mock_chain_enriches_exact_fields(self):
        result=self.mock_score()
        self.assertEqual((result['base_close_verified'],result['target_close'],result['target_day_low'],result['target_day_high']),
                         ('16.88','17.10','16.50','17.40'))
        self.assertIs(result['forward_signature_verified'],True)
        self.assertIs(result['actual_authority'],False)
        self.assertEqual(result['actual_forward_days_increment'],0)

    def test_target_symbol_or_date_drift_blocks(self):
        self.raw=write_new(self.root/'SYNTHETIC-wrong.json',{'data':{'fields':['ts_code','trade_date','close'],
            'items':[['600312.SH','20261007','17']]}})
        self.prior_score['outcome_raw_ref']=self.raw
        with self.assertRaisesRegex(ValueError,'TARGET_SYMBOL_DATE'):
            self.mock_score()

    def test_late_body_never_grants_authority(self):
        body=r.attestation_body('HUMAN_USER')
        self.assertEqual(body['timing_class'],'POST_OPEN/LATE_ATTESTATION')
        self.assertIs(body['preopen_signature'],False)
        self.assertIs(body['actual_authority'],False)

    def test_retroactive_preopen_attestation_rejected(self):
        body=r.attestation_body('HUMAN_USER');body['preopen_signature']=True
        body_ref=write_new(self.root/'bad-body.json',body)
        sig=self.root/'synthetic.sig';sig.write_bytes(bytes(64))
        with self.assertRaisesRegex(ValueError,'ATTESTATION_SCOPE'):
            r.verify_attestation(body_ref,ref(sig),'HUMAN_USER')

    def test_forged_signature_rejected(self):
        body_ref=write_new(self.root/'body.json',r.attestation_body('HUMAN_USER'))
        sig=self.root/'synthetic.sig';sig.write_bytes(bytes(64))
        with self.assertRaisesRegex(ValueError,'SIGNATURE_REJECTED'):
            r.verify_attestation(body_ref,ref(sig),'HUMAN_USER')

    def test_invalid_role_rejected(self):
        with self.assertRaisesRegex(ValueError,'ATTESTATION_ROLE'):
            r.attestation_body('LLM_APPROVE')

    def test_journal_append_chain_and_old_prefix_preserved(self):
        p=self.journal();score=self.mock_score()
        with patch.object(r,'score_day1',return_value=score):
            head,_=r.journal_head(p)
            row=r.append_day1(p,head,'mock',self.snap_ref,'603993.SH')
            first=p.read_bytes()
            new_head,seen=r.journal_head(p)
            self.assertEqual(new_head,row['outcome_sha256']);self.assertEqual(seen,{'603993.SH'})
            self.assertEqual(row['expected_head'],row['previous_hash'])
            score2=copy.deepcopy(score);score2['symbol']='600312.SH'
            with patch.object(r,'score_day1',side_effect=lambda store,snapshot,symbol,*_: score if symbol=='603993.SH' else score2):
                r.append_day1(p,new_head,'mock',self.snap_ref,'600312.SH')
                self.assertTrue(p.read_bytes().startswith(first))
                self.assertEqual(len(r.journal_head(p)[1]),2)

    def test_stale_head_no_bytes_changed(self):
        p=self.journal()
        with self.assertRaisesRegex(ValueError,'STALE_HEAD'):
            r.append_day1(p,'sha256:'+'f'*64,'mock',self.snap_ref,'603993.SH')
        self.assertEqual(p.read_bytes(),b'')

    def test_duplicate_outcome_no_append(self):
        p=self.journal();score=self.mock_score()
        with patch.object(r,'score_day1',return_value=score):
            head,_=r.journal_head(p);r.append_day1(p,head,'mock',self.snap_ref,'603993.SH')
            original=p.read_bytes();head,_=r.journal_head(p)
            with self.assertRaisesRegex(ValueError,'DUPLICATE_OUTCOME'):
                r.append_day1(p,head,'mock',self.snap_ref,'603993.SH')
            self.assertEqual(original,p.read_bytes())

    def test_partial_line_stop_no_repair(self):
        p=self.journal();p.write_bytes(b'{"interrupted":')
        with self.assertRaisesRegex(ValueError,'PARTIAL_JOURNAL'):
            r.journal_head(p)
        self.assertEqual(p.read_bytes(),b'{"interrupted":')

    def test_journal_modified_outcome_rejected(self):
        p=self.journal();score=self.mock_score()
        with patch.object(r,'score_day1',return_value=score):
            head,_=r.journal_head(p);row=r.append_day1(p,head,'mock',self.snap_ref,'603993.SH')
            row['target_close']='99';p.write_bytes(canonical(row)+b'\n')
            with self.assertRaisesRegex(ValueError,'JOURNAL_CHANGED'):
                r.journal_head(p)

    def test_journal_symlink_and_hardlink_rejected(self):
        import os
        p=self.journal();sym=self.root/'sym.jsonl';sym.symlink_to(p)
        with self.assertRaisesRegex(ValueError,'JOURNAL_PATH'):
            r.journal_head(sym)
        hard=self.root/'hard.jsonl';os.link(p,hard)
        with self.assertRaisesRegex(ValueError,'PERMISSIONS'):
            r.journal_head(p)


if __name__=='__main__':
    unittest.main()
