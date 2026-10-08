import {isDeepStrictEqual} from 'node:util';

const CODES = Object.freeze(['603993', '600312', '603228']);
const FROM = '2026-04-08';
const TO = '2026-10-05';
const HOLIDAY = 'https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml';
const LEGAL = 'https://www.sse.com.cn/home/legal/';
const INDEX = 'https://query.sse.com.cn/security/stock/queryCompanyBulletin.do';

function requireSource(condition, code = 'SLICE_DQ_FAILED') {
  if (!condition) throw new Error(code);
}

function disclosureUri(code) {
  const query = new URLSearchParams({
    isPagination: 'true', productId: code, keyWord: '',
    securityType: '0101,120100,020100,020200,120200',
    reportType2: '', reportType: 'ALL', beginDate: FROM, endDate: TO,
    'pageHelp.pageSize': '5', 'pageHelp.pageNo': '1',
    'pageHelp.beginPage': '1', 'pageHelp.endPage': '1',
  });
  return `${INDEX}?${query}`;
}

/** Exact reviewed website pages; this is not a global provider entitlement. */
export function captureSpecs() {
  return [
    {id: 'sse-terms', source_id: 'official:sse-website-legal', product: 'SSE_PUBLIC_WEBSITE_LEGAL', data_type: 'CALENDAR_RULES', symbols: [], uri: LEGAL},
    {id: 'sse-holiday', source_id: 'official:sse-calendar-reference-v2', product: 'SSE_PUBLIC_WEBSITE_HOLIDAY_DOCUMENT', data_type: 'CALENDAR_RULES', symbols: [], uri: HOLIDAY},
    ...CODES.map(code => ({id: `sse-announcements-${code}`, source_id: 'official:sse-disclosure-reference', product: 'SSE_PUBLIC_WEBSITE_DISCLOSURE_INDEX', data_type: 'ANNOUNCEMENTS', symbols: [`SSE:${code}`], uri: disclosureUri(code)})),
  ];
}

function reviewedSpec(spec) {
  const expected = captureSpecs().find(item => item.id === spec?.id);
  requireSource(expected && isDeepStrictEqual(spec, expected), 'SLICE_PRODUCT_MISMATCH');
  return expected;
}

function rawText(bytes) {
  requireSource(Buffer.isBuffer(bytes) || bytes instanceof Uint8Array);
  requireSource(bytes.byteLength > 0 && bytes.byteLength <= 524288);
  return Buffer.from(bytes).toString('utf8');
}

