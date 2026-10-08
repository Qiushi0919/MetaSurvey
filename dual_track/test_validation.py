"""Explicit synthetic fixtures; never production account or cost defaults."""
import json
import tempfile
import unittest
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from .common import FORWARD_V1_REF, ROOT, SYMBOLS, canonical, now, ref, reopen, sha, write_new
from .forward import (owner_text_prediction, validate_prediction, synthetic_score,
                      fixture_head, append_fixture_outcome, append_actual_outcome, d10_ranking)
from .history import prefix_forecast, reveal_label, distribution, COST_GRID_BPS


def fixture_rows(count=100):
    result=[]
    for i in range(count):
        close=Decimal('100')+i
        result.append({'trade_date':(date(2025,1,1)+timedelta(days=i)).strftime('%Y%m%d'),
            'ts_code':SYMBOLS[0],'open':str(close),'close':str(close),'low':str(close-1),'high':str(close+1),'vol':'100',
            'source_ref':{'raw_sha256':'sha256:'+'a'*64,'available_at':'2026-10-06T12:00:00Z',
                          'retrieved_at':'2026-10-06T12:00:00Z','provenance':'SYNTHETIC_FIXTURE'}})
    return result


def fixture_calendar(rows):
    return {'state':'COMPLETE_CURRENT_REFERENCE_RECONSTRUCTION','open_dates':[r['trade_date'] for r in rows]}


