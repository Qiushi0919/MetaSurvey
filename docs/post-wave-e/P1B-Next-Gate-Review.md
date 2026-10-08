# P1-B Post-Wave-E PIT / Forward Preparation Gate Review

**P1B_POST_WAVE_E_GATE = PASS_WITH_CONDITIONS (engineering only).**
Owner acceptance PENDING. No execution or next-phase authority.

本轮仅完成历史 PIT / Forward 的工程准备。正式交接文档继续为主要 Source
of Truth；Owner 当前接受 Wave D/E WITH CONDITIONS，其历史 Gate 原文没有改写。
经济目标、业务参数、许可与历史可见性缺失项不因工程测试通过而升级为规则。

## 基线与代码

基线9f975258b0c8f88770eebacd841573e492bdbc48；最终代码候选
95476b67255863efd7fc5fb9ee34c84766e7d68a；release1.0.1-post-wave-e-preparation。
663 个旧不可变文件保持原 bytes，只允许3个导航文件更新。001–006迁移/schema6/
依赖锁/旧实验和seal保持不变。37个新 code/schema/rules/ADR pins冻结。

```text
post_wave_e/
  common.py / core.py / run.py / contracts.mjs / check.mjs
  pit.py / action.py / strategy.py / provider.py / preflight.py
  forward.py / real_adapter.py / tests/
contracts/post-wave-e/    8个1.0.0合同
docs/post-wave-e/         Gate、证据、验收、runbook与manifest
docs/adr/                ADR029–031
```

996个运行上下文依赖逐次校验，含293个直接采纳的私有路径；94个观测请求身份
对应85个原文hash和94个物理原文。同内容、不同请求/抓取时点仍分别保留。
Git只保存代码、合同和脱敏证据元数据；私有原文、fixture数据库、完整日志与
失败批次在Git外。这里只证明所采纳依赖的完整性，不能证明历史可见性或许可。

## 合同与接口

八个合同均1.0.0：HistoricalPITGap、TradeabilityHistoryReadiness、
FinancialRevisionReadiness、ActionAdjustmentReconciliation、FrozenStrategySpec、
ForwardPaperRealAdapterReadiness、SnapshotBPreparation、ProviderLicenseTransportGap。
required/optional、closed enum、units/Decimal/integer money、显式timezone、版本、
hash/trace、reason codes及失效条件均在schema/contract-matrix和接口定义中明确。
它们仅允许LOCAL_PREPARATION_DISPLAY；schema/hash通过不构成任何真实issuer权限。

财报选择按cutoff对应上海日期拒绝未来报告期；晚修订及未来元数据不改变过去
prefix的值、计数和hash。OBSERVED_AT_TIME与历史重建分开，DATE_ONLY不补午夜。
event_time允许表示公开已知的未来有效事件，没有错误施加通用四钟总顺序。
实际财报仍是当前抓取版本：12项coverage全部BLOCKED，first visibility/revision/
units均未获证明。positive selector仅SYNTHETIC fixture，不能选出实际可交易记录。

历史ST/suspension/limits/delist/listed/universe六组件要求完整区间与可见证据；
缺失、冲突、当前列表回填均UNKNOWN。KNOWN fixture也不能证明订单可成交。
三个实际证券历史状态coverage全部BLOCKED。

公司行动保留5个歧义、8个pre_close差异及UNSET tolerance/rounding。raw/factor
隔离；factor+cash credit双重计入拒绝；同供应方因子没有独立权威地位。

StrategySpec冻结评价要求和公平比较协议，未选定MA20/MA60为最终策略，未对
Wave E曲线做优化。entry/exit、benchmark/history/收益回撤阈值/OOS等均UNSET。
原30个真实账户配置仍UNSET_REQUIRED；这些字段与新策略要求分别统计。

实际adapter可封闭读取三股当前观测anchor，不能产生fresh SnapshotB/实际Paper
记录。SQLite持久化只验证SYNTHETIC NO_DECISION：重开、hash chain、事务rollback、
并发expected-head、重复防止、namespace/path/schema绑定。没有native订单/成交
表或issuer，real runner及actual append入口始终BLOCKED；actual_forward_days=0。
hash-chain不承诺抵御特权整库重写或恶意解释器；fixture authority仍process-local。

Provider intake只接受受限本地脱敏JSON；重复decoded key和Bearer/query敏感标记
在原文留存前拒绝。材料入库仍UNVERIFIED，不形成许可、entitlement或PIT证明。
没有新授权材料，因此provider/license/transport仍未核验，无法律结论。

