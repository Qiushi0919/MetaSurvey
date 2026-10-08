# ADR-006 ResearchCard → Signal → Approval → OrderIntent 版本链

状态：P0 工程实现，待 Gate Review。

决定：所有引用绑定 id/version/content_hash，并保留 trace_id。Signal.rule_version 必须匹配卡片，已触发状态必须有 trigger 时钟。批准分 DECISION_APPROVAL 与 FINAL_ORDER_CONFIRMATION，两者只能由可信人类上下文认可，不能由 LLM APPROVE 满足。

第一阶段确认研究/信号；最终确认绑定明确 side/quantity/limit price/cost/account snapshot/client id 和有效期。不可变未签草稿承载最终条款；条款 fingerprint 不包含最终批准引用或后续状态，避免循环 hash。SQL 中的草稿引用表达版本关联，不能把初始研究批准解释成已经确认条款。

任何条款、卡片、信号、规则、成本或账户快照变化都使旧批准链失效。scope 同时绑定账户、模式、策略和证券。订单/成交幂等键在账户/模式内唯一，跨策略也不能重复。

P0 只有静态/关系校验和测试桩，没有登录认证、完整状态转换、账户预留、真实当前时钟门禁、券商发送或重启恢复服务。两份合法结构批准不会产生真实订单。
