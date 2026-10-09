# MetaSurvey 本地只读工作台 v0 验收

2026-10-09，Asia/Shanghai。**本轮软件交付通过：页面已实际启动并接入现有产物。** 这是只读界面的验收，不新增数据/策略Gate。正式历史验证、真实Forward及交易的既有阻断保持原状态。

## 打开与启动

当前本机已启动：[打开工作台](http://127.0.0.1:8765/)。仅127.0.0.1；停止终端进程后服务结束，不自启动或调度。

```sh
cd '/Users/qiushi/投资研究/ashare-trading-v1'
/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m workbench.server --port 8765
```

其他机器使用Python3.12+：`python3 -B -m workbench.server --port 8765`；无新增依赖，不修改旧锁。公开克隆缺少本机研究档案时，页面会显示FILE_MISSING而非演示报告。启动、端口占用、终端输出、读取白名单与验证入口详见 [使用说明](../../workbench/README.md)。

## 页面与真实接入

| 页面 | 实际读取 | 结果边界 |
|---|---|---|
| 仪表盘 | 最新集成Status、ForwardStatus、集成报告 | 7,567价格日期/582财报期记录是报告事实；PIT0、Forward0；报告不是运行心跳 |
| 候选池 | 三股封存研究manifest及Markdown | 研究对象可点开；正式候选未连接，保持真实空状态，不生成推荐 |
| 单股卡 | 603993.SH / 600312.SH / 603228.SH各自report.md | 标题/截止/版本、业务/盈利/现金/估值/行业/催化/风险/未知项和证据索引；不补正式grade、胜率、目标价或仓位 |
| 盯盘 | 已记录Forward状态和冻结策略链接 | 未连接实时任务/日志，不显示Agent运行进度，无执行按钮 |
| 回测与前瞻 | 集成Status/报告、原Day1Status | 历史Lite327日个案诊断、后续五年覆盖、正式引擎、Forward分开；NULL不画净值0 |
| 配置 | 状态、Owner方法待决原文、六DTO缺口、冻结策略、未配置账户模板 | 只读；候选方法不生效，实际账户配置不由服务返回 |

每次请求重新读允许文件，响应no-store。结果带来源、文件SHA、读取时间、报告/数据截止和版本（材料未提供则明确“未提供”）。报告身份由路径和hash确定，未补造run_id。证据按钮实际打开原报告/状态内容和来源hash；研究报告核对冻结manifest的路径/字节数/预期SHA。原始行情、PDF、report.json、数据库不通过Web服务提供。

**实际浏览器操作完成**：启动 → 打开仪表盘 → 点击洛阳钼业 → 打开原报告校验依据 → 浏览候选池、盯盘、验证、配置 → 打开未配置账户模板 → 刷新 → 回到仪表盘。六页可见内容逐页确认；浏览器标签保留供Owner查看。截图、AX操作记录在Git外 `/Users/qiushi/投资研究/.p1b-archives/workbench-v0-20261009/`；[Checks](Checks.json)记录各文件hash及实际操作结果。含本地研究内容的截图没有公开分发。

## 验证与失败记录

**31个独立适配/HTTP用例通过，0失败**；JS语法检查通过。测试涵盖：字段等于源文件、刷新重读、缺文件、非法JSON、错误kind、未知engine状态、版本不支持、bool不冒充计数、报告hash/大小/路径/重复entry、symlink/目录逃逸、敏感内容、实际账户替换模板拒绝、非白名单/跨域/Host/跨站、query拒绝、POST405和读取前后输入字节不变。

真实浏览器另确认隔离合成错误夹具中的FILE_MISSING、UNSUPPORTED_VERSION、HASH_MISMATCH确实显示，带显著SYNTHETIC标签，不填0或缓存结果。未知状态在适配测试中严格拒绝；前端使用同一错误呈现。该错误夹具服务已停止，Owner工作台始终读取真实允许产物。

初次29用例中的13失败/4错误是macOS临时目录别名触发路径拒绝；只将测试根目录canonicalize，未放宽产品symlink规则。首轮浏览器AX采样过早且采用增量状态，产生false检查标志；原记录保留，最终等可见内容并核对完整快照六页通过。最终31用例及前后重复执行不累计，全项目旧Gate未重跑、也未声称通过。

## 保全与安全

所有原tracked文件在导航更新前与基线 `176e2de1a42c1d4e186213770fe84aa307ce155f` 字节匹配；之后仅改AGENTS/README/架构导航/LATEST/INDEX。四份Forward保护文件与15件Wave D封存产物仍匹配原清单；专项worktree HEAD4252876保持清洁。旧策略、原生合同、六DTO、数据库迁移、旧pin/seal/账本和依赖锁均未改。源文件SHA、字段对照、截图/log指纹和保全核对见Checks及Git外Acceptance-Evidence。

Python标准库服务+静态页面，新增代码仅workbench目录。没有数据库连接、credentials/私钥读取、市场API调用、研究/回测引擎调用、Forward追加、模型/云端调用或订单。Host/Origin/cross-site限制、CSP、textContent和固定文件白名单减少本地浏览风险；信任边界仍是可信本机OS，不宣称抵御本机管理员。

## 仍待完成

此版能看已有成果和追溯依据。不能创建研究任务、重新采集、重试实验、签名审批或执行订单。旧研究复跑的WAVE_C_DEPENDENCY_INVALIDATED如实展示，未改pin/seal。共享DTO字段冻结HOLD、M01–M08待Owner决定、真实费用/资金/风险UNSET_REQUIRED、正式PIT/OOS和实际Forward证据缺口，均不被界面验收关闭。

本轮完成后停止，不自动进入受控任务工作台或下一业务阶段。
