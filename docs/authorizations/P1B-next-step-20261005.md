



P1-B 启动决策与 Codex 下一步执行方案
Executive Summary
基于你已经完成的 P0 → P1-A → Conditional Closure 全链路，我的判断是：

现在可以发送 APPROVE_P1B，但必须把它定义成“有边界的 P1-B 工程启动授权”，绝不能理解成“允许真实股票研究/AI 选股/实盘交易”。

原因很明确。当前 Closure Gate 是 PASS_WITH_CONDITIONS；P1B_READINESS_GATE = PASS，但这个 PASS 只覆盖 fixture-only、MANUAL_EXPORT / PAPER 的研究输入输出边界；REAL_DATA_ADMISSION_GATE = BLOCKED；productionGate=false；真实账户、真实券商费率、真实风险参数仍保持 UNSET_REQUIRED。Closure 已经证明 ResearchDraft 不能产生订单，LLM 不能伪造人工批准，Synthetic 数据不能直接晋升为真实研究数据，且独立 Reviewer 的攻击集已经通过。

所以当前不是继续修 P1-A，也不是直接做 GUI，更不是去接真实行情后马上开始荐股。正确下一步是进入一个受限的 P1-B0：Research Semantics & Research Pipeline 阶段，把“什么叫好公司、什么叫好时机、S/A/B/C/X 到底是什么意思、证据如何分级、ResearchCard 如何形成、什么时候允许进入 Candidate”先变成机器可验证合同。正式交接本来就要求研究层和执行层分开，并把 S/A/B/C/X、ResearchCard、BrainPacket、费用后 Edge 和状态机作为核心 V1 能力。

我建议从现在开始把两个批准命令永久分开：

text
复制
APPROVE_P1B
代表：

批准 P1-B 的研究语义、fixture-only 研究管线、数据准入准备、ResearchCard/Assessment 工程。

而未来真正允许拿真实 A 股历史数据 + ChatGPT/Deep Research 做研究试运行时，再使用：

text
复制
APPROVE_P1B_RESEARCH_PILOT
这两个授权不要合并。这样以后 Codex 不会因为看到 APPROVE_P1B 就一路自动做到真实股票研究甚至信号生产。

还有一个重要的状态一致性提示：你这轮上传材料中存在一份更靠后的《P1-B DATA/SEMANTICS GATE REVIEW》，其中已经出现 ResearchAssessment、十维语义、S/A/B/C/X 精确定义以及有限 SSE 日历真实参考准入，并明确写着“完整 P1-B1 股票历史研究 MVP = PARTIAL/BLOCKED，Research Pilot = BLOCKED”。如果这份文件确实代表 Codex 当前最新 repo 状态，那么就不要重复发送本文的 APPROVE_P1B 启动命令，而应直接进入后续真实股票数据准入阶段；如果当前实际停点仍是你截图中的 Closure Gate，那么下面的指令就是现在应该发送的。

当前状态与放行判断
当前工程状态实际上相当健康。P0 已经完成新 repo、合同、schema、ADR、legacy manifest、Golden Tests 和生产阻断；V5 被保留为 legacy experiment，没有改名冒充 CORE_40，真实配置保持 UNSET_REQUIRED。

P1-A 随后完成了确定性数据/费用/账本/Paper 基础，包括 PIT、防未来泄漏、raw/adjusted 隔离、财报修订、T+1、共享现金、费用归因、partial fill、确定性 replay、MAE/MFE 基础指标与 Micro-Ladder Filter；但当时明确没有把这些 synthetic / reference 能力冒充真实研究准备完成。

Closure 又进一步补上了最关键的一道隔离墙：

Synthetic Source → DataEnvelope → SnapshotManifest → AdmissionPolicy → AdmissionReceipt → sanitized BrainPacket → MANUAL_EXPORT → ResearchDraft

