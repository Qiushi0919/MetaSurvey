# H-B A–F 独立工程审查 G3

结论：**PASS_WITH_CONDITIONS**。本结论只接受受限 A–F 工程准备；实际 G 继续 HOLD。真实 Snapshot B 尚未运行，actual_forward_days=0。本审查没有安装实际信任根、生成实际签名键、读取凭据、联网查询市场数据或创建实际状态库。

候选：`98337a5cb55371b2dc8539a601ed90403c343b4b`。Code hash：`sha256:f8721c8e40f993621cf1e1f57d347e06dfa66db1187208f19636f2a2e701c158`。Context：`sha256:112d608f09b5e51407a69952b0da5a0f3c4aeb33a8feffdf5d2f9cd33c7297fc`。26 code pins、116 private pins、1,858 项依赖及 857 个既有文件在审查前后保持相同；另重开 26 个候选 Git blob，均与当前 code pin 一致。H-A 代码/context、native contracts、Schema、锁和 legacy 资产边界未变。

最终完成 **28,515 个原子断言**：Python 14,414，独立 BigInt 有理数费用 oracle 14,101。未解决产品错误放行为 **0**。这些是独立语义和来源断言，不计为 regression 执行；总控完整 fresh-clone 回归的实际结果另报，本审查不把预计数量写成 PASS。

| 审查组 | 原子断言 |
|---|---:|
| Source 前检、旧基线与 bindings | 6,448 |
| Preflight / candidate 公钥 / Owner 模板 / PIT map | 2,078 |
| Budget 停止锁存、顺序与 deadline | 68 |
| Synthetic PIT 四时钟与未来 revision 隔离 | 87 |
| 本地官方费用原件、单位与 map 保留 | 76 |
| 保存 metadata 与 Source 后检 | 5,657 |
| 独立 BigInt Cost oracle | 14,101 |

Preflight 只展开固定三股、最多 13 个只读请求；planned-session 字符串不是 actual witness。捕获、独立 Review、另行 Human Forward 的角色和签名没有被合并。Source/hash/metadata、公钥形状、自述 outside-producer/fixture=false 和 LLM APPROVE 都未产生 actual authority；actual/native/cloud/production 接口保持阻断。

30 个真实账户/费率/风险字段及 15 个补充 Owner 字段仍 UNSET_REQUIRED。费用引擎仅可计算明确 SYNTHETIC_FIXTURE，缺项/UNKNOWN、非法日期/单位、重复费用、滑点双算、ACTUAL_ACCOUNT 或 production 模式全部 fail closed。独立有理数 oracle 核对 640 个买卖 quote 和 200 个 round trip 的逐分结算、累计 partial fills、每订单最低佣金、费用包含和费用后现金变化。没有把旧实验费用或法定参考自动写入账户。

6 个官方费用原件只在本地重开，未重新联网。SSE DOCX §3.1.1 支持 A 股竞价双向 fraction 0.0000341；法条支持卖方征税，JPG 税表目视末行支持 base 0.001；结合减半公告支持 reference 0.0005。日期/适用范围与 URL 迁移不同，effective_to 仍 UNKNOWN，当前 retrieved_at 只证明当前收到，不能成为历史首可见。

PIT Git 文件现为 3,336-byte 机器索引；1,732,906-byte 完整地图在 private MAP-G2 保留，并与 a04 原 Git 对象、build_map 逐字节相同。20 个域、183 个冻结输入、174 个旧报告特征实例、1,699 个原件 refs 没有丢失；连续历史域闭环仍 0。旧 PIT delegate report/manifest 的 docs refs 是其交接时代原 map/hash，不能声称等于当前 index 路径；原字节通过旧 Git 和 private map 重开。

两个真实的离线 Budget 缺陷已经修复并独立拒绝：G1 错误阶段开始后没有锁存 STOP；edge-G2 第二次时钟读跨过 whole deadline 时 begin 返回负 limit。最终会锁存 invalid begin/finish、clock、supervisor/timer/body/cleanup 失败；timer arm 前再次检查，原 handler 恢复，消耗阶段不能自动 retry。原源码/反例均保留，没有放宽业务门禁。

审查器失败也保留：G1 错读 witness 子合同 version；旧 review-G2 在候选推进后 HEAD 前检退出而 superseded；G3 前置 Git cwd 错误导致 Python 未启动；G3b 旧式文本 fixture 被最终结构化 proof binding 正确拒绝；G3c 审查器变量覆盖导致 AFTER 检查前 KeyError。新的 G3d 完成全部来源前后与语义检查。这些失败不是产品假放行，未改产品、旧 seal、历史原件或测试门禁来通过。

实际 G 的缺项仍是：外部不同 Owner/Independent Reviewer 公钥和身份/保管证明、真实 observed open/EOD 原件、固定 Keychain 运行时可用性、当前 Capture 签名、独立原件重开的 Review 签名、另行 Human Forward 签名及实际 expected head。当前代码审查不能替代这些 runtime authority。Budget 是可信 operator 阶段监督工具，实际 transport/签名/正链及真实库 restart 尚未验收；没有 scheduler 或 Day 2 自动授权。

Provider/License/Transport 的 8 维、正式历史 PIT、真实费用 admission、Edge、native 交易对象、Broker、真钱、Cloud/model/export/redistribution 与 production 继续 BLOCKED。没有 host/interpreter/key-compromise、远程 CI、archive 迁移或凭证全域不存在证明。

完成动作：**STOP，实际 G 保持 HOLD**。
