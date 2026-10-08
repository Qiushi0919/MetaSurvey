"""Deterministic Chinese reports; no LLM calls or data export."""
from .core import assert_registered, ref, digest, produce_reports, parent_for

TITLES={'company_quality':'公司与财务质量','sector_quality':'行业证据','catalyst':'催化与公司行动','evidence_quality':'证据质量与覆盖','valuation':'估值','timing':'价格位置与 Timing','risk':'风险与反证','cost':'费用','account_suitability':'账户适配','tradeability':'为何当前不可交易'}

def _report_body(assessment):
    reports=[]
    for a in [assessment]:
        assert_registered(a);b=a['body'];fs={f['name']:f for f in b['features']}
        def v(k):return fs[k]['value'] if fs[k]['value'] is not None else 'UNKNOWN'
        q=b['quality_score']['value'] or 'UNKNOWN';t=b['timing_score']['value'] or 'UNKNOWN'
        qparts={x['feature_name']:x['value'] or 'UNKNOWN' for x in b['quality_score']['component_scores']['components']}
        growth=v('netprofit_yoy')
        from .math import num
        growth_note='未知' if growth=='UNKNOWN' else '正增长' if num(growth)>0 else '负增长' if num(growth)<0 else '同比持平'
        timing_note='UNKNOWN' if v('distance_ma20_pct')=='UNKNOWN' else '在原始20日均线上方' if num(v('distance_ma20_pct'))>0 else '在原始20日均线下方' if num(v('distance_ma20_pct'))<0 else '等于原始20日均线'
        texts={
          'company_quality':[f"当前观察名称：{v('current_observed_name')}。最新可用报告期间为 {v('latest_observed_report_period')}；源声明公告日期 {v('source_ann_date')}，不是已核验的公开时刻。",f"网关观察的 ROE={v('roe')}、净利润同比={v('netprofit_yoy')}（按源数值符号为{growth_note}）、资产负债率={v('debt_to_assets')}、EPS={v('eps')}。这些数值的单位/比例标度尚未独立核验。",f"Quality 实验坐标 {q}/100：盈利能力相对坐标 {qparts['roe']}，增长相对坐标 {qparts['netprofit_yoy']}，较低负债率相对坐标 {qparts['debt_to_assets']}。仅比较这三股的当前观察，不是完整公司质量。现金创造、利润现金含量、业务竞争力和报表细项 UNKNOWN；不能以季度EPS冒充TTM盈利。"],
          'sector_quality':[f"工程可用的当前行业声明：{v('current_observed_industry')}。被日期DQ阻断的行业行不作为分类依据；current membership不回填历史标签。","行业景气、产业链订单、商品价格和竞争格局缺证据，Sector Quality=UNKNOWN；当前名称或行业代码不能推出公司业务逻辑。"],
          'catalyst':[f"可用公司行动物理观察 {v('corporate_action_observations')} 条，因子观察 {v('factor_observations')} 条；数量包含重复捕获，不能称为独立事件数量。","公司公告/订单/新闻催化 UNKNOWN。既有SSE官方日历与代码参考证据保持独立，不能替代公司经营公告。原action多原件歧义及非零参照差额保留；未来ex/pay日期仅为源声明安排，不是已发生现金或收益。"],
          'evidence_quality':[f"八类中有工程可用观察的类别为 {b['evidence_quality']['usable_categories']}/8，覆盖坐标 {b['evidence_quality']['value']}/100。缺失类别：{', '.join(b['missing_categories']) or '无类别计数缺失，但仍有重要字段缺失'}。","该坐标不度量真伪、权限或可信概率。来源仍为OWNER_PROVIDED_MONTHLY_GATEWAY；formal admission=BLOCKED。任何source conflict与排除记录都保留在输入及评估对象中。"],
          'valuation':["当前PE、TTM盈利、EV/EBITDA、股本/企业价值、历史估值分位均UNKNOWN。已有EPS不足以构造可比TTM估值，不能写出便宜或昂贵的结论。"],
          'timing':[f"最后报告的行情日期 {v('last_reported_bar_date')}，raw close={v('last_raw_close')}；MA20={v('raw_ma20')}，MA60={v('raw_ma60')}。按该原始序列当前{timing_note}。这是冻结捕获中的历史原始收盘观察，不是今天实时价格。",f"20/60观察日原始价格变化 {v('raw_price_change_20_sessions_pct')}% / {v('raw_price_change_60_sessions_pct')}%；离MA20/MA60 {v('distance_ma20_pct')}% / {v('distance_ma60_pct')}%；60观察日最大原始回撤 {v('raw_max_drawdown_60_sessions_pct')}%；20个日变化的样本波动 {v('raw_daily_volatility_20_sessions_pct')}%（不年化）。",f"Timing 实验坐标 {t}/100，独立来自价格变化、均线距离、回撤和波动。reported amount 20观察日均值={v('reported_amount_mean20')}，源标度未核验，不转换成账户人民币成交能力。所有序列保持raw；除权可能影响指标，因此不判定入场或触发。"],
          'risk':["风险包括原始价格波动/回撤、负债指标、缺失完整财报、未验证行业与公司公告、状态完整性以及source/license/transport缺口。高Quality不能抵消这些风险。","非ST、未停牌、涨跌停可成交状态均UNKNOWN；空响应不是安全证明。revision chronology UNKNOWN，不按update_flag或今日抓取时间推定历史可见版本。"],
          'cost':["真实券商、佣金、最低佣金、税费、滑点与费用后Edge均UNSET_REQUIRED；不套用旧实验参数，不产生费用后预期收益。"],
          'account_suitability':["真实本金、风险预算、持仓、可用现金与单票金额均UNSET_REQUIRED。实验坐标与历史价格不构成账户适配、购买力或sizing结论。"],
          'tradeability':["NON_TRADEABLE / LOCAL_ONLY / NO_ORDER / NO_BROKER / NO_PRODUCTION。Quality与Timing均未校准；S/A/B/C/X阈值映射保持UNSET_REQUIRED，不给出胜率、概率或买卖建议。","正式ResearchCard、Candidate、Signal、Approval、OrderIntent、Order、Fill与云端模型消费者不得接受本报告。LLM结论不等于HUMAN_USER approval；本轮没有模型或券商调用。"]}
        sections=[{'dimension':d['name'],'title':TITLES[d['name']],'paragraphs':texts[d['name']],'feature_names':d['feature_names']} for d in b['dimensions']]
        reports.append({'assessment_ref':ref(a),'features_hash':digest(b['features']),'report_kind':'LOCAL_DETERMINISTIC_TEMPLATE_NOT_LLM','sections':sections,
          'unknowns':[f['name'] for f in b['features'] if f['value'] is None],'warnings':b['warnings']})
    return reports[0]

