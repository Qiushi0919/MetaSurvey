# CORE_40 完整计算方法候选 v1.0.1

状态：**PROPOSAL_ONLY / OWNER_APPROVAL_PENDING / NOT_VALIDATED / NON_TRADEABLE**。这是可审查的方法候选，尚未应用到现有策略。当前 Frozen StrategySpec SHA-256 `d4eb866d6675e52f4b5158374f94a3152e4ae406c62add22a8c807762b0215da` 及两个 family 均不改。参数表中的数字是新方法的待批准研究设定，不是真实账户、券商费率或生产默认值。本轮不读取真实股票结果来选公式、阈值或模型，不运行真实回测。

## 1. 已有定义与真正缺口

| 范围 | 已有定义与引用 | 本次处理 |
| --- | --- | --- |
| 财务与 Timing 硬门槛 | Frozen v1：四季/八季、收入增长、毛利率变化、OCF/NI≥0.8、净债务/EBITDA≤3、两 family 的全部 Timing 条件 | 原样引用；不加ROE/PB门槛，不改阈值 |
| 估值准入 | resource 用归一化周期 EBITDA 的EV倍数；另两股正PE TTM；前1260实际session、1260有效PIT观察、弱排名≤0.6 | 补分母、权益桥与历史快照定义；不放宽样本/排名 |
| 预期收益与Edge | 正式交接：μ=ΣpR；NetEdge=μ−费用−缓冲。Frozen v1：净Edge≥400bp，净Edge/费用≥5，零费用不无限通过 | 保留公式，补可获得、可校准的p、R、U来源 |
| 评分 | 正式交接已建议25/20/15/15/10/10/5权重、风险扣0.2、成本惩罚上限15 | 不重复设计；补各输入、Research、连续区间及优先级。这些仍未成为Owner有效政策 |
| 资本成本与周期正常化 | Frozen v1明确UNSET_REQUIRED | M01/M02候选 |
| 概率、误差缓冲、等级映射 | Frozen v1与P1B语义明确未校准/UNSET | M04–M07候选。未知独立于X；研究高≠Timing通过≠真实账户适用 |

现有 `wave_f/strategy.py` 的净Edge/费用和 `src/p1a/edge.mjs` 的增量**毛**收益/费用是不同量，不允许换名字共用。既有合成模块、Wave C相对排序和研究文字均不算缺失方法的正式定义。全局门禁、账户/执行/风险配置、本轮新方法批准是各自独立的事项。

## 2. 共通时间、单位与失效规范

所有运算有 `method_version / parameter_hash / input_snapshot_hash / code_hash / decision_cutoff / model_frozen_at / training_end / label_maturity_max / reason_codes`。这是方法sidecar候选元数据，不改16个native合同。上海决策cutoff与UTC绝对时刻对应；event、published、available、retrieved四钟及精度分别保留。DATE_ONLY不补午夜，今天的retrieved不证明历史可见。计算时钟仅接收带明确UTC offset的ISO时刻、0–9位小数，转为integer epoch-nanoseconds精确比较；更高精度/未知offset/无时区拒绝，不截掉纳秒。供应商只有日期的披露仍需独立ClockEvidence，不能因工具接收时刻就补造时间。正式历史重建必须重开独立first-visible/修订证明；缺证据只可作明确NON_PIT诊断，不能得到正式PIT输出。

TTM flow由最后4个完整、已披露单季量求和；YTD财报须同一当时可见版本前期YTD相减，第四季为已披露年度减前三季，不把后来年度数回填前三季。资产负债存量不累加；修订在其available_at之后才形成新版本。收入、利润、债、现金、市值用同一币种CNY和合并范围；股份为integer shares；价格为Decimal CNY/share；收益/率用Decimal ratio，1bp=0.0001。所有来源的万元/亿元/%先显式转换并绑定单位版本；禁float。分析精度Decimal50、HALF_EVEN；最终展示不参与边界比较。账本的整数分与既有HALF_UP/HALF_EVEN适配仍由费用桥定义，本候选不改变账本舍入。

有效期候选：国债曲线最后已知观察≤5实际session；信用利差≤20实际session；年度ERP vintage≤18日历月；最后资产负债表period end距cutoff≤220日历日。这些是待批新鲜度门槛，不是历史可见性证明。修订/撤回、原件hash或方法改变、币种/范围不一致、超期、模型标签未成熟、任一必要输入未知，输出NOT_COMPUTABLE及具体原因；不默认0，不静默换数据源/模型/窗口。