并证明 ResearchDraft 为 NON_TRADEABLE，不能越级成为 Candidate、Signal、Approval 或 OrderIntent。最终 clean 检查为 258 项、257 PASS、0 FAIL、1 optional SKIP，25 类 Golden 不变量没有回退，新 Reviewer 的 22 类攻击全部通过。

因此我给当前状态的定义是：

Gate / 字段	当前必须保持的值	P1-B 中能否改变
Closure Gate	PASS_WITH_CONDITIONS	不回写历史 Gate
P1B_READINESS_GATE	PASS，仅 fixture-only	可据新 Gate 扩展，但不得静默改含义
REAL_DATA_ADMISSION_GATE	BLOCKED	只有独立数据准入证据后才能局部解除
productionGate	false	P1-B 禁止改变
AccountProfile 真实字段	UNSET_REQUIRED	未有真实证据前禁止填
真实佣金/最低佣金	UNSET_REQUIRED	未核实券商资料前禁止猜
真实风险限额	UNSET_REQUIRED	用户未明确决定前禁止猜
真实 sizing	BLOCKED	P1-B0 禁止
真实 Net Edge	BLOCKED	成本/账户未知时禁止
Broker capability	不存在/不可见	P1-B 禁止建立
Research consumer	MANUAL_EXPORT	当前保持
LLM 权限	Research only	不得成为 HUMAN_USER
ResearchDraft	can_produce_order=false	P1-B0 必须保持

这正是一个适合进入 Research Intelligence 定义阶段，但不适合进入真实交易阶段的状态。早期 GAP Analysis 已经明确指出，研究入口和真实数据准入是独立问题，不能因为 snapshot 能通过完整性校验，就把许可、PIT、用途、freshness 一起视为已证明。

工程上继续坚持 frozen baseline、独立 Reviewer、Golden Tests、版本化合同与不可静默修改是合理的；这与 NIST SSDF 强调将安全、验证、变更管理和可复现交付纳入开发生命周期的方向一致。

你现在应采取的动作
我不建议你现在去填真实账户金额、佣金或者最大回撤，也不建议开始设计完整 GUI。你当前最重要的职责其实只有两个：批准 P1-B0 的边界，以及在下一个 Gate 阻止 Codex 偷偷把“研究评分”升级成“真实买入建议”。

动作	负责人	优先级	验收标准	预计完成时间
核对 Closure 最终 commit/tag、工作树 clean、Gate JSON	Codex 总控 + 你	P0	与 Closure Review 中 commit/tag/hash 一致；git status clean；旧 tag 未变	15–30 分钟
明确 APPROVE_P1B 仅等于 P1-B0 工程授权	你	P0	Codex 回执中明确“不授权真实研究、不授权交易”	立即
冻结 P1-B 语义和合同边界	Codex 总控	P0	W1 文档明确 Quality/Timing/Cost/Tradeability 分离；旧合同不原地改	1–2 小时
建 ResearchAssessment / ResearchCard 研究语义层	Research 子 agent	P0	Synthetic fixture 能生成结构化 assessment；真实 symbol/account 不参与	2–4 小时
精确定义 S/A/B/C/X	Research 子 agent + 总控	P0	每级都有必要条件、Hard Block、最大允许动作；S ≠ 自动买入	W2 内
建 Evidence Trust Model	Data/Research agent	P0	Local admitted evidence 与 cloud-discovered lead 分离；未认证证据不能解除 Hard Block	W2–W3
建真实数据 Source Inventory / License / PIT Matrix	Data agent	P0	每 source 有用途、许可、时钟、coverage、状态；UNKNOWN 必须 fail closed	2–6 小时
保持 Cost-before-Candidate	Cost/Research integration	P0	缺真实 CostProfile 时不能产生真实 Account Suitability / Net Edge / Tradeability	W2–W3
建 fixture-only Research E2E	Codex 总控	P0	BrainPacket → Research result → ResearchDraft → Assessment，可确定性 replay，零订单写入	W3 前
做 outcome leakage 攻击	Independent Reviewer	P0	MAE/MFE、future price、future financial revision 不得进入 research input	W4
完整 Golden regression	总控	P0	P0/P1-A/Closure 的所有关键不变量无回退，0 非预期 FAIL	W4
提交 P1-B Gate Review	总控	P0	下文“准备清单”全部逐项给状态和证据	W4
决定是否开放真实 Research Pilot	你	P0	只有满足后述真实数据准入条件才发送 APPROVE_P1B_RESEARCH_PILOT	Gate 后
GUI 主体	暂缓	P2	ResearchCard / Candidate / Signal semantics 稳定后再做	后续
Broker / Production	暂缓	禁止	productionGate=false	后续

