# P1-B Wave F — Research Evaluation Activation Preparation

**工程结论：PASS_WITH_CONDITIONS；Owner验收PENDING，本轮交付后STOP。**
干净副本完整回归1498项：1497PASS / 0FAIL / 1既有可选V5SKIP；独立R2
4374原子断言全部通过。这些结果不构成历史数据、实际Paper或交易执行授权。

当前 human 已接受 Post-Wave-E PASS_WITH_CONDITIONS；旧 Gate、失败、原始证据
及参数状态保留。本轮只完成 Wave F A–G；附件后面的 Snapshot B / Day1 文本
是未来示例，明确不是此次授权。正式交接文档继续为主要 Source of Truth。

## 实际交付与工程边界

基线 afb102f2f10ceb4330d837b17ab580c478b42fbb；代码候选
cca9c2394db015a0ef9fb34fd315322dc9acc605；独立本地 branch
wave-f/evaluation-activation-20261006。release 1.0.0-wave-f-preparation，
23个代码/测试/文档/策略 pins。722个旧不可变文件保持原bytes；只允许3个导航
文件更新。既有contracts、migrations001–006/schema6、locks、V5/seals/旧账本
和旧runs都未改。没有增加新 native 合同或 JSON Schema。

```text
wave_f/
  common.py / core.py / run.py / check.mjs / display.mjs
  strategy.py / pit.py / backtest.py / activation.py
  tests/  fixture经济、PIT、时钟、durability、完整性与native边界
docs/wave-f/
  冻结候选、Owner决策表、三股证据矩阵、最低PIT Gate
  Backtest/Snapshot/Paper Readiness、runbook、失败、验收与证据索引
docs/adr/ADR-032-predeclared-research-candidates.md
```

采用1074个逐次重开的依赖：746个Git路径、328个私有路径；包含原有完整证据
链及31个新公共证据依赖。PIT子任务直接核验的来源共50个路径，复用项不重复
冒充新采集。两个元数据回放逐字节一致；代码Checkout可以移动，私有证据仍须
留在原位置。这不证明远程CI、私有归档搬迁或特权解释器完整性。

## A：冻结两个研究候选，未选择赚钱策略

Frozen-StrategySpec-v1.json及Git外Strategy-Preregistration绑定两个family：
CORE40_Q_PULLBACK_V1 / CORE40_Q_BREAKOUT_V1。共用Company/Financial Quality、
Growth、Valuation、官方Catalyst、Risk、Timing、Evidence与成本后Edge门槛；
进入/观察/退出/持有现金、每日复核与20–40session研究期限均明确。
候选来自正式交接的规则例子，并非从Wave E收益或三股后验走势调参。

冻结的是研究候选和评价草案。各20%/合计60%、2ATR、10%drawdown等数值明确
是待接受的研究提议，不是Owner真实风险政策。30项实际账户配置继续UNSET；
资本成本估计、周期正常化盈利、情景概率/误差缓冲、benchmark及其total-return
方法、模拟费用/滑点、统计协议和风险接受仍待Owner决定。缺关键特征即
NO_DECISION；fixture match仅是假设研究标签，没有native Signal。

事前声明CSI300 total return benchmark提议、5年/1260session目标、固定
IS/validation/retrospective时间区间、带40session purge/embargo的walk-forward
协议、两个family全部报告/失败保留和多重检验草案。统计重采样实现/依赖结构
及真实样本仍须前置审查，未声称已有显著性或Edge。**所有过去资料均保守视为
potentially exposed；之前已看过的327session不能重新称未见OOS。**
真正未见样本只能来自后续单独授权及验收的未来session。0新真实收益reveal，
0优化/grid search；未选择赢家。Owner-Policy-Decision-Sheet分开列出提议与
UNSET项，填写任何参数都不会自动开放正式回测或production。

## B：真实公共证据推进，历史PIT仍不完整

10次官方无凭据GET，10条发现查询/3次工具调用；没有授权API/secret lookup。
取得603993的官方HKEX托管发行人**A股**上市PDF、603228的SSE同期上市公告、
600312发行人当前网页回顾上市日期，后者明确不是同期可见性证据。
取得2026 SSE修订通知、原始OOXML和暂缓条款，及2023生效触发条件通知。
不能把2023网页日期当作实际生效session，也不能把2026规则倒填历史股票状态。
公共出处和版本/hash、时间精度/适用范围均在机器矩阵列出。

