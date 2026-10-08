# MetaSurvey GitHub 公开发布验收报告

日期：2026-10-08（Asia/Shanghai）。Owner 明确选择 public。目标仓库：`Qiushi0919/MetaSurvey`。

## 发布范围

发布主控当前已集成软件、16 原生合同及阶段扩展、001–006 migrations、合成/legacy 工程测试、ADR、授权范围、Gate、方法提案和审查报告。新增架构导航、固定最新验收入口、机器报告索引、正式交接文档的逐字节副本以及独立 R1/R2/失败澄清的工程元数据副本。

第一次公开历史从独立快照建立，没有复制本地主控原 Git 历史。原历史包含六项许可未核验的 PUBLIC_REFERENCE 原件，因此公开快照排除这六项，仅记录路径、大小、SHA-256 和理由。原件、旧 seal、旧账本和原本地 Git 历史不修改。运行数据库、credentials、私钥、实际原始市场数据和大型验收 ZIP 不进入仓库。

源工程 commit 与每个公开文件的字节哈希见生成的 `docs/review/Source-Snapshot.json`；排除项见 `docs/review/Local-Only-Manifest.json`。源工程本轮允许改变的旧文件仅 README、AGENTS 和两个旧 CI 入口；所有旧业务代码、合同、迁移、冻结策略、测试和历史报告原文保持原字节。公开仓库只表示主控已集成系统，专项独立 worktree 不覆盖。

## 检查与结果

本机原完整源工程的原生测试：258 项中 257 PASS、0 FAIL、1 原有外部 V5 可选 SKIP。16 项原生 1.0.0 合同与 frozen release bytes 校验通过，30 项必填配置缺口保持阻断。这是本机检查，不冒充公开复现结果。

公开快照独立复现结果：Node 249 项原注册用例中 248 PASS、0 FAIL、1 原有外部 V5 SKIP；另有明确列出的 9 项 local-only 不执行。Node 另报 1 项无执行用例文件的加载成功，原始 runner 总数为 250/249 PASS，文件加载项不加入业务用例计数。Python 209/209 PASS（sidecar 123 + 未批准方法合成算术 75 + 边界 11），真实网络尝试 0。原生合同/冻结 release bytes 校验通过。工程发布验收为 PASS_WITH_EXPLICIT_LOCAL_ONLY_EXCLUSIONS；完整机器结果见 [Checks.json](Checks.json)，保全见 [Preservation.json](Preservation.json)。GitHub 上的运行状态以 [公开 CI](https://github.com/Qiushi0919/MetaSurvey/actions/workflows/review.yml) 为准。公开测试只针对可共享的工程行为，不改变 PIT、费用、审批、namespace 或生产门禁。两项依赖六份 local-only 原件、七项依赖未公开原 Git 历史的测试公开不执行，原因和精确用例名称明确列出；原测试和 code-provenance pin 未被修改。初次公开 Node 运行的七项 provenance 失败与 Python 临时目录别名导致的两项 runner 错误保留在本机日志；公开能力范围和 runner 路径修正后另开新日志复测，不改写原失败。

历史专项独立审查原文见 `../2026-10-08-p1-integration/`，逐文件来源哈希见 `Evidence-Copies.json`。保留初始保全 harness FAIL 和纠正后的表示比较结果；R2 原始 105 项中的 1 个 harness 冲突保留，独立澄清 3 项单列，不改写为原 105 全通过。

## 当前仍被阻断的执行

六 DTO 最终字段冻结 HOLD，CORE40 方法提案待 Owner 决策；真实历史 PIT admitted=0，正式 family NOT_COMPUTABLE / ENGINE_NOT_RUN，OOS windows=0。真实账户、费用、风险参数 UNSET_REQUIRED；Provider/License 未核验。Forward Day0 保持冻结，Snapshot B NOT_YET_RUN，actual days=0。生产数据、历史正式回测、云端研究数据导出、券商和真实资金执行继续 BLOCKED。

公开上传、架构展示与 CI 成功不授予真实数据转移、独立审核替代、策略优化或实际交易权限。完成公开发布后本轮停止，不自动进入研究或交易下一阶段。