这里尤其不要让 Codex因为现在已有 257 个 PASS 就把测试数量当进度百分比。当前通过的是工程不变量，不是策略有效性。旧实验本身也明确证明过：代码能跑、研究文字完整、评分高，不等于投资有效性；V5 只有 4 轮完整交易，净结果仍为负，远不足以证明策略。

当项目以后迁到远程 GitHub 时，再把 main 设为 protected branch，至少要求 status checks 和 review 后才能 merge；GitHub 官方 branch protection 本身支持 required reviews、required status checks、限制 push、禁止绕过等能力。

可直接发给 Codex 的下一步指令
下面这版我建议直接复制粘贴。它不是“继续随便开发 P1-B”，而是一个受限授权。

text
复制
APPROVE_P1B

我确认 P1-A Conditional Closure Gate：

Closure Gate = PASS_WITH_CONDITIONS
P1B_READINESS_GATE = PASS
scope = fixture-only MANUAL_EXPORT / PAPER
REAL_DATA_ADMISSION_GATE = BLOCKED
productionGate = false

本次 APPROVE_P1B 的含义严格限定为：

P1-B0 — Research Semantics / Research Pipeline / Data Admission Preparation

它不等于：

- APPROVE_REAL_DATA_RESEARCH
- APPROVE_RESEARCH_PILOT
- APPROVE_LIVE_SIGNAL
- APPROVE_EVENT_3
- APPROVE_GUI
- APPROVE_BROKER
- APPROVE_PRODUCTION

真实股票研究、真实账户 suitability、真实 Net Edge、
真实 sizing、真实 Signal、真实订单继续 BLOCKED。

所有未确认真实参数继续：

UNSET_REQUIRED

包括但不限于：

- actual account capital
- per-position budget
- account risk limits
- sector exposure limits
- drawdown limits
- real broker commission
- real minimum commission
- exchange/other broker-specific fee inclusion
- effective fee period
- real slippage
- production sizing parameters

不得从旧 V5、5000/6000/10000 元实验、
历史研究报告或 synthetic fixture 自动继承。

productionGate 必须继续保持 false。

MANUAL_EXPORT 必须继续是唯一允许的 Brain 边界。

==================================================
启动前 Preconditions
==================================================

总控首先验证：

1. 当前 HEAD 与 P1-A Closure 最终交付一致。
2. Closure tag / archive / bundle 可恢复。
3. Git worktree clean。
4. P1B_READINESS_GATE = PASS。
5. REAL_DATA_ADMISSION_GATE = BLOCKED。
6. productionGate = false。
7. 真实 Account / Cost / Risk 配置仍为 UNSET_REQUIRED。
8. 旧 P0 / P1-A / Closure contracts、migrations、tags 原字节未修改。
9. 现有 Golden baseline 可复跑。
10. Research consumer 无 DB/raw/broker credential/capability。

任一项不满足：
停止并报告。
不得自行修历史对象来满足前置条件。

==================================================
W1 — Research Semantics & Contract Freeze
==================================================

本阶段由 Codex 总控负责，不允许子 agent 自行决定架构。

先做 Contract-Fit Analysis，
再决定是否需要新增 sidecar contract，
不得直接修改冻结的 ResearchCard 1.0 / BrainPacket / Closure contract。

必须冻结以下语义：

A. 十个独立研究维度

