# P1-A Gate Review — 2026-10-05

**结论：PASS_WITH_CONDITIONS。范围仅为 P1-A 离线工程基础设施。** 这是总控与独立 Reviewer 的技术验收结论，用户对本 Gate 的确认仍为 PENDING。P1-B Research Intelligence 与真实资金执行继续 BLOCKED；本轮到此停止。

正式交接文档仍是主要 Source of Truth。已确认 P0 及现状/迁移审查提供工程基线；所有真实账户、费率、风险和未校准策略政策继续 UNSET_REQUIRED。以下 synthetic 值、Paper 约束和条件项均不自动升级为生产业务规则。

## 1. P0 baseline freeze evidence — PASS

P0 annotated tag：`p0-v1.0.0-20261005`；baseline commit：`433a2e96482e5db6e2a0ea452727baf61f4c4426`。归档位于 `/Users/qiushi/投资研究/.p1a-archives/p0-20261005/p0-v1.0.0.bundle`，SHA-256：`f61c4d26173e2d1f6cd2e5462c4c1a6d8aeb625cd0d5df5a7055e03681867c23`。Bundle 已校验，并实际克隆、检出该 annotated tag 和复跑检查；不是仅建立标签。

P0 release SHA：`eee1c485838212210f646f755c0ce4c61b38b46dfd6fa1b8708a6ced1bb9b770`；001：`ed626c0d79d1d1492e77e4c89d9324f62b6acd16753be19e6264dcfaf6bcff1a`；002：`77e0e011e28ac6f8d8264d4263baed62cb6d6b7b3ea24a44292e4f43d4bf4f84`。P0 29 个冻结文件的字节保持一致。

机器证据：[P0-freeze](baselines/P0-freeze-20261005.json)。旧 seal 未修改；legacy_native_compatibility=FAIL_KNOWN_COMPATIBILITY，legacy_data_replay=PASS，legacy_ledger_reconciliation=PASS。

## 2. Clean environment reproducibility — PASS，平台边界明确

P0 从 bundle 恢复到独立 checkout、新 node_modules、新 npm cache、两份独立空 npm 配置和最小环境变量集合执行 `npm ci`、`npm run check`，均 exit 0：98 项，97 PASS、1 optional external SKIP。最初一次安装准备因 user/global npm config 指向同一文件被 npm 拒绝，测试未运行；改用两份空文件后通过，失败未隐藏。[P0机器证据](baselines/P0-clean-reproduction-20261005.json)。

P1-A 额外从候选 commit `060acfe11728ccee8022974d4794f5a262803afa` 独立 clone（no-local，不共享 Git 对象硬链接），再用新依赖目录/cache/空配置执行相同命令，均 exit 0：**210 项，209 PASS、0 FAIL、1 SKIP**。Node 24.19.0，darwin/arm64；不继承 legacy 环境或 credentials。安装需要 npm 网络，测试不需要网络/旧宿主资产。该验证证明 clean checkout/dependency 环境可复现，未声称所有操作系统或真实 PostgreSQL 部署已验收。

[P1A机器证据与日志SHA](baselines/P1A-clean-reproduction-20261005.json)；原始日志保存在 `/Users/qiushi/投资研究/.p1a-archives/p1a-candidate-20261005-060acfe/`。

## 3. Canonical SecurityIdentity — 机制 PASS；真实主数据准入未完成

Canonical 沿冻结合同统一为 `SSE:600000` / `SZSE:000001`。`sh.600000`、`sh600000`、带后缀表示保留 original_symbol；裸六位代码必须给交易所，不能按数字前缀猜测。冲突 QUARANTINE + reason + 实际 audit event；同一身份不能 silently merge。

已实现 security_id、listing/delisting、board、lot size、ST/special、suspension、有效时段与状态版本。查询先按 cutoff/四时钟/有效期过滤再选择版本，快照必须包含当时最新有效状态。真实完整官方 security master/status feed 尚未导入；synthetic registry 不冒充真实权威注册表。[实现与条件](p1a-data.md)。

## 4. Trading Calendar — 有界官方 reference PASS；历史交易准入仍受限

