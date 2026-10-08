# CORE_40 数据维护与重复验收

在专项 worktree `/Users/qiushi/投资研究/ashare-backtest-5y` 执行。原件、库和新输出均留在私有 epoch；每次输出目录必须是未使用的新目录。已有结果保留原样。

日常维护流程是：生成更新计划 → 明确选择可用来源 → 增量采集并保留原件 → 重新检查缺口、质量和版本冲突 → 生成最新策略前置条件诊断 → 生成逐字段验收材料。当前已配置的公开来源不能提供完整历史状态、财务修订链、行业和总收益；这些缺口不会因重复运行自动变成 PASS。

[原入口](</Users/qiushi/投资研究/ashare-backtest-5y/backtest_5y/README.md>)给出了 import / refresh / check 的实际命令。以下命令读取最终真实库和 R3 诊断，仅生成验收报告。这里的 `example-new-acceptance` 需在每次执行时换为新的目录名：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m backtest_5y.delivery \
  --db /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/evidence.sqlite \
  --diagnostic /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/run-07-r3/frozen-family-diagnostic.json \
  --output /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/example-new-acceptance
```

如果库已更新，先执行 check 并将 `--diagnostic` 指向新 check 的文件。验收入口会拒绝计数不一致或引用不属于当前库的诊断，拒绝家族/策略变化、未解析引用、越界日期，以及任何引擎运行/真实准入/生产权限或非空经济成绩声明。报告输入必须通过原件完整性复查；输入库在报告生成前后保持字节一致。

本次真实执行目录是 [acceptance-01](</Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/acceptance-04/Delivery-Package-Manifest.json>)，含20域111字段依赖行、3,633股票日期前置记录和7,266两家族决策前置记录。它们用于定位缺口，不能被导入真实订单或当成完整模拟交易账本。

更新保留实际采集完成时间、原始披露日期的精度、来源和请求、原始响应哈希、捕获与内容版本关系。日期级披露不推成零点可见；采集哈希不是供应商 revision ID；请求完整历史区间也不证明返回完整修订链。未知单位、同季度矛盾版本、缺字段和跨源冲突会保留并阻断计算。

当前月度网关遇到 IP 并发限制。新采集器在该错误后停止剩余请求；恢复前需确认稳定出口和供应商允许方式。公开来源采用有上限的请求，不包含隐藏代理、重试或权限购买。没有修改 Clash 设置。

此机制提供可重复维护入口。本轮 Gate 提交后停止采集/实验，没有创建定时任务。下一轮恢复数据维护及任何方法/接口或实际 PIT 准入仍按 Owner 和原主控验收边界处理。当前全部成果 NON_PIT_DIAGNOSTIC / NOT_FORMAL_OOS / NON_TRADEABLE；完整家族 NOT_COMPUTABLE，经济 ENGINE_NOT_RUN/null。
