# 五年历史回测专项六接口：独立只读审查 R1

结论：**REQUEST_CHANGES**。当前计算路径与六接口最终共享合同冻结暂不接受；已有工程资产可以继续只读封存、隔离保留。这不是下一业务阶段授权。软件审查不签发数据 PIT、许可、人类审核或真实执行权限。

审查对象：代码 `cfbd2092a7ded31803647314410e04d0b6578fc5`；交付 HEAD `4252876e23224df5d29c20492a08da9436dccf4a`，工作区清洁。六 DTO 全为 `1.0.0-candidate`。原 Frozen StrategySpec SHA-256 `d4eb866d6675e52f4b5158374f94a3152e4ae406c62add22a8c807762b0215da` 保持不变，两 family 未被替换。

## 已复现的三项缺陷

**F01 / P1：源时钟截断造成当前财务诊断的未来数据过滤失效。** `pit.py:26–32` 把任意小数位 ISO 时刻交给微秒精度的 `datetime.fromisoformat`。`strategy.py:101–121` 依赖其比较，在 `financial_quarters` 中先判断 first_visible 再查看 payload；调用入口在 `strategy.py:354`。

独立合成输入包含八个连续季度、明确 DISCRETE_QUARTER 和 CNY，最后一个版本 first_visible=`2020-01-10T00:00:00.000000001Z`，cutoff=`2020-01-10T00:00:00Z`。正确过滤应只留七个季度，TTM 无法计算；实际将两时刻当作相等，保留八个，输出 `RAW_CLOCK_ELIGIBLE_ARITHMETIC_ONLY`、TTM revenue=`400`。微秒后的对应版本会被正确排除，说明是精度边界问题。输出 `historical_visibility_proven=false` 和未运行引擎，不能让这项诊断计算自动获得未来数据安全性。

要求在新候选中以无损精度比较，或在计算前拒绝不支持的精度；严格验证 offset，增加 1ns、等价 offset 和未来 payload 不读取的独立反例。不可改原始数据或策略阈值让测试通过。**这里只证明合成边界会泄漏，未声称旧实际数据已污染，也未声称实际/正式回测已运行。**

**F02 / P2：无效源日期/offset 被赋予可靠精度。** `dto.py:7–20` 将 `2020-01-10T00:00:00+08:60` 标为 `EXACT_SOURCE_RECORDED`，派生 timezone=`+09:00`，却保留无效原文字；`pit.exact_clock` 同样接受它。`2020-99-99` 被标为 `DATE_ONLY`，因为只检查长度十。要求在确定日期/精确时刻标签前做完整日历/时间/offset/精度校验；无法解释的原文应保留为未解释，不静默推断。合法日期仍保持 timezone=null、不补成午夜。

**F03 / P2：有限消费者未执行已经声明的 JSON 约束。** `dto.py:51–84` 用 Python 相等判 const，`productionGate=0` 与 false、`formal_windows_executed=false` 与零均被接受；此外非空 windows 违反 Schema 的 maxItems=0、空 labels 违反 contains NON_PIT_DIAGNOSTIC，也返回 True。要求按 JSON 类型处理 const/enum 并执行所有已声明约束，保留合格的 UNKNOWN/未运行候选；不要通过删掉约束或放宽门禁修复。

## 六 DTO 的字段兼容性

