# 本轮工程授权与边界

Owner 于 2026-10-14 明确要求以当前实际仓库为起点，实现独立 `CORE40_SECTOR_STOCK_BASELINE_V0` 双层评分实验、七页本地只读工作台、四项实验接口和五年优化/消融预注册。这个授权只覆盖本轮工程实现与合成验证，不冻结原生业务方法、不运行真实评分任务、正式历史回测、Forward 揭晓、优化器、市场采集或交易。

源工程开始 HEAD `f23c0b260bc82c49712e7725a9b750b34125f85b`，分支 `publication/github-20261008`，工作区清洁。公开仓库 HEAD `8ac0c3e8bd44aa35dec32cc651c7f8cf19b0d32c` 是对应安全快照；独立专项 HEAD `4252876e23224df5d29c20492a08da9436dccf4a`、清洁。本轮不改专项工作区。旧六页工作台已存在，复用原读取、安全和页面组件。

新文件所有权：`experiments/sector_stock_v0/`、`contracts/sector-stock-v0/`、`docs/sector-stock-v0/` 归总控；修改 `workbench/` 和导航文档。原生合同、数据库迁移、旧锁文件、Frozen StrategySpec、M01–M08 待决原文、旧 pin/seal/账本/原件和 Forward 字节不改。新 Schema 是隔离的实验接口，不替代六 DTO 候选或原生 ResearchCard/BrainPacket。

个股 25/20/15/15/10/10/5 权重来自 Owner 本轮明确要求。板块等权、线性锚点、结构化编码细节、风险阈值与扣分是本轮可审查候选方法；工程实现不等于 Owner 批准其投资有效性。所有账户经济参数保持原有 UNSET_REQUIRED。

完成工程验收后沿用既有公开发布授权，只上传经扫描的软件、合成测试和审查元数据。私有原件/数据库/密钥与含真实报告的截图不上传。STOP，等待 Owner 下一轮审批。
