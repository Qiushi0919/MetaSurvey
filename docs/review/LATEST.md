# 最新验收入口

更新：2026-10-08（Asia/Shanghai）。审核人先读当前集成报告，再读需要自己复核的合同与独立审查。

| 内容 | 位置 | 状态 |
|---|---|---|
| 本轮 GitHub 公开发布 | [公开发布验收报告](releases/2026-10-08-github-publication/REPORT.md) | 工程发布检查；不改变业务准入 |
| 五年回测专项 P1 主控集成 | [Acceptance-Report](../backtest-5y-integration/Acceptance-Report.md) · [Status](../backtest-5y-integration/Status.json) | PASS_WITH_CONDITIONS |
| 共享接口与六 DTO | [Remaining-Contract-Gaps](../backtest-5y-integration/Remaining-Contract-Gaps-v1.json) | 1.0.1-candidate；最终字段冻结 HOLD |
| 独立审查原文 | [R1](releases/2026-10-08-p1-integration/reviewer/Independent-Interface-Review-R1.md) · [R2](releases/2026-10-08-p1-integration/reviewer/Independent-Interface-Review-R2.md) · [R2 harness 澄清](releases/2026-10-08-p1-integration/reviewer/Cases-R2-Harness-Clarification.json) | 原文复制，保留失败和限制 |
| 保全审计 | [初始 FAIL](releases/2026-10-08-p1-integration/Integrated-Preservation.json) · [纠正表示比较后的结果](releases/2026-10-08-p1-integration/Integrated-Preservation-Corrected.json) | 原件没有修改 |
| CORE40 方法提案 | [Review-Report](../core40-method-proposal/Review-Report.md) · [Owner-Decisions](../core40-method-proposal/Owner-Decisions.md) | M01–M08 PENDING；未采用 |
| 系统架构 | [ARCHITECTURE](ARCHITECTURE.md) | 已实现与目标分别说明 |

旧 Gate 的历史状态保持原文。当前真实执行边界以集成 Status 和新的人类授权为准；公开上传只授权软件、合同、文档和可分享工程审查元数据发布。实际 PIT admitted=0、实际 Forward days=0、真实费用/账户/风险参数仍未设置，正式历史回测、OOS、生产数据、云端研究导出、券商和真实资金执行继续 BLOCKED。

以后每一轮主控验收更新此入口，机器索引在 [INDEX.json](INDEX.json)。固定入口用于找到最新报告；正式验收时同时记录报告的 GitHub commit 固定链接，以免后续更新改变被验收版本。
