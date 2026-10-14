# 虚拟费用：SIMULATED_COSTS

全部假设在 `protocol.json` 中、查看本次策略结果前冻结。账户参数不是Owner真实偏好。

基础：佣金成交额0.03%、每笔最低5元，约定已含交易所经手及监管费用；过户费0.001%另收，卖方印花税0.05%另收；单边滑点10bps含在成交价中，不在现金账再次扣除。压力配置佣金0.1%/滑点30bps。未运行压力优化或选择赢家。

复用 `backtest_5y.economics.quote_hypothetical` → `wave_f.backtest._fees`，整数分、显式HALF_EVEN。这是新实验内部规范，不改变原生产/账本HALF_UP政策。最低佣金补足不作为第二笔佣金叠加。

税率核对：[财政部税务总局2023年第39号](https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html)规定2023-08-28起证券交易印花税减半；[税务机关税目说明](https://gtm-cn-uqm3dbhc20k.guangdong.chinatax.gov.cn/gdsw/zhswsszldwqjszczl/2023-03/28/content_46e522dea2fe422ea8df29764e3b1e74.shtml)列减半前0.1%。[武汉金融局转载中国结算通知](https://jrj.wuhan.gov.cn/ynzx_57/xwzx/202204/t20220429_1964160.shtml)记录2022-04-29起过户费双向0.01‰。这是转载证据，不冒充已捕获中国结算原发版本。[上交所收费表](https://www.sse.com.cn/services/tradingservice/charge/ssecharge/)列A股经手费双向0.00341%；模型已在佣金中包含，不重复收费。

本次未得到真实账户费用资料，以上仍是模拟成本；原始政策完整生效链及交易状态不足时不因此解除行情准入阻断。限2023-08-28至本次记录日的实验配置，不能外推任意历史。行情跳空和卖不出可能使实际模拟损失超过计划止损预算；预算不是收益/风险保证。