def fixture_bar(symbol=SYMBOLS[0], close='16.88', session='2026-10-08'):
    return {'mode':'SYNTHETIC_FIXTURE','symbol':symbol,'session':session,'open':close,'close':close,
            'low':str(Decimal(close)-1),'high':str(Decimal(close)+1)}


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        src=self.root/'synthetic-owner-text.txt';src.write_text('SYNTHETIC FIXTURE, not real authorization')
        with patch('dual_track.forward.now',return_value='2026-10-07T15:00:00Z'):
            self.prediction=owner_text_prediction(ref(src))
        self.pred_ref=write_new(self.root/'prediction.json',self.prediction)

    def test_prefix_future_poison_and_removal_invariance(self):
        rows=fixture_rows();cal=fixture_calendar(rows);cutoff=rows[70]['trade_date']
        expected=prefix_forecast(rows,cutoff,10,cal,SYMBOLS[0])
        changed=deepcopy(rows)
        for row in changed[71:]: row['close']='FUTURE_POISON'
        self.assertEqual(expected,prefix_forecast(changed,cutoff,10,cal,SYMBOLS[0]))
        self.assertEqual(expected,prefix_forecast(rows[:71],cutoff,10,cal,SYMBOLS[0]))
        self.assertEqual(expected['training_pairs'],61)
        self.assertLessEqual(expected['training_end_max'],cutoff)
        self.assertFalse(expected['historical_visibility_proven'])

    def test_current_fundamental_payload_not_a_feature(self):
        rows=fixture_rows();cal=fixture_calendar(rows);cutoff=rows[70]['trade_date']
        expected=prefix_forecast(rows,cutoff,5,cal,SYMBOLS[0])
        for row in rows: row.update(today_roe='9999',industry='FUTURE_NAME',announcement='later')
        self.assertEqual(expected,prefix_forecast(rows,cutoff,5,cal,SYMBOLS[0]))

    def test_horizon_alignment_and_right_censoring(self):
        rows=fixture_rows();cal=fixture_calendar(rows)
        for horizon in (1,5,10,20,40):
            label=reveal_label(rows,rows[5]['trade_date'],horizon,cal,SYMBOLS[0])
            self.assertEqual(label['endpoint_date'],rows[5+horizon]['trade_date'])
            self.assertEqual(reveal_label(rows,rows[-1]['trade_date'],horizon,cal,SYMBOLS[0])['state'],'PENDING')

    def test_no_implicit_calendar_and_conflict_no_winner(self):
        rows=fixture_rows();cal=fixture_calendar(rows);cutoff=rows[70]['trade_date']
        with self.assertRaises(ValueError): prefix_forecast(rows,cutoff,5,{'state':'UNKNOWN'},SYMBOLS[0])
        duplicate=deepcopy(rows[5]);duplicate.update(close='105.5',high='106')
        self.assertEqual(prefix_forecast(rows+[duplicate],cutoff,5,cal,SYMBOLS[0])['state'],'BLOCKED')

    def test_missing_open_bar_blocks_price_and_path(self):
        rows=fixture_rows();cal=fixture_calendar(rows)
        missing=rows[:20]+rows[21:]
        self.assertEqual(prefix_forecast(missing,rows[70]['trade_date'],5,cal,SYMBOLS[0])['state'],'BLOCKED')
        self.assertEqual(reveal_label(missing,rows[19]['trade_date'],5,cal,SYMBOLS[0])['state'],'BLOCKED')

    def test_future_label_changes_do_not_change_forecast(self):
        rows=fixture_rows();cal=fixture_calendar(rows);cutoff=rows[70]['trade_date']
        prediction=prefix_forecast(rows,cutoff,5,cal,SYMBOLS[0])
        label=reveal_label(rows,cutoff,5,cal,SYMBOLS[0]);changed=deepcopy(rows)
        for row in changed[71:]:
            for field in ('open','close','high','low'):row[field]=str(Decimal(row[field])*2)
        self.assertNotEqual(label,reveal_label(changed,cutoff,5,cal,SYMBOLS[0]))
        self.assertEqual(prediction,prefix_forecast(changed,cutoff,5,cal,SYMBOLS[0]))

    def test_protocol_cost_grid_is_synthetic_boundary(self):
        f={'center_return_ratio':'0.001'}
        label={'raw_return_ratio':'0.005','mae_ratio':'-0.01','mfe_ratio':'0.02','close_path_max_drawdown_ratio':'0.01'}
        board=distribution([(f,label)])
        self.assertEqual([r['roundtrip_bps'] for r in board['cost_sensitivity']],list(COST_GRID_BPS))
        self.assertEqual(Decimal(board['cost_sensitivity'][-1]['median_label_minus_cost_ratio']),Decimal(0))
        self.assertEqual(Decimal(board['cost_sensitivity'][-1]['positive_label_minus_cost_fraction']),Decimal(0))

    def test_prediction_no_money_no_native_no_mixed_namespace(self):
        for change in (lambda p:p.update(namespace='EVENT_3'),lambda p:p['boundaries'].update(productionGate=True),
                       lambda p:p.update(order_intent='BUY'),lambda p:p.update(original_artifact_state='VERIFIED')):
            p=deepcopy(self.prediction);change(p)
            with self.assertRaises(ValueError):validate_prediction(p)

    def test_version_duplicate_scope_invalidated(self):
        p=deepcopy(self.prediction);p['entries'][1]=deepcopy(p['entries'][0])
        with self.assertRaises(ValueError):validate_prediction(p)
        p=deepcopy(self.prediction);p['version']='2.0.0'
        with self.assertRaises(ValueError):validate_prediction(p)

    def test_decimal_float_nan_and_infinite_rejected(self):
        for value in (16.88,'NaN','Infinity','1e8',True):
            p=deepcopy(self.prediction);p['entries'][0]['base_close_cny']=value
            with self.assertRaises(ValueError):validate_prediction(p)

    def test_preopen_deadline_timezone_and_price_rounding(self):
        for value in ('2026-10-08T01:30:00Z','2026-10-07T12:00:00'):
            p=deepcopy(self.prediction);p['frozen_at']=value
            with self.assertRaises(ValueError):validate_prediction(p)
        self.assertEqual([e['derived_center_price_cny'] for e in self.prediction['entries'] if e['horizon']==10],['17.72','20.90','104.25'])

    def test_direction_range_are_separate_and_zero_neutral(self):
        base=Decimal('16.88')
        for ratio_value,direction,band in [('1.021',True,True),('1.055',True,False),('0.995',False,True),('1',False,True)]:
            score=synthetic_score(self.prediction,SYMBOLS[0],1,[fixture_bar(close=str(base*Decimal(ratio_value)))])
            self.assertEqual((score['direction_hit'],score['range_hit']),(direction,band))

    def test_exact_band_boundary_inclusive(self):
        for multiplier in ('0.99','1.035'):
            score=synthetic_score(self.prediction,SYMBOLS[0],1,[fixture_bar(close=str(Decimal('16.88')*Decimal(multiplier)))])
            self.assertTrue(score['range_hit'])

    def test_path_gaps_duplicates_and_real_promotion_blocked(self):
        with self.assertRaises(ValueError):synthetic_score(self.prediction,SYMBOLS[0],5,[fixture_bar()])
        b=fixture_bar();b['mode']='ACTUAL_RESEARCH_ONLY'
        with self.assertRaisesRegex(ValueError,'ADAPTER_NOT_ADMITTED'):synthetic_score(self.prediction,SYMBOLS[0],1,[b])
        b=fixture_bar();b['session']='2026-09-30'
        with self.assertRaises(ValueError):synthetic_score(self.prediction,SYMBOLS[0],1,[b])

    def test_one_append_duplicate_prevention_and_stale_head(self):
        store=self.root/'fixture-store';head,_=fixture_head(store,self.pred_ref)
        append_fixture_outcome(store,self.pred_ref,head,SYMBOLS[0],1,[fixture_bar()])
        newhead,seen=fixture_head(store,self.pred_ref)
        self.assertEqual(len(seen),1);self.assertNotEqual(head,newhead)
        with self.assertRaisesRegex(ValueError,'STALE_HEAD'):append_fixture_outcome(store,self.pred_ref,head,SYMBOLS[1],1,[fixture_bar(SYMBOLS[1],'20.29')])
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):append_fixture_outcome(store,self.pred_ref,newhead,SYMBOLS[0],1,[fixture_bar()])

    def test_changed_frozen_source_or_prediction_blocked(self):
        Path(self.prediction['source_ref']['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'REFERENCE_CHANGED'):fixture_head(self.root/'store',self.pred_ref)
        # Adversary can chmod its own file: byte hash still must reject it.
        Path(self.pred_ref['path']).chmod(0o600);Path(self.pred_ref['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'REFERENCE_CHANGED'):fixture_head(self.root/'store',self.pred_ref)

    def test_store_path_binding_and_segment_tamper(self):
        store=self.root/'store';head,_=fixture_head(store,self.pred_ref)
        r=append_fixture_outcome(store,self.pred_ref,head,SYMBOLS[0],1,[fixture_bar()])
        other=self.root/'other';other.mkdir();(other/'001.json').write_bytes(Path(r['path']).read_bytes())
        with self.assertRaisesRegex(ValueError,'CHAIN_CHANGED'):fixture_head(other,self.pred_ref)
        row=json.loads(Path(r['path']).read_bytes());row['score']['range_hit']=not row['score']['range_hit']
        Path(r['path']).chmod(0o600);Path(r['path']).write_bytes(canonical(row))
        with self.assertRaisesRegex(ValueError,'CHAIN_CHANGED'):fixture_head(store,self.pred_ref)

    def test_fixture_cannot_enter_actual_adapter_no_store_created(self):
        bad=write_new(self.root/'fake-snapshot.json',{'version':'1.0.0','kind':'OFFLINE_SIMULATION_SNAPSHOT_B'})
        store=self.root/'actual';head,_=fixture_head(store,self.pred_ref,'ACTUAL_RESEARCH_ONLY')
        with self.assertRaisesRegex(ValueError,'DT_V1_PREDICTION_NOT_REGISTERED'):
            append_actual_outcome(store,self.pred_ref,head,bad,SYMBOLS[0],1)
        self.assertFalse(store.exists())

    def test_pit_register_preserves_missing_optional_metadata(self):
        from .pit import build
        result=json.loads(Path(build(self.root/'PIT.json')['path']).read_bytes())
        self.assertEqual((result['domain_count'],result['symbol_domain_rows'],result['continuous_domains_closed']),(20,60,0))
        self.assertEqual(len({(r['symbol'],r['domain']) for r in result['entries']}),60)
        self.assertEqual(sum(r['current_historical_coverage']=='UNRECORDED_IN_BASELINE' for r in result['entries']),18)
        self.assertTrue(all(r['formal_admission']=='BLOCKED' and r['first_seen_at'] is None for r in result['entries']))

    def test_actual_scoring_clock_cannot_be_in_future(self):
        from .reviewed import score_actual_snapshot
        with self.assertRaisesRegex(ValueError,'DT_FUTURE_SCORING_CLOCK'):
            score_actual_snapshot(json.loads(reopen(FORWARD_V1_REF)),{},SYMBOLS[0],1,'2099-10-08T12:00:00Z')

    def test_valid_self_hash_simulation_snapshot_is_not_actual_review(self):
        fake={'version':'1.0.0','kind':'OFFLINE_SIMULATION_SNAPSHOT_B',
              'namespace':'OFFLINE_SIMULATION_FORWARD_NO_DECISION','body':{}}
        fake['content_hash']=sha(canonical(fake))
        snapshot_ref=write_new(self.root/'simulation-snapshot.json',fake)
        from .reviewed import score_actual_snapshot
        with self.assertRaisesRegex(ValueError,'WH_FORWARD_SNAPSHOT_NAMESPACE_PROMOTION'):
            score_actual_snapshot(json.loads(reopen(FORWARD_V1_REF)),snapshot_ref,SYMBOLS[0],1)

    def test_changed_source_blocks_direct_actual_scoring_entry(self):
        Path(self.prediction['source_ref']['path']).write_text('changed')
        from .reviewed import score_actual_snapshot
        with self.assertRaisesRegex(ValueError,'DT_REFERENCE_CHANGED'):
            score_actual_snapshot(self.prediction,{},SYMBOLS[0],1)

    def test_changed_prediction_and_rewritten_receipt_cannot_replace_v1(self):
        from .reviewed import score_actual_snapshot
        registered=json.loads(reopen(FORWARD_V1_REF))
        registered['entries'][0]['center_return_percent']='1.0'
        registered['entries'][0]['derived_center_price_cny']='17.05'
        replacement=write_new(self.root/'replacement.json',registered)
        self.assertNotEqual(replacement['sha256'],FORWARD_V1_REF['sha256'])
        with self.assertRaisesRegex(ValueError,'DT_V1_PREDICTION_NOT_REGISTERED'):
            score_actual_snapshot(registered,{},SYMBOLS[0],1)

    def test_d10_ranking_requires_all_three_and_preserves_ties(self):
        scores=[]
        for symbol,value in zip(SYMBOLS,('5','3','3')):
            scores.append({'symbol':symbol,'horizon':10,'metric_scope':'SYNTHETIC_RAW_PRICE_PATH_NOT_EXECUTION_PNL','realized_return_percent':value})
        rank=d10_ranking(self.prediction,scores)
        self.assertFalse(rank['ordinal_order_hit']);self.assertEqual(rank['strict_pairwise_hits'],2)
        self.assertEqual(rank['actual_tie_groups'][1],list(SYMBOLS[1:]))
        with self.assertRaises(ValueError):d10_ranking(self.prediction,scores[:2])

    def test_no_silent_overwrite_of_frozen_artifact(self):
        with self.assertRaises(FileExistsError):write_new(self.pred_ref['path'],self.prediction)
        self.assertEqual(ref(self.pred_ref['path']),self.pred_ref)


if __name__=='__main__':unittest.main()
