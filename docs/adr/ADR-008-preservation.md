# ADR-008 legacy experiment preservation policy

状态：P0 工程实现，待 Gate Review。

决定：preserve → isolate → replace → verify → deprecate。KEEP/MODIFY/ISOLATE/DEPRECATE/DELETE_LATER 是机器处置标签，不是修改或删除授权。MODIFY 指新实现/适配器，旧已封存实现保持只读；DELETE_LATER 需后续证据/恢复审查，本轮删除为空。

V5 是 LEGACY_EXPERIMENT：40 日是实验窗口，计划持仓 5—8 日；原本金、预算、费用、滑点、代码 hash、运行状态原样保留且不映射 Core/Event。14 日回放作为历史事实一致性 baseline，不作为收益有效性或完整 PIT 认证。

已知 CLI seal mismatch 必须保留原封存 hash 和实际 hash，native compatibility 继续报告失败，不能改旧 seal、旧 ledger 或改预期值伪造通过。新 portable golden tests 可断言这个失败事实；外部引擎回放成功不等于旧 native pipeline 全通过。