## 验证与独立审查

Final full regression: **1138 unique =1137 PASS /0 FAIL /1 existing optional V5 SKIP**.
939carried+199new；Python671/native467。失败批次及Reviewer assertions不重复累计。
199新用例PASS（187Python+12native）。
干净检出副本+离线依赖安装；私有归档保持原位置，不宣称远程CI或归档迁移。
最终8个机器合同两次重放byte-identical，原始失败/中间输出epochs未覆盖。

Independent R2: **PASS_WITH_CONDITIONS，14,986独立断言通过**；996依赖前后
bytes一致，4,206观测行raw hash直接覆盖，447财报观测/4,875原文cell-ordinal核对。
完整攻击future leakage/revision与universe回填、
状态缺失推断、same-bar/T+1、双重action、synthetic fee/day与diagnostic策略晋级、
LLM-human混淆、source/license和Order/Broker权限。最终计数另列，不加进回归数。

## 失败保留与修复

基线比较脚本首次误用absolute-path record layout，保留摘要并明确原始完整log
未保存；producer tuple违反strict JSON的完整log和35/35匹配源码保留，修为
内部JSON array而未放宽float/PIT门禁。首次ordinal uniqueness schema失败保留
完整log、35/35源码与PREPARATION-G1，修复request/capture identity与multiset语义。

Independent R1为REMEDIATION_REQUIRED：财务原文间接绑定及provider重复key/Bearer
留存边界是两个真实工程发现。root扩展到所有retained observation originals，
新增44个路径，并修复strict decoded JSON与redaction。旧候选039、R1证据和
PREPARATION-G2保留，最终采用G3。Reviewer的reseal-hash及SMOKE发现脚本错误
分开分类，原脚本/log未覆盖。没有以harness错误掩盖真实工程问题。

旧V5 CLI hash mismatch/旧seal、optional外部V5 skip、SSE6个HTML非PDF失败、
provider/license/history/action/config缺口全部保留；旧14日ledger regression
仍为fixture验收资产，不映射为CORE_40/EVENT_3，不改旧账本使其通过。

## 当前Gate与阻断

ENGINE_DIAGNOSTIC_READY=READY；LOCAL_REAL_RESEARCH_SANDBOX历史Gate继续
PASS_WITH_CONDITIONS。C12–C22正式关闭0项；C30实际Paper days=0。
FORMAL_PRICE_BACKTEST、FORMAL_FUNDAMENTAL_PIT_BACKTEST、formal source admission、
Research Pilot、cloud/model/export/redistribution、Signal/Approval/Order/Fill、
broker/production均BLOCKED；productionGate=false。

0新增authenticated/public请求、0凭证lookup、0新行情下载、0model/broker/cloud
调用、0调度任务、0策略参数优化、0证券扩张、0真实交易权限。

真实资金执行仍至少缺：独立provider/license/transport与API entitlement；历史
PIT/状态/财报修订/行动单位和对账；Owner账户/dated fee/risk/kill与冻结策略评价
政策；实际fresh SnapshotB/Paper验收；可信人工审批链及券商/部署/风控独立Gate。
填写参数或取得SnapshotB都不能自动解除real runner的当前硬阻断。

后续建议：Owner先确认本Gate；需要实际观测时再单独授权实际开市/盘后SnapshotB。
Data/PIT agent针对真实证据补缺；Forward agent在独立政策/证据/授权齐备后做
实际activation；经济评价/backtest agent须先有公平冻结策略与历史PIT依据。
Independent Reviewer继续独立只读。当前不启动任何后续agent或实际runner。

## 交付与停止

12类必需交付：7个指定JSON、Snapshot-B-Runbook.md、Independent-Review.md、
P1B-Next-Gate-Review.md、external Delivery-Checkpoint.json及Git-only rollback bundle。
额外提供schema/ADR/validation/evidence/known-failures/artifact-index和本机验收ZIP。
最终commit/tag/tree/clean worktree与bundle绑定由Git外Checkpoint记录，避免自引用。
Git-only bundle不包含私有原文、凭证或运行DB，须保持私有归档原位置复验。

STOP after delivery。Owner acceptance PENDING；本轮不自动进入Snapshot B、实际
Paper Day1、Research Pilot、正式历史回测、broker、production或任何调度。
