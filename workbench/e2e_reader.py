"""Read-only E2E projection: fixed paths, byte pins and independent recomputation.

Registry entries are expected hashes, not permission to choose filesystem paths.
The PDFs are hashed in bounded chunks and never returned to the browser.
"""
from pathlib import Path
import hashlib
import json

ARCHIVE = Path('/Users/qiushi/投资研究/.p1b-archives/e2e-pilot-v1-20261014')
PACKAGE = ARCHIVE / 'Run.json'
SOURCE_NAMES = ('data/Financial-Inputs.json', 'data/Official-Disclosure-Captures.json') + tuple(
    'data/' + symbol + '-2025.pdf' for symbol in (
        '603228', '002463', '002916', '600312', '601179', '002028',
        '603993', '601899', '600362')) + (
            'data/Historical-Coverage-Audit.json', 'Diagnostic-Case.json')
CODE = tuple('experiments/e2e_pilot_v1/' + name for name in (
    'research.py', 'method.json', 'protocol.json', 'execution.py')) + (
    'backtest_5y/economics.py', 'wave_f/backtest.py',
    'contracts/e2e-pilot-v1/Run.schema.json')
KEY = 'e2e-registry'


def load(reader, archive=ARCHIVE):
    """Internal archive override exists solely for temporary synthetic tests."""
    from workbench.server import ReadError, digest
    registry, provenance = reader.json(KEY, 'E2EPilotRegistry')
    package_path = archive / 'Run.json'
    if (registry.get('package_path') != str(package_path)
            or not isinstance(registry.get('code_pins'), dict)
            or set(registry.get('code_pins', {})) != set(CODE)):
        raise ReadError('E2E_REGISTRY_SCOPE', KEY)

    def check_text(path, base, expected, size=None):
        raw, text = reader.read_path(path, base)
        if digest(raw) != expected or (size is not None and len(raw) != size):
            raise ReadError('E2E_PIN_MISMATCH', path.name)
        return raw, text

    for relative, expected in registry['code_pins'].items():
        check_text(reader.root / relative, reader.root, expected)

    pins = registry.get('source_pins')
    expected_paths = {str(archive / name) for name in SOURCE_NAMES}
    if (not isinstance(pins, list) or len(pins) != len(SOURCE_NAMES)
            or any(not isinstance(pin, dict) for pin in pins)
            or any(not isinstance(pin.get('path'), str) for pin in pins)
            or {pin.get('path') for pin in pins} != expected_paths):
        raise ReadError('E2E_SOURCE_SCOPE', KEY)
    source_json, source_hashes = {}, {}
    for pin in pins:
        path = Path(pin['path'])
        if type(pin.get('bytes')) is not int or pin['bytes'] < 0:
            raise ReadError('E2E_SOURCE_SCOPE', KEY)
        if path.suffix != '.pdf':
            _, text = check_text(path, archive, pin.get('sha256'), pin['bytes'])
            try:
                source_json[path.name] = json.loads(text)
                source_hashes[path.name] = pin['sha256']
            except ValueError:
                raise ReadError('INVALID_JSON', path.name)
            continue
        if (path.resolve() != path or path.is_symlink()
                or not path.is_relative_to(archive)):
            raise ReadError('UNSAFE_PATH', path.name)
        count, sha = 0, hashlib.sha256()
        try:
            with path.open('rb') as stream:
                while chunk := stream.read(1_048_576):
                    count += len(chunk)
                    if count > 64_000_000:
                        raise ReadError('FILE_TOO_LARGE', path.name)
                    sha.update(chunk)
        except FileNotFoundError:
            raise ReadError('FILE_MISSING', path.name)
        except OSError:
            raise ReadError('FILE_UNREADABLE', path.name)
        if count != pin['bytes'] or 'sha256:' + sha.hexdigest() != pin.get('sha256'):
            raise ReadError('E2E_PIN_MISMATCH', path.name)

    # A rehashed input package cannot claim a different original or observation
    # clock than the pinned capture record. The registry itself grants no license.
    financial = source_json['Financial-Inputs.json']
    captures = source_json['Official-Disclosure-Captures.json']
    sources = financial.get('sources') if isinstance(financial, dict) else None
    symbols = {Path(name).name.split('-')[0] for name in SOURCE_NAMES if name.endswith('.pdf')}
    if (not isinstance(sources, list) or not isinstance(captures, list)
            or len(sources) != 9 or len(captures) != 9
            or any(not isinstance(row, dict) or not isinstance(row.get('symbol'), str)
                   for row in sources + captures)
            or {row['symbol'] for row in sources} != symbols
            or {row['symbol'] for row in captures} != symbols):
        raise ReadError('E2E_SOURCE_CROSS_BINDING', KEY)
    captures_by_symbol = {row['symbol']: row for row in captures}
    pins_by_path = {pin['path']: pin for pin in pins}
    critical = ('symbol', 'path', 'sha256', 'bytes', 'url', 'final_url',
                'retrieved_at', 'available_at')
    for source in sources:
        capture = captures_by_symbol[source['symbol']]
        expected_path = str(archive / 'data' / (source['symbol'] + '-2025.pdf'))
        pin = pins_by_path[expected_path]
        if (any(key not in source or key not in capture or source[key] != capture[key]
                for key in critical)
                or any(not isinstance(source.get(key), str) or not source[key]
                       for key in ('url', 'final_url', 'retrieved_at', 'available_at'))
                or source.get('path') != expected_path
                or source.get('sha256') != pin['sha256'].removeprefix('sha256:')
                or type(source.get('bytes')) is not int
                or source['bytes'] != pin['bytes']):
            raise ReadError('E2E_SOURCE_CROSS_BINDING', KEY)

    _, text = check_text(package_path, archive, registry.get('package_sha256'))
    try:
        package = json.loads(text)
    except ValueError:
        raise ReadError('INVALID_JSON', package_path.name)
    if (not isinstance(package, dict)
            or package.get('source_pins') != pins
            or package.get('content_hash') != registry.get('package_content_hash')
            or package.get('financial_inputs_sha256') != source_hashes['Financial-Inputs.json']
            or package.get('diagnostic_case_sha256') != source_hashes['Diagnostic-Case.json']
            or package.get('historical_coverage_audit_sha256') != source_hashes['Historical-Coverage-Audit.json']
            or package.get('financial_inputs') != source_json['Financial-Inputs.json']
            or package.get('historical_coverage_audit') != source_json['Historical-Coverage-Audit.json']
            or package.get('diagnostic_case') != source_json['Diagnostic-Case.json']):
        raise ReadError('E2E_EVIDENCE_BINDING', KEY)
    try:
        from experiments.e2e_pilot_v1.research import validate_run
        value = validate_run(package, root=reader.root)
    except (ValueError, KeyError, TypeError, ArithmeticError):
        raise ReadError('E2E_VALIDATION_FAILED', KEY)
    except (ImportError, OSError):
        raise ReadError('E2E_VALIDATOR_UNAVAILABLE', KEY)
    value['provenance'] = provenance
    value['integrity'] = 'PINNED_FILES_AND_RECOMPUTED_EXPERIMENT_MATCH'
    return value
