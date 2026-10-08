# 真实股票数据准入准备：Contract Fit Analysis

Status: PROPOSAL_FOR_OWNER_REVIEW，未改变真实source状态/用途或已冻结合同。当前baseline是1fffea9/P1-B DATA/SEMANTICS Gate，不是Closure停点；因此不重复P1-B0或将HEAD回退。

| 既有对象 | 适配与缺口 |
|---|---|
| P0 SecurityIdentity1.0 | 保留symbol/exchange/board/status/ST/区间/原件/hash；flat今日列表不能证明historical status；tick/lot/session规则未知不补 |
| P0 DataEnvelope/SnapshotManifest1.0 | 保留四时钟与OBSERVED/RECONSTRUCTED隔离；新clock必须区分business event与observation capture，未批准历史重构不得造available |
| P1-A SourceObservation1.0 | 有event/published/available/retrieved，但runtime source admission不是通用真实许可服务，不靠换label借权 |
| P1-B SourceObservation1.1 | 只支持有限calendar reference，clock无独立event_time；不能用于price/action/financial/sector扩展 |
| P1-B Policy1.1/Receipt1.1/Packet1.2 | 只calendar、零股票、local-only、内存DEV authority、单次use_at；不可变成证券historical/LLM权限 |
| ResearchCard1.0 / Assessment1.0 | 不改；当前真实Card未实现，assessment仅synthetic，card_ref=null。数据准备不建立真实producer |
| 001–006 / releases / 140+34 source pin | 原字节全部保留；本轮proposal不注册DB，不增加007或生产依赖 |

本轮新建 ClockEvidenceProposal1.0 和 StockSliceProposal1.0，目录contracts/admission-preparation，全部明确admission=BLOCKED/production=false/pilot=false。这些是源准入方案的机器可验证附件，不是SourceObservation新runtime版本，不写Snapshot/Receipt/BrainPacket。字段满足只意味着proposal可供审查，不意味着事实/许可/PIT已核验。

未来实际source版本应新增独立observation_event_time、明确业务event/effective date、publication精度、available proof basis、retrieved；financial period_end != publication，action record/ex/effective dates != availability，industry in/out/effective interval != file mtime。DATE_ONLY保存date与null instant，不补00:00或23:59。旧calendar adapter的capture event语义保持原状，不回写。

观察路线与历史路线必须分别批准：当前时点研究拟允许读取过去bars/财报数值；若采用实际取回作为本地可消费时点，须先审定这个新clock policy，且不能据此声称首次公开时点或给过去cutoff使用。历史decision研究须额外证明对应原版本在当时可见。两者都先验证source用途许可/原件/coverage/DQ，MANUAL_EXPORT到模型须单独许可。该路线仅为建议，不是已获批业务规则。
