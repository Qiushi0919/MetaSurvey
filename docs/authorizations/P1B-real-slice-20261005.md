



P1-B 真实股票数据准入准备：独立深度审查与下一步放行决策
结论
我重新把你最新贴出的 “真实股票数据准入准备审查”、此前已经完成的 P1-B DATA/SEMANTICS Gate、P1-A Closure、正式工程交接架构，以及当前能够核验的交易所/数据供应商规则放在一起审了一遍。

我的结论很明确：

这轮 Preparation 可以批准，但现在仍然不应该发送 APPROVE_P1B_RESEARCH_PILOT。

下一步应该批准一个更窄的阶段：

APPROVE_P1B_REAL_SLICE_W1

也就是：第一次真正的、有限范围的 真实股票数据准入切片。

原因不是 Codex 做得不好，恰恰相反，它这次做对了最重要的一件事：没有把“我找到了供应商文档”“schema 能校验”“网页能下载”偷换成“真实数据已经可以合法、PIT 正确地送给研究大脑”。

此前 P1-B Data/Semantics Gate 实际只把一个很窄的 SSE 日历参考范围准入，symbols=[]，真实历史股票 ADMITTED snapshot 仍然是 0；真实 security、bars、corporate actions、financial revisions、industry membership 等仍被阻断。
 P1-A Closure 证明的也只是 fixture-only 的 MANUAL_EXPORT / PAPER 研究边界，真实数据准入当时仍是 BLOCKED。

所以现在项目已经完成了：

“系统有没有能力拒绝坏数据？”

下一阶段第一次真正要回答：

“系统能不能正确接受一小块真实股票数据？”

这两者完全不同。

正式交接本来就要求云端大脑和本地数据/执行层分离，第一阶段采用 MANUAL_EXPORT，并且坚持 PIT、用途绑定、费用先行和 fail-closed，而不是为了早点跑 AI 研究去放宽来源条件。

因此我的 Gate 判断是：

Gate	我的判断
Source Preparation	PASS
Proposal / Clock 设计准备	PASS
P1-B Data/Semantics	PASS_WITH_CONDITIONS
Fixture Research Boundary	PASS
Real Stock Data Admission	尚未 PASS
Real Research Pilot	HOLD
Historical PIT Backtest	BLOCKED
Real Signal / Order	BLOCKED
Production	BLOCKED

你现在不是还要继续做一轮“准备的准备”。应该正式进入真实数据切片实现了。

为什么现在还不能直接跑真实股票 Research Pilot
最新报告里最值得注意的不是 300 项测试里有多少 PASS，而是它主动保留了四个事实。

第一，ClockEvidenceProposal 和 StockSliceProposal 目前只是 proposal schema。它们能够证明 JSON 结构合法，却不能证明里面写的 available_at 是真实的。例如，一个格式完全合法但实际虚构的历史 available_at，单纯靠 schema 根本发现不了。因此 Codex 正确地把它保持在 PROPOSED_UNVERIFIED，而不是升级成 runtime truth。

第二，完整的：

ResearchDraft → ResearchAssessment → ResearchCard

目前仍然没有作为一条统一版本链完成端到端验收。Closure 阶段证明的是：

BrainPacket → 外部返回 → NON_TRADEABLE ResearchDraft

而 P1-B0 又单独证明了 synthetic ResearchAssessment / 等级语义。它们不能因为各自通过就被口头拼成“完整研究系统已经通过”。这一点与此前 P1-B Gate 的证据状态一致。

第三，也是最重要的：真实股票 admitted snapshot 仍然没有形成。 当前真正被准入过的真实内容只是很窄的 SSE 日历参考，而不是股票行情/财报/公司行动切片。

第四，供应商“能提供这些字段”和“你的账户/用途有权这样使用这些字段”是两件不同的事。

例如 Tushare 的技术覆盖实际上很适合我们的工程：官方文档有未复权 A 股日线，日线页面说明数据通常在交易日 15:00–16:00 入库；有复权因子；财务报表有 ann_date、f_ann_date 和调整前/调整后报表类型；申万行业成员还有 in_date/out_date。从技术字段覆盖来说，它确实非常适合做第一版 structured provider。

