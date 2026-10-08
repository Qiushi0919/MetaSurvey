# Wave G 独立审查 R1

结论：PASS_WITH_CONDITIONS，仅适用于本地回顾性诊断和准备工程。未发现产品假接受；真实 Snapshot B、Forward Day-1、原生 Signal/Approval/Order/Fill、Broker、云/模型、生产与真钱全部仍 BLOCKED，actual_forward_days=0。

审查候选 c4fdb9a98a083677973fd052c622da5060be85d4，context sha256:cfe01c4e0d31b0bb4c21e73f77f8f7095054848b5820b9b34664ec86cb8e497d。28 个 code pins、764 个 Wave F 不可变文件和 1,295 个直接依赖均重开哈希/大小；审查前后无变化。最终另重开 1,295 个依赖检查不加入下述断言合计。

独立脚本合计 39,942 个原子断言通过：Python 31,420，native 408，官方结构语义/有限脱敏审查 62，规则与敏感性独立 membership oracle 8,052。原子数包含逐字段比较与前后哈希检查，不能称为 39,942 个独立回归测试。没有重复项目全套回归。

从三份原始 coverage 日线读取 981 个独立日期，直接以 Decimal100 重算 981 行价格特征、2,943 个未来标签（2,688 个可观察标签、255 个尾部 UNKNOWN）、6,408 条规则不等式和 1,602 个价格子条件 membership。18 个固定扩展前缀均对全部标签统计移除末尾 60 个锚点；18 个已登记单变量诊断均保留，不选赢家。原始 close 比率、路径回撤、交易日 offset、当前 Quality 留一字段排名一致；当前财务没有倒填历史。完整 family 的 1,962 个观察全部 NO_DECISION。

独立攻击覆盖未来无效负载、晚到旧日期修订、缺失/冲突 bar、pre_close 与公司 Quality 混入、实际时钟精度、event_time 伪 availability、caller 重哈希原件行、HUMAN/LLM 自签许可、16 原生合同与跨 namespace 晋级。15 个实际入口在伪许可输入下均在文件/路径/socket IO 之前拒绝。来源完整或 HTTP200、官方 HTTP 示例均不能变成具体网关许可证。

只在 Reviewer 独占目录建立新的 staging 夹具：2 个 session、1 条失败 duplicate 链，actual day 仍 0；expected-head、source/A binding、追加、重启、原件重开、外部 SQL 写入拒绝均通过。第一轮 Reviewer 把 Current-Observed 第一包与另一 source-binding 的第二包混用，严格 guard 正确拒绝，Python 审查中止；原脚本、日志和 store 保留，G2 改用冻结 staging 的对应两包后通过。该 harness 故障未被改写成 PASS，也未导致修改产品代码。

官方原件审查确认：603993 的税前现金 0.255 元/股与差异化除息参考约 0.2535 分离，实际净现金和到账未知；603228 2025-071 为后来实施说明，不冒充首次实施公告；600312 的 1.38 元/十股为待批准分配提案；无更正声明不证明完整修订历史。SSE 计划 2026-10-08 恢复交易不证明当日实际 open/EOD。新增 11 项结构事实，连续 PIT 域关闭仍 0。

8 类 Provider 证据仍 UNKNOWN，30 项账户/费用/风险参数仍 UNSET_REQUIRED，Small Live v0 仍 OWNER_PENDING。真实 collector/source clock/status 适配、source exception/capture acceptance/version interpretation、实际独立 review/Human issuer、accepted-session namespace 计日均仍需未来授权下编码及独立验收；generic staging 不能直接切换为实际账本。实际 Snapshot B 缺口不限于 Human 授权。

根有限 credential 扫描 8 个历史命中文件均重开验证为明确 synthetic 攻击/test 或失败说明。没有扫描 chat、环境、Keychain 或历史凭据，也没有声称通用 secret absence。

此审查不替代总控的 fresh clone 全回归、最终 Git/bundle/checkpoint/ZIP 完整性与停止交付职责；完成后 STOP，等待 Owner。
