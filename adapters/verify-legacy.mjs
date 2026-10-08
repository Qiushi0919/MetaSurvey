import { pathToFileURL } from 'node:url';
import { readJson, manifestPath, verifyAnchors, runExternalLegacy, verifyFixtureHash } from './legacy-common.mjs';

export async function verifyLegacy() {
  const manifest = await readJson(manifestPath);
  const anchors = await verifyAnchors(manifest);
  if (anchors.status !== 'PASS') return { status: 'FAIL', integrity: anchors, compatibility: { status: 'NOT_RUN' } };
  await verifyFixtureHash(manifest);
  const native = await runExternalLegacy('bindings');
  const after = await verifyAnchors(manifest);
  if (after.status !== 'PASS' || after.fingerprint !== anchors.fingerprint) return { status: 'FAIL', integrity: after, legacy_assets_unchanged: false, compatibility: native.compatibility };
  const status = native.compatibility.status === 'PASS' ? 'PASS' : native.compatibility.known_issue === 'LEGACY_CODEX_CLI_HASH_MISMATCH' ? 'FAIL_KNOWN_COMPATIBILITY' : 'FAIL';
  return { status, integrity: anchors, legacy_assets_unchanged: true, compatibility: native.compatibility };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const result = await verifyLegacy();
    console.log(JSON.stringify(result, null, 2));
    if (result.status === 'FAIL_KNOWN_COMPATIBILITY') process.exitCode = 2;
    else if (result.status !== 'PASS') process.exitCode = 1;
  } catch (error) {
    console.error(JSON.stringify({ status: 'FAIL', reason: error.code || error.message }));
    process.exitCode = 1;
  }
}
