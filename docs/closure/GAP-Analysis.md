# P1-A PASS_WITH_CONDITIONS 条件闭环 GAP Analysis

日期：2026-10-05。范围：**只读审查、条件分类和待批准计划**。没有新业务实现、migration、contract、ADR或生产配置变更；没有启动任何子 agent，没有重新运行/恢复 V5 策略，也没有调用研究模型。

当前 P1-A 技术结论维持 **PASS_WITH_CONDITIONS**。本轮不是 P0→P1-A 重构。**P1B_READINESS_GATE = FAIL**：必须经过的研究读取/导出/导入边界尚不存在，不能用冻结基础模块的测试成绩代替未来consumer验收。这个 FAIL 指研究接入前置门槛尚未建立，不表示已验收的 synthetic cost/ledger/replay 核心失效。

Closure Plan 与分类均 PENDING_APPROVAL。P1-B、Research Agent、Deep Research、GUI主体、EVENT策略与真实交易全部 BLOCKED。人工批准本计划之前不开始 Closure 实现；最终通过 Closure 后仍必须另有 `APPROVE_P1B`。

## A. 已完成能力与证据

下表的能力引用已有 P1-A 验收/测试证据，本轮只校验其完整性。历史210项检查没有在本轮重新执行；新定点检查也不计入210。新Milestone不声称已发生独立Reviewer复核。

| 能力 | 已完成内容/范围 | 证据 |
|---|---|---|
| Git/P0/P1-A基线 | annotated tag、commit、bundle/SHA及恢复检查点存在，工作区的冻结实现与tag一致 | `baselines/P0-freeze-20261005.json / 外部P1-A归档manifest` |
| Source of Truth | 正式交接+现状审查+P1-A授权指纹吻合；工程ADR不升级未定业务规则 | `source-of-truth.json / closure/evidence-verification.json` |
| 合同 | 16份V1+13份P1-A module schemas、独立release、reason registry均冻结 | `contracts/release.v1.json / contracts/release.p1a.json / closure/contract-matrix.json` |
| Schema | 连续001–005，empty→latest与repeat/checksum证据；60表51/7/2 | `baselines/P1A-schema-validation.json / closure/migration-matrix.json` |
| Legacy | 五类manifest，V5独立legacy experiment；旧seal兼容失败未伪造PASS | `legacy/asset-manifest.v1.json / baselines/P1A-legacy-native-compatibility.json` |
| Golden | 25类不变量映射至冻结case；clean 210/209/0/1，skip真实标注 | `closure/golden-test-matrix.json / baselines/P1A-clean-reproduction-20261005.json` |
| Clean reproduce | 独立clone/new deps/cache/两空npm配置/minimal env，darwin/arm64 | `baselines/P1A-clean-reproduction-20261005.json` |
| Canonical identity | SSE/SZSE canonical，裸code需exchange，冲突quarantine/audit；状态PIT | `src/data/security.mjs / tests/p1a-data.test.mjs` |
| Trading calendar | 显式session/coverage、长假、超界拒绝；官方副本reference-only | `src/data/calendar.mjs / tests/fixtures/p1a-data/public-capture.json` |
| 真实bars pipeline | 2条真实SSE raw bytes→Observation→staging→normalized→DQ；缺时钟/许可仍阻断 | `src/data/source.mjs / src/data/market.mjs / public-capture.json` |
| PIT fail-closed | 四时钟及raw/proof/source/hash绑定；晚retrieval不回填available | `src/data/source.mjs / src/data/snapshot.mjs` |
| Action/adjustment | raw/adjusted身份隔离、factor/action递归可见性，有限Decimal | `src/data/market.mjs / tests/p1a-data.test.mjs` |
| Financial revision | ORIGINAL/RESTATEMENT/SOURCE_CORRECTION追加，先cutoff后latest | `src/data/market.mjs / tests/p1a-data.test.mjs` |
| Snapshot | 内容寻址+完整closure读回+原byte mutation失效；低层验证不等于研究准入 | `src/data/snapshot.mjs / docs/closure/boundary-inspection.json` |
| Cost | 独立Decimal100/BigInt，integer cents/minimum/included关系/partial累计费用 | `src/cost/index.mjs / tests/p1a-cost.test.mjs` |
| Affordability | 整手含全部费，最终money界限+最坏partial reservation | `src/cost/index.mjs / tests/p1a-cost.test.mjs` |
| Shared reservation | 账户现金共享、策略lots隔离、同连接事务/重启/重复安全 | `src/paper/index.mjs / tests/p1a-paper.test.mjs` |
| Paper lifecycle | reserve→submit→partial/full fill/cancel/reject→ledger→reconcile，PROD拒绝 | `docs/p1a-paper.md / tests/p1a-paper.test.mjs` |
| Ledger/oracle | 独立BigInt scaled-rational oracle，T+1/Shanghai日期/partial/seq/hash | `src/paper/oracle.mjs / tests/p1a-paper.test.mjs` |
| Experiment A | 两次8字段一致，cost/rule/source byte mutation改变hash，实际code pin | `docs/experiments/P1A-results.json` |
| Experiment B | 固定毛收益60000分，摩擦537/2070/7788，净59463/57930/52212；Edge 6/4/2 orders | `docs/experiments/P1A-results.json` |
| Micro-Ladder | 每tranche独立完整roundtrip cost，三类拒绝；生产三阈值UNSET | `src/p1a/edge.mjs / tests/p1a-integration-foundation.test.mjs` |
| Attribution | gross/commission/min-effect子集/stamp/exchange/other/slip/friction/net+ratios | `src/p1a/replay.mjs / docs/experiments/P1A-results.json` |
| CORE skeleton | 20–40是review horizon；四失效原因可提前；弱短期表现不自动退出 | `src/p1a/core-skeleton.mjs / tests/p1a-integration-foundation.test.mjs` |
| MAE/MFE | 5/10/20/40D及timing/duration/path hash、DAILY_APPROXIMATION/不足null | `src/p1a/metrics.mjs / docs/adr/ADR-011-economic-replay.md` |
| Audit | Data→Snapshot→Feature→实际Cost→Replay parent/hash/time/version；九表TRUNCATE反例 | `src/p1a/audit.mjs / docs/independent-review-p1a.md` |
| Unknown inventory | schema生成30AccountProfile未知/63required leaf；生产永久false | `config/p1a/unset-required.inventory.json / tests/p1a-production-lock.test.mjs` |
| Independent review | 旧实现和最终25项P1-A报告已只读攻击/一致性审查；不替新consumer背书 | `docs/independent-review-p1a.md` |
| 无真实执行 | 无broker submit/credential path，LLM不能authenticate HUMAN；本轮实际gate=false | `src/baseline/gates.mjs / closure/boundary-inspection.json` |

证据读取与核验见 [evidence-verification.json](evidence-verification.json)、[contract matrix](contract-matrix.json)、[migration matrix](migration-matrix.json)、[Golden matrix](golden-test-matrix.json)。所有SHA及时间/run关联由 [artifact-index.json](artifact-index.json) 汇总；历史PASS能关联到已核验原始clean日志，当前新consumer tests明确NOT_RUN。

## B. 从“闭包校验”到“研究准入”的实际缺口

1. `verifyDataSnapshot`读回raw/objects及cutoff闭包，提供完整性证明；它不是source许可、真实性、用途授权或研究运行隔离证明。当前真实source仍全部非交易，不存在真正ADMITTED真实历史snapshot。
2. 本轮只在临时内存PGlite中复现：对synthetic根闭包，使用新的rules hash并请求 `scope=OBSERVED`，低层freeze返回FROZEN且verify通过。原始source仍是SYNTHETIC。当前runReplay另强制scope=SYNTHETIC，因此没有执行真实路线；反例证明不能把manifest名称当来源准入能力。**这是C02必须封住的scope晋升攻击**，不在本轮修改低层实现来消除反例。
3. P0 `validateBrainPacket`要求 `hashValue(packet.evidence)==snapshot.data_hash`；P1-A `data_hash=hashValue({root_refs,closure_refs,feature_version,decision_cutoff,rules_hash})`。闭包含source/calendar等非DataEnvelope对象。不能把正确P1-A闭包直接塞进旧reference packet，再删除hash断言或重算旧snapshot来过测试。需要明确新协议版本和adapter，见C04/D02。
4. Snapshot历史cutoff合法不等于今天新信号报价fresh。研究入口需要purpose、coverage、消费context与失效proof；历史研究cutoff与实时freshness必须分别判断。
5. 当前Cost API与生产门禁可用，但研究返回、candidate admission顺序与未知真实成本适用性尚未有producer-levelE2E。

