# MetaSurvey｜Five-Year Historical Backtest P1 Gate Review

2026-10-08。专项工作区 `/Users/qiushi/投资研究/ashare-backtest-5y`。已执行真实历史采集、原件处理、增量维护、冻结两家族的前置条件诊断及工程独立复审。本批没有完整模拟交易实验。

## Gate 结论

**R3 原工程与 R4 最终补审均 PASS_WITH_CONDITIONS，仅限定工程层；当前无未关闭软件发现。完整策略、真实 PIT 和正式 OOS 保持 HELD。** 收益、费用、期末资金、回撤、MAE/MFE/MAE40 与基准超额均为 null；当前正确状态是 **ENGINE_NOT_RUN + NOT_COMPUTABLE**。不能发布 NO_TRADES、0 收益、DIAGNOSTIC_RESULT 或 FORMAL_PIT_RESULT。

固定 R3 代码 `a07ee5cc2a883e1a4fc662c6faf77c9c704b6019`；新增验收适配器修复固定代码 `cfbd2092a7ded31803647314410e04d0b6578fc5`；旧补充候选 `73c22b75784a138e92b174a976511d141f876096` 及失败证据保留，只新增两源码文件，R3 原32文件字节不变。R1/R2失败审查、原输入、错误与旧运行均保留。没有 push、自动合并或由专项修改原主控文件。

| 验收层 | 实际交付 / 当前限制 |
|---|---|
| 三股真实数据 | 7,567 个价格日期；582 条四类财务报告期记录；两股长估值/因子，公告原件和当前状态片段；不是完整 PIT 数据 |
| 统一原件库 | 300 捕获登记、35,621 捕获绑定行、35,606 内容版本；原件重解析/行绑定/哈希审计通过，不把计数当独立样本量 |
| 实际重复维护 | 第二批40请求/22新捕获/479捕获行；消耗更新计划并重新检查缺口。固定初版180批离线重放、0网络，价格/家族投影一致；累计捕获与一次导入的不同计数留档 |
| 详细 prompt 验收材料 | 已生成20类111逐字段依赖行、Five-Year-Coverage、PIT-Admission-Progress、原件清单、来源/许可矩阵、历史池和引擎适配进展 |
| 两家族前置检查 | 3,633唯一股票日期 × 两家族＝7,266前置决策，全NO_DECISION；完整引擎未调用，未发出交易候选 |
| 输出状态 | 20项输出逐项登记：2项NOT_COMPUTABLE、16项ENGINE_NOT_RUN、2项BLOCKED；order/trade/NAV/绩效不存在，MAE40和期末资金为空 |
| 工程测试 | 固定R3 Root及Reviewer97/97；独立26＋18＋27反例全通过，19项实际读回断言另计。最终Root及独立Reviewer110/110；新增独立28/28、51/51、23/23、12/12全通过，28实际完整性断言另计，旧失败不累计为通过数 |
| 历史准入 | 真实price-only/full-family PIT均0；所有42逐股coverage条目未准入；原件完整性和合成正向检查不签发真实PIT |
| 策略和时间 | 两冻结家族/Spec hash未变；已曝光历史untouched_oos=false，正式窗口0；没有按结果删除失败策略/样本或调参 |
| 接口 | 六类metadata DTO/Schema仍候选，有限消费检查通过；完整JSON Schema与共享字段/跨模块兼容须原主控终审 |
| 产品/权限评估 | 四家具体产品、12组字段申请、27官方证据；实际许可/完整vintage/first-visible/留存未验证，没有采购或注册 |

[完整缺口与维护报告](</Users/qiushi/投资研究/ashare-backtest-5y/docs/backtest-5y/CORE40-Data-Gaps-and-Maintenance-P1.md>)；[重复验收用法](</Users/qiushi/投资研究/ashare-backtest-5y/docs/backtest-5y/Acceptance-Usage-P1.md>)；[R3固定输入](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/Candidate-Manifest-R3.json>)；[新增固定输入](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/Candidate-Manifest-Supplement-R4.json>)；[12项实际产物哈希清单](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/acceptance-04/Delivery-Package-Manifest.json>)。

## 独立审查与已修复问题

[R1](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/reviewer/Independent-Review.md>)为REQUEST_CHANGES：最新可见财务季度整期缺字段可能被跳过，未知金额单位和混币可能进入计算。[R2](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/reviewer/Independent-Review-R2.md>)关闭这两项，但发现同季较晚可见口径未知版本仍可能退用旧有效版本（F03）。

[R3](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/reviewer/Independent-Review-R3.md>)关闭F01/F02/F03/C01，**无剩余软件发现，限定工程PASS_WITH_CONDITIONS**。最新季度缺失、单位/币种/尺度不明、口径/数值/alias冲突、较晚版本删除字段、同钟复用revision ID却内容矛盾均阻断对应财务cell；正常分域稀疏记录、完全相同重复和明确CNY的YTD差分仍可算。未来first-visible版本先过滤。没有推断FX/尺度转换、补造数据或修改策略。

R3与新增报告生成均对原正确路径的库执行只读检查，数据库hash仍 `0f894cc5752689ec6f3c597469fc7b92729b1f0e8033e6b1a002e1490db706db`；原snapshot不变。此前Root改名复制库触发原件内容寻址目录保护的run05失败保留，没有弱化审计，未宣称移动库文件即可迁移。

