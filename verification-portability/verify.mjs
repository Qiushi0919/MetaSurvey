import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import Ajv from 'ajv/dist/2020.js';

export const root = path.resolve(import.meta.dirname, '..');
const digest = bytes => 'sha256:' + createHash('sha256').update(bytes).digest('hex');
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const fail = code => { throw new Error(code); };
const configPath = path.join(root, 'config/verification-portability/evidence-roots.v1.json');
const CONFIG_HASH = 'sha256:507c739cac43622a4fb47284dfcd1b05853407197faece0b53e29b7c85598755';

function checkedBytes(filename, expectedHash, base) {
  if (typeof filename !== 'string' || !path.isAbsolute(filename) || path.resolve(filename) !== filename ||
      !filename.startsWith(base + path.sep)) fail('DIAGNOSTIC_EVIDENCE_PATH_UNAPPROVED');
  try {
    if (fs.realpathSync(base) !== base || fs.realpathSync(filename) !== filename ||
        !fs.lstatSync(filename).isFile()) fail('DIAGNOSTIC_EVIDENCE_PATH_UNAPPROVED');
    const fd = fs.openSync(filename, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
    try {
      const before = fs.fstatSync(fd, {bigint: true});
      if (!before.isFile() || before.size > 2n * 1024n * 1024n) fail('DIAGNOSTIC_EVIDENCE_FILE_INVALID');
      const bytes = fs.readFileSync(fd);
      const after = fs.fstatSync(fd, {bigint: true});
      if (before.ino !== after.ino || before.dev !== after.dev || before.size !== after.size ||
          before.mtimeNs !== after.mtimeNs || before.ctimeNs !== after.ctimeNs ||
          fs.realpathSync(filename) !== filename) fail('DIAGNOSTIC_EVIDENCE_FILE_CHANGED');
      if (digest(bytes) !== expectedHash) fail('DIAGNOSTIC_EVIDENCE_MISMATCH');
      return bytes;
    } finally { fs.closeSync(fd); }
  } catch (error) {
    if (error instanceof Error && /^DIAGNOSTIC_[A-Z_]+$/.test(error.message)) throw error;
    fail('DIAGNOSTIC_EVIDENCE_FILE_UNAVAILABLE');
  }
}

const manifest = JSON.parse(checkedBytes(configPath, CONFIG_HASH, root));
const schema = JSON.parse(fs.readFileSync(path.join(root, 'contracts/verification-portability/EvidenceRootBinding.schema.json')));
const ajv = new Ajv({strict: true, allErrors: true});
const validateBinding = ajv.compile(schema);
export function validateRootBinding(value) {
  if (!validateBinding(value)) fail('EVIDENCE_ROOT_BINDING_SCHEMA_INVALID');
  return structuredClone(value);
}
validateRootBinding(manifest);
for (const ref of manifest.frozen_dependencies) checkedBytes(path.join(root, ref.path), ref.sha256, root);
// The frozen validator supplies the original schema/hash/business checks. Its
// checkout-dependent file check is replaced by the exact seven bindings below.
// No historical object or frozen source is rewritten, and no admission is issued.
const legacy = await import('../tushare-admission/parent/verify.mjs');

function checkMappedReferences(report, repositoryRoot, archiveRoot) {
  const result = legacy.verifyAdmissionVerification(report, {verifyEvidence: false});
  const expected = manifest.bindings.map(b => ({path: b.canonical_path, sha256: b.sha256}));
  if (!Array.isArray(report.evidence_refs) || report.evidence_refs.length !== expected.length)
    fail('DIAGNOSTIC_EVIDENCE_INVENTORY_INVALID');
  for (let i = 0; i < expected.length; i++) {
    const actual = report.evidence_refs[i], binding = manifest.bindings[i];
    if (actual.path !== expected[i].path) fail('DIAGNOSTIC_EVIDENCE_PATH_UNAPPROVED');
    if (actual.sha256 !== expected[i].sha256) fail('DIAGNOSTIC_EVIDENCE_MISMATCH');
    const base = binding.root_kind === 'REPOSITORY_DOCUMENT' ? repositoryRoot : archiveRoot;
    checkedBytes(path.join(base, binding.relative_path), binding.sha256, base);
  }
  return result;
}

export function verifyHistoricalDiagnostic(report) {
  return checkMappedReferences(report, root, manifest.private_archive_root);
}

// The same filesystem checks can be attacked in isolated temporary directories.
// This API never accepts live roots or produces a historical/source receipt.
export function verifyFixtureBindings(report, {fixtureRoot, repositoryRoot, archiveRoot}) {
  const tmp = fs.realpathSync(os.tmpdir());
  if (typeof fixtureRoot !== 'string' || !fixtureRoot.startsWith(tmp + '/ashare-verification-fixture-') ||
      path.dirname(fixtureRoot) !== tmp || fs.realpathSync(fixtureRoot) !== fixtureRoot ||
      repositoryRoot !== fixtureRoot + '/repo' || archiveRoot !== fixtureRoot + '/archive')
    fail('SYNTHETIC_BINDING_ROOT_INVALID');
  checkMappedReferences(report, repositoryRoot, archiveRoot);
  return {kind: 'SYNTHETIC_FILESYSTEM_FIXTURE_ONLY', admitted_policy_count: 0, production_enabled: false};
}

export function validateVerificationRelease(release) {
  const keys = ['version', 'scope', 'contract_versions', 'schema_version', 'new_migrations',
    'admitted_policy_count', 'production_enabled', 'historical_visibility_proven', 'files'];
  const files = ['config/verification-portability/evidence-roots.v1.json',
    'contracts/verification-portability/EvidenceRootBinding.schema.json',
    'verification-portability/verify.mjs', 'verification-portability/check.mjs',
    'verification-portability/tests/legacy-compatibility.test.mjs',
    'verification-portability/tests/security.test.mjs'];
  if (!release || typeof release !== 'object' || Array.isArray(release) ||
      !equal(Object.keys(release).sort(), keys.sort())) fail('VERIFICATION_RELEASE_SCOPE_INVALID');
  if (release.version !== '1.7.0-verification' || release.scope !== 'OFFLINE_READ_ONLY_CHECKOUT_VERIFICATION' ||
      !equal(release.contract_versions, {EvidenceRootBinding: '1.0.0'}) ||
      release.schema_version !== 6 || !equal(release.new_migrations, []) ||
      release.admitted_policy_count !== 0 || release.production_enabled !== false ||
      release.historical_visibility_proven !== false) fail('VERIFICATION_RELEASE_SCOPE_INVALID');
  if (!Array.isArray(release.files) || release.files.length !== files.length ||
      !equal(release.files.map(f => f.path).sort(), files.sort()) ||
      release.files.some(f => !equal(Object.keys(f).sort(), ['path', 'sha256']) ||
        typeof f.sha256 !== 'string' || !/^sha256:[0-9a-f]{64}$/.test(f.sha256)))
    fail('VERIFICATION_RELEASE_INVENTORY_INVALID');
  return structuredClone(release);
}

export function verifyBindingRelease() {
  const release = validateVerificationRelease(JSON.parse(fs.readFileSync(path.join(root, 'contracts/release.verification-portability.json'))));
  for (const ref of release.files) checkedBytes(path.join(root, ref.path), ref.sha256, root);
  legacy.verifyDiagnosticRelease();
  return structuredClone(release);
}

export function verificationResult() {
  verifyBindingRelease();
  const gate = JSON.parse(checkedBytes(path.join(root, manifest.historical_gate.relative_path), manifest.historical_gate.sha256, root));
  verifyHistoricalDiagnostic(gate);
  return {
    contract: 'EvidenceRootBinding1.0.0', scope: manifest.scope,
    historical_gate_content_hash: gate.content_hash,
    historical_gate_status: gate.verification_conclusion,
    unchanged_canonical_references: gate.evidence_refs.length,
    repository_documents_mapped: manifest.bindings.filter(b => b.root_kind === 'REPOSITORY_DOCUMENT').length,
    unmoved_private_documents_verified: manifest.bindings.filter(b => b.root_kind === 'PRIVATE_ARCHIVE_DOCUMENT').length,
    historical_permissions_preserved: gate.permissions,
    authenticated_network_requests: 0, credential_lookups: 0,
    admitted_policy_count: 0, historical_visibility_proven: false, production_enabled: false
  };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  try {
    if (process.argv.length !== 2) fail('VERIFICATION_ARGUMENT_INVALID');
    console.log(JSON.stringify(verificationResult()));
  } catch (error) {
    console.error(error instanceof Error && /^[A-Z_]+$/.test(error.message) ? error.message : 'VERIFICATION_FAILED');
    process.exitCode = 1;
  }
}
