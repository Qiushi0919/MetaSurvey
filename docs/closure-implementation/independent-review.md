# P1-A Conditional Closure — NEW Independent Reviewer W4

结论：**PASS，仅限批准的 fixture-only MANUAL_EXPORT / PAPER 范围**。本轮 22 项独立攻击全部阻断；发现的 1 项 P1 问题 F01 已由总控修复并复验，开放问题为 0。REAL_DATA_ADMISSION_GATE = BLOCKED，production = false；本结论不授权 P1-B。

审查对象：candidate HEAD `b9a4ed6283733ca0c6e55fbaf5e86dd948ceb356`；实际代码 commit `e22979d3b9d2938e24fe493c24c93f4716921cdc`；source tree `sha256:f74cb7c5b9409a66b1959cbc2d1c2087d990c221bb6828d556d6a321116673f5`，140 个实际 committed 文件逐字节验证。旧合同、旧 BrainPacket validator、001–005、历史 release、旧 provenance 与 legacy manifest 共 43 个冻结文件与历史 commit 原字节相同。旧测试唯一变化是 exact schemaVersion 5 → 6，没有放宽安全或经济断言。

审查依据为本轮用户 D01–D04 / W1–W4 授权、正式交接文档与冻结 W1。本 Reviewer 是本轮新建独立任务，只读业务实现和预期，不复用旧 Reviewer 的结论。所有攻击代码、日志与机器报告保存在外部审查目录；没有修改 legacy seal、ledger 或恢复 V5。

## F01 闭环

原实现仅在导出开始时验证一次。独立脚本真实 verify 成功后真实撤销 receipt，模拟两个 await 之间的状态变化；修复前仍写出 1 个文件并记 EXPORT_ACCEPTED。消费者和 importer 会拒绝该旧包，因此没有订单或消费者权限绕过，但导出接受记录不正确。旧失败日志保留为 pre-fix-revocation-race.log。

总控 commit e22979d 添加同进程、同 DB handle 的最终发布队列，publication、policy registration、receipt/policy revocation 共用锁，锁内使用原 facade 真实重验后发布和审计。consumer 没有 callback、DB 或 private signer。原攻击复验现在为 CLOSURE_RECEIPT_REVOKED、新文件 0、仅 EXPORT_REJECTED；新增 4 个专项测试全部通过，含历史文件保留、第二 facade 撤销及政策升级排序。该锁不宣称跨进程或 DB owner 权限隔离，也不回收已读 bytes。F01 = RESOLVED。

## 22 项独立攻击

每项均实际尝试，并由外部 attack-script.log 记录返回证据。A01 特别先让原 verifier 实际接受 OBSERVED 冻结，再证明 admission 拒绝；没有用代码 provenance 提前失败冒充数据 guard。A14 使用公开 fixture key 重新签名所有篡改对象后仍在 source-derived projection 边界拒绝。

| ID | 攻击 | 结果 | 原因 / 实测边界 |
|---|---|---|---|
| A01 | synthetic → OBSERVED relabel | PASS | CLOSURE_SYNTHETIC_SCOPE_ESCALATION |
| A02 | synthetic → REAL_RESEARCH escalation | PASS | CLOSURE_SYNTHETIC_SCOPE_ESCALATION, CLOSURE_PURPOSE_MISMATCH |
| A03 | quarantined export | PASS | CLOSURE_DATA_QUARANTINED |
| A04 | future-data export | PASS | CLOSURE_FUTURE_DATA |
| A05 | available_at spoof with coherent new hashes | PASS | CLOSURE_SOURCE_LINEAGE_INCOMPLETE |
| A06 | source byte mutation after admission | PASS | CLOSURE_SOURCE_LINEAGE_INCOMPLETE |
| A07 | receipt reuse across snapshot/version/code epoch | PASS | CLOSURE_RECEIPT_INVALIDATED, CLOSURE_RECEIPT_UNKNOWN, CLOSURE_POLICY_UNTRUSTED |
| A08 | receipt/policy revocation and old export reuse | PASS | CLOSURE_RECEIPT_REVOKED, CLOSURE_POLICY_REVOKED |
| A09 | receipt purpose mismatch | PASS | CLOSURE_PURPOSE_MISMATCH |
| A10 | coverage mismatch | PASS | CLOSURE_COVERAGE_INCOMPLETE |
| A11 | stale data and receipt expiry | PASS | CLOSURE_STALE_DATA, CLOSURE_RECEIPT_EXPIRED |
| A12 | namespace crossover | PASS | CLOSURE_NAMESPACE_MISMATCH |
| A13 | future MAE/MFE payload and metadata leakage | PASS | CLOSURE_OUTCOME_LEAKAGE |
| A14 | arbitrary all-signed payload injection | PASS | CLOSURE_HASH_MISMATCH, CLOSURE_IMPORT_INVALID |
| A15 | raw path leakage | PASS | CLOSURE_SECRET_OR_PATH_LEAKAGE |
| A16 | secret leakage | PASS | CLOSURE_SECRET_OR_PATH_LEAKAGE |
| A17 | LLM fake HUMAN approval | PASS | CLOSURE_LLM_EXECUTION_INJECTION, CLOSURE_IMPORT_INVALID |
| A18 | LLM OrderIntent injection | PASS | CLOSURE_LLM_EXECUTION_INJECTION, CLOSURE_IMPORT_INVALID |
| A19 | unknown real-cost/account suitability | PASS | CLOSURE_COST_REQUIRED_FIRST |
| A20 | Candidate before actual Cost Engine | PASS | COST_BEFORE_ACCOUNT_READ_AND_NON_EXECUTABLE_TRANSITION |
| A21 | productionGate bypass | PASS | CLOSURE_SYNTHETIC_SCOPE_ESCALATION, CLOSURE_IMPORT_INVALID, PRODUCTION_DISABLED_P0, UNSET_REQUIRED_CONFIG, SYNTHETIC_FIXTURE_ONLY |
| A22 | broker capability/DB/raw/credential discovery and actual native OS isolation | PASS | ACTUAL_NATIVE_OS_PERMISSION_DENIAL |

