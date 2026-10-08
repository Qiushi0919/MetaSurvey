# P1-A Conditional Closure Plan（待人工批准）

这是 `PASS_WITH_CONDITIONS → Gate Closure` 计划，不是重新启动P1-A。当前只允许本轮GAP/文档与证据审查。**implementation_authorized=false；P1B=false；production=false**。

## 1. 推荐的最小范围

先闭环C01–C11，验收fixture-only MANUAL_EXPORT/PAPER工程输入边界：trusted local admission facade → purpose-bound receipt → minimal manual file → validated non-tradeable research draft。不得调用ChatGPT/Deep Research，不启动Research Agent，不选股/评分/调阈值，不做GUI/EVENT/broker，不重跑V5。

真实market/security/status/calendar/action/financial数据在当前没有ADMITTED正向样本。五个public reference来源 UNKNOWN/UNVERIFIED，仍不能送入研究模型或可交易Card/Candidate/Signal。若人工要求真实公司研究在下一阶段可用，相关C12–C20按实际消费fields/source/date/board覆盖升级为前置，另增加一个**真实授权source+真实clock证明+闭包**正向验收。批准计划本身不能替代许可与历史可得证据。

验证synthetic-only reader可保证研究工程不会被真实未知数据污染，但不能声称已具备真实研究或交易价值。因此提出两个用途门槛：明确scope的 `P1B_READINESS_GATE` 与单源/用途的真实 `DATA_ADMISSION_GATE`。它们不互相代替。任何UNKNOWN scope均fail closed。

## 2. 需确认的四项决定

### D01 P1-B放行范围

推荐：只验收fixture-only MANUAL_EXPORT/PAPER工程边界；真实source仍全BLOCKED。

替代：若要求真实公司研究输入，必须先增加最小真实授权source的clock/完整closure/覆盖与用途正向样本验收。状态：PENDING。

### D02 BrainPacket协议与Admission contracts

推荐：独立BrainPacket1.1 + AdmissionReceipt/SourceAdmissionPolicy/ResearchDraft1.0；旧v1/P1-A schemas原字节保留。

替代：独立ResearchInputBundle wrapper+明确跨协议映射，需另具体审查；不得默默复用P0 hash校验。状态：PENDING。

### D03 运行隔离与迁移范围

推荐：MANUAL_EXPORT文件边界，研究环境无raw/DB凭证/secret/transport；拟006只持久化policy/receipt/revocation/import/export审计。

替代：若DB-backed研究则最小真实server research_read/RBAC测试升为MUST，不能依赖PGlite角色反例。状态：PENDING。

### D04 接受限制与延期清单

推荐：按C12–C47 stated scope延期/保留；SELL不用于真实退出可行性或策略PnL，daily不用于未来预测。

替代：若扩大成交评价/真实用途，相关项必须升级MUST并重新批准范围。状态：PENDING。

仅批准Closure Plan不会构成 `APPROVE_P1B`。未知真实字段仍不要求填写。所有“已接受限制”分类实际仍待人工确认其范围。

## 3. 研究读取合同与硬门禁提案

以下是设计约束提案，未创建schemas/DDL/实现：

| 输入/对象 | 必须绑定 | 拒绝条件 |
|---|---|---|
| SourceAdmissionPolicy | authentic issuer/policy version/hash、source/class、许可证据、allowed purpose/export/retention、clock mapping与coverage | UNKNOWN/UNVERIFIED/无用途授权/撤销/过期/caller自称OFFICIAL或许可 |
| AdmissionReceipt | persisted snapshot ref、raw/closure/data hash、cutoff、source/policy/clock/security/calendar/action/revision refs、scope/purpose/context、code/projection/version | 不能读回闭包、scope晋升、未来/陈旧/缺覆盖、任一hash/ref/version改变 |
| 新BrainPacket协议（待D02） | 1.1版本或独立wrapper、源closure snapshot与导出projection双hash、receipt、evidence subset、namespace、cutoff | 不支持版本、只匹配自封manifest、P0/P1 hash协议混用、未准入evidence、内部路径/credential |
| ResearchDraft | receipt/packet/source refs、mode/purpose/namespace、未经信任的模型结果与版本；can_produce_order=false | LLM自报HUMAN/APPROVE/订单、返回新增未准入证据、真实账户适用性、未知policy伪装calibrated |

