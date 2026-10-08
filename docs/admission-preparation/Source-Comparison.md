# 真实股票来源比较与 Owner 决策材料

状态：`PROPOSAL_FOR_OWNER_REVIEW`。以已交付的 `1fffea9` / P1-B DATA/SEMANTICS Gate 为基线，继续做来源准备，不重复 P1-B0。**本轮没有真实股票来源获得准入。** `REAL_STOCK_RESEARCH`、`Research Pilot`、Signal、Order 继续 `BLOCKED`，`productionGate=false`。

建议先审查“当前观察研究”的有限 slice，再单独审查“历史 asof 研究”。这是工程建议，尚未成为已批准业务规则。两条路线均需真实用途许可；当前观察路线只减少历史可见性证明的负担，不能绕过来源、原件、权限、覆盖或 DQ。

机器附件为 [provider-evidence.json](/Users/qiushi/投资研究/ashare-trading-v1/docs/admission-preparation/provider-evidence.json)。其中 `READ_FACT` 是实际读到的官方文档事实，`INFERENCE` 是据此作出的工程阻断判断。它们都是文档审查证据，不是市场数据或供应商授予本项目的许可。

## 候选来源

| 路径 | 已取得的证据 | 用途 / PIT 缺口 | 本次结论 |
|---|---|---|---|
| SSE 正式历史 EOD 产品或明确获授权的供应商 | 上交所目录列出沪市历史及日终产品、CSV、订阅方式；中文服务页另列授权许可与申请流程 | owner 的实际产品合同、技术规格、权限有效期均未取得；目录不能证明 raw OHLC 单位、修订可见性或云端处理权；不自动覆盖深市/北交所 | 优先核验的正式产品路径建议；`BLOCKED` |
| Tushare Pro | 已读服务协议及 daily / adj_factor / income / index_member_all 字段文档 | 协议限定个人查看、非商业、不可转让、有期限、可撤销许可；本项目自动研究、历史回测及向模型的 MANUAL_EXPORT 权利未证明，实际 endpoint entitlement 未取得 | 有字段规格的比较候选；`BLOCKED` |
| 发行人 / 交易所原文，辅以 CNINFO 数据服务 | CNINFO 本次取得 JS 页面外壳 | 可读服务许可、实际产品权限与字段规格未取得；尚无所选股票的公告/报告/修订原件或历史可得时间证明 | 必要官方事实核验路径建议；`BLOCKED` |
| BaoStock | 本轮官方首页仅返回不可读单字符页面，无可读数据条款 | 缺官方数据许可、字段与修订时钟证据；第三方 SDK 的 MIT 软件许可不能当市场数据许可 | 当前证据不足；`BLOCKED` |
| 旧 Tencent / AKShare / official-reference 资产 | 只引用上一轮冻结清单；本轮没有读取旧数据库或执行旧采集器 | 原用途许可、原始捕获链、历史 available_at、版本与复权谱系未证明 | 保留、隔离；`BLOCKED` |

