"""Root P1 repair regression fixtures; synthetic clocks never admit real data."""
import copy
import unittest
from backtest_5y.clocks import exact_clock, source_day
from backtest_5y.dto import clock, evidence_bundle, validate_candidate, walk_forward_plan
from backtest_5y.maintenance import _clock
from backtest_5y.schema_subset import validate
from backtest_5y.strategy import financial_quarters


def quarters(last_visible='2020-01-10T00:00:00.000000001Z'):
    rows = []
    for year in (2018, 2019):
        for end in ('03-31', '06-30', '09-30', '12-31'):
            day = f'{year}-{end}'
            visible = last_visible if day == '2019-12-31' else '2020-01-09T00:00:00Z'
            rows.append(dict(symbol='600312.SH', domain='FINANCIAL_INCOME', event_date=day,
                published_at=visible, available_at=visible, first_visible_at=visible,
                revision_id='SYNTHETIC_ROOT_F01', fields=dict(reporting_basis='DISCRETE_QUARTER',
                    revenue='100',oper_cost='100',n_income='100',n_cashflow_act='100',ebitda='100'),
                units={k:'CNY' for k in ('currency','revenue','oper_cost','net_income','operating_cashflow','ebitda')},
                provenance={'classification':'SYNTHETIC_FIXTURE'}))
    return rows


def bundle():
    row = dict(symbol='600312.SH', domain='PRICE', identity='SYNTHETIC',
        event_date='20200110', published_at=None, available_at=None, first_visible_at=None,
        retrieved_at='2026-10-08T00:00:00Z', fields={}, provenance={}, units={},
        source='SYNTHETIC',source_url='https://example.invalid/SYNTHETIC',raw_ref='SYNTHETIC_MEMORY',
        raw_sha256='a'*64,record_hash='b'*64,row_ordinal=0,license_state='UNVERIFIED')
    return evidence_bundle([row])


