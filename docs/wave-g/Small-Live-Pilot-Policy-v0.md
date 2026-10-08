# Small-Live Pilot Policy v0 — OWNER_PENDING

本文件只登记未来政策提议，没有采用参数、连券商或交易的权限。实际账户、费用、风险30项和研究评价政策继续UNSET_REQUIRED。本轮模型不能产生native Signal/Approval/Order/Fill，任何自签JSON、LLM APPROVE或工程PASS都不能代替逐单HUMAN批准。

| 前置验收 | 当前状态 | 后续所需 |
| --- | --- | --- |
| Provider/source使用边界 | BLOCKED | 销售/产品/期限/entitlement/用途/留存传输/endpoint/transport八项实际证据及独立接受 |
| 正式价格/基本面PIT | BLOCKED | 连续状态/日历/行动/首次可见/修订原件，不能回填当前资料 |
| 策略/费用后评价 | BLOCKED | Owner接受候选及评价规则，dated佣金/最低费/税/其他费/slippage明确；按事前规则报告全部失败 |
| 未调参独立验证 | 未具备 | 已观察样本不能满足OOS；未来样本充分性另定 |
| Forward Paper | actual_forward_days=0 | 独立实际session/EOD捕获审查，单独Human授权与NO_ORDER阶段记录 |
| Broker dry-run | 未授权/未接入 | 未来独立授权；只读账户/权限、幂等、模拟拒单/重复/断线/对账及kill-switch验收 |
| Small Live | 未授权 | 所有前置达标、真实参数冻结、逐单Human批准，再单独授权限额Pilot |

以下数值来自当前附件建议，全部OWNER_PENDING，仅显示在人审政策表中，不进入任何执行默认值：

| 提议 | 待Owner接受内容 |
| --- | --- |
| Pilot资金池 | 可投资资产≤1%，另有绝对人民币上限；两者都由Owner确认，当前绝对金额UNSET_REQUIRED |
| 单票 | 可投资资产≤0.33%且Pilot资金≤1/3；计算基数/含费用/权益时点须确认 |
| 证券数 | 最多现有三只；不自动扩市场 |
| 杠杆/融资/做空 | 提议禁止；Owner政策未正式冻结 |
| 自动下单/人工批准 | 提议不自动下单，逐单HUMAN；模型不得越过否决 |
| 摊低成本 | 提议Pilot禁止；不能当已生效风险规则 |
| 数据/状态/费用/对账UNKNOWN | NO_ORDER；不靠猜测、fallback或放宽门禁处理 |
| 日内风险Kill | 阈值、异常定义、停止新增/取消未成交/恢复流程UNSET_REQUIRED |
| 累计回撤Kill | -3%为附件提议，不是已生效限额；峰值基数/费用计入/恢复审批另定 |
| 样本要求 | 126实际session、每family50笔独立完整OOS交易仍为Wave F提议；不能为提早实盘自动降标 |

账户真实本金/可用现金/持仓、券商/市场交易权限、lot/最小下单量、佣金/最低佣金/税/交易费用包含关系、slippage方法、单票/行业/总仓位、单笔风险/日损/总回撤、kill-switch/审批/对账/错误恢复及凭证隔离均须后续冻结。原30项库存见现有unconfigured AccountProfile；不从V5或synthetic继承。

资金政策不阻塞纯NO_DECISION本地工程准备，仍严格阻止任何资金执行。本文件没有可直接执行的订单、自动授权或到期激活逻辑。STOP_AFTER_WAVE_G_DELIVERY。
