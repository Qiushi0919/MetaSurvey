# Gateway V3 独立工程审查

日期：2026-10-14。独立代码审查Agent，不冒充独立人类身份或许可认证。只读业务代码与私有原件；未读取凭证、未调用认证接口、未改V2/旧资产。此次以Owner最新授权的本地重建诊断为边界，来源许可问号保持可见，不因缺少客服材料自行否决整个工程。

## 实际采集与续传

直接读取并以builder重建新capture-01/02：两份日历各485行、首只stock_basic一行和daily327行。01停在stk_limit的`IP_CONCURRENCY_LIMIT`；02继承成功原件后取得stk_limit327行、suspend_d合法空响应，随后adj_factor再次限流。02续传链核对26个manifest/wrapper/raw pins，继承原请求/采集时钟，没有把复制时刻伪装成重新抓取。两份都返回明确失败，不产生Case；尚无真实策略引擎执行或模拟成交。

本轮固定同端点；限流后停止，不换IP/服务商。后续受限同端点续传是新capture，需保留前驱manifest/hash，不能删除失败。空响应仅是已调用且零记录，与NOT_CALLED不同。

## 初审发现及待修正

1. `verify_existing`未核定provider_license_status、source_epoch、cost_label、scope的固定边界值。重新计算content_hash后可能把许可标签改为VERIFIED仍通过；Reader只补source_epoch不足。需固定校验这些标签，不能把可重新计算hash视为权限签名。
2. 空表未校产品最低Schema。独立合成复现：将suspend_d原始响应及一致wrapper的fields改为[]、items仍[]，重封manifest后builder仍ADMITTED。应对空表同样校必需字段，防止未实现接口的空壳变成“没有停牌”。
3. namechange目前取出后忽略。应至少验证身份/日期/Schema并准确标REFERENCE_ONLY，或实施历史名称覆盖；不能在文档称已验证全部历史ST/重上市情况。直接每日限价解决的是限价来源，不是完整状态事件审计。
4. Input-Plan的“relist ambiguity blocks”比当前实现保证更强，需精确写明仅当前证券身份、实际逐日限价和停牌交叉，而非声称已审完历史重上市事件。

## 初次独立测试

便携入口`tools/e2e_gateway/check.py`：73个唯一用例，4错误、0断言失败、0跳过；4错均来自新run测试的macOS临时目录别名（/var与/private/var）触发路径保护。修正应发生在fixture.resolve()，不放宽生产symlink/alias检查。日志`/tmp/metasurvey-independent-gateway-v3-review1/`，该轮不得计全绿。

`workbench.tests.test_gateway`另22个唯一用例通过，涵盖只读投影、本机HTTP、错误状态、pin修改、path/symlink、执行状态冲突、空调用与未调用区分。它们是合成工程检查，不是真实数据或投资有效性证明。

## 动作与运行规则初审

- daily价格不复权；成交量手×100、金额千元×1000，Decimal从字符串/整数读取，拒绝binary float。
- 每个开市日必须有正成交daily与实际限价，或有明确整日S且缺daily；未知缺口不造OHLC。盘中停牌、停牌却有成交条均阻断。
- dividend仅实施记录，税前现金与总送转比例分开；送转总数等于分项之和。实际record/ex/pay/div_listdate分别使用；缺日期与冲突版本阻断。
- 因子变动日期与支持的行动逐日对应，原始close→后日除权preclose经济桥核对。未知配股等不能凭标签假定没有；目前不是完整公司行动源头认证。
- 采用实际限价，0/NULL/缺失/倒置/非tick价格及OHLC越界阻断，不补10%默认值。
- 原策略与V2 engine复用，V3仅新来源epoch和输入政策；实际结果前需冻结全部新业务代码。生产/PIT/云端权限不提升。

当前结论：修正复核进行中，真实完整输入尚未取得。初审测试与部分采集不能替代首次真实成交验收。


## 首只完整产品的真实字段复核（不运行策略）

capture-03首只景旺已取得327日daily、327日adj_factor、58条dividend和2条namechange。窗口内4条实施披露对应2个完全相同经济字段的事件：2025-06-11税前0.8元/股、2026-05-18税前0.55元/股。两组分别有不同ann_date，实施公告/登记/除息/派息/金额一致，不能重复计现金。原件stk_div明确0，stk_bo_rate/stk_co_rate为NULL；这证明总送转为0，分项未报告，不应把分项偷偷填0，也不应把已知总量认作缺失。红股上市日仅在总送转大于0时需要。

