# Wave F Independent Review R2

**结论：PASS_WITH_CONDITIONS，仅针对受限工程准备；不授予数据、回测、Paper 或交易权限。**

审查候选：`cca9c2394db015a0ef9fb34fd315322dc9acc605`，release `1.0.0-wave-f-preparation`，23 个代码/政策 pins。实际 Snapshot B=0，actual_forward_days=0，新的真实绩效 reveal=0。

独立执行 **4,374 个原子断言：3,874 Python + 500 native，全部 PASS，0 FAIL**。这不是 4,374 个独立策略试验，也不是项目完整回归数量。计数包括 1,074 个活跃依赖在审查前和后的两轮哈希核验，以及 722 个前代不可变文件的比较；详细唯一断言 ID 和分类见 matrix.json 与各语言 evidence。作者已有测试没有被加入此计数。总控的 fresh clone 完整回归在本报告形成时仍独立运行，Gate 必须核验其最终退出和实际结果，不能采用预期数量代替成功。

## 已独立核验的行为

- 三股/两个 research family 事前冻结。旧 Wave E 走势和所有 retrospective 样本明确 exposed；没有通过改名字恢复 untouched OOS。未执行新真实收益、参数搜索或按结果选赢家。账户及费用/风险的 30 个真钱参数继续 UNSET_REQUIRED；候选门槛及统计协议只是待批准的研究提议。
- look-ahead / revision：未来财报 revision 的 ID、值和额外内容不改变已可见前缀；未来 financial period 不进入选择结果；可获得性、检索时钟、DATE_ONLY、current snapshot、缺失历史、UNKNOWN 与 QUARANTINED 自称 synthetic proof 均受门禁。每股 ST、停牌、上市、退市、universe 和 limit 成分分别被攻击。
- 两个 family 的所有 25 个特征被逐项攻击 future clock、unknown value、可用时钟晚于检索；金融特征还受 future period 隔离。隐藏政策修改、原始 freeze hash 失效、reveal 后冻结与未登记 family 被拒绝。未声称对合同外的任意 malformed future JSON 提供全面非干扰证明。
- 会计采用独立数值 oracle：多组佣金/最低佣金边界，费用包含可负担性、卖出税、滑点只计一次、现金先卖后买与反向次序，登记日分红权益在卖出后仍保留、除息 receivable/支付、拆股后 turnover 的期初净值、benchmark、drawdown 与终端未平仓。逐条 audit entry 对现金、数量和 hash chain 对账。next exchange session、同 bar、T+1、停牌不跳到下一有 bar 的日、调整价交易、公司行动/复权双计、未知状态和费用缺失均独立攻击。
- Python fixture 输入与派生输出超出 JavaScript exact safe integer 的情况都被拒绝；私有 Decimal=100 不受外部低精度上下文影响。fixture 数值仍不是生产默认值，也不能直接作为 native integer-string 资金合同。
- Activation 新 shape `1.0.1` 将每个 synthetic original 的日期、数据、单位、时钟与 URI/version/hash 绑定。旧 raw payload/hash 改贴新会话被拒绝。缺失任一 bar、盘后前捕获、未知状态、stale、重复 day/ID、隐藏冻结策略/来源/Schema/政策改变和伪装 HUMAN 的 LLM 均被攻击。所有记录为 NO_DECISION/safe_to_trade=false，fixture day 绝不增加 actual_forward_days。
- 新的私有 SQLite fixture 验证 reopen/recovery、不修账、expected head、并发只赢一个 append、SQL append-only、native_orders schema 注入与故障原文保留；这些仅是 fixture store，不是实际账户或 Paper 数据库。
- 5 个本轮真实 readiness 元数据对象不能通过 16 个旧 native 合同，不能升级为 ResearchCard/Candidate/Signal/Approval/Order/Fill/ADMITTED/PRODUCTION；caller 重新签 hash 只能 DISPLAY。formal producer 的 stock receipt registry 仍为空。11 个实际入口对 caller HUMAN/批准/来源/production 等解锁参数全部硬阻断。

## 原始证据与范围

实际重开 **1,074 个活跃依赖**，前后 bytes/hash/size/mode 完全一致；722 个不可变前代文件与 afb102f baseline 一致。新公共资料的 31 个路径和完整 50 个 public evidence 依赖分别核验原文 hash、大小与 0600；10 个新 GET/10 个 query/3 次 discovery call 的身份来自已冻结 capture。审查自身联网 0、凭证查询 0、原始文件修改 0。

直接从 HKEX-hosted PDF 重新提取文本确认 603993 的 A 股上市日为 2012-10-09，并与 H 股 2007-04-26 区分；SSE 603228 notice 的 2017-01-05 发布日与 2017-01-06 上市日不同；600312 当前 issuer 网页只证明其当前回顾说法，不是当年发布的记录。2026 SSE notice 与原始 DOCX 分别确认 2026-04-24 发布、2026-07-06 施行及 delayed clauses；2023 notice 是首只注册制主板股票上市首日触发，不能采用 generic 网页日期。三个 301 原文不是已验证公告 PDF，失败没有被消除。

