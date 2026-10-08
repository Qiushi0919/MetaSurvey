# MetaSurvey 双线验证报告 — 2026-10-07

本轮完成双线工程与受限价格诊断，工程结论为 **PASS_WITH_CONDITIONS**。它不是正式历史 OOS、策略盈利证明或真实执行授权。

已经保存新的 **ForwardPrediction-v1-OWNER_TEXT_IMPORT**，本机记录时间是 **2026-10-07 23:01:37（Asia/Shanghai）**，早于计划中的10/8开盘。**原始 `7718…7072` 文件未提供，原 hash 未核验**；本轮保存的是来源明确的新文字导入版，不能宣称找回或验过旧文件。本机时间没有独立时间戳或 Human 执行签名背书。

历史线使用每股327个已暴露的观察日，完成4,905个预测位置、4,449个可评分的参考预测/结果对。**真实 Snapshot B 仍未生成，actual forward days=0，行情请求=0，本轮凭据读取=0。** G05保留上一轮本机读取通过结论；G06–G10仍未执行。

## 原始预测文件有什么用

它是盲测的“答题纸”：保存预测者在看到答案前写下的目标、区间、中心、日期和来源。SHA-256只能核对一个已经存在的文件是否改变，不能从hash还原文件。没有原件时，不能核验那份原答案；本轮已把用户提供的文字保留为来源，并生成新文件和新hash，后续仅追加结果，不能回改这份v1。

新JSON：`ForwardPrediction-v1-OWNER_TEXT_IMPORT.json`（4146 bytes）。

新SHA-256：`954569db8402e2e50e66841c1a449523c72f20ff1ce364d6183c4d3c7a018039`。

声称的旧SHA-256：`7718b46d2d3f281fe574215ce347caedca8b2355033551774d6febc181067072`。状态：ORIGINAL_NOT_PROVIDED_HASH_NOT_VERIFIED。

## Track A：Historical-OOS-Lite / PRICE_ONLY 的实际状态

样本范围为 **2025-06-03～2026-09-30，每股327个观察日**，证券固定为603993.SH、600312.SH、603228.SH。330条日线观察中相同版本只在算术中折叠为327日期，原始版本与hash引用保留；冲突版本不择优、不覆盖。

采用raw unadjusted价格，没有使用当前财务、行业、公告、名称或adjusted价格回填。完整当前参考日历只用于日期窗口映射，未冒充历史交易日证明。今天的retrieved/available时刻没有改写成历史可见时刻。源provider/license、单位完整性、历史状态、公司行动及真实历史universe仍未准入。

本轮预声明一个**无调参价格参考预测**：在每个cutoff，用终点≤cutoff的已完成h日raw close变化求扩展均值，h固定为1/5/10/20/40。没有parameter selection，没有最佳版本筛选。它不是新增MetaSurvey生产策略，也不是两套冻结StrategySpec的完整预测。全部历史位置保留：228个warmup、228个right-censored endpoint，共4,449个可评分交集，不丢弃难看的结果。

本轮历史预测在 **23:11:33** 持久化并hash绑定，重开后于 **23:12:18** 保存未来标签。独立算术实现复核4,905个预测及4,677个已观察标签终点通过。这个顺序证明本轮freeze-before-reveal，**不能抹去旧327日已经被看过的事实**。因此实际tier为RETROSPECTIVE_DIAGNOSTIC_ONLY，untouched_oos=false，historical_visibility_proven=false。严格历史PIT价格回测仍BLOCKED。

以下是参考预测与raw价格标签的描述性统计。方向命中比较预测中心和实际raw return的三态sign；它不是成交胜率。均值/中位数、MAE/MFE及窗口最大回撤是价格标签，**不是策略组合毛收益、净收益或组合回撤**。多日窗口相互重叠，不能当成独立交易或据此做显著性宣告。

| 窗口 | 可评分对 | 参考方向命中 | raw标签均值 | raw标签中位数 | 路径MAE中位数 | 路径MFE中位数 | 最大close路径回撤 |
|---|---:|---:|---:|---:|---:|---:|---:|
| D1 | 975 | 51.28% | 0.29% | 0.10% | -1.66% | 1.85% | 10.00% |
| D5 | 951 | 52.47% | 1.47% | 0.74% | -3.82% | 5.06% | 20.37% |
| D10 | 921 | 52.23% | 3.02% | 1.50% | -5.36% | 8.42% | 26.32% |
| D20 | 861 | 60.16% | 4.95% | 3.61% | -7.31% | 13.80% | 33.51% |
| D40 | 741 | 61.40% | 8.35% | 4.93% | -9.86% | 20.15% | 38.99% |

费用敏感性：以下只把预声明的synthetic roundtrip bps从每个raw标签减去，显示中位数。**它没有成交、股数、最低佣金、最低收费、现金可买性、T+1执行或真实账本模拟**，不是费用后策略盈利。

