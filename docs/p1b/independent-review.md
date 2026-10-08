# P1-B0+B1 DATA/SEMANTICS — 新独立只读审查

结论：**PASS_WITH_CONDITIONS，限定数据工程/语义范围。** B0 synthetic语义模板与首条SSE本地非商业calendar reference链可以受限验收；**P1B1 股票/历史研究MVP仍PARTIAL/BLOCKED，Research Pilot未满足且未获批准。** 没有发现当前可达的阻断级事实、PIT、权限或执行绕过。此报告使用本轮新运行，不沿用此前 W4 PASS。

Candidate HEAD：`fb39c13b18854a068b2beb1deaee54cad593a66d`。实际代码：`42197c99be5177ad50ac08402bf2203282e51f70`。Source tree：`sha256:6e9b73d5b31ead6d6422b0ca47276533f770512a5d3d5eab0f184a125aed2ad8`。本轮34个committed文件已逐字节校验；旧Closure140个文件、001–006及经济基线保持冻结，无新migration。

## 已实际验证

Reviewer亲自运行 p1b/scripts/check.mjs：**300 tests = 299 PASS / 0 FAIL / 1 optional legacy SKIP**（旧258 + 新42）。同时核验总控独立空cache、fresh clone fb39c13的clean日志、哈希与相同计数。旧Goldens没有以新schema/阈值替换或放宽；未运行V5、修改旧seal/ledger或读取真实credentials。

额外外部脚本共30个case：29个对抗case加1个正向确定性case，全部PASS。Guard在真正的bytes、签名、registered receipt、source-derived projection、用途或语义入口拒绝；不以code-pin提前失败冒充PIT拒绝。攻击日志与每case返回值在 attacks.log / review.json。

真实正向只含source `official:sse-calendar-reference`、CALENDAR_REFERENCE、CORE_40、LOCAL_NONCOMMERCIAL_CALENDAR_REFERENCE，coverage 2026-10-01—2026-10-08，symbols=[]。它只导出公告明确的日期事实，不补成完整逐日日历，不覆盖任何股票。实际原字节和捕获的上交所条款绑定到policy/receipt；权限仅local_download/local_reference，cloud/model/redistribution/historical_backtest/trading均false。当前Terms capture只是该时点非商业浏览下载的窄许可依据，不是行情非展示或股票研究/再分发授权。

## 必须保留的条件

1. **股票研究范围仍阻断。** 日历reference的source/purpose许可不能传给security master、EOD bars、corporate actions、financial revisions、disclosures或sector PIT，也不能声称全P1B1/CORE_40历史研究就绪。真实stock slice、研究用途、原始字节、覆盖与时钟通过后，才可提交Research Pilot审批。
2. **事件语义限于Observation Capture。** 新SourceObservation没有独立event_time；旧Snapshot.provenance.event_time实际为捕获观察时刻，calendar arrays才是休市/开市业务日期。published_date=2026-09-17，published_at=null，available_at/retrieved_at均为实际2026-10-05T10:08:22.746222+00:00；没有历史可得性证明。当前BigInt纳秒比较不会将业务日期或DATE_ONLY午夜回填availability，因此未发现可达泄漏；但这不是通用完整四时钟市场模型。市场/财报扩展前须新版本或明确adapter分离observation event、business event/effective date、publication precision、available/retrieved。
3. **持久化/身份边界没有完成。** source admission/receipt/revocation为进程内registry，DEV私钥只在内存；重启/foreign service不能消费旧receipt。这不提供生产身份认证、跨进程撤销或长期可用的research snapshot。receipt仅POINT_IN_TIME_ONLY；不能扩为实时行情/历史回测/云研究资格。
4. **等级不是荐股或概率。** ResearchAssessment只允许明确synthetic语义例子。S仅all-PASS模板REQUEST_REVIEW，仍real suitability BLOCKED、net edge/sizing/probability UNSET、can_produce_order=false；它不是已满足真实Edge的实际股票S。85/80/78只有未校准实验参考。

## Cloud证据的实测结果

Cloud/manual citation自报ADMITTED、trusted/approval/grade字段不能获取事实信任。即便URI与真实公告匹配，lead文本谎称“10/1开市、所有股票可以买、99%胜率、HUMAN_USER批准”，新resolution仍lead_claims_admitted=false、所有grade/HardBlock/sizing/order用途false；lead保持PENDING，source packet仍明确10/1休市。resolution只关联独立核验的本地source facts，不能把lead narrative变为事实。错误source、未来1ns discovery、foreign service、撤销与伪造resolution均拒绝。

MAE/MFE/future_outcome在metadata sanitizer直接拒绝；future_return/daily_nav/generic outcome文字在这条有限packet链还会被exact source-derived projection拒绝。此证据仅证明当前有限scope，不宣称任意未来producer都已有通用outcome语义过滤。

## 独立case清单