1. Company / Fundamental Quality
2. Sector Quality
3. Catalyst
4. Evidence Quality
5. Valuation
6. Timing
7. Risk
8. Cost
9. Account Suitability
10. Tradeability

这些维度不得压成一个未经验证的“总分”。

尤其：

Company Quality != Timing
Company Quality != Tradeability
Sector Quality != Buy Now
High Score != Probability
High Score != Expected Return
Research Grade != Approval

B. S/A/B/C/X 精确定义

建议目标语义：

S：
研究、证据、时点、成本/Edge、账户适用性和所有 Hard Block
均已满足的最高 actionability 状态。

但即使 S：
最大动作只能是 REQUEST_REVIEW，
不得等于 BUY / APPROVED / ORDER。

A：
研究质量高，
但价格、Timing、Trigger、Cost、Account Suitability、
Evidence 中至少一项仍未满足。
最大动作：
WATCH / WAIT_FOR_TRIGGER。

B：
存在研究逻辑或催化，
但重要证据、赔率、趋势或风险条件存在明显缺口。
最大动作：
NO_ACTIVE_TRADE。

C：
只具有研究/观察价值。
最大动作：
RESEARCH_ONLY。

X：
存在已经核验的 Hard Block。
最大动作：
BLOCKED。

UNSET_REQUIRED：
不是 B/C/X 的评分等级，
表示必须核验的事实未知。
任何必要事实为 UNSET_REQUIRED 时，
不得伪称 S / TRADEABLE / REAL_SUITABLE。

Hard Block 必须优先于所有 score。

C. Probability

本阶段禁止：

- 把 score 映射成胜率
- 把 S/A/B/C 映射成概率
- 生成伪 calibrated probability
- 声称未来20/40日上涨概率已验证

没有 calibration dataset / OOS evidence 时：
probability = UNSET_REQUIRED / UNCALIBRATED。

D. Evidence Trust

必须区分：

ADMITTED_LOCAL_EVIDENCE

与：

CLOUD_DISCOVERED_EVIDENCE

ChatGPT / Deep Research 返回的新 URL、citation、claim、
新闻、数字和反证首先只能是：

PENDING_VERIFICATION

不能因为模型给了链接就：

- 解除 Hard Block
- 升级 S
- 设置 TRADEABLE
- 设置真实 sizing
- 生成 Signal

必须经：

local capture
→ original bytes/hash
→ source identity
→ timestamps
→ license/purpose
→ normalization/DQ
→ Snapshot
→ AdmissionPolicy
→ AdmissionReceipt

后才能升级为 trusted local evidence。

W1 完成后提交：

P1B-W1-FREEZE

包括：

- Contract Fit Analysis
- semantics matrix
- S/A/B/C/X matrix
- Hard Block registry proposal
- Evidence trust model
- score/probability boundary
- reason codes
- hash/version/invalidation protocol
- owned-path matrix

完成 W1 Freeze 前，
子 agent 不得开始业务实现。

==================================================
W2 — Fixture-Only Research Intelligence
==================================================

启动 Research/Semantics Agent。

目标：

证明研究系统可以在完全 synthetic、
无真实股票、无真实账户的环境中形成正确结构，
而不是证明策略有效。

实现：

1. ResearchAssessment 或等价 sidecar
2. ResearchCard compatibility adapter
3. Quality / Timing 分离
4. Valuation 独立维度
5. Risk 独立维度
6. Cost / AccountSuitability / Tradeability 独立维度
7. Hard Block precedence
8. invalidation / counter-evidence
9. evidence refs
10. deterministic assessment hash

必须包含 synthetic 反例：

CASE A：
Company Quality 极高，
Timing GAP
→ 不得成为 S。

CASE B：
Company + Sector + Catalyst 高，
Cost UNSET_REQUIRED
→ 不得 Real Tradeable。

CASE C：
研究质量高，
Account Suitability UNSET_REQUIRED
→ 不得 Real Suitable。

CASE D：
模型说 BUY NOW，
但 Hard Block 存在
→ BLOCKED。

