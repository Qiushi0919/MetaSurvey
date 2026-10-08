# 真实股票 slice：来源、时钟与覆盖要求

状态：PROPOSAL_FOR_OWNER_REVIEW。八类数据全部 BLOCKED；以下是拟验收要求，不是已准入数据或新的业务规则。正式交接继续为主要 Source of Truth，旧 Gate 与 C12–C22 保持原结论。

本轮只读取已冻结的 [16 项库存](../p1b/source-inventory.json)，其 as-of 为 2026-10-05T10:22:08.462Z，没有重扫旧数据库、WAL、credentials 或 runs。新增 [供应方文档证据](provider-evidence.json) 来自九份实际捕获的公开官方页面；每份原字节、取回时刻、URL 与 SHA 见 [capture manifest](public-document-captures.json)。原件隔离在 Git 外。这些是接口/产品/条款线索，没有股票数据或本账户 entitlement。

## 拟路线

| 路线 | 可研究的时点 | 必须额外证明 | 当前状态 |
|---|---|---|---|
| [当前观察路线](slice-observed.proposal.json) | 将来明确批准的当前 decision cutoff；过去数值只作为此时取得的证据 | 实际原件、原版本、合法本地用途、完整覆盖、新 clock policy；如采用捕获时点作为本地可消费时点，不宣称首次公开时间 | OWNER_REVIEW_REQUIRED；范围与用途 UNSET_REQUIRED |
| [真实历史截面路线](slice-historical.proposal.json) | 明确批准的历史 decision cutoff | 每个原版本在当时已可见的独立证据，含财报修订、action/factor 和成员变更；不能拿今日最新版回填 | OWNER_REVIEW_REQUIRED；范围、历史可见性与重构政策 UNSET_REQUIRED |

建议先审当前观察路线，减少历史可见性证明的依赖；这只是工程顺序建议。两条路线均无许可推定，均不允许模型消费或真实研究试运行。证券清单、起止日、cutoff 由所有者决定，不以旧实验或缓存规模代替。

## 八类数据的最小要求

| 数据类 | 内容与单位 | 版本/时间要求 | 关键反例与覆盖核验 | 当前准入 |
|---|---|---|---|---|
| SECURITY_STATUS | 永久身份映射、exchange/board、上市/退市/ST/停牌状态、适用 tick/lot | 原件与状态有效区间；业务生效时刻和公开/可得时刻分开 | 今日证券列表不能证明历史状态；无身份映射、退市样本或规则范围即阻断 | BLOCKED / C12 |
| CALENDAR_RULES | 相关交易所/板块的交易日、session 与适用规则 | 官方原版本/修订、effective 区间、可得证据 | 现有 SSE 10/1–8 公告、零证券覆盖，不是所有交易所完整日历 | BLOCKED；C13 仅旧有限参考 PARTIAL |
| RAW_BARS_1D | 未复权 OHLC、volume、amount、原始前收字段语义；价格 Decimal 字符串 | security + trade date + price basis + source version；原始、调整版本不覆盖 | Tushare `vol` 为手、`amount` 为千元，`pre_close` 为除权价，不得当原始前收；证券/缺日/停牌/异常值逐项核验 | BLOCKED / C15 |
| CORPORATE_ACTIONS | 分红/送转/配股等公告、修订、record/ex/effective/payment 日期与权利语义 | action identity + immutable revision；公布与生效不同 | factor 不是完整 action/entitlement stream；未知公告与权利规则阻断 | BLOCKED / C16 |
| ADJUSTMENT_VERSIONS | raw→adjusted 的 factor、basis、算法版本、原件与 action refs | factor 每次观察/修订保留；不能拿今日 qfq 回填旧观察 | raw/adjusted 分离；缺 factor/action 链与对账样本阻断 | BLOCKED / C17 |
| FINANCIAL_REVISIONS | 原财报与修订、report type、字段口径/币种/单位、原件 | period end、ann_date/f_ann_date、公开精度、原版/修订可得证据分别保留 | 报告期末不是发布时间；最新接口行不是全部历史可见版本；财报未来修订不能进旧 cutoff | BLOCKED / C18 |
| ANNOUNCEMENTS | 标题/正文、issuer/security mapping、附件 hash、公告/修订与反证 | 原件捕获、原版本、publication precision、available proof | URL/标题日期或模型 citation 不等于内容核验/许可/可得时间 | BLOCKED；未扩大旧线索用途 |
| INDUSTRY_MEMBERSHIP | 分类体系/层级/版本、成员及 in/out/effective 区间 | 业务成员区间与版本公开/可得时刻分开 | 当前行业标签不能回填；in/out 日期不证明原文件当时可见；存续偏差检查 | BLOCKED / C20 |

