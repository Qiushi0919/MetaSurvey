# P1-B REAL STOCK SLICE GATE REVIEW — 2026-10-05

**LOCAL_REAL_RESEARCH_GATE = PARTIAL；工程审查 = PASS_WITH_CONDITIONS。** 首条真实股票公告参考链已实际运行，fixture Draft→Assessment→Card 已组合跑通；完整股票研究数据尚未齐备。CLOUD_RESEARCH_EXPORT_GATE、HISTORICAL_BACKTEST_GATE、PRODUCTION_DATA_GATE 均 BLOCKED，redistribution=DENIED，Research Pilot=NOT_GRANTED。本轮到此停止。

正式交接文档继续是主要 Source of Truth。本轮依据 [Owner 决定](../authorizations/P1B-real-slice-20261005.md) 和“暂无可核验 Tushare 授权，保持 BLOCKED”的明确回复执行。先前 Source Preparation 已被 Owner 接受，但其历史报告的 PENDING 状态和原始字节保留；本次新报告记录后续批准与实现，未把建议自动升级为业务规则。

## 1. 实际证据链与准入数量

最终正向重新捕获发生在北京时间 **2026-10-05**，实际 decision cutoff=`2026-10-05T12:51:22.803Z`（20:51:22.803）。捕获5份原件：SSE网站法律声明、节假日通知、三只证券各一份披露索引响应。原始 bytes、SHA-256、collector completion clock、签名记录和完整对象均在 Git 外。

| 数量 | 实际结果 | 边界 |
| --- | ---: | --- |
| admitted source identities | 2 | SSE disclosure reference / calendar reference；不是两家行情供应商 |
| admitted products | 2 | 有限官网披露索引 / 节假日文件 |
| admitted stock references | 3 | SSE:603993、SSE:600312、SSE:603228，仅CORE_40工程证券 |
| real StockSnapshot1.0 | 3 | 每只证券一份公告参考manifest，共用已准入有限日历 |
| real AdmissionReceipt2.0 | 3 | exact reference scope、actual usepoint、code epoch，DEV签发 |
| sanitized BrainPacket2.0 | 3 | LOCAL_REVIEW_ONLY、未上传、无模型调用 |
| actual announcement pointers | 15 | 每只5条；不代表180天完整覆盖 |
| structured market / financial rows | 0 / 0 | 缺失类别无fallback |

每只证券实际经过 `original bytes → capture/hash → source-derived normalization/DQ → ClockEvidence → exact policy → registered snapshot → signed receipt → signed sanitized packet → local verify/transfer`。同一真实 capture/usepoint/issuer 的第二次运行得到完全相同的三个对象。新的独立抓取有新的 retrieval/usepoint，不能假装与此前是同一次观察。

[对象ref与完整证据指纹](artifact-refs.json) 给出三个实际 snapshot/receipt/packet 的 id/version/hash。完整脱敏本地对象见 [外部正向证据](/Users/qiushi/投资研究/.p1b-archives/real-stock-slice-20261005/positive-repaired-A/real-slice-evidence.json)，文件SHA-256=`303dcf5b02ad0a58179193bec3aa0facb9d70bcd34579d9d47d0b9de5226d18e`。这些归档证明当次观察；进程结束后不恢复 live registry、签发能力或未来用途许可。

## 2. 八类数据覆盖

三只证券具有相同的覆盖结论，各自公告参考仅5条：

| 类别 | Gate | 实际证据 / 缺口 |
| --- | --- | --- |
| Security/status | BLOCKED | 指针含证券代码；无完整身份/status/ST/停牌有效历史 |
| Calendar/rules | PARTIAL | 14个明确休市/复市日期；无完整320-session calendar及session rules |
| Raw bars | BLOCKED | 0行情行；320交易日OHLCV、原始前收/单位/许可未证齐 |
| Corporate actions | BLOCKED | 没有解析行动条款、权益、有效区间和修订原件 |
| Adjustment versions | BLOCKED | 没有factor版本、行动链和raw-adjusted对账 |
| Financial revisions | BLOCKED | 没有12季度财务字段、predecessor和修订可见性链 |
| Announcements | PARTIAL | 每只5条实际索引参考；完整180天/原文/修订链未完成 |
| Industry membership | BLOCKED | 没有已准入分类版本及成员有效历史 |

索引请求pageSize=5，实际网站缓存返回25条。原件不裁剪，批准projection只取实际前5条。公告标题或PDF链接不成为financial/action数据。可选3份PDF因官网重定向严格阻断，未把失败请求伪装为成功原件；最终正向runner不准入PDF原文，document_sha256仍null。[Data Notes](Data-Notes.md) 记录具体证据与限制。

## 3. Clock proof

[完整时钟矩阵](clock-proof-matrix.json) 保留每条source的actual capture hash、raw source version和严格ClockEvidence1.0：

