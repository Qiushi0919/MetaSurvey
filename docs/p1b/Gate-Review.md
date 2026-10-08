# P1-B DATA/SEMANTICS GATE REVIEW

结论：**PASS_WITH_CONDITIONS，仅限下述数据工程/语义范围。**验收边界为 **P1-B0语义 + 真实SSE有限日历本地参考数据工程**；**完整P1-B1股票历史研究MVP = PARTIAL / BLOCKED，Research Pilot = BLOCKED**。本轮没有真实选股、模型研究、订单或券商。即使本地工程有条件通过，也不意味着股票研究准备完成。

实际 CODE_VERSION `42197c99be5177ad50ac08402bf2203282e51f70`，SOURCE_TREE_HASH `sha256:6e9b73d5b31ead6d6422b0ca47276533f770512a5d3d5eab0f184a125aed2ad8`；独立检出 candidate `fb39c13b18854a068b2beb1deaee54cad593a66d`。新 release=1.3.0，Schema=6，无007。34个新增阶段代码/fixture/schema/接口文件绑定真实Git commit；140个旧Closure code原字节不变。旧迁移/合同/releases/经济报告等233个旧tracked文件保持原字节，当前README/AGENTS/SoT导航文档按授权更新。证据见 [冻结基线](frozen-baseline.json)、[contract matrix](contract-matrix.json)、[schema实证](schema-report.json)。最终delivery commit/tag/bundle/index的非循环指纹放独立external checkpoint。

## 1. Research semantics

十维独立：Company/Fundamental Quality、Sector Quality、Catalyst、Evidence Quality、Valuation、Timing、Risk、Cost、Account Suitability、Tradeability。ResearchAssessment1.0仅为明确synthetic语义模板，不输入真实symbol/account，不生成真实ResearchCard或等级。[语义](Semantics-and-Evidence.md)、[配置](../../p1b/config/semantics.v1.json)保留85/80/78为EXPERIMENTAL_DEFAULT；没有概率/胜率/经验边界映射。真实Edge、sizing、calibration仍UNSET_REQUIRED。

## 2. Quality vs Timing separation

Company Quality不能推出Timing通过或现在可以买。合法synthetic高质量样本在Timing/Cost/AccountSuitability/Tradeability存在GAP时保持 `research_grade=HIGH`、`actionability_grade=A`、`next_action=WATCH`。更改核验维度和证据会生成新assessment hash；只有公司质量改善不能自动A→S。[新Golden](golden-test-matrix.json)保存实际测试名称/行号/源hash/新run。

## 3. S/A/B/C/X precise semantics

| 等级 | 语义 | 最大动作 |
|---|---|---|
| S | 研究、时点、证据、Edge/成本与资格检查全部通过且无Hard Block | REQUEST_REVIEW；不能自动买入 |
| A | 研究质量高，当前价格/Timing/trigger/费用/适用性仍有未满足项 | WATCH / WAIT_FOR_TRIGGER |
| B | 存在逻辑或催化，重要证据/赔率/趋势等存在缺口 | NO_ACTIVE_TRADE |
| C | 只有研究/观察价值 | RESEARCH_ONLY |
| X | 已核验Hard Block或明确策略不满足 | BLOCKED |
| UNSET_REQUIRED | 必须核验的事实未知 | UNKNOWN；不能伪称S或事实已确定 |

本轮S只是synthetic全PASS模板；真实账户、Edge和生产输出仍阻断。已知例子Hard Block优先于质量，cloud/manual断言不能设置/清除它。未来real producer须明确Edge、strategy requirements与证据政策，不能借此模板当真实评分引擎。

## 4. ResearchCard contract-fit analysis

[先提交的Fit Analysis](Contract-Fit-Analysis.md)结论：保留ResearchCard1.0四层 Research / Price / Trade / Probability。独立ResearchAssessment sidecar表达三轴，禁止伪造required真实account_id；当前card_ref严格null-only，不创建真实Card producer。新SourceObservation1.1、Policy1.1、Receipt1.1、Packet1.2、DiscoveredEvidence1.0、EvidenceResolution1.0拥有独立版本/URN，旧P0/P1A/Closure schema/validators原字节不改。SnapshotManifest1.0在OBSERVED范围复用。

## 5. Evidence trust classes

