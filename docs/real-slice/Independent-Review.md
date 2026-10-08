# P1-B REAL STOCK SLICE 独立审查结论

**工程边界审查：PASS_WITH_CONDITIONS。LOCAL_REAL_RESEARCH_GATE：PARTIAL。** 本结论只对应修复后的 `266a7083ce2c77c31917899ced458951661ddaed`，29 文件 source pin `sha256:358cd6afd7100ce2c6283fffef39496e09149fe9bfcdd96de5d34ff80847e89e`。它不批准真实 Research Pilot，也不授予云端、历史回测或生产用途。

## 独立发现与修复复验

初始候选 `ba6cb20...` 的基础 33 项攻击通过，但本 Reviewer 另写的 38 项检查发现五次错误接受，归为两个缺陷。原 FAIL 报告、脚本和运行结果完整保留在 `Candidate-Failure-Review.md`、`review-attacks.mjs`、`review-results-2026-10-05T124459178Z.json`，没有重写成通过。

| Finding | 初始风险 | 修复后独立复验 |
|---|---|---|
| IR-001 / P1 | `this` 验证调用可被 `call/apply` 的替代 receiver 绕过；可签发回填 cutoff 的真实 issuer packet、接受错误 usepoint/已撤销 receipt、返回任意 raw/token 载荷 | 验证调用改为 closure 绑定的冻结 facade。原四个反例分别被 `SLICE_REF_INVALIDATED`、`SLICE_RECEIPT_REVOKED`、`SLICE_DQ_FAILED` 阻断；合法调用及异步输入变异控制保持正确 |
| IR-002 / P2 | Date.parse 截断 Card TTL；到期后 1ns 仍被接受 | 严格日历/时分秒验证后以纳秒比较。到期后 1ns、cutoff 前 1ns 被阻断；恰好到期和到期前 1ns 保持合法；无效日期、24:00、超过九位小数、无效 offset 拒绝 |

Reviewer 没有修改 repo、业务规则、政策、预期结果、旧账本、旧 seal 或 Git。修复及新提交由总控执行；复验使用新冻结代码和 Reviewer 自己的五份全新真实抓取，未修改最终交付原件。

## 实际运行证据

真实复验 cutoff 为 `2026-10-05T12:52:01.244Z`（上海 20:52:01）。机器结果为 `review-results-2026-10-05T125159272Z.json`，逐项日志为 `recheck-attacks.log`，独立复验脚本为 `review-attacks-recheck.mjs`。

| 检查集合 | 结果 | 证据性质 |
|---|---:|---|
| 总控基线攻击，由 Reviewer 针对自己的真实 live registry 执行 | 41 / 41 | 38 个拒绝反例 + 3 个异步输入保持控制 |
| Reviewer 独立编写的新增检查 | 49 / 49 | 31 个拒绝反例 + 18 个正向控制，含原五个失败复现 |
| Reviewer 直接时钟算术检查 | 10 / 10 | 显式 SYNTHETIC，不制造或恢复任何真实准入 |
| Owner 指定威胁类别 | 28 / 28 已执行 | 逐项 boundary/reason 见 `Independent-Review.json` |

100 是执行检查数量，包含正向控制和重叠威胁，不能理解为 100 个独立安全问题。本次发现的 P1/P2 实现缺陷已关闭，复验没有残留失败。旧全量 Golden 结果由总控的干净 checkout 检查提供，本 Reviewer 不把旧报告或测试总数代替本次边界攻击。

正常链产生两个实际 admitted source identity、两个 product、三只证券的三份 stock-reference snapshot、三份 receipt、三份 sanitized LOCAL_REVIEW_ONLY packet。原件五份：官网法律声明、休市公告、三个有限公告索引。15 条公告 metadata reference 与 14 条有限日历事实来自实际原始内容；市场行、财务行、模型调用、券商调用、执行写入均为零。所有 raw hash 与 capture 签名独立检查有效，自己的 raw/terms 变异测试后逐字节恢复。

## 范围仍然有限