这些文档只增加结构事实，不补足三股连续历史。每股仅 327 distinct session/330 retained bar observation，低于 1260-session 候选评价要求。三个 listing anchor 不是上市/退市区间或去存活偏差 universe。42 个域明细仍保留缺口；minimum price gate 的 30 个 required security-domain blocker 和额外来源/政策/成本/benchmark 要求未放行。ann_date/f_ann_date 与 update flag 不证明 first visibility 或 revision chain。日期不补午夜，当前检索不证明历史可见性，同 provider factor 不成为独立权威。

## R1 条件闭环与保留失败

R1 结论 REMEDIATION_REQUIRED 的 **两项真实 synthetic 工程发现均修复并在本轮独立重测拒绝**：R1-01 visible feature available_at > retrieved_at；R1-02 stale original 被改贴未来会话日期。未发现 ACTUAL false acceptance。R1 原脚本、接受结果、hash、activation 原代码/测试完整副本均保留；strategy 修复前完整字节副本未及时取得，本报告明确此限制，不重构或冒充原文件。

初次 R1 私有脚本调用缺 PYTHONPATH；初次 R2 native launch 的 workdir 漏前导斜杠，进程根本未创建。两者是 reviewer harness failure，具体原输出/工具拒绝分别留存；不是产品失败，也没有以测试绿灯抹除。R2 成功的执行日志和唯一断言 evidence 分开记录。

## Owner 的六个问题

1. **三股正式历史价格回测能否开始：NO / BLOCKED。** 部分 rule/listing 文档不完成历史 tradeability/action/calendar/universe/PIT；费用、策略/评价接受、benchmark、real adapter 与单独授权仍缺。
2. **基本面 PIT 回测能否开始：NO / BLOCKED。** 财报历史首可见时点、修订链原文、单位及行业历史仍未证明。
3. **剩余历史缺口：** 各证券连续上市/退市/name/ST/停牌、dated limit 与例外、完整 session/calendar exception、公司行动实施/登记/支付与单位、factor method/version 和 raw action reconciliation、去存活偏差 universe/行业、财报公告精度与 revision first visibility，以及完整五年历史和 total-return benchmark。
4. **Owner 必须决定：** 研究 family 与成功/失败/样本/多重检验方案、估计资本成本/周期盈利/Edge 概率与误差缓冲、benchmark identifier/total-return 方法、模拟经济本金/dated fee/slippage/风险仓位等。真钱原30项继续 UNSET。NO_DECISION 的无金额工程不应被真钱本金阻塞；未来真实 source exception、capture acceptance、研究版本解释、审查/人工 issuer 与激活授权仍须明确。
5. **Oct8 Snapshot B 是否只差 HUMAN 授权：NO。** 当前交付严格检测算法、runbook 与 durable fixture boundary。实际 open/EOD 尚未发生，actual collector/capture/review/approval issuer 和 store 接线/source policy 及解释政策仍需下一次授权范围中的验收；到日期或到16点不能直接激活。本轮 actual entrypoint 都是 hard block。不能把此 NO 写成 ready-to-fire PASS。
6. **本轮是否有产生实际 Signal / Order / broker write 的路径：NO。** 仅有明确标记的 fixture hypothetical execution 与 NO_DECISION store；不存在本轮 actual 数据/批准到 native 交易的桥。该结论不表示恶意解释器、任意外部程序或整个主机都经过审计。

## 条件与限制

该 PASS_WITH_CONDITIONS 仅对上述 commit/pins、生效 source hashes 与受限工程成立；代码/策略/来源版本改变须新审。总控最终 fresh clone 完整回归必须实际通过，不能从新360 tests 或本文4,374 assertions 推定全回归成功。可移植性只覆盖本地 checkout 移动且旧 private archive 原址不动，不证明 remote CI/证据搬迁。

真实 provider/license/transport、historical/source admission、formal backtest、actual Snapshot B/Paper、model/cloud export、native order/broker/production 均继续 BLOCKED。准备不是策略 Edge 的证据。unsupported rights/fractional cash-in-lieu/dynamic dividend tax/minute queue/partial fill/MAE-MFE 及 bootstrap/OOS 统计、real source reader/activation 接线不得被当作已完成。SQLite hash/trigger 与 process-local synthetic handle 不抵御特权整库重签、恶意解释器或全主机攻击。23 个新 pins 的 credential literal pattern scan 仅是有界检查，不声称全机器凭证审计。

**STOP_AFTER_DELIVERY：等待 Owner 验收；本报告不自动开启下一阶段。**
