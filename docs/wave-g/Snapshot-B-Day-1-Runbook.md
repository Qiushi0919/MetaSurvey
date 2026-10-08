# Snapshot B / Day-1：单次运行准备手册

本版仅为准备包。actual_forward_days=0；没有实际 Snapshot B 或 Day-1。现有三股日线原件各327个日期，共981行，不含计划2026-10-08数据。日历计划与16:00时间经过都不能替代实际开市、EOD及新响应证据。

已实现：原始响应/单位/四钟精度/原件hash重开、A→B lineage、exact3覆盖、版本和新鲜度校验、独立staging store原子追加、expected-head并发、去重、失败链和只读恢复。该store只接受REAL_SHAPED_FIXTURE_NEVER_ACTUAL_SESSION，不计actualday。真实collector、Human/独立reviewer能力适配及实际namespace/计日绑定尚未部署；本轮禁止启用实际入口。

后续新授权下的单次顺序：

1. 核对最终commit、code/source/policy/strategy/hash，在新exclusive本地epoch保存全部原件和失败。不得覆盖旧run。
2. Owner另行批准一次exact3只读本地capture；冻结source exception/capture acceptance版本和独立角色。Forward NO_DECISION为另一个权限，不能从capture授权推导。
3. 在新的授权范围实现并独立验收实际collector/session/status/clock binding、Human与实际reviewer issuer、accepted-session namespace计日适配。复用已实现staging事务算法，禁止仅切换布尔值。
4. 要求实际open/EOD及三股当日更新响应；每个授权响应只capture一次。失败保存并STOP，不产生B或day递增。
5. 重开raw/clock/A原件，核对hash、source/unit/symbol/session、新capture身份、四钟原始精度、retrieval/cutoff/freshness、覆盖与冻结版本。UNKNOWN publication/first visibility保留；OBSERVED_CURRENT_CAPTURE只能证明当前取得。
6. 实际独立reviewer重开原件并接受精确facts/source exception。PREPARATION_REVIEW_DISPLAY_ONLY和自签hash不能替代实际能力。
7. 仅在另行Forward授权、issuer和namespace都验收后追加一个NO_DECISION/NO_ORDER/NO_BROKER/NO_MONEY/safe_to_trade=false session。计日只在未来已接受actual namespace；fixture/staging/日历/失败次数不计日。
8. 重启先只读验证path/schema/hash/原件/chain；不自动修复损坏。不完整、duplicate、stale-head、版本/时钟/hash故障均STOP并保留失败。单次完成后STOP，不启动schedule。

Packet v1精确字段及可用函数见wave_g/activation.py及本轮Delegate-Report-G7；原件引用固定为{path,sha256,bytes}，Git引用读调用checkout，private原件不移动。当前实际入口execute_capture/run_snapshot_b/run_real_forward/append_actual_session始终先阻断。历史PIT和真钱参数不妨碍纯NO_DECISION准备，但仍阻止经济回测/交易；Provider/License/Transport继续独立BLOCKED。