规则和上市锚点只关闭各自有限结构事实，不关闭连续5年数据域。三个证券仍
各只有327个不同raw日期，20250603–20260930，属于当前获取的QUARANTINED
版本。连续上市/退市、ST/name/status、停复牌、证券级限价与例外、完整calendar、
industry/universe、行动实施/单位/对账、财报首次可见/修订原文仍UNKNOWN。
保留3个HTTP301原始失败，未跟随HTTP重定向、未伪造成PDF或公告正文。
ann_date/f_ann_date/报告期/update_flag定义不是revision chronology证明。
published_at/available_at未知或DATE_ONLY保留原语义，不补午夜。

PRICE_BACKTEST_MINIMUM_PIT_READY=BLOCKED；formal price/fundamental PIT均BLOCKED；
C12–C22正式关闭0。当前retrieval不能证明历史available_at；Observed-at-time与
历史重建分开；无bar不推定停牌或可交易；当前幸存者/当前ST名单不回填历史。

## C：可执行合成回测与账本

新增strict synthetic accounting engine，next-calendar-session不是next-observed-bar；
no same-bar、逐lot T+1、停牌/未知状态、保守限价代理、RAW与adjusted隔离；
日期版佣金/最低佣金/税/含入关系/其他费/滑点、费用包含affordability、冻结
现金顺序、仓位/敞口/换手与drawdown kill均有计算和反例测试。
分红record/ex/pay分开、应收不等于可用现金、整数拆股/送股及可卖日期明确。
后来公布的行动按record cutoff因果进入；不要求多年行动都在起始策略冻结时
已知。factor只能信息字段，factor+cash不得重复；源价必须RAW合法tick。

每个cash/qty/lot/entitlement动作逐笔审计与hash chain，输出Gross/Net、全部
费用/滑点、权益/回撤/换手/benchmark/期末持仓/未收分红，不强制期末清仓。
包含1260session/3780bar常价合成金额oracle与确定性重放。
Decimal100、输入≤50有效位；Python fixture整数分钱严格限制JSON安全整数，
累计溢出阻断。这不是native LedgerEntry合同已适配的声明。

只运行synthetic fixture，actual source reader/real adapter未实现或激活，
run_formal硬阻断。Rights、零碎股折现、动态持有期分红税、多个歧义share action、
盘口队列/部分成交与分钟MAE/MFE不支持；不得把代理成交写成真实观察。
数据Gate、Owner政策、实际适配/审查与单独回测授权齐备前无正式经济结果。

## D/E：盘后与NO_DECISION准备；实际天数0

capture fixture1.0.1校验实际开市观察语义、盘后exact3原始bar、四钟、A→B
与source/rules/strategy/policy/schema/review版本链。每个session原始packet
绑定canonical source_payload hash及日期/证券/单位/值/时钟；旧原文重贴日期拒绝。
Caller自签review/LLM审批不等于真实独立review/HUMAN批准。

新SQLite只存synthetic NO_DECISION/metadata/failure两条append-only链：expected
head、day/capture/observations去重、冻结政策、事务rollback、线程并发单赢家、
干净新进程重开和只读recovery。失败链只保留sanitized reason，不保留未验证
payload/敏感内容或其hash；未来实际raw失败需另存authorized capture epoch。
未证明多进程同时写、断电/hot-journal修复或特权整库重写防护。

NO_DECISION工程不被真实资本/佣金UNSET阻塞；native Order仍不可产生。
九位纳秒是fixture格式，不能给实际来源补精度。无bar依然incomplete UNKNOWN，
不能制造flat bar。实际SourceObservation/ClockEvidence捕获和独立真实issuer
接线需在后续单独激活时验收，不可借用synthetic capability。

Snapshot B/Paper **并非只差一句Human授权**：还缺实际open/EOD观察、source
exception/capture acceptance、策略解读/版本与独立capture审查，以及真实adapter/
approval issuer激活。2026-10-08只为计划候选，actual_forward_days=0。
Provider/license/transport继续独立BLOCKED；public HTTPS文件不核验私有gateway；
API成功/Owner声明/15000月卡都未升级为许可或历史PIT。0模型/cloud/export/
broker/production/真实资金、0证券扩张、0调度，无等待到10月8日后台任务。

## 验证、独立审查与失败保留

