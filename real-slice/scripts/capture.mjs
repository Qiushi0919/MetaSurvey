import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createCollector} from '../src/core.mjs';
import {captureSpecs, normalizeCapture, parseSseTerms} from '../src/providers.mjs';

const defaultDirectory = '/Users/qiushi/投资研究/.p1b-archives/real-stock-slice-20261005/data';

/** Live capability is returned only to a trusted caller in the same process.
 * Disk records prove what was captured; they do not restore admission authority.
 */
export async function captureApprovedReferences({archiveDirectory = defaultDirectory, capturePdfOriginals = true} = {}) {
  const specs = captureSpecs();
  const collector = createCollector({specs, archiveDirectory});
  const handles = [];
  const projections = [];
  for (const spec of specs) {
    const handle = await collector.fetch(spec);
    const {record, bytes} = await collector.open(handle);
    handles.push(handle);
    if (spec.id === 'sse-terms') parseSseTerms(bytes);
    else projections.push({id: spec.id, index_capture_hash: record.content_hash, normalized: normalizeCapture({spec, bytes})});
  }
  const records = await collector.manifest(handles);
  const pdfCaptures = [];
  if (capturePdfOriginals) {
    // Exactly one already observed official document per approved security;
    // source body/financial numbers are not parsed or admitted by this script.
    const references = projections.filter(item => item.id.startsWith('sse-announcements-')).map(item => ({...item, reference: item.normalized.facts[0]}));
    const pdfSpecs = references.map(item => ({id: `pdf-original-${item.reference.symbol.slice(4)}`, source_id: 'official:sse-disclosure-reference', product: 'SSE_PUBLIC_WEBSITE_DISCLOSURE_PDF_ORIGINAL', data_type: 'ANNOUNCEMENTS', symbols: [item.reference.symbol], uri: item.reference.official_uri}));
    const pdfCollector = createCollector({specs: pdfSpecs, archiveDirectory});
    for (let index = 0; index < pdfSpecs.length; index++) {
      try {
        const handle = await pdfCollector.fetch(pdfSpecs[index]);
        const {record, bytes} = await pdfCollector.open(handle);
        if (!bytes.subarray(0, 8).toString('ascii').startsWith('%PDF-')) throw new Error('SLICE_DQ_FAILED');
        pdfCaptures.push({capture: record, origin_index_capture_hash: references[index].index_capture_hash,
          origin_reference: references[index].reference, disposition: 'QUARANTINED_ORIGINAL_NOT_ADMITTED', content_parsed: false});
      } catch (error) {
        pdfCaptures.push({spec: pdfSpecs[index], origin_index_capture_hash: references[index].index_capture_hash,
          disposition: 'BLOCKED_CAPTURE_OR_DQ', reason_code: error.message?.startsWith('SLICE_') ? error.message : 'SLICE_CAPTURE_UNTRUSTED', content_parsed: false});
      }
    }
  }
  const manifest = {scope: 'ACTUAL_CURRENT_OBSERVED_WEBSITE_REFERENCE_CAPTURE',
    captured_on: new Date().toISOString(), namespace: 'CORE_40', collector_public_key_der: collector.publicKeyDer,
    records, projections, pdf_originals: pdfCaptures,
    restored_live_authority: false, historical_visibility_proven: false,
    cloud_raw_export: false, research_pilot_authorized: false, production_enabled: false};
  await fs.mkdir(archiveDirectory, {recursive: true});
  const manifestPath = path.join(archiveDirectory, `capture-${new Date().toISOString().replaceAll(':', '').replaceAll('.', '')}.json`);
  await fs.writeFile(manifestPath, JSON.stringify(manifest, null, 2) + '\n', {flag: 'wx'});
  return {collector, handles, manifest, manifestPath};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = await captureApprovedReferences();
  console.log(JSON.stringify({captured_original_count: result.manifest.records.length,
    normalized_announcement_reference_count: result.manifest.projections.filter(item => item.id.startsWith('sse-announcements-')).reduce((count, item) => count + item.normalized.facts.length, 0),
    quarantined_pdf_original_count: result.manifest.pdf_originals.filter(item => item.disposition === 'QUARANTINED_ORIGINAL_NOT_ADMITTED').length,
    manifest_path: result.manifestPath, historical_visibility_proven: false, production_enabled: false}, null, 2));
}
