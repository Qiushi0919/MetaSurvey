# 双线并行接口审查 v1.0.0

2026-10-08。主控基线 `0ea206a834cf4f68a94b536b26377d390f02ec18`。依据 Owner 本轮明确批准的专项受限实施，以及专项 `Shared-Interface-Proposals.md` 作工程审查。正式交接文档仍为主要 Source of Truth，建议和 UNSET_REQUIRED 不因此成为业务规则。

结论：**APPROVE_WITH_CONDITIONS_FOR_SIDECAR_IMPLEMENTATION**。批准下面的模块边界、接口语义和原版本只读引用；六类接口目前没有完整字段 Schema，不能宣布它们已获最终字段合同批准。专项可在自己的 worktree 实现、测试并提交具体 Schema 与正反例，不需要等待真实账户参数才能编程。正式运行权限由原有数据/人类审核/执行门禁决定。

## 工作区与文件所有权

主控源码 `/Users/qiushi/投资研究/ashare-trading-v1`，分支 `forward/parallel-review-20261008`，负责 Forward 原件、实际当前市场数据链、跨模块合同终审、合并及验收。专项 `/Users/qiushi/投资研究/ashare-backtest-5y`，分支 `backtest/5y-initial-review-20261008`，负责新目录 `backtest_5y/`、`contracts/backtest-5y/`、`docs/backtest-5y/`、`tests/backtest-5y/`。

专项内部 Data、Engine、Economics、Audit 精确文件分配由专项总控维护；共用文件只由专项总控整合。四个新目录中的合同属于待审候选。旧 954 个文件、原生16合同、Schema6、migrations001–006、策略、锁和 legacy 保持原字节。专项不修改主控工作区，也不修改共享外部原件；主控不在专项 worktree 写入、切换分支、重置或合并。新增 ADR/迁移若确有必要，提交差异与兼容方案，由主控分配编号；本轮不预占任何编号。

## 六类接口决定

| 接口 | 当前审查决定 | 最终接入前必须验证 |
| --- | --- | --- |
| HistoricalEvidenceBundle | 批准工程证据 DTO 方向 | 原件路径/hash/字节/行选择、四时钟与精度、知识/有效区间、修订链和单位明确；技术访问与许可、历史可见性分别表达。日期精度不得补成午夜 |
| AdmittedHistoricalSnapshot | 批准实现拒绝路径和真实证明消费桥 | 不能以调用者布尔值、软件审查或当前抓取 hash 发放准入；price-only 与 full-family 覆盖须明确分层；旧981候选不 promotion。price-only 正向通过不授权完整含基本面策略 |
| StrategyFeatureDecision | 批准隔离诊断输出 | 必需 Quality/行业/估值/费用等缺项仍 NOT_COMPUTABLE；Timing 通过不替代完整 family。不是原生 Signal/Approval/Order。任何价格消融另有 ID/spec/hash/假设，不能代替两冻结 family，未获明确 Owner 答复前不启动新增消融实验 |
| DatedExecutionEconomics | 批准显式费用桥与假设情景工程 | HALF_UP/分字符串/BigInt 与 HALF_EVEN/Python整数分别带版本；禁止隐式 float 或换名共用 profile。最低佣金订单聚合、partial fill、取消重下、日期有效区间、滑点包含关系和逐分 oracle 必须检验。实际费用仍 UNSET_REQUIRED |
| WalkForwardWindowPlan | 批准编排和阻断实现 | 保留 initial36m expanding + validation12m + sealed6m + step6m，purge/embargo 各40实际session；anchor、边界包含性、purge对象/embargo起点、跨窗持仓/现金、右删失及 exposure 规则待明确字段审查。未定义不得执行正式窗口 |
| AuditableSimulationRun | 批准隔离模拟结果 DTO | 准确区分 ENGINE_NOT_RUN、NOT_COMPUTABLE、NO_TRADES、DIAGNOSTIC_RESULT、FORMAL_PIT_RESULT；未运行收益为 NULL。逐订单/fill/现金/仓位/费用/NAV及拒绝、未退出、失败窗保留；完整交易数不是买卖边数或标签数 |

每个候选字段合同提交：版本、required/optional、enum、单位、钱的表示/rounding、timezone/precision、hash/trace、reason codes、失效条件和消费者测试。源时间与可见性证据不是互相替代的字段；source hash 不是 vendor revision。新 metadata 合同不得静默替换 native v1。

## 冻结策略与诊断范围

继续只读引用 `docs/wave-f/Frozen-StrategySpec-v1.json`，SHA-256 `d4eb866d6675e52f4b5158374f94a3152e4ae406c62add22a8c807762b0215da`；`CORE40_Q_PULLBACK_V1` 与 `CORE40_Q_BREAKOUT_V1` 不改阈值、不根据结果挑选。CORE_40 是策略 namespace，不表示扩到40只股票。EVENT_3、RESEARCH_6_18M、Forward 实际验证与历史诊断分别隔离。

已获专项 Owner 授权的诊断使用 `NON_PIT_DIAGNOSTIC / NOT_FORMAL_OOS / NON_TRADEABLE`，假设资金和费用必须说明为 counterfactual，不继承旧实验参数。完整 family 缺项明确 NOT_COMPUTABLE。已曝光样本保持 untouched_oos=false；实际 PIT 正确、价格模拟完整、真正未见 OOS 盈利证据分别验收。软件 Reviewer 不签发人类 PIT 或真实执行权限。新增消融和缺失业务参数仍由 Owner 决定，主控接口审查不代答。

## Forward 与真实市场链

Day0 预测、文字来源和 Freeze Receipt 保持原件；D1 journal 由主控现有签名验证入口追加，不给专项写权限。收盘时间已到不是 EOD 原件。公钥已登记、setup 验签成功不等于 CAPTURE、独立 REVIEW、单独 FORWARD 执行签名。今日 actual store / Snapshot B / D1 尚未提供完整实际链时，真实验证日仍0。D5/D10日期沿用冻结v1，D20/D40 UNSET；不因专项收益调预测，也不拿未来揭晓调历史策略。

## 交付与集成

专项提交固定 commit、精确改动清单、候选合同及 hashes、输入/代码/spec/scenario/policy版本、可重放命令、完整交易ledger/NAV/费用结果或具体阻断、所有失败与独立软件审查。主控在自己的新验收 worktree 对固定 commit 做差异、旧954文件与 Forward保全、合同兼容、正反例、逐分核账、重放及真实证据等级检查；不读取正在变动的工作区来宣称正式验收。

`integration_review` 的读取报告只辅助发现文件越界，不是权限沙箱、PIT issuer 或产品执行门禁。预期批准范围外的变更须先提交兼容方案；不自动 merge/rebase/push，不重封旧hash。通过代码与合同验收不等于 Owner 业务放行或 production 放行。
