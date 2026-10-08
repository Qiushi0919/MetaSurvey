# Wave H-A：Owner 激活说明

本轮工程 **PASS_WITH_CONDITIONS**，Actual Collector 达到 **READY_FOR_ONE_SHOT_OWNER_AUTH**。真实 Snapshot B **NOT_YET_RUN**，actual_forward_days **0**。这是已实现并离线验证的单次运行能力；真实签名正向链、行情返回和实际 store 尚未验证。本轮交付后 STOP，没有调度任务。

未来 H-B 仍需在实际市场事实已知后给出一份新的 Owner 指令。计划日历、2026-10-08 标签、今天能查询旧日线、fixture 或模拟 ledger 均不能证明实际开市/EOD 或 Day 1。本轮没有读取 Keychain 或要求 Token。

单次运行必须依次完成：

1. Owner 在 producer 之外安装不同的实际 Owner / Independent Reviewer 公钥；不安装测试键。当前固定 enrollment 项不存在。实际签名私钥由外部人类保管，产品没有实际签名或 enrollment 接口。
2. 记录真实 observed open/EOD、精确观察时钟及原件，建立绑定冻结 A 的 exact-three plan；Owner 单独签署 Capture grant。
3. 仅抓 603993.SH / 600312.SH / 603228.SH，当日固定 13 个只读 request，不自动重试、redirect、proxy 或 fallback。实际 credential 只由已冻结的 Keychain 引用读取。clean raw/clock 保存后校验；失败隔离，不生成 Snapshot、不计日。
4. 独立 reviewer 重开 raw、clock、A 和 lineage，验证 fresh exact-three、actual session、时钟精度、policy/schema/hash；在 producer 之外签署 Review grant，再颁发当前 Snapshot B。
5. 在新的 H-B scope 和实际 enrollment 下独占创建空 actual store，读取 genesis head（仍为 0 天）；若已有 series，先完整 reopen，绝不覆盖。之后 Owner 才签署另一个绑定 Snapshot B/session/head 的 Forward grant。
6. atomic append 一次 NO_DECISION / NO_ORDER / NO_BROKER / NO_MONEY；重开验证 actual_forward_days=1 后 STOP。Capture 不等于 Forward，Forward 不等于 trading；失败、partial、duplicate 和 staging 均不能增加实际天数。

完整字段与操作顺序见 One-Shot-Activation-Runbook.md / Contracts-v1.json；机器 metadata 见 Owner-Activation-Report.json。公钥安装和签名键保管是外部信任根，不能证明被盗键背后的人类意图；不声称抵御宿主机所有者、特权文件系统或 interpreter 篡改。

Provider / license / HTTP transport 八维仍 UNKNOWN/BLOCKED。LOCAL exception 只允许单独批准的当前本地只读捕获，不能升级 source admission、历史 PIT 或云端转移许可。正式价格/财务 PIT、真钱、broker、native Signal/Approval/OrderIntent/Order/Fill、cloud/model/export/redistribution、production 继续 BLOCKED。30 项真实账户/成本/风险设置保留 UNSET_REQUIRED；本轮不采购、猜测、优化或扩大证券池。