ADMITTED_LOCAL_EVIDENCE与CLOUD_DISCOVERED_EVIDENCE分离。Citation、manual assertion、URL可形成PENDING_VERIFICATION lead/counterargument；没有trust proof、不能满足/解除Hard Block、升级S、Signal/Tradeable或真实sizing。Schema/hash是完整性工具，不能替代可信source、approved policy、stored receipt、固定issuer签名和live revocation。[合同](contract-matrix.json)与[接口澄清](Interface-Clarifications.md)给出字段/required/枚举/时区/hash/失效规则。

## 6. Cloud-discovered evidence workflow

pending lead → local capture原件/hash → timestamps/source/terms/purpose/coverage → normalized/DQ → snapshot → approved policy → registered receipt → 新source-facts EvidenceResolution。原lead不原地升级，文本claims一直pending。实际E2E使用明确模拟LLM lead（没有模型调用），本地匹配官方原URI后只认证原件中的calendar事实；`lead_claims_admitted=false`。同URI但谎称休市日开市也不认证谎言。Resolution每次use重验packet/receipt及撤销；本scope HardBlock/grade/sizing/cloud/model/order仍禁止。[真实链结果](real-reference-results.json)及独立攻击可复验。

## 7. Source inventory

[机器清单](source-inventory.json)在 `2026-10-05T10:22:08.462Z` 实际只读清点16条目，包括两个NOT_FOUND标记；不是16个获许可源。旧SQLite main-file用mode=ro&immutable=1/query_only：stock_info15,549，hk_daily3,904,281、2016-08-19—2026-08-19。HK不是A股准入。主文件/WAL/SHM前后hash一致，immutable排除未checkpoint WAL，不宣称live数据库认证。Kline只清点8,975个filename，未认证行/日期。排除credentials、Codex状态/日志/模型DB、账户状态、个人工作簿；未执行旧collector/V5或迁移历史大库。

## 8. Source/license matrix

