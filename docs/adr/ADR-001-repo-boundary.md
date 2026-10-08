# ADR-001 新 repo 与 legacy assets 的边界

状态：P0 工程实现，待 Gate Review；不授予后续功能/生产许可。

背景：现工作区是多代实验、运行状态和证据的资产库，整体迁入会污染工程基线并破坏路径封存。

决定：新独立 repo 为工作区下 ashare-trading-v1。只提交新代码、contracts、migrations、tests/fixtures、docs/ADR、小型配置模板、legacy manifest/adapters。原目录不移动；可配置 LEGACY_ASSET_ROOT 解析工作区相对 locator。禁止大文件、credentials、runs 和运行状态库入 Git；CI/本地检查文件大小与敏感类别。

后果：新 repo 可独立运行 portable tests，外部实际回放另需旧依赖与原资产。没有复制一致性数据库备份，后续正式导入前须完成备份恢复验收。
