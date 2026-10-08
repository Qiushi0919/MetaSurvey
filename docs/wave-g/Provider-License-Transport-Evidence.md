# Provider / License / Transport — 八项实际证据表

实际月卡材料本轮仍为0。当前Owner允许本机既有隔离数据做RETROSPECTIVE_DIAGNOSTIC_ONLY；该工程授权不是供应方许可证明。八项缺口分别是：销售/供应主体、订单/产品、有效期、每类账户权益、用途许可、留存/备份/传输/再分发、endpoint身份、具体传输链路。每项均UNKNOWN，准确产品名/有效期/独立权限继续UNSET_REQUIRED；15000/月卡只记录为Owner声明。

本轮捕获7个官方公共网页原件，200响应/页面hash仅证明这次文档获取。官网描述本地存储能力，并非该月卡账户的用途或保存许可。[官方首页](https://tushare.pro/)

公共用户协议和服务协议区分账户与第三方边界，服务协议对销售/转让资格及账户使用有规定；本工程不据此判断该具体供应方违法或已获授权，必须收集其身份和正式授权链。[用户协议](https://tushare.pro/document/1?doc_id=409)、[数据服务协议](https://tushare.pro/document/1?doc_id=405)

官方文档仍给出HTTP API示例。因此HTTP本身不自动证明真伪，也不核验当前私有gateway的运营身份、代理/重定向或传输风险；这些具体链路证据仍缺。旧Transport Gate保持BLOCKED，未以公共例子放宽正式准入。[HTTP调用文档](https://tushare.pro/document/1?doc_id=130)

日线OHLC是未复权数据，停牌没有日线。pre_close是除权参考价，pct_chg按该参考值计算；不能把它当上一条RAW close，或累计成总回报。复权因子是另一数据产品，不能独立证明行动实施/历史版本。[daily](https://tushare.pro/document/2?doc_id=27)、[adj_factor](https://tushare.pro/document/2?doc_id=28)

财务指标的公告日与报告期字段不同，不证明历史第一可见时刻或修订链。[fina_indicator](https://tushare.pro/document/2?doc_id=79)

脱敏材料可按Provider-Redacted-Material-Template.json准备，由Owner明确提供后才进入本机私有staging。当前inspect_redacted_material仅做有界字段检查与材料存在记录，返回SUPPLIED_NOT_VERIFIED，不公开内容、不读凭证、不自动变成许可/entitlement/Provider/Transport PASS。未提交材料没有被虚构成证据；工程无需等待这些材料。无需提供Token。

官方文档版本以本次原文hash记录，未冒充账户有效期或合同生效版本。published_at/历史available_at未知；原始HTTP Date也不是协议发布时间。原文仍在私有public/provider归档，Git/交付只包含限定摘要与hash/path引用；没有公开再分发或云传输权限。