CASE E：
模型提供新 citation，
但未 local admission
→ PENDING_VERIFICATION。

CASE F：
只改善 Company Quality，
Timing 未改变
→ 不得自动 A→S。

CASE G：
Synthetic fixture 全部通过
→ 可以形成 synthetic S template，
但 max_action 仍只能 REQUEST_REVIEW。

禁止真实 symbol / account / real sizing。

==================================================
W3 — Research Pipeline + Data Admission Preparation
==================================================

启动 Data Admission / Research Integration Agent。

本阶段构建：

BrainPacket
→ MANUAL_EXPORT
→ simulated external research
→ ResearchDraft
→ ResearchAssessment
→ ResearchCard/sidecar
→ NON_TRADEABLE research state

要求 deterministic replay。

同时完成真实数据进入未来 Research Pilot
所需的数据工程准备：

1. Source Inventory
2. Source / License / Purpose Matrix
3. PIT Clock Matrix
4. Coverage Matrix
5. SecurityIdentity requirements
6. Calendar requirements
7. bars_1d requirements
8. corporate-action requirements
9. adjustment requirements
10. financial revision requirements
11. industry membership PIT requirements
12. source revocation/invalidation semantics

严格区分：

VERIFIED
和
ADMITTED

VERIFIED 仅证明完整性/闭包。

ADMITTED 才证明：
可信来源
+ 时间语义
+ 明确用途
+ coverage
+ policy
+ receipt。

不能：

FROZEN → ADMITTED
DQ_PASS → ADMITTED
PUBLIC_URL → ADMITTED
OFFICIAL-looking domain → ADMITTED
Synthetic → Observed
Synthetic → Real Research

若本阶段能够证明某一个极窄的真实 reference scope，
允许作为 LOCAL_REFERENCE_ONLY 工程正向样例。

例如 calendar reference。

但：

不得因此把：

REAL_DATA_ADMISSION_GATE

全局改为 PASS。

真实 A 股历史 bars / financial / action /
industry membership 未分别 admission 前，
不得用于真实股票 Research Pilot。

==================================================
Cost-Before-Candidate
==================================================

沿用现有 Cost Engine。

流程必须是：

Research
→ Data/Evidence validity
→ Cost
→ Account Suitability
→ Candidate Eligibility

而不是：

Research
→ Candidate
→ 以后再算手续费。

真实 CostProfile 为 UNSET_REQUIRED 时：

禁止产生：

REAL_NET_EDGE
REAL_ACCOUNT_SUITABLE
REAL_SIZING
REAL_TRADEABLE

synthetic CostProfile 只能用于 TEST/FIXTURE。

不得因为股票“很好”
绕过交易成本。

==================================================
Outcome Leakage
==================================================

Research input 禁止包含：

- future MAE
- future MFE
- future return
- future drawdown
- future target hit
- future stop hit
- future financial revision
- future corporate action knowledge
- backtest outcome label
- hidden future trace

MAE/MFE 当前只能作为：

historical evaluation / calibration target

不得作为同一历史决策时点的输入。

==================================================
LLM / Human / Execution Boundary
==================================================

ChatGPT / Deep Research 返回：

BUY
SELL
APPROVE
HUMAN_USER
OrderIntent
quantity
price

均视为 untrusted research content。

不得写：

Approval
OrderIntent
Order
Fill
Ledger

LLM 永远不能 authenticate HUMAN_USER。

ResearchDraft：

can_produce_order = false

tradeable = false

必须保持。

productionGate=false。

禁止创建 broker transport、
broker credentials、
broker capability discovery。

==================================================
W4 — Integration / Golden / Independent Review
==================================================

总控完成：

1. 新 candidate freeze
2. clean checkout
3. clean dependency install
4. full check
5. deterministic fixture replay
6. contract/schema validation
7. old Golden regression
8. new P1-B Golden tests
9. artifact/hash/index
10. release/tag/bundle/archive

随后启动全新的 Independent Reviewer。

