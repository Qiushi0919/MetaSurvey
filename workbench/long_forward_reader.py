"""Read-only Long/Forward projection. No prepare, settle, capture or credential calls."""
from pathlib import Path
import re
import subprocess

KEY = 'long-forward-registry'
MINIMUM_CODE_PATHS = frozenset({
    'tools/long_forward/' + name + '.py' for name in ('builder', 'reporting', 'run', 'forward', 'capture')
} | {'experiments/long_forward_v1/engine.py'})
PROTOCOL = 'experiments/long_forward_v1/protocol.json'
REUSED_PATHS = frozenset({
    'experiments/e2e_pilot_v1/execution.py', 'experiments/e2e_pilot_v1/method.json',
    'backtest_5y/economics.py', 'backtest_5y/gateway.py', 'wave_f/backtest.py',
    'backtest_5y/interface.py',
    'tools/e2e_gateway/builder.py', 'tools/e2e_gateway/capture.py',
    'experiments/e2e_gateway_v3/input-policy.json', 'experiments/e2e_history_v2/engine.py',
    'config/provider/tushare-monthly-gateway.json',
    'tushare-real-admission/probe.py', 'tushare-admission/probe.py',
    'tools/v3_review/performance.py', 'tools/v3_review/benchmarks.py',
    'post_wave_e/common.py', 'overnight/analysis/inputs.py', 'wave_f/common.py', 'backtest_5y/interface.py',
    'docs/long-forward/Source-Policy.json', 'docs/long-forward/Authorization.md',
})
HASH = re.compile(r'sha256:[0-9a-f]{64}')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}')


def _pin_path(value):
    if not isinstance(value, str): return False
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or str(path) != value: return False
    return value in REUSED_PATHS or (
        path.suffix in {'.py', '.json'} and len(path.parts) == 3
        and '/'.join(path.parts[:2]) in {'tools/long_forward', 'experiments/long_forward_v1'})


def load(reader):
    from workbench.server import ReadError, digest
    registry, source = reader.json(KEY, 'LongForwardRegistry')
    archive = reader.root.parent / '.p1b-archives/long-forward-20261015'
    if registry.get('status') != 'LOCAL_ONLY' or registry.get('archive_root') != str(archive):
        raise ReadError('LONG_FORWARD_BOUNDARY_MISMATCH', KEY)
    if archive.resolve() != archive or archive.is_symlink():
        raise ReadError('UNSAFE_PATH', 'long-forward-20261015')
    pins = registry.get('code_pins')
    if (not isinstance(pins, dict) or not MINIMUM_CODE_PATHS.issubset(pins)
            or any(not _pin_path(p) or not isinstance(h, str) or not HASH.fullmatch(h) for p, h in pins.items())):
        raise ReadError('LONG_FORWARD_CODE_SCOPE', KEY)
    for path, expected in pins.items():
        raw, _ = reader.read_path(reader.root / path, reader.root)
        if digest(raw) != expected: raise ReadError('LONG_FORWARD_CODE_PIN_MISMATCH', path)
    raw, _ = reader.read_path(reader.root / PROTOCOL, reader.root)
    if digest(raw) != registry.get('protocol_ref'):
        raise ReadError('LONG_FORWARD_PROTOCOL_MISMATCH', PROTOCOL)
    for field, prefix in (('history_run', 'runs'), ('forward_state', 'forward')):
        value = registry.get(field)
        if value is None: continue
        if (not isinstance(value, str) or len(Path(value).parts) != 2
                or Path(value).parts[0] != prefix or not NAME.fullmatch(Path(value).name)):
            raise ReadError('LONG_FORWARD_ARTIFACT_SCOPE', field)
        target = archive / value
        if target.resolve() != target or target.is_symlink(): raise ReadError('UNSAFE_PATH', field)
    try:
        from tools.long_forward.reporting import verify_dashboard
        checked = verify_dashboard(registry)
    except ImportError: raise ReadError('LONG_FORWARD_VERIFIER_UNAVAILABLE', KEY)
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError,
            subprocess.TimeoutExpired, subprocess.CalledProcessError):
        raise ReadError('LONG_FORWARD_INTEGRITY_ERROR', KEY) from None
    if not isinstance(checked, dict) or checked.get('status') != 'VERIFIED':
        raise ReadError('LONG_FORWARD_INTEGRITY_ERROR', KEY)
    history, forward = checked.get('history'), checked.get('forward')
    if history is not None and (not isinstance(history, dict) or type(history.get('engine_called')) is not bool):
        raise ReadError('LONG_FORWARD_HISTORY_SHAPE', KEY)
    if forward is not None and (not isinstance(forward, dict) or not isinstance(forward.get('strategy_a'), dict)
            or not isinstance(forward.get('strategy_b'), dict)):
        raise ReadError('LONG_FORWARD_FORWARD_SHAPE', KEY)
    # No Case, raw bars, credential/config body or arbitrary verifier key is exposed.
    history_fields = ('run_id', 'status', 'engine_called', 'window', 'overall', 'yearly', 'controls', 'exposure', 'errors')
    a_fields = ('status', 'activation', 'plan', 'settlements', 'next_execution', 'observed_sessions', 'errors')
    b_fields = ('status', 'module', 'reason')
    return {'status': 'VERIFIED',
            'history': None if history is None else {k: history[k] for k in history_fields if k in history},
            'forward': None if forward is None else {
                'strategy_a': {k: forward['strategy_a'][k] for k in a_fields if k in forward['strategy_a']},
                'strategy_b': {k: forward['strategy_b'][k] for k in b_fields if k in forward['strategy_b']}},
            'integrity': checked.get('integrity'), 'source': source}
