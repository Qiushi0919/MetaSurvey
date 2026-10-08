# P1-B 来源、许可与 PIT 时钟矩阵

库存时间：2026-10-05T10:22:08.462Z。机器字段及原引用见 [source-inventory.json](source-inventory.json)。清点不等于准入；计数是只读 main-file snapshot，排除 WAL，不是 live 认证。

## 来源 / 许可 / 用途

| source_id | 类型 | terms | 再分发 | 可用 purpose / status |
|---|---|---|---|---|
| legacy:stock-info-main-snapshot | A_SECURITY_MASTER_STATUS | UNKNOWN | UNKNOWN_NOT_AUTHORIZED | NONE / BLOCKED |
| legacy:akshare-calendar-file | B_TRADING_CALENDAR | UNKNOWN | UNKNOWN_NOT_AUTHORIZED | NONE / BLOCKED |
| legacy:sse-calendar-spec | B_TRADING_CALENDAR | UNKNOWN | UNKNOWN_NOT_AUTHORIZED | NONE / BLOCKED |
| legacy:kline-cache | C_EOD_PRICE | UNKNOWN | UNKNOWN_NOT_AUTHORIZED | NONE / BLOCKED |
| legacy:hk-daily-main-snapshot | C_EOD_PRICE_HK_OUTSIDE_A_SHARE_SCOPE | UNKNOWN | UNKNOWN_NOT_AUTHORIZED | NONE / BLOCKED |
| legacy:tencent-smoke-price-leads | C_EOD_PRICE | UNKNOWN | UNKNOWN_NOT_AUTHORIZED | NONE / BLOCKED |
| missing:corporate-action-revision-feed | D_CORPORATE_ACTION | UNKNOWN | UNKNOWN_NOT_AUTHORIZED | NONE / BLOCKED |
| legacy:financial-disclosure-leads | E_FINANCIAL_STATEMENTS_REVISIONS | UNKNOWN | UNKNOWN_NOT_AUTHORIZED | NONE / BLOCKED |
| legacy:announcement-policy-leads | F_ANNOUNCEMENTS_DISCLOSURES | UNKNOWN | UNKNOWN_NOT_AUTHORIZED | NONE / BLOCKED |
| missing:industry-membership-history | G_INDUSTRY_SECTOR_MEMBERSHIP | UNKNOWN | UNKNOWN_NOT_AUTHORIZED | NONE / BLOCKED |
| official:sse-dayk | C_EOD_PRICE | UNKNOWN | NOT_AUTHORIZED | NONE / BLOCKED |
| official:sse-holiday | B_REFERENCE_DOCUMENT | UNKNOWN | NOT_AUTHORIZED | NONE / BLOCKED |
| official:szse-holiday | B_REFERENCE_DOCUMENT | UNKNOWN | NOT_AUTHORIZED | NONE / BLOCKED |
| official:sse-session | B_REFERENCE_DOCUMENT | UNKNOWN | NOT_AUTHORIZED | NONE / BLOCKED |
| official:szse-session | B_REFERENCE_DOCUMENT | UNKNOWN | NOT_AUTHORIZED | NONE / BLOCKED |
| official:sse-calendar-reference | B_CALENDAR_REFERENCE | VERIFIED_FOR_NARROW_LOCAL_REFERENCE | NOT_AUTHORIZED | LOCAL_NONCOMMERCIAL_CALENDAR_REFERENCE / CANDIDATE_REQUIRES_APPROVED_POLICY_AND_ACTUAL_RECEIPT |

最后一行仅为库存候选。最终已注册政策与 Receipt 另见 [real-reference-results.json](real-reference-results.json)：CORE_40 / CALENDAR_REFERENCE / 2026-10-01—10-08 / symbols=[] / LOCAL_NONCOMMERCIAL_CALENDAR_REFERENCE / LOCAL_REVIEW_ONLY。其他日期不补齐，空 symbols 不是全市场。股票、财务、云端/模型、再分发、交易、历史回测均未授权。

