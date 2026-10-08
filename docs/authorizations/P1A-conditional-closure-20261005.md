



A股交易系统 P1-A：Codex 总控执行与 Gate 结论指令
Executive Summary
我重新逐项读了正式交接文档、P0 Gate、P0 深度复核以及你刚提供的 P1-A Gate Review。结论与我前面给你的“现在启动 P1-A”已经不同：

现在不应该再给 Codex 一条“启动 P1-A”的指令。P1-A 实际已经做完，而且工程结果明显超出了最初 P1-A 的最低要求。当前正确动作是：接受它已经到达 PASS_WITH_CONDITIONS Gate 的事实，先执行一次“P1-A 条件闭环审查”，再决定是否开放 P1-B。

当前 P1-A 已经有相当完整的工程证据：P0 被 annotated tag 和 bundle 冻结并可从独立 checkout 重放；P1-A 自 clean clone 重装依赖后执行 210 项检查，结果为 209 PASS、0 FAIL、1 optional SKIP；SecurityIdentity、PIT fail-closed、Raw→Normalized、Snapshot lineage、Cost Engine、Affordability、账户预留、Paper lifecycle、Ledger reconciliation、deterministic replay、friction stress、Micro-Ladder rejection、成本归因、CORE_40 skeleton、MAE/MFE 和机器可读 UNSET_REQUIRED inventory 都已经实现。独立 Reviewer 也完成只读攻击性复核。

尤其值得肯定的是，你最开始最在意的“45.2、45.5、45.8 这种伪精细买点”已经不只是写进文档，而是真正形成了 REJECT_INSUFFICIENT_INCREMENTAL_EDGE / REJECT_INSUFFICIENT_NET_EDGE / REJECT_INSUFFICIENT_EDGE_COST_RATIO 三类拒绝机制；交易成本压力实验也实际证明，在毛利润相同的情况下，摩擦升高会显著吞噬净利润，并进一步让 Edge Filter 把完成交易数从 6 降到 4、再降到 2。

这正符合正式交接文档最核心的设计原则：费用必须先于交易准入计算；本地程序负责数据、成本、信号、回测和确定性执行准备；ChatGPT/Deep Research 后续负责研究判断，但不能把自然语言直接变成真实订单。 

因此，我不建议让 Codex 重新做一次 P0→P1-A GAP Analysis，也不建议重新启动 Agent A/B。那样会重复施工，甚至可能污染已经冻结的 P1-A 证据。现在应该把你原本要求的“代码修改前先 GAP Analysis”改成：

在任何新的代码修改前，先提交 P1-A PASS_WITH_CONDITIONS → Gate Closure 的 GAP Analysis 和闭环方案，并等待人工批准。

目前真正剩下的问题并不是 P1-A 核心机制没有做出来，而是“真实数据准入”和“生产级基础设施”仍然没有完成：完整官方 security/status feed、全年 calendar、真实 corporate action / financial parser、来源许可与历史 available_at 证明、真实 PostgreSQL 多连接并发、RBAC、恢复与 COMMIT fault injection、真实券商费用映射、真实用户认证、真实账户风险参数等均仍被明确保留为条件项。P1-B 和真实资金执行目前都继续 BLOCKED。

我的 Gate 判断是：

P0：PASS
P1-A：PASS WITH CONDITIONS
立即重做 P1-A：不批准
真实交易：继续禁止
GUI 大规模开发：继续禁止
EVENT_3：继续禁止
Research Intelligence 全面开工：暂不批准
下一动作：P1-A Conditional Closure / Data Admission Boundary Review

这也比“为了测试全绿而把所有技术债都消灭”更合理。P1-B 并不需要先做真实券商、Kill Switch、生产 PostgreSQL 集群这些 P2 能力；它真正需要的是一个可靠前提：

Research Agent 只能消费 VERIFIED / ADMITTED snapshot，绝不能把 QUARANTINED、license unknown 或 PIT 不可证明的数据悄悄送进研究层。

下面这份就是我建议你现在直接复制给 Codex 总控的正式指令。

当前 Gate 判断与交付矩阵
P0 原本建立了独立 repo、16 份 V1.0.0 合同、migration、八份 ADR、legacy manifest、Golden Tests 与 30 项 UNSET_REQUIRED，并正确保持 V5 为 LEGACY_EXPERIMENT；P1-A 随后又增加了数据、成本、Paper、Replay、Audit、CORE_40 和路径指标等真正的实现层。
 

因此下面的矩阵不是“从零待做事项”，而是 Codex 必须在 P1-A Gate Closure 中逐项证明现状、补齐条件或明确延期归属的验收矩阵。