function htmlText(bytes) {
  return rawText(bytes)
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&(?:nbsp|#160);/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

function isoDate(value) {
  requireSource(typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value));
  const instant = Date.parse(`${value}T00:00:00Z`);
  requireSource(Number.isFinite(instant) && new Date(instant).toISOString().slice(0, 10) === value);
  return value;
}

function day(year, month, date) {
  return isoDate(`${year}-${String(month).padStart(2, '0')}-${String(date).padStart(2, '0')}`);
}

function days(from, to) {
  const result = [];
  requireSource(from <= to);
  for (let cursor = Date.parse(`${from}T00:00:00Z`); cursor <= Date.parse(`${to}T00:00:00Z`); cursor += 86400000) {
    requireSource(result.length < 31);
    result.push(new Date(cursor).toISOString().slice(0, 10));
  }
  return result;
}

function fact(kind, symbol, date, title, official_uri, document_sha256 = null) {
  return {kind, symbol, date, title, official_uri, document_sha256};
}

function clocks(published_date, {effective_from = null, effective_to = null} = {}) {
  // No provider update time, URI filename time or ADDDATE becomes availability.
  // Capture/availability clocks are exclusively supplied by the parent collector.
  return {published_date, published_at: null, published_precision: 'DATE_ONLY', event_time: null, event_date: null, business_effective_at: null, effective_from, effective_to};
}

/** Terms are an input to the parent's exact policy, never an admitted market fact. */
export function parseSseTerms(bytes) {
  const body = htmlText(bytes);
  requireSource(body.includes('任何机构或者个人可基于非商业目的浏览、下载本网站的内容')
    && body.includes('未经上海证券交易所书面许可')
    && body.includes('不得以向他人出售牟利为目的')
    && body.includes('上海证券交易所保留对本声明的修改、解释权'), 'SLICE_TERMS_UNPROVEN');
  return {local_noncommercial_reference: true, local_download: true, cloud_raw_export: false, redistribution: false, historical_pit: false, market_feed_entitlement: false};
}

function normalizeHoliday(spec, bytes) {
  const body = htmlText(bytes);
  requireSource(body.includes('关于2026年中秋节、国庆节休市安排的公告') && body.includes('上海证券交易所'));
  const signatures = [...body.matchAll(/(20\d{2})年(\d{1,2})月(\d{1,2})日/g)].map(match => day(match[1], match[2], match[3]));
  requireSource(signatures.length === 1 && signatures[0] === '2026-09-17');
  const segment = body.match(/一、休市安排：([\s\S]*?)二、/);
  requireSource(segment);
  const content = segment[1];
  const closures = [...content.matchAll(/(\d{1,2})月(\d{1,2})日（星期[一二三四五六日]）至(\d{1,2})月(\d{1,2})日（星期[一二三四五六日]）休市/g)];
  const reopens = [...content.matchAll(/(\d{1,2})月(\d{1,2})日（星期[一二三四五六日]）起照常开市/g)];
  const weekendClause = content.match(/另外，([\s\S]*?)为周末休市/);
  requireSource(closures.length === 2 && reopens.length === 2 && weekendClause);
  const weekends = [...weekendClause[1].matchAll(/(\d{1,2})月(\d{1,2})日（星期[六日]）/g)];
  requireSource(weekends.length === 2);
  const closed = [...closures.flatMap(match => days(day('2026', match[1], match[2]), day('2026', match[3], match[4]))), ...weekends.map(match => day('2026', match[1], match[2]))].sort();
  const open = reopens.map(match => day('2026', match[1], match[2])).sort();
  requireSource(isDeepStrictEqual(closed, ['2026-09-20', '2026-09-25', '2026-09-26', '2026-09-27', '2026-10-01', '2026-10-02', '2026-10-03', '2026-10-04', '2026-10-05', '2026-10-06', '2026-10-07', '2026-10-10'])
    && isDeepStrictEqual(open, ['2026-09-28', '2026-10-08']));
  const facts = [...closed.map(date => fact('CALENDAR_CLOSED', null, date, 'SSE explicitly announced closed date', spec.uri)), ...open.map(date => fact('CALENDAR_OPEN', null, date, 'SSE explicitly announced reopening date', spec.uri))].sort((left, right) => left.date.localeCompare(right.date));
  return {...clocks(signatures[0], {effective_from: closed[0], effective_to: closed.at(-1)}), facts,
    coverage: {symbols: [], from: closed[0], to: closed.at(-1), complete: false, claim: 'FINITE_CALENDAR_REFERENCE'}};
}

function documentUri(row, code) {
  requireSource(typeof row.URL === 'string' && row.URL.length <= 2000);
  const uri = new URL(row.URL, 'https://www.sse.com.cn');
  requireSource(uri.protocol === 'https:' && uri.hostname === 'www.sse.com.cn' && !uri.port && !uri.username && !uri.password && !uri.search && !uri.hash, 'SLICE_SCOPE_MISMATCH');
  const expected = new RegExp(`^/disclosure/listedinfo/announcement/c/new/${row.SSEDATE}/${code}_${row.SSEDATE.replaceAll('-', '')}_[A-Z0-9]{4}\\.pdf$`);
  requireSource(expected.test(uri.pathname), 'SLICE_SCOPE_MISMATCH');
  return uri.href;
}

function normalizeAnnouncements(spec, bytes) {
  let document;
  try {document = JSON.parse(rawText(bytes));} catch {throw new Error('SLICE_DQ_FAILED');}
  const code = spec.symbols[0].slice(4);
  requireSource(document && !Array.isArray(document) && document.productId === code && document.beginDate === FROM && document.endDate === TO && document.isPagination === 'true', 'SLICE_SCOPE_MISMATCH');
  requireSource(document.pageHelp?.pageSize === 5 && document.pageHelp?.pageNo === 1);
  requireSource(Array.isArray(document.result) && document.result.length >= 1 && document.result.length <= 100);
  // The website currently returns a 25-row cache for a five-row request. Only
  // the approved first five metadata records enter the projection. Originals
  // retain the cache unchanged; this never claims all 180 days were covered.
  const rows = document.result.slice(0, 5);
  const seen = new Set();
  const facts = rows.map(row => {
    requireSource(row && row.SECURITY_CODE === code, 'SLICE_SCOPE_MISMATCH');
    const date = isoDate(row.SSEDATE);
    requireSource(date >= FROM && date <= TO, 'SLICE_SCOPE_MISMATCH');
    requireSource(typeof row.TITLE === 'string' && row.TITLE.trim().length > 0 && row.TITLE.length <= 300 && !/[<>\u0000-\u001f]/.test(row.TITLE));
    const uri = documentUri(row, code);
    requireSource(!seen.has(uri)); seen.add(uri);
    return fact('DOCUMENT_REFERENCE', spec.symbols[0], date, row.TITLE, uri);
  });
  const dates = facts.map(item => item.date).sort();
  return {...clocks(dates.at(-1)), facts, coverage: {symbols: [...spec.symbols], from: dates[0], to: dates.at(-1), complete: false, claim: 'DOCUMENT_REFERENCES_ONLY'}};
}

/** Deterministic original-byte projection; no caller-normalized payload accepted. */
export function normalizeCapture({spec, bytes}) {
  const approved = reviewedSpec(spec);
  if (approved.id === 'sse-holiday') return normalizeHoliday(approved, bytes);
  if (approved.id.startsWith('sse-announcements-')) return normalizeAnnouncements(approved, bytes);
  throw new Error('SLICE_PRODUCT_MISMATCH');
}

/** Candidate adapter deliberately stops before both secret lookup and network.
 * A caller-supplied entitlement object is not a verified entitlement capability.
 * A future authorised implementation needs the parent's verified policy boundary.
 */
export function tushareAdapter({entitlement = null} = {}) {
  const provided = entitlement !== null;
  return Object.freeze({
    provider: 'TUSHARE', role: 'CANDIDATE_LOCAL_STRUCTURED_PROVIDER', status: 'BLOCKED',
    reason_code: 'SLICE_ENTITLEMENT_UNKNOWN', entitlement_provided: provided,
    async fetch() {throw new Error('SLICE_ENTITLEMENT_UNKNOWN');},
    preflight() {throw new Error('SLICE_ENTITLEMENT_UNKNOWN');},
  });
}
