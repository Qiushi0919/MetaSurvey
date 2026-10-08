# Wave C 新独立只读 Reviewer — G3

结论：**PASS_WITH_SCOPE_LIMITATIONS**。仅审查 frozen code candidate `4b1d0ef8f3ca42cc1cf47881b7286e7d24cdea8a` 与 `REPORTS-G3`；不授予正式准入、历史 PIT、研究 Pilot、云端、审批、订单或生产权限。

实际断言 **287/287**（Python 126，真正旧 native consumers 161）；失败 0，Owner 17 类攻击均覆盖。Reviewer 断言未并入 Golden regression。

## 独立检验的实际行为

- 本机逐一核对三股 Input 的 eligible observations：以 raw hash 找到原件、按原始 fields/items 与 row ordinal 直接比较，不只信 normalization 元数据。所有有值特征的直接 refs 都对应 eligible 原件。
- 独立使用 Decimal 从原始 close/amount 重算十项价格指标，再独立重算真实三股 Quality/Timing 的各组件相对排名与均值；不调用实现中的 raw_statistics/pairwise_rank 作为期望值。没有复权、年化、人民币流动性换算或将 UNKNOWN 填 0。
- 三份机器报告与本地中文报告均保留十维、源/版本/hash/clock 和 UNKNOWN；Quality 仅为 ROE、利润同比、负债率的三股相对实验坐标，不是完整公司基本面评分；Timing 独立来自四种 raw price 结构坐标。缺现金流/盈利质量/估值/经营催化时保持未知。
- 财务整响应排除、同期间数值版本冲突和修订 chronology UNKNOWN 均保留。报告期间没有成为 publication instant。行业无效响应被排除，当前行业声明不回填历史标签；空 ST/停牌响应不构成负证明。action/factor 分开，多原件歧义与 reconciliation UNKNOWN 保留。
- 正常调用公开 register/derive，以及正确 shape、正确 parents 的 private _register 注入，均被拒绝；private helper 正控只能重现原 factory 的完整精确内容。调用者修改 context 副本不改变已有权威；修改 context 或携带任意 body 的 factory 调用不能铸造真实结果。
- 使用未改旧 native 合同、签名 admission、Packet builder、importer、CostEngine、state transitions、semantics 与 order-chain gates。真正 SSE calendar reference 的 VERIFIED/ADMITTED 正控只允许原狭窄范围；正式 stock producer 精确拒绝 `WAVE_C_FORMAL_STOCK_RECEIPT_NOT_REGISTERED`。
- 实际旧 closure importer 正控仅生成明确 synthetic 的 NON_TRADEABLE Draft；真实 sandbox Report 冒充正式合同、refs、Signal/Approval/OrderIntent/订单链均拒绝。LLM APPROVE/HUMAN_USER 注入与 namespace 错配拒绝；高 Quality 配低 Timing 的 synthetic 数学与旧语义反例成立。
- 仅在 RAM 替换 read_bytes 返回值分别模拟 raw、financial/action/factor/industry 版本、rules、code、schema、provider evidence 改变；已注册三报告全部失效。物理原件/代码/规则没有修改。持久化报告重放与另两次 projection 相等。

## Owner 17 类攻击结果

| 攻击类 | 通过 | 失败 |
|---|---:|---:|
| quarantine → formal ADMITTED escalation | 37 | 0 |
| sandbox → formal ResearchCard promotion | 54 | 0 |
| historical available_at backfill | 7 | 0 |
| current industry → historical membership | 6 | 0 |
| empty status → negative proof | 3 | 0 |
| factor → fabricated corporate action | 4 | 0 |
| financial report_date → publication spoof | 11 | 0 |
| future announcement leakage | 3 | 0 |
| score → probability fabrication | 12 | 0 |
| Quality → Timing auto-pass | 8 | 0 |
| high Quality → tradeable | 10 | 0 |
| LLM → HUMAN_USER | 5 | 0 |
| SandboxReport → Signal | 9 | 0 |
| SandboxReport → OrderIntent | 12 | 0 |
| sandbox namespace crossover | 19 | 0 |
| source byte mutation | 15 | 0 |
| rule/code version invalidation failure | 12 | 0 |

## 旧失败与修复，不覆盖原结论

- `48081c0892bb514ef4d5abe19a2b2f390897b604 / REPORTS-G2` 仍为失败候选：正常 public derive 接受调用者伪造 Quality，再让 make_reports 注册包含伪造值的 sandbox Report。formal/production 仍 blocked 不能抵消此 authenticity 漏洞。
- 原攻击脚本、实际 AssertionError 日志、失败元数据以及 Input/诚实 Assessment/伪造 Assessment/伪造 Report 的不可逆 refs 均保存在本私有目录；没有输出真实价格/财务值或复制全文报告。
- review assembly 曾因同时出现四个新未跟踪交付元数据而触发过强的全工作区 clean 前提；原 assembly 脚本/实际失败日志已保存。只读复核669个冻结依赖逐字节相同，明确允许该交付元数据后完成组装；这不改变业务断言或拒绝门禁。
- root 修复后的 G3 使用闭合 producer、fresh context 比对、header/body 全量重算与 private helper 防伪；本审查重新运行全部最终断言，不合并 G2 的结果。root 另外发现的 fresh-checkout 定位失败由 root 保存与验收；本 Reviewer 不宣称自己验收了远端或移动私有证据目录。

## 权限、写入与证据边界

- 669 个去重 raw/source/rule/code/report 文件在审查前后逐字节 hash 一致。所有 review 新文件权限 0600。
- Native executionState 检查的是本轮新建 synthetic PGlite fixture 的 22 个 Card/执行表：前后均 0；正式 producer Input/Assessment/Card 与 real-stock receipt registry 均 0。没有接真实账户 DB，也没有给旧账本或 seal 写入。
- 本 Reviewer 没有读取凭证/Keychain/环境值，没有网络、模型或券商调用；所有真实值和报告仅在本机程序核对，工具输出仅为脱敏计数/hash/固定 reason code。
- underlying observations 仍 QUARANTINED，sandbox 仍 UNVERIFIED_GATEWAY；Provider/License/Transport 未核验，formal admission BLOCKED，historical_visibility_proven=false，productionGate=false，真实费用/账户/grade/probability 仍 UNSET_REQUIRED。C12–C22 不因 sandbox PASS 自动关闭。

## 明确限制

- 独立检查的 score 是已冻结实验公式的实现正确性与来源真实性，不是对公式经济合理性、源数值真伪、单位、许可证、完整公司研究或收益预测的认证。
- 三股小样本相对坐标未校准；原始价格存在 corporate-action distortion；并非实时价格或历史 as-of/PIT 回测。财务首次可见和修订顺序仍未知；企业新闻、订单、估值、现金生成与行业景气仍不足。
- 正式 producer 是 closed EMPTY-stock-receipt fail-closed skeleton。不存在真实正向 Input→Assessment→ResearchCard capability，本审查不能声称其已经可用。
- 拒绝边界的范围为正常模块接口、注册回放与消费门禁。未进行任意恶意 Python/OS 代码、直接破坏进程私有 registry、文件系统竞态、完整网络渗透或 remote CI 安全认证。
- 22 表零写入属于 native synthetic fixture 的实际检测，不能描述为对任意外部运行数据库的扫描。全仓 Golden、全新检出与最终 Git 交付由总控单独验收。

审查完成后 **STOP**；等待 Owner。