交付物	验收标准	当前判断	负责人	优先级	估计工时
Git repo / Gate baseline	独立 repo；P0/P1-A tag、commit、bundle/hash 可验证；clean checkout 可复现；工作树状态明确	已基本通过，需在 Closure 报告重新列证据	unspecified	P0	unspecified
Source of Truth freeze	正式交接、P0、P1-A Gate 的 SHA/版本关系明确；不得由后续 ADR 偷改业务目标	已基本通过	unspecified	P0	unspecified
Contracts 列表与版本	冻结 V1 contracts 不被静默修改；P1-A module schemas 有独立 release/version/hash	已通过，需汇总 machine manifest	unspecified	P0	unspecified
Schema migration	空库→latest 成功；重复迁移幂等；checksum 防篡改；迁移只追加不回改	已通过至 005，需重新给 migration IDs/hash	unspecified	P0	unspecified
Legacy manifest	KEEP/MODIFY/ISOLATE/DEPRECATE/DELETE_LATER 机器可读；V5 永远不映射 CORE_40	已通过	unspecified	P0	unspecified
Golden Tests	PIT、T+1、cash ordering、fee-inclusive affordability、namespace、stale、duplicate、version invalidation、UNSET fail-closed 等必须 0 FAIL	已通过；P1-A 总检查 209 PASS / 0 FAIL / 1 optional SKIP	unspecified	P0	unspecified
Clean reproducibility	从独立 clone、新依赖目录、空 npm 配置、无 legacy credentials 条件下复现	已通过 darwin/arm64；跨平台不是当前 Gate 硬要求	unspecified	P0	unspecified
Data pipeline architecture	Raw→Observation→Staging→Normalized→DQ→Snapshot 的 lineage 完整	机制通过	unspecified	P0	unspecified
Canonical SecurityIdentity	不猜 exchange；保留 original symbol；冲突 quarantine；状态 PIT 化	机制通过；真实完整官方 master 未完成	unspecified	P0	unspecified
Trading Calendar	明确 session/version/source；超覆盖范围 fail-closed	有界 reference 通过；全年准入未完成	unspecified	P0	unspecified
Real-source PIT admission	event/published/available/retrieved 语义可证明；不得用 retrieved 回填 available	fail-closed 已通过；真正可交易历史 PIT 未完成	unspecified	P0	unspecified
bars_1d pipeline	真实 raw bytes → normalized；raw/adjusted 隔离；无法证明 PIT 时禁止 snapshot admission	已完成真实 slice；仍 NON_TRADEABLE	unspecified	P0	unspecified
Corporate actions	action/factor lineage、ex-date 可见性、raw/adjusted 隔离；不得前视	机制通过；真实 feed/权益数学未完成	unspecified	P1	unspecified
Financial revisions	ORIGINAL/RESTATEMENT 追加版本；旧 cutoff 看不到未来修订	机制通过；真实 parser/source admission 未完成	unspecified	P1	unspecified
SnapshotManifest	内容寻址；closure refs；一个 raw byte 改变必须导致 hash 变化；旧 approval 不可复用	已通过	unspecified	P0	unspecified
Cost Engine	Decimal/整数分、minimum、stamp/exchange/other/slippage、included relation、partial fill settlement	synthetic reference 已通过；真实券商参数保持 UNSET	unspecified	P0	unspecified
Affordability	gross + 全部费用 <= available cash；不能只按裸股款	已通过	unspecified	P0	unspecified
Micro-Ladder Filter	新 tranche 必须证明增量 benefit 足够覆盖完整新增摩擦，否则拒绝	已通过 experimental；生产阈值仍 UNSET	unspecified	P0	unspecified
Account reservation	shared cash、strategy isolation、reserve/release/cancel/partial fill、不能双花	Paper reference 已通过	unspecified	P0	unspecified
Ledger / Replay	append-only、独立 oracle、T+1、费用、lot、hash chain、restart idempotency	已通过	unspecified	P0	unspecified
Paper lifecycle	Reserve→Submit→Partial/Full Fill→Cancel/Reject→Ledger→Reconcile；所有 PROD 入口拒绝	已通过，SELL 零现金限制待后续设计	unspecified	P1	unspecified
Deterministic Replay	相同 snapshot/config/code/cost/rule 输入运行两次经济结果完全一致	已通过；有固定 economic / ledger hash	unspecified	P0	unspecified
CORE_40 skeleton	20–40 session 是 review horizon，不是硬持有；允许 thesis/risk/event/structure 提前退出	已通过	unspecified	P0	unspecified
MAE/MFE	5/10/20/40D、days_to_positive、days_to_MFE、drawdown duration 等；必须标明 DAILY_APPROXIMATION	已通过	unspecified	P1	unspecified
Transaction-cost attribution	gross、各项费用、slippage、total friction、net、friction ratios 分开	已通过	unspecified	P0	unspecified
Friction Stress Test	LOW/BASE/HIGH 同毛 PnL 下证明 net PnL 差异；Edge ON/OFF 分开	已通过	unspecified	P0	unspecified
Audit chain	Data→Snapshot→Feature→Cost→Replay 真实 parent/hash 链；append-only；敏感字段最小化	已通过基础攻击测试	unspecified	P0	unspecified
Independent Reviewer	Reviewer 只读，不修改业务规则；攻击关键门禁并形成 notes/hash	已通过，结论 PASS_WITH_CONDITIONS	unspecified	P0	unspecified
UNSET_REQUIRED inventory	从 schema 自动产生；逐字段缺失 fail-closed；不得只写“30项”	已通过	unspecified	P0	unspecified
Production Gate	productionGate.allowed=false；无 broker submit/credentials/LLM auto-order path	必须继续保持	unspecified	P0	unspecified
Gate artifacts	commit id、tag、test run id、migration id、manifest hash、golden report、reviewer notes 均可追踪	已有大部分；Closure Gate 重新索引	unspecified	P0	unspecified

