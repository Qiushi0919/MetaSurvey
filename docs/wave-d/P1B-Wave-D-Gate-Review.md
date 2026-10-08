# P1-B Wave D Gate Review — Three-Stock Local Real Research Loop

本轮交付是三股当前观察的本地研究闭环；正式交接文档仍为主要 Source of Truth，显式 Owner 授权只覆盖 Wave D。Wave C 已获 Owner 接受，旧 Gate 保留交付时事实。所有数值、原件与四份真实报告保存在 Git 外的固定私有归档，Git 只保存方法、合同、规则、指纹与验收元数据。

最终工程结论为 **PASS_WITH_CONDITIONS**，LOCAL_REAL_RESEARCH_SANDBOX_GATE=PASS；795项回归=794PASS/0FAIL/1原有可选SKIP，独立审查413/413PASS。精确结论见同目录 Gate.json、validation.json 和 Independent-Review.md。建议接受本轮有限本地交付；正式准入、研究完整性、历史 PIT、云端模型及交易继续 HOLD/BLOCKED。该建议本身不是后续授权。

## 新版报告与事实增量

| 交付 | 本机私有文件 |
|---|---|
| 603993.SH 本地研究报告2.x | [报告](/Users/qiushi/投资研究/.p1b-archives/wave-d-20261006/results/REPORTS-G4/603993.SH.report.md) |
| 600312.SH 本地研究报告2.x | [报告](/Users/qiushi/投资研究/.p1b-archives/wave-d-20261006/results/REPORTS-G4/600312.SH.report.md) |
| 603228.SH 本地研究报告2.x | [报告](/Users/qiushi/投资研究/.p1b-archives/wave-d-20261006/results/REPORTS-G4/603228.SH.report.md) |
| 三股横向 ResearchComparison | [比较](/Users/qiushi/投资研究/.p1b-archives/wave-d-20261006/results/REPORTS-G4/ResearchComparison.md) |

每股58项 feature，九个明确分离的研究轴；34项财务/估值字段或派生特征有当前观察值。估值使用来源声明的 PE TTM/PB/PS TTM、股本/市值/换手率；没有将季度 EPS 冒充 TTM、计算 DCF 或给出贵便宜阈值。新增 income/balancesheet/cashflow 全字段原件（94/158/97字段）与 fina_indicator，保留报告期、ann_date、版本、原始 ordinal 和 hash；研究投影只使用明确命名字段。收入、合并利润、CFO、同口径现金转化、毛利、ROE、负债及应收/存货诊断逐项显示期间、单位和证据状态。财务货币量级仍未经独立证明，未转换成生产 CNY ledger 单位。

九轴为 Business Quality、Earnings/Cash Quality、Valuation、Sector、Catalyst、Timing、Risk、Evidence Quality、Unknowns。业务模式/竞争力缺验证经营原文，行业景气缺证据；财务事实不能代替这些判断。原 Wave C Quality/Timing 只保留原始实验坐标、原 cutoff 和 predecessor refs；新财务数据不重算旧评分。横向比较同时展示事实、坐标、冲突、证据质量及 UNKNOWN，没有总分排名、BUY/SELL、S/A/B/C/X、概率、胜率或 Edge。

## UNKNOWN 和八类覆盖

[逐项 UNKNOWN delta](unknown-delta.json)：旧每股10项 UNKNOWN 中4项已有当前观察值（CFO、同口径现金转化、源 PE TTM、当前行业）；6项仍未解决，新版另显式列历史可见性 UNKNOWN，因此当前为7项。不能用10减7推断闭合了3项，两个版本的特征词表不同。Business Quality 轴仍 UNKNOWN；每股现有7项 feature UNKNOWN 不是全部研究缺口清单。

[八类 coverage delta](coverage.json) 是可用原件投影的物理观察计数，重叠请求/多版本不伪装成唯一报告期或准入率。security、financial、industry、announcement 有当前观察增量；calendar、raw bars、actions、factors 主要保留旧证据。每股327个独立 raw/factor 日期保持分离，330/333物理记录体现保留版本，不是新交易日。三个新 stock_basic 源行业声明已可用，不回填历史成员；603993 原已有一个带行业字段的旧原件计数，不能把相同计数误读成没有新观察。

