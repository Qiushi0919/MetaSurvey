# E2E History V2 — 独立复核

审查时间：2026-10-14（Asia/Shanghai）。审查者为独立代码审查子Agent，不冒充人类签名审核人。只读业务代码；未修改冻结资产、来源策略、协议或算法。当前文档为候选修正复核记录，最终复核状态见末尾。

## 真实执行状态

已直接读取两次官方BaoStock匿名SDK login原件：probe-01和probe-02均为`10002007`网络接收错误，分别在08:17:08–08:17:28 UTC及08:20:00–08:20:20 UTC。第一轮使用系统DNS；第二轮保存独立DNS证据，解析同一官方hostname到114.94.20.42。主控记录两次TCP连接成功，但SDK匿名会话接收失败；未更改系统网络设置。没有真实行情返回，**不能说已调用真实历史策略引擎或产生真实行情模拟成交**。网络连接成功也不证明产品数据可用。

没有免费官方备用行情端点的可核验文档；官方HTTPS示例下载不是九股目标数据。VIP节点需要API_KEY，不能购买后仍标免费或当绕过方式。推荐等待官方匿名服务恢复，或在Owner同意的本机网络条件下用同一冻结命令复跑一次；另一路为原供应商提供书面用途/产品/期限证明后再准入，或Owner提供已有合法产品的导出与用途说明。暂无新采购必要性证据，未建议直接购买积分/VIP。

## 口径澄清与官方规则补证

公司行动统计两种窗口不同：**2025-06-03～2026-09-30含预热区间为8个去重实施现金事件；2025-10-01～2026-09-30目标区间为5个**。都是旧隔离网关三股原件，不是新准入九股全部事件，不能填NONE。

初审发现Source-Policy只绑定SSE2026，缺少早期及SZ规则。继续查官方已废止归档而非停在缺件：现已取得两所前后四份正文及SSE两版暂缓附件，原件在新私有source-review目录。正常主板条款实际核对如下：

| 规则 | 原件SHA256 | 核对条款 |
|---|---|---|
| SSE2023 | `7aa2319f6dcf597be1e86b3b69d7c2ad0e6acb2a5d0cc6be48a01af602fded40` | 3.3.8 100股；3.3.11 0.01元；3.3.13 10%；3.3.17四舍五入；4.3.3除权参考 |
| SSE2026 | `fc922c433438b2636cb631eab25cca405209712acbb6aaded768c45456ff8888` | 相同普通主板条款，2026-07-06生效 |
| SZSE2023 | `7018114a6e11deb239c2a72e71e49defc6e8841b3e2c093b3bbf809282c67222` | 3.3.8 100股；3.3.11 0.01元；3.3.13主板10%；3.3.14 preclose公式；3.3.19舍入；4.4.3除权基准 |
| SZSE2026 | `9b66f8b0db70f84a25ef1ccb4ee2351001724e408117552d75f6d8993483c586` | 相同普通主板条款，2026-07-06生效 |

