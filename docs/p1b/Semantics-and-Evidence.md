# P1-B0 研究语义与证据信任

Company / Fundamental Quality、Sector Quality、Catalyst、Evidence Quality、Valuation、Timing、Risk、Cost、Account Suitability、Tradeability十个独立维度。Quality高只能支持研究优先级，不能推出价格合适、Timing通过、适合真实账户或可交易。ResearchAssessment仅用明确synthetic模板测试；当前没有真实ResearchCard Producer、真实股票评分或荐股输出。

S/A/B/C/X是行动资格语义。S须研究/Timing/证据/Edge/Hard Block全部通过，只能REQUEST_REVIEW；A是高质量但价格/Timing/trigger/费用/适用性仍未满足，WATCH/WAIT；B有逻辑/催化但重要缺口，NO_ACTIVE_TRADE；C只有研究/观察价值；X是已准入的Hard Block或明确策略不满足。UNSET_REQUIRED独立于X，未知不能伪称已验证的排除或买入资格。Fixture refs只是语义示例，绝非source身份认证。

现有ResearchCard四层继续保留；未来解释必须机器回答为什么A不是S、现在不买的原因、哪些检查通过才A→S、哪些可信反证触发A→X。85/80/78仅EXPERIMENTAL_DEFAULT参考，不映射真实概率、胜率或校准阈值；真实Edge、sizing、费用与账户参数仍UNSET_REQUIRED。Price Region+Trigger+Invalidation优先，新增tranche仍须超过transaction cost+uncertainty buffer；未知buffer不能补值，旧Micro-Ladder拒绝不变。

证据有两类：ADMITTED_LOCAL_EVIDENCE与CLOUD_DISCOVERED_EVIDENCE。citation、手工断言、云端找到的新URL/公告/新闻只能形成PENDING_VERIFICATION的research lead或counterargument。不能据此满足/解除Hard Block、升级S、产生tradeable/signal/order或真实sizing；pending数据不进入decision事实/hash。人工改trust_class也不会认证。

具体workflow：pending lead → 可信local capture → immutable raw/hash → actual timestamp / PIT → source/terms/purpose/coverage → normalized / DQ → snapshot → policy / stored receipt → 新source-derived EvidenceResolution。原lead与文本claims保持pending，不原地改status。在首条calendar scope中，adapter仅将已验证本地calendar facts链接到lead，lead_claims_admitted=false；resolution每次use重新核验receipt及撤销，仍不能用于评分、Hard Block、模型导出或交易。发现其他source仍停在quarantine，不能从这条日历许可借权。

未校准Expected MAE/MFE/Probability不由本阶段生成，未来P1B3必须按质量/Timing/sector/entry/regime/horizon分层留出/OOS，保留失败实验。此Gate只证明语义和有限源的数据工程，不证明CORE_40投资有效性。
