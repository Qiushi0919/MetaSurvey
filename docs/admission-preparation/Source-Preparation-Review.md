# P1-B 最新状态：真实股票数据准入准备审查

结论：**PASS_WITH_CONDITIONS，仅来源与合同准备**。本轮不重做已交付的 P1-B0，不是完整研究管线 W4，不放行真实股票研究。真实股票数据准入、Research Pilot、真实 Signal/Order、production 继续 BLOCKED；productionGate=false。

本次人类指令明确分为 Closure 停点与更晚 P1-B Gate 两条路线。实际 repo 已在后者：`1fffea964ad3fed5c47d7955b9121b31f8ceff74`，tag `p1b-data-semantics-20261005`。因此执行“最新 Gate 之后的数据准入准备”，不回退 HEAD 或重写历史验收。[前置核验](preconditions.json)、[原始授权](../authorizations/P1B-next-step-20261005.md) 与 [W1 工程准备边界](W1-Preparation-Freeze.md) 保留判断依据。提案内容尚未获所有者批准为业务规则。

## 本轮交付

```text
contracts/admission-preparation/
  ClockEvidenceProposal.schema.json     # 1.0.0，PROPOSED_UNVERIFIED
  StockSliceProposal.schema.json        # 1.0.0，OWNER_REVIEW_REQUIRED
tools/admission-preparation/
  check-proposals.mjs                   # 仅提案结构与外部原件 hash 核验
docs/admission-preparation/
  Contract-Fit-Analysis.md / W1-Preparation-Freeze.md
  Source-Comparison.md / provider-evidence.json
  Data-Requirements.md
  slice-observed.proposal.json / slice-historical.proposal.json
  clock-unknown.proposal.json / public-document-captures.json
  35-item-audit.md / 35-item-audit.json
  preconditions.json / preservation.json / validation.json
  proposal-validation.json / independent-review.md / independent-review.json
  Source-Preparation-Review.md / Preparation-Gate.json / artifact-index.json
docs/authorizations/P1B-next-step-20261005.md
```

新提案位于独立目录，没有成为 SourceObservation/Policy/Receipt/BrainPacket 的真实新 runtime 版本。没有新股票 adapter、Snapshot、Receipt、consumer、migration、数据库或策略参数。仅更新 README、AGENTS、source-of-truth 的当前导航，历史报告保留原字节。

## 来源、时钟与覆盖结论

[来源比较](Source-Comparison.md) 比较 SSE 正式产品、Tushare、官方公告/CNINFO、BaoStock 与旧线索五条路径；[机器证据](provider-evidence.json) 区分文档事实和工程推断。九份实际官方文档的 URL、capture time、原件 SHA/长度全部核验。原 HTML 与日志在 Git 外隔离；条款、产品目录和字段文档不等于本账户 entitlement，未调用认证接口、下载市场数据、购买或联系供应商。

两份可审查方案均为 CORE_40、八类必需数据：Security/status、Calendar/rules、raw bars、corporate actions、adjustment versions、financial revisions、announcements、industry membership。证券、日期窗口、cutoff、来源权属、许可、覆盖与 PIT 仍 UNSET_REQUIRED/BLOCKED。local research、cloud MANUAL_EXPORT、historical backtest 三项用途未知；redistribution=DENIED。没有借用旧 SSE 零证券日历政策。

建议先审 [当前观察路线](slice-observed.proposal.json)，只在将来已批准的当前观察 cutoff 使用实际取得的版本；它不能证明过去决策。若需要 [真实历史截面路线](slice-historical.proposal.json)，必须另证原版与修订在当时可见。推荐顺序不是已批准规则。

[时钟提案与 requirements](Data-Requirements.md) 明确 business event/effective date 与 observation capture 分开，publication 保留精度，DATE_ONLY 不补午夜，retrieval 不推导首次公开时点。新 schema **只验形状，没有 chronology/source-fact runtime**：形状合法的虚构 available_at 仍可能通过，但对象保持 PROPOSED_UNVERIFIED、BLOCKED、historical_visibility_proven=false。真实 source 扩展前必须有新版本 adapter 和实际证据攻击，不能把本轮结构 PASS 称为历史 PIT PASS。

旧 [C12–C22](../p1b/conditions.json) 均未自动关闭：C13 仍仅日历参考 PARTIAL，C19 历史 DATE_ONLY 政策未定，其他股票身份/raw/action/financial/industry/真实 producer/calibration 仍阻断。旧真实参考 Receipt 是一次 DEV/内存 registry 的历史证据，没有现在可消费的持久 live授权。

## 实际验证与独立审查

[本轮检查](validation.json)：在当前 checkout 实际运行完整冻结基线，**300 项：299 PASS、0 FAIL、1 optional external V5 SKIP**。portable 14 日 ledger baseline 与25类既有 Golden 不变量通过；没有恢复/执行 V5、修 seal、改 ledger 或重跑覆盖旧经济报告。新增两份 schema 编译，提案结构17/17 PASS，九份实际文档原件 SHA/长度 MATCH；这17项不证明股票数据或真实 PIT。