定点行为原证据：[boundary-inspection.json](boundary-inspection.json)。它只包含synthetic内存数据库与未配置profile实际gate调用，不写业务代码、不访问旧账本/真实credentials、不调用网络或模型。原反例必须在将来真实admission guard处拒绝，不能用更早的CodeVersion错误冒充修复。

## C. 全部条件分类（建议，尚未获人工批准）

五种分类是审批提案。尤其 `ACCEPTED_KNOWN_LIMITATION` 表示建议接受明确范围，**不表示用户已接受**。任何用途扩大均可使延期项升级为必修：真实source某字段被消费前，所需许可/clock/identity/calendar/action/financial覆盖必须完成；DB-backed研究需要最小真实DB权限验收；若承诺真实退出/策略PnL，SELL限制必须前移。

- `MUST_CLOSE_BEFORE_P1B`：11项。
- `MAY_DEFER_TO_P1B`：11项。
- `MAY_DEFER_TO_P2`：9项。
- `PROD_ONLY_BLOCKER`：8项。
- `ACCEPTED_KNOWN_LIMITATION`：8项。

| ID | 条件 | 建议分类 |
|---|---|---|
| C01 | 研究读取入口与最小权限隔离尚未建立 | MUST_CLOSE_BEFORE_P1B |
| C02 | 数据来源许可、用途与 synthetic scope 必须由可信 receipt 绑定 | MUST_CLOSE_BEFORE_P1B |
| C03 | PIT 策略必须在研究入口复核，不接受 caller 自证时钟 | MUST_CLOSE_BEFORE_P1B |
| C04 | P0 BrainPacket 与 P1-A closure 的 hash 协议尚未桥接 | MUST_CLOSE_BEFORE_P1B |
| C05 | Feature/Card 输入、namespace 与 outcome 隔离必须端到端绑定 | MUST_CLOSE_BEFORE_P1B |
| C06 | Freshness、覆盖范围与 invalidation 必须按消费用途强制 | MUST_CLOSE_BEFORE_P1B |
| C07 | Cost-before-Candidate 与真实费用未知禁适用性结论 | MUST_CLOSE_BEFORE_P1B |
| C08 | MANUAL_EXPORT/研究导入必须不可执行，LLM不能认证人工 | MUST_CLOSE_BEFORE_P1B |
| C09 | 研究包字段最小化，拒绝 arbitrary payload 与内部raw路径 | MUST_CLOSE_BEFORE_P1B |
| C10 | Closure新增代码与冻结实现的版本/测试协议需先确定 | MUST_CLOSE_BEFORE_P1B |
| C11 | 12项P1B_READINESS_GATE必须有新端到端证据与独立审查 | MUST_CLOSE_BEFORE_P1B |
| C12 | 真实完整官方security/master/status历史未完成 | MAY_DEFER_TO_P1B |
| C13 | 全年calendar与当前各板块session规则未认证 | MAY_DEFER_TO_P1B |
| C14 | 真实历史available_at/可信时间证明尚无 | MAY_DEFER_TO_P1B |
| C15 | 真实bars slice缺clock/license/preclose，真实可研究snapshot为0 | MAY_DEFER_TO_P1B |
| C16 | 真实corporate-action feed与跨来源factor对账未完成 | MAY_DEFER_TO_P1B |
| C17 | 真实adjustment math / entitlement reconciliation未实现 | MAY_DEFER_TO_P1B |
| C18 | 真实financial parser/修订样本/source admission未实现 | MAY_DEFER_TO_P1B |
| C19 | DATE_ONLY历史重构政策未批准 | MAY_DEFER_TO_P1B |
| C20 | 行业成员、名称/sector PIT和真实长期验证数据未齐备 | MAY_DEFER_TO_P1B |
| C21 | 真实指标使用/校准样本覆盖未确认 | MAY_DEFER_TO_P1B |
| C22 | Research-store/Brain业务producers、评分与概率/Edge准入政策尚未实现 | MAY_DEFER_TO_P1B |
| C23 | 真实PostgreSQL多连接/多进程现金并发未验收 | MAY_DEFER_TO_P2 |
| C24 | 完整server RBAC/least privilege未部署 | MAY_DEFER_TO_P2 |
| C25 | 备份恢复、可信storage/timestamp authority与不可变外部归档未验收 | MAY_DEFER_TO_P2 |
| C26 | COMMIT前后崩溃fault injection未验收 | MAY_DEFER_TO_P2 |
| C27 | 持续数据健康监控/高频watcher/实时feed恢复未做 | MAY_DEFER_TO_P2 |
| C28 | Paper SELL全额费预留使零available cash全仓不能退出 | MAY_DEFER_TO_P2 |
| C29 | 真实tick/涨跌停/流动性/停牌撮合与minute-level执行模型未实现 | MAY_DEFER_TO_P2 |
| C30 | 20日真实forward Paper未验收 | MAY_DEFER_TO_P2 |
| C31 | 生产部署/备份运维、完整GUI、L2/高频基础设施未建 | MAY_DEFER_TO_P2 |
| C32 | 真实account/capital/budgets/risk/frequency参数未配置 | PROD_ONLY_BLOCKER |
| C33 | 真实券商费率/范围/inclusion/slippage/rounding/effective period映射未认证 | PROD_ONLY_BLOCKER |
| C34 | 真实交割单/费用/持仓现金对账未做 | PROD_ONLY_BLOCKER |
| C35 | 真实sizing与账户总risk enforcement未实现 | PROD_ONLY_BLOCKER |
| C36 | 真实用户认证与双人工审批权限未实现 | PROD_ONLY_BLOCKER |
| C37 | 真实broker gateway与接入/适用义务确认未完成 | PROD_ONLY_BLOCKER |
| C38 | production Kill Switch/NO_NEW_ORDERS部署未验收 | PROD_ONLY_BLOCKER |
| C39 | 真实credentials/账户敏感数据与生产密钥分发未设置 | PROD_ONLY_BLOCKER |
| C40 | Legacy native CLI hash mismatch继续保留 | ACCEPTED_KNOWN_LIMITATION |
| C41 | DAILY_APPROXIMATION与retrospective metric定义 | ACCEPTED_KNOWN_LIMITATION |
| C42 | Experiment A/B只有synthetic工程意义 | ACCEPTED_KNOWN_LIMITATION |
| C43 | 现有fixtures与有界reference只证明小范围能力 | ACCEPTED_KNOWN_LIMITATION |
| C44 | clean验证为darwin/arm64且optional external legacy test skip | ACCEPTED_KNOWN_LIMITATION |
| C45 | 最坏partial rounding导致BUY reserve高于整单affordability | ACCEPTED_KNOWN_LIMITATION |
| C46 | synthetic cost生效区间两端包含，P0 harness旧语义不同 | ACCEPTED_KNOWN_LIMITATION |
| C47 | 审计脱敏不是完整DLP、trigger不是DB owner防篡改承诺 | ACCEPTED_KNOWN_LIMITATION |

完整机器清单：[conditions.json](conditions.json)。以下逐项给出原因、三种影响、模块、测试、migration、冻结合同影响与业务决定。

## D. 条件逐项说明

### C01 研究读取入口与最小权限隔离尚未建立

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：verifyDataSnapshot 是可调用的低层函数；没有必须经过它的 Research export/read facade。无消费者不等于未来消费者已受保护。 未来模块直接查询 raw/objects 或接收 caller 自封 manifest，会绕过现有门禁。

影响：Research—会：未知许可/隔离证据可能进入研究；回测—会：模型输入可能不再绑定真实闭包；真实执行—会：污染后续 Card/Candidate/Signal，但当前仍硬禁用。

