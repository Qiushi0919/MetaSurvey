import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { readJson, manifestPath, fixturePath, verifyPortableFixture, checkLegacyFees, legacyFinancialRows, verifyFixtureHash, verifyAnchors, containedFile } from '../adapters/legacy-common.mjs';
import { replayLegacy } from '../adapters/replay-legacy.mjs';

const manifest = await readJson(manifestPath);
const fixture = await readJson(fixturePath);
const evidence = JSON.parse(await readFile(new URL('./fixtures/legacy/p0-external-replay-evidence.v1.json', import.meta.url), 'utf8'));
const expectCode = (code, run) => assert.throws(run, error => error.code === code);

test('manifest contains all five dispositions and does not authorize old writes or deletion', () => {
  assert.equal(manifest.manifest_version, '1.0.0');
  assert.deepEqual(new Set(manifest.assets.map(asset => asset.classification)), new Set(['KEEP', 'MODIFY', 'ISOLATE', 'DEPRECATE', 'DELETE_LATER']));
  assert.equal(manifest.deletions_executed, false);
  assert.equal(manifest.legacy_writes_permitted, false);
  for (const asset of manifest.assets) {
    assert.equal(path.isAbsolute(asset.path), false);
    assert.equal(asset.path.split(/[\\/]/).includes('..'), false);
  }
  for (const anchor of manifest.selected_anchors) {
    assert.match(anchor.sha256, /^[a-f0-9]{64}$/);
    assert.equal(anchor.access, 'READ_ONLY');
    assert.equal(/credentials|secrets|\/state\/|\.(db|sqlite)/i.test(anchor.path), false);
  }
});

test('V5 remains its original 5–8 session legacy experiment, with frozen code/cost/state', () => {
  const v5 = manifest.assets.find(asset => asset.asset_id === 'v5-experiment');
  assert.equal(v5.kind, 'LEGACY_EXPERIMENT');
  assert.equal(v5.classification, 'ISOLATE');
  assert.equal(v5.target_strategy_mapping, null);
  assert.equal(v5.holding_horizon.minimum_plan_sessions, 5);
  assert.equal(v5.holding_horizon.maximum_plan_sessions, 8);
  assert.equal(v5.holding_horizon.experiment_window_sessions, 40);
  assert.equal(v5.legacy_fee_profile.provenance, 'LEGACY_FIXTURE_NOT_PRODUCTION');
  assert.equal(v5.legacy_rules.initial_cash_cents, 1000000);
  assert.equal(v5.recorded_state.finished, false);
  assert.equal(v5.recorded_state.completed_days, 14);
  assert.equal(v5.recorded_state.runtime.state, 'BLOCKED');
  assert.equal(v5.recorded_state.real_trades, false);
  assert.ok(v5.source_code_hashes.length > 0);
});

test('primary handoff hash remains the original SoT, while migration suggestions do not become defaults', () => {
  assert.equal(manifest.primary_source_of_truth.sha256, '63e78aac5e061a82419bd202b58c2cba28ca025053030a14b8aad8737b55fb38');
  assert.equal(manifest.migration_baseline.confirmed_direction_only, true);
  assert.equal(manifest.migration_baseline.unconfirmed_proposals_are_business_rules, false);
});

test('portable immutable V5 fixture independently reconciles all 14 daily snapshots', async () => {
  await verifyFixtureHash(manifest);
  const result = verifyPortableFixture(fixture);
  assert.equal(result.status, 'PASS');
  assert.equal(result.completed_days, 14);
  assert.equal(result.trade_rows, 8);
  assert.equal(result.completed_rounds, 4);
  assert.equal(result.fees_cents, '4986');
  assert.equal(result.final_cash_cents, '979114');
  assert.equal(result.final_nav_cents, '979114');
  assert.equal(result.net_pnl_cents, '-20886');
  assert.equal(result.unfilled_rows_preserved, 4);
  assert.deepEqual(fixture.days.at(-1).snapshot.positions, {});
});

test('fixture rejects modern strategy remapping and every altered day/version binding', () => {
  expectCode('LEGACY_STRATEGY_MAPPING_FORBIDDEN', () => verifyPortableFixture({ ...fixture, target_strategy_mapping: 'CORE_40' }));
  const changed = structuredClone(fixture);
  changed.days[0].frozen_hash = 'f'.repeat(64);
  expectCode('LEGACY_DAY_BINDING_MISMATCH', () => verifyPortableFixture(changed));
  const reordered = structuredClone(fixture);
  [reordered.days[0], reordered.days[1]] = [reordered.days[1], reordered.days[0]];
  expectCode('LEGACY_DAY_BINDING_MISMATCH', () => verifyPortableFixture(reordered));
});

test('independent historical fee profile rejects changed fees rather than altering the old seal', () => {
  const row = fixture.days.flatMap(day => day.rows).find(row => row.type === 'TRADE');
  expectCode('LEGACY_FEE_MISMATCH', () => checkLegacyFees({ ...row, fees: { ...row.fees, commission: row.fees.commission + 1 } }, fixture.legacy_fee_profile));
  expectCode('LEGACY_FEE_PROFILE_INVALID', () => checkLegacyFees(row, { ...fixture.legacy_fee_profile, commission_rate: 'UNSET_REQUIRED' }));
  const changed = structuredClone(fixture);
  const trade = changed.days.flatMap(day => day.rows).find(row => row.type === 'TRADE');
  trade.cash_delta++;
  expectCode('LEGACY_CASH_DELTA_MISMATCH', () => verifyPortableFixture(changed));
});

