我已审阅：

1. P1-A PASS_WITH_CONDITIONS 条件闭环 GAP Analysis
2. P1-A Conditional Closure Plan

我批准本轮 Closure Plan。

批准状态：

D01 = APPROVED
D02 = APPROVED
D03 = APPROVED
D04 = APPROVED

具体解释如下。

D01：
批准 fixture-only MANUAL_EXPORT / PAPER 范围完成
P1B_READINESS_GATE。

当前不要求真实 market/security/financial/corporate-action
source 成为 ADMITTED。

所有真实 source 继续保持 BLOCKED，
不得为了进入 P1-B 而伪造 license、available_at、
coverage 或 authority。

D02：
批准新建：

BrainPacket 1.1
AdmissionReceipt 1.0
SourceAdmissionPolicy 1.0
ResearchDraft 1.0

旧 BrainPacket 1.0、V1 contracts、
P1-A schemas 和历史 hash 全部保持原字节。

禁止通过修改旧 BrainPacket validator
来兼容 P1-A closure。

D03：
批准 MANUAL_EXPORT 文件边界。

Research consumer：

不得直接访问 raw store
不得直接访问 DB
不得获得 DB credentials
不得获得 broker credentials
不得获得 broker capability
不得获得内部 raw paths

只允许读取经过：

VERIFIED
+
ADMITTED
+
purpose-bound

的 sanitized export artifact。

006 migration 仅允许在确有必要时保存：

policy
receipt
revocation
export/import audit

不得借 006 扩张成新的业务数据库重构。

D04：
批准 GAP 中当前建议的延期分类。

C12-C22：
允许按 P1-B 实际消费的数据和用途逐步完成。

C23-C31：
允许延期到 P2；
如果未来拓扑或用途扩大导致其成为安全前置，
必须重新升级 Gate。

C32-C39：
继续作为 PROD_ONLY_BLOCKER。

C40-C47：
接受为当前明确范围下的 KNOWN_LIMITATION，
但不构成永久豁免。

==================================================
现在正式开始：
P1-A CONDITIONAL CLOSURE IMPLEMENTATION
==================================================

只允许执行 W1 → W4。

W1：
总控冻结本轮：

- 新合同字段
- hash protocol
- reason codes
- Admission policy semantics
- migration 006 exact scope
- release/version plan
- Agent owned paths

W1 完成后才允许子 agent 写实现。

W2：
启动 Agent DA：

Data Admission Closure

重点关闭：

C01
C02
C03
C04
C05
C06
C09

尤其必须证明：

SYNTHETIC
不能通过 relabel / caller assertion
晋升为 OBSERVED / REAL_RESEARCH。

QUARANTINED
UNKNOWN_LICENSE
UNVERIFIED_TERMS
future-invalid
stale
coverage-incomplete
source-lineage-incomplete

全部不得导出到 Research consumer。

W3：
启动 Agent PH：

Minimal Platform / Non-executable Research Import

只处理：

C07
C08

以及 C01 所需的最小运行隔离。

必须证明：

Cost Engine
先于 Candidate suitability/admission。

真实费用/account仍UNSET时：

不得产生：

REAL_ACCOUNT_SUITABLE
REAL_NET_EDGE
REAL_SIZING
TRADEABLE

之类结论。

ResearchDraft 必须：

can_produce_order = false

LLM 返回：

BUY
APPROVE
HUMAN_USER
OrderIntent

都不能写：

Approval
OrderIntent
Order
Fill

并且不能触发任何 broker transport。

W2 / W3 可以在 W1 接口冻结后有限并行。

==================================================
MANUAL_EXPORT E2E
==================================================

本轮必须建立一条完整 fixture-only E2E：

Synthetic Source
→ DataEnvelope
→ SnapshotManifest
→ verifyDataSnapshot
→ SourceAdmissionPolicy
→ AdmissionReceipt
→ sanitized BrainPacket 1.1
→ MANUAL_EXPORT file
→ simulated external research result
→ ResearchDraft import
→ validation
→ NON_TRADEABLE draft

整个链路必须可确定性重放。

必须证明：

ResearchDraft
不能直接变成：

Candidate tradeable
Signal
Approval
OrderIntent
Fill

==================================================
P1B_READINESS_GATE
==================================================

完成实现后，
重新验证 R01-R12。

只有：

R01 PASS
R02 PASS
R03 PASS
R04 PASS
R05 PASS
R06 PASS
R07 PASS
R08 PASS
R09 PASS
R10 PASS
R11 PASS
R12 PASS

才能将：

P1B_READINESS_GATE = PASS

任何一项失败：

P1B_READINESS_GATE = FAIL

==================================================
Independent Reviewer
==================================================

W4 必须重新启动新的 Independent Reviewer。

不能复用旧 P1-A Reviewer 的结论替代本轮审查。

Reviewer 必须重点攻击：

synthetic → observed relabel
synthetic → real_research scope escalation
quarantined export
future-data export
available_at spoof
source byte mutation
receipt reuse
receipt revocation
receipt purpose mismatch
coverage mismatch
stale data
namespace crossover
future MAE/MFE outcome leakage
arbitrary payload injection
raw path leakage
secret leakage
LLM fake HUMAN approval
LLM OrderIntent injection
unknown real cost suitability
Candidate-before-Cost
productionGate bypass
broker capability discovery/access

Reviewer 只读，
不得修改业务实现或测试预期。

==================================================
Golden Regression
==================================================

现有 P0/P1-A Golden 不变量必须全部保持。

尤其：

PIT
T+1
raw/adjusted isolation
financial revision PIT
corporate-action visibility
cash ordering
BigInt reconciliation
cost attribution
partial fill
strategy namespace
duplicate order
restart idempotency
Snapshot lineage
source-byte invalidation
UNSET_REQUIRED
LLM != HUMAN_USER
PROD rejection
Micro-Ladder rejection

任何安全不变量回退：

Closure Gate = FAIL

==================================================
继续禁止
==================================================

本轮仍然禁止：

- 调用 ChatGPT / Deep Research 做真实研究
- 创建真正 Research Agent
- AI选股
- S/A/B/C/X 参数优化
- Quality/Timing 校准
- 概率模型
- 真实 Edge 参数
- 真实 sizing
- EVENT_3
- GUI 主体开发
- broker adapter
- 真实账户
- 真实 credentials
- 自动下单
- productionGate=true
- V5 恢复
- 修改旧 seal / ledger

==================================================
Closure Gate
==================================================

W4 完成后提交：

P1-A Conditional Closure Gate Review

必须包含计划要求的25项，
并额外给出：

P1B_READINESS_GATE = PASS / FAIL

以及：

REAL_DATA_ADMISSION_GATE = BLOCKED

除非本轮另外获得真实source许可和时钟证据，
否则 REAL_DATA_ADMISSION_GATE 必须继续 BLOCKED。

Closure Gate 的结论只能：

PASS
PASS_WITH_CONDITIONS
FAIL

完成后停止。

即使：

P1B_READINESS_GATE = PASS

也不得自动进入 P1-B。

等待我明确发送：

APPROVE_P1B