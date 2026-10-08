# ADR-036：双线诊断与 Owner 文字预测冻结

状态：本轮工程决定；不是生产业务规则。日期：2026-10-07。

现有历史样本已经暴露，首次可见、行动、状态、许可仍未证明。旧 H-B 真实链只追加 NO_DECISION，不产生方向预测。用户授权旁路验证两条线，并确认外部原始预测文件应不存在。

决定：新模块与原 G 链隔离，保留全部既有字节。Historical-OOS-Lite 名称保留为请求名称，实际结果只能标为 retrospective price-prefix reconstruction。历史各 cutoff 的已完成 h 日 raw close 变化均值作为无调参参考预测，训练终点不得晚于 cutoff，所有时间位置和失败保留。两套原 Timing 条件仅输出 TRUE/FALSE/UNKNOWN；其余策略门禁不补齐、不放宽，完整策略仍为 NO_DECISION。

历史预测文件先 exclusive-create、fsync、hash 绑定，之后重开再计算标签。这个顺序证明本轮计算顺序，不能抹去旧样本暴露或证明历史首次可见。只用当前完整参考日历映射目标，仍不是历史交易日证据。重叠窗口有依赖，三只事后选定存续证券存在选择偏差，不进行收益显著性或 Edge 宣告。

Owner 文字被保存为原文，生成新的 ForwardPrediction v1 OWNER_TEXT_IMPORT 及新 hash。原 hash 状态保持 NOT_VERIFIED；本机 UTC 记录时间属于 host-clock evidence，没有第三方时间戳，也不属于 Human Ed25519 执行签名。预测的价格是 Owner 输入假设，实际评分前必须与原固定 Reference A 原件核对；数值不符应阻断和保留错误，不能修订 v1。

收益比率用 Decimal80，1 代表100%；预测表使用 percent，误差用 percentage points。Owner 中心价格按 CNY 0.01 ROUND_HALF_UP，仅用于展示预测推导，不充当订单价。历史费用网格 0/5/10/25/50 roundtrip bps 是本轮预声明的 synthetic label sensitivity，不是券商费率、成本引擎、最低佣金或真实费用后 P&L。账户、费率、风险、基准、等级与 Edge 参数继续 UNSET_REQUIRED。

ForwardPrediction 和 ForwardOutcome 是独立 metadata contracts 1.0.0，非 native ResearchCard/Signal/Approval/OrderIntent。预测文件不能覆盖，sidecar outcome 独立于 G store，hash/expected-head/版本/原文/源原件绑定，重复 symbol+horizon 拒绝。真实 outcome adapter 重用原 `_validate_snapshot`，重新验真实 CAPTURE 和独立 REVIEW 签名及原始数据；不生成 grant，不增 actual_forward_days。D5/D10 缺乏完整路径日历和原件时 MAE/MFE 为 NULL；不能用稀疏点伪装完整路径。

D10 Owner 明确顺序为 603993 > 600312 > 603228，但后两只数值中心均为+3%。分别保留显式 ordinal 顺序和 numeric tie，实际结果相等不算严格顺序命中，不伪造 tie-break。主观概率和区间未经校准，命中率不是交易胜率。

后果：可保存第一份待揭晓答案，并测试严格的时间前缀与 append 算法。正式历史 PIT、实际预测验证、可执行策略净收益、Paper、Broker、Real Money 仍各有缺口。测试通过不授予这些能力。任何后续 v2/v3 必须新文件及明确 parent/version lineage，不能修改本次 v1 或旧合同。
