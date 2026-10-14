# 首个真实输入核对包：PCB / 景旺电子

当前观察研究、候选方法、非交易建议。仅603228.SH；PCB制造为待核实产品边界，成员与收入阈值未批准；另外两只获准证券不混入，多公司覆盖未完成。

原市场观察截止 `2026-10-06T07:50:49.627682Z`；本次档案核对 `2026-10-14T05:34:06.276674+00:00`，不代表新增市场数据或历史PIT。

私有完整输入包：`/Users/qiushi/投资研究/.p1b-archives/score-review-20261014/Sample-r2.json`。公开仅元数据。18个评分输入均不可准入、归一化分项0、完整分数0。另有1项半年收入同比纯算术核对（非TTM、非分数），Decimal与独立Fraction复算一致。

| 字段 | 原件与时点 | 单位 | 计算 | 缺口 |
|---|---|---|---|---|
| demand_growth_bps | 缺该字段完整可准入原件；四时钟不补造 | BPS | 同口径行业实际销量/消费量同比增长 × 10000；前期量必须>0 | SECTOR_UNIVERSE_MEMBERSHIP_AND_ORIGINAL_SERIES_MISSING；INSUFFICIENT_PEERS；OWNER_ECONOMIC_METHOD_PENDING |
| demand_capacity_gap_bps | 缺该字段完整可准入原件；四时钟不补造 | BPS | 行业需求同比增长bps − 可比有效产能同比增长bps；正值表示供给约束 | SECTOR_UNIVERSE_MEMBERSHIP_AND_ORIGINAL_SERIES_MISSING；INSUFFICIENT_PEERS；OWNER_ECONOMIC_METHOD_PENDING |
| price_orders_growth_bps | 缺该字段完整可准入原件；四时钟不补造 | BPS | (行业成交价格同比bps + 已确认新订单同比bps)/2；两者缺一即缺失 | SECTOR_UNIVERSE_MEMBERSHIP_AND_ORIGINAL_SERIES_MISSING；INSUFFICIENT_PEERS；OWNER_ECONOMIC_METHOD_PENDING |
| policy_balance | 缺该字段完整可准入原件；四时钟不补造 | SIGNED_COUNT | 固定90日内独立且仍有效政策，支持条款计+1、限制条款计−1；同一政策去重；双人证据编码；冲突未知阻断 | SECTOR_UNIVERSE_MEMBERSHIP_AND_ORIGINAL_SERIES_MISSING；INSUFFICIENT_PEERS；OWNER_ECONOMIC_METHOD_PENDING |
| global_demand_bps | 缺该字段完整可准入原件；四时钟不补造 | BPS | 同范围全球行业实际需求同比bps；不得用今日预测代历史实际 | SECTOR_UNIVERSE_MEMBERSHIP_AND_ORIGINAL_SERIES_MISSING；INSUFFICIENT_PEERS；OWNER_ECONOMIC_METHOD_PENDING |
| margin_change_bps | 缺该字段完整可准入原件；四时钟不补造 | BPS | 当时行业成员按收入加权毛利率同比变化bps；亏损成员保留，缺失成员不得静默移除 | SECTOR_UNIVERSE_MEMBERSHIP_AND_ORIGINAL_SERIES_MISSING；INSUFFICIENT_PEERS；OWNER_ECONOMIC_METHOD_PENDING |
| sector_valuation_percentile | 缺该字段完整可准入原件；四时钟不补造 | RATIO | 正行业估值倍数在过去1260完整交易日弱排名 count(x<=current)/1260；方法/成员冻结 | SECTOR_UNIVERSE_MEMBERSHIP_AND_ORIGINAL_SERIES_MISSING；INSUFFICIENT_PEERS；OWNER_ECONOMIC_METHOD_PENDING |
| sector_rs20_bps | 缺该字段完整可准入原件；四时钟不补造 | BPS | 行业20交易日总回报 − 同期冻结基准总回报，×10000 | SECTOR_UNIVERSE_MEMBERSHIP_AND_ORIGINAL_SERIES_MISSING；INSUFFICIENT_PEERS；OWNER_ECONOMIC_METHOD_PENDING |
| sector_adverse_share | 缺该字段完整可准入原件；四时钟不补造 | RATIO | 行业成员中经核验有效重大不利事件公司的收入权重占比；明确全体覆盖才能填0 | SECTOR_UNIVERSE_MEMBERSHIP_AND_ORIGINAL_SERIES_MISSING；INSUFFICIENT_PEERS；OWNER_ECONOMIC_METHOD_PENDING |
| revenue_growth_bps | FULL-income-603228.SH.response.json rows11/12、19/20；2025/2026H1；检索2026-10-06T07:37:20.698937Z；event_time/published_at未知 | BPS | 最新可见TTM收入/前TTM收入−1 ×10000；前收入>0 | HALF_YEAR_YOY_IS_NOT_TTM；UNIT_NOT_INDEPENDENTLY_CERTIFIED；PUBLICATION_INSTANT_UNKNOWN；MULTIPLE_UPDATE_FLAGS_SAME_REVENUE_REVISION_CHAIN_UNPROVEN；OWNER_ECONOMIC_METHOD_PENDING |
| cash_conversion | 缺该字段完整可准入原件；四时钟不补造 | RATIO | TTM经营现金流/TTM净利润；净利润<=0记缺失 | TTM_CASHFLOW_PROFIT_BRIDGE_MISSING；OWNER_ECONOMIC_METHOD_PENDING |
| roic_spread_bps | 缺该字段完整可准入原件；四时钟不补造 | BPS | (ROIC−资本成本)×10000；需独立冻结资本成本方法，M01未批准不自动采用 | M01_CAPITAL_COST_NOT_APPROVED；ROIC_BRIDGE_MISSING；OWNER_ECONOMIC_METHOD_PENDING |
| sector_revenue_share | 缺该字段完整可准入原件；四时钟不补造 | RATIO | 公司归属该板块业务收入/总收入；必须绑定下方sector结果同一板块身份 | SEGMENT_REVENUE_MEMBERSHIP_NOT_VERIFIED；OWNER_ECONOMIC_METHOD_PENDING |
| catalyst_balance | 缺该字段完整可准入原件；四时钟不补造 | SIGNED_COUNT | 固定60交易日内仍有效已核实订单/投产/业绩指引事件：正向+1、撤销/负向−1；去重、正文定位、双人编码 | BODY_SEARCH_WINDOW_AND_TWO_CODER_RECORDS_MISSING；OWNER_ECONOMIC_METHOD_PENDING |
| stock_rs20_bps | 缺该字段完整可准入原件；四时钟不补造 | BPS | 个股20交易日总回报 − 对应行业总回报，×10000 | SECTOR_TOTAL_RETURN_AND_ACTION_BRIDGE_MISSING；OWNER_ECONOMIC_METHOD_PENDING |
| stock_valuation_percentile | 缺该字段完整可准入原件；四时钟不补造 | RATIO | 正选定倍数过去1260交易日弱排名；负盈利不可映射成低估值 | PIT_MULTIPLE_HISTORY_AND_METHOD_MISSING；OWNER_ECONOMIC_METHOD_PENDING |
| median_turnover_cny | 缺该字段完整可准入原件；四时钟不补造 | CNY_YUAN | 最近20实际交易日成交金额中位数（偶数取中间两项平均）；不是账户可成交容量 | AMOUNT_UNIT_AND_COMPLETE_20_SESSION_WINDOW_UNVERIFIED；OWNER_ECONOMIC_METHOD_PENDING |
| verified_fact_share | 缺该字段完整可准入原件；四时钟不补造 | RATIO | 预先登记的必需事实中经原文、单位、修订和时钟核对的比例；分母不许删掉缺失事实 | FACT_DENOMINATOR_AND_REVIEW_NOT_FROZEN；OWNER_ECONOMIC_METHOD_PENDING |

财报原件hash `sha256:62efd4db1a65ebdb73a910757c7055abad12e8e6849e08546b66ec882143c216`。每期两条update_flag不同、收入相同的记录全部保留，不选“最新”；ann_date/f_ann_date仅源提供日期，非核验发布时间。Provider/license、单位真实性仍未证明。

公司集中度、杠杆、重大不确定性UNKNOWN；板块前两项NOT_APPLICABLE、扣分NULL，SECTOR_RISK_METHOD_PENDING阻断；硬门槛仍UNKNOWN。

V0 ScoreResult合同仅承载阻断兼容链，V01适用性另绑定候选配置。EvidenceBundle唯一事实是本次本地“可准入评分输入不完整”核对，不冒充市场事实或人类审批。真实财务原文缺四时钟，未进入评分事实。

下一步补PCB成员与分部收入、行业价格/订单可比性、真正竞争格局及板块风险方法；逐项审批经济口径和补原件。新增同板块公司仍须范围/来源许可。本轮不新增采集。