但 Tushare 当前数据服务协议同时明确把数据服务许可描述为个人、不可转让、非商业、可撤销、有期限，并写明仅可用于个人查看使用。与此同时，它的网站又公开宣传本地存储、私有化存储以及 AI 对接能力。两类表述之间不能由我们的程序自行扩大解释，所以具体账号、具体产品和具体用途仍需要形成可审计的 entitlement/purpose 证据，尤其不能直接推导出“可以把原始数据上传到第三方云端模型”。

所以这一步真正应该做的是：

从 proposal 进入 real admission implementation。

而不是从 proposal 一步跳到 AI 荐股。

数据源应该怎么定
这里我建议不要寻找“一个供应商包打天下”，而是正式采用 按证据角色拆分来源 的方案。

官方来源作为事实锚
上交所、深交所/巨潮应该成为：

Authority / Evidence Anchor

尤其适合证券状态、交易日历、上市公司公告、正式披露、公司行动事实以及必要的规则证据。

上交所网站当前法律声明允许机构和个人在遵守相关规定的前提下，以非商业目的浏览和下载网站内容；但上证所信息网络有限公司同时保留正式的行情授权体系，其公开授权声明把交易所产生的证券信息纳入许可管理，并提供 Level-1、历史数据、实时数据以及面向模型验证/交易模拟的数据产品。工程上最安全的解释不是“网页公开=所有用途自由”，而是：公开网页可以成为本地非商业 reference capture；批量行情、非展示使用、转发、云端传输和正式历史数据用途应按具体产品/许可重新判断。 

这一点非常重要，因为它正好支持你现在系统里的：

purpose-bound AdmissionReceipt

不要建立一个全局：

SOURCE=SSE → everything allowed

而应该是：

SSE website announcement → LOCAL_RESEARCH_REFERENCE → allowed

和：

SSE market feed → CLOUD_MODEL_EXPORT → UNKNOWN/BLOCKED

完全可以同时存在。

巨潮资讯网目前明确说明自己是深交所信息披露官方网站、由深交所全资子公司深圳证券信息有限公司运营，同时还有独立的数据服务/API平台。它非常适合作为公告和披露事实的权威证据源，但批量 API、结构化数据及再利用同样应该走具体产品的用途审查，而不是仅凭“网站公开”推导权限。

Tushare作为第一 structured provider 候选，而不是自动 ADMITTED
我认为 Tushare 应该进入第一个真实 adapter 的实现候选名单。

不是因为我要替它背书，而是因为从工程覆盖看，它几乎正好覆盖你这次提出的八类数据中的大部分：

数据	Tushare 技术适配性
security/status	较好
calendar	有
raw daily bars	很好
corporate-action related data	有部分
adjustment factors	很好
financials/revisions	较好
announcement dates	有
industry membership	有 in/out dates

官方文档明确将 daily 定义为未复权行情，并提供 pre_close/OHLC/volume/amount；adj_factor 是 Tushare 自行生产的复权因子，官方还给出了盘前入库窗口；财务报表保存调整前报表类型，并有 ann_date/f_ann_date；行业成员接口提供纳入和剔除日期。

这意味着它很适合：

本地 structured ingestion + cross-check

但目前我不会批准：

TUSHARE → RAW → CHATGPT CLOUD

因为其当前数据服务协议对个人、非商业和使用方式有明确限制。

因此正确状态应该是：

TUSHARE = CANDIDATE_LOCAL_STRUCTURED_PROVIDER

而不是：

TUSHARE = GLOBAL_ADMITTED_SOURCE

Codex 下一阶段可以实现 adapter，并在本地检查你的账号实际拥有的产品/权限，但 Token 只存在本地 secret store；不进入 Git、BrainPacket、日志或给我。

BaoStock继续保持候选但不准入
BaoStock 官方当前确实公开提供 A 股日线、复权因子等 API/数据能力。

但在我这轮能核验到的 BaoStock 官方材料中，我没有找到足够明确、能够支撑我们定义“自动研究、长期数据库保存、云模型传输、历史回测”等用途的许可条款。因此目前 Codex 把它保持在：

UNKNOWN_LICENSE / BLOCKED

是对的。

这不是说 BaoStock 不能用，而是：

工程不能把“免费 API”自动翻译成“拥有我们需要的使用权”。

