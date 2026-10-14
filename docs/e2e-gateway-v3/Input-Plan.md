# Gateway V3 input successor — preregistered construction plan

Recorded before any Gateway V3 strategy outcome: 2026-10-14. This is an input-source successor, not a new economic strategy. The existing V2 engine, its namespace, frozen strategy, nine contemporary sample members, window, cash, risk and fees remain unchanged. Root records the exact freeze timestamp and hashes before the real run. No engine execution is performed by the builder.

## Source and authorization boundary

Owner explicitly authorizes the existing fixed monthly gateway for local reconstructed-history diagnosis. The receipt must say `OWNER_AUTHORIZED_LOCAL_USE_UNVERIFIED_PROVIDER_LICENSE`; source identity and license are not independently certified. No production, cloud transfer, redistribution or original PIT admission is implied. The builder never reads credentials or performs network requests.

The root-owned source policy and capture receipt bind the endpoint identifier, Owner authorization reference, exact request scope, actual retrieval clocks, raw response bytes, canonical field/item wrapper, hashes and row counts. Every raw file remains outside Git. No success claim may be made from an API response alone.

## Predeclared field mapping

| Product | Required fields/use | Unknown or conflict |
|---|---|---|
| `trade_cal` | Both SSE/SZSE full civil dates, `exchange,cal_date,is_open`; equal open-day sets for this shared-account engine | Missing civil day, mismatch or duplicate blocks |
| `stock_basic` | `ts_code,exchange,market,list_date,delist_date,list_status`; exact frozen identity and mature mainboard sample | Current identity and listing window only; not historical ST, relisting or exchange-exception certification |
| `daily` | RAW `open,high,low,close,pre_close,vol,amount`; volume hands×100→shares, amount thousand-CNY×1000→CNY | No prices invented for missing bars; malformed volume/units block |
| `stk_limit` | Actual `up_limit,down_limit` per symbol and trading date | Missing, zero, null, inverted or unsupported sentinel values block; no normal-limit default |
| `suspend_d` | `trade_date,suspend_type,suspend_timing` | Empty response alone does not prove absence of suspension; missing daily bar requires explicit all-day suspension; intraday timings block |
| `dividend` | Only implemented events; tax-before `cash_div_tax`, mandatory total `stk_div`, nullable components `stk_bo_rate` / `stk_co_rate` checked when reported, registration/ex/payment/bonus listing dates | Unimplemented proposals and `停止实施` retained as excluded evidence; missing required dates or conflicting revisions block |
| `namechange` | Identity, name, start/end and optional announcement dates, duplicate checks; local 1000-row cap | Reference only; neither historical status certification nor independently complete history. Cap is an engineering bound, not a claimed supplier limit |
| `adj_factor` | Current captured factor sequence as action-consistency evidence only | Missing/change unexplained by implemented events blocks; never used to back-adjust all history |

