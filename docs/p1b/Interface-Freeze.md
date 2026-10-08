# P1-B0 / P1-B1 Interface Freeze v1.0

授权只允许完成DATA/SEMANTICS Gate然后停止等待APPROVE_P1B_RESEARCH_PILOT。实际Research Producer/Deep Research、真实荐股、broker/production/EVENT/GUI均未授权。旧P0/P1A/Closure合同、001–006、旧seal/ledger/经济基线原字节冻结。

## 新版本与兼容边界

contracts/p1b新增 SourceObservation1.1.0、SourceAdmissionPolicy1.1.0、AdmissionReceipt1.1.0、BrainPacket1.2.0、ResearchAssessment1.0.0、DiscoveredEvidence1.0.0。required/enum/units/time/hash/ref/invalidation见各schema；reason registry独立。ResearchCard1.0四层优先保留，语义sidecar使用独立版本，不强行给真实account_id。SnapshotManifest1.0重用结构和原hash。P1B对象content_hash=canonical(body排除顶层content_hash/proof)；receipt/packet ED25519签UTF8 content_hash，trust root由parent constructor固定，不信任caller公钥。

新实现/tests/scripts置于p1b/，使原Closure140文件commit proof与原check入口保持字节和行为。新phase验证器覆盖p1b+新contracts；不改原source proof/oldvalidators来适配。无新增migration：当前只读legacy、文件object store和进程内source admission，不扩张业务数据库。

## 首条候选scope

仅SSE官方节假日公告、CALENDAR_REFERENCE、CORE_40、有限公告明确日期、LOCAL_NONCOMMERCIAL_CALENDAR_REFERENCE、LOCAL_REVIEW_ONLY、OBSERVED_AT_RETRIEVAL。symbols=[]是没有证券覆盖，绝不解释为全市场股票。官网非商业浏览/下载条款实际捕获并固定hash；cloud_export/redistribution/historical_backtest/model_research/trading全部false。官网行情展示endpoint、旧UNKNOWN条款sources不自动晋升。

published_date从原HTML正文提取；published_at=null保留未知intraday；available_at=真实capture retrieved_at；event_time是观察事件。cutoff必须不早于每个raw/terms capture；DATE_ONLY不能回填午夜，不能据此做过去cutoff的PIT回测。POINT_IN_TIME_ONLY receipt绑定use_at==cutoff，不声称永久实时有效。first real scope若无法证明许可/clock/coverage则FAIL/BLOCKED，如实交Gate。

## Parent shared helper API — p1b/src/contracts.mjs

hash/sha/seal/refOf/validateP1B/assertPublicPayload/makeDevelopmentAuthority/verifyTrustedProof。makeDevelopmentAuthority创建仅本轮DEV内存ED25519身份，私钥不写Git、不交consumer；公钥可进报告。新reasons独立。新helper不得改旧source文件。

## RD owned API — p1b/src/real-data.mjs

createRealAdmissionService({captures,approvedPolicyHashes,authority,codeEpoch})；captures由可信parent实际capture/审核后的manifest和bytes固定，绝非consumer自报source_class/license/clock。constructor复制captures/approved Set/authority，不暴露raw/file/DB/private signer。

- observationFor(source_id)：从原source bytes/clock记录推导严格SourceObservation1.1，仅认可冻结parser/官网条款语义。
- buildPolicy({source_id,use_at,coverage})：输出严格policy；parent批准其hash后registerPolicy。service不能自行扩大批准hash。
- registerPolicy(policy)：原字节/terms/permissions/coverage/use_at/code epoch核验后存内存不可变。
- createSnapshot({policy_ref})：原SnapshotManifest1.0，scopeOBSERVED；data_hash=hash({observation_ref,policy_ref,coverage,purpose,strategy_id,code_epoch})；evidence_refs=[observation_ref]；冻结cutoff==use_at。
- admit({policy_ref,snapshot})：signed、registered receipt；复核PIT和原字节。
- buildPacket({receipt,snapshot})：strict sanitized BrainPacket1.2，只含有限calendar facts/clock/hash/ref，LOCAL_REVIEW_ONLY；不能含内部路径、账户、任意payload、outcomes或credentials。
- verifyPacket({packet,receipt,snapshot,use_at,purpose,strategy_id})：hash/signature、registered receipt/live revocation、原snapshot/policy/capture/terms/source-derived projection逐项比较。
- revokeReceipt(hash)、revokePolicy(hash)、assertTransfer(packet,target)：MANUAL_EXPORT/API/model/cloud/trading请求均拒绝；本地reference唯一用途。
- auditEvents()返回严格ref/reason/hashes无raw或任意payload；trustPublicKeyDer()公钥copy。