Reviewer 只读，不修改：

- code
- contract
- schema
- expected test output
- Gate status

重点攻击：

1. high-quality → auto S
2. S → auto BUY
3. score → probability
4. synthetic → observed
5. synthetic → real research
6. cloud citation → trusted evidence
7. cloud claim → HardBlock removal
8. fake available_at
9. stale evidence reuse
10. revoked receipt reuse
11. coverage mismatch
12. purpose mismatch
13. namespace crossover
14. future MAE/MFE leakage
15. future financial revision leakage
16. future corporate-action leakage
17. account UNSET bypass
18. cost UNSET bypass
19. Candidate-before-Cost
20. LLM fake HUMAN approval
21. ResearchDraft → OrderIntent
22. productionGate bypass
23. broker capability leakage
24. secret/raw path leakage
25. arbitrary payload injection
26. old approval/result reuse after version change

任一安全类攻击成功：

P1-B Gate = FAIL。

==================================================
P1-B Gate Review 必须逐条提交
==================================================

最终报告至少包含：

[01] Current commit / tag / source-tree hash
[02] Frozen contract/release matrix
[03] Contract Fit Analysis
[04] Research semantics specification
[05] Ten-dimension matrix
[06] Quality-vs-Timing proof
[07] S/A/B/C/X exact semantics
[08] Hard Block registry
[09] Probability/calibration status
[10] Evidence trust classes
[11] Cloud-discovered evidence workflow
[12] ResearchAssessment / ResearchCard relationship
[13] BrainPacket / ResearchDraft E2E
[14] MANUAL_EXPORT isolation proof
[15] Source inventory
[16] License / Purpose matrix
[17] PIT clock matrix
[18] Coverage matrix
[19] Data admission matrix
[20] Cost-before-Candidate proof
[21] Account/Cost UNSET blocking proof
[22] Outcome leakage tests
[23] Namespace isolation tests
[24] Deterministic replay results
[25] Golden regression results
[26] Independent Reviewer findings
[27] Remaining C12-C22 status
[28] Remaining technical debt
[29] REAL_DATA_ADMISSION_GATE status
[30] productionGate status
[31] remaining UNSET_REQUIRED inventory
[32] Explicit statement:
     whether REAL STOCK RESEARCH is ready
[33] Explicit statement:
     whether Research Pilot is ready
[34] Explicit statement:
     whether any path can produce Signal/Order
[35] Recommendation for next Gate

Gate conclusion只能：

PASS
PASS_WITH_CONDITIONS
FAIL

==================================================
本阶段禁止事项
==================================================

禁止：

- 真实荐股
- 真实股票 S/A/B/C/X
- 真实股票 ResearchCard
- 真实股票 Signal
- 真实账户 sizing
- 真实 Net Edge
- 填猜测佣金
- 填猜测本金
- 填猜测风险参数
- EVENT_3 implementation
- GUI 主体开发
- watcher 实盘化
- broker integration
- credentials
- 自动下单
- productionGate=true
- 修改 legacy seal
- 恢复 V5
- 用历史 outcome 调当前评分
- 为测试全绿降低 Hard Block
- 为提高 S 数量降低标准
- 让评分变成概率
- 让 S 等于 BUY

==================================================
停止条件
==================================================

W4 和 Independent Review 完成后停止。

不得自动进入真实股票研究。

即使：

P1-B Gate = PASS

也必须继续等待新的人工指令：

APPROVE_P1B_RESEARCH_PILOT

在我发送该命令之前：

REAL STOCK RESEARCH = BLOCKED
REAL SIGNAL = BLOCKED
REAL ORDER = BLOCKED
PRODUCTION = BLOCKED
我认为这条指令比简单一句 APPROVE_P1B 重要得多，因为它解决了以后最容易出现的语义污染：

“P1-B 被批准”究竟是批准研究基础设施，还是批准开始拿真实股票做投资判断？

现在我们把它明确规定为前者。

