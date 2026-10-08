**Wave B 独立只读 Review — G4**

候选 `a2abc62d641388dd8298e7e31c8ee916fdb9c546`，release `1.9.2-wave-b-candidate`，产物 `CANDIDATE-G4`。结论为 **PASS_WITH_CONDITIONS，仅受限工程检查**。实际独立攻击覆盖30类，191条断言全部通过（Python126，真正 native65），关键错误接受0。另实际执行 `node wave_b/check.mjs --new-only`，124 Python +11 Node =135项，135PASS/0FAIL/0SKIP，exit0。两组计数分别报告，不与总控669项或先前候选累加。

source_admission、Research/Pilot/cloud/history/model/broker/production等上层Gate仍BLOCKED；historical_visibility_proven=false，productionGate=false。供应商、产品、许可、正式权益和可信传输无可验证证明。HTTP200/code0、Owner15000、技术覆盖或Review通过均不是准入。实际Policy/Receipt/Snapshot/Packet/Assessment/Card/Candidate/Signal/Approval/Order签发数均0；30账户参数仍UNSET_REQUIRED，真实Snapshot B不因本报告就绪。

**前一候选真实失败及Reviewer口径修正均保留**

`77abd49f4d1dbb8bf253ce5e9854c97ded086562` / release1.9.1 / G3保留 **FAIL**。原Python98断言=97PASS/1FAIL：在RAM中仅替换 `docs/overnight/conditions.json` 单一文件读取结果并加一字节空格，真实原件未改；已注册候选经 `core.require_result` 仍被接受。该条件baseline来源未进入input identity/runtime依赖，是有效类别30绑定缺口。新core把481旧不可变文件、baseline/start checkpoint/release原字节和新列出code/schema/rule pins全部绑定。G4原反例及旧AccountProfile schema、新AdmissionCandidate schema、namespace rule、baseline/release/checkpoint变化、加载前来源变化都实际拒绝。

原native65断言=64PASS/1FAIL，其中另一个失败为Reviewer过宽测试口径：我把纯synthetic描述句 `SYNTHETIC keychain_service=PRIVATE_REF` 误当必拒真实隐私引用。原生importer允许其进入fixture-only描述性ResearchDraft；没有实际配置的Keychain引用、凭证、Packet/报告泄漏或实际写入。原v1脚本/精确日志/失败matrix保留；v2改用明确敏感字段、约定引用或伪凭证标记。修正后的G3 native65/65单列，G3仍因真实类别30缺口FAIL。最终191PASS不能掩盖原始失败。

**实际30类记录**

每一数量是具名期待—实际检查的断言/case记录数。同一请求的多个检查不冒充新网络调用、独立市场事件或额外回归测试。机器matrix逐条保留expected/actual及关键错误接受字段。

| 类别 | 攻击范围 | 断言 / case记录 | PASS / FAIL |
| --- | --- | ---: | ---: |
| 1 | Raw 单字节与来源变更 | 3 | 3 / 0 |
| 2 | HTTP200/code0、Owner15000 不等于准入 | 6 | 6 / 0 |
| 3 | provider/license/transport 自报 true | 9 | 9 / 0 |
| 4 | OFFICIAL 别名 | 5 | 5 / 0 |
| 5 | 响应 symbol/date 越界、未知 ann 整体阻断并保留 | 13 | 13 / 0 |
| 6 | available_at 历史回填 | 2 | 2 / 0 |
| 7 | DATE_ONLY 虚构午夜 | 1 | 1 / 0 |
| 8 | historical_visibility true | 4 | 4 / 0 |
| 9 | daily adjusted 污染 | 3 | 3 / 0 |
| 10 | 股/元单位猜测与校准 | 6 | 6 / 0 |
| 11 | 空停牌 UNKNOWN | 3 | 3 / 0 |
| 12 | 空 ST UNKNOWN、合法 ST 观察保留 | 5 | 5 / 0 |
| 13 | 多 dividend 原件合并 | 3 | 3 / 0 |
| 14 | factor 推导 action/权益账 | 3 | 3 / 0 |
| 15 | exdate 后捕获回填 cutoff、复制对象与当前名称历史 | 8 | 8 / 0 |
| 16 | REPORT_PERIOD 不替代 ann_date | 4 | 4 / 0 |
| 17 | is_new 历史回填 | 2 | 2 / 0 |
| 18 | in_date 作为 available_at | 2 | 2 / 0 |
| 19 | quarantine 注入原生 Packet/Assessment/import | 6 | 6 / 0 |
| 20 | 原生 Card/Candidate/Signal/transition、真实写入零 | 13 | 13 / 0 |
| 21 | real/synthetic 混合 scope | 5 | 5 / 0 |
| 22 | EVENT_3/Research namespace 越界 | 6 | 6 / 0 |
| 23 | 敏感引用字段/伪凭证标记及原生导出 | 10 | 10 / 0 |
| 24 | redirect/proxy/fallback 的无发送模拟 | 5 | 5 / 0 |
| 25 | 非 allowlist/MCP 探索请求的纯拒绝 | 3 | 3 / 0 |
| 26 | 未知费用、REAL_NET_EDGE/SIZING | 14 | 14 / 0 |
| 27 | LLM/HUMAN_USER 伪审批 | 5 | 5 / 0 |
| 28 | production/broker true、执行状态零变化 | 11 | 11 / 0 |
| 29 | 同 inputs/rules/code 双 replay hash | 5 | 5 / 0 |
| 30 | source/raw/rule/code/schema/归档绑定失效 | 26 | 26 / 0 |