`VERIFIED`表示完整性/闭包验证，`ADMITTED`表示真实许可、时钟与明确用途准入；二者必须同时满足。Synthetic只能是 `SYNTHETIC_TEST_ONLY` 的测试用途，不得变为 `REAL_RESEARCH`。FROZEN、DQ PASS、OFFLINE_ELIGIBLE、自封scope都不能单独代替admission。

研究运行的最小隔离必须真实验证：MANUAL_EXPORT消费者只拿sanitized文件，不拿raw挂载、DB句柄/凭证、内部paths或broker capability；拒绝对象不得通过标题/ID/reason列表/hashmetadata泄漏。模型额外知识或额外手工输入不自动获trusted身份，导入的新证据只能quarantine，不能生成可交易Card。应用不能证明研究过程遵守该受限通道时保持BLOCKED。没有声称能对抗拥有所有文件与签发权限、主动绕过流程的管理员。

历史cutoff与current用途freshness分别判断，不能为过TTL而篡改旧快照或把今天状态回填历史。真实DATE_ONLY/其他freshness未知政策不猜；参考fixture规则不能升级真实政策。

Cost-before-Candidate只补边界：显式synthetic费用可测Paper，但实际费用/account未知时不得声称适合真实账户、真实sizing或费用后净Edge。Draft无交易资格；真正评分/校准仍后置。保持全部旧拒绝码与human双阶段约束。

## 4. 实施顺序与停止点

| Milestone | 范围与负责人建议 | 前置/交付/DoD |
|---|---|---|
| W0 本轮GAP/条件分类/证据索引 | parent；`DELIVERED_FOR_REVIEW` | Parent hash/tag/bundle/log/source/experiment checks recorded; plan pending human approval. |
| W1 人工批准范围、协议、契约/DDL设计冻结 | parent；`NOT_STARTED_PENDING_PLAN_APPROVAL` | Exact approved contract versions/fields/hash protocol and source/clock scope; old release/tag bytes preserved. |
| W2 Data Admission与export boundary | proposed Agent DA；`NOT_STARTED` | Original relabel/future/unknown-license/source mutation attacks rejected at intended admission guard with no rejected payload exported. |
| W3 Cost/非执行Import边界 | parent or narrowly scoped Agent PH；`NOT_STARTED` | Unknown real costs block real suitability; importer cannot write orders/approval; all production routes rejected. |
| W4 总控集成、新版本freeze、Golden/clean/独立review | parent + approved read-only Reviewer；`NOT_STARTED` | All required criteria proven for approved scope, current implementation pinned, no old safety assertion relaxed, artifacts complete. |
| W5 停止并等待最终用户Gate与APPROVE_P1B | parent/user；`NOT_STARTED` | No automatic P1-B, Research Agent, Deep Research, scoring/GUI/EVENT/broker work. |

W1必须先确定新协议字段、reason扩展、receipt信任来源/迁移设计，不能由agent自行定架构。W2与W3在接口确定后才可有限并行；W4由总控集成和冻结新版本，Reviewer独立只读验证原反例。W5无任何自动续作。

## 5. Contracts、migration与CodeVersion规则

