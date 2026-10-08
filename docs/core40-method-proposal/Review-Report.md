# MetaSurvey 主控：方法提案与双线协同审查（2026-10-08）

本轮完成可供Owner确认的 **CORE_40 方法候选 v1.0.1**，独立软件/方法规格审查为 **PASS_WITH_CONDITIONS**，无未关闭的软件finding。它补齐WACC、周期正常化、估值、情景概率/缓冲、净Edge与评分等级的具体计算选择；**尚未获Owner批准、尚未应用、没有真实fit/回测或Edge证据**。

五年专项继续独立worktree；主控保留Forward与全局合同、策略版本和最终集成职责。专项本批仍在完成自己的最终Gate，本文不代其宣告最终验收。既有主要Source of Truth、Frozen StrategySpec v1和Day0预测不变。

## 已交付的具体方法

| 候选 | 计算与决定 | 主要实际输入/失败条件 |
| --- | --- | --- |
| M01 资本成本/ROIC | CNY CAPM、104完整周beta/2⁄3收缩；WACC包含母公司、各NCI价值与独立权益成本、合并债税盾；TTM NOPAT/平均IC | dated rf/ERP/信用/税与合并资本桥；非零NCI成本或价值未知不默认母公司Ke |
| M02 周期盈利 | 最近5个可比且当时已披露年度的EBITDA利润率中位数×当前TTM收入，包括亏损年 | EBITDA经营/D&A桥、收入、重述/会计范围/PIT；缺年或非正正常化分母阻断 |
| M03 估值 | resource归一化EV倍数，另两角色正PE；1260逐cutoff弱排名与中位倍数权益桥 | 不能凑窗口外样本/用后来利润回填；解释性fair-price空间不冒充40日收益 |
| M04 情景概率 | 单独待批EX_EDGE成熟反事实标签，family×历史行业；±200bp三桶、alpha1平滑及桶内均值 | 同域、全部非Edge/Timing满足才适用；未触发观察不借用条件概率；样本不足不编概率 |
| M05 缓冲/校准 | 4×3m留时验证折、固定概率箱、联合session moving-block、2000 draw与nearest-rank；sampling LCB+留时乐观偏差 | fit≥16、validation≥4有事件块仅为覆盖；稀疏桶/空draw/延期尾部可阻断，不宣称独立性或统计功效 |
| M06 费用后Edge | 保留净Edge≥400bp、净比率≥5；BASE/PESSIMISTIC各算；加档ΔNet严格>0 | 未定义手续费/滑点/机会成本不填0；真实profile仍UNSET，不重复扣滑点 |
| M07 分数/等级 | 具体七维anchor、Research轴、连续Decimal等级及HardBlock/UNKNOWN优先级 | 概率离域/未知不给Final/交易等级；单独research_priority不等于A/S可交易；S只请求人工 |
| M08 生效 | Owner选择后另建方法及策略版本、合同/pins/事前登记、专项接入与集成验收 | 不重写旧v1/hash、旧结果或Forward；不根据收益回调方法 |

完整公式、理由、替代方案、时间/单位/失效条件见 [Methods-v1.md](/Users/qiushi/投资研究/ashare-trading-v1/docs/core40-method-proposal/Methods-v1.md)；数字参数见 [Proposed-Parameters-v1.json](/Users/qiushi/投资研究/ashare-trading-v1/docs/core40-method-proposal/Proposed-Parameters-v1.json)；新增原始字段与四钟/版本/许可要求见 [Data-Requirements-v1.json](/Users/qiushi/投资研究/ashare-trading-v1/docs/core40-method-proposal/Data-Requirements-v1.json)。它们都是提案sidecar，未更改native合同/生产配置。

[Owner-Decisions.md](/Users/qiushi/投资研究/ashare-trading-v1/docs/core40-method-proposal/Owner-Decisions.md) 是本轮需要确认的M01–M08清单。软件Reviewer和主控均不能代Owner选择。方法选择不包含真实本金、券商费用、仓位风险、数据许可/PIT或执行签名批准。

## 独立审核与失败保留

首版R1发现：纳秒截断可能接收未来标签；合并ROIC与不含NCI的WACC口径不一致；合格机会概率被外推到未触发观察；校准算法分箱/时间折/抽样定义不足。R2又发现非法ISO offset分钟会被正常化。五项均由新候选修复，旧失败报告、候选源文件和Git commit保留。

