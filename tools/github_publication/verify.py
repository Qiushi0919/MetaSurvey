"""Verify public Git contents against the source snapshot; no local originals required."""
import argparse
import hashlib
import json
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--git', default=shutil.which('git'))
parser.add_argument('--index', action='store_true', help='Check staged index before commit/push')
args = parser.parse_args()
if not args.git:
    raise SystemExit('GIT_REQUIRED')

def git(*values):
    return subprocess.check_output([args.git, *values])

def read(name):
    return git('show', (':' if args.index else 'HEAD:') + name)

manifest_name = 'docs/review/Source-Snapshot.json'
omitted_name = 'docs/review/Local-Only-Manifest.json'
manifest = json.loads(read(manifest_name))
omitted = json.loads(read(omitted_name))
expected = {r['path'] for r in manifest['files']} | {manifest_name, omitted_name}
names = git('ls-files', '-z') if args.index else git('ls-tree', '-rz', '--name-only', 'HEAD')
actual = set(names.decode().strip('\0').split('\0'))
if expected != actual:
    raise SystemExit(json.dumps({'missing': sorted(expected-actual), 'unexpected': sorted(actual-expected)}))
for row in manifest['files']:
    data = read(row['path'])
    if len(data) != row['bytes'] or 'sha256:' + hashlib.sha256(data).hexdigest() != row['sha256']:
        raise SystemExit('SOURCE_FILE_MISMATCH:' + row['path'])
if any(r['path'] in actual for r in omitted['files']):
    raise SystemExit('LOCAL_ONLY_PAYLOAD_IN_PUBLIC_GIT')
if manifest['source_commit'] != omitted['source_commit'] or manifest['productionGate'] is not False:
    raise SystemExit('SNAPSHOT_METADATA_MISMATCH')
print(json.dumps({'status': 'PASS', 'public_git_files': len(actual),
                  'source_files_verified': len(manifest['files']),
                  'local_only_payloads_absent': len(omitted['files']),
                  'source_commit': manifest['source_commit'], 'productionGate': False}))
