# W1 类型澄清（不改合同或边界）

SourceAdmissionPolicy schema 明确无 proof，信任为 parent constructor 的 approved hash 白名单 + issuer identity + canonical body 校验；W1 registerPolicy 的“验签”在该对象上指这套校验。Receipt/BrainPacket 必须 ED25519 验签。旧 schema 不变。

signPacket 参数细化为 {snapshot,receipt,now,body?}，service 复核原闭包和 receipt，重新生成唯一允许的 projection；如提供 body 必须 canonical exact equal。没有 generic signObject capability 返回给调用方。

active closure provenance 与 historical P1A proof 分开保存。旧 P1A verify 是 schema5 历史验收入口；本阶段 check 用 schema6 的 verify-closure，同时严格检查旧合同/001–005/P0 gates 原字节，以及当前全部 committed implementation。唯一旧测试改动：integration replay 的 exact schemaVersion 从5升6；经济、安全断言保持原样。

W1 shared_api_files 的哈希记录的是开工前 shared helper 初版（可在299313c恢复）；schema/006字节冻结。Parent 在不改接口/权限的情况下追加sanitizer字符串 account/outcome 检查，最终代码由新active provenance覆盖；不把初版helper哈希冒充最终实现。

Code/schema epoch：parent fixture factory先验证当前实际committed CodeProvenance，再把code commit/schema6/packet1.1.0/receipt1.0.0加入policy.object_id，只有该epoch policyhash进白名单。旧policy/receipt不自动批准；只读unit fixture helper可独立复现数据攻击，防止provenance提前失败掩盖数据guard。该规则不证明真实source授权。

W4 Reviewer P1 修复：新增 trusted parent `withPacketUse({packet,snapshot,purpose,strategy_id,now,operation})`，在共享同DBhandle进程内队列里真实verifyPacket后发布文件及记录接受。policy registration、receipt/policy revocation 使用同队列，避免最初verify后撤销仍发布。callback不接收DB/private capability；没有JSON/consumer调用入口。拒绝只清理本次新文件，不删除既有历史导出。多进程/DB owner绕过不在scope，C23/C47仍保留；已经读到的bytes不可追溯撤回。旧4schemas与006不改。
