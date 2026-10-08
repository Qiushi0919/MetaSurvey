# MetaSurvey 历史 PIT 推进与条件回测验收报告

日期：2026-10-08（Asia/Shanghai）。本轮按 Owner 直接授权推进 P0-PIT / 条件 P0-BT / P0-AUDIT；正式交接文档仍是主要 Source of Truth，原审查基线与冻结策略保持原样。

## 结论

**本轮完成真实原件只读适配、逐日候选审计、60 行闭环矩阵和失败前置评估。正式 Historical OOS / Walk-forward 仍 BLOCKED，回测引擎调用为 0。** 这不是一次已执行的盈利回测，也不是历史 PIT 放行。

| 项目 | 本轮实际结果 |
| --- | --- |
| 三股观察日期 | 每股327个，2025-06-03～2026-09-30 |
| 原件适配 | 重开131个既有直接原件引用；3740条 price/calendar/status/action API 行绑定原件哈希、请求指纹与行号 |
| 逐日候选视图 | 3×327＝981份；cutoff仍UNSET_REQUIRED，全部NO_DECISION；正式准入快照0 |
| PIT闭环 | 20域×3股＝60行；连续闭环0；首次可见/修订链仍未证明 |
| 新日历证据 | 6份上交所年度休市通知，40个日期区间；实际例外和完整开市历史未证明 |
| 回测／账本／指标 | 未调用引擎；真实完整交易0；账本EMPTY_PENDING；gross/net/fees/turnover/MDD/excess/MAE/MFE等为NULL |
| 验证 | 最终工程副本381个独立用例PASS、0FAIL、0SKIP；另80个合同原子断言，不并入用例数 |
| 保全 | 940个旧文件、1858个采用的旧证据依赖、26个固定代码引用匹配；Day0预测/来源/回执精确原哈希匹配 |
| 未来线 | 本轮实际前向天数增加0；原预测不改；没有新建或启用自动揭晓 |
| 资金执行 | productionGate=false；真实订单、券商、模型调用为0 |

本轮新增6次不带凭证的上交所公开GET。公开检索只用于寻找证据，未把搜索摘要、二手页面或现行状态转成历史事实。行情API认证请求、钥匙串读取、私钥读取均为0；没有扩大三股范围、迁移旧数据库或覆盖旧账本。

## P0-PIT：原件与四时钟

既有数据实际API行数：daily990、trade_cal1500、stock_basic12、dividend240、adj_factor998，共3740。每股daily的330条观察对应327个不同日期，3个完全相同重复日期保留请求别名与来源；没有以“去重”删除证据。financial/industry/catalyst等仍在原20域缺口要求内，本次四组适配没有宣称它们闭环。

原件绑定保存 actual API、request_id/fingerprint、row_ordinal、raw SHA-256、source_version、原始字段值及字面取得时间。raw daily与adj_factor分开保留，不生成复权价格去覆盖raw。内容哈希只是捕获内容版本，不能充当供应商revision ID。源单位仍未独立准入；不对这些值计算真钱账本。

`current_available_at`与`historical_available_at`明确分开。现存数据在历史样本日期之后取得；event_date早于今天不证明当时可见。historical_available_at、first_visible_at均NULL，revision_chain=NOT_PROVEN。网站发布日期只有日期精度，未填成00:00或其它猜测时刻。当前Owner尚未指定逐日Asia/Shanghai决策截止时刻，保持UNSET_REQUIRED。

981份是**历史候选审计视图**，不是正式native SnapshotManifest。每份visible_records为空、四组状态UNKNOWN、historical_visibility_proven=false。原件引用/拒绝记录仅存在外部审计清单；未来信息的值、ID、数量和哈希均不进入该日决策载荷。每份语义哈希已重新读取验证；自重算哈希也不能加入未来字段或升级准入。

60行JSON保留原20域要求、原理由和原件索引。你本次的条件回测授权已经生效，旧“尚未授权”理由仅留在历史字段，不再作为当前理由。当前条件未通过，不能执行P0-BT。

主要证据：[逐日候选视图](/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/run-G4/Daily-PIT-Candidate-Snapshots.json)、[60行矩阵](/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/run-G4/PIT-Closure-Matrix-60.json)、[原件审计清单](/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/run-G4/Current-Originals-Audit-Inventory.json)、[覆盖与下一批证据计划](/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/Coverage-and-Next-Evidence-Plan.json)。

## 新增日历证据及限度

