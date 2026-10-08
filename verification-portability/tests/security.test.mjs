import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {spawnSync} from 'node:child_process';
import {hashValue} from '../../src/contracts/validate.mjs';
import {root, verificationResult, verifyHistoricalDiagnostic, verifyFixtureBindings,
  validateRootBinding, validateVerificationRelease} from '../verify.mjs';

const read = p => JSON.parse(fs.readFileSync(path.join(root, p)));
const manifest = read('config/verification-portability/evidence-roots.v1.json');
const gate = () => read(manifest.historical_gate.relative_path);
const release = () => read('contracts/release.verification-portability.json');
const reseal = value => {const {content_hash, ...body} = value; return {...body, content_hash: hashValue(body)};};

function withFixture(body) {
  const fixtureRoot = fs.mkdtempSync(path.join(fs.realpathSync(os.tmpdir()), 'ashare-verification-fixture-'));
  const roots = {fixtureRoot, repositoryRoot: fixtureRoot + '/repo', archiveRoot: fixtureRoot + '/archive'};
  const files = manifest.bindings.map(binding => {
    const base = binding.root_kind === 'REPOSITORY_DOCUMENT' ? roots.repositoryRoot : roots.archiveRoot;
    const sourceBase = binding.root_kind === 'REPOSITORY_DOCUMENT' ? root : manifest.private_archive_root;
    const filename = path.join(base, binding.relative_path);
    fs.mkdirSync(path.dirname(filename), {recursive: true});
    fs.copyFileSync(path.join(sourceBase, binding.relative_path), filename);
    return filename;
  });
  try {body(roots, files);} finally {fs.rmSync(fixtureRoot, {recursive: true, force: true});}
}

test('relocated verification proves exactly two repository and five unmoved archive documents with no source authority', () => {
  const result = verificationResult();
  assert.equal(result.repository_documents_mapped, 2);
  assert.equal(result.unmoved_private_documents_verified, 5);
  assert.equal(result.historical_gate_content_hash, gate().content_hash);
  assert.equal(result.historical_gate_status, 'BLOCKED_PROVIDER_PREREQUISITES');
  assert.equal(result.authenticated_network_requests, 0);
  assert.equal(result.credential_lookups, 0);
  assert.equal(result.admitted_policy_count, 0);
  assert.equal(result.production_enabled, false);
  assert.equal(result.historical_visibility_proven, false);
  assert.ok(Object.values(result.historical_permissions_preserved).every(v => v === false));
});

test('missing, duplicated and reordered references cannot pass the seven-object inventory', () => {
  for (const change of [g => g.evidence_refs.pop(), g => g.evidence_refs.push(g.evidence_refs[0]),
    g => g.evidence_refs[1] = g.evidence_refs[0], g => g.evidence_refs.reverse()]) {
    const g = gate(); change(g);
    assert.throws(() => verifyHistoricalDiagnostic(reseal(g)), /EVIDENCE_(INVENTORY_INVALID|PATH_UNAPPROVED)/);
  }
});

test('filesystem fixture relocation reuses exact originals but can only return a synthetic non-admission result', () => {
  withFixture(roots => {
    const result = verifyFixtureBindings(gate(), roots);
    assert.deepEqual(result, {kind: 'SYNTHETIC_FILESYSTEM_FIXTURE_ONLY', admitted_policy_count: 0, production_enabled: false});
  });
});

test('changed repository authorization bytes fail without resealing historical records', () => {
  withFixture((roots, files) => {
    fs.appendFileSync(files[0], '\nSYNTHETIC_TAMPER');
    assert.throws(() => verifyFixtureBindings(gate(), roots), /EVIDENCE_MISMATCH/);
  });
});

test('changed private archive bytes fail despite correct reference metadata', () => {
  withFixture((roots, files) => {
    fs.writeFileSync(files[1], '{}');
    assert.throws(() => verifyFixtureBindings(gate(), roots), /EVIDENCE_MISMATCH/);
  });
});

