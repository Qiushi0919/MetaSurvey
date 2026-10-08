"""Deterministic local Chinese reports and fact-led cohort comparison."""
from .core import assert_registered
LABELS={'Business Quality':'业务与盈利能力','Earnings/Cash Quality':'利润与现金质量','Valuation':'估值','Sector':'行业','Catalyst':'公告与催化','Timing':'价格状态','Risk':'风险','Evidence Quality':'证据质量','Unknowns':'未知项'}
def esc(v):return str(v).replace('|','\\|').replace('\n',' ').replace('<','&lt;').replace('>','&gt;')
def feature_table(fs):
 lines=['| 研究事实 | 状态 | 值 | 期间/日期 | 单位与口径 |','|---|---|---|---|---|']
 for f in fs:lines.append('| '+ ' | '.join(esc(v) for v in [f['name'],f['state'],f['value'] if f['value'] is not None else 'UNKNOWN',f['period'] or '见原价格截止/来源索引',f['unit']+' / '+f['formula']])+' |')
 return lines

def factual_reading(fs):
 from decimal import Decimal
 lines=[]
 for key,label in [('source_netprofit_yoy','来源声称净利润同比'),('source_revenue_yoy','来源声称收入同比'),('source_operating_cashflow','来源声称经营净现金流')]:
  f=fs.get(key)
  if f and f['value'] is not None:
   x=Decimal(f['value']);lines.append(label+('为正' if x>0 else '为负' if x<0 else '为零')+'；期间'+str(f['period'])+'。')
 f=fs.get('cash_conversion_ratio')
 if f and f['value'] is not None:
  x=Decimal(f['value']);lines.append('同口径CFO'+('高于' if x>1 else '低于' if x<1 else '等于')+'本期合并净利润；仅描述期间现金转化，不判断可持续性。')
 return lines

