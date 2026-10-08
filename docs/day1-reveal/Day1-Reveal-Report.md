# MetaSurvey Day0 保全与 Day1 Reveal 验收报告

日期：2026-10-08，Asia/Shanghai。本报告截至本轮午间核验；未取得当日真实 EOD 原件。工程验收 **PASS_WITH_CONDITIONS**；真实 D1 **BLOCKED**。按 Owner 指令完成到明确阻断后停止，没有设置定时任务或自动进入 Day2。

## 1. Day0 原件核对

当前唯一原预测仍为 `ForwardPrediction-v1-OWNER_TEXT_IMPORT.json`，4146 bytes，SHA-256 `954569db8402e2e50e66841c1a449523c72f20ff1ce364d6183c4d3c7a018039`。逐字节重开核对，文件保持只读，未修改、格式化或重新生成。source text 24864 bytes，SHA-256 `f990215f49d5b572f17c7b4eacbf203243268783b324b7dadd02637f48f95b60`。

前次验收 ZIP 2855891 bytes，SHA-256 `6502262756081c70d7af0e0bc4d7b494851238eaca5a99f4b70a4f04efed78e5`；32 个成员 CRC 完整，31 个 payload 的 bytes/SHA 与 Package Manifest 全部匹配。旧 Freeze Receipt 和 ForwardPrediction/ForwardOutcome schema1.0.0 与原包字节一致。任何 mismatch 都会 STOP，不进行修复。

旧 external artifact `7718b46d2d3f281fe574215ce347caedca8b2355033551774d6febc181067072` 仍为 **ORIGINAL_NOT_PROVIDED_HASH_NOT_VERIFIED**。它不是当前新预测哈希。原记录冻结时刻为 2026-10-07 23:01:37.602020 +08:00，只是本机时钟证据；没有独立时间戳/TSA，也没有可验预测 detached signature。未改旧 receipt 的三个 false 字段。D20/D40 仍 UNSET，冻结 horizon 仅 D1/D5/D10；未制作任何新的 Oct8 pre-open v1 或 v2。

## 2. 固定 Reference A 基准价

固定 A 原件、3 个 vendor response 的字节/SHA、证券和 20260930 日期均已重开；每只证券只有一条该日期匹配记录。

| 证券 | 冻结假设 / 原始 raw close，元 | 核验 |
|---|---:|---|
| 603993.SH | 16.88 / 16.88 | PASS |
| 600312.SH | 20.29 / 20.29 | PASS |
| 603228.SH | 101.21 / 101.21 | PASS |

这只关闭本轮“基准假设是否与固定当前原件匹配”的问题。数据在 Oct5 取得，不能证明 Sep30 或历史各 cutoff 当时可见，不能证明供应方、license、corporate action 或调整后 total return。未回写原预测的 unverified 字段；新的核验单独保存。

## 3. 公开登记及签名缺口

实际 Owner 安装的 enrollment 已重开，SHA-256 `0278b10f426f6484e1fdb428961364feb8e309d1276f301dc18572a6f802f677`。两人是此前 Owner 确認的另一位真实独立审核人和本人；没有重问身份，没有替任何人生成或保管密钥。公开登记声明保留原字节与哈希。身份/独立保管是已有 Human 声明，验签不等于第三方身份认证。

| 角色 | 公钥文件 SHA-256 | 实际核验范围 |
|---|---|---|
| Owner | 3374e1b962dea302d3bb24918cf573b6a6ca7583de9c83f1720faed4e36c128a | 原 setup 签名通过；改动 body 后拒绝 |
| Independent Reviewer | c415df6c2fc5504afee0df54e92ebc5f6ecdbe1004a7044e81a11503bf16fb0f | 原 setup 签名通过；改动 body 后拒绝 |

新包包含两份44-byte公钥 DER、实际 enrollment 原文、公开登记声明、双方原 setup body/64-byte signature、Public-Key-and-Signature-Gap 和独立运行所需的 public-only audit 脚本。可用 OpenSSL3 在解包的 public 目录复核。原 enrollment 的本地引用路径保持原样，解包不会把它安装成审核者机器的信任根。

