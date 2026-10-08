# P1-B REAL STOCK SLICE — Fresh independent candidate review

Candidate `ba6cb20efb609757ce198cb52ac13fa23ca5139c`, pinned source tree `sha256:7d20334a66ec4775ca9224355ab612e2c08bee33a0f7311523153a9c2e94aa2d`.

**Candidate gate: FAIL.** Existing unit checks and the parent attack suite do not close two independently reproduced authority defects. This report is immutable candidate evidence, not the final corrected-code decision.

## Executed evidence

The fresh reviewer ran `/independent-review/review-attacks.mjs` from outside the repository. It obtained five actual official SSE HTTPS captures in its own external directory at actual cutoff `2026-10-05T12:45:00.622Z`. The normal frozen path emitted three stock-reference snapshots, three receipts and three LOCAL_REVIEW_ONLY packets. Each snapshot is CLOSED, live price null, trigger false, tradeable false, latest trading session null. Fifteen announcement references and fourteen finite calendar facts are present. Market and financial rows are zero. No secret lookup, authenticated provider access, actual model, broker or execution writes occurred.

The parent base suite was independently invoked against this live registry: 33/33 fail closed. The reviewer authored 38 additional cases: 33 expected outcomes, **five erroneous acceptances**. Together this is 71 executed cases; it is not 71 independent threat categories. All 28 owner-requested threat categories are represented by the base suite; additional cases probe actual issuer receiver dispatch, archive restoration, detached returns, exact refs, terms mutation, native strict Card, supersession, revocation and precise TTL.

Machine record: `review-results-2026-10-05T124459178Z.json`. Execution log: `review-attacks.log`. Exact attacker code: `review-attacks.mjs`. Own raw/terms mutation tests were restored byte-exactly. Final delivery originals were never touched.

## Open findings

**IR-001 / P1 — Replaceable receiver bypasses private admission checks.** `real-slice/src/core.mjs:108–111` invokes `this.verifyReceipt`, `this.packet` and `this.verifyPacket`. Object freezing does not prevent `Function.call`/`apply` from substituting these methods through a foreign receiver. Four independently executed variants succeeded:

1. `service.packet.call({verifyReceipt: async () => true}, backdatedSnapshot, actualReceipt)` minted a schema-valid packet carrying `2026-09-30T00:00:00Z` with the **actual private issuer's valid Ed25519 signature**. This is not a merely caller-signed object.
2. `verifyPacket.call({verifyReceipt: async () => true, packet: async () => originalPacket}, contextWithWrongUsePoint)` returned true.
3. The same replacement returned true after the original receipt had been irreversibly revoked.
4. `transfer.call({verifyPacket: async () => true}, {packet: {raw_document: 'SYNTHETIC_UNAPPROVED_RAW_BODY', token: 'SYNTHETIC_TEST_ONLY', production_enabled: true}}, 'LOCAL_REVIEW_ONLY')` returned the arbitrary payload. Test values were synthetic; no real token was read.

Required correction: internal verification and packet construction must use lexical trusted functions or a closure-bound immutable facade, independent of the public call receiver. Add receiver-rebinding regression tests, preserve original signature/registry/use-point/scope checks, and issue a new committed source pin. This does not authorize any rights expansion.

**IR-002 / P2 — Card TTL truncates fractional precision.** `real-slice/src/fixture-chain.mjs:66` compares clocks using `Date.parse`, which truncates to milliseconds. Actual issued native fixture Card at `valid_until + 1 nanosecond` was accepted; the same Card at `valid_until + 1 millisecond` was blocked. This weakens a declared version-chain invalidation condition.

Required correction: validate actual ISO calendar/time/offset values and compare nanoseconds without truncation. Do not edit the old pinned P1B implementation; its timestamp helper also uses Date.parse for the calendar component, so importing it alone does not prove malformed dates are rejected. Retain exact-boundary and just-before-cutoff controls and add just-after-expiry rejection.

## Evidence that is valid, with limits

Normal paths reject foreign signer receipts/packets, fresh issuer reconstruction, caller-synthetic collector promotion, source product mismatch, purpose and namespace escalation, widened coverage, raw mutation, exact-ref changes and reuse, receipt/policy revocation, cloud/manual-export target and unknown Tushare entitlement. Returned collector buffers and metadata are detached from the registered originals. Terms/raw hashes are checked again on consume.

The native fixture path uses the frozen Closure export/isolated consumer/import and frozen semantics implementation. It validates strict ResearchCard 1.0 and the new sidecar, keeps mandatory identity synthetic, native grade/Edge/sizing/probability UNSET_REQUIRED and action non-executable. Identical replay matched; upstream revisions invalidated the old Card; policy revocation could not be cleared by another producer run. The illustrative assessment S remains only REQUEST_REVIEW. The semantic coordinates are fixed synthetic inputs, not facts calculated from a real company.

Unsupported corporate-action/factor/financial/industry insertion is blocked **at the registered-reference boundary**. Those negative attacks do not prove real history parsers, financial revision lineage, factor calculations, industry PIT or corporate-action math. No such real datasets are admitted. Calendar and announcements are PARTIAL; security/status, raw bars, actions, factors, financials and industry are BLOCKED. Five metadata references per stock do not prove complete 180-day history or PDF bodies.

Actual current retrieval supports current availability only. DATE_ONLY keeps publication date and null instant. Archive signatures are evidence, not restored live authority. Host wall clock and HTTPS collector remain a documented DEV trust boundary. A synthetic A→B test proves invalidation mechanics; **no real post-holiday Snapshot B exists**. A narrow holiday document does not prove 2026-09-30 was the last actual trading session; null is appropriate.

## Conditions after corrections

If a new frozen candidate independently rejects all five reproductions and preserves positive controls, the engineering decision may become PASS_WITH_CONDITIONS while LOCAL_REAL_RESEARCH_GATE remains PARTIAL. Tushare stays BLOCKED before secret/network; cloud, historical, production, redistribution and actual Research Pilot stay blocked. C12–C22 are not closed wholesale: current clock extension and fixture composition are engineering closures only; real security/history/full-calendar/market/action/factor/financial/industry/calibration/producers remain absent. No previous reviewer result is inherited.
