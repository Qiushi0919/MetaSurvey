"""Read-only V2 history and current-research projection; no collection or execution.

The verifier reruns deterministic validation/math over already recorded inputs.
It never creates a Case, refreshes a source, grants authority or repairs a seal.
"""
from pathlib import Path
import hashlib
import json
import re

ARCHIVE = Path('/Users/qiushi/投资研究/.p1b-archives/e2e-history-v2-20261014')
OLD_DATA = Path('/Users/qiushi/投资研究/.p1b-archives/e2e-pilot-v1-20261014/data')
KEY = 'history-registry'
CODE_PATHS = tuple('tools/e2e_history/' + name + '.py' for name in ('run', 'builder', 'capture')) + (
    'experiments/e2e_history_v2/engine.py', 'experiments/e2e_history_v2/protocol.json',
    'experiments/e2e_history_v2/input-policy.json', 'docs/e2e-history-v2/Source-Policy.json',
    'experiments/e2e_pilot_v1/method.json', 'experiments/e2e_pilot_v1/execution.py',
    'backtest_5y/economics.py', 'wave_f/backtest.py')
RESEARCH_CODE = 'tools/e2e_history/research_factors.py'
RESEARCH_METHOD = 'experiments/e2e_history_v2/research-method.json'
SYMBOLS = ('603228', '002463', '002916', '600312', '601179', '002028', '603993', '601899', '600362')