实际捕获沪深秋季休市公告与 session 说明原字节、URL、retrieved time、source/version/hash。官方 adapter 的覆盖仅为 2026-09-20 至 2026-10-11，包含交易/非交易日、竞价/连续交易 sessions、长假；9/30 后下一 session 为 10/8。周末处理依据捕获的交易所周规则，超出覆盖范围 fail closed，不以系统工作日猜测。

今天观察的公告副本不能证明旧 cutoff 时市场/系统已经可得；日历只 PASS_REFERENCE_ONLY。深圳 session 说明是明确标记的 2019 版本，未认证其覆盖当前全部规则/板块。全年日历、当前完整规则、可交易历史可得证明尚未完成。Paper 测试仍用显式 synthetic sessions，不能替代真实长期 T+1 日历准入。

## 5. bars_1d Raw→Normalized — 实际 slice PASS，DQ/快照阻断正常

实际 SSE display endpoint 两条 RAW 日线（2026-09-29、09-30）已经经历原字节 → source observation → staging → typed normalized → DQ。保留 source/version、raw/payload SHA、四时钟、canonical/original symbol、price basis、adjustment version、lineage、DQ 与 trace。

端点不提供 published_at / available_at / preclose，故归一化后仍 QUARANTINED / NON_TRADEABLE；Snapshot admission 返回 BLOCKED，不伪造可交易 SnapshotManifest。RAW 与 ADJUSTED 对象身份分开，不能覆盖。CI 使用已标记 public reference 原字节，不重新抓取网络。[真实捕获清单](../tests/fixtures/p1a-data/public-capture.json)。

## 6. Real-source PIT semantics — fail closed PASS；真实历史可交易 PIT 未完成

真实 collector 的 retrieved_at 由采集器实际生成；禁止 caller override，private capture capability 绑定原字节/source/retrieval。不能用 retrieved_at 给历史市场 available_at 回填。公开可访问也不等于取得交易许可。

五个源均 license_type=UNKNOWN、terms_version=UNVERIFIED、redistribution_allowed=false，实际行情 available_at=null。REFERENCE_DOCUMENT 的 observation clock 只证明当时观察到副本；SOURCE_FIELD 映射目前仅允许 synthetic。没有获准真实历史市场快照；真实 license、可得时间语义与可信归档权威仍是条件项。PIT 缺失不阻塞离线工程，却继续阻塞真实模型/交易输入。

## 7. Corporate Actions / adjustment lineage — 机制 PASS；真实 feed/调整数学未完成

支持 dividend/split/bonus/rights 结构、ex/effective dates、原始 terms、factor、source/version/hash 和独立 adjustment/action refs。闭包复核实际 raw/facts/security/action、factor 可见与生效日期；ex-date 前不能看到后来生成的调整。Infinity/NaN/exponent/过精度因子被拒绝；原价与后复权对象并存。

当前接受的是明确 fixture 结构与因子，不自行计算真实价格调整、权利/现金分配或权益账本。真实 corporate action feed、跨来源 factor 对账、真实 entitlement reconciliation 尚未实现。

## 8. Financial revision PIT — 机制 PASS；真实财报 parser/sample admission 未完成

ORIGINAL / RESTATEMENT / SOURCE_CORRECTION 追加存储，修订绑定 predecessor；旧版本不能更新、删除或 TRUNCATE。查询先过滤 as_of/cutoff 和完整 source lineage，再选择当时可见 revision；今日修订不会回填旧决策。

金额保留整数分，source/raw/payload/四时钟/hash/版本可追踪。实测未来修订与晚 retrieval 隔离。真实财报来源 parser、修订样本与许可/时钟认证仍待建设。

## 9. Snapshot lineage — PASS

内容地址绑定 root refs、递归 closure refs、source facts/bytes、cutoff、feature version、rules hash。身份/状态、calendar、actions/factors、财报前序版本都必须满足 cutoff；拒绝的未来对象不污染输出 metadata/hash。重复冻结相同输入返回首个不可变快照。

每次使用必须 `verifyDataSnapshot` 读回 persisted raw/object/closure。原始 source 多一个空格字节，即使解析值不变也改变 raw/closure/data hash；旧结果、snapshot、approval binding 不可复用。不能仅对一个自声明 manifest 做 hash 后放行。[合同](contracts-p1a.md)。

## 10. Cost Engine — PASS（独立 synthetic reference）