RD还拥有p1b/src/inventory.mjs、p1b/scripts/inventory.mjs、p1b/tests/real-data.test.mjs、docs/p1b/source-inventory.json和RD-notes.md。inventory只读工作区指定研究DB的schema/counts、source manifests、raw metadata；明确排除credentials/Codex state/logs/models state；不运行V5、不打开DB writable。至少清点A–G数据类型/provider/source/license/clock/coverage/authority/purpose/limits，保留UNKNOWN而不补造。

## RI owned API — p1b/src/semantics.mjs / evidence.mjs

- assessSemantics({dimensions,evidence_refs,hard_block_refs,research_card_ref,scope})：只接受SYNTHETIC_SEMANTIC_TEST_ONLY；十维输入PASS/GAP/UNSET_REQUIRED/NOT_APPLICABLE；Quality≠Timing≠Account Suitability≠Tradeability。输出schema ResearchAssessment；所有real suitability/edge/sizing/probability BLOCKED/UNSET、can_produce_order=false。任何不可信cloud refs不得驱动Hard Block/grade；S仅模板REQUEST_REVIEW，绝非买单；未知required dims不得S；高研究质量但timing/trigger/edge缺口A；逻辑缺口B；观察C；可信Hard Block/明确不符合X。精确解释reason，不用85/80/78做概率。
- ingestDiscoveredEvidence({original_uri,lead,discovered_at,origin})：strict immutable PENDING_VERIFICATION/CLOUD_DISCOVERED_EVIDENCE，usable_for_* false；无网络/raw/DB权限，无self-promote。
- assertEvidenceUse(evidence,purpose)：pending对hard block/grade/sizing/signal/order拒绝；只有由真实admission facade核验的local receipt对象经显式adapter才可能作为ADMITTED_LOCAL_EVIDENCE，当前无通用consumer晋升入口。
- describeVerificationWorkflow()：capture raw→hash→clock→source/purpose→policy→receipt，单纯citation/manual assertions不改变trust。

RI拥有对应semantics/evidence两源文件、p1b/tests/semantics.test.mjs和evidence.test.mjs、docs/p1b/RI-notes.md。禁止真正RI producer、模型/选股/评分调参、改shared contracts或任何execution写。

## Task contracts

RD — Goal: 首条真实限定scope与source inventory。Context: P1B授权/本freeze/旧source参考。Inputs: schemas,parent captures/helpers,只读legacy。Outputs: owned APIs/tests/inventory/notes。Interfaces: RD API。Constraints: owned paths only；不改合同/全局purpose/旧bytes；未知许可/PIT不能猜；不碰credentials或旧run。Tests: raw mutation/future/DATE_ONLY spoof/source/purpose/coverage/code/receipt revoke/namespace/arbitrary payload/path/cloud transfer等；真实正向必须真实捕获。DoD: 有实际scope证据或精确BLOCKED清单，拒绝入口实测，源元数据可审计。

RI — Goal: 研究语义与不可信线索边界。Context/Inputs: schema/config/授权/旧ResearchCard。Outputs: owned pure semantics/evidence APIs/tests/notes。Constraints: synthetic模板测试而非真实荐股；不建research producer；不改变旧合同/费率/Edge。Tests: quality高不能推timing通过，unknown不能S，cloud不能改Hard Block/grade/sizing，score不能概率，executionfalse。DoD: required20项Gate相关语义可解释并有拒绝测试。

Independent Reviewer — 只读本轮candidate/source inventory/license/clock/semantic contracts，实际攻击PIT/evidence/grades/relabel/scope、检查旧冻结和Golden；报告新的本轮证据，不复用历史PASS。不改实现/预期。Parent只负责shared schema/ADR/reasons/releases/最终source pin/Gate。所有agent不执行git mutations；parent统一提交。RD/RI在本freeze提交后才能写实现。BT/P1B2/P1B3本轮不启动。
