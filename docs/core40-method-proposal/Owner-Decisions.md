# Owner 方法确认单v1.0.1（尚未生效）

此单没有预选值自动生效，不能由软件Reviewer、专项或主控代Owner确认。下面均为待批准的方法候选，不是实际费率/资金/风险参数。完整公式见 Methods-v1.md。

| 决策 | 主控推荐的具体候选 | 替代/不同意时的处理 |
| --- | --- | --- |
| M01 WACC/ROIC | CNY CAPM；104完整周/≥78对；beta 2/3收缩；dated中国total ERP、10年国债、发行人信用利差；真实税/含NCI的合并资本结构桥；非零NCI需要其价值及独立Ke，未知阻断；TTM NOPAT/平均IC | bottom-up beta、implied ERP或dated贷款报价另定；不直接填固定8%WACC |
| M02 周期盈利 | 最近5个完整PIT年度中位EBITDA/revenue利润率×当前TTM收入；含亏损，不可比阻断 | 7–10年或分产品commodity结构模型另预注册 |
| M03 估值 | 归一化EV/EBITDA或正PE；逐历史cutoff1260弱排名；中位倍数仅解释fair value | DCF另定义；不得把fair价空间直接当40日收益 |
| M04 情景/概率 | 单独EX_EDGE shadow标签；仅全部非Edge/Timing合格且域相同；family×历史行业；100成熟标签/各桶10/16时间块；±200bp三桶、alpha1平滑 | 新分类模型/人工情景另预注册；样本不足不得编概率 |
| M05 缓冲/校准 | 2000次时间块bootstrap、L≥40且覆盖最长标签、seed20261008；4个3m验证fold、固定0.1概率箱、joint-session抽块和nearest-rank；fit至少16有事件块、validation至少4有事件块；sampling LCB+留时乐观偏差/可靠性检查 | 不减buffer填0；isotonic等替代需隔离校准数据 |
| M06 Edge/加档 | 保持400bp及净比率5；预计费用明确情景加权；推荐BASE/PESSIMISTIC都过；ΔNet严格>0、机会成本不缺省 | 任一费用/计划模型未知仍阻断；不把毛比率冒充净比率 |
| M07 评分等级 | 引用原权重、成本惩罚；具体分数anchor/Research轴、连续区间及S全部门槛；UNKNOWN/离概率域不出交易Final；独立research_priority另列；S只请求人工 | 可以先只输出门槛轴，grade保持UNSET；不能静默选别的评分模型 |
| M08 生效方式 | 全套候选方法批准后新版本，旧Frozen v1、Forward原件和既有封存结果不改；新fit/reveal前冻结 | 有修改意见先改候选并重审，不边看收益边调整 |

审批不包含：真实本金/券商费率/税率/止损和仓位、数据许可/PIT issuer、市场与行业指数identifier/完整TR证据、正式窗口锚点、真实Forward的执行签名或资金执行。它们继续独立保留UNSET_REQUIRED/BLOCKED。

推荐可以整体接受候选方法，或逐项指定修改；回复应明确方法候选版本与哪些项确认。确认后工程接入仍需固定合同、数据和测试验收，不直接运行真钱。

当前独立软件review只验证提案一致性、反例和保存边界。统计样本、税/信用/NCI报价与许可/PIT仍须独立证据；拟议validation仅少量时间块的统计不稳定风险不能被工程PASS消除。