全新费用内核不导入 V5 或 P0 经济计算；versioned synthetic CostProfile / P1ACostEstimate 支持佣金、minimum、卖出 stamp、exchange、other、slippage、包含关系、生效区间与 HALF_UP。真实费用继续 UNSET_REQUIRED。

整数分/BigInt 与私有 Decimal100；实际 commission=proportional+minimum effect，effect 仅子归因。已含在佣金的费用、已含在价格的滑点不重复计费。部分成交按累积 per-order fee 差额结算，minimum effect delta 可负。新 synthetic profile 日期两端包含；不映射为真实券商生效规则。[Cost/Paper API](p1a-paper.md)。

## 11. Affordability — PASS，精度限制明确

整手数量计算要求 gross + 全部费用 <= available cash；最低佣金边界、精确含费边界、bare notional 可买但含费不可买均测试。39 位 all-in 金额即使单项都合法也拒绝。

Paper reserve 额外覆盖最坏分拆成交分舍入；亚分价格时所需 reservation 可能高于一次整单 affordability 估计，服务会拒绝不足预留。没有因此放宽现金门禁。

## 12. Account reservation — PASS（共享现金/独立持仓）

available=settled−reserved；reserve/release/cancel/reject/partial fill 与持仓分配在事务中更新。账户行锁、唯一键和金额 CHECK 保护共享账户现金，Core/Event 不得花同一笔钱；lot/position 按 mode/account/strategy/security 分离。

同连接并发双花、并发读状态、多个卖单 lot allocation 已验证。真实 portfolio risk policy/sector/drawdown/实际 sizing 未实现或赋值；它们仍 UNSET_REQUIRED，不能把共享现金检查称作完整生产 risk engine。外部 PostgreSQL 多连接另列技术债。

## 13. Paper lifecycle — PASS（DEV/PAPER fixture DTO）

实际执行 Reserve → Submit(PAPER) → Partial/Full Fill 或 Cancel/Reject → immutable ledger → independent reconcile。重启后从持久化数据恢复 sequence、hash chain、现金、预留、lot、请求；相同 key 重放不多记账，相同 key 改 payload/重复 client/fill/终态迟到成交拒绝。

所有入口拒绝 PROD，无 broker transport。两阶段 synthetic HUMAN authority 只用于 acceptance fixture，不能替代真实登录认证，更不能接受 LLM APPROVE。生产 ResearchCard→Signal→Approval→OrderIntent 仍使用冻结 P0 chain，P1-A 没有实现其业务 producers。

**已知保守限制：SELL 预留全部预计费用，零可用现金的全仓账户无法发起卖单。** 本轮保留并公开该 reference 限制，不宣称这是券商规则；真实接入前必须另行设计、验证和确认。

## 14. Ledger reconciliation — PASS

独立 BigInt scaled-rational oracle 不调用 Decimal/cost engine，复算每笔 gross rounding、累计佣金/所有费用、delta、预留、现金、T+1/lot allocation/namespace/sequence/hash chain。200 次亚分 partial 以及整单/分拆 rounding 差异均验证；replay gross 从实际累计成交取值，不按整单重新舍入。负时区 offset 转换上海交易日后也核账一致。

旧 V5 额外实际只读 replay：14 日/8 rows，final cash/NAV=979114 分，费用4986分；85 个选定锚点 before=after=`e4b6e8a9d9eb2d28128940804be51b915e64b36a3501ab47b3588dfbcfc47d2a`。旧 engine/seal/ledger 无写入；这不是旧策略盈利或全量旧证据 PIT 认证。[外部证据](baselines/P1A-legacy-external-replay.json)。

## 15. Experiment A deterministic replay — PASS

固定 snapshot、FeatureSet version/hash、synthetic AccountProfile hash、CostProfile、Rule、Calendar、Security 版本/hash，以及实际实现 commit `8cca36056bde7cf55bf84bb699d59905994cb724`。Source tree=`sha256:aa8902654fdec40134b862f9abff91330caadddcff7c8ac82bde494d4abff46a`；逐文件验证当前字节与该 Git commit，拒绝合法但错误的旧 SHA、未提交修改或新增实现文件。