**真正native边界与零写入**

使用真实 `buildBrainPacket`、admission service registerPolicy、`assessSemantics`、`importResearchResult`、`stageContractFixture`、`assertDraftTransition`、`validateOrderChain`、`productionGate`、`writeManualExport`、Cost Engine和原合同验证器；没有用Wave B always-reject helper替代native检查。内存synthetic DB和合法签名fixture作positive control，合法纯fixture路径确实可产生非交易ResearchDraft，但real_net_edge/real_sizing仍UNSET_REQUIRED、tradeable=false。

实际quarantine候选、非admitted evidence_ref、混合真实/synthetic snapshot、缺失quarantine root引用、跨namespace、伪审批和production声明都被原生接口拒绝。ResearchCard持久化写入增量0；22个研究卡/信号/审批/订单/成交/持仓/账簿等执行状态表前后全0；拒绝export没有创建目标目录。复制observation、复制候选、自行reseal及effective/ann/in_date回填cutoff均没有获得历史权威。

空ST/停牌在自构造空响应和实际空blocked响应中均UNKNOWN；合法ST观察保留而不授予历史完整性。current name不回填历史；未知namechange ann_date阻断整份响应并保留原行，未知边界不填无穷。dividend原件不合并，factor不造action/权益账。REPORT_PERIOD不替ann_date，is_new不证明历史可见。

**只读与原字节检查**

最终HEAD再次读取仍为完整a2abc62候选。攻击前后检查636个source/raw/code/rule/schema/产物路径SHA-256，两个map完全一致；native与新回归结束后的首次再次检查也一致。随后父控合法整合 `docs/wave-b/known-failures.json` 审查元数据，final组装严格断言因此失败一次；该组装日志元数据单独保留。最终明确排除此未列入release源码pin的动态元数据，**其余635个原source/raw/code/rule/artifact路径仍完全一致**。final pin map保留唯一known-failures的前后hash差异和父控授权更新原因，没有误报为Reviewer写入或隐藏字节变化。

检查覆盖旧不可变基线、新release、start checkpoint、旧44+新55 raw/捕获报告和G4产物。mock仅替换RAM单一读结果，真实raw/code/seal/ledger不写。源对象只用copy或synthetic内存DB。Reviewer输出仅在本Git外目录，所有文件0600，无repo/Git变更。独立攻击的网络/model/broker调用0，未查凭证、Keychain或environment value，未调用capture/_send。redirect/proxy/fallback/MCP只做纯callback/spec验证；sender无proxy声明仅静态读取。另按授权运行现成新阶段回归。初始系统git因Xcode许可exit69，只改用现有可执行文件作只读rev-parse，不改许可。

**范围限制与停止**

不证明任意恶意Python monkeypatch、原生系统权限、任意filesystem race或全面远程CI安全；不证明供应商/许可证/产品/账户权益、HTTP可信传输、历史首次可见或财报修订时间。通用synthetic描述文字不是全部禁止。原生验证只用内存fixture DB，不是实际账户/真实研究producer。旧534回归未由Reviewer再次运行；旧不可变来源字节已复核，总控669回归/freshcheckout单列。G4路径绑定仅固定且未移动的Owner私有归档，不声称任意归档迁移。

机器总矩阵 `Independent-Review-Matrix.json`；逐条实际日志 `a2abc62-G4-python-exact.log`、`a2abc62-G4-native-exact.log`、`a2abc62-G4-new-regression-exact.log`；pins `a2abc62-G4-pins-before.json`、`-pins-after.json`、`-pins-final.json`。G3原始失败、v2口径复验以及报告组装失败另存原epoch文件。执行脚本 `independent_attacks_v2.py`、`independent_native_attacks_v2.mjs`；原v1保留。完整文件sha/bytes/0600清单见 `Independent-Review-Evidence.json`。

Review已完成并停止，没有放行下阶段权限。