字段描述依据 [Tushare raw daily](https://tushare.pro/document/2?doc_id=27)、[factor](https://tushare.pro/document/2?doc_id=28)、[income](https://tushare.pro/document/2?doc_id=33)、[industry members](https://tushare.pro/document/2?doc_id=335)。以上文档说明不构成实际数据的完整性、时间或本账户用途证明。

每类拟 scope 的 source_id、provider 权属、许可版本与实际 entitlement、本地程序处理、存储、MANUAL_EXPORT、第三方模型/云端、再分发权限须分别核验。当前 local_research、cloud_manual_export、historical_backtest 三项为 UNSET_REQUIRED，redistribution=DENIED。手工复制仍是传输，不能因为叫 MANUAL_EXPORT 就绕过用途限制。

## 四时钟与证据精度

| 字段 | 含义 | 当前状态/禁止推断 |
|---|---|---|
| observation_event_time | 本地观察/捕获事件时刻 | 从未来真实 capture 取得；不充当业务 event_time |
| event_time / event_date / business_effective_date | bar 业务期、公告事件或状态/action/member 生效日 | 未知保留 null；DATE_ONLY 只保留日期，不填午夜；不同对象按自己的业务语义定义 |
| published_at / published_date / publication_precision | 原来源的公开时刻与可证明精度 | 日期不能升级为 instant；财报 period end 与 URL 日期不能代替 |
| available_at / availability_method_proposal | 拟消费系统何时可使用此原版本及证据依据 | UNSET；当前观察与历史可见性分开；抓取时刻不推导首次公開/历史可得时点 |
| retrieved_at | 本系统取回原字节的实际时刻 | 实际记录；mtime、接口计划入库时间不是该原版本的取回/历史可得证明 |

交易所 civil date 按 Asia/Shanghai 解释，instant 必须带 UTC offset；保留原精度。新 [ClockEvidenceProposal 1.0](../../contracts/admission-preparation/ClockEvidenceProposal.schema.json) 只校验提案形状。SECOND 必須有 instant；DATE_ONLY 有 date 且 instant=null；UNKNOWN/NOT_APPLICABLE 禁止自造 instant。它没有来源认证或 chronology runtime：`available_at=2000`、`retrieved_at=2026` 这种形状合法的矛盾值仍可能通过 schema，但 admission 永远 BLOCKED，historical_visibility_proven 永远 false。这是未来真实 adapter 必须处理的缺口，不能称为 PIT 通过。

## Snapshot / Policy / Receipt 与失效

未来拟链：原件与 actual capture → identity/原版本/单位/clock/DQ → finite coverage → frozen Snapshot → 所有者批准用途及 policy hash → 已注册、由可信 authority 签发的 Receipt → sanitized packet。只验证 hash 或 DQ 不获得 admission。股票 scope 不能借用旧 calendar policy、DEV receipt 或零证券 coverage。

coverage 必须有明确证券/数据类/区间、完整性和缺失原因；空列表不能解释为全市场。Snapshot、source bytes、terms/entitlement、parser/clock policy、版本、namespace、purpose、consumer、cutoff 任一变化，拟重新核验并失效旧引用；每次消费重新检查撤销、有效期与 live registry。修订与新证据追加，不改旧 seal。Cloud citation 保持 PENDING_VERIFICATION，不能自清 Hard Block。

持久 issuer、跨进程/重启 registry、真实 PostgreSQL concurrency/RBAC/备份/crash、真实财报/行业解析与 stock producer 尚未完成。本轮没有新 adapter、receipt、migration、研究 consumer 或权限升级。

## 所有者需确定的范围

1. 可证明的供应方/产品与实际合法用途。只需不含 secret 的 entitlement/条款证据；本轮不索取 token、密码或券商资料。
2. 当前观察路线或真实历史截面路线；明确有限证券、起止日与拟 cutoff。
3. 审阅新 clock proposal，尤其 DATE_ONLY、观察事件与业务事件、本地可消费时点和历史 proof 的区分。

这些决定之后仍须做实际原件、覆盖、PIT、许可与独立攻击验收，才能提出一个具体 source 的准入。Research Pilot 另需 `APPROVE_P1B_RESEARCH_PILOT`，不在本轮授权中。