模块：拟新增 admission/export facade；src/data/index.mjs；未来 brain-adapter/research-store。验收：quarantined/future/unknown license/缺 lineage 均无输出；禁止 raw URI/path/DB handle 暴露；MANUAL_EXPORT 运行仅获得已准入 artifact，无 raw 挂载/DB凭证；受限运行环境尝试直读 raw/store 必须拒绝。

Migration：建议006仅在批准 receipt/拒绝审计持久化后追加；最小隔离若仅文件不需DB迁移。冻结contract：旧16/13 schemas原字节不改；拟新增 AdmissionReceipt 等独立合同。

用户决定：需要批准最小运行边界：推荐 MANUAL_EXPORT 文件通道；不授权真实研究调用。证据：`src/data/index.mjs` / `src/data/snapshot.mjs` / `docs/p1a-data.md`。

### C02 数据来源许可、用途与 synthetic scope 必须由可信 receipt 绑定

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：公开来源均 UNKNOWN/UNVERIFIED，现有允许仅 synthetic；内存反例显示 synthetic 闭包可被低层函数标成 OBSERVED 并通过 verify。 仅看 FROZEN/PASS/scope 名称会误把模拟数据或引用副本当真实可研究数据。

影响：Research—会：来源可信性/许可污染；回测—会：伪造 OBSERVED PIT 样本；真实执行—会：真实适用性结论无根据。

模块：source policy/admission registry；src/data/source.mjs；src/data/snapshot.mjs；拟新增 AdmissionReceipt。验收：复现 synthetic→OBSERVED 的原反例必须在 admission 处拒绝；unknown/过期/撤销/用途不符许可拒绝；caller 修改source_class/allowed_use或receipt签发者无效；source/raw hash不匹配拒绝。

Migration：拟006追加版本化source-policy/receipt/revocation记录，不更新旧对象。冻结contract：新 SourceAdmissionPolicy/AdmissionReceipt 拟1.0；已有冻结合同不回改。

用户决定：必须批准 fixture-only 或真实source用途；真实许可证据仍UNSET，用户批准不能制造许可。证据：`docs/closure/boundary-inspection.json` / `tests/fixtures/p1a-data/public-capture.json` / `src/data/source.mjs`。

### C03 PIT 策略必须在研究入口复核，不接受 caller 自证时钟

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：当前四时钟/闭包 guards 可靠，但真实 SOURCE_FIELD 授权与历史重构未启用；P0 reconstruction harness 不应直接充当真实准入。 自封 available_at、晚取得资料、未来标题/ID或未批准 DATE_ONLY 规则可污染模型。

影响：Research—会：前视；回测—会：未来泄漏；真实执行—会：输入失真。

模块：admission facade；src/data/source.mjs；src/data/snapshot.mjs；src/contracts/validate.mjs。验收：cutoff±1秒/晚retrieval/未来revision/factor/title/ID拒绝且不进入输出hash；retrieved不得回填历史available；DATE_ONLY无获批policy拒绝；fixture reconstruction标签不能晋升真实。

Migration：使用拟006 receipt绑定clock-policy/version；不重写001–005。冻结contract：旧四时钟合同不修改；新增用途/时钟policy refs。

用户决定：真实时钟/重构语义继续UNSET；本轮建议只验证拒绝，不制定真实规则。证据：`src/data/source.mjs` / `src/data/snapshot.mjs` / `src/contracts/validate.mjs` / `tests/gates.test.mjs`。

### C04 P0 BrainPacket 与 P1-A closure 的 hash 协议尚未桥接

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：P0 validateBrainPacket 比较 hashValue(packet.evidence)；P1-A data_hash 为 root/closure/feature/cutoff/rules 的hash。闭包含source/calendar，不能直接当全DataEnvelope数组。 照搬旧validator会拒绝正确闭包；绕开检查或重算data_hash会破坏已冻结证据。

影响：Research—会：packet不能证明对应闭包；回测—会：输入身份混乱；真实执行—会：Card链引用错误。

模块：拟新 BrainPacket协议adapter；src/baseline/gates.mjs（保持冻结）；src/data/snapshot.mjs。验收：真实source snapshot→packet→import→draft完整绑定；旧P0 harness继续通过；root/closure/feature/projection任一字节变更拒绝；不能删校验或改旧hash来通过。

Migration：拟006仅保存 receipt/packet refs；现存schema hash不改。冻结contract：需要人工批准新 BrainPacket 1.1 或独立ResearchInputBundle；推荐独立版本BrainPacket1.1+AdmissionReceipt，不冒充v1.0。

用户决定：需要批准新协议版本；不是批准改变策略或审批规则。证据：`src/baseline/gates.mjs` / `src/data/snapshot.mjs` / `contracts/v1/BrainPacket.schema.json` / `docs/closure/boundary-inspection.json`。

### C05 Feature/Card 输入、namespace 与 outcome 隔离必须端到端绑定

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：runReplay 已严格绑定 last_close；尚无通用研究导入链。MAE/MFE/path/future marks 是回放outcome，不是decision Feature。 模型可携带自封feature、新增来源、其他strategy或未来收益标签入Card。

影响：Research—会：事实/namespace/未来标签污染；回测—会：目标泄漏与交叉策略污染；真实执行—会：误导信号。

模块：packet adapter；research import validator；feature provenance projection。验收：feature/source/snapshot/cutoff/version不一致拒绝；返回新证据ID只 quarantine，不升级trusted；未来outcomes/拒绝标题不输出；CORE/EVENT/RESEARCH交叉拒绝，RESEARCH无订单。

Migration：拟006记录derivation/projection refs；不导入新研究业务表。冻结contract：新增draft/projection binding合同；ResearchCard/Signal/Approval/OrderIntent旧合同不回改。

用户决定：不需真实参数；拟draft只能非交易、未知scores/grade/policy保持UNSET。证据：`src/p1a/replay.mjs` / `src/p1a/metrics.mjs` / `contracts/v1/FeatureSet.schema.json` / `contracts/v1/ResearchCard.schema.json`。

### C06 Freshness、覆盖范围与 invalidation 必须按消费用途强制

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：verifyDataSnapshot 证明冻结cutoff的闭包；没有当前Research消费时间/freshness参数。历史合法不等于当前实时信号可用。 越日/越年calendar、陈旧状态/许可或旧receipt可能被复用；一刀切wall-clock TTL也会误杀合法历史研究。

影响：Research—会：实时上下文失效；回测—会：若把当前状态回填历史，污染PIT；真实执行—会：stale信号。

模块：admission receipt consumer；calendar/security policy；future signal adapter。验收：历史cutoff验证与current-context freshness分开；过calendar覆盖/缺最新状态拒绝；许可撤销/新ref/schema/code/purpose变化旧receipt拒绝；实时市场5秒边界沿原规则保留。

Migration：拟006追加失效事件；不修改冻结历史。冻结contract：新 receipt含purpose/cutoff/coverage/validity/policy refs；不得给P0对象伪造新ACTIVE状态。

用户决定：实时/财报/公告不同freshness政策未指定部分保持UNSET；fixture显式规则不变。证据：`src/data/snapshot.mjs` / `src/data/calendar.mjs` / `src/baseline/gates.mjs` / `docs/P1A-Gate-Review.md`。

### C07 Cost-before-Candidate 与真实费用未知禁适用性结论

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：独立cost API已存在，Candidate语义需要cost_ref；还没有保证先计算费用再准入的真实producer。 模型可用synthetic费用声称适合实际账户或产生tradeable候选。

影响：Research—会：净Edge/可负担性结论失真；回测—会：毛收益被当成费用后结果；真实执行—会：费用/资金门禁绕过。

模块：拟candidate admission boundary；src/cost/index.mjs；config/account-profile.unconfigured.v1.json（不改）。验收：missing/UNSET真实fee或account时拒绝真实suitability与tradeable；synthetic明确LABEL且禁止晋升；验证cost计算先于candidate admission；三种Edge拒绝码及独立minimum不回退。