[独立审查](independent-review.md) 由本轮新建只读 Reviewer 执行，结论范围仅 PREPARATION。独立 schema/越权变体32/32 PASS，九份原件、140+34冻结 code pins、291个历史 Git artifact 对象实核一致。Chronology runtime、真实源/权限/coverage、持久 issuer/revocation、未完成的股票管线仍列为条件；没有复用旧 Reviewer PASS 冒充本轮全业务攻击。

审查指出的文档用途标签、旧导航与不存在的测试链接已纠正。提案工具的报告输出边界也补上 realpath 检查，避免外部目录 symlink 指回 repo；保持 wx 新文件写入，不覆写历史结果。修后17项结构检查与九原件核验重新通过。

可独立运行提案检查，不写入 repo：

```sh
node tools/admission-preparation/check-proposals.mjs
# 如果持有外部原件，可添加 --capture-dir=/absolute/public-documents
# 如需保存报告，添加 --output=/absolute/outside-repo/new-report.json
```

无 capture-dir 时只检查结构与 manifest 的阻断标签，不声称验证外部原件。输出报告必须是 repo 外新文件，不能覆写已保存结果。

## 35 项现状与未完成内容

完整逐条状态与证据见 [35 项审查表](35-item-audit.md) / [机器清单](35-item-audit.json)，不是35项全部 PASS。

既有十维语义、Quality/Timing 分离、S 最大 REQUEST_REVIEW、cloud lead pending、费用/账户/审批/namespace/PIT 工程隔离有实际回归证据。**Draft → Assessment → Card 的完整 fixture 版本链、compatibility adapter 与贯通 replay 仍 PARTIAL**：Closure 的 MANUAL_EXPORT→NON_TRADEABLE Draft 与 P1-B pure synthetic Assessment 是各自实现；不能把它们拼称为已验收的新完整研究管线。

真实市场/财报/action/industry adapter 与原件版本链、许可/PIT/coverage、通用 evidence resolution、持久 issuer/撤销尚未完成。真实 PostgreSQL 多连接/RBAC/备份恢复/crash、SELL/真实撮合等后续条件也未完成；PGlite 单进程测试不能外推生产安全。

没有真实股票 ResearchCard/等级、模型调用、真实账户适用性、真实 Net Edge、sizing 或研究到真实 Signal/Order 的路径。本项目仍有明确 synthetic/PAPER 内核的测试订单路径，不能错误宣称整个 repo 无任何模拟订单。ResearchDraft/Assessment 的 can_produce_order=false 未改，LLM 不能认证 HUMAN_USER。

## Git 与冻结资产

工程基线仍为 release1.3.0、schema6、001–006。Runtime CODE_VERSION `42197c99be5177ad50ac08402bf2203282e51f70`、SOURCE_TREE_HASH `sha256:6e9b73d5b31ead6d6422b0ca47276533f770512a5d3d5eab0f184a125aed2ad8` 未变；提案变更不伪造新的业务 release。

[保留核验](preservation.json) 实测289个当前不可变文件与旧 delivery commit 逐字节一致；旧291项 index 对历史 Git 对象一致。旧 P0/P1A/Closure/P1B schemas、releases、pins、migrations、经济报告、legacy manifest 与 tags 均未改。两个旧 bundle 实际 hash MATCH；旧恢复证明保持其原执行日期。

新工作分支 `p1b/source-preparation`；本轮最终 commit/tag、新 index/hash、bundle 与实际恢复核验记录在 Git 外 [delivery checkpoint](/Users/qiushi/投资研究/.p1b-archives/source-preparation-20261005/delivery-checkpoint.json)。它在提交后生成，避免报告写自己的 commit/hash。没有 push 或再分发。本轮归档只包含新 repo Git 对象，不包含历史 DB、状态、credential 或大体积原件。

## 下一道 Owner Gate

请审 [来源比较](Source-Comparison.md)、两份 slice 与 clock proposal，确定：具体供应方/产品及可证明用途；当前观察或历史截面路线；有限证券/日期/cutoff；新 clock 的语义。无需提供 token、真实账户本金、佣金或风险值。许可原证据与 owner 选择分别必需，选择不能代替供应商授权。

本次指令要求：“Codex 想把某个真实 source 从 BLOCKED 升为 ADMITTED”时由你决定，W1 Freeze 也须审一次。当前已经把可审查材料完成，因此在实际 source/clock/范围实现前停下等待这一决定；不是因30个真实账户未知字段停止工程。

确认后建议只开一个有明确有限范围的 Data/PIT agent，加一个独立 Reviewer；总控保留 shared contracts/clock/versions/Git。另设 fixture Integration 任务补全上面的 Draft→Assessment→Card 缺口，待具体新接口审阅后再编码；不启动全部功能 agent、GUI、EVENT_3 或 broker。

真实资金执行仍被生产开关、账户/费用/风险30项未知、生产拓扑/权限/并发/恢复未验收与实际券商 capability 缺失阻断。真实研究试点还需股票 source 的独立 source/licence/PIT/coverage/Receipt 前提、完整 MANUAL_EXPORT/Evidence Resolution/版本链与攻击验收，然后由你显式发送 `APPROVE_P1B_RESEARCH_PILOT`。本轮完成后停止，不自动进入这些工作。