[完整矩阵](Data-Matrices.md)逐source列terms、再分发和allowed purpose。公开访问不能代替许可。旧SSE dayk、腾讯cache、CNINFO/issuer引用与原五个public captures继续BLOCKED。首条新scope仅依 [SSE官网条款](https://www.sse.com.cn/home/legal/) 非商业浏览/下载用途建立本地参考，不推导行情产品、cloud/model、再分发、股票研究/交易或历史backtest许可。[公告原件](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml)和terms raw hashes均绑policy/receipt。

## 9. PIT clock matrix

正文published_date=2026-09-17，URI含09-15不代表发布时间；intraday published_at=null，DATE_ONLY不补午夜。实际available_at=retrieved_at=`2026-10-05T10:08:22.746222+00:00`；terms retrieved=`2026-10-05T10:08:22.572813+00:00`。任一原件/terms晚于use_at即拒绝，比较保留纳秒精度。当前calendar业务日期另存facts；Snapshot event_time是**捕获观察事件**，不是休市事件时间。新SourceObservation缺独立event_time，因此不声称通用四时钟市场/财报MVP；扩展前需新版本区分observation event/business effective date。此次10月捕获不能回填9月historical availability。[PIT矩阵](Data-Matrices.md)、[条件](conditions.json)保留这一限制。

## 10. First real admitted scope

`REAL_DATA_ADMISSION = PASS_FOR_SPECIFIC_SCOPE`：

| 边界 | 值 |
|---|---|
| source / data_type | official:sse-calendar-reference / CALENDAR_REFERENCE |
| namespace | CORE_40；EVENT_3与RESEARCH_6_18M不可借权 |
| coverage | SSE 2026-10-01—2026-10-08，只包含公告明确日历事实；symbols=[]为零证券覆盖 |
| purpose / transfer | LOCAL_NONCOMMERCIAL_CALENDAR_REFERENCE / LOCAL_REVIEW_ONLY |
| 固定use_at | 2026-10-05T10:31:00.916Z |
| 本次run | P1B-REAL-REFERENCE-20261005T103100961Z |
| 两次相同上下文重放 | canonical相同；replay_hash `sha256:d0bc3410052d76cc9bad237c785ef4974209abe0a2cbdc3c87b39167dc0bc45d` |
| 仍禁止 | cloud、model、历史回测、真实股票荐股、真实sizing、交易、production |

这是OBSERVED参考证明：不完整日历、不股票历史slice、不全局REAL_DATA PASS。历史股票ADMITTED snapshots=0。原件来自实际TLS capture、非synthetic；小原件label=REAL_PUBLIC_CAPTURE_NOT_SYNTHETIC/TEST_REFERENCE。测试代码epoch不充当最终Receipt，最终对象绑定实际Git pin与actual use_at。

## 11. First REAL SnapshotManifest

SnapshotManifest1.0，scope=OBSERVED，`content_hash=sha256:663d7a0996779f2b6779fc735c75564869b71f7ac6d1920821d81f013bc1496d`。provenance原source bytes、retrieval、DATE_ONLY与frozen cutoff均可追踪；data_hash绑定observation/policy/coverage/purpose/namespace/code epoch。完整对象在 [真实E2E](real-reference-results.json)，对应单独归档引用见 [对象索引](artifact-refs.json)。未将reference改成RECONSTRUCTED或历史股票snapshot。

## 12. First REAL AdmissionReceipt

AdmissionReceipt1.1，VERIFIED+ADMITTED仅上述scope，`content_hash=sha256:0a55afd72629bfd9f321e6cfe19399fabf4d3332062e0d33ce86c85bcfeaaa15`。ED25519固定DEV公钥验证；exact source/policy/snapshot/data/use_at/epoch绑定。自签、自报ADMITTED、相同key但foreign service、撤销后用、换purpose/namespace均拒绝。私钥仅当次进程内存，未入Git/consumer。当前receipt/revocation registry不持久，归档能证明当次结果，不能跨重启自动admit或作为live生产授权。

## 13. First REAL sanitized BrainPacket

BrainPacket1.2，`content_hash=sha256:3189c0df3dbde1da557dbcfd371cd55f739d44d0ba7693aab28aa1334e848d40`。只含source-derived scoped日历/clock/ref，固定projection与signature再次比较；无账户、credentials、内部路径或未来outcome。`transfer_mode=LOCAL_REVIEW_ONLY`，production/order=false，schema禁止任意字段。cloud/export/API/model/trading用途均拒绝。保存完整packet、公钥、receipt和audit，能够检验当次签名与两次重放；不假装获得云端研究许可。

## 14. Rejected source examples

旧行情cache：无original bytes/license/per-bar available/PIT，qfq→raw fallback缺adjustment lineage；旧SSE dayk：公开capture但条款/clock/coverage未认证；旧CNINFO/PDF hashes：只是manifest断言，非revision admission；旧calendar updated_at：非historical availability；当前industry标签：不能证明历史成员。故原sources保持BLOCKED。实际negative tests还拒绝UNKNOWN terms、伪原URI、自报source、byte/hash修改、未approved policy、全年/证券coverage。[清单](source-inventory.json)与测试记录不伪造通过。

## 15. Future leakage attacks

新测试实际覆盖source/terms比cutoff晚1微秒、publication午夜spoof、future lead、snapshot/version/ref替换、撤销、跨service/epoch、source projection污染和cloud grade/HardBlock用途。可信签名也不能改变源facts；未来MAE/MFE/outcome/trace在真实guard拒绝；拒绝audit只记固定reason/action及空caller refs，不传播注入的trace或payload。Independent Reviewer另作1纳秒、真实重签projection和谎言lead攻击；最终独立结果见第20项。没有用code-pin早期拒绝冒充PIT/source边界。

## 16. Industry membership PIT result

**REAL = BLOCKED**。未找到已准入effective-dated行业/sector member revision history，不用今天sector标签回填历史。原PIT/kernel与namespace synthetic回归通过，但不充当真实industry证据。C20继续开放，下一次真实股票slice须单独认证。

## 17. Corporate-action / financial revision result

**REAL = BLOCKED**。旧qfq/hfq缓存不能建立官方action/revision/factor/entitlement lineage；真实financial parser、revision source bytes和历史可见性未齐备。原raw/adjusted隔离、corporate-action visibility、financial revision PIT的synthetic Golden保持通过；未改旧财务/行情库或seal，未称真实财报修订验收完成。

## 18. Remaining C12–C22

| 条件 | 当前状态 | 剩余工作 |
|---|---|---|
| C12 | BLOCKED | flat stock_info无历史状态、原件许可和可得时间证明 |
| C13 | PARTIAL_REFERENCE_ONLY | 仅SSE公告10/1–8明确日历事实本地参考；完整日历/其他交易所/板块规则未认证 |
| C14 | BLOCKED_HISTORICAL | 新calendar只有实际取回的observed availability，旧source不可补历史 |
| C15 | BLOCKED | 旧cache/old SSE dayk无独立行情许可、原始bar clocks/preclose/PIT；无证券范围 |
| C16 | BLOCKED | 独立action/revision/source admission未齐备 |
| C17 | BLOCKED | 旧qfq→raw fallback不能建立factor版本/原始价格对账 |
| C18 | BLOCKED | 旧CNINFO/issuer引用只是线索；许可、修订原件/可见时钟未齐备 |
| C19 | UNSET_REQUIRED | 不补午夜；本地参考已知发布日期+retrieval可用，历史研究规则未批准 |
| C20 | BLOCKED | 未找到已准入的effective-dated历史成员/修订；当前标签不可回填 |
| C21 | BLOCKED | 没有真实股票研究slice，85/80/78仅实验坐标 |
| C22 | SEMANTICS_ONLY_PRODUCERS_BLOCKED | 仅synthetic语义与pending证据/有限calendar adapter；未实现真实producer/store/荐股/calibration |

[conditions.json](conditions.json)另外保留实际source用途许可、第二个人工Gate、memory/DEV registry、四时钟扩展和真实30字段/Edge/sizing/calibration的条件。建议下一次首先由RD完成有限真实证券+行情+财报公告slice的许可/clock闭环；RI真实producer须在数据与人工pilot Gate后才启动；BT校准在producer稳定后。此处只是建议，不创建/启动下一阶段agent，也不联系外部、购买数据或接credentials。

## 19. Golden regression

全新外部clone、空node_modules/cache、空user/global npmconfig、env-i仅PATH：**300 tests / 299 PASS / 0 FAIL / 1 optional legacy SKIP**。旧258（257PASS/1SKIP）+新42（42PASS）；25类Golden无回退，portable14日V5 ledger fixture通过，未恢复/运行外部V5。旧CLI seal mismatch继续保留。旧T+1/cash ordering/费用含量affordability/最低佣金/BigInt对账/重复单/版本失效/LLM≠human/生产阻断均通过。空库→001–006→schema6，64表，第二次迁移无新增；旧迁移原hash不变。[validation](validation.json)、[Golden矩阵](golden-test-matrix.json)、[schema](schema-report.json)、[冻结基线](frozen-baseline.json)给实际源/hash/log。

本轮不改cost/ledger/replay代码或经济报告；原六组friction/Edge经济证据作为历史基线保留，当前完整旧回归实际重跑。新real-reference facade无DB/order/broker import/handle，执行能力不存在，E2E没有订单写入路径；不是假称查询了真实订单库。未执行远端CI或部署实际PostgreSQL。系统Git/Python受Xcode许可限制，本轮使用Homebrew Git与bundled runtime，未变更系统设置。账户30字段仍UNSET_REQUIRED，productionGate=false、真实broker/自动执行BLOCKED、V5=LEGACY_EXPERIMENT。

## 20. Independent Reviewer result

新[独立Reviewer报告](independent-review.md) / [机器返回值与log SHA](independent-review.json)：**PASS_WITH_CONDITIONS**；额外29项对抗+1项正向，30/30 PASS；Reviewer亲自完整检查300项（299PASS/0FAIL/1optionalSKIP）。实际candidate/code/tree/34新增+140旧文件逐字节确认，没有使用以前W4 PASS代替，也没有修改repo/legacy/预期/业务规则。无本轮可达的阻断级缺陷。

条件为：股票研究/Pilot未就绪；Observation Capture与business effective dates明确分开；内存registry/DEV issuer/固定时点证明不能变成持久生产身份或live权限；synthetic S不是实际股票S或概率。所有条件已体现在本Gate与conditions中，不因PASS_WITH_CONDITIONS自动关闭。

已完成本轮20项审查与受限工程交付。**停止，等待用户审阅本Gate并显式APPROVE_P1B_RESEARCH_PILOT；真实股票source许可/PIT/覆盖前提仍必须独立闭环。** 不启动P1-B2/P1-B3、真实模型/选股、GUI、broker、EVENT_3或自动执行。