Migration：纯validator不需migration；审计沿拟006。冻结contract：若需记录suitability status新增wrapper；不向旧Candidate schema塞自由字段。

用户决定：所有真实fee/本金/Edge/sizing政策继续UNSET，无需用户现在填值。证据：`src/cost/index.mjs` / `src/contracts/validate.mjs` / `src/p1a/edge.mjs` / `contracts/v1/CandidateEligibility.schema.json`。

### C08 MANUAL_EXPORT/研究导入必须不可执行，LLM不能认证人工

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：当前无broker路径、PROD拒绝；未来LLM输出导入producer尚无E2E。 自然语言或模型自报HUMAN approval被当成订单/许可。

影响：Research—会：研究输出越权；回测—会：未经批准策略被执行；真实执行—会：直接真实订单（当前关闭）。

模块：manual export/import boundary；approval validator；production lock。验收：模型返回BUY/APPROVE/HUMAN_USER/OrderIntent均不能写order/approval；两人工阶段仍独立；PROD调用拒绝，broker transport无能力；manual fixture完整roundtrip仅产非交易draft。

Migration：receipt/import audit可用拟006，不建broker表/transport。冻结contract：新 ResearchDraft 非交易DTO；旧HUMAN双阶段合同不改。

用户决定：批准 Closure fixture export验证，不等于 APPROVE_P1B/允许模型调用。证据：`src/baseline/gates.mjs` / `src/paper/index.mjs` / `tests/p1a-production-lock.test.mjs`。

### C09 研究包字段最小化，拒绝 arbitrary payload 与内部raw路径

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：现有audit脱敏有明确非DLP边界；未来研究包不能只靠敏感键regex。 泄露账户标识、raw路径、secret/future元数据；模型获得quarantine线索。

影响：Research—会：隐私/输入隔离污染；回测—会：未来元数据泄漏；真实执行—会：credentials风险。

模块：manual export allowlist；audit producer；receipt refs。验收：白名单拒绝未知字段/嵌套secret/内部路径/真实account号；refs只能经许可允许的摘要/结构化值；未知许可不能导出原文/摘要；日志也无blocked标题/IDs。

Migration：一般无migration；导出审计refs沿006。冻结contract：新export/draft合同明确字段；原AuditChainEvent不改。

用户决定：需要用途许可规则；未知保持阻断；不读取真实credentials做测试。证据：`src/p1a/audit.mjs` / `docs/independent-review-p1a.md` / `contracts/v1/BrainPacket.schema.json`。

### C10 Closure新增代码与冻结实现的版本/测试协议需先确定

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：当前CodeProvenance枚举全部实现/测试文件，新增代码会使8cca360 pin失效；不能在新candidate继续声称旧CodeVersion有效。 编辑旧release、忽略新文件、改扩展名躲pin或强行保持旧hash，会破坏证据。

影响：Research—会：输入代码身份错误；回测—会：回放不可解释；真实执行—会：审批/版本复用。

模块：parent release/version owner；code-provenance/phase verification；artifact index。验收：旧tag完整恢复并校验冻结bytes；新candidate实际commit/source-map覆盖所有新/改文件；新release独立版本且不改旧release/provenance；旧语义Golden均保留，版本变更必须可解释。

Migration：仅按获批追加006；不回改001–005。冻结contract：建议closure release1.2.0，旧v1/p1a1.1保留；Brain新合同单独批准。

用户决定：需要批准release/协议演进方案；不可通过放宽来源/费用/审批断言迁就旧hash。证据：`src/p1a/code-provenance.mjs` / `scripts/verify-p1a.mjs` / `contracts/release.p1a.json` / `config/p1a/code-provenance.json`。

### C11 12项P1B_READINESS_GATE必须有新端到端证据与独立审查

分类：`MUST_CLOSE_BEFORE_P1B`（待批准）。

原因与不修风险：现有Reviewer审的是P1-A实现，不能替尚不存在的consumer、权限、manual adapter背书。 仅凭209测试或未来承诺放行研究。

影响：Research—会：入口未验证；回测—会：可信性缺口；真实执行—会：生产边界未证。

模块：parent integration；approved DA/PH；independent reviewer（批准后）。验收：12项readiness矩阵逐条负向攻击；25类Golden不回退且0FAIL；批准边界同snapshot重复导出/导入一致；旧hash/code/许可/bytes变更拒绝；reviewer只读且notes实际hash。

Migration：沿批准migration；无额外功能DDL。冻结contract：所有新版本由总控冻结；review不改业务规则。

用户决定：Closure Plan批准后才开工；最终仍须显式APPROVE_P1B。证据：`docs/closure/readiness-matrix.json` / `docs/closure/golden-test-matrix.json` / `docs/independent-review-p1a.md`。

### C12 真实完整官方security/master/status历史未完成

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：先保证入口只能使用已准入的明确symbol/date/board覆盖，完整全市场历史可分源分批补完。 把缺证券/历史状态当正常会污染公司/候选身份。

影响：Research—若越coverage会；允许范围内并已认证时不污染；回测—会影响survivorship/status PIT；真实执行—必须交易前认证。

模块：src/data/security.mjs；source-specific security parser。验收：改名/退市/ST/停牌/lot变更与版本冲突PIT；当前状态不能回填历史；缺覆盖symbol拒绝。

Migration：优先沿003对象追加；通常不需DDL，需新索引则追加新号。冻结contract：旧SecurityIdentity不改；真实policy需新receipt refs。

用户决定：真实feed/provider/license尚UNSET；批准fixture-only无需补全真实主数据。证据：`docs/P1A-Gate-Review.md` / `src/data/security.mjs`。

### C13 全年calendar与当前各板块session规则未认证

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：无须先补全所有年份才能验证fixture reader；真实用途所需区间必须完整，超界仍拒绝。 2019参考被误用为当前完整规则或使用工作日猜交易日。

影响：Research—超覆盖会；回测—会：session/T+1/窗口计数错；真实执行—会：交易状态错。

模块：src/data/calendar.mjs；official calendar/session adapters。验收：闰年/跨年/长假/板块sessions版本；覆盖缺一天拒绝；current规则来源与生效期证据。

Migration：沿003追加calendar版本；暂不需新DDL。冻结contract：旧calendar projections不改；新coveragepolicy refs。

用户决定：当前真实calendar准入政策/来源证据未确认。证据：`docs/p1a-data.md` / `tests/fixtures/p1a-data/public-capture.json`。

### C14 真实历史available_at/可信时间证明尚无

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：C03先保证不证明就阻断；真实历史研究用途开放前逐source批准证明，不要求凭空补过去时间。 今天抓取回填旧cutoff，产生虚假的历史研究表现。

影响：Research—若使用未证历史会；回测—会：前视；真实执行—会：输入错。

模块：src/data/source.mjs；approved clock mapping/archival authority。验收：未经批准SOURCE_FIELD拒绝；signed/archive/source proof与raw严格绑定；区分observed/reconstructed标签；晚retrieval不得冒充observed。

Migration：源proof可沿003/拟006追加；不写旧时钟。冻结contract：新proof/policy版本，P0四时钟不改。

用户决定：真实许可/时钟证据仍UNSET，人工批准范围也不能制造过去available_at。证据：`docs/p1a-data.md` / `src/data/source.mjs`。

### C15 真实bars slice缺clock/license/preclose，真实可研究snapshot为0

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：当前阻断正确。可在P1-B数据接入子里程碑补合法完整source，之前只用fixture。 把两条抓到的日线当可交易研究数据。

影响：Research—会：若绕过阻断；回测—会：行情不完整；真实执行—会：报价/费用结论失真。

模块：source-specific bars adapter；market DQ。验收：原2条reference继续BLOCKED；授权+时钟+preclose/证券/日历均完整才允许明确用途；raw decimal lexeme保留。

Migration：沿003，非全历史导入。冻结contract：旧DataEnvelope不改；新增source mapping须版本化。

用户决定：需要真实授权source选择/用途证据；当前不要求支付/账号或新抓取。证据：`docs/closure/data-admission-matrix.json` / `src/data/market.mjs`。

