# P1-A Cost / Ledger / Paper reference

状态：P1-A 离线工程模块；真实资金执行继续关闭。此模块不导入 V5、legacy engine 或 P0 经济计算实现。P0 基础合同哈希工具只用于 canonical JSON / SHA-256；费用计算与 BigInt 核账在新模块独立实现。

## 任务合同

- Goal：提供显式版本化费用、含费数量、共享账户现金预留、按策略分离持仓、可重启确定性 Paper 状态机及独立核账。
- Context：正式交接文档为主要 SoT；P0 已通过；P1-A development 条件授权；P1-A Gate / P1-B / production 未开放。
- Inputs：DEV/PAPER、显式 synthetic CostProfile、PaperReplayOrderIntent、证券/交易日历版本及 hash、固定时钟、两阶段 synthetic human authority fixture。
- Outputs：`src/cost/index.mjs`、`src/paper/index.mjs`、`src/paper/oracle.mjs`、迁移候选 004、带来源 fixture 与 scoped tests。
- Interfaces：`db.exec(sql)` / `db.query(sql, positionalParams)` 必须绑定同一 PostgreSQL connection。总控拥有共享合同、ADR、迁移编号、release 和最终合并。
- Constraints：无网络/券商路径/credentials；无 LLM approval；不猜真实费率、本金、风险；EVENT_3 仅验证 namespace 共用现金，未实现策略。
- Tests：独立 BigInt exact oracle、minimum boundary、partial/cancel/reject、same cash 并发、持久化重启/幂等、T+1/calendar、namespace、时钟/价格/版本、mutation 与账本篡改攻击。
- Definition of Done：scoped tests 通过，来源与限制明确，总控审核合并，真实参数继续 UNSET_REQUIRED，生产门禁继续关闭。

## 本地模块类型与共享合同投影

模块输入是明确标为 `SYNTHETIC_TEST_ONLY` 的 Paper reference 类型。它们不是生产 ResearchCard/Signal/Approval gateway，也不声称直接符合冻结 P0 wire schemas。总控应把新类型版本化，并负责共享字段/合同投影；本 agent 未改 P0 contracts / ADR / reason registry / migrations 001/002。

真实 AccountProfile 不在此模块补值。当前依赖的本金与费用只从 `tests/fixtures/p1a-paper/baseline.json` 显式读取，文件声明手工编写的 synthetic fixture、无 legacy 参数继承；不会作为配置默认值。fixture human authority 不是登录认证、更不是券商授权。

## Cost API

`sealCostProfile(profile)` 生成内容 hash；`validateCostProfile(profile,{mode,trade_date})` 校验版本/hash、生效范围、精确费用、包含关系、显式来源与 synthetic scope。

`estimateCost({mode,profile,side,price,quantity,trade_date})` 返回完整成交估计。`cumulativeCost({mode,profile,side,fills,trade_date})` 处理 per-order 累积。`incrementalCost({...,previous_fills,next_fill})` 返回 `{cumulative,delta}`。

`affordableQuantity({mode,profile,side:'BUY',price,lot_size,available_cash_cents,max_quantity,trade_date})` 用含全部费用的单次完整成交估计二分合法整手数量。最大数量、整手、预算都必须显式传入，无默认本金/费率。

`maximumBuyReservation({mode,profile,executed_fills:[],remaining_quantity,limit_price,trade_date})` 额外保守覆盖任意部分成交的分舍入：剩余股数 × 每股 limit price 向上取整到分，加上仍可能发生的累积费用。含费 affordability 与最坏部分成交 reserve 的精度不同；亚分价格时 reserve 可能高于一次整单成本，reservation 可显式拒绝预算。

费用 profile 字段见 fixture：CNY；整数分字符串；HALF_UP；PER_ORDER；佣金率/最低佣金；卖出印花税；exchange_fee/other_fee 各有 rate 和 included_in=COMMISSION|EXCLUDED；滑点 treatment=SEPARATE_ESTIMATE|INCLUDED_IN_EXECUTION_PRICE。后者要求额外滑点 rate=0，避免价格内滑点再计一次。

