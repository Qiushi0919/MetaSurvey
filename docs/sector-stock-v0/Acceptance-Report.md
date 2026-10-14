# MetaSurvey 双层评分实验与本地工作台 V0 验收

交付日期：2026-10-14，Asia/Shanghai。结论：**本轮限定的工程实现与验收完成；实验方法候选待 Owner 审批，投资有效性未建立。** 实际新板块评分0、实际新个股评分0、正式候选0；未运行优化器、正式五年回测或 Forward 揭晓。STOP。

## 现在可以使用什么

本地地址：<http://127.0.0.1:8765/>。七页均已在浏览器实际打开：仪表盘、板块研究与评分、股票候选池与评分、单股研究卡、回测/Forward、Agent任务记录、配置/待决事项。复用上一轮真实只读工作台，未另造重复微服务。

- 仪表盘显示已有集成报告记录的7,567个股票价格日期、582条财报期记录；这是旧报告覆盖数字，不是新抓数据或PIT准入。
- 仍可查看洛阳钼业、平高电气、景旺电子三份封存研究报告，打开证据弹窗核对来源、原件hash和预期hash。原报告内旧 Quality/Timing 坐标原文保留，不是本轮评分。
- 板块页展示九维输入口径、来源、窗口与候选锚点；候选池展示七项Owner指定权重和真实评分缺口，不将研究对象当推荐。
- 正式历史验证显示 ENGINE_NOT_RUN / NULL；Forward显示原有冻结与阻断状态，没有把日期流逝当作完成新交易日。
- Agent页显示三股研究、五年集成和上一轮界面验收的归档文档。没有实时任务运行器/日志/心跳，不显示“Agent正在研究”。
- 配置页可读本轮规则、预注册草案、M01–M08和旧未配置账户模板，没有批准、下单或任务执行按钮。

本机启动（已有Python3.12运行环境，无新依赖）：

```sh
cd '/Users/qiushi/投资研究/ashare-trading-v1'
/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m workbench.server --port 8765
```

其他机器在仓库根目录用 `python3 -B -m workbench.server --port 8765`。访问127.0.0.1，按Ctrl+C停止。本轮交付时服务保持运行供Owner查看；未安装自动启动或调度。公开clone没有私有研究档案时会明确FILE_MISSING，不能声称复现了本机真实报告。端口冲突时可改本机端口，不开放局域网。

## 工程基线及范围

基线 source HEAD `f23c0b260bc82c49712e7725a9b750b34125f85b`，分支 `publication/github-20261008`、清洁；对应公开HEAD `8ac0c3e8bd44aa35dec32cc651c7f8cf19b0d32c`。专项HEAD `4252876e23224df5d29c20492a08da9436dccf4a`、清洁。实际读取了 LATEST、ARCHITECTURE、完整Handoff、Frozen StrategySpec、Owner-Decisions、已有GUI与原生卡/包Schema，确认评分不存在后新增隔离实现。

新增 `experiments/sector_stock_v0/`、`contracts/sector-stock-v0/`、`docs/sector-stock-v0/`；修改workbench只读展示和导航。Node评分复用原锁定的Ajv/decimal.js，Python服务依旧stdlib；没有修改package锁或迁移。当前交付commit由仓库本报告所在commit和公开Source-Snapshot确定，避免在文件内放自引用commit。

## 评分与接口交付

独立实验 `CORE40_SECTOR_STOCK_BASELINE_V0`、版本 `0.1.0-candidate`、namespace `EXPERIMENT:CORE_40:SECTOR_STOCK_V0`。

实现九维板块等权归一化、个股25/20/15/15/10/10/5加权、四个独立硬门槛、三类候选扣分、缺项/未来/过期/未知阻断、Decimal复算、配置/代码/输入/证据hash绑定。个股层实际重算板块层并核对版本引用。任何总分都不是上涨概率，输出 `probability=null / formal_candidate=false / can_produce_order=false`。

四项要求接口 ResearchHypothesis、CandidateSet、EvidenceBundle、ValidationResult 已建Schema，另有ScoreInput/ScoreResult和封闭ReasonCodes。`validateGraph`核对实验引用链、候选与假设/分数对应并复算结果；现有ResearchCard/BrainPacket仅以原版本hash引用，原生合同不变。接口清单及限制见[规则](Scoring-Rules.md)。

**已实际计算的只是合成案例**：中性板块50.00、指定合成股票50.50，以及缺项/风险/边界反例。没有使用旧报告的YTD当TTM、未认证金额当已准入单位，也没有回填真实当前/历史分数。纯函数消费预先形成的证据指标，不等于已实现原始财报自动提取、独立来源认证或全市场选股。