干净fresh checkout候选cca9c239，离线依赖安装成功且检查实际退出0，Git保持clean。
完整1498项=1497PASS/0FAIL/1原有外部V5可选SKIP：1021Python全部通过，
477native中476PASS/1SKIP；本轮新增350Python+10native=360项全部通过。
独立R2共4374原子断言=3874Python+500native，0失败，工程PASS_WITH_CONDITIONS；
其中含1074依赖在审查前后两轮hash核验和722前代比较，不能称4374个策略实验。
1074来源前后逐字节一致，独立review联网/凭证/改源码均0。原R2报告形成时完整
回归尚在运行，该原报告不改写；总控validation.json记录随后实际结束结果。
独立Full-Fresh附录另做88项文件/日志/clone/pins核验全部通过，不追加到原4374；
原报告pending作为形成时的事实保留，后续实际回归条件由该附录闭环。
回归计数与Reviewer原子断言分开，不把重跑/失败epoch累计为新增测试。

独立R1 REMEDIATION_REQUIRED：两个真实synthetic工程发现——feature可见/抓取
时钟矛盾未拒绝、旧source hash重标session通过。均未获得实际权限。
已修正为available<=retrieved与逐row原文绑定；原accepted反例/输出/hash/脚本
和activation旧源码保留。strategy原整文件在修复前未保存，明确不伪造或把
重建文件冒充原始snapshot。最终R2已独立重测，两者在最终候选均被拒绝；
11个实际入口全部硬阻断，critical_actual_false_acceptance=false。

PIT首次smoke顺序、G1 enum预期及zsh保留变量；backtest语法、G2金额oracle
及G4测试工具；activation G2 helper；独立review调用目录/PYTHONPATH工具失败
均保留可用原始源码/完整log或实际工具拒绝，分类与产品发现分开。另一次未限定
Git路径的只读状态查询遇到Apple Git/Xcode许可环境限制；有效Git操作均使用
已有Homebrew Git，不改变系统许可设置。旧Post-
Wave-E失败、V5 CLI hash mismatch/旧seal/14日ledger baseline、可选V5SKIP、
行动歧义与对账差异不改写。Known-Failures逐项列出，未为了测试放宽门禁。

## 必须明确回答的六个问题

| 问题 | 本轮结论 |
| --- | --- |
| 三股历史价格能否正式回测？ | **不能。PRICE_BACKTEST_MINIMUM_PIT_READY=BLOCKED**；历史状态/行动/时钟、5年覆盖与正式来源政策仍不完整，Owner费用/策略/评价及后续单独授权未齐。 |
| 基本面PIT能否正式回测？ | **不能。** 还缺首次可见时点、完整修订链原文、单位/行业历史，日期字段不能代替。 |
| 剩哪些历史可见性缺口？ | matrix14domains/每股范围与minimum gate逐项列出；没有从当前观测回填，连续历史域正式关闭0。 |
| 哪些必须Owner决定？ | Policy Sheet列出family/benchmark/方法与校准/模拟费用资本/风险/样本和成功判据接受；真实30项继续UNSET_REQUIRED。 |
| 10月8日是否只差HUMAN authorization？ | **否。** 离线算法/runbook/存储已备；实际open/EOD、源例外、版本/解读/真实issuer与独立capture验收仍需逐项落实。当天不能仅凭计划或时间自动PASS。 |
| 能否产生native Signal/Order/broker write？ | **NO。** 本轮实际入口全部硬阻断；fixture研究标签/代理成交/NO_DECISION不得晋级native对象。 |

## 后续与交付

Owner验收后建议仅启动目标明确的Actual Capture/Forward agent，先解决本地
quarantine NO_ORDER来源例外、真实精度/缺bar政策及一次capture/review/issuer接线，
再以单独Human授权实际盘后捕获和验收；真实金额参数不应误阻塞纯NO_DECISION。
Data/PIT agent针对完整历史状态/行动/修订资料补缺；经济评价agent须等待Owner
批准研究政策及历史Gate，不因fixture通过启动正式回测。Independent Reviewer
继续只读，当前不自动启动任何下一阶段agent。

交付12类指定文件及Git-only rollback bundle，额外含runbook/ADR/版本/输入
pins/失败/完整验证证据/本机ZIP。最终Git head/tree/tag/clean和bundle由外部
Delivery-Checkpoint绑定，避免自引用。私有raw/数据库/凭证不纳入Git/bundle，
本机复验需原始私有归档保持位置，验收包不是公开再分发授权。
最终交付commit仅添加验收文档与导航；23个代码/测试/策略pins与被测试候选相同。
新repo已有.lock/测试/本地检查；本轮未新增Schema/迁移，旧001–006保持原字节。

STOP AFTER DELIVERY；Owner验收PENDING。不开正式回测、实际Snapshot B/Paper
Day1、Research Pilot、model/cloud/export、Signal/Order、broker或production。