两次运行八字段完全一致：order_sequence、fill_sequence、ledger_entries、daily_nav、cost_breakdown、MAE/MFE/path metrics、economic_result_hash、ledger_chain_hash。runtime trace/wall clock 不进入经济 hash；audit chain 的诊断 clock/hash 可不同。输入 snapshot/Feature 自身 trace 固定，因为冻结对象完整 hash 仍参与绑定。

Economic hash=`sha256:b59d2cd0c6b89f3abfdbc5348763665cbb3b1dc3ced7d4e5785ba3e6ab152b4c`；ledger chain=`sha256:ceb3373ceff6099f28532e5977664f54a9a20549c8b0834e5eed03327c1ea449`。仅改 cost version、仅改 rule version、仅改 source 一个字节的三项 mutation 均改变 result hash；原 approval/result 输入绑定拒绝复用。

完整 fixture cash/sessions/marks/path 也绑定，且检查账户/日历一致；实际 security/calendar/source/Feature 投影必须匹配闭包。篡改后 ordersWritten=0。[双运行与mutation全部输出](experiments/P1A-results.json)。这些是预定 synthetic 信号的工程实验，不是策略回测收益或 OOS 结果。

## 16. Experiment B friction stress — PASS

第一轮 Edge OFF，三档固定信号、quantity 和预摩擦 fill 价格/路径，毛 PNL 同为60000分：

| Synthetic profile | Gross（分） | Friction（分） | Net（分） | Completed orders / round trips |
|---|---:|---:|---:|---:|
| LOW_FRICTION | 60000 | 537 | 59463 | 6 / 3 |
| BASE_FRICTION | 60000 | 2070 | 57930 | 6 / 3 |
| HIGH_FRICTION | 60000 | 7788 | 52212 | 6 / 3 |

第二轮 Edge ON：completed orders=6→4→2，round trips=3→2→1；每个拒绝都有明确 reason codes。未改变第一轮数量来“买得起”高费率，没有调选股/Quality/Timing/价格档位阈值。[机器实验结果](experiments/P1A-results.json)。

## 17. Micro-Ladder rejection — PASS（EXPERIMENTAL）

每个新 tranche 作为独立订单计算买卖完整增量费用；不把既有订单 partial delta 冒充新订单费用。包含实际佣金及 minimum effect 子归因、stamp、exchange、other、slippage；只比较显式 fixture 预期 benefit，非 AI 生成价格档位。

拒绝码：REJECT_INSUFFICIENT_INCREMENTAL_EDGE、REJECT_INSUFFICIENT_NET_EDGE、REJECT_INSUFFICIENT_EDGE_COST_RATIO。测试中的 multiple=2 明确 SYNTHETIC_EXPERIMENTAL；生产 safety_multiple、minimum_net_edge、minimum_edge_cost_ratio 均 UNSET_REQUIRED，PROD 调用拒绝。

## 18. Cost attribution 与实际 Audit chain — PASS

每个 replay 输出 gross、实际 commission、proportional、minimum effect、stamp、exchange、other、slippage、total friction、net，以及 friction/gross-profit ratio、per completed order、per round trip、per strategy。effect_is_subset=true；net=gross−friction 独立核对。非正 gross 的 profit ratio 返回 null，不伪造比例。

实际存储 MarketData → Snapshot → Feature → Cost → Replay 五个事件，带 source/hash/time/security/version/trace 与 parent refs/hash chain；Cost 指向实际成本归因，不只有 profile 描述。真实 quarantined market ingest 也有实际 Data audit/blocked snapshot 事件，但不会伪造后续可交易链。未来 chain 可接 P0 Card/Signal/two HUMAN approvals/OrderIntent/Fill/Ledger；本阶段不创建真实 producers。

审计 refs 严格字段白名单，递归脱敏敏感键及常见自由文本 secret patterns。九张 source/paper/replay 历史表 UPDATE/DELETE/TRUNCATE 保护已独立攻击。**脱敏规则不是能识别任意未标注秘密的完整 DLP；producer 必须只传必要结构化数据。** 没有接触真实 broker credentials 或记录完整实际账户号。

## 19. CORE_40 skeleton — PASS