## 3. M01 — WACC与ROIC（推荐）

采用CNY名义、年化资本成本：

`Ke = rf + beta_shrunk × ERP_CN_total`

`Kd = rf + issuer_credit_spread`

`WACC_consolidated = [E_parent×Ke_parent + Σ_j NCI_value_j×Ke_NCI_j + D_consolidated×Kd×(1−tax_shield_rate)] / [E_parent + Σ_j NCI_value_j + D_consolidated]`。

ROIC、EBIT/NOPAT和债务均用合并范围，所以WACC必须包含同范围的少数股东资本。NCI为0必须有证明，不能由字段缺失变成0；NCI为0时其成本为NOT_APPLICABLE。每个非零NCI对应明确的权益价值、主体和权益资本成本，不能默认与母公司Ke相同。

这是资本成本结构，币种/市场权重与风险溢价应一致；公式依据 [Damodaran, The Cost of Capital](https://pages.stern.nyu.edu/adamodar/pdfiles/papers/costofcapital.pdf)。下面具体窗口、来源和拒绝规则是本项目的新候选，不是该论文给出的A股生产参数。

- `rf`：决策当时已可见的财政部/中债CNY10年国债到期收益率版本；[官方曲线入口](https://yield.chinabond.com.cn/cbweb-czb-web/czb/moreInfo?locale=cn_ZH&nameType=1)。不抄今天数值回填历史，原件许可/用途另核验。
- `ERP_CN_total`：当时已发布的中国市场**总**权益风险溢价年度vintage，首选可留存发布/修订证据的NYU country-risk原件；只读取total equity premium，不再重复加country premium，不拿美国ERP直接当中国ERP。无法取得对应历史vintage/用途许可时保持缺项。新数据源不因本候选而准入。
- `beta_raw = Cov(r_stock−rf_week, r_market−rf_week)/Var(r_market−rf_week)`。最近104个完整周，至少78对有效观察；使用已核验行动/分红的总收益及PIT成员/指数版本，按实际交易日历定义周终。每周以ISO周内最后实际session为周终，使用相邻周终总收益比；104窗口只包含已完整结束的ISO周，至少78对非缺失收益。`rf_week=(1+dated_rf_annual)^(实际相邻周终日数/365)−1`，ACT/365年化复利；个别缺观察不向窗口外延伸凑78，协方差/方差用相同配对和样本分母。正在形成的周不进入回归，缺bar不能自行当零收益。
- `beta_shrunk = (2/3)beta_raw + 1/3`。这是事前固定的收缩候选；不以本三股未来收益拟合收缩权重。负收缩beta、零市场方差或样本不足拒绝，不能隐式改beta=1。候选风险市场为有许可、版本可核验的CSI300总收益序列；identifier/方法仍须确认，价格指数不顶替TR。
- `issuer_credit_spread`：同币种发行人的可靠债券/融资信用报价减去相同剩余期限的国债曲线，报价/映射当时已知。不能拿平均历史利息费用/债务当作边际融资价格。缺可靠信用报价则NOT_COMPUTABLE。
- `E_parent`：母公司所有普通股种类的当时市场价值之和，扣已知库存股；异种股票按当时可见汇率/价格转换。每个上市子公司`NCI_value_j=当时子公司普通股市场价值×合并范围内非控制持股比例`，其`Ke_NCI_j`按同一CNY CAPM/104完整周协议使用子公司股票beta；股份、比例、汇率及报价绑定同cutoff。跨币种主体需先另审同币种资本成本桥。未上市NCI的可靠市场价值或独立资本成本未定义时，本候选WACC直接NOT_COMPUTABLE；不能用book NCI与母公司Ke默填。若Owner另选估计，须事前另注册价值、风险、杠杆及成本模型后新版本，不在本候选偷偷fallback。`D_consolidated`为有息债及租赁负债；可交易债用市场价值，非交易借款用显式标注的book proxy及敏感性，不能悄悄把book称market。存在未定义优先权益/混合工具时拒绝该简化WACC，等待资本结构桥。
- `tax_shield_rate`：该时点已证明适用且可使用的利息税盾；有证据不得抵扣时为0，无证据是UNKNOWN。不能自动填25%或15%。NOPAT的适用所得税率与税盾分别存储，不把净利润有效税率默认为二者。

ROIC补充候选：`NOPAT_TTM = operating_EBIT_TTM × (1−operating_tax_rate)`；`IC = parent_book_equity + NCI + interest_debt − eligible_excess_cash − nonoperating_investments`；`ROIC = NOPAT_TTM / mean(IC_begin, IC_end)`。IC_begin/end为TTM跨度两个边界的当时可见资产负债表，均需>0。operating EBIT按披露桥剔除投资/公允价值/融资损益等非经营项；合并EBIT对应合并资本，不能税后净利润代NOPAT、漏NCI或重复加NCI。operating_tax_rate须时点实际适用证据，缺项阻断。**Quality仍用ROIC_TTM>WACC，不用正常化ROIC替换。**

替代方案：bottom-up industry beta（要历史行业成员、各股beta/资本结构）、中国市场implied ERP（要当时市场现金流预测及求根协议）、发行人贷款报价替代信用债（必须新方法tag和当时可验证报价）。不默切替代；Owner在看结果前另选。推荐回归beta路径因为输入、窗口、收缩和失败条件可复算；不声称其更赚钱。

## 4. M02 — 周期盈利正常化（603993角色）

采用同公司、同业务合并范围最近5个完整已披露年度的中位数利润率，**包括亏损年份**，不只选高景气年：

`m_EBITDA_norm = median(EBITDA_y / revenue_y, last5 visible completed years)`

`EBITDA_norm(t) = revenue_TTM(t) × m_EBITDA_norm(t)`；同时可输出 `EBIT_norm = revenue_TTM × median(operating_EBIT_y/revenue_y)` 与 `NOPAT_norm=EBIT_norm×(1−tax)` 作研究解释，不替代冻结财务质量的真实TTM利润、现金流及杠杆。

EBITDA采用 `operating EBIT + operating D&A` 的明确报表桥；现金流表折旧只有经桥验证与利润表经营范围一致才可用。五年收入须>0；任一必要年度缺失、非可比业务/会计范围改变且没有cutoff前可见的重述桥、正常化EBITDA≤0，均NOT_COMPUTABLE。不得用后来披露的重述替旧cutoff覆盖原报表，不截掉负利润率，不用全历史均值。

选择理由：公司规模以当前TTM收入表达，利润率用五年周期平滑；避免直接平均旧绝对利润造成规模偏差。一般周期估值的正常化动机及不同方法见 [Damodaran, Valuing Cyclical and Commodity Companies](https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/commodity.pdf)。本候选的5年/median不是经本股票收益优选，也不保证五年完整覆盖一个商品周期；这一结构风险要报告。

数据预算必须倒推：如果最早估值warmup观察在2016，正常化又要求之前5个可见年度，则可能需约2011起年度报表及当时披露证据。不能用已有2014起采集就宣布足够，也不因此把“五年评价”改成十年评价。具体最早日期由实际session和披露可见性算出。

替代：7–10年中位利润率；产量×事前中性商品价格−单位成本−固定成本的分产品结构模型。前者覆盖需求更长；后者依赖真实历史分产品产量/售价/成本、价格长期假设及合并桥。V1推荐5年中位利润率以保持可重放，结构模型另预注册，不根据收益择优。

## 5. M03 — 估值分母、百分位和解释性价值

`NetDebt=D−eligible_excess_cash`；`EV=common_market_equity + NetDebt + NCI_value + preferred_value − nonoperating_investment_value`。NCI_value与M01资本范围一致。单独解释性EV可显示未上市NCI的book proxy及敏感性，但该proxy不自动成为WACC的市场资本；M01未闭合则整体Quality/完整family不可计算；受限现金不作excess cash；负NetDebt原样保留不截成0。市场价、股数、债/现金、NCI及非经营投资均为该cutoff可见版本，币种/合并范围一致。

- 周期角色：`multiple=EV/EBITDA_norm`；EV、分母须>0。
- 600312/603228角色：`multiple=common_market_equity / NI_parent_TTM`，归母TTM利润须>0。不要把供应商weighted-average-share EPS与当前股数拼接；每股表示仅为 `NI_parent_TTM/current_outstanding_common_shares` 的一致转换。
- 对**前1260实际session含当前已完结session**各自按其当时cutoff重建倍数；`percentile=count(hist_multiple <= current_multiple)/1260`。每个session必须有正且合规的倍数，缺一个即不满足1260；不能往窗口外捡有效值凑数、改midrank或用当前盈利回填旧倍数。全相等时弱排名=1，不是0.5。
- 冻结估值门槛仍为percentile≤0.6。当前cutoff对应报价只有盘后原件准入后才能用于正式计算；当日未完结session不得调用其收盘值。

解释性价值候选 `M_ref=median(last1260 PIT multiples)`：普通角色 `fair_equity=M_ref×NI_parent_TTM`；周期角色 `fair_equity=M_ref×EBITDA_norm−NetDebt−NCI−preferred+nonoperating_investments`；`fair_price=fair_equity/current_shares`。fair_equity≤0输出明确非正权益原因，不伪造正目标价。资本结构不一致则拒绝。

**fair_price/current_price−1只是长期估值空间，不是20/40日预期收益。** 不把这一空间直接塞进Edge，也不自动追加“低于fair_price就买”的规则。替代DCF须事前现金流/再投资/终值协议，不能与倍数法按谁结果好切换。

## 6. M04 — 20–40日情景、概率与收益（推荐可审协议）

情景来自冻结规则下**完全成熟的事前反事实标签**，不从LLM评分或目标价臆造40/35/25概率。

1. 另建 `EX_EDGE_SHADOW_LABEL_PROPOSAL_V1`：仅在其时点全部**非Edge**研究/Timing/状态门槛已满足的机会形成标签；不根据最终grade/Edge或未来结果选入。忽略Edge是概率估计的单独、明确反事实标签协议，不是删除策略Edge门槛的回测。需Owner确认后才生成标签，现有两family真实策略仍全部门槛。
2. 使用相同已确认entry/exit、T+1/行动/未成交处理与一个事前批准的hypothetical经济/持仓单位协议。gross标签为完整退出现金流含公司行动、**参考执行价未扣费用和滑点**的收益，分母为entry参考买入notional；调用已有ledger须核对是否已把滑点放进fill，先用新桥还原/注明，不能重扣。没有已确认risk/exit/fill政策不生成标签。
3. 标签持有期通常20–40日；停牌/跌停导致退出延期则保留真实label_end，完全退出并且相应账本材料可见后才成熟。未成交、未完整退出、右删失分别保留，不当0收益。形成时刻、退出/可见时刻、censor状态要有索引；合格标签与排除数全量报告。可另报D20/D40价格预测标签，但它们不是本策略exit收益训练标签。
4. 拟议校准单元：`family × 当时有效行业组`，三股工程先保持该三股总体选择偏差说明；不同family不合并选优，不能用今天股票池替历史池。行业组taxonomy/来源在训练前固定，未知不改成“其他”。每单元至少100个已成熟完整shadow标签、每情景≥10、覆盖≥16个不同时间区块；这些是候选最低覆盖，不证明标签独立，shadow数不计入100真实完整策略交易门槛。
5. 定义gross return bps `r`：DOWN `r<−200`，FLAT `−200≤r≤200`，UP `r>200`，是事前固定的幅度桶，不称胜率。`p_k=(n_k+1)/(N+3)`（Dirichlet/Laplace alpha1），`R_k=该桶标签gross收益的算术均值`；`μ=Σp_k R_k`。条件均值可以包含尾部，不winsorize坏结果；空桶/样本不足仍NOT_COMPUTABLE，不用平滑创造缺失桶均值。
6. **适用域必须匹配**：每个模型绑定family、历史industry taxonomy/version、非Edge全部门槛版本、Timing状态、hypothetical标签经济单位和训练样本范围；每次预测保存cutoff时域判定及所用模型hash。只对全部非Edge/Timing门槛通过且属于训练/校准单元的机会输出本模型概率。Timing未触发、未知或taxonomy/证券总体适用性无证明时，`p/R/μ/U/Edge/FinalScore=UNSET_REQUIRED`，原因`PROBABILITY_NOT_APPLICABLE`或`APPLICABILITY_UNKNOWN`；不得用合格机会的条件概率推给未触发观察。独立ResearchScore可以继续输出。想预测Timing失败/新证券总体须另预注册相应域的模型和验证，不能共用现有模型。
7. 报单独 `P(net_profit>0)` 时必须使用同一完整gross/费用单位、成熟标签及独立校准流程；UP概率不是扣费胜率，S评分不是概率。

模型参数只能在TRAIN由已有成熟标签确定。在validation各小折的训练标签结束+knowledge时间必须早于该预测freeze；不能用整个validation拟合之后回头评分validation。SEALED OOS前可以按事前声明的计划用已成熟TRAIN+VALIDATION做一次最终refit，之后该test模型/参数/hash固定；validation校准诊断必须来自之前真正按时间留出的预测，不拿refit的内样本误差代替。时间滚动原则见 [Forecasting: Principles and Practice](https://otexts.com/fpp3/tscv.html)。

M04选择理由：可直接追溯事件、标签与情景均值，先解决可审计来源，避免小样本复杂模型和与Edge自我筛选循环。缺点：分层稀疏、市场状态混合和三股偏差，必须保留。替代多项logistic/树模型或人工经济情景，均需另定特征、训练/校准隔离和历史预测原件；不得看test后换。

## 7. M05 — 缓冲与概率校准

M05全部算法选择在本候选固定，仍待Owner批准；不由程序员在揭晓后选择分箱、fold、随机块或失败处理。真实fit/重采样本轮未运行，以下是实施规格。

**时间折与模型冻结。** 使用已审的WalkForwardWindowPlan给定36m TRAIN、12m VALIDATION、6m SEALED。12m VALIDATION按起点加0/3/6/9/12个日历月划成4个顺序fold；边界映射为官方session日历上当日或之后第一个session，左闭右开，不按测试收益移边界。每fold的`prediction_frozen_at`为该fold首session之前最后实际session收盘的已准入精确cutoff；该cutoff无精度/原件则整个fold NO_DECISION。用于fit的标签必须anchor在TRAIN或之前已完成VALIDATION fold内，且label_end和label_available_at均≤freeze；即使名义持有40日，延期标签仍按实际end。另purge：anchor必须早于fold首session前40个实际session的边界，且标签区间不能与当前held fold重叠。embargo：已完成held fold后的40个actual-session anchor不纳入后续fit（这些session的预测仍报告，不能删除）。不足100成熟标签/每类10/16块时fold INCONCLUSIVE，失败fold和未成交/删失记录全部保留。

首fold只用TRAIN；后fold可加入先前已成熟且满足purge/embargo的验证标签，形成真正rolling-origin预测。每fold只冻结一次模型；fold中不更新p/R，所有合格机会用冻结模型，不在实际结果出现后重写预测。最终SEALED前按相同成熟/purge/embargo规则用TRAIN+已完成VALIDATION做一次事前声明的refit，之后test模型/hash固定。概率校准和U_optimism始终来自前述真实留时预测，不能用最终refit回填validation。全局两family检验、正式window anchor和计划合同仍须专项接口审核；本候选fold不得改变原36/12/6/6与purge/embargo=40协议。

**联合区块索引。** 每个fit使用TRAIN开始至freeze之前的完整actual-session轴T，包含无机会的空session。每条完全成熟的标签按`decision_anchor_session`入列，非按退出日入列；保存actual label_end跨度。块长`L=max(40,所有纳入标签的最大anchor到label_end跨度session数)`，跨度包括真实延期。fit覆盖要求`floor(T/L)≥16`且按TRAIN轴起点划分的不重叠L-session块中至少16个有纳入事件；空块不凑实际事件覆盖。这是覆盖最低线，绝不称16块独立。所有证券及family的同时事件按同一session行绑定，同一次抽样使用同一个全局块序列，再分别计算冻结单元统计量，禁止为每个证券独立抽块来抹掉相关性。

固定2000 draw、seed=20261008。随机整数协议为Python stdlib `random.Random(seed).randrange(0,T−L+1)`，固定代码和Python runtime版本/hash进入run manifest；只有固定runtime的重放claim，不称跨语言同seed相同。每draw按均匀有放回抽`ceil(T/L)`个非环形连续L-session块，按抽取顺序拼接后截到T行，行中全部事件随行一起复制，空行保留。每个单元从该draw重算情景n/p/R/μ；抽样后总样本/各类/覆盖要求不再强行保持原最低数，但任一类空或统计量未定义→整次校准NOT_COMPUTABLE并保留draw，不能丢弃后补抽。样本原件/组归属在抽样前已固定。

`μ_LCB=q0.05(2000个bootstrap μ)`，nearest-rank定义：排序后的第`ceil(q×B)`项，1-based，q∈(0,1]。`U_sampling=max(0, μ_point−μ_LCB)`。

`U_optimism=max(0, mean(μ_out_of_time_prediction − realized_gross_return))`，只用当前refit前已完全成熟、真实4-fold留时预测中的对应单元事件，事件权重等权，不把股票日空行当0误差。用完整12m validation实际session轴、同样anchor/联合block协议和L计算其误差均值及置信区间；validation须100成熟事件/每类≥10、`floor(T_val/L)≥4`且至少4个不重叠块有事件；4是明确的新候选验证覆盖线（不同于fit的16），不是独立性/统计功效证明。任一不足或无预测原件时NOT_COMPUTABLE，不填0。12m验证通常只有约6个40-session块，必须报告区间不稳定与三股选择偏差，不能为了通过缩L/挪窗/补样本；延期使L更长时仍可被阻断。增加验证跨度需Owner另批新窗口版本。

`UncertaintyBuffer=U_sampling+U_optimism`，单位bps，两项分报。保守减法可能重复惩罚抽样/校准风险，报告敏感性不宣称最优；WACC不再加这份交易预测误差，U不含手续费。

**可靠性分箱与资格。** multiclass Brier=`mean Σ_k(p_k−1[y=k])²`、log loss=`−mean log p_realized`；每个情景分别固定概率边界0,.1,.2,…,1，左闭右开，最后[.9,1]包含1。恰好.1入[.1,.2)，0入首桶。空桶标EMPTY不捏造频率，不强行PASS；每个非空桶均展示，不能合桶/隐藏失败桶。每个非空桶成熟事件≥50，否则INCONCLUSIVE；每桶平均预测与实现频率差≤.10，且平均预测落入其时间块95%实现频率区间，否则UNCALIBRATED。区间用同一validation全轴的联合draw，桶成员随其原预测事件固定，q.025/.975 nearest-rank；某draw桶为空导致未定义→整次该资格NOT_COMPUTABLE，无删draw。全部必需单元/桶合格才能标`proposal_calibration_criteria_pass`，不能以低Brier代替校准，也不能叫真实Edge已验证。

基线是每fold只用当时合格TRAIN频率计算的冻结p；Brier/logloss及有效样本全量对比，不把观察基线优劣作为重调参数的理由。每grade仍另需原建议≥50独立完整OOS/Paper交易才可作正式grade概率解释。未知/失败使Edge/Final不可计算。校准与预测训练隔离的原则见 [scikit-learn Probability calibration](https://scikit-learn.org/stable/modules/calibration.html)；.10/50与上述bootstrap/fold是待批准工程设定，不来自文档、不保证真实概率。替代isotonic/sigmoid需另定独立校准集，在test前选，不能看结果后换。

## 8. M06 — Net Edge和Micro-Ladder

`C_expected = Σ p_k × dated_cost_bps(plan, scenario k)`；费用来自已批准profile、量/价格、订单累计最低佣金、税费包含关系及BASE/PESSIMISTIC单独成本版本。可用counterfactual profile做明确假设计算；真实账户仍UNSET。手续费只扣一次，成交价含滑点时不再扣独立滑点，选择的gross-reference口径则C必须包含滑点。

`NetEdge=μ−C_expected−U`；`net_edge_to_cost_ratio=NetEdge/C_expected`，只有C>0且完全核验才有比率。C=0/缺费项不输出∞或PASS。保持Frozen候选阈值NetEdge≥400bp、净比率≥5；BASE和PESSIMISTIC分开报告，不能挑BASE盖掉失败情景。建议正式候选准入要求二者均通过，但这属于新增待批风险决策，不从旧研究例子自动继承。

Micro-Ladder比较**同一总预算/目标风险、已确认fill/机会成本模型**的原计划P0与加档计划P1：

`ΔNet = [E(gross PNL(P1))−E(gross PNL(P0))] − [C(P1)−C(P0)] − [U(P1)−U(P0)]`（整数分最终结算前以Decimal分估计）。必须 `ΔNet>0` 且 `ΔGross>ΔCost+ΔU`、原完整策略Edge/风险/lot/费用可负担均通过，才有假设计划资格；等号拒绝。不假定每档成交、赚到全部价差或忽略错过行情的机会成本；缺fill/机会成本模型仍NOT_COMPUTABLE。

明确输出 `incremental_gross_benefit_to_cost_ratio` 与 `incremental_net_edge_to_cost_ratio`，不沿用旧P1A的通用字段名冒充Wave F比率。若ΔCost≤0，分母比率为NULL、原因NONPOSITIVE_INCREMENTAL_COST，但现金比较仍可检验；不能借此称无限优势。报价“更便宜1分”不是额外收益证明。未定义撤改单成本不得填零。

替代：一次买入与分档完整路径蒙特卡洛，但需冻结fill/队列/机会成本模型；日线不知队列，不能称真实可成交收益。所有假设plan结果仍NON_TRADEABLE。

## 9. M07 — 输入分数和S/A/B/C/X完整映射

所有维度0–100，`clip`仅截展示分数，不截财务损失/收益/风险原值。未知值保持UNSET，不填0。下面的线性anchor全部是待批研究设定，不是收益概率。`lin(x,a,b)=100×clip((x−a)/(b−a),0,1)`。

| 分数 | 明确计算候选 | 数据/限制 |
| --- | --- | --- |
| F Fundamental | mean(lin(收入同比,0,0.20), lin(毛利率变化,0,0.05), lin(ROIC−WACC,0,0.10), lin(OCF/NI,0.8,1.5), 100−lin(NetDebt/EBITDA,0,3)) | TTM及前四季PIT、资本成本；NI/EBITDA必须>0。质量硬门槛原样独立验证，不因均分高绕过 |
| S Sector | lin(当时行业RS20,−0.10,0.10) | 这里是行业TR减冻结市场TR；股票减行业的family RS另存，不能误用一个字段。任一行业成员/TR未知则UNSET |
| C Catalyst | 100当验证且未失效的冻结三类官方催化存在；0当完整可核验搜索证明窗口内不存在；覆盖未知UNSET | 不由模型编正向公告；0不代表全family已满足Catalyst |
| T Trend | 100×mean(close>MA60, MA60 slope20>0, stock−sector RS20>0) | 三个已定义条件；用经行动对账的当时价格 |
| V Valuation | 100×(1−冻结弱排名percentile) | 满足1260有效PIT值，不把fair-price gap当概率 |
| L Liquidity | `100×clip(1− planned_buy_notional / (0.01×median(last20 daily_turnover_CNY)),0,1)` | 目标买单及20日金额已知；1%为待批score anchor，不是新可成交保证或trade-cap。整数/Decimal、profile用途清楚；计划量未知则UNSET |
| E Evidence | 80当全部关键PIT/原件/版本/单位/有效性已通过；100当另有独立可重放完整核查通过 | 第二核查只是可复核性加分，不签发PIT；关键证据未知UNSET、已证伪按HardBlock处理 |
| Risk | `max(100×clip(NetDebt/EBITDA/3,0,1), 100×clip(−trailing_peak_drawdown/0.30,0,1))` | ratio≤0负净债现金风险分0但raw保留；raw/action-TR过去60session峰值drawdown≤0；0.30仅评分anchor，不替代Owner kill或仓位规则 |
| Timing | 100×(已满足的family Timing逻辑数量/全部数量)，pullback6、breakout4 | S另须全部family Timing通过，不能5/6仍83.3分就获S；UNKNOWN任一条件UNSET |

`RawScore=.25F+.20S+.15C+.15T+.10V+.10L+.05E`（引用交接建议）；`ResearchScore=(.25F+.20S+.15C+.10V+.05E)/.75`（本候选明确研究轴不含T/L）；`RiskAdjustedScore=RawScore−.20Risk`；`CostPenalty=min(15,100×C_expected/max(μ,50bp))`；`FinalScore=clip(RiskAdjustedScore−CostPenalty,0,100)`。分母/分子必须同为bps；50bp即交接0.5%，不是50%。不先整数四舍五入再分层。

这里的FinalScore和numeric actionability grade仅在M04适用域内可计算。非Edge/Timing未通过或域未知时，即使独立ResearchScore很高，也不能给交易Final/A/S；可以输出`research_priority=A`（Research≥80）、B（68≤Research<80）、C（Research<68），其字段/namespace单独标`RESEARCH_PRIORITY_ONLY`，不借用actionability grade，也不引用μ或扣费概率。这些研究轴阈值也是待批准设定。

确定性优先级：

1. 已证明Hard Block（包括已确认不可交易/重大反证/完整计算证实μ≤费用等）→X，明确trusted reason；即使有分数也不可覆盖。
2. M04概率域不适用/未知（尤其Timing未触发）或任一关键证据、账户用途所需费用/计划量、分数或概率校准未知→`UNSET_REQUIRED / NO_DECISION`，不能假X或假S。反事实profile能得**hypothetical grade**，其actual_account_suitability始终BLOCKED，不能生成实际tradeable。
3. Final<55→X；55≤Final<68→C；68≤Final<78→B。
4. Final≥78且F≥80、Research≥80→A候选，否则最多B。
5. 只有Final≥85、F≥80、Research≥85、Timing≥80、Evidence≥80、**全部非Edge研究门槛/全部family Timing、已校准Edge通过**、无HardBlock，才S。域内Final≥85但Edge等S条件失败留A或B，保留明确降级原因；不存在84–85或77–78的Decimal空档。F≥80是本候选明确补充的高质量前置条件，不声称来自旧冻结v1。

S动作仅REQUEST_HUMAN_REVIEW，不是签名、native Signal/Approval/Order或账户资格；域内A WATCH_WAIT（例如Timing已满足而净Edge不足），B NO_ACTIVE_TRADE，C RESEARCH_ONLY，X EXCLUDE，UNSET NO_DECISION。每次输出全维度、公式及哪个门槛阻止A→S。Quality/研究与Timing分别保存，不把维度分数说成概率。

替代：只输出原硬门槛加研究/Timing轴，不公布数值grade直到有独立样本；这样数据门槛可先验证，但不能冒充完成S/A/B/C/X绩效目标。Owner选择替代时需明确下一版本grade为UNSET，不能自行假设确认了当前表。

## 10. 数据、训练时间与版本生效

最早价/状态/action/行业/公告观察必须覆盖：1260估值warmup、每个warmup时点所需已披露正常化5年/TTM财务、104周beta/市场TR、dated rf/ERP/信用/税、20/60日特征、完整shadow退出标签及延期尾部。费用/计划量另需要事前批准counterfactual或actual policy；真实账户本金/券商仍UNSET_REQUIRED。新增历史源需合法本地存储/版本/许可/PIT证明，不能为了关缺口按网页可访问性放行。

新增原始字段及first-visible/版本需求见 `Data-Requirements-v1.json`；它是方法候选sidecar，不增加Frozen v1硬门槛、不把供应商字段名当合同。

数据原件→已有独立证据/PIT审核→候选方法计算→完整策略新版本freeze→新标签/fit→leave-forward校准→每个sealed窗口固定模型。收益已暴露的三股327旧观察和新回顾历史全部 exposure 登记，不改untouched=false；方法选择及本候选参数没有看任何新收益。正式Walk-forward anchor/边界/purge/embargo/跨窗现金/风险政策仍待独立字段审查，本提案没有用旧static日期替代36m/12m/6m/6m协议。

Owner批准**方法**只解决方法定义，不能证明数据/PIT/许可、真实费用、实际执行签名、策略Edge或生产准入。确认后新建 `CORE40_METHODS_1.x` 与新的 StrategySpec版本/兼容说明，旧v1不动；再在固定数据/参数窗口事前登记并由主控审核专项接入。未确认前：原运行政策继续UNSET_REQUIRED，专项仅继续不依赖这些方法的采集/PIT/引擎检查。本轮停止于可审提案与独立软件review。

## 11. 本轮可运行算术示例的证明边界

`method_proposals/reference_math.py` 只收 `SYNTHETIC_METHOD_PROPOSAL_ONLY` 的Decimal算术，不被任何active策略导入；示例中的概率、beta、费率和金额都是合成输入。它验证WACC、正常化、弱排名、权益桥、情景EV/缓冲/净Edge、加档和等级、标签成熟边界及概率分箱/nearest-rank/联合session索引。索引测试不等于真实模型fit或校准通过。真实报表桥、ERP/credit/PIT issuer、模型拟合、moving-block重采样和真实校准在本轮未实现或运行，不能因公式用例PASS称方法已获实证验证。fit/fold/区块索引/quantile规范已在M05固定，具体实现仍须Owner选择后审查；不能把未运行算法说成统计验证。R1纳秒/PIT、NCI口径、概率适用域及算法规格四项失败保留，v1.0.1修复后重新独立审查。
