# Contracts V1.0.0

本轮冻结工程数据结构与不变量，不补齐未确认的业务准入、评分、仓位或概率模型。`contracts/release.v1.json` 是字节清单；`contracts/persistence-mapping.v1.json` 是持久化边界。任何后续修改都须经总控审核，不能更新测试期望值来迁就旧逻辑。

## 所有对象共同规则

每份 Schema 的 `required` 是字段必须存在的权威定义。只有 `notes` 可省略；`null` 字段仍必须存在，代表明确未知或不适用。嵌套对象也有独立 required 数组，并拒绝未知属性。不会自动补字段、类型转换或填默认值。

共同必填：contract_name、contract_version、object_id、object_version、trace_id、content_hash、recorded_at、business_timezone、provenance、reason_codes、invalidation。wire 版本为 1.0.0；对象版本为正整数（上限 2,147,483,647）。引用严格绑定 `(object_id, object_version, content_hash)`，版本号相同但哈希不同也必须失效。

`content_hash = sha256(canonical JSON excluding only top-level content_hash)`。键按序排列，数组保持顺序；只允许 JSON safe integer number，财务数值用字符串。此规范是项目自有格式，未宣称兼容外部 JCS。DataEnvelope 的 payload_hash 单独绑定 payload；raw_hash 绑定外部原字节，二者不可互换。SnapshotManifest.data_hash 绑定有序的完整可见 evidence 数组，其 content_hash 绑定清单本身。

每个对象保存四时钟、source_id / source_version / source_hash。所有瞬间要求 Z 或显式 offset；业务日按 Asia/Shanghai，存储瞬间按 UTC。日期是日历事实，不能伪装成午夜秒级披露。DATE_ONLY 在准入时必须使用明确交易日历和下一交易日规则；UNKNOWN 只能留存隔离，不能进入决策材料。

金额为最多 38 位 canonical integer-cent string（人民币分），计算用 BigInt。价格为最多 14 位整数、6 位小数的 Decimal 元/股，交易价格和 tick 必须大于零。通用 Decimal 最多 10 位整数、10 位小数；rate 是比例，bps 是 1/10,000，score 为 0—100，session 为交易日，month 为研究月份。数量是正 safe integer 股数。费用组件各自按明确 HALF_UP 舍入到分后求和；未知券商实际舍入/最低费结算范围仍需验证，P0 HALF_UP 是基线规范。价格含滑点时单独 slippage_cents 必须为零。

`reason-codes.v1.json` 提供冻结枚举：工程校验阻断、准入阻断或来源标签。失效状态 ACTIVE / INVALIDATED / EXPIRED / UNKNOWN；ACTIVE 不允许残留 invalidated_at/reason，INVALIDATED 必须有时钟与原因。每个 Schema 的 `x-contract.invalidated_by` 列出触发条件。P0 只实现校验与链失效反例，未实现后台 TTL 清理或状态转换服务。

## 合同清单

