"""Synthetic accounting checks; no network, private originals or actual outcomes."""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_EVEN
from unittest.mock import patch
import unittest

from experiments.e2e_history_v2 import engine
from experiments.e2e_pilot_v1.tests.test_execution import case as v1_case

D=Decimal


def case(days=100,trend=True):
    old=v1_case(days,trend)
    calendar=[{**row,'decision_at':row['date']+'T18:00:00+08:00','decision_clock_label':engine.CLOCK_LABEL,
               'evidence_ref':'SYNTHETIC:source'} for row in old['calendar']]
    scope={'target_window':{'warmup_start':calendar[0]['date'],'start':calendar[20]['date'],'end':calendar[-1]['date']},
           'members':{'SSE:TEST':'TEST'}}
    source={'source':'SYNTHETIC','source_version':'fixture1','raw_sha256':'sha256:'+'0'*64,
            'published_at':None,'available_at':'2026-10-14T00:00:00Z','retrieved_at':'2026-10-14T00:00:00Z',
            'visibility_assumption':'SYNTHETIC ONLY; no claimed historical PIT'}
    return {'namespace':'SYNTHETIC:E2E_HISTORY_V2','strategy_id':'SYNTHETIC_PRICE_VOLUME_V2',
            'run_id':'SYNTHETIC:test','evidence_grade':engine.SYNTHETIC,'run_at':'2026-10-15T00:00:00Z',
            'rules':deepcopy(engine.RULES),'rules_hash':engine.digest(engine.RULES),
            'synthetic_scope':scope,'synthetic_scope_hash':engine.digest(scope),
            'calendar':calendar,'calendar_coverage':{'start':calendar[0]['date'],'end':calendar[-1]['date'],
                'days':[{'date':row['date'],'is_open':True,'evidence_ref':'SYNTHETIC:source'} for row in calendar]},
            'universe':[{'symbol':'SSE:TEST','sector':'TEST','selection_evidence_ref':'SYNTHETIC:source'}],
            'window':old['window'],'fee_schedule':old['fee_schedule'],'evidence':{'SYNTHETIC:source':source},
            'bars':[{**{k:v for k,v in row.items() if k!='evidence'},'evidence_ref':'SYNTHETIC:source'} for row in old['bars']],
            'actions':[]}


def action(value,cash='.50',bonus='0',split='1',record=25,ex=26,pay=30,available=30):
    return dict(id='SYNTHETIC:dividend',symbol='SSE:TEST',record_date=value['calendar'][record]['date'],
                ex_date=value['calendar'][ex]['date'],pay_date=value['calendar'][pay]['date'],
                shares_available_date=value['calendar'][available]['date'],cash_per_share=cash,
                bonus_ratio=bonus,split_ratio=split,tax_rate='.20',evidence_ref='SYNTHETIC:source')


def adjusted_after(value,a):
    ratio=D(a['split_ratio'])+D(a['bonus_ratio'])
    for row in value['bars']:
        if row['session']>=a['ex_date']:
            for k in ('open','high','low','close'):
                row[k]=str(((D(row[k])-D(a['cash_per_share']))/ratio).quantize(D('.01'),rounding=ROUND_HALF_EVEN))


def suspend(value,index):
    row=value['bars'][index]
    row.update(status='SUSPENDED',open=None,high=None,low=None,close=None,volume_shares='0',lower_limit=None,upper_limit=None)