## 正向与回归证据

独立实际执行 Synthetic Source → Snapshot → admission → signed sanitized packet → manual file → native isolated simulated consumer → cost → NON_TRADEABLE Draft。两次完整 E2E 的 identity 与 replay hash 完全相同：`sha256:6165915a189c9222235027035d706360477455d0502aec9db85014029b575572`。最终 Draft.can_produce_order=false；真实账户适用性 BLOCKED、真实 net edge/sizing 及业务策略参数仍 UNSET_REQUIRED。实际 Cost Engine 的结果与独立 estimateCost 计算相等；IMPORT_COST_ESTIMATED 审计事件先于实际 AccountProfile 属性读取，缺费用时账户读取次数为 0；该证据来自真实调用与读取顺序，不以 phase_order 常量自证。

真实 native sandbox 在相同 profile、移除 Node permission 后仍阻断 6 个 raw/DB/credential/broker/repo canary 文件、监听中的本地网络、shell 与 Node 子进程、artifact 写。child 环境仅 TZ，没有 regular-file descriptor、DB 或 broker global。所有执行表计数前后不变；parent E2E 明确覆盖全部 7 张 p1a_paper 表及共 22 张相关表。没有读真实 credentials。

空库 migration 与幂等再次 migrate 达 schema6；006 仅 policies/receipts/revocations/audit，append-only、现存行删除与 TRUNCATE 拒绝。Unsupported platform 分支在进入 verifier 前 fail-closed；这是分支模拟加源码验证，不冒充 Linux native positive 测试。

最终 fresh clean checkout b9a4ed6、独立空 cache 安装、正确 e22979d / f74 provenance 的完整检查：**258 tests，257 PASS，0 FAIL，1 optional external legacy SKIP**。确认 reviewer-fixed-check.log 的 release/provenance/30 UNSET 检查与上述最终计数；pre-fix 的 254 测试日志未充当最终证据。

## 保留边界

- All conclusions apply only to approved synthetic fixture MANUAL_EXPORT/PAPER scope. All real sources remain BLOCKED; no real source authority/license/clock was fabricated.
- Positive OS isolation was actually tested on macOS. Unsupported platform fail-closed was verified by platform-branch emulation and code; no claim of native Linux positive isolation.
- Publication/revocation ordering is single process and same DB handle. Multi-process/server RBAC/DB-owner access and revocation of already-read bytes require future topology-specific Gate.
- The public known synthetic signing seed authenticates fixture integrity only; approved policy hashes, stored receipts and exact data projection are also required. It is not production issuer authentication.
- No actual model/Research Agent/AI selection/EVENT strategy/GUI/real credential/real account/broker call/production execution/V5 restoration was introduced or exercised. P1-B still requires explicit APPROVE_P1B.

机器明细及 SHA256 在 independent-review.json；实际攻击命令、日志与 F01 修复前后证据均保留。此 PASS 只证明已批准工程范围的闭环，完成本轮 Gate 后停止等待用户 APPROVE_P1B。