- 旧16份V1合同、13份P1-A模块schemas、reason registry、001–005、release.v1/release.p1a及旧provenance保持原字节；新版本并列保存。P0/P1-A tag/bundle、旧实验结果永久可复核。
- 建议closure独立release **1.2.0**；新BrainPacket 1.1与Admission/Draft1.0需D02批准。新增ADR只能记录已批准工程语义，不能改业务目标/策略/审批/UNSET。本轮没有创建这些合同/ADR。
- **006只是候选编号**，建议范围仅policy版本、receipt、revocation及export/import audit的append-only records/refs。由总控批准DDL后落地并测试empty→latest、repeat、checksum、权限与TRUNCATE。沿003存储的真实source/parser通常不需新DDL；不得为强行填006重复造表。
- 当前verifier自动枚举全部实现/测试；新增文件会使旧8cca360 source-tree pin失效。未来candidate必须绑定新实际commit与覆盖全部代码的proof，不能修改旧release预期hash、移动文件/换扩展名逃避pin，不能把旧CodeVersion用于新实现。
- 旧candidate的210案例从冻结tag可以独立复现（optional旧宿主仍skip，不运行V5策略）。新candidate保留每项旧安全case，必要的current-code ref升级逐条review；不通过删除case、只认旧tag或放宽PIT/费用/approval实现“全绿”。新实现/Git commit改变输入身份是正确行为，不强求旧economic_result_hash跨版本相同。
- 保存旧Experiment A/B全输出不覆盖。新版本另存实验报告；signals、quantity、prefriction fills与fees policy均不改来优化结果。比较order/fill/ledger/NAV/cost/path经济组件，并分别解释CodeVersion导致的新身份hash。每次新增版本/hash变更都应使旧结果/approval失效。

## 6. 子Agent任务合同（仅建议，尚未启动）

### Agent DA — Data Admission Closure

| 字段 | 内容 |
|---|---|
| Context | 已验收P1-A保持冻结；C01–C06/C09尚缺强制consumer；unknown真实源不准入。 |
| Goal | 实现经总控批准的用途准入facade、闭包receipt、最小manual export与负向攻击。 |
| Inputs | 批准的D01–D03、新schema/receipt协议、P0/P1-A tags、真实reference负向fixture、synthetic正向fixture。 |
| Outputs | scope-owned admission/export代码与tests、实际source/byte/clock读回证据、quarantine/失败审计。 |
| Interfaces | 总控指定的db只读closure adapter/receipt authority；只输出已准入minimal packet，不向consumer传DB/raw能力。 |
| Constraints | 不得改shared schemas/ADR/编号/SoT/Gate；不得补真实许可/available_at；不抓新源/不读credentials/不调用模型；只能获批隔离worktree owned paths。 |
| Tests | 原scope晋升反例、unknown许可、未来clock/修订/action、source-byte mutation、raw直读/metadata泄漏、coverage/freshness/失效。 |
| Definition of Done | 所有原反例在指定guard拒绝，rejected payload未输出；source trace可读回；总控审核合并，未建立真实默认值。 |

### Agent PH — 最小Platform/非执行Import（可选）

| 字段 | 内容 |
|---|---|
| Context | 全PG/RBAC/SELL hardening延期；只处理C07/C08以及批准范围内C01最小隔离，不重新写经济kernel。 |
| Goal | cost先于候选准入、未知真实适用性拒绝、模型返回仅非交易draft；证明消费者无broker/approval写能力。 |
| Inputs | 获批receipt/packet/draft协议、原cost/paper API、unknown profile、synthetic人工fixture、运行隔离方案。 |
| Outputs | 薄validator/import adapter与failure audit、producer调用次序/zero-write/LLM越权负向tests。 |
| Interfaces | consumer只接受DA签发receipt；cost API显式profile/version；draft持久化仅获批006边界。 |
| Constraints | 不改变fee/rounding/reserve/SELL/T+1/namespace语义；不建真实server/gateway/auth/GUI；共享合同/迁移由总控；如DB-backed拓扑另批准再开工。 |
| Tests | UNSET费用/account不能真实suitability、cost-before-admission、LLM伪HUMAN/BUY/OrderIntent zero writes、PROD拒绝、namespace交叉、无raw/transport能力。 |
| Definition of Done | 明确范围全负向与manual fixture链通过，旧费用/账本/审批Golden不回退，没有真实值/transport。 |

### Independent Reviewer — 只读

