import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {captureSpecs, normalizeCapture, parseSseTerms, tushareAdapter} from '../src/providers.mjs';

const read = name => fs.readFileSync(new URL(`fixtures/data/${name}`, import.meta.url));
const original = JSON.parse(read('synthetic-index.json'));
const indexSpec = captureSpecs().find(spec => spec.id === 'sse-announcements-600312');
const holidaySpec = captureSpecs().find(spec => spec.id === 'sse-holiday');
function index(mutator = () => {}) {
  const value = structuredClone(original); mutator(value);
  return normalizeCapture({spec: indexSpec, bytes: Buffer.from(JSON.stringify(value))});
}

test('specs remain exactly three engineering securities and website references', () => {
  assert.equal(captureSpecs().length, 5);
  assert.deepEqual(captureSpecs().filter(item => item.data_type === 'ANNOUNCEMENTS').map(item => item.symbols[0]), ['SSE:603993', 'SSE:600312', 'SSE:603228']);
  assert.equal(captureSpecs().some(item => /tushare|token|marketfeed/i.test(item.uri)), false);
  const changed = captureSpecs(); changed[0].uri = 'https://evil.test/';
  assert.notEqual(captureSpecs()[0].uri, changed[0].uri);
});

test('synthetic DATE_ONLY disclosure references omit ADDDATE and caller clocks', () => {
  const value = index();
  assert.equal(value.facts.length, 5);
  assert.equal(value.published_date, '2026-09-30');
  assert.equal(value.published_precision, 'DATE_ONLY');
  assert.equal(value.published_at, null);
  assert.equal(value.event_time, null);
  assert.equal(value.event_date, null);
  assert.equal(Object.hasOwn(value, 'available_at'), false);
  assert.equal(Object.hasOwn(value, 'retrieved_at'), false);
  assert.equal(JSON.stringify(value).includes('ADDDATE'), false);
  assert.equal(JSON.stringify(value).includes('1900'), false);
  assert.equal(JSON.stringify(value).includes('2099'), false);
  assert.equal(value.coverage.complete, false);
  assert.equal(value.coverage.claim, 'DOCUMENT_REFERENCES_ONLY');
  assert.equal(value.facts.every(item => item.document_sha256 === null), true);
});

test('cache surplus never widens the five-reference projection', () => {
  const value = index(input => input.result.push(...Array.from({length: 20}, () => input.result[0])));
  assert.equal(value.facts.length, 5);
  assert.equal(value.coverage.complete, false);
});