最终固定代码候选：`f20ef3667ecf5f0340592dc54d09c3922e3ca5b3`。R3方法正文/参数/Owner单/字段表与已审R2逐字节相同；最后修复仅为offset格式拒绝和相应用例。

| 验证 | 结果及范围 |
| --- | --- |
| 主控最终合成测试 | 75/75 PASS；干净本地clone重复75/75，不合计为150独立测试 |
| Independent Reviewer R1 | 40反例：39 PASS / 1 FAIL；另有方法口径/规格finding |
| Independent Reviewer R2 | 64反例：62 PASS / 2 FAIL；原4项关闭，offset范围待修 |
| Independent Reviewer R3 | 34独立差异反例全部PASS；5项全部关闭，无open finding |
| 旧工程/预测保护 | 主控先前963文件、4Forward保护文件、R1/R2候选存档均逐hash匹配 |
| 两边代码边界 | 各954旧文件PASS；专项37个新/变更路径全部在约定目录内；是读取时点检查，不是OS权限隔离 |

本轮没有跑全项目回归、真实模型拟合/概率校准、策略引擎、ledger replay或市场采集；不能以合成算术和索引用例PASS冒充真实绩效验证。G1曾有精度期望用例失败、G3曾有UNKNOWN拒绝的异常类型不一致；原日志与失败代码均保留，未调整旧业务门禁以凑全绿。

独立原报告：[R3](/Users/qiushi/投资研究/.p1b-archives/core40-method-proposal-20261008/reviewer/Independent-Review-R3.md)；机器结论、34反例证据及R1/R2均随验收包提供。独立审查不替代另一位真实审核人的数据/执行签名。

## 并行与共享接口

主控分支 `research/core40-method-proposal-20261008`；专项 `/Users/qiushi/投资研究/ashare-backtest-5y`，读取时HEAD `cfbd2092a7ded31803647314410e04d0b6578fc5`。主控没有修改/覆盖专项worktree，没有合并其代码。

前一轮六个共享接口的语义方向仍为APPROVE_WITH_CONDITIONS：HistoricalEvidenceBundle、AdmittedHistoricalSnapshot、StrategyFeatureDecision、DatedExecutionEconomics、WalkForwardWindowPlan、AuditableSimulationRun。具体字段schema、时钟精度/失效、标签与window边界、consumer端到端证明仍需专项固定候选后由主控审核。旧16 native contracts、6 Schema、001–006 migrations、策略/锁/历史资产均未改变。

专项通报已建20类111逐字段数据依赖，三股有7567个价格日期及582条四类财务记录；**这些是专项采集覆盖事实，未在本轮另行做原件逐行准入审核，不能推出历史PIT或full-family可运行**。其正式price/full PIT仍0、完整引擎未跑。本文新增要求特别列明ERP/信用/NCI/经营EBIT/D&A/年份可比桥等额外输入，不把供应商拼写当新硬门槛。

## Forward与真实数据链

Day0预测、来源和freeze receipt保持原hash。当前注册actual capture目录不存在，D1 journal仍0字节；实际前向天数仍为0，Snapshot B未运行。本轮无secret/private-key读取、市场请求、store追加或自动运行，也未重写已冻结预测。

继续按原顺序独立验证：Owner CAPTURE签名 → 实际原件 → 真实独立Reviewer REVIEW → Snapshot/store head → Owner另签FORWARD → 合规append与D1揭晓。公钥setup验签和聊天授权不代替已有合同要求的这三份执行签名。不能拿专项回顾采集替换当日Forward证据。当前不需要提供Token或密码。

## 尚未解除的条件与下一步

1. Owner明确确认候选v1.0.1的M01–M08，或指定修改；本轮停在提交确认，不自动采用。
2. 若批准，另审新的方法/策略版本和六个接口字段；旧Frozen v1不动。
3. 继续在原授权范围内补真实资本/财报/PIT/许可/历史industry/TR、假设经济政策与实际费用的各自证明，禁止latest回填。
4. 独立实现并验收成熟标签、fit/fold/联合重采样/校准；每次run冻结输入/参数/hash，不删除失败窗。
5. 数据与政策真正通过后才可按原正式OOS协议另行放行；暴露历史仍不得改untouched=true。Forward实际数据/签名链独立推进。

真实账户资金/费率/风险、provider/license、历史首次可见/修订链、正式OOS资格、真实概率与费用后Edge、实际Forward签名/native order/broker/cloud/production仍UNSET_REQUIRED或BLOCKED。当前PASS_WITH_CONDITIONS仅表示方法候选软件规格可交Owner审阅。
