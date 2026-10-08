import { pathToFileURL } from 'node:url';
import { readJson, manifestPath, fixturePath, verifyAnchors, verifyPortableFixture, verifyFixtureHash, runExternalLegacy } from './legacy-common.mjs';

export async function replayLegacy() {
  const manifest = await readJson(manifestPath);
  const before = await verifyAnchors(manifest);
  if (before.status !== 'PASS') throw new Error('LEGACY_ANCHOR_MISMATCH');
  await verifyFixtureHash(manifest);
  const portable = verifyPortableFixture(await readJson(fixturePath));
  const external = await runExternalLegacy('replay');
  const after = await verifyAnchors(manifest);
  if (after.status !== 'PASS' || before.fingerprint !== after.fingerprint) throw new Error('LEGACY_FINGERPRINT_CHANGED');
  if (external.replay.status !== 'PASS') throw new Error('LEGACY_EXTERNAL_REPLAY_FAILED');
  return {
    replay_status: 'PASS', integrity_status: 'PASS', legacy_assets_unchanged: true,
    selected_anchor_count: before.selected_anchor_count, before_fingerprint: before.fingerprint, after_fingerprint: after.fingerprint,
    portable_fixture: portable, external_replay: external.replay,
    native_compatibility: external.compatibility,
    native_compatibility_is_repaired: false,
    limitations: ['Saved inputs/outputs deterministic replay only; 14 of 40 sessions.', 'No fresh audit of all original evidence/PIT, no profitability proof, no legacy writes or production execution.'],
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    console.log(JSON.stringify(await replayLegacy(), null, 2));
  } catch (error) {
    console.error(JSON.stringify({ replay_status: 'FAIL', reason: error.code || error.message }));
    process.exitCode = 1;
  }
}
