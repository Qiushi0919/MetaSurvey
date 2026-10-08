# 双线合同与本机检查入口

ForwardPrediction-v1 / ForwardOutcome-v1 两个 closed JSON Schema 均为 1.0.0，目录 `contracts/dual-track/`。这是研究 metadata sidecar，不增加 native 合同、数据库 schema 或 migrations。已有 CORE_40 / EVENT_3 / RESEARCH_6_18M 隔离不变；新 sidecar 只接受本轮 CORE_40 三股 namespace，拒绝额外交易字段。

所有 schema 字段 required，明确 nullable 的字段才可为空。Prediction 的 D10 概率和引用中心价在 D1/D5 必须 NULL；version_parent 在这次新 v1 为 NULL。新信息须另存新版本。金钱使用 CNY Decimal 字符串；return_percent 表示百分数，forecast_error_percent_points 是百分点；历史诊断 ratio 中 1=100%。拒绝 float/NaN/Infinity/科学记数法输入。保存 UTC offset-aware timestamp，交易日使用 Asia/Shanghai 日期，不把 date-only 财报日期填成午夜。

Prediction 绑定 source_ref(path/bytes/SHA-256)、固定日期、九个 symbol+horizon 条目、本机冻结时间、原外部 hash 的未核验状态、reason_codes、invalidation。Runtime 进一步检查唯一性、区间、中心价舍入、D10 tie、pre-open deadline。文件或原文 hash 改变、base 原件不匹配、target mapping 被推翻、边界改变均阻断；不自动修补 v1。

Outcome 绑定 prediction SHA、store 实际路径所生成的 genesis、sequence、previous_hash、expected_head、symbol+horizon 和 score hash。SYNTHETIC_FIXTURE 与 ACTUAL_RESEARCH_ONLY 为不同 genesis 和 schema 分支。实际分支必须重开原 Snapshot B 验证器，核验真实采集和独立复核签名、原件和 Literal Clock，并核对 base raw close。单独 FORWARD 签名与原 G store 仍由旧模块处理，sidecar 不替代它，也不增加实际前向天数。

direction_hit 使用三态 sign（0 是 neutral），range_hit 上下边界 inclusive；realized_return 为 target raw close / base raw close - 1，forecast_error 为实际减预测中心。D1 MAE/MFE 使用真实当日 low/high 与 base 对比；D5/D10 不完整路径为 NULL。结果全是 raw price comparison，行动与许可未核验，不是 total return、成交或净盈利。D10 必须三股同一预测的已验证结果齐全后才能计算严格顺序及 pairwise hits，保留实际收益相等的 tie group。

合同相关 reason codes 以源文件中的 `DT_*` 为 fail-closed 工程错误；保留旧 `WH_*` 验签、命名空间和源数据错误，不统一吞成 PASS。模式、身份、时间、版本、hash、来源、head 和重复检查不可由显示用 JSON 或 LLM APPROVE 替代。

本地离线检查：

```text
node dual_track/check.mjs
node wave_hb/check.mjs --new-only
```

前者执行新单元测试和版本化 schema 检查，后者执行已有 230 项 H-B 检查。依赖锁、package.json 不变。测试使用明确 synthetic fixture，不能拿它作为真行情。

手工读取已冻结记录：

```text
python -B -m dual_track inspect --freeze-receipt /绝对路径/Freeze-Receipt.json
```

后续真实 outcome 的 head/append-reviewed-outcome 入口只读取已存在且真实签名链合格的 Snapshot B，没有数据下载、密钥生成、Keychain 读取或自动运行功能。当前没有这样的 Snapshot B，不能运行正向实际路径。现有私有证据根不可搬移；本轮验证不声称远程无证据根 CI 可复现。

停止条件：完成本轮报告和验收包即停止。Oct8 在真实 EOD 前没有答案；现有研究合同不能绕过三次人工签名、自动启动实际 G、Day2 或资金执行。
