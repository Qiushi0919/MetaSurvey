# Schema V1 P0 草案与验证边界

正式工程交接文档是主要 Source of Truth。此文件解释 `migrations/001_schema_v1.sql` 的工程实现；账户、费率、评分、风险和上线许可没有在这里补成默认值。DDL 的合同版本固定为 `1.0.0`，迁移编号为 `001`。本轮没有迁移历史全量数据。

## 可执行迁移

`src/baseline/migrate.mjs` 接受同一连接上的 `exec(sql)`、`query(sql, parameters)` 适配器。它要求从 `001` 连续编号，按文件原始字节计算 SHA-256，并把整个待应用迁移批次放在一个事务中。重复运行只验证已应用文件；已应用文件变动、缺失、历史顺序变化或编号断档会失败。首次失败连 `schema_migrations` 都回滚，不留下半建成数据库。修改已确认并应用的迁移必须新增迁移，不得改旧校验值。

```sh
npm run test:schema
```

测试使用 `@electric-sql/pglite` 的实际 PostgreSQL 引擎，不使用 SQLite 近似。`001` 建立 **45 张业务/辅助表**，`002` 增加 **1 张无损 contract_records**，另有 **1 张迁移跟踪表**；空库应用全部连续迁移至 latest，共 47 张 public 表。`001` 的两个临时 DDL 展开函数只用于将同一套 provenance 列展开到平表，完成后删除；没有留下动态建表运行接口。当前 focused Schema suite 为 **23 项通过**，包括独立审查提出的未触发订单和伪造快照时钟反例。

## 表清单

| 边界 | 表 | 版本与隔离 |
| --- | --- | --- |
| 来源与证券 | `data_sources`, `securities`, `security_master` | 来源许可声明；稳定证券身份与主数据修订分离 |
| 行情与公司行动 | `corp_actions`, `adjustment_versions`, `adjustment_actions`, `bars_1d`, `bars_1m`, `orderbook_l2` | raw/adjusted 分键；调整因素版本和行动引用；L2 表存在不代表获得许可 |
| 披露与 PIT | `announcements`, `financials`, `news_events`, `sector_membership` | 财务原始/修订独立版本；披露关联同一证券；行业有效期与知道时点分离 |
| 配置与账户/成本 | `config_versions`, `accounts`, `account_profiles`, `account_snapshots`, `cost_estimates` | mode/account 复合身份；配置 hash/version；证券成本绑定；未确定参数状态明确保存 |
| 快照与特征 | `snapshot_manifests`, `snapshot_entries`, `features_eod` | 冻结时点、截止、数据 hash；决策输入与未来裁判材料隔离 |
| 研究 | `research_evidence`, `research_cards`, `card_evidence`, `brain_packets`, `brain_reviews`, `candidate_eligibility` | 三类策略 namespace；引用证据版本；LLM review 与人类批准分表 |
| 信号与批准 | `signal_events`, `order_drafts`, `approvals` | 卡/信号版本链；确定的未签订单草稿；人类两阶段批准 |
| 模拟交易 | `order_claims_sim`, `orders_sim`, `fills_sim`, `positions_sim`, `ledger_sim` | 只允许 DEV/PAPER；账户/策略/模式/版本复合 FK |
| 真实记录 | `order_claims_real`, `orders_real`, `fills_real`, `positions_real`, `ledger_real` | 只允许 PROD 记录；P0 无实盘执行入口和授权能力 |
| 回放与审计 | `backtest_runs`, `strategy_metrics`, `audit_log` | 输入数据/配置/成本/规则版本；审计 append-only |
| 最小导入 | `legacy_asset_registry`, `staging_imports`, `contract_records`（002） | 只读外部 locator/hash，隔离导入状态，未映射历史实验至新交易策略；canonical wire 无损存储 |

所有来源资料、关键业务对象和版本记录均保留扁平的 `event_time`、`published_at`、`available_at`、`retrieved_at`、`source_id`、`source_version`、`source_hash`、`payload_hash`、`trace_id`、`reason_codes`、`contract_version`、`object_version`、`business_timezone`。`order_claims_*` 是内部幂等身份索引，`schema_migrations` 是迁移控制表，二者不充当市场/账户数据对象。

Canonical wire contracts 是结构合同的唯一来源。`001` 是所需关系和门禁的 normalized projection，不是另一份完整 wire Schema；`002` 无损保存经过合同验证的 canonical payload，并提供 fixture staging。`001.payload_hash` 表示所投影 canonical wire `content_hash`；`source_hash` 表示来源记录/原始材料 hash。`snapshot_manifests.content_hash` 与该表 `payload_hash` 相等，供 FeatureSet、ResearchCard、BrainPacket 的 snapshot 引用。`data_hash` 另表示数据集摘要，供 BacktestResult 数据绑定，不能把它当作 SnapshotManifest 的合同 hash。Importer 的无损持久化已由 registry 承接，而 wire → normalized 的完整映射/投影器尚未实现；不得声称 `001` 能独立无损 round-trip 全部合同。