| 窗口 | 0 bps | 5 bps | 10 bps | 25 bps | 50 bps |
|---|---:|---:|---:|---:|---:|
| D1 | 0.10% | 0.05% | 0.00% | -0.15% | -0.40% |
| D5 | 0.74% | 0.69% | 0.64% | 0.49% | 0.24% |
| D10 | 1.50% | 1.45% | 1.40% | 1.25% | 1.00% |
| D20 | 3.61% | 3.56% | 3.51% | 3.36% | 3.11% |
| D40 | 4.93% | 4.88% | 4.83% | 4.68% | 4.43% |

两套冻结Timing价格条件另行诊断：PULLBACK的981个证券/日期位置为TRUE=6、FALSE=738、UNKNOWN=237；BREAKOUT为TRUE=9、FALSE=792、UNKNOWN=180。对应D1/D5/D10/D20/D40已观察TRUE样本分别为PULLBACK **6/6/5/5/4**、BREAKOUT **9/9/9/9/8**；样本极小，未选优、未放宽条件。其余Quality、行业RS、valuation、catalyst、状态、行动、费用Edge及PIT门禁仍缺失，完整策略 **1,962个NO_DECISION**。完整分组描述保留在包内Scoreboard；其中direction_hit字段属于无调参参考预测，不能解释成Timing完整策略胜率。

请求中的实际策略gross return、真实费用net return、组合max drawdown、turnover、benchmark excess及S/A/B/C/X分层保持 **NULL / NOT_COMPUTABLE**；实际策略trade_count=0。没有资金配置、已验证成交语义和基准/等级政策时，不能通过猜值补齐这些结果。价格标签统计和synthetic成本网格已经输出，但**尚未完成可执行策略回测**。目前不能判定Edge。

## Formal Historical PIT Gap Register

从已封存H-B map重新hash读取生成20类、60个证券/数据域条目；**连续历史域关闭数=0**。旧date-only、单个事件、已有当前hash、失败证据和reason codes均通过原map/selector引用保留，不覆盖旧map。18行原map没有可选的展示元数据，本轮标成UNRECORDED_IN_BASELINE，不填成已证明。

| 数据域 | 继续必须补齐的证据 |
|---|---|
| financial | 可核验的published instant、first_seen/available、ann/fann语义、revision/supersedes/version与原件hash |
| announcement | 证券匹配的官方原件、公开/首次可用时刻、修订顺序、可重开来源及许可 |
| industry | 历史membership有效区间、变更版本与当时可见时刻；不得回填今天标签 |
| status | ST/名称、停复牌、上市退市、涨跌幅制度的完整历史有效区间与例外 |
| corporate action | 分红/拆并/除权行动、复权因子版本及生效/公告/首次可见；raw不可被adjusted覆盖 |

每个decision还需要明确timezone-aware cutoff、四时钟精度、source/version/hash、完整rule interval、universe、安全适用范围、单位和purpose/license。现有今天可查询的历史行不满足这些条件。扩大5～10年数据前须先提交source、license、PIT与覆盖缺口方案；本轮没有回填或新增下载。

## Track B：文字导入版v1已冻结，真实结果仍为0

以下仅是Owner提供的预测文字转录，base close是**尚待固定Reference A原件核对的输入假设**；没有重新核验附件中的商品、港股、公司或宏观叙述，也没有新LLM研究调用。区间不是校准置信区间，64/60/55%的主观概率不是实际胜率。

| 证券 | 9/30输入基准 | D1区间 / 中心 | D5区间 / 中心 | D10区间 / 中心 |
|---|---:|---|---|---|
| 603993.SH | ¥16.88 | -1.0%～3.5% / 1.2% | -2.5%～7.0% / 3.5% | -3.5%～9.0% / 5.0% |
| 600312.SH | ¥20.29 | -1.0%～2.5% / 0.7% | -2.0%～5.0% / 2.0% | -3.0%～7.0% / 3.0% |
| 603228.SH | ¥101.21 | -2.5%～5.0% / 1.5% | -7.0%～10.0% / 2.0% | -10.0%～12.0% / 3.0% |

Base固定2026-09-30 close；D1=2026-10-08、D5=2026-10-14、D10=2026-10-21，都是Owner计划目标，尚不是实际交易日open/EOD witness。D10 quoted中心价依次17.72/20.90/104.25元；主观正收益概率64%/60%/55%。显式排名603993>600312>603228被保留，后两只数值中心同为+3%的tie也保留，不偷偷补tie-break。

新增ForwardPrediction/ForwardOutcome两个metadata合同1.0.0。预测采用exclusive create/fsync/hash，真实评分入口固定本次v1新hash，不能通过重写receipt替换答案。Outcome为独立append链，expected head、路径genesis、prediction hash、symbol+horizon去重；不改原G store、不增加actual_forward_days、不产生Signal/Approval/OrderIntent。

