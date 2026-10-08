# MetaSurvey · A 股研究与验证系统

这是 MetaSurvey 的公开工程与审查仓库。审核人可以从这里阅读目标架构、当前代码、跨模块合同、数据库迁移、冻结策略、测试和历次 Gate 报告。

- **[最新验收入口](docs/review/LATEST.md)**：每轮报告和待确认事项从这里进入。
- **[系统架构与模块地图](docs/review/ARCHITECTURE.md)**：区分目标架构、已实现工程和仍被阻断的真实执行链。
- **[正式 V1 工程交接文档](docs/specifications/V1-Engineering-Handoff.md)**：原文保全副本；[来源与哈希](docs/specifications/Source.json)。
- **[五年回测专项集成验收](docs/backtest-5y-integration/Acceptance-Report.md)** / [状态](docs/backtest-5y-integration/Status.json) / [共享合同缺口](docs/backtest-5y-integration/Remaining-Contract-Gaps-v1.json)。
- **[CORE40 方法提案待 Owner 决策](docs/core40-method-proposal/Owner-Decisions.md)**：提案尚未升级为策略规则。
- **[公开测试与本地证据边界](docs/review/TESTING.md)** / [发布维护说明](docs/review/PUBLISHING.md)。

当前工程集成为 `PASS_WITH_CONDITIONS`。五年回测六项共享 DTO 是 `1.0.1-candidate`，最终字段冻结仍 HOLD；正式历史 PIT、OOS、真实资金执行继续 BLOCKED。Forward Day0 保持冻结，实际前向天数为 0，Snapshot B 尚未实际运行。测试通过表示对应工程用例通过，不能证明策略收益或授予交易权限。

```text
contracts/              原生 16 合同与各阶段扩展
src/                    Data/PIT、成本、纸面账本、版本门禁与审计
migrations/             PostgreSQL 001–006
config/                 UNSET_REQUIRED 与研究规则配置
backtest_5y/            五年历史专项 sidecar（已集成，正式运行受阻）
dual_track/             历史诊断与未来盲测协议
day1_reveal/            冻结与揭晓检查
method_proposals/       未批准方法的合成算术验证
integration_review/     分支边界与冻结文件保全检查
docs/                   ADR、授权范围、Gate、审查与验收
legacy/ + adapters/     历史资产 manifest / 兼容适配
tests/                 合成与标明来源的工程回归夹具
tools/github_publication/  可公开复现检查与单向发布工具
```

公开仓库是由主控工程生成的**单向发布快照**，不是原始工作区的所有磁盘内容。运行数据库、credentials、私钥、历史原始证据、大型验收 ZIP 和许可未核验的行情/页面原件留在本机。首次公开提交没有携带含原件的本地 Git 历史。

发布快照的逐文件 SHA-256 与源工程 commit 见 `docs/review/Source-Snapshot.json`；排除项见 `docs/review/Local-Only-Manifest.json`。这两份文件由发布工具生成。旧报告中的本机绝对路径仍按原文保留，公开可读的独立审查副本见 [报告索引](docs/review/LATEST.md)。没有发布仓库许可证或授予第三方数据再分发权。
