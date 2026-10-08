# Post-Wave-E preparation interface freeze 1.0.0

Parent owns contracts, rules, ADR 029–031, release numbering, source pins, Git,
actual source projection, integration and acceptance. Exact three symbols only.
663 predecessor files immutable; only AGENTS/README/source-of-truth navigation
may change. No new source/credential/network/scheduled calls. Private artifacts
outside Git, directories0700/files0600. No numerical actual source data in Git.

The current human accepts Wave D/E WITH CONDITIONS, without rewriting either
historical Gate. This phase prepares interfaces; it does not admit sources or
prove historical PIT. New contracts version1.0.0 are metadata/display-only.

## PIT delegate

Own only post_wave_e/pit.py and tests/test_pit.py. Pure interfaces:
`select_financial(records, symbol, period, cutoff, mode)` and
`select_tradeability(records, symbol, effective_at, cutoff, mode)`;
`financial_readiness(inputs)` and `tradeability_readiness(inputs)` summarize
immutable Wave D input metadata. Inputs never create source/clock authority.
Modes OBSERVED_AT_TIME and HISTORICAL_AVAILABILITY_RECONSTRUCTION preserve
ADR004/009: event time may be a future scheduled action; date-only publication
is never midnight; historical reconstruction never asserts observed then.
Positive evidence is explicitly SYNTHETIC fixture-only. No actual historical
proof issuer exists. Output status UNKNOWN/BLOCKED on absent/unproven/conflicting
data; never infer safe status or universe from current rows or absence. Preserve
original source version/hash/ordinal and late revision visibility. Prefix
selection metadata/counts/hash must exclude future rows. Define strict record
shapes in module docstring; no financial statement values in Git except labelled
synthetic fixtures. Parent adopts/reviews shapes before release.

## Forward delegate

Own only post_wave_e/forward.py and tests/test_forward.py. Interfaces:
`readiness()`, `create_fixture_store(path)`,
`issue_fixture_authority(kind,evidence)`,
`append_fixture_record(path,authority,record,expected_head)`,
`inspect_fixture_store(path)`, `run_real_forward(*args,**kwargs)`.
SQLite append-only storage separate from main database/migrations001–006.
Persistence/reopen/hash-chain/dedup/concurrency rollback tested; NO_DECISION
records append without native Candidate/Signal/Order writes. Only clearly
SYNTHETIC fixture authority can append; LLM approval cannot act as human. Bind
scope/account/strategy/mode, snapshot/version and clocks. Reject same-bar
hypothetical fill and T+1 violation if supporting hypothetical fills. Synthetic
days always actual_forward_days0. Real runner hard BLOCKED unconditionally;
no caller boolean/path/receipt/policy can unlock. No real source captures,
account defaults, OrderIntent/Fill issuance or permissions. Root common.py is
read-only to delegates. Define exact shapes in module docs.

## Root and independent review

Root adds action/evaluation/provider/preflight/closed-factory modules. Fresh
Independent Reviewer after candidate is read-only on all code/rules/source;
writes only private review artifacts. Attack future leak, revision/universe
backfill, absent status, same-bar fills, double action, synthetic fee/forward
promotion, diagnostic strategy promotion, LLM human confusion, provider/license
and Order/Broker authority leakage. Business critical false acceptance -> FAIL
and STOP; preserve harness failures separately with actual available evidence.

JSON schema or self-resealed hash can be DISPLAY-valid and never live authority.
Every closed object is bound to predecessor and adopted raw source bytes.
Do not overwrite previous producer/capture epochs. Finish fresh offline
regression, deterministic replay, independent review, rollback/Gate then STOP.