### C16 真实corporate-action feed与跨来源factor对账未完成

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：必须先禁止未认证adjusted/事件相关feature；全面feed补完属于后续按需求的数据接入。 未来factor或错分红/送配可改变历史价格/结论。

影响：Research—若消费该feature会；回测—会：复权/回报污染；真实执行—会：持仓状态错。

模块：src/data/market.mjs；action/feed parser。验收：源action/factor/hash/ex-date可见性；缺action完整性不得称无事件；跨source不一致quarantine。

Migration：沿003 action/adjustment追加；新entitlement表另行提案。冻结contract：旧price-basis/lineage不改。

用户决定：真实feed/licensing/方法继续UNSET；批准前只fixture结构测试。证据：`docs/P1A-Gate-Review.md` / `src/data/market.mjs`。

### C17 真实adjustment math / entitlement reconciliation未实现

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：研究窗口不消费调整/权益未认证结果可以继续工程；将其用于真实回测前必须补。 错误factor/分红权益影响价格路径、收益和NAV。

影响：Research—估值/回报若使用会；回测—会：特别是跨公司行动PnL；真实执行—会：权益账本。

模块：approved adjustment math；future entitlement ledger；backtester。验收：split/bonus/rights/dividend现金及股数精确对账；ex-date前拒绝未来结果；方法版本变化失效。

Migration：若权益lot/现金事件落库需另行追加（不是本轮006自动包含）。冻结contract：需单独提案新权益合同，禁止更改旧Fill/Ledger语义。

用户决定：真实权益/复权口径需用户/权威source确认；不在本Closure偷偷实现。证据：`docs/P1A-Gate-Review.md` / `docs/adr/ADR-005-adjustments.md`。

### C18 真实financial parser/修订样本/source admission未实现

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：修订机制已通过，但真实财务输入使用前必须按field/source准入；不要求一次完成所有报表历史。 今日修订或错误单位混进旧公司研究。

影响：Research—会：财务逻辑错；回测—会：revision leakage；真实执行—会：Card错。

模块：src/data/market.mjs；real financial parser。验收：真实原报/重述/源更正样本；单位CNY/cents精确；先cutoff后latest；缺财务样本feature不输出。

Migration：沿003追加revision，通常不改DDL。冻结contract：旧financial数据语义不改；receipt覆盖声明新增。

用户决定：真实license/报告时间/字段口径未确认。证据：`docs/P1A-Gate-Review.md` / `src/data/market.mjs`。

### C19 DATE_ONLY历史重构政策未批准

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：不能由工程师任选次日午夜/工作日。C03先禁无policy的使用，真实重构待后续审批。 伪造时钟或盲目升级P0 synthetic reconstruction。

影响：Research—会：历史前视；回测—会：cutoff错误；真实执行—会：过期消息。

模块：source clock policy；calendar adapter。验收：无版本化policy/官方session不允许重构；下一实际session边界fixture；reconstructed不会冒充observed。

Migration：使用policy记录，无需覆盖旧对象。冻结contract：P0reference规则不改；真实policy单独版本化。

用户决定：需要业务确认真实DATE_ONLY规则与证据，保持UNSET。证据：`docs/p1a-data.md` / `src/contracts/validate.mjs`。

### C20 行业成员、名称/sector PIT和真实长期验证数据未齐备

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：P1-A只最小slice，不代表交接文档5年等历史需求已满足；全样本扩展在研究/验证阶段。 survivorship、现名现行业回填过去，短强市样本冒充OOS。

影响：Research—会：板块研究污染；回测—会：有效性虚假；真实执行—会：结果误导。

模块：sector history adapter；research data store；backtest dataset builder。验收：历史成员/退市/版本PIT；数据coverage/censoring标记；walk-forward训练验证严格隔离。

Migration：视新sector/news/announcement索引需求另行追加；非本Closure批量迁移。冻结contract：冻结namespace/SoT历史要求不变。

用户决定：真实数据provider/coverage/授权未定；不得以fixture代历史承诺。证据：`正式交接文档数据深度/sector_membership要求` / `docs/P1A-Gate-Review.md`。

### C21 真实指标使用/校准样本覆盖未确认

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：已有daily retrospective实现不是未来风险预测。P1-B若需要预测/分层证据必须另做样本方法。 以MAE/MFE定义直接产概率或未来drawdown结论。

影响：Research—会：未校准预测；回测—会：outcome泄漏；真实执行—会：风险误导。

模块：research metrics consumer；future calibration（明确批准后）。验收：outcome与decision Feature物理分离；不足窗口null；真实样本分层/coverage/OOS标签。

Migration：沿后续research artifact记录，不改当前metrics表/结果。冻结contract：PathMetrics1.0保留；预测合同若需要单独版本。

用户决定：概率校准/质量时点政策保持UNSET；本Closure不实现。证据：`src/p1a/metrics.mjs` / `docs/adr/ADR-011-economic-replay.md`。

### C22 Research-store/Brain业务producers、评分与概率/Edge准入政策尚未实现

分类：`MAY_DEFER_TO_P1B`（待批准）。

原因与不修风险：P1-B才负责研究工程；Closure只证明非交易输入/输出边界，不能偷偷开Quality/Timing/Grade参数优化。 把示例阈值或multiple2/模型判断当已校准规则。

影响：Research—会：研究有效性无证；回测—会：优化偏差；真实执行—会：不当sizing/净Edge。

模块：未来research-store/brain-adapter/candidate-engine；approved calibration tasks。验收：未知评分/概率/净Edge/准入policy保持UNSET且不能交易；真正calibration另里程碑OOS测试；RESEARCH长周期不直接驱动CORE买单。

Migration：后续research producers可能用现P0表或新增版本索引，另提案。冻结contract：旧Card chain不改；draft/新增研究版本总控批准。

用户决定：需要后续APPROVE_P1B及明确评分/概率政策，不在本轮确定。证据：`docs/P1A-Gate-Review.md` / `contracts/v1/ResearchCard.schema.json` / `src/p1a/edge.mjs`。

### C23 真实PostgreSQL多连接/多进程现金并发未验收

分类：`MAY_DEFER_TO_P2`（待批准）。

原因与不修风险：纯MANUAL_EXPORT/单进程fixture研究不操作账户现金；若选择DB服务/多writer则使用前必须升级为必修。 PGlite同连接通过被误当真实多连接现金锁已证。

影响：Research—选文件边界则无；DB-backed研究需改分类；回测—并发交易回测部署会影响；真实执行—会：double spending需真实server证明。

模块：PostgreSQL integration adapter；paper transaction boundaries。验收：独立连接/进程Core+Event同时预留；隔离级别/锁超时/重试/幂等；reconcile每次精确。

Migration：部署/索引/约束需追加新号；不回改004。冻结contract：paper API契约不能悄改；新增并发协议单独版本。

用户决定：需先选文件或DB-backed拓扑；推荐文件边界后置。证据：`docs/P1A-Gate-Review.md` / `docs/p1a-paper.md`。

### C24 完整server RBAC/least privilege未部署

分类：`MAY_DEFER_TO_P2`（待批准）。

原因与不修风险：C01最小研究通道隔离仍必修；全平台角色/管理员权限体系可延期。研究若直连DB，research_read权限测试立即成为前置。 将无权限共享数据库暴露给研究，或把trigger当owner攻击防护。

影响：Research—若有直接DB访问会；文件隔离通过后不污染；回测—管理员改写证据可能污染；真实执行—会：账户/审计权限。

模块：runtime isolation；server roles/research_read/data_admin/trade roles。验收：export-only process没有raw挂载/DB凭证；DB模式需SELECT只准入视图，无raw/写/TRUNCATE/函数绕过；owner/operator威胁明确。

Migration：角色/grants/view部署可能追加006或后续；不可改旧DDL。冻结contract：角色不是放宽合同；无旧contract变化。

用户决定：部署拓扑选择影响分类；不能以延期全RBAC为由省C01。证据：`docs/P1A-Gate-Review.md` / `正式交接文档角色边界`。

### C25 备份恢复、可信storage/timestamp authority与不可变外部归档未验收

分类：`MAY_DEFER_TO_P2`（待批准）。