def render_report(v):
 assert_registered(v);b=v['body'];fs={f['name']:f for f in b['features']};name=fs['current_observed_name']['value'] or v['symbol']
 lines=[f'# {name}（{v["symbol"]}）— 本地真实研究报告 2.0','', '**LOCAL_ONLY / NON_TRADEABLE / UNVERIFIED_GATEWAY**。正式准入、历史PIT、模型/云端与交易仍BLOCKED。','',f'本轮观察截止：{v["decision_cutoff"]}；最新接收：{v["retrieval_cutoff"]}。证券行情日不等于今天；日期、财报期间与首次观察时间分别保留。','',f'版本链：Wave C Report {b["wave_c_report_ref"]["content_hash"]} → Wave D Input {b["input_ref"]["content_hash"]} → Assessment {b["assessment_ref"]["content_hash"]} → Report {v["content_hash"]}。','', '所有金额为来源声明的尺度；财务表金额单位尚未独立认证。市值/股本字段明确标注来源声明万元/万股，未转换成账户金额。YTD不能冒充TTM。','']
 for d in b['dimensions']:
  lines.extend(['## '+LABELS[d['name']],'',d['description'],''])
  if d['name']=='Business Quality':
   lines+=factual_reading(fs)+['']
   lines+=feature_table([f for f in b['features'] if f['name'] in ('source_roe','source_revenue','source_netprofit_yoy','source_revenue_yoy','derived_revenue_yoy','derived_consolidated_profit_yoy')])+['','盈利/增长的正负事实可观察；当前三股并不能代表全市场，数值高低不构成商业质量评级。','']
  elif d['name']=='Earnings/Cash Quality':
   lines+=feature_table([f for f in b['features'] if f['name'] in ('source_consolidated_net_profit','source_parent_net_profit','source_cashflow_net_profit','source_operating_cashflow','cash_conversion_ratio','cash_after_capex_proxy','source_gross_margin','source_accounts_receivable','source_inventories','receivables_to_revenue_ratio','inventory_to_revenue_ratio')])+['','现金转化比是同口径CFO/合并净利润；分母非正不作好坏排序。存量应收/存货相对YTD收入只作诊断，不是周转天数，现金减资本开支不是完整自由现金流。','']
  elif d['name']=='Valuation':lines+=feature_table([f for f in b['features'] if f['name'].startswith('source_p') or f['name'] in ('source_total_mv','source_circ_mv','source_total_share','source_turnover_rate','source_daily_basic_close','valuation_ev_ebitda')])+['','不因较低PE/PB声称便宜，也不将来源PE TTM当成独立重建TTM。缺EV/EBITDA保持UNKNOWN。','']
  elif d['name']=='Sector':lines+=feature_table([fs['current_observed_industry'],fs['historical_industry_membership']])+['','当前分类来自新捕获stock_basic；行业景气、竞争格局与历史成员没有证据。','']
  elif d['name']=='Catalyst':
   lines+=feature_table([fs['official_announcement_reference_count'],fs['body_verified_catalyst_documents']])+['']
   for a in b['announcements']:
    lines.append(f'- {a["date"]} [{esc(a["title"])}]({a["uri"]})：{a["body_status"]}；索引原件 {a["source_ref"]["raw_sha256"]}。')
    if a['snippet']:lines.append('  正文有限摘录：'+esc(a['snippet'])+'。')
   lines+=['','标题只证明索引条目存在；未验证的PDF不得推定经营事实或利好/利空。官方地址跳转到同路径static.sse.com.cn已另存证，但本次返回正文未通过PDF格式检查，保留失败原件。','']
  elif d['name']=='Timing':
   lines+=feature_table([f for f in b['features'] if f['name'].startswith('raw_') or f['name'] in ('last_raw_close','last_reported_bar_date','distance_ma20_pct','distance_ma60_pct','reported_amount_mean20')])+['',f'原Wave C Quality={b["wave_c_quality"]["value"] or "UNKNOWN"}；Timing={b["wave_c_timing"]["value"] or "UNKNOWN"}。坐标截止 {b["coordinates_cutoff"]}，本轮保留为前轮观察，未将新财务补回旧截止。未经校准，不能解释为胜率或入场资格。','']
   lines+=feature_table([fs['adjusted_series_consistency_sessions'],fs['independently_verified_action_reconciliation']])+['','复权序列另存于报告机器对象adjustment.series，以最新观察因子作锚；只是同一网关原价与因子的数学一致性。raw未覆盖，不是总回报或独立权益验证。原5处歧义、8个非零pre_close参照差额继续存在。','']
  elif d['name']=='Risk':
   lines+=feature_table([f for f in b['features'] if f['name'] in ('st_status','suspension_status','source_total_assets','source_total_liabilities','debt_ratio_pct','source_debt_to_assets','source_money_capital')])+['','状态查询限定2026-09-30，不能证明10月6日可交易。完整集合的终止页schema未通过，故不能从不在列表推断NON_ST/NOT_SUSPENDED。','']
   lines.extend('- '+esc(x) for x in b['conflicts']);lines.append('')
  elif d['name']=='Evidence Quality':
   lines+=['| 类别 | Wave C | Wave D可用观察 | 差值 | 正式准入 |','|---|---:|---:|---:|---|']
   lines += [f'| {c["category"]} | {c["previous_count"]} | {c["eligible_observation_count"]} | {c["delta"]} | BLOCKED |' for c in b['coverage']]
   lines+=['','物理观察数量不等于独立事件数、覆盖完整性或可信概率；数据与公开产品定义兼容不证明渠道许可或源真实性。','']
  elif d['name']=='Unknowns':
   lines+=['- '+esc(n) for n in b['unknowns']]+['','真实账户/费用/风险30项UNSET_REQUIRED；评级映射、概率、胜率、Edge、成本、仓位均未计算。Snapshot B保持PENDING，需10月8日恢复交易后的真实盘后观察并单独授权。','']
 lines+=['## 原始证据索引与计算依据','', '每个特征的完整raw/request/ordinal/clock链保存在同名report.json。以下列出每个特征的来源hash，正文不包含凭证或账户状态。','']
 for f in b['features']:
  rs=sorted(set(r['raw_sha256'] for r in f['source_refs']));lines.append('- '+f['name']+'：'+(', '.join(rs) if rs else 'UNKNOWN，无来源推定')+'；'+','.join(f['reason_codes']))
 lines+=['','本报告不产生ResearchCard、Candidate、Signal、Approval、OrderIntent或BUY/SELL。STOP，等待Owner。','']
 return '\n'.join(lines)