def load(reader, archive=ARCHIVE, old_data=OLD_DATA):
    """Archive overrides are internal temporary-test injection, never HTTP input."""
    from workbench.server import ReadError, digest
    registry, source = reader.json(KEY, 'E2EHistoryRegistry')
    pins = registry.get('code_pins')
    if not isinstance(pins, dict) or set(pins) != set(CODE_PATHS):
        raise ReadError('HISTORY_CODE_SCOPE', KEY)

    def safe(path, base):
        if not path.is_relative_to(base) or path.resolve() != path or path.is_symlink():
            raise ReadError('UNSAFE_PATH', path.name)

    def pinned(path, base, expected):
        raw, text = reader.read_path(path, base)
        if digest(raw) != expected: raise ReadError('HISTORY_PIN_MISMATCH', path.name)
        return raw, text

    def parsed(text, name):
        try: return json.loads(text)
        except ValueError: raise ReadError('INVALID_JSON', name)

    for relative, expected in pins.items():
        pinned(reader.root / relative, reader.root, expected)
    value = registry.get('run_directory')
    if not isinstance(value, str): raise ReadError('HISTORY_RUN_SCOPE', KEY)
    directory = Path(value)
    if directory.parent != archive / 'runs' or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}', directory.name):
        raise ReadError('HISTORY_RUN_SCOPE', KEY)
    safe(directory, archive)
    _, text = pinned(directory / 'Run.json', archive, registry.get('run_sha256'))
    run = parsed(text, 'Run.json')
    if (not isinstance(run, dict) or run.get('kind') != 'HistoricalDiagnosticRun'
            or run.get('version') != '2.0.0' or run.get('run_id') != directory.name
            or run.get('code_pins') != pins or type(run.get('engine_called')) is not bool):
        raise ReadError('HISTORY_RUN_BINDING', KEY)
    for field, relative in (
        ('protocol_hash', 'experiments/e2e_history_v2/protocol.json'),
        ('input_policy_hash', 'experiments/e2e_history_v2/input-policy.json'),
        ('source_policy_hash', 'docs/e2e-history-v2/Source-Policy.json')):
        if run.get(field) != pins[relative]: raise ReadError('HISTORY_RUN_BINDING', KEY)
    capture = run.get('capture_dir')
    if not isinstance(capture, str): raise ReadError('HISTORY_CAPTURE_SCOPE', KEY)
    folder = Path(capture)
    if folder.parent != archive or not re.fullmatch(r'baostock-[A-Za-z0-9._-]+', folder.name):
        raise ReadError('HISTORY_CAPTURE_SCOPE', KEY)
    safe(folder, archive)
    policy = parsed(reader.read_path(reader.root / 'docs/e2e-history-v2/Source-Policy.json', reader.root)[1], 'Source-Policy.json')
    if not isinstance(policy, dict) or policy.get('raw_document_root') != str(archive / 'source-review'):
        raise ReadError('HISTORY_SOURCE_POLICY_SCOPE', KEY)
    try:
        from tools.e2e_history.run import verify_existing
        checked = verify_existing(directory)
    except (ValueError, KeyError, TypeError, ArithmeticError, OSError):
        raise ReadError('HISTORY_RECOMPUTATION_FAILED', KEY)
    except ImportError:
        raise ReadError('HISTORY_VERIFIER_UNAVAILABLE', KEY)
    if not isinstance(checked, dict) or checked.get('run') != run:
        raise ReadError('HISTORY_VERIFIER_RUN_MISMATCH', KEY)
    report, diagnostic = checked.get('build_report'), checked.get('engine_result')
    if not isinstance(report, dict): raise ReadError('HISTORY_BUILD_REPORT_MISSING', KEY)
    if run['engine_called'] is True and not isinstance(diagnostic, dict):
        raise ReadError('HISTORY_ENGINE_STATE_CONFLICT', KEY)
    # A built Case may fail engine preflight and legitimately carry a blocked
    # EngineResult with engine_called=false. Preserve that outcome explicitly.
    if diagnostic is not None and (not isinstance(diagnostic, dict)
            or diagnostic.get('engine_called') is not run['engine_called']
            or diagnostic.get('status') != run.get('status')):
        raise ReadError('HISTORY_ENGINE_STATE_CONFLICT', KEY)

    research_registry = registry.get('research')
    if not isinstance(research_registry, dict): raise ReadError('HISTORY_RESEARCH_NOT_REGISTERED', KEY)
    inputs_path = archive / 'research/Research-Factor-Inputs.json'
    results_path = archive / 'research/Research-Factors.json'
    if research_registry.get('input_path') != str(inputs_path) or research_registry.get('result_path') != str(results_path):
        raise ReadError('HISTORY_RESEARCH_SCOPE', KEY)
    pinned(reader.root / RESEARCH_CODE, reader.root, research_registry.get('code_sha256'))
    method_raw, method_text = pinned(reader.root / RESEARCH_METHOD, reader.root, research_registry.get('method_sha256'))
    method = parsed(method_text, 'research-method.json')
    _, text = pinned(inputs_path, archive, research_registry.get('input_sha256'))
    inputs = parsed(text, inputs_path.name)
    _, text = pinned(results_path, archive, research_registry.get('result_sha256'))
    research = parsed(text, results_path.name)
    if (not isinstance(method, dict) or not isinstance(inputs, dict) or inputs.get('method_hash') != digest(method_raw)
            or inputs.get('method_frozen_at') != method.get('frozen_at')
            or inputs.get('prior_inputs_path') != str(old_data / 'Financial-Inputs.json')):
        raise ReadError('HISTORY_RESEARCH_BINDING', KEY)
    _, prior_text = pinned(old_data / 'Financial-Inputs.json', old_data, inputs.get('prior_inputs_hash'))
    prior = parsed(prior_text, 'Financial-Inputs.json')
    files = inputs.get('source_files')
    expected = {str(old_data / (symbol + '-2025.pdf')) for symbol in SYMBOLS}
    if (not isinstance(files, list) or len(files) != 9
            or any(not isinstance(row, dict) or not isinstance(row.get('path'), str) for row in files)
            or {row['path'] for row in files} != expected):
        raise ReadError('HISTORY_RESEARCH_ORIGINAL_SCOPE', KEY)
    if (not isinstance(prior, dict) or not isinstance(prior.get('sources'), list)
            or any(not isinstance(row, dict) or not isinstance(row.get('path'), str)
                   for row in prior['sources'])):
        raise ReadError('HISTORY_RESEARCH_ORIGINAL_BINDING', KEY)
    prior_sources = {row['path']: row for row in prior['sources']}
    if len(prior_sources) != 9 or set(prior_sources) != expected:
        raise ReadError('HISTORY_RESEARCH_ORIGINAL_SCOPE', KEY)
    for row in files:
        path = Path(row['path']); safe(path, old_data)
        sha, size = hashlib.sha256(), 0
        try:
            with path.open('rb') as stream:
                while block := stream.read(1_048_576):
                    size += len(block)
                    if size > 64_000_000: raise ReadError('FILE_TOO_LARGE', path.name)
                    sha.update(block)
        except FileNotFoundError: raise ReadError('FILE_MISSING', path.name)
        except OSError: raise ReadError('FILE_UNREADABLE', path.name)
        old_source = prior_sources.get(str(path), {})
        if (row.get('sha256') != 'sha256:' + sha.hexdigest() or row.get('bytes') != size
                or old_source.get('sha256') != sha.hexdigest() or old_source.get('bytes') != size):
            raise ReadError('HISTORY_RESEARCH_ORIGINAL_BINDING', KEY)
    try:
        from tools.e2e_history.research_factors import evaluate, seal
        if inputs.get('content_hash') != seal(inputs): raise ValueError('INPUT_CONTENT_HASH')
        if evaluate(inputs) != research: raise ValueError('RESEARCH_RECOMPUTATION')
    except (ValueError, KeyError, TypeError, ArithmeticError):
        raise ReadError('HISTORY_RESEARCH_RECOMPUTATION_FAILED', KEY)
    # Only recorded outcomes and metadata; no raw Case, PDF or original price rows.
    report_fields = ('kind', 'version', 'run_id', 'recorded_at', 'status', 'errors',
                     'field_coverage', 'real_input_rows', 'market_sessions', 'target_sessions',
                     'action_inventory', 'limitations', 'historical_visibility_proven')
    return {'status': 'VERIFIED', 'run': run,
            'build_report': {key: report[key] for key in report_fields if key in report},
            'diagnostic': diagnostic, 'research': research, 'source': source,
            'integrity': 'FIXED_PINNED_ORIGINALS_AND_RECOMPUTATION_MATCH'}
