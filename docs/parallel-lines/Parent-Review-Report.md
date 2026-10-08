# MetaSurvey 双线并行接口审查与 Forward 状态报告

2026-10-08，Asia/Shanghai。**专项受限工程实施继续；主控已审查六类接口语义并有条件批准 sidecar 边界。具体字段合同与专项最终代码尚未验收，尚未合并。** 主控继续负责 Forward 和实际市场数据链。冻结预测未改，真实首日验证仍0。

## 版本与工作区

- 主控：`/Users/qiushi/投资研究/ashare-trading-v1`，分支 `forward/parallel-review-20261008`，工程候选 `55401054af42b20a36fb190febcf88800287657a`，基线 `0ea206a834cf4f68a94b536b26377d390f02ec18`。
- 专项：`/Users/qiushi/投资研究/ashare-backtest-5y`，分支 `backtest/5y-initial-review-20261008`。正在实施；本报告没有在其工作区写文件、切换分支、提交或重置。
- 主控新增 `integration_review/` 和 `docs/parallel-lines/`。专项获准新目录 `backtest_5y/`、`contracts/backtest-5y/`、`docs/backtest-5y/`、`tests/backtest-5y/`。954旧文件、16native合同、Schema6、迁移001–006、依赖锁、legacy及原冻结策略保持原样。没有新ADR/迁移编号。

## 已完成的接口审查

完整决定见 [Interface-Review.md](/Users/qiushi/投资研究/ashare-trading-v1/docs/parallel-lines/Interface-Review.md)；机器可读决定为 [Interface-Decision-v1.json](/Users/qiushi/投资研究/ashare-trading-v1/docs/parallel-lines/Interface-Decision-v1.json)，版本1.0.0。

HistoricalEvidenceBundle、AdmittedHistoricalSnapshot、StrategyFeatureDecision、DatedExecutionEconomics、WalkForwardWindowPlan、AuditableSimulationRun 的语义方向已批准用于受限sidecar实现。它们尚未提交完整字段Schema，不把概念表或代码注释当成已冻结跨模块字段合同。

原 Frozen StrategySpec SHA-256 `d4eb866d6675e52f4b5158374f94a3152e4ae406c62add22a8c807762b0215da` 及两family不改。已只读查看专项刚建立的接口/protocol/所有权草案，归档当时的公开代码快照；已向专项反馈三项要求：四时钟和精度/version/reason/invalidation；正式窗口anchor与1260有效warmup的实际session验证；增量raw/record版本保留及“缺数据”和“缺方法”的区分。

专项Owner补充已明确优先完整策略数据与持续维护，当前价格消融为false。主控没有代替Owner批准新消融、WACC/周期盈利/校准方法、真实费用或风险参数。2016采集buffer与2021样本日期只作工程范围，不能默定为正式Walk-forward起点。HALF_UP和HALF_EVEN仍需带版本的显式费用桥、逐分oracle和消费者反例；原生审批/订单不会因诊断DTO产生。

## Forward 与实际市场链的本轮推进

重新打开冻结包31payload、预测/来源/receipt和既有schema原件，Day0完整性PASS；重新核验两人的公开setup签名，PASS_SETUP_ONLY。已登记公钥继续有效，无需重新生成密钥。本轮未读取凭证或私钥，也没有要求Token/密码。

当前D1 journal仍0字节、尚无结果；已注册的 `/Users/qiushi/投资研究/.p1b-archives/wave-h-20261007/capture/actual` 目录不存在。本轮指定archives文件名清单未发现实际store/实际capture；未声称电脑其他未登记路径不存在材料。完整实际链尚未取得，Snapshot B未运行，真实Forward天数0。

**墙上时间已过今日收盘，仍不能替代当日实际开市/EOD原件及签名链。** 剩余顺序：实际当日原件 → Owner签CAPTURE → 有限只读采集 → 独立Reviewer复核并签REVIEW → Snapshot B及store head → Owner另签FORWARD → actual append → D1研究揭晓。三个主题分别绑定，setup签名或聊天中的“继续”不能伪装成这些密码学授权。既有 [One-Shot-Activation-Runbook.md](/Users/qiushi/投资研究/ashare-trading-v1/docs/wave-h/One-Shot-Activation-Runbook.md) 描述该合同要求；不放宽既有执行门禁。

D5/D10沿用冻结v1目标日期10月14日/10月21日，D20/D40仍UNSET。本轮没有启用自动任务或新增下一日采集。没有实际市场请求、credential/private-key读取、store mutation、原生订单或真实资金执行。

## 验证与限制

35个去重用例通过：新边界反例11、既有Day1回归24，0FAIL/0SKIP；并行保全在读取时核对两边各954原文件和4份Forward保护文件，全部PASS，不加进测试数。专项当时5个新增文件全部位于批准根目录。后续正在生成的文件须交付时重新核对，这不是实时锁或操作系统权限沙箱。

测试覆盖改字节、缺文件、文件/目录symlink、路径越界、提交/暂存/工作区/非ignored新文件及不相干Git历史；原Forward回归覆盖未来时钟、缺签名/模拟链、重复/stale head、截断与篡改journal等。实际正向签名链NOT_RUN，整项目历史大套件未本轮重跑；原有失败、旧封存日志和参数不改。本轮为主控软件审查，不冒充独立人类PIT审核或尚未完成的专项Independent Reviewer。

## 最终集成安排与当前阻断

主控已把两批具体审查反馈发到专项对话。专项提交固定commit、完整字段候选、重放入口、逐笔ledger/NAV/费用或精确阻断、失败索引和独立软件报告后，主控再建立单独验收checkout审查，不自动merge/rebase或侵入正在施工的worktree。

当前正式历史PIT仍沿用基线60行/闭环0；实际账户30原字段+15补充字段、研究方法政策UNSET，供应方/许可/传输及历史可见性仍未证明。完整策略缺项继续NOT_COMPUTABLE，未运行收益必须NULL；已曝光数据不恢复untouched OOS。正式历史OOS、真实资金、券商、production和cloud继续BLOCKED。

本轮工程接口审查已交付，专项继续其已获Owner授权的施工。**未取得实际证据与独立执行签名时，不生成虚假Snapshot B或Forward结果。**
