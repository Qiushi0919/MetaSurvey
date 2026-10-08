# ADR-022 — Wave B checkout relocation with unmoved evidence

2026-10-06 · Parent engineering correction; no source permission change.

The initial candidate e5142a2 fails actual fresh-checkout verification because the new frozen producer derives its archive path from the checkout location. The failed log and original commit are preserved. G2 producer bytes/raw/collector clocks remain immutable.

A new read-only evidence_root verifier binds only its path comparison to the exact existing Owner archive `/Users/qiushi/投资研究/.p1b-archives/wave-b-20261006/captures/WAVE-B-PROBE-20261006-G2/report.json`. It uses the unchanged producer verifier code with copied globals; it never modifies module globals, sends requests, reads credentials, alters parsing, approves policies or supplies clocks. Unknown roots/paths/extra fields and byte mutations fail. Candidate registration binds this new verifier's own source hash.

Only relocated checkout with this private archive unmoved is supported. No universal/remote CI portability or moved archive restoration is claimed. G2 analysis output is preserved and superseded by G3 with a fresh code/input identity; old failed candidates are not rewritten.