所有整数分最多 38 位，禁止金额 float/exponent。价格最多 14 位整数/6dp；费率 0..1 且最多10dp；数量 positive safe integer。私有100位 Decimal 构造器不受全局 Decimal.set 影响。费用、生效起止和 trade_date 严格校验 Gregorian date，交易日身份仍由独立 Calendar adapter 提供。

`commission_cents` 是实际佣金 `max(rounded proportional commission,minimum)`。`minimum_commission_effect_cents` 是其中子归因；`proportional_commission_cents` 是比例部分。`total_friction_cents=commission+stamp_tax+exchange_fee+other_fee+slippage`，不得再次加 minimum effect。

部分成交按精确累积成交金额计算费用，再与上一累计值相减。最低佣金在首笔实际成交结算；取消未成交订单不收成交费用；部分成交取消保留已结算费用。minimum effect 的差分可负（比例部分上升、最低佣金子归因下降），实际 commission delta 不负。gross cash 按每笔实际成交单独四舍五入，不假装分拆成交与一次成交必然具有相同 gross rounding。

## Paper API

`createPaperService({db})` 返回以下异步方法，每个方法输入都必须显式 `mode:'DEV'|'PAPER'`，PROD 拒绝：

- `openAccount({mode,account_id,opening_cash_cents,event_time,trace_id,fixture_scope:'SYNTHETIC_TEST_ONLY',source_ref:{content_hash}})`。仅首次创建，重复必须匹配原始经济输入；不提供现金充值捷径。
- `reserveOrder({mode,account_id,idempotency_key,event_time,trace_id,intent,cost_profile,security,calendar,authorization,authority})`。
- `submitOrder({mode,account_id,order_id,strategy,symbol,idempotency_key,event_time,trace_id})`。
- `fillOrder({...submit fields,fill_id,quantity,price,market_data_at})`。
- `cancelOrder({...submit fields,reason_code})` / `rejectOrder({...submit fields,reason_code})`。
- `getAccount({mode,account_id})`, `getOrder({mode,account_id,order_id})`, `getLedger({mode,account_id})`, `reconcile({mode,account_id})`。

可运行的完整入参构建示例位于 `tests/p1a-paper-helpers.mjs` 的 `createIntent` / `reserveInput` / `operation` / `open`；测试不调用 legacy Engine。

PaperReplayOrderIntent 必须绑定 mode/account/order/client/strategy/symbol/side/quantity/limit/trade_date、rule_version、snapshot_hash、feature_hash、CostProfile version/hash、calendar_hash、security_hash、market_data_at、valid_until。有效订单类型仅 LIMIT reference；fill 买价不得高于 limit，卖价不得低于 limit。event_time 上海日期必须等于 intent trade_date，禁止 caller 自报旧日期。

证券输入：`{security_id,canonical_symbol:SSE:xxxxxx|SZSE:xxxxxx,original_symbol,lot_size,status:'ACTIVE',suspended:false,tradeable:true,version,available_at,content_hash}`。

日历输入：`{version,sessions:[YYYY-MM-DD] sorted unique,available_at,source:{kind:'SYNTHETIC_FIXTURE'|'OFFICIAL_CAPTURE',source_hash},content_hash}`。只使用明示 session；不靠系统工作日推断。买入 lot 的 sellable_date 是绑定 calendar 的实际下一 session；没有下一 session 拒绝买入 fill。状态/日历 available_at 必须 <= 操作时间。

`sealReferenceObject` 只封装内容 hash，不证明 source 真实、许可有效或官方可见时间。在真实数据应用里，必须由 Data adapter 的 admission 和 lineage closure 提供证券/日历输入；reference service 只接受 synthetic intent，不承担真实 source authority。

authorization 必须 `kind:'FIXTURE_HUMAN_CONFIRMATION',scope:'SYNTHETIC_TEST_ONLY',actor_type:'HUMAN_USER'`、精确 `order_terms_hash`、两个不同的 decision/final approval hashes。外部 authority 必须也为人类 fixture scope，且 `verified_approval_hashes:Set` 同时包含两份批准。payload 里自称 HUMAN_USER 不能替代外部 authority。`orderTermsHash` 绑定 snapshot/rule/cost/security/calendar 等所有条款，改变任何一项使旧确认失效。

## 现金、预留与持仓