正式交易所历史数据留给真正的 Historical Gate
上证所信息网络有限公司现在有明确的历史行情/基础数据/公告数据服务，并公开说明相关数据可用于历史行情回溯、策略模型验证和交易模拟测试。

这条路线在未来做严肃历史 PIT/OOS 验证时非常干净，但现阶段没有必要为了第一张 ResearchCard 就去建设昂贵的机构级数据授权体系。

所以我的推荐是：

当前观察研究：官方披露 + 可核验 structured provider

严肃历史回测：以后单独开 Historical Data Admission Gate

不要混在一起。

我建议现在正式批准的 Clock 与真实切片
先批准 Current Observation，而不是 Historical Reconstruction
这是这次最关键的 Owner Decision。

我批准：

ROUTE = CURRENT_OBSERVED_SLICE_FIRST

不批准：

ROUTE = HISTORICAL_RECONSTRUCTION_FIRST

原因很简单。

假设今天 2026-10-05，我从一个供应商读取了一条 2026-06-01 的日线。

我们可以证明的是：

2026-10-05 我已经看到了这条 6 月 1 日数据。

但这不能证明：

2026-06-01 当天 15:07 它已经以同样版本存在。

所以它完全可以用于：

“今天研究这只股票时计算 MA60/MA250。”

但不一定可以用于：

“模拟 6 月 2 日的历史决策。”

这正是 Current Observation 和 Historical PIT 必须分开的原因。

Clock 语义现在可以正式冻结
我建议 Owner 现在直接批准下面的规则：

Clock	正式含义
business_effective_at	该事实经济/业务上开始生效的时间
event_time	业务事件发生时间，不等于抓取时间
published_at	来源正式披露时间
published_precision	EXACT / MINUTE / DATE_ONLY / UNKNOWN 等
retrieved_at	本系统真正拿到原始内容的时间
available_at	在当前信任边界内，最早能够证明系统可以使用的时间
observation_event_at	本次 collector 实际观察/捕获事件
effective_from/to	status/action/industry membership 等状态有效区间

规则则是：

有来源提供精确发布时间 → 保存精确值。

只有日期 → 保存 DATE_ONLY；不补 00:00:00。

不知道历史 first-availability → 不猜。

对于 CURRENT_OBSERVED 数据，如果没有更早的可信证据：

available_at = retrieved_at

这是保守且正确的做法。

但这个值只意味着：

“最迟从我们现在抓到时可用。”

它绝不能被倒灌成过去某天的 historical availability。

Tushare 日线文档写的是通常在 15:00–16:00 入库，但这是更新时间窗口，不是某一条记录精确的首次公开时刻，所以程序不能机械写成 available_at=15:00 或 16:00；应该以真实成功取回时间作为保守下界。

同理，Tushare 的复权因子页面说明其因子由 Tushare 自行生产并在盘前约 9:15–9:20 入库。这个时间可以作为 provider operational metadata，却不能替代公司行动的官方披露时刻。

第一批股票，我建议现在就把 scope 定死
为了不让 Codex 又回来问你“有限证券是哪几只”，我建议 Owner 直接指定三个 工程测试证券：

text
复制
CORE_40 / SSE ONLY

SSE:603993
SSE:600312
SSE:603228
也就是从你过去已经长期研究过的资源、电网、PCB 三种完全不同类型里各取一个。

这不是推荐现在买这三只。

选这三个是为了让真实数据管道面对不同业务结构，而不是选出来验证“我们以前的研究很准”。

第一批 slice 建议：

text
复制
market:
  SSE

securities:
  603993
  600312
  603228

purpose:
  LOCAL_REAL_RESEARCH_PREPARATION

strategy_namespace:
  CORE_40

bars:
  latest 320 trading sessions
  ending at latest closed session

financials:
  latest 12 quarters
  preserve predecessor/revision where available

announcements:
  latest 180 calendar days
  + every announcement later cited by research evidence

corporate_actions:
  all actions affecting the 320-session price window

adjustment_versions:
  all versions required to reconstruct used adjusted features

industry_membership:
  membership + effective history covering the slice where available

security_status:
  complete status covering the slice

calendar:
  exact exchange sessions covering the slice
