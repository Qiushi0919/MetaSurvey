# Fixture Research Chain 1.0 — bounded integration notes

状态：组合测试 14 PASS / 0 FAIL / 0 SKIP。仅 `SYNTHETIC_TEST_ONLY` / `CORE_40`；真实 Research Pilot、真实评级和执行均未授权。整体 Gate 与独立审查由总控发布。

## Goal / Context / Inputs / Outputs

Goal：闭合真实运行的 fixture `BrainPacket → ResearchDraft → ResearchAssessment → ResearchCard1.0 compatible sidecar`，保留严格版本、hash、trace 和失效链。

Context：旧 Closure round trip 与 P1-B pure semantics 原先分别成立，缺少完整组合。当前阶段只组合其原有实现，不更改原合同或业务规则。

Inputs：冻结的 `buildClosureFixture`、`buildBrainPacket`、`writeManualExport`、`runIsolatedConsumer`、`importResearchResult`、`assessSemantics`，原 ResearchCard1.0 validator，总控 `FixtureResearchChain1.0` schema，以及四个明确手写的合成 case。

Outputs：`real-slice/src/fixture-chain.mjs`、fixture replay 入口、14 个组合回归测试、小型 `cases.json`、本说明。原合同、代码、费用假设、migration、legacy 文件均未修改。

## Interfaces / Constraints

`runFixtureChain({directory, fixture_case='BASE'})` 返回实际 packet/draft/assessment/card/sidecar、来源 refs、输入 hash、replay hash、原生隔离探针和执行表计数。只接受固定 `BASE` / `UPSTREAM_REVISION` / `TIMING_GAP` / `HARD_BLOCK` case。

`verifyFixtureChain(chain, {packet,draft,assessment,card,use_at})` 验证严格 schema、原生对象 validators、私有已签发对象的原始内容、refs、当前版本和 TTL。`use_at` 默认明确的合成 cutoff，绝不声称当前真实时点有效。

`compareFixtureChains(previous,next)` 返回变化的 refs、应失效的旧 card ref 和未变化的 refs。`invalidateFixtureChain(chain,{reason})` 仅允许 `RECEIPT_REVOKED` / `POLICY_REVOKED` / `CARD_SUPERSEDED`，不可逆地收窄 fixture 权限，没有恢复或放行接口。

约束：原生 consumer 仍使用 macOS deny-default sandbox 和 Node permission。实际文件写入仅为脱敏 fixture export / 本地回归输出；没有模型调用、真实股票数据输入、账户 secret、Signal / Approval / Order 生产器、券商能力或业务参数优化。

## 证据与语义的边界

合成 bar 原始字节经过冻结的 source→snapshot→receipt→packet 路径，再实际经过隔离 consumer 和 `importResearchResult`。旧导入器仍先调用真实实现的合成 Cost Engine，再形成非执行 draft。执行表前后计数一致。

`assessSemantics` 只接受其固定的 illustrative evidence coordinate；本模块按原接口原样调用，没有把真实 bar refs 冒充该 coordinate，也没有复制评级算法。sidecar 同时记录真实运行产生的合成 `source_evidence_refs` 和单独的 `semantics_input_hash`。十维 PASS/GAP 是手写测试坐标，不是从 bar 推导出的公司质量、真实账户适配或收益估计。

兼容 card 的 `account_id='SYNTHETIC_FIXTURE:NON_ACCOUNT'`、`symbol='SYNTHETIC:NON_SECURITY_FIXTURE'` 均是明确非身份。原 ResearchCard1.0 字符串字段允许这些 sentinel，原严格 validator 实际通过。card 的 native `grade` 保持 `UNSET_REQUIRED`，price=null，所有 scores、net edge、probability、sizing、fee suitability 均未知/阻断。必填的 20–40 session / 6–18 month 字段仅验证合同结构，不是生产参数。

合成 all-PASS assessment 的 S 最大动作为 `REQUEST_REVIEW`；native card 不继承 S，不生成 Signal，也不等于任何人类 Approval。

## 版本与失效

sidecar 将 packet、draft、assessment、card、snapshot、receipt 的 exact id/version/hash 一并绑定，统一 trace 由上游 fingerprint 生成。原 Draft 合同没有 trace 字段，侧车负责组合 trace，没有修改旧合同。

相同当前 fingerprint 的两次真实 fixture 运行生成完全相同的 packet/draft/assessment/card/sidecar 和 replay hash。合成 bar `10.00 → 10.25` 在真实冻结 producer 中重建源字节、snapshot、receipt、packet 和 draft；即使 assessment 的独立 illustrative 输入未变化，新 card/chain version 也递增，旧 card 不能继续验证。Quality=HIGH 且 Timing=GAP 的 A/WATCH 和 HardBlock 的 X/BLOCKED 都来自冻结语义函数。

失效实现不修改已经交付的对象或账本。模块私有 registry / current head 记录 supersession、exact receipt/policy revocation 和 TTL。调用者重新计算 hash、伪造 refs、替换原始对象或重跑相同已撤销来源均不能恢复 authority。

这些 registry 只是当前进程的 DEV fixture composition authority。旧数据 DB 在每次执行后关闭；本 verifier 不声称可以在 DB 关闭后认证真实 receipt 的当前许可，也不从归档证明重启后的真实数据权限。重启后的既有 chain 未注册，会 fail-closed。

独立审查实际发现初版 verifier 使用毫秒 `Date.parse` 作比较，TTL+1ns 会被截断后误接受；原始失败记录由总控保留。当前修复先验证 ISO、真实日历日期和时间分量，再调用冻结的 `timestampNs`，以 BigInt 纳秒比较 cutoff/TTL。`Date.parse` 只用于验证日历而不用于边界比较。精确 cutoff/TTL 和等价时区通过，cutoff−1ns / TTL+1ns 拒绝；`2026-09-31`、`2026-02-30`、24:00 和超过九位小数拒绝，无法依赖 JavaScript 日期归一化进入有效窗口。没有改变业务规则、合同或原 nanosecond helper。

## Tests / Definition of Done

实际执行：`node --test --test-concurrency=1 real-slice/tests/fixture-chain.test.mjs`，修复后 14 PASS / 0 FAIL / 0 SKIP（13.40秒）。覆盖实际 OS 隔离与无执行写入、两次确定性回放、原 ResearchCard validator、S 最大 REQUEST_REVIEW、每一种上游 ref / caller reseal 攻击、source/namespace/grade/production 升权、精确纳秒时钟/TTL、非法日期归一化、合成上游替换、Quality≠Timing、HardBlock 优先、receipt/policy 不可逆撤销。

回放入口：`node real-slice/scripts/fixture-chain.mjs [外部本地证据目录]`，实际执行两次 BASE，并生成小型 `fixture-chain-results.json`。未指定目录时使用临时目录。代码 source pin、最终归档和整体 Gate 由总控处理。

DoD：fixture 全链真实运行、严格验证、同输入两次结果一致，上游变化使旧 card 失效；所有真实身份/费用/评级/Edge/概率/sizing 保持未决，零模型/执行/券商调用。该 fixture 链缺口已闭合，真实研究生产链仍未建立。
