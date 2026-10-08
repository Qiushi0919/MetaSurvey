import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import Ajv from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';

// Proposal structure only. This tool cannot admit a source or authenticate clocks.
const root = path.resolve(import.meta.dirname, '../..');
const options = new Map();
for (const argument of process.argv.slice(2)) {
  const match = /^--(output|capture-dir)=(.+)$/.exec(argument);
  assert.ok(match && !options.has(match[1]), 'Use unique --output / --capture-dir options');
  assert.ok(path.isAbsolute(match[2]), 'Option paths must be absolute');
  options.set(match[1], path.resolve(match[2]));
}
let output = options.get('output');
if (output) {
  // Resolve the existing parent too: a symlink outside the repo can point inside.
  const realRoot = await fs.realpath(root);
  const realParent = await fs.realpath(path.dirname(output));
  output = path.join(realParent, path.basename(output));
  const relative = path.relative(realRoot, output);
  assert.ok(relative.startsWith('..' + path.sep), 'Reports must be written outside the repository');
}
const load = async file => JSON.parse(await fs.readFile(path.join(root, file), 'utf8'));
const ajv = new Ajv({ strict: false, allErrors: true });
addFormats(ajv);
const clock = ajv.compile(await load('contracts/admission-preparation/ClockEvidenceProposal.schema.json'));
const slice = ajv.compile(await load('contracts/admission-preparation/StockSliceProposal.schema.json'));
const observed = await load('docs/admission-preparation/slice-observed.proposal.json');
const historical = await load('docs/admission-preparation/slice-historical.proposal.json');
const unknown = await load('docs/admission-preparation/clock-unknown.proposal.json');
const cases = [];
function check(name, validator, value, expected) {
  assert.equal(Boolean(validator(value)), expected, name);
  cases.push({ name, result: 'PASS', expected_schema_valid: expected,
    assertion: 'STRUCTURE_ONLY_NOT_SOURCE_OR_CLOCK_VERIFICATION' });
}
function changed(base, fn) {
  const value = structuredClone(base);
  fn(value);
  return value;
}
check('unknown clocks remain nullable and unverified BLOCKED', clock, unknown, true);
check('observed proposal preserves source/pilot/order blocked and exact CORE namespace', slice, observed, true);
check('historical proposal preserves separate route and all critical evidence UNKNOWN', slice, historical, true);
check('real source ADMITTED label rejected', slice, changed(observed, x => x.real_source_admission = 'ADMITTED'), false);
check('cloud ALLOWED label rejected', slice, changed(observed, x => x.usage_rights.cloud_manual_export = 'ALLOWED'), false);
check('production true rejected', slice, changed(observed, x => x.production_enabled = true), false);
check('pilot pass rejected', slice, changed(observed, x => x.real_research_pilot = 'PASS'), false);
check('EVENT crossover rejected', slice, changed(observed, x => x.namespace = 'EVENT_3'), false);
check('missing financial revision requirements rejected', slice, changed(observed, x => delete x.datasets.FINANCIAL_REVISIONS), false);
check('arbitrary order/path payload rejected', slice, changed(observed, x => x.OrderIntent = { path: '/private/synthetic-only' }), false);
const example = changed(unknown, x => {
  x.source_id = 'SYNTHETIC_SCHEMA_EXAMPLE_ONLY';
  x.data_type = 'SYNTHETIC';
  x.published_date = '2020-01-01';
  x.publication_precision = 'DATE_ONLY';
});
check('synthetic DATE_ONLY publication retains null instant', clock, example, true);
check('DATE_ONLY cannot acquire midnight publication instant', clock,
  changed(example, x => x.published_at = '2020-01-01T00:00:00+08:00'), false);
check('instant without timezone rejected', clock, changed(unknown, x => x.retrieved_at = '2020-01-01T00:00:00'), false);
check('fake historical visibility true rejected', clock, changed(example, x => x.historical_visibility_proven = true), false);
check('SECOND precision cannot carry a null publication instant', clock,
  changed(unknown, x => x.publication_precision = 'SECOND'), false);
check('UNKNOWN precision cannot carry a guessed event instant', clock,
  changed(unknown, x => x.event_time = '2020-01-01T00:00:00Z'), false);
const invented = changed(example, x => {
  x.available_at = '2019-01-01T00:00:00Z';
  x.retrieved_at = '2020-01-01T00:00:00Z';
});
check('valid-shaped invented availability remains unverified BLOCKED; no chronology runtime', clock, invented, true);
assert.equal(invented.admission, 'BLOCKED');
assert.equal(invented.historical_visibility_proven, false);
const captures = await load('docs/admission-preparation/public-document-captures.json');
let originalsVerified = 0;
for (const item of captures.items) {
  assert.equal(item.license_grant, false);
  assert.equal(item.admission, 'BLOCKED');
  assert.equal(item.real_market_dataset, false);
  if (options.has('capture-dir') && item.result === 'CAPTURED_DOCUMENT_ONLY') {
    assert.equal(path.basename(item.archive_filename), item.archive_filename);
    const raw = await fs.readFile(path.join(options.get('capture-dir'), item.archive_filename));
    assert.equal('sha256:' + createHash('sha256').update(raw).digest('hex'), item.raw_sha256);
    assert.equal(raw.length, item.byte_length);
    originalsVerified++;
  }
}
const report = {
  run_id: 'PROPOSAL-SCHEMA-' + new Date().toISOString(),
  scope: 'OWNER_REVIEW_PREPARATION_SHAPE_CHECK_ONLY', compiled_schemas: 2, cases,
  counts: { cases: cases.length, pass: cases.length, fail: 0 },
  captured_provider_documents_verified: originalsVerified,
  external_raw_check: options.has('capture-dir') ? 'RUN' : 'NOT_REQUESTED_NO_CLAIM',
  real_source_admission_created: false, source_clock_facts_verified: false,
  research_pilot: false, productionGate: false,
  notes: [
    'No runtime adapter or business decision engine built.',
    'Schema-valid timestamps do not establish facts, historic availability or licence.',
    'Live source/PIT/permission guard remains a future owner-reviewed versioned adapter prerequisite.'
  ]
};
if (output) await fs.writeFile(output, JSON.stringify(report, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ cases: cases.length, pass: cases.length, real_sources_admitted: 0,
  documents_verified: originalsVerified, external_raw_check: report.external_raw_check }));