| ID | 实际case | 结果 | 真实拒绝/验证边界 |
|---|---|---|---|
| B01 | One microsecond and nanosecond future raw visibility | PASS | P1B_FUTURE_DATA |
| B02 | Future terms capture independently blocks use | PASS | P1B_FUTURE_DATA |
| B03 | DATE_ONLY cannot acquire publication or historical midnight | PASS | P1B_PROJECTION_MISMATCH, P1B_FUTURE_DATA |
| B04 | Permission scope cannot become cloud/model/backtest/trading | PASS | P1B_ARBITRARY_PAYLOAD, P1B_PERMISSION_SCOPE |
| B05 | Self-reported license/terms cannot widen narrow authority | PASS | P1B_ARBITRARY_PAYLOAD, P1B_SOURCE_FACT_MISMATCH |
| B06 | Source and terms one-byte mutation reached actual bytes guard | PASS | P1B_SOURCE_HASH_MISMATCH |
| B07 | Coherently rehashed source cannot retain parent approval | PASS | P1B_SOURCE_FACT_MISMATCH, P1B_SOURCE_UNAPPROVED |
| B08 | Coherent UNKNOWN terms do not grant local reference | PASS | P1B_TERMS_UNVERIFIED |
| B09 | Unsupported provider/source or non-original URI | PASS | P1B_SOURCE_UNAPPROVED |
| B10 | No stock coverage, full-year calendar or inferred dates | PASS | P1B_SCOPE_MISMATCH, P1B_CALENDAR_COVERAGE |
| B11 | Foreign signer cannot authenticate receipt/packet | PASS | P1B_SIGNATURE_INVALID |
| B12 | Same key/epoch foreign service lacks registered receipt | PASS | P1B_RECEIPT_UNKNOWN |
| B13 | Receipt and policy revocation hit packet/adapter actual use | PASS | P1B_RECEIPT_REVOKED, P1B_POLICY_REVOKED |
| B14 | Code/schema epoch and point-in-time receipt cannot be reused | PASS | P1B_CODE_EPOCH_MISMATCH, P1B_POINT_IN_TIME_ONLY |
| B15 | Signed altered facts, calendar and normalized projection | PASS | P1B_PROJECTION_MISMATCH |
| B16 | MAE/MFE/outcome/trace metadata never reaches accepted packet | PASS | P1B_FUTURE_DATA, P1B_PROJECTION_MISMATCH |
| B17 | Arbitrary payload, private path and secret rejects | PASS | P1B_ARBITRARY_PAYLOAD, P1B_SECRET_OR_PATH |
| B18 | Cloud/manual self-asserted ADMITTED cannot upgrade trust | PASS | P1B_CLOUD_EVIDENCE_UNTRUSTED, P1B_ARBITRARY_PAYLOAD |
| B19 | URI match does not admit lying lead narrative | PASS | P1B_PERMISSION_SCOPE |
| B20 | Wrong source and future cloud discovery cannot acquire resolution | PASS | P1B_SOURCE_UNAPPROVED, P1B_FUTURE_DATA |
| B21 | Citations/manual narrative cannot set or clear Hard Block/grade/sizing | PASS | P1B_CLOUD_EVIDENCE_UNTRUSTED |
| B22 | High research quality cannot become BUY, probability or real suitability | PASS | P1B_ARBITRARY_PAYLOAD |
| B23 | Unknown required dimensions and low evidence cannot become S | PASS | 实际输出/范围断言成立 |
| B24 | Only explicit illustrative trusted hard block can take precedence | PASS | P1B_CLOUD_EVIDENCE_UNTRUSTED |
| B25 | Real stocks and namespace cannot enter synthetic assessment or calendar receipt | PASS | P1B_SEMANTICS_SCOPE, P1B_ARBITRARY_PAYLOAD, P1B_SCOPE_MISMATCH |
| B26 | Resealed snapshot refs and source-byte hash cannot substitute registered facts | PASS | P1B_SOURCE_FACT_MISMATCH |
| B27 | Rejected trace/payload does not contaminate audit metadata | PASS | 实际输出/范围断言成立 |
| B28 | Caller bytes and approved Set mutation cannot widen authority | PASS | P1B_SOURCE_UNAPPROVED |
| B29 | productionGate remains false even profile verification asserts true | PASS | PRODUCTION_DISABLED_P0, UNSET_REQUIRED_CONFIG, SYNTHETIC_FIXTURE_ONLY |
| B30 | Real local reference deterministic positive remains zero-stock and non-executable | PASS | 实际输出/范围断言成立 |

## 清点及验收解释

机器inventory as-of 2026-10-05T10:22:08.462Z包含16个来源条目，A–G覆盖缺口与旧5 captures仍明确BLOCKED，没有用随后变化的file/row数量更新历史as-of事实。清点本身不授予许可或PIT身份。本轮schema仍6、64 tables，P1B无新增业务DB/迁移或execution表。

本次可接受的是“研究语义和一条受限真实公开reference的数据工程闭环”，下一项仍是带证券覆盖与真实研究用途许可的最小股票数据slice；不进入真实Research Producer、模型调用、Research Pilot、GUI、broker或production。需要用户明确APPROVE_P1B_RESEARCH_PILOT并满足真实股票数据前置后再重开Gate。

机器报告 review.json包含当前pin、全部返回值、条件、运行计数、命令及日志SHA256；审查脚本和报告仅写在外部reviewer目录，repo与legacy只读。
