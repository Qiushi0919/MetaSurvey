# Legacy 资产与回放边界

`legacy/asset-manifest.v1.json` 是机器可读资产索引，包含 `KEEP / MODIFY / ISOLATE / DEPRECATE / DELETE_LATER` 五类。分类只描述迁移处置方式。`MODIFY` 指新项目中的版本化替换实现；旧原件继续只读。`DEPRECATE` 是替代验收后的计划，当前未退役旧写入口；`DELETE_LATER` 仅记录候选缓存，本轮没有删除授权或执行。

V5 的 namespace 为 `LEGACY_EXPERIMENT:sector-swing40-v5`，`target_strategy_mapping=null`。保存原 40 个交易日实验窗口、5—8 个交易日计划持仓、旧本金/预算/风险假设、旧费用/滑点、46 个封存源码与配置哈希、原始运行状态。其 `BLOCKED`、完成 14/40 日、下一日 2025-04-30、未完成状态原样保留；该状态快照不证明当前后台进程健康。V5 不映射为 `CORE_40` 或 `EVENT_3`，旧参数不是生产默认值。

manifest 中的路径相对旧工作区根。默认根为新 repo 父目录，搬迁后设置 `LEGACY_ASSET_ROOT` 到包含 `模拟交易实验`、`交易策略` 和 `History` 的工作区根即可。只读 adapter 不重写旧的绝对路径、relocation manifest、seal 或历史答案。

## 纳入 Git 的最少内容

- manifest：边界索引和 85 个选中旧文件的 SHA-256、字节数，包括正式交接、迁移基线、V5 源码/规则、旧 seal、状态/日志与 14 日 frozen/result。
- `tests/fixtures/legacy/v5-fourteen-days.v1.json`：`LEGACY_FIXTURE_NOT_PRODUCTION`，仅保存 14 日日账本行、快照、旧独立核账、源码/决策/原始文件哈希和明确的旧费用 profile。保留全部 `UNFILLED` 原因。金额维持原整数分、价格维持原整数厘；只有 legacy adapter 接受原始 safe integer。
- `tests/fixtures/legacy/p0-external-replay-evidence.v1.json`：本轮实际外部重放的选中锚点前后 fingerprint、逐日一致性、六项 native binding 诊断及原 seal 失败。
- 新 read-only adapters 和 portable golden tests。

大体积 runs、PDF、Parquet、原回答、模型 state 数据库、业务数据库、credentials 和 Application Support 运行副本不纳入 Git。不复制整个实验目录。目录级资产条目是边界清单，不是全目录递归内容认证；本轮只对上述 85 个选中文件做内容 fingerprint，未重新审核全部原始资料。Application Support 运行副本和所有 DB 内容也不在本 fingerprint 范围。

## 验证入口与状态口径

```sh
npm test
npm run legacy:verify
npm run legacy:replay
RUN_LEGACY_EXTERNAL_TESTS=1 node --test tests/legacy.test.mjs
```

默认 CI 只运行 portable fixture 测试，不依赖本机旧目录、Python 环境或 CLI。外部命令需要旧资产和有 BeautifulSoup 等旧依赖的 Python 环境；默认沿用已安装的 `InvestmentResearchV2/venv/bin/python`，可用 `LEGACY_PYTHON` 显式指定。没有安装或升级旧环境。

`legacy:verify` 检查 85 个原始锚点及 portable fixture 哈希，诊断 native bindings，并运行**原封不动的** `isolation_audit.verify_contract`。本轮锚点通过，原 seal 仍报 `PINNED_CONTEXT_OR_CLI_CHANGED`，因此命令返回 **exit 2**。这表示已知 native compatibility 失败，不能报告为全通过。未知损坏、额外绑定变化、缺失文件或 adapter 错误返回 exit 1。

`legacy:replay` 的验收对象是保存输入的确定性核算：portable 侧用独立 BigInt 算法逐日核查厘到分、原 profile 费用、现金、数量和 NAV；external 侧读取保存 frozen/bars/actions，调用未修改的旧 `Engine` 和 `reconcile`，逐日比较 saved rows / snapshots / reconciliations。14 日核算一致时返回 **exit 0**，同时单列 `native_compatibility.status=FAIL` 和 `native_compatibility_is_repaired=false`。它不能代替失败的 native seal 验证。

外部 Python 使用 `-B`，并安装 audit hook 阻止文件写入、文件变更、网络与子进程；不调用旧运行、模型、采集或通知入口。Node 在执行前后再次核验选中锚点 fingerprint。此 guard 防止 adapter 及正常 Python 依赖误写原件，不是对抗恶意本机拥有者或原生扩展的安全证明。

## 本轮实际结果（2026-10-05）

2025-04-10 至 2025-04-29，14/14 日旧 snapshot、daily rows、旧独立 reconcile 匹配；8 笔买卖、4 个完整 round、保留 4 条未成交记录。期末现金和 NAV 均 979,114 分，显式费用 4,986 分，净盈亏 −20,886 分，期末无持仓。

85 个选中锚点的 before/after fingerprint 均为：

`e4b6e8a9d9eb2d28128940804be51b915e64b36a3501ab47b3588dfbcfc47d2a`

原 native seal 的 tool schema、builtin、static context、environment template、command 五项一致。CLI 封存哈希为 `3e11ccc743e8198a5ef84fb57c89941d845b0ea0302485ed1fbac2f0821aca5a`；本轮实际文件哈希为 `6b582e8813ce7e8ed4c52814ee5cf230dba647bf2292df747a4003f2657ef201`。此兼容性问题保持 OPEN，未修改 seal，未更换 expected 值，也未将诊断结果伪装成 native PASS。

以上证明保存决策与保存日线代理裁判数据可确定性重放，不能证明全部原始公告/资料满足严格 PIT、整个 40 日实验已完成或策略具有盈利能力。代理成交标签与数量不确定区间保持原样。没有补造现代 account_id、strategy_id、概率、审批或真实成交事实。

Portable legacy 测试有 11 项常规测试通过，1 项外部测试默认跳过；显式启用外部资产时该项也运行。外部测试期望保留 native FAIL，不能因 regression suite 全绿而宣称 native compatibility 修复。
