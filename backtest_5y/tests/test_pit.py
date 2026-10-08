"""A positive synthetic verifier path is never actual historical admission."""
import copy
import unittest
from datetime import date, timedelta

from backtest_5y.interface import canonical, digest
from backtest_5y.pit import exact_clock, verify_price_admission


def evidence_fixture():
    rows=[]
    start=date(2024,1,1);end=(start+timedelta(days=79)).isoformat()
    for i in range(80):
        d=(start+timedelta(days=i)).isoformat()
        rows.append(('PRICE','600312.SH',d,dict(trade_date=d.replace('-',''),open='10',high='11',low='9',close='10',vol='100'),{'price':'CNY_PER_SHARE','volume':'SHARES'}))
        rows.append(('CALENDAR','SSE',d,dict(cal_date=d.replace('-',''),exchange='SSE',is_open='1'),{'calendar':'DATE'}))
    rows += [('STATUS','600312.SH',start.isoformat(),dict(effective_from=start.isoformat(),effective_to=end,tradeable=True,st=False,halted=False,board='MAIN',lot_size='100',limit_rule_version='FIXTURE_V1'),{'status':'BOOLEAN'}),
        ('ACTION','600312.SH',start.isoformat(),dict(coverage_start=start.isoformat(),coverage_end=end,action_inventory='COMPLETE',price_basis='RAW_COMPARABLE_ACTION_RECONCILED'),{'action':'RECONCILIATION'})]
    records=[];proofs=[];documents={}
    for i,(domain,symbol,day,fields,units) in enumerate(rows):
        raw=canonical([fields]);sha=digest(raw);documents[sha]=raw
        r=dict(domain=domain,symbol=symbol,event_date=day,identity='FIXTURE:'+str(i),record_hash='FIXTURE_KEY:'+str(i),
            raw_sha256=sha,row_ordinal=0,revision_id='FIXTURE_V1',units=units,fields=fields,
            published_at='2024-01-01T01:00:00+00:00',available_at='2024-01-01T01:01:00+00:00',
            first_visible_at='2024-01-01T01:02:00+00:00',retrieved_at='2026-10-08T01:00:00+00:00',
            license_state='VERIFIED_FOR_LOCAL_HISTORICAL_RESEARCH')
        clock_day = day if domain == 'PRICE' else end if domain == 'ACTION' else '2024-01-01'
        r.update(published_at=clock_day+'T07:00:00+00:00',available_at=clock_day+'T07:01:00+00:00',
                 first_visible_at=clock_day+'T07:02:00+00:00')
        records.append(r)
        proofs.append(dict(record_key=r['record_hash'],**{k:r[k] for k in ('domain','symbol','identity','raw_sha256','row_ordinal','revision_id','units','published_at','available_at','first_visible_at')},
            source_url='https://www.sse.com.cn/FIXTURE_NOT_REAL',evidence_kind='OFFICIAL_ARCHIVED_PUBLICATION_WITH_VERSION',
            availability_basis='INDEPENDENT_HISTORICAL_PUBLICATION_ARCHIVE'))
    return records,dict(manifest=dict(classification='SYNTHETIC_FIXTURE',proofs=proofs),raw_documents=documents)


