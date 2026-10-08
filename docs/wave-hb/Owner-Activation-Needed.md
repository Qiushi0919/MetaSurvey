# H-B 实际运行前仍需的材料

Owner 的本轮条件授权已记录，无需重复批准 A–F。已完成离线预检；实际 G 当前 HOLD，actual_forward_days=0。此文件是缺项说明，不是签署的 Capture / Review / Forward grant。

1. Owner 与独立 Reviewer 的实际 Ed25519 **公钥**及外部身份、来源和独立保管证明。当前两个公钥和 fingerprint 均 UNSET_REQUIRED。公钥候选格式或不同指纹不能证明独立人类身份，producer 不代为安装信任根。
2. 下一实际有效 session 的 observed open/EOD 原件、精确时钟及来源。预检中的 2026-10-08 只是计划日标签，不能提前认定开市或收盘，更不能生成 Day 1。
3. 外部 Owner 签署 Capture grant；独立 Reviewer 重开原件并签署 Review grant。Review PASS 后才可发行 actual current Snapshot B。
4. 独占创建或验证 actual Forward store、读取真实 expected head 后，Owner 另行签署绑定 Snapshot/session/head 的 Forward grant。Capture、Review 与 Forward 权限互不替代。

实际运行仅使用既有冻结的 credential lookup reference；本轮未重查 Keychain。请勿提供 Token、私钥或密码。当前异步问题只请求公钥及证明材料的本地路径，没有收到材料。

满足这些前提后的单次顺序见 H-B-Preflight.json 与旧 H-A One-Shot-Activation-Runbook.md。上限为 exact-three / 13 次只读请求，采集15分钟、独立审查30分钟、append5分钟、全链60分钟；失败隔离并 STOP，无重试、补日或自动晋级。新监督器仅离线验收，不自行调用实际 runner。

Provider/License/Transport 八维仍 UNKNOWN；正式历史 PIT、云/模型/再分发、Signal/Order/Broker/真实资金/生产继续 BLOCKED。原30项真实账户配置及15项补充输入继续 UNSET_REQUIRED，它们不阻止工程准备，但仍阻止真实净收益和生产执行。ACTUAL_ACCOUNT 成本证据 admission adapter 尚未实现，即使自填 OWNER_SET/self-hash 也无法计算真实 NetEdge。

本轮报告交付后 STOP。未创建定时任务、Day 2 或真实运行计划；不自动等到计划日期执行。
