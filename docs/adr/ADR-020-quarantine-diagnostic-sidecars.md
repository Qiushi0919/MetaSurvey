# ADR-020: Offline quarantine sidecars and fixture separation

Status: Accepted for Owner-authorized T1–T9 engineering only (2026-10-06).

The raw gateway captures contain useful engineering observations but no admitted supplier rights or historical visibility. Normalize them into versioned, deterministic, append-only private diagnostic sidecars. Preserve all original hashes, request clocks, source literals, response DQ and namespace. The registered loader is the only actual input authority. No sidecar can be an admission Receipt, a market DataEnvelope or a real ResearchCard.

Factor arithmetic uses exact rational values and reports missing/ambiguous action links; it does not resolve provider semantics or create an action feed. Financial request dates retain report-period semantics; out-of-scope responses and all observed versions remain quarantined. DATE_ONLY cannot become a publication instant or historical availability.

The fixture chain receives only fixed synthetic cases. Reuse frozen composition/contracts rather than redesigning grade, cost or approval logic. Actual sidecar data cannot cross that producer boundary. Dry-run readiness always reports all real gates blocked and zero issued real objects. Detailed interfaces are frozen in [Interface-Freeze](../overnight/Interface-Freeze.md).

Consequences: no SQL migration or business contract changes in this epoch; evidence remains Git-external and private. Persistent consumers, new business semantics, supplier admission and real Snapshot B need a separate contract/Owner Gate. C12–C22 are not closed by diagnostic readiness; C30 still requires actual forward paper trading days.