ST与停牌 MAIN/REPEAT 分别保留296/13条同日集合，但两份 terminal 响应未满足请求 schema，因此三股均不能由未出现在集合中推断 NON_ST/NOT_SUSPENDED，更不能推断10月6日可交易。新 listing/name/industry 仅为当前来源声明，不证明历史状态。

SSE官方180天查询窗口本轮每股只取索引第一页5条，共15条参考；不宣称完整180天覆盖。首次六个 PDF 请求遇到301；新 G2 独立记录原跳转并仅允许完全相同路径的 HTTPS static.sse.com.cn 目标。六个实际静态响应仍不是有效 PDF，body_verified=false；标题/日期不能成为经营催化事实。该公开 SSE 处理不适用于任何携带凭证的 gateway 请求。

同供应方 adjusted_close=raw_close×source_factor/latest_factor 共每股327条，仅为数学一致性诊断，不冒充独立价格/公司行动验证或总回报。旧5处多原件行动歧义、8处非零 pre_close 差额及 UNSET 容差保持原状；603228 旧财务冲突同样保留，未通过覆盖旧原件消失。

## 数据、时钟与权限

[实际产品/时钟矩阵](products-clock-matrix.json) 保存33次 gateway 请求（24初始＋9全字段）、33原件；均实际 code0，只能证明技术响应。旧数据重复抓取不等于新交易日。另有33次公开参考读取，包含官方文档、SSE索引、跳转元数据诊断和失败正文，不将失败响应计算成可用业务证据。两次本机 secret lookup，无凭证交互；未在 Git、fixture、报告或日志写入 Token，也未重读凭证做静态审计。捕获阶段进行了内存 Token 回显检查；最终高置信静态模式检查的范围和局限见 static-boundary.json。

新 retrieved_at 为原完整响应实际完成时刻；在无法独立证明历史首可见时，available_at=retrieved_at。只有 DATE_ONLY 的公告/报表/交易日期保留独立 source literal，event_time/published_at=null，不补午夜。未来 cutoff、source/rule/code/schema/hash 变动和重复/不一致版本必须阻断。[current/historical 边界](current-historical-boundary.md) 不以今日查询历史反推当时可见。

Provider / License / HTTP transport integrity 均 false，销售主体、产品、有效期和授权用途未获独立证明。Owner 声明15000月卡不会升级成独立认证 entitlement；技术成功也不产生 license、留存/转发或云端权限。所有 gateway 对象继续 QUARANTINED / UNVERIFIED_GATEWAY，formal_source_admission=BLOCKED；本轮未购买、绕过或申请新权限。historical_visibility_proven=false。

## 工程树与本轮新增边界

```text
ashare-trading-v1/
├── wave_d/                       # producer / features / private capture / reports / checks
│   ├── core.py / financial.py / status_action.py / research.py
│   ├── probe.py / full_statements.py / public_probe.py / public_enrich.py
│   ├── report.py / run.py / verify.py / contracts.mjs / check.mjs
│   └── tests/                    # 66 Python + 9 native new regressions
├── contracts/wave-d/              # Input / Assessment / Report2.0.0; Comparison1.0.0
├── docs/wave-d/                   # Gate / deltas / matrices / review / release / index
├── docs/authorizations/P1B-WAVE-D-20261006.md
└── docs/adr/ADR-025-three-stock-current-observed-research-loop.md
```

新增代码/合同与旧v1、WaveB/C、fixtures、migrations独立；没有改业务规则或GUI。真实报告、raw、日志、source snapshots、Git-onlybundle全部在私有归档，目录0700/文件0600，fresh checkout/npmcache的依赖副本不纳入数值证据库存。

## 合同、版本、Schema 与旧资产

[合同矩阵](contract-matrix.json)：RealResearchSandboxInput/Assessment/Report2.0.0、ResearchComparison1.0.0。闭合 schema、required/optional、enum/const、单位、Decimal字符串、时区、hash/trace、reason/invalidation、明确前序 refs 均版本化。闭合在进程 producer 必须重算 body、核验真实注册 upstream/context/parents 及实时来源依赖；正确 shape、hash、seal 或布尔标志不能赋予 live authority。JSON/Ajv 的本地 DISPLAY 校验不是正式 admission。

