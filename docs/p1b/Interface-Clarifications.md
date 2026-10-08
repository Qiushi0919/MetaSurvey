# P1-B0 interface type clarifications

父总控在5e4aa52冻结后、子agent写实现期间仅明确先前未定的输入类型，合同/业务边界不改。

RI bare evidence refs不是trust proof。本轮只接受两个已知语义fixture：synthetic:semantics:admitted-local-example和synthetic:semantics:hard-block-example，version1，hash=hash({fixture_id:object_id,scope:SYNTHETIC_SEMANTIC_TEST_ONLY})。它们仅为例子，不代表真正准入的公司事实。Cloud object/ref、自报ADMITTED字段、未知fixture ref/hash拒绝；真实trust adapter留给获批pilot。S模板要求十维PASS、至少一合法例子、无hard block；仍不可荐股或交易。

RD capture形状由parent固定：source_id/source_version/original_uri/raw_bytes/raw_sha256/retrieved_at/capture_method与terms{original_uri/raw_bytes/raw_sha256/retrieved_at/capture_method}。真实TLS新捕获的HTML及manifest在p1b/tests/fixtures/real-reference，原始字节另存外部archive。下载时间为真实观察，不构成2026-09历史可得证据。BODY发布日期09-17不能以URL09-15替代。

coverage只涵盖公告明确指出的休市/开市/周末事实，不把起止区间补成完整逐日交易日历；symbols=[]意味着零证券覆盖。codeEpoch由parent实际phase pin核验后提供；unit-test epoch明示TEST，不充当最终Gate证据。Development authority为内存新ED25519身份，不是生产key，私钥不入Git/consumer；最终公钥及签名可归档验证。

新source timestamps原始捕获具有微秒精度，PIT比较须保留亚毫秒边界；禁止因为JavaScript Date舍弃精度而让未来available_at通过。日期只有DATE_ONLY则published_at=null，不人为补时分秒。

Parent新增明确adapter合同EvidenceResolution1.0.0（新独立对象，不改已冻结6合同），作为local calendar-only cloud线索验证链的具体落实。模拟cloud lead仍PENDING；只有原URI匹配真实capture且真实facade再次验证receipt/packet/snapshot，才新建ADMITTED_LOCAL_EVIDENCE source-facts resolution。它不把lead文本或任意claims当已验证事实，lead_claims_admitted=false；hardblock/grade/sizing/cloud/model/execution用途仍全部false。每次resolution use重验实时撤销。此adapter父总控实现，RI的pending API无需扩权；不建立通用real research producer。