P1-A 报告目前已经给出了关键实现证据，包括 p0-v1.0.0-20261005、P1-A clean clone 验证、060acfe... 候选提交、实际经济实现 commit 8cca360...、p1a-review-20261005 tag，以及 deterministic replay 的 economic hash 和 ledger chain hash。Closure 阶段应该做的是统一索引和确认，而不是为了产生“新 commit”重新写已有实现。

可直接发送给 Codex 总控的正式指令
text
复制
你现在是 A股交易系统 V1 的 Lead Engineer / Orchestrator。

请注意当前真实项目状态：

P0 已通过。
P1-A 已完成技术实现与独立 Reviewer 审查，
当前 Gate 结论为：

PASS_WITH_CONDITIONS

这不是“尚未开始 P1-A”。

因此：
不要重新执行 P0→P1-A 重构，
不要重新启动已经完成的 Agent A/B 工作，
不要为了产生新代码而修改已经通过的实现。

正式交接文档仍然是主要 Source of Truth。
P0 Gate Review、P1-A Gate Review、冻结 contracts、
ADR、migration 和 machine evidence 属于次级工程证据。

任何未明确指定的真实账户、券商、费用、风险、
数据许可、评分、概率、Edge、Sizing 和生产执行参数，
继续标记：

UNSET_REQUIRED

不得自行填写。

==================================================
本轮名称
==================================================

P1-A CONDITIONAL CLOSURE
/ P1-A Gate 条件闭环审查

本轮目的不是继续扩功能。

目的只有三个：

1. 确认 P1-A 已完成能力的证据闭环；
2. 对 PASS_WITH_CONDITIONS 中的条件进行分类；
3. 判断哪些条件必须在开放 P1-B 前解决，
   哪些可以明确延期到 P1-B/P2/Production Readiness。

在本轮人工 Gate 批准前：

P1-B = BLOCKED
Research Agent = BLOCKED
真实交易 = BLOCKED
GUI 大规模开发 = BLOCKED
EVENT_3 = BLOCKED

==================================================
开始任何新代码修改之前
==================================================

先不要改代码。

先提交：

《P1-A PASS_WITH_CONDITIONS 条件闭环 GAP Analysis》

必须包含：

A. 当前 P1-A 已完成能力清单

B. PASS_WITH_CONDITIONS 中所有 condition / technical debt /
execution blocker 的完整清单

C. 将每项分成：

1. MUST_CLOSE_BEFORE_P1B
2. MAY_DEFER_TO_P1B
3. MAY_DEFER_TO_P2
4. PROD_ONLY_BLOCKER
5. ACCEPTED_KNOWN_LIMITATION

D. 对每项说明：

- 为什么属于该级别
- 不修会造成什么风险
- 是否会污染 Research Intelligence
- 是否会污染回测
- 是否会影响真实执行
- 所需修改模块
- 所需 tests
- 所需 migration
- 是否涉及冻结 contract
- 是否需要用户业务决定

E. 提交 P1-A Conditional Closure Plan

在我人工批准 GAP Analysis 与 Closure Plan 前：

不得开始新的大规模代码修改。

注意：

不要重新提交“P0→P1-A migration plan”。
该迁移已经完成。

现在需要的是：

P1-A PASS_WITH_CONDITIONS
→
P1-A GATE CLOSURE PLAN

==================================================
Gate Closure 的核心判断原则
==================================================

不要错误地认为：

“所有生产技术债都必须在 P1-B 前完成”。

P1-B 是 Research Intelligence，
不是 production trading。

因此请重点判断：

Research Agent 是否能够被严格限制为：

VERIFIED / ADMITTED SNAPSHOT ONLY

只要某数据：

- license UNKNOWN
- terms UNVERIFIED
- available_at 无法证明
- source lineage 不完整
- DQ failed
- Snapshot admission BLOCKED
- QUARANTINED
- stale
- future visibility uncertain

都不得进入可交易 ResearchCard / Candidate / Signal 输入。

这条边界如果不能硬保证，
P1-B 不得开放。

==================================================
优先检查的 P1-A Conditions
==================================================

