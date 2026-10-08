# P1-A independent review record

Reviewer is read-only and does not choose business parameters. Reviewed implementation commit: `8cca36056bde7cf55bf84bb699d59905994cb724`; source tree: `sha256:aa8902654fdec40134b862f9abff91330caadddcff7c8ac82bde494d4abff46a`.

Complete independent `npm run check`: exit 0, 210 tests, 209 PASS, 0 FAIL, 1 optional external legacy SKIP. P0 restore was separately exercised: 98 tests, 97 PASS, 1 SKIP. P1-A clean checkout/log hashes and distinct empty npm configuration files were independently checked.

| Discovered defect / attack | Final resolution and evidence |
|---|---|
| Normalized price could reuse raw evidence containing another value | Source raw.fact → typed payload → normalized facts compared again at closure; original substitution rejected |
| Visible suspension absent from bar closure | Latest effective visible security/status selected at cutoff; omitted/non-tradeable status rejects admission |
| Self-sealed security/calendar projection could diverge from actual snapshot | Read back exact registry/calendar refs, fields, source hashes, sessions and versions before orders |
| Consumed cash/session fixture values not bound | Complete execution fixture hash plus account/source/calendar consistency; hidden input change rejects |
| Adjusted factor accepted Infinity | Canonical finite bounded Decimal strings at ingest and read-back; Infinity/NaN/exponent/overprecision reject |
| Individually legal gross/fees could create 39-digit all-in money | Final monetary bound checked; original case rejects MONEY_OVERFLOW |
| Oracle used textual date slice with negative time-zone offset | Independent Shanghai-date conversion, valid negative-offset scenario reconciles |
| Whole-order rounding could differ from partial-fill gross | Replay attribution derives actual cumulative gross; 20002-cent split-fill case reconciles exactly |
| Audit refs/parent refs/free text could leak synthetic secrets | Strict three-field refs/hash; recursive structured/string redaction; original synthetic metadata attacks reject/redact |
| TRUNCATE bypassed UPDATE/DELETE immutability | Statement triggers added before release; nine source/paper/replay tables reject non-owner TRUNCATE CASCADE |

Final six cross-module attacks: altered fixture cash, security symbol, security lot, calendar source hash, calendar sessions and future feature value. All rejected at the intended source/input guard, with ordersWritten=0. No early code-provenance failure was counted as a source attack closure. Nine non-owner TRUNCATE attacks independently rejected.

The reviewer also inspected the saved Experiment A eight-field equality and three mutation hashes; Experiment B fixed signals/prefriction/gross and monotonic friction/net/counts were independently checked. Selected legacy anchors remained identical; native compatibility still fails on CLI hash and seal_modified=false.

Recommendation: PASS_WITH_CONDITIONS for P1-A offline engineering. Real historical source availability/licensing, full official security/calendar/action/financial admission, external PostgreSQL multi-connection/deployment, zero-cash SELL limitation and non-DLP redaction limits remain explicit. P1-B and production remain blocked; a technical recommendation does not constitute the user's acceptance.

Final document consistency review completed read-only: all 25 Gate items and report links, code/source-tree/economic/ledger hashes, 29 frozen P0 files, 30 UNSET entries and 63 required leaves, all five migration checksums and 60 tables (51/7/2), five source raw hashes/sizes/admission states, and all three Source-of-Truth fingerprints matched actual evidence. No report correction was requested. The reviewer confirmed offline PASS_WITH_CONDITIONS, user acceptance PENDING and P1-B/production BLOCKED. The annotated delivery tag is created by the parent after the final documentation commit; it is not a business authorization.
