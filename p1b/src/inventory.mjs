import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {sha} from './contracts.mjs';

const REPO=fileURLToPath(new URL('../../',import.meta.url));
const DB='History/炒股/程序/data/stocks.db';
const EXPERIMENT='模拟交易实验/historical-validation-100d/';
const PYTHON='/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3';
const SQL_READER=String.raw`
import sqlite3,json,pathlib,sys
p=pathlib.Path(sys.argv[1])
c=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
c.execute('PRAGMA query_only=ON')
out=[]
for name, in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
 q='"'+name.replace('"','""')+'"'
 cols=[{'name':r[1],'type':r[2]} for r in c.execute('PRAGMA table_info('+q+')')]
 if any(word in name.lower() for word in ['credential','password','token','secret','account','position','ledger','goal','memory','state','queue','log']):
  out.append({'table':name,'columns':cols,'count':None,'exclusion':'NO_SENSITIVE_OR_RUNTIME_CONTENT_READ'})
  continue
 count=c.execute('SELECT COUNT(*) FROM '+q).fetchone()[0]
 bounds={}
 for col in [x['name'] for x in cols if x['name'] in ['date','trade_date','report_date','published_at','announcement_date','list_date']]:
  cc='"'+col.replace('"','""')+'"'
  bounds[col]=list(c.execute('SELECT min('+cc+'),max('+cc+') FROM '+q).fetchone())
 out.append({'table':name,'columns':cols,'count':count,'date_bounds':bounds})
c.close()
print(json.dumps(out,ensure_ascii=False))
`;

async function fingerprint(filename){
 if(!fs.existsSync(filename))return {present:false};
 const stat=fs.statSync(filename),h=createHash('sha256');for await(const chunk of fs.createReadStream(filename))h.update(chunk);
 return {present:true,byte_length:stat.size,raw_sha256:`sha256:${h.digest('hex')}`};
}
const load=filename=>JSON.parse(fs.readFileSync(filename,'utf8'));
function fileMetadata(root,relative){const p=path.resolve(root,relative);if(!fs.existsSync(p))return {reference:relative,present:false};const bytes=fs.readFileSync(p);return {reference:relative,present:true,byte_length:bytes.length,raw_sha256:sha(bytes)};}
function source({source_id,provider,data_type,original_reference,coverage='UNKNOWN',authority_level='UNVERIFIED',...extra}){
 return {source_id,provider,data_type,original_reference,license_terms_status:'UNKNOWN',redistribution_status:'UNKNOWN_NOT_AUTHORIZED',retrieved_at_semantics:'UNKNOWN_NO_BYTE_LINKED_SOURCE_CAPTURE',published_at_semantics:'UNKNOWN',available_at_semantics:'UNKNOWN_NOT_INFERRED_FROM_MTIME',coverage,authority_level,pit_suitability:'BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF',allowed_purposes:[],admission:'BLOCKED',known_limitations:[],...extra};
}

