# Wave H-A 独立审查 G2

结论：**PASS_WITH_CONDITIONS**。审查对象是冻结候选 `5996a76b8442fe55458c6cdae5686d6024e2080c`。工程准备通过；H-B 的真实捕获、实际 Snapshot B 和 Day 1 没有执行或放行。

10,403 个独立原子断言通过，包含 10,041 个来源/基线完整性断言与 362 个权限、原件、时钟、状态、事务及显示检查。它们不是产品回归执行数；完整 fresh-clone 回归由总控单独统计。1,697 个运行依赖和 812 个不可变前序文件均在审查前后保持相同字节、大小和 hash。代码 hash `sha256:395f3ea17166811173dfb940c88347aa545b8682e662f6dc4987fc5fd3440184`；context hash `sha256:5159515509c7cf5959a2c572af9981ba4fa886d5ec7a911d56ff3e9c3b655096`。

## 已关闭的独立发现

- 原候选的独立解析器接受了 collector 已拒绝的 malformed stock_basic、suspend_d 和负 pre_close。原始反例完整保存；最终解析器拒绝各类重新封装的原件，也严格要求 witness_source 与 Reference A capture_id。
- 原权限有效期谓词未要求 issued_at 不晚于真实时钟，并把纳秒截为微秒。最终纯时间窗检验保持整数纳秒，拒绝未来签发、提前生效与到期边界；已接受的旧公开签名按原 issued_at 验证，不把正常到期改写成过去无效。
- 原新 H 显示对象仅浅冻结，内部 actual_forward_days 可被篡改后继续显示。最终递归冻结；独立 JavaScript 攻击无法改成 99，原生转换仍阻断。
- 单次 fresh-series 操作手册已改为先在独立 H-B 授权与外部 enrollment 下创建空 store、读取 genesis head，再签署绑定该 head 的 Human Forward grant；现有 series 不创建或覆盖。

G1 原件、旧候选代码和反例仍保留。首个 Reviewer schema harness 因脚本导入路径缺失失败；使用显式项目路径的第二份日志验证反例，第一份失败日志未覆盖。时钟反例是纯 shape/有效期谓词观察，未安装权限或颁发能力；其 body code_hash 来自并发修复时的稍后观察，不能伪称为完整冻结候选 grant。显示反例也诚实标记为稍后 metadata 观察。

## 最终验证范围

分别攻击 Actor/HUMAN/LLM、自签摘要、调用者公钥、fixture 签名、复制/未颁发 handle、Capture/Review/Forward scope、代码/策略/政策/基线/来源 schema 变化、date-only 与四钟混淆、publication/available_at 伪造、缺股/错股/错日/缺 job/超范围、状态 UNKNOWN 提升、原始 SHA 改动、费用及真实资金配置继承、native/订单/broker/cloud/formal history 路径。所有被测试的越权输入被拒绝，没有实际假接受。

独立新建 OFFLINE_SIMULATION fixture/store 完成同一 head 并发竞争、只成功一次、重复/陈旧 head 拒绝、sanitized failure chain、外部 SQL 修改拒绝、重启原件重开、read-only recovery 和第二个新 session 追加。2 个模拟 session、1 个失败尝试；actual_forward_days 始终为 0。固定策略/政策/schema/A series 保持一致，而逐日响应 SHA 正常变化。该私有 SQLite 是明确的审查模拟资产，不能作为 actual store。

六份 SSE 官方 HTML/DOCX/DOC 原始返回分别重新读取并独立提取文本，核对八条新增结构性事实。没有以原团队 parsed.txt 或搜索摘要替代原件。URL 路径日期不是发布时间；2020 notice 日期、暂缓条款、首日规则、风险警示/退市阈值、除权参考价与因子/现金链区别均保持原语义。连续历史域关闭数仍为 0；逐证券适用状态、触发日、版本区间、历史首次可见性及正式价格/财务 PIT 继续缺证。

六份 readiness 私有产物与 Git 文件逐字节相同，canonical 内容 hash、代码及 context 绑定一致。30 项真实账户/费用/风险参数继续 UNSET_REQUIRED。未修改 repo、旧业务规则、账本、seal 或既有 DB。未安装 enrollment、生成 actual handle、读 secret、做网络请求、执行实际捕获或计日。

## 条件与实际证明边界

外部 Owner/operator 公钥安装及签名私钥保管是信任根；程序拒绝普通调用者提供的键/角色，不能独立证明被盗签名键背后的人类意图。未证明能抵御宿主机所有者、Python interpreter 或文件系统特权篡改。

实际签名正向链、真实固定 HTTP transport、实际 Snapshot B、actual Forward store 尚未运行。本次验证证明实现及离线隔离路径，不能声称完成实时端到端认证。H-B 仍需 NEW Owner 指令、独立不同公钥、真实 observed open/EOD 原件、新鲜 exact-three 返回、固定 Keychain credential 可用、独立审核签名、单独 Human Forward grant。

Owner 签名的 actual-session witness 是 Owner 的当前观察与原件边界，不是独立供应方证明或历史 PIT。HTTP 网关仅有明确 LOCAL exception；Provider/license/transport 仍 UNKNOWN/BLOCKED。真实资金、原生 Signal/Approval/Order/Fill、broker、云/模型/转发、formal backtest 与 production 均未获准。

旧可选 V5 回归依赖另行提供的外部资产；不能把 SKIP 解释成已经证明资产物理不存在，也不能用独立原子断言代替该回归。

已 STOP。总控完成自己的最终 fresh-clone、Git 与验收交付；不得自动进入 H-B。