**预测 detached signature、实际 CAPTURE signature、独立 REVIEW signature、Owner FORWARD signature均尚未提供，未验证。** 新生成两份 unsigned `POST_OPEN/LATE_ATTESTATION` body，仅确认当前原预测哈希，不授予 capture/review/forward/trading。没有调用任何私钥，没有假造签名，没有 pre-open signature 或独立签名时间的声明。可选补签必须由两位 Human 在各自设备完成，只返回公开 signature；这不会补成历史时间戳，也不会代替 Day1 的三份执行签名。

## 4. Day1 执行与评分

截至核验时仍在 Oct8 收盘前；本机时间或计划日历不能代替实际收盘原件。未取得真实 EOD witness、真实采集 manifest/raw/clock、独立 Review、Snapshot B、单独 FORWARD 或已接受的实际 G store。注册基线 actual_forward_days=0；本轮增量=0，没有创建实际 store。未穷举电脑上所有未登记文件作为执行证据。

| 证券 | D1 冻结区间，% | 冻结中心，% | 真实 return | direction / range hit | center error | MAE / MFE |
|---|---|---:|---|---|---|---|
| 603993.SH | [-1.0, +3.5] | +1.2 | PENDING | PENDING | PENDING | PENDING |
| 600312.SH | [-1.0, +2.5] | +0.7 | PENDING | PENDING | PENDING | PENDING |
| 603228.SH | [-2.5, +5.0] | +1.5 | PENDING | PENDING | PENDING | PENDING |

所有实际指标都为未知，不使用零、false、模拟价或盘中数据填补。`ForwardOutcome-D1.jsonl` 目前0 bytes/0条，是明确标记的待追加研究 journal；它不是 Snapshot B，不是已评分结果，也不会增加真实天数。未生成任何“空的 Snapshot B”冒充完成。

新增 adapter 保留冻结 G 合同：**真实 open/EOD 原件 → plan → Owner CAPTURE 签名 → 凭证/只读采集 → 独立 Human 原件复核和 REVIEW 签名 → Snapshot B → Owner 单独 FORWARD/head签名 → exactly-one NO_DECISION**。附件的自然语言箭头不会把 CAPTURE gate 改成事后授权。只有 frozen G inspector 重开并验证全部三份签名、实际 accepted session==1、Oct8 matching snapshot 后才允许评分。只含 Capture+Review 的 Snapshot B 不够。

独立研究合同 `Day1RevealOutcome` 1.0.0 明确记录 Owner 要求的 prediction_sha256、verified base close、target close/high/low、realized_return、direction_hit、range_hit、center_forecast_error、MAE/MFE、Capture/Review/Forward验证结果、scored_at、outcome_sha256、previous_hash、expected_head，以及原 G record/head、原件/clock reference。价格是 Decimal 字符串 CNY/share，return/MAE/MFE 是 percent，center error 是 realized−center 的 percentage points。MAE=min(0,low/base−1)，MFE=max(0,high/base−1)，均×100；raw-price excursion 不是策略 P&L、组合最大回撤或费用后收益，action reconciliation 仍 UNKNOWN。

JSONL 每次重开旧链并重评分原件，expected head 校验、独占锁、去重和 fsync 后只追加；截断行保留且 STOP，不自动修复。不能迁移已使用 journal 的路径，因为 genesis 与原绝对路径绑定。不声称抵御已被控制的操作系统、解释器或本机管理员。

D5 固定 Oct14 EOD，D10 固定 Oct21 EOD，仍未观测/评分。若实际日历推翻 mapping，只记 TARGET_SESSION_MAPPING_DISPROVED 并提出显式新版本，不改v1。D10 ordinal=603993>600312>603228，并保留后两股 center=3% 数值 tie；没有新 tie-break。

## 5. 历史线 / PIT

历史线继续是 RETROSPECTIVE_DIAGNOSTIC_ONLY / FORMAL_OOS_BLOCKED：4905预测位置，4677非warmup数值预测，228warmup；4677可观察标签，228右截尾；4449配对。327已暴露session/股，选定三股有生存者偏差；不是 untouched walk-forward OOS。历史算术不是完整策略回测、净收益或Edge。原 frozen预测与after-freeze标签按原字节纳入新本地包，解决前包缺少逐条算术材料的问题；vendor raw originals 仍在外部本机引用，包本身不能完整重证供应方/PIT。

