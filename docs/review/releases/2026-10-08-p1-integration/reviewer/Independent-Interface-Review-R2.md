# 五年历史回测接口：独立差异复验 R2

结论：**PASS_WITH_CONDITIONS_FOR_ROOT_ISOLATED_P1_REPAIR**。原 R1 的 F01/F02/F03 在主控隔离候选中闭环；可作为限定工程集成验收的修复证据。六 DTO 仍为候选，**不批准最终共享字段合同或任何正向业务状态**。

对象：`37ec2ec9f8f16d406b10f2e2724858fc1a58f375`，主控私有 `fixed-child-code-clone`，版本 `1.0.1-candidate`。专项工作区仍为 `4252876e23224df5d29c20492a08da9436dccf4a`、清洁且未修改；主控972基线 HEAD `11fba19fa3b2dde8288fbed470f2319020a60da6`。本 Reviewer 只写新的审查证据，没有改任何源码、Git、原报告/封印或实际数据。

## 三项闭环

| 原 finding | 独立观察 | R2 结论 |
| --- | --- | --- |
| F01 / P1 纳秒截断/未来财务记录 | 整数 UTC ns 比较保留1ns区别；原八季度反例只留七季度、TTM=NULL；同 cutoff 的合法版本仍可纳入；纳秒后 poison 数值/单位未被消费 | 限定计算修复 CLOSED |
| F02 / P2 非法日期/offset可靠标签 | +08:60 等 offset 和不可能日期被拒绝/保留未解释原文；合法 compact date 保留 source_literal，不补午夜；原合法 offset 与分数位仍保持 | 限定 source-clock metadata 修复 CLOSED |
| F03 / P2 消费者未执行已声明 Schema | 原 bool/number const、非空 windows、缺 diagnostic label 四反例全部拒绝；六候选正向及未知/未运行仍通过；nested const/type/required/items/contains/min/max/allOf/local-ref/if-then/additionalProperties 有定向复验 | 已声明六候选 subset CLOSED |

原 R1 十个现有代码反例全部通过修复期望。时钟另复核0–9小数位整数值、负 epoch、跨日期及+08:59/±23:59等价时刻、合法 leap date；非法时/分/秒/offset、未知 -00:00、超过九位和无 offset 均拒绝。pit、DTO、maintenance 共用严格 parser，未观察到此次差异继续截断。

schema_subset 的未知 keyword 藏在 if、未命中 then、未使用 $defs、contains，以及远程 ref 藏在 if 都会拒绝，不通过条件分支吞掉。它只支持固定六候选实际声明的 subset；没有把这项检查称为通用 Draft2020-12 实现。候选 counter 的 bool/int/float representation 明确分开，不将其作为真实 money/业务配置默认。

## 独立统计与 harness 澄清

首次实际执行 **105项：104符合期望、1项失败**，保留在 `Cases-R2.json`（SHA-256 `f4493a54937c6a7855b01e71d976c86ae8d8dbd4eb1863a358cebd8e74f675a0`）。原失败 `T44_INVALID_LITERAL_REJECTED` 将 `None` 同时送给严格源时钟 parser 和 optional maintenance adapter，误要求三个入口都必须拒绝；同一批已有正向用例却正确要求 maintenance 返回 UNKNOWN=None。这是 Reviewer harness 的互相矛盾预期，不是源码缺陷。

随后只执行 **3项澄清：3 PASS / 0 FAIL**：exact_clock(None) 拒绝、pit exact_clock(None) 拒绝、maintenance._clock(None) 返回明确 UNKNOWN=None。新记录 `Cases-R2-Harness-Clarification.json`；没有更改候选或原失败日志。**不把首次105项改写成全绿，也不将两批计数或 producer123 suite 混加。** producer suite 由主控另跑，本 Reviewer 不在此认领其结果。

分组首次结果：原计算反例/控制10/10，整数/源时钟33/34（上述 harness 项），原metadata10/10，DTO/Schema消费者36/36，Schema条件与subset15/15。

## 保全与变更边界

独立流式哈希全部 MATCH：候选40 pins、主控旧972、clone旧972、专项旧954、Forward4、R1四份输出、专项最终seal209引用行/176路径（含DB与snapshot原件）、方法addendum3引用。没有查询实际DB行，也没有重新封印旧记录。原 Frozen StrategySpec SHA-256 `d4eb866d6675e52f4b5158374f94a3152e4ae406c62add22a8c807762b0215da` 和两 family 保持；原 R1 REQUEST_CHANGES 及专项原 R4 范围证据不覆写。

新 commit 差异仅13个路径：clocks/schema_subset新增、DTO/pit/maintenance消费桥、两测试路径和六candidate Schema。逐对象恢复旧ID/version再比较，六Schema内容均与专项逐字段相同；只有 `1.0.0-candidate`→`1.0.1-candidate`。无 native16、旧Schema/迁移、依赖锁、策略或 Forward 修改；source_literal 是可追踪原日期字面量，未引入真实日期/费用默认。

## 继续保留的条件

六接口最终字段矩阵沿用 R1 的保留/待定项，不能因本次修复冻结为可执行业务合同。R1 三个额外字段探针中，EXACT/null 矛盾已由候选额外明确拒绝；metrics必需key和 record security/namespace scope 仍未指定，保持最终字段待审，不强加默认或把它们升级成新的实际采集漏洞。完整 namespace/mode/身份、source/clock proof、money/rounding/partial-fill/date profile、窗口anchor/包含性/purge对象/embargo起点/跨窗现金/删失、逐交易审计链仍需正式合同和 Owner 决策。

本次只通过 P1 限定软件缺陷闭环；实际历史 PIT/许可证明未获得，实际 registry仍空、formal windows=0、完整family NOT_COMPUTABLE、引擎未运行、实际经济指标NULL。methods v1.0.1 Owner pending，并未采用；账户/真实费用/风险继续 UNSET_REQUIRED。实际市场、credentials、DB读取/改写、fit/策略/交易请求均0；生产始终 false。不能据此自动开展数据采集、正式回测、Forward实测、人类审核签名或下一业务阶段。

证据文件：`Independent-Interface-Review-R2.json`、`Cases-R2.json`、`Cases-R2-Harness-Clarification.json`。该软件审查可供主控决定隔离工程集成，不能替代 Owner 方法/政策批准、独立人类真实审核或执行授权。