| 年度 | 官网标示发布日期（DATE_ONLY） | 捕获的休市日期区间数 | 来源 |
| --- | --- | --- | --- |
| 2021 | 2020-12-24 | 7 | [上交所原件](https://www.sse.com.cn/disclosure/announcement/general/c/c_20201224_5286949.shtml) |
| 2022 | 2021-12-20 | 7 | [上交所原件](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20211220_5663057.shtml) |
| 2023 | 2022-12-27 | 6 | [上交所原件](https://www.sse.com.cn/disclosure/announcement/general/c/c_20221227_5714458.shtml) |
| 2024 | 2023-12-26 | 7 | [上交所原件](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20231226_5733941.shtml) |
| 2025 | 2024-12-23 | 6 | [上交所原件](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20241223_10767110.shtml) |
| 2026 | 2025-12-22 | 7 | [上交所原件](https://www.sse.com.cn/disclosure/dealinstruc/closed/c/c_20251222_10802510.shtml) |

以上原件已保存于本地外部证据目录，分别记录取得时间、原文/解析文本哈希。公告有年度计划日期，尚无独立first-visible与完整修订链，故不能补成历史精确available_at。40个区间包括通知中的跨年安排；2024元旦区间保留2023-12-30起点。

981个已观察raw-bar日期与这些计划休市区间的冲突为0。该检查只验证日期相容性，不证明所有实际开市日、临时停市、个股停牌/ST/涨跌停/退市状态，也不关闭exchange_calendar_version。公司行动实施、支付、登记与因子版本仍需原件和连续核对；未找到的新公司原件不以二手材料代替。

## P0-BT：冻结协议保全及执行条件

保持两个family：CORE40_Q_PULLBACK_V1、CORE40_Q_BREAKOUT_V1。冻结StrategySpec原件SHA-256：`d4eb866d6675e52f4b5158374f94a3152e4ae406c62add22a8c807762b0215da`。

本次Owner采纳的headline协议是：初始36个月训练（旧冻结协议为expanding）、12个月验证、6个月sealed test、每6个月滚动，purge与embargo均40个实际交易日，目标至少1260 sessions与100 complete trades。未运行优化，也未改变两个family或因结果选赢家。

当前每股327个观察日期，比1260的数量目标至少少933个；**已准入历史session仍为0**。五个日历年不能自动等于1260个交易日，取得1260日也不能保证100笔交易。冻结估值特征还要求决策前1260个有效观察的warmup，因此只补到样本数量目标仍可能不足。

旧静态retrospective训练段不是新的36个月Walk-forward锚点；不得暗中替换。实际训练/验证/留出锚点、交易日边界、purge/embargo的可审查实现与未触碰封存窗口仍待确定。已暴露、窗口重叠的Lite预测标签保留RETROSPECTIVE_DIAGNOSTIC_ONLY、untouched_oos=false；方向命中率不是交易胜率、费用后Edge或策略净收益。

正式运行还需要全20域与完整family共同门槛。price/calendar/status/action优先闭环也不能代替金融财报、产业/行业、催化、估值、基准及Edge输入。Owner本金、日期化实际佣金/最低收费/税费包含范围、滑点、风险、仓位、benchmark与经济估计政策继续UNSET_REQUIRED。旧5000/6000/10000本金、单票金额和旧费率未继承。现有cost/backtest的正向测试仍使用明确synthetic fixture；实际PIT正向接入引擎的adapter尚未实现或获独立审核，不把实验撮合入口改名当作正式入口。

[前置条件失败记录](/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/run-G4/Backtest-Prerequisite-Attempt-BLOCKED.json)标示BLOCKED_BEFORE_ENGINE、engine_called=false、sealed_windows_executed=0。它记录的是前置评估，没有伪造失败交易窗口或零收益。

## P0-AUDIT：交付、版本与检查

新增3个封闭metadata合同，均1.0.0：HistoricalPITCandidateSnapshot、HistoricalPITClosureMatrix、HistoricalBacktestPrerequisiteAttempt。必填/NULL、枚举、namespace、时区、hash/ref、reason codes、失效条件在合同及[Contracts说明](/Users/qiushi/投资研究/ashare-trading-v1/docs/historical-pit/Contracts.md)中固定。它们不是原16个native合同或交易授权。

新增[ADR-038](/Users/qiushi/投资研究/ashare-trading-v1/docs/adr/ADR-038-daily-historical-pit-audit-and-conditional-backtest.md)及[本轮Owner授权记录](/Users/qiushi/投资研究/ashare-trading-v1/docs/authorizations/HISTORICAL-PIT-20261008.md)。native contracts、数据库Schema、001–006 migrations、依赖锁、生产参数、策略及legacy实验保持原样；未新增数据库迁移。

工程变化仅在historical_pit/、contracts/historical-pit/、docs/historical-pit/和上述两个新文档。分支historical/pit-20261008；前序基线54696f794b1bf4373654fc509aa22bda063b4488；最终代码候选c54abb06595bf7495c9d69bb22421402f91d562a。最终含报告的Git提交与文件清单由验收包Delivery-Checkpoint绑定，未推送远端。

| 检查范围 | 用例 |
| --- | ---: |
| 新历史原件读取／候选视图／闭环／反伪造／账本待执行状态 | 32 |
| 原财报与交易状态PIT | 96 |
| 原价格PIT | 45 |
| 原synthetic回测、T+1、费用与账本 | 110 |
| 原冻结策略与freeze-before-reveal | 38 |
| 原H-B PIT map | 36 |
| 原Day1受阻适配器 | 24 |
| 合计独立用例 | 381 |

最终工程副本所有381项PASS；合同另80个原子断言PASS。重复运行不累加，未重跑整个项目历史全量套件。工程副本使用同一本机锁定依赖与未移动的外部原件，验证的是本机干净检出的可复核性，不是远端CI或完整离线自包含原件证明。[最终检查摘要](/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/Final-Checks-Summary.json)、[最终原件保全摘要](/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/Final-Preservation-Summary.json)、[最终run重读验证](/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/Final-Run-Readback.json)。

New-Checks-Epoch2曾因新合同把原12字段字典误写成数组而失败；已修正新合同，原字典和所有失败日志保留。根代理审查还纠正了当前矩阵中的旧授权理由，原理由仍留存。本轮进行了根代理工程自审与自动验证，**没有把这些结果称为独立人工历史PIT放行**。旧V5 CLI hash mismatch和旧失败资产未修改、未伪造通过。

run-G1/G2/G3为保留的中间工程产物；最终采用run-G4。每个epoch独立目录，不覆盖前次。最终run有manifest/hash、冻结spec、原map与代码/合同引用。真实逐笔ledger文件为空并写明PENDING；所有实际收益指标NULL，待真正准入并执行后才产生记录。错误/失败/曝光窗口都不得删除。

## 尚未满足的执行条件与下一步

1. 三股逐日、逐域的独立历史first-visible、修订版本、有效区间、精确证券适用性与原件哈希；完整实际calendar/status/action核对；全family数据覆盖。现有供应方、许可和传输准入仍BLOCKED，技术可访问性不能替代这些证明。
2. Owner确认逐日决策时刻、实际日期化账户经济/风险/基准政策；锚点及purge/embargo边界在揭晓前完成审查和冻结。不能因工程完成自行补参数。
3. 独立实际审核通过全部历史输入，并完成正式PIT到实际引擎的正向adapter审查；封存未触碰的测试窗口。然后才执行已条件授权的协议，并生成逐笔ledger、gross/net、fees、turnover、MDD、benchmark excess、MAE/MFE与各窗口manifest/hash。
4. 未来线继续保持原v1。真实当日收盘证据及独立CAPTURE/REVIEW/FORWARD签名仍未由本轮历史工程提供；Day1/D5/D10不补造、不自动揭晓，也不回改预测。

[20域×三股完整矩阵](/Users/qiushi/投资研究/.p1b-archives/historical-pit-20261008/run-G4/PIT-Closure-Matrix-60.json)如下。BLOCKED指连续历史闭环，不否认已经存在部分结构/原件。

| 域 | 603993.SH | 600312.SH | 603228.SH |
| --- | --- | --- | --- |
| `adjustment_factor_semantics` | BLOCKED | BLOCKED | BLOCKED |
| `benchmark_total_return` | BLOCKED | BLOCKED | BLOCKED |
| `catalyst_originals` | BLOCKED | BLOCKED | BLOCKED |
| `corporate_actions` | BLOCKED | BLOCKED | BLOCKED |
| `dated_costs_and_account` | BLOCKED | BLOCKED | BLOCKED |
| `dividend_action_reconciliation` | BLOCKED | BLOCKED | BLOCKED |
| `economic_estimation_policy` | BLOCKED | BLOCKED | BLOCKED |
| `exchange_calendar_version` | BLOCKED | BLOCKED | BLOCKED |
| `financial_ann_fann_date` | BLOCKED | BLOCKED | BLOCKED |
| `historical_price_limit_regime` | BLOCKED | BLOCKED | BLOCKED |
| `historical_universe_completeness` | BLOCKED | BLOCKED | BLOCKED |
| `industry_history` | BLOCKED | BLOCKED | BLOCKED |
| `listing_anchor` | BLOCKED | BLOCKED | BLOCKED |
| `listing_delisting_history` | BLOCKED | BLOCKED | BLOCKED |
| `name_status_history` | BLOCKED | BLOCKED | BLOCKED |
| `raw_bars_volume` | BLOCKED | BLOCKED | BLOCKED |
| `revision_chronology_first_visibility` | BLOCKED | BLOCKED | BLOCKED |
| `st_history` | BLOCKED | BLOCKED | BLOCKED |
| `suspension_history` | BLOCKED | BLOCKED | BLOCKED |
| `valuation_history` | BLOCKED | BLOCKED | BLOCKED |

本轮工程产物完成交付并停止。正式历史回测、历史OOS、真实前向累计、云端研究导出、Signal/Order/券商和真钱执行仍未获本轮工程放行。验收包含本报告、代码/合同/ADR、60行矩阵、981候选视图、审计清单、前置失败记录、原件hash/index、以前序54696f7为基线的增量Git恢复包与检查日志；大体积既有原件、供应商原始响应、secret、私钥、数据库和手机备份不打包，留在原本地证据路径。

增量Git包的恢复需要已保全的54696f7前序仓库。原件重开与检查依赖未移动的本机证据路径；本验收ZIP不承担跨机器迁移全部历史数据的功能。
