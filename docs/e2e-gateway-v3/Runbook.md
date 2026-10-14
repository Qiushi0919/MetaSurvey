# 现有网关：本地重建历史诊断运行入口

仅用于 Owner 已授权的固定九股、2025-06-03 预热至 2026-09-30，目标窗口 2025-10-01 至 2026-09-30。沿用原 V2 策略与虚拟10万元，V3是来源/输入后继，不是另一套优化结果。方法及实际执行状态以本目录验收报告和 Freeze/Registry 为准。

在源仓库根目录、Python 3.12 环境中运行。新 capture epoch / run_id 必须未使用；不会覆盖旧文件。已有连接配置必须与旧安全连接一致；凭证只经现有Keychain读取，命令不接收Token。运行命令本身不调用行情接口，只有 capture 命令会进行固定范围读取。

```sh
python3 -B tools/e2e_gateway/capture.py --epoch capture-NEW --interval 30
# 中断后，从真实存在的前次 Manifest 续接；只复制验证过的成功原件，保留失败历史。
python3 -B tools/e2e_gateway/capture.py --epoch capture-RESUME-NEW --resume /Users/qiushi/投资研究/.p1b-archives/e2e-gateway-v3-20261014/capture-PREVIOUS --interval 30
python3 -B tools/e2e_gateway/run.py --capture-dir /Users/qiushi/投资研究/.p1b-archives/e2e-gateway-v3-20261014/capture-NEW --run-id E2EG3-NEW
python3 -B tools/e2e_gateway/run.py --verify-existing /Users/qiushi/投资研究/.p1b-archives/e2e-gateway-v3-20261014/runs/E2EG3-NEW
python3 -B -m workbench.server --port 8769
```

浏览器打开 http://127.0.0.1:8769/ 。工作台不采集、不读取凭证、不触发新的策略运行；它校验当前Registry并确定性复算已存在的运行产物。公开clone缺私有原件时显示缺件，不假装通过。新运行需要主控审核后建立独立Registry，不自动改旧版本。

采集失败查对应epoch的Manifest及脱敏wrapper；原始API响应保存在同目录的raw.json但不得公开。构建失败查BuildReport；执行失败查EngineResult.errors、failed_at和已完成ledger/daily，保留部分产物。空仓、无交易、未调用引擎和中途失败分别呈现。

## 离线工程验证

```sh
python3 -B tools/e2e_gateway/check.py /tmp/metasurvey-gateway-check
python3 -B tools/score_review/check.py workbench --out /tmp/metasurvey-workbench-check
```

CI只用明确合成的临时fixture，禁止市场网络/私有档案/凭证；HTTP测试只连本机临时服务。工程阳性不代表投资有效性。

## 证据等级

供应商身份和许可证独立核实仍未完成。Owner本轮批准个人本地重建诊断，不把API成功升级为许可/PIT认证。真实retrieved_at保留；18:00是模拟决策可见性假设，不是倒填的历史available_at。当前选定九股有选择偏差，不能代表全市场。旧Forward、正式五年验证、云端导出、生产和券商均未解锁。

## 本轮已存在产物的只读复核

```sh
python3 -B tools/e2e_gateway/run.py --verify-existing /Users/qiushi/投资研究/.p1b-archives/e2e-gateway-v3-20261014/runs/E2EG3-20261014-FIXED-NINE-01
```

该命令不采行情、不读取凭证；校验原件/版本绑定并确定性复算已登记结果，不生成新的策略选择或交易。