原因与不修风险：Git bundle/固定raw hash能恢复工程证据；长寿命外部服务的备份/可信时间不是fixture工程前置。 把本地运行clock/DB owner触发器当不可篡改时间权威或数据永存保证。

影响：Research—长寿命真实研究服务会；fixture重建则范围可控；回测—历史归档真实性与恢复影响；真实执行—会：灾难恢复。

模块：external object store；database backup/recovery；timestamp authority。验收：独立恢复raw/schema/receipt/audit全部hash；丢失对象失败；外部clock漂移拒绝；WORM/权限绕过威胁测试。

Migration：通常部署配置/归档元数据追加，另批。冻结contract：source/clock proofs不能升格；新authority合同另版本。

用户决定：真实source授权/retention规则未定，保持阻断。证据：`docs/P1A-Gate-Review.md` / `docs/baselines/P0-freeze-20261005.json`。

### C26 COMMIT前后崩溃fault injection未验收

分类：`MAY_DEFER_TO_P2`（待批准）。

原因与不修风险：普通restart/idempotency已证，单进程研究导出不承诺生产交易的崩溃恢复；receipt使用前验证完整性，半成品不得发布。 部分事务/重试重复记账或导出半包。

影响：Research—导出原子发布最小测试属于C01/C11；全面事务故障后置；回测—会：持久回测损坏；真实执行—会：账本恢复。

模块：paper service/db adapter；atomic export writer。验收：杀进程于COMMIT前/后/响应前；重启exactly-once账本/释放预留；receipt/export临时写后原子发布及损坏拒绝。

Migration：按DB能力另行追加；不要重写旧账本。冻结contract：生命周期语义不放宽；故障协议可新版本。

用户决定：不需要真实资金参数；外部部署另授权。证据：`docs/P1A-Gate-Review.md` / `tests/p1a-paper.test.mjs`。

### C27 持续数据健康监控/高频watcher/实时feed恢复未做

分类：`MAY_DEFER_TO_P2`（待批准）。

原因与不修风险：消费时stale/缺source拒绝C06必修；常驻健康监控、通知和秒级watcher非manual研究Closure范围。 断流后用旧值冒充最新，或告警风暴。

影响：Research—实时研究会；历史fixture不污染；回测—实时报价/撮合会；真实执行—会：数据陈旧。

模块：future watcher/collector monitor；signal feed health。验收：断流/恢复/sequence gap均NO_NEW_ORDERS；去重/限频；消费stale拒绝先保留。

Migration：后续health/state schema视需求追加。冻结contract：现freshness语义不变。

用户决定：不确定新增时间阈值不猜；现明示5秒边界保留。证据：`docs/P1A-Gate-Review.md` / `src/baseline/gates.mjs`。

### C28 Paper SELL全额费预留使零available cash全仓不能退出

分类：`MAY_DEFER_TO_P2`（待批准）。

原因与不修风险：限定reference/fixture演示可保留；若下一阶段承诺策略执行评价或退出可行性，则必须提前修并批准费用结算语义。 risk exit无法执行，产生虚假持仓/净收益统计或把保守限制当券商规则。

影响：Research—会影响交易建议可行性；非交易draft不承诺可卖；回测—会：不能当真实策略matcher；真实执行—会：不能推广真实行为。

模块：src/paper/index.mjs；src/paper/oracle.mjs；future settlement profile。验收：零现金SELL/partial/cancel/fee-from-proceeds/极端费用；lot预留/T+1/资金顺序；oracle独立核账；不能破坏旧fixture解释。

Migration：如需proceeds担保/reserve类别，追加新迁移/版本，非本Closure默认006。冻结contract：可能新 settlement/reservation contract；不悄改旧PER_ORDER reference。

用户决定：真实券商结算映射未定；延期只代表保留限制，不代表认可为规则。证据：`docs/p1a-paper.md` / `docs/P1A-Gate-Review.md`。

### C29 真实tick/涨跌停/流动性/停牌撮合与minute-level执行模型未实现

分类：`MAY_DEFER_TO_P2`（待批准）。

原因与不修风险：Paper LIMIT fixture不是完整A股撮合；研究工程无需马上补全部matcher，但不能称能交易或可信策略PnL。 不可能成交/滑点误差被当收益；最低手与零股边界错误。

影响：Research—若声称买点执行优势会；回测—会：费用后策略有效性；真实执行—会：订单合法性。

模块：future market microstructure/matcher；security capability mapping。验收：tick/价格笼子/涨跌停/停牌/零股/量能/部分撮合；高低滑点固定输入对比。

Migration：按真实规则索引另行追加。冻结contract：不得自行填tick/broker规则；新matcher协议版本。

用户决定：真实板块/订单类型规则和来源需确认。证据：`docs/p1a-paper.md` / `contracts/v1/SecurityIdentity.schema.json`。

### C30 20日真实forward Paper未验收

分类：`MAY_DEFER_TO_P2`（待批准）。

原因与不修风险：现实验只有fixed synthetic输入，不是forward paper；属于后续真实数据与运行安全验收。 两日模拟/legacy replay被当长期上线证据。

影响：Research—不验证研究alpha；回测—会：真实forward claim无证；真实执行—生产必须完成后续验收。

模块：future forward-paper runner；daily audit/reconcile。验收：连续>=20真实sessions按已获批规则；每日费用/现金/持仓核账；异常fail closed与恢复。

Migration：使用后续paper运行表/manifest；不迁移旧runs。冻结contract：新run来源/许可scope明确。

用户决定：真实source准入与Paper范围需后续批准，不需现在真实账号值。证据：`docs/P1A-Gate-Review.md` / `正式交接文档Paper验收`。

### C31 生产部署/备份运维、完整GUI、L2/高频基础设施未建

分类：`MAY_DEFER_TO_P2`（待批准）。

原因与不修风险：与数据准入文件通道不构成必然依赖；C01最小隔离可独立交付，不能为Closure扩成平台工程。 过早接账户或开发主体GUI，偏离授权范围。

影响：Research—当前不污染，若越权接source会；回测—不是当前测试有效性前提；真实执行—真实运营需部署验收。

模块：future deployment/gui/watcher（本轮不启动）。验收：之后按正式交接验收；本轮验证模块/transport缺省关闭。

Migration：本轮无此DDL；后续明确编号。冻结contract：不改变SoT总体目标，延期不等于删除。

用户决定：需要后续阶段显式授权；Kubernetes/service mesh不是当前要求。证据：`docs/P1A-Gate-Review.md` / `正式交接文档部署/GUI要求`。

### C32 真实account/capital/budgets/risk/frequency参数未配置

分类：`PROD_ONLY_BLOCKER`（待批准）。

原因与不修风险：30项AccountProfile未知不妨碍纯fixture研究，但不允许真实sizing或适合账户判断。 继承旧5000/6000/10000或3000/8000、旧loss限制。

影响：Research—会：若谈真实账户适用性；回测—真实组合回测参数无效；真实执行—必须阻断。

模块：config/account-profile.unconfigured.v1.json；future account-risk gate。验收：所有required叶缺失/null/NaN/UNSET均fail closed；真实适用性声明拒绝；fixture不能改profile_kind升格。

Migration：本轮无账户状态迁移。冻结contract：AccountProfile1.0原字节保留；新增未知不猜。

用户决定：不要求现在填值；真实account设置保持UNSET。证据：`config/p1a/unset-required.inventory.json` / `tests/p1a-production-lock.test.mjs`。

### C33 真实券商费率/范围/inclusion/slippage/rounding/effective period映射未认证

分类：`PROD_ONLY_BLOCKER`（待批准）。

原因与不修风险：Synthetic PER_ORDER和日期边界不是券商事实。C07保证未知时不给真实净Edge结论；正式费用接入生产前核验。 错误minimum/手续费重复/税费日期或成交结算偏差。

影响：Research—会：真实净Edge/affordability失真；回测—真实策略费用后统计会；真实执行—必须阻断。

模块：future broker-cost mapper；cost verifier。验收：按交割单边界/partial/cancel/minimum/收费范围/日期/rounding核账；比对independent oracle；未知字段拒绝。

