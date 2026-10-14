"""Fixed V3 gateway artifact projection: no collection, credential lookup or repair."""
from pathlib import Path
import json
import re

ARCHIVE = Path('/Users/qiushi/投资研究/.p1b-archives/e2e-gateway-v3-20261014')
KEY = 'gateway-registry'
CODE_PATHS = (
    'tools/e2e_gateway/run.py', 'tools/e2e_gateway/builder.py', 'tools/e2e_gateway/capture.py',
    'experiments/e2e_gateway_v3/input-policy.json', 'docs/e2e-gateway-v3/Source-Policy.json',
    'docs/e2e-gateway-v3/Owner-Authorization.md', 'config/provider/tushare-monthly-gateway.json',
    'tushare-real-admission/probe.py', 'tushare-admission/probe.py',
    'experiments/e2e_history_v2/engine.py', 'experiments/e2e_history_v2/protocol.json',
    'experiments/e2e_pilot_v1/method.json', 'experiments/e2e_pilot_v1/execution.py',
    'backtest_5y/gateway.py', 'backtest_5y/economics.py', 'wave_f/backtest.py')
API_NAMES = {'trade_cal', 'stock_basic', 'daily', 'stk_limit', 'suspend_d', 'adj_factor', 'dividend', 'namechange'}
API_STATES = {'SUCCESS', 'EMPTY_RESPONSE', 'IP_CONCURRENCY_LIMIT', 'ENTITLEMENT_NOT_GRANTED', 'API_ERROR', 'REQUEST_FAILED', 'NOT_CALLED'}


def load(reader, archive=ARCHIVE):
    """Archive override is solely an internal synthetic-test dependency injection."""
    from workbench.server import ReadError, digest
    registry, source = reader.json(KEY, 'E2EGatewayRegistry')
    pins = registry.get('code_pins')
    if not isinstance(pins, dict) or set(pins) != set(CODE_PATHS):
        raise ReadError('GATEWAY_CODE_SCOPE', KEY)
    for relative, expected in pins.items():
        raw, _ = reader.read_path(reader.root / relative, reader.root)
        if digest(raw) != expected: raise ReadError('GATEWAY_CODE_PIN_MISMATCH', relative)
    value = registry.get('run_directory')
    if not isinstance(value, str): raise ReadError('GATEWAY_RUN_SCOPE', KEY)
    directory = Path(value)
    if (directory.parent != archive / 'runs'
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}', directory.name)):
        raise ReadError('GATEWAY_RUN_SCOPE', KEY)
    if directory.resolve() != directory or directory.is_symlink(): raise ReadError('UNSAFE_PATH', directory.name)
    raw, text = reader.read_path(directory / 'Run.json', archive)
    if digest(raw) != registry.get('run_sha256'): raise ReadError('GATEWAY_RUN_PIN_MISMATCH', KEY)
    try: run = json.loads(text)
    except ValueError: raise ReadError('INVALID_JSON', 'Run.json')
    if (not isinstance(run, dict) or run.get('kind') != 'HistoricalGatewayDiagnosticRun'
            or run.get('version') != '3.0.0' or run.get('run_id') != directory.name
            or run.get('code_pins') != pins or type(run.get('engine_called')) is not bool):
        raise ReadError('GATEWAY_RUN_BINDING', KEY)
    if (run.get('evidence_grade') != 'RECONSTRUCTED_HISTORY_DIAGNOSTIC'
            or run.get('historical_visibility_proven') is not False
            or run.get('production_enabled') is not False
            or run.get('source_epoch') != 'COMPATIBLE_GATEWAY_V3'):
        raise ReadError('GATEWAY_BOUNDARY_MISMATCH', KEY)
    for field, relative in (
        ('protocol_hash', 'experiments/e2e_history_v2/protocol.json'),
        ('input_policy_hash', 'experiments/e2e_gateway_v3/input-policy.json'),
        ('source_policy_hash', 'docs/e2e-gateway-v3/Source-Policy.json')):
        if run.get(field) != pins[relative]: raise ReadError('GATEWAY_POLICY_BINDING', KEY)
    capture = run.get('capture_dir')
    if not isinstance(capture, str): raise ReadError('GATEWAY_CAPTURE_SCOPE', KEY)
    folder = Path(capture)
    if folder.parent != archive or not re.fullmatch(r'capture-[A-Za-z0-9._-]+', folder.name):
        raise ReadError('GATEWAY_CAPTURE_SCOPE', KEY)
    if folder.resolve() != folder or folder.is_symlink(): raise ReadError('UNSAFE_PATH', folder.name)
    try:
        from tools.e2e_gateway.run import verify_existing
        checked = verify_existing(directory)
    except ImportError: raise ReadError('GATEWAY_VERIFIER_UNAVAILABLE', KEY)
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError):
        raise ReadError('GATEWAY_RECOMPUTATION_FAILED', KEY)
    if not isinstance(checked, dict) or checked.get('run') != run:
        raise ReadError('GATEWAY_VERIFIER_RUN_MISMATCH', KEY)
    report, diagnostic, matrix = checked.get('build_report'), checked.get('engine_result'), checked.get('api_matrix')
    if not isinstance(report, dict): raise ReadError('GATEWAY_BUILD_REPORT_MISSING', KEY)
    if run['engine_called'] is True and not isinstance(diagnostic, dict):
        raise ReadError('GATEWAY_ENGINE_STATE_CONFLICT', KEY)
    # Engine preflight rejection can produce a legitimate blocked result without
    # invoking the execution loop. Do not confuse that with successful no-trades.
    if diagnostic is not None and (not isinstance(diagnostic, dict)
            or diagnostic.get('engine_called') is not run['engine_called']
            or diagnostic.get('status') != run.get('status')):
        raise ReadError('GATEWAY_ENGINE_STATE_CONFLICT', KEY)
    if not isinstance(matrix, list): raise ReadError('GATEWAY_API_MATRIX_MISSING', KEY)
    projected, identities = [], set()
    for row in matrix:
        if (not isinstance(row, dict) or row.get('api_name') not in API_NAMES
                or row.get('state') not in API_STATES or not isinstance(row.get('params'), dict)
                or any(key not in {'ts_code', 'exchange', 'start_date', 'end_date'} for key in row['params'])):
            raise ReadError('GATEWAY_API_MATRIX_INVALID', KEY)
        identity = (row['api_name'], json.dumps(row['params'], sort_keys=True))
        if identity in identities: raise ReadError('GATEWAY_API_MATRIX_DUPLICATE', KEY)
        identities.add(identity)
        count = row.get('row_count')
        if row['state'] == 'NOT_CALLED':
            if count is not None: raise ReadError('GATEWAY_API_MATRIX_INVALID', KEY)
        elif type(count) is not int or count < 0: raise ReadError('GATEWAY_API_MATRIX_INVALID', KEY)
        projected.append({key: row.get(key) for key in (
            'api_name', 'params', 'row_count', 'state', 'error_code', 'retrieved_at',
            'min_date', 'max_date', 'raw_sha256')})
    fields = ('kind', 'version', 'run_id', 'recorded_at', 'status', 'errors', 'field_coverage',
              'real_input_rows', 'market_sessions', 'target_sessions', 'action_inventory',
              'limitations', 'historical_visibility_proven')
    return {'status': 'VERIFIED', 'run': run,
            'build_report': {key: report[key] for key in fields if key in report},
            'diagnostic': diagnostic, 'api_matrix': projected, 'source': source,
            'integrity': 'FIXED_GATEWAY_CAPTURE_PINS_AND_RECOMPUTATION_MATCH'}