- published_precision=DATE_ONLY；保存来源日期，published_at=null，未补午夜。
- retrieved_at由collector在成功取得完整原件时产生；caller不能传入或倒填。
- 当前无earlier availability proof，available_at=observation_event_at=retrieved_at。
- event_time / business_effective_at / observation_event_at 分开；未知业务时刻保持null，日期事实不冒充时刻。
- 所有historical_visibility_proven=false；trade_date、ADDDATE、供应商更新窗口、今天抓取均不产生历史PIT权限。

真实使用验证同时检查原始byte integrity、注册对象、精确policy/usepoint和code epoch。时钟结构/纳秒算术测试与真实collector authority分别记录。当前信任边界是本机wall clock和HTTPS collector，不是可信硬件时间或生产身份设施。

## 4. License / purpose

[用途矩阵](license-purpose-matrix.json) 逐份绑定source/product/data_type/purpose/CORE_40/有限symbols与dates/clock version/captured terms hash/approved projection/code epoch/usepoint，不存在SOURCE_X=TRUSTED。

SSE法律声明的已捕获非商业浏览下载条款支持这些精确官网页面的本地参考角色；它不授予全市场行情feed、结构化财务产品、raw/cloud export、再分发或历史PIT。所有packet都只允许 LOCAL_REVIEW_ONLY，CLOUD_MODEL / MANUAL_EXPORT 等用途升级被阻断。

Tushare adapter在secret lookup与网络之前返回SLICE_ENTITLEMENT_UNKNOWN；即使caller提交verified=true也不能自证。没有读取Token或调用授权API。BaoStock保持UNKNOWN_LICENSE/BLOCKED；正式历史产品仅保留未来候选，本轮未购买、接入或联系供应方。

## 5. Snapshot A / B

Snapshot A三份均实际识别CLOSED，live_price=null、trade_trigger=false、tradeable=false。已准入节假日原件可证明10月5日休市，但不能独立证明9月30日是最新实际交易日。因此latest_trading_session=null，而非weekday推算或复用旧缓存。

**真实Snapshot B尚未存在，真实A/B比较未执行。** 新增合成比较验证new source hash→new snapshot hash→受影响feature/packet失效、独立未变事实hash保持；fixture真实执行的上游合成bar变更也使旧Card失效。这些机制测试不能证明10月8日真实bar已经返回。

已建立北京时间10月8日16:30的一次性本对话就绪复核，详见 [Continuation](Continuation.md) / [A/B机器状态](Snapshot-AB.json)。只有实际新交易日原件、准入用途和冻结接口均成立时才能构建B；若仍缺授权/数据则继续PENDING。当前固定索引查询截止10月5日，不会把重抓旧窗口当成新交易日。

## 6. Fixture Draft → Assessment → Card

[实际回放结果](fixture-results.json) 使用冻结Closure producer、OS隔离consumer、importResearchResult、冻结assessSemantics及原严格ResearchCard1.0 validator，组合成新FixtureResearchChain1.0侧车。两次实际BASE回放一致，replay hash=`sha256:93ffa7f02bfa27c1621ddb68be7acadbb87220cda6350592661e88b2b41c627f`。

完整packet/draft/assessment/card/snapshot/receipt版本与hash均被绑定。上游bar变更使旧Card superseded，即使独立semantics结果不变；TTL、receipt/policy撤销、caller reseal和namespace升权都被阻断。旧card/ledger未被改写。

native Card使用明确的非证券/非账户synthetic sentinel，grade继续UNSET_REQUIRED，真实cost suitability、Edge、概率、sizing均未知。合成assessment的S最多REQUEST_REVIEW；LLM输出不成为user Approval。来源证据refs与semantics固定illustrative坐标分开，未把市场bar推导成公司质量。Research Model调用、broker调用、执行写入均0。详见 [Integration Notes](Integration-Notes.md)。

## 7. 新独立审查及修复

新Reviewer使用自己的实际5份抓取和同进程registry，未修改repo/policy/业务规则。**首个候选ba6cb20被判FAIL**：receiver替换绕过验证（P1）、fixture TTL毫秒截断（P2），共5个错误接受。原失败报告、原件和重现实验全部保留，没有放宽预期来做绿测试。

最终代码266a708修复为私有immutable lexical facade，公开异步边界在首个await前复制输入；fixture先严格验证ISO日历/时分秒再以BigInt纳秒比较。旧冻结helper、合同和业务规则未改。修复后新capture、新pin、新独立复验均执行。

[独立审查](Independent-Review.md) / [机器结果](independent-review.json)：**100项期望检查通过、0失败**，包括41项当前live suite、49项独立构造检查、10项独立纯clock检查；90项real-registration/fixture检查与10项算术检查分别列出。原5个失败反例全部被阻断。正向control、raw变异逐字节恢复、receiver call/apply、await变异、精确TTL与非法日期均复验。28项Owner威胁逐项映射。

