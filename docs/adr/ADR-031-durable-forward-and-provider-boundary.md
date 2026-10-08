# ADR-031 — Durable Forward storage and unverified evidence intake

Status: accepted preparation boundary; actual runner BLOCKED. Version1.0.0.

New isolated SQLite storage implements append-only NO_DECISION records, schema
and path binding, transactional expected-head checks, duplicate/day prevention,
whole-chain verification and reopen/replay. It has no Candidate/Signal/Order/
Fill tables or issuance. Synthetic human capabilities remain process-local;
the fixture ledger persists. A shape-valid or consistently resealed database
is never an independently authorised actual Paper session. Filesystem owner/
hostile interpreter rewriting an entire store is outside hash-chain integrity
proof; this still cannot create real authority here. Main schema6/migrations
001–006 remain unchanged. Synthetic days count zero actual Forward days.

The real runner and Snapshot B entry unconditionally block. Caller booleans,
LLM APPROVE, JSON hashes and source success cannot unlock. No scheduler/waiter
is created. Actual reopening/EOD and a fresh HUMAN Owner authorization are
required later, as are versioned account/cost/risk/strategy policies.

Redacted provider evidence intake accepts bounded local JSON only from the
designated provider folder and copies exclusively into private staging. It
rejects credential/query-bearing text, binds document hashes, and never
validates license/identity/transport/entitlement or source historical PIT.
Absent order/product/expiry/purpose materials remain UNVERIFIED. Existing
captured official docs are reusable semantic evidence, not account entitlement.
No new network or credential calls are needed. All actual higher Gates block.
