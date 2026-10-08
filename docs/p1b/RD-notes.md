# RD 实施与真实数据限定准入

Goal / Context / Inputs / Outputs / Interfaces / Constraints / Tests / Definition of Done 均以总控冻结的 `Interface-Freeze.md`、`Interface-Clarifications.md` 和 ADR-015 为准。本 agent 仅写获准的六个 owned paths；不改 shared contracts、旧 migration、旧 source pin、V5、费用/账户/策略规则；无 Git mutation。

## 实际正向范围

新原始 TLS 捕获为 SSE 节假日公告和官网法律声明，manifest 与小原件位于 `p1b/tests/fixtures/real-reference/`，不是 synthetic provider payload。Calendar hash `sha256:779cbf7cc7ab2c4b34db17ceee29e266bc483e075860d8313b85c1d5d0f307bc`，terms hash `sha256:26733c0c6cd93428d1ec5d62401b6ad269a26990a9181c5f5d63237c35431f69`。Raw 原件另有外部 archive；agent 不进行追加行情/财务采集。

Source=`official:sse-calendar-reference`，datatype=`CALENDAR_REFERENCE`，namespace=`CORE_40`，purpose=`LOCAL_NONCOMMERCIAL_CALENDAR_REFERENCE`，transfer=`LOCAL_REVIEW_ONLY`。只有公告明确指出的 9/25–27、10/1–7 休市、9/28 和 10/8 开市、9/20 和 10/10 周末休市。Coverage 默认仅为这些事实的 2026-09-20～2026-10-10 有限包围范围，其他日期保持未知；可以由 parent 批准更小区间。`symbols=[]` 表示零证券覆盖，既不是全市场也不是可选股 universe。没有假设普通工作日均为交易日，没有实现完整日历或 board rules。

正文署名日期 2026-09-17，URI 虽含 20260915 也不能改成 09-15。网页生成时间不是 intraday 发布证明。SourceObservation 中 `published_at=null`、published_date=2026-09-17、precision=DATE_ONLY；available_at=retrieved_at=`2026-10-05T10:08:22.746222+00:00`，未补造午夜或历史 available。Terms 实际取回=`2026-10-05T10:08:22.572813+00:00`。Source/terms 任何一个晚于 use_at 都阻断；比较保留纳秒整数精度。不能将此次 10 月捕获用于 9 月历史 cutoff。

