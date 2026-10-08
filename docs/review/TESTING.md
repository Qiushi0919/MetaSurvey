# 公开复现检查与本地证据检查

公开 CI 是 `Public synthetic engineering checks`，在 Ubuntu/macOS 使用 Node 24、Python 3.12。依赖按现有 package-lock 安装，Python 此入口只使用标准库。

```sh
npm ci --ignore-scripts
node scripts/verify-contracts.mjs
node tools/github_publication/test_node.mjs
python3 -B tools/github_publication/test_python.py
```

Node runner 不改原有用例，明确排除两项需要本机未核验许可的 PUBLIC_REFERENCE 原件测试：真实 SSE raw/calendar adapter 测试，以及公共夹具原件哈希/来源测试。外部 V5 replay 是原先的可选 SKIP；公开 CI 不声称已经复核本机 V5 的真实 14 日封存账本。另有七项 closure/replay 用例必须校验未公开的原始 Git commit 与 source tree，公开版明确不执行；不改 code-provenance pin，也不伪造原始 Git 历史。九项不执行用例的精确名称和分别的原因由 Node runner 输出。公开集合内的 PIT、费用、T+1、审批、namespace、UNSET 执行阻断断言照常运行。本机完整原生集合另行通过，见发布报告；公开集合不等价于完整 Gate。

Python runner 原样运行 backtest sidecar 123、未批准方法合成算术 75、workspace boundary 11，共 209 项。仅在 runner 进程中把六个 fixture 输出路径指向新的临时目录，并把 Homebrew Git 路径映射到当前 Git；不改原代码、断言或业务门禁。socket 连接被拒绝且尝试计数必须为 0，不读取真实凭证、账户或历史库。

公开 CI 不覆盖：实际 Provider/License 证明、真实历史 PIT、真实 Day1 原件揭晓、真实签名审批链、原件重分发授权，以及本机私有档案依赖的历次阶段总 Gate。原有 `npm run check` 和历次 `wave_*/check` 保持原逻辑，需要相应本机证据；旧 P0 入口还含阶段性 1 MiB 文件限制，当前大型 PIT 元数据超出该旧规则。旧 workflow 改为手工触发并明确其依赖，不能把其未运行解释为通过。

本轮公开检查的实际数量、失败/跳过和运行位置记录在 [发布报告](releases/2026-10-08-github-publication/REPORT.md)。合成检查成功不关闭任何真实数据或交易 Gate。

仓库文件完整性可用 `python3 -B tools/github_publication/verify.py` 校验。此检查逐一核对当前 Git HEAD 的公开文件集合、源文件字节哈希和六项 local-only 排除，不需要本机历史原件。
