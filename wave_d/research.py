"""Nine separated research axes; no score-to-trade or business defaults."""
from copy import deepcopy
from .core import SYMBOLS,assert_registered,ref
from .financial import financial_features
from .status_action import status_features,adjustment_features,feature
DIMENSIONS=('Business Quality','Earnings/Cash Quality','Valuation','Sector','Catalyst','Timing','Risk','Evidence Quality','Unknowns')
def assessment_bodies(inputs,ctx,up):
 out=[]
 for i,v in enumerate(inputs):
  assert_registered(v);obs=v['body']['observations'];symbol=v['symbol'];fin,conflicts,warnings=financial_features(obs,symbol)
  status,status_evidence=status_features(obs,up['capture']['requests'],symbol);adjust,adjustment=adjustment_features(obs)
  old=up['old_assessments'][i]['body'];retained=[]
  for f in old['features']:
   if f['name'].startswith('raw_') or f['name'] in ('last_raw_close','last_reported_bar_date','distance_ma20_pct','distance_ma60_pct','reported_amount_mean20','observed_bar_sessions'):
    x=deepcopy(f);x['period']=None
    for r in x['source_refs']:r['event_time']=None
    retained.append(x)
  ann=v['body']['announcements'];known=[r for r in obs if r['api_name']=='sse_announcement']
  catalyst=feature('official_announcement_reference_count',str(len(ann)) if ann else None,'INDEX_METADATA_NOT_BUSINESS_BODY_FACT','COUNT_APPROVED_SSE_INDEX_REFERENCES',known,['BODY_NOT_PROVEN_NO_BUSINESS_EFFECT_INFERRED'])
  body_catalyst=feature('body_verified_catalyst_documents',str(sum(a['body_status']=='BODY_VERIFIED' for a in ann)) if any(a['body_status']=='BODY_VERIFIED' for a in ann) else None,'VERIFIED_PDF_IDENTITY_NOT_PREDICTIVE_EFFECT','COUNT_VERIFIED_OFFICIAL_DOCUMENTS',known,['INDEX_TITLE_CANNOT_SUBSTITUTE_DOCUMENT_BODY'])
  fs=status+retained+fin+adjust+[catalyst,body_catalyst,feature('valuation_ev_ebitda',None,'UNKNOWN','NO_VERIFIED_ENTERPRISE_VALUE_AND_EBITDA'),feature('historical_as_of_visibility',None,'UNKNOWN','CURRENT_RETRIEVAL_CANNOT_PROVE_HISTORICAL_VISIBILITY')]
  names=[f['name'] for f in fs];assert len(names)==len(set(names))
  category_apis={'security':('stock_basic','stock_st','suspend_d'),'calendar':('trade_cal',),'bars':('daily',),'actions':('dividend',),'factors':('adj_factor',),'financial':('income','balancesheet','cashflow','fina_indicator'),'industry':('stock_basic',),'announcements':('sse_announcement',)}
  coverage=[]
  for category,apis in category_apis.items():
   rows=[r for r in obs if r['api_name'] in apis and (category!='industry' or bool(r['values'].get('industry')))]
   previous=next(x for x in old['coverage'] if x['category']==category)
   coverage.append({'category':category,'eligible_observation_count':len(rows),'previous_count':previous['eligible_observation_count'],'delta':len(rows)-previous['eligible_observation_count'],'state':'OBSERVED_PARTIAL' if rows else 'UNKNOWN','formal_admission':'BLOCKED'})
  old_unknown={f['name'] for f in old['features'] if f['value'] is None};current_unknown=[f['name'] for f in fs if f['value'] is None];replacement={'earnings_quality':'cash_conversion_ratio','cash_generation':'source_operating_cashflow','valuation_ttm_pe':'source_pe_ttm','current_observed_industry':'current_observed_industry','company_announcement_catalyst':'body_verified_catalyst_documents','st_status':'st_status','suspension_status':'suspension_status','historical_industry_membership':'historical_industry_membership','valuation_ev_ebitda':'valuation_ev_ebitda','verified_action_reconciliation':'independently_verified_action_reconciliation'}
  lookup={f['name']:f for f in fs};delta=[{'wave_c_feature':name,'wave_d_feature':replacement.get(name,name),'state':lookup[replacement.get(name,name)]['state'] if replacement.get(name,name) in lookup else 'UNKNOWN'} for name in sorted(old_unknown)]
  summary={
   'Business Quality':'业务模式与竞争力缺少可验证经营原文；ROE、增长与资产负债指标仅形成财务观察，不能代替商业判断。',
   'Earnings/Cash Quality':'经营现金流与合并净利润按同一报告期、口径比较；冲突/非正利润/缺失使现金转化保持UNKNOWN。YTD不是TTM。',
   'Valuation':'展示供应方声明的PE TTM/PB/PS TTM/市值与股本，不从季度EPS计算TTM，也不把较低倍数解释为买入。',
   'Sector':'当前stock_basic分类是本次观察的来源声明；历史成员和行业景气仍UNKNOWN。',
   'Catalyst':'SSE官方索引可追溯；正文未被验证的公告只显示标题/日期，不能推定订单、利润影响或催化强弱。',
   'Timing':'保留Wave C原raw价格结构坐标及其截止时间；复权诊断另列，不替换原数据或重算旧评分。',
   'Risk':'展示回撤、波动、负债、现金转化、版本冲突及状态完整性；未知状态不等于可交易。',
   'Evidence Quality':'八类观察覆盖、字段完整性、原件版本、冲突与来源限制分别列出；覆盖不是可信概率。',
   'Unknowns':'缺失估值/财务/行业/PDF正文/状态完整性/历史可见性均显式列出，真实成本和账户参数UNSET_REQUIRED。'}
  dimensions=[{'name':n,'state':'UNKNOWN' if n=='Business Quality' else 'OBSERVED_PARTIAL','description':summary[n]} for n in DIMENSIONS]
  out.append({'input_ref':ref(v),'wave_c_report_ref':v['body']['wave_c_report_ref'],'features':fs,'dimensions':dimensions,'wave_c_quality':deepcopy(old['quality_score']),'wave_c_timing':deepcopy(old['timing_score']),'coordinates_cutoff':up['old_assessments'][i]['decision_cutoff'],'coordinates_policy':'PRESERVED_WAVE_C_ORIGINAL_EXPERIMENTAL_NOT_UPDATED_WITH_NEW_FINANCIALS','coverage':coverage,'unknowns':current_unknown,'unknown_delta':delta,'conflicts':sorted(set(old['conflicting_evidence']+conflicts)),'warnings':old['warnings']+warnings+['新数据首次可见时刻为实际retrieval；不能回填旧cutoff。','前三股相对坐标未校准，不能称为概率/胜率/Edge/等级或交易资格。'],'status_evidence':status_evidence,'announcements':ann,'adjustment':adjustment,'grade':'UNSET_REQUIRED','probability':'UNSET_REQUIRED','win_rate':'UNSET_REQUIRED','net_edge':'UNSET_REQUIRED','cost':'UNSET_REQUIRED','account_suitability':'UNSET_REQUIRED','tradeability':'BLOCKED','snapshot_B':'PENDING_SEPARATE_POST_HOLIDAY_FRESH_OBSERVATION'})
 return out
