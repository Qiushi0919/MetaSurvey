# Provider / License 事实缺口

本轮仅读取官方公开文档，不访问账户或 gateway。未作合法/非法判断，未认证当前 gateway；技术成功不构成许可、授权、历史PIT或生产准入。

## 捕获的官方事实

官方服务协议要求经官方或授权方式取得服务，限制第三方销售与转让，并对个人服务规定不可转让及非商业用途；公开文字不能证明当前销售渠道获授权，也不能替代该渠道的合同与具体用途许可。[Tushare 服务协议](https://tushare.pro/document/1?doc_id=405)，[用户协议](https://tushare.pro/document/1?doc_id=409)。

公开权限表分别描述积分档位和独立权限；15,000档位在公开表中的调用能力不能直接映射为这个月卡账户的实际 entitlement。月卡产品、实际账户关联、有效期、存储与转移授权仍待外部证据。[积分与权限](https://tushare.pro/document/2?doc_id=290)。

日线文档描述未复权日线及盘后更新区间；每日指标文档另列更新区间。它们是产品更新说明，不能替代某个交易日的实际响应可得时刻，不设一个猜测时点直接放行 EOD。[日线](https://tushare.pro/document/2?doc_id=27)，[每日指标](https://tushare.pro/document/2?doc_id=32)。

财报文档提供公告日期、实际公告日期、报表类型和更新标记等版本字段，但日期和当前多版本行不证明过去决策时的 first visibility / revision chronology。[利润表](https://tushare.pro/document/2?doc_id=33)，[资产负债表](https://tushare.pro/document/2?doc_id=36)，[现金流量表](https://tushare.pro/document/2?doc_id=44)，[财务指标](https://tushare.pro/document/2?doc_id=79)。

上交所休市公告列明10月1日至7日休市、10月8日恢复。恢复日仍需核验实际开市与盘后数据可得；本轮不运行 Snapshot B。[上交所公告](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml)。

## 当前项目证据与外部待答问题

| 项目 | 当前事实 | 需要的外部证据 |
|---|---|---|
| 月卡积分 | Owner声明15,000 | 实际账户/订单/entitlement，不能仅凭积分字样 |
| Seller / product / sales authorization | 均UNVERIFIED | 销售主体、产品名称、授权渠道与账户对应证明 |
| 有效期 | Owner声明，准确起止独立证明UNVERIFIED | 含时区与到期时刻的订单或授权记录 |
| Provider身份 | false | endpoint与授权提供方身份的可核验绑定 |
| License | false | 本地研究、历史回测、生产用途、保留/存储/转移/云端/再分发的明确授权或限制 |
| Transport完整性 | false | 当前原始gateway HTTP数据的可核验完整性及经确认安全端点；本轮不探测认证端点 |
| Historical PIT | false | 历史首次可见和版本修订时间链；今天查询历史记录不足 |

不会购买、绕过权限或向Owner索取Token。Token轮换不是本轮启动前提。Provider/License缺口保持阻断；C12–C22未因公开文档或引擎成功而关闭。

## 捕获与版本

10个公开页面+同6份SSE公告的origin/static共22次无凭证GET。六份PDF地址响应虽返回200，解码后仍为HTML，body_verified=0；不将标题变成经营事实。原始wire、decoded、文本文档、URL身份、hash、时间及redirect链保存在Git外0600档案；provider-document-matrix.json和public-ref.json只提供引用。官方公开资料仅是文档事实，不能证明账户授权。