**仍是候选方法**：板块等权、各指标线性锚点、政策/催化编码、客户集中度/杠杆阈值、风险扣分、优化目标及统计协议。Owner本轮指定的是个股七权重与工程任务，没有自动批准M01–M08或真实账户政策。

## 优化与消融预注册

[独立预注册配置](Preregistration.json)记录：逐历史cutoff重建候选/上市退市/行业成员/PIT证据；36m训练+12m验证+6m封存测试、滚动6m、purge/embargo40；基准与9组阈值候选；板块筛选、公司深研、催化剂、反证软排序、时机、退出、组合七项单因素消融；日期化费用、回撤、稳定性、参数敏感性、失败保留及多重比较。

未实现优化执行器，未启动任何候选搜索或观察新历史结果。硬风险、缺失证据、T+1/停牌/涨跌停/费用等不能因“消融”被取消。旧已暴露区间不能改称untouched OOS。

正式五年运行仍缺：历史候选和行业成员的PIT可见性/修订链、来源许可与范围、真实日期化成本/滑点/资金/仓位/风险、六DTO最终字段与消费者审核、M01–M08或替代方法批准、新实验执行适配器、真实窗口/基准和独立封存样本。1260 sessions/100笔交易是目标；预热窗口叠加purge/embargo后可能需要更长数据，不降低要求制造“跑通”。

## 实际验收证据

- [评分/Schema测试完整日志](Scoring-Tests.txt)：45项通过、0失败。含独立手算50.50、精确舍入、上下游篡改/缺项/单位/未来时钟/过期/风险及图引用反例。
- [界面/HTTP测试完整日志](Workbench-Tests.txt)：41个唯一测试通过、0失败（原31+新10）。含拒绝伪造真实分数、未知状态、错误版本、配置失效、同源/只读/文件白名单、读取不改输入。
- [既有回归摘要](Legacy-Regression-Summary.txt)：P0/Closure/schema6校验通过，258项执行=257PASS/0FAIL/1既有可选外部V5 SKIP。未重跑所有历史Wave专属Gate，也未将旧研究复跑WAVE_C_DEPENDENCY_INVALIDATED改成PASS。
- 浏览器实际操作：七页逐项打开；公司报告→原件hash追溯；配置→预注册；合成隔离页面显示FILE_MISSING、UNSUPPORTED_VERSION、UNKNOWN_STATUS。测试夹具有明确横幅，测试服务已停。
- API返回的配置、评分状态、集成状态、Forward状态与源文件逐字段相等；三份私有报告正文与原件字节一致。
- [冻结保全核对](Preservation.json)：基线1058个tracked文件，1049个逐字节未变，9个仅为授权UI/导航修改；19个指定私有封存文件前后hash一致；专项工作区HEAD和清洁状态不变。此结论范围明确，不冒称扫描了全硬盘或所有私有原件。
- [机器验收清单](Checks.json)记录配置/代码/hash、截图位置与测试统计。没有凭证/私钥读取、市场API调用、新采集、原始数据导出、正式策略执行或券商请求。

本机截图/操作记录在 `/Users/qiushi/投资研究/.p1b-archives/sector-stock-v0-20261014/`：`Dashboard.jpg`、`Sectors.jpg`、`Candidates.jpg`、`Stock.jpg`、`Validation.jpg`、`Tasks.jpg`、`Config.jpg`、`Evidence.jpg`、`Preregistration.jpg`、`Errors.jpg`、`Workbench-Preview.jpg`及相应文本。截图为真实浏览器页面，留本地；公开仓库只发布可分享测试/规则/哈希元数据，不公开含受限研究正文的截图。

验收工具纠正记录：Python测试最初因导入TestCase被发现两次而执行63次，去掉重复发现后唯一41项，本报告不重复计数；证据弹窗自动定位最初等待英文MATCH超时，实际页面已正确显示中文“原件一致”，改按实际文字定位并核对hash。未改业务规则或降低断言。

## Owner 下一步

建议先审核本轮候选评分口径和风险规则，再选择一个板块及少量公司补齐可追溯输入，产出首个“真实但仅限研究”的双层评分包；同时由五年专项继续独立补PIT及日期化费用。当前方法尚未经历史/前向有效性验证，不应把高分当作可靠交易建议。

本轮由总控实施及复核，未声称新增独立人类审批或独立Agent审核。七页可使用、数学和接口可复算；真实选股和正式验证仍待证据与审批。交付后STOP，等待Owner。
