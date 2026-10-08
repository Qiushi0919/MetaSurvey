# W2 Data/PIT — bounded current-observed official references

Scope is CORE_40, SSE:603993 / SSE:600312 / SSE:603228 only. The three symbols are engineering validation securities; this phase produces no research score, recommendation, Signal, Approval or Order. Tushare entitlement was explicitly reported absent by the human and stays BLOCKED.

## Actual capture and deterministic projection

The new parent collector performed five successful TLS captures on 2026-10-05, with completion clocks from `2026-10-05T12:26:48.669Z` through `2026-10-05T12:26:49.359Z`. The original bytes and signed capture records are outside Git under `.p1b-archives/real-stock-slice-20261005/data/`; the first diagnostic manifest is `capture-2026-10-05T122649541Z.json`. This manifest is archival evidence, not a capability for restoring a live issuer or self-admitting data after restart. The parent final Gate run captures again after the code epoch is pinned.

| Captured original | Raw SHA-256 |
| --- | --- |
| SSE website legal statement | `26733c0c6cd93428d1ec5d62401b6ad269a26990a9181c5f5d63237c35431f69` |
| SSE 2026 holiday notice | `779cbf7cc7ab2c4b34db17ceee29e266bc483e075860d8313b85c1d5d0f307bc` |
| 603993 disclosure metadata | `17338562bc659bec549e65dcfe5890a548081be735c88c8b0c760e71d97f297f` |
| 600312 disclosure metadata | `637dbfa67533c258ae2f6c21ddedf2d27a53ca371d0c4ae13419599c54aa59d1` |
| 603228 disclosure metadata | `6346c4bf74263cf25bcdaeb5a92109022b2ba74a770220f78f7fc5d7a45aaf4c` |

The official disclosure website response returns a 25-row cache despite a five-row page request. The approved projection takes only the first five actual metadata records per security: **15 document references** total. The original cached response is retained unchanged. No additional pages or stock universe were fetched. The initial query without the website's pagination/type parameters returned empty lists and was rejected as unusable evidence; no records were synthesised from those responses.

Each projected reference contains exactly kind, symbol, date, title, official URI and nullable document SHA-256. SECURITY_CODE must match the exact requested security. SSEDATE is a date, never a midnight instant. The official document URI must preserve the security and publication date and remain on the reviewed SSE website path. Duplicate or malformed references, changed source/product/window and unexpected page parameters fail closed. ADDDATE and all other unused raw fields stay outside the approved projection. The current publisher dates are 2026-09-19 for 603993 and 2026-09-30 for 600312 / 603228. They do not assert exact intraday publication or earlier system availability.

The parent collector alone supplies retrieved_at / observation_event_at; the current-observed implementation uses available_at = retrieved_at. No provider operational update window, document filename date or ADDDATE substitutes for this collector boundary. Historical visibility remains false.

## Eight requested categories — honest incompleteness

| Category | Current evidence | Status against requested slice |
| --- | --- | --- |
| Security/status | Security identity in five disclosure references per symbol; no complete listed/suspended/status history | BLOCKED |
| Calendar/rules | Fourteen explicitly announced closed/reopening dates in the holiday notice; no exact 320-session calendar | PARTIAL |
| Raw bars | No licensed market rows collected; no 320-session OHLCV dataset | BLOCKED |
| Corporate actions | Some titles may refer to corporate actions; no parsed official action terms, effective intervals or complete window | BLOCKED |
| Adjustment versions | No captured factor versions or action reconciliation | BLOCKED |
| Financial revisions | Document pointers do not prove twelve quarters, financial fields or predecessor/revision completeness | BLOCKED |
| Announcements | Five metadata references per security within the approved 180-day query window; no full-window or revision completeness claim | PARTIAL |
| Industry membership | No licensed membership/effective-history rows observed | BLOCKED |

A document reference, including a financial-report or dividend title, never becomes structured financial/corporate-action data by inference. `coverage.complete=false` is explicit in every current source projection. Missing categories have no synthetic or legacy fallback.

The admitted calendar facts can prove 2026-10-05 is CLOSED, and that the notice says trading resumes on 2026-10-08. They do **not** independently prove 2026-09-30 was the latest actual trading session. latest_trading_session therefore remains null. No 2026-10-05 price, live trade trigger or tradeability is produced. Snapshot B has not occurred; only the parent's clearly marked synthetic comparison can test future invalidation.

## Rights and original-document limits

The [SSE website legal statement](https://www.sse.com.cn/home/legal/) supports a narrow noncommercial local browse/download reference role under its conditions. This is the captured policy evidence for these exact website pages. It does not grant a global SSE market-feed entitlement, bulk licensed data rights, cloud raw transfer, redistribution or historical PIT rights. This phase keeps these purposes denied/blocked. The [holiday notice](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml) supplies the finite official calendar facts.

One exact first-row PDF per symbol was requested as an optional original-file reference. All three initially failed closed because the www.sse.com.cn document links redirect to static.sse.com.cn and the collector forbids implicit redirects. A finite diagnostic check of the 600312 URI observed HTTP 301 with a same-path static.sse.com.cn Location. These failed PDF attempts do not become successful original-file captures, parsed financial evidence or document SHA values. Any separately reviewed exact static capture remains quarantined unless the parent binds it to the already observed index and a new exact policy. Current admitted index references retain `document_sha256=null`.

Tushare is implemented as a bounded candidate adapter that throws SLICE_ENTITLEMENT_UNKNOWN before secret lookup or network access. Even a caller-supplied `{verified:true}` object cannot become the parent's verified entitlement. No Token, secret store or authenticated API was accessed. A future authorised structured-provider implementation must bind current agreement, actual account/product entitlement, local purpose, storage/retention, transfer rule and source version; provider documentation alone is insufficient. BaoStock and formal historical providers were not queried or promoted.

## Tests and boundary

`real-slice/tests/data.test.mjs`: **20 PASS, 0 FAIL**, all fixtures explicitly SYNTHETIC_TEST_ONLY. Checks cover absent/caller-forged entitlement with zero network/secret calls; source/product/security/window/page mismatch; malformed or empty originals; URL security/date/host mismatch; title/duplicate DQ; DATE_ONLY without midnight fabrication; ignored ADDDATE and raw future/financial fields; finite calendar coverage without weekday inference; and local-only terms. These are parser and adapter checks. The parent independently validates actual collector clocks, admission policies, receipts and capability revocation; the source tests do not claim synthetic evidence has been real-admitted.

No legacy code, seal, ledger, database, run, historical result, shared schema, migration, cost/grade rule or Git state was edited by this Data/PIT task. Files owned by this task are the provider/capture code, these source tests and small synthetic fixtures, capture-specs.json and this note.