class PitTests(unittest.TestCase):
    cutoff='2024-03-20T16:00:00+08:00'

    def test_complete_fixture_positive_never_actual_or_engine(self):
        rows,evidence=evidence_fixture()
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence,mode='synthetic_fixture')
        self.assertEqual(out['reason_codes'],[])
        self.assertEqual(out['state'],'FIXTURE_PRICE_VERIFIED')
        self.assertFalse(out['admitted']);self.assertFalse(out['historical_visibility_proven'])
        self.assertFalse(out['full_strategy_admitted']);self.assertFalse(out['engine_called'])

    def test_caller_flags_hashes_and_fixture_cannot_admit_actual(self):
        rows,evidence=evidence_fixture();evidence['historical_visibility_proven']=True
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence)
        self.assertEqual(out['state'],'BLOCKED')
        self.assertIn('INDEPENDENT_HISTORICAL_MANIFEST_REQUIRED',out['reason_codes'])
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence='/tmp/unapproved-history.json')
        self.assertIn('HISTORICAL_MANIFEST_NOT_IN_INDEPENDENT_REVIEW_PINS',out['reason_codes'])

    def test_modes_and_clock_precision_fail_closed(self):
        rows,evidence=evidence_fixture()
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence,mode='FORMAL')
        self.assertEqual(out['reason_codes'],['UNSUPPORTED_PIT_MODE'])
        for clock in ('2024-01-01','2024-01-01T01:00+08:00','2024-01-01T01:00:00'):
            with self.assertRaises(ValueError): exact_clock(clock)
        out=verify_price_admission(rows,cutoff='2024-03-20',mode='synthetic_fixture',evidence=evidence)
        self.assertIn('DECISION_EXACT_CLOCK_REQUIRED',out['reason_codes'])

    def test_current_retrieval_is_separate_reconstruction(self):
        rows,evidence=evidence_fixture()
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence,mode='historical_reconstruction')
        self.assertEqual(out['state'],'RECONSTRUCTION_ONLY');self.assertFalse(out['admitted'])
        evidence['manifest']['proofs'][0]['availability_basis']='CURRENT_RETRIEVAL'
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence,mode='synthetic_fixture')
        self.assertIn('CURRENT_RETRIEVAL_IS_NOT_HISTORICAL_VISIBILITY',out['reason_codes'])

    def test_raw_payload_binding_not_caller_hash(self):
        rows,evidence=evidence_fixture();rows[0]['fields']['close']='999'
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence,mode='synthetic_fixture')
        self.assertIn('RAW_ROW_FIELDS_BINDING_CONFLICT',out['reason_codes'])
        self.assertIn('PRICE_NUMERIC_OR_OHLC_CONFLICT',out['reason_codes'])
        self.assertFalse(out['admitted'])

    def test_future_poison_does_not_enter_earlier_verification(self):
        rows,evidence=evidence_fixture();before=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence,mode='synthetic_fixture')
        poison={'event_date':'2030-01-01','fields':{'close':'NaN'},'domain':'PRICE','symbol':'600312.SH'}
        after=verify_price_admission(rows+[poison],cutoff=self.cutoff,evidence=evidence,mode='synthetic_fixture')
        self.assertEqual(before,after)

    def test_calendar_status_action_and_units_each_required(self):
        rows,evidence=evidence_fixture()
        for domain,code in [('CALENDAR','OFFICIAL_CIVIL_CALENDAR_COVERAGE_MISSING'),
            ('STATUS','OFFICIAL_HISTORICAL_STATUS_INTERVAL_MISSING_OR_CONFLICTING'),
            ('ACTION','OFFICIAL_COMPLETE_ACTION_RECONCILIATION_REQUIRED')]:
            out=verify_price_admission([r for r in rows if r['domain']!=domain],cutoff=self.cutoff,evidence=evidence,mode='synthetic_fixture')
            self.assertIn(code,out['reason_codes'])
        rows[0]['units']['volume']='LOTS_UNVERIFIED'
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence,mode='synthetic_fixture')
        self.assertIn('PRICE_AND_VOLUME_VERIFIED_UNIT_REQUIRED',out['reason_codes'])

    def test_publication_after_cutoff_and_clock_binding_block(self):
        rows,evidence=evidence_fixture();rows[0]['first_visible_at']='2026-10-08T01:00:00+00:00'
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence,mode='synthetic_fixture')
        self.assertIn('HISTORICAL_CLOCK_ORDER_OR_CUTOFF_CONFLICT',out['reason_codes'])
        rows,evidence=evidence_fixture();rows[0]['published_at']='2023-12-31T01:00:00+00:00'
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence,mode='synthetic_fixture')
        self.assertIn('INDEPENDENT_PUBLICATION_CLOCK_BINDING_CONFLICT',out['reason_codes'])

    def test_eod_price_cannot_be_known_before_bar(self):
        rows,evidence=evidence_fixture()
        rows[0]['published_at']='2024-01-01T01:00:00+00:00'
        evidence['manifest']['proofs'][0]['published_at']=rows[0]['published_at']
        out=verify_price_admission(rows,cutoff=self.cutoff,evidence=evidence,mode='synthetic_fixture')
        self.assertIn('PRICE_PUBLICATION_PRECEDES_EOD_BAR',out['reason_codes'])


if __name__=='__main__': unittest.main()