仅 namespace/lifecycle/metrics，target horizon20–40 trading sessions，不强制最少持有20日。THESIS_INVALIDATED / RISK_INVALIDATED / MATERIAL_EVENT / PRICE_STRUCTURE_INVALIDATED 可于第1日产生 EXIT_ELIGIBLE；仅平盘、次日跌1%或短线资金弱保持 OPEN。到目标周期也只是 review_due，不自动结束 thesis。

EVENT_3 只有 namespace placeholder/隔离测试，没有交易策略。RESEARCH_6_18M 禁止订单。没有 AI 选股、评分优化或参数调优。

## 20. MAE/MFE metrics — PASS（日线近似）

存储 MAE_5/10/20D、MFE_5/10/20/40D、days_to_positive、days_to_MFE、drawdown_duration、max_underwater_days 与 resolution/window/sample/path hash。全部明确 DAILY_APPROXIMATION，连续窗口不足返回 null/INCOMPLETE。

显式交易 sessions 计数；未知日内 entry 排除 entry day 的 high/low，session-open entry 可包含。positive 指 close 高于 entry price（未扣费）；MFE time 为观察连续路径首次最大正向 high；duration 为最长 close 低于 running peak 的连续 sessions，underwater 为低于entry的连续 sessions。数据缺口不压缩成更短“5日”。路径是 retrospective outcome，不进入 decision Feature；fixture 中可包含实际提前退出后的价格观察，不能称为实际持有期间的分钟路径。

## 21. UNSET_REQUIRED inventory — PASS，生产继续阻断

[机器清单](../config/p1a/unset-required.inventory.json)从冻结 schema 与真实未配置 AccountProfile 自动生成，包含路径、schema pointer、required/status 与阻断范围。当前30项 UNSET；不是只报告计数。63个 required leaf paths 逐个删除时结构校验拒绝，productionGate.allowed 始终false。

包括真实 account ID、capital/target amount/positions、strategy budgets、loss/sector/drawdown/margin/frequency、broker ID、佣金/minimum/计费范围、stamp/exchange/other/slippage/rounding/生效区间/验证来源、user risk policy。生产 Edge 参数、数据许可/时钟、校准/评分/准入/sizing 政策另行未确认。本轮不要求用户补真实值；不会阻塞本离线工程。

## 22. Independent Reviewer results — PASS_WITH_CONDITIONS recommendation

Reviewer 只读，未改业务代码/规则。独立全 `npm run check` 与两次实验/clean日志hash核验通过；六类实际跨模块原反例在正确门禁处拒绝，订单写入0；九表 non-owner TRUNCATE CASCADE 全部拒绝。

已修复并复验：raw事实替换、停牌遗漏、自封 source projection、fixture输入漏绑定、Infinity factor、39位all-in、负offset oracle、partial gross差异、audit refs/free-text泄露、TRUNCATE绕过。没有以 code-pin 的提前拒绝冒充 source 门禁修复。最终25项报告另经只读一致性复核，hash/迁移/表数/未知项/来源隔离与实际证据相符，无需修正。[独立审查记录](independent-review-p1a.md)。

## 23. Known failures — 如实保留

Legacy native seal compatibility 仍 FAIL_KNOWN_COMPATIBILITY（exit2，PINNED_CONTEXT_OR_CLI_CHANGED）：CLI expected=`3e11ccc743e8198a5ef84fb57c89941d845b0ea0302485ed1fbac2f0821aca5a`，observed=`6b582e8813ce7e8ed4c52814ee5cf230dba647bf2292df747a4003f2657ef201`；另外5个binding一致，seal_modified=false，未伪造PASS。[当前机器证据](baselines/P1A-legacy-native-compatibility.json)。

真实 SSE 数据/未知许可被主动阻断，是正确 gate 状态，不伪装为可交易 PASS。旧2号latest-count断言在新迁移后不再正确，总控改为实际完整migration集长度，原checksum与roundtrip/PIT断言保留。发布前一个session mutation测试因更早拒绝的reason不在预期列表而失败，现断言精确early reason并补源投影攻击；未改准入规则。[验证记录](p1a-validation.json)。最终自动检查0 FAIL。

## 24. Remaining technical debt / execution blockers — 明确保留