这里 320 个交易日不是让系统偷偷开始历史回测，而是为了今天可以计算 MA250、趋势位置、近期波动、20–40 日风险路径等特征。

这些旧 bar 即使全部在今天才抓到，也可以用于“今天的研究”；它们只是不能因此自动获得“过去各天 PIT 已证明”的资格。

今天还有一个非常有利的天然测试条件
今天是 2026-10-05，而上交所和深交所官方都规定 10 月 1 日至 10 月 7 日休市、10 月 8 日恢复交易。

所以现在非常适合做两个快照：

Snapshot A：节日期间 Current Observation

text
复制
decision date = 2026-10-05
market_state = CLOSED
last actual trading session = 2026-09-30
系统可以研究公司、财报、公告、历史价格结构，但：

live_price = unavailable

trade_trigger = disabled

tradeability = false

然后：

Snapshot B：10 月 8 日真实复市后重新捕获。

这一次检查：

旧研究事实是否保持；

最新 bar 是否正确加入；

snapshot/hash 是否发生正确变化；

stale/closed-market flag 是否消失；

ResearchCard 是否应该生成新版本。

这实际上是一次非常好的现实版 PIT/invalidation 实验。

项目现在还剩哪些关键 Gate
从现在到“我真正开始基于你的本地数据研究三五只股票”，已经没有很多层了。

流程应该是：

text
复制
[已完成]
P0
   ↓
P1-A Deterministic Foundation
   ↓
Conditional Closure
   ↓
P1-B0 Data / Semantics
   ↓
Source Admission Preparation
   ↓

[现在]
REAL STOCK SLICE
   ↓
真实 Source/Clock/Receipt/Snapshot/BrainPacket
   +
fixture Draft→Assessment→Card 完整链
   ↓

[下一道大门]
P1-B RESEARCH PILOT
   ↓
第一次真实股票研究卡
   ↓
评分/等级/等待信号验证
   ↓

Historical PIT / OOS Calibration
   ↓
GUI + Watcher
   ↓
Forward Paper
   ↓
Production Readiness
所以，从“正式开始真实 AI 股票研究”的角度，现在还差一道真正的数据 Gate。

不是十道。

不过即使 Research Pilot 开始，我仍建议第一阶段把真实卡最大动作锁死在：

WATCH / WAIT_FOR_TRIGGER / REQUEST_REVIEW

而不是产生真实可交易 S。

因为你的真实：

AccountProfile
broker fee
minimum commission
slippage calibration
risk budget
position sizing

目前依然是 UNSET_REQUIRED。而你自己定义的 S 语义已经要求 Cost / Account Suitability / Tradeability 等都通过；不能因为公司研究很漂亮就跳过这些维度。

这是一个非常好的架构结果。

以后可能出现：

Research Quality = 93/100

Timing = PASS

Evidence = PASS

Net Edge = UNKNOWN

Account Suitability = UNKNOWN

最终等级 = A

Action = WAIT / REQUEST COST CONFIG

而不是 AI 随口把它叫做 S。

现在直接给 Codex 的指令
下面这条我建议你直接交给总控。它已经把这次 Owner Gate 需要你决定的东西都决定掉了。

text
复制
OWNER GATE DECISION

我已审阅：

- P1-B DATA/SEMANTICS Gate
- Source Preparation Review
- Source Comparison
- Stock Slice proposals
- Clock Evidence proposal
- 35-item audit

本次决定：

SOURCE_PREPARATION_GATE = APPROVED

但：

APPROVE_P1B_RESEARCH_PILOT = NOT_GRANTED

现在批准一个新的有限阶段：

APPROVE_P1B_REAL_SLICE_W1

目标是：

建立第一条真实股票数据
→ admission
→ snapshot
→ receipt
→ sanitized BrainPacket

完整证据链。

不得调用真实 Research Model。

==================================================
OWNER DECISION A
ROUTE
==================================================

批准：

CURRENT_OBSERVED_SLICE_FIRST

不批准：

HISTORICAL_RECONSTRUCTION_FIRST

当前阶段只证明：

“在当前 decision cutoff，
这些真实数据已被系统实际观察并可用于当前研究。”

不得由今天的 retrieval 推导：

“历史某个 decision cutoff 当时已经可见”。