至少逐项处理以下问题：

1. Canonical SecurityIdentity
   - 机制已通过
   - 真实完整官方 security/status feed 未完成

2. Trading Calendar
   - 当前只有有界官方 reference
   - 全年历史 calendar / 当前完整 session rule 未完成

3. Real-source PIT
   - fail-closed 已实现
   - 真正可交易历史 available_at 证明未完成

4. Market Data
   - Raw→Normalized slice 已实现
   - 当前真实行情仍因 clock/license 缺失被 NON_TRADEABLE 阻断

5. Corporate Actions
   - lineage / factor visibility 机制已实现
   - 真实 feed / adjustment math /
     entitlement reconciliation 未完成

6. Financial PIT
   - revision mechanism 已实现
   - 真实 parser / revision sample / source admission 未完成

7. Real PostgreSQL
   - PGlite/当前 SQL 测试不等于真实 server
   - 多连接/多进程 cash concurrency、RBAC、
     backup/recovery、fault injection 未验收

8. Paper SELL reservation
   - 当前保守实现可能导致
     零 available cash 的全仓账户无法提交 SELL
   - 不得把该行为解释为券商规则

9. Real broker cost mapping
   - 真实佣金/minimum/收费范围/rounding
     仍 UNSET_REQUIRED

10. Authentication / broker gateway / Kill Switch
    - 当前未实现
    - 这些原则上属于 PROD_ONLY_BLOCKER，
      不应为了开放 Research P1-B 而提前接实盘

11. Research calibration
    - Quality / Timing / Grade / Edge / probability /
      sizing / admission policy 未确认
    - 不得在本 Closure 阶段偷偷实现

==================================================
本轮必须保留的 UNSET_REQUIRED
==================================================

至少以下真实字段不得自行填充：

- real account_id
- real capital
- target order amount
- max positions
- per-trade risk limit
- sector exposure limit
- daily loss limit
- portfolio drawdown limit
- margin / leverage permission
- trading frequency policy
- CORE_40 real budget
- EVENT_3 real budget
- broker_id
- real commission rate
- real minimum commission
- commission charging scope
- exchange fee
- exchange-fee inclusion relation
- regulatory / other broker fee
- other-fee inclusion relation
- sell-side tax/stamp configuration
- real fee effective period
- base slippage
- stress slippage
- broker rounding rule
- fee verification source
- user_risk_policy_version
- production micro-ladder safety_multiple
- production minimum_net_edge
- production minimum_edge_cost_ratio
- production sizing policy
- production probability calibration policy
- real market-data licensing/admission policy

历史实验中的：

5000 / 6000 / 10000 元本金、
3000 / 8000 元单票金额、
旧佣金、
旧滑点、
旧止损参数

全部禁止自动继承。

==================================================
禁止事项
==================================================

本轮至少遵守以下禁止事项：

1. 禁止重新运行或恢复 V5 策略实验。
2. 禁止把 V5 改名或包装为 CORE_40。
3. 禁止修改旧 seal 以消除 legacy CLI mismatch。
4. 禁止覆盖、重算或美化旧 ledger。
5. 禁止把 synthetic fee profile 变成 production default。
6. 禁止猜测任何真实账户参数。
7. 禁止猜测任何真实券商费率。
8. 禁止把 retrieved_at 回填成历史 available_at。
9. 禁止把 QUARANTINED 数据送入可交易 Research 输入。
10. 禁止因为网页公开可访问就假定有数据再利用许可。
11. 禁止把 raw / adjusted price 互相覆盖。
12. 禁止用今天的 security name/status/sector 回填历史。
13. 禁止用未来 corporate action 生成过去可见的复权价格。
14. 禁止让 LLM APPROVE 等价于 HUMAN_USER approval。
15. 禁止新增真实 broker submit path。
16. 禁止读取或提交真实 broker credentials。
17. 禁止打开 productionGate。
18. 禁止启动 EVENT_3 策略实现。
19. 禁止开始 S/A/B/C/X 参数优化。
20. 禁止开始 Quality/Timing/Edge 概率校准。
21. 禁止大规模开发 GUI。
22. 禁止为了“测试全绿”放宽任何 PIT、cost、approval、
    namespace、cash 或 audit 门禁。
23. 禁止把 DAILY_APPROXIMATION MAE/MFE
    描述成分钟级真实路径。
24. 禁止把 Experiment A/B 的 synthetic PnL
    描述成策略收益。
25. 禁止把当前 Paper reference implementation
    描述成真实券商行为。

==================================================
Milestone Artifact 规则
==================================================

从现在开始，每个里程碑必须留下可审计 artifact。

至少包括：

- git branch
- commit id
- annotated tag（适用时）
- source tree hash
- contract release hash
- migration id
- migration checksum
- schema validation report
- test run id
- test command
- test counts
- golden test report hash
- data/source manifest hash
- legacy manifest hash
- SnapshotManifest / fixture hash
- experiment result hash
- independent reviewer notes
- reviewer report hash
- Gate report JSON
- Gate report Markdown

