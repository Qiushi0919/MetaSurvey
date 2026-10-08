# MetaSurvey：五年专项 P1 集成与 Forward 保全验收

2026-10-08；本报告由主控维护。旧专项 P1、R3/R4、CORE40 方法提案与历史封存报告仍按各自版本保留，本报告补充后来发现的边界问题，不覆盖旧结论。

**主控本轮结论：限定工程集成 PASS_WITH_CONDITIONS。** 修复副本已合入主控验收分支 `review/backtest-5y-p1-20261008`，固定代码 `37ec2ec9f8f16d406b10f2e2724858fc1a58f375`。新增40路径，原主控972文件全部保留。专项自己的worktree、分支、交付HEAD和37份原文件仍原样，未替专项Owner解除交付后STOP。这里的合入是可选工程模块保留，不启用采集或实际运行。

独立R2为 `PASS_WITH_CONDITIONS_FOR_ROOT_ISOLATED_P1_REPAIR`，三项软件发现CLOSED；最终共享字段冻结仍HOLD，正式历史PIT/完整策略/方法批准/真实执行仍未放行。主控合入后复验123专项合成测试+35隔离/Forward用例，全PASS（158个不同producer用例，前后副本重复执行不累计）。

## 验收边界

本轮审阅五年专项交付 HEAD `4252876e23224df5d29c20492a08da9436dccf4a`，代码 `cfbd2092a7ded31803647314410e04d0b6578fc5`。主控只读核对209引用行/176唯一路径全MATCH，并在隔离副本重跑110项原合成测试全PASS。独立R1仍发现三个未被旧suite覆盖的问题，因此原PASS不等于最终接口验收。

F01/P1：截断纳秒会把截止时刻后1ns的合成财务版本纳入诊断，错误形成八季度/TTM=400；正确为七季度、NOT_COMPUTABLE、TTM=null。F02/P2：非法offset与不可能日期被标为可靠时钟。F03/P2：布尔与数值const混同，且消费者忽略已声明的空windows和诊断labels约束。R1自建31项中18项符合、10项反例、3项坦陈的最终字段缺口探针；不把后3项升级成新业务漏洞。旧实际数据是否污染未得到证据，本轮也没有运行实际引擎。

专项按自己的Owner交付后STOP保持原工作区。主控在集成私有副本准备限定修复，不通过发送新消息替代专项Owner阶段授权。候选代码 `37ec2ec9f8f16d406b10f2e2724858fc1a58f375`：共用整数UTC纳秒解析（0–9位小数）；严格日期、时分秒/offset范围；未知-00:00与更高精度拒绝；非法源字面量保持未解释。compact日期规范化时另保留source_literal，不补午夜。递归执行六候选Schema已声明的约束，明确只支持固定子集，未知关键词/引用失败关闭；const须精确JSON表示类型，计数零不能由false或0.0替代。原日期metadata测试仅扩展原文字段的预期，未放宽门禁。

六Schema ID/version升为1.0.1-candidate；没有改变原生16合同、原有六份基础Schema、001–006迁移、依赖锁、两家族或Frozen StrategySpec。方法提案v1.0.1依然仅候选，M01–M08未获Owner批准，不被本次clock修复导入或激活。

## 测试与数据事实

主控固定候选123合成用例全部通过，另11隔离+24Forward=35用例通过。原110与固定123是前后版本重跑，不能累计成233独立测试；独立Reviewer结果另外计，哈希核验不计为用例。实际数据、凭证、私钥、交易、模型拟合和调参操作均为0；全系统旧suite本轮未重跑。合成测试的六个临时路径常量仅运行时重定向到新临时目录，source/schema/冻结策略字节不因此改写；网络在测试进程禁止。

