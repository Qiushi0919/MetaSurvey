# P1-B0 RI: Research semantics and cloud evidence boundary

Scope: user `P1B-20261005.md`, `Interface-Freeze.md`, parent `Interface-Clarifications.md`, and the ResearchCard Contract Fit Analysis. This task implements only pure semantic templates and pending research leads. No real Research Producer, model call, stock selection, new database, evidence fetch, trust-promotion capability, EVENT, GUI or broker is created. Parent owns shared contracts, config, release and Git commits.

## Ten dimensions and provisional semantics

The input preserves independent `company_quality`, `sector_quality`, `catalyst`, `evidence_quality`, `valuation`, `timing`, `risk`, `cost`, `account_suitability` and `tradeability` states. Each is exactly `PASS`, `GAP`, `UNSET_REQUIRED` or `NOT_APPLICABLE`. No numeric score, real-account claim, probability, approval or order field is accepted. The semantic scope is exactly `SYNTHETIC_SEMANTIC_TEST_ONLY` and strategy is CORE_40. Every output is an immutable ResearchAssessment 1.0 sidecar, with distinct `research_grade` and `actionability_grade`, real suitability BLOCKED, real net edge/sizing/probability UNSET_REQUIRED, and order/production false.

The HIGH research axis requires company, sector, evidence, valuation and risk PASS. Timing, cost, account and tradeability do not become PASS because quality is high. This is an abstract checklist template, not a validated financial ranking or calibrated model. `85 / 80 / 78` remain configuration reference values with mapping UNSET_REQUIRED; the API does not consume them or convert them to grades, odds or win rates.

| Grade | Precise template rule | Next action |
|---|---|---|
| X | Known synthetic hard-block example exists, or explicit risk GAP | BLOCKED |
| UNSET_REQUIRED | Required company/evidence/risk check is unknown or NOT_APPLICABLE, or no known illustrative evidence ref exists | UNKNOWN |
| S | All ten abstract checks PASS, known illustrative evidence exists, no hard block | REQUEST_REVIEW |
| A | HIGH research axis, but timing/cost/account/tradeability has an unmet or unknown check | WATCH |
| B | Company or catalyst logic exists while other gaps remain | NO_ACTIVE_TRADE |
| C | Only observation/research value remains | RESEARCH_ONLY |

Hard Block precedence is above quality and timing. S is only `PROVISIONAL_ACTIONABILITY_TEMPLATE_NOT_RECOMMENDATION`; even all-PASS fixtures do not demonstrate real account suitability, real net edge, real sizing or real tradeability. The input `tradeability=PASS` is a hypothetical template premise, never a real executable conclusion. All real outputs remain blocked, including S.

“Why A rather than S?” is explained by the unchanged HIGH research grade and the explicit unmet entry dimensions, plus uncalibrated/edge/account/non-execution reason codes. Timing GAP additionally carries `P1B_TIMING_UNSATISFIED`. To illustrate A→S, all remaining ten checks must become PASS, the exact illustrative evidence ref must remain present and there must be no hard block. Passing timing alone cannot upgrade an A whose trigger/edge abstraction in tradeability remains GAP. A→X occurs on the known hard-block example or risk GAP. These changes create a different object identity/hash and do not grant execution authority. Unknown mandatory checks produce UNKNOWN, never S.

## Reference limits and contract fit

Current `evidence_refs` accepts only `synthetic:semantics:admitted-local-example`; `hard_block_refs` accepts only `synthetic:semantics:hard-block-example`. Both are object version 1 with `hash({fixture_id:object_id,scope:'SYNTHETIC_SEMANTIC_TEST_ONLY'})`. They are explicit test examples agreed by the parent, not real admitted facts or authentication of local evidence. Cloud objects, cloud refs, citation strings, additional trust assertions, changed hashes/versions and duplicate refs are refused. Nothing in this API can relabel a discovered real-world source into an admitted example. A caller can deliberately construct the known synthetic template, but its scope and blocked real outputs cannot change.

ResearchCard 1.0 remains unchanged and its four layers are preserved. `research_card_ref` is null-only at this first Gate until an approved explicit Card adapter exists. The schema reserves future nullable binding without pretending an arbitrary caller reference has been verified. ResearchAssessment input identity includes dimensions, illustrative refs and scope; the original input belongs to the deterministic fixture replay. The sidecar does not add unversioned fields to frozen ResearchCard, Snapshot, Closure or execution objects.

## Cloud-discovered evidence

`ingestDiscoveredEvidence` records only a public HTTP(S) citation pointer, descriptive lead, offset discovery timestamp and LLM/manual lead origin. It performs no URL request, raw capture or DB access. Credentials, internal paths, local endpoints, secret query parameters and caller-supplied admission/available_at/license/approval fields are refused. The immutable result is always CLOUD_DISCOVERED_EVIDENCE / PENDING_VERIFICATION, admission_ref=null and all hard-block/grade/sizing/order/production flags false. A future discovery timestamp remains a pending lead; it is not publication or historical availability proof.

`assertEvidenceUse` permits only RESEARCH_LEAD and COUNTERARGUMENT. It rejects setting or clearing Hard Block, grading, upgrades to S, sizing, signal, approval, order/fill, historical PIT/backtest and admission purposes. Resealing caller claims such as ADMITTED_LOCAL_EVIDENCE, ADMITTED status, receipt refs or true usage flags fails. A lead's text may contain a cited claim or malicious approval wording, but remains an untrusted narrative and cannot act on any of those assertions.

`describeVerificationWorkflow` describes capture original source → hash bytes → verify event/publication/availability/retrieval clocks → verify source/terms → verify purpose/namespace/coverage → approved policy → verified receipt → explicit versioned local adapter. Citation and manual assertion cannot substitute for these steps. The current API exposes no general trust-promotion entry point and describes no fictional working bridge.

## Scoped verification and remaining work

RI tests: **12 PASS, 0 FAIL** on Node 24.19.0: 7 semantics tests plus 5 evidence tests. They exercise every independent dimension and unknown state, grade precedence, high-quality timing gaps, missing evidence, A→S/A→X conditions, numeric/probability injection, real/production scope escalation, cloud/ref/caller trust injection, trust relabel/reseal, unsafe URI/secret/path inputs, future discovery timestamps and execution false. Outputs validate against the parent-frozen schemas; no expected financial outcomes or business defaults were modified.

Owned paths: `p1b/src/semantics.mjs`, `p1b/src/evidence.mjs`, `p1b/tests/semantics.test.mjs`, `p1b/tests/evidence.test.mjs`, and this note. Full Golden regression, actual source admission, scoped real packet, code provenance, new independent review and the 20-item DATA/SEMANTICS Gate remain parent-owned. Real Research Pilot, real stock recommendation, real account sizing, broker and production remain blocked pending the required later approvals.
