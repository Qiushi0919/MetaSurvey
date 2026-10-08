# H-B A–F 完整回归

干净本地副本：**2,101 次执行 = 2,100 PASS / 0 FAIL / 1 既有可选 SKIP**。Python 1,458，Node 643；本轮新增 230（87 Python + 143 Node）。完整入口 `node wave_hb/check.mjs` 包括所有前序阶段。独立审查 28,515 个原子断言另计，不冒充回归执行。

冻结代码候选 `98337a5cb55371b2dc8539a601ed90403c343b4b`，26 个代码 pin / 1,858 项依赖 / 857 个不可变前序文件。锁定依赖离线安装、禁用安装脚本；测试进程正常 umask022、原日志0600；副本执行后干净。原始逐套件计数、日志SHA与run result见JSON。

唯一 SKIP 为既有 V5 外部历史资产 opt-in 回归，未推断资产不存在，旧CLI hash mismatch/seal/14日账本未修改。首次 fresh-clone-G1 正确拒绝新的1.73MB Git地图；exit1与候选保留，调整为小Git索引+完整私有map后重跑，旧1MiB限制不改。此前230项new-only结果属旧候选，不累加进最终2101。

恢复范围仅本机checkout位置变化、原私有证据根不移动；不证明远程CI、actual API、实际公钥或真实签名正向链。实际请求/credential lookup/Forward天数均0，实际G HOLD，完成后STOP。