专项已经有7,567股票价格日期、582财务报告期记录，300capture/35,621绑定行/35,606内容版本；这些是现有封存事实，不是本轮新增请求、独立样本量或历史可见性证明。3,633股票日期×两家族=7,266全NO_DECISION；完整引擎ENGINE_NOT_RUN、策略NOT_COMPUTABLE、经济指标NULL。price-only/full-family实际PIT均0、正式窗口0、untouched_oos=false。旧库和snapshot原件只做哈希，不重生成正式成绩。

## 接口与下一步约束

六DTO是有界未运行候选：HistoricalEvidenceBundle、AdmittedHistoricalSnapshot、StrategyFeatureDecision、DatedExecutionEconomics、WalkForwardWindowPlan、AuditableSimulationRun。最终共享合同冻结仍HOLD：完整required/optional、namespace/mode、安全身份、所有单位/金额/rounding、proof/receipt/hash链、reason/invalidation及正向运行状态尚需后续冻结。真实本金/费率/风险不猜；HALF_EVEN/HALF_UP桥、部分成交最低佣金聚合、WF anchor/边界/purge对象/embargo起点/跨窗现金/持仓/删失政策仍待确定。

Forward仍由主控负责。四份Day0/来源/receipt/D1原件字节不变；实际capture目录未出现，D1结果文件0字节，Snapshot B未运行，实际前向天数0。现有双人公钥与setup验签不等于实际Capture/Review/Forward或预测签名。本轮未查钥匙串、未新建授权、未采集行情、未设置自动运行。D1目标10月8日、D5目标10月14日、D10目标10月21日保持；不能事后改Day0或捏造当日计数。

后续先完成Owner方法/执行经济/窗口政策决定、六DTO字段冻结及合法PIT原件闭环，再重新审完整两家族运行资格。Forward只有实际当日原件及独立人类签名链齐备，才可按现有合同追加真实揭晓；软件PASS不补这些证据。实盘、券商、云端导出、正式OOS/历史回测及策略优化继续BLOCKED。本轮验收后停止，不自动进入下一业务阶段。

## 独立复审统计与失败留档

独立R2首次105用例：104符合、1项Reviewer harness预期冲突；原Cases-R2保留，新3项澄清3/3通过，源码未因此再改。原R1十项软件反例均关闭，限定修复无open finding。六Schema逐对象核对只升级ID/version；维护适配器None=UNKNOWN与严格parser必须拒绝None分别验证。独立统计不混入158个producer用例。

合入后保全：主控旧972/专项旧954/Forward4/集成40源码均MATCH，233封存/审查/输入引用行（185唯一路径）MATCH，专项HEAD仍4252876且清洁。原库hash `0f894cc5752689ec6f3c597469fc7b92729b1f0e8033e6b1a002e1490db706db`、snapshot hash `05acf30a03d7f4d3f8bf543d6f5baff6fbdb8f89bf8530f32527c20cda569d6e` 不变。最初主控保全脚本错误要求所有hash都含sha256:前缀，误判212引用行；原FAIL Integrated-Preservation.json保留。新Integrated-Preservation-Corrected.json只在检查时兼容原有裸hex/带前缀hex表示，重新读同一原件得到233/233MATCH，没有修改旧seal/期望hash/数据/ledger。此前开发阶段122用例PASS日志也保留，最后增加窗口约束用例后固定候选为123，122不另累计。

## 阅读与恢复

本报告及 `Status.json` 是主控本轮补充结论；`Remaining-Contract-Gaps-v1.json` 列六接口最终冻结前条件。`Evidence-Index.json` 绑定本轮私有源码候选、独立R1/R2和失败/澄清、合入前后测试、保全与Forward读回。源码修复独立于待批准的方法提案；CORE40方法Owner决定见既有 `docs/core40-method-proposal/Owner-Decisions.md`。

交付ZIP包含本报告、六字段缺口表、独立审查、修复源码快照、测试与失败/澄清证据、SHA清单及增量Git bundle。没有打包实际历史数据库或供应商原始数据；需要基线11fba19和本机既有私有档案，不宣称离线包能独立重演真实数据或提供历史PIT。旧方法/专项验收包不被替换，本轮新增独立验收包。