任何报告里的 PASS
必须能追踪到机器证据。

不得只写：

“已验证”
“测试通过”
“没有问题”

而没有 artifact。

==================================================
子 Agent 规则
==================================================

本轮暂时不要创建大量 agent。

在 Closure Plan 获得人工批准后，
最多建议：

Agent DA：
Data Admission Closure

Agent PH：
Platform / Paper Hardening
（仅处理被批准为 P1-B 前必须解决的项）

Independent Reviewer：
只读攻击验证

总控掌握：

- shared contracts
- ADR
- migration numbering
- Gate status
- Source of Truth
- final merge

每个子 agent 开工前必须提交：

Context
Goal
Inputs
Outputs
Interfaces
Constraints
Tests
Definition of Done

没有上述任务合同，不得开工。

子 agent 不得自行修改项目级架构。

发现需要改变：

- frozen contract
- Source of Truth
- strategy semantics
- approval model
- UNSET_REQUIRED policy
- production gate

必须返回总控，
由总控升级为人工决策。

==================================================
Golden Tests 必须继续保持
==================================================

以下 baseline 不得回退：

- PIT / future-data isolation
- freeze-before-reveal
- T+1
- same-day cash ordering
- integer / Decimal / BigInt reconciliation
- minimum commission boundary
- fee-inclusive affordability
- raw / adjusted isolation
- corporate-action visibility
- financial revision PIT
- security identity conflict quarantine
- strategy namespace isolation
- stale data blocking
- duplicate order prevention
- card/version invalidation
- Snapshot lineage closure
- source-byte mutation invalidation
- same cash double-spending prevention
- partial fill accounting
- restart idempotency
- append-only audit protection
- unknown config production block
- LLM != HUMAN_USER approval
- PROD gateway rejection
- micro-ladder insufficient-edge rejection

任何修复导致这些测试下降：

Gate 立即 FAIL。

==================================================
当前必须保存的经济实验
==================================================

保留 P1-A Experiment A：

同一个：

Snapshot
FeatureSet
AccountProfile fixture
CostProfile
RuleVersion
CalendarVersion
SecurityVersion
CodeVersion

重复运行必须得到相同：

order sequence
fill sequence
ledger
NAV
cost breakdown
MAE/MFE
economic hash
ledger chain hash

保留 Experiment B：

LOW_FRICTION
BASE_FRICTION
HIGH_FRICTION

必须保持：

Gross PnL
与
Net PnL

明确分开。

Edge OFF 与 Edge ON
必须是两个实验层。

禁止通过修改选股、
价格档位、
quantity
去“优化”压力测试结果。

==================================================
Micro-Ladder / 手续费规则
==================================================

继续保留：

REJECT_INSUFFICIENT_INCREMENTAL_EDGE
REJECT_INSUFFICIENT_NET_EDGE
REJECT_INSUFFICIENT_EDGE_COST_RATIO

任何额外 tranche：

必须单独计算完整 round-trip incremental friction。

不得因为 AI 给出了：

45.20
45.50
45.80

这样的价格，
就认为三个档位都有交易价值。

如果新增档位预期改善不足以显著覆盖新增摩擦：

拒绝。

但：

production safety multiple
production minimum net edge
production edge/cost ratio

继续 UNSET_REQUIRED。

不得由 Codex 自行选择。

==================================================
P1-B 放行条件
==================================================

Closure Plan 中必须提出明确的：

P1B_READINESS_GATE

至少证明：

1. Research Intelligence 无法读取 QUARANTINED 数据。
2. Research Intelligence 无法读取 future-invalid 数据。
3. Research Intelligence 只能引用验证过的 SnapshotManifest。
4. Card 输入能追踪至 source/raw/hash/time/version。
5. Research 输出不会直接产生订单。
6. LLM approval 不构成人工批准。
7. CORE_40 / EVENT_3 / RESEARCH_6_18M namespace 保持隔离。
8. Cost Engine 可以在 Candidate admission 前运行。
9. 真实费用未知时不能生成“适合真实账户”的结论。
10. productionGate 继续 false。
11. Broker transport 不存在或继续硬禁用。
12. P1-B 能在纯 MANUAL_EXPORT / PAPER 环境工作。

如果这些条件不能满足：

P1-B = BLOCKED。

==================================================
本轮不要求解决的内容
==================================================

除非 GAP Analysis 证明它是 P1-B 安全前提，
否则本轮不要为了“完美”提前建设：

- 真实 broker adapter
- 实盘自动下单
- production Kill Switch 部署
- 完整 GUI
- EVENT_3
- Level-2
- 高频 watcher
- 全生产 Kubernetes / service mesh
- Research scoring optimization
- AI选股策略
- 概率模型
- portfolio alpha model

