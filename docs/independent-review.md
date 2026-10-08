# P0 独立审查与关闭记录

审查角色：p0_reviewer；只读，无业务规则/预期值修改权限。最终结论：在本轮 P0 范围未发现未关闭的阻断缺陷，不能外推为生产可上线。

| 问题 | 修复与反例 |
| --- | --- |
| BrainPacket 嵌套证据 bypass hash / future cutoff | 嵌套 DataEnvelope 重新验 Schema/content/payload hash + PIT；独立断言 FUTURE_DATA / HASH_MISMATCH；外部清单另做 exact binding |
| signal/card rule_version 不一致或缺 trigger | wire chain 和 SQL order trigger 同时绑定版本和已触发状态；honest reseal/rebind 仍拒绝 |
| global Decimal 精度20造成大金额假通过 | 私有 precision100；最大合法价格×safe quantity 用独立 BigInt oracle；错误32位分值拒绝，全局精度3也不改变结果 |
| symbol/exchange/code矛盾，零订单价格 | 身份 canonical 关系与正价/tick 校验，SQL成本/草稿正价格 |
| snapshot 自报旧时钟引用未来公告 | SQL typed source allowlist 查实际版本/hash/source/四时钟；伪报时钟拒绝，未知 dataset 拒绝 |
| financial retrieval 先于关联公告 | publication/available/retrieved 输入谱系核验，原 OBSERVED 反例拒绝 |
| SQL卡缺账户/模式、成本缺证券 | 关系字段与复合 FK 补齐；跨 account/mode/security 反例拒绝 |
| snapshot内容 hash 与 dataset hash混同 | 分列 content_hash/data_hash；引用合同内容与回测数据摘要分别绑定 |
| wire/SQL enum 与 ledger mode不同 | 人工 USER_*、INITIAL_RESEARCH、INVALIDATED、UNSET grade、DEV/PAPER 对齐；规范化完整适配不伪称已实现 |
| DATE_ONLY Packet 写入有日历但读回丢上下文 | readContractFixture 第5参 context；独立专项1通过，缺日历仍UNKNOWN_PUBLICATION，P2关闭 |

审查员最初默认全套复跑 95 项：94通过、0失败、1项外部默认跳过；随后独立复跑外部 legacy 12/12，以及上述修复反例和 DATE_ONLY 专项。总控后来加入未来 BAR 时钟、实际旧 fixture staging、P0全部配置也不放行等测试；最终总控全套数量和证据以 Gate Review / p0-validation.json 为准，不能把早期数量当作最后结果。

原 native seal mismatch 未关闭：verify exit2、85锚点未变、seal_modified=false。独立 reviewer 实测 Python hook 阻断写、删除、network/socket和subprocess；这个 guard 是误写防护，不是对抗恶意本机原生代码的权限隔离认证。

后续 Gate 限制：规范化全部投影、真实来源与 hash 核验、可信身份认证、部分成交收费、并发迁移锁、外部 PostgreSQL/RBAC/恢复演练、行情时钟质量/券商费用和连续 Paper。当前无真实交易传输能力，账户/费率/风险仍未定。
