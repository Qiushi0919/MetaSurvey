# P1-A delegated task contracts

Authority: formal handoff, accepted P0, explicit user request in authorizations/P1A-20261005.md. P0 tag/bundle/clean reproduction and permanent production guard were established before A/B started. Parent owns contracts, ADRs, reason codes, numbering, review and merge. Only A, B and the independent reviewer were used.

| Field | Agent A — Data/PIT/Security | Agent B — Cost/Paper/Oracle | Independent Reviewer |
|---|---|---|---|
| Goal | Bounded real evidence and cutoff-safe data backbone | Independent exact economic/reference state machine | Find bypasses in contracts, migrations and tests |
| Context | Real clocks/permission unknown must quarantine | All rates/account values synthetic; real values UNSET | Read-only adversarial review; no business rule changes |
| Inputs | Formal handoff, P0 release, public official samples, explicit fixtures | Frozen contracts, explicit CostProfile/intent/security/calendar fixtures | P0 archive/reproduction plus actual A/B/integration candidates |
| Outputs | data API, 003, source captures/provenance, scoped tests/docs | cost/paper/oracle APIs, 004, fixtures/tests/docs | Defect messages, independent command/attack results and conditional recommendation |
| Interfaces | db.exec/query; source observations, registry/calendar/raw-bar/action/revision closure | db.exec/query on same connection; cost estimates and persistent lifecycle | Read current source; write only isolated in-memory/temp test databases |
| Constraints | No clock invention, silent identity merge, future factor/revision or legacy writes | No legacy economic imports/network/broker path/LLM authorization/real defaults | No repository edits, source reset, seal changes or relaxed safety assertions |
| Tests | 14 scoped tests: raw/fact, clocks/status, future actions/revisions, mutation/truncate | 23 scoped tests: exact fees, cash/lot reservations, partial/cancel, T+1/restart/oracle | Full check, six cross-module mutations, nine non-owner truncate attacks, archived logs/hashes |
| Definition of Done | Parent integrates API and contiguous migration; unknown real admission explicitly retained | Parent integrates and independently checks paper and deterministic experiments | Discovered engineering blockers fixed/retested; conditions clearly separated from business acceptance |

A worked at `.p1a-worktrees/data` on p1a/data (commit baf08bb); B at `.p1a-worktrees/economics` on p1a/economics (commit 49e0b45). App worktree creation could not find its Git runtime; the parent used Homebrew Git worktrees as a documented fallback. No shared checkout was used for their edits. Parent cherry-picked their owned files, aligned canonical SSE/SZSE names and tightened pre-release DDL against TRUNCATE. Main stays at accepted P0; integration is p1a/integration. These local worktrees are not Codex-managed worktrees.
