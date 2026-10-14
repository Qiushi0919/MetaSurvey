# V0 审查修正与首个真实输入核对包

工程候选已实现；真实评分仍 BLOCKED。Owner 已批准 D01–D07 作为候选工程规则，未批准经济评分。未运行优化、正式回测、Forward揭晓或交易。

## 基线与交付

公开起点 `7558a9360d635aea278f7e9e98f3745d76c63e17`；实际源码起点 `574177653f962aae16e40ec02d303adde298e3a4`，两工作区均干净、无后续他人改动。源码与公开仓库历史分开，最终公开 Source-Snapshot 绑定源码提交。本轮仅主控实施，无扩大Agent体系，无修改专项worktree。

- [候选差异](Changes.md)、[具体决策表](Owner-Decisions.md)：分层风险与行业适用性；V0原字节保留，V01 `0.2.0-candidate`。
- [修正预注册](Preregistration.json)：基本面因子固定50的准确消融名称；完整深研增量实验延期；未运行优化器。
- [真实字段清单](Field-Matrix.md)、[固定校验清单](Sample-Registry.json)：18项输入、PCB产品边界与景旺电子单公司；多公司覆盖不足。5个原件/捕获记录只读核对，具体原文/数值在Git外。
- [独立复算](Independent-Recompute.json)：4条原始收入行、半年同比纯算术核对；Fraction独立于生产Decimal实现，不是独立人类签名。不是TTM、不是评分。
- [页面与产物一致性证据](UI-Evidence.json)：实际打开板块页、字段证据、股票页；校验代码/配置/Schema/输入/原件/上游板块引用后展示；不改原UNADMITTED_SCORE_PAYLOAD，也不填Status数组。
- [资产保全](Preservation.json)：原冻结策略、Forward、V0、旧账本/证据、旧pin/seal保全；限定基线全部tracked +19固定私有文件，不声称审计整个磁盘。

本轮准入器只接受固定版本的全阻断核对包；非NULL真实分项/总分仍需经济方法批准和完整原件另行验收。V0 ScoreResult用于兼容阻断链，V01适用性记录独立绑定。没有把UNKNOWN/NOT_APPLICABLE变成ABSENT或0扣分。

## 检查

本地评分72唯一用例（保留45 V0，加27修正校验）；工作台51唯一用例（保留41，加10准入测试）。测试编号按文件和已注册用例区分；V0的NaN/Infinity字符串与数值有同名标签，仍是不同参数用例，不以名称去重误报70。

现有公开回归保持：Node250执行=249通过/1原有可选SKIP；Python209通过。16个原生合同与30个真实配置缺口核对通过。没有通过改旧pin/seal修复历史复跑；WAVE_C_DEPENDENCY_INVALIDATED仍如实显示。

独立Ubuntu/macOS CI：工作流 `.github/workflows/score-workbench.yml`，评分与工作台独立job，唯一用例清单、commit、运行链接及日志作为artifact保存。最终实际运行结果见本页随后补入的CI记录；当前本地工程检查已经通过，远程检查待发布运行。原 `review.yml` 回归保留，原 `p0.yml/real-slice.yml` 不变。

HTTP测试只启动临时loopback服务并使用临时合成档案；审计钩子拒绝私有档案/钥匙串访问，外部连接拒绝。真实页面操作证据单独记录，读取Owner允许的固定本地研究档案，不进入公共CI。

## 使用与剩余工作

在仓库安装锁定Node依赖 `npm ci --ignore-scripts` 后，用Python3.12运行：

```sh
python3 -B -m workbench.server --port 8767
```

浏览器 `http://127.0.0.1:8767/#sectors`。本机可看V01风险适用性、真实资料截止、核对时间、缺口和来源。公开clone无私有原件时显示FILE_MISSING，不伪造数据。

现有同板块真实完整分数0、归一化分项0；仅半年同比算术1项可独立核对。九维板块风险/竞争格局/价格订单、TTM与资本成本、完整事件窗口、成员与分部收入等仍需审批/证据。旧原件有效期与修订链不因本次核对变得完整。下轮优先补这张字段表和具体方法，不启动全市场选股或正式五年回测。

首轮准备遇到财报同期间多个update_flag，保留各行并只在收入完全相同时做纯算术比较，不选版本。政策窗口候选文字误把90自然日概括成60交易日，已恢复V0政策90自然日/催化60交易日，保留初版私有包Sample.json，最终采用Sample-r2.json；不改封存V0。工程验收不代表数据许可、历史PIT或投资有效性。完成后STOP。
