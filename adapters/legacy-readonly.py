"""Read saved V5 artifacts; output JSON only, no old entrypoints or model/broker calls."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def forbid_mutation(event, args):
    if event == 'open':
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        if isinstance(mode, str) and any(letter in mode for letter in 'wax+'):
            raise PermissionError('LEGACY_READ_ONLY_FILE_WRITE_BLOCKED')
        if isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise PermissionError('LEGACY_READ_ONLY_FILE_WRITE_BLOCKED')
    if event in {
        'os.remove', 'os.rename', 'os.rmdir', 'os.mkdir', 'os.link', 'os.symlink',
        'os.chmod', 'os.chown', 'os.truncate', 'os.utime', 'os.system', 'subprocess.Popen',
    } or event.startswith('socket.'):
        raise PermissionError('LEGACY_READ_ONLY_MUTATION_OR_NETWORK_BLOCKED:' + event)


# -B plus the audit hook guard dependencies as well as the adapter itself.
sys.dont_write_bytecode = True
sys.addaudithook(forbid_mutation)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contained(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('LEGACY_PATH_ESCAPE')
    result = (root / path).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError('LEGACY_PATH_ESCAPE')
    return result


def bindings(root):
    import isolation_audit as original
    from hv import digest
    from relocation import archive_path
    seal_path = root / 'runs/isolation-contract-native-v2.json'
    seal = read(seal_path)
    probe = archive_path(seal['probe_run']).resolve()
    invocation = read(probe / 'invocation.json')
    traces = list((probe / 'trace').iterdir())
    if len(traces) != 1:
        raise ValueError('LEGACY_PROBE_TRACE_COUNT')
    trace = traces[0]
    events = [json.loads(line) for line in (trace / 'trace.jsonl').read_text().splitlines()]
    first = next(event for event in events if event['payload']['type'] == 'inference_started')
    reference = first['payload']['request_payload']['path']
    request = read(contained(trace, reference))
    items = request['input']
    actual = {
        'tool_schema_sha256': digest(items[0]['tools']),
        'builtin_sha256': digest(original.text_of(items[1])),
        'static_context_sha256': digest(original.text_of(items[2])),
        'environment_template_sha256': digest(original.normalized(original.text_of(items[3])[0], probe)),
        'command_sha256': original.command_contract(invocation, probe),
        'cli_sha256': sha(Path(invocation['args'][0]).resolve()),
    }
    fields = {
        key: {'expected': value, 'observed': actual.get(key), 'matches': value == actual.get(key)}
        for key, value in seal['binding'].items()
    }
    differences = [key for key, value in fields.items() if not value['matches']]
    # Run the unchanged original verifier. Do not pass a substituted baseline or create a new seal.
    try:
        original.verify_contract(seal_path)
        native_status = 'PASS'
        error = None
    except Exception as failure:
        native_status = 'FAIL'
        error = str(failure)
    known = differences == ['cli_sha256'] and error == 'PINNED_CONTEXT_OR_CLI_CHANGED'
    return {
        'status': native_status,
        'known_issue': 'LEGACY_CODEX_CLI_HASH_MISMATCH' if known else None,
        'original_verifier_error': error,
        'binding_fields': fields,
        'mismatching_fields': differences,
        'seal_modified': False,
        'repaired': False,
        'scope': 'Original native seal compatibility; raw-derived bindings are diagnostics only, not a substitute PASS.',
    }


def replay(root, fixture, workspace):
    from hv import digest
    from swing40_engine_v5 import Engine
    from swing40_reconcile_v5 import reconcile
    config = read(contained(workspace, fixture['source_run']) / 'config.json')
    calendar = read(root / 'trading_calendar.json')
    engine = Engine(calendar, config['dates'][0], config['rules_hash'])
    results = []
    for expected in fixture['days']:
        frozen_path = contained(workspace, expected['source_paths']['frozen'])
        result_path = contained(workspace, expected['source_paths']['result'])
        if sha(frozen_path) != expected['frozen_file_sha256'] or sha(result_path) != expected['result_sha256']:
            raise ValueError('LEGACY_REPLAY_SOURCE_HASH_CHANGED')
        frozen, saved = read(frozen_path), read(result_path)
        if frozen['hash'] != expected['frozen_hash'] or digest(frozen['decision']) != expected['decision_sha256']:
            raise ValueError('LEGACY_DECISION_HASH_CHANGED')
        before_count = len(engine.rows)
        snapshot = engine.step(frozen, saved['bars'], config['dates'][-1], saved.get('actions', ()))
        if snapshot != saved['snapshot'] or snapshot != expected['snapshot']:
            raise ValueError('LEGACY_REPLAY_SNAPSHOT_MISMATCH:' + expected['day'])
        new_rows = engine.rows[before_count:]
        if new_rows != saved['rows'] or new_rows != expected['rows']:
            raise ValueError('LEGACY_REPLAY_ROWS_MISMATCH:' + expected['day'])
        audited = reconcile(engine.rows, snapshot)
        if audited != saved['reconciliation'] or audited != expected['saved_reconciliation']:
            raise ValueError('LEGACY_REPLAY_RECONCILIATION_MISMATCH:' + expected['day'])
        results.append({'day': expected['day'], 'cash_cents': str(snapshot['cash_cents']), 'nav_cents': str(snapshot['nav_cents']), 'daily_rows_match': True, 'snapshot_matches': True, 'independent_legacy_reconcile_matches': True})
    trades = [row for row in engine.rows if row['type'] == 'TRADE']
    fees = sum(sum(row['fees'].values()) for row in trades)
    expected = fixture['expected']
    if (len(results), len(trades), str(engine.cash), str(engine.snapshots[-1]['nav_cents']), str(fees), engine.positions) != (
        expected['completed_days'], expected['trade_rows'], expected['final_cash_cents'], expected['final_nav_cents'], expected['fees_cents'], expected['open_positions'],
    ):
        raise ValueError('LEGACY_REPLAY_FINAL_MISMATCH')
    return {
        'status': 'PASS', 'completed_days': len(results), 'trade_rows': len(trades),
        'final_cash_cents': str(engine.cash), 'final_nav_cents': str(engine.snapshots[-1]['nav_cents']),
        'fees_cents': str(fees), 'provenance': 'LEGACY_FIXTURE_NOT_PRODUCTION',
        'engine': 'UNCHANGED_EXTERNAL_V5_ENGINE', 'reconcile': 'UNCHANGED_EXTERNAL_V5_RECONCILE',
        'read_only_guard': 'PYTHON_AUDIT_HOOK_NO_WRITES_NETWORK_OR_SUBPROCESSES', 'days': results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace-root', required=True)
    parser.add_argument('--mode', choices=['bindings', 'replay'], required=True)
    parser.add_argument('--fixture', required=True)
    args = parser.parse_args()
    workspace = Path(args.workspace_root).resolve()
    root = contained(workspace, '模拟交易实验/historical-validation-100d')
    sys.path.insert(0, str(root))
    fixture = read(Path(args.fixture))
    result = {'compatibility': bindings(root)}
    if args.mode == 'replay':
        result['replay'] = replay(root, fixture, workspace)
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    main()
