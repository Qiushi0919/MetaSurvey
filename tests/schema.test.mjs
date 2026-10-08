import test, { before, after } from 'node:test';
import assert from 'node:assert/strict';
import { PGlite } from '@electric-sql/pglite';
import { mkdtemp, readdir, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { migrate, defaultMigrationDirectory } from '../src/baseline/migrate.mjs';

// All amounts, account IDs, costs and records here are SYNTHETIC schema fixtures.
// They are deliberately tiny integer boundaries, never production defaults.
const hash = char => `sha256:${char.repeat(64)}`;
const t0 = '2020-01-03T01:00:00Z';
const cutoff = '2020-01-02T07:00:00Z';
const expiry = '2020-01-04T01:00:00Z';
const orderTime = '2020-01-03T02:00:00Z';
const envelope = (overrides = {}) => ({
  object_version: 1, contract_version: '1.0.0', business_timezone: 'Asia/Shanghai',
  event_time: t0, published_at: null, published_at_precision: 'NOT_APPLICABLE',
  published_at_not_applicable: true, available_at: t0, retrieved_at: t0,
  source_id: 'synthetic', source_version: 'fixture-v1', source_hash: hash('a'),
  payload_hash: hash('b'), trace_id: 'SYNTHETIC-schema-fixture', reason_codes: [],
  ...overrides,
});
const published = at => ({ event_time: at, published_at: at, published_at_precision: 'SECOND',
  published_at_not_applicable: false, available_at: at, retrieved_at: at });
let db;
const migrationNames = (await readdir(defaultMigrationDirectory)).filter(n => /^\d{3}_[a-z0-9_]+\.sql$/.test(n)).sort();
async function insert(table, row, { common = true } = {}) {
  const data = common ? envelope(row) : row;
  const columns = Object.keys(data);
  const parameters = Object.values(data).map(v => v !== null && typeof v === 'object' ? JSON.stringify(v) : v);
  return db.query(`INSERT INTO ${table} (${columns.join(',')}) VALUES (${columns.map((_, i) => `$${i + 1}`).join(',')})`, parameters);
}
async function expectReject(fn, pattern) {
  await assert.rejects(fn, pattern);
}

async function seedChain({ suffix = 'dev', account_id = 'synthetic-dev', mode = 'DEV', strategy_id = 'CORE_40', signalOverrides = {}, cardOverrides = {} } = {}) {
  const refs = { account_id, mode, strategy_id };
  const cardId = suffix==='dev' ? 'card-core' : `card-${suffix}`;
  if (suffix!=='dev') {
    const base = (await db.query("SELECT * FROM research_cards WHERE object_id='card-core' AND object_version=1")).rows[0];
    await insert('research_cards', { ...base, object_id: cardId, ...refs, ...cardOverrides });
  }
  await insert('cost_estimates', {
    object_id: `cost-${suffix}`, ...refs, security_id: 'synthetic-security', side: 'BUY', quantity: 10, price: '1',
    config_id: 'cfg-cost', config_version: 1, config_hash: hash('c'),
    commission_cents: '1', tax_cents: '0', other_fees_cents: '1', total_explicit_cents: '2',
    slippage_model: { kind: 'SYNTHETIC' }, simulation_assumptions: true,
  });
  await insert('account_snapshots', {
    object_id: `account-snapshot-${suffix}`, account_id, mode,
    cash_cents: '10000', equity_cents: '10000', exposure_cents: '0', ledger_sequence: 0, reconciled: true,
  });
  await insert('signal_events', {
    object_id: `signal-${suffix}`, ...refs, security_id: 'synthetic-security',
    card_id: cardId, card_version: 1, card_hash: hash('b'),
    state: 'TRIGGERED', rule_id: 'SYNTHETIC', rule_version: 'fixture-v1',
    dedupe_key: `${strategy_id}:synthetic:${suffix}`, triggered_at: t0, expires_at: expiry, ...signalOverrides,
  });
  await insert('order_drafts', {
    object_id: `draft-${suffix}`, ...refs, security_id: 'synthetic-security',
    signal_id: `signal-${suffix}`, signal_version: 1, signal_hash: hash('b'),
    card_id: cardId, card_version: 1, card_hash: hash('b'),
    side: 'BUY', quantity: 10, limit_price: '1', cost_id: `cost-${suffix}`, cost_version: 1, cost_hash: hash('b'),
    account_snapshot_id: `account-snapshot-${suffix}`, account_snapshot_version: 1, account_snapshot_hash: hash('b'),
    target_fingerprint: hash('d'), expires_at: expiry,
  });
  for (const [phase, id] of [['DECISION_APPROVAL', `decision-${suffix}`], ['FINAL_ORDER_CONFIRMATION', `final-${suffix}`]]) {
    await insert('approvals', {
      object_id: id, ...refs, phase, decision: 'USER_APPROVED', actor_kind: 'HUMAN_USER', actor_id: 'synthetic-human',
      draft_id: `draft-${suffix}`, draft_version: 1, draft_hash: hash('b'), target_fingerprint: hash('d'),
      expires_at: expiry, auth_context_hash: hash('e'),
    });
  }
  return {
    object_id: `order-${suffix}`, client_order_id: `client-${suffix}`, ...refs,
    draft_id: `draft-${suffix}`, draft_version: 1, draft_hash: hash('b'), target_fingerprint: hash('d'),
    decision_approval_id: `decision-${suffix}`, decision_approval_version: 1,
    decision_phase: 'DECISION_APPROVAL', decision_value: 'USER_APPROVED',
    final_approval_id: `final-${suffix}`, final_approval_version: 1,
    final_phase: 'FINAL_ORDER_CONFIRMATION', final_value: 'USER_APPROVED', state: 'PREPARED',
    event_time: orderTime, available_at: orderTime, retrieved_at: orderTime,
  };
}
async function claim(order, family = 'sim') {
  return insert(`order_claims_${family}`, { account_id: order.account_id, mode: order.mode,
    client_order_id: order.client_order_id, order_id: order.object_id, strategy_id: order.strategy_id }, { common: false });
}
let baseOrder;

before(async () => {
  db = new PGlite();
  await migrate(db);
  await insert('data_sources', { source_id: 'synthetic', provider: 'SYNTHETIC_FIXTURE',
    source_class: 'SYNTHETIC', license_type: 'SYNTHETIC', allowed_use: ['TEST_ONLY'],
    retention_policy: 'FIXTURE_ONLY', redistribution_allowed: false, rate_limit: {}, terms_version: 'fixture-v1' });
  await insert('securities', { security_id: 'synthetic-security', symbol: 'SYNTH', exchange: 'SSE' });
  await insert('security_master', { security_id: 'synthetic-security', effective_from: '2000-01-01T00:00:00Z',
    effective_to: null, name: 'SYNTHETIC security', board: 'SYNTHETIC', lot_size: 1,
    status: 'ACTIVE', st_flag: false, list_date: '2000-01-01', delist_date: null, trading_rules: { synthetic: true } });
  await insert('config_versions', { object_id: 'cfg-cost', strategy_id: null, config_type: 'COST',
    configuration: { fixture: true, actual_broker_rate: 'UNSET_REQUIRED' }, config_hash: hash('c'),
    parameter_status: 'SYNTHETIC_FIXTURE', published_by: 'schema-test' });
  for (const [account_id, mode] of [['synthetic-dev','DEV'], ['synthetic-dev-other','DEV'], ['synthetic-paper','PAPER'], ['synthetic-prod-record','PROD']]) {
    await insert('accounts', { account_id, mode, identity_status: 'SYNTHETIC_FIXTURE',
      broker_ref: 'UNSET_REQUIRED', currency: 'CNY', production_authorized: false });
  }
  await insert('snapshot_manifests', { object_id: 'snapshot', decision_cutoff: cutoff, frozen_at: t0,
    data_hash: hash('f'), content_hash: hash('b'), visibility_basis: 'OBSERVED_AS_OF', fixture_kind: 'SYNTHETIC', manifest: {} });
  await insert('research_cards', { object_id: 'card-core', strategy_id: 'CORE_40', account_id: 'synthetic-dev', mode: 'DEV', security_id: 'synthetic-security',
    grade: 'A', action: 'WAIT', decision_cutoff: cutoff, expires_at: expiry,
    snapshot_id: 'snapshot', snapshot_version: 1, snapshot_hash: hash('b'), rule_version: 'fixture-v1',
    layers: { synthetic: true }, invalidation_rules: ['fixture-only'], probability_calibrated: false });
  baseOrder = await seedChain();
  await claim(baseOrder);
  await insert('orders_sim', baseOrder);
});
after(async () => db?.close());

test('empty database -> full PostgreSQL V1; second migration run verifies checksums and changes nothing', async () => {
  const fresh = new PGlite();
  try {
    assert.deepEqual((await migrate(fresh)).applied, migrationNames);
    assert.deepEqual(await migrate(fresh), { schemaVersion: migrationNames.length, applied: [], verified: migrationNames });
    const tables = (await fresh.query("SELECT tablename FROM pg_tables WHERE schemaname='public'")).rows.map(r => r.tablename);
    for (const name of ['financials','bars_1d','bars_1m','orders_sim','orders_real','fills_sim','fills_real',
      'positions_sim','positions_real','ledger_sim','ledger_real','staging_imports','legacy_asset_registry','audit_log']) assert.ok(tables.includes(name), name);
    assert.equal((await fresh.query("SHOW TIMEZONE")).rows[0].TimeZone, 'UTC');
  } finally { await fresh.close(); }
});

test('failed migration is transactional even on an empty database', async () => {
  const directory = await mkdtemp(path.join(tmpdir(), 'ashare-schema-rollback-'));
  const fresh = new PGlite();
  try {
    await writeFile(path.join(directory, '001_failure.sql'), 'CREATE TABLE partial_build(id INTEGER); SELECT * FROM nonexistent_table;');
    await assert.rejects(migrate(fresh, { directory }), /nonexistent_table/);
    assert.equal((await fresh.query("SELECT count(*) FROM pg_tables WHERE schemaname='public'")).rows[0].count, 0);
  } finally { await fresh.close(); await rm(directory, { recursive: true, force: true }); }
});

test('altering a previously applied migration rejects instead of resealing history', async () => {
  const directory = await mkdtemp(path.join(tmpdir(), 'ashare-schema-checksum-'));
  try {
    for (const name of migrationNames) {
      const sql = await readFile(path.join(defaultMigrationDirectory,name),'utf8');
      await writeFile(path.join(directory,name), name==='001_schema_v1.sql' ? `${sql}\n-- changed bytes\n` : sql);
    }
    await assert.rejects(migrate(db, { directory }), /MIGRATION_CHECKSUM_OR_HISTORY_MISMATCH/);
    assert.equal((await db.query('SELECT count(*) FROM schema_migrations')).rows[0].count, migrationNames.length);
    await writeFile(path.join(directory, `${String(migrationNames.length+2).padStart(3,'0')}_gap.sql`), 'SELECT 1;');
    await assert.rejects(migrate(db, { directory }), /MIGRATION_SEQUENCE_GAP/);
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test('raw and adjusted prices coexist, traced adjustment revisions cannot overwrite either', async () => {
  await insert('adjustment_versions', { object_id: 'adjustment', security_id: 'synthetic-security',
    method: 'SYNTHETIC', action_refs: [], decision_cutoff: cutoff, factors_hash: hash('f'), visibility_basis: 'OBSERVED_AS_OF' });
  const bar = { object_id: 'bar-raw', security_id: 'synthetic-security', security_version: 1,
    trade_date: '2020-01-02', price_basis: 'RAW', adjustment_id: null, adjustment_version: null,
    open: '10', high: '11', low: '9', close: '10', preclose: '10', volume: 10, amount_cents: '10000' };
  await insert('bars_1d', bar);
  await insert('bars_1d', { ...bar, object_id: 'bar-adjusted', price_basis: 'ADJUSTED', adjustment_id: 'adjustment', adjustment_version: 1,
    open: '5', high: '5.5', low: '4.5', close: '5', preclose: '5' });
  const rows = (await db.query('SELECT price_basis,close::text FROM bars_1d ORDER BY price_basis')).rows;
  assert.deepEqual(rows, [{ price_basis: 'ADJUSTED', close: '5' }, { price_basis: 'RAW', close: '10' }]);
  await expectReject(() => insert('bars_1d', { ...bar, object_id: 'duplicate-raw' }), /unique constraint/);
  await expectReject(() => insert('bars_1d', { ...bar, object_id: 'raw-with-adjustment', adjustment_id: 'adjustment', adjustment_version: 1 }), /check constraint/);
  await expectReject(() => db.query("UPDATE bars_1d SET close=8 WHERE object_id='bar-raw'"), /APPEND_ONLY_HISTORY/);
  await expectReject(() => insert('bars_1d', { ...bar, object_id: 'broken-ohlc', object_version: 2, high: '8' }), /check constraint/);
  await expectReject(() => insert('bars_1d', { ...bar, object_id: 'broken-adjustment', price_basis: 'ADJUSTED', adjustment_id: 'absent', adjustment_version: 1 }), /foreign key/);
});

test('financial restatements preserve old versions; PIT blocks future revisions and later retrieval', async () => {
  for (const [v, at] of [[1,'2019-08-01T01:00:00Z'], [2,'2020-02-01T01:00:00Z']]) {
    await insert('announcements', { object_id: 'financial-announcement', object_version: v,
      security_id: 'synthetic-security', title: `SYNTHETIC revision ${v}`, raw_uri: 'fixture://announcement', raw_hash: hash('a'), ...published(at) });
    await insert('financials', { object_id: 'financial', object_version: v, security_id: 'synthetic-security', period: '2019-06-30',
      statement_type: 'INCOME', announcement_id: 'financial-announcement', announcement_version: v,
      revision_kind: v===1 ? 'ORIGINAL' : 'RESTATEMENT', currency: 'CNY', unit: 'CNY_CENTS',
      values_cents: { revenue: v===1 ? '12345' : '54321' }, ...published(at) });
  }
  const asOf = async (at, basis = 'OBSERVED_AS_OF') => (await db.query('SELECT object_version,values_cents FROM financials_as_of($1,$2)', [at,basis])).rows;
  assert.deepEqual(await asOf('2020-01-01T00:00:00Z'), [{ object_version: 1, values_cents: { revenue: '12345' } }]);
  assert.deepEqual(await asOf('2020-03-01T00:00:00Z'), [{ object_version: 2, values_cents: { revenue: '54321' } }]);
  assert.equal((await db.query('SELECT count(*) FROM financials')).rows[0].count, 2);
  await expectReject(() => db.query("UPDATE financials SET values_cents='{\"revenue\":\"0\"}'"), /APPEND_ONLY_HISTORY/);
  await insert('announcements', { object_id: 'archive-announcement', security_id: 'synthetic-security',
    title: 'SYNTHETIC archived report', raw_uri: 'fixture://archive', raw_hash: hash('a'),
    ...published('2019-08-01T01:00:00Z'), retrieved_at: '2020-10-01T00:00:00Z' });
  await insert('financials', { object_id: 'archive-financial', security_id: 'synthetic-security', period: '2019-03-31',
    statement_type: 'INCOME', announcement_id: 'archive-announcement', announcement_version: 1,
    revision_kind: 'ORIGINAL', currency: 'CNY', unit: 'CNY_CENTS', values_cents: { revenue: '1' },
    ...published('2019-08-01T01:00:00Z'), retrieved_at: '2020-10-01T00:00:00Z' });
  assert.equal((await asOf('2020-01-01T00:00:00Z')).length, 1);
  assert.equal((await asOf('2020-01-01T00:00:00Z','PUBLIC_AS_OF')).length, 2);
  await expectReject(() => asOf(t0,'ASSUME_LATEST'), /UNKNOWN_VISIBILITY_BASIS/);
  await expectReject(() => insert('financials', { object_id: 'bad-money-financial', security_id: 'synthetic-security', period: '2019-12-31',
    statement_type: 'BAD', announcement_id: 'archive-announcement', announcement_version: 1, revision_kind: 'ORIGINAL',
    currency: 'CNY', unit: 'CNY_CENTS', values_cents: { revenue: 1.5 }, ...published(t0) }), /FINANCIAL_MONEY_INTEGER_STRING_REQUIRED/);
});

test('four clocks use UTC instants, declared publication precision, and explicit non-applicability', async () => {
  await insert('news_events', { object_id: 'tz-news', entity: 'SYNTHETIC', event_type: 'TEST', summary: 'fixture',
    sentiment: null, confidence: null, raw_uri: 'fixture://news', raw_hash: hash('a'),
    ...published('2020-01-03T09:00:00+08:00') });
  assert.equal((await db.query("SELECT event_time=TIMESTAMPTZ '2020-01-03T01:00:00Z' AS same_instant FROM news_events WHERE object_id='tz-news'")).rows[0].same_instant, true);
  await expectReject(() => insert('news_events', { object_id: 'null-published-news', entity: 'SYNTHETIC', event_type: 'TEST', summary: 'fixture',
    sentiment: null, confidence: null, raw_uri: 'fixture://news', raw_hash: hash('a') }), /check constraint/);
  await expectReject(() => insert('securities', { security_id: 'bad-publication', symbol: 'BAD', exchange: 'SSE',
    published_at: t0 }), /check constraint/);
  await expectReject(() => insert('securities', { security_id: 'bad-clock', symbol: 'BAD', exchange: 'SSE',
    ...published(t0), available_at: '2020-01-02T00:00:00Z' }), /check constraint/);
});

test('freeze-before-reveal and future-data isolation are enforced for snapshot members', async () => {
  for (const [id, at, retrieval] of [['past-disclosure','2020-01-02T06:59:59Z','2020-01-02T06:59:59Z'],
    ['future-disclosure','2020-01-02T07:00:01Z','2020-01-02T07:00:01Z'], ['archive-disclosure','2020-01-02T06:59:59Z',t0],
    ['withheld-disclosure','2020-01-04T00:00:00Z','2020-01-04T00:00:00Z']]) {
    await insert('announcements', { object_id: id, security_id: 'synthetic-security', title: 'SYNTHETIC snapshot disclosure',
      raw_uri: `fixture://${id}`, raw_hash: hash('a'), ...published(at), retrieved_at: retrieval });
  }
  const member = { object_id: 'past-input', snapshot_id: 'snapshot', snapshot_version: 1, dataset: 'announcements',
    dataset_object_id: 'past-disclosure', dataset_object_version: 1, dataset_hash: hash('b'),
    entry_role: 'DECISION_INPUT', reveal_after: null, ...published('2020-01-02T06:59:59Z') };
  await insert('snapshot_entries', member);
  await expectReject(() => insert('snapshot_entries', { ...member, object_id: 'future-input', dataset_object_id: 'future-disclosure', ...published('2020-01-02T07:00:01Z') }), /PIT_FUTURE_DATA_BLOCKED/);
  await expectReject(() => insert('snapshot_entries', { ...member, object_id: 'late-retrieval', dataset_object_id: 'archive-disclosure', retrieved_at: t0 }), /PIT_FUTURE_DATA_BLOCKED/);
  await expectReject(() => insert('snapshot_entries', { ...member, object_id: 'early-reveal', entry_role: 'FUTURE_REVEAL', reveal_after: t0 }), /FREEZE_BEFORE_REVEAL_REQUIRED/);
  await insert('snapshot_entries', { ...member, object_id: 'withheld-future', dataset_object_id: 'withheld-disclosure', entry_role: 'FUTURE_REVEAL', reveal_after: '2020-01-03T01:00:01Z', ...published('2020-01-04T00:00:00Z') });
  await expectReject(() => db.query('DELETE FROM snapshot_entries'), /APPEND_ONLY_HISTORY/);
});

test('Decimal/int cents and bounded price precision reject invalid inputs without rounding', async () => {
  assert.equal((await db.query("SELECT '99999999999999999999999999999999999999'::money_cents::text AS amount")).rows[0].amount,
    '99999999999999999999999999999999999999');
  for (const amount of ['1.1', '100000000000000000000000000000000000000']) await expectReject(() => db.query('SELECT $1::money_cents',[amount]), /check constraint/);
  await expectReject(() => db.query("SELECT '1.0000001'::price_yuan"), /check constraint/);
  await expectReject(() => db.query("SELECT '0.00000000001'::decimal_rate"), /check constraint/);
  await expectReject(() => db.query("SELECT 'sha256:incorrect'::sha256_digest"), /check constraint/);
  await expectReject(() => db.query('SELECT 0::positive_version'), /check constraint/);
});

test('account/mode/strategy/version crossover and research-only signals are rejected', async () => {
  const signal = { object_id: 'bad-signal', account_id: 'synthetic-dev', mode: 'DEV', strategy_id: 'CORE_40',
    security_id: 'synthetic-security', card_id: 'card-core', card_version: 1, card_hash: hash('b'),
    state: 'TRIGGERED', rule_id: 'fixture', rule_version: 'fixture-v1', dedupe_key: 'bad', triggered_at: t0, expires_at: expiry };
  for (const override of [{ strategy_id: 'EVENT_3' }, { strategy_id: 'RESEARCH_6_18M' }, { mode: 'PAPER' }, { card_version: 9 }, { card_hash: hash('c') }]) {
    await expectReject(() => insert('signal_events', { ...signal, ...override }), /foreign key|check constraint/);
  }
  const draft = (await db.query("SELECT * FROM order_drafts WHERE object_id='draft-dev'")).rows[0];
  for (const override of [{ account_id: 'synthetic-dev-other' }, { mode: 'PAPER' }, { strategy_id: 'EVENT_3' },
    { signal_version: 9 }, { quantity: 11 }, { limit_price: '1.01' }, { cost_hash: hash('c') }, { account_snapshot_hash: hash('c') }]) {
    await expectReject(() => insert('order_drafts', { ...draft, object_id: 'bad-draft', ...override }), /foreign key/);
  }
});

test('LLM APPROVE cannot be a user Approval; both human phases bind the same immutable draft', async () => {
  const approval = (await db.query("SELECT * FROM approvals WHERE object_id='decision-dev'")).rows[0];
  await expectReject(() => insert('approvals', { ...approval, object_id: 'llm-approval', actor_kind: 'LLM' }), /check constraint/);
  await expectReject(() => insert('orders_sim', { ...baseOrder, object_version: 2, final_approval_id: 'decision-dev' }), /check constraint|foreign key/);
  await expectReject(() => insert('orders_sim', { ...baseOrder, object_version: 2, target_fingerprint: hash('c') }), /foreign key/);
  await expectReject(() => insert('orders_sim', { ...baseOrder, object_version: 2, event_time: expiry, available_at: expiry, retrieved_at: expiry }), /EXPIRED_OR_FUTURE_ORDER_CHAIN/);
  await expectReject(() => db.query("UPDATE approvals SET actor_id='different'"), /APPEND_ONLY_HISTORY/);
});

test('client-order claim prevents duplicate orders while allowing immutable state revisions', async () => {
  await expectReject(() => insert('order_claims_sim', { account_id: baseOrder.account_id, mode: baseOrder.mode,
    client_order_id: baseOrder.client_order_id, order_id: 'different-order', strategy_id: 'EVENT_3' }, { common: false }), /unique constraint/);
  await insert('orders_sim', { ...baseOrder, object_version: 2, state: 'SUBMITTED' });
  assert.equal((await db.query("SELECT count(*) FROM orders_sim WHERE object_id='order-dev'")).rows[0].count, 2);
  await expectReject(() => insert('orders_sim', { ...baseOrder, object_id: 'different-order' }), /foreign key/);
});

test('simulated and real transaction families enforce modes and account/strategy fill attribution', async () => {
  const real = await seedChain({ suffix: 'real', account_id: 'synthetic-prod-record', mode: 'PROD' });
  await claim(real, 'real'); await insert('orders_real', real);
  await expectReject(() => insert('orders_sim', real), /check constraint/);
  await expectReject(() => insert('orders_real', baseOrder), /check constraint/);
  const fill = { object_id: 'fill-dev', account_id: baseOrder.account_id, mode: baseOrder.mode, strategy_id: baseOrder.strategy_id,
    order_id: baseOrder.object_id, order_version: 1, broker_fill_id: 'synthetic-fill-1', trade_date: '2020-01-03', quantity: 10,
    price: '1', notional_cents: '1000', fee_cents: '2', fill_observation: 'SYNTHETIC' };
  await insert('fills_sim', fill);
  for (const override of [{ account_id: 'synthetic-dev-other' }, { strategy_id: 'EVENT_3' }, { order_version: 9 }, { mode: 'PAPER' }]) {
    await expectReject(() => insert('fills_sim', { ...fill, object_id: 'bad-fill', broker_fill_id: 'bad-fill-id', ...override }), /foreign key/);
  }
  await expectReject(() => insert('fills_real', fill), /check constraint/);
  await expectReject(() => insert('fills_sim', { ...fill, object_id: 'duplicate-fill' }), /unique constraint/);
  const ledger = { object_id: 'ledger-1', account_id: baseOrder.account_id, mode: baseOrder.mode, strategy_id: baseOrder.strategy_id,
    account_sequence: 1, entry_type: 'BUY', amount_cents: '-1002', balance_cents: '8998',
    fill_id: 'fill-dev', fill_version: 1, previous_entry_hash: null };
  await insert('ledger_sim', ledger);
  await expectReject(() => insert('ledger_sim', { ...ledger, object_id: 'ledger-2', strategy_id: 'EVENT_3', account_sequence: 2 }), /foreign key/);
  await expectReject(() => insert('ledger_sim', { ...ledger, object_id: 'ledger-duplicate-sequence', fill_id: null, fill_version: null }), /unique constraint/);
  await expectReject(() => db.query('TRUNCATE ledger_sim'), /APPEND_ONLY_HISTORY/);
});

test('superseded card invalidates new orders without rewriting past order history', async () => {
  const old = (await db.query("SELECT * FROM research_cards WHERE object_id='card-core'")).rows[0];
  await insert('research_cards', { ...old, object_version: 2, payload_hash: hash('c'), available_at: '2020-01-03T03:00:00Z', retrieved_at: '2020-01-03T03:00:00Z' });
  await expectReject(() => insert('orders_sim', { ...baseOrder, object_version: 3, event_time: '2020-01-03T04:00:00Z',
    available_at: '2020-01-03T04:00:00Z', retrieved_at: '2020-01-03T04:00:00Z' }), /SUPERSEDED_ORDER_CHAIN/);
  assert.equal((await db.query("SELECT count(*) FROM orders_sim WHERE object_id='order-dev'")).rows[0].count, 2);
});

test('P0 schema never grants production authorization and preserves append-only audit', async () => {
  await expectReject(() => insert('accounts', { account_id: 'illegal-prod', mode: 'PROD', identity_status: 'USER_CONFIRMED',
    broker_ref: 'UNSET_REQUIRED', currency: 'CNY', production_authorized: true }), /check constraint/);
  await insert('audit_log', { object_id: 'audit-1', actor_kind: 'SERVICE', actor_id: 'schema-test', action: 'FIXTURE_INSERT',
    account_id: null, mode: null, strategy_id: null, before_state: null, after_state: { synthetic: true }, previous_event_hash: null });
  await expectReject(() => db.query('DELETE FROM audit_log'), /APPEND_ONLY_HISTORY/);
  assert.equal((await db.query('SELECT count(*) FROM audit_log')).rows[0].count, 1);
});

test('corporate-action factors cannot expose future knowledge or precede factor retrieval', async () => {
  await insert('corp_actions', { object_id: 'future-action', security_id: 'synthetic-security', security_version: 1,
    action_type: 'DIVIDEND', ex_date: '2020-02-01', record_date: null, terms: { synthetic: true } });
  await expectReject(() => insert('adjustment_actions', { object_id: 'future-factor-input', security_id: 'synthetic-security',
    adjustment_id: 'adjustment', adjustment_version: 1, action_id: 'future-action', action_version: 1 }), /PIT_FUTURE_CORPORATE_ACTION_BLOCKED/);
  await insert('adjustment_versions', { object_id: 'future-adjustment', security_id: 'synthetic-security', method: 'SYNTHETIC', action_refs: [],
    decision_cutoff: t0, factors_hash: hash('f'), visibility_basis: 'OBSERVED_AS_OF',
    available_at: '2020-01-03T02:00:00Z', retrieved_at: '2020-01-03T02:00:00Z' });
  await expectReject(() => insert('bars_1d', { object_id: 'early-adjusted-bar', security_id: 'synthetic-security', security_version: 1,
    trade_date: '2020-01-01', price_basis: 'ADJUSTED', adjustment_id: 'future-adjustment', adjustment_version: 1,
    open: '1', high: '1', low: '1', close: '1', preclose: '1', volume: 1, amount_cents: '100' }), /ADJUSTED_BAR_BEFORE_FACTOR/);
});

test('PIT bar revisions are selected after cutoff filtering; future observation times cannot be backdated', async () => {
  const old = (await db.query("SELECT * FROM bars_1d WHERE object_id='bar-raw'")).rows[0];
  assert.equal((await db.query('SELECT count(*) FROM bars_1d_as_of($1)',[cutoff])).rows[0].count, 0);
  assert.equal((await db.query('SELECT count(*) FROM bars_1d_as_of($1)',[t0])).rows[0].count, 2);
  await insert('bars_1d', { ...old, object_version: 2, close: '10.5', available_at: '2020-02-01T01:00:00Z', retrieved_at: '2020-02-01T01:00:00Z' });
  assert.equal((await db.query("SELECT close::text FROM bars_1d_as_of($1) WHERE price_basis='RAW'",[t0])).rows[0].close, '10');
  assert.equal((await db.query("SELECT close::text FROM bars_1d_as_of($1) WHERE price_basis='RAW'",['2020-03-01T01:00:00Z'])).rows[0].close, '10.5');
  await expectReject(() => insert('bars_1d', { ...old, object_id: 'backdated-future-bar', object_version: 3,
    event_time: '2020-02-01T00:00:00Z' }), /check constraint/);
});

test('a later revision cannot move an object across strategy namespaces', async () => {
  const old = (await db.query("SELECT * FROM research_cards WHERE object_id='card-core' AND object_version=1")).rows[0];
  await expectReject(() => insert('research_cards', { ...old, object_version: 3, strategy_id: 'EVENT_3' }), /REVISION_NAMESPACE_CHANGE_BLOCKED/);
});

test('untriggered, invalidated, mismatched-rule, and UNSET grade chains cannot create orders', async () => {
  for (const [suffix, options] of [
    ['watching', { signalOverrides: { state: 'WATCHING', triggered_at: null } }],
    ['invalidated', { signalOverrides: { state: 'INVALIDATED', triggered_at: null } }],
    ['wrong-rule', { signalOverrides: { rule_version: 'DIFFERENT_RULE_VERSION' } }],
    ['unset-grade', { cardOverrides: { grade: 'UNSET_REQUIRED' } }],
  ]) {
    const order = await seedChain({ suffix, ...options });
    await claim(order);
    await expectReject(() => insert('orders_sim', order), /ORDER_SIGNAL_OR_RULE_INVALID/);
  }
  const old = (await db.query("SELECT * FROM signal_events WHERE object_id='signal-dev' AND object_version=1")).rows[0];
  await expectReject(() => insert('signal_events', { ...old, object_id: 'trigger-after-event', triggered_at: '2020-01-03T01:00:01Z' }), /check constraint/);
  await expectReject(() => insert('signal_events', { ...old, object_id: 'trigger-required', triggered_at: null }), /check constraint/);
});

test('snapshot manifests verify typed actual source versions, hashes and clocks before freezing', async () => {
  const future = '2020-02-01T01:00:00Z';
  await insert('announcements', { object_id: 'forgery-future-source', security_id: 'synthetic-security', title: 'SYNTHETIC future title',
    raw_uri: 'fixture://future-forgery', raw_hash: hash('a'), ...published(future) });
  const member = { object_id: 'forged-member', snapshot_id: 'snapshot', snapshot_version: 1, dataset: 'announcements',
    dataset_object_id: 'forgery-future-source', dataset_object_version: 1, dataset_hash: hash('b'),
    entry_role: 'DECISION_INPUT', reveal_after: null, ...published('2020-01-01T01:00:00Z') };
  await expectReject(() => insert('snapshot_entries', member), /SNAPSHOT_MEMBER_PROVENANCE_MISMATCH/);
  await expectReject(() => insert('snapshot_entries', { ...member, ...published(future) }), /PIT_FUTURE_DATA_BLOCKED/);
  await expectReject(() => insert('snapshot_entries', { ...member, dataset: 'nonexistent_untyped_source' }), /SNAPSHOT_DATASET_UNSUPPORTED/);
  await expectReject(() => insert('snapshot_entries', { ...member, dataset_object_version: 9 }), /SNAPSHOT_MEMBER_NOT_FOUND/);
  await expectReject(() => insert('snapshot_entries', { ...member, ...published(future), dataset_hash: hash('c') }), /SNAPSHOT_MEMBER_PROVENANCE_MISMATCH/);
  await expectReject(() => insert('snapshot_entries', { ...member, ...published(future), source_hash: hash('c') }), /SNAPSHOT_MEMBER_PROVENANCE_MISMATCH/);
});

test('financial PIT lineage cannot be retrieved or published before its actual announcement', async () => {
  await insert('announcements', { object_id: 'late-lineage-announcement', security_id: 'synthetic-security', title: 'SYNTHETIC late archive',
    raw_uri: 'fixture://late-lineage', raw_hash: hash('a'), ...published('2020-01-01T01:00:00Z'), retrieved_at: '2020-02-01T01:00:00Z' });
  const financial = { object_id: 'lineage-financial', security_id: 'synthetic-security', period: '2019-12-31', statement_type: 'LINEAGE_FIXTURE',
    announcement_id: 'late-lineage-announcement', announcement_version: 1, revision_kind: 'ORIGINAL',
    currency: 'CNY', unit: 'CNY_CENTS', values_cents: { revenue: '1' }, ...published('2020-01-01T01:00:00Z') };
  await expectReject(() => insert('financials', financial), /FINANCIAL_BEFORE_DISCLOSURE/);
  await expectReject(() => insert('financials', { ...financial, published_at: '2019-12-31T01:00:00Z', retrieved_at: '2020-02-01T01:00:00Z' }), /FINANCIAL_BEFORE_DISCLOSURE/);
  await insert('financials', { ...financial, retrieved_at: '2020-02-01T01:00:00Z' });
  assert.equal((await db.query("SELECT count(*) FROM financials_as_of($1) WHERE object_id='lineage-financial'",['2020-01-15T00:00:00Z'])).rows[0].count, 0);
  assert.equal((await db.query("SELECT count(*) FROM financials_as_of($1,'PUBLIC_AS_OF') WHERE object_id='lineage-financial'",['2020-01-15T00:00:00Z'])).rows[0].count, 1);
});

test('snapshot canonical content_hash and dataset data_hash remain distinct identities', async () => {
  const old = (await db.query("SELECT * FROM research_cards WHERE object_id='card-core' AND object_version=1")).rows[0];
  await expectReject(() => insert('research_cards', { ...old, object_id: 'wrong-snapshot-hash', snapshot_hash: hash('f') }), /foreign key/);
  await expectReject(() => insert('snapshot_manifests', { object_id: 'mismatched-content-hash', decision_cutoff: cutoff, frozen_at: t0,
    data_hash: hash('f'), content_hash: hash('c'), visibility_basis: 'OBSERVED_AS_OF', fixture_kind: 'SYNTHETIC', manifest: {} }), /check constraint/);
  await insert('brain_packets', { object_id: 'initial-brain-packet', strategy_id: 'CORE_40', snapshot_id: 'snapshot', snapshot_version: 1,
    snapshot_hash: hash('b'), decision_cutoff: cutoff, brain_mode: 'MANUAL_EXPORT', request_type: 'INITIAL_RESEARCH', packet: {} });
  await expectReject(() => insert('brain_packets', { object_id: 'old-brain-packet', strategy_id: 'CORE_40', snapshot_id: 'snapshot', snapshot_version: 1,
    snapshot_hash: hash('b'), decision_cutoff: cutoff, brain_mode: 'MANUAL_EXPORT', request_type: 'RESEARCH', packet: {} }), /check constraint/);
});

test('cards bind account/mode and cost estimates bind exact security', async () => {
  const signal = (await db.query("SELECT * FROM signal_events WHERE object_id='signal-dev' AND object_version=1")).rows[0];
  await expectReject(() => insert('signal_events', { ...signal, object_id: 'cross-account-card', account_id: 'synthetic-dev-other' }), /foreign key/);
  await expectReject(() => insert('signal_events', { ...signal, object_id: 'cross-mode-card', account_id: 'synthetic-paper', mode: 'PAPER' }), /foreign key/);
  await insert('securities', { security_id: 'synthetic-other-security', symbol: 'OTHER_SYNTH', exchange: 'SSE' });
  const cost = (await db.query("SELECT * FROM cost_estimates WHERE object_id='cost-dev'")).rows[0];
  await insert('cost_estimates', { ...cost, object_id: 'cost-other-security', security_id: 'synthetic-other-security' });
  const draft = (await db.query("SELECT * FROM order_drafts WHERE object_id='draft-dev'")).rows[0];
  await expectReject(() => insert('order_drafts', { ...draft, object_id: 'cross-security-cost', cost_id: 'cost-other-security' }), /foreign key/);
});

test('positive costs prices and safe integer quantities match wire contract bounds', async () => {
  const cost = (await db.query("SELECT * FROM cost_estimates WHERE object_id='cost-dev'")).rows[0];
  await expectReject(() => insert('cost_estimates', { ...cost, object_id: 'zero-price-cost', price: '0' }), /check constraint/);
  await expectReject(() => insert('cost_estimates', { ...cost, object_id: 'unsafe-quantity-cost', quantity: '9007199254740992' }), /check constraint/);
  await insert('cost_estimates', { ...cost, object_id: 'safe-quantity-boundary', quantity: '9007199254740991' });
  assert.equal((await db.query("SELECT quantity::text FROM cost_estimates WHERE object_id='safe-quantity-boundary'")).rows[0].quantity, '9007199254740991');
  assert.equal((await db.query("SELECT '9999999999.9999999999'::decimal_rate::text AS boundary")).rows[0].boundary, '9999999999.9999999999');
  const approval = (await db.query("SELECT * FROM approvals WHERE object_id='decision-dev'")).rows[0];
  await expectReject(() => insert('approvals', { ...approval, object_id: 'ambiguous-llm-decision', decision: 'APPROVE' }), /check constraint/);
});