独立Decimal脚本逐条核对327日的326个原始close→下一pre_close转移，应用上述明确现金/总送转口径，0处不一致；因子恰在两次除息日变动。未运行策略、未计算收益。namechange两条完全相同，参考视图可去重但保存原始数量。原件包含停止实施记录，应明确排除，不与实施事件混合。以上语义适配应在首次真实策略结果前固定。


## 修正后独立复核（首次真实策略运行之前）

第二次便携入口独立完成89个唯一用例，0失败、0错误、0跳过；Reader22例再跑通过。初次4个路径错误已通过修正测试临时目录.resolve消除，生产路径校验未放宽。第二轮便携日志为`/tmp/metasurvey-independent-gateway-v3-review2/`，本次为macOS本地执行，检查时HEAD为`ecfdf9b0dc695f5bc4c533fc73a37c0099d74655`，工作区新修改不等于该公开提交已含本轮成果。

已关闭初审四项问题：Run固定许可/成本/来源/范围标签；空表必需Schema；namechange严格身份/日期校验并标仅参考、精确重复留存hash；Input-Plan不再承诺全历史ST/重上市审计。经济事件精确一致的多条披露合并执行一次，金额/日期或组件披露冲突仍拒绝；明确总量下NULL分项保留NOT_REPORTED；停止实施排除并保留原始进度和行hash。

本次追加发现Source-Policy的kind/version仍只查非空，而不是固定schema版本；已要求固定GatewayLocalResearchPolicy/3.0.0及负向用例，复核结果待补。此为版本合同校验问题，不是重新要求供应方认证。


### 静态阶段最终复核

Source-Policy现固定`kind=GatewayLocalResearchPolicy`、`version=3.0.0`，新增错kind/错version负向用例，测试fixture另有SYNTHETIC_TEST_ONLY标识。真实当前source_authority读取通过，仍返回Owner限定本地重建且供应方/许可未独立认证。

最终静态便携入口独立复跑91个唯一用例（engine32、builder51、capture-plan3、run5）全部通过；另22个Reader用例通过，共113个不同用例。临时原始日志`/tmp/metasurvey-independent-gateway-v3-static-final/`已保全至新Git外`e2e-gateway-v3-20261014/checks/reviewer-static/`。此前失败记录仍保留，不用新结果覆盖。

此阶段没有发现尚未修正、会允许上述已测坏输入/许可标签晋升的阻断级问题。判定仅限当前工程静态与合成检查；capture仍在进行，未审完整真实Case/策略结果，不能提前认定真实成交目标完成。完整输入取得后另作实际原件与算术复核。


## 空停牌响应契约补查与候选修正规则

实际原件核对纠正：此前称capture-02“正常字段”不准确。三PCB真实suspend_d均为HTTP200、整数code0、msg=null、data={fields:[],items:[]}，请求明确含ts_code/trade_date/suspend_timing/suspend_type四字段。原件未返回列，不得声称已校验响应Schema。

