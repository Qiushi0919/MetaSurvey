# E2E History V2 — 独立来源与公司行动核验

审查日期：2026-10-14，Asia/Shanghai。范围仅为公开来源条款/字段与既有本地原件，未读取凭证、未调用认证行情、未联系供应商、未修改旧资产。本报告是工程来源评估，不证明历史首次可见性或法律认证。

## 可推进的路线

**BaoStock 官方文档对免费量化数据、本地保存和分析有明确用途描述，足以提交本轮有限本地诊断的来源准入候选。** 这条依据来自数据服务说明，不是代码开源许可证。官网 [平台介绍](https://www.baostock.com/mainContent?file=home.md) 明确支持数据全部保存在本地分析；[本地复权计算说明](https://www.baostock.com/mainContent?file=localdatafactorInfo.md) 也直接介绍利用本地日线生成复权价格。平台公开介绍为免费、无需注册；未购买 VIP、未使用 API_KEY。

已直接核对主控两次官方0.9.4 SDK匿名login原件，均返回`10002007`网络接收错误、未取得行情；第一次系统DNS，第二次独立DNS核对同一官方hostname解析地址。主控记录TCP连通但应用会话接收失败，未改变系统网络设置，不再自动重试。**用途依据已找到与网络服务可用是两项不同状态。** 本审查不把用途候选写成实际数据到位。官网仅发现固定示例 XLSX 下载；它们不是九股目标日期资料。版本说明提到多节点，但未发现可供匿名使用的官方备用节点地址；明确列出的 VIP 节点需 API_KEY，不能作为免费绕行。不得采用第三方封装所谓 HTTP 备用来暗换来源。

官网另有通用网站版权声明，限制未经书面许可复制、传播或商业使用网站内容。数据 API 的本地量化用途说明比通用网站说明更具体，但不据此推断数据转售、公开原件、云模型传输或生产许可。推荐新来源政策仅准入**个人本地、有限证券、回溯重建诊断**，原件仍 Git 外；这并不改变旧来源政策或旧阻断。

## 字段 → 官方 API → 用途 → 实际情况

| 必需字段 | 官方 BaoStock 接口/口径 | 本轮用途与必须检查 | 已有证据与缺口 |
|---|---|---|---|
| 证券身份、上市/退市日 | `query_stock_basic`：code/code_name/ipoDate/outDate/type/status | 九股身份、上市期/特殊状态排除；status 是当前基础属性，不能代替逐日状态 | 文档已捕获；本审查未查询，九股实际响应待取得 |
| 开市日历 | `query_trade_dates`：calendar_date/is_trading_day | 固定区间、预热与next-session | 文档说明可查SSE日历；需核验SZ适用与实际完整返回 |
| RAW OHLC/volume/amount | `query_history_k_data_plus`，frequency=d，adjustflag=3 | 成交与价格基准；volume=股、amount=元 | 文档已捕获；非复权不能与前/后复权混用；网络失败后未获本轮行情 |
| 停牌/ST | 同一日线tradestatus(1正常/0停牌)、isST(1/0) | 每证券每日执行状态 | 未知/空字符串不得当正常；非空交易行不证明IPO、重上市、退市整理等例外已排除 |
| 昨收/除权基准 | 同一日线preclose | 派生当日限价、动作复核 | 官方解释：除权日是交易所除权参考价格，而非上一日RAW close |
| 现金/送转 | `query_dividend_data(code,year,yearType='operate')` | 登记权利、除权、派息和红股可售日期 | 提供预披露/预案/实施相关数据，不能将全部返回行当实施；缺日期不得补成ex日 |
| 因子 | `query_adjust_factor` | 原始价和指标序列分离、异常行动排查 | 涨跌幅复权算法；因子变化不能替代现金账、送转股或配股账 |
| 直接涨跌停价 | 上述日线字段不包含 | 只能生成标为DERIVED的限价并绑定规则版本 | 必须有逐日有效比例、tick、preclose与特殊情况；不能称交易所直接提供 |
| 历史首次可见/修订 | 上述文档未给逐条不可变revision/历史采集时间 | 保留真实retrieved_at，标历史重建 | 不能用今天查询反推过去available_at，正式PIT/OOS仍未证明 |

官方字段页：[日线](https://www.baostock.com/mainContent?file=stockKData.md)、[基础资料](https://www.baostock.com/mainContent?file=StockBasicInfoAPI.md)、[日历/API](https://www.baostock.com/mainContent?file=pythonAPI.md)、[分红](https://www.baostock.com/mainContent?file=dividInfo.md)、[复权因子](https://www.baostock.com/mainContent?file=factorInfo.md)。

## 执行口径不能遗漏的条件

BaoStock preclose 文档明确除权日使用参考价。正常主板、非特殊首日且有效日状态已核实的记录，可将 `preclose × (1 ± 当日比例)` 按0.01元 `ROUND_HALF_UP` 派生限价；保留输入、公式、规则引用与DERIVED标签，检查最小tick等规则边界。原始OHLC、限价和停牌不一致时拒绝，不用舍入修补异常数据。

[上交所2026交易规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml) 自2026-07-06生效：3.3.8为100股整手、3.3.11为0.01元tick、3.3.13正常比例10%、3.3.17四舍五入，4.3.2–3规定除权参考价与涨跌幅基准。原件及暂缓实施附件已保存。**不能将2026版倒填整个2025区间，也不能把ST永久硬编码5%。** [深交所2026风险警示指南](https://www.szse.cn/lawrules/service/member/t20260630_621404.html) 明确2026-07-06制度变化；遇历史ST/特殊状态应使用日期化规则或阻断。深交所2023旧路径GET为404，失败保留；随后从[官方已废止规则通知](https://www.szse.cn/lawrules/rule/repeal/rules/t20230217_598773.html)的实际附件链接成功取得原件。两所2023/2026四份正文均已实际核到普通主板100股、0.01元、10%及除权参考价规则，已加入来源策略原件pins。具体hash/条款见Independent-Review.md。当前仅支持逐日isST=0的正常主板；这仍不自动排除重上市、退市整理首日或交易所其他特殊情形，须另核例外覆盖。

分红字段严格区分：`dividRegistDate`登记、`dividOperateDate`除权、`dividPayDate`现金到账、`dividStockMarketDate`红股上市；`dividCashPsBeforeTax`为每股税前现金，`dividStocksPs`/`dividReserveToStockPs`为每股送股/转增。税后字段可能是条件文字（例如多个持有期税率），不能直接当Decimal。缺pay或红股上市日时不能默认为ex；原案/停止实施不得入账；重复披露需归并经济事件并保存披露版本。

## 旧网关：查到了什么、仍缺什么

已核对 `backtest_5y/sources.py`、`docs/p1b-real-admission/provider-evidence.json`、同目录entitlement-matrix、`docs/wave-hb/Provider-License-Inbox.json` 和 Wave-G来源包。网关销售主体、产品合同、实际账户权益/期限、历史本地诊断用途均无独立材料。15000月卡及有效期为Owner陈述；技术IP/SDK兼容性不能反推出销售主体。

后期技术矩阵实际记录：stock_basic 6行、suspend_d 0行、trade_cal 504行、daily/adj_factor各990行、dividend 227行、fina_indicator 63行、index_member_all 6行。它们是ACCESS_OBSERVED，不是授权证明；早期NOT_QUERIED文档已被后期技术探针超越，不应重复宣称从未有响应。

[官方Tushare数据协议](https://tushare.pro/document/1?doc_id=405) 描述官方主体和个人使用边界，并不为该网关提供授权关联；[权限表](https://tushare.pro/document/2?doc_id=290) 也不能证明第三方月卡产品。没有通过读取Token解决此问题的途径。

若继续指定旧网关，集中需要：销售主体/产品和订单的脱敏证明；供应方确认该产品允许本轮九股历史行情/状态/行动下载、本地保存及模拟诊断的条款；实际有效期和独立产品权限。**推荐先用有明确本地用途说明的BaoStock路径解决免费有限诊断，网络不可用则提供可恢复运行入口及精确错误；不立即购买。** 如Owner已有合法数据产品导出，可提供原始CSV/JSON与对应用途证明，仍逐字段检验。无需再发送Token或密码。

## 九股现有公司行动证据

只读核对旧G2三股dividend原件：600312=98行、603228=58行、603993=71行，合计227行，包含实施/股东会通过/预案，另有预披露或停止实施。不能把227行当227次经济事件。

按证券+ex/record/pay+股数/现金归并，预热及观察范围2025-06-03～2026-09-30内有8个已实施现金除息事件：600312为3，603228为2，603993为3；其中2025-10-01～2026-09-30观察窗为5个（2/1/2）。这些只是旧未获许可网关的隔离原件，非新源准入，亦不证明其他公司行动全无。逐事件字段、原件hash和原始重复版本留在私有记录中。

九份现有FY2025官方PDF又提供有用线索，但均为今天读取的年报，不能替代当年实施公告/完整历史动作序列：

| 公司 | 本地原件位置（PDF页） | 明确线索/不足 |
|---|---|---|
| 沪电002463 | 41 | 2025-05-07的2024年度权益分派实施公告索引；需要实际公告及日期 |
| 深南002916 | 47、73 | 2025登记2025-05-28、10派15并10转3，记载2025-05-29实施完成；另有FY2025方案，不等于已实施 |
| 中国西电601179 | 39 | 2025年两次现金方案及登记日；没有完整pay/ex原件链 |
| 江西铜业600362 | 2、50 | 已实施中期现金分红与拟年度方案需分开；不能把拟派额提前入账 |
| 思源002028、紫金601899、洛钼603993 | 有限关键词提取未定位完整链 | 无命中不是无行动；紫金仅7页摘要，洛钼前页字体提取受限 |
| 平高600312、景旺603228 | 已有年报行动线索及上述结构化原件 | 仍缺新许可下完整时序与异常类型覆盖 |

上述九股不能填 `corporate_actions=NONE`。送转、现金、配股/其他资本动作要分别审查；既有年报不能证明2026-09窗口末行动完整性。

## 可复核私有证据

根目录：`.p1b-archives/e2e-history-v2-20261014/source-review/`（Git外）。

- `Public-Documentation-Manifest.json`：BaoStock官方公开文档/前端实际路由、SHA256、字节数；旧批次捕获时间明确标为文件mtime完成观察，不冒充原始发布时间。
- `New-Capture-Receipt.json`：新增官方文档请求起止、SHA256及深交所404失败。
- `baostock-home.md`、`baostock-stockKData.md`、`baostock-dividInfo.md`、`baostock-factorInfo.md`、`baostock-StockBasicInfoAPI.md`、`baostock-localdatafactorInfo.md`及通用版权原件。
- `sse-trade2023.docx`、`sse-deferred2023.docx`、`sse-trade2026.docx`、`sse-deferred2026.docx`、`szse-trade2023.pdf`、`szse-trade2026.pdf`及提取文本；`Rule-Capture-Receipt.json`、`SZSE-2023-Archive-Receipt.json`、`SZSE-2026-Receipt.json`保存新增成功请求与hash，旧404记录保留。
- `Existing-Structured-Actions.json`：3份旧原件227行、8个窗口经济事件的审查记录。计算hash不等于独立来源认证。
- `Existing-AnnualReport-Action-Search.json`：9份已存PDF的hash、实际页码与摘录。仅关键词辅助定位，不声称完整行动审计。

本轮独立来源评估结论：**存在有具体官方用途依据的免费替代路线；实际行情网络/覆盖、执行字段与历史重建审查仍需完成。旧网关供应方未知维持不变。**


最终实现边界补充：正常主板条款原件已经取得并绑定，但`require_exception_coverage`尚无官方事件解码器，真实路径固定以`RULE_EXCEPTION_COVERAGE_UNPROVEN`拒绝准入。匿名API服务恢复并不自动补齐该工程/证据缺口；需要覆盖九股完整预热至窗口末的IPO、重上市首日、退市整理首日及其他无涨跌幅限制例外资料，实施可验证解码器后另行冻结。当前实际失败run另先停在`ANONYMOUS_SOURCE_LOGIN_FAILED`，未越过该前置错误，也未调用策略引擎。
