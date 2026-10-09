# MetaSurvey 本地只读工作台 v0

在项目根目录启动（Python 3.12+，只用标准库，无新增依赖、安装步骤或锁文件）：

```sh
python3 -B -m workbench.server --port 8765
```

本机已验证的完整命令：

```sh
cd '/Users/qiushi/投资研究/ashare-trading-v1'
/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m workbench.server --port 8765
```

打开 **http://127.0.0.1:8765/**。按 Ctrl+C 停止；端口被占用时使用其他 `--port`。只绑定127.0.0.1，没有后台安装、自启动或调度。进程重启后页面需重新刷新。

六页：仪表盘、候选池与研究对象、单股研究卡、盯盘、回测与前瞻验证、配置。点击研究对象打开已有报告，再点击“查看原报告与校验依据”追溯封存manifest和完整SHA。页面“刷新产物”只重新读文件，不运行任何研究。

默认读最新允许文件，无前端数据缓存；缺文件、格式/版本/状态不支持、报告字节/hash不匹配均显示错误，不用0或旧缓存替代。公开仓库克隆到其他机器也能启动；本机封存研究报告未随Git分发，缺失时研究对象显示FILE_MISSING，公开状态/报告仍可读。

## 精确读取边界

公开文档白名单位于 `workbench/server.py:FILES`，仅包括集成Status/报告、ForwardStatus、六DTO缺口、方法决定表、未配置账户模板（实际账户配置拒绝返回）、冻结StrategySpec、研究manifest、交接readback、Latest和架构。没有任意文件/目录接口。原生合同、六DTO、迁移均不因GUI适配层改变。

私有白名单仅为 `/Users/qiushi/投资研究/.p1b-archives/wave-d-20261006/results/REPORTS-G4/` 下三股各自的 `.report.md`。读取前核对 `docs/wave-d/evidence.json` 的路径、大小和SHA；拒绝symlink/别名、manifest改路径和超限内容。它们是Owner获准本地读取的已封存研究报告，不是原始行情feed。报告里的证据hash可以追查，但原始PDF/供应商response/数据库不由Web服务返回。

不读credentials/私钥/数据库，禁止外部Host/Origin及cross-site fetch，无CORS，GET固定白名单；POST/PUT/PATCH/DELETE均405。CSP限制本地资源，所有产物以textContent安全呈现，不执行Markdown内的HTML/脚本，也不访问其中的外部链接。响应no-store，访问日志禁用；终端只有启动说明。安全边界是可信本机与本地OS，不能防御有本机管理员权限的攻击者。

## 结果语义

每条读取结果包含来源、sha256、实际读取时间和类型；已有报告提供的截止/版本显示原值，未提供时明确标注。仪表盘覆盖数字从现有集成报告提取，不是实时库查询。正式候选未连接，不能从研究对象推定推荐。历史Lite327日、后续五年覆盖、正式引擎和Forward分别显示；NULL/未运行/失败不替代成收益0。没有运行日志/心跳，不显示Agent在运行。

`WAVE_C_DEPENDENCY_INVALIDATED` 来自与已有交接记录中旧CI pin的只读比对，不复跑研究、不改seal。打开旧报告不意味着当前工作区旧研究可复跑；`wave_d.verify`也不包装成新研究入口。

## 检查

```sh
python3 -B -m unittest discover -s workbench/tests -v
node --check workbench/static/app.js
```

适配层合成夹具与HTTP读取边界测试分别标记；浏览器真实操作、页面字段一致性与保全证据见 [本轮验收](../docs/workbench-v0/Acceptance-Report.md)。原有全系统Gate不因这些测试升级。任务执行、采集、签名审批、Forward追加、优化、券商和订单没有UI入口。
