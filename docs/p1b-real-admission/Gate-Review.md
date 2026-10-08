# P1-B Tushare Real Data Admission Gate Review

2026-10-05 · 工程 Gate：**PASS_WITH_CONDITIONS**。本轮已完成真实三股只读探针、原始证据、严格 DQ、离线回放与安全回归；**新网关真实数据准入仍 BLOCKED**。接口访问成功不等于账户正式权益、授权销售渠道、许可、传输完整性或历史 PIT。既有 SSE 本地参考链保持 PARTIAL；Research Pilot 和 production 均未放行。

凭证已按 Owner 最新明确指令保存至本机钥匙串，后续从固定名称读取；没有 Token、可逆表示或 Token hash identifier 进入工程、报告、fixture、BrainPacket、普通日志或请求指纹。实际有效期按 Owner 声明记录2026-10-05起一个月、2026-11-05 DATE_ONLY；精确到期时刻和供应商证明仍 UNSET_REQUIRED。

| 事项 | 实际结果 / 可核验证据 |
|---|---|
| 1. Executive conclusion | 工程准备及有限真实探针 PASS_WITH_CONDITIONS；REAL_DATA_ADMISSION_GATE=BLOCKED。本轮不是完整真实研究流水线，也未构建真实 Snapshot B。 |
| 2. Owner authorization | [最新授权](../authorizations/P1B-limited-tushare-real-probe-20261005.md)：既有 credential exposure risk accepted、不要求轮换、明确允许当前 HTTP 本地只读探针，并允许钥匙串保存复用。此前要求轮换/HTTPS的报告按原状态保留。 |
| 3. Git / code version | 先前准备 e3e2a6b；初始新候选3c08f85；实际捕获8f8cc0d；强制原始证据验证42e1e4c。捕获/验证 epoch 分开记录；[9文件 source pin](code-provenance.json)。Schema6，SQL001–006不变，无新migration/市场policy。 |
| 4. Secret boundary | 原生 Security.framework 固定 Keychain service/account；读取仅 RAM，释放原生缓冲；禁止 CLI/代理/redirect/fallback、任意钥匙串引用、凭证回显、请求dump。G1命令行ACL读取失败0请求已保留，G2原生读取成功。最终内存匹配扫描见交付证据。 |
| 5. Provider/channel evidence | [Provider evidence](provider-evidence.json)：Owner声明15000积分月卡；销售主体、产品名、渠道授权、真实账户、订单和精确expiry未独立证明。公开权限表不是当前gateway账户权益。 |
| 6. Gateway/transport | OWNER_PROVIDED_MONTHLY_GATEWAY / TUSHARE_MONTHLY_GATEWAY。Owner仅批准HTTP probe；provider_identity_verified、transport_integrity_verified、license_verified全部false。SDK-compatible路径使用已安装1.4.29实际行为；不宣称官方直连/包来源认证。 |
| 7. Entitlement matrix | [8接口矩阵](entitlement-matrix.json)：44次认证请求，均HTTP200/code0；每接口观察到技术访问。没有拒权响应，因此不能填写ENTITLEMENT_NOT_GRANTED；空结果不证明完整coverage。实际账户等级/产品权限清单仍未核验。 |
| 8. Eight-category Data/PIT | [机器矩阵](data-pit-matrix.json)：Security/status、Calendar/rules、Raw bars、Corporate actions、Adjustment versions、Financial revisions、Announcements、Industry membership分开；新gateway所有admission BLOCKED。公告仅既有SSE reference，不调用Tushare公告或分钟接口。 |
| 9. Three-symbol coverage | [覆盖](three-symbol-coverage.json)：603993.SH/600312.SH/603228.SH，各327个交易日raw bars及327因子；目标320计数达到但不等于准入。财务每股原始返回15个报告期，宽窗全响应因范围异常隔离，不能称12季度verified PASS。 |
| 10. Raw capture/hash | [44原始响应清单](raw-inventory.json)，Git外private0600 quarantine。2786是SMOKE+COVERAGE物理行观察数，包含重叠，不是2786个独立已准入事实；唯一raw bars为981。无请求body/token URL存档。 |
| 11. ClockEvidence | [44请求时钟矩阵](clock-matrix.json)：collector-owned完整响应时刻为retrieved/observation/available；FIRST_OBSERVED_BY_THIS_COLLECTOR。event/published精确时刻未知=null，DATE_ONLY不补午夜，history visibility=false。此处是quarantine采集证据，尚未签发admitted ClockEvidence2.0。 |
| 12. DQ | [结果](dq-results.json)：26非空响应PASS，9空响应EMPTY_NOT_COVERAGE，9响应BLOCKED。raw未复权；OHLC/pre_close/非负量额/Decimal/重复/日期/identity检查通过的仅对应观察行，手/千元等保留文档语义与未核验provider单位身份。因子、公司行动、财务版本分别append，不覆盖旧原件。 |
| 13. Cross-source comparison | [交叉比较](cross-source-comparison.json)：13个与当前scope相交的官方SSE calendar事实一致，3股公告reference代码与stock_basic代码一致；1个官方日期在请求范围外明确排除。无完整ST/名称/上市状态官方对照，也无已准入OHLC/行动数值参考；不拿公告标题冒充价格核验。 |
| 14. Snapshot results | 新SourceObservation、policy、StockSnapshot、BrainPacket均NOT_ISSUED；原SSE对象/SourceObservation2.0专用合同保持原样。没有造第三套snapshot协议，未把quarantine market/financial rows塞进SSE reference合同。 |
| 15. Receipt / blocked decisions | [三股blocked decisions](blocked-decisions.json)，没有签发ADMITTED Receipt。缺provider/purpose/license/transport及完整必需类别；真实Snapshot B仍PENDING实际新数据和admitted lineage。 |
| 16. Deterministic replay | [原件回放](deterministic-replay.json)两次结果hash一致，验证原字节、scope/fingerprint、clock、DQ、epoch及bar/calendar/factor date alignment；回放不读凭证、不联网。重抓网络是新observation，未冒充同一capture。 |
| 17. C12–C22 | [条件清单](conditions.json)：本轮新增关闭0项。技术原始覆盖显著改善；所有旧baseline状态保留。C14 historical availability=false、C19历史重建UNSET_REQUIRED/BLOCKED、C22真实producer BLOCKED。 |
| 18. Independent Reviewer | 新只读Reviewer：当前代码、raw/report、Gate证据绑定、旧安全consumer均有实际攻击与原始失败留档。终审报告及补充guard复测见[独立审查](Independent-Review.md)；不把同一suite重复运行计成新增tests。 |
| 19. Golden regression | [Validation](validation.json)：唯一463项=462PASS/0FAIL/1既有可选V5 SKIP；398既有+27新Gate+38新Data。最终55cfa442 fresh checkout/fresh cache的npm ci、npm run check(258项)及新epoch --new-only(65项/原件强制回放)通过；完整聚合入口因旧验证器绝对证据路径退出1，明确保留为迁移技术债；fixture Draft→Assessment→Card保持synthetic，并有独立回放，不拼成真实Research pipeline。 |
| 20. Known failures | [已知失败](known-failures.json)：编码secret回显、Gate统计未绑定、Keychain CLI ACL、未来imp_ann_date验证缺口均留痕；当前强制父验证器对未来公告日期阻断。财务宽窗含范围外报告期、行业空out_date继续quarantine；未放宽来制造PASS。最早58615候选源码未精确恢复，明确披露，失败JSON/harness/SHA仍保留。最终clone聚合检查还发现旧证据路径不可迁移；没有放宽allowlist或改旧Gate使其通过。 |
| 21. License unresolved | 19份官方公开文档及实际捕获时间/hash已记录在[Public evidence](public-evidence.json)。它们支持产品字段/协议规则，但不认证该网关、月卡渠道或许可。supplier storage/retention/transfer/redistribution/cloud及使用purpose均未获独立证明；Owner probe存储授权不替代supplier license。 |
| 22. Remaining Owner inputs | 脱敏订单/商品/销售主体、渠道授权、账户权益/有效期原件路径；supplier明确local研究/storage/retention/transfer说明；解释financial start/end实际filter语义和industry空日期schema。无需再发Token、无需因本轮启动而先轮换、未购买权限。 |
| 23. REAL_DATA_ADMISSION_GATE | **BLOCKED**，仅允许现有Owner read-only local quarantine probe成果；没有任何新ADMITTED source scope。 |
| 24. LOCAL_REAL_RESEARCH_GATE | 新月卡网关 **BLOCKED**。全局已有SSE reference **PARTIAL**保留，不能由gateway技术成功升级成完整真实研究PASS。 |
| 25. P1B_RESEARCH_PILOT_GATE | **BLOCKED**。实际模型、真实Card producer、Cloud Export/Manual Export到云、historical backtest、策略优化、EVENT_3、GUI主体全部未启动。 |
| 26. productionGate | **false**。30项真实账户/本金/佣金/风险UNSET_REQUIRED不变；Signal/Approval/Order、真实sizing/NetEdge/broker/production均阻断，LLM不能成为HUMAN_USER。V5 seal/ledger/code/旧DB/runs只读。 |

