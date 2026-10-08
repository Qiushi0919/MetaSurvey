# P1-A Data / PIT / Security

This module is an offline foundation. It provides no broker path and never enables production execution. P0 contracts and migrations 001/002 remain byte-for-byte unchanged. Migration 003 adds an append-only evidence store that can represent unknown clocks without pretending to satisfy the stricter P0 DataEnvelope.

## Running and persistence

`src/data/index.mjs` is the public entry point. Every database operation accepts the existing single-connection `db.exec(sql)` / `db.query(sql, parameters)` adapter. Tests use PostgreSQL through PGlite; server roles, deployment and external PostgreSQL operations remain outside this acceptance scope.

Migration 003 creates:

- `p1a_data_raw`: original bytes, bounded to 1 MiB per captured object, addressed by SHA-256.
- `p1a_data_objects`: immutable versioned source observations, security records, calendars, status, raw/adjusted bars, actions, factors, financial revisions and snapshots. Flat indexed clocks and source/security/version/hash/trace accompany the full closed record.
- `p1a_data_staging`: parser version, observation reference, normalized reference and DQ decision. No historical bulk import.
- `p1a_data_audit`: append-only events with source/hash/time/security/version/trace and reason codes. No account identities or credentials.

UPDATE, DELETE and TRUNCATE are rejected. Re-ingesting the same object/version/hash is idempotent; a different payload at the same version fails. Raw insertion, typed normalization and snapshot admission are distinct operations. Quarantined data is retained for investigation and cannot be projected into an admitted snapshot.

## API

| Export | Inputs and output |
| --- | --- |
| `capturePublicSource` | `{url,source,rawDirectory?,maxBytes?}` → bounded HTTPS original bytes and genuine collector retrieval time; no caller clock override, authenticated endpoint or credentials. A private in-process capture capability binds bytes, source policy and retrieval time. |
| `ingestSourceObservation` | Raw bytes, immutable source policy, clock proof, payload, version and trace → persisted observation. Real live input requires the genuine capture capability. `archived_reference:true` explicitly imports a captured reference copy with unknown availability; it cannot manufacture live capture authority. |
| `parseSseDayKPayload` | Original SSE dayk bytes → strict typed decimal lexemes. No floating point money or price enters canonical hashes. |
| `registerSecurity`, `resolveSecurity`, `parseSecuritySymbol` | Canonical `SSE:600000` / `SZSE:000001`; explicit exchange is required for bare six-digit codes. No inferred exchange by code prefix. Versioned listing/delisting/board/lot/ST/suspension/effective ranges; conflicts quarantine and audit. |
| `ingestSecurityStatus` | Source-proven status facts plus immutable security reference → appended status history. Resolution and bar snapshots select visible effective status before admitting data. |
| `ingestCalendar`, `officialAutumn2026Calendar`, `nextTradingSession` | Explicit complete daily coverage and versioned sessions. Official bounded adapter verifies holiday and session evidence; next-session result carries the exact calendar reference. Unknown/out-of-range days and unknown/suspended status fail closed. |
| `ingestBar`, `ingestSseDayK` | Source-proven daily facts plus security/calendar/status/factor references → raw or adjusted normalized object plus staging DQ. Raw and adjusted identities are separate. Unknown availability/preclose/security status is non-tradeable. |
| `ingestCorporateAction`, `ingestAdjustment` | Dividend/split/bonus/rights structure, ex/effective dates, terms and explicit factor → appended action/factor lineage. No production adjustment or entitlement mathematics is inferred. |
| `ingestFinancialRevision`, `financialsAsOf` | Original/restatement/source-correction, period, integer cents and explicit predecessor → appended revision. Query filters availability/retrieval and complete lineage at cutoff first, then chooses the latest visible revision. |
| `lineageClosure`, `verifyVisible` | References and cutoff → recursively verified source bytes, parsed facts, source policy, clocks, security/calendar/status/actions/factors/financial predecessors. Missing, stale version, altered hash, cycles or future dependencies fail. |
| `freezeDataSnapshot`, `verifyDataSnapshot` | Root refs, cutoff, feature version, rules hash, scope and freeze time → P0 `SnapshotManifest` plus a P1-A lineage bundle and stored snapshot ref. Invalid input returns `BLOCKED`, a reason, and no manifest. |
| `projectDataEnvelope` | A locally verified, known-clock typed object → unchanged strict P0 DataEnvelope projection. Calendar/source observations remain distinct objects in the lineage bundle. |

`tests/fixtures/p1a-data/helpers.mjs` provides `dataDb()`, `observation()` and `createDataFixture(db, options)` for integration. The builder returns `{security,calendar,barObservation,bar,snapshot,cutoff,...}`. All monetary assumptions and source clocks in this builder are explicitly synthetic. Changing `barClose` in a fresh database changes raw/payload/closure/data hashes. It does not create a production default.

