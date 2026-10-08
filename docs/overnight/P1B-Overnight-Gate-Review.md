# P1-B Overnight Gate Review

2026-10-06 · 受限离线工程；代码候选55cb3916262fc6f236a92d156028561248ae2f09。工程结论 **PASS_WITH_CONDITIONS**；真实数据准入继续 **BLOCKED**，Owner验收待确认。

Owner授权的T1–T9工程工作已完成实现与验证。原44份响应可稳定归一化与回放，完整fixture研究链可验证版本/失效边界。本轮没有新增真实采集，没有实际模型/股票评级/ResearchCard/Signal/Approval/Order/券商或资金执行。约20小时是授权窗口；不为凑时长继续开发，不自动进入下一阶段。

| 工作 | 结果与限制 |
|---|---|
| T1 Clean/portable baseline | 最终候选clean clone与新npm cache；完整入口执行534项：533PASS/0FAIL/1既有可选SKIP。新EvidenceRootBinding1.0.0固定2份checkout文档+5份原位置私有文档。旧绝对路径入口及其历史失败保留；只证明移动checkout而私有归档不移动的验证，不声称任意机器/云CI可迁移。 |
| T2 Quarantine normalization | 44请求/2,786物理行，保留SMOKE/COVERAGE重叠、raw/report hash、request fingerprint、单位与原捕获时钟。所有请求与行QUARANTINED/BLOCKED；typed1.0.1-diagnostic。Staging是验证后的请求/响应投影，没有写市场表或发布DataEnvelope。 |
| T3 Bars/calendar | 492日历日、327开市日；三股各327 raw bars/327 factors、无观测重复/缺口，OHLC/Decimal/量额检查完成。仅13个SSE日历事实与3个证券代码参考比较一致；空停牌响应UNKNOWN，单位身份及数值第二来源未证明。 |
| T4 Factor/action | 8变化点均有同日dividend观测，其中5点多原始行语义未解决；8项pre_close因子参考非零差异。精确有理数计算、不猜容差、不生成action、无权益账本或权威复权价格；PARTIAL。 |
| T5 Financial | 63观测、45证券/报告期组，每股15报告期；14多观测版本组，仅1组指标差异，均不证明修订时间序列。6越界行和3宽窗完整BLOCKED响应保留。DATE_ONLY保持字面量/null published_at，不补午夜、不回填historical available_at。 |
| T6 Fixture chain | 6次固定synthetic链执行，BASE/revision各两次确定性回放；Packet→Draft→Assessment→nativeCard refs/hash/version绑定，版本变更、截止/TTL、Receipt/Policy撤销阻断。全部为NON_SECURITY/NON_ACCOUNT；真实Card/model调用/链执行写入均0。 |
| T7 Eight-category dry-run | 八类分别给出工程准备、原件范围和阻断；零policy/SourceObservation/admittedClockEvidence/真实Snapshot/Receipt/Packet/Card签发。C12–C22新增业务关闭0。 |
| T8 Independent review | 第一新Reviewer134主断言PASS，另4个期待拒绝却被接受的synthetic反例保留；发现2处P2新入口缺口。修复仅限new typed text guard和fixture options snapshot，旧核心不变。工具内容审查曾两次中止；最终限定复核104/104 PASS，四反例已拒绝。两个计数分开，不能冒充最终全量重新攻击。 |
| T9 Gate/rollback | 534=533PASS/0FAIL/1原可选V5SKIP；7主要产物最终epoch双回放一致。430旧immutable字节核验，3导航更新允许。新Gate/索引/Git-only bundle/checkpoint归档后STOP。 |

真实读取来源仍为TUSHARE_MONTHLY_GATEWAY/OWNER_PROVIDED_MONTHLY_GATEWAY。Owner声明15000积分月卡不替代真实账户、销售主体/授权渠道、订单/产品、精确expiry和用途许可证明；当前expiry2026-11-05 DATE_ONLY仅Owner声明。API返回成功不是entitlement inventory、许可、历史PIT或云传输权限。既有SSE本地参考链仍PARTIAL。

财报日期按官方接口参考的报告期语义检查，未把请求start/end改成公告日来消除范围异常。[fina_indicator官方参考](https://tushare.pro/document/2?doc_id=79)只用于字段语义，不认证网关。公司行动/factor连接为观察关系，未按因子推导权益；[dividend](https://tushare.pro/document/2?doc_id=103)、[adj_factor](https://tushare.pro/document/2?doc_id=28)同样仅是产品参考。

真实研究仍需：具体source/product/purpose及storage/retention/transfer许可；真实身份/权益/有效期原件；financial越界过滤说明、公司行动多记录/复权参照与rounding政策、行业空结束日期语义；完整状态/停牌/ST、财报和公告修订、行业PIT及真实新数据lineage。历史回测还需独立历史首可见证据；现在能查历史不能反推过去可见。真实Snapshot B尚不能构建。分钟/公告独立权限是否购买本轮不作决定，没有购买或绕过。

所有30项真实账户/本金/券商费用/风险保持UNSET_REQUIRED，实际概率、Edge、sizing/calibration未赋值。C30至少20个实际交易日forward Paper仍是日历约束，fixture时间不是真实Paper天数。Schema6/SQL001–006、旧contracts/releases/Gates、V5实验/14日ledger/seal/旧DB/runs保持；V5从未映射成CORE_40或EVENT_3。

本轮只交付新工程分支，不push、不部署、不启动GUI/策略优化或真实Research Agent。下一步先审本Gate与供应方事实；只有另一次明确Owner授权及独立前提满足后，才讨论具体LOCAL_REAL_RESEARCH准入。Pilot、cloud、historical、redistribution、broker、production仍BLOCKED。到此STOP。


验证入口为 `node overnight/check.mjs`；原package/lock及CI文件不变，未运行远端CI。534唯一项分解：451原未改测试+12原业务断言经新受限文件绑定运行+14新增路径安全项+57本轮新增项；旧463、重复回放及Reviewer134/104不重复累计。新 Schema 只有诊断合同，没有业务SQL迁移或SourcePolicy升级。

新目录：verification-portability/、overnight/{data,analysis,fixture,admission,tests}、contracts/{verification-portability,overnight}、两个新ADR及docs/overnight。新release1.8.2；typed1.0.1；Readiness1.0.0；原1.8.0/1.8.1候选和所有失败原件留存。旧完整绝对路径入口未改，用新严格绑定入口处理可迁移检查。

[机器Gate](Gate.json)、[验证](validation.json)、[7份主要私有产物hash](evidence.json)、[确定性回放](deterministic-replay.json)、[C12–C22 delta](conditions.json)、[已知问题/失败保留](known-failures.json)、[第一独立实测证据清单](First-Independent-Review-Evidence.json)、[最终限定独立报告](Independent-Functional-Review.md)、[完整交付索引](artifact-index.json)分别可核验。独立报告只确认已列功能边界，不提供任意恶意JavaScript/文件系统竞态的全面安全证明；额外hidden/symbol keys与getters被拒绝，已知键的non-enumerable data descriptor可被固定读取。

代码候选55cb391的凭证审计（2026-10-05T16:50:20Z；随后归档文档另核对）2528文件/578Git blobs实际匹配0，未分类generic匹配0（22文件为明确SYNTHETIC）；没有Token或Token hash输出，密码提示0。诊断/Reviewer不查凭证；父控仅为RAM边界审计读取，原生缓冲释放。Git-only回滚包和最终HEAD/clean状态见[外部交付检查点](/Users/qiushi/投资研究/.p1b-archives/overnight-20261005/delivery/Delivery-Checkpoint.json)，不含raw/credentials/运行DB。
