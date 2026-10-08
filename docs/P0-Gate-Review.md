# P0 Gate Review — A 股交易系统 V1

日期：2026-10-05，Asia/Shanghai。结论：**P0 工程基线可提交验收；存在已知 legacy CLI compatibility 失败；真实资金执行仍完全阻断。** 本轮完成后停止，等待项目所有者确认，不自动进入功能开发。

主要 Source of Truth：[正式交接文档](/Users/qiushi/投资研究/交易策略/A股交易系统重构工程交接文档：云端“大脑”与本地“眼睛和手”.md)，SHA-256 `63e78aac5e061a82419bd202b58c2cba28ca025053030a14b8aad8737b55fb38`。

已确认的 Current-State / Migration Baseline：[第一阶段审查](/Users/qiushi/投资研究/交易策略/A股交易系统V1第一阶段现状与迁移审查_2026-10-05.md)，SHA-256 `fd46c1822b7b3371aa2b6c516d2961dca92a93979aa6c4bb63d4a1fd1e05922f`。其中“建议”“待确认”“未指定”仍不是已批准业务规则。两份原文保持不变。

## 1. 新 repo tree

独立项目：[ashare-trading-v1](/Users/qiushi/投资研究/ashare-trading-v1)。没有把历史实验整体搬入。

```text
ashare-trading-v1/
├── .git/                            独立 Git，main
├── .github/workflows/p0.yml          CI：Linux / Node 24 / npm run check
├── .gitignore / .nvmrc / .env.example
├── AGENTS.md / README.md
├── package.json / package-lock.json
├── config/
│   └── account-profile.unconfigured.v1.json
├── contracts/
│   ├── v1/                          16 schemas + common.schema.json
│   ├── reason-codes.v1.json
│   ├── persistence-mapping.v1.json
│   └── release.v1.json              冻结字节清单
├── migrations/
│   ├── 001_schema_v1.sql
│   └── 002_contract_registry.sql
├── src/
│   ├── contracts/validate.mjs
│   └── baseline/
│       ├── gates.mjs / migrate.mjs / staging.mjs
│       └── economics.mjs / ledger.mjs
├── adapters/
│   ├── legacy-common.mjs / legacy-readonly.py
│   └── verify-legacy.mjs / replay-legacy.mjs
├── legacy/asset-manifest.v1.json
├── tests/
│   ├── contracts / gates / economics / ledger .test.mjs
│   ├── schema / staging / legacy .test.mjs
│   ├── helpers.mjs
│   └── fixtures/
│       ├── synthetic/               16合同样例 + 显式费用边界
│       └── legacy/                  14日账本 + 实际只读回放证据
├── scripts/
│   ├── check.mjs / verify-contracts.mjs
│   └── generate-contracts.mjs / freeze-baseline.mjs
└── docs/
    ├── adr/                         ADR-001 … ADR-008
    ├── source-of-truth.json / agent-plan-p0.md
    ├── contracts-v1.md / schema-v1.md
    ├── economics-baseline.md / legacy-assets.md
    ├── independent-review.md / p0-validation.json
    └── P0-Gate-Review.md
```

Git 不包含 node_modules、大体积证据、credentials、运行状态库、旧业务数据库或旧 runs；.local 测试日志也被排除。工程实现提交含 89 个小型文件、合计约 593KB；最大文件为约52.5KB manifest。本报告作为随后文档提交，不改变已验证运行逻辑。

## 2. Git baseline / commit 状态

工程基线提交：`2ad4641bf4f926592b82580f38a925524b1e5174`，标题 `chore: establish isolated P0 contracts schema and regression baseline`。分支 `main`，无远程，无 push。本报告与最后交付说明作为随后 docs 提交；最终交付时工作树干净，报告本身不嵌入其自身提交哈希。

已建立 .gitignore、精确依赖锁、测试/本地检查入口和基础 CI。Node 工程允许24/25、推荐24；最终完整检查实际使用本机 Node **24.19.0 / darwin arm64**。依赖：Ajv 8.20.0、ajv-formats 3.0.1、decimal.js 10.6.0；测试 PostgreSQL PGlite 0.5.8。CI 配置已保存，尚未发生远程 CI run。

## 3. contracts 清单及版本

以下全部为 **1.0.0**，完整字段定义见 [contracts说明](/Users/qiushi/投资研究/ashare-trading-v1/docs/contracts-v1.md)，字节冻结见 [release](/Users/qiushi/投资研究/ashare-trading-v1/contracts/release.v1.json)。