test('unfilled failures stay in the evidence and cannot silently carry money changes', () => {
  const unfilled = fixture.days[0].rows[0];
  assert.equal(unfilled.type, 'UNFILLED');
  assert.equal(unfilled.reason, 'OPEN_OUTSIDE_LIMIT');
  assert.deepEqual(legacyFinancialRows([unfilled]), []);
  expectCode('LEGACY_INVALID_UNFILLED', () => legacyFinancialRows([{ ...unfilled, cash_delta: 100 }]));
  expectCode('LEGACY_UNSUPPORTED_ENTRY', () => legacyFinancialRows([{ type: 'UNKNOWN_MONEY_EVENT' }]));
});

test('altered legacy cash / NAV or proxy assumptions fail portable replay checks', () => {
  const changedCash = structuredClone(fixture);
  changedCash.days[0].snapshot.cash_cents++;
  expectCode('LEGACY_CASH_MISMATCH', () => verifyPortableFixture(changedCash));
  const changedNav = structuredClone(fixture);
  changedNav.days[0].snapshot.nav_cents++;
  expectCode('LEGACY_NAV_MISMATCH', () => verifyPortableFixture(changedNav));
  const changedProxy = structuredClone(fixture);
  changedProxy.days.flatMap(day => day.rows).find(row => row.type === 'TRADE').fill_assumption = 'OBSERVED_REAL_FILL';
  expectCode('LEGACY_PROXY_ASSUMPTION_CHANGED', () => verifyPortableFixture(changedProxy));
});

test('native compatibility remains an explicit known failure; five other bindings matched in recorded evidence', () => {
  const issue = manifest.known_compatibility_issues[0];
  assert.equal(issue.status, 'OPEN_KNOWN_FAILURE');
  assert.equal(issue.native_compatibility_pass_claimed, false);
  assert.equal(issue.seal_modified, false);
  assert.equal(evidence.native_compatibility.status, 'FAIL');
  assert.equal(evidence.native_compatibility.original_verifier_error, 'PINNED_CONTEXT_OR_CLI_CHANGED');
  assert.equal(evidence.native_compatibility.known_issue, 'LEGACY_CODEX_CLI_HASH_MISMATCH');
  assert.deepEqual(evidence.native_compatibility.mismatching_fields, ['cli_sha256']);
  for (const [field, binding] of Object.entries(evidence.native_compatibility.binding_fields)) {
    assert.equal(binding.matches, field !== 'cli_sha256');
    assert.equal(binding.expected, issue.expected_binding[field]);
  }
  assert.equal(evidence.native_compatibility.binding_fields.cli_sha256.observed, issue.observed_cli_sha256);
  assert.equal(evidence.native_compatibility_is_repaired, false);
  assert.equal(evidence.legacy_verify_exit_code, 2);
});

test('recorded external replay matches saved results and the selected before/after fingerprint', () => {
  assert.equal(evidence.external_replay.status, 'PASS');
  assert.equal(evidence.external_replay.completed_days, 14);
  assert.equal(evidence.external_replay.final_nav_cents, '979114');
  assert.equal(evidence.selected_anchor_count, manifest.selected_anchors.length);
  assert.equal(evidence.before_fingerprint, evidence.after_fingerprint);
  assert.equal(evidence.legacy_assets_unchanged, true);
  assert.equal(evidence.external_replay.read_only_guard, 'PYTHON_AUDIT_HOOK_NO_WRITES_NETWORK_OR_SUBPROCESSES');
  for (const day of evidence.external_replay.days) {
    assert.equal(day.daily_rows_match, true);
    assert.equal(day.snapshot_matches, true);
    assert.equal(day.independent_legacy_reconcile_matches, true);
  }
});

test('anchor verification fails modified bytes and rejects path traversal in isolated synthetic sandbox', async () => {
  const temporary = await mkdtemp(path.join(tmpdir(), 'p0-legacy-anchors-'));
  try {
    await mkdir(path.join(temporary, 'sample'));
    await writeFile(path.join(temporary, 'sample/evidence.json'), '{}');
    const changed = await verifyAnchors({ selected_anchors: [{ path: 'sample/evidence.json', sha256: '0'.repeat(64), bytes: 2 }] }, temporary);
    assert.equal(changed.status, 'FAIL');
    assert.equal(changed.failures.length, 1);
    await assert.rejects(() => containedFile(temporary, '../escape'), error => error.code === 'LEGACY_PATH_ESCAPE');
  } finally {
    await rm(temporary, { recursive: true, force: true });
  }
});

test('optional external read-only V5 replay (requires explicitly supplied legacy host assets)', { skip: process.env.RUN_LEGACY_EXTERNAL_TESTS !== '1' }, async () => {
  const result = await replayLegacy();
  assert.equal(result.replay_status, 'PASS');
  assert.equal(result.legacy_assets_unchanged, true);
  assert.equal(result.native_compatibility.status, 'FAIL');
  assert.equal(result.native_compatibility.known_issue, 'LEGACY_CODEX_CLI_HASH_MISMATCH');
});