这些不是 P1-A Closure 的目标。

==================================================
Closure 完成后的 Gate Review
==================================================

完成批准范围后，
提交：

P1-A Conditional Closure Gate Review

至少包含：

1. Executive conclusion
2. 当前 Git state
3. P0 / P1-A tags / commits / hashes
4. Contract release matrix
5. Migration matrix
6. Golden Test matrix
7. Data Admission matrix
8. Security/Calendar/PIT 状态
9. Cost Engine 状态
10. Paper/Ledger/Replay 状态
11. CORE_40 skeleton 状态
12. MAE/MFE 状态
13. Transaction-cost attribution
14. Friction stress result
15. Micro-Ladder result
16. Audit-chain evidence
17. Independent Reviewer findings
18. UNSET_REQUIRED machine inventory
19. Known limitations
20. Deferred-to-P1B list
21. Deferred-to-P2 list
22. PROD_ONLY_BLOCKERS
23. P1B_READINESS_GATE result
24. ProductionGate result
25. Artifact index

最后只能输出以下三个结论之一：

PASS
PASS_WITH_CONDITIONS
FAIL

不得使用模糊措辞。

==================================================
重要：完成后停止
==================================================

即使 P1-A Closure 最终结论为 PASS：

也不要自动启动 P1-B。

不要创建 Research Agent。
不要调用 Deep Research。
不要开始评分。
不要开始选股。
不要开始 GUI。
不要开始真实交易。

提交 Gate Review 后停止。

等待我的人工 Gate Review 和明确：

APPROVE_P1B

后，才能进入下一阶段。
上面这条指令与你原本要求的“代码修改前必须先 GAP Analysis”精神一致，但我刻意没有要求 Codex 再做一次 P0→P1-A migration plan。因为该迁移事实上已经完成，再要求它做一次只会制造两套互相冲突的迁移基线。第一阶段审查最初要求的 preserve → isolate → replace → verify → deprecate 已经被 P0/P1-A 实际执行，V5 也仍被正确隔离。
 

P0 到 P1-A 的工程时间线与 Agent 流程
当前实际状态更接近下面这条时间线，而不是“准备启动 P1-A”。P0 已完成合同/Schema/legacy 隔离，P1-A 已经实现 deterministic foundation；现在停在人工 Gate 之前。
 

P0 基线审查
正式交接文档成为Source of Truth
新 repo 与 legacy隔离
V5 固定为LEGACY_EXPERIMENT
P0 Contracts /Schema
16 个 V1 contracts
001 / 002 migrations
ADR-001 ~ ADR-008
UNSET_REQUIRED
Production Gate OFF
P0 Golden Baseline
98 tests
Legacy 14日 replay
旧 seal mismatch如实保留
P1-A DataFoundation
CanonicalSecurityIdentity
Raw → Normalized
PIT / Snapshotlineage
Calendar / Action /Financial revisionmechanics
P1-A EconomicFoundation
Cost Engine
Affordability
Reservation
Paper lifecycle
Ledger / BigIntreconciliation
P1-A ResearchSupport Metrics
CORE_40 skeleton
MAE / MFE
Cost attribution
Micro-Ladder Filter
P1-A Experiments
Deterministic Replay
LOW / BASE / HIGHfriction stress
Edge OFF / ON
P1-A IndependentReview
210 checks
209 PASS
0 FAIL
1 optional SKIP
当前状态
PASS_WITH_CONDITIONS
用户 Gate =PENDING
P1-B BLOCKED
Production BLOCKED
下一步
Conditional ClosureGAP
人工确认
再决定是否APPROVE_P1B
A股交易系统 V1：P0 → P1-A → 当前 Gate


显示代码
Agent 关系应该继续保持“总控拥有架构和最终合并权，Reviewer 不写业务规则”的结构，而不是让多个 agent 自由并行修改共享 contracts。P1-A 当前报告本身就是在独立 worktree + 总控 cherry-pick + 独立 Reviewer 模式下完成，这个模式值得继续保留。

批准 Gate / 决定业务参数

批准 Closure Plan

代码 + tests + artifacts

代码 + tests + artifacts

PASS / CONDITIONS / FAIL

拒绝

批准 P1-A

否

是

禁止绕过

你 / 项目所有者

Codex 总控 Orchestrator

先提交 Closure GAP Analysis

Data Admission Agent

Platform / Paper Hardening Agent

Integration Candidate

Independent Reviewer
只读攻击与证据核验

P1-A Closure Gate Review

修复后重新 Gate

是否明确 APPROVE_P1B?

STOP
保持 P1-B BLOCKED

P1-B Research Intelligence

真实交易



