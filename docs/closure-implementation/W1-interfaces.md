# W1 冻结：fixture-only MANUAL_EXPORT / PAPER

授权：docs/authorizations/P1A-closure-implementation-20261005.md，D01–D04 APPROVED。正式交接文档仍为主要 Source of Truth；历史 pending 文档原样保留。P1B、真实 source、模型调用及 production 未授权。

## 合同及协议

BrainPacket 1.1.0、AdmissionReceipt 1.0.0、SourceAdmissionPolicy 1.0.0、ResearchDraft 1.0.0 exact required/enum 字段由 contracts/closure 定义；closure reasons 独立。旧 schema/validator/001–005/releases/old code proof 原字节。

content_hash 使用 canonical/hashValue，排除顶层 content_hash/proof；ED25519 对 UTF8 content_hash 签名。parent constructor 信任 DER SPKI，而非 caller 公钥。projection_hash=hashValue({snapshot_ref,data_hash,decision_cutoff,feature_version,rules_hash,evidence})。原 P1A data_hash 仍绑定 root/closure/version/cutoff/rules；closure_hash=hashValue(closure_refs)。三类 hash 不互换。

Policy 为 parent 批准 hash 白名单，source_id/version/hash/class/license/terms/allowed_use/raw_hashes 全绑定。所有 closure 对象/manifest/bundle SYNTHETIC；OBSERVED/RECONSTRUCTED/REAL_RESEARCH 升格拒绝。原字节验证时钟；freshness 显式 per-kind 秒，相对 use time，没有默认。coverage 精确 symbols/exchanges/date interval/kinds，消耗均覆盖且声明由闭包兑现。policy/receipt 有效期半开 [from,until)。更新不自动继承旧 receipt。每次 export/import/consumer use 重验原数据、PIT、闭包、撤销。冻结不等于永久有效。

006 exact 范围：p1a_closure 四张 append-only 表 policies/receipts/revocations/audit；没有业务 Draft/Candidate/Order/Fill 表。审计只有严格 refs/reasons/顺序和链 hash，不存不可信 payload/path/secret。同一 DB 进程内串行；多服务并发拓扑未授权。

## Parent owned shared API

contracts.mjs: closureHash/sealClosure/closureRef/projectionHash/validateClosure/assertSanitized/createFixtureAuthority/verifyClosureSignature。测试私有 authority 永不导出给 consumer。
store.mjs: savePolicy/readPolicy/saveReceipt/readReceipt/assertNotRevoked/revoke/closureAudit。
fixture.mjs: parent 提供显式 synthetic factory；policy 来自原 closure source registry/字节；real account 加载原 UNSET_REQUIRED；fixture cost 独立。

## DA owned API

createAdmissionService({db,authority,approvedPolicyHashes}) 返回 trusted facade，不暴露 db/private authority：
- registerPolicy(policy)：验签/白名单/synthetic 后保存。
- admit({snapshot,policy_ref,strategy_id,purpose,now,expires_at})：signed/stored AdmissionReceipt。
- verifyReceipt({receipt,snapshot,purpose,strategy_id,now})：重验原 closure/policy/source/cutoff/freshness/coverage/签名/撤销。
- verifyPacket({packet,snapshot,purpose,strategy_id,now})：重验 receipt，比较原 snapshot 重新生成的 projection，不能只检查 self hash。
- revokeReceipt/revokePolicy({hash,now,reason_code})；audit({chain_id,event_type,event_time,refs,reason_codes})；trustPublicKeyDer() 返回公钥 copy。
- 为 buildBrainPacket 提供 signPacket(body) capability，仅能对重新验证的 approved projection 签名，不能暴露通用 signer。

buildBrainPacket({service,snapshot,receipt,now}) 返回 signed BrainPacket；FIXTURE_BAR_ENVELOPE_V1 仅 BAR root，严格 payload 白名单；任意 extra/MAE/MFE/future outcome/path/secret 拒绝。保留时钟/source/hash/lineage refs，raw_uri 仅 sha256-object:。writeManualExport({service,packet,snapshot,directory,now}) → {path,byte_hash,packet_ref}，验证后 canonical JSON 原子写文件，失败无拒绝数据落盘。

