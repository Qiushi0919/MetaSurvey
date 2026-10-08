# P0 成本与账本验收基线

本目录只提供纯函数验收 harness，覆盖费用金额、可负担数量、模拟账本和 legacy 整数核账。它不是完整成本引擎、撮合器、券商网关或生产执行许可。正式交接文档仍是主要 Source of Truth；真实账户、券商、佣金、最低佣金、费用包含关系、结算单位、滑点校准与风险参数继续为 `UNSET_REQUIRED`。

## 明确的测试边界

- `tests/fixtures/synthetic/economics.json` 是 `SYNTHETIC_NOT_PRODUCTION`。137 分最低佣金、其中的费率、预算和日期均为任意边界例子，不能导入账户或当作当前法定收费事实。合成日历也不是经过验证的交易所日历。
- 成本 harness 只接受 `SYNTHETIC_NOT_PRODUCTION` 或 `LEGACY_READ_ONLY` 配置，不接受生产配置。所有必需参数必须显式给出；费用已包含时，其费率也不得省略或猜填。
- 当前只检验一个完整订单的 `PER_ORDER` 最低佣金。不支持部分成交、多日结算、撤单重报的实际券商收费规则。这些规则仍需用户账户合同或交割单确认。
- 模拟账本仅接受 `DEV` / `PAPER`。`CORE_40` 和 `EVENT_3` 在同一账户共享一个现金余额，各自 lot 隔离。`RESEARCH_6_18M` 和 legacy namespace 不能进入此交易 harness。
- 一张订单只应用一次完整 fill；第二个 fill 或同订单再次应用被阻断。后续正式部分成交实现必须另建状态与佣金累积合同，不能直接放松本 harness。
- 事件时间和顺序来自调用方，harness 检查它们是否一致，不能证明它们就是真实成交证据。输入按调用方声明的顺序逐项检查，绝不排序修复。跨调用保留 `asof_event_time` 和 `last_execution_sequence`，防止后面的卖出现金用于前面的买入。
- T+1 依赖显式交易日历和逐 lot `available_trade_date`，不能把日历天加一当作下一交易日。跨策略卖出、同日卖出和声称 `USER` / override 均不绕过约束。

## 金额和舍入

金额 wire 类型是最多 38 位的规范整数分字符串，允许负值；不接受 Number、科学计数、前导零、`+` 或 `-0`。内部现金与账本使用 `BigInt`。价格是最多 6 位小数的规范十进制元字符串；费率最多 10 位小数；不接受科学计数和多余尾零；数量为正 safe integer。依赖的 `Decimal` 使用私有 100 位精度构造器，不改变全局设置。

先用精确十进制 `price × quantity` 计算成交金额，每个显式费用成分分别 `HALF_UP` 到分，再求和。最低佣金先与未舍入佣金比较，然后该成分舍入。成交总金额单独 `HALF_UP` 到分。负金额的半分按远离零处理。输出超出 38 位分精度直接拒绝。

`INCLUDED_IN_EXECUTION_PRICE` 表示输入已经是执行价格。显式费用不再扣第二份滑点。费用包含标记为 true 时，对应成分为零。当前 harness 不生成参考价到执行价的滑点模型，也不推断法规或券商收费。

## API

`src/baseline/economics.mjs`：

```js
validateCostConfig(config, trade_date)
estimateCost({ price, quantity, side, trade_date, config })
affordableQty({ price, lot_size, budget_cents, max_quantity, trade_date, config })
parseCents(value, { nonnegative })
roundYuanToCents(value)
```

配置字段：`version`, `provenance`, `effective_from`, `effective_to`（显式 null 表示无到期日）, `currency`, `commission_rate`, `minimum_commission_cents`, `commission_scope`, `exchange_fee_rate`, `exchange_fee_included`, `stamp_tax_sell_rate`, `other_fee_rate`, `other_fee_included`, `rounding_mode`, `slippage_treatment`。生效区间左闭右开。

估计输出包括成分费用、`gross_notional_cents`, `explicit_fees_cents`, `cash_delta_cents`, BUY 的 `all_in_buy_cents` 和成本版本。可负担数量按显式 lot size 二分搜索，使用含费 BUY 金额，不能只用裸成交额。此函数输出是测试局部对象；正式跨模块 wire 必须另外经过版本化 `CostEstimate` 合同验证和 hash/trace 绑定。

`src/baseline/ledger.mjs`：

```js
replayFills({ opening, fills, trading_calendar, expected })
verifyLegacyIntegerSnapshot({ opening_cash_cents, opening_positions, rows, snapshot })
```

`opening` 必需字段：`account_id`, `mode`, `currency`, `cash_cents`, `lots`, `applied_fill_ids`, `applied_order_ids`, `asof_event_time`, `last_execution_sequence`。每个 lot 有 `lot_id`, `namespace`, `security_id`, `quantity`, `acquired_trade_date`, `available_trade_date`。

fill 必需字段：`fill_id`, `order_id`, `account_id`, `mode`, `namespace`, `security_id`, `side`, `quantity`, `execution_price_yuan`, `gross_notional_cents`, `explicit_fees_cents`, `cash_delta_cents`, `trade_date`, `event_time`, `execution_sequence`。BUY 增加 `lot_id`；SELL 增加显式 `lot_allocations: [{lot_id, quantity}]`。`event_time` 必须带 UTC 或 offset，`trade_date` 与 `Asia/Shanghai` 日期一致。账本自行用 BigInt 分数算成交金额、现金变化和 lot 数量，不调用成本函数自证正确。

可选 `expected` 检查账户、模式、现金和完整 lot 状态。返回新的现金、lot、幂等记录和最后事件上下文，不修改调用方 opening；没有审批、风险门禁或真实委托路径。

legacy 验证器只为旧 V5 原始整数字段提供安全整数转换，其他新 wire 不允许 Number 金额。旧 TRADE 行保存 `symbol`, `side`, `qty`, `price_mills`, `gross_cents`, 原始 `fees`, `cash_delta`；可核对 CASH_ACTION 的 `net_cash_cents`。旧 snapshot 保留 `cash_cents`, symbol-keyed `positions`（`qty`、如校验 NAV 则有 `mark` 厘）和可选 `nav_cents`。独立检查厘到分的 HALF_UP、逐行现金变化、非负现金、数量和 NAV，**不重算或改写旧费率，不改 seal，不重新标为 CORE_40 / EVENT_3**。父级 legacy adapter 单独使用显式历史费用 fixture 核查旧费用；这种 fixture 仍不是生产规则。

## Golden tests

运行 `node --test tests/economics.test.mjs tests/ledger.test.mjs`。20 项测试覆盖：Decimal 与独立 BigInt oracle、一分舍入边界、最低佣金下方/恰好/上方、含费可负担数量、费用包含/滑点单扣、成本版本时效、全部参数未定阻断、38 位金额及 unsafe Number 拒绝；T+1 与日历间隔、同日现金先后及跨调用冻结时点、共享账户现金与策略 lot 隔离、重复 fill/order、账户/模式/证券不匹配、现金/持仓快照核对，以及旧单位只读核账。

PIT、freeze-before-reveal、stale-data、ResearchCard / Signal / Approval / OrderIntent 版本失效和 production execution 门禁由其他 P0 合同与测试承担；此 harness 不替代这些验收，也不因其自身测试通过而授权真实资金。
