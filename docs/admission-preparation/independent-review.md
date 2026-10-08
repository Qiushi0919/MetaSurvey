独立只读审查：真实股票数据准入准备

审查角色：`/root/source_preparation_reviewer`。本报告是本轮新的判断；没有沿用此前 P1-B/W4 PASS。当前被审资产是两个 proposal schema、两条 slice 方案、clock unknown 示例、公开供应商文档、Contract Fit 与 W1 准备边界。基线为 `1fffea964ad3fed5c47d7955b9121b31f8ceff74`，输入的具体 SHA 记录在同目录 `review-audit.json`。已补审当前 Data-Requirements、Source-Comparison、35 项 MD/JSON、Source-Preparation-Review、Preparation-Gate、README、AGENTS、SoT 1.7 与 portable check 入口。最终审查绑定 28 个输入文件的具体 SHA；父级后续 Git/index/archive 交付验证另行记录，不把本轮称为完整新业务 W4。

**结论：PASS_WITH_CONDITIONS，范围仅 PREPARATION。可接受准备成果，真实股票研究继续 BLOCKED。**

当前受审准备范围没有未关闭的阻断级安全发现。没有发现准备对象能把 source 自行晋升为 ADMITTED、授予模型用途或开启 production。新增资产没有实际行情 fetcher、股票 Snapshot/Receipt、Brain producer、Candidate/Signal/Order API。许可、coverage、历史版本可见性和账户字段并未由 schema-valid 自动变成已核验事实。这一判断只覆盖 preparation；不是完整真实数据/PIT pipeline、策略有效性或真实 Research Pilot 的 PASS。

**亲自核验的证据**

- 公开文档实际原件 9/9：读取外部 archive 中的原始 HTML，逐个 SHA-256 与字节长度匹配 manifest；没有把文档的 retrieved_at 当成证券数据行的 retrieved_at/available_at。
- 人类授权原文与 repo 保存副本逐字节一致；真实账户 skeleton 实际仍有 30 个 UNSET_REQUIRED。
- 当前 140 项 Closure + 34 项 P1-B code pin：分别比较当前文件、pin 预期和 pin 指向的真实 Git commit，174/174 一致。旧 291 项 artifact index 按历史 `1fffea9` Git 对象验证，291/291 一致；历史 index 内 AGENTS 等历史文档的 SHA 没有被拿来要求新版工作文档保持旧状态。
- 另逐件比较 289 个当前不可变文件与旧 delivery commit，289/289 相同；两个旧 bundle/manifest 的当前字节 hash MATCH。仅重验字节，没有把旧 restore 证明改称本轮重跑。
- 独立编译当前两份 schema，实际执行 32 项形状与越权变体，32 PASS / 0 FAIL。其中包含 self-ADMITTED、许可自批、cloud grant、historical_visibility=true、pilot/signal/order/production 升格、EVENT_3 串线、字段注入、缺 dataset、时区缺失、DATE_ONLY 午夜与 SECOND/UNKNOWN 精度反例。
- 当前 provider-evidence 的 9 文档引用、15 条事实/推断引用、manifest SHA 和旧 inventory SHA 一致。所有候选、八类数据 requirements 与两条 route 仍保持 BLOCKED；owner route 选择也明确不能替代供应商许可。

**两条路线有实质区别**

`OBSERVED_CURRENT_RESEARCH_PROPOSED` 可以未来在许可、原件、DQ 和有限范围闭环后读取带过去业务日期的数据，供当前 cutoff 使用。actual retrieval 是这次观察的可见性上界证据，不能据此把该原版本在过去 cutoff 的可见性写成已证明。

`HISTORICAL_ASOF_RESEARCH_PROPOSED` 还需要每个用于决策的版本在当时可见的独立证据，并保留修订、纠错和适用区间。两条 route 中公司行动有效日、财报期末、行业纳入/剔除日属于业务语义，不能替代 publication、available 或 retrieval。只有发布日期时保留 date + null instant，不补午夜或日末。当前两个 proposal 的 symbols、范围与 cutoff 都仍 UNSET_REQUIRED，没有偷偷选择真实股票作为研究对象。

