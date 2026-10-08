# P1B-SOURCE-PREPARATION W1 Freeze

冻结工程边界；所有真实source/字段/历史重构/范围决定仍PROPOSAL_FOR_OWNER_REVIEW。依据docs/authorizations/P1B-next-step-20261005.md中的最新repo分支，默认推进真实股票数据准入准备；不重新实施旧P1B0，不自动运行模型/荐股。

Goal: 可审查来源、许可/PIT/coverage差距、两条拟slice路线及新四时钟proposal；保留35项逐项现状对照。
Context: 最新1fffea9为有限calendar-only PASS_WITH_CONDITIONS；实际stock/historical/cloud=BLOCKED，30真实账户字段UNSET_REQUIRED。
Inputs: 正式交接、旧Gate与条件、旧machine inventory、新公开官方文档capture/hash；不读credentials/账户状态，不跑旧collector。
Outputs: ClockEvidenceProposal1.0/StockSliceProposal1.0 schema和proposal fixture、源比较/requirements/35项对照、仅结构的验证入口tools/admission-preparation/check-proposals.mjs、新独立只读review、Git/archive证据。
Interfaces: documents/proposal validation only；没有source fetcher runtime、ADMITTED receipt、model consumer、Candidate/Signal/Approval/Order API。
Constraints: 旧P0/P1A/Closure/P1B code/contract/migrations/tag/report全字节保留；仅新docs/admission-preparation、contracts/admission-preparation、tools/admission-preparation及authorizations，以及AGENTS/README/source-of-truth当前导航；共享协议与状态由父总控管理；不改SABCX/HardBlock/Approval/production；不购买/联系供应商/接token，不升级真实source。
Tests: 实际新schema编译，UNKNOWN/date-only/null与offset clock形状；伪ADMITTED/pilot/production/extra payload拒绝；所有旧source pin/index在历史tag/currentimmutable路径校验；逐条证据原件/hash一致。新schema shape tests不冒充真实PIT/许可验收。
Definition of Done: 能明确看到至少一个可决定的source-route方案、全部必要原证据和未决字段；无source升格；owner应审新clock/范围/授权后才建实际adapter，真实Research Pilot仍需单独APPROVE_P1B_RESEARCH_PILOT。

Owned paths: 父总控新contracts、proposal、仅结构验证入口、Freeze、requirements、35-item audit、preconditions、Git/index/archive及当前导航；RD仅写docs/admission-preparation/provider-evidence.json和Source-Comparison.md两份文档，不实现业务或修改Git；新Independent Reviewer只写独立外部review，不改代码/合同/expected/Gate。

Trigger来自本次人类指令：source BLOCKED→ADMITTED、填真实UNSET、改变等级/审批/production、扩大MANUAL_EXPORT均需用户决定。当前不会触发任何升级。Owner review是下一步实际source/clock implementation前置；本轮只完成可供审查的准备资产。