test('missing private evidence blocks verification instead of falling back or claiming empty coverage', () => {
  withFixture((roots, files) => {
    fs.unlinkSync(files[1]);
    assert.throws(() => verifyFixtureBindings(gate(), roots), /EVIDENCE_FILE_UNAVAILABLE/);
  });
});

test('a symlink to identical leaf bytes is rejected rather than following a replacement', () => {
  withFixture((roots, files) => {
    const other = roots.fixtureRoot + '/identical-file'; fs.renameSync(files[0], other); fs.symlinkSync(other, files[0]);
    assert.throws(() => verifyFixtureBindings(gate(), roots), /EVIDENCE_PATH_UNAPPROVED/);
  });
});

test('a parent symlink to identical documents is rejected before content verification', () => {
  withFixture((roots, files) => {
    const parent = path.dirname(files[0]), other = roots.fixtureRoot + '/identical-directory';
    fs.renameSync(parent, other); fs.symlinkSync(other, parent);
    assert.throws(() => verifyFixtureBindings(gate(), roots), /EVIDENCE_PATH_UNAPPROVED/);
  });
});

test('a directory in place of an evidence file cannot be treated as an empty object', () => {
  withFixture((roots, files) => {
    fs.unlinkSync(files[1]); fs.mkdirSync(files[1]);
    assert.throws(() => verifyFixtureBindings(gate(), roots), /EVIDENCE_PATH_UNAPPROVED/);
  });
});

test('synthetic API refuses live and unrelated root bindings', () => {
  assert.throws(() => verifyFixtureBindings(gate(), {fixtureRoot: root, repositoryRoot: root,
    archiveRoot: manifest.private_archive_root}), /SYNTHETIC_BINDING_ROOT_INVALID/);
  withFixture(roots => {
    assert.throws(() => verifyFixtureBindings(gate(), {...roots, archiveRoot: manifest.private_archive_root}), /SYNTHETIC_BINDING_ROOT_INVALID/);
  });
});

test('root contract refuses guessed roots, traversal, extra entitlement fields and strategy promotion', () => {
  for (const change of [m => m.private_archive_root = '/Users/qiushi/.ssh',
    m => m.bindings[0].relative_path = '../secret', m => m.bindings[0].canonical_path += '/..',
    m => m.production_enabled = true, m => m.historical_visibility_proven = true,
    m => m.entitlement = 'APPROVED', m => m.namespace = 'EVENT_3']) {
    const value = structuredClone(manifest); change(value);
    assert.throws(() => validateRootBinding(value), /BINDING_SCHEMA_INVALID/);
  }
});

test('CLI rejects root override and unsupported bypass flags with a controlled reason', () => {
  for (const flag of ['--skip-evidence', '--archive-root=/Users/qiushi/.ssh', '--production']) {
    const result = spawnSync(process.execPath, ['verification-portability/verify.mjs', flag], {cwd: root, encoding: 'utf8'});
    assert.equal(result.status, 1); assert.equal(result.stdout, '');
    assert.equal(result.stderr.trim(), 'VERIFICATION_ARGUMENT_INVALID');
  }
});

test('mapped verification does not rewrite original references, dates, hashes or prior state', () => {
  const g = gate(), before = JSON.stringify(g); const result = verifyHistoricalDiagnostic(g);
  assert.equal(JSON.stringify(g), before); assert.deepEqual(result, g);
  result.evidence_refs[0].path = '/SYNTHETIC_CHANGED_COPY';
  assert.equal(JSON.stringify(g), before);
});

test('release rejects unknown authority, omitted/duplicated source pins and changed schema or migrations', () => {
  for (const change of [r => r.production_enabled = true, r => r.historical_visibility_proven = true,
    r => r.admitted_policy_count = 1, r => r.schema_version = 7, r => r.new_migrations = ['007'],
    r => r.permission = 'ADMITTED', r => r.files = [], r => r.files.push(r.files[0]),
    r => r.files[0].path = '../secret', r => r.files[0].sha256 = 'SYNTHETIC_INVALID']) {
    const value = release(); change(value);
    assert.throws(() => validateVerificationRelease(value), /VERIFICATION_RELEASE_(SCOPE|INVENTORY)_INVALID/);
  }
});