对financial/action/factor/industry的攻击只证明“未支持类别不能塞进reference boundary”；公告删除攻击只证明已注册projection不能caller删改。它们不认证尚缺的真实历史解析、完整修订或industry PIT算法。Reviewer结论PASS_WITH_CONDITIONS，各用途Gate不升级。

## 8. 合同、Schema、Git与保存边界

新release1.4.0的 [7份严格合同与全部文件hash](contract-matrix.json)：ClockEvidence1.0.0、SourceObservation2.0.0、SourceAdmissionPolicy2.0.0、StockSnapshot1.0.0、AdmissionReceipt2.0.0、BrainPacket2.0.0、FixtureResearchChain1.0.0；新reason registry1.0.0。StockSnapshot明确是新股票参考manifest，没有伪装成已通过旧SnapshotManifest validator。required/nullable、enum、单位、timezone、ref/hash、reason和失效条件均明确；没有新增真实money默认值。

最终source code commit=`266a7083ce2c77c31917899ced458951661ddaed`，29文件source_tree_hash=`sha256:358cd6afd7100ce2c6283fffef39496e09149fe9bfcdd96de5d34ff80847e89e`。[source pin](../../real-slice/config/code-provenance.json) 与Git实际字节绑定，CI不会自动重算预期来掩盖变更。

Schema仍6，001–006、64表及空库→latest/幂等回归通过；无007或全量历史迁移。[Schema报告](schema-report.json) 明确新authority为DEV process registry / 外部文件证据，不声称持久consumer或真实服务器数据库已部署。

以准备交付981e370为baseline，316个原tracked文件中的313个不可变文件逐字节相同，允许更新仅AGENTS/README/source-of-truth导航。旧140+34 source pins、old releases/ADR/报告、真实配置和经济报告全部保存；V5保持LEGACY_EXPERIMENT，不映射CORE_40/EVENT_3，旧实验、seal、ledger、DB和runs只读。[保存证明](preservation.json) 可核验。

新代码在real-slice/，合同在contracts/real-slice/；ADR-016和当前Gate独立保存。新CI仅offline检查，无真实网络collector或模型。正式交付tag为p1b-real-stock-slice-20261005，最终commit/tag、Git bundle与恢复校验记录在Git外delivery-checkpoint.json，避免报告自身引用自己的commit。

## 9. Golden回归

[干净副本验证](validation.json)：精确锁依赖重新安装，实际完整运行 **348 tests：347 PASS、0 FAIL、1 SKIP**。旧258项（257通过/1可选外部V5跳过）、旧P1B42项全过，新48项全过（Data20/Core14/fixture14）。[25类既有Golden](golden-test-matrix.json) 按新日志实际名称和原文件hash重新验证；portable14日ledger baseline通过，未重写旧账本。

单个SKIP是未提供外部V5 host assets的可选路径；旧CLI hash mismatch仍为已知legacy compatibility issue，未改seal或伪造通过。未执行远端CI、经济调参或真实历史回测。

## 10. 已知缺口、C12–C22与下一步

[当前条件清单](conditions.json) 不重写旧条件：C12完整status、C13完整calendar、C15 bars、C16 actions、C17 factors、C18财报/公告修订、C20行业历史和C21真实样本仍未闭环。C14历史可见性仍阻断；C19只闭合获准current DATE_ONLY政策，historical reconstruction继续UNSET_REQUIRED；C22闭合fixture composition，真实research producers/概率/Edge/calibration仍BLOCKED。

仍需可核验的actual provider account/product、服务协议、purpose、retention/storage、transfer rule和source version证明。既有30项真实账户/券商/资金/费率/风险字段继续UNSET_REQUIRED，未继承旧5000/6000/10000本金、3000/8000单票金额、旧费率或旧风险。

下一轮如Owner另行批准，应先由一个Data/PIT Agent补经核验用途的数据和八类缺口，再由独立Reviewer重新准入；现阶段不适合启动真实Research Pilot。真实模型producer须另获APPROVE_P1B_RESEARCH_PILOT，且数据/transfer前提独立成立。当前不启动GUI、EVENT_3、策略优化或多模块全面开发。

## 11. 真实资金执行阻断与停止

生产仍因真实配置未确定、市场/财务/status/calendar等数据未齐、历史可见性/校准不足、durable issuer/revocation未建设、model/cloud transfer未准入、真实human approval链及broker/production权限未获准而阻断。当前BrainPacket和fixture Card从合同到runtime均不可产生Order。

本阶段完成获准的current reference工程链与fixture组合、独立审查和Gate后停止。**不自动进入Research Pilot或其他下一阶段；Snapshot B保持真实证据到来前PENDING。**