来源：[SSE2023归档](https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20250612_10824490.shtml)、[SSE2026](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml)、[SZSE2023归档](https://www.szse.cn/lawrules/rule/repeal/rules/t20230217_598773.html)、[SZSE2026](https://investor.szse.cn/lawrules/rule/trade/t20260424_620190.html)。深交所2023旧公开路径404，已保留失败；成功来自已废止规则通知的实际附件href，不使用非官方镜像。

这证明正常主板规则沿革，不证明九股历史所有日期符合正常状态。ST、IPO/重上市、退市整理等必须另外排除；对当前仅支持isST=0的新路径，不将其他状态默认普通10%。

## 初审问题与修正要求

1. **用途原件绑定不完整**：`source_authority`初版允许删去documents中的home pin，同时仍从未pin的home读取短语。要求强制文档集合、来源/用途/保留边界及政策版本，不接受布尔开关代替证据。
2. **行动日期匹配不等于完整动作解释**：初版仅比因子事件日期与现金/送转日期，未核因子数值、实际preclose和前一RAW close。需要数值与动作解释一致；同一ex日的配股/复杂动作不能被简单现金记录掩盖。参考价残差只可采用预先固定的精度规则，不能根据结果调整容差。
3. **合法preflight失败应能展示**：run可产生EngineResult(status=DATA_BLOCKED, engine_called=false)，初版reader把非空诊断且engine_called=false一概拒绝。需保持重算绑定，允许真实preflight错误结果呈现，不把它变成RUN_NO_TRADES。
4. **历史规则原件缺口**：上述四份正文现已补齐，主控需要将新规则证据绑定到Source-Policy，保留日期版本，不能仅列在说明文档里。

## 已完成的独立工程检查

第一次只读复跑engine新测试：32个唯一用例通过。它们涵盖现金应收/到账、送转锁定、T+1、停牌不伪造OHLC、连续21真实交易bar、部分失败保留、未来行动不改过去决策、固定窗口/样本与外部provenance校验。只证明合成执行工程，不证明投资优势。

另使用Python Fraction独立核对一例现金+送转：登记1600股，每股现金0.50元，模拟税1/5，应收64000分，新增1600锁定股；实际合成结果一致。逐条重加4笔现金流水，80个每日NAV均符合cash+exposure+receivable。没有把此例混入真实市场绩效。

审查代码保留实际retrieved_at与独立模拟18:00决策时钟，未把2026采集时间倒填2025available_at。协议标RECONSTRUCTED_HISTORY_DIAGNOSTIC、当前样本选择偏差和SIMULATED_COSTS；即使未来成功运行，也不是原始PIT或正式五年OOS。

## 当前结论

最终只读复核已完成，结论为部分工程交付、业务主目标未达成。实际外部阻断为匿名数据会话失败；内部仍缺官方历史特殊交易状态事件解码器。九股完整calendar/status/action/factor原件未获得，本报告不支持“首次真实成交已完成”，也不支持“只要网络恢复即可成交”。

## 修正复核（第二次）

独立复跑tools新测试31个（builder16 + current-research15）及history-reader20个全部通过。Reader已允许合法preflight阻断结果，并核对结果状态与run一致；不放宽结果重算。Builder现强制用途文档集合及两所新旧规则原件，新增动作描述拒绝配股/复杂事项、因子正值和每日前收经济桥核验。因子目前仅为异常/覆盖交叉检查，未把具有算法歧义的因子数值直接用于收益。

本次也定位并修复了测试工具问题：测试类自定义`fail`覆盖unittest原方法，使一次预期错误码不匹配递归重跑。该次发现后中断、保留为未完成执行，不算通过；更名及修正fixture后上列31例才是有效完成计数。

附加路径审查提出：run/capture固定元文件也须拒绝symlink/非普通文件，不能只验证目录；该修正的最终状态与实际失败run重算待最后一次核对。

## 修正复核（第三次：便携执行入口）

独立执行`tools/e2e_history/check.py`（输出临时目录）完成**87个唯一用例**：engine32 + builder22 + research15 + run18，0失败、0错误、0跳过；加此前单独history-reader20例，当前已独立完成107个不同用例。便携入口禁止网络和私有档案读取；误将输出目录指定到私有档案时被该保护拒绝，改为临时日志目录后才完成该次测试，拒绝不算测试通过。日志位于`/tmp/metasurvey-independent-e2e-history-v2-check/`，本地运行没有GitHub run URL，不替代双平台CI证据。

Runner现在逐一拒绝Run/BuildReport/Case/EngineResult/Manifest的symlink、悬空链接、非普通文件和父目录别名。可重复核验只读重建case和结果，手改并重封run状态无法绕过实际重算。路径问题关闭。

仍需精确保留普通主板例外限制：当前ipoDate/outDate及逐日isST=0不能单独证明历史区间没有重上市、退市整理首日或交易所其他无涨跌幅限制事件；价格碰巧在10%范围内也不是例外排除证据。应补固定九股的例外覆盖记录，或者明确`RULE_EXCEPTION_COVERAGE_UNPROVEN`阻断，而不声称“所有例外已核实”。

## 最终复核（实际失败产物与剩余工程缺口）

最终独立复跑完成 **110个不同用例**：便携入口88例（engine32、builder23、research15、run18）及history-reader22例；全部通过，无失败/错误/跳过。便携日志原路径 `/tmp/metasurvey-independent-e2e-history-v2-final/`，已复制保全至Git外 `.p1b-archives/e2e-history-v2-20261014/checks/reviewer/portable-final/`，旁附保全hash清单；22例reader运行日志保留于本次工具输出，未伪造成文件原件。本地平台为macOS/darwin，检查时Git HEAD为`21fd58b9f52c3c85d37292180057c3644323934d`，新工作区修改尚未提交；该HEAD不是新功能已公开提交的证明。Ubuntu/macOS远端CI状态由主控另提供实际运行链接，本文不冒称独立运行过Ubuntu。

特殊状态覆盖现已明确阻断：真实builder调用`require_exception_coverage`固定抛出`RULE_EXCEPTION_COVERAGE_UNPROVEN`，不能靠输入布尔值、ipoDate或isST清除。合成正向测试明确patch为`SYNTHETIC_ONLY`替身，并有独立不patch必阻断用例。因此测试通过证明其余转换/执行逻辑和阻断行为，并不证明真实九股适配已经闭合。未来需合法官方事件原件、范围覆盖与实际decoder，在新代码/配置冻结后重新运行，不能把当前失败包改写成成功。

已独立执行`verify_existing`完整重建以下真实失败run，再调用`workbench.history_reader.load(Reader())`核对实际展示引用链：

- run_id：`E2EH2-20261014-ANONYMOUS-SOURCE-FAILURE-01`
- Run.json SHA256：`9076e1f60016430cf76f3902e6e633b40a5946e0220905baa07f93c6ee97e9f2`
- BuildReport.json SHA256：`1168b219ec4b1955e35fbaefde30264c1e6cc04a6e9f00a8044798744b5b127e`
- 实际状态：`SOURCE_OR_INPUT_BLOCKED`；错误：`ANONYMOUS_SOURCE_LOGIN_FAILED`；`engine_called=false`；Case与EngineResult均不存在，页面diagnostic为NULL。
- Reader状态`VERIFIED`仅表示已固定原件/pin与重算一致，不表示历史数据或研究已准入；真实历史模拟成交未发生，收益/回撤不得填0冒充结果。
- `Before-Run-Addendum.json`全部11个代码/配置pin与审查时文件一致，覆盖实际builder、runner、engine及来源/输入规则；本次复核未修改这些文件。

对当前研究新产物再以独立临时Fraction脚本复算4个可得业务收入比例、9家公司客户集中度判定（7个有结论、2个未知），结果一致；9个完整七项总分均为NULL。精确分子分母与复算产物保存在本机研究档案。平高已披露客户口径触发10分扣分，其余6个可判定对象为0；上界判定/原报告归并口径不能变成精确最大终端客户比例。此次是产物算术与引用链复核，不冒充对新增摘录的全量人工源头审计、许可认证或独立人类签名。

最终结论：失败可追溯、来源规则补证、合成执行及只读重算链已交付；**首次真实行情成交引擎运行未完成，完整研究策略尚未完成验证**。应优先取得可实际访问的用途合规历史来源，并补齐九股特殊交易状态事件覆盖/decoder和行动链；两项都完成后才能重新冻结并运行。不得因工程测试全绿标本轮业务主目标PASS。