| 合同 | 核心边界 |
| --- | --- |
| SecurityIdentity | canonical symbol、市场/类型/状态、规则与来源版本 |
| DataEnvelope | raw/payload hashes、四时钟、数据质量和调整版本 |
| SnapshotManifest | cutoff、freeze、可见输入 refs/data hash、禁止未来元数据 |
| FeatureSet | strategy、feature版本、单位/缺失质量、快照引用 |
| AccountProfile | mode/account、账户/费用/风险未知值、HUMAN_CONFIRM |
| CostEstimate | scoped symbol、量价、整数分费用、配置与有效期 |
| ResearchCard | 四层、score/grade、规则、反证、概率校准及独立周期 |
| BrainPacket | MANUAL_EXPORT、嵌套 PIT/hash、快照绑定；LLM意见无执行授权 |
| CandidateEligibility | Hard Block、成本与准入政策版本、显式不可交易状态 |
| SignalEvent | 状态/触发/TTL、card/rule版本、行情时钟/去重键 |
| Approval | 两份独立 HUMAN_USER 批准；最终确认绑定精确条款 |
| OrderIntent | LIMIT、量价/成本/账户快照/client ID、版本链、P0不执行 |
| Fill | order/approval绑定、成交来源、整数分、幂等成交标识 |
| LedgerEntry | 账户共享现金、策略持仓、事件顺序和前项hash |
| BacktestResult | data/config/code/cost版本、情景、MAE分辨率、OOS标签 |
| AuditEvent | actor/action/target、前后与链hash；模型复核非授权 |

每个合同包含 required/optional、enum、单位、timezone、version、hash/trace、reason codes 和失效条件。notes可选；required的null仍须存在。钱为38位整数分字符串，价/率为Decimal字符串，数量safe integer；禁浮点金额和默认类型转换。私有Decimal precision100，独立BigInt核账。真实券商舍入/收费范围并未确认。

Core 20—40交易日、Event 1—3交易日、Research 6—18月隔离；Research不能生成订单链。身份验证Set只是测试可信上下文，数据库HUMAN_USER字段只是关系声明，不等于完成认证。

## 4. Schema / migrations

| 迁移 | 实现与验证 |
| --- | --- |
| 001_schema_v1.sql | 45张业务/辅助表：来源/证券、行情/因素/行动、财报/披露、快照/特征、研究/信号/草稿/批准、模拟/真实账簿、回测/审计、staging/legacy注册 |
| 002_contract_registry.sql | 1张 canonical contract_records，16合同无损保存；fixture记录只能QUARANTINED |
| schema_migrations | 1张跟踪表：编号/原字节SHA/name/applied_at；latest=2，共47 public表 |

空库→latest、重复应用、篡改阻断、失败事务回滚均测试通过。迁移文件发布后必须追加新编号，不能修改已应用的校验值。PGlite真实执行PostgreSQL DDL；尚未验证外部服务器/RBAC/并发部署。

raw与adjusted分键追加保存；调整id/version/hash/行动谱系可追踪。财报原始/修订版不覆写，as_of先过滤时点后选版本。关键对象保留四时钟与source/version/hash。快照成员以允许类型解析实际源记录，并校验原时钟/hash；不能自报旧时钟引用未来资料。

orders/fills/positions/ledger 的sim/real物理表、mode/account/strategy/security复合边界已建立；两阶段批准和未签订单草稿绑定版本。账户现金顺序与client ID在账户层共享，跨策略不能重复消费。

最小导入已完成：16份synthetic合同无损读写、真正的旧14日fixture作为opaque LEGACY_FIXTURE隔离导入、敏感字段/PROD/tamper拒绝，规范化订单/成交/账本零写入。**全量历史数据和完整 wire→规范化投影均未迁移或实现**，映射状态机器可读且显式NOT_IMPLEMENTED，不是另一套业务Source of Truth。

## 5. ADR 清单

八份ADR均为“P0工程实现、待Gate Review”，不授予生产许可。

| 编号 | 决定 |
| --- | --- |
| ADR-001 | 新repo/外部legacy边界、排除大证据/credentials/state |
| ADR-002 | 三策略namespace、交易scope、共享账户现金/总风险 |
| ADR-003 | money/Decimal/精度拒绝与HALF_UP基线、含费预算 |
| ADR-004 | 四时钟、严格观察与公开可得重建、未来元数据隔离 |
| ADR-005 | raw/adjusted分离、公司行动因素版本、财报修订/PIT |
| ADR-006 | card→signal→两份human approval→order的版本/条款链 |
| ADR-007 | UNSET_REQUIRED与无条件关闭P0生产执行 |
| ADR-008 | preserve→isolate→replace→verify→deprecate、保留seal失败 |