风险清单与责任分配
下面是我认为 P1-B 最值得防的风险。多数风险并不是“代码会不会报错”，而是系统表面运行正常，但语义已经偷偷错了。

风险场景	严重度	典型后果	缓解措施	责任人
APPROVE_P1B 被解释成“允许真实荐股”	极高	Synthetic pipeline 被直接用于真股票	明确 P1-B0 / Research Pilot 两级批准	你 + 总控
Synthetic 被重新打标签为 OBSERVED	极高	虚构数据进入真实研究	AdmissionReceipt 必须绑定 source bytes、scope、purpose、policy	Data Agent
available_at 被抓取时间/发布日期猜出来	极高	历史回测出现未来函数	四时钟 fail-closed；未知即 UNKNOWN	Data Agent
“官网 URL”被等同于许可和可信证据	高	未授权数据进入云端/模型	Source License/Purpose Matrix；PUBLIC ≠ ADMITTED	Data Agent
Company Quality 与 Timing 合并	高	“好公司”自动变成“现在买”	十维独立、Quality/Timing 分离 Golden	Research Agent
S 被解释成“无脑买”	极高	绕开 Signal/Approval	S 最大动作只允许 REQUEST_REVIEW	总控
Score 被解释成胜率	高	85分→85%概率之类伪统计	无 calibration 时 probability=UNCALIBRATED	Research Agent
真实费用未知却算 Net Edge	极高	重新出现你最反感的“手续费吞收益”	UNSET_REQUIRED 时拒绝 Real Net Edge / Suitability	Cost Agent
LLM 返回 APPROVE / BUY 被解析成授权	极高	AI 越权生成交易链	ResearchDraft 永远 non-executable；HUMAN_USER 独立认证	Platform Agent
Cloud citation 被直接当 trusted evidence	高	幻觉/错误资料升级研究等级	新证据只做 lead，必须 local capture + admission	Data + Research
Future MAE/MFE 泄漏进历史研究输入	极高	回测看答案	outcome 字段独立 namespace；Reviewer 定向攻击	Reviewer
receipt 撤销后仍能重用	高	已失效数据继续消费	每次消费重新验证 receipt + revocation	Data Agent
contract/version 改了但旧卡仍有效	高	旧结论跨版本继续交易	content hash + version invalidation	总控
Core/Event/Research namespace 串线	极高	短线状态干扰中线仓位	namespace hard isolation + cross-contamination tests	总控
GUI 先于语义稳定	中高	前端自己形成第二套业务规则	GUI 后置，只消费 API/contract	GUI Agent
PGlite 测试结果被当成真实 PostgreSQL 并发证明	中高	多连接后出现现金双花/状态竞争	P2 做真实 PostgreSQL concurrency / fault injection	Platform Agent

最后一个问题目前可以延期，但以后进入真实 server 时必须重新验收。PostgreSQL 当前文档明确指出 READ COMMITTED 是默认隔离级别，同一事务内不同语句可能看到不同的并发提交状态；若业务依赖严格串行化约束，必须选择适当的 isolation/locking 并处理 serialization failure，而不能把 PGlite 单进程测试自动外推为多进程生产安全。

另外，当前 Closure Plan 本身已经正确指出 C23–C31 可以后移，但真实 PostgreSQL 多连接、RBAC、备份恢复、crash fault injection、SELL 退出约束、真实撮合等都不能因为 P1-B 通过而被视为完成。

时间表与 Gate 触发点
按照你现在 Codex 总控 + 子 agent 的效率，我建议不要按传统团队“几周一个 sprint”来排，而用Gate 驱动。这里给的是工程估算，不是承诺；真实数据 source 许可/PIT 认证可能显著拉长 W3。

