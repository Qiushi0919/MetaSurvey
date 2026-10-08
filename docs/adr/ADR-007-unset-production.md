# ADR-007 UNSET_REQUIRED 与生产执行阻断

状态：P0 工程实现，待 Gate Review。

决定：账户身份、本金、目标单票金额、频率、最大持仓数、风险/回撤/行业上限、融资、策略预算、券商/费率/最低费/包含项/计费范围/有效期/滑点/政策来源均保持 UNSET_REQUIRED，直到明确配置并核验。null 不代替 required；旧 5000/6000/10000 元、3000/8000 单票和旧费率不能进入真实模板。

未知配置阻断生产，不阻断空库、合同、合成测试和明确隔离的旧回放。本轮 productionGate 无条件拒绝；accounts.production_authorized 只能 false，OrderIntent.production_execution_enabled 只能 false，没有下单传输。

后续实盘还需要源/交易规则/券商能力/费用对账、可信人工认证、Paper验收、Kill Switch、合规核验、部署权限/备份恢复等独立 Gate。填写参数不自动解除任何 Gate，也不授权本 agent 开启下一阶段。