historical_visibility_proven
默认 false，

除非存在独立、可审计的历史可得性证据。

==================================================
OWNER DECISION B
CLOCK SEMANTICS
==================================================

批准新的 clock semantic implementation。

必须区分：

business_effective_at
event_time
published_at
published_precision
available_at
retrieved_at
observation_event_at
effective_from
effective_to

规则：

1.

published_at 必须来自 source evidence。

若只有日期：

published_precision = DATE_ONLY

禁止补：

00:00:00

2.

retrieved_at 必须是 collector 实际成功取得原件的时间。

禁止 caller override。

3.

available_at 定义为：

在当前 trust boundary 内，
能够证明该数据已经可被本系统使用的最早时间。

4.

CURRENT_OBSERVED 模式：

如果没有可信的 earlier availability proof，

available_at = retrieved_at

这是 conservative observation boundary，

不是 historical first-public-time。

5.

禁止：

trade_date
business effective date
provider update window
today's retrieval

自动推导 historical available_at。

6.

任何 historical decision 使用的数据，

若 historical visibility 无法证明：

HISTORICAL_VISIBILITY_UNPROVEN

必须阻止 historical PIT admission。

==================================================
OWNER DECISION C
FIRST REAL STOCK SLICE
==================================================

限定：

strategy_namespace = CORE_40

market = SSE

securities：

SSE:603993
SSE:600312
SSE:603228

注意：

这些只是 engineering validation securities，
不是投资推荐，
不得用未来收益选择或替换。

数据范围：

bars:
  latest 320 trading sessions

financials:
  latest 12 quarters
  + predecessor/revisions where available

announcements:
  latest 180 calendar days
  + every evidence item actually cited

corporate_actions:
  all actions affecting the bar window

adjustment_versions:
  all versions/factors actually consumed

industry_membership:
  current membership
  + effective history covering window if proven

security/status:
  complete status required by consumed dates

calendar/rules:
  complete SSE sessions covering consumed dates

必须覆盖此前提案中的八类：

Security/status
Calendar/rules
Raw bars
Corporate actions
Adjustment versions
Financial revisions
Announcements
Industry membership

但：

任何类别没有达到真实 admission 要求时，
不得伪造 PASS。

允许 slice 结果：

PARTIAL_RESEARCH_ONLY

不允许通过 fallback
把缺失类别伪装成完整数据。

==================================================
OWNER DECISION D
SOURCE ROLES
==================================================

不要设计一个全局
SOURCE_X = TRUSTED
的简单白名单。

Admission 必须继续：

source
+
product
+
data_type
+
purpose
+
namespace
+
coverage
+
clock policy

逐项绑定。

来源角色：

A. SSE / SZSE / CNINFO official public documents

角色：

AUTHORITY_REFERENCE

允许在 exact evidence/policy 支持下用于：

LOCAL_NONCOMMERCIAL_REFERENCE
CURRENT_OBSERVED_RESEARCH

不自动获得：

CLOUD_RAW_EXPORT
REDISTRIBUTION
HISTORICAL_PIT
MARKET_FEED_ENTITLEMENT

资格。

B. Tushare

角色：

CANDIDATE_LOCAL_STRUCTURED_PROVIDER

允许实现 adapter。

但在真正 ADMITTED 前必须本地保存并核验：

current service agreement
actual account entitlement
actual product/API entitlement
purpose mapping
retention/storage rule
transfer rule
source/version evidence

Token：

只允许 local secret store。

禁止进入：

Git
logs
audit payload
BrainPacket
ResearchDraft
model prompt
archive bundle

不要向我或 cloud 暴露 token。

在 transfer permission 未被明确证明前：

NO_RAW_CLOUD_EXPORT = true

C. BaoStock

继续：

BLOCKED_UNKNOWN_LICENSE

直到存在可审计的使用许可证据。

D. Formal exchange/licensed historical data

保留为：

FUTURE_HISTORICAL_PROVIDER

本阶段不要求购买或接入。

==================================================
OWNER DECISION E
PURPOSE GATES
==================================================

不要再使用一个模糊的：

REAL_DATA_ADMISSION

代表所有用途。

至少在 Gate report 中分别表达：

LOCAL_REAL_RESEARCH_GATE