test('empty source response fails DQ instead of synthesising stock evidence', () => assert.throws(() => index(value => value.result = []), /SLICE_DQ_FAILED/));
test('malformed source JSON and HTML website shell fail DQ', () => {
  for (const bytes of [Buffer.from('{'), Buffer.from('<html><div id="app"></div></html>')])
    assert.throws(() => normalizeCapture({spec: indexSpec, bytes}), /SLICE_DQ_FAILED/);
});
test('wrong index product/symbol envelope cannot cross the stock boundary', () => assert.throws(() => index(value => value.productId = '603993'), /SLICE_SCOPE_MISMATCH/));
test('source row for another security fails closed', () => assert.throws(() => index(value => value.result[0].SECURITY_CODE = '603993'), /SLICE_SCOPE_MISMATCH/));
test('future publication date cannot escape exact index window', () => assert.throws(() => index(value => value.result[0].SSEDATE = '2026-10-08'), /SLICE_SCOPE_MISMATCH/));
test('invalid calendar publication date fails DQ', () => assert.throws(() => index(value => value.result[0].SSEDATE = '2026-02-30'), /SLICE_DQ_FAILED/));
test('historical date-window widening in the response fails', () => assert.throws(() => index(value => value.beginDate = '2020-01-01'), /SLICE_SCOPE_MISMATCH/));
test('page-size and page-number mismatch fail instead of silently widening', () => {
  assert.throws(() => index(value => value.pageHelp.pageSize = 100), /SLICE_DQ_FAILED/);
  assert.throws(() => index(value => value.pageHelp.pageNo = 2), /SLICE_DQ_FAILED/);
});
test('document URL must preserve official host, security and source date', () => {
  for (const uri of ['https://evil.test/data.pdf', 'https://www.sse.com.cn.evil.test/data.pdf',
    '/disclosure/listedinfo/announcement/c/new/2026-09-30/603993_20260930_TEST.pdf',
    '/disclosure/listedinfo/announcement/c/new/2026-09-30/600312_20260929_TEST.pdf',
    `${original.result[0].URL}?token=SYNTHETIC`, `${original.result[0].URL}#SYNTHETIC`])
    assert.throws(() => index(value => value.result[0].URL = uri), /SLICE_SCOPE_MISMATCH/);
});
test('duplicate document pointers do not masquerade as independent evidence', () => assert.throws(() => index(value => value.result[1] = value.result[0]), /SLICE_DQ_FAILED/));
test('HTML/control/overlong source title is not a sanitised document reference', () => {
  for (const title of ['<script>SYNTHETIC</script>', 'SYNTHETIC\u0000TITLE', 'X'.repeat(301)])
    assert.throws(() => index(value => value.result[0].TITLE = title), /SLICE_DQ_FAILED/);
});
test('unknown raw financial/outcome fields are excluded from approved references', () => {
  const value = index(input => Object.assign(input.result[0], {future_MAE: 'SYNTHETIC', total_assets: 'SYNTHETIC', available_at: '1900-01-01T00:00:00Z'}));
  assert.equal(/future_MAE|total_assets|available_at|1900/.test(JSON.stringify(value)), false);
  assert.deepEqual(Object.keys(value.facts[0]), ['kind', 'symbol', 'date', 'title', 'official_uri', 'document_sha256']);
});
test('mutated spec source/product/symbol/date or caller clock cannot become approved', () => {
  for (const mutator of [value => value.source_id = 'caller:source', value => value.product = 'SSE_MARKET_FEED',
    value => value.symbols.push('SSE:999999'), value => value.uri = value.uri.replace('2026-04-08', '2020-01-01'),
    value => value.retrieved_at = '1900-01-01T00:00:00Z']) {
    const spec = structuredClone(indexSpec); mutator(spec);
    assert.throws(() => normalizeCapture({spec, bytes: read('synthetic-index.json')}), /SLICE_PRODUCT_MISMATCH/);
  }
});
test('synthetic calendar proves explicit closed/open days without inferring latest session', () => {
  const value = normalizeCapture({spec: holidaySpec, bytes: read('synthetic-holiday.html')});
  assert.equal(value.facts.find(item => item.date === '2026-10-05').kind, 'CALENDAR_CLOSED');
  assert.equal(value.facts.find(item => item.date === '2026-10-08').kind, 'CALENDAR_OPEN');
  assert.equal(value.facts.some(item => item.date === '2026-09-30'), false);
  assert.equal(Object.hasOwn(value, 'latest_session'), false);
  assert.equal(value.published_at, null);
  assert.equal(value.published_date, '2026-09-17');
  assert.equal(value.coverage.complete, false);
});
test('altered holiday schedule/signature cannot replace the reviewed official facts', () => {
  for (const bytes of [read('synthetic-holiday.html').toString().replace('10月7日', '10月6日'),
    read('synthetic-holiday.html').toString().replace('2026年9月17日', '2026年9月18日'),
    '<html><h1>关于2026年中秋节、国庆节休市安排的公告</h1>上海证券交易所</html>'])
    assert.throws(() => normalizeCapture({spec: holidaySpec, bytes: Buffer.from(bytes)}), /SLICE_DQ_FAILED/);
});
test('terms parser gives narrow local reference only, without transferable rights', () => {
  const terms = parseSseTerms(read('synthetic-terms.html'));
  assert.equal(terms.local_noncommercial_reference, true);
  assert.equal(terms.cloud_raw_export, false);
  assert.equal(terms.market_feed_entitlement, false);
  assert.equal(terms.historical_pit, false);
  assert.throws(() => parseSseTerms(Buffer.from('<html><h1>法律声明</h1></html>')), /SLICE_TERMS_UNPROVEN/);
  assert.throws(() => normalizeCapture({spec: captureSpecs()[0], bytes: read('synthetic-terms.html')}), /SLICE_PRODUCT_MISMATCH/);
});
test('absent and caller-forged Tushare entitlement block before secret/network access', async () => {
  let calls = 0;
  const transport = async () => {calls++; throw new Error('NETWORK_MUST_NOT_BE_CALLED');};
  const secretStore = {get() {calls++; throw new Error('SECRET_MUST_NOT_BE_READ');}};
  for (const entitlement of [null, {}, {verified: true, account: 'SYNTHETIC', products: ['daily'], purpose: 'LOCAL_REAL_RESEARCH_PREPARATION', local_storage: true, cloud_transfer: true}]) {
    const adapter = tushareAdapter({entitlement, transport, secretStore});
    assert.equal(adapter.status, 'BLOCKED');
    assert.throws(() => adapter.preflight(), /SLICE_ENTITLEMENT_UNKNOWN/);
    await assert.rejects(adapter.fetch({api_name: 'daily'}), /SLICE_ENTITLEMENT_UNKNOWN/);
  }
  assert.equal(calls, 0);
});
