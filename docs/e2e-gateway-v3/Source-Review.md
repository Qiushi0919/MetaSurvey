# 现有 Tushare 兼容网关 V3：来源与执行字段复核

复核日期：2026-10-14，Asia/Shanghai。本文件属于新V3，不修改已封存V2。独立审查Agent只读取已存脱敏服务说明和官方公开文档，没有读取凭证或调用认证行情接口。实际九股请求、原件与覆盖由主控本轮采集记录证明；本文不预填成功。

## 本轮采用的边界

按Owner最新明确指令，只继续使用现有15000积分月卡兼容网关，在本机开展有限重建历史诊断，不再寻找替代来源、不采购、不重复要求相同客服材料。旧记录中的停止/准入条件是历史状态；本轮新授权与新实验必须另外保存，不改旧BLOCKED为PASS。原件不公开、不云传、不调用券商、不声称正式PIT或投资有效性。

现有脱敏服务说明为`docs/p1b-real-admission/provider-evidence.json`及`docs/tushare-admission/public-terms-evidence.json`：产品等级15000及月卡日期是Owner陈述；销售主体、正式产品合同、官方网关关联未核实。已有技术响应可以证明具体请求返回了字段，不能证明官方直连身份。源码`backtest_5y/sources.py`已有同一IP端点、旧技术响应及限流记录，不能把兼容SDK当服务商认证。

