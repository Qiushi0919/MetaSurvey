# Owner 决策表：研究候选与执行政策分开

这次冻结的是两套研究候选及评价草案，未运行新的真实收益比较，也未选出赢家。
Candidate v1 的数值是**待批准的研究假设**，不是生产默认值。此前看过的三股
走势和 Wave E 结果继续视为 exposed；回看历史不能重新成为 untouched OOS。
原30项真实账户配置保持 UNSET_REQUIRED。工程建设无需等待填写这些项。

| 决策 | 已冻结候选/协议 | Owner 当前有效政策 | 不填写的影响 |
| --- | --- | --- | --- |
| 方法 | Quality + 回踩、Quality + 突破，两组全量报告，不按收益挑赢家 | UNSET_REQUIRED | 不开展正式策略评价 |
| 研究证券 | 603993.SH、600312.SH、603228.SH；选择偏差明确 | 三股工程范围已授权；无全市场推广权 | 不扩证券范围 |
| Quality/财务 | 收入增长、利润/现金质量、ROIC、杠杆、估值与官方催化的硬条件 | 估计资本成本、周期正常化盈利方法 UNSET_REQUIRED | 缺少对应 PIT 数值/方法时 NO_DECISION |
| 赔率 | 净Edge≥400bp、Edge/费用≥5 的交接文档示例作为候选 | 概率、误差缓冲、校准方法 UNSET_REQUIRED | 不把分数解释成上涨概率 |
| 评价基准 | CSI300 total return 作为提议；三股等权仅有偏诊断对照 | identifier、来源、税/分红再投资口径及选择 UNSET_REQUIRED | 不报告正式超额收益 |
| 时间切分 | ≥5年、1260session；IS/validation/retrospective 固定；旧资料可能全部 exposed | 确认此评价方案与未来 OOS 规则 UNSET_REQUIRED | 不声称旧资料为未见 OOS |
| 前向样本 | 未来至少126实际session及每family50笔独立完整OOS交易是研究提议 | 样本/独立性/失败判据接受 UNSET_REQUIRED | 样本不足 INCONCLUSIVE |
| 多重检验 | 固定2个family、全报告；Bonferroni 0.025/组；依赖感知区块重采样待实现前审 | 确认统计方案 UNSET_REQUIRED | 不给正式显著性/Edge PASS |
| 模拟账户 | 显式金额、lot、namespace、dated fees，不继承旧5千/1万元 | 模拟本金、佣金、最低佣金、费用包含关系、其他费/税版本、slippage UNSET_REQUIRED | 不运行真实数据经济回测或假定成本 |
| 持仓/风险 | 3只、各20%、合计60%、2ATR/40日退出、10%drawdown是候选提议 | 仓位/行业上限、单笔风险、日损、回撤/kill UNSET_REQUIRED | 不转成真实风险承诺或订单 |
| 新鲜快照 | 10月8日只是首个计划候选日；须实际开市及实际盘后数据检查 | 实际 Snapshot B 捕获单独 HUMAN 授权未获 | 不捕获或排程 |
| NO_DECISION Paper | 无金额/委托的研究记录；可独立于真实账户参数准备 | 真实session来源例外、策略版本/解读政策、独立审查和单独 HUMAN 激活未获 | actual_forward_days=0 |
| 正式数据/历史PIT | 独立 provider/license/transport、历史状态/行动/财报可见性证明 | 尚未具备；技术访问不是证明 | formal price/fundamental backtest仍 BLOCKED |
| 实盘 | 当前无 native Signal/Approval/Order/Fill/broker 路径 | 账户/券商/合规/真实交割费率/人工审批等另行验收 | production BLOCKED |

无需现在填真钱参数才能验收 Wave F。后续实际盘后 NO_ORDER/NO_DECISION 捕获，
也不应被错误地要求先填真实本金；但源范围、时钟、版本、独立审查、人工授权
以及策略解读的缺口必须仍逐项验收。授权捕获、记录一个真实session、批准策略
评价或资金执行是不同的动作，不相互替代。

本表没有预选项自动生效。Owner 可明确接受/修改研究提议；任何改动需新版本、
事前登记与新的曝光账本，已经揭示的旧样本无法恢复为未见样本。