显示代码
这里有一个非常重要的架构边界：P1-A 的 Data Admission 不等于“把所有真实数据都抓进来”。 当前真实行情 slice 被正确标成 QUARANTINED / NON_TRADEABLE，就是好现象，因为源端没有足够的 available_at 和许可证明。错误做法反而是为了让 Research Agent 尽快跑起来，把 retrieved_at 当 available_at，或把“网页能打开”理解成“可以作为历史可交易数据集使用”。P1-A 报告已经明确拒绝了这两种捷径。

正式交接本来也要求 raw 数据、Point-in-Time、版本与来源优先于研究层，且“数据异常时 fail-closed”。

Gate 决策原则与禁止降级项
我建议你以后审核 Codex 的 Gate，不再只看“测试通过多少项”，而是看四种证据是否同时成立：

第一层，代码证据。 有 commit/tag/source-tree hash。

第二层，数据证据。 有 source/raw/hash/time/version/lineage。

第三层，行为证据。 有 Golden Tests 和 adversarial tests，证明错误输入确实被拒绝，而不仅是正常输入能跑通。

第四层，独立证据。 Reviewer 不修改实现，只做攻击性复核。

P1-A 这次做得比较成熟的地方，恰恰是这四层都开始出现了。例如 deterministic replay 不只是说“运行两次一样”，还固定了 Snapshot、Feature、Account fixture、CostProfile、Rule、Calendar、Security 与实现代码版本，并对 cost version、rule version、source byte 做 mutation，验证 result hash 随之改变；这比简单断言“同一随机种子结果一致”严格得多。

相反，以下东西绝不能成为 P1-B 放行理由：

“209/210 看起来已经 99% 完成。”
“真实行情已经抓到了两天，所以可以研究。”
“费用以后再填，现在先让 AI 推荐。”
“Research 不下单，所以 PIT 松一点没事。”
“真实 PostgreSQL 以后再说，因此所有并发都算通过。”
“Micro-Ladder multiple=2 测试不错，所以生产直接设2。”
“SELL reservation 现在比较保守，就先当券商规则。”
“DAILY MAE/MFE 已实现，所以可以预测未来最大回撤。”
“Experiment B 净利润为正，所以策略有效。”
“V5 能重放，所以旧策略有效。”
P1-A 报告自身已经很克制地说明：Experiment A/B 是工程实验，不是策略回测收益或 OOS 结果；MAE/MFE 目前是 retrospective DAILY_APPROXIMATION；旧 V5 replay 只证明保存输入和账本可重放，并不能证明策略盈利或完整 PIT。

这一点非常重要，因为你的最终系统应该避免重新掉回旧项目最大的坑：工程真实性、研究质量和投资有效性是三个不同命题。 原历史验证总结中，V5 前14日4轮交易只有1轮小赚、3轮亏损，净结果为 -2.0886%，已经很好地说明“能调用模型、能冻结、能核账”不等于“投资策略有效”。

因此 P1-B 才应该真正负责后面那件事：

在已经可信的数据与经济基座上，验证“什么研究因子、什么板块/公司结构、什么时机、什么价格、什么费用后 Edge”是否真的具有预测和交易价值。

而不是继续补底层账本。

P1-A 完成结论模板
下面这段建议直接要求 Codex 固定作为所有 P1-A Closure / 后续 Gate 的最终结论格式。只能三选一，不允许写“基本通过”“大体完成”“原则上可以”。

text
复制
# P1-A Gate 最终结论

Gate：
P1-A / P1-A CONDITIONAL CLOSURE

评审日期：
YYYY-MM-DD

评审 commit：
<commit_id>

评审 tag：
<tag_or_NA>

Source Tree Hash：
<hash>

Test Run ID：
<run_id>

Independent Reviewer Report：
<artifact_id/hash>

用户批准状态：
PENDING / APPROVED / REJECTED


==================================================
结论格式 A：PASS
==================================================

结论：PASS

含义：

P1-A 范围内所有必须条件已经满足；
未发现阻止下一阶段研究工程开发的 P0/P1 blocker。

注意：

PASS 不等于批准 P1-B。
PASS 不等于批准真实交易。
PASS 不等于真实账户参数已配置。

关键证据：

- Git / clean reproduction：
  <证据>

- Contracts：
  <版本/hash>

- Migrations：
  <ids/checksums>

- Golden Tests：
  <pass/fail/skip>

- Data Admission：
  <证据>

- PIT / Snapshot：
  <证据>

- Cost Engine：
  <证据>

- Ledger / Replay：
  <证据>

- CORE_40：
  <证据>

- MAE/MFE：
  <证据>

- Cost Attribution：
  <证据>

- Friction Stress：
  <证据>

- Independent Reviewer：
  <证据>

- UNSET_REQUIRED：
  <inventory/hash>

- productionGate：
  false

未决问题：

P1-B deferred：
- <item>

P2 deferred：
- <item>

PROD_ONLY：
- <item>

阻止进入下一阶段的条件：

无 P1-A 工程 blocker。

但：

必须由用户显式给出
APPROVE_P1B

否则保持停止。

建议动作：

