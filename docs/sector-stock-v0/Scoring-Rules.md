# 双层评分实验规则 0.1.0-candidate

实验：`CORE40_SECTOR_STOCK_BASELINE_V0`；namespace：`EXPERIMENT:CORE_40:SECTOR_STOCK_V0`。本规则只定义研究排序试验，不输出 S/A/B/C/X、上涨概率、Edge、仓位或订单。与既有冻结 CORE_40 两 family、M01–M08、正式六 DTO 不互相替换。

## 输入、来源与计算

机器权威配置：[config.json](../../experiments/sector_stock_v0/config.json)。其中 `metrics` 对每个指标定义单位、完整输入口径、窗口、证据来源、0/100 分锚点、缺失与版本，工作台直接读取这些字段。规则不是靠前端复制数字。

`N(x)=max(0,min(100,100×(x−zero)/(hundred−zero)))`。反向指标估值排名/不利事件占比的 zero=1、hundred=0。锚点之外的普通增长指标截断；有明确合法区间的比例出界则阻断，不能把错误值截断成高分。

板块九维：需求、供给、价格及订单、政策、全球趋势、竞争格局、估值、相对强弱、风险。每项 N(x)，九项等权平均。等权是候选选择，用户尚未指定板块权重。风险维度衡量行业不利事件收入占比，独立硬门槛及扣分另作用于被评价对象，不能因其他维度高分抵销硬风险。

个股：基本面25%（收入增长、现金含量、ROIC−资本成本三项归一化分数平均）；板块受益20%（同 cutoff、同实验/trace/type 下重算的对应板块 final_score × 该板块业务收入占比）；催化剂15%；趋势15%；估值10%；流动性10%；证据质量5%。七项权重固定相加为100%。板块正式结果在跨层边界保留2位小数，个股按其封存值计算；其余中间计算保留 Decimal 精度后统一舍入。

纯函数不下载、不提取财报、不访问数据库、不自动执行 AI。所有指标由未来输入适配器按配置公式形成，并保留原文定位、修订、来源/版本、raw hash、单位、完整窗口和提取版本。当前函数能验证输入结构、证据值/单位绑定及四时钟约束，**不能仅凭调用者声明的原件 hash 证明原件真实性、窗口完整性、授权或双人身份**；这些仍是实际输入准入的前置工作。因此现有真实报告不被自动改造成 ScoreInput，本轮真实板块/个股评分均0。

政策/催化剂是结构化证据编码，须有双人独立编码记录、原文条款、去重事件身份、有效期与冲突处理；不是给 AI 一个主观0–100分的槽位。编码人的身份与记录真实性需未来准入审查，本轮只有合成结构验证。无完整事件检索不能把“没找到”填成0。

## 风险、缺失与不确定性

四个独立硬门槛：source_integrity、critical_evidence_complete、status_verified、thesis_intact。状态必须全部 PASS，FAIL/UNKNOWN 任一即 BLOCKED；每个 PASS/FAIL 要有匹配的证据事实。完整定义在配置 `hard_gate_definitions`。

三项候选扣分：客户集中度10、较高杠杆10、非关键重大不确定性5，分别只扣一次，final=max(0,raw−总扣分)。客户集中度阈值>50%，净债务/正EBITDA>3；比较口径和 UNKNOWN 条件见 `risk_definitions`。PRESENT/ABSENT 都须证据，UNKNOWN 阻断；关键反证进入硬门槛，不能变成5分软惩罚。没有真实风险上限或生产政策从本规则继承。

任一必需指标缺失：分量 NULL，raw/final/扣分 NULL，保留具体 reason code；不按剩余权重归一、不以50/0补值。失效/未知的数据可保留独立分量供排查，整体状态必须 BLOCKED。审查阶段不能据分量给推荐。

## 数值、时间与复算

Decimal字符串输入（至多10位小数），拒绝浮点/指数/NaN/Infinity、布尔和未知字段。Decimal40有效位；最终分量/总分 ROUND_HALF_UP 至0.01，聚合使用未舍入分量。成交金额单位 CNY_YUAN，不是分，纯评分不建立货币账本。

event_time/published_at/available_at/retrieved_at 全部要求带时区且<=cutoff；当前观察的 available_at 保守地不得早于 retrieved_at 或 published_at；expires_at<cutoff 阻断。此实验不提供 historical 模式，`historical_visibility_proven=false` 固定，不能靠今日获取历史数据倒填过去可见性。recorded_at 必须>=cutoff，是调用者提供的真实写入时间，计算函数不猜钟。

对象 hash：UTF-8、JSON键按 JavaScript UTF-16 字符串排序、无空格、数组顺序保留，排除顶层 content_hash 的 SHA-256；数字业务值均字符串。config_hash 则绑定配置**原文件字节**；ScoreResult 另绑定 engine_sha256 原代码字节。输入对象版本、trace_id、cutoff、证据 bundle ref、上游sector ref全部可追踪。重算任何差异使旧结果失效，不能更新旧封存值来通过校验。

可复算：`evaluate(input,bundle,sectorContext)`，STOCK 的 context 必须包含 SECTOR 的 input/bundle，函数实际重新计算板块结果并比对 ref；不信任随手填写的 sectorScore。`validateGraph(objects)` 检验四接口关系、候选和分数一致性并重算每个结果。运行示例在 [工程入口](../../experiments/sector_stock_v0/README.md)。

## 四项实验接口

六个独立 Schema 位于 [contracts/sector-stock-v0](../../contracts/sector-stock-v0)：

| 对象 | 职责与关联 |
|---|---|
| EvidenceBundle | 带时钟、单位、修订及原件定位的标量事实；不携带原始文件正文 |
| ResearchHypothesis | 论点、最强反证、未知项，绑定 EvidenceBundle；保留原生 ResearchCard/BrainPacket hash ref |
| ScoreInput / ScoreResult | 指标/硬门槛输入及可复算分数；绑定配置、代码和上游版本 |
| CandidateSet | 独立实验候选引用分数与对应假设；EMPTY/BLOCKED 无成员；永不成为正式候选 |
| ValidationResult | 本轮仅 SYNTHETIC_ENGINEERING_ONLY 或 NOT_RUN；经济结果NULL、有效性NOT_ESTABLISHED |

Schema required 为字段权威，未列字段拒绝；nullable表示已知缺失而非optional。native_refs 可以为空，存在时只允许 ResearchCard/BrainPacket 1.0.0 的身份/版本/hash；本轮不伪造原生对象、不消费它们作为执行授权，也不开放 MANUAL_EXPORT。输入包→假设/研究→候选→验证，引用不能成为人类审批。

## 审批与停止

Owner 本轮授权工程实现不等于接受候选锚点、板块权重、编码方法、风险规则或优化协议。完整账户、日期化真实费用、资本成本、PIT与许可证仍单独待定。测试分数只验证算术和失效行为，不是历史盈利证明。