SSE 产品事实依据 [官方历史产品目录](https://english.sse.com.cn/markets/dataservice/products/) 与 [中文服务页](https://www.sse.com.cn/transparency/services/)，对应 `SSE-01`—`SSE-03`。目录展示的范围不是本项目已验证 coverage，也不是 owner entitlement；当前有限日历参考的许可不会扩展到股票行情。

Tushare 用途事实依据 [服务协议，二（二）第 5 项](https://tushare.pro/document/1?doc_id=405)，对应 `TS-01`—`TS-02`。协议页面和 API 文档可访问，不能据此填写 `VERIFIED_FOR_RESEARCH` 或 `ALLOWED`。本项目所需权限仍为 `UNSET_REQUIRED`；向 ChatGPT/Deep Research 传递数据须单独证明，即使传递方式是手工也一样。

CNINFO 依据 [官方服务首页](https://webapi.cninfo.com.cn/) 的本次原始 HTML，对应 `CN-01`—`CN-02`。只取得页面外壳，不能声称已读到服务条款或财报 API 契约。BaoStock 的 [官方首页](https://www.baostock.com/) 本轮浏览观察未形成原件捕获，不用于许可事实证明。

## 已明确的字段陷阱

| 类型 | 官方文档中的事实 | 本项目必须保留的区别 |
|---|---|---|
| Tushare daily | OHLC 描述为未复权；`pre_close` 为除权昨收，`vol` 以手计，`amount` 以千元计；停牌期间无日线 | `pre_close` 不等于上一交易日 raw close；volume/amount 必须按已核验单位转换。服务公布的入库时段不等于逐条历史 availability 证明 |
| Tushare adj_factor | 因子由供应商自行生产 | 因子与官方 action/entitlement 分开；当前提取的历史因子不能证明每次修订当时已知 |
| Tushare income | 有 `ann_date`、`f_ann_date`、`report_type`、`update_flag` | 报告期、发布日期、更新标记与某次修订首次可见时间分别记录；日期字段不能证明完整版本原件和历史 asof 查询 |
| Tushare index_member_all | 有 `in_date`、`out_date`、`is_new`，查询参数默认最新 | 成员生效区间与分类/修订可得时间分开；当前成员不能反填历史，仍需 taxonomy/version 原件与可见性 |

对应 [daily 文档](https://tushare.pro/document/2?doc_id=27)（`TS-03`—`TS-04`）、[因子文档](https://tushare.pro/document/2?doc_id=28)（`TS-05`—`TS-06`）、[利润表文档](https://tushare.pro/document/2?doc_id=33)（`TS-07`—`TS-08`）、[行业成员文档](https://tushare.pro/document/2?doc_id=335)（`TS-09`—`TS-10`）。这些是规格事实和缺口判断，本轮没有调用数据接口来验证实际响应。

## 两条拟 slice 路线

| 项目 | 当前观察研究提案 | 历史 asof 研究提案 |
|---|---|---|
| 提案 | [slice-observed.proposal.json](/Users/qiushi/投资研究/ashare-trading-v1/docs/admission-preparation/slice-observed.proposal.json) | [slice-historical.proposal.json](/Users/qiushi/投资研究/ashare-trading-v1/docs/admission-preparation/slice-historical.proposal.json) |
| 允许宣称的可见性 | 将来实际捕获的版本，只能用于捕获以后经批准的观察 cutoff；历史业务日期不等于历史可见 | 将来必须另外证明原版本在每个选定历史 decision cutoff 前已可见 |
| 所需原证据 | 有效来源与用途许可、实际字节/hash、证券/日期 coverage、字段/单位/version、DQ、观察四时钟 | 左列全部，再加原始版本历史发布/可见证据、修订谱系、historical/backtest 用途许可 |
| DATE_ONLY | 保留日期和 null instant；不填午夜 | 同左；未知历史 availability 不得靠本次 retrieval 或旧文件 mtime 重构 |
| MANUAL_EXPORT 到模型 | 所选源明确允许后才可进入后续审批；当前无此权限 | 同左，并证明历史研究用途许可 |
| 当前 source / pilot | `BLOCKED` / `BLOCKED` | `BLOCKED` / `BLOCKED` |

两条路线的 namespace 仅拟为 `CORE_40`；symbols、from、to、decision_cutoff 均保持 `UNSET_REQUIRED`。本轮不选股票、不填区间、不形成真实 ResearchCard。观察路线可以研究包含过去业务日期的已授权资料，但不会据此验证某个过去的决策或回测结果。历史路线不能以“今天能下载历史数据”代替当时版本可见性。

## 完整 stock slice 仍需哪些证据

| 数据 | 最小证据包 | 尚未闭环 |
|---|---|---|
| Security/status | 官方 identity/exchange/board、状态/ST/停牌有效区间、修订原件/hash、用途权限；未知 lot/tick 不猜 | C12 |
| Calendar/rules | 所选交易所/板块有限日期和有效规则版本；不推断周一至周五均开市，不借用零股票日历 Gate | C13 |
| Raw bars | raw OHLC 原件、精确十进制文本、量额单位/session、pre-close 定义、每次修订与四时钟；停牌不造 bar | C15 |
| Corporate actions | 官方 action/entitlement 原件、record/ex/payment/effective dates 与公告/可见时钟、修订链 | C16 |
| Adjustment | raw/factor/adjusted 分离、锚点和版本、纳入 action 的可见性、现金权益与原始价格对账 | C17 |
| Financial revisions | 每份报告及修订原件/hash、报告期与类型、publication 精度、版本 availability；不覆盖旧值 | C18 |
| Announcements | 官方原件、发布时间精度、实际捕获和更正链；citation 不是准入凭证 | C18 / source-purpose gap |
| Industry membership | taxonomy/version、in/out 有效区间、原件和修订首次可见证据；禁止今日分类回填 | C20 |

全体还受 C14 历史 available_at、C19 DATE_ONLY 政策、C21 真实验证样本、C22 真实 producer/概率/Edge 政策约束。本轮仅准备 evidence requirements，不关闭这些条件，也不新增生产凭据、DB migration 或真实 adapter。

## 旧资产为什么不能升级

继续引用 [已冻结 source-inventory.json](/Users/qiushi/投资研究/ashare-trading-v1/docs/p1b/source-inventory.json)，该文件 SHA 另在机器附件中固定。库存已有平面 stock_info、kline 缓存、HK 历史表、财报公告线索与旧官方 capture；数量、文件名和 URL 不提供用途许可或历史可见性。HK 行情不属于 A 股 slice；qfq→raw fallback 不建立版本化复权谱系；旧 PDF hash/date 声明尚非新准入的修订原件。V5 保持 legacy experiment，其原 seal、ledger 与运行状态不变。

现有 `official:sse-calendar-reference` 只证明原 Gate 中有限日历的本地参考。它没有股票覆盖、没有历史研究或 cloud 用途。其 Receipt 不能供本轮股票提案引用为许可或历史信任证明。

## 给 Owner 的最少决策项

1. 选择路线：建议先审 `OBSERVED_CURRENT_RESEARCH_PROPOSED`；历史路线另设更严格的时钟 Gate。选择不等于 source 准入或 Research Pilot。
2. 选择具体供应商/产品及所需用途，提供可脱敏的现有 entitlement / 许可原证据。分别确认本地计算、历史回测、云端 MANUAL_EXPORT、保留/衍生产物权限；不发送账号、密码、token。若没有，保持未知，不由 Codex 注册、购买或联系供应商。
3. 决定有限证券、交易所、业务日期范围和 decision cutoff。当前全部 `UNSET_REQUIRED`，没有猜测默认股票或窗口。
4. 审查新 clock proposal 的语义形状。未知历史可见性仍阻断，不能仅批准形状就把无证据字段填为事实。

当前不需要真实本金、单票预算、佣金或风险参数来完成来源准备；既有真实账户 30 项未知配置维持原状。owner 路线或实现批准也不能替代供应商许可。后续真实 source、clock 和范围审查通过后，才可另外讨论实际 adapter；真实研究试点仍需明确 `APPROVE_P1B_RESEARCH_PILOT`。

## 本轮证据核验

对 [public-document-captures.json](/Users/qiushi/投资研究/ashare-trading-v1/docs/admission-preparation/public-document-captures.json) 中 9 份实际 TLS 文档捕获逐件核验 SHA-256 和 byte length，全部一致。原件在 `/Users/qiushi/投资研究/.p1b-archives/source-preparation-20261005/public-documents`，机器附件逐件记录完整 SHA、实际 retrieval 和路径。证据时间是文档取回时间，不能当成未下载市场数据的 available_at。

本轮没有 market row 获取、认证 API、旧 DB 读取、供应商联系/注册/购买、模型调用、source policy/Receipt 发放，也没有 source 升格。仅产出可审查来源比较。
