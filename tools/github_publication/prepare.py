"""One-way code/review publication. Never copy the source Git history or untracked files."""
from pathlib import Path, PurePosixPath
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
import shutil
import subprocess

SOURCE = Path(__file__).resolve().parents[2]
GENERATED = ('docs/review/Source-Snapshot.json', 'docs/review/Local-Only-Manifest.json')
MARKER = '.metasurvey-publication.json'

def safe_path(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or str(path) != value or not path.parts:
        raise ValueError('UNSAFE_PUBLICATION_PATH')
    return path

def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def inspect_text(name, data, policy):
    text = data.decode('utf-8')
    issues = []
    patterns = {
        'PRIVATE_KEY': r'-----BEGIN (?:ENCRYPTED |RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'GITHUB_CREDENTIAL': r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b',
        'OPENAI_CREDENTIAL': r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}',
        'QUERY_CREDENTIAL': r'[?&](?:token|api_key|access_token)=([A-Za-z0-9_-]{24,})',
        'LITERAL_CREDENTIAL': r'\b(?:token|api_key|secret_key|password)\s*[=:]\s*[\"\x27]([A-Za-z0-9_-]{24,})[\"\x27]',
        'SDK_LITERAL_CREDENTIAL': r'pro_api\(\s*[\"\x27]([A-Za-z0-9_-]{24,})[\"\x27]',
    }
    exemptions = 0
    for rule, pattern in patterns.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = match.group(1) if match.lastindex else match.group(0)
            line = text.splitlines()[text[:match.start()].count('\n')]
            if rule == 'LITERAL_CREDENTIAL' and any(
                row['path'] == name and row['value_sha256'] == hashlib.sha256(value.encode()).hexdigest()
                and row['required_context'] in line for row in policy['synthetic_secret_sentinels']
            ):
                exemptions += 1
            else:
                issues.append({'path': name, 'rule': rule,
                               'line': text[:match.start()].count('\n') + 1})
    return issues, exemptions

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--git', default=shutil.which('git'))
    args = parser.parse_args()
    if not args.git:
        raise SystemExit('GIT_EXECUTABLE_REQUIRED')
    def git(*values):
        return subprocess.run([args.git, '-C', str(SOURCE), *values], check=True,
                              capture_output=True).stdout
    if git('status', '--porcelain'):
        raise SystemExit('SOURCE_MUST_BE_CLEAN_COMMITTED_BEFORE_EXPORT')
    head = git('rev-parse', 'HEAD').decode().strip()
    policy = json.loads((SOURCE / 'tools/github_publication/policy.json').read_text())
    dest = args.destination.expanduser().absolute()
    if dest.is_symlink() or dest.resolve() != dest:
        raise SystemExit('DESTINATION_SYMLINK_OR_ALIAS_FORBIDDEN')
    if dest == SOURCE or dest.is_relative_to(SOURCE) or SOURCE.is_relative_to(dest):
        raise SystemExit('SEPARATE_PUBLICATION_DIRECTORY_REQUIRED')
    old = None
    if dest.exists():
        marker = dest / MARKER
        if not marker.is_file() or marker.is_symlink():
            raise SystemExit('UNRELATED_DESTINATION_REFUSED')
        old = json.loads(marker.read_text())
        if old.get('kind') != 'MetaSurveyOneWayPublication' or old.get('source_root') != str(SOURCE):
            raise SystemExit('PUBLICATION_OWNERSHIP_MISMATCH')

    included, excluded, payloads, issues, exemptions = [], [], {}, [], 0
    for entry in git('ls-tree', '-rz', '--full-tree', 'HEAD').split(b'\0'):
        if not entry:
            continue
        metadata, name_bytes = entry.split(b'\t', 1)
        mode, kind, object_id = metadata.decode().split()
        name = name_bytes.decode()
        safe_path(name)
        if mode not in ('100644', '100755') or kind != 'blob':
            raise SystemExit('NON_REGULAR_GIT_OBJECT_REFUSED:' + name)
        data = git('cat-file', 'blob', object_id)
        row = {'path': name, 'bytes': len(data), 'sha256': digest(data)}
        if name in policy['local_only_paths']:
            excluded.append({**row, 'reason': 'REFERENCE_FIXTURE_LICENSE_UNKNOWN_REDISTRIBUTION_NOT_ALLOWED'})
            continue
        if name in GENERATED or name == MARKER:
            raise SystemExit('GENERATED_MIRROR_FILE_MUST_NOT_ENTER_SOURCE_REPO:' + name)
        if len(data) >= 100 * 1024 * 1024:
            raise SystemExit('LARGE_OBJECT_REFUSED:' + name)
        parts = PurePosixPath(name).parts
        if any(p in ('raw', 'object-store', 'node_modules', '.p1b-archives', 'state', 'runs', '.git') for p in parts):
            raise SystemExit('PRIVATE_OR_RUNTIME_PATH_REFUSED:' + name)
        if name.endswith(('.db', '.sqlite', '.zip', '.pem', '.key', '.parquet', '.pdf')) or any(p.startswith('.env') and p != '.env.example' for p in parts):
            raise SystemExit('PRIVATE_OR_BINARY_SUFFIX_REFUSED:' + name)
        try:
            hits, excepted = inspect_text(name, data, policy)
        except UnicodeDecodeError:
            raise SystemExit('UNREVIEWED_BINARY_REFUSED:' + name)
        issues.extend(hits); exemptions += excepted
        included.append(row); payloads[name] = (mode, data)
    if len(excluded) != len(policy['local_only_paths']):
        raise SystemExit('LOCAL_REFERENCE_EXCLUSION_INVENTORY_CHANGED_REVIEW_REQUIRED')
    if issues:
        print(json.dumps({'status': 'BLOCKED', 'findings_without_values': issues}))
        raise SystemExit(1)

    managed = set(payloads) | set(GENERATED)
    if old:
        for name in set(old['managed_paths']) | managed:
            safe_path(name)
            target = dest / name
            if any(p.is_symlink() for p in (target, *target.parents) if p != dest.parent):
                raise SystemExit('DESTINATION_SYMLINK_REFUSED:' + name)
        for name in managed - set(old['managed_paths']):
            if (dest / name).exists():
                raise SystemExit('UNMANAGED_DESTINATION_FILE_REFUSED:' + name)
        for name in old['managed_paths']:
            p = dest / name
            expected = old.get('managed_hashes', {}).get(name)
            if not p.is_file() or expected is None or digest(p.read_bytes()) != expected:
                raise SystemExit('LOCAL_PUBLICATION_EDIT_REFUSED:' + name)
    dest.mkdir(mode=0o700, parents=True, exist_ok=True)
    if old:
        for name in set(old['managed_paths']) - managed:
            (dest / name).unlink()
    for name, (mode, data) in payloads.items():
        p = dest / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        p.chmod(0o755 if mode == '100755' else 0o644)
    captured_at = datetime.now(timezone.utc).isoformat()
    manifest = {'kind': 'PublicSourceSnapshot', 'version': '1.0.0', 'source_commit': head,
                'captured_at': captured_at, 'source_git_history_uploaded': False,
                'included_source_files': len(included), 'files': included,
                'local_only_manifest': GENERATED[1], 'secret_scan': 'PASS_WITH_EXPLICIT_SYNTHETIC_SENTINEL',
                'synthetic_sentinel_matches': exemptions, 'productionGate': False}
    write_json(dest / GENERATED[0], manifest)
    write_json(dest / GENERATED[1], {'kind': 'LocalOnlyPublicationManifest', 'version': '1.0.0',
               'source_commit': head, 'files': excluded, 'raw_payloads_published': False,
               'missing_local_checks_are_not_passed': True, 'productionGate': False})
    hashes = {name: digest((dest / name).read_bytes()) for name in sorted(managed)}
    write_json(dest / MARKER, {'kind': 'MetaSurveyOneWayPublication', 'version': '1.0.0',
               'source_root': str(SOURCE), 'source_commit': head,
               'managed_paths': sorted(managed), 'managed_hashes': hashes})
    ignore = dest / '.git/info/exclude'
    if ignore.parent.exists() and MARKER not in ignore.read_text():
        with ignore.open('a') as f:
            f.write('\n/' + MARKER + '\n')
    print(json.dumps({'status': 'PREPARED', 'source_commit': head, 'included': len(included),
                     'excluded_local_only': len(excluded), 'secret_values_printed': False,
                     'source_git_history_copied': False, 'productionGate': False}))

if __name__ == '__main__':
    main()
