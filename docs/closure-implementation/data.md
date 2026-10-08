# W2 Data Admission Closure

DA 在 W1 `299313cdbca17a308a1e6a2bd1fcfd52d8e69c6e` 冻结后实施，仅修改 admission/export、对应测试和本说明。新合同、006、共享 sanitizer、release 与实际 code proof 由总控维护。本模块不访问真实 source，也不声明真实来源 ADMITTED。

## 输入与信任

`createAdmissionService({db,authority,approvedPolicyHashes})` 仅在可信 parent 构造。批准 hash 集合、公钥与 issuer 被复制，返回冻结 facade；不返回 DB、private signer、raw objects、broker 或 credentials。SourceAdmissionPolicy 不含 proof，采用 constructor 批准 hash、issuer、公钥身份及 canonical body 校验。AdmissionReceipt 和 BrainPacket 使用 ED25519，consumer 的公钥来自可信 parent，不能从 packet 自报信任。

fixture authority 的确定性种子是公开的 synthetic test material，不能用于生产身份认证。即便持有该测试 signer，伪造 packet 仍必须通过已存 receipt/policy、实时撤销及原 snapshot 的 projection 重建；测试明确验证“全部签名正确但新造 evidence”仍拒绝。

真实 source、OBSERVED/RECONSTRUCTED manifest、REAL_RESEARCH purpose、PROD 及生产开关全部拒绝。沿用旧数据 validator 原字节，并在新 admission 边界增加约束；测试保留旧 validator 接受 synthetic → OBSERVED/RECONSTRUCTED 的原反例，再证明新边界拒绝。

## 校验与失效

每次 admit、receipt verify、packet verify、export 均重验原 DB 对象、original raw bytes、PIT clocks、原 closure、DQ、source/source-version/source-hash/raw-hash/terms/license/allowed use。source observation 的 fixture event_time 必须等于字节证明的 SECOND published_at，避免 caller 刷新旧证据年龄。所有 freshness 秒数由显式 fixture policy 给出；每个实际消费 kind 都必须有值，按声明的 fixture use time 检查，无生产默认。

coverage 精确绑定实际 roots 的 symbols/exchanges/date interval 和闭包 kinds；对应 calendar 每个 TRADING day 都必须有 root bar，声明不能扩成未提供的股票、日期或 kind。source 原 fact 也按其直接 normalized child kind 严格白名单，允许明确 SYNTHETIC 的 fixture_kind；即使 `next_day_price` 无关键词、normalizer 已丢弃该 extra，也拒绝其原 fact。已公布 calendar 的未来日期按 calendar 语义保留，没有用日期字符串作泛化 future 拒绝。

receipt 绑定 policy、snapshot、root/closure refs、三类独立 hash、cutoff、feature/rules、purpose、namespace、版本与半开有效期。旧 receipt 不因 policy 新版本自动继承；新代码/schema epoch 的 service 不自动批准旧 policy hash。policy/receipt revocation append-only，不改旧 seal。跨 namespace 或 snapshot 重用拒绝；同一合法 packet 的重复文件导出允许 exact bytes 幂等，而不是重复交易授权。

## 唯一投影与文件

`signPacket({snapshot,receipt,now,body?})` 是总控批准的上下文细化：内部复验并重建唯一 approved body；caller body 若存在须 canonical exact equal。不能签任意 payload。`buildBrainPacket({service,snapshot,receipt,now})` 包装该能力。

FIXTURE_BAR_ENVELOPE_V1 仅导出 BAR roots 的严格字段白名单及 DataEnvelope 的四时钟/source/hash/lineage refs。raw_uri 转成 `sha256-object:` opaque address；不导出原 source fact、DB/raw 路径、账户标识、secret、future MAE/MFE/outcome metadata 或任意 extra。DataEnvelope original bytes 与新投影 hash 的语义明确区分；旧 BrainPacket 1.0 validator 不变。

`writeManualExport({service,packet,snapshot,directory,now})` 在写文件前验证并复制请求数据，使用 canonical JSON、0600 临时文件及原子 rename。拒绝时不落 packet bytes，audit 仅记允许的 reasons，无不可信 refs/payload。existing target 及最末 output directory 的 symlink 拒绝，existing bytes 使用 O_NOFOLLOW 读取并 exact 比对。directory 是 trusted parent 提供的路径；祖先目录或同机其他进程的恶意替换不构成本轮多用户文件系统权限模型，consumer OS 隔离由 PH 实测。

## 测试与范围

`tests/closure-admission.test.mjs` 覆盖确定性重放、严格 stored refs/signatures、原 scope counterexample、quarantine、license/terms、future/available_at spoof、raw-byte mutation、stale/coverage/lineage、policy/raw binding、namespace/purpose/version/expiry/revocation、source fact extra、IDs/trace/source/feature 的 outcome 注入、签名后的伪 evidence、production、caller await mutation、symlink 和新代码/schema policy epoch。

`tests/fixtures/closure/data-helpers.mjs` 提供 `createClosureDataFixture` 与 `createClosurePolicy`，所有配置明确 SYNTHETIC_TEST_ONLY。30 天 freshness、样例金额及日期仅为 fixture 证据，不可作为真实账户、费率或风险配置。测试中的 unsafeSnapshot、raw-read mutation 是新建内存 fixture DB 的 adversarial harness，不修改旧 DB、seal、ledger 或历史 runs。

实际 full Golden、新 release pin、clean install、consumer isolation、Independent Reviewer 与 25 项 Closure Gate 由总控集成验收；本模块的 scoped PASS 不代替最终 Gate。REAL_DATA_ADMISSION_GATE 仍 BLOCKED，P1B 及 production 仍未授权。