新 PIT register 保留全部60行原 baseline entries 和理由，canonical rows hash一致，20个domain仍0关闭。新增行动优先级 PRICE/CALENDAR → STATUS → ACTION → FINANCIAL → ANNOUNCEMENT → INDUSTRY → UNIVERSE/LICENSE；明确 per-cutoff availability、first-visible、修订链、有效区间、证券适用性、单位与许可所需证据。其余 benchmark_total_return、valuation、dated_cost/account、economic_policy 继续保留 BLOCKED，没有删项或补默认值。新 Sep30基准价验证只提供当前原件匹配，不能关闭历史可见性。

当前没有独立可验证的供应方/销售主体、产品和有效期、用途/retention/storage/transfer授权材料；当前可调用 API 不等于 license admitted、historical PIT proven 或 cloud permitted。Formal backtest 仍 BLOCKED，没有新历史下载、参数优化、只留最佳版本或策略改动。

## 6. 检查、保全及限制

本轮相关离线测试：24新增 +25原 dual-track +87原 H-B Python +143原 H-B Node = **279 cases PASS，0 FAIL，0 SKIP**。51新增及35原 schema atomic assertions 单独计数。双方 setup 验签各一次及改动body拒绝单独记录，不凑测试数。冻结 G 正向模拟 fixture 只证明代码行为，真实签名的 D1 positive path 没有跑通，未获得独立 Human 对本轮原件的 REVIEW。

首次测试24项中18通过、3失败、3错误：macOS /var→/private/var 与fixture canonical path不一致；修fixture，不放宽journal路径门禁。第二次22通过、2错误：mock共享score字典被metadata污染；copy结果后再加journalmetadata。原失败日志全部保留。未改PIT、费用、审批或执行门禁来通过测试。

全部926 predecessor tracked files、1858 evidence dependencies、26 frozen code pins零mismatch，原预测/source/receipt/enrollment和旧ZIP未动。16native contracts、001–006迁移、数据库schema、依赖锁、两套冻结strategy、V5 seal/ledger保持原状。新内容仅独立工程代码、1.0.0研究metadata schema、ADR-037、授权/运行说明、状态与外部证据。新artifact并不取代旧状态文件。

最终代码候选 `932edc2ce63041141655d430cfe136a50036a3e9` 已在新的本地 checkout 中重跑上述279 cases，全部通过。使用原锁定依赖和未移动的原private archives；这是本地fresh checkout验证，不是remote-CI/独立Human验收。分支 `day1/reveal-20261008`，最终Git提交由随包Delivery-Checkpoint固定，无远程push。

本轮真实行情请求0、credential lookup0、私钥读取0、签名生成0、实际G追加0、outcome0、Order/Broker/Model/云调用0。测试运行重开原离线证据，未启动现网接口。没有写真实账户30项或额外15项UNSET_REQUIRED；实际cost仍NOT_COMPUTABLE。Fresh clone和最终Git/包校验见随包 Checkpoint/Checks，不把先前255或全量2101重复加到本轮计数，也不宣称全项目CI。

## 7. 本轮 Gate 与接下来唯一必要动作

Day0 integrity PASS，base Reference A PASS，公开登记/原 setup interoperability PASS，工程 PASS_WITH_CONDITIONS；真实 D1 BLOCKED。只在 Owner 本轮签名流程继续时，取得真实收盘事实并由双方依次签署 CAPTURE → REVIEW → FORWARD；随后可追加三条研究outcome。本次生成文件不能代签或授予能力。

Paper/Signal/Order/Broker/Real Money/production data与execution、Cloud、Formal Historical Backtest 均 BLOCKED：尚无可验证实际Day1链及天数、费用后策略Edge/OOS/Paper证据、来源许可/历史PIT、真实account/broker/fees/risk参数和新的对应Owner放行。没有因为公钥配置或单日预测而升级任何Gate。

本轮已到明确 BLOCKED 停止点，等待 Owner；不等待到收盘自动执行，不调度，不自动Day2，不进入下一阶段。