目录：[docs/adr](/Users/qiushi/投资研究/ashare-trading-v1/docs/adr)。后续真实收费、策略政策和部署组合仍需单独决定；不能把工程规范误作已核验生产事实。

## 6. legacy manifest

[机器清单](/Users/qiushi/投资研究/ashare-trading-v1/legacy/asset-manifest.v1.json)，版本1.0.0；14个资产分类项：KEEP 3、MODIFY 2、ISOLATE 7、DEPRECATE 1、DELETE_LATER 1。处置标签不授权当前写入/删除。MODIFY仅针对新替代实现，DEPRECATE未执行退役，DELETE_LATER没有执行删除。

V5固定为 `LEGACY_EXPERIMENT:sector-swing40-v5`、target_strategy_mapping=null。保留40日实验窗口、5—8日计划持仓、原本金/预算/风险/费用/滑点、46项源码/配置hash，以及原BLOCKED、14/40、下一日2025-04-30状态。V1R、research-v2、旧GUI、旧业务/模型库和Application Support运行副本均留外部只读。

85个选中锚点包括正式文档/审查、V5规则/代码、旧seal、状态以及14日frozen/result。前后fingerprint均为 `e4b6e8a9d9eb2d28128940804be51b915e64b36a3501ab47b3588dfbcfc47d2a`。目录分类不是全目录递归认证，未全量重审旧原始材料或所有DB内容。

## 7. Golden Tests 结果

最终入口 `npm run check`：**98项，97通过、0失败、1项默认跳过**。跳过项仅为需要本机外部旧资产的回放；该外部套件又被显式执行：**12/12通过、0跳过**，其中11项与portable重复，不能相加成110项独立通过。

| 测试文件 | 默认结果 |
| --- | --- |
| contracts.test.mjs | 26通过 |
| gates.test.mjs | 13通过 |
| economics.test.mjs | 9通过 |
| ledger.test.mjs | 11通过 |
| schema.test.mjs | 23通过 |
| staging.test.mjs | 4通过 |
| legacy.test.mjs | 11通过，1外部默认跳过；显式运行12通过 |

| 用户要求的基线 | 结果与关键反例 |
| --- | --- |
| PIT / future-data isolation | 通过：未来正文/标题/ID不入哈希；迟到取得与重建口径分开；伪造source clock引用拒绝 |
| freeze-before-reveal | 通过：未承诺不能reveal，承诺后修改调用方决策不改变已保存版本 |
| T+1 | 通过：同日、人类override、跨策略取lot均不绕过；显式交易日历跨长假 |
| same-day cash ordering | 通过：后卖现金不能支付前买，跨replay调用仍检查snapshot顺序 |
| integer / Decimal reconciliation | 通过：BigInt独立oracle；合法大数量价极值、分值/费用/现金/持仓/NAV不一致拒绝 |
| minimum commission boundary | 通过：显式synthetic最低费下方/恰好/上方；不是5元生产默认值 |
| fee-inclusive affordability | 通过：裸一手金额够但含费不足时禁止，含费项不双扣 |
| strategy namespace isolation | 通过：Research不能交易，Core/Event持仓独立且共享账户现金；SQL scope FK |
| stale data blocking | 通过：5秒边界、>5秒、未来行情时钟拒绝；尚无真实feed服务 |
| duplicate order prevention | 通过：同账户client/order/fill幂等，跨策略也不重复，历史状态修订仍可追加 |
| card/version invalidation | 通过：改card/signal/rule/cost/量价/account snapshot或过期不能复用批准 |
| unknown config blocks production | 通过：30项UNSET保持；即使自声明全部配置/验证也无法开启P0生产 |

14日原V5 engine / rows / snapshots / reconcile 完全一致，2025-04-10至04-29；8笔交易、4轮、4条未成交原样保留；期末现金/NAV 979114分、费用4986分、净盈亏−20886分、无持仓。只证明保存输入可重放，不证明完整PIT、40日完成或盈利能力。

