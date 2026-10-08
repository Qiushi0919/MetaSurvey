# ADR-037 — Preserve Day0 and append only fully signed Day1 outcomes

Status: accepted engineering choice within Owner DAY1-REVEAL-20261008 scope; not trade authority.

The registered v1, source text, receipt, schemas and previous ZIP are external pinned originals. Reopen all 32 ZIP members and 31 payload hashes before new research operations. A changed receipt cannot register a changed prediction; mismatch stops without repair. Existing ForwardPrediction/ForwardOutcome contracts remain unchanged.

New Day1RevealOutcome metadata 1.0.0 enriches the original reviewed raw-price scorer with explicit target OHLC, price/return/error units and the separate Owner FORWARD proof. The adapter first calls the frozen G store inspector, which verifies actual CAPTURE, independent REVIEW, separate FORWARD and SQL/hash lineage. It requires exactly one accepted Oct8 NO_DECISION record. Snapshot B alone is insufficient for this authorized phase. It reads the G store and never appends days or creates grants.

A separate mode0600 JSONL journal requires an expected head, validates and rescores every original prefix, uses exclusive file locking, appends a canonical line and fsyncs. Duplicate symbols and stale heads are blocked. A crash-truncated last line remains evidence and blocks further writes without repair. This protects cooperating local processes; it does not claim resistance to a compromised filesystem, interpreter or operator. Do not relocate a live journal because its canonical path binds its genesis.

MAE=min(0,(D1 low/base−1)×100), MFE=max(0,(D1 high/base−1)×100), in percent; center error=realized return−forecast center, in percentage points. These are raw-price research excursions, not execution P&L, strategy drawdown or action-reconciled total return. Decimal precision80 comes from the existing scorer. No fees, trading rules or defaults are inferred.

Public enrollment and original public DERs are portable audit evidence; original local paths in enrollment stay intact, not installed into the verifier's machine. Existing setup-test signatures only prove signer interoperability. New detached prediction acknowledgments are explicitly late, unsigned until the Humans sign, and never count as capture/review/forward authority or independent preopen timestamps. The old receipt is not rewritten.

Historical PIT receives a new prioritized gap register without replacing its 60 baseline rows or closing any domain without independent first-visible/cutoff/version/license evidence. History remains diagnostic. No scheduler, Day2, cloud, broker, money or native orders are added.
