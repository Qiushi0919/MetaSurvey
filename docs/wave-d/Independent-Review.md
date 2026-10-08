# Wave D Independent Review — G4

结论：**PASS_WITH_CONDITIONS**，只适用于三股本地 current-observed 研究工程。Owner 的正式阶段批准与数据准入不由本审查签发。

冻结候选：`51771e9a4ac70f417d70b04f7833d8b463ad8712`，基线 `4403985`；release `2.0.0-wave-d-local-loop`。报告固定为 `REPORTS-G4`。本审查只读代码、原件及固定产物，输出仅写入本机私有 review 目录，未读取凭证、联网、调用研究模型或券商。

## 实际验证结果

共 **413 / 413** 项实际断言：217 项 producer / 原件 / Decimal 财务与价格、172 项 native 消费端、24 项独立 SSE 原件和边界。PASS 413，FAIL 0。父级完整回归结果单独计数；G3 旧运行、重复生成与历史审查不加入本次断言总数。

563 个不可变基线文件、28 个候选代码 / schema / rules pin，以及 791 个去重原件、依赖和产物 before / after SHA256 一致。新交付文档和3个导航入口不在这些代码原件 pin 中；本审查不声称最终 Git 工作区干净，最终提交由总控核验。

## 正向控制与真实数学

三股 Input / Assessment / Report 加 Comparison 共10个注册对象可由真实固定来源链重建；4份人类报告及10份机器产物逐字节对应本次重放，完整 proof 保留。所有实际 gateway 行均逐字段核对原始响应 fields / items / ordinal，完整财务原件的9个请求确实包含94 / 158 / 97个官方字段，具名研究投影与原件对应。

财务预期由审查脚本直接从原始行分组、比较 Decimal 数值并计算，而不是从 financial helper 取预期。单独核验收入 / 合并利润同比、CFO / 同期合并净利润、现金减资本支付代理、负债率、应收 / 存货相对同期YTD收入；同比基期、不同report_type / comp_type、现金期错配、修订冲突、非正分母和缺失都有独立负向测试。归母利润不充当合并现金转化分母，季度 / YTD不冒充TTM。估值只保留来源声称的 PE TTM / PB / PS TTM 等以及未验证单位。

十个保留 raw 价格指标独立重算；各股327个复权诊断点逐点以原价和来源因子独立计算。raw未被覆盖，5处公司行动歧义与8个非零pre_close参照差额继续保留；同供应方数学一致性不转成独立权益验证。原 Wave C Quality / Timing 及 cutoff精确保留，新的财务事实不回填旧坐标，也不形成总分、BUY / SELL、概率、评级或Edge。

SSE 三股索引的 TITLE / SSEDATE / SECURITY_CODE / URL 及报告 ordinal / hash直接与原件对应；无需使用 normalize_index 的输出作为预期。6条实际官方301仅到同路径static.sse.com.cn，记录的正文均非有效PDF。索引标题只证明条目，正文催化继续 UNKNOWN。新 current stock_basic 行业声明存在，historical industry membership仍UNKNOWN。

## 实际攻击与 native 闸门

公共 register / derive、正常形状的私有 _mint caller body、篡改 context、伪造 upstream copy / capture /旧report、live _UPSTREAMS 内容改变、复制 /重封对象均不能获得 producer 认可。返回 context 的修改不改变注册权威；每次调用重新核验依赖，同一 context 先通过后修改 source / rule / code / schema / SSE version / full-statement version即拒绝。仅在RAM拦截文件读取，磁盘原件始终不变。

真实 stock_st / suspend_d终止页 schema失败继续保留，完整集合与负状态均未证明。独立 synthetic完整集合正向通过，空集 /截断 /非空终止页 /重复差异 /错日 /失败schema /重复行 /缺页均拒绝；9月30日的状态集合不证明10月6日可交易。真实Clock均以实际retrieval作为首次可用，日期本身不生成午夜 available_at，纳秒未来数据被拒绝。

实际 native 合同、formal producer、signed packet builder、research importer、semantics、审批和OrderChain消费端均拒绝 sandbox / Comparison跨入正式 ResearchCard / Candidate / Signal / Approval / OrderIntent / Order / Fill /云端。真实旧 SSE calendar reference的窄范围 ADMITTED正向控制可以通过自身验证，但仍不能进空的正式股票receipt registry。实际synthetic importer仅生成fixture Draft。两阶段已认证synthetic OrderChain仅structurally preparable、production disabled；LLM即使自带正确approval hashes也不是human authority。实际profile保持30项UNSET，productionGate始终false。

新建 native synthetic fixture 的22个执行 / Card表在审查前后均为0。这里是消费端测试的零写入证据，**不代表审计任意外部运行数据库**。formal producer股票receipt与输出仍0。

## 限制、已保留失败及建议

本轮未证明 Provider / License / Transport真实性、资金单位认证或历史PIT；只验证来源原件与工程计算自洽。native sandbox验证器的结构 / hash /本地展示检查不等于来源许可或producer权威。威胁范围不含任意有权限Python函数 /模块全局registry覆写、OS攻击或并发竞态。root另行执行的fresh-checkout检查只涉及原私有归档仍在本机，不能宣称任意远程CI或归档搬迁兼容。

G3源码路径身份导致的真实fresh重放失败、错误cwd的root成功重放、先前退出130的未交付原型都保留，不算最终通过。审查自身初版多余括号的语法错误与候选变动中途的WAVE_D_CONTEXT_FORGERY日志也保留；修正仅涉及审查harness，未改业务预期。G3 native168项通过只属预最终时代，不并入G4总数。

建议：**APPROVE_WITH_CONDITIONS** 接受这三股新版本地研究与比较工程；**HOLD**正式数据准入 / Research Pilot、C12–C22业务闭环、历史回测、云端、信号 /审批 /订单、券商和生产。Snapshot B仍PENDING，未观察10月8日的新交易数据，未满足20个真实forward交易日。状态完整性、SSE正文、单位、license与独立公司行动证明继续缺口。

审查已完成，**STOP**。不自行扩股、补抓数据、创建正式Card或进入下一阶段。

## 机器矩阵覆盖

| 攻击 /核对类 | 实际断言数 |
|---|---:|
| announcement_body | 9 |
| announcement_url_pdf | 25 |
| current_industry_to_history | 3 |
| deterministic_replay | 15 |
| financial_independent_math | 33 |
| financial_period_revision | 26 |
| full_statement_schema | 2 |
| future_announcement | 1 |
| high_quality_to_tradeable | 5 |
| historical_available_at_backfill | 1 |
| human_report_coverage | 3 |
| llm_to_human | 7 |
| native_positive_control | 19 |
| pit_four_clocks | 8 |
| producer_authority | 39 |
| quality_to_timing | 1 |
| quarantine_formal_escalation | 34 |
| raw_adjusted_isolation | 9 |
| report_to_order | 12 |
| report_to_signal | 9 |
| sandbox_namespace | 14 |
| sandbox_permission | 3 |
| sandbox_to_formal_card | 60 |
| score_coordinates | 4 |
| score_to_probability | 9 |
| source_lineage | 9 |
| source_pin_integrity | 2 |
| source_version_invalidation | 18 |
| status_completeness | 23 |
| unknown_not_zero | 6 |
| valuation_units | 3 |
| zero_execution_writes | 1 |

逐项预期与实际、reject reason及精确本地证据hash见 `Independent-Review-Matrix.json` / `Independent-Review-Evidence.json`。没有真实价格、财务数值、Token或可逆凭证写入审查报告。