[官方HTTP说明](https://tushare.pro/document/1?doc_id=130)只规定data含fields/items；[官方SDK client.py](https://raw.githubusercontent.com/waditu/tushare/master/tushare/pro/client.py)在code=0后直接把items、fields传给DataFrame，因此空列空行可得到合法空表。这个实现证明客户端兼容该表示，不保证网关已经完整实现停牌数据或不存在盘中停牌。两份原件新存`source-review/Empty-Response-Contract-Receipt.json`，SDK原件SHA256 `2919f2a844201a5de4e613964231245c042f9ac463d155ec16ff3bb6da467af1`。

推荐在首次真实结果前冻结一个限定的输入规则修订：只对suspend_d的精确空shape、完整原请求fields、明确成功状态与完整原件链，记`EMPTY_TABLE_SCHEMA_NOT_RETURNED`；该证券必须全交易日都有真实正成交日线、有效实际限价及完整因子。任一天缺bar不得用此空结果推定停牌或正常，也不得前填。非空或部分字段错误、其他API空schema照常拒绝。`response_schema_verified=false`、`intraday_halt_absence_proven=false`，执行仍标日线开盘代理和供应商未报告停牌的重建假设。

这项修正有具体协议与实际返回依据，适用于Owner授权的有限重建诊断，不是无条件删除旧检查或证明全日可成交；旧初审发现及旧测试结果保留。它不能提升PIT/许可/生产准入。建议不为获得形式上的空表列名重复扩大请求，必要时只在已授权同源同范围做实测。

建议负向测试：缺daily/limit/factor、缺/错request_fields、部分response fields、非空坏表、data或items缺失、非200、非整数0错误码（含bool false）、其他产品空schema、明确盘中停牌均拒绝；合法例外保留未认证标签。该修订的最终实现和实测结果待主控交付后复核。


### 输入规则 3.0.1 最终独立静态复核

新规则已实际落盘，旧3.0.0另存`Input-Policy-3.0.0.json`。3.0.1记录前版本hash与首次策略运行前登记时间；不修改V2策略语义。窄例外只适用于原件与wrapper一致的suspend_d精确空表，完整请求字段、整数0错误码、HTTP200、EMPTY_RESPONSE均核定。缺任一天真实daily/limit/factor仍阻断，正成交量、有效OHLC、实际限价与因子行动检查继续执行。其他产品空schema、非空坏表、部分schema均不获豁免。Case逐bar保留`suspension_schema_verified=false`及`intraday_halt_absence_proven=false`，输入限制列出适用证券。

独立复跑便携入口105个唯一用例（engine32、gateway73），0失败/错误/跳过；其中新增14个空表兼容边界测试。Reader22个唯一用例再次通过，注册测试共127个不同用例。本审核另外从合成fixture分别破坏原始data为null、删除items、删除fields，保持wrapper与新hash重封，3次均被ORIGINAL_WRAPPER_CONTENT_MISMATCH拒绝；这3项为临时独立负向实验，不混入105/127注册用例数量。全部记录保全在Git外`e2e-gateway-v3-20261014/checks/reviewer-schema301/`。

静态结论：本次限定空表兼容修订与其保留的不确定性相符，未发现该修改绕过已测必要价格/限价/因子/原件/身份/时钟条件。允许主控将此作为新输入政策冻结后继续实际Case构建；这不是独立许可认证、全时段无停牌认证或真实策略结果验收。本复核没有执行真实历史策略，也不承诺尚未完成的九股全量输入最终通过。实际Case和运行算术仍需单独复核。

本次代码核验hash：
- `tools/e2e_gateway/builder.py`：`sha256:cd99b5c62a9e8e4015bc47f34ea9d85e755d71715cb3fbc76df51431736a8fa6`
- `tools/e2e_gateway/tests/test_builder.py`：`sha256:989f27353a6640cb7023c2e9a38868dbef9076fd9e1fcca2bf54aa2982faffb7`
- `experiments/e2e_gateway_v3/input-policy.json`：`sha256:864c8b6b7375c5bcb242690a3d64579726fb0ac51c2df2c2ad42d66ff522cef1`
- `docs/e2e-gateway-v3/Input-Policy-3.0.0.json`：`sha256:277255bc25ad7ec699323b9081a17f15e0bedbb4a303daff7075c37239c21b22`


### 预披露与最终冻结补核

随后实际源表出现`预披露`，新代码将它明确列为非实施状态，保留原行hash、报告期、披露与执行日期字段；不生成现金/股票权益。该行若携登记、除权、支付、红股上市或实施公告日期，直接报PREDISCLOSURE_WITH_EXECUTION_DATES_CONFLICT，不静默排除。未知进度仍报ACTION_PROCESS_UNKNOWN。新增3例覆盖正常预披露、带除权日期、带实施公告日期。

独立复跑最终便携入口108个唯一测试（engine32、gateway76），全部通过，0失败/错误/跳过；另上一复核Reader22通过未发生相关代码变更，合计130个注册用例，不把重复执行加数。Freeze.json登记时间2026-10-14T09:15:03.216086+00:00，其16个代码/配置pin独立计算全部一致。前段记录的代码hash为此前复核时点，最终依据以本Freeze为准；不倒改旧记录。日志与逐项pin结果在Git外checks/reviewer-prefreeze108/。本阶段静态签核完成，仍未由审核人运行真实策略，等待完整实际Case与运行算术复核。


### 完整原件中的除权前收字段语义核对（3.0.3候选，策略运行前）

完整capture-04的9股2943组daily/stk_limit逐条对比，发现7处pre_close不同；独立读取72个wrapper/原始JSON并核manifest/raw hash及字段内容一致。7处都在已核实施现金除息日，限价表pre_close等前一真实未除权收盘价，日线pre_close等已披露现金/总送转后的0.01元HALF_UP参考价；登记日为前一真实交易日，当日因子变动，实际OHLC处于实际上下限内。

|证券|除息日|前一RAW close / limit.pre_close|daily.pre_close|税前现金/股|
|---|---|---:|---:|---:|
|600312.SH|20260625|18.37|18.23|0.143|
|601179.SH|20260625|16.26|16.21|0.054|
|002028.SZ|20260708|165.95|165.25|0.6998907|
|603993.SH|20260909|18.94|18.85|0.095|
|601899.SH|20260626|25.92|25.54|0.38|
|601899.SH|20260821|34.25|33.83|0.42|
|600362.SH|20260717|42.11|41.51|0.6|

仅据这些实际记录，支持另记输入政策3.0.3：已核实施行动日允许limit.pre_close严格等于前一RAW close或当日日线除权基准两种明确语义；存两原值与选择标签。每日因果现金/送转价格桥仍必须通过，非行动日差异、第三种值或缺项仍阻断。实际上下限继续来自原件，不以公式重建。7处上下限也匹配daily基准10%是本次旁证，不被提升为所有日期/证券的限价规则证明。

原件逐条数值、实施公告/登记/支付日期、披露行hash、因子和边界检查存Git外checks/reviewer-actual/Preclose-Semantics.json；0处无法解释的差异。旧阻断结果及Freeze应保全，新政策在首次策略结果前另冻。此处是语义候选复核，最终代码/测试尚待接收；未执行策略。


### 3.0.3 实现与测试签核

已核实现：独立保存previous_raw_close，只有确认实施除权日才允许限价表前收等该原收盘；其余差异拒绝。每日因果经济桥仍单独强制，Case与BuildReport保留原前收和语义选择。null前收明确LIMIT_PRECLOSE_MISSING。未改上下限、实际OHLC、策略或费用。新负向例覆盖非事件差异、除权第三值、伪daily桥、无实际前收、null等，正向保留两种已声明语义。

便携入口独立复跑117个唯一测试（engine32、gateway85），全部通过，0失败/错误/跳过。此为当前最终输入规则测试；以前105/108等仍是各自时点记录。复核日志与代码hash在Git外checks/reviewer-schema303/。限定静态签核完成，可由主控冻结新R3后继续首次真实引擎运行；本人仍未运行真实策略。
- `tools/e2e_gateway/builder.py`：`sha256:c7f18a86de6393ba3a5c8a62d99d01e462ee0ff0df29496dd59865831f39c6d1`
- `experiments/e2e_gateway_v3/input-policy.json`：`sha256:054220c9905270982c4122e428e35fd2bd5dadb433bf19f1dd1f278bb568486d`
- `tools/e2e_gateway/tests/test_builder.py`：`sha256:eb30ac97265f648dfb7fda12ae60a7d564ec5082ee4d1364a8be859a17c8291a`


## 首次真实运行独立算术验收

实际run `E2EG3-20261014-FIXED-NINE-01` 为SIMULATED_TRADES，engine_called=true。Freeze-R3登记早于Run的2026-10-14T09:33:21.518878+00:00，其16个代码/配置pin与Run完全一致。独立脚本在结果产生前准备，仅用标准库Decimal，不导入或调用生产engine、quote、费用helper，也不启动第二次真实策略。

实际输入为9股×327日=2943日线（含预热）；目标为2025-10-09至2026-09-30的241个交易日。重算70条成交（35买、35卖）、95条账本、241日净值、23项公司行动权益，5811项逐条断言0差异。这些是同一实际run内的检查次数，不是5811个统计独立样本或独立策略测试。

独立一致结果：期末现金/净值105,969.76元，末持仓及应收均空；35笔完整模拟交易；净收益5.96976%，最大回撤约10.66275%；费用534.24元，滑点711.00元已包含在成交价格内，未再次扣现金。两次分红现金共84.00元，按冻结模拟20%税口径重算。全部成交的整手、T+1、次日候选/卖出指令引用、同日卖先买、实际限价/日线范围/成交量边界、建仓与板块/总仓位限制、2ATR止损估计损失与1%风险预算、账本现金守恒及每日持仓/NAV均核对。

83条未成交中，独立另核5条滑点越日内范围：均确实越界，且无同日同向成交；其中两次卖出受阻后分别保留200股与100股，未虚构退出。其余78条未成交的全部机会排序/最优可买整手数量未独立穷尽复演，不能宣称这一层已经双实现全覆盖。

公共汇总见`Independent-Arithmetic.json`；脚本、逐条私有原件与详细算术记录保留Git外`checks/reviewer-actual/`。本验收支持“第四阶段执行工程已接通，完整研究策略尚未完成验证”。本次执行的是冻结量价诊断，九维研究评分没有被这次收益验证；当前选出的九股、已暴露历史、供应商重建、日线开盘代理、模拟费用、许可未独立核验与盘中停牌未证明限制继续存在。5.97%不能当成正式OOS、五年验证通过或实盘预期。