证据：[p0-validation.json](/Users/qiushi/投资研究/ashare-trading-v1/docs/p0-validation.json)、[外部回放](/Users/qiushi/投资研究/ashare-trading-v1/tests/fixtures/legacy/p0-external-replay-evidence.v1.json)、[独立审查](/Users/qiushi/投资研究/ashare-trading-v1/docs/independent-review.md)。独立审查发现的P1和最后DATE_ONLY读回P2均已修复并复验，没有以放宽门禁换取通过。

## 8. 已知失败与技术债

**仍失败：legacy:verify返回exit2 / FAIL_KNOWN_COMPATIBILITY**，原验证器错误 `PINNED_CONTEXT_OR_CLI_CHANGED`。tool schema、builtin、static context、environment template、command五项一致，CLI sha差异仍OPEN：

- 旧seal：`3e11ccc743e8198a5ef84fb57c89941d845b0ea0302485ed1fbac2f0821aca5a`
- 当前：`6b582e8813ce7e8ed4c52814ee5cf230dba647bf2292df747a4003f2657ef201`

旧seal/ledger均未更改。`legacy:replay`成功与native compatibility失败分列，不伪装native PASS。

尚未完成：完整规范化投影、外部PostgreSQL部署/并发迁移锁/RBAC/恢复演练、可信源时间与原始hash认证、官方security/calendar/行动、真实费用/部分成交结算、完整状态机/账户预留/登录签名/审计权限、真实feed与Paper连续验收。CI未远程运行。只读Python hook是误写防护，不是恶意原生代码沙箱。

## 9. 尚未确定的业务参数

真实模板：[account-profile.unconfigured.v1.json](/Users/qiushi/投资研究/ashare-trading-v1/config/account-profile.unconfigured.v1.json)。30个required值继续UNSET_REQUIRED：账户身份；capital/target order/max positions/单笔风险/行业暴露/日损失/回撤/融资/频率/Core和Event预算；券商id/佣金率/最低费/结算范围/经手与其他费率和包含项/卖出税率及官方来源核验/费用有效期/基础与压力滑点/舍入与配置来源；user_risk_policy_version。

法定费率也没有从文档当年的描述自动升级为当前验证事实；真实有效期和来源需核验。旧5000/6000/10000本金、3000/8000单票和250/400风险绝未复制到这个模板。

另需对应模块开工前决定：证券范围与权限、L1/分钟/L2源与深度预算、主部署/对象存储/Redis组合、Research/Quality/Raw/Final/Timing评分关系、A触发后准入、Edge比率分子/不确定折扣/零费用口径、概率未校准时Paper sizing、实时last与正式close、Core提前退出/Event完整规则、Kill Switch减仓权限、同股跨策略lot调拨、部分成交收费及统计验收。正式交接中标为建议初始值的阈值未被擅自升级。

这些缺口不阻塞已完成的工程基线，但继续阻断对应业务和真实执行。

## 10. 下一阶段建议启动的 agent（尚未启动）

首批建议仍保持总控 + 两个实现 agent + Independent Reviewer：

1. Data/PIT/Security Adapter：先实现canonical→规范化投影、来源时钟/原字节校验、证券/日历/公司行动slice；未决来源进入quarantine。
2. Cost/Ledger/Paper Reference：把纯harness接入版本化wire与账户预留、完整费用/lot/cash回放；只离线或明确Paper，不接券商。
3. Independent Reviewer：只读审跨模块反例、迁移和Golden回归；总控继续拥有shared contracts/ADR/编号。

首条离线slice验收后再释放一个实现槽给Research Store / MANUAL Brain Adapter。candidate、signal、watcher分批推进，GUI后置；不启动A–F全部并行。每个任务继续使用8段任务合同，示例见 [agent-plan-p0.md](/Users/qiushi/投资研究/ashare-trading-v1/docs/agent-plan-p0.md)。

## 11. 仍阻止真实资金执行的内容

P0的 `productionGate.allowed=false` 是无条件工程阻断；DB `production_authorized`只能false，OrderIntent执行flag只能false；repo没有券商传输/凭证/提交服务。LLM APPROVE不能满足人类Approval。fixture importer拒绝PROD且只QUARANTINED。

此外30项真实参数未定、费用/来源/证券权限未核验、概率/评分/仓位政策不完整、可信认证/最新行情/账户预留/Kill Switch/权限部署/备份恢复/Paper验收未完成。即使用户后续填齐参数，也不能自动解除这些门禁。

**本轮停止于P0 Gate；等待你确认，再进入下一阶段。**
