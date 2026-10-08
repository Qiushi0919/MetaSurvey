import { readFile, realpath } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifyLegacyIntegerSnapshot } from '../src/baseline/ledger.mjs';

export const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const legacyWorkspaceRoot = path.resolve(repoRoot,process.env.LEGACY_ASSET_ROOT || '..');
export const manifestPath = path.join(repoRoot, 'legacy/asset-manifest.v1.json');
export const fixturePath = path.join(repoRoot, 'tests/fixtures/legacy/v5-fourteen-days.v1.json');
const execute = promisify(execFile);

function fail(code, details) {
  const error = new Error(details || code);
  error.code = code;
  throw error;
}
const digestBytes = bytes => createHash('sha256').update(bytes).digest('hex');
export const readJson = async file => JSON.parse(await readFile(file, 'utf8'));

export async function containedFile(workspace, relative) {
  if (typeof relative !== 'string' || path.isAbsolute(relative) || relative.split(/[\\/]/).includes('..')) fail('LEGACY_PATH_ESCAPE');
  const root = await realpath(workspace);
  const result = await realpath(path.join(root, relative));
  if (!result.startsWith(root + path.sep)) fail('LEGACY_PATH_ESCAPE');
  return result;
}

export async function fingerprintAnchors(manifest, workspace = legacyWorkspaceRoot) {
  const rows = [];
  for (const entry of manifest.selected_anchors) {
    const file = await containedFile(workspace, entry.path);
    const bytes = await readFile(file);
    rows.push({ path: entry.path, sha256: digestBytes(bytes), bytes: bytes.length });
  }
  rows.sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0);
  return { fingerprint: digestBytes(Buffer.from(JSON.stringify(rows))), anchors: rows };
}

export async function verifyAnchors(manifest, workspace = legacyWorkspaceRoot) {
  const observed = await fingerprintAnchors(manifest, workspace);
  const expected = new Map(manifest.selected_anchors.map(entry => [entry.path, entry]));
  const failures = observed.anchors.filter(entry => entry.sha256 !== expected.get(entry.path)?.sha256 || entry.bytes !== expected.get(entry.path)?.bytes);
  if (expected.size !== manifest.selected_anchors.length) fail('DUPLICATE_LEGACY_ANCHOR');
  return { status: failures.length ? 'FAIL' : 'PASS', selected_anchor_count: observed.anchors.length, fingerprint: observed.fingerprint, failures };
}

function integer(value) {
  if (Number.isSafeInteger(value)) return BigInt(value);
  if (typeof value === 'string' && /^(?:0|-?[1-9][0-9]{0,37})$/.test(value)) return BigInt(value);
  fail('LEGACY_UNSAFE_INTEGER');
}

function rateFraction(rate) {
  if (typeof rate !== 'string' || !/^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(rate)) fail('LEGACY_FEE_PROFILE_INVALID');
  const [whole, tail = ''] = rate.split('.');
  return [BigInt(whole + tail), 10n ** BigInt(tail.length)];
}

function rateFee(gross, rate) {
  const [numerator, denominator] = rateFraction(rate);
  return (2n * gross * numerator + denominator) / (2n * denominator);
}

export function legacyFinancialRows(rows) {
  return rows.filter(row => {
    if (row.type === 'UNFILLED') {
      if (typeof row.reason !== 'string' || !row.reason || ['cash_delta', 'gross_cents', 'fees'].some(field => Object.hasOwn(row, field))) fail('LEGACY_INVALID_UNFILLED');
      return false;
    }
    if (!['TRADE', 'CASH_ACTION'].includes(row.type)) fail('LEGACY_UNSUPPORTED_ENTRY');
    return true;
  });
}

/** Explicit historical profile only, independent integer fee calculation, never a broker default. */
export function checkLegacyFees(row, profile) {
  if (profile.provenance !== 'LEGACY_FIXTURE_NOT_PRODUCTION' || profile.commission_scope !== 'PER_LEGACY_TRADE_ROW') fail('LEGACY_FEE_PROFILE_INVALID');
  const gross = integer(row.gross_cents);
  const calculated = rateFee(gross, profile.commission_rate);
  const minimum = integer(profile.commission_min_cents);
  const commission = calculated > minimum ? calculated : minimum;
  const rules = profile.stamp_sell_rates.filter(rule => rule.effective_from <= row.day).sort((a, b) => a.effective_from < b.effective_from ? -1 : 1);
  if (!rules.length) fail('LEGACY_FEE_PROFILE_INVALID');
  const expected = {
    commission, transfer: rateFee(gross, profile.transfer_rate),
    stamp: row.side === 'SELL' ? rateFee(gross, rules.at(-1).rate) : 0n,
  };
  if (JSON.stringify(Object.keys(row.fees).sort()) !== JSON.stringify(Object.keys(expected).sort())) fail('LEGACY_FEE_COMPONENT_MISMATCH');
  for (const [name, value] of Object.entries(expected)) if (integer(row.fees[name]) !== value) fail('LEGACY_FEE_MISMATCH', `${row.day} ${row.symbol} ${name}`);
  return Object.values(expected).reduce((sum, fee) => sum + fee, 0n);
}

