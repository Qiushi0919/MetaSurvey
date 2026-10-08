# ADR-009 — Source observation and admission
Status: accepted engineering constraint within P1-A authorization; production source policy remains UNSET_REQUIRED.

P0 strict DataEnvelope is immutable. A source observation can retain unknown event/publication/availability clocks as null; the object is quarantined and non-tradeable. Retrieved time is never backdated to create historical visibility. Reference documents observed now can prove observation now, not publication or historical availability. Real HTTP capture retains original bytes and an observed retrieval clock. Public access is not an authorization for trading use.

Raw and normalized rows, calendars, security history, financial revisions and corporate action factors are versioned. Snapshot closure checks every dependency at the cutoff before choosing a revision. A later factor/action cannot alter a frozen raw or adjusted view. Content-addressed raw bytes and object hashes are checked again when using the snapshot.
