# Snapshot B / NO_DECISION Paper：未来单次盘后执行手册

**本轮只交付准备与离线演练。真实捕获/Paper尚未授权，也没有调度任务。**
2026-10-08为计划候选日；交易所假期公告不是“当日已经完成交易”的证据。
需要实际开市、实际EOD数据和独立验收，时钟到16点不能代替数据完整性。

## 现在可执行的复验

在新工程目录运行 `node wave_f/check.mjs`，使用项目约定 bundled Node/Python。
它只校验旧冻结证据、读取本轮独立公共资料、做严格 synthetic 演练和回放。
不会读凭证、联网下载、等待日期或生成实际 Snapshot/Paper。不能重新运行
exclusive producer覆盖已交付 epoch；`verify_saved`为只读。

## 实际捕获前的单独 Owner 授权

确认仅603993.SH/600312.SH/603228.SH、本机 LOCAL_ONLY/NON_TRADEABLE、当前
source remains QUARANTINED，授权一次真实read-only捕获和独立审查，是否允许
合格session产生无金额/无委托 NO_DECISION 记录另行写清。不要在授权文本里
附凭证。凭证只从既有本机secret store读，不从聊天或旧日志恢复。

Owner需确认source exception/capture acceptance、研究版本/解释政策、审查角色与
冻结bindings。真实本金/费用/风控参数不阻塞无金额 NO_DECISION 的工程准备，
但策略评价/经济Paper/任何订单仍需这些独立参数和Gate。
**目前并非“只差一句 HUMAN authorization”：实际session/EOD、source policy、
策略解读及真实capture/review/approval issuer接线尚须在单独激活阶段验收。**
本轮全部actual入口硬阻断，caller flag/hash/LLM文字不能解锁。

## 未来捕获与验收顺序

1. 验证最终commit、代码/策略/来源/Schema/审查版本hash及所有旧证据完整性；
   source policy不准从技术API成功升级为license/transport/provider verified。
2. 创建全新私有exclusive捕获epoch，目录0700、文件0600。Snapshot A是旧三股
   current-observation anchor，不能改称 admitted snapshot。所有失败都另存；
   不覆盖A或先前B候选，不复用capture_id。
3. 从实际交易所session证据校验当天开盘/收盘；仅日历计划保持UNKNOWN。
4. 使用经授权collector捕获当天exact3 raw unadjusted EOD、证券状态、来源/单位。
   所有当前响应原文先保存/hash，再做标准化。保存request/capture identity、
   实际retrieved_at及available_at依据；DATE_ONLY不补午夜；不知道published_at
   时保留UNKNOWN，不能借用fixture纳秒时钟伪造精度。
5. 检查当天session每股数据确已更新且retrieval晚于A及实际EOD；缺失bar不是
   停牌或正常交易证明。当前严格准备算法要求3个bar，确认停牌的无bar情况需
   明确新版本的独立状态证据/NO_DECISION完整性规则，不能假造flat bar。
6. 对账A→B日期、不同capture与raw hash、source/rules/strategy/policy/Schema
   版本。拒绝旧响应重贴新日期、重复当天/重复内容身份、未来时钟和未解释冲突。
7. Independent Reviewer直接重开raw originals，对freshness、clock semantics、
   scope、source exception、政策版本及权限攻击；caller自签review不是实际review。
8. 全部关键条件合格且有针对Paper的单独HUMAN许可，才由真实独立issuer生成
   NO_ORDER/NO_DECISION研究记录。必须safe_to_trade=false，不生成native
   Card/Candidate/Signal/Approval/OrderIntent/Fill或broker动作。
9. 真实actual_forward_days只能通过已验收的独立实际session增量；fixture天数、
   日历日期、截图、尝试次数与未通过capture一律不计。此次交付始终为0。

## 私有账本、失败与重启

本轮 `wave_f.activation` 的 capture fixture v1.0.1 对每个session原始packet
校验canonical payload hash、来源、日期、证券、值、单位和时钟，不能只改外层
日期把旧原文晋级为新鲜。它只提供 `.wave-f.fixture.sqlite3` 正例，绝不用于实际Paper
计数。它测试hash chain、expected-head原子append、day/capture/observations去重、
NO_DECISION、失败sanitized reason chain、并发single winner及事务rollback。
完整失败原文应在未来实际capture epoch另外按授权保存；fixture失败链刻意不保存
未验证payload、敏感字符串或其hash。

重启先只读校验路径/Schema/metadata/两条完整chain，验证最后head与版本；需要
新批准后才能append。损坏保持原文、停止，不truncate、不re-seal、不修账来绿灯。
hash chain不证明抵御特权整库替换或恶意解释器。真实store/权限与批准issuer
必须在未来实际激活时再审，不能借用process-local synthetic capability。

任一critical freshness/source/clock/status/version/integrity失败：不创建合格B，
不增加actualdays，保留失败并STOP。成功也不开放历史PIT、cloud/model、正式
策略评价、Signal/Order、broker或production。本轮交付后STOP，等待Owner验收。
