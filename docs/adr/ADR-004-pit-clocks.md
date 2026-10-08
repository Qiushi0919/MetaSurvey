# ADR-004 PIT 四时钟语义

状态：P0 工程实现，待 Gate Review。

event_time 表示事件发生/计划生效事实；published_at 表示公开披露；available_at 表示来源与处理规则下可用于系统的时点；retrieved_at 表示实际取得。四者分列且保留来源版本/hash。未来生效的已公布公司行动可以 event_time 晚于 available_at；不能用一条错误的总排序否定它。

OBSERVED_AT_TIME / SQL OBSERVED_AS_OF 要求 available 和 retrieved 均不晚于截止。HISTORICAL_AVAILABILITY_RECONSTRUCTION / SQL PUBLIC_AS_OF 可显式表示事后归档的历史公开可得资料，但不得声称系统当时已取得。UNKNOWN 时点或 DATE_ONLY 无可信日历时拒绝决策准入；精确发布时间不得被取得时间覆盖。

冻结前先过滤全文、标题、ID、计数和哈希输入；不向模型泄露未来资料的元数据。快照与数据对象引用需核对真实版本/hash/clocks。freeze session 保留不可变决策承诺后才揭示未来材料。P0 没有来源时钟认证、对象存储权限隔离或硬件可信时间；这类缺口继续阻止生产准入。