release2.0.0-wave-d-local-loop 共28个冻结源码/合同/规则 pins；563个旧不可变 tracked 文件与旧001–006、Schema6、依赖锁保持原字节，仅3导航文件允许更新。没有007迁移或旧数据库修改，临时 synthetic 原生执行正反对照并不认证实际外部数据库。V5一直为LEGACY_EXPERIMENT，14日portable ledger baseline和旧CLI hash mismatch保持原状态；没有改旧 seal、账本、runs、GUI或参数。

版本链为 Wave C Input/Assessment/Report 原件指纹 → Wave D Input → Assessment → Report → ResearchComparison。raw与adjusted分离；financial版本append而不覆盖。LLM APPROVE不是人工审批，沙盒对象不得进入正式receipt/packet/import/Card/Signal/Approval/Order。账号、佣金、资本、风险30项仍UNSET_REQUIRED，旧实验资金及费率未继承。

## 验收证据与已知失败

实际干净副本完整入口exit0：795unique=794PASS/0FAIL/1SKIP，其中旧720＋新75（41financial＋25boundary＋9native），没有重复计数。独立413/413PASS=217Python＋172native＋24SSE，32类实际断言；563旧不可变文件、28冻结pins、791去重依赖/产物before/after hash一致。精确日志 hash 见 validation.json / Gate.json；旧可选外部V5 SKIP仍作为SKIP，不计成PASS。独立审查只读源码与原件，财务比值/同比/复权独立 Decimal 计算，status完整性和原native正式消费者/订单门禁均做实际调用；正向对照明确 synthetic，production disabled。

[known-failures.json](known-failures.json) 保留数据失败、42越界财报行、旧差额和初始实现问题。G1/G2离线原型因全字段范围/数据边界收敛中断exit130，不计测试PASS。G3候选6eb2367的实际干净副本 replay FAIL：报告source_identity含Git绝对路径，移动checkout后改变；旧代码/原件/报告/失败日志与直接身份对比全部保留。G4改用Git相对路径＋固定私有归档键，重新冻结新 cutoff/code hash；修复未改变研究事实或费用/PIT/审批预期。另一次误在ROOT运行的日志虽然命名含fresh，不作为fresh证据。Interface-Freeze早段“final G3”只描述旧原型，最终G4段、rules和release pins为最终身份。G3 Reviewer native通过与源码变动后的Python中止均单独保留，不合并进最终assertion数。

## C12–C22、Snapshot B 与下一步建议

[conditions.json](conditions.json) 完整保留各项原状态并列新工程delta；C12–C22正式闭合数为0。C18/C21/C22有全字段原件、财务现金特征与新报告链的实质增量，仍缺正式来源、修订时序、校准/概率/Edge与正式producer。C30至少20个实际forward-paper交易日仍未满足，本轮新增实际paper日为0，不从日历或回放虚构。

[Snapshot B readiness](Snapshot-B-Readiness.json)：2026-10-06/07休市；10月8日只是候选恢复日。必须实际恢复交易、盘后数据真正可获得、另获Owner有限授权，再append新的observation；当前重新抓旧数据不能冒充B。正式B另需purpose-specific ADMITTED lineage，当前仍PENDING/NOT_READY。本轮没有创建后续自动执行/定时任务。

建议 **APPROVE_WITH_CONDITIONS：接受本轮三股 LOCAL_ONLY/NON_TRADEABLE 交付**；**HOLD：正式数据准入/Research Pilot、历史as-of/backtest、cloud/model/export/redistribution、Signal/Order、broker/production**。若后续获明确授权，优先解决status完整性、可验证公告正文/经营原文、provider/license/单位和实际Snapshot B，而不是扩股票池或参数优化。建议不构成这些任务的执行授权。

本轮完成后 **STOP**，Owner验收PENDING，next_phase_authorized=false。Git clean基线、最终tag、Git-only回滚bundle与本机交付checkpoint绑定最终提交；checkpoint路径见Gate.json。私有归档必须保持固定原路径，干净副本只证明移动Git checkout后的本地复现，不宣称私有archive可搬迁或远端CI认证。
