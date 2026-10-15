"""Synthetic clock/accounting fixtures; no network, secrets, or real quotes."""
from copy import deepcopy
import unittest
from experiments.e2e_history_v2.tests.test_engine import case as old_case
from experiments.long_forward_v1 import engine as e
from tools.long_forward.forward import prepare,settle,_sealed


def fixture(mode='FORWARD_A',end=21,total=85):
    full=old_case(total)
    protocol={'namespace':'EXPERIMENT:CORE40:LONG_FORWARD_V1','strategy_id':'CORE40_FIXED_NINE_LONG_FORWARD_V1',
        'frozen_at':'2024-12-01T00:00:00Z','method_ref':'sha256:'+'a'*64,
        'rules_hash':e.digest(e.RULES),'synthetic_only':True,'members':{'SSE:TEST':'TEST'},
        'fee_schedule':deepcopy(full['fee_schedule']),
        'target_window':{'warmup_start':full['calendar'][0]['date'],'start':full['calendar'][20]['date'],'end':full['calendar'][-1]['date']},
        'forward':{'warmup_start':full['calendar'][0]['date'],'first_decision_session':full['calendar'][21]['date'],'bootstrap_delayed_entry':True,'review_sessions':[5,20,40]}}
    c=deepcopy(full);c.update(namespace=protocol['namespace'],strategy_id=protocol['strategy_id'],mode=mode,
        method_ref=protocol['method_ref'],protocol_ref=e.digest(protocol))
    for proof in c['evidence'].values():proof.update(available_at='2024-12-31T00:00:00Z',retrieved_at='2024-12-31T00:00:00Z')
    if mode=='FORWARD_A':
        c['calendar']=c['calendar'][:end+1];day=c['calendar'][-1]['date'];c['bars']=c['bars'][:end+1]
        c['execution_calendar']=deepcopy(full['calendar'][end+1:end+4])
        c['calendar_coverage']['end']=day;c['calendar_coverage']['days']=c['calendar_coverage']['days'][:end+1]
        c['window']={'first_session':protocol['forward']['first_decision_session'],'last_session':day}
        c['forward_scope']={'warmup_start':protocol['forward']['warmup_start'],'start':protocol['forward']['first_decision_session'],'end':day}
        c['run_at']=day+'T18:00:00+08:00'
    else:c['run_at']='2026-10-15T00:00:00Z'
    return c,protocol

