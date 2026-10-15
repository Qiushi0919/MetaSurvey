# 扩展历史与新 Forward 页面核验

## 首份 Forward 启动核验（历史运行待补）

2026-10-15 在本机 `http://127.0.0.1:8769/#validation` 检查真实产物，非合成测试。此节仅验首份 Forward，不能作为五年历史页面最终验收。

- `/api/state` 的 `long_forward.status=VERIFIED`。`strategy_a.plan` 与私有 `Plan.json` 全对象相等，激活记录与 `Event.json` 相等。
- 计划 `FORWARD-A-20261015-BOOTSTRAP-01`：依据 2026-10-14 数据；实际冻结为 `2026-10-15T03:40:40.410179+00:00`；最早执行为 2026-10-16 09:30（北京时间）；启动跳过 10 月 15 日。
- 页面实际显示计划已冻结、买入计划 0、结算 0、观察并结算交易日 0，未将计划当成交。B 显示未就绪，与 A 分开。
- 历史对象为 `null`，页面明确“尚无已登记的历史运行”，没有填 0% 收益。
- Safari / CUA 实际完成刷新、展开“卖出计划与决策依据”、打开注册清单及协议证据弹窗。可访问性文本显示上述字段及对应来源 hash。
- HTTP 读取与浏览前后，已纳入核对的 1,604 个既有文件 hash 全部未变（本轮 Forward 包、冻结运行时、旧 V3 及绩效档案；排除截图和 Python 缓存）。并行历史采集新增文件不在这项既有文件比较范围。

本机证据目录：`.p1b-archives/long-forward-20261015/ui-evidence/`；原始截图和页面可访问性文本在同档案 `screenshots/`，均在 Git 外。机器记录为 `Forward-UI-Verification.json`，保全清单为 `Forward-UI-Before.json`。

截图验收仍未完成：第一张包含页面内容但地址栏处于导航瞬态，后续截图工具返回空白图，虽可访问性文本仍可读取、点击。空白图及瞬态图不计为最终截图通过；未以其他技术绕过桌面工具限制。待历史运行形成后补验实际页面和有效截图。

同一 CUA 工具的备用尝试也未产生有效截图：应用内浏览器返回 `Browser is not available: iab`；独立 Chrome 工作台标签返回 `net::ERR_BLOCKED_BY_CLIENT`。未修改浏览器或系统安全设置。

## 自动化读取与展示检查

正式入口 `tools/score_review/check.py workbench`：169 个唯一用例、169 次执行，0 失败、0 错误、0 跳过。日志 `/tmp/long-forward-workbench-subprocess/tests.txt`。本地该次检查基于 `362b958444d5ffc06ebf439cfe0936249809581c` 加本轮未提交改动；网络仅临时 loopback，私有档案访问仍被审计钩子拒绝。合成用例不作为真实策略表现证据。
