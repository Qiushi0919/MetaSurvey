# P1-B Tushare 有限真实探针：独立只读审查

工程结论 **PASS_WITH_CONDITIONS**，范围仅为本机只读 quarantine 捕获及强制父验证器回放。新网关 `REAL_DATA_ADMISSION_GATE` 和 `LOCAL_REAL_RESEARCH_GATE` 均 **BLOCKED**；既有 SSE LOCAL 为 PARTIAL；Research Pilot、Cloud、历史回测、Signal/Order、broker 和 production 均未放行。

当前独立编写并实际执行的检查 **906 PASS / 0 FAIL**：127 探针、25 模拟传输、22 模拟原生 secret-reader、67 冻结 consumer/审批/账户安全、506 Schema/语义门禁、54 synthetic 原件验证、42 两轮真实 report/原件攻击、37 实际 Gate 证据绑定攻击、26 元数据与历史保护检查。早期失败、重复运行和项目自身 Golden 不计入此数量。Reviewer 没有读取真实 credential、调用真实 Keychain 或发出网络请求。

实际父采集链可核验 **44 认证请求 / 44 原始响应 / 2786 物理行观察**；各股327日 raw bars 和327 factors，唯一raw bars为981。44次HTTP200/code0仅证明技术访问；26非空响应技术DQ PASS、9空响应不证明coverage、9响应继续隔离。财务宽窗含20221231范围外报告期，行业out_date为空，均未靠重写原件、扩范围或猜测空值制造PASS。

capturer为8f8cc0d，mandatory verifier为42e1e4c；9文件当前source hash `sha256:4dcc9bd86cc87ef4c7032a124a69ed4d0e62c957b1243c453e388ecde63aaf9a`。两个真实report的SHA、原字节、scope、fingerprint、时钟、DQ、epoch和Gate统计均复核；恶意修改仅在RAM拦截读取，实际原件从未被Reviewer修改。

晚期发现 `imp_ann_date` 未来公告在裸fe632collector未阻断。该事实和失败记录保留；强制42e父验证器独立阻断所有未来ann_date/f_ann_date/imp_ann_date，且允许未来ex/pay business dates。本项 **在强制验证边界关闭**，不能描述成裸collector已经修复或历史可见性已经证明。此前非法UTF8编码credential回显也在实际联网前修复并复测。

13条有scope交集的既有SSE日历参考事实与当前原件一致，3股证券代码范围相符。完整ST/status与行情/公司行动数值交叉核验没有可准入第二来源；完整factor/action重建也未实现。对应攻击矩阵为 **CONDITION**，没有冒充完整功能测试PASS或数据许可。

历史基线392文件中 **389原字节不变，3项仅允许的导航变化**（AGENTS、README、source-of-truth），无历史code/Gate/seal/ledger/schema被改写；30账户/费用/风险UNSET_REQUIRED继续阻断生产。最早58615候选完整源码未精确恢复，仅失败JSON/harness/fullSHA保留，已明确列为保全限制。

供应商/销售渠道/产品/订单、正式账户权益、精确月卡expiry和local用途/storage/retention/transfer许可仍未独立证明。Owner允许现有凭证/HTTP/probe存储，不等于供应商许可或可信传输。新policy、SourceObservation、admitted ClockEvidence、Snapshot、Receipt、BrainPacket及Card签发数量为0，C12–C22新增关闭0，真实Snapshot B仍PENDING。

完整证据见 [Independent-Review.json](/Users/qiushi/投资研究/.p1b-archives/tushare-real-admission-20261005/reviewer/Independent-Review.json)、[逐项攻击矩阵](/Users/qiushi/投资研究/.p1b-archives/tushare-real-admission-20261005/reviewer/Attack-Matrix.json)。项目463项Golden结果由总控保留，独立906项不与其重复相加。最终干净checkout/交付commit证明仍由总控补齐；如source pin或Gate变化，应另行复审。

**完成报告后停止。不得自动进入 Research Pilot、historical backtest、cloud、真实资金执行或购买权限。**