CLOUD_RESEARCH_EXPORT_GATE

HISTORICAL_BACKTEST_GATE

PRODUCTION_DATA_GATE

可以仍然复用现有
purpose-bound AdmissionReceipt，
不要求为了命名额外重构 schema。

当前目标：

LOCAL_REAL_RESEARCH_GATE
→ 尝试 PASS

CLOUD_RESEARCH_EXPORT_GATE
→ 仅允许经过 policy 明确许可的 sanitized projection

HISTORICAL_BACKTEST_GATE
→ BLOCKED

PRODUCTION_DATA_GATE
→ BLOCKED

redistribution
→ DENIED

==================================================
W1
FREEZE
==================================================

总控先冻结：

Clock contract version
SourceObservation version
Admission policy semantics
Receipt semantics
coverage semantics
purpose enum
new reason codes
adapter interfaces
data category mapping
projection rules
Git/version plan

shared contracts / migration
只能由总控修改。

不要让 Data Agent 自己重新定义 clock。

==================================================
W2
REAL DATA / PIT AGENT
==================================================

只启动一个有限 Data/PIT Agent。

任务：

实现 approved providers 的 adapter，
并建立三只股票的 first real slice。

不得：

调用模型
打分
选股
调参
访问 broker
读取账户资产
产生 Signal
产生 Approval
产生 OrderIntent

每一类真实数据都必须：

capture original bytes
hash original bytes
record source identity
record source/product version
record terms/purpose evidence
normalize
DQ
clock validate
coverage validate
freeze Snapshot
issue AdmissionReceipt

如果任何 required proof 不成立：

FAIL CLOSED。

==================================================
2026-10-05 HOLIDAY SNAPSHOT
==================================================

建立 Snapshot A。

项目时区：

Asia/Shanghai

capture date：

2026-10-05

必须识别：

market = CLOSED

因为 2026-10-01 through 2026-10-07
为交易所休市期。

latest trading session
必须由 admitted calendar 得出，
不能由 weekday 推算。

Snapshot A：

允许研究/数据验证，
禁止 live tradeability。

不得产生不存在的 2026-10-05 market price。

==================================================
POST-HOLIDAY SNAPSHOT
==================================================

在 2026-10-08 交易恢复后，
当真实 data source 已经实际返回新的交易日数据时，

建立 Snapshot B。

不要根据供应商声称的 update window
提前写 available_at。

使用实际 retrieval/proof。

比较：

Snapshot A
vs
Snapshot B

必须证明：

new source bytes
→ new source hash
→ new snapshot hash
→ affected features invalidated
→ affected BrainPacket invalidated

同时未变化的独立事实
不得无理由重写。

==================================================
W3
FIXTURE RESEARCH CHAIN INTEGRATION
==================================================

另开一个范围严格的 Integration Agent。

只补此前仍 PARTIAL 的：

ResearchDraft
→ ResearchAssessment
→ ResearchCard

完整 fixture 链。

不得使用真实股票结果优化语义。

不得让 Agent：

重新设计 S/A/B/C/X
修改 Quality/Timing semantics
修改 Hard Block
填真实概率
填真实 Edge
填真实账户
修改 Cost Engine

必须证明：

BrainPacketVersion
→ DraftVersion
→ AssessmentVersion
→ CardVersion

完整 trace/hash/invalidation。

任何 upstream evidence/snapshot/version 改变，
旧 Card 必须失效或产生新版本。

==================================================
REAL BRAINPACKET
==================================================

W2 如果 real slice admitted，

允许生成：

REAL SANITIZED BrainPacket

但本阶段不上传给 ChatGPT / Deep Research。

BrainPacket 中只允许：

approved projection。

不得包含：

provider token
credentials
raw filesystem paths
DB connection
broker information
unapproved raw licensed data
future outcome
future MAE/MFE
hidden historical revisions

如果 provider transfer permission 未证明，

raw rows/raw documents
不得出现在 cloud-transferable projection。

==================================================
INDEPENDENT REVIEWER
==================================================

W2/W3 完成后启动新的只读 Reviewer。

重点攻击：