**官方文档支持的事实与本次推断**

| 类别 | 官方文档事实 | 审查推断与未满足前提 |
|---|---|---|
| SSE EOD 产品路线 | 目录列出沪市历史/日终数据和订阅路径，中文服务页列出授权与业务申请路径。[历史产品](https://english.sse.com.cn/markets/dataservice/products/)、[行情服务](https://www.sse.com.cn/transparency/services/) | 产品目录不是本项目许可，也不是沪深北完整 coverage；具体产品合同、owner entitlement、OHLC/修订规格、本地运算/历史/云端/保留用途未取得。calendar 本地参考许可不可借给股票。 |
| Tushare 权限 | 服务条款约定个人、非商业、期限及可撤销使用；用户协议描述 AI/MCP 服务。[服务协议](https://tushare.pro/document/1?doc_id=405)、[用户协议](https://tushare.pro/document/1?doc_id=409) | 积分、可调用 API 或 AI 功能介绍不足以证明这个项目的自动研究、历史回测和 ChatGPT/Deep Research MANUAL_EXPORT 权利；用途保持 UNSET_REQUIRED，需具体授权与有效权益证明。 |
| Tushare daily | 文档说明 OHLC 为未复权、停牌日无行情；pre_close 是除权昨收，vol 单位是手、amount 是千元。[daily 规格](https://tushare.pro/document/2?doc_id=27) | pre_close 不应冒充上一交易日 raw close；公布入库时段不能证明每条历史 bar 原版本在过去某刻可见。空 bar 不能擅自填价格或解释为真实成交；精确十进制、单位换算、session/盘后范围仍须核验。 |
| 复权/行动 | adj_factor 文档说明因子由 Tushare 生产。[factor 规格](https://tushare.pro/document/2?doc_id=28) | 因子不等于交易所/发行人/中国结算的行动与权益原件；需 factor 版本、anchor/asof、可见行动、现金权益独立对账和纠错 lineage。 |
| 财报修订 | income 提供 ann_date、f_ann_date、period/report_type/update_flag 与不同报表类型。[income 规格](https://tushare.pro/document/2?doc_id=33) | 字段存在不等于修订原件与版本首次可见性已证明；当前最新返回值不能填入过去 decision。 |
| 行业成员 | 接口列出 in_date、out_date、is_new；查询默认偏向最新。[行业规格](https://tushare.pro/document/2?doc_id=335) | effective interval 不等于该版本的 first-visible time；需 taxonomy/version/revision 原件与 availability，不能回填今天标签。 |
| CNINFO | 本轮公开页面仅返回需 JavaScript 的服务壳。[官方入口](https://webapi.cninfo.com.cn/) | 没有由壳页证明 source entitlement、API 条款或数据/PIT规格。Issuer/交易所/CNINFO 只能是待认证路线。 |

BaoStock 没有本轮字节捕获与可读许可证据，不依据第三方 SDK 软件许可证推导数据权利。旧 cache、main-file HK 数据库、当前 stock_info 和 V5 仍为历史资产；HK 大库不是 A 股准入，flat security master 不是历史 ST/停牌/退市证明。


**补审主报告、导航与验证工具**

35 项有 35 个唯一编号，12/13/24 如实保留完整 Draft→Assessment→Card 版本链、compatibility adapter 与 linked replay 缺口；第 17 项只验 clock proposal shape，32–34 的真实股票研究/Pilot/订单继续 BLOCKED。旧 kernel 的 synthetic/PAPER 订单路径仍存在，因此主报告没有虚称整个 repo 不存在模拟订单。README 的前次入口已与最新准备入口区别，SoT 1.7 保留旧 Gate 并绑定此次人类授权，owner acceptance 仍 PENDING。除待原字节复制的独立报告自身，35 项证据链接均实际存在。

审查发现并由父级修复：Data-Requirements 的三项未知用途/再分发 DENIED 标签；35 项第 14 项不存在的旧 test 路径；README 的旧“当前入口”措辞；checker 仅用词法路径判断 repo 外输出。最后一项已改用 repo root 与输出父目录 realpath、解析后的实际外部路径及 wx 新文件写入。

修后亲自运行 portable 入口边界 **5/5 PASS**：无原件参数时结构17项通过但 external bytes claim 为零；真实九原件与新的外部报告通过；外部目录符号链接指回 repo 时提前拒绝且 repo 未生成任何目标；外部已存结果的覆盖请求拒绝且原 hash 不变；相对路径拒绝。使用受控外部目录与合成输出名，没有改 repo 或 legacy。所审 checker 的 SHA 为 `sha256:2bafac725d02581deb89f08514acbf416c89a933ef3e5cd813af53c9a840c3b6`。该工具没有网络/账户/数据库/模型或 admission 接口，也不修改 frozen expected。

亲自读取父级完整检查日志并核对 SHA 与计数：300 项、299 PASS、0 FAIL、1 optional SKIP。这是父级实际 current checkout 执行，由 Reviewer 核验原日志；不是 Reviewer 亲自再跑300，也不称 fresh clean install。父级稍后新提案入口的 clean dependency/repository restore 结果须在其交付 checkpoint 另记。

**必须保留的条件**

1. ClockEvidenceProposal 是 unverified shape。独立尝试 `available_at=2000`、`retrieved_at=2026` 的 OBSERVED proposal，schema 会接受形状，但 admission=BLOCKED、historical_visibility_proven=false。不能把这个检查称为 PIT PASS。真正 runtime 必须绑定原件/版本/source/hash/evidence 与微秒或更细的 chronology，拒绝 observed availability 倒填，且在 cutoff 消费时重新验证许可、撤销和 freshness。
2. 新 proposal 当前不是可注册的 runtime observation；没有取得实源 raw bytes、逐行 clocks、DQ 和许可。以后进入实际 adapter 必须先冻结新的 source/clock contract，不能原地扩展限定 calendar 的 SourceObservation1.1 / Receipt1.1 / Packet1.2，也不能只换 OBSERVED 标签取得信任。
3. 股份身份/status、完整交易所 session/rules、raw bars、action、factor、financial revisions、announcement、industry 的关键证据都仍未闭环，C12–C22 未因准备材料自动关闭。当前真实股票 source、Research Pilot、模型导出、Signal/Order 与 production 继续 BLOCKED。
4. 跨进程或持久 consumer 之前还须复审稳定 issuer、receipt/revocation 持久性及 publish 时 live recheck；既有 DEV authority 与一次固定 use_at 的 archive 证明不能当永久授权。
5. MANUAL_EXPORT 只是运输边界，不是供应商用途许可。用户的 route/contract review 或将来的 Pilot 批准均不能制造第三方授权；云端导出需单独满足来源、数据类型、coverage、purpose 与有效许可。

**owner 下一步可决定的四件事**

先选当前 OBSERVED 研究准备或历史 ASOF 路线，再选具体 provider/product 与允许用途，明确有限 symbols/exchanges/业务日期/cutoff，最后审新四时钟 proposal。可以提供脱敏的有效权益、条款和授权附件；不需要账户本金、佣金、风险参数或 token。此时的决定仅为后续 source implementation 的前提；既不意味着 ADMITTED，也不等于 APPROVE_P1B_RESEARCH_PILOT。

Reviewer 只写外部审查证据，未修改 repo/legacy、合同、expected、业务规则或 Gate；未联系/购买/注册供应商，未调用认证数据 API、真实模型或账户。父级完整旧 300 执行日志已核验；本轮总控交付 metadata/tag/bundle 与实际 restore 仍为父总控的后续验证，不能在本报告中冒称已由 Reviewer 亲自执行。审查日期 2026-10-05，精确 checked_at、input SHA、32 项检查与5项入口边界证据见同名 JSON。