官网声明允许非商业浏览/下载，当前实现按已冻结窄用途仅允许本地参考，并不据此声称行情、模型研究、云端传播、再分发、交易或历史回测获准。[实际条款](https://www.sse.com.cn/home/legal/) 与 [公告](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml) 为原始来源。

Service constructor 是可信 parent capability boundary：复制 raw/terms bytes、metadata、approved Set、固定公钥和 bound signer；不向 facade 返回任何原件、内部路径、DB 或私钥。buildPolicy 不会自批准；只有总控审核后以 exact policy hash 重新构建 service，registerPolicy 才成功。每次 admit/buildPacket/verifyPacket 都重导来源事实、terms hash、coverage、snapshot/receipt/ref/signature/epoch，实时检查撤销。原 SnapshotManifest1.0 保留 original hash/validator，以 OBSERVED scope 重用。其旧 provenance DATE_ONLY 字段存已知日期字符串，SourceObservation/BrainPacket intraday 字段仍为 null。Packet 可包含的每个字段由来源重投影后逐项比较，合法自签/自 hash 也不能改变事实。

`POINT_IN_TIME_ONLY` 将 use_at 与 frozen cutoff 精确绑定；它是本次观察的有限 reference proof，不是持续实时许可、历史可见性重建或 source 自动续权。Service 当前为单进程内存记录，所有方法同步，无真实 DB/多进程/remote trust service，也无 Research consumer/producer。

## 实际 source inventory

`source-inventory.json` 来自 `p1b/scripts/inventory.mjs` 的 metadata-only 执行：16 个条目清点 A–G、原五条 public captures、新 source，未把未知许可/clock/purpose 补成通过。唯一 allowlisted研究 SQLite 为 `History/炒股/程序/data/stocks.db`；URI=`mode=ro&immutable=1`、PRAGMA query_only，旧源码不导入。只读 main-file snapshot 下 stock_info 15,549 行，hk_daily 3,904,281 行，日期 2016-08-19～2026-08-19；这不是 A 股 PIT universe 或当前 live DB 认证。主文件/WAL/SHM SHA256 before/after 一致；immutable 明确忽略未 checkpoint WAL 行。

Kline 目录 metadata-only 清点 库存时间 2026-10-05T10:22:08.462Z 下 8,975 个 Parquet filename（sh 2,862；sz 3,324；bj 292；hk 2,020；us 477），没有读取这些 row payload 或认证其 dates。Legacy fetcher 的 qfq→raw fallback 与覆写缓存不能满足 raw/adjusted version lineage。旧 calendar 文件含 8,797 日期与 local updated_at，但没有 original raw/license/历史可见性；legacy manifest 中 SSE/CNINFO/issuer/NBS/MOF/腾讯 URL 与 expected hashes 仅为待核验线索。没有发现已独立验证的 company-action revision feed 或历史行业 membership。Codex model/state/memory/goals/queue/logs DB、credentials、账户状态、个人工作簿均明确排除；未运行 V5 或旧 collector，未搬迁历史数据。

## 股票/价格/财务 scope 仍 BLOCKED

本地已有真实缓存不等于获准的历史研究数据。原五条 P1A captures 继续原始 UNKNOWN/UNVERIFIED，不因此次官网 terms 而自动升格；新 source 不继承它们的 identity/data class。C12–C22 的真实 security master/status、全 calendar/board rules、bars clocks/license、corporate-action调整、financial revisions、industry membership、指标样本、Research producers 尚未闭环。本轮有限日历正向不能满足真实股票+真实历史价格+财报/公告+正确 PIT 的研究 pilot 前提。

可继续核查的正式来源路线：SSE 的 [行情服务入口](https://www.sse.com.cn/transparency/services/index.shtml) 明确提供产品、授权许可与业务文档；其 [交易规则第五章](https://www.sse.com.cn/lawandrules/sselawsrules2025/fund/trading/c/c_20260424_10817739.shtml) 对交易信息使用及传播另有许可范围。CNINFO 的 [正式数据服务](https://webapi.cninfo.com.cn/) 是候选接口路线，未取得相应条款/用户权限/原字节 clocks，本轮未准入。这些是下一次 source 审核入口，不是已获授权，不联系外部、不购订阅、不接 credentials。Web 查询结果不作为 admitted fact 或 policy 自动升级来源。

## 验证

`node --test p1b/tests/real-data.test.mjs`：22/22 PASS、0 SKIP。测试使用明确标签 REAL_PUBLIC_CAPTURE_TEST_REFERENCE，unit `P1B_RD_TEST_CODE_EPOCH` 仅测 guard，不充当最终总控 code pin。攻击实际到达 raw hash/terms/clock/projection/approval/receipt boundary，无 code-proof early reject 伪通过。包括微秒 future、未来 terms、URL/body DATE_ONLY 午夜 spoof、原字节变更、未知 terms、自报 source、coverage/year/股票扩权、approved Set mutation、伪 snapshot/ref/signature/receipt、namespace/purpose/code epoch、source fact mutation、revocation、任意 payload/path、所有 cloud/API/model/broker/trading transfer。同步拒绝记录只含固定 action/reason/parent epoch、空 caller refs 与可核验 audit hash chain，不写不可信 raw/message/payload。

最终全量 Golden、actual checked code epoch 的真实 receipt/packet 报告、Independent Reviewer 和 Gate 由 parent 验收；本 notes 不替代最终 Gate。真实30账户参数保持 UNSET_REQUIRED；production/broker/orders/stock recommendation 继续 BLOCKED；停止边界仍是等待 APPROVE_P1B_RESEARCH_PILOT。