检查入口：原工作区 `node tushare-real-admission/check.mjs` 完成398既有+65新项；新checkout可运行 `node tushare-real-admission/check.mjs --new-only` 独立验证65新项及原件。完整clone聚合入口暂有旧绝对路径技术债（退出1），不是全链可迁移PASS。运行期密钥不进入Git，source pin、诊断ProbeGate1.0.0/release1.6.0和ADR-018不授予市场数据许可。既有contract/release/schema和全部历史Gate均保留；允许的变化仅导航和本轮新文件。

最终交付复核：独立906项PASS/0FAIL与项目463项（462PASS/1既有SKIP）分开计数。55cfa442干净副本的新65项及原件回放通过；旧聚合绝对路径失败未掩盖。最终凭证内存匹配扫描1090文件/0泄露，389历史文件及9个新source pin原字节保持。复核补充见[交付补充审查](Delivery-Addendum.md)，完整文件索引见[artifact index](artifact-index.json)；最终Git commit与clean状态记录于[交付checkpoint](/Users/qiushi/投资研究/.p1b-archives/tushare-real-admission-20261005/delivery-checkpoint/Delivery-Checkpoint.json)。

本轮到此停止，等待Owner下一次明确决定。即使技术访问与计数目标达成，也不自动进入Research Pilot、Historical Backtest、cloud或实盘。
