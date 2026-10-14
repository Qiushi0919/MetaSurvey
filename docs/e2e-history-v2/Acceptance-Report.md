# 真实历史输入接入 V2：本轮未完成首次真实行情执行

日期：2026-10-14，Asia/Shanghai。**主目标 NOT_ACHIEVED。** 本轮没有取得新的可运行九股行情，没有生成真实 Case，没有调用真实行情引擎。不是“规则未触发所以无交易”，也没有收益、回撤、逐日现金/持仓曲线可供投资判断。工程测试通过不改变这一结论。

## 实际起点与交付

源工作区起点 `21fd58b9f52c3c85d37292180057c3644323934d`，公开起点 `d6f882d731634ad2105ec40ba29219f6007e430a`，开始均干净。五年专项保持 `4252876e23224df5d29c20492a08da9436dccf4a`。没有回退其他工作。

新增独立 `CORE40_RECONSTRUCTED_PRICE_VOLUME_DIAGNOSTIC_V2` / `EXPERIMENT:CORE40:E2E_HISTORY_V2`。原 V1、Frozen CORE40、V0/V01、Forward、旧 seal/pin/账本/原件不变。方法及研究因子先登记在 [Freeze](Freeze.json)，执行数值桥、来源政策、尚缺的例外域在 [执行前补充冻结](Before-Run-Addendum.json) 固定；实际策略结果尚未出现。

| 验收项 | 实际成果与限制 |
|---|---|
| 来源与用途 | 捕获BaoStock官方本地保存/量化分析说明与两所2023/2026规则；仅有限本地重建诊断，不公开原件、不作正式PIT。旧月卡销售主体/产品/用途仍未独立核实 |
| 真实调用 | 官方匿名SDK 0.9.4 两次login均返回 `10002007`；一次系统DNS，一次核对同一官方主机的公共DNS后直连，未改系统网络设置；TCP能连不等于API可用。行情行数0 |
| 输入构建 | 新增scope/身份、完整日历、RAW、单位、重复/缺失、停牌、时间、分红/因子/除权参考价检查，来源原件和代码/config绑定。特殊上市/无涨跌幅历史事件decoder尚缺，真实Case不能准入 |
| 执行器 | 支持现金权益/模拟扣税、整数送转和锁定股、到账现金、收盘后决策/次日执行、中途失败保留已完成账目；工程阳性仅合成测试，真实验证未完成 |
| 新真实 Run | `E2EH2-20261014-ANONYMOUS-SOURCE-FAILURE-01`，`SOURCE_OR_INPUT_BLOCKED`，`engine_called=false`；从捕获与政策重新计算校验通过，保留原失败资产 |
| 当前研究 | 保留27个FY2025财务分项；新增4个可核算业务暴露子分项、7个客户集中度判断。催化/完整风险/完整总分仍未完成，未送入历史选股 |
| 工作台 | 新V2读取器校验Run、来源/输入/代码/配置与研究原件，再复算；不是手填Status。实际界面/HTTP检查见 [UI证据](UI-Verification.json) |
| 测试与保全 | [CI结果](CI-Results.json)、[保全](Preservation.json)、[独立审查](Independent-Review.md)。仅工程可信度，不是投资有效性 |

## 两条实质缺口与下一步

1. **外部实际行情尚未取得**：免费官方接口两次匿名网络接收失败。原因不能仅凭TCP连接确定；不猜备用网关、不买VIP、不使用未核验月卡绕过。建议先恢复这一免费官方来源；如仍不可用，由Owner提供现有合法产品的原始导出及本地诊断用途条款。旧月卡路线需要销售主体/产品、实际有效期及九股历史行情/状态/公司行动本地下载保存分析的书面范围，无需Token。
2. **内部适配仍未闭合**：当前基础资料的IPO日期和逐日isST不能排除历史重上市、退市整理首日等特殊例外。`require_exception_coverage`明确拒绝真实Case，缺少官方历史事件decoder。即使行情API恢复，也必须补齐事件原件、覆盖范围及decoder，并重新冻结后继版本，不能改布尔值或旧Case。

推荐先取得免费官方接口实际响应和事件覆盖证据，再实现这一明确的缺域decoder，保持既定9股/区间及参数。若改用付费来源，需先核实其是否同时提供这些执行域和用途，当前没有可核验报价，不建议先买更多积分。本轮没有采购、凭证读取、broker调用或真实资金行为。请求过一次供应方材料，未收到补充；没有将其当作默认授权。

## 可以复用的命令

在项目根目录运行；原件与运行产物始终Git外。SDK安装到独立临时依赖目录，不改旧锁文件。先最小probe，成功后才fixed-nine。每次 `--out` 和 `--run-id` 必须全新。

```sh
python3 -m pip install --no-deps --target /绝对路径/独立SDK目录 baostock==0.9.4
python3 -B tools/e2e_history/capture.py --sdk /绝对路径/独立SDK目录 --out /Users/qiushi/投资研究/.p1b-archives/e2e-history-v2-20261014/baostock-probe-NEW --scope probe
python3 -B tools/e2e_history/capture.py --sdk /绝对路径/独立SDK目录 --out /Users/qiushi/投资研究/.p1b-archives/e2e-history-v2-20261014/baostock-nine-NEW --scope registered-nine
python3 -B tools/e2e_history/run.py --capture-dir /Users/qiushi/投资研究/.p1b-archives/e2e-history-v2-20261014/baostock-nine-NEW --run-id E2EH2-NEW
python3 -B tools/e2e_history/run.py --verify-existing /Users/qiushi/投资研究/.p1b-archives/e2e-history-v2-20261014/runs/E2EH2-20261014-ANONYMOUS-SOURCE-FAILURE-01
python3 -B -m workbench.server --port 8769
```

最后一项打开 `http://127.0.0.1:8769/`。没有本机私有档案的公开clone会显示缺件，不会显示伪结果。上述capture/run入口可重用，但本版本即使捕获齐全仍会因例外域缺失拒绝真实Case；命令不是“已经跑通”的证明。SDK依赖pandas由当前本机隔离运行时提供，新的环境需按官方SDK依赖安装；不在CI联网采行情。

## 用普通话解释

研究对象仍是PCB的景旺/沪电/深南，高压设备的平高/西电/思源，铜产业链的洛钼/紫金/江铜，未按后续涨跌删样本。四个业务子分数来自明确产品收入占同年合并收入；七项客户判断来自客户披露，不是完整公司评分，更不是上涨概率。缺口保留未知，不用中性分或剩余权重凑总分。

10万元只是虚拟实验配置。本轮没有形成真实行情模拟持仓，因此不能解释“买了哪些、赚了多少”；不能拿合成账本作回答。引擎能处理现金分红和送转的逻辑已经通过受限测试，真实行情下仍未验证。完整五年线还缺合法且完整的执行数据、历史可见版本/候选重建、足够覆盖和已冻结的正式验证条件；本轮未替代五年专项或解锁OOS。

本轮按未完成提交，停止自动推进，不宣称“第四阶段已在真实行情上接通”。