真实历史 bars/security/status/calendar/action/financial 的完整权威与license/time admission未完成；市场数据持续健康监控、全年各板块规则、DATE_ONLY重构策略、真实权益/adjustment对账未完成。已捕获五个源只用于有界reference，不能扩张许可或历史可得含义。

真实 PostgreSQL server、多连接/多进程cash并发、RBAC/least privilege、storage/timestamp authority、备份/部署、崩溃恰在COMMIT前后fault injection尚未验收。PGlite真实SQL/行锁/角色反例不等于生产部署。Paper SELL零现金限制、synthetic PER_ORDER/费用区间语义与真实券商结算映射必须在接入前另行确认。

没有真实 gateway/user authentication、broker adapter、交割单费率核账、真实sizing/全账户risk enforcement、20日真实forward Paper、production Kill Switch部署验收；研究概率/Edge校准、scoring/admission政策也未确认。未知30项及新增Edge/数据政策继续阻断真实资金。productionGate 永久false测试与冻结P0 gate字节不变；无新broker submit path/credentials/LLM下单路径。

## 25. 是否建议开放 P1-B Research Intelligence — 本轮继续 BLOCKED

建议先由用户确认本 PASS_WITH_CONDITIONS Gate 及真实source准入边界，再另行授权下一轮。可讨论的下一步是 Data Admission 补完（官方security/status、全年calendar、真实financial/action parser与时钟/许可），以及仅消费已验证snapshot的 Research-store / BrainPacket-contract / manual adapter；不能把quarantined evidence导入可交易研究。

本轮不启动这些 agent，不调用Deep Research，不实现评分/质量/时点优化、EVENT策略、GUI、真实 broker 或生产。真实账户未知项不要求现在填写。**报告完成后停止，等待用户确认。**

## 工程交付索引 / Git状态

工程目录：`/Users/qiushi/投资研究/ashare-trading-v1`。Main 保持P0；当前 `p1a/integration`。A/B分别在独立Git worktree提交，再由总控审核cherry-pick。实际经济代码版本为上述8cca360；候选元数据060acfe；最终报告检查点以 annotated tag `p1a-review-20261005` 标识，标签代表交付技术审查，不代表用户批准下一阶段。[机器可读Gate](P1A-Gate-Review.json)单独记录技术结论与用户确认状态，不改写冻结的候选release。

```text
ashare-trading-v1/
├── contracts/ v1/（16个不变） + p1a/（13个新module schemas）
│   ├── release.v1.json / release.p1a.json
│   └── reason-codes.v1.json / reason-codes.p1a.json
├── migrations/ 001/002（不变） → 003_data → 004_paper → 005_replay_audit
├── src/ contracts/ + baseline/（冻结）
│   ├── data/ source/security/calendar/market/snapshot
│   ├── cost/ + paper/（独立BigInt oracle）
│   └── p1a/ contracts/audit/code-provenance/fixture/replay/edge/metrics/core/inventory
├── config/ account-profile.unconfigured.v1.json（不变） + p1a/库存/代码证明
├── tests/（210项） + fixtures/ synthetic / legacy / p1a-data / p1a-paper / p1a-replay
├── scripts/ check / verify / explicit parent freeze / p1a experiments
├── docs/ ADR001–012 / baselines / experiments / Gate / reviewer / agents
├── legacy/ asset-manifest.v1.json（不变） + adapters/（只读）
└── package-lock.json / .gitignore / 基础CI
```

冻结P0 contract version1.0.0；P1-A独立release1.1.0、新module schemas1.0.0，详见 [合同清单](contracts-p1a.md)。ADR009来源准入、010Paper经济、011确定性版本/回放/指标、012实验Edge；原ADR001–008不变。[Agent任务合同](agent-plan-p1a.md)。

空库→005和重跑不变均实际验证，共60张用户表：public51、p1a_paper7、p1a_replay2。[Migration checksums与表清单](baselines/P1A-schema-validation.json)。未批量迁移旧数据，未把历史大资产或状态库放入Git；public原字节fixture均小于46KiB。

Legacy manifest KEEP/MODIFY/ISOLATE/DEPRECATE/DELETE_LATER保持机器可读且未修改；V5永远LEGACY_EXPERIMENT，5–8日原持仓计划、旧cost/cash/hash/state保留，不映射CORE/EVENT。实验数据与legacy证据不成为真实参数默认值。