def make_reports(assessments):return produce_reports(assessments)

def render(report):
    assert_registered(report)
    assessment=parent_for(report);features=assessment['body']['features']
    def esc(s):return str(s).replace('|','\\|').replace('\n',' ')
    lines=[f"# {report['symbol']} — 本地真实研究沙盒报告",'',
      'RealResearchSandboxReport 1.0.0 · LOCAL_ONLY · NON_TRADEABLE','',
      f"研究cutoff：{report['decision_cutoff']}；捕获截止：{report['retrieval_cutoff']}。业务时区Asia/Shanghai。",'',
      '真实网关捕获经工程DQ后进入独立沙盒；provider/license/transport未核验，formal source admission仍BLOCKED。Historical visibility proven=false。此为当前观察研究，不是历史as-of研究、实时行情或正式ResearchCard。','']
    for section in report['body']['sections']:
        lines += ['## '+section['title'],'',*sum(([p,''] for p in section['paragraphs']),[])]
    lines += ['## 特征与直接证据','', '| 特征 | 数值/状态 | 单位 | 直接源行数 |','|---|---|---|---|']
    for f in features:lines.append(f"| {esc(f['name'])} | {esc(f['value'] if f['value'] is not None else f['state'])} | {esc(f['unit'])} | {len(f['source_refs'])} |")
    lines += ['','## 冲突、缺失与限制','']
    for s in assessment['body']['conflicting_evidence']+report['body']['warnings']:lines.append('- '+esc(s))
    lines += ['','UNKNOWN项：'+', '.join(report['body']['unknowns'])+'。','','## 版本与源证据索引','',
      f"report hash：{report['content_hash']}",f"assessment hash：{report['body']['assessment_ref']['content_hash']}",f"features hash：{report['body']['features_hash']}",f"source identity：{report['source_identity']}",f"rules hash：{report['rules_hash']}",f"code hash：{report['code_hash']}",'',
      '每个机器特征逐行绑定request fingerprint、raw hash、row ordinal和原始retrieved_at/available_at（published_at=null）。下面按请求合并展示索引；不合并原始版本。','',
      '| 请求 | raw hash | 引用行号 | 捕获可见时间 |','|---|---|---|---|']
    groups={}
    sources=[f['source_refs'] for f in features]+[c['source_refs'] for k in ('quality_score','timing_score') for c in assessment['body'][k]['component_scores']['components']]
    for source_refs in sources:
        for r in source_refs:
            k=(r['request_id'],r['raw_sha256'],r['available_at']);groups.setdefault(k,set()).add(r['row_ordinal'])
    for (request,h,at),ordinals in sorted(groups.items()):
        lines.append(f"| {esc(request)} | {h} | {','.join(str(x) for x in sorted(ordinals))} | {at} |")
    return '\n'.join(lines)+'\n'