class RootRegressions(unittest.TestCase):
    cutoff = '2020-01-10T00:00:00.000000000Z'

    def test_nanosecond_future_financial_is_excluded(self):
        out = financial_quarters(quarters(),symbol='600312.SH',cutoff=self.cutoff)
        self.assertEqual(out['eligible_versions'],7)
        self.assertEqual(out['state'],'NOT_COMPUTABLE')
        self.assertIsNone(out['ttm'])

    def test_equal_nanosecond_boundary_is_inclusive_arithmetic_only(self):
        out = financial_quarters(quarters(self.cutoff),symbol='600312.SH',cutoff=self.cutoff)
        self.assertEqual(out['eligible_versions'],8)
        self.assertEqual(out['ttm']['revenue'],'400')
        self.assertFalse(out['historical_visibility_proven'])

    def test_nanosecond_future_payload_is_not_inspected(self):
        rows = quarters();before = financial_quarters(rows[:-1],symbol='600312.SH',cutoff=self.cutoff)
        rows[-1]['fields']={'reporting_basis':'POISON','revenue':'NaN'}
        self.assertEqual(before, financial_quarters(rows,symbol='600312.SH',cutoff=self.cutoff))

    def test_nanosecond_ordering_and_offset_equivalence(self):
        self.assertEqual(exact_clock('1970-01-01T00:00:00Z'),0)
        self.assertEqual(exact_clock('1969-12-31T23:59:59.999999999Z'),-1)
        for digits in range(1,10):
            with self.subTest(digits=digits):
                literal='2020-01-10T00:00:00.'+'0'*(digits-1)+'1Z'
                self.assertEqual(exact_clock(literal)-exact_clock(self.cutoff),10**(9-digits))
        self.assertEqual(exact_clock(self.cutoff),exact_clock('2020-01-10T08:00:00.000000000+08:00'))
        self.assertEqual(exact_clock(self.cutoff),exact_clock('2020-01-10T08:59:00+08:59'))

    def test_invalid_clock_components_fail_closed_every_consumer(self):
        for text in ('2020-01-10T00:00:00+08:60','2020-01-10T00:00:00+08:99',
                     '2020-01-10T00:00:00-00:99','2020-01-10T00:00:00+24:00',
                     '2020-01-10T00:00:00-00:00','2020-02-30T00:00:00Z',
                     '2020-01-10T24:00:00Z','2020-01-10T00:60:00Z','2020-01-10T00:00:60Z',
                     '2020-01-10T00:00:00.0000000001Z','2020-01-10T00:00:00',
                     '2020-01-10T00:00Z'):
            with self.subTest(text=text):
                for parser in (exact_clock,_clock):
                    with self.assertRaises(ValueError): parser(text)
                out=clock(text)
                self.assertEqual(out['value'],text)
                self.assertEqual(out['precision'],'UNINTERPRETED_SOURCE_LITERAL')
                self.assertIsNone(out['timezone'])

    def test_invalid_source_dates_not_valid_metadata(self):
        for text in ('2020-99-99','20200230','2019-02-29','2020-01-10TRAILING'):
            with self.subTest(text=text):
                with self.assertRaises(ValueError): source_day(text)
                self.assertEqual(clock(text)['precision'],'UNINTERPRETED_SOURCE_LITERAL')
        self.assertEqual(clock('20200229')['source_literal'],'20200229')
        self.assertEqual(clock('20200229')['value'],'2020-02-29')
        self.assertIsNone(clock('20200229')['timezone'])

    def test_exact_source_literal_survives_metadata(self):
        text='2020-01-10T08:00:00.000000001+08:00'
        self.assertEqual(clock(text)['value'],text)
        self.assertEqual(clock(text)['timezone'],'+08:00')

    def test_top_level_boolean_integer_float_cannot_exchange(self):
        self.assertTrue(validate_candidate(walk_forward_plan()))
        for field, replacements in (('productionGate',(0,0.0,None,'false')),
                                     ('formal_windows_executed',(False,0.0,'0'))):
            for replacement in replacements:
                with self.subTest(field=field,replacement=replacement):
                    value=walk_forward_plan();value[field]=replacement
                    with self.assertRaisesRegex(ValueError,'DTO_CONST'):validate_candidate(value)

    def test_nested_boolean_integer_float_cannot_exchange(self):
        self.assertTrue(validate_candidate(bundle()))
        for replacement in (0,0.0,'false',None):
            with self.subTest(replacement=replacement):
                value=bundle();value['records'][0]['formal_admitted']=replacement
                with self.assertRaises(ValueError):validate_candidate(value)

    def test_unrun_window_and_declared_empty_array_are_enforced(self):
        value=walk_forward_plan();value['windows']=[{'id':'SYNTHETIC_UNRUN'}]
        with self.assertRaisesRegex(ValueError,'DTO_ARRAY_LENGTH'):validate_candidate(value)

    def test_nested_bad_clock_metadata_rejected(self):
        for precision, literal,zone in (
                ('EXACT_SOURCE_RECORDED','2020-01-10T00:00:00+08:60','+09:00'),
                ('DATE_ONLY','2020-99-99',None),
                ('EXACT_SOURCE_RECORDED','2020-01-10T00:00:00Z','+08:00'),
                ('UNKNOWN','2020-01-10',None),('UNINTERPRETED_SOURCE_LITERAL','bad','+00:00')):
            with self.subTest(precision=precision,literal=literal):
                value=bundle();value['records'][0]['published']={'value':literal,'precision':precision,'timezone':zone}
                with self.assertRaises(ValueError):validate_candidate(value)

    def test_nested_arrays_refs_enum_and_required_checked(self):
        for mutation in ('missing','array','enum','clock','hash','labels'):
            with self.subTest(mutation=mutation):
                value=bundle()
                if mutation=='missing':value['records'][0]['source'].pop('revision_id')
                if mutation=='array':value['records']='not-array'
                if mutation=='enum':value['records'][0]['event']['precision']='EXACT_FAKE'
                if mutation=='clock':value['records'][0]['event']=[]
                if mutation=='hash':value['records'][0]['source']['record_hash']='x'
                if mutation=='labels':value['labels']=[]
                with self.assertRaises(ValueError):validate_candidate(value)

    def test_non_json_inputs_and_unsupported_schema_fail_closed(self):
        for value in ([],{'kind':'../../secret'},False,None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):validate_candidate(value)
        for item in (float('nan'),float('inf'),()):
            value=walk_forward_plan();value['extra']=item
            with self.assertRaises(ValueError):validate_candidate(value)
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_SCHEMA_KEYWORD'):
            validate(0,{'maximum':0})
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_SCHEMA_KEYWORD'):
            validate(0,{'if':{'maximum':0},'then':{'const':1}})