真实评分adapter只接收原H-A验证器通过的真实Snapshot B，重新核验CAPTURE、独立REVIEW、raw/clock原件、固定Reference A和收盘时间。新增sidecar不会制造签名、授予许可或替代Owner FORWARD。D1可计算方向、区间、raw return、误差和当日low/high MAE/MFE；D5/D10在完整路径日历与所有原件没有证明时MAE/MFE为NULL。D10须三个已核验同版本结果齐全才能评分排序；真实收益相等保留tie，不算严格ordinal命中。

**真实签名Snapshot B的正向评分尚未运行**；目前验证了数学fixture和拒绝伪造/模拟/过期时间/改hash/重复/stale-head路径。不能把离线测试称为真实预测命中。v1实际outcome_count=0，所有目标PENDING，不生成未来答案。首次真实Day1完成后仍STOP；D5/D10的数据执行不能自动借用过期或不同session的原grant。

## 10/8 Snapshot B 与原G链

双人公开registry当前仍可重开并验证；这不是本轮CAPTURE/REVIEW/FORWARD授权。G05沿用前轮PASS_LOCAL_LOOKUP_ONLY；凭证有效期、实际API、provider身份和license不从本机读取成功推定。

当前 **actual_G=HOLD，G06–G10 NOT_EXECUTED，Snapshot B NOT_YET_RUN，actual_forward_days=0**。10/8真实open/EOD到来后，仍须原始当日事实、Owner CAPTURE签名、独立Reviewer对原件的REVIEW签名、Snapshot B、另外Owner FORWARD签名及恰好一次NO_DECISION append。现有有界计划最多13个只读请求，未启动scheduler或自动运行；本轮没有请求行情。

## 验证、Git与保留边界

最终代码candidate为 `a778c86ff86427c95ab38be83b8f9b9e8ad750e4`，在独立本机clone验证 **255项案例PASS**：新增25 +已有87 Python +143 Node。35个schema atomic assertions另计，不冒充35个测试案例；复核4,905预测、4,677标签终点另计。旧轮/修复前/当前/独立副本不能累加为新的通过数。private evidence根未移动、locked node_modules共享，不声称无这些证据根的远程CI可移植。

906个已有tracked文件、1,858证据依赖、26 H-A代码pin重新hash检查均零变化。native16、既有数据库Schema、migrations001–006、锁文件、两套StrategySpec、旧V5/seal/ledger/runs全部保留。新代码位于dual_track/，合同位于contracts/dual-track/，新增ADR-036及本轮文档；正式工程交接文档仍为主要Source of Truth。旧V5 CLI hash mismatch继续作为已知legacy compatibility issue保留，本轮未修改旧seal或ledger来制造通过。

失败历史保留：第一轮20个新案例有18PASS/2ERROR，原因是攻击测试不能直接写chmod-400的临时fixture；仅给临时攻击fixture显式chmod，没有放宽生产保护。PIT adapter两次因旧map缺可选展示字段在写输出前停止，缺字段现按UNRECORDED处理。预发布自查补上真实v1固定hash、原文重开和默认评分时钟采样顺序；所有修复在任何真实outcome之前完成，反例与旧日志保留。没有为了通过测试修改旧封存数据或账本。

这次没有冒充独立Human Reviewer；本轮自查、算术复核与独立clone是自动工程证据。实际数据仍必须由已登记的另一位真实Reviewer签名复核；实际评分正向路径仍待真实材料。

最终Git提交、clean状态、rollback bundle及包checksum见验收包Delivery-Checkpoint与Package-Manifest。逐cutoff预测/标签（约7.6MB）及raw源证据保留在私人档案，Git只存代码/合同/报告/metadata索引；验收包不含逐日vendor raw、credentials、私钥、Token、运行数据库或iPhone备份。

## 仍阻止Paper / Broker / Real Money的条件

1. 当前没有真实Snapshot B或actual forward day，三份独立执行签名与当日open/EOD尚未形成；一个研究答案文件不是采集或资金授权。
2. 首份v1尚无真实结果，只有三股单个预测版本；现有327历史日已暴露、窗口重叠、证券选择偏差，不能证明稳定OOS、Edge、S/A/B/C/X或费用后盈利。
3. 历史PIT、provider/license/运输与存储/云端权限、状态与公司行动完整性仍BLOCKED；正式历史回测和生产数据未准入。
4. 真实账户/券商/费用/本金/风险与原30+补充15项继续UNSET_REQUIRED，真实成本NOT_COMPUTABLE；没有完整成交账本、可买性/T+1策略执行、确认后的benchmark政策及Owner资金授权。
5. Paper readiness还缺可执行策略、已证明数据和足够真实前向记录（原门槛至少20实际交易日及其余条件没有被本报告改写）；Broker、Tiny Canary与真钱需要各自后续验收和明确Owner授权。

下一步是等真实目标session事实与原链的人工签名，保留v1并追加可核验的结果；历史线先提出更长raw价格及calendar/status/action/PIT/license数据方案。不会自动扩股、优化、下载、开启Day2、Broker、资金或下一阶段。**本轮交付后停止。**
