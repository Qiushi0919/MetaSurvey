# P0 委派与审核记录

共享 contracts / ADR / migration numbering / Git 集成由总控拥有。子 agent 没有改变项目级架构、改旧资产、填业务参数或开启后续开发的授权。本轮三个子 agent 只在共享新 repo 的互斥文件范围工作，没有自行提交 Git。

## 总控

Goal：建立独立 repo，冻结全局接口与验收基线。
Context：正式交接 + 已确认迁移方向，P0 结束必须停止。
Inputs：原文、审查、agent 输出和独立反例。
Outputs：Git、16 contracts/语义校验器、002 registry/最小隔离导入、ADR、release、CI、Gate Review。
Interfaces：最终负责跨模块 scope、hash、时钟、approval 和钱单位。
Constraints：不启动 A–F 完整开发、不写 legacy、不真实交易。
Tests：全局 check、全部 Golden Tests、外部回放、未知配置门禁。
Definition of Done：反例修复、测试证据、干净提交和完整 Gate Review；等待用户下一决定。

## Agent A — p0_schema

Goal：把 PostgreSQL Schema 草案落为可执行、追加迁移和不变量测试。
Context：四时钟、raw/adjusted、财报修订、namespace 与两阶段审批。
Inputs：正式交接、总控冻结字段/编号、独立 reviewer 反例。
Outputs：001_schema_v1.sql、migrate.mjs、schema.test.mjs、schema-v1.md。
Interfaces：exec/query 连接适配器、version/hash/source/scope 字段；001 号独占。
Constraints：不得修改 contracts、002、ADR、业务政策或任何旧库；不得授予 PROD 权限。
Tests：空库/latest、篡改/回滚、精度、PIT/引用、版本和复合 FK 正反例。
Definition of Done：测试全通过且记录部署/RBAC/源真实性/完整投影限制，交总控合并。

## Agent B — p0_economics

Goal：用独立整数核账冻结费用/现金/T+1行为，并提取 V5 只读回放。
Context：旧实验费用与本金只能出现在标记 fixture，不做生产默认值。
Inputs：正式交接、保存的 V5 14 日 frozen/results、原规则/seal/hash。
Outputs：economics/ledger harness、对应 synthetic tests、legacy manifest/adapters/fixtures/tests/docs。
Interfaces：全局钱单位及 DEV/PAPER；外部资产按 workspace-relative locator。
Constraints：不得改 contracts、migration 号、ADR或旧账本/旧 seal；不得调用模型、网络、券商或旧运行入口。
Tests：minimum commission、含费 affordability、BigInt/Decimal、T+1、同日/跨调用时序、幂等、逐日旧 replay、前后 fingerprint、已知失败保留。
Definition of Done：portable 与实际 external 回放通过，native compatibility 单列失败，旧资产字节不变。

## Independent Reviewer — p0_reviewer

Goal：独立攻击合同、迁移、版本链、测试盲区和只读边界。
Context：全绿不代表合同可靠，也不允许削弱门禁。
Inputs：全部候选代码、测试、schema、manifest 和修复差异。
Outputs：可复现缺陷、风险级别、复验结论；不修改文件。
Interfaces：向总控反馈，不改变共享合同。
Constraints：不能改业务规则或 fixture expected，不访问真实券商、不写旧资产。
Tests：重新构造 honest rehash/rebind、未来 source 引用、跨 scope、精度极值和伪造人工身份反例。
Definition of Done：已报告缺陷逐项修复/复验；未完成能力明确列为下一 Gate 条件。

## 下一阶段建议（尚未启动）

首批建议仅两个实现槽：Data/PIT Adapter 与 Security Master；Cost/Ledger/Paper Reference；另保留 Independent Reviewer。首条端到端离线 slice 验收后释放一个实现槽给 Research Store / Manual Brain Adapter。总控保留合同/迁移/ADR，独立 reviewer 保留只读身份。用户确认后再扩大到 candidate/signal/watcher；GUI 排在可信状态与 API 后，Prod 另设 Gate。评分/Edge/仓位等缺失规则若未决定，只能实现阻断状态，不能自行优化或猜测。
