"""Portable synthetic-only runner. Original business/test source bytes remain unchanged."""
from pathlib import Path
import importlib
import json
import shutil
import socket
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'backtest_5y/tests')]
attempts = []

def denied(*args, **kwargs):
    attempts.append('NETWORK_ATTEMPT')
    raise AssertionError('ACTUAL_NETWORK_FORBIDDEN_IN_PUBLIC_SYNTHETIC_TESTS')

socket.create_connection = denied
socket.socket.connect = denied

with tempfile.TemporaryDirectory(prefix='metasurvey-public-fixtures-') as temp:
    private = Path(temp).resolve()
    remaps = (
        ('backtest_5y.collectors', 'PRIVATE_ROOT'),
        ('backtest_5y.delivery', 'PRIVATE'),
        ('backtest_5y.tests.test_store', 'PRIVATE'),
        ('test_data', 'PRIVATE_ROOT'),
        ('test_delivery', 'PRIVATE'),
        ('test_store', 'PRIVATE'),
    )
    for name, key in remaps:
        setattr(importlib.import_module(name), key, private)

    import integration_review.boundary as boundary
    import integration_review.test_boundary as boundary_tests
    git = shutil.which('git')
    if not git:
        raise RuntimeError('GIT_EXECUTABLE_REQUIRED')
    boundary_tests.GIT = git
    original_git_output = boundary.git_output
    def portable_git_output(root, args, git='/opt/homebrew/bin/git'):
        selected = boundary_tests.GIT if git == '/opt/homebrew/bin/git' else git
        return original_git_output(root, args, git=selected)
    boundary.git_output = portable_git_output

    loader = unittest.defaultTestLoader
    groups = [
        ('backtest_sidecar', loader.discover(str(ROOT / 'backtest_5y/tests'))),
        ('unapproved_method_math', loader.loadTestsFromName('method_proposals.test_reference_math')),
        ('workspace_boundary', loader.loadTestsFromModule(boundary_tests)),
    ]
    counts = {name: suite.countTestCases() for name, suite in groups}
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(suite for _, suite in groups))
    summary = {
        'scope': 'PUBLIC_SYNTHETIC_ENGINEERING_ONLY', 'counts': counts,
        'tests_run': result.testsRun, 'failures': len(result.failures),
        'errors': len(result.errors), 'skips': len(result.skipped),
        'passed': result.wasSuccessful() and not attempts,
        'temporary_fixture_path_remaps': len(remaps), 'git_executable_remapped': True,
        'business_rules_or_assertions_changed': False,
        'actual_network_attempts_blocked': len(attempts),
        'actual_data_or_accounts_used': False, 'productionGate': False,
        'local_day1_original_archive_tests_in_scope': False,
    }
    print(json.dumps(summary, sort_keys=True))
    sys.exit(0 if summary['passed'] else 1)