fake available_at
retrieved_at backdating
DATE_ONLY midnight fabrication
trade_date → available_at inference
provider update-window spoof
historical visibility escalation
current-observed → historical-PIT escalation
synthetic → observed escalation
source/product entitlement mismatch
purpose escalation
local → cloud scope escalation
coverage widening
symbol widening
date widening
namespace crossover
raw byte mutation
receipt reuse
receipt revocation
policy revocation
source version mutation
corporate-action future leakage
adjustment factor future leakage
financial revision leakage
industry current-label backfill
announcement revision loss
raw/cloud payload leakage
secret/token leakage
future outcome leakage

以及：

Snapshot A → B invalidation chain。

Reviewer 只读，
不得修改业务实现、policy或测试预期。

==================================================
REAL STOCK SLICE GATE
==================================================

最终提交：

P1-B REAL STOCK SLICE GATE REVIEW

必须明确：

LOCAL_REAL_RESEARCH_GATE =
PASS / PARTIAL / FAIL

CLOUD_RESEARCH_EXPORT_GATE =
PASS_LIMITED / BLOCKED

HISTORICAL_BACKTEST_GATE =
BLOCKED

PRODUCTION_DATA_GATE =
BLOCKED

并报告：

real admitted source count
real admitted stock count
real stock Snapshot count
AdmissionReceipt count
data category coverage
clock proof matrix
license/purpose matrix
Snapshot A/B comparison
fixture Draft→Assessment→Card E2E
independent attacks
known limitations
remaining C12-C22
all new contract/version hashes
Golden regression status

==================================================
STRICT STOP
==================================================

本阶段仍然禁止：

ChatGPT真实股票研究调用
Deep Research真实股票研究调用
APPROVE_P1B_RESEARCH_PILOT
真实S级
真实Net Edge
真实position sizing
真实Signal
Approval
OrderIntent
broker
EVENT_3
GUI主体开发
historical backtest
production

即使：

LOCAL_REAL_RESEARCH_GATE = PASS

也必须停止。

等待 Owner 明确发送：

APPROVE_P1B_RESEARCH_PILOT
下一次 Gate 我会怎么判断
下一次 Codex 回来以后，不要再被“400项测试全部通过”这种总数字吸引。

我会重点看五件东西。

第一，看它是否真的第一次产生了：

real stock SnapshotManifest + real AdmissionReceipt

而不是又增加十个 proposal。

第二，看它有没有把：

今天抓到的历史 K 线

偷偷包装成：

历史 PIT 已经证明。

这是下一阶段最容易出现的错误。

第三，看 provider policy 是否真正绑定到了用途。尤其 Tushare 这种技术上非常方便、但协议与具体使用场景需要谨慎映射的来源，不能因为 API 调通就自动获得 CLOUD_EXPORT。

第四，看：

Draft → Assessment → Card

是不是终于作为同一条版本链跑通，而不是三个模块分别存在。

第五，看它能不能坦然给出这样的结果：

text
复制
603993:

Security         PASS
Calendar         PASS
Bars             PASS
Financial        PASS
Announcements    PASS
Corporate Action PARTIAL
Adjustment       PASS
Industry PIT     UNKNOWN

Result:
PARTIAL_RESEARCH_ONLY

Tradeability:
BLOCKED
如果系统能诚实输出这个，我反而会认为它成熟了。

因为我们整个 V1 最重要的理念就是：

不知道就是 UNKNOWN，缺证据就是 GAP。

不能为了让 AI 给答案而把 UNKNOWN 变成 PASS。

等这一道 Real Stock Slice Gate 真正通过，再发 APPROVE_P1B_RESEARCH_PILOT。那时我建议第一次只让 ChatGPT/Deep Research 研究 这三只工程股票，验证真实的：

Real BrainPacket → Deep Research → ResearchDraft → Assessment → ResearchCard → Quality/Timing/Evidence/Risk → A/B/C/X

整个过程。

而且第一轮即使研究极其看好某只股票，也不允许出现真正的 S 和“现在买”：真实账户费用、资金、风险预算仍未配置，Cost/Account Suitability 无法通过。等真实研究卡体系本身跑稳以后，再单独进入你最初真正关心的那一层——费用后的 Net Edge、A→S 晋级、真正有价值的买点，而不是 45.2/45.5 这种给券商贡献手续费的伪精细操作。 