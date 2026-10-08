"""Synthetic engineering fixtures only; no source/PIT/actual approval claims."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from .boundary import check_refs, owned, review_changes

GIT = '/opt/homebrew/bin/git'


class Preservation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'old.txt').write_bytes(b'synthetic baseline')
        self.b = {'parent_root': '/synthetic-original', 'tracked_files': [
            {'path': '/synthetic-original/old.txt', 'bytes': 18,
             'sha256': 'sha256:' + hashlib.sha256(b'synthetic baseline').hexdigest()}]}

    def test_matching_original(self):
        self.assertEqual(check_refs(self.root, self.b)['state'], 'PASS')

    def test_same_length_changed_original(self):
        (self.root / 'old.txt').write_bytes(b'synthetic changed!')
        self.assertEqual(check_refs(self.root, self.b)['state'], 'FAIL')

    def test_missing_original(self):
        (self.root / 'old.txt').unlink()
        self.assertEqual(check_refs(self.root, self.b)['state'], 'FAIL')

    def test_same_bytes_symlink_rejected(self):
        (self.root / 'old.txt').rename(self.root / 'target')
        (self.root / 'old.txt').symlink_to(self.root / 'target')
        self.assertEqual(check_refs(self.root, self.b)['state'], 'FAIL')

    def test_directory_symlink_rejected(self):
        (self.root / 'real').mkdir()
        (self.root / 'old.txt').rename(self.root / 'real' / 'old.txt')
        (self.root / 'alias').symlink_to(self.root / 'real', target_is_directory=True)
        self.b['tracked_files'][0]['path'] = '/synthetic-original/alias/old.txt'
        self.assertEqual(check_refs(self.root, self.b)['state'], 'FAIL')

    def test_absolute_forward_checkpoint_drift(self):
        row = dict(self.b['tracked_files'][0], path=str(self.root / 'old.txt'))
        b = {'protected_files': [row]}
        self.assertEqual(check_refs(self.root, b, absolute=True)['state'], 'PASS')
        (self.root / 'old.txt').write_bytes(b'changed')
        self.assertEqual(check_refs(self.root, b, absolute=True)['state'], 'FAIL')


class Paths(unittest.TestCase):
    def test_approved_new_directories(self):
        for path in ('backtest_5y/data/reader.py', 'contracts/backtest-5y/Evidence-v1.json',
                     'docs/backtest-5y/Report.md', 'tests/backtest-5y/case.py'):
            self.assertTrue(owned(path))

    def test_old_or_escaping_paths_rejected(self):
        for path in ('docs/wave-f/Frozen-StrategySpec-v1.json', 'AGENTS.md',
                     '../backtest_5y/x', 'backtest_5y/../wave_f/x',
                     '/backtest_5y/x', 'backtest_5y//x', 'backtest_5y-not-owned/x'):
            self.assertFalse(owned(path))


class GitBoundaries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git('init', '-q')
        (self.root / 'baseline').write_text('synthetic')
        self.git('add', 'baseline')
        self.commit('synthetic baseline')
        self.base = self.git('rev-parse', 'HEAD').decode().strip()

    def git(self, *args):
        return subprocess.run([GIT, '-C', str(self.root), *args], check=True,
                              capture_output=True).stdout

    def commit(self, message):
        return self.git('-c', 'user.name=Synthetic Test', '-c',
                        'user.email=synthetic@example.invalid', 'commit', '-qm', message)

    def test_committed_staged_untracked_and_ignored_scope(self):
        (self.root / 'backtest_5y').mkdir()
        (self.root / 'backtest_5y' / 'reader.py').write_text('synthetic')
        self.git('add', 'backtest_5y/reader.py')
        self.commit('synthetic approved path')
        (self.root / 'outside-staged').write_text('x')
        self.git('add', 'outside-staged')
        (self.root / 'outside-untracked').write_text('x')
        # Ignored files are explicitly outside this tool's inspection claim.
        (self.root / '.git' / 'info' / 'exclude').write_text('ignored-local\n')
        (self.root / 'ignored-local').write_text('synthetic no secret')
        r = review_changes(self.root, self.base)
        self.assertEqual(r['state'], 'FAIL')
        self.assertEqual(r['outside_owned_paths'], ['outside-staged', 'outside-untracked'])
        self.assertIn('backtest_5y/reader.py', r['changed_paths'])
        self.assertTrue(r['ignored_files_not_inspected'])

    def test_unstaged_baseline_edit_rejected(self):
        (self.root / 'baseline').write_text('changed')
        self.assertEqual(review_changes(self.root, self.base)['outside_owned_paths'], ['baseline'])

    def test_baseline_not_ancestor_rejected(self):
        self.git('checkout', '--orphan', 'unrelated')
        self.commit('synthetic unrelated root')
        with self.assertRaises(subprocess.CalledProcessError):
            review_changes(self.root, self.base)


if __name__ == '__main__':
    unittest.main()
