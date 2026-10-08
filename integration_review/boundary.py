"""Review byte preservation and proposed path ownership without writing checkouts.

This is a point-in-time engineering check, not a filesystem permission sandbox.
Do not use its PASS as market, PIT, approval or execution authority.
"""
from pathlib import Path, PurePosixPath
import hashlib
import subprocess

ALLOWED = ('backtest_5y/', 'contracts/backtest-5y/',
           'docs/backtest-5y/', 'tests/backtest-5y/')


def owned(path):
    p = PurePosixPath(path)
    return (not p.is_absolute() and '..' not in p.parts and
            path == p.as_posix() and any(path.startswith(x) for x in ALLOWED))


def check_refs(root, baseline, *, absolute=False):
    """Baseline is trusted review input; paths are validated before reading."""
    root = Path(root).resolve()
    original = Path(baseline['parent_root']).resolve() if not absolute else None
    findings = []
    refs = baseline['protected_files'] if absolute else baseline['tracked_files']
    for row in refs:
        raw_path = Path(row['path'])
        try:
            relative = raw_path.relative_to(original) if not absolute else None
            path = raw_path if absolute else root / relative
            # A symlink can preserve bytes while redirecting ownership; reject it.
            aliased = path.is_symlink()
            if not absolute:
                aliased = aliased or any((root / Path(*relative.parts[:i])).is_symlink()
                                        for i in range(1, len(relative.parts) + 1))
            if aliased or (not absolute and path.resolve().is_relative_to(root) is False):
                raise ValueError('PATH_ALIAS_OR_ESCAPE')
            data = path.read_bytes()
            if len(data) != row['bytes'] or 'sha256:' + hashlib.sha256(data).hexdigest() != row['sha256']:
                findings.append({'path': str(path), 'reason': 'BASELINE_BYTES_CHANGED'})
        except (OSError, ValueError):
            findings.append({'path': row['path'], 'reason': 'MISSING_OR_UNSAFE_PATH'})
    return {'checked': len(refs), 'state': 'FAIL' if findings else 'PASS', 'findings': findings}


def git_output(root, args, git='/opt/homebrew/bin/git'):
    result = subprocess.run([git, '-C', str(root), *args], check=True,
                            capture_output=True, env=None)
    return result.stdout


def review_changes(root, baseline_head, git='/opt/homebrew/bin/git'):
    """Committed, staged, unstaged and nonignored untracked changes are covered."""
    git_output(root, ['merge-base', '--is-ancestor', baseline_head, 'HEAD'], git)
    changed = set()
    for args in (['diff', '--name-only', '-z', baseline_head, 'HEAD'],
                 ['diff', '--name-only', '-z', 'HEAD'],
                 ['ls-files', '--others', '--exclude-standard', '-z']):
        changed.update(x.decode('utf-8') for x in git_output(root, args, git).split(b'\0') if x)
    blocked = [p for p in sorted(changed) if not owned(p)]
    return {'state': 'FAIL' if blocked else 'PASS', 'changed_paths': sorted(changed),
            'outside_owned_paths': blocked,
            'ignored_files_not_inspected': True, 'working_copy_can_change_after_read': True}