| 字段 | 内容 |
|---|---|
| Context | 获批Closure实现整合后；先前Reviewer证据只覆盖旧candidate，不替新边界背书。 |
| Goal | 独立攻击12项readiness与全部Golden关键不变量；核对可恢复版本、命令日志/hash和源许可边界。 |
| Inputs | 实际candidate commit/newrelease/新migration、原反例、clean日志、P0/P1-A tags、机器artifact索引。 |
| Outputs | 只读finding/复验记录/具体scope Gate建议，report/hash与实际run id。 |
| Interfaces | 仅读取repo/captures/日志；使用隔离fixture DB/运行环境进行攻击，不修改业务。 |
| Constraints | 不改业务规则/测试预期/release/SoT/旧seal，不决定真实参数，不创建Research Agent。 |
| Tests | future/许可/purpose/scope/metadata/hash/namespace/cost/approval/PROD/DB权限旁路，且原反例必须命中正确门禁。 |
| Definition of Done | 全部MUST有实际证据，未关闭项如实说明；Gate只能PASS/PASS_WITH_CONDITIONS/FAIL，用户批准另记录。 |

总控保留shared contracts、ADR、migration numbering、SoT、Gate status与final merge。各agent隔离worktree，shared edits只能由总控进行。需要改冻结业务合同、策略语义、approval、UNSET或production边界时暂停相关工作并升级人工决定。不得靠已有task消息自动授权子任务。

## 7. 本轮与后续验收证据

本轮复用历史clean log：210 tests / 209 PASS / 0 FAIL / 1 optional SKIP，派生索引run id（不是伪造原CI号）在 [golden-test-matrix.json](golden-test-matrix.json)。本轮新增artifact hash/tag/bundle/log审查与内存反例有独立run id；没有新的210项run，没有新Independent Reviewer，没有重跑V5。

获批实现完成后才运行新candidate全检查/实验/clean依赖复现及Reviewer。25类Golden和12项readiness必须逐条报告；任何旧核心不变量下降直接FAIL。检查当前新源代码的admission guard，不能用provenance错误提前拒绝遮盖实际source旁路。

每个Milestone索引必须给branch/commit/tag、真实source-tree、contract release、migration checksum、schema report、test run id/命令/counts/log hash、golden matrix/report hash、data/legacy manifest、snapshot/fixture/实验hash、独立report/hash、Gate JSON/Markdown。索引自身的hash及交付commit放外部checkpoint manifest，避免自引用hash循环。`NA/NOT_RUN/PENDING`必须注明原因。

## 8. 延期与生产阻断

完整47项分类见 [GAP](GAP-Analysis.md) / [conditions.json](conditions.json)。C12–C22为P1-B内按消费数据/用途逐里程碑补完；在补完前对应实际source/feature仍BLOCKED。C23–C31是P2候选，若拓扑/执行用途扩大须升级前置。C32–C39生产专属阻断。C40–C47建议接受已声明的有限能力，不代表永久豁免，也不形成真实券商/投资规则。

真实AccountProfile原30项及生产Edge/sizing/概率/许可等扩展unknown政策原样保留，见 [unset supplement](unset-required-supplement.json)。本轮不索取真实账户、费率或风险值。

## 9. 最终Closure Gate的报告合同

批准范围完成后才提交 `P1-A Conditional Closure Gate Review`，逐项：

1. Executive conclusion
2. 当前Git state
3. P0/P1-A及Closure tags/commits/hashes
4. Contract release matrix
5. Migration matrix
6. Golden Test matrix
7. Data Admission matrix
8. Security/Calendar/PIT
9. Cost Engine
10. Paper/Ledger/Replay
11. CORE_40 skeleton
12. MAE/MFE
13. Transaction-cost attribution
14. Friction stress
15. Micro-Ladder
16. Audit-chain evidence
17. Independent Reviewer findings
18. UNSET_REQUIRED inventory
19. Known limitations
20. Deferred-to-P1B
21. Deferred-to-P2
22. PROD_ONLY_BLOCKERS
23. P1B_READINESS_GATE
24. ProductionGate
25. Artifact index

结论只能 `PASS / PASS_WITH_CONDITIONS / FAIL`，并明确评审commit/tag/source-tree/run id/Reviewer hash/用户PENDING或APPROVED/REJECTED。未解决MUST不得对readiness给PASS。任何技术PASS都不能自动开P1-B；没有明确 `APPROVE_P1B`，保持停止。

当前这里只提交GAP与计划：P1-A = PASS_WITH_CONDITIONS；P1B_READINESS_GATE = FAIL；Closure Plan = PENDING_APPROVAL；P1-B/Research/Production = BLOCKED。不宣称Closure Gate已经完成。