阶段	主要工作	Codex/Agent 纯执行估算	你的介入点
启动检查	Closure commit/tag/Gate/clean tree	15–30 分钟	无需逐代码审
W1	Contract Fit + semantics freeze	1–2 小时	必须审一次 W1 Freeze
W2	Research semantics + synthetic assessment	2–4 小时	不需中途干预，除非发现业务歧义
W3	Research E2E + source/PIT/admission preparation	2–6 小时	只有真实 source 范围变化才需你决定
W4	集成、clean replay、Golden、Reviewer	2–4 小时	等最终 Gate
Owner Gate	审 P1-B Gate Review	30–90 分钟	决定 Research Pilot

如果执行顺畅，P1-B0 的工程闭环大约是 8–16 小时的 Agent 工作量，日历时间通常 1–3 天；真实 source 许可、historical available_at 或 corporate-action/financial PIT 认证不适合给固定时长，因为这些取决于来源能否提供足够证据。

10-05
10-05
10-06
10-06
10-07
10-07
10-08
10-08
10-09
Closure状态确认
发送APPROVE_P1B
审查W1 Freeze
W1 语义与合同冻结
W2 Research语义与Synthetic E2E
W3 Source/PIT/Admission准备
W4 集成与发布冻结
审查P1-B Gate
决定Research Pilot
安全与语义攻击复核
Owner
Codex总控
Research Agent
Data Agent
Independent Reviewer
A股交易系统 P1-B0 建议时间线


显示代码
真正需要你暂停 Codex 并亲自决策的触发点只有四类：

第一，Codex 想把某个 UNSET_REQUIRED 填成真实值；第二，Codex 想把某个真实 source 从 BLOCKED 升为 ADMITTED；第三，Codex 想改变 S/A/B/C/X、Hard Block、Approval 或 production boundary；第四，Codex 想扩大 MANUAL_EXPORT 为 API/DB 直连。

除此之外，合同实现、测试、fixture、hash、Golden、Reviewer 攻击都可以继续由总控自主组织。

最终判断
如果你现在截图中的 P1-A Closure Gate 确实是 repo 的当前最新状态，我建议现在就发送上面的 APPROVE_P1B。

不是再做一轮 P1-A，也不是先做 GUI，更不是先去接一堆真实行情。

下一阶段的核心任务应该从：

“系统能不能安全地接研究结果？”

转向：

“系统到底怎样表达一个高质量但未必值得现在买的股票？”

也就是正式实现：

Company Quality ≠ Timing ≠ Cost ≠ Account Suitability ≠ Tradeability

以及：

S ≠ BUY

这两条原则一旦在 P1-B 被工程化，你最开始抱怨的两个坏习惯才算真正从架构上消失：

一是“好股票就建议现在买”；二是“45.20、45.50、45.80 这种没有费用后经济意义的伪精细买点”。

Cost Engine 已经在 P1-A 给后者打了地基；P1-B 要做的是把前者彻底消灭。正式交接文档的目标本来就是“研究质量”和“当前可交易性”分层，并让费用后 Edge、20–40 日风险收益、状态机和人工确认共同决定最终行动。

而真正开始拿现实 A 股让 ChatGPT/Deep Research 研究的批准条件，我建议固定成下面这组，不再临时发挥：

P1-B Gate = PASS/PASS_WITH_CONDITIONS 且没有未关闭的研究安全 MUST；至少一个实际消费所需的真实股票数据 slice 拥有可验证的 source、许可/用途、PIT clock、coverage、Snapshot、AdmissionReceipt；真实研究所需的 Security/Calendar/Bars/Corporate Action/Financial/Industry 数据不存在关键未证明字段；MANUAL_EXPORT E2E 和 Evidence Resolution 通过；真实费用/账户未知时仍不能产出真实 Tradeability；Reviewer 的 future leakage、synthetic escalation、LLM authority、Cost bypass 全部失败关闭；productionGate=false；然后才发送：

text
复制
APPROVE_P1B_RESEARCH_PILOT
在那之前，**REAL_DATA_ADMISSION_GATE=BLOCKED、productionGate=false、真实配置 UNSET_REQUIRED、MANUAL_EXPORT 边界都继续保持。**这不是保守，而是在给以后“敢于下结论”的 AI 建一个不会靠猜测获得自信的底座。