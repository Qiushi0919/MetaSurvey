# P1-A shared contracts and projections

The frozen P0 sixteen contracts remain version 1.0.0 with their original hashes. `contracts/release.p1a.json` is the separate 1.1.0 engineering release; new module schemas are version 1.0.0 in `contracts/p1a/`. Required arrays and explicit nulls are authoritative; unknown is never silently defaulted. All timestamps require offsets; trading dates and sessions use Asia/Shanghai. Integer cents are canonical strings/BigInt; prices, rates and ratios are Decimal strings. Validation lives in `src/p1a/contracts.mjs`, admission and lineage proof in the data module, exact settlement and reconciliation in cost/paper.

| Contract | Purpose / binding | Invalidation |
|---|---|---|
| SourceObservation | raw bytes + payload hash, four clocks, source/policy, DQ and tradeability; unknown clocks stay null | raw/payload/parser/proof/source policy mutation |
| SnapshotLineageBundle | recursive typed closure, root/closure refs, cutoff, feature version, data/manifest hashes | any input hash/version/cutoff/feature change |
| CostProfile | explicit synthetic PER_ORDER fees, inclusion relationships, dates, rounding, source | version/hash/rate/effective range change |
| P1ACostEstimate | cumulative exact order economics and minimum effect attribution | fills/profile/version/side change |
| PaperCalendarProjection | explicit sessions, source ref/hash, availability/version | session/source/cutoff change |
| PaperSecurityProjection | registry ref/hash, canonical identity, lot/status/version | identity/status/source/cutoff change |
| PaperReplayOrderIntent | synthetic-only terms, exact cost/source/snapshot/feature bindings | terms/version/source/approval change |
| ReplayInputManifest | all source/feature/account/cost/rule/calendar/security/code refs and execution fixture hash | any consumed fixture/input/code change |
| DeterministicReplayResult | input, deterministic orders/fills/ledger/NAV/cost/path outcomes and economic hash | input or economic projection change |
| CostAttribution | gross, all fee components, net and per trade/round/strategy ratios | reconciliation failure or changed economics |
| PathMetrics | MAE/MFE horizons, timing/resolution/censoring conventions | input path/entry/calendar change |
| AuditChainEvent | source/hash/time/security/version/trace and hash chain | chain mismatch; immutable persistence |
| CodeProvenance | actual implementation commit, current and committed source-byte map | uncommitted/current byte or bound commit change |

Actual commission = proportional commission + minimum effect. The effect is a subset, not an extra charge. Total friction uses actual commission + stamp + exchange + other + separately estimated slippage. Included fees/slippage are excluded from explicit charging. Partial fills settle cumulative order deltas; a new ladder order pays its own minimum. Reason codes retain the P0 registry and add a P1-A registry; the three Edge rejection codes are mandatory, production policy is UNSET_REQUIRED.

PaperReplayOrderIntent is a synthetic fixture DTO, not an alternate production approval contract. Its two fixture human confirmations are trusted only by explicit synthetic authority. The P0 ResearchCard→Signal→two HUMAN approvals→OrderIntent rules remain unchanged; LLM review cannot authenticate either approval. P1-A does not implement their business producers or any broker dispatch.

Economic hashes exclude diagnostic trace/runtime wall clock. Input trace is fixed within the snapshot/FeatureSet objects because their full canonical hashes remain binding; runtime trace variation cannot alter economic results. Audit hashes may vary with diagnostic clock/trace and are verified separately. Code provenance is pinned after implementation is committed. Later documentation/evidence commits do not alter the code identity.

CostProfile 的 synthetic 日期区间两端包含。该语义只适用于这个版本的 Paper reference；P0 cost harness 的历史区间语义和真实 Broker AccountProfile 均未修改，真实映射必须另行确认。Ledger entries 是模块版本化事件，来源四时钟通过闭包引用保留；不会把操作时间冒充市场可得时间。