| 合同 | 关键约束、单位与失效原因 |
| --- | --- |
| SecurityIdentity | symbol=`exchange:6-digit-code`；交易所/板块/类型/状态枚举；lot 股数、tick 元；官方状态与有效版本变更失效 |
| DataEnvelope | raw URI/hash、payload/hash、四时钟、质量、RAW/ADJUSTED 与调整版本；未来/质量不通过不得入包；LEGACY_FIXTURE 只隔离 |
| SnapshotManifest | decision_cutoff、frozen_at、data_hash、精确 evidence refs、rules_hash；未来资料元数据也不输出 |
| FeatureSet | symbol/date/strategy、快照引用、feature_version、数值/单位/质量；VALID 不允许 null，缺失值不能替代为零 |
| AccountProfile | mode/account、CNY、账户与策略预算、费用来源和风险参数；未知值保持 UNSET_REQUIRED；仅 HUMAN_CONFIRM，auto_execute=false |
| CostEstimate | mode/account/strategy/symbol、方向/股数/价格、分值组件及合计、配置/hash/有效期；改变价格/量/费用失效 |
| ResearchCard | 四层 research/price/trade/probability、13 个 score 字段、grade、rule/policy versions、反证/hard blocks；研究与交易周期分开 |
| BrainPacket | 可见证据+清单引用+cutoff；MANUAL_EXPORT；LLM APPROVE/WAIT/REJECT 是研究意见；嵌套证据重验；无账户身份凭证 |
| CandidateEligibility | 显式 scope、card/feature/cost refs、Hard Block、准入政策版本；未确定业务政策不能 tradeable=true |
| SignalEvent | 完整状态枚举、rule/card 版本、行情时钟、trigger/expiry、dedupe key；已触发状态必须有真实触发时钟 |
| Approval | HUMAN_USER、独立 DECISION_APPROVAL / FINAL_ORDER_CONFIRMATION；USER_APPROVED 等枚举；后者绑定 cost 与精确 order_terms_hash |
| OrderIntent | LIMIT、股数/价格/交易日、卡/信号/两个批准/成本/账户快照/client ID；P0 production_execution_enabled=false |
| Fill | scoped order/approval refs、精确成交与分费用、broker_fill_id、execution_source；重复成交不能入账两次 |
| LedgerEntry | 账户共享 cash_after、策略持仓 after、正负分与股数、账户顺序号/previous hash；按事件时序对账 |
| BacktestResult | 策略/模拟 mode、数据/配置/代码/成本版本、BASE 等情景、MAE分辨率、gross/net/fees/层级指标/OOS状态；不混实盘 |
| AuditEvent | actor/action/target refs、before/after/previous hashes、occurred_at；model_review_is_authorization=false |

Schema 不会替业务决定评分合成、Edge 分子/置信折扣、概率校准、S/A/B 分界或仓位函数。明确已给定的 Core 20—40 日、Event 1—3 日、研究 6—18 月保留；其余未定政策版本或参数保持 UNSET_REQUIRED。

## 链与执行门禁

ResearchCard → SignalEvent → DECISION_APPROVAL → 确定订单条款 → FINAL_ORDER_CONFIRMATION → OrderIntent。条款 fingerprint 排除最终批准引用和状态，避免互相依赖的循环 hash。两份批准均绑定卡/信号/账户快照；最终确认还绑定成本与订单全部关键条款。修改数量、价格、账户、mode、strategy、卡版本、规则版本或成本将拒绝旧确认。

`validateOrderChain` 必须接收来自外部可信上下文的 actor 与 verified_approval_hashes；伪造 payload.actor_type 不会取得授权。这个 Set 是测试桩，后续要实现登录、权限、签名和可信当前时钟。通过校验只返回 structurally_preparable，永不提交订单。

`validateBrainPacket(packet,snapshot)` 额外核验外部快照版本、清单 hash、cutoff、有序 evidence 内容与数量。只调用结构 validator 并不能证明 snapshot_ref 在真实存储中存在。后续 brain adapter 必须调用此入口并实现字段级脱敏，不能只相信 `contains_account_identity_or_credentials=false` 自声明。

## 持久化和最小导入

002 的 contract_records 无损保留 16 份 wire 对象和四时钟；fixture importer 先验 Schema/语义/content hash，再写隔离记录；拒绝 PROD 与敏感字段，不写标准订单/成交/账本。legacyEvidenceEnvelope 保留旧 payload 为 UNKNOWN 的 LEGACY_FIXTURE，不伪造新策略卡或批准。

001 的关系表是目标规范化 Schema 草案，SQL 中的 payload_hash 在合同投影行用于 canonical contract content_hash，source record hash 则由源适配器独立核验。快照 content_hash 与 data_hash 分列。来源 record → wire envelope →规范化行的完整适配尚未实现，不能把 staging 记录宣称为生产数据迁移完成。映射声明有 IMPLEMENTED_FIXTURE_REGISTRY 和 NOT_IMPLEMENTED_NORMALIZED_PROJECTION 两种明确状态。