def render_comparison(v):
 assert_registered(v);b=v['body'];rows=b['reports'];names={f['name'] for r in rows for f in r['features']};facts={r['symbol']:{f['name']:f for f in r['features']} for r in rows}
 lines=['# 三股横向真实研究比较 — 本地沙盒','', '**LOCAL_ONLY / NON_TRADEABLE / UNVERIFIED_GATEWAY**。逐项事实比较，未建立综合总分或BUY/SELL排名。','',f'观察截止：{v["decision_cutoff"]}。新估值与财务是本轮current-observed；原Quality/Timing保留旧截止，不回填。','', '| 研究事实（各自期间、单位、冲突必须同时阅读） | 603993.SH | 600312.SH | 603228.SH |','|---|---|---|---|']
 selected=['current_observed_name','current_observed_industry','source_roe','source_revenue_yoy','source_netprofit_yoy','source_operating_cashflow','source_consolidated_net_profit','cash_conversion_ratio','source_gross_margin','source_total_assets','source_total_liabilities','debt_ratio_pct','source_accounts_receivable','source_pe_ttm','source_pb','source_ps_ttm','source_total_mv','source_total_share','last_reported_bar_date','raw_price_change_20_sessions_pct','raw_max_drawdown_60_sessions_pct','st_status','suspension_status','body_verified_catalyst_documents']
 for name in selected:
  cells=[]
  for r in rows:
   f=facts[r['symbol']][name];cells.append(esc((f['value'] or 'UNKNOWN')+' / '+f['state']+' / '+(f['period'] or '原价格截止')+' / '+f['unit']))
  lines.append('| '+esc(name)+' | '+' | '.join(cells)+' |')
 for r in rows:
  lines+=['','### 本期可直接支持的观察（'+r['symbol']+'）','']+factual_reading(facts[r['symbol']])+['']
  lines+=['','## '+r['symbol'],'',f'原Wave C实验相对坐标：Quality {r["wave_c_quality"]["value"] or "UNKNOWN"} / Timing {r["wave_c_timing"]["value"] or "UNKNOWN"}，仅三股队列，非概率、等级或交易排序。','', '较强/较弱仅能在相同口径、期间和证据状态下逐项比较。现金转化、资产负债与估值事实见上表；业务竞争力、行业景气及未验证公告正文不足以形成综合优劣结论。','', 'UNKNOWN：'+', '.join(r['unknowns'])+'。','', '冲突：'+('; '.join(r['conflicts']) if r['conflicts'] else '无新增已记录冲突；不代表不存在其他修订')+'。','', '| 类别 | 可用观察 | 原观察 | 正式准入 |','|---|---:|---:|---|']
  lines += [f'| {c["category"]} | {c["eligible_observation_count"]} | {c["previous_count"]} | BLOCKED |' for c in r['coverage']]
  lines+=['', '版本链报告hash：'+r['report_ref']['content_hash']+'。']
 lines+=['','研究下一步建议：**APPROVE_WITH_CONDITIONS** 继续同三股本地证据补全；**HOLD** 正式准入/Pilot、历史PIT/回测、云端与交易。不得由此扩大股票池或自动抓取Snapshot B。','']
 return '\n'.join(lines)