class EngineTests(unittest.TestCase):
    def test_successful_ledger_and_explicit_grade(self):
        result=engine.run_diagnostic(case())
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        self.assertFalse(result['historical_visibility_proven'])
        cash=10000000
        for row in result['ledger']:
            self.assertEqual(row['cash_before_cents'],cash)
            cash+=row['cash_delta_cents'];self.assertEqual(cash,row['cash_after_cents'])
        self.assertEqual(cash,result['final_cash_cents'])

    def test_flat_no_trade_is_engine_called(self):
        result=engine.run_diagnostic(case(trend=False))
        self.assertEqual(result['status'],'RUN_NO_TRADES');self.assertTrue(result['engine_called'])
        self.assertEqual(result['net_return'],'0')

    def test_decision_clock_is_not_source_available_clock(self):
        value=case();result=engine.run_diagnostic(value)
        self.assertEqual(result['decisions'][0]['decision_at'],'2025-01-21T18:00:00+08:00')
        self.assertEqual(value['evidence']['SYNTHETIC:source']['available_at'],'2026-10-14T00:00:00Z')
        self.assertFalse(result['decisions'][0]['historical_visibility_proven'])

    def test_decision_at_close_rejected(self):
        value=case();value['calendar'][20]['decision_at']=value['calendar'][20]['close_at']
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'DATA_BLOCKED');self.assertFalse(result['engine_called'])

    def test_cash_dividend_receivable_not_cash_until_payment(self):
        value=case();a=action(value);value['actions']=[a];adjusted_after(value,a)
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        record=next(x for x in result['dividends'] if x['stage']=='RECORD')
        ex=next(x for x in result['dividends'] if x['stage']=='EX')
        expected=engine.cents(D(record['quantity'])*D('.50')*D('.80'))
        self.assertEqual(ex['net_receivable_cents'],expected)
        before=next(x for x in result['daily'] if x['session']==a['record_date'])
        exday=next(x for x in result['daily'] if x['session']==a['ex_date'])
        pay=next(x for x in result['daily'] if x['session']==a['pay_date'])
        self.assertEqual(exday['cash_cents'],before['cash_cents'])
        self.assertEqual(exday['receivable_cents'],expected)
        self.assertEqual(pay['receivable_cents'],0)
        self.assertEqual(pay['cash_cents'],exday['cash_cents']+expected)
        self.assertEqual(exday['nav_cents'],exday['cash_cents']+exday['exposure_cents']+expected)

    def test_integer_bonus_shares_valued_but_locked(self):
        value=case();a=action(value,cash='0',bonus='1');value['actions']=[a];adjusted_after(value,a)
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        record=next(x for x in result['dividends'] if x['stage']=='RECORD')['quantity']
        exday=next(x for x in result['daily'] if x['session']==a['ex_date'])['positions'][0]
        pay=next(x for x in result['daily'] if x['session']==a['shares_available_date'])['positions'][0]
        self.assertEqual(exday['quantity'],record*2);self.assertEqual(exday['available_quantity'],record)
        self.assertEqual(pay['available_quantity'],record*2)

    def test_cash_and_bonus_compose_in_one_event(self):
        value=case();a=action(value,bonus='1');value['actions']=[a];adjusted_after(value,a)
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        ex=next(x for x in result['dividends'] if x['stage']=='EX')
        self.assertEqual(ex['added_shares'],ex['record_quantity'])
        self.assertEqual(ex['price_transform'],{'subtract_gross_cash':'0.50','divide_ratio':'2'})

    def test_fractional_action_preserves_partial_engine_result(self):
        value=case();a=action(value,cash='0',bonus='.000001');value['actions']=[a];adjusted_after(value,a)
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'ENGINE_FAILED',result);self.assertTrue(result['engine_called'])
        self.assertTrue(result['fills']);self.assertTrue(result['ledger'])
        self.assertEqual(result['last_completed_session'],a['record_date'])
        self.assertEqual(result['errors'][-1]['session'],a['ex_date'])
        self.assertEqual(result['performance_scope'],'PARTIAL_COMPLETED_DAYS_ONLY')

    def test_unknown_action_date_preflight_block(self):
        value=case();a=action(value);a['pay_date']=None;value['actions']=[a]
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'DATA_BLOCKED');self.assertFalse(result['engine_called'])

    def test_nonadjacent_record_ex_block(self):
        value=case();value['actions']=[action(value,ex=27)]
        self.assertIn('ACTION_RECORD_EX_NOT_ADJACENT',engine.run_diagnostic(value)['reason_codes'])

    def test_suspension_no_fake_ohlc_no_trade_and_stale_mark_only(self):
        value=case();suspend(value,25)
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        day=value['calendar'][25]['date'];snapshot=next(x for x in result['daily'] if x['session']==day)
        self.assertEqual(snapshot['raw_bar_count'],0)
        self.assertTrue(snapshot['positions'][0]['mark']['stale_mark'])
        self.assertEqual(snapshot['positions'][0]['mark']['source_session'],value['calendar'][24]['date'])
        self.assertFalse(any(x['session']==day for x in result['fills']))
        self.assertIsNone(value['bars'][25]['close'])

    def test_fabricated_suspended_close_fails_retaining_prior_ledger(self):
        value=case();suspend(value,30);value['bars'][30]['close']='13.00'
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'ENGINE_FAILED');self.assertTrue(result['ledger'])
        self.assertEqual(result['last_completed_session'],value['calendar'][29]['date'])

    def test_resume_requires21_consecutive_real_bars(self):
        value=case(days=130);suspend(value,25)
        result=engine.run_diagnostic(value)
        for index in range(25,46):
            row=next(x for x in result['decisions'] if x['session']==value['calendar'][index]['date'])
            self.assertEqual(row['selected_sectors'],[])
        row=next(x for x in result['decisions'] if x['session']==value['calendar'][46]['date'])
        self.assertTrue(row['selected_sectors'])

    def test_t1_buy_lots_not_same_day_available(self):
        result=engine.run_diagnostic(case())
        bought=result['fills'][0];day=next(x for x in result['daily'] if x['session']==bought['session'])
        self.assertEqual(day['positions'][0]['available_quantity'],0)
        self.assertEqual(day['positions'][0]['lots'][0]['available_date'],'2025-01-23')

    def test_midrun_missing_bar_retains_all_completed_state(self):
        value=case();del value['bars'][35]
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'ENGINE_FAILED');self.assertTrue(result['fills'])
        self.assertEqual(result['last_completed_session'],value['calendar'][34]['date'])
        self.assertEqual(result['final_cash_cents'],result['ledger'][-1]['cash_after_cents'])

    def test_window_crop_is_preflight_block(self):
        value=case();value['window']['first_session']=value['calendar'][40]['date']
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'DATA_BLOCKED');self.assertFalse(result['engine_called'])

    def test_universe_substitution_is_preflight_block(self):
        value=case();value['universe'][0]['symbol']='WINNER:AFTER_OUTCOME'
        self.assertIn('FROZEN_UNIVERSE_MISMATCH',engine.run_diagnostic(value)['reason_codes'])

    def test_dropped_civil_day_is_preflight_block(self):
        value=case();del value['calendar_coverage']['days'][50]
        self.assertIn('CIVIL_CALENDAR_INCOMPLETE',engine.run_diagnostic(value)['reason_codes'])

    def test_rules_mutation_blocks(self):
        value=case();value['rules']['maximum_positions']=20
        self.assertEqual(engine.run_diagnostic(value)['status'],'DATA_BLOCKED')

    def test_provenance_callback_required_for_real_grade(self):
        value=case();scope=value['synthetic_scope'];value['evidence_grade']=engine.GRADE
        with patch.object(engine,'_scope',return_value=scope):
            result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'DATA_BLOCKED')
        self.assertEqual(result['reason_codes'],['EXTERNAL_PROVENANCE_VERIFIER_REQUIRED'])

    def test_provenance_callback_cannot_admit_other_case(self):
        value=case();scope=value['synthetic_scope'];value['evidence_grade']=engine.GRADE
        with patch.object(engine,'_scope',return_value=scope):
            result=engine.run_diagnostic(value,lambda c:{'verified':True,'case_hash':'sha256:'+'0'*64,'receipt_hash':'sha256:'+'1'*64,'purpose':'LOCAL_HISTORICAL_DIAGNOSTIC'})
        self.assertIn('PROVENANCE_RECEIPT_NOT_CASE_BOUND',result['reason_codes'])

    def test_no_input_mutation_and_determinism(self):
        value=case();original=deepcopy(value)
        first=engine.run_diagnostic(value);second=engine.run_diagnostic(value)
        self.assertEqual(first,second);self.assertEqual(value,original)


    def test_unsupported_rights_field_cannot_be_silently_ignored(self):
        value=case();a=action(value);a['rights_ratio']='.1';value['actions']=[a]
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'DATA_BLOCKED')
        self.assertIn('ACTION_CLOSED_SHAPE_OR_COMPLEX_EVENT_UNSUPPORTED',result['reason_codes'])

    def test_locked_bonus_exit_sells_available_shares_then_keeps_pending(self):
        value=case();a=action(value,cash='0',bonus='1',available=33);value['actions']=[a];adjusted_after(value,a)
        for row in value['bars'][27:]:
            for k in ('open','high','low','close'):row[k]=str((D(row[k])-D('1')).quantize(D('.01')))
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        ex=next(x for x in result['dividends'] if x['stage']=='EX')
        first_sale=next(x for x in result['fills'] if x['side']=='SELL')
        self.assertEqual(first_sale['quantity'],ex['record_quantity'])
        self.assertLess(first_sale['session'],a['shares_available_date'])
        self.assertTrue(any(x['reason']=='ACTION_SHARES_STILL_LOCKED' for x in result['unfilled']))
        locked_sales=[x for x in result['fills'] if x['side']=='SELL' and x['session']>=a['shares_available_date']]
        self.assertTrue(locked_sales)

    def test_future_action_does_not_adjust_prior_decisions(self):
        value=case();a=action(value);value['actions']=[a];adjusted_after(value,a)
        with_action=engine.run_diagnostic(value);without=engine.run_diagnostic(case())
        before_with=[d for d in with_action['decisions'] if d['session']<a['ex_date']]
        before_without=[d for d in without['decisions'] if d['session']<a['ex_date']]
        self.assertEqual(before_with,before_without)

    def test_dividend_ledger_hash_chain_includes_non_cash_ex_and_cash_pay(self):
        value=case();a=action(value);value['actions']=[a];adjusted_after(value,a)
        result=engine.run_diagnostic(value)
        previous=engine.digest({'initial_cash_cents':10000000})
        for row in result['ledger']:
            self.assertEqual(row['previous_hash'],previous)
            body={k:v for k,v in row.items() if k!='content_hash'}
            self.assertEqual(engine.digest(body),row['content_hash']);previous=row['content_hash']
        self.assertTrue(any(x['kind']=='ACTION_EX' and x['cash_delta_cents']==0 for x in result['ledger']))
        self.assertTrue(any(x['kind']=='DIVIDEND_PAYMENT' and x['cash_delta_cents']>0 for x in result['ledger']))

    def test_pending_exit_retained_when_suspended(self):
        value=case()
        for index in range(61,70):suspend(value,index)
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        self.assertTrue(any(x['side']=='SELL' and x['reason']=='SUSPENDED' for x in result['unfilled']))
        self.assertFalse(any(x['side']=='SELL' and value['calendar'][61]['date']<=x['session']<value['calendar'][70]['date'] for x in result['fills']))


    def test_pay_after_terminal_remains_receivable_not_cash(self):
        value=case();a=action(value);a['pay_date']='2025-12-31';a['shares_available_date']=None
        value['actions']=[a];adjusted_after(value,a)
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        self.assertTrue(result['receivables'])
        self.assertTrue(result['daily'][-1]['receivable_cents']>0)
        self.assertFalse(any(x['kind']=='DIVIDEND_PAYMENT' for x in result['ledger']))

    def test_non_exchange_pay_day_arrives_next_session(self):
        value=case();a=action(value);value['actions']=[a];adjusted_after(value,a)
        pay=a['pay_date']
        value['calendar_coverage']['days'][30]['is_open']=False
        value['calendar']=[r for r in value['calendar'] if r['date']!=pay]
        value['bars']=[r for r in value['bars'] if r['session']!=pay]
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        payment=next(x for x in result['ledger'] if x['kind']=='DIVIDEND_PAYMENT')
        self.assertEqual(payment['session'],'2025-02-01')

    def test_no_cash_action_allows_null_pay_date(self):
        value=case();a=action(value,cash='0',bonus='1');a['pay_date']=None
        value['actions']=[a];adjusted_after(value,a)
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        self.assertFalse(any(x['kind']=='DIVIDEND_PAYMENT' for x in result['ledger']))

    def test_added_shares_require_actual_availability_date(self):
        value=case();a=action(value,cash='0',bonus='1');a['shares_available_date']=None
        value['actions']=[a]
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'DATA_BLOCKED')
        self.assertIn('ACTION_REQUIRED_DATE_MISSING:shares_available_date',result['reason_codes'])


    def test_nonterminating_ratio_uses_decimal_sizing_bridge(self):
        value=case(days=130);a=action(value,cash='0',bonus='.3',record=20,ex=21,pay=25,available=25);value['actions']=[a];adjusted_after(value,a)
        result=engine.run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        self.assertFalse(result['errors'])
        # First pending entry crosses ex-date: ATR /.3+1 is nonterminating.
        # A later entry confirms the successor remains usable.
        self.assertGreaterEqual(len([f for f in result['fills'] if f['side']=='BUY']),2)


if __name__=='__main__':unittest.main()