Migration：真实profile版本追加，需表另批。冻结contract：新broker profile/version；旧synthetic不可升级default。

用户决定：所有真实费用继续UNSET，不猜 statutory/rate配置。证据：`docs/p1a-paper.md` / `config/account-profile.unconfigured.v1.json`。

### C34 真实交割单/费用/持仓现金对账未做

分类：`PROD_ONLY_BLOCKER`（待批准）。

原因与不修风险：reference oracle只证明synthetic实现，不证明实际券商结算。 engine精确但映射错误，真实账户/费率不可信。

影响：Research—不允许真实账户适用性；回测—会：真实费用/成交回测口径；真实执行—必须阻断。

模块：future statement import/reconcile；broker capability checker。验收：read-only脱敏交割单对gross/全部fees/cash/lot；差异NO_NEW_ORDERS；原始证据hash/version保留。

Migration：只在另授权后staging/statement表追加，不导入旧状态库。冻结contract：新broker证据DTO；当前Fill/Cost旧语义不回改。

用户决定：需要后续真实账户证据授权；本轮不读取credentials/账号/交割单。证据：`docs/P1A-Gate-Review.md` / `正式交接文档费用与交割单验收`。

### C35 真实sizing与账户总risk enforcement未实现

分类：`PROD_ONLY_BLOCKER`（待批准）。

原因与不修风险：共享现金检查不等于sector/daily loss/drawdown/budget全账户risk engine。 策略各自有现金但账户总风险越界。

影响：Research—会：真实仓位建议；回测—会：真实portfolio回测；真实执行—必须阻断。

模块：future account risk/sizing engine。验收：共享策略budget+sector+drawdown+loss+margin+frequency组合边界；未知风险全部拒绝。

Migration：risk状态/事件另行追加。冻结contract：新risk/sizing合同需审批；旧namespace和account共享约束不变。

用户决定：用户风险政策、真实阈值全部UNSET。证据：`docs/P1A-Gate-Review.md` / `config/p1a/unset-required.inventory.json`。

### C36 真实用户认证与双人工审批权限未实现

分类：`PROD_ONLY_BLOCKER`（待批准）。

原因与不修风险：synthetic authority只为fixture。研究返回可记录为untrusted draft，不能认证任何真实操作人。 模型自报/本地共享会话被当真实用户批准。

影响：Research—会：研究输出越权；回测—未经批准决策replay可能混淆；真实执行—必须阻断。

模块：future user auth/approval authority。验收：用户会话认证/权限/过期/两阶段terms绑定；LLM永不HUMAN；明确修改后批准失效。

Migration：真实auth/approval状态另授权后追加。冻结contract：冻结Approval双阶段保持；真实authority协议另批。

用户决定：真实角色/认证方式后续确认，无需现在账户参数。证据：`src/baseline/gates.mjs` / `docs/P1A-Gate-Review.md`。

### C37 真实broker gateway与接入/适用义务确认未完成

分类：`PROD_ONLY_BLOCKER`（待批准）。

原因与不修风险：P1-B研究无需broker transport；当前不得接入。 自然语言/准备订单越权发送真实委托。

影响：Research—不需要broker；回测—真实成交验证需后续授权；真实执行—必须阻断。

模块：future execution-gateway（本轮禁止）。验收：只在正式生产评审后能力授权/幂等/人工确认/拒绝回报；无凭证默认不可达。

Migration：真实broker表/transport另阶段，不占本Closure迁移。冻结contract：OrderIntent/Approval链不得改；接入capability单独审批。

用户决定：broker/account/适用接入要求UNSET，后续权威确认。证据：`docs/P1A-Gate-Review.md` / `正式交接文档HUMAN_CONFIRM边界`。

### C38 production Kill Switch/NO_NEW_ORDERS部署未验收

分类：`PROD_ONLY_BLOCKER`（待批准）。

原因与不修风险：现productionGate永久false比临时KillSwitch更严格；研究阶段不能为了验收去打开实盘。 真实断线/错仓位/风险破限未自动禁止新单。

影响：Research—研究不需要实盘开关；回测—真实运行模拟需后续验收；真实执行—必须阻断。

模块：future production ops/gateway/health policy。验收：断线/stale/costunset/reconcilefail/unknownstatus/risklimit均禁止新单；恢复人工条件/审计。

Migration：ops状态另阶段追加。冻结contract：冻结production=false不更改；未来开prod另新授权/新版本。

用户决定：生产风险/上线授权UNSET；本轮保持false。证据：`src/baseline/gates.mjs` / `tests/p1a-production-lock.test.mjs`。

### C39 真实credentials/账户敏感数据与生产密钥分发未设置

分类：`PROD_ONLY_BLOCKER`（待批准）。

原因与不修风险：本轮无读取/提交；研究环境必须无prod密钥，C09出口白名单先完成。 dev/research拿到prod权限或日志保存完整账户号。

影响：Research—会：隐私与越权；回测—不是fixture验证需要；真实执行—必须阻断。

模块：future secret storage/auth；export/log minimization。验收：dev/paper无法读prodsecret；leastpriv旋转/吊销/审计；真实标识不进入packet/日志。

Migration：本轮无credentials表/导入。冻结contract：不在schema给真实secret字段；权限政策后续版本。

用户决定：不索取真实credentials；安全部署后续授权。证据：`docs/P1A-Gate-Review.md` / `AGENTS.md`。

### C40 Legacy native CLI hash mismatch继续保留

分类：`ACCEPTED_KNOWN_LIMITATION`（待批准）。

原因与不修风险：已知兼容失败不是V1安全输入来源；保留原seal/ledger资产比改旧证据更重要。 伪造PASS或覆盖seal/账本破坏审计。

影响：Research—隔离后不污染；不允许research复用旧实验假设；回测—旧资产只能regression fixture，非策略有效性；真实执行—不作为production输入。

模块：legacy manifest/adapters（不修改、不运行旧策略）。验收：本轮只校验manifest/reports hash；未来compatibility修复只能新adapter/version，旧seal保持。

Migration：无legacy迁移。冻结contract：原manifest/seal不修改。

用户决定：建议接受兼容限制，不代表历史盈利/PIT认证；不需修旧CLI。证据：`docs/baselines/P1A-legacy-native-compatibility.json` / `legacy/asset-manifest.v1.json`。

### C41 DAILY_APPROXIMATION与retrospective metric定义

分类：`ACCEPTED_KNOWN_LIMITATION`（待批准）。

原因与不修风险：已有明确窗口、缺数据null/INCOMPLETE、entry-day约定；不是minute路径。 把未来outcome当预测/持有全路径或伪分钟数据。

影响：Research—C05隔离后可作历史结果；不能直接预测；回测—日线近似需声明，缺窗不压缩；真实执行—不能当未来风险保证。

模块：src/p1a/metrics.mjs（保持）；future research outcome boundary。验收：旧窗口/负timezone/缺session/entry规则保留；packet不得携带未来指标作为feature。

Migration：无修改005 metrics数据。冻结contract：PathMetrics定义保持1.0；新resolution另版本。

用户决定：建议接受日线近似范围；概率预测政策仍UNSET。证据：`docs/adr/ADR-011-economic-replay.md` / `docs/experiments/P1A-results.json`。

### C42 Experiment A/B只有synthetic工程意义

分类：`ACCEPTED_KNOWN_LIMITATION`（待批准）。

原因与不修风险：gross相同/摩擦递增/Edge拒绝证明工程机制；固定信号不是选股或策略回测。 把正净收益、multiple2或短持有交易当CORE策略有效。

影响：Research—不能证明研究alpha；回测—不能称OOS/生产收益；真实执行—不能据此开资金。

模块：experiment artifacts（不重跑优化）；report labels。验收：八字段一致/hash mutation证据保留；固定signals/qty/prefill；Edge OFF/ON区分/拒绝码；不改实验以美化收益。

Migration：无迁移。冻结contract：保留旧experiment.json/report/hash；新版本产生新结果另存。

用户决定：建议接受实验范围，不批准任何真实threshold/alpha。证据：`docs/experiments/P1A-results.json` / `docs/adr/ADR-012-experimental-edge.md`。

