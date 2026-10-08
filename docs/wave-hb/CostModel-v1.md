# CostModel v1.0.0 — 只读经济诊断

本轮新增独立的 `wave_hb/cost.mjs`，提供 `quoteCost({mode, profile, side, fills, trade_date})` 和 `netEdge({mode, profile, buy_fills, sell_fills, buy_date, sell_date})`。唯一 mode 是 `ECONOMIC_DIAGNOSTIC_ONLY`；输出不是订单、账本或执行许可。旧成本模块、16 个 native contracts、Schema 6、依赖锁、旧实验费率和 ledger 保持原样。

`EconomicDiagnosticCostProfile`、`EconomicDiagnosticCostResult`、本模型和官方费用参考 roster 的版本均为 `1.0.0`。完整字段、required/enum/单位、缺失表示、hash、reason codes 和 invalidation 条件在 [CostModel-v1.json](CostModel-v1.json)。Profile 是 closed schema，22 个顶层字段全部 required；各组件字段和 fill 的 price/quantity 也全部 required，没有业务默认值。

七个组件分别为 commission、stamp_tax、exchange_fee、clearing_fee、regulatory_fee、other_fee 和 slippage。每项必须明确精确字符串 rate、`FRACTION_OF_NOTIONAL` 单位、收费 sides、完整 effective_from/effective_to 日期窗口、evidence_ref。佣金另需最低收费整数分和累计单订单口径；税费另需是否已计入综合佣金；滑点另需价格是否已经包含其影响。明确填入零与 UNKNOWN 是两回事。

当前只有明确标为 `SYNTHETIC_FIXTURE` 的 profile 可以获得 `COMPUTABLE_SYNTHETIC_ONLY`，其 evidence tier 永远为 `SYNTHETIC_NOT_REAL`。测试参数全部为人工算术样本，不能成为真实账户默认值。真实账户 profile、OWNER_SET 字样、self hash 和 API 可访问性都不是实际券商计费证据。本版本没有已准入的 broker-evidence adapter，因此完整填写 `ACTUAL_ACCOUNT` 仍返回 `NOT_COMPUTABLE / ACTUAL_ACCOUNT_EVIDENCE_NOT_ADMITTED`；真实账户原有 30 个字段及总控扩展待填字段保持 UNSET_REQUIRED。

缺失、null、UNKNOWN 或 UNSET_REQUIRED 返回 `NOT_COMPUTABLE`、`REQUIRED_COST_CONFIG_UNSET` 和 `net_edge_cents=null`，并列出 missing_fields。格式、版本、hash、date、side、单位、收费包含关系等已填写但非法时，返回固定错误码和 null，不产生乐观净收益。`PRODUCTION` 和其他 mode 全部拒绝。所有结果保持 `production_enabled=false / safe_to_trade=false / native_authority=false / historical_pit_proven=false / source_admission=false`。

每个 fills 数组代表一个累计诊断订单，不能把不同订单合并。价格为每股 CNY 的精确 Decimal 字符串，数量为正 safe integer 股数，money 为 integer cents string。私有 Decimal.clone 固定 precision 100、HALF_UP，外部 Decimal.set 不改变计算。每次 fill 的成交额单独取整到分并累加；各费用按该订单精确累计成交额计算，每项取整到分；佣金只对该累计订单取一次 `max(比例佣金, 最低佣金)`。这些规则是冻结的诊断算术规范，尚不证明真实券商采用同一舍入办法。

标为 `COMMISSION` 的 exchange/clearing/regulatory/other fee 不重复扣减；同时保留其独立比例参考值。标为 `SEPARATE` 才加到费用中。已包含在成交价格中的滑点必须指定 incremental rate 为精确零；`SEPARATE_ESTIMATE` 才追加费用。净收益使用卖出现金变化与买入现金变化相加，要求股数相等、日期前后合法、两日都处于每一项明确有效窗口。Profile、验证后的请求和结果都有 SHA256；synthetic source_refs 明确绑定 profile evidence_id，但不产生实际 authority。

本轮取得 6 次无凭据官方 GET 原件：SSE 费用通知 HTML、其 DOCX 附件、印花税法 HTML、附件税率表两张 JPG、减半公告 HTML，全部 200。3 个搜索 query 仅用于发现原文。原始字节、请求/响应 URL、UTC 微秒时钟、响应头、bytes/hash 保存在 Git 外 0700/0600 目录。脱敏索引为 [official-fee-evidence.json](../../config/wave-hb/official-fee-evidence.json)。没有读取凭据、调用市场 API、代理、重定向、购买权限或扩大股票范围。

SSE 2025 页面路径承载的正文和 DOCX 是 2023 年 8 月修订，通知注明 2023-08-28 生效。附件 §3.1.1 的 A 股竞价交易经手费换算为成交额 fraction `0.0000341`、双向；它不能说明本账户是否已含在券商综合佣金中。[SSE 官方通知与附件](https://www.sse.com.cn/lawandrules/sselawsrules2025/charge/c/c_20250610_10781461.shtml)

印花税法第三条明确转让方承担证券交易印花税，附件最后一行给出 base fraction `0.001`；该法于 2022-07-01 施行。再与 2023 年第 39 号公告的减半、2023-08-28 起效条件组合，得到 reference fraction `0.0005`、卖方。[印花税法及附件](https://shanghai.chinatax.gov.cn/zcfw/zcfgk/yhs/202106/t458595.html)、[减半公告](https://shanghai.chinatax.gov.cn/zcfw/zcfgk/yhs/202308/t468451.html)

上述法定参考数据没有插入 Owner profile，effective_to 仍为 UNKNOWN，不构成完整历史区间或当时可见证明。当前捕获 available_at 仅等于本地收到原件的 retrieved_at；不能倒推历史首次可见。真实 broker commission、最低佣金、双向口径、清算/过户/监管和其他收费、包含关系、成交滑点、实际取整、资料当前有效性仍缺独立证据。本轮没有从债券页面推断清算费率。Provider / License、formal historical PIT、真钱、Broker、Cloud 和 production 阻断继续保留。
