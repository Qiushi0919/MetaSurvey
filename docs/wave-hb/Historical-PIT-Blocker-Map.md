# Historical PIT 阻断地图 V1

本图重开既有 H-A 原件和 Wave D 三股报告；新增网络请求、历史连续域闭环、实际 Forward 天数均为 0。
正式价格/基本面回测、来源许可、交易、云端和生产继续 BLOCKED。

范围：603993.SH, 600312.SH, 603228.SH；20 个域组；183 个冻结规格输入节点；174 个既有报告特征实例（每股 58）。

历史 decision_time 未提供，必须逐决策提供；本图不会替 Owner 选择截止、午夜时间或历史区间。
每个输入均要求 event_time、published_at、available_at、retrieved_at、first-visible、revision/version、有效区间、证券适用性、原件 SHA 和用途许可。现有报告的 2026 年捕获时间只证明当前观察。

| PIT 域 | 当前依据与缺口 | 正式状态 |
|---|---|---|
| adjustment_factor_semantics | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |
| benchmark_total_return | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |
| catalyst_originals | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |
| corporate_actions | 已有单事件/通用规则结构；缺连续适用区间、首次可见和修订链 | BLOCKED |
| dated_costs_and_account | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |
| dividend_action_reconciliation | 已有单事件/通用规则结构；缺连续适用区间、首次可见和修订链 | BLOCKED |
| economic_estimation_policy | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |
| exchange_calendar_version | 已有单事件/通用规则结构；缺连续适用区间、首次可见和修订链 | BLOCKED |
| financial_ann_fann_date | 已有单事件/通用规则结构；缺连续适用区间、首次可见和修订链 | BLOCKED |
| historical_price_limit_regime | 已有单事件/通用规则结构；缺连续适用区间、首次可见和修订链 | BLOCKED |
| historical_universe_completeness | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |
| industry_history | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |
| listing_anchor | 已有单事件/通用规则结构；缺连续适用区间、首次可见和修订链 | BLOCKED |
| listing_delisting_history | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |
| name_status_history | 已有单事件/通用规则结构；缺连续适用区间、首次可见和修订链 | BLOCKED |
| raw_bars_volume | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |
| revision_chronology_first_visibility | 已有单事件/通用规则结构；缺连续适用区间、首次可见和修订链 | BLOCKED |
| st_history | 已有单事件/通用规则结构；缺连续适用区间、首次可见和修订链 | BLOCKED |
| suspension_history | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |
| valuation_history | 缺三股逐决策完整原件/版本/适用区间/首次可见证明 | BLOCKED |

机器地图逐项保留两个冻结 family 的 timing、共同指标、退出/仓位/风险/经济/OOS 规格及每股 58 个报告特征。冻结规格中的阈值仍是研究提案；费用、账户和业务决策不因列入地图而成为生产默认值。

官方上市锚、2020/2023/2026 交易规则、公告索引、当下可查询历史行情、同源因子数学一致性，均不能单独关闭证券连续历史 PIT。失败正文、5 处行动歧义、8 个 pre_close 差异和财报修订缺口保留。

Provider/License/Transport 的 8 个维度仍 UNKNOWN。来源 hash 绑定的是捕获内容，不证明提供方版本、许可或历史首次可见。

后续每个正式 decision input 只有在原件可重开、历史 first-visible ≤ decision_time、有效区间/证券适用性、版本修订链、规则/单位/用途许可和独立审查均有证据时才可申请闭环；本模块没有实际准入接口。

测试仅使用明确 SYNTHETIC fixture 演练四时钟、未来版本隔离和修订选择；fixture 一致也不会获得正式回测或交易权限。

原件位于既有不可迁移 private archive；JSON 索引包含路径和 hash，验收包不得据此复制 raw/数据库/凭证。

地图 hash：sha256:48bca6c842eefdce19b21c4186d7e485f0e98023f080b20e01678dc5d6dedc6c
H-A context：sha256:5159515509c7cf5959a2c572af9981ba4fa886d5ec7a911d56ff3e9c3b655096

完整逐字段 JSON 位于本机私有归档 `results/MAP-G2/Historical-PIT-Blocker-Map.json`，Git 同名文件为带 SHA/大小的机器索引。原 1.73MB 文件被现有 1MiB 仓库检查拒绝，首次失败候选与日志保留；完整内容逐字节保留，未修改仓库限额或 PIT 门禁。冻结证据 wrapper 另见 evidence.json。