### C43 现有fixtures与有界reference只证明小范围能力

分类：`ACCEPTED_KNOWN_LIMITATION`（待批准）。

原因与不修风险：五source、2条bar、有限calendar/synthetic41sessions不是完整真实市场coverage；真实snapshot准入为0。 将有限证据扩大成全年/全市场/历史available认证。

影响：Research—fixture-only不得称真实研究；回测—不能替5年/多市场样本；真实执行—不能交易准入。

模块：fixture/source manifest（保留）；admission coverage policy。验收：所有输出显式scope/coverage；越界拒绝；public references不能送LLM可交易研究输入。

Migration：无新历史导入。冻结contract：不把SYNTHETIC scope修改成OBSERVED；C02修复入口。

用户决定：建议接受有界证据范围；真实消费须另批准具体source/domain。证据：`tests/fixtures/p1a-data/public-capture.json` / `tests/fixtures/p1a-replay/experiment.json`。

### C44 clean验证为darwin/arm64且optional external legacy test skip

分类：`ACCEPTED_KNOWN_LIMITATION`（待批准）。

原因与不修风险：已实测clean install/check，portable测试不需要旧宿主。跨平台不是当前Gate硬要求。 声称远端CI/所有系统通过，或把skip算通过/新run。

影响：Research—不直接污染；回测—跨平台精度需之后实测；真实执行—真实部署仍P2/Prod blocker。

模块：artifact index；CI docs（不虚报远端run）。验收：核验原日志SHA/counts；skip原因明确；新candidate按实际平台clean复现，失败不得掩盖。

Migration：无迁移。冻结contract：无合同变化。

用户决定：建议接受平台边界；本轮复用日志而不假造新210 run。证据：`docs/baselines/P1A-clean-reproduction-20261005.json` / `docs/closure/golden-test-matrix.json`。

### C45 最坏partial rounding导致BUY reserve高于整单affordability

分类：`ACCEPTED_KNOWN_LIMITATION`（待批准）。

原因与不修风险：保守预留保证不透支；亚分fixture差异明确。不能为了买得起放宽资金门禁。 忽略部分成交rounding会双花/透支；把保守行为当真实券商要求。

影响：Research—真实执行适用性不得声称；回测—模拟可行性需说明；真实执行—真实tick/结算映射需另证。

模块：src/cost/index.mjs；src/paper/index.mjs（保持）。验收：整单20000 vs split20002例核账；reservation不足拒绝；partial最低佣金delta不double count。

Migration：无本轮迁移；以后真实reserve政策另版本。冻结contract：旧money/rounding不变。

用户决定：建议接受fixture保守界限；真实broker规则UNSET。证据：`docs/p1a-paper.md` / `docs/independent-review-p1a.md`。

### C46 synthetic cost生效区间两端包含，P0 harness旧语义不同

分类：`ACCEPTED_KNOWN_LIMITATION`（待批准）。

原因与不修风险：两个reference协议版本明确；不统一改旧contract或误映射真实券商。 off-by-one费率切换或悄改历史测试。

影响：Research—真实成本未知不可用该结论；回测—历史profile须按绑定版本；真实执行—真实费用需要C33。

模块：cost version registry（保持）；future mapper。验收：两个reference各自原边界PASS；跨version复用拒绝；真实有效期未知拒绝。

Migration：无本轮迁移。冻结contract：不回改P0/当前synthetic profile；真实版本另批。

用户决定：建议接受reference语义差异，不批准真实broker区间。证据：`docs/contracts-p1a.md` / `docs/p1a-paper.md`。

### C47 审计脱敏不是完整DLP、trigger不是DB owner防篡改承诺

分类：`ACCEPTED_KNOWN_LIMITATION`（待批准）。

原因与不修风险：已有递归敏感键/常见secret攻击防护；生产producer/权限仍需加严，研究export C09白名单先落实。 任意未标注秘密或管理员绕过可泄露/改写。

影响：Research—结构化出口通过后范围可控；回测—证据管理员恶意修改不是当前保证；真实执行—真实权限/日志最小化仍Prod blocker。

模块：audit producer；export allowlist；future RBAC。验收：原secret/ref攻击与九表非owner TRUNCATE保护保留；export白名单定点反例；不声称能对抗拥有全盘权限的管理员。

Migration：无旧audit重写；新receipt审计append-only。冻结contract：原Audit合同不放宽。

用户决定：建议接受已明示威胁模型；C01/C09不是可延期项。证据：`docs/independent-review-p1a.md` / `src/p1a/audit.mjs`。

## E. P1B_READINESS_GATE当前逐项判断

这里评的是未来研究入口，不是给已通过的底层Golden改判。两个PASS是现有禁止生产/无broker能力的事实；它们在新Closure candidate仍须回归验证。其余10项有些底层guard已通过，但consumer证据尚不存在，不能给完整要求PASS。

| ID | 要求 | 当前 | 原因/待验收 |
|---|---|---|---|
| R01 | Research无法读取QUARANTINED | FAIL | 已有data closure拒绝quarantine；不存在强制consumer入口/隔离运行验收。 |
| R02 | Research无法读取future-invalid | FAIL | 已有PIT机制Golden；未实现研究export/import时cutoff复核。 |
| R03 | 只能引用验证且用途准入的SnapshotManifest | FAIL | 低层verifier不认证许可/真实性；synthetic→OBSERVED反例可通过低层校验。 |
| R04 | Card输入可追踪source/raw/hash/time/version | FAIL | 已有source→snapshot→reference Feature→Cost→Replay链；正式Card producer/导入链尚无。 |
| R05 | 研究输出不能直接产生订单 | FAIL | 基线无transport且reference只可PAPER；新的模型导入/订单字段负向链未实现。 |
| R06 | LLM approval不是人工批准 | FAIL | 冻结Approval schema与两HUMAN authority检查已通过；新研究ingress尚无端到端负向证据。 |
| R07 | CORE/EVENT/RESEARCH namespace隔离 | FAIL | 现contract/SQL/Paper隔离已通过；新packet/import链的namespace交叉需验收。 |
| R08 | Cost Engine在Candidate admission前运行 | FAIL | 独立cost API可用；实际候选producer的前后顺序尚无。 |
| R09 | 费用未知不能声称适合真实账户 | FAIL | 30真实参数UNSET且prod gate关闭；新研究Card/import适用性声明还需验证。 |
| R10 | productionGate保持false | PASS | 本轮实际调用未配置profile：allowed=false；冻结gate和production-lock测试字节未改。 |
| R11 | Broker transport不存在或硬禁用 | PASS | 现模块只有PAPER reference，无broker submit route；冻结实现source tree字节已核验。 |
| R12 | 纯MANUAL_EXPORT/PAPER可工作 | FAIL | 已有synthetic paper/replay；MANUAL_EXPORT真正生成/返回输入闭包adapter尚未实现。 |

机器矩阵及各项负向验收：[readiness-matrix.json](readiness-matrix.json)。当前整体 **FAIL，P1-B BLOCKED**。范围尚未批准也不能放行。以后只有明确scope内12项全部PASS、11项MUST关闭、Golden核心不变量零失败、独立审查证据完整，再由用户显式 `APPROVE_P1B` 才可启动。

## F. 仍未确定的参数与需要批准的边界

真实AccountProfile原30项未知及schema required-leaf测试原样保留；扩展的真实许可/clock/质量时点/概率/Edge/sizing/消费scope政策见 [unset-required-supplement.json](unset-required-supplement.json)。它是分析清单，不写入生产配置，不自动填默认值。当前不用填写任何真实账户值。

推荐批准的不是全功能研究，而是 [Conditional Closure Plan](Conditional-Closure-Plan.md) 中的 W1–W4，限定fixture-only的mandatory admission、manual file roundtrip、non-tradeable draft及negative tests。D01–D04需要明确处理；详细方案和Agent任务合同均在该计划中。所有真实source目前继续BLOCKED。

本轮完成分析后停止。没有批准Closure实现，也没有创建Research Agent。未生成“Closure已完成”的Gate；未来批准范围完成后才提交25项Closure Gate。