`available_cash=settled_cash-reserved_cash`。账户现金在 Core/Event 间共享；每笔事务锁账户行，不能两策略花同一现金。订单/client/fill/idempotency key 都在 mode/account 层唯一；跨策略不得重复。同 ID 不同请求 hash 返回冲突，trace_id 作为诊断项不改变经济请求。

买单预留最坏现金支出；每个 partial fill 同一事务扣 settled cash、释放/保留剩余 reservation、写 lot、fill、hash-chain ledger 和 idempotency result。filled/cancelled/rejected 是终态，迟到 fill 拒绝。cancel/reject 释放一次剩余预留。

**明确保守限制：SELL 预先保留全部预计成交费用，即便成交收入原本可以支付费用。全仓零可用现金账户在此 reference 内无法发起卖单。总控已选择本轮保留并报告此限制；它不是券商规则，也不能升级为生产业务规则。** 实际卖出仍在同一事务增加收入、扣费用、释放预留；后续买单只能在卖出提交后使用收入。

持仓 lot 按 mode/account/strategy/symbol 独立，SELL 只预留并消耗自己 namespace 的可售 lot。另一策略不能卖 Core lot；同日买入不能卖；多卖单分别保留 lot，取消释放对应 allocation。EVENT_3 仅作为隔离验证 namespace，无策略实现。

## SQL / 幂等 / 核账

迁移候选 004 创建独立 `p1a_paper` schema：accounts、orders、lots、lot_reservations、fills、ledger、requests。所有表 mode CHECK 只接受 DEV/PAPER，fills/ledger/requests append-only。不存在真实 broker submit 表或函数。

服务要求 db 绑定同一 connection；BEGIN/COMMIT/ROLLBACK 和账户 `FOR UPDATE` 在 SQL 执行。对同一 db 对象的并发入口另有队列，防止单连接重叠事务；队列只是连接协议保护，现金保护仍由 SQL row lock / CHECK / unique key实现。重启从持久化 DB 读取订单、原始 cost/security/calendar、累计费用、lot、请求与序号；不依赖进程内缓存恢复经济状态。

每个实际 reference 操作写 ledger event，包含操作 event_time、security/calendar/cost/rule/snapshot/Feature 版本与 hash 绑定及 trace。市场数据的四时钟保留在被引用的 Data objects 中，不通过订单操作时钟回填。经济账本 hash 排除 trace_id，event_time 来自显式固定输入。不存在 wall-clock default 或随机 UUID；费用/现金/序号/生命周期仍进入 hash。请求/审计禁止 password/token/secret/credentials 字段。这里的 DERIVED 时钟只指本操作，并不改写 Market Data 原始 PIT 时钟。

`independentCostOracle` 完全使用 BigInt scaled rational + 独立 HALF_UP，不调用 cost engine 或 Decimal。`reconcilePaperAccount` 独立复算每个累积 fee 和 delta、最坏 reservation、现金、lot allocation/T+1、namespace 和 ledger chain；仅账本自报现金相加不算费用核账通过。

## 验证与技术债

本分支独立 scoped 测试显式执行冻结 001/002 和本模块候选 004；不把缺少 003 的分支声称为空库→latest 完整迁移。总控集成后负责 001→002→003→004→005 的完整链。

已验证 PostgreSQL/PGlite 真实 SQL、同连接并发双花攻击、持久化目录关闭/重新打开、部分成交/cancel/reject、minimum crossing、200次亚分价格 partial settlement、不同卖单 lot allocation、独立费用/ledger oracle、错误身份/namespace/时钟/版本/批准/secret字段。

尚未验证真实 PostgreSQL 多连接/多进程并发、服务崩溃恰在 COMMIT 前后的故障注入、真实券商 partial/cancel 实际结算规则、真实账户风险上限与20日真实前向 Paper。封装 source hash 不等于可信官方来源；真实 Data adapter admission 必须由总控集成验证。PaperReplayOrderIntent 仍是 synthetic reference；没有真实 gateway authentication、broker connection、真实费用交割单核账或生产释放路径。

新 synthetic CostProfile 的 effective_from / effective_to 均含端点。P0 旧 pure harness 的 to-exclusive 语义保持不变；本模块不进行真实 broker 配置映射，此差异不得推断成生产费率生效规则。总控已在最终004发布前增加fills/ledger/requests的TRUNCATE statement保护。