官网非商业浏览/下载许可按本地有限参考解释，未推导行情产品或云端权限。[SSE 原条款](https://www.sse.com.cn/home/legal/)、[实际公告](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml)。原五个旧 capture 继续 BLOCKED，新 source identity 不改变旧对象。

## PIT clock

| source_id | publication | availability | retrieval | 历史 PIT |
|---|---|---|---|---|
| legacy:stock-info-main-snapshot | UNKNOWN | UNKNOWN_NOT_INFERRED_FROM_MTIME | UNKNOWN_NO_BYTE_LINKED_SOURCE_CAPTURE | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| legacy:akshare-calendar-file | UNKNOWN | UNKNOWN_NOT_INFERRED_FROM_MTIME | LOCAL_FILE_UPDATED_AT_ASSERTION_ONLY:2026-09-03T18:46:08+08:00 | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| legacy:sse-calendar-spec | UNKNOWN | UNKNOWN_NOT_INFERRED_FROM_MTIME | UNKNOWN_NO_BYTE_LINKED_SOURCE_CAPTURE | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| legacy:kline-cache | UNKNOWN | UNKNOWN_NOT_INFERRED_FROM_MTIME | UNKNOWN_NO_BYTE_LINKED_SOURCE_CAPTURE | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| legacy:hk-daily-main-snapshot | UNKNOWN | UNKNOWN_NOT_INFERRED_FROM_MTIME | UNKNOWN_NO_BYTE_LINKED_SOURCE_CAPTURE | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| legacy:tencent-smoke-price-leads | UNKNOWN | UNKNOWN_NOT_INFERRED_FROM_MTIME | UNKNOWN_NO_BYTE_LINKED_SOURCE_CAPTURE | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| missing:corporate-action-revision-feed | UNKNOWN | UNKNOWN_NOT_INFERRED_FROM_MTIME | UNKNOWN_NO_BYTE_LINKED_SOURCE_CAPTURE | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| legacy:financial-disclosure-leads | UNKNOWN | UNKNOWN_NOT_INFERRED_FROM_MTIME | UNKNOWN_NO_BYTE_LINKED_SOURCE_CAPTURE | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| legacy:announcement-policy-leads | UNKNOWN | UNKNOWN_NOT_INFERRED_FROM_MTIME | UNKNOWN_NO_BYTE_LINKED_SOURCE_CAPTURE | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| missing:industry-membership-history | UNKNOWN | UNKNOWN_NOT_INFERRED_FROM_MTIME | UNKNOWN_NO_BYTE_LINKED_SOURCE_CAPTURE | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| official:sse-dayk | UNKNOWN | UNKNOWN | ACTUAL_OLD_CAPTURE:2026-10-05T06:09:58.788Z | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| official:sse-holiday | 2026-09-17 | RETRIEVAL_ONLY_NO_HISTORICAL_PROOF | ACTUAL_OLD_CAPTURE:2026-10-05T06:09:59.054Z | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| official:szse-holiday | 2026-09-17 | RETRIEVAL_ONLY_NO_HISTORICAL_PROOF | ACTUAL_OLD_CAPTURE:2026-10-05T06:09:59.201Z | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| official:sse-session | UNKNOWN | RETRIEVAL_ONLY_NO_HISTORICAL_PROOF | ACTUAL_OLD_CAPTURE:2026-10-05T06:09:59.554Z | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| official:szse-session | 2019-12-04 | RETRIEVAL_ONLY_NO_HISTORICAL_PROOF | ACTUAL_OLD_CAPTURE:2026-10-05T06:09:59.601Z | BLOCKED_NO_HISTORICAL_AVAILABILITY_PROOF |
| official:sse-calendar-reference | BODY_DATE_ONLY_2026-09-17_INTRADAY_UNKNOWN | ACTUAL_RETRIEVAL_ONLY_NOT_HISTORICAL | ACTUAL_NEW_TLS_CAPTURE:2026-10-05T10:08:22.746222+00:00 | OBSERVED_AT_RETRIEVAL_ONLY |

当前日历事实中的开/休市日期是 business effective dates；SourceObservation 表示 capture observation。Snapshot provenance.event_time 是这一观察的捕获时刻，不是休市事件发生时刻。新 observation clock 没有单独 event_time 字段，因此这不是通用完整四时钟市场/财报 MVP；扩展前须新版本区分 observation event 与业务 effective date。

正文 published_date=2026-09-17；URL 的 20260915 不代表发布日期。intraday published_at=null，禁止补午夜。actual available_at=retrieved_at=2026-10-05T10:08:22.746222+00:00；条款 retrieved_at=2026-10-05T10:08:22.572813+00:00。所有 cutoff/use time 保留亚毫秒精度，任一原件/条款晚于 use_at 均拒绝。不能用本次10月捕获反填9月历史可见性。

receipt 为一次固定时点的 DEV 参考证明；撤销 registry/signing identity 当前在单进程内存。归档可检验当时签名和重放，不是现在/未来可消费的持久 live授权。跨进程、重启、多源、持久撤销、通用许可及业务 producer 仍未实现。
