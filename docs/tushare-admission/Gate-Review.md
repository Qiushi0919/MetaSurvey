# TUSHARE MONTHLY GATEWAY ADMISSION REVIEW

2026-10-05 · 当前 Owner 准入建议：**BLOCK**。本轮完成离线准备、正式文档捕获、门禁实现与独立攻击复测，**尚未完成真实账户 entitlement 或三股数据准入**。最新指令要求先轮换凭证、确认供应方正式 HTTPS/身份；这些证据未提供，因此没有读取凭证、没有发送认证请求。此前连通性测试保留为历史诊断，不算本轮三股/账户许可证据。

主要 Source of Truth 仍为正式工程交接文档；执行边界以 [最新 Owner 指令](../authorizations/TUSHARE-monthly-gateway-probe-20261005.md) 为准。其解释性建议不能升级为账户或供应方事实。记录 `actual_account_tier=15000`、月卡，证据来源 OWNER_ASSERTED；有效期和权益绑定尚未独立核验。先前 SSE Gate/原件/合同/业务规则均保持交付时事实。

| Owner 要求 | 本轮实际结论与证据 |
|---|---|
| 1. Provider/gateway identity | `TUSHARE_MONTHLY_GATEWAY`，网关/上游身份 UNVERIFIED；兼容协议不等于官方直连。没有供应方把当前IP/8030与购买权益绑定的证据。 |
| 2. Transport security | 已知配置为HTTP；供应方正式HTTPS文档/地址、HTTP-only声明和Owner有限HTTP例外均未提供。在secret lookup之前阻断；不猜HTTPS、不绕证书、不跟随认证跳转。 |
| 3. Purchase/terms evidence hashes | 订单/账户权益原件未提供。实际捕获17份官方公开协议、权限和产品文档，保留UTC捕获时间与原字节SHA256，原件在Git外；[指纹矩阵](public-terms-evidence.json)。官方资料不证明代理身份、月卡权益或代理license。 |
| 4. Actual expiration | `UNSET_REQUIRED`。不从官方年价表或“月卡”一词推算起止日期。旧凭证禁用；新凭证轮换未确认。 |
| 5. Actual entitlement matrix | [矩阵](entitlement-matrix.json)：各账户产品权益均UNSET_REQUIRED，没有实际拒权证据，不能标记NOT_ENTITLED。PhaseA未查询；B等A通过；anns_d未获独立权益证明而跳过。 |
| 6. API-by-API probe | 34条是inventory：A16/B18；实际认证查询**0**。A覆盖stock_basic/stock_st/suspend_d/trade_cal/daily/adj_factor，B为dividend/income/balancesheet/cashflow/fina_indicator/index_member_all。SDK/HTTP sender未启用。 |
| 7. Three-stock coverage | 范围固定603993.SH、600312.SH、603228.SH / CORE_40；本轮实际股票行数0、准入数0。八类[覆盖矩阵](coverage-matrix.json)明确未采集；原SSE公告/日历PARTIAL保留。 |
| 8. Raw-bar result | 实际raw bars未取回。离线解析器保留Decimal与raw OHLC语义，不用qfq/hfq替代；官方vol=手、amount=千元只是documented units，尚未证明代理一致性。pre_close保留官方除权参考价语义，不自动等于上一行close。 |
| 9. Adjustment result | 实际因子0、raw→adjusted对账未执行、factor版本/公司行动lineage未证明。计划只请求独立adj_factor短窗，不生成复权价或补历史可见性。 |
| 10. Corporate-action result | PhaseB未执行。dividend只采用文档支持的ts_code+ann_date精确过滤，不猜start/end过滤。空返回不能证明没有公司行动，更不能证明feed完整。 |
| 11. Financial revision result | PhaseB未执行，12季度覆盖0。未来保留ann_date/f_ann_date/end_date/report_type/update_flag及原件引用，同期多行不覆盖/去重。修订标志不是稳定revision identity或历史available_at证明；未明确金额/比例单位仍UNSET_REQUIRED。 |
| 12. Industry result | PhaseB未执行；is_new=Y只表示请求当前成员。in_date/out_date是业务有效日期，不是历史首见；不回填历史PIT。 |
| 13. PIT/clock result | `historical_visibility_proven=false`。股票请求无成功capture，event/published/available/retrieved均null，不伪造ClockEvidence。实际公开文档可得边界取实际retrieve clock；合成测试验证严格UTC时钟、DATE_ONLY/null、未来财报发布日期阻断。 |
| 14. SDK vs MCP | 本轮NOT_PERFORMED。历史测试SDK1.4.29成功、MCP工具发现/一条查询成功，已标记不同证券/不同阶段，不算当前证据。当前适配器为stdlib1.0.0诊断，没有SDK依赖；MCP仅允许canonical路径完成后的同symbol/date/field等价smoke，不是原字节权威入口。 |
| 15. Official-source cross-check | NOT_PERFORMED。既有SSE证据只有公告指针/有限日历，没有获准的OHLC数值源，不能拿标题充当行情对账。没有为通过比较而购权、换源或修正数值。 |
| 16. DQ result | 没有实际股票响应，不能称REAL_DQ_PASS。离线38项、合同12项通过；拒绝范围/字段/日期/行数/Decimal错误及权限、凭证、命名空间、历史PIT升级。官方信息与代理实际schema/单位/更新一致性仍待验证。 |
| 17. Snapshot/Receipt | 新SourceObservation/ClockEvidence/policy/StockSnapshot/AdmissionReceipt全部NOT_ISSUED、引用null。旧SSE-specific2.0合同不容纳Tushare行情/财报权限，未假签policy。真实SnapshotB仍PENDING新交易日真实数据与准入lineage。 |
| 18. Independent Reviewer | 新只读Reviewer按最终源字节复测：独立70项探针攻击、164项合同检查通过；此前失败候选和错误harness日志均保留、区分。工程PASS_WITH_CONDITIONS不升级source。详见[独立审查](Independent-Review.md)。 |
| 19. C12–C22 | **本轮关闭0项**。每项原状态与阻断原因见[conditions](conditions.json)；财务/公司行动/因子/行业/行情/历史首见等没有新增已准入证据。C22真实producer/Pilot仍BLOCKED。 |
| 20. Extra paid permissions | 当前不能证明任何额外购买的实际必要性；没有购买。公开anns_d/分钟说明要求独立权限，但当前账户是否已获授权尚未证明。分钟/实时不属于本轮P1-B最小slice；现有SSE公告链继续保留。 |
| 21. Exact recommendation | **BLOCK** 新网关准入。Global LOCAL维持原SSE PARTIAL；云端导出/模型、历史回测、redistribution、Pilot、Signal/Order、券商/生产保持阻断。停止本轮，不扩大覆盖。 |

