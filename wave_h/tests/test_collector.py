"""Offline adversarial collector tests; fixtures can never issue actual authority."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch, Mock

from wave_h import collector as c
from wave_h.common import ARCHIVE, SYMBOLS, bindings, canonical, digest, ref, write_private


def synthetic_inputs(directory, *, observed_at='2026-10-08T07:04:59.123Z'):
    """Explicit simulation evidence, never real SourceSessionWitness/Reference A."""
    p = Path(directory)
    p.mkdir(mode=0o700, parents=True, exist_ok=True)
    witness_original = p / 'synthetic-market-observation.json'
    write_private(witness_original, canonical({'kind': 'SYNTHETIC_MARKET_OBSERVATION',
        'session': '2026-10-08', 'observation': 'SIMULATION_NOT_ACTUAL_MARKET_FACT'}))
    source_refs = []
    for symbol in SYMBOLS:
        raw = c._definitions('2026-09-30')[1 + list(SYMBOLS).index(symbol)]
        values = {'ts_code': symbol, 'trade_date': '20260930', 'open': '10', 'high': '11',
                  'low': '9', 'close': '10', 'pre_close': '10', 'change': '0',
                  'pct_chg': '0', 'vol': '100', 'amount': '100'}
        path = p / f'synthetic-A-{symbol}.json'
        write_private(path, native(raw, [values]))
        source_refs.append(ref(path))
    anchor = {'version': '1.0.0', 'kind': 'OFFLINE_SIMULATION_REFERENCE_A',
        'capture_id': 'SIMULATION_ONLY_REFERENCE_A', 'session_date': '2026-09-30',
        'retrieved_at': '2026-10-05T14:49:51.119338Z', 'observed_universe': list(SYMBOLS),
        'raw_observation_hash': digest(source_refs), 'source_policy_hash': 'sha256:' + '1' * 64,
        'rules_hash': bindings()['strategy_hash'], 'source_original_refs': source_refs,
        'source_admission': 'BLOCKED', 'historical_visibility_proven': False}
    ap = p / 'synthetic-reference-A.json'
    write_private(ap, canonical(anchor))
    witness = {'version': '1.0.0', 'kind': 'OFFLINE_SIMULATION_SESSION_WITNESS',
        'session': '2026-10-08', 'symbols': list(SYMBOLS), 'actual_session_open': True,
        'eod_observed': True, 'observed_at': observed_at,
        'precision': c._precision(observed_at), 'original_refs': [ref(witness_original)],
        'witness_source': 'SYNTHETIC_OFFLINE_MARKET_OBSERVATION_NOT_ACTUAL'}
    wp = p / 'synthetic-session-witness.json'
    write_private(wp, canonical(witness))
    plan = c.build_plan('2026-10-08', ref(wp), ref(ap))
    return plan


def native(job, rows=(), *, code=0, msg=None):
    return canonical({'code': code, 'msg': msg,
        'data': {'fields': job['fields'], 'items': [[row.get(x) for x in job['fields']] for row in rows]}})


def synthetic_responses(plan):
    responses = {}
    for job in plan['jobs']:
        api = job['api_name']
        row = {}
        if api == 'trade_cal':
            row = {'exchange': 'SSE', 'cal_date': '20261008', 'is_open': 1,
                   'pretrade_date': '20260930'}
        elif api == 'daily':
            row = {'ts_code': job['symbol'], 'trade_date': '20261008',
                   'open': '10.001', 'high': '11.123456789', 'low': '9.01',
                   'close': '10.001', 'pre_close': '10.1', 'change': '-0.099',
                   'pct_chg': '-0.98', 'vol': '100', 'amount': '100.01'}
        elif api == 'stock_basic':
            row = {'ts_code': job['symbol'], 'symbol': job['symbol'].split('.')[0],
                   'name': 'SYNTHETIC_NAME', 'exchange': 'SSE', 'curr_type': 'CNY',
                   'list_status': 'L', 'list_date': '20000101', 'delist_date': None}
        elif api == 'stk_limit':
            row = {'ts_code': job['symbol'], 'trade_date': '20261008',
                   'pre_close': '10', 'up_limit': '11', 'down_limit': '9'}
        responses[job['job_id']] = native(job, [row] if row else [])
    return responses


CLOCK = {'started_at': '2026-10-08T07:05:00.123456Z',
         'retrieved_at': '2026-10-08T07:05:01.123456Z'}


class CollectorTests(unittest.TestCase):
    def setUp(self):
        base = ARCHIVE / 'validation/collector'
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.temp = Path(tempfile.mkdtemp(prefix='offline-test-', dir=base))
        self.plan = synthetic_inputs(self.temp / 'inputs')
        self.responses = synthetic_responses(self.plan)
        self.created = []

    def tearDown(self):
        shutil.rmtree(self.temp)
        for p in self.created:
            if p.exists():
                shutil.rmtree(p)

    def output(self):
        parent = ARCHIVE / 'capture/simulation'
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        unique = Path(tempfile.mkdtemp(prefix='offline-test-output-', dir=parent))
        unique.rmdir()
        self.created.append(unique)
        return unique

    def capture(self):
        return c.simulate_capture(self.plan, self.responses, CLOCK, self.output())

    def mutate_witness(self, **changes):
        d = json.loads(Path(self.plan['session_evidence_ref']['path']).read_bytes())
        d.update(changes)
        p = self.temp / ('witness-mutant-' + str(len(list(self.temp.iterdir()))) + '.json')
        write_private(p, canonical(d))
        return ref(p)

    def test_exact_thirteen_jobs_only_three_symbols(self):
        self.assertEqual(len(self.plan['jobs']), 13)
        self.assertEqual([x['api_name'] for x in self.plan['jobs']],
                         ['trade_cal'] + ['daily'] * 3 + ['stock_basic'] * 3 +
                         ['suspend_d'] * 3 + ['stk_limit'] * 3)
        self.assertEqual([x['max_rows'] for x in self.plan['jobs'][7:10]], [8, 8, 8])
        self.assertTrue(all('token' not in c.canonical(job).decode().lower() for job in self.plan['jobs']))

    def test_extra_universe_even_resealed_rejected(self):
        p = copy.deepcopy(self.plan)
        p['symbols'].append('000001.SZ')
        p['plan_hash'] = digest({k: v for k, v in p.items() if k != 'plan_hash'})
        with self.assertRaises(ValueError):
            c.validate_plan(p)

    def test_extra_method_even_resealed_rejected(self):
        p = copy.deepcopy(self.plan)
        p['jobs'][0]['api_name'] = 'order'
        p['plan_hash'] = digest({k: v for k, v in p.items() if k != 'plan_hash'})
        with self.assertRaises(ValueError):
            c.validate_plan(p)

    def test_changed_fields_endpoint_proxy_and_retry_rejected(self):
        for field, value in [('endpoint', 'https://example.invalid/'), ('proxy', 'http://example.invalid/'),
                             ('retries', 1)]:
            p = copy.deepcopy(self.plan)
            p[field] = value
            p['plan_hash'] = digest({k: v for k, v in p.items() if k != 'plan_hash'})
            with self.assertRaises(ValueError):
                c.validate_plan(p)

    def test_calendar_plan_without_actual_eod_witness_rejected(self):
        r = self.mutate_witness(eod_observed=False)
        with self.assertRaisesRegex(ValueError, 'ACTUAL_OPEN_EOD_REQUIRED'):
            c.build_plan(self.plan['session'], r, self.plan['snapshot_a_ref'])

    def test_witness_ambiguous_date_only_and_wrong_day_rejected(self):
        for changes in ({'observed_at': '2026-10-08', 'precision': 'DATE_ONLY'},
                        {'observed_at': '2026-10-07T07:05:00Z', 'precision': 'SECOND'}):
            with self.assertRaises(ValueError):
                c.build_plan(self.plan['session'], self.mutate_witness(**changes), self.plan['snapshot_a_ref'])

    def test_witness_literal_fraction_precision_preserved(self):
        for literal in ('2026-10-08T07:04:59Z', '2026-10-08T07:04:59.1Z',
                        '2026-10-08T07:04:59.123456Z', '2026-10-08T07:04:59.123456789Z'):
            r = self.mutate_witness(observed_at=literal, precision=c._precision(literal))
            p = c.build_plan(self.plan['session'], r, self.plan['snapshot_a_ref'])
            self.assertEqual(c._witness(r, p['session'], p['mode'])['observed_at'], literal)

    def test_witness_precision_claim_conflict_rejected(self):
        with self.assertRaisesRegex(ValueError, 'PRECISION_CONFLICT'):
            c.build_plan(self.plan['session'], self.mutate_witness(precision='SECOND'), self.plan['snapshot_a_ref'])

    def test_original_mutation_invalidates_plan(self):
        r = json.loads(Path(self.plan['session_evidence_ref']['path']).read_bytes())['original_refs'][0]
        Path(r['path']).write_bytes(b'MUTATED_SYNTHETIC_ORIGINAL')
        with self.assertRaisesRegex(ValueError, 'DEPENDENCY_INVALIDATED'):
            c.validate_plan(self.plan)

    def test_anchor_retrieved_later_than_bar_date_is_current_not_pit(self):
        a = c._anchor(self.plan['snapshot_a_ref'], self.plan['session'], c.SIMULATION_MODE)
        self.assertNotEqual(c._local_day(a['retrieved_at']), a['session_date'])
        self.assertIs(a['historical_visibility_proven'], False)

    def test_anchor_late_session_rejected(self):
        with self.assertRaisesRegex(ValueError, 'A_TO_B_LINEAGE_INVALID'):
            c._anchor(self.plan['snapshot_a_ref'], '2026-09-30', c.SIMULATION_MODE)

    def test_complete_simulation_reopens_all_raw_clock_files(self):
        result = self.capture()
        reopened = c.reopen_capture(result['manifest_ref'], self.plan, allow_simulation=True)
        self.assertEqual(len(reopened['reconstructed']), 13)
        self.assertEqual(reopened['manifest']['coverage']['mandatory_daily_count'], 3)
        self.assertEqual(reopened['manifest']['actual_forward_days'], 0)
        self.assertIs(reopened['manifest']['safe_to_trade'], False)
        self.assertIsNone(reopened['manifest']['capture_authorization'])

    def test_unchanged_empty_status_raws_are_not_false_duplicate(self):
        result = self.capture()
        entries = [x for x in result['manifest']['jobs'] if x['job']['api_name'] == 'suspend_d']
        self.assertEqual(len({x['source_response_hash'] for x in entries}), 1)
        self.assertEqual(len({x['raw_ref']['path'] for x in entries}), 3)
        self.assertTrue(all(x['status'] == 'EMPTY' and x['reason_code'] for x in entries))
        self.assertTrue(all(x['state'] == 'UNKNOWN' for x in result['manifest']['status_unknowns']))

    def test_optional_permission_denial_is_explicit_not_normal(self):
        for job in self.plan['jobs']:
            if job['api_name'] == 'suspend_d':
                self.responses[job['job_id']] = native(job, code=-1, msg='permission denied')
        result = self.capture()
        entries = [x for x in result['manifest']['jobs'] if x['job']['api_name'] == 'suspend_d']
        self.assertTrue(all(x['status'] == 'API_DENIED' and x['reason_code'] == 'ENTITLEMENT_NOT_GRANTED'
                            for x in entries))
        c.reopen_capture(result['manifest_ref'], self.plan, allow_simulation=True)

    def test_missing_symbol_response_prevents_snapshot_capture(self):
        job = self.plan['jobs'][1]
        self.responses[job['job_id']] = native(job, [])
        with self.assertRaisesRegex(ValueError, 'MANDATORY_EXACT_THREE'):
            self.capture()

    def test_missing_response_job_is_not_partial_success(self):
        del self.responses[self.plan['jobs'][1]['job_id']]
        with self.assertRaisesRegex(ValueError, 'EXACT_JOB_SET'):
            self.capture()

    def test_old_date_response_rejected_even_capture_is_fresh(self):
        job = self.plan['jobs'][1]
        doc = json.loads(self.responses[job['job_id']])
        doc['data']['items'][0][doc['data']['fields'].index('trade_date')] = '20260930'
        self.responses[job['job_id']] = canonical(doc)
        with self.assertRaisesRegex(ValueError, 'STALE_SESSION'):
            self.capture()

    def test_duplicate_raw_from_other_symbol_rejected(self):
        self.responses[self.plan['jobs'][2]['job_id']] = self.responses[self.plan['jobs'][1]['job_id']]
        with self.assertRaisesRegex(ValueError, 'SYMBOL_DRIFT'):
            self.capture()

    def test_calendar_is_open_conflict_rejected(self):
        j = self.plan['jobs'][0]
        self.responses[j['job_id']] = native(j, [{'exchange': 'SSE', 'cal_date': '20261008',
                                                'is_open': 0, 'pretrade_date': '20260930'}])
        with self.assertRaisesRegex(ValueError, 'CALENDAR_SESSION_CONFLICT'):
            self.capture()

    def test_duplicate_json_key_and_nonfinite_rejected(self):
        for raw in (b'{"code":0,"code":1,"msg":null,"data":null}',
                    b'{"code":0,"msg":null,"data":NaN}'):
            with self.assertRaises(ValueError):
                c.parse_native(self.plan['jobs'][0], raw, self.plan['session'])

    def test_native_schema_row_cap_and_ohlc_have_independent_oracles(self):
        job = self.plan['jobs'][1]
        original = json.loads(self.responses[job['job_id']])
        mutations = []
        a = copy.deepcopy(original); a['data']['fields'].append('future_label'); mutations.append(a)
        a = copy.deepcopy(original); a['data']['items'].append(a['data']['items'][0]); mutations.append(a)
        a = copy.deepcopy(original); a['data']['items'][0][a['data']['fields'].index('high')] = '8'; mutations.append(a)
        for doc in mutations:
            with self.assertRaises(ValueError):
                c.parse_native(job, canonical(doc), self.plan['session'])

    def test_decimal_native_literal_not_binary_float_rounding(self):
        job = self.plan['jobs'][1]
        raw = self.responses[job['job_id']].replace(b'"10.001"', b'10.001')
        parsed = c.parse_native(job, raw, self.plan['session'])
        self.assertEqual(parsed['rows'][0]['close'], '10.001')
        self.assertEqual(parsed['rows'][0]['high'], '11.123456789')

    def test_clock_unknown_source_date_only_event_current_visibility(self):
        result = self.capture()
        clock = json.loads(Path(result['manifest']['jobs'][1]['clock_ref']['path']).read_bytes())
        self.assertEqual(clock['event_precision'], 'DATE_ONLY')
        self.assertIsNone(clock['published_at'])
        self.assertIsNone(clock['source_available_at'])
        self.assertEqual(clock['current_available_at'], CLOCK['retrieved_at'])
        self.assertEqual(clock['current_available_precision'], 'MICROSECOND')
        self.assertIs(clock['historical_visibility_proven'], False)

    def test_capture_clock_before_witness_or_different_day_rejected(self):
        for clock in ({'started_at': '2026-10-08T07:04:58Z', 'retrieved_at': '2026-10-08T07:05:01Z'},
                      {'started_at': '2026-10-07T07:05:00Z', 'retrieved_at': '2026-10-07T07:05:01Z'}):
            with self.assertRaises(ValueError):
                c.simulate_capture(self.plan, self.responses, clock, self.output())

    def test_raw_changed_after_capture_cannot_be_reviewed(self):
        result = self.capture()
        p = Path(result['manifest']['jobs'][1]['raw_ref']['path'])
        p.write_bytes(p.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'DEPENDENCY_INVALIDATED'):
            c.reopen_capture(result['manifest_ref'], self.plan, allow_simulation=True)

    def test_safe_native_value_failure_retains_quarantine_originals_no_manifest(self):
        job = self.plan['jobs'][1]
        doc = json.loads(self.responses[job['job_id']])
        doc['data']['items'][0][doc['data']['fields'].index('high')] = '8'
        received = canonical(doc)
        self.responses[job['job_id']] = received
        out = self.output()
        with self.assertRaisesRegex(ValueError, '^WH_CAPTURE_OHLC_INCONSISTENT$'):
            c.simulate_capture(self.plan, self.responses, CLOCK, out)
        self.assertEqual((out / (job['job_id'] + '.raw.json')).read_bytes(), received)
        clock = json.loads((out / (job['job_id'] + '.clock.json')).read_bytes())
        self.assertEqual(clock['retrieved_at'], CLOCK['retrieved_at'])
        self.assertEqual(clock['retrieved_precision'], 'MICROSECOND')
        failure = json.loads((out / 'failure.json').read_bytes())
        self.assertEqual(failure['kind'], 'OFFLINE_SIMULATION_CAPTURE_FAILED')
        self.assertEqual(failure['completed_job_count'], 1)
        self.assertEqual(len(failure['quarantined_safe_response_originals']), 2)
        self.assertEqual(failure['actual_forward_days'], 0)
        self.assertIs(failure['safe_to_trade'], False)
        self.assertIs(failure['positive_capture_manifest_issued'], False)
        self.assertFalse((out / 'capture-manifest.json').exists())

    def test_safe_native_schema_failure_retains_exact_received_body(self):
        job = self.plan['jobs'][1]
        doc = json.loads(self.responses[job['job_id']])
        index = doc['data']['fields'].index('close')
        del doc['data']['fields'][index]
        del doc['data']['items'][0][index]
        received = canonical(doc)
        self.responses[job['job_id']] = received
        out = self.output()
        with self.assertRaisesRegex(ValueError, '^WH_CAPTURE_NATIVE_FIELDS_DRIFT$'):
            c.simulate_capture(self.plan, self.responses, CLOCK, out)
        self.assertEqual((out / (job['job_id'] + '.raw.json')).read_bytes(), received)
        self.assertTrue((out / (job['job_id'] + '.clock.json')).exists())
        self.assertFalse((out / 'capture-manifest.json').exists())

    def test_invalid_json_cannot_be_hashed_or_archived_as_safe_response(self):
        out = self.output()
        c._capture_dir(out, c.SIMULATION_MODE)
        with patch.object(c, 'sha', side_effect=AssertionError('hash forbidden')), \
             patch.object(c, 'write_private', side_effect=AssertionError('body archive forbidden')):
            with self.assertRaisesRegex(ValueError, '^WH_CAPTURE_JSON_INVALID$'):
                c._archive_returned_safe_response(self.plan, self.plan['jobs'][1],
                    'sim:INVALID_JSON_NO_CAPTURE', b'{"code":0,"data":',
                    CLOCK['started_at'], CLOCK['retrieved_at'], c.SIMULATION_MODE, out)
        self.assertEqual(list(out.iterdir()), [])

    def test_secret_echo_cannot_be_archived_by_safe_response_helper(self):
        module = c._source_module()
        secret = 'SYNTHETIC_MEMORY_ONLY_' + 'v' * 32
        credential = module.Credential(secret)
        out = self.output()
        c._capture_dir(out, c.SIMULATION_MODE)
        body = canonical({'code': -1, 'msg': secret, 'data': None})
        with patch.object(c, 'sha', side_effect=AssertionError('secret hash forbidden')), \
             patch.object(c, 'write_private', side_effect=AssertionError('secret archive forbidden')):
            with self.assertRaisesRegex(ValueError, '^WH_CAPTURE_SECRET_ECHO_DISCARDED$'):
                c._archive_returned_safe_response(self.plan, self.plan['jobs'][1],
                    'sim:SECRET_ECHO_NO_CAPTURE', body, CLOCK['started_at'],
                    CLOCK['retrieved_at'], c.SIMULATION_MODE, out, credential)
        self.assertEqual(list(out.iterdir()), [])

    def test_returned_clock_conflict_retains_literal_quarantine_not_acceptance(self):
        out = self.output()
        c._capture_dir(out, c.SIMULATION_MODE)
        job = self.plan['jobs'][1]
        raw = self.responses[job['job_id']]
        conflicting_completion = '2026-10-09T00:00:00.654321Z'
        original = c._archive_returned_safe_response(self.plan, job,
            'sim:CLOCK_CONFLICT_NO_CAPTURE', raw, CLOCK['started_at'],
            conflicting_completion, c.SIMULATION_MODE, out)
        clock = json.loads(Path(original['clock_ref']['path']).read_bytes())
        self.assertEqual(clock['retrieved_at'], conflicting_completion)
        self.assertEqual(Path(original['raw_ref']['path']).read_bytes(), raw)
        with self.assertRaisesRegex(ValueError, '^WH_CAPTURE_CLOCK_SESSION_CONFLICT$'):
            c.validate_clock(clock, self.plan, job, 'sim:CLOCK_CONFLICT_NO_CAPTURE',
                             raw, c.SIMULATION_MODE)
        self.assertFalse((out / 'capture-manifest.json').exists())

    def test_clock_changed_after_capture_cannot_be_reviewed(self):
        result = self.capture()
        p = Path(result['manifest']['jobs'][1]['clock_ref']['path'])
        p.write_bytes(p.read_bytes() + b' ')
        with self.assertRaisesRegex(ValueError, 'DEPENDENCY_INVALIDATED'):
            c.reopen_capture(result['manifest_ref'], self.plan, allow_simulation=True)

    def test_simulation_cannot_reopen_as_actual(self):
        result = self.capture()
        with self.assertRaisesRegex(ValueError, 'PLAN_MODE_INVALID'):
            c.reopen_capture(result['manifest_ref'], self.plan)

    def test_actual_calls_reject_before_any_path_or_credential_io(self):
        for fake in (None, {'issuer': 'HUMAN_USER'}, {'issuer': 'LLM'}, self.plan):
            with patch.object(c, 'validate_plan', side_effect=AssertionError('path IO')), \
                 patch.object(c, '_lookup_named_credential', side_effect=AssertionError('secret IO')), \
                 patch.object(c, '_fetch_native', side_effect=AssertionError('network IO')):
                with self.assertRaises(ValueError):
                    c.execute_capture(self.plan, fake)

    def test_same_output_exclusive_restart_does_not_rewrite(self):
        p = self.output()
        c.simulate_capture(self.plan, self.responses, CLOCK, p)
        before = (p / 'capture-manifest.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'EXCLUSIVE_OUTPUT_REQUIRED'):
            c.simulate_capture(self.plan, self.responses, CLOCK, p)
        self.assertEqual((p / 'capture-manifest.json').read_bytes(), before)

    def test_private_raw_file_modes_and_separate_schema_version(self):
        r = self.capture()
        self.assertEqual(r['manifest']['source_schema_version'], 'TUSHARE_NATIVE_EOD_REQUEST_FIELDS_V1')
        for entry in r['manifest']['jobs']:
            self.assertEqual(Path(entry['raw_ref']['path']).stat().st_mode & 0o777, 0o600)
            self.assertEqual(Path(entry['clock_ref']['path']).stat().st_mode & 0o777, 0o600)
            self.assertNotEqual(entry['source_response_hash'], r['manifest']['source_schema_version'])

    def test_secret_echo_discarded_before_hash_or_archive(self):
        module = c._source_module()
        secret = 'SYNTHETIC_MEMORY_ONLY_' + 'x' * 32
        credential = module.Credential(secret)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.geturl.return_value = c.ENDPOINT
        response.status = 200
        response.read.return_value = canonical({'code': -1, 'msg': secret, 'data': None})
        opener = Mock(); opener.open.return_value = response
        with patch.object(c.urllib.request, 'build_opener', return_value=opener), \
             patch.object(c, 'sha', side_effect=AssertionError('secret hashing forbidden')), \
             patch.object(c, 'write_private', side_effect=AssertionError('secret persistence forbidden')):
            with self.assertRaisesRegex(ValueError, 'SECRET_ECHO_DISCARDED'):
                c._fetch_native(self.plan['jobs'][0], credential)

    def test_fixed_wire_uses_no_environment_proxy_one_attempt(self):
        module = c._source_module()
        credential = module.Credential('SYNTHETIC_MEMORY_ONLY_' + 'y' * 32)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.geturl.return_value = c.ENDPOINT
        response.status = 200
        response.read.return_value = self.responses[self.plan['jobs'][0]['job_id']]
        opener = Mock(); opener.open.return_value = response
        with patch.object(c.urllib.request, 'build_opener', return_value=opener) as factory:
            raw = c._fetch_native(self.plan['jobs'][0], credential)
        self.assertEqual(raw, response.read.return_value)
        handlers = factory.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], c._NoRedirect)
        self.assertEqual(opener.open.call_count, 1)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, c.ENDPOINT)
        self.assertEqual(request.get_method(), 'POST')
        self.assertNotIn('?', request.full_url)
        self.assertEqual(json.loads(request.data)['params']['exchange'], 'SSE')

    def test_wire_failure_has_no_fallback_or_retry(self):
        module = c._source_module()
        credential = module.Credential('SYNTHETIC_MEMORY_ONLY_' + 'z' * 32)
        opener = Mock(); opener.open.side_effect = RuntimeError('UNTRUSTED_PROVIDER_MESSAGE_NOT_LOGGED')
        with patch.object(c.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaisesRegex(ValueError, '^WH_CAPTURE_TRANSPORT_FAILED_NO_RETRY$'):
                c._fetch_native(self.plan['jobs'][0], credential)
        self.assertEqual(opener.open.call_count, 1)

    def test_consumed_claim_is_flushed_and_exclusive_after_restart(self):
        path = self.temp / 'synthetic-only-consumed-claim.json'
        body = {'kind': 'OFFLINE_SIMULATION_REQUEST_CLAIM', 'no_retry': True,
                'actual_forward_days': 0}
        original_fsync = c.os.fsync
        with patch.object(c.os, 'fsync', wraps=original_fsync) as flush:
            c._write_claim(path, body)
        self.assertEqual(flush.call_count, 2)
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            c._write_claim(path, body)
        self.assertEqual(path.read_bytes(), before)

    def test_fixed_transport_rejects_redirect_and_has_no_injected_callback(self):
        with self.assertRaisesRegex(ValueError, 'REDIRECT_REJECTED'):
            c._NoRedirect().redirect_request(None, None, 301, None, None, 'https://example.invalid/')
        with self.assertRaises(TypeError):
            c.execute_capture(self.plan, None, transport=lambda _: None)
        with self.assertRaises(TypeError):
            c.execute_capture(self.plan, None, proxy='http://example.invalid/')

    def test_native_broker_and_cloud_paths_always_forbidden(self):
        for function in (c.issue_order, c.cloud_export):
            for fake in ({'issuer': 'HUMAN_USER'}, {'issuer': 'LLM'}, {'approved': True}):
                with self.assertRaises(ValueError):
                    function(fake)

    def test_readiness_is_not_actual_result_or_license(self):
        r = c.readiness()
        self.assertEqual(r['body']['implementation'], 'READY_FOR_ONE_SHOT_OWNER_AUTH')
        self.assertEqual(r['body']['authenticated_requests_in_H_A'], 0)
        self.assertEqual(r['actual_forward_days'], 0)
        self.assertIs(r['productionGate'], False)


if __name__ == '__main__':
    unittest.main()
