# 并行开发检查入口

运行位置：`/Users/qiushi/投资研究/ashare-trading-v1`。依赖现有 Python 标准库和本机 `/opt/homebrew/bin/git`，没有新增包或变更锁。

```sh
/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m unittest integration_review.test_boundary -v
/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m integration_review \
  --baseline /Users/qiushi/投资研究/.p1b-archives/backtest-5y-handoff-20261008/Parent-Immutable-Baseline.json \
  --forward-checkpoint /Users/qiushi/投资研究/.p1b-archives/backtest-5y-handoff-20261008/Protected-Forward-Refs.json \
  --parent /Users/qiushi/投资研究/ashare-trading-v1 \
  --child /Users/qiushi/投资研究/ashare-backtest-5y
```

检查只读，不修改两边代码、Git或外部原件；覆盖基线文件内容、允许目录、已提交/已暂存/未暂存/非ignored新文件。ignored运行状态和工作区读取后变化不在这个工具的证明范围。它不是操作系统权限隔离，不阻止一个拥有文件权限的程序写其他位置。

954旧文件在两边都逐字节/hash核对。保护文件中的 D1 journal 是本轮工程检查点；后续主控依法通过原签名验证入口追加时，要新建经审阅的 journal 检查点版本，保留旧检查点，不能重写冻结预测/来源/receipt。工具不会阻断或改写产品运行链。

Forward 当前入口仍使用原 `day1_reveal` 和 `wave_h`。三阶段签名依次绑定不同主题，不能合并成一次签名：Owner CAPTURE → 捕获原件 → 独立 Reviewer REVIEW → Snapshot B/检查store head → Owner FORWARD → actual append → D1 reveal。公开公钥的 setup 验签不替代这三份授权。

当前 root 只跑只读检查，无secret读取、市场请求、私钥读取、实际store创建/追加或自动运行。本轮报告的通过结论只覆盖工程边界，不包含专项尚未交付的完整策略、实际价格链、历史PIT或费用后Edge。