## 时间与 PIT

业务时区为 `Asia/Shanghai`，时间字段用 `TIMESTAMPTZ` 表示真实时间瞬间。迁移及测试连接设置 UTC；部署时仍须在每个连接/服务设置 UTC。只有交易日期、报告期间、除权日期等日历事实用 `DATE`。公司行动 `event_time` 可以指未来生效事件，因此不会用错误的 `event_time <= available_at` 检查拒绝已公布的未来除权日。

`published_at` 允许空值的唯一情形是声明 `published_at_not_applicable=true` 且 `published_at_precision=NOT_APPLICABLE`，适合本地派生对象。正式公告、财务、新闻必须声明非空的发布时间。精度必须声明为 MICROSECOND/SECOND/MINUTE/DAY；日级精度的实时时点是否可靠仍须源适配器检查，Schema 不会替源编造秒级时间。`published_at <= available_at <= retrieved_at` 保持成立。允许不适用不等于允许把缺失的外部披露时间当作本地派生时间。

`financials_as_of(cutoff, visibility_basis)` 与 `bars_1d_as_of(cutoff, visibility_basis)` 显式要求截止时点，并先过滤知道时点，再选可见的最新修订。默认 `OBSERVED_AS_OF` 要求 `available_at` 和 `retrieved_at` 都不晚于截止，能用于实际当时留存的观察记录；显式 `PUBLIC_AS_OF` 允许随后归档的历史公开资料，但仍要求来源宣称的 `available_at` 和适用的 `published_at` 不晚于截止。这一模式只表达历史公开可得口径，不能证明本系统当时已经取得资料，也不能替代 timestamp quality/source 审查。

快照的成员必须通过 dataset allowlist 解析到已保存的真实源记录版本。允许 `bars_1d`、`bars_1m`、`corp_actions`、`adjustment_versions`、`announcements`、`financials`、`news_events`、`sector_membership`、`features_eod`、`research_evidence`、`orderbook_l2`、`account_snapshots`、`security_master`、`securities`；未支持类型拒绝进入。来源行的 payload hash、source id/version/hash、四时钟及 publication precision/not-applicable 必须与成员一致，不能把未来正文/标题的时钟改写为过去。随后 `DECISION_INPUT` 成员再受知道时点约束。`FUTURE_REVEAL` 同样核对源记录，并必须有晚于冻结的 `reveal_after`，不会混入决策成员。

研究卡与 Brain Packet 的截止必须与其快照一致；卡片证据引用也受截止约束。财务记录的 publication/available/retrieved 都不能早于关联公告，防止已提前宣称取得的财报借用晚到的公告。复权版本以 `adjustment_actions` 指定行动修订，并阻断截止后的行动；调整行情不得早于调整因素可得和取得时间。复权因素实际数学核验、冻结文件字节与清单的一致性及未来材料读取权限由后续数据适配器/对象存储权限实现，SQL 的 hash 格式约束不代替这些工作。

## 金额、价格与数量

人民币金额统一为整数分。`money_cents` 是无 typmod 的 `NUMERIC` domain，以整数和绝对值 `<10^38` 检查达到 38 位整数分范围。不能直接用 `NUMERIC(38,0)` 接不可信输入，因为 PostgreSQL 会在 CHECK 前先把 `1.1` 分四舍五入为 `1` 分；此实现明确拒绝它。JSON 财务金额也必须是符合最多 38 位的整数字符串。

`price_yuan` 是最多 6 位小数、14 位整数的非负 Decimal 元，CostEstimate/订单/成交价格另外要求严格大于零；`decimal_rate` 与 common Decimal 合同对齐，最多 10 位小数、10 位整数且有符号。输入超精度直接拒绝，不暗中舍入。数量用 BIGINT 并限制在 wire safe integer 范围 `<=9007199254740991`；数量、lot size、volume 不能借 SQL BIGINT 超过 wire 精度。费用引擎在指定计费单位和舍入合同下完成舍入，再写整数分；这里没有最低佣金、佣金率、滑点率或账户资金默认值。

## 版本链与交易隔离