官方[服务协议405](https://tushare.pro/document/1?doc_id=405)确有具体限制：第二区分官方/授权渠道，禁止未经授权第三方销售、账号共享；个人许可为非商业、不可转让、有期限。没有取得该兼容网关自身条款，不能据这些文字判定其实际授权关系，也不能出具`LICENSE_VERIFIED`。本轮工程记录应区分`OWNER_AUTHORIZED_LOCAL_DIAGNOSTIC`与`PROVIDER_LICENSE_UNVERIFIED`；不以缺客服回复停止全部本地实现，亦不公开原始数据或宣称具有转售/云端/生产权利。此处为原文边界记录，不是法律认证。

## 字段、官方语义及具体接入要求

| 数据域与API | 官方文档确认 | 本轮接入与不足 |
|---|---|---|
| [daily /27](https://tushare.pro/document/2?doc_id=27) | 未复权；停牌期间不提供行。`pre_close`是除权昨收，`vol`为手，`amount`为千元 | 明确转为股×100、元×1000，保留原值。与逐交易日日历、停牌、限价交叉；缺行不能自动前填。今日读取不证明当年可见 |
| [trade_cal /26](https://tushare.pro/document/1?doc_id=26) | 默认SSE；可指定SSE/SZSE；`cal_date/is_open/pretrade_date`。文档说三个股票交易所日历一致 | 请求明确交易所与完整自然日区间，验证无缺失/重复。不能用价格日期集合自建完整日历 |
| [stock_basic /25](https://tushare.pro/document/2?doc_id=25) | 当前基础列表；market、exchange、curr_type、list_status、list_date、delist_date。默认list_status=L | 显式fields；只用于证券身份与上市日期，不推断全历史每天非ST/正常上市。避免默认L把已退市对象静默排除 |
| [stk_limit /183](https://tushare.pro/document/2?doc_id=183) | 逐证券逐交易日`up_limit/down_limit`，可显式取`pre_close/asset_type/exchange`；单次5800 | 直接使用供应商返回每日限价，标`SUPPLIER_RECONSTRUCTED_DAILY_LIMITS`，不再自行固定10%填值；字段缺失、0、NULL、负数、非有限数、倒置、OHLC越界均阻断；不是交易所原始公告 |
| [suspend_d /214](https://tushare.pro/document/2?doc_id=214) | S停/R复；`suspend_timing`非空表示日内停牌区间；按日期获取，单次5000 | 保留空成功与错误区别，核请求范围、字段、分页。日内停牌不能视为普通开盘可成交；已有日线也不能忽略该标记 |
| [adj_factor /28](https://tushare.pro/document/2?doc_id=28) | 官方称自行生产的逐日复权因子；能取个股历史 | 因子需正且完整，变动与行动/除权pre_close对照。不是行动类型、到账日期或历史修订链；不能用因子反推现金到账 |
| [dividend /103](https://tushare.pro/document/2?doc_id=103) | `div_proc`进度；`cash_div_tax`税前/股，`cash_div`税后/股；`stk_div`每股送转，`stk_bo_rate/stk_co_rate`分项；登记/除息/派息/红股上市/实施公告日期分别提供 | 必须显式取`div_listdate`（红股上市日）及`imp_ann_date`。实施版本按经济事件归并，预案/停止实施不入账；不能把stk_div再与分项相加。现金缺pay_date、送转缺div_listdate要阻断对应行动，不默认ex日 |
| [namechange /100](https://tushare.pro/document/1?doc_id=100) | 返回name、start_date/end_date、ann_date、change_reason；**输入start/end筛公告日期** | 按ts_code取完整已返回历史，再以有效区间比对目标窗口，避免只筛窗口公告而漏掉此前开始的ST。名称未含ST不是完整特殊事件证明；空/重叠/缺覆盖保留状态不明 |

上述单位、范围与字段来自官方接口规格；兼容网关是否按规格实际返回，仍须对当次原件单独核验。请求成功的0行不可等同权限缺失，也不可无条件等同该域无事件。响应达到单次条数上限或未证明分页结束时，不接受完整性结论。

## 三项关键工程结论

**直接每日限价可以替代V2的自行推导路径，但不能解释不限价日。** 官方stk_limit文档没有定义0/NULL代表什么，也没有承诺所有特殊上市事件的编码。V3可依赖实际返回的、有效的每日限价运行重建诊断，另核身份/历史名称/停牌。不能由0/NULL推断无涨跌幅限制，也不能按10%补齐。出现缺限价或状态冲突，应明确指出日期和证券，保留失败/未成交与风险敞口。不可为了接入V3删除或改写V2的例外阻断。

**suspend_d空响应是一个稀疏事件查询结果。** 可保留`EMPTY_SUCCESS_NO_REPORTED_SUSPENSIONS`，但只有请求范围有效、返回结构正确、未截断，并与完整日历、对应daily、正成交和限价覆盖一致时，才能在重建诊断假设下标“该日有成交、没有供应商报告停牌”。它不证明盘中每一时刻可成交。若某个开市日日线缺失且无对应S事件，状态UNKNOWN，不能造一根停牌K线；若S带日内时间，现有仅日线执行器需保守禁入/禁出或明确预先冻结处理。

**分红字段具备所需日期，但不等于完整公司行动分类。** 送转使用div_listdate解锁，现金使用pay_date变为可用；记录日登记权利，不能将今天的实施公告可见性倒填历史。已有模拟税假设应独立标注，不能把税后字段和模拟税再次扣除。

## 配股及其他资本行动

官方当前目录可以核实[stk_seasoned /494](https://tushare.pro/document/2?doc_id=494)，定义为公开/非公开增发流程，含老股东优先配售等字段。该接口不等于已核实的完整配股rights事件接口，本轮官方目录及检索未找到明确的专用rights规格，因此不猜API名称。其空响应也不能证明不存在配股。

行动完整性应以当次dividend、daily除权pre_close、相邻adj_factor变化联合检查；任何无法由已支持现金/送转解释的参考价或因子变化，保留`UNEXPLAINED_CORPORATE_ACTION`之类严格错误，不默认为NONE、不将配股伪装送股。本轮没有新增配股认购支出/权利处置模型；发现此类事件应留在单独不足清单，不能以重建诊断标签跨过现金/股数守恒。

## 时钟、许可与状态的分层

实际`retrieved_at`取本轮采集完成时间；供应商trade_date、ann_date、imp_ann_date分别保留，不被统一改成available_at。模拟18:00决策时刻若使用，是明确的重建假设，`historical_visibility_proven=false`。本轮许可问号与技术工程可并行，不自动提升正式历史PIT、生产或云端导出权限。

本文件未访问Token/Keychain、未调用认证API、未联系供应方；实际账户权益以主控本轮逐API结果为准，而不是“15000”推断。只记录必要脱敏指标与hash，公开仓库不含原始响应、密钥或运行数据库。

## 原始公开文档留存

新私有目录`.p1b-archives/e2e-gateway-v3-20261014/source-review/`保存以上8个API、stk_seasoned及官方服务协议共10份HTML，`Documentation-Receipt.json`记录每次实际URL、开始/完成时间、HTTP状态、bytes、SHA256。本轮10份请求均HTTP200；这是官方文档获取状态，不是网关API权益或数据完整性验证。旧V2与旧供应方证据均保持只读。
