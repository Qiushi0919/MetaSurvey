"""Synthetic temporary inputs only; no market, credentials or private archives."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
import unittest
import json
from pathlib import Path
from hashlib import sha256

from experiments.e2e_pilot_v1.execution import RULES, NAMESPACE, STRATEGY, build_portfolio, digest, run_diagnostic


def fees():
    return [dict(version='SYNTHETIC-1', effective_from='2025-01-01',effective_until='2027-12-31',
                 commission_rate='0.0003',minimum_commission_cents=500,exchange_rate='0.00001',
                 exchange_included=False,other_buy_rate='0',other_sell_rate='0',other_included=True,
                 sell_tax_rate='0.0005',slippage_bps='5',currency='CNY',rate_unit='FRACTION_OF_NOTIONAL',
                 money_rounding='HALF_EVEN',commission_scope='PER_ORDER',slippage_treatment='INCLUDED_IN_EXECUTION_PRICE')]


def case(days=65, trend=True):
    calendar=[]; bars=[]; previous='10.00'
    for index in range(days):
        day=(date(2025,1,1)+timedelta(days=index)).isoformat()
        # Synthetic exchange calendar: dates intentionally need not be real sessions.
        opened=day+'T09:30:00+08:00'; closed=day+'T15:00:00+08:00'
        calendar.append(dict(date=day,open_at=opened,close_at=closed,evidence_ref='SYNTHETIC:calendar'))
        close=Decimal(10)+Decimal(index)*Decimal('.10') if trend else Decimal(10)
        proofs={}
        for kind in ('price','status','lot','action','limit'):
            at=closed if kind=='price' else opened
            proofs[kind]=dict(source_ref='SYNTHETIC:'+kind,source_hash='sha256:'+'0'*64,source_version='1',
                              event_time=at,published_at=at,available_at=at,retrieved_at=at,historical_visible_at=at)
        bars.append(dict(session=day,symbol='SSE:TEST',price_kind='RAW',status='TRADABLE',action_status='NONE_VERIFIED',
                         lot_size=100,listing_status='ACTIVE',st_status='NORMAL',evidence=proofs,
                         open=str(close),close=str(close),high=str(close+Decimal('.05')),low=str(close-Decimal('.05')),
                         lower_limit='1.00',upper_limit='100.00',volume_shares='1000000',previous_close=previous))
        previous=str(close)
    admission=dict(license_for_local_historical_diagnostic=True,historical_price_visibility=True,calendar_complete=True,
                   execution_domains_complete=True,membership_scope_explicit=True,source='SYNTHETIC',product='SYNTHETIC',
                   purpose='ENGINEERING_TEST_ONLY',evidence_refs=['SYNTHETIC'],evidence_kind='SYNTHETIC')
    return dict(namespace=NAMESPACE,strategy_id=STRATEGY,label='SYNTHETIC_ENGINE_TEST',run_id='SYNTHETIC:execution-test',
                rules=deepcopy(RULES),rules_hash=digest(RULES),preregistration_ref='SYNTHETIC:freeze',
                frozen_at='2024-12-01T00:00:00Z',run_at='2026-10-14T00:00:00Z',admission=admission,admission_hash=digest(admission),
                calendar=calendar,universe=[dict(symbol='SSE:TEST',sector='TEST',selection_evidence_ref='SYNTHETIC')],
                window=dict(first_session=calendar[20]['date'],last_session=calendar[-1]['date']),bars=bars,fee_schedule=fees())


def candidate(symbol='SSE:ONE',sector='A',price='10.00',atr='0.50'):
    return dict(symbol=symbol,sector=sector,price=price,atr20=atr,lot_size=100,previous20_median_volume_shares='1000000')


def malicious_historical_metadata():
    """Never run a successful real case: forged test metadata for rejection tests."""
    root=Path(__file__).resolve().parents[1]
    protocol_bytes=(root/'protocol.json').read_bytes(); protocol=json.loads(protocol_bytes)
    method_bytes=(root/'method.json').read_bytes(); method=json.loads(method_bytes)
    value=case()
    value.update(label='HISTORICAL_DIAGNOSTIC',preregistration_ref='sha256:'+sha256(protocol_bytes).hexdigest(),
                 method_ref='sha256:'+sha256(method_bytes).hexdigest(),frozen_at=protocol['frozen_at'],
                 run_at='2027-01-01T00:00:00Z',fee_schedule=protocol['fee_schedule'])
    value['admission']['evidence_kind']='TEST_FORGED_METADATA_MUST_NEVER_RUN'
    value['admission_hash']=digest(value['admission'])
    value['universe']=[dict(symbol=m['symbol'],sector=g['id'],selection_evidence_ref='SYNTHETIC:attack-test')
                       for g in method['universe'] for m in g['members']]
    start=date.fromisoformat(protocol['target_window']['warmup_start']); end=date.fromisoformat(protocol['target_window']['end'])
    days=[(start+timedelta(days=n)).isoformat() for n in range((end-start).days+1)]
    # All-open civil dates are deliberately synthetic; these tests mutate scope
    # and must return DATA_BLOCKED before any market arithmetic can execute.
    value['calendar_coverage']=dict(start=days[0],end=days[-1],days=[dict(date=d,is_open=True,evidence_ref='SYNTHETIC:attack-test') for d in days])
    value['calendar']=[dict(date=d,open_at=d+'T09:30:00+08:00',close_at=d+'T15:00:00+08:00',evidence_ref='SYNTHETIC:attack-test') for d in days]
    value['window']=dict(first_session=protocol['target_window']['start'],last_session=days[-1])
    value['bars']=[]
    return value


class PortfolioTests(unittest.TestCase):
    def build(self, candidates=None, cash=10000000, positions=None):
        return build_portfolio(candidates or [candidate()],cash,positions or [],10000000,fees(),'2025-02-01')

    def test_quantity_lot_and_risk(self):
        result=self.build(); plan=result['plans'][0]
        self.assertEqual(plan['quantity']%100,0)
        self.assertLessEqual(plan['planned_loss_cents'],100000)
        self.assertLessEqual(plan['entry']['fees']['notional_cents'],2000000)

    def test_fee_inclusive_cash(self):
        result=self.build(cash=100000)
        self.assertGreaterEqual(result['remaining_cash_cents'],0)
        self.assertEqual(result['plans'],[])
        self.assertEqual(result['remaining_cash_cents'],100000)

    def test_minimum_commission(self):
        plan=self.build()['plans'][0]
        self.assertGreaterEqual(plan['entry']['fees']['commission_cents'],500)

    def test_same_sector_cap(self):
        result=self.build([candidate('A',price='10',atr='.01'),candidate('B',price='10',atr='.01'),candidate('C',price='10',atr='.01')])
        self.assertLessEqual(result['invested_cents'],4000000)

    def test_three_positions_and_total_cap(self):
        result=self.build([candidate(str(n),str(n),atr='.01') for n in range(5)])
        self.assertEqual(len(result['plans']),3)
        self.assertLessEqual(result['invested_cents'],6000000)

    def test_no_averaging(self):
        result=self.build(positions=[dict(symbol='SSE:ONE',sector='A',quantity=100,mark_price='10')])
        self.assertEqual(result['rejections'][0]['reason'],'NO_AVERAGING_OR_SAME_DAY_REENTRY')

    def test_duplicate_prevention(self):
        result=self.build([candidate(),candidate()])
        self.assertEqual(len(result['plans']),1)
        self.assertEqual(result['rejections'][0]['reason'],'DUPLICATE_CANDIDATE')

    def test_unaffordable_leader_kept_as_rejection(self):
        result=self.build([candidate(price='3000',atr='10')])
        self.assertEqual(result['plans'],[])
        self.assertEqual(result['rejections'][0]['reason'],'RISK_CASH_LOT_OR_VOLUME_UNAFFORDABLE')

    def test_passive_exposure_block(self):
        result=self.build(positions=[dict(symbol='OTHER',sector='B',quantity=7000,mark_price='10')])
        self.assertEqual(result['plans'],[])
        self.assertIn(result['rejections'][0]['reason'],('PASSIVE_OR_ACTIVE_EXPOSURE_CAP','PASSIVE_POSITION_OR_SECTOR_CAP'))


    def test_passive_single_position_breach_blocks_new_sector(self):
        result=self.build(positions=[dict(symbol='OTHER',sector='B',quantity=2500,mark_price='10')])
        self.assertEqual(result['plans'],[])
        self.assertEqual(result['rejections'][0]['reason'],'PASSIVE_POSITION_OR_SECTOR_CAP')

    def test_previous_volume_cap_is_not_replaced_by_current_volume(self):
        value=candidate(atr='.01'); value['previous20_median_volume_shares']='10000'
        result=self.build([value]); self.assertEqual(result['plans'][0]['quantity'],100)


    def test_position_quantities_must_be_positive_integers(self):
        for quantity in (-1,0,1.5,'100',True):
            with self.subTest(quantity=quantity), self.assertRaisesRegex(ValueError,'POSITIVE_INTEGER_POSITION_QUANTITY_REQUIRED'):
                self.build(positions=[dict(symbol='OTHER',sector='B',quantity=quantity,mark_price='10')])

    def test_duplicate_positions_rejected(self):
        position=dict(symbol='OTHER',sector='B',quantity=100,mark_price='10')
        with self.assertRaisesRegex(ValueError,'DUPLICATE_POSITION'):
            self.build(positions=[position,deepcopy(position)])


class EngineTests(unittest.TestCase):
    def test_simulated_run_ledger_reconciliation_and_t1(self):
        result=run_diagnostic(case())
        self.assertTrue(result['engine_called'],result)
        self.assertEqual(result['status'],'SIMULATED_TRADES')
        cash=10000000; acquired={}
        for row in result['ledger']:
            self.assertEqual(row['cash_before_cents'],cash)
            cash+=row['cash_delta_cents']; self.assertEqual(cash,row['cash_after_cents'])
            if row['side']=='BUY': acquired[row['symbol']]=row['session']
            else: self.assertGreater(row['session'],acquired[row['symbol']])
        self.assertEqual(cash,result['final_cash_cents'])

    def test_no_trades_is_not_not_run(self):
        result=run_diagnostic(case(trend=False))
        self.assertEqual(result['status'],'RUN_NO_TRADES')
        self.assertTrue(result['engine_called']); self.assertEqual(result['net_return'],'0')

    def test_missing_critical_execution_data_blocks_before_engine(self):
        value=case(); del value['bars'][24]['lot_size']
        result=run_diagnostic(value)
        self.assertEqual(result['status'],'DATA_BLOCKED'); self.assertFalse(result['engine_called'])
        self.assertIsNone(result['net_return'])

    def test_unknown_corporate_action_blocks(self):
        value=case(); value['bars'][30]['action_status']='UNKNOWN'
        self.assertIn('CORPORATE_ACTION_UNSUPPORTED_OR_UNKNOWN',run_diagnostic(value)['reason_codes'])

    def test_future_price_visibility_blocks(self):
        value=case(); value['bars'][25]['evidence']['price']['historical_visible_at']='2027-01-01T00:00:00Z'
        self.assertEqual(run_diagnostic(value)['status'],'DATA_BLOCKED')

    def test_synthetic_cannot_be_real_performance(self):
        value=case(); value['label']='HISTORICAL_DIAGNOSTIC'
        self.assertEqual(run_diagnostic(value)['status'],'DATA_BLOCKED')

    def test_limit_block_has_no_fabricated_fill(self):
        value=case()
        for bar in value['bars'][21:]:
            bar['upper_limit']=bar['open']; bar['high']=bar['open']
        result=run_diagnostic(value)
        self.assertEqual(result['status'],'RUN_NO_TRADES'); self.assertGreater(len(result['unfilled']),0)

    def test_failed_exit_retains_risk(self):
        value=case()
        # Buy first, then suspension precisely when terminal40 exit becomes due.
        for bar in value['bars'][61:]: bar['status']='SUSPENDED'
        result=run_diagnostic(value)
        self.assertTrue(result['positions'])
        self.assertTrue(result['terminal_pending_exits'])
        self.assertTrue(any(x['side']=='SELL' and x['reason']=='SUSPENDED' for x in result['unfilled']))

    def test_input_and_frozen_rules_unchanged(self):
        value=case(); before=deepcopy(value)
        run_diagnostic(value); self.assertEqual(value,before)
        value['rules']['maximum_positions']=5
        self.assertEqual(run_diagnostic(value)['status'],'DATA_BLOCKED')

    def test_current_retrieval_does_not_backfill_historical_visibility(self):
        value=case()
        for proof in value['bars'][20]['evidence'].values():
            proof['available_at']='2026-10-14T00:00:00Z'; proof['retrieved_at']='2026-10-14T00:00:00Z'
            proof['historical_visible_at']='2026-10-14T00:00:00Z'
        self.assertEqual(run_diagnostic(value)['status'],'DATA_BLOCKED')


    def test_all_admission_gaps_reported_and_null_performance(self):
        value=case()
        for key in ('license_for_local_historical_diagnostic','historical_price_visibility','execution_domains_complete'):
            value['admission'][key]=False
        value['admission_hash']=digest(value['admission'])
        result=run_diagnostic(value)
        self.assertEqual(len(result['reason_codes']),3)
        self.assertFalse(result['engine_called']); self.assertIsNone(result['maximum_drawdown'])

    def test_final40_sessions_no_new_entries(self):
        result=run_diagnostic(case())
        self.assertTrue(all(not row['ranked_buy_symbols'] for row in result['decisions'][-41:]))
        final40={row['session'] for row in result['equity'][-40:]}
        self.assertFalse(any(row['side']=='BUY' and row['session'] in final40 for row in result['fills']))

    def test_source_hash_tampering_rejected(self):
        value=case(); value['bars'][25]['evidence']['price']['source_hash']='not-a-hash'
        self.assertEqual(run_diagnostic(value)['status'],'DATA_BLOCKED')

    def test_two_runs_are_identical(self):
        value=case()
        self.assertEqual(run_diagnostic(value),run_diagnostic(deepcopy(value)))

    def test_sell_first_allows_fresh_symbol_using_actual_sale_cash(self):
        value=case(days=120)
        value['universe'].append(dict(symbol='SSE:TWO',sector='OTHER',selection_evidence_ref='SYNTHETIC'))
        peer=[]; previous='10.00'
        for index, source in enumerate(value['bars']):
            row=deepcopy(source); row['symbol']='SSE:TWO'
            close=Decimal('10') if index<24 else Decimal('11')+Decimal(index-24)*Decimal('.1')
            row.update(open=str(close),close=str(close),high=str(close+Decimal('.05')),
                       low=str(close-Decimal('.05')),previous_close=previous)
            previous=str(close); peer.append(row)
        value['bars'][24].update(open='10.00',close='10.00',high='10.05',low='9.95')
        value['bars'][25]['previous_close']='10.00'
        value['bars']+=peer
        result=run_diagnostic(value)
        self.assertEqual(result['status'],'SIMULATED_TRADES',result)
        day=value['calendar'][25]['date']
        rows=[row for row in result['ledger'] if row['session']==day]
        self.assertEqual([row['side'] for row in rows],['SELL','BUY'])
        self.assertEqual(rows[1]['cash_before_cents'],rows[0]['cash_after_cents'])
        self.assertNotEqual(rows[0]['symbol'],rows[1]['symbol'])

    def test_selection_limited_to_top_two_sectors(self):
        value=case()
        original=deepcopy(value['bars'])
        for name in ('TWO','THREE'):
            value['universe'].append(dict(symbol='SSE:'+name,sector=name,selection_evidence_ref='SYNTHETIC'))
            value['bars'] += [dict(deepcopy(row),symbol='SSE:'+name) for row in original]
        result=run_diagnostic(value)
        self.assertTrue(all(len(row['selected_sample_sectors'])<=2 for row in result['decisions']))
        self.assertEqual(len(result['decisions'][0]['selected_sample_sectors']),2)

    def test_execution_volume_shortfall_records_unfilled_not_fill(self):
        value=case()
        value['bars'][21]['volume_shares']='1'
        result=run_diagnostic(value)
        day=value['calendar'][21]['date']
        self.assertTrue(any(row['session']==day and row['reason']=='ACTUAL_SESSION_VOLUME_CAP' for row in result['unfilled']))
        self.assertFalse(any(row['session']==day for row in result['fills']))


class FrozenHistoricalScopeTests(unittest.TestCase):
    def assert_blocked(self,value,reason):
        result=run_diagnostic(value)
        self.assertEqual(result['status'],'DATA_BLOCKED',result)
        self.assertFalse(result['engine_called']); self.assertIsNone(result['net_return'])
        self.assertIn(reason,result['reason_codes'])

    def test_method_hash_is_mandatory(self):
        value=malicious_historical_metadata(); del value['method_ref']
        self.assert_blocked(value,'REAL_METHOD_HASH_REQUIRED')

    def test_changed_method_hash_rejected(self):
        value=malicious_historical_metadata(); value['method_ref']='sha256:'+'0'*64
        self.assert_blocked(value,'REAL_METHOD_HASH_REQUIRED')

    def test_cropped_universe_cannot_share_protocol(self):
        value=malicious_historical_metadata(); value['universe']=value['universe'][:3]
        self.assert_blocked(value,'REAL_FROZEN_UNIVERSE_MISMATCH')

    def test_changed_sector_mapping_cannot_share_protocol(self):
        value=malicious_historical_metadata(); value['universe'][0]['sector']='WINNING_NEW_SECTOR'
        self.assert_blocked(value,'REAL_FROZEN_UNIVERSE_MISMATCH')

    def test_cropped_window_cannot_share_protocol(self):
        value=malicious_historical_metadata(); value['window']['first_session']='2026-01-01'
        self.assert_blocked(value,'REAL_PREREGISTERED_WINDOW_MISMATCH')

    def test_tail_truncation_cannot_share_protocol(self):
        value=malicious_historical_metadata(); value['window']['last_session']='2026-08-31'
        self.assert_blocked(value,'REAL_PREREGISTERED_WINDOW_MISMATCH')

    def test_absent_complete_calendar_cannot_share_protocol(self):
        value=malicious_historical_metadata(); del value['calendar_coverage']
        self.assert_blocked(value,'REAL_COMPLETE_CALENDAR_COVERAGE_REQUIRED')

    def test_dropped_calendar_day_blocks(self):
        value=malicious_historical_metadata(); del value['calendar_coverage']['days'][50]
        self.assert_blocked(value,'REAL_CALENDAR_CIVIL_DATE_GAP_OR_TRUNCATION')

    def test_dropped_exchange_session_blocks(self):
        value=malicious_historical_metadata(); del value['calendar'][50]
        self.assert_blocked(value,'REAL_EXCHANGE_SESSIONS_MISMATCH')

    def test_warmup_crop_blocks(self):
        value=malicious_historical_metadata(); value['calendar_coverage']['start']='2025-09-01'
        self.assert_blocked(value,'REAL_COMPLETE_CALENDAR_COVERAGE_REQUIRED')


if __name__=='__main__': unittest.main()