`RESEARCH_6_18M` 可以存研究/证据/特征/Brain 数据，不能插入信号、候选交易资格、订单、成交、持仓、交易账本或交易回测。CORE_40/EVENT_3 在所有交易表显式绑定，复合 FK 阻止跨模式、账户、策略、证券、版本或 hash 拼接。同一对象的后续版本不得换 namespace/account/mode。研究卡还显式绑定 account/mode，卡片证据、候选和信号不能复用其他账户或模式的卡；CostEstimate 显式绑定 security，草稿不能借用另一证券的成本估计。

版本链为：

```text
ResearchCard(id/version/hash/strategy/security/account/mode)
  -> SignalEvent(id/version/hash/account/mode/strategy + exact card ref)
  -> OrderDraft(exact signal/card, side, quantity, price,
                CostEstimate ref/hash, AccountSnapshot ref/hash, target_fingerprint)
  -> HUMAN_USER DECISION_APPROVAL + FINAL_ORDER_CONFIRMATION
  -> OrderIntent persisted in orders_sim / orders_real
  -> Fill -> LedgerEntry
```

订单草稿是未签名、没有执行能力的目标对象。它用于绑定明确的费用、数量、方向、价格和账户快照，避免订单 hash 与最终批准 hash 互相依赖。初始决策批准允许先记录针对这份明确目标的批准；用户最终确认仍必须单独存在，两个批准必须指向相同草稿版本/hash/目标指纹。订单通过不可变草稿引用取得完整的卡/信号/成本/快照版本链；线上的扁平合同可从这一链投影。

`approvals.actor_kind` 只允许 HUMAN_USER，批准决定使用 USER_APPROVED/USER_WAIT/USER_REJECTED；LLM APPROVE/WAIT/REJECT 只能进入 `brain_reviews`，无法满足批准 FK。Brain Packet 请求类型固定 INITIAL_RESEARCH/TRIGGER_REVIEW。数据库只是验证保存的身份声明和关系，不会认证“谁真的是用户”；后续权限服务必须核验可信登录、权限、签名和最终确认。表内的 `auth_context_hash` 不是登录凭证。

Signal 支持 INVALIDATED；TRIGGERED/ACKNOWLEDGED/APPROVED/EXECUTION_READY/EXECUTED 必须有不晚于事件时点且早于 expiry 的 triggered_at。P0 新订单仅准入 TRIGGERED/ACKNOWLEDGED，其触发时点不得晚于订单、rule_version 必须与卡相同。卡可以保存 UNSET_REQUIRED grade，不能准入订单链。新订单记录也拒绝在其事件时点已过期、尚未可得、或已被更高卡/信号版本取代的链。完整后续状态机仍待实现；执行服务将来必须按真实当前时钟再次检查批准、行情、配置、现金和 Kill Switch。

`order_claims_*` 保证同一 account/mode/client_order_id 只能归属一个订单，即使换 strategy 也不能复用；同一订单可追加状态修订。`fills_*` 的 broker_fill_id 在账户/模式内唯一，重复回报不能入账两次；纠正已保存的成交事实须新纠正事件/反向账项，不能覆写原成交。现金账本顺序号在 account/mode 内共享唯一，策略不能各自从同一个现金序号重复记账。分策略持仓隔离保存，并提供 lot_allocations 与 available_quantity；T+1 计算、预留现金、成本和完整账户守恒由后续账本实现及 Golden Tests 验证，DDL 不声称已实现撮合引擎。

## 不可变性与 P0 限制

业务历史表、版本表和幂等索引对 UPDATE/DELETE/TRUNCATE 均阻断。修改需要新增修订。`accounts.production_authorized` 只能为 false。真实表可表达隔离的合成/历史事实，并不意味着这些订单已经真正发送或获得发送许可；本 repo 没有券商请求、凭证或提交服务。

触发器和 CHECK 已在 PGlite 上执行正反例，能证明 PostgreSQL DDL 可从空库建立、事务回滚、复合关系/PIT/精度/不可变检查有效。还没有验证外部 PostgreSQL 服务器部署、并发多连接迁移锁、RBAC/超级用户对触发器的绕过防护、对象存储不可变保留、真实行情时间质量、真实券商交割单、备份恢复或生产服务吞吐。hash 格式和 FK hash 相等只验证声明一致，不能认证内容 SHA、来源真实性或人类批准。

001 提供 staging/legacy registry Schema；002 与新 fixture importer 实现 canonical wire 的最小隔离导入，所有记录的 ingestion_status 只能 QUARANTINED，拒绝 PROD，不写规范化交易表。实际旧资产 locator 读取、85个选中锚点哈希复核和14日回放由新只读 adapter 完成。完整 source/wire→规范化字段投影、权限和全量迁移尚未实现；没有触碰旧 V5 seal、账本、数据库、运行目录，也没有将其 5—8 日实验解释成 CORE_40。