export function verifyPortableFixture(fixture) {
  if (fixture.provenance !== 'LEGACY_FIXTURE_NOT_PRODUCTION' || fixture.experiment_namespace !== 'LEGACY_EXPERIMENT:sector-swing40-v5' || fixture.target_strategy_mapping !== null) fail('LEGACY_STRATEGY_MAPPING_FORBIDDEN');
  const cumulativeRows = [];
  const results = [];
  let fees = 0n;
  let trades = 0;
  let completedRounds = 0;
  let unfilled = 0;
  let previousDay = '';
  for (const day of fixture.days) {
    if (day.day <= previousDay || day.snapshot.day !== day.day || day.snapshot.frozen_hash !== day.frozen_hash) fail('LEGACY_DAY_BINDING_MISMATCH');
    if (day.rows.some(row => row.day !== day.day)) fail('LEGACY_DAY_BINDING_MISMATCH');
    const financial = legacyFinancialRows(day.rows);
    unfilled += day.rows.length - financial.length;
    for (const row of financial) {
      if (row.type === 'TRADE') {
        fees += checkLegacyFees(row, fixture.legacy_fee_profile);
        trades++;
        if (row.side === 'SELL') completedRounds++;
        if (row.fill_assumption !== 'daily_proxy_conditional_fill_not_observed_auction') fail('LEGACY_PROXY_ASSUMPTION_CHANGED');
      }
    }
    cumulativeRows.push(...financial);
    const verified = verifyLegacyIntegerSnapshot({ opening_cash_cents: fixture.opening_cash_cents, rows: cumulativeRows, snapshot: day.snapshot });
    if (integer(day.saved_reconciliation.cash_cents).toString() !== verified.cash_cents || integer(day.saved_reconciliation.nav_cents).toString() !== verified.nav_cents || integer(day.saved_reconciliation.fees_cents) !== fees) fail('LEGACY_SAVED_RECONCILIATION_MISMATCH');
    results.push({ day: day.day, cash_cents: verified.cash_cents, nav_cents: verified.nav_cents });
    previousDay = day.day;
  }
  const last = results.at(-1);
  const expected = fixture.expected;
  if (!last || results.length !== expected.completed_days || trades !== expected.trade_rows || completedRounds !== expected.completed_rounds || fees.toString() !== expected.fees_cents || last.cash_cents !== expected.final_cash_cents || last.nav_cents !== expected.final_nav_cents || (integer(last.nav_cents) - integer(fixture.opening_cash_cents)).toString() !== expected.net_pnl_cents || Object.keys(fixture.days.at(-1).snapshot.positions).length !== 0) fail('LEGACY_EXPECTED_RESULT_MISMATCH');
  return { status: 'PASS', provenance: fixture.provenance, completed_days: results.length, trade_rows: trades, completed_rounds: completedRounds, unfilled_rows_preserved: unfilled, fees_cents: fees.toString(), final_cash_cents: last.cash_cents, final_nav_cents: last.nav_cents, net_pnl_cents: expected.net_pnl_cents, days: results };
}

export async function verifyFixtureHash(manifest) {
  const observed = digestBytes(await readFile(fixturePath));
  if (observed !== manifest.portable_fixture.sha256) fail('PORTABLE_FIXTURE_HASH_MISMATCH');
  return observed;
}

export async function runExternalLegacy(mode, workspace = legacyWorkspaceRoot) {
  if (!['replay', 'bindings'].includes(mode)) fail('UNKNOWN_LEGACY_ADAPTER_MODE');
  const python = process.env.LEGACY_PYTHON || '/Users/qiushi/Library/Application Support/InvestmentResearchV2/venv/bin/python';
  const { stdout, stderr } = await execute(python, ['-B', path.join(repoRoot, 'adapters/legacy-readonly.py'), '--workspace-root', workspace, '--mode', mode, '--fixture', fixturePath], {
    cwd: repoRoot, timeout: 60000, maxBuffer: 2 * 1024 * 1024,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  });
  if (stderr.trim()) fail('LEGACY_ADAPTER_STDERR', stderr.trim());
  return JSON.parse(stdout);
}
