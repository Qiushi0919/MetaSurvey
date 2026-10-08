# ADR-013：fixture admission 与 manual export

Status: ACCEPTED_ENGINEERING_SCOPE_ONLY，2026-10-05；D01–D04。

SourceAdmissionPolicy1.0 由 trusted parent 批准 hash 白名单；Receipt1.0/BrainPacket1.1 使用 trusted public key 的 ED25519。真实许可/账户/时钟/coverage 无法因 synthetic relabel 成立；scope恒为 SYNTHETIC_TEST_ONLY/FIXTURE_MANUAL_EXPORT。每次 use 重验现有 data snapshot、闭包、原始字节、policy、expiry/freshness、revocation。原协议 hash 不变，新增 explicit projection_hash 绑定净化投影，输入与投影 hash 不能互换。

006 只存 policy/receipt/revocation/audit。append-only，不存 research业务state或执行对象。消费者不访问DB，排除了把PGlite当真正server RBAC证据的误用。多进程生产服务不在scope；新架构需重开Gate。

新schema版本独立，旧BrainPacket1.0 validator与所有历史release原字节保留。fixtures完整来源/hash/time/version链可追踪但不证明真实数据真实性或授权。真实源全BLOCKED。
