"""Independent arithmetic oracles and adversarial prefix/label boundaries."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal, localcontext

from wave_g.diagnostic import (FAMILIES, _distribution, _group, _quality,
                               annotate_action_overlap, coordinate_sensitivity,
                               evidence, forward_label, price_features, validate_calendar)
from wave_g.common import BASELINE_ROOT, canonical, checked_reference, locate_reference, reference, sha


def fixture(n=160):
    rows=[]
    start=datetime(2025,1,1)
    for i in range(1,n+1):
        day=(start+timedelta(days=i-1)).strftime('%Y%m%d')
        source={'raw_sha256':'sha256:'+'a'*64,'row_ordinal':i-1,
                'published_at':None,'available_at':'2026-10-06T00:00:00Z',
                'retrieved_at':'2026-10-06T00:00:00Z','revision':1}
        rows.append({'trade_date':day,'ts_code':'603993.SH','open':str(i),
                     'close':str(i),'high':str(Decimal(i)+Decimal('0.1')),
                     'low':str(Decimal(i)-Decimal('0.1')),
                     'vol':'200' if i==80 else '100','source_ref':source})
    return rows


def calendar_for(rows, closed=()):
    return validate_calendar([{'values':{'cal_date':r['trade_date'],'exchange':'SSE',
                             'is_open':'0' if r['trade_date'] in closed else '1'},
                              'source_ref':deepcopy(r['source_ref'])} for r in rows])


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.rows=fixture();self.cutoff=self.rows[79]['trade_date'];self.cal=calendar_for(self.rows)

    def features(self,rows=None,**kwargs):
        return price_features(self.rows if rows is None else rows,self.cutoff,
                              symbol='603993.SH',**kwargs)

    def test_independent_linear_arithmetic_oracle(self):
        f=self.features(calendar=self.cal)
        v=f['values']
        self.assertEqual(v['ma20'],'70.5');self.assertEqual(v['ma60'],'50.5')
        self.assertEqual(v['ma60_slope_20'],'20.0');self.assertEqual(v['atr20'],'1.1')
        self.assertEqual(v['previous3_high'],'79.1');self.assertEqual(v['previous60_high'],'79.1')
        self.assertEqual(v['volume_to_previous20'],'2')
        with localcontext() as ctx:
            ctx.prec=100
            self.assertEqual(Decimal(v['distance_ma20_atr']),Decimal('9.5')/Decimal('1.1'))
            self.assertEqual(Decimal(v['breakout60_ratio']),Decimal(80)/Decimal('79.1')-1)
            self.assertEqual(Decimal(v['volume3_to_volume20']),Decimal(400)/Decimal(3)/Decimal(105))
        self.assertEqual(f['price_component'][FAMILIES[1]],'TRUE')
        self.assertEqual(f['price_component'][FAMILIES[0]],'FALSE')
        self.assertEqual(f['full_family_decision'],'NO_DECISION')

    def test_slope_minimum80_not79(self):
        f=price_features(self.rows,self.rows[78]['trade_date'])
        self.assertEqual(f['values']['ma60_slope_20'],None)
        self.assertEqual(f['price_component'][FAMILIES[0]],'UNKNOWN')
        self.assertNotEqual(f['price_component'][FAMILIES[1]],'UNKNOWN')

    def test_breakout_first61_dates_independent_of_pullback80(self):
        rows=deepcopy(self.rows);rows[60]['vol']='200'
        f=price_features(rows,rows[60]['trade_date'],calendar=self.cal)
        self.assertEqual(f['values']['ma60'],'31.5')
        self.assertEqual(f['values']['previous60_high'],'60.1')
        self.assertEqual(f['values']['volume_to_previous20'],'2')
        self.assertEqual(f['price_component'][FAMILIES[1]],'TRUE')
        self.assertEqual(f['price_component'][FAMILIES[0]],'UNKNOWN')
        before=price_features(rows,rows[59]['trade_date'],calendar=self.cal)
        self.assertEqual(before['price_component'][FAMILIES[1]],'UNKNOWN')

    def test_missing_older_pullback_bar_does_not_delay_complete_breakout(self):
        rows=deepcopy(self.rows);del rows[0]
        f=self.features(rows,calendar=self.cal)
        self.assertEqual(f['price_component'][FAMILIES[0]],'UNKNOWN')
        self.assertEqual(f['price_component'][FAMILIES[1]],'TRUE')
        self.assertEqual(f['family_window_completeness'][FAMILIES[0]]['missing_dates'],[self.rows[0]['trade_date']])

    def test_future_payload_revision_prefix_isolation(self):
        expected=self.features(calendar=self.cal)
        modified=deepcopy(self.rows)
        for r in modified[80:]:
            r['close']=42.7;r['vol']='NaN';r['source_ref']['revision']=999
        self.assertEqual(canonical(expected),canonical(self.features(modified,calendar=self.cal)))
        self.assertEqual(canonical(expected),canonical(self.features(self.rows[:80],calendar=self.cal)))

    def test_later_retrieved_old_date_revision_excluded_from_frozen_reconstruction(self):
        rows=deepcopy(self.rows)
        late=deepcopy(rows[40]);late.update(open='999',high='1000',low='998',close='999')
        late['source_ref'].update(available_at='2026-10-07T00:00:00Z',retrieved_at='2026-10-07T00:00:00Z',revision=2)
        rows.append(late)
        kwargs={'calendar':self.cal,'reconstruction_cutoff':'2026-10-06T00:00:00Z'}
        self.assertEqual(canonical(self.features(rows,**kwargs)),canonical(self.features(**kwargs)))
        self.assertEqual(self.features(rows)['price_component'][FAMILIES[1]],'UNKNOWN')

    def test_identical_versions_preserved_conflicting_versions_not_overwritten(self):
        rows=deepcopy(self.rows)
        duplicate=deepcopy(rows[10]);duplicate['source_ref']['revision']=2;duplicate['high']='11.10'
        rows.append(duplicate)
        f=self.features(rows)
        self.assertEqual(f['duplicate_dates'][0]['count'],2)
        self.assertEqual(len(f['duplicate_dates'][0]['source_refs']),2)
        conflict=deepcopy(rows[30]);conflict.update(open='99',high='100',low='98',close='99')
        rows.append(conflict)
        self.assertEqual(self.features(rows)['values'],{})
        self.assertEqual(self.features(rows)['full_family_decision'],'NO_DECISION')

    def test_missing_reference_session_not_flat_or_bar_offset(self):
        rows=deepcopy(self.rows);del rows[65]
        f=self.features(rows,calendar=self.cal)
        self.assertIn('REQUIRED_REFERENCE_SESSION_BAR_MISSING',f['reason_codes'])
        self.assertEqual(f['values'],{})
        label=forward_label(rows,self.rows[60]['trade_date'],20,calendar=self.cal)
        self.assertEqual(label['state'],'UNKNOWN')
        self.assertEqual(label['raw_price_change_ratio'],None)

    def test_session_endpoint_differs_from_observed_offset_with_absent_bar(self):
        rows=deepcopy(self.rows);del rows[81]
        session=forward_label(rows,self.cutoff,5,calendar=self.cal)
        observed=forward_label(rows,self.cutoff,5)
        self.assertEqual(session['endpoint_date'],self.rows[84]['trade_date'])
        self.assertEqual(session['state'],'UNKNOWN')
        self.assertEqual(observed['endpoint_date'],self.rows[85]['trade_date'])
        self.assertEqual(observed['session_label_state'],'UNKNOWN')
        self.assertEqual(observed['label_name'],'OBSERVED_BAR_OFFSET_RAW_CLOSE_CHANGE')

    def test_calendar_absent_incomplete_conflicting_or_unbound_remains_unknown(self):
        self.assertEqual(validate_calendar([])['state'],'UNKNOWN')
        rows=[{'values':{'cal_date':r['trade_date'],'exchange':'SSE','is_open':'1'},
               'source_ref':r['source_ref']} for r in self.rows]
        bad=deepcopy(rows);del bad[70]
        self.assertEqual(validate_calendar(bad)['state'],'UNKNOWN')
        conflict=deepcopy(rows[70]);conflict['values']['is_open']='0';bad=rows+[conflict]
        self.assertEqual(validate_calendar(bad)['state'],'UNKNOWN')
        rows[0]['source_ref']={}
        with self.assertRaisesRegex(ValueError,'CALENDAR_LINEAGE'): validate_calendar(rows)

    def test_independent_labels_horizon_and_path_drawdown_oracle(self):
        label=forward_label(self.rows,self.cutoff,60,calendar=self.cal)
        self.assertEqual(label['raw_price_change_ratio'],'0.75')
        self.assertEqual(label['raw_close_path_max_drawdown_ratio'],'0')
        rows=deepcopy(self.rows)
        # Path 80->100->50->...85: 50% peak-to-trough raw CLOSE drawdown.
        for i,value in [(80,'100'),(81,'50')]:
            rows[i].update(open=value,close=value,high=str(Decimal(value)+1),low=str(Decimal(value)-1))
        label=forward_label(rows,self.cutoff,5,calendar=self.cal)
        self.assertEqual(label['raw_price_change_ratio'],'0.0625')
        self.assertEqual(label['raw_close_path_max_drawdown_ratio'],'0.5')
        self.assertFalse(label['total_return']);self.assertFalse(label['fee_inclusive_strategy_profit'])

    def test_future_price_changes_label_never_features(self):
        rows=deepcopy(self.rows)
        rows[84].update(open='1000',close='1000',high='1001',low='999')
        self.assertEqual(canonical(self.features(rows)),canonical(self.features()))
        self.assertNotEqual(forward_label(rows,self.cutoff,5)['raw_price_change_ratio'],
                            forward_label(self.rows,self.cutoff,5)['raw_price_change_ratio'])

    def test_label_conflicts_and_tail_stay_unknown(self):
        duplicate=deepcopy(self.rows[81]);duplicate.update(open='800',close='800',high='801',low='799')
        label=forward_label(self.rows+[duplicate],self.cutoff,5,calendar=self.cal)
        self.assertIn('CONFLICTING_LABEL_PATH',label['reason_codes'])
        for h in (5,20,60):
            self.assertEqual(forward_label(self.rows,self.rows[-1]['trade_date'],h,calendar=self.cal)['state'],'UNKNOWN')

    def test_status_action_financial_catalyst_inputs_cannot_promote_family(self):
        rows=deepcopy(self.rows)
        for r in rows:
            r.update(status='TRADABLE',action='NO_ACTION',quality='PASS',sector_rs20='100',
                     costs='0',native_approval=True,pct_chg='999',pre_close='1')
        expected=self.features()
        self.assertEqual(canonical(expected),canonical(self.features(rows)))
        self.assertEqual(self.features(rows)['full_family_decision'],'NO_DECISION')

    def test_preclose_not_used_for_atr_or_raw_labels(self):
        rows=deepcopy(self.rows)
        for r in rows:r.update(pre_close='0.01',pct_chg='999999')
        self.assertEqual(self.features(rows)['values']['atr20'],'1.1')
        self.assertEqual(forward_label(rows,self.cutoff,60)['raw_price_change_ratio'],'0.75')

    def test_zero_atr_volume_unknown_not_infinite(self):
        rows=deepcopy(self.rows)
        for r in rows:r.update(open='10',high='10',low='10',close='10',vol='0')
        f=self.features(rows)
        self.assertIsNone(f['values']['distance_ma20_atr'])
        self.assertIsNone(f['values']['volume3_to_volume20'])
        self.assertIsNone(f['values']['volume_to_previous20'])
        self.assertEqual(set(f['price_component'].values()),{'UNKNOWN'})

    def test_float_nonfinite_negative_and_bad_units_rejected(self):
        for value in (80.0,'NaN','Infinity','-1','1e2'):
            rows=deepcopy(self.rows);rows[79]['close']=value
            with self.assertRaises(ValueError):self.features(rows)
        rows=deepcopy(self.rows);rows[79]['source_ref']={}
        with self.assertRaisesRegex(ValueError,'SOURCE_REQUIRED'):self.features(rows)
        with self.assertRaises(ValueError):forward_label(self.rows,self.cutoff,6)
        with self.assertRaisesRegex(ValueError,'NON_JSON_OR_FLOAT'):canonical({'x':0.1})

    def test_fixed_distribution_order_statistics_and_unknowns(self):
        labels=[{'state':'OBSERVED_RAW_LABEL','raw_price_change_ratio':str(i),
                 'raw_close_path_max_drawdown_ratio':'0.1'} for i in range(-2,3)]
        labels.append({'state':'UNKNOWN','raw_price_change_ratio':None})
        out=_distribution(labels)
        self.assertEqual(out['observed_count'],5);self.assertEqual(out['unknown_count'],1)
        self.assertEqual(out['raw_close_change_distribution']['median'],'0')
        self.assertEqual(out['raw_close_change_distribution']['q95'],'1')
        self.assertEqual(out['max_raw_close_path_drawdown_ratio'],'0.1')

    def test_price_only_block_purge_does_not_leak_horizon60(self):
        # Independent closed-form index oracle for the frozen first prefix.
        rows=fixture(327);cal=calendar_for(rows);end=126;retained=rows[:end-60]
        labels=[forward_label(rows,r['trade_date'],60,calendar=cal) for r in retained]
        self.assertEqual(len(labels),66)
        self.assertTrue(all(x['endpoint_date']<=rows[end-1]['trade_date'] for x in labels))
        self.assertTrue(all(price_features(rows,r['trade_date'],calendar=cal)['price_component'][FAMILIES[0]]=='UNKNOWN'
                            for r in retained))
        self.assertEqual(sum(price_features(rows,r['trade_date'],calendar=cal)['price_component'][FAMILIES[1]]!='UNKNOWN'
                             for r in retained),6)

    def test_current_coordinate_field_removal_rank_counterexample_and_missing(self):
        fields={'a':{'roe':'100','growth':'100','debt':'0'},
                'b':{'roe':'50','growth':'50','debt':'100'}}
        base=coordinate_sensitivity(fields)
        self.assertEqual(base['competition_ranks'],{'a':1,'b':1})
        omit=coordinate_sensitivity(fields,'debt')
        self.assertEqual(omit['scores'],{'a':'100','b':'50'})
        self.assertEqual(omit['competition_ranks'],{'a':1,'b':2})
        missing=coordinate_sensitivity({'a':{'roe':None,'growth':None,'debt':None}})
        self.assertEqual(missing['scores'],{})
        self.assertEqual(missing['competition_ranks'],{})
        self.assertEqual(missing['unknown_symbols'],['a'])
        self.assertFalse(missing['missing_imputed_zero'])

    def test_action_annotation_is_downstream_limitation_no_cash_adjustment(self):
        label=forward_label(self.rows,self.cutoff,5,calendar=self.cal)
        action={'symbol':'603993.SH','ex_date':self.rows[81]['trade_date'],'gross_cash_cny_per_share':'0.255'}
        annotated=annotate_action_overlap(label,[action])
        self.assertEqual(annotated['raw_price_change_ratio'],label['raw_price_change_ratio'])
        self.assertEqual(annotated['raw_close_path_max_drawdown_ratio'],label['raw_close_path_max_drawdown_ratio'])
        self.assertEqual(annotated['known_action_discontinuities'],[action])
        self.assertFalse(annotated['known_action_cash_or_adjustment_applied'])
        self.assertEqual(annotated['continuous_action_history'],'UNKNOWN')
        self.assertEqual(label.get('known_action_discontinuities'),None)

    def test_same_bytes_clone_reference_reads_calling_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone=Path(tmp).resolve();target=clone/'docs/wave-c/evidence.json'
            target.parent.mkdir(parents=True);body=b'{"fixture":"same-bytes-source"}\n';target.write_bytes(body)
            frozen={'path':str(BASELINE_ROOT/'docs/wave-c/evidence.json'),'sha256':sha(body),'bytes':len(body)}
            with patch('wave_g.common.ROOT',clone):
                self.assertEqual(locate_reference(frozen['path']),target)
                self.assertEqual(checked_reference(frozen),body)
                self.assertEqual(reference(target),frozen)

    def test_changed_clone_wave_c_target_ref_rejects_not_original_checkout_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone=Path(tmp).resolve();target=clone/'docs/wave-c/evidence.json'
            target.parent.mkdir(parents=True)
            body=b'{"fixture":"C-target"}\n';target.write_bytes(body)
            frozen={'path':str(BASELINE_ROOT/'docs/wave-c/evidence.json'),'sha256':sha(body),'bytes':len(body)}
            target.write_bytes(b'{"fixture":"C-mutant"}\n')
            with patch('wave_g.common.ROOT',clone):
                with self.assertRaisesRegex(ValueError,'DEPENDENCY_INVALIDATED'):checked_reference(frozen)
                target.unlink()
                with self.assertRaisesRegex(ValueError,'PATH_INVALID'):checked_reference(frozen)

    def test_private_source_identity_remains_fixed_under_clone_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            private=Path(tmp).resolve()/'fixed-original';private.write_bytes(b'private fixed bytes')
            frozen={'path':str(private),'sha256':sha(private.read_bytes()),'bytes':private.stat().st_size}
            with patch('wave_g.common.ROOT',Path(tmp).resolve()/'different-clone'):
                self.assertEqual(locate_reference(private),private)
                self.assertEqual(checked_reference(frozen),b'private fixed bytes')

    def test_saved_diagnostic_evidence_binds_clone_c_target_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            clone=Path(tmp).resolve();target=clone/'docs/wave-c/evidence.json'
            target.parent.mkdir(parents=True);body=b'{"fixture":"saved-evidence-C"}\n';target.write_bytes(body)
            frozen={'path':str(BASELINE_ROOT/'docs/wave-c/evidence.json'),'sha256':sha(body),'bytes':len(body)}
            manifest={'artifacts':[],'direct_input_refs':[frozen]}
            with patch('wave_g.common.ROOT',clone),patch('wave_g.diagnostic.checked_file',return_value=canonical(manifest)):
                self.assertEqual(evidence(),manifest)
                target.write_bytes(body.replace(b'saved',b'other'))
                with self.assertRaisesRegex(ValueError,'DEPENDENCY_INVALIDATED'):evidence()


if __name__=='__main__': unittest.main()