双方各954旧文件、Forward4、交接引用17、首轮产物20共1,949引用行（1,938唯一路径）已逐字节保全；新增固定源/输入一致。[补审前保全](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/Final-Preservation-Supplement-PreReview.json>)、[新增实际读回](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/Acceptance-Actual-Readback.json>)。旧失败/原件不覆写；最终交付索引绑定下列独立补审结论与关闭保全。

[初次补充审查](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/reviewer/Independent-Review-Supplement.md>)发现新增适配器 Supplement-F01/P2：重算hash后的伪造时钟/身份或未来/跨证券价格引用会被报告入口接受，28独立反例中11失败。真实产物25完整性断言均通过、没有发现污染。修复将catalog全部15字段绑定原记录，实际PRICE窗口日期/证券/域及嵌套引用、snapshot日期/证券逐项校验；新acceptance-02的两账本和另外8项JSON字节与旧acceptance-01相同。旧失败报告和接受坏输入的夹具保留，不把软件修复称为真实PIT关闭。

[补审R2](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/reviewer/Independent-Review-Supplement-R2.md>)已关闭上述P2；新增F02/P3指Python等值比较会把False/0.0当作整数0，51新增边界中2失败。最终候选改为canonical JSON字节比较，拒绝类型不一致；Root109测试通过，真实acceptance-03的10项文件与acceptance-02字节相同，[独立补审R3](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/reviewer/Independent-Review-Supplement-R3.md>)已关闭F01/F02。原R2条件和失败证据保留。

Root随后指出日期编码旁路，[独立日期附加审查](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/reviewer/Independent-Review-Supplement-R3-Date-Addendum.md>)复现F03/P2：基本日期/周日期会normalize到同一天，但原字符串比较可放过未来PRICE/重复日期；12边界中7失败，原补审R3结论不覆写，附加Gate为REQUEST_CHANGES。最终候选仅接受规范YYYY-MM-DD决策日期，Root110测试通过；acceptance-04的10项文件与03字节相同，实际原报告日期全规范，未受污染。[最终独立R4](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/reviewer/Independent-Review-Supplement-R4.md>)已关闭三个补充发现。110工程测试及28/51/23/12独立边界全部通过；28项实际包完整性断言单列，固定34源/127输入及1,949旧引用匹配。

## 下一轮阻断项与原主控协调

1. **数据访问**：现有月度网关返回IP并发限制，不证明积分/权限不足。新代码在该错误后停止剩余请求。Clash系统代理关闭但TUN路由存在，中国IP DIRECT规则存在，实际出口和供应商共享上游未证；未改代理设置，没有可靠自动解锁等待时长。
2. **数据证据**：补齐EBITDA/净债务及财务原始/修订披露链、603228历史估值/因子、早期实际日历、完整上市/退市/ST/停复牌/涨跌停/公司行动、历史行业成员与总收益、合格催化/风险证据、完整历史股票池及许可总收益基准。当前采集时间不等于当年可见时间。
3. **方法冻结**：按Owner最新决定，已联系原主控聊天“制定A股系统重构执行计划”，要求先找已有定义，再提交WACC、周期盈利、估值推算、情景/概率/缓冲/校准与等级映射的公式、参数、数据需求、理由和替代方案，经独立Reviewer及Owner审批。原主控已核对既有公式、补齐候选方法/原始字段/算例，并完成独立PASS_WITH_CONDITIONS，正在发布提案包，等待Owner最终确认；既有概念公式不能代替未接受的完整可执行方法。提案不能直接改Frozen StrategySpec或取得策略验证资格。
4. **资金与执行**：真实账户仍UNSET_REQUIRED；允许情景名BASE/PESSIMISTIC/UPPER-BOUND，但本批没有给默认本金/费率/滑点。Wave F纯成本检查已覆盖整数分、HALF_EVEN、最低佣金、内含滑点一次计入；HALF_UP桥、部分成交费用聚合、完整历史执行适配、ledger/NAV核账和风险/仓位政策尚未接受。NetEdge未知/零成本阻断；额外分档增量收益不高于增量成本则Micro-Ladder拒绝。
5. **扩池和正式测试**：三股完整数据、方法和接口通过后先跑两完整家族，形成真实price-only PIT正向样本，再核验CORE_40历史成员，之后审全A历史一个月。必须纳入历史暂停/退市/ST，不能只用今日存续股。TRAIN→VALIDATION→SEALED OOS→WALK-FORWARD保留，正式起点/边界/跨窗现金持仓与40实际session的purge/embargo需另验；已曝光区间不能重包装为untouched OOS。

权限交付见 [产品/字段申请](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/data/vendor-access-v3/Vendor-Access-Assessment.md>)。优先核对现有合同或合法完整导出；无需同时买四套，也无需在聊天中发送Token。Owner授权固定网关只读访问不等于上游许可、本地保存或PIT准入。

## 关闭动作

新增定点独立补审已完成，Root提交本Gate并完成最终封存。按Owner本轮停止条件 **STOP，等待Owner Gate决定**。可重复更新代码保留；未安装无人值守任务。原主控方法提案按Owner授权独立继续审核，本专项不自动采用候选方法。

没有实盘、券商下单、productionGate=true、EVENT_3、Forward Day0/Day1改写、真实签名或自动合并。当前交付用于隔离工程和证据等级审阅，不发布完整策略收益或正式五年成绩。

最终封存索引：[Delivery-Index](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/Delivery-Index.json>)；[最终保全](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/Final-Preservation-P1.json>)；[完整失败/限制索引](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/Known-Failures-Final.json>)。这些文件只新建，早期失败状态与旧产物保留。
