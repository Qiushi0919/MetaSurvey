# 最新验收入口

更新：2026-10-14（Asia/Shanghai）。审核人先读当前集成报告，再读需要自己复核的合同与独立审查。

| 内容 | 位置 | 状态 |
|---|---|---|
| 现有网关真实历史诊断 V3 | [本轮验收](../e2e-gateway-v3/Acceptance-Report.md) · [实际数据覆盖](../e2e-gateway-v3/API-Coverage.json) · [独立算术](../e2e-gateway-v3/Independent-Arithmetic.json) · [CI](../e2e-gateway-v3/CI-Results.json) | 引擎已实际运行：241日、70模拟成交、35完整买卖；完整研究策略未验证；页面截图暂待解锁或授权独立浏览器 |
| 真实历史输入与首次引擎运行 V2 | [本轮验收](../e2e-history-v2/Acceptance-Report.md) · [来源核验](../e2e-history-v2/Source-Review.md) · [独立审查](../e2e-history-v2/Independent-Review.md) · [CI](../e2e-history-v2/CI-Results.json) | 主目标未达成：匿名源两次连接失败，engine_called=false；历史例外事件decoder仍缺；新增4业务子分项/7集中判断 |
| 端到端研究试点与基础组合诊断 V1 | [本轮验收](../e2e-pilot-v1/Acceptance-Report.md) · [真实资料](../e2e-pilot-v1/Data-Feasibility.md) · [独立复核](../e2e-pilot-v1/Independent-Review.md) · [双平台CI](../e2e-pilot-v1/CI-Results.json) | 9家公司/27真实财务分项已接工作台；完整总分及真实历史运行尚未完成 |
| V0审查修正与真实输入核对 | [本轮验收](../score-review-v01/Acceptance-Report.md) · [差异](../score-review-v01/Changes.md) · [字段缺口](../score-review-v01/Field-Matrix.md) | Ubuntu/macOS评分72+工作台51均通过；真实总分BLOCKED；候选工程规则已确认 |
| 双层评分实验与七页工作台 | [本轮验收报告](../sector-stock-v0/Acceptance-Report.md) · [规则](../sector-stock-v0/Scoring-Rules.md) · [预注册](../sector-stock-v0/Preregistration.json) | 计算/Schema/界面工程通过；真实评分0，正式回测未运行；候选方法待审批 |
| 本轮本地只读工作台 v0 | [界面验收与启动](../workbench-v0/Acceptance-Report.md) · [Checks](../workbench-v0/Checks.json) | 已实际启动；六页真实产物；不改变业务准入 |
| 当前交接入口 | [执行卡与背景报告](../handoff/MetaSurvey-Handoff.md) · [只读核对与预期哈希](../handoff/Evidence-Index-20261008.json) | 保留正文；记录当前分支旧研究复跑的依赖哈希阻断，无新 Gate |
| 本轮 GitHub 公开发布 | [公开发布验收报告](releases/2026-10-08-github-publication/REPORT.md) | 工程发布检查；不改变业务准入 |
| 五年回测专项 P1 主控集成 | [Acceptance-Report](../backtest-5y-integration/Acceptance-Report.md) · [Status](../backtest-5y-integration/Status.json) | PASS_WITH_CONDITIONS |
| 共享接口与六 DTO | [Remaining-Contract-Gaps](../backtest-5y-integration/Remaining-Contract-Gaps-v1.json) | 1.0.1-candidate；最终字段冻结 HOLD |
| 独立审查原文 | [R1](releases/2026-10-08-p1-integration/reviewer/Independent-Interface-Review-R1.md) · [R2](releases/2026-10-08-p1-integration/reviewer/Independent-Interface-Review-R2.md) · [R2 harness 澄清](releases/2026-10-08-p1-integration/reviewer/Cases-R2-Harness-Clarification.json) | 原文复制，保留失败和限制 |
| 保全审计 | [初始 FAIL](releases/2026-10-08-p1-integration/Integrated-Preservation.json) · [纠正表示比较后的结果](releases/2026-10-08-p1-integration/Integrated-Preservation-Corrected.json) | 原件没有修改 |
| CORE40 方法提案 | [Review-Report](../core40-method-proposal/Review-Report.md) · [Owner-Decisions](../core40-method-proposal/Owner-Decisions.md) | M01–M08 PENDING；未采用 |
| 系统架构 | [ARCHITECTURE](ARCHITECTURE.md) | 已实现与目标分别说明 |

旧 Gate 的历史状态保持原文。当前真实执行边界以集成 Status 和新的人类授权为准；公开上传只授权软件、合同、文档和可分享工程审查元数据发布。实际 PIT admitted=0、实际 Forward days=0、真实费用/账户/风险参数仍未设置，正式历史回测、OOS、生产数据、云端研究导出、券商和真实资金执行继续 BLOCKED。

以后每一轮主控验收更新此入口，机器索引在 [INDEX.json](INDEX.json)。固定入口用于找到最新报告；正式验收时同时记录报告的 GitHub commit 固定链接，以免后续更新改变被验收版本。