/** Curated metadata-only inventory. No model/runtime DB is opened, and no old code is imported. */
export async function buildSourceInventory({workspaceRoot=path.dirname(REPO.replace(/\/$/,'')),pythonExecutable=PYTHON}={}){
 const root=fs.realpathSync(workspaceRoot),dbFile=path.resolve(root,DB);
 const database={reference:DB,opened:false,read_mode:'SQLITE_URI_MODE_RO_IMMUTABLE_QUERY_ONLY',wal_included:false,not_current_live_database_proof:true};
 if(fs.existsSync(dbFile)){
  // This exact allowlist is intentional: no arbitrary DB path or recursive DB-content scanning.
  if(fs.realpathSync(dbFile)!==dbFile)throw new Error('P1B_SOURCE_UNAPPROVED');
  const before=Object.fromEntries(await Promise.all(['','-wal','-shm'].map(async suffix=>[suffix||'main',await fingerprint(dbFile+suffix)])));
  database.tables=JSON.parse(execFileSync(pythonExecutable,['-B','-c',SQL_READER,dbFile],{encoding:'utf8',maxBuffer:2*1024*1024,env:{PATH:path.dirname(pythonExecutable),PYTHONDONTWRITEBYTECODE:'1',LC_ALL:'en_US.UTF-8'}}));
  database.opened=true;
  const after=Object.fromEntries(await Promise.all(['','-wal','-shm'].map(async suffix=>[suffix||'main',await fingerprint(dbFile+suffix)])));
  database.before_fingerprint=before;database.after_fingerprint=after;database.fingerprints_unchanged=JSON.stringify(before)===JSON.stringify(after);
  database.known_limitations=['immutable read ignores uncheckpointed WAL rows','schema/counts and date aggregates only; no account/order/row payload','counts certify the main-file snapshot only; ingestion provider/clock/license not thereby proven'];
 }
 const klineDir=path.resolve(root,'History/炒股/程序/data/kline'),parquet=fs.existsSync(klineDir)?fs.readdirSync(klineDir).filter(n=>/^(?:sh|sz|bj|hk|us)[A-Za-z0-9]+\.parquet$/.test(n)):[];
 const prefixCounts={};for(const n of parquet)prefixCounts[n.slice(0,2)]=(prefixCounts[n.slice(0,2)]??0)+1;
 const parquetMetadata={reference:'History/炒股/程序/data/kline',file_count:parquet.length,filename_prefix_counts:prefixCounts,content_verified:false,license_and_clocks_verified:false};
 const manifests=['calendar_spec.json','source_manifest_v2.json','smoke_primary_sources.json','smoke_price_sources.json','broad_market_sources.json'].map(n=>fileMetadata(root,EXPERIMENT+n));
 const oldCapture=load(path.join(REPO,'tests/fixtures/p1a-data/public-capture.json'));
 const calRef='History/炒股/程序/data/akshare/trading_calendar_cn.json',calMeta=fileMetadata(root,calRef),oldCal=calMeta.present?load(path.resolve(root,calRef)):null;
 const sources=[
  source({source_id:'legacy:stock-info-main-snapshot',provider:'LEGACY_AGGREGATOR_PROVENANCE_UNVERIFIED',data_type:'A_SECURITY_MASTER_STATUS',original_reference:DB+'#stock_info',coverage:{row_count:database.tables?.find(t=>t.table==='stock_info')?.count??null,history:'CURRENT_FLAT_SNAPSHOT_ONLY'},known_limitations:['code/name/market/stock_type/last_update; no status effective-time/revision/PIT history','row count does not establish a point-in-time A-share universe']}),
  source({source_id:'legacy:akshare-calendar-file',provider:'AKSHARE_LABEL_IN_LEGACY_PATH_NO_ORIGINAL_CAPTURE',data_type:'B_TRADING_CALENDAR',original_reference:calRef,coverage:oldCal?{date_count:oldCal.dates?.length??0,from:oldCal.dates?.[0]??null,to:oldCal.dates?.at(-1)??null}:'UNKNOWN',retrieved_at_semantics:oldCal?.updated_at?`LOCAL_FILE_UPDATED_AT_ASSERTION_ONLY:${oldCal.updated_at}`:'UNKNOWN',known_limitations:['no original source bytes, license, per-date clock, exchange-specific coverage','future dates in file do not prove historical source visibility']}),
  source({source_id:'legacy:sse-calendar-spec',provider:'SSE_OFFICIAL_URLS_IN_LEGACY_MANIFEST',data_type:'B_TRADING_CALENDAR',original_reference:EXPERIMENT+'calendar_spec.json',authority_level:'OFFICIAL_REFERENCE_LEAD_NOT_ADMITTED',known_limitations:['source URLs and DATE_ONLY declarations only; not admitted captures','old specification/weekday arithmetic does not establish historical availability']}),
  source({source_id:'legacy:kline-cache',provider:'LEGACY_TENCENT_OR_AGGREGATOR_CODE_INDICATES_QFQ_FALLBACK_RAW',data_type:'C_EOD_PRICE',original_reference:parquetMetadata.reference,coverage:{file_count:parquet.length,filename_prefix_counts:prefixCounts,rows_and_dates:'NOT_VERIFIED'},known_limitations:['cache filename is not official symbol/status provenance','qfq→day fallback in legacy fetcher; adjustment version lineage not retained','no original byte chain, per-bar published/available/retrieved clock, license; not raw historical bars admission']}),
  source({source_id:'legacy:hk-daily-main-snapshot',provider:'LEGACY_AKSHARE_TENCENT_CODE_REFERENCES_NOT_ROW_PROOF',data_type:'C_EOD_PRICE_HK_OUTSIDE_A_SHARE_SCOPE',original_reference:DB+'#hk_daily',coverage:{row_count:database.tables?.find(t=>t.table==='hk_daily')?.count??null,date_bounds:database.tables?.find(t=>t.table==='hk_daily')?.date_bounds??{},scope:'HK_ONLY_NOT_A_SHARE_ADMISSION'},known_limitations:['REAL prices in old mutable cache do not imply admitted source','raw/qfq/hfq enum not a versioned corporate-action lineage','read-only main-file counts exclude WAL; IEEE REAL legacy prices are not canonical new money']}),
  source({source_id:'legacy:tencent-smoke-price-leads',provider:'TENCENT_PUBLIC_ENDPOINT_LEADS',data_type:'C_EOD_PRICE',original_reference:EXPERIMENT+'smoke_price_sources.json',known_limitations:['public endpoint access is not license','URL dates are requested coverage, not byte-verified coverage','historical observation time/adjustment metadata absent']}),
  source({source_id:'missing:corporate-action-revision-feed',provider:'NOT_FOUND_IN_CURATED_INVENTORY',data_type:'D_CORPORATE_ACTION',original_reference:null,known_limitations:['no independently verified official action/entitlement/factor stream','qfq/hfq caches cannot establish corporate-action PIT']}),
  source({source_id:'legacy:financial-disclosure-leads',provider:'CNINFO_AND_ISSUER_URLS_IN_MANIFEST',data_type:'E_FINANCIAL_STATEMENTS_REVISIONS',original_reference:EXPERIMENT+'source_manifest_v2.json',authority_level:'DISCLOSURE_LEADS_ONLY',known_limitations:['expected PDF hashes and DATE_ONLY claims remain legacy assertions here','no real revision parser/available-clock/terms/revision lineage admission']}),
  source({source_id:'legacy:announcement-policy-leads',provider:'SSE_NBS_MOF_ISSUER_URLS_IN_MANIFEST',data_type:'F_ANNOUNCEMENTS_DISCLOSURES',original_reference:EXPERIMENT+'broad_market_sources.json',authority_level:'OFFICIAL_URL_LEADS_NOT_ADMITTED',known_limitations:['URL/citation is not trusted evidence','no full original-source time/license checks in this inventory']}),
  source({source_id:'missing:industry-membership-history',provider:'NOT_FOUND_IN_CURATED_INVENTORY',data_type:'G_INDUSTRY_SECTOR_MEMBERSHIP',original_reference:null,known_limitations:['current sector tags/research descriptions cannot establish historical membership','no effective-dated membership revisions admitted']})
 ];
 for(const cap of oldCapture.captures)sources.push(source({source_id:cap.source.source_id,provider:cap.source.source_class==='OFFICIAL'?'OFFICIAL_REFERENCE':'UNKNOWN',data_type:cap.name==='sse-dayk'?'C_EOD_PRICE':'B_REFERENCE_DOCUMENT',original_reference:cap.url,raw_sha256:cap.raw_sha256,license_terms_status:cap.source.license_type,redistribution_status:'NOT_AUTHORIZED',retrieved_at_semantics:`ACTUAL_OLD_CAPTURE:${cap.retrieved_at}`,published_at_semantics:cap.published_at??'UNKNOWN',available_at_semantics:cap.clock_basis==='RETRIEVAL_OBSERVATION'?'RETRIEVAL_ONLY_NO_HISTORICAL_PROOF':'UNKNOWN',authority_level:'RAW_PUBLIC_CAPTURE_ONLY',known_limitations:['old frozen terms UNVERIFIED; cannot promote original object','new narrowly reviewed calendar source does not relicense this source/data class']}));
 const realManifest=load(path.join(REPO,'p1b/tests/fixtures/real-reference/capture-manifest.json')),newCal=realManifest.items.find(x=>x.id==='sse-calendar'),terms=realManifest.items.find(x=>x.id==='sse-terms');
 sources.push(source({source_id:'official:sse-calendar-reference',provider:'SSE',data_type:'B_CALENDAR_REFERENCE',original_reference:newCal.original_uri,license_terms_status:'VERIFIED_FOR_NARROW_LOCAL_REFERENCE',redistribution_status:'NOT_AUTHORIZED',retrieved_at_semantics:`ACTUAL_NEW_TLS_CAPTURE:${newCal.retrieved_at}`,published_at_semantics:'BODY_DATE_ONLY_2026-09-17_INTRADAY_UNKNOWN',available_at_semantics:'ACTUAL_RETRIEVAL_ONLY_NOT_HISTORICAL',coverage:{exchange:'SSE',symbols:[],from:'2026-09-20',to:'2026-10-10',complete_trading_calendar:false,stock_coverage:false},authority_level:'OFFICIAL_ANNOUNCEMENT_BYTES_FOR_LIMITED_REFERENCE',pit_suitability:'OBSERVED_AT_RETRIEVAL_ONLY',allowed_purposes:['LOCAL_NONCOMMERCIAL_CALENDAR_REFERENCE'],admission:'CANDIDATE_REQUIRES_APPROVED_POLICY_AND_ACTUAL_RECEIPT',raw_sha256:newCal.raw_sha256,terms_raw_sha256:terms.raw_sha256,known_limitations:['terms support noncommercial local browse/download; model/cloud/redistribution/trading disabled','finite explicit calendar facts only; other days unknown','retrieved after article; no historical-cutoff availability proof','not a stock/price/financial slice; no real research pilot readiness claim']}));
 return {version:'1.0.0',inventory_kind:'ACTUAL_CURATED_METADATA_READ_ONLY_NOT_DATA_ADMISSION',recorded_at:new Date().toISOString(),database,parquet_metadata:parquetMetadata,legacy_manifest_metadata:manifests,calendar_metadata:calMeta,new_capture_manifest_sha256:sha(fs.readFileSync(path.join(REPO,'p1b/tests/fixtures/real-reference/capture-manifest.json'))),sources,excluded:['ALL_CODEX_MODEL_STATE_MEMORY_GOALS_QUEUE_LOGS_DATABASES','CREDENTIAL_FILES_AND_DATABASES','ACCOUNT_STATE_AND_PERSONAL_WORKBOOKS','V5_RUNTIME_EXECUTION_AND_WRITABLE_LEGACY_IMPORT','RECURSIVE_CONTENT_SCAN_OF_LEGACY_RUNS'],limitations:['curated known locations, not exhaustive workspace certification','no old model/collector/V5 program executed','local cache coverage and counts do not confer license or PIT trust','runtime and raw evidence remain outside Git; only this metadata manifest is saved']};
}