| 数据类别 | 本轮实证 |
|---|---|
| Security/status | BLOCKED；工程指定 symbol 不等于已准入完整 SecurityIdentity/状态历史 |
| Calendar/rules | PARTIAL；仅公告明确日期，完整 session/board 规则缺失 |
| Raw bars | BLOCKED；没有 320 个交易日原始行情 |
| Corporate actions | BLOCKED；没有真实 action/revision feed |
| Adjustment versions | BLOCKED；没有真实 factor lineage/reconciliation |
| Financial revisions | BLOCKED；没有 12 季度原件及修订链 |
| Announcements | PARTIAL；每只仅五条 metadata reference，无完整 180 日历史及 PDF 正文准入 |
| Industry membership | BLOCKED；没有有效期历史及修订证据 |

公司行动、因子、财报修订、行业标签的伪造插入测试证明的是**注册 reference 边界拒绝扩大数据类型**，没有证明真实领域算法。公告删改测试证明的是 exact registered fact/hash 不可被消费者替换，不代表完整公告修订抓取器已实现。`Independent-Review.json` 明确标注这些限制。

实际时钟来源于本次 collector 成功取回原件后的完成时间；available_at、retrieved_at、observation_event_at 对应同一保守观察边界。DATE_ONLY 留日期且 instant 为 null。源更新窗口、mtime、trade_date、已知业务生效日都不成为历史 availability。直接纳秒和 precision 算术检查与真实 registration 检查分别报告，不混淆结构合法与准入权威。

官网 captured terms 仅支持本地非商业有限 reference 用途；没有 source-wide entitlement。Tushare 因用户明确没有可核验授权记录，在 secret lookup 和网络前保持 BLOCKED；未读取 Token。BaoStock/正式历史产品也没有得到准入。cloud/raw redistribution、历史 PIT、市场 feed、生产权利没有随网页抓取扩张。

Snapshot A 的三份实际快照均为 CLOSED，live_price=null、trade_trigger=false、tradeable=false；latest_trading_session=null。有限休市公告不能证明 320 日 session 或最近实际交易日，不能把 9 月 30 日作为推测默认值。**真实 Snapshot B 仍待 10 月 8 日后实际新数据；本次没有创造它。** synthetic A→B 只证明 hash/ref 变化和 Card invalidation 机制，不能认证未来市场变化。

## Fixture 完整版本链

独立复验实际组合冻结的 Closure export → OS 隔离模拟 consumer → importResearchResult → 原 assessSemantics → 严格 ResearchCard 1.0 + FixtureResearchChain 1.0 sidecar。packet/draft/assessment/card/snapshot/receipt/source evidence exact refs 相互绑定。相同输入回放一致；上游变化使旧 Card 失效，撤销不能被重复 producer 清除；TTL 精度修复通过。

Native Card 使用明确 synthetic symbol/account，真实 grade、Edge、概率、sizing 全为 UNSET_REQUIRED；can_produce_order=false。Illustrative assessment 的 S 只能 REQUEST_REVIEW。语义维度是固定 synthetic 坐标，不是由真实股票 facts 得出的质量/择时评级；没有实际股票或模型结果被用于评分。这关闭 fixture 组合验收缺口，不关闭真实 Research producers/calibration。

## 继续阻断的条件

本审查是 DEV 同进程 registry/私有 signer 边界的证明。归档 public signature 可离线核验原件和报告，无法恢复下一进程 live authority；宿主机时钟/HTTPS 是已声明的信任边界，没有伪称硬件可信时间或持久生产认证。

当前必须保持：LOCAL=PARTIAL，CLOUD=BLOCKED，HISTORICAL=BLOCKED，PRODUCTION=BLOCKED，REDISTRIBUTION=DENIED，RESEARCH_PILOT=NOT_GRANTED。C12–C22 不整组关闭：当前观察 clock 扩展和 fixture 版本链取得工程实证；真实身份、完整日历、行情、行动、因子、财务、行业、校准及 producers 条件仍需实际证据。30 个真实账户/费用/风险参数及真实 Edge/sizing 未配置；它们不阻塞本轮工程，但继续阻止真实资金执行。

完成本 Gate 后停止。需要后续实际新数据及 Owner 另行明确批准 Research Pilot；本审查、定时准备检查、fixture 结果和未来 Snapshot B 均不构成该批准。
