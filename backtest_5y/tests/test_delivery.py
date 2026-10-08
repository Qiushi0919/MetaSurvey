"""Acceptance inventory must preserve uncertainty and reject false execution claims."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from backtest_5y.delivery import PRIVATE, build_matrix, emit, pin, validate_parent
from backtest_5y.interface import FAMILIES, LABELS, SPEC_SHA256, canonical, digest, write_new
from backtest_5y.store import EvidenceStore
from backtest_5y.strategy import _ref
from backtest_5y.tests.test_store import batch


def parent(records):
    # Synthetic shape fixture; no source admission or economic result.
    r=records[0]
    ref=_ref(r)
    refid='sha256:'+digest(canonical(ref))
    snapshot={'fixture_only':True,'symbol':'603993.SH','asof':'2026-01-02'};sid='sha256:'+digest(canonical(snapshot))
    blockers={'state':'BLOCKED','fixture_only':True};bid='sha256:'+digest(canonical(blockers))
    return {'strategy_sha256':SPEC_SHA256,'families':list(FAMILIES),'labels':LABELS,
        'state':'ENGINE_NOT_RUN','execution_state':'ENGINE_NOT_RUN','prerequisite_state':'NOT_COMPUTABLE',
        'engine_called':False,'historical_visibility_proven':False,'untouched_oos':False,
        'productionGate':False,'native_orders':False,'timing_ablation_authorized':False,
        'economic_metrics':{'return':None,'fees':None},'candidate_count':1,
        'lineage_catalog':{refid:ref},'prerequisite_snapshots':{sid:snapshot},'common_blockers':{bid:blockers},
        'candidates':[{'symbol':'603993.SH','decision_date':'2026-01-02','prerequisite_ref':sid,
            'common_blocker_ref':bid,'price_features':{'values':{},'conditions':{},'window_lineage_refs':[refid]},
            'families':{f:{'state':'NO_DECISION','reason':'FIXTURE_UNKNOWN','raw_price_component':'UNKNOWN'} for f in FAMILIES}}]}


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='delivery-fixture-',dir=PRIVATE)
        self.root=Path(self.temp.name);self.db=self.root/'capture.sqlite'
        b=batch();b['symbol']='603993.SH'
        with EvidenceStore(self.db) as store:
            store.ingest(b);self.records=store.records()
        self.result=parent(self.records)
        self.summary={'record_versions':1,'domain_counts':{'PRICE':1}}

    def tearDown(self):self.temp.cleanup()

    def test_current_capture_date_never_becomes_disclosure_or_pit(self):
        matrix=build_matrix(self.records)
        row=next(r for r in matrix['rows'] if r['category']=='Price / Volume Timing' and r['required_raw_fields']==['close'])
        self.assertEqual(row['captured_nonnull_rows'],1)
        self.assertEqual(row['published_at']['precision_counts'],{'UNKNOWN':1})
        self.assertEqual(row['retrieved_at']['precision_counts'],{'EXACT_SOURCE_RECORDED':1})
        self.assertEqual(row['pit_status'],'BLOCKED')
        self.assertFalse(matrix['full_strategy_data_pass'])
        self.assertEqual(matrix['optional_not_entry_gates'],['ROE','PB'])
        self.assertEqual(row['observed_event_range']['first'],'2026-01-02')

    def test_date_only_disclosure_preserves_precision(self):
        records=deepcopy(self.records);records[0]['published_at']='2026-01-02'
        row=next(r for r in build_matrix(records)['rows'] if r['required_raw_fields']==['close'])
        self.assertEqual(row['published_at']['precision_counts'],{'DATE_ONLY':1})
        self.assertEqual(row['published_at']['sample_literals'],['2026-01-02'])
        self.assertFalse(row['published_at']['historical_admission'])

    def test_rejects_performance_and_authority_promotions(self):
        for key in ('engine_called','historical_visibility_proven','untouched_oos','productionGate','native_orders','timing_ablation_authorized'):
            with self.subTest(key=key):
                bad=deepcopy(self.result);bad[key]=True
                with self.assertRaisesRegex(ValueError,'ONLY_UNRUN'):validate_parent(bad,self.records,self.summary)
        bad=deepcopy(self.result);bad['economic_metrics']['return']=0
        with self.assertRaisesRegex(ValueError,'ONLY_UNRUN'):validate_parent(bad,self.records,self.summary)

    def test_rejects_family_scope_duplicates_and_count_drift(self):
        bad=deepcopy(self.result);bad['candidates'][0]['families'].pop(FAMILIES[1])
        with self.assertRaisesRegex(ValueError,'CANNOT_CONSUME'):validate_parent(bad,self.records,self.summary)
        for symbol,day in (('UNAUTHORIZED','2026-01-02'),('603993.SH','2021-10-07'),('603993.SH','2026-10-01')):
            bad=deepcopy(self.result);bad['candidates'][0].update(symbol=symbol,decision_date=day)
            with self.assertRaisesRegex(ValueError,'SCOPE_CONFLICT'):validate_parent(bad,self.records,self.summary)
        bad=deepcopy(self.result);bad['candidates'].append(deepcopy(bad['candidates'][0]));bad['candidate_count']=2
        with self.assertRaisesRegex(ValueError,'SCOPE_CONFLICT'):validate_parent(bad,self.records,self.summary)
        bad=deepcopy(self.result);bad['candidate_count']=99
        with self.assertRaisesRegex(ValueError,'COUNT_CONFLICT'):validate_parent(bad,self.records,self.summary)

    def test_rejects_changed_lineage_missing_refs_and_stale_store(self):
        bad=deepcopy(self.result);next(iter(bad['lineage_catalog'].values()))['raw_sha256']='changed'
        with self.assertRaisesRegex(ValueError,'HASH_CONFLICT'):validate_parent(bad,self.records,self.summary)
        bad=deepcopy(self.result);bad['candidates'][0]['prerequisite_ref']='absent'
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_PREREQUISITE'):validate_parent(bad,self.records,self.summary)
        bad=deepcopy(self.result);bad['candidates'][0]['price_features']['window_lineage_refs']=['absent']
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_PRICE'):validate_parent(bad,self.records,self.summary)
        with self.assertRaisesRegex(ValueError,'NOT_IN_CURRENT_STORE'):validate_parent(self.result,[],self.summary)
        with self.assertRaisesRegex(ValueError,'COUNTS_CONFLICT'):validate_parent(self.result,self.records,{'record_versions':2})

    def test_actual_report_path_is_new_and_db_unchanged(self):
        diag=self.root/'diagnostic.json';write_new(diag,self.result);write_new(self.root/'summary.json',self.summary)
        before=pin(self.db);out=self.root/'acceptance'
        receipt=emit(self.db,diag,out)
        self.assertEqual(receipt['decision_prerequisite_rows'],2)
        self.assertEqual(pin(self.db),before)
        status=json.loads((out/'Required-Outputs-Status.json').read_bytes())
        self.assertEqual(status['outputs']['daily_nav']['state'],'ENGINE_NOT_RUN')
        self.assertIsNone(status['outputs']['net_return']['value'])
        self.assertIsNone(status['MAE40'])
        self.assertFalse((out/'complete_trade_ledger.jsonl').exists())
        rows=[json.loads(x) for x in (out/'Decision-Prerequisite-Ledger.jsonl').read_bytes().splitlines()]
        self.assertEqual({r['family'] for r in rows},set(FAMILIES))
        self.assertEqual({r['decision'] for r in rows},{'NO_DECISION'})
        manifest=json.loads((out/'Delivery-Package-Manifest.json').read_bytes())
        self.assertTrue(all(pin(f['path'])==f for f in manifest['files']))
        self.assertTrue(all(p.stat().st_mode&0o777==0o600 for p in out.iterdir()))
        with self.assertRaises(FileExistsError):emit(self.db,diag,out)

    def test_rejects_outside_epoch_before_opening_database(self):
        with self.assertRaisesRegex(ValueError,'OUTSIDE_NEW_PRIVATE_EPOCH'):
            emit('/tmp/absent.sqlite',self.root/'absent.json',self.root/'out')

    def test_rehashed_fabricated_clock_and_identity_still_rejected(self):
        for key in ('published_at','available_at','first_visible_at','retrieved_at','source','domain','symbol','identity','raw_ref','source_url','revision_id'):
            with self.subTest(key=key):
                bad=deepcopy(self.result);old,ref=next(iter(bad['lineage_catalog'].items()))
                ref[key]='FABRICATED';new='sha256:'+digest(canonical(ref))
                bad['lineage_catalog']={new:ref};bad['candidates'][0]['price_features']['window_lineage_refs']=[new]
                with self.assertRaisesRegex(ValueError,'METADATA_CONFLICT'):validate_parent(bad,self.records,self.summary)

    def test_future_other_symbol_and_unknown_price_date_rejected(self):
        for key,value,error in (('event_date','2026-01-03','FUTURE_EVENT'),
                                ('event_date',None,'EVENT_DATE_UNKNOWN'),
                                ('symbol','600312.SH','IDENTITY_CONFLICT'),
                                ('domain','CALENDAR','IDENTITY_CONFLICT')):
            with self.subTest(key=key,value=value):
                records=deepcopy(self.records);records[0][key]=value
                bad=parent(records)
                summary={'record_versions':1,'domain_counts':{records[0]['domain']:1}}
                with self.assertRaisesRegex(ValueError,error):validate_parent(bad,records,summary)

    def test_nested_price_and_prerequisite_identity_are_bound(self):
        bad=deepcopy(self.result);bad['candidates'][0]['price_features']['conflicts']=[{'lineage_refs':['absent']}]
        with self.assertRaisesRegex(ValueError,'NESTED_PRICE_REFERENCE'):validate_parent(bad,self.records,self.summary)
        bad=deepcopy(self.result);ref=next(iter(bad['prerequisite_snapshots'].values()));ref['asof']='2026-01-03'
        new='sha256:'+digest(canonical(ref));bad['prerequisite_snapshots']={new:ref};bad['candidates'][0]['prerequisite_ref']=new
        with self.assertRaisesRegex(ValueError,'SNAPSHOT_IDENTITY_CONFLICT'):validate_parent(bad,self.records,self.summary)

    def test_historical_event_with_current_capture_remains_diagnostic(self):
        records=deepcopy(self.records);records[0]['event_date']='2025-12-31'
        valid=parent(records);validate_parent(valid,records,self.summary)
        self.assertFalse(valid['historical_visibility_proven'])

    def test_lineage_binding_requires_same_json_scalar_type(self):
        for ordinal in (False,0.0,'0'):
            with self.subTest(ordinal=ordinal):
                bad=deepcopy(self.result);ref=next(iter(bad['lineage_catalog'].values()))
                ref['row_ordinal']=ordinal;new='sha256:'+digest(canonical(ref))
                bad['lineage_catalog']={new:ref};bad['candidates'][0]['price_features']['window_lineage_refs']=[new]
                with self.assertRaisesRegex(ValueError,'METADATA_CONFLICT|NOT_IN_CURRENT_STORE'):
                    validate_parent(bad,self.records,self.summary)

    def test_candidate_date_aliases_cannot_hide_future_window_or_duplicates(self):
        for literal in ('20260102','2026-W01-5'):
            for future in (False,True):
                with self.subTest(literal=literal,future=future):
                    records=deepcopy(self.records)
                    if future:records[0]['event_date']='2026-01-03'
                    bad=parent(records);bad['candidates'][0]['decision_date']=literal
                    snapshot=next(iter(bad['prerequisite_snapshots'].values()));snapshot['asof']=literal
                    new='sha256:'+digest(canonical(snapshot));bad['prerequisite_snapshots']={new:snapshot}
                    bad['candidates'][0]['prerequisite_ref']=new
                    with self.assertRaisesRegex(ValueError,'SCOPE_CONFLICT'):validate_parent(bad,records,self.summary)


if __name__=='__main__':unittest.main()