class ForwardTests(unittest.TestCase):
    def test_bootstrap_has_no_historical_trade_or_nav(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p)
        self.assertEqual(a['status'],'PLAN_FROZEN');self.assertEqual(a['state']['result']['daily'],[])
        self.assertEqual(a['state']['result']['fills'],[]);self.assertEqual(a['plan']['source_session'],c['calendar'][-1]['date'])
        self.assertEqual(a['plan']['execution_session'],c['execution_calendar'][0]['date'])
        self.assertTrue(a['plan']['pending_buys'])
    def test_next_session_settlement_cash_chain_and_idempotence(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22)
        b=settle(c2,a['state'],a['plan'],c2['run_at'],p)
        self.assertEqual(b['status'],'SETTLED');self.assertTrue(b['state']['result']['fills'])
        cash=10000000
        for row in b['state']['result']['ledger']:
            self.assertEqual(row['cash_before_cents'],cash);cash+=row['cash_delta_cents'];self.assertEqual(row['cash_after_cents'],cash)
        self.assertEqual(cash,b['state']['runtime']['cash_cents'])
        again=settle(c2,b['state'],a['plan'],c2['run_at'],p)
        self.assertEqual(again['status'],'ALREADY_SETTLED');self.assertEqual(again['state'],b['state'])
    def test_no_preexisting_plan_is_missed(self):
        c,p=fixture();self.assertEqual(settle(c,None,None,c['run_at'],p)['status'],'MISSED')
    def test_changed_plan_rehashed_still_not_bound(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);bad=deepcopy(a['plan']);bad['pending_buys']=[];bad=_sealed(bad);c2,_=fixture(end=22)
        with self.assertRaisesRegex(ValueError,'PLAN_NOT_BOUND'):settle(c2,a['state'],bad,c2['run_at'],p)
    def test_previous_close_is_valid_during_current_session_but_stale_at_close(self):
        c,p=fixture();next_day=c['execution_calendar'][0]['date'];now=next_day+'T14:59:59+08:00';c['run_at']=now
        self.assertEqual(prepare(c,None,now,p)['status'],'PLAN_FROZEN')
        c['run_at']=next_day+'T15:00:00+08:00'
        with self.assertRaisesRegex(ValueError,'STALE_FORWARD_COMPLETED_SESSION'):prepare(c,None,c['run_at'],p)
    def test_previous_session_cannot_prepare_after_latest_close(self):
        c,p=fixture();now=c['execution_calendar'][0]['date']+'T18:30:00+08:00';c['run_at']=now
        with self.assertRaisesRegex(ValueError,'STALE_FORWARD_COMPLETED_SESSION'):prepare(c,None,now,p)
        current,_=fixture(end=22);current['run_at']=now
        self.assertEqual(prepare(current,None,now,p)['status'],'PLAN_FROZEN')
    def test_removing_execution_calendar_cannot_bypass_stale_guard(self):
        c,p=fixture();c['run_at']=c['execution_calendar'][0]['date']+'T18:30:00+08:00';c['execution_calendar']=[]
        with self.assertRaisesRegex(ValueError,'EXECUTION_CALENDAR_REQUIRED'):prepare(c,None,c['run_at'],p)
    def test_future_bar_in_prepare_rejected(self):
        c,p=fixture();now=c['calendar'][-1]['date']+'T14:00:00+08:00'
        c['run_at']=now
        with self.assertRaisesRegex(ValueError,'UNFINISHED_SESSION'):prepare(c,None,now,p)
    def test_future_source_clock_rejected(self):
        c,p=fixture();c['evidence']['SYNTHETIC:source']['retrieved_at']='2030-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'FUTURE_RETRIEVAL'):prepare(c,None,c['run_at'],p)
    def test_first_plan_wins_after_same_execution_day_new_data(self):
        c,p=fixture();now=c['execution_calendar'][0]['date']+'T11:00:00+08:00';c['run_at']=now
        a=prepare(c,None,now,p);self.assertEqual(a['plan']['execution_session'],c['execution_calendar'][1]['date'])
        self.assertEqual(a['state']['events'][0]['kind'],'BOOTSTRAP_DELAYED_ENTRY')
        c2,_=fixture(end=22);b=prepare(c2,a['state'],c2['run_at'],p)
        self.assertEqual(b['status'],'FIRST_PLAN_WINS');self.assertEqual(b['plan'],a['plan'])
        c3,_=fixture(end=23);done=settle(c3,b['state'],b['plan'],c3['run_at'],p)
        self.assertEqual(len(done['state']['result']['daily']),1)
        self.assertEqual(done['state']['result']['daily'][0]['session'],c3['calendar'][-1]['date'])
    def test_regular_late_freeze_is_missed_no_backfill(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22);b=settle(c2,a['state'],a['plan'],c2['run_at'],p)
        late=c2['execution_calendar'][0]['date']+'T10:00:00+08:00';c2['run_at']=late
        r=prepare(c2,b['state'],late,p);self.assertEqual(r['status'],'MISSED');self.assertIsNone(r['plan'])
    def test_settlement_before_close_rejected(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22);now=c2['calendar'][-1]['date']+'T14:00:00+08:00';c2['run_at']=now
        with self.assertRaisesRegex(ValueError,'UNFINISHED_SESSION'):settle(c2,a['state'],a['plan'],now,p)
    def test_consumed_history_change_rejected(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22);c2['bars'][0]['close']='10.01'
        with self.assertRaisesRegex(ValueError,'CONSUMED_BAR_CHANGED'):settle(c2,a['state'],a['plan'],c2['run_at'],p)
    def test_future_range_only_rejects_frozen_plan_not_changes_order(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);original=deepcopy(a['plan']);c2,_=fixture(end=22)
        row=c2['bars'][-1];row['open']=row['close']=row['high']=row['low']=row['upper_limit']
        b=settle(c2,a['state'],a['plan'],c2['run_at'],p)
        self.assertEqual(b['state']['result']['fills'],[]);self.assertEqual(a['plan'],original)
        self.assertEqual(b['state']['result']['unfilled'][0]['reason'],'LIMIT_OR_SLIPPAGE_BOUND')
    def test_two_settlements_are_continuous(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22);b=settle(c2,a['state'],a['plan'],c2['run_at'],p)
        a2=prepare(c2,b['state'],c2['run_at'],p);c3,_=fixture(end=23);b2=settle(c3,a2['state'],a2['plan'],c3['run_at'],p)
        self.assertEqual(len(b2['state']['result']['daily']),2);self.assertEqual(b2['state']['parent_hash'],a2['state']['content_hash'])
        self.assertEqual(b2['state']['result']['ledger'][:len(b['state']['result']['ledger'])],b['state']['result']['ledger'])
    def test_future_announced_dividend_record_then_ex_receivable_and_locked_bonus(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22)
        action={'id':'SYNTHETIC:DIV','symbol':'SSE:TEST','record_date':c2['calendar'][-1]['date'],
            'ex_date':c2['execution_calendar'][0]['date'],'pay_date':c2['execution_calendar'][1]['date'],
            'shares_available_date':c2['execution_calendar'][1]['date'],'cash_per_share':'1','bonus_ratio':'1',
            'split_ratio':'1','tax_rate':'0.20','evidence_ref':'SYNTHETIC:source'}
        c2['actions']=[action];b=settle(c2,a['state'],a['plan'],c2['run_at'],p)
        quantity=b['state']['result']['daily'][-1]['positions'][0]['quantity']
        plan2=prepare(c2,b['state'],c2['run_at'],p);c3,_=fixture(end=23);c3['actions']=[action]
        row=c3['bars'][-1]
        for k in ('open','high','low','close'):row[k]=str((e.D(row[k])-1)/2)
        # RAW cent ticks remain mandatory.
        for k in ('open','high','low','close'):row[k]=str(e.D(row[k]).quantize(e.D('.01')))
        r=settle(c3,plan2['state'],plan2['plan'],c3['run_at'],p)
        self.assertEqual(r['status'],'SETTLED',r)
        d=r['state']['result']['daily'][-1];self.assertEqual(d['receivable_cents'],quantity*80)
        self.assertEqual(d['positions'][0]['quantity'],quantity*2);self.assertEqual(d['positions'][0]['available_quantity'],quantity)
    def test_mid_session_action_error_retains_original_state_for_retry(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22)
        action={'id':'SYNTHETIC:FRACTION','symbol':'SSE:TEST','record_date':c2['calendar'][-1]['date'],
            'ex_date':c2['execution_calendar'][0]['date'],'pay_date':None,
            'shares_available_date':c2['execution_calendar'][1]['date'],'cash_per_share':'0','bonus_ratio':'0.0001',
            'split_ratio':'1','tax_rate':'0.20','evidence_ref':'SYNTHETIC:source'}
        c2['actions']=[action];b=settle(c2,a['state'],a['plan'],c2['run_at'],p);plan2=prepare(c2,b['state'],c2['run_at'],p)
        c3,_=fixture(end=23);c3['actions']=[action];r=settle(c3,plan2['state'],plan2['plan'],c3['run_at'],p)
        self.assertEqual(r['status'],'SETTLEMENT_BLOCKED');self.assertIn('FRACTIONAL_CORPORATE',r['reason'])
        self.assertEqual(r['state'],plan2['state']);self.assertEqual(r['plan'],plan2['plan'])
    def test_consumed_calendar_and_evidence_are_immutable(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p)
        for change in ('calendar','evidence'):
            c2,_=fixture(end=22)
            if change=='calendar':c2['calendar'][0]['close_at']=c2['calendar'][0]['date']+'T15:01:00+08:00'
            else:c2['evidence']['SYNTHETIC:source']['source_version']='changed'
            with self.assertRaisesRegex(ValueError,'CONSUMED_'):settle(c2,a['state'],a['plan'],c2['run_at'],p)
    def test_post_settlement_changed_case_rejected(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22);b=settle(c2,a['state'],a['plan'],c2['run_at'],p)
        c2['run_at']=c2['calendar'][-1]['date']+'T19:00:00+08:00'
        with self.assertRaisesRegex(ValueError,'SETTLED_CASE_CHANGED'):settle(c2,b['state'],a['plan'],c2['run_at'],p)
    def test_missed_no_plan_marks_exposure_without_any_trade(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22);b=settle(c2,a['state'],a['plan'],c2['run_at'],p)
        c3,_=fixture(end=23);missed=settle(c3,b['state'],None,c3['run_at'],p)
        self.assertEqual(missed['status'],'MISSED_NO_PLAN_MARK_ONLY');self.assertEqual(missed['receipt']['successful_forward_days_added'],0)
        self.assertEqual(missed['state']['result']['fills'],b['state']['result']['fills'])
        self.assertEqual(missed['state']['result']['daily'][-1]['observation_status'],'MISSED_NO_PLAN_MARK_ONLY')
        self.assertGreater(missed['state']['result']['daily'][-1]['exposure_cents'],0)
        nextplan=prepare(c3,missed['state'],c3['run_at'],p);self.assertEqual(nextplan['status'],'PLAN_FROZEN')
    def test_missing_plan_argument_cannot_discard_existing_frozen_plan(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22)
        with self.assertRaisesRegex(ValueError,'EXPLICIT_EXPIRED_PLAN_ARCHIVE'):settle(c2,a['state'],None,c2['run_at'],p)
    def test_missed_mark_is_idempotent_and_not_successful_forward_day(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22);b=settle(c2,a['state'],a['plan'],c2['run_at'],p)
        c3,_=fixture(end=23);m=settle(c3,b['state'],None,c3['run_at'],p);again=settle(c3,m['state'],None,c3['run_at'],p)
        self.assertEqual(again['status'],'ALREADY_MARKED_MISSED');self.assertEqual(again['state'],m['state'])
        days=m['state']['result']['daily'];self.assertEqual(sum(x['decision_executed'] for x in days),1)
    def test_missed_days_do_not_generate_any_backfilled_decision(self):
        c,p=fixture();a=prepare(c,None,c['run_at'],p);c2,_=fixture(end=22);b=settle(c2,a['state'],a['plan'],c2['run_at'],p)
        c4,_=fixture(end=24);m=settle(c4,b['state'],None,c4['run_at'],p)
        self.assertEqual(m['state']['result']['decisions'],b['state']['result']['decisions'])
        self.assertEqual(len(m['receipt']['missing_sessions']),2)
    def test_mutation_does_not_touch_caller(self):
        c,p=fixture();old=deepcopy(c);a=prepare(c,None,c['run_at'],p);self.assertEqual(c,old)
        saved=deepcopy(a);c2,_=fixture(end=22);settle(c2,a['state'],a['plan'],c2['run_at'],p);self.assertEqual(a,saved)

if __name__=='__main__':unittest.main()