The [`daily` documentation](https://tushare.pro/document/2?doc_id=27) identifies its output as unadjusted, omits suspended-period bars, specifies volume in hands and amount in thousand CNY, and defines `pre_close` as the ex-right reference. These are adapter unit semantics, not proof of the gateway provider's identity.

The [`stk_limit` documentation](https://tushare.pro/document/2?doc_id=183) identifies actual daily upper/lower limit fields. The [`suspend_d` documentation](https://tushare.pro/document/2?doc_id=214) distinguishes suspension/resumption and intraday timing. No empty response is promoted to an independently verified all-session tradability statement.

The [`dividend` documentation](https://tushare.pro/document/2?doc_id=103) distinguishes gross/net cash, stock components, record/ex/payment and bonus-listing dates. Gross cash and total bonus must reconcile with the ex-right daily reference; unsupported actions remain blockers.

## Cross-domain checks

Every exchange session and symbol must have either (a) a positive-volume daily bar plus actual valid daily limits without a contradictory suspension event, or (b) an explicit all-day suspension event with no trading bar, normalized to null OHLC and zero volume. A resumption record is not a replacement for a daily bar. Intraday suspension is not silently treated as an ordinary open.

Price history must explain each transition from the preceding genuine RAW close to the next supplied `pre_close`: unchanged without an intervening event, or the frozen gross-cash/share-ratio transformation when an implemented event exists. Factor changes provide an additional event inventory check. These are reconstructed consistency checks, not original PIT claims.

V2 action requirements remain: adjacent record/ex exchange sessions; integer held-share entitlement; conservative simulated 20% cash withholding; real cash payment date only when cash exists; real bonus-listing date only when shares exist. Missing required data must remain blocked. The builder must never invent event dates to satisfy the engine.

## Verification

Synthetic archive tests cover complete construction, decimal units, missing/zero limits, missing bars, explicit suspension, intraday suspension, calendar and identity mismatch, missing action dates, factor/price conflicts, raw/hash tampering and receipt replay. They do not count as a real market run. Root separately verifies source receipts and runs the unchanged V2 engine after freezing code and input hashes.

## Capture continuation and failure accounting

A successor epoch may inherit successful/empty wrappers only when a same-archive `capture-*` predecessor Manifest is hash-bound, its actual wrapper and raw response bytes reverify, and copied bytes match its successful receipt. All predecessor paths are checked for aliases, cycles and depth. Failed product receipts remain preserved and cannot supply input tables. Partial construction reports captured daily rows and per-product status separately from normalized/admitted execution rows.

## Empty-schema and unknown-value treatment

Every successful product must include its required field schema even when there are zero rows. A response with both empty `fields` and `items` is insufficient evidence of no events; raw capture remains preserved and the product remains blocked. Null dividend components are unknown and never converted to zero; an explicitly reported total stock entitlement remains usable, subject to reported-component compatibility. `namechange` is labelled `REFERENCE_ONLY_NOT_HISTORY_STATUS_CERTIFICATION`: its identities, date syntax/order, duplicates and a local 1000-row bound are checked, but no independently complete ST/relisting history is claimed. The boundary is current basic identity plus actual observed daily limit values, not a relisting audit.

## Pre-run disclosed-total and duplicate-row interpretation

Registered on 2026-10-14 before any Gateway strategy outcome, following source-field review: `stk_div` is the mandatory total stock entitlement. A known total zero proves no stock entitlement without guessing unpublished component values. Null `stk_bo_rate` / `stk_co_rate` remain `NOT_REPORTED`; reported components must be nonnegative and no larger than the total, and when both are reported their sum must equal it. Positive known total can be used without classifying its internal bonus/transfer split; the same gross economic ex-right bridge still applies. Missing total or gross cash remains blocked.

Multiple disclosure rows for the same ex-date are normalized to one economic event only when all execution values/dates, reporting period and implementation-announcement date agree; differing disclosure announcement dates remain separate source-row hashes and dates. Any conflicting economic value/date blocks. Exactly duplicated name-reference rows can form one reference view while every original row/hash remains counted; inconsistent records sharing one identity remain blocked. These are source interpretation changes, not strategy threshold changes.

`div_proc=停止实施` is explicitly excluded from executable actions and retained with original row hash and process label. Exact duplicate name-reference rows retain `observed_rows`, `unique_reference_rows`, `duplicate_count` and individual disclosure hashes.

## Input policy 3.0.1 — narrow empty suspension-table compatibility

Registered before strategy execution at 2026-10-14T09:11:17.717939+00:00. Prior 3.0.0 policy is preserved byte-for-byte in `Input-Policy-3.0.0.json` (sha256:277255bc25ad7ec699323b9081a17f15e0bedbb4a303daff7075c37239c21b22). Reviewer checked the official HTTP / SDK empty-table contract; this documents compatible response semantics, not independent completeness of this gateway.

Only `suspend_d` with integer HTTP 200, integer response `code=0`, exact raw `data={"fields":[],"items":[]}`, wrapper `EMPTY_RESPONSE`, exact requested fields `ts_code,trade_date,suspend_timing,suspend_type`, valid raw/receipt pins, exact fixed request scope and valid actual clocks can be recognized as `EMPTY_TABLE_SCHEMA_NOT_RETURNED`. It retains `schema_verified=false` and `intraday_halt_absence_proven=false`. No raw field is added or rewritten.

The compatibility branch additionally requires positive-volume actual daily bars, valid actual limits and factor records for every calendar session of that security. It cannot create any missing bar or represent a suspension as trading. Other products with no schema, partially missing suspension schema, malformed nonempty tables, false/string status codes, wrong requested fields, missing daily/limits/factors, and explicit intraday suspensions remain rejected. Source authorization remains Owner-bounded reconstructed diagnosis with unverified provider/license and no original PIT claim. No strategy, price signal, portfolio, cost or old V2 changes.

### 3.0.1 non-implementation enum addendum — 2026-10-14T09:14:10.255206+00:00

Read-only capture-04 review found `预披露` in two 600312.SH disclosure rows and one 601179.SH row. Their record/ex/pay/bonus-listing/implementation-announcement dates are all null. Root approved explicit non-implementation classification before code freeze or strategy execution: preserve process label, source-row hash and all date fields in audit, exclude from executable actions. A `预披露` row carrying any record/ex/pay/bonus-listing/implementation-announcement date is a conflict and must block, not silently exclude. Prior 3.0.0 snapshot is unchanged. Private evidence review hash: `0c4d482753838dbf6624fa062554742ee4ea03b9754810805344644f70275255`.

## Input policy 3.0.2 — explicit rejected dividend proposals

Registered before any strategy run at 2026-10-14T09:26:54.542622+00:00. Prior 3.0.1 code/policy remain preserved by commit `247da84`; old Freeze is unchanged. Previous policy hash: `sha256:09a17bef6ff4d345b5c8f846e46a5fef8ea994c342e651a2d6313a676884e74f`. Root will produce a separate Freeze-R2 rather than overwrite the earlier freeze.

Capture-04 紫金 601899.SH contains `股东大会未通过` and `未通过`, one historical 2011-period disclosure each, with all record/ex/pay/share-listing/implementation-announcement dates null. Final 江铜 600362.SH dividend capture was checked before this single combined revision; it adds no unknown process enum. These two exact rejected-proposal states are explicit non-implementation exclusions, with process, all date fields and original row hashes retained. Any such row carrying an execution-related date blocks as `NONIMPLEMENTED_WITH_EXECUTION_DATES_CONFLICT`. Unknown states remain blocked. This does not alter strategy, universe, clocks, portfolio, fees or prices.