公共接口变化先报 parent。允许内部 helper，但只能在 owned paths，不能扩展权限。

## PH owned API

importResearchResult({service,packet,snapshot,result,realAccountProfile,costProfile,tradeTerms,now}) → {draft,cost_estimate,phase_order}。result 严格 shape {packet_ref,receipt_ref,strategy_id,purpose,observations:[{evidence_ref,statement,classification:'DESCRIPTIVE_ONLY'}]}；extra fields/BUY/APPROVE/HUMAN_USER/OrderIntent/真实适用性/未来 outcome/path/secret 拒绝。evidence_ref 必须属于 packet。verifyPacket 先于导入。

tradeTerms 显式 fixture {side,price,quantity,trade_date}；实际调用 Cost Engine estimateCost(PAPER) 后才评估 suitability。缺 costProfile 拒绝 COST_REQUIRED_FIRST；caller cost_ref 不能替代调用。cost_test=SYNTHETIC_TEST_ONLY；realAccountProfile 自报 VERIFIED 不能扩大 scope。Draft can_produce_order=false、tradeable=false、real_account_suitability=BLOCKED，real_net_edge/real_sizing/grade/scoring/probability/sizing/edge_policy_version=UNSET_REQUIRED。phase_order 可审计。assertDraftTransition(draft,targetKind) 对 CandidateTradeable/Signal/Approval/OrderIntent/Order/Fill 全拒绝。

runIsolatedConsumer({service,packet,snapshot,export_path,now,...probeOptions})：parent 子进程前后 verifyPacket；consumer 只拿 artifact + 信任公钥 + 有限 bootstrap。无 DB/raw/secret/broker。macOS 实际 sandbox-exec deny-default，只读 Node/OS 必要运行依赖及专属 staging；禁止 network/process spawn。无隔离器报 ISOLATION_UNAVAILABLE，不回退普通进程。Linux 验 fail-closed，macOS clean 验实际正向+文件/DB/raw/network/exec probes。probe 不能给任意目录授予访问权限。

## Agent task contracts

DA — Goal: C01–C06/C09 准入导出。Context: D01–D04/W1。Inputs: shared/new schema、src/data、fixtures。Outputs: admission/export、tests/data.md。Interfaces: DA API。Constraints: W1 owned paths only，不改共享/旧 validator/费用/账本/业务规则，不接真实源。Tests: 正向及 relabel两种/license/terms/quarantine/future/raw/receipt version-purpose-revoke-expiry/coverage/stale/lineage/namespace/payload/path/secret。Definition of Done: intended boundary 拒绝，拒绝 bytes 不落 artifact，持久化/签名可追踪；自己的 commit，parent 合并。

PH — Goal: C07/C08+C01隔离。Context: W1/D01–D04。Inputs: facade、新 contracts、Cost Engine、UNSET profile。Outputs: import/consumer/isolation、tests/platform.md。Interfaces: PH API。Constraints: owned paths only，零 model/broker/production，consumer 无 repo/DB/raw/credentials。Tests: cost顺序/未知真实费用/LLM approval-order/Draft transition/actual OS isolation/mutation/unsupported fail-closed。Definition of Done: 隔离和非交易往返实测，execution writes=0，独立 commit。

W4 NEW Independent Reviewer — Goal: 攻击 closure candidate。Context: 本轮授权/W1/新candidate。Inputs: contracts/migrations/tests/artifacts。Outputs: 外部只读报告、22攻击证据。Interfaces: parent candidate pin。Constraints: 不改实现/规则/预期、不复用旧结论。Tests: 用户22项逐一实测或注明证明。Definition of Done: findings 或 scoped PASS；parent 修复后复验。

## Release

closure 1.2.0 + separate active provenance 覆盖全部新 src/scripts/tests/schema/fixture/006；原 releases/config/p1a proof 作历史 commit 验证。W4 实际新 commit pin + clean install/replay；不可用旧 pin 隐藏新代码。25项 Gate 后停止等待 APPROVE_P1B。