P0：
- 等待用户 Gate Review。

P1：
- 用户批准后才建立 P1-B Agent Plan。

P2：
- <deferred infrastructure>

最终状态：

P1-A = PASS
P1-B = BLOCKED_PENDING_HUMAN_APPROVAL
PRODUCTION = BLOCKED


==================================================
结论格式 B：PASS_WITH_CONDITIONS
==================================================

结论：PASS_WITH_CONDITIONS

含义：

P1-A 核心机制已经成立，
但仍存在明确条件项。

必须区分：

MUST_CLOSE_BEFORE_P1B
MAY_DEFER_TO_P1B
MAY_DEFER_TO_P2
PROD_ONLY_BLOCKER
ACCEPTED_KNOWN_LIMITATION

关键证据：

- Git / clean reproduction：
  <证据>

- Contracts：
  <证据>

- Migrations：
  <证据>

- Golden Tests：
  <证据>

- Data/PIT：
  <证据>

- Cost/Ledger：
  <证据>

- Deterministic Replay：
  <证据>

- Stress Test：
  <证据>

- Reviewer：
  <证据>

条件项：

MUST_CLOSE_BEFORE_P1B：

1. <问题>
   风险：
   <risk>
   修复：
   <action>
   优先级：P0
   验收：
   <test/artifact>

2. <问题>
   ...

MAY_DEFER_TO_P1B：

- <item>

MAY_DEFER_TO_P2：

- <item>

PROD_ONLY_BLOCKER：

- <item>

ACCEPTED_KNOWN_LIMITATION：

- <item>

未决 UNSET_REQUIRED：

- <machine inventory ref/hash>

阻止进入下一阶段的条件：

只要任一 MUST_CLOSE_BEFORE_P1B 未解决：

P1-B = BLOCKED

即使全部解决：

仍必须等待用户显式
APPROVE_P1B。

建议修复动作：

P0：
- <必须修>

P1：
- <可在 P1-B 内处理>

P2：
- <生产/部署后置>

最终状态：

P1-A = PASS_WITH_CONDITIONS
P1-B = BLOCKED
PRODUCTION = BLOCKED


==================================================
结论格式 C：FAIL
==================================================

结论：FAIL

含义：

发现 P1-A 核心不变量失效，
不能把当前 candidate 作为下一阶段可信基础。

关键失败证据：

1. <failure>
   artifact：
   <id/hash>

2. <failure>
   artifact：
   <id/hash>

失败类型：

[ ] PIT / future leakage
[ ] Snapshot lineage
[ ] raw / adjusted contamination
[ ] corporate-action leakage
[ ] financial revision leakage
[ ] security identity corruption
[ ] fee calculation
[ ] money rounding
[ ] cash double spending
[ ] T+1 bypass
[ ] partial fill reconciliation
[ ] strategy namespace contamination
[ ] replay non-determinism
[ ] audit mutability
[ ] approval bypass
[ ] productionGate bypass
[ ] UNSET_REQUIRED fail-open
[ ] legacy contamination
[ ] other: __________

影响：

- 对回测：
  <impact>

- 对研究：
  <impact>

- 对 Paper：
  <impact>

- 对生产：
  <impact>

必须修复：

P0：

1. <repair>
   owner：
   <agent>
   tests：
   <tests>
   Definition of Done：
   <DoD>

2. ...

禁止事项：

- 不得启动 P1-B
- 不得启动 Research Agent
- 不得启动 GUI 主体开发
- 不得启动 EVENT_3
- 不得接真实 broker
- 不得开放 productionGate
- 不得通过修改测试预期掩盖失败

重新 Gate 条件：

<明确列出>

最终状态：

P1-A = FAIL
P1-B = BLOCKED
PRODUCTION = BLOCKED
REMEDIATION_REQUIRED = TRUE
以你现在这份 P1-A 报告为依据，我会把当前状态保持为 PASS_WITH_CONDITIONS，而不是直接改成 PASS。 原因不是核心工程质量不够，恰恰相反，目前 deterministic foundation 已经相当完整；真正需要人工确认的是“P1-B 到底允许消费什么级别的数据”。P1-A 报告自己也明确建议：先确认真实 source admission 边界，再考虑只消费已验证 snapshot 的 Research Store / BrainPacket / MANUAL adapter；不能把 quarantined evidence 导入可交易研究。

所以现在发给 Codex 的关键词应该从：

“开始 P1-A”

变成：

“P1-A 已完成。先做 PASS_WITH_CONDITIONS 条件闭环和 P1B_READINESS_GATE；没有我的 APPROVE_P1B，完成后必须停。”

这一步走对以后，下一阶段才真正轮到你最关心的核心：ResearchCard、Quality/Timing 双评分、S/A/B/C/X、A→S 晋级、净 Edge、20–40 日风险路径、ChatGPT/Deep Research 决策接口。但它们现在不应该被 Codex 偷跑。

