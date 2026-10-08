# P1-B0 ResearchCard Contract Fit Analysis

依据：用户P1B-20261005授权、正式交接文档与已确认Closure Gate。结论：**ResearchCard1.0保留并优先复用四层主体，新增独立语义sidecar；当前不创建真实ResearchCard producer。** 不回改任何冻结字节。

| 当前1.0字段 | 适配结论 |
|---|---|
| research.thesis / strongest_counterevidence / unknowns / evidence_refs | 足够表达研究层；evidence trust状态须由新的Evidence sidecar验证，不能靠citation获得信任 |
| price.reference_price / entry_rules / no_trade_rules | 保留；未来adapter表达region+trigger+invalidation；不生成微小梯度 |
| trade.target_holding_sessions / invalidation_rules / thesis_invalidation / sizing_policy_version / can_produce_order | 保留；本阶段can_produce_order=false、sizing UNSET_REQUIRED |
| probability.scenarios / calibrated / calibration_ref / expected_mae_bps / net_edge_bps / edge_policy_version | 保留；未校准数值不得解释为概率；真实edge未知 |
| scores.quality / timing / research及其他维度 | 已分维度；数值阈值没有验证，不能以总分推出交易资格 |
| grade S/A/B/C/X、hard_blocks | wire可用，但缺显式research_grade/actionability_grade/account_suitability三轴和等级语义版本 |
| account_id为required | 不用伪造真实账户标识满足合同；本轮只做语义sidecar及source packet，真实Card生成留给获批pilot |
| immutable common reason enum / additionalProperties=false | 无法直接加入cloud信任类别或新receipt；独立版本/adapter，而不是修改旧validator |

新增ResearchAssessment1.0仅为SYNTHETIC_SEMANTIC_TEST_ONLY语义测试对象：十个维度、research_grade、provisional actionability_grade、真实适用性BLOCKED、不下单/不荐股；未来research_card_ref显式绑定旧Card1.0。DiscoveredEvidence1.0只描述PENDING_VERIFICATION研究线索，不允许trusted/grade/sizing/hard-block使用。

Closure BrainPacket1.1/SourceAdmissionPolicy1.0/AdmissionReceipt1.0硬编码fixture范围，不能直接承载真实数据。新SourceObservation1.1、SourceAdmissionPolicy1.1、AdmissionReceipt1.1、BrainPacket1.2使用独立urn/目录和验证入口。SnapshotManifest1.0的OBSERVED、四时钟及refs结构可以复用；其data_hash由新协议明确绑定，旧BrainPacket/Closure verifier不修改也不绕过。

首个真实候选只考虑交易所官方日历公告的非商业本地参考。官网条款允许非商业浏览/下载；这不是行情非展示、云端研究、再分发、真实荐股或historical backtest许可。来源/实际下载字节/条款/clock evidence验证后才可能准入，不凭公开可访问判定。条款依据：[上交所声明](https://www.sse.com.cn/home/legal/)。公告只有发布日期，available_at必须使用实际retrieved_at，不能把URL日期或发布日午夜当历史可得时间。

此Analysis先提交；随后冻结新合同和owned interfaces。数值85/80/78仅在semantics配置标记EXPERIMENTAL_DEFAULT参考，无已校准映射或真实概率。