## Clock and source trust

All timestamps require offsets; business timezone is Asia/Shanghai. Unknown source event/publication/availability times remain null. `retrieved_at` is never used to assert that an old market observation was historically available.

`SOURCE_FIELD` proof binds raw JSON clock paths and a source-policy hash/version. P1-A permits that mapping only for explicitly synthetic fixtures: no real official timestamp mapping has been authorized. The synthetic parsed fact is independently checked against `raw.fact`. Typed normalization and snapshot closure also compare facts with that source payload, so resealing a new close or financial value with old raw bytes fails.

For an actual reference document, `RETRIEVAL_OBSERVATION` means only that this document copy was observed at capture time. A DATE_ONLY publication remains date-only; capture time does not become its original market publication time. Historical DATE_ONLY reconstruction with a verified calendar/policy is not enabled by this module. Such historical admission stays blocked rather than silently assigning midnight or a next weekday.

Source license/allowed use/terms/retention are versioned in the record. The five captured public sources have `license_type=UNKNOWN`, `terms_version=UNVERIFIED`, and `redistribution_allowed=false`. Their records remain reference-only. Neither a caller setting `source_class=OFFICIAL` nor a claimed timestamp grants production/data-license authority.

## Actual bounded evidence

`public-capture.json` records original raw SHA-256, retrieval time, source URL/policy and resulting reference-only status for five successfully fetched official sources. Each fixture is below 46 KiB.

- [SSE 600000 daily display endpoint](https://yunhq.sse.com.cn:32042/v1/sh1/dayk/600000?begin=-3&end=-1&period=day): two raw unadjusted daily observations, 2026-09-29 and 2026-09-30. It does not supply publication, market availability or preclose fields. The normalized prices preserve raw decimal lexemes; amount is converted exactly to integer cents. These bars remain QUARANTINED / NON_TRADEABLE.
- [SSE autumn holiday announcement](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml) and [SZSE autumn holiday announcement](https://investor.szse.cn/disclosure/notice/general/t20260917_622911.html).
- [SSE session/week rule explanation](https://one.sse.com.cn/onething/gptz/) and [SZSE session explanation](https://investor.szse.cn/knowledge/stock/deal/t20191204_572383.html). The SZSE reference is dated 2019 and is explicitly versioned; P1-A does not certify it as a complete current rulebook.

The official adapter covers only 2026-09-20 through 2026-10-11. Holiday closures and weekday rules come from those explicit exchange documents. It returns 2026-10-08 after 2026-09-30, with auction/continuous-session boundaries. Weekend construction follows the cited exchange rule; it is not a generic weekday calendar. Out-of-coverage dates fail.

Archived copies used by CI have unknown availability. Live-capture evidence records a reference-observation time, but never claims historical observed PIT. No currently admitted real historical market snapshot is claimed. SH/SZ canonical parsing is implemented; a complete authoritative historical security-master/status feed remains missing.

## Snapshot and revision guarantees

The economic input address hashes canonical `{root_refs,closure_refs,feature_version,decision_cutoff,rules_hash}`. Every ref binds exact id/version/hash. Metadata from rejected future rows is omitted. Re-freezing the same economic input returns the first immutable snapshot even when diagnostic trace differs.

Closed lineage includes actual raw bytes, source policy/clock proof, normalized facts, exact security/calendar references and visible status. ADJUSTED bars additionally require exact adjustment/action references, matching security, factor availability and effective/ex-date guards. A factor learned after cutoff cannot enter an earlier snapshot. Financial revisions keep their visible predecessors and cannot overwrite originals. Ingesting future status/revision does not contaminate a prior cutoff.

The manifest alone is not sufficient evidence: consumers must call `verifyDataSnapshot` against this store and use its lineage bundle. P0's strict schema is a projection, not a license, source authenticity certificate or production execution authorization.

## Validation and remaining conditions

The scoped suite exercises identity conflicts, status revisions, official long-holiday references, unknown clocks, forged capture/availability, substitution of future facts into old evidence, original-byte hashes, adjustment closure, financial revision PIT, append-only persistence and one-byte snapshot mutation. The parent owns integration and full migration-sequence checks.

Remaining limitations block real execution: missing licensed/verified historical bars and clocks, complete official security/status history, current session rules for all boards, annual calendar coverage, corporate-action price/entitlement reconciliation, real financial-source parser and revision samples, trustworthy external timestamp/storage authority, external PostgreSQL role/deployment acceptance and continuous production data-health checks. P1-A synthetic replay remains possible; production is permanently closed throughout this stage.