本地检查入口：`node tushare-admission/check.mjs`。旧348项回归=347PASS/0FAIL/1原有可选外部V5 SKIP；新增12合同+38离线探针全部PASS。合计398项=397PASS/0FAIL/1SKIP，不重复计数Reviewer运行的同一suite。独立另234项实际攻击通过。完整日志及源指纹见[validation](validation.json)、[code provenance](code-provenance.json)。没有执行远端CI、实际DB迁移或真实模型/订单。

初始独立审查找到错误拒权分类、财报未来日期、编码凭证回显、可重载子类范围绕过、时钟文本持久化和深层百分号解码边界等问题，均修复后换源指纹重新复测。一个Reviewer日历fixture误把enum当Decimal已修正测试harness，原失败日志保留且不算代码缺陷。父合同凭证状态一致性也修复；首次基线集成因新增脚本落入旧Closure动态冻结目录而失败，只移动新文件到新目录，不修改旧检查或重算旧期望hash。

新12文件源指纹冻结，原203 source pins、368文件前次交付中除允许导航外的原字节、SQL001–006、旧releases/contracts/Gates、legacy code/seal/ledger/database/runs保持不变；Schema仍6，无新migration。新增合同是AdmissionVerification1.0.0诊断合同、release1.5.0-diagnostic；不是市场数据SourceObservation/Receipt发布。私有report registry只防当次诊断对象篡改，不是持久source authority。原件、日志、状态在Git外；没有Token或TokenSHA identifier进入新repo/report。

继续所需输入：Owner确认旧凭证作废并取得新凭证，给出Keychain服务/账户或approved secret-store引用；提供供应方正式HTTPS/网关身份说明，以及脱敏购买产品、渠道、账户权益和有效期原件路径。**不要发送Token。** 若供应方明确只有HTTP，再由Owner明确决定有限local-probe例外；当前不存在该例外。用途与storage/retention/transfer仍须具体证据绑定，确认这些条件不会自动放行Pilot/历史回测/生产。

上述阻断来自最新Owner指令的 SECURITY FIRST / TRANSPORT GATE，而非命名细节或账户资金参数。本轮到此停止，待所需事实补齐；现有真实账户/券商/资金/费率/风险30项UNSET_REQUIRED继续阻止真实资金执行。