| DTO / 版本 | 当前可保留语义 | 最终接入前仍缺 / 当前结论 |
| --- | --- | --- |
| HistoricalEvidenceBundle / 1.0.0-candidate | 四时钟与 first_visible、披露原文、raw/record hash 与 selector、未知修订/区间/单位/许可保持分开 | F02/F03；时钟有效性、完整类型/精度一致性、namespace/mode/安全身份、proof/receipt/reasons/invalidation 需终审；HOLD |
| AdmittedHistoricalSnapshot / 1.0.0-candidate | BLOCKED/fixture-only，实际准入和 full-family false；独立实际 manifest registry 为空 | F01/F03；正向覆盖、数据时刻/hash/许可/issuer/receipt 链尚无完整字段合同；HOLD |
| StrategyFeatureDecision / 1.0.0-candidate | 两原 family/spec hash；诊断与完整 family 分开；ENGINE_NOT_RUN/NOT_COMPUTABLE | F01/F03；逐日期/证券/单位/未知维度/源链类型与完整前置条件待闭；不得采用待 Owner 批准新方法；HOLD |
| DatedExecutionEconomics / 1.0.0-candidate | 实际 profile UNSET；Wave F HALF_EVEN 与 parent HALF_UP 分开；未批准 partial-fill/rounding bridge | F03；dated fee/money/slippage/订单聚合/profile trace 等需规范，真实参数继续 UNSET；HOLD |
| WalkForwardWindowPlan / 1.0.0-candidate | 原36/12/6/step6协议，anchor=null/windows=[]/formal0/untouched=false，边界明确未定 | F03；参数类型、真实 session 网格、anchor/包含性/purge对象/embargo起点/跨窗现金/删失需 Owner/合同审查；HOLD |
| AuditableSimulationRun / 1.0.0-candidate | 未运行≠无交易；经济指标 NULL，不假装零收益；ledger/NAV 不可用 | F03；metric必需名与单位、状态enum、逐订单/fill/现金/NAV和拒绝/失败/未退出 trace 尚未完整；HOLD |

上述未定字段已在专项文档明确披露，没有把候选合同冒充成最终 Schema；它们属于后续字段冻结条件。空 metrics、EXACT 与 null 矛盾、超出三股证券 scope 三项仅作为最终合同缺口探针，**不增加成三项现有业务漏洞，也不据此指称当前实际采集越界**。本轮重点只要求 F01–F03 限定工程闭环；其他字段/业务政策不由 Reviewer 自行补默认值。详细 required 字段、Schema pins、每个接口的保留/修复/最终条件在 `Six-DTO-Field-Matrix-R1.json`。

## 独立证据与检查范围

31 个定向合成用例：18 项符合期望；10 项复现上述现有代码边界缺陷；3 项记录已披露的最终合同未完备点。分组：计算 4/8 满足、metadata 4/6、现有保守门禁 10/10、已声明 Schema 消费者 0/4、最终字段缺口探针 0/3。不是原专项 110 suite 的失败统计，本 Reviewer 没有重跑该 suite。现有空实际 manifest registry、true production 拒绝、缺版本拒绝、实际 false 与 record false 区别、未运行非 NULL 指标拒绝均得到复核。未安装/运行完整 JSON Schema validator，不宣称完成该校验。

独立重新读取与哈希：候选 source34/inputs127、交付42、封存 DB 与 snapshot2 全 MATCH；旧保全1949引用行/1938独立路径全 MATCH，其中主控旧954、专项旧954、Forward4、交接17、首轮审查20均保持原字节。只流式哈希 DB，没有查询、改写或重新封印。失败旧 epochs 和旧 R4 PASS 范围仍应原样保留。

此前独立 harness 因授权 reviewer 输出目录尚未存在而在导入/运行前停止；本次仅创建被授权的新输出目录并重新运行，初次 harness 错误已记录于 Cases JSON，未归为专项缺陷。

## 集成决定与权限边界

允许隔离封存原工程资产；当前计算复用与最终共享合同验收 **REQUEST_CHANGES**。F01–F03 需在新的候选 commit/epoch 修复，保留旧 code/report/seal、数据原件和 Frozen/Forward。主控不能覆盖专项已经 STOP 的 worktree。新候选仅做差异独立复验和已有工程范围回归，不据此采集新数据、采用新策略方法或开放下一阶段。

即使修复通过，六 DTO 仍需精确字段和消费者兼容终审；实际历史 PIT=0、formal windows=0、完整 family NOT_COMPUTABLE、收益为 NULL、methods v1.0.1 Owner pending、账户/真实费用/风险与窗口政策继续 UNSET_REQUIRED。许可、真实原件可见性/修订链、完整策略覆盖、实际账户成本、人类独立审核与执行授权仍不能由 software PASS 替代。本轮市场/secret/模型 fit/策略/交易请求均为零。

输出：`Independent-Interface-Review-R1.json`、`Independent-Interface-Cases-R1.json`、`Six-DTO-Field-Matrix-R1.json`。所有输出为新只读证据，未修改主控/专项源码、合同、Git、旧 DB/封印或预测原件。
