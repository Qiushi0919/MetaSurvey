"""Actual local research over registered eligible observations, with explicit gaps."""
from decimal import Decimal, localcontext
from .core import assert_registered, context_for, digest, require, SYMBOLS, produce_assessments
from .math import raw_statistics, pairwise_rank, mean_score, text, num

DIMENSIONS=('company_quality','sector_quality','catalyst','evidence_quality','valuation','timing','risk','cost','account_suitability','tradeability')
PRICE_NAMES=('last_raw_close','raw_ma20','raw_ma60','raw_price_change_20_sessions_pct','raw_price_change_60_sessions_pct','distance_ma20_pct','distance_ma60_pct','raw_max_drawdown_60_sessions_pct','raw_daily_volatility_20_sessions_pct','reported_amount_mean20')

def refs(rows):
    unique={digest(r['source_ref']):r['source_ref'] for r in rows}
    return [unique[k] for k in sorted(unique)]

def feature(name,value,unit,formula,rows=(),reason=(),conflict=False):
    return {'name':name,'state':'CONFLICT' if conflict else 'UNKNOWN' if value is None else 'DERIVED' if formula!='SOURCE_LITERAL' else 'OBSERVED',
      'value':value,'unit':unit,'formula':formula,'source_refs':refs(rows),'reason_codes':list(reason) or ([] if value is not None else ['WAVE_C_MISSING_EVIDENCE'])}

def unique_scalar(rows,key):
    xs={r['values'].get(key) for r in rows}
    return next(iter(xs)) if len(xs)==1 else None

def build_features(input):
    assert_registered(input);obs=input['body']['observations'];by={api:[r for r in obs if r['api_name']==api] for api in ('stock_basic','daily','fina_indicator','index_member_all','dividend','adj_factor','trade_cal')}
    out=[];conflicts=[]
    out.append(feature('current_observed_name',unique_scalar(by['stock_basic'],'name'),'SOURCE_NAME_NOT_HISTORICAL_IDENTITY','SOURCE_LITERAL',by['stock_basic']))
    for key in ('st_status','suspension_status'):out.append(feature(key,None,'UNKNOWN','EMPTY_RESPONSE_IS_NOT_NEGATIVE_PROOF'))
    dates={}
    for row in by['daily']:dates.setdefault(row['values']['trade_date'],[]).append(row)
    bars=[];bar_conflict=False
    for d,rows in sorted(dates.items()):
        if len({digest(r['values']) for r in rows})>1:bar_conflict=True;conflicts.append('RAW_BAR_CONFLICT:'+d)
        bars.append(rows[0])
    if bar_conflict or len(bars)<61:
        for key in PRICE_NAMES:out.append(feature(key,None,'UNKNOWN','RAW_SERIES_REQUIRED',by['daily'],conflict=bar_conflict))
    else:
        stats=raw_statistics([r['values']['close'] for r in bars],[r['values']['amount'] for r in bars])
        for key,val in stats.items():
            count=1 if key=='last_raw_close' else 20 if key in ('raw_ma20','distance_ma20_pct','reported_amount_mean20') else 21 if key in ('raw_price_change_20_sessions_pct','raw_daily_volatility_20_sessions_pct') else 61 if key=='raw_price_change_60_sessions_pct' else 60
            selected_dates={r['values']['trade_date'] for r in bars[-count:]}
            source_rows=[r for r in by['daily'] if r['values']['trade_date'] in selected_dates]
            unit='PROVIDER_CNY_PER_SHARE_UNVERIFIED' if key in ('last_raw_close','raw_ma20','raw_ma60') else 'PROVIDER_AMOUNT_SCALE_UNVERIFIED' if key=='reported_amount_mean20' else 'PERCENT_RAW_PRICE_STRUCTURE'
            out.append(feature(key,val,unit,'DECIMAL_RAW_'+key.upper()+'; NO_ADJUSTMENT; NO_FORECAST',source_rows,['WAVE_C_RAW_ACTION_DISTORTION','WAVE_C_UNIT_NOT_INDEPENDENTLY_VERIFIED']))
    out.append(feature('last_reported_bar_date',bars[-1]['values']['trade_date'] if bars else None,'SOURCE_DATE_ONLY','SOURCE_LITERAL',dates.get(bars[-1]['values']['trade_date'],[]) if bars else []))
    out.append(feature('observed_bar_sessions',str(len(bars)),'OBSERVED_ROW_DATES_NOT_EXCHANGE_AUTHORITY','COUNT_DISTINCT_REPORTED_DATES',by['daily']))
    groups={}
    for r in by['fina_indicator']:groups.setdefault(r['values']['end_date'],[]).append(r)
    for period,rows in sorted(groups.items()):
        metrics={digest({k:r['values'].get(k) for k in ('eps','roe','debt_to_assets','netprofit_yoy')}) for r in rows}
        if len(metrics)>1:conflicts.append('FINANCIAL_OBSERVED_METRIC_VERSIONS:'+period+'; CHRONOLOGY_UNKNOWN')
    latest=max(groups) if groups else None;rows=groups.get(latest,[])
    out.append(feature('latest_observed_report_period',latest,'REPORT_PERIOD_NOT_PUBLICATION','SOURCE_LITERAL',rows))
    out.append(feature('source_ann_date',unique_scalar(rows,'ann_date') if rows else None,'SOURCE_DATE_ONLY_NOT_PUBLICATION_INSTANT','SOURCE_LITERAL',rows))
    for key in ('eps','roe','debt_to_assets','netprofit_yoy'):
        raw=unique_scalar(rows,key) if rows else None
        val=text(num(raw)) if raw is not None else None
        conflict=bool(rows and len({r['values'].get(key) for r in rows})>1)
        out.append(feature(key,val,'PROVIDER_CURRENCY_PER_SHARE_UNVERIFIED' if key=='eps' else 'PROVIDER_RATIO_PERCENT_SCALE_UNVERIFIED','SOURCE_LITERAL',rows,['WAVE_C_REVISION_CHRONOLOGY_UNKNOWN','WAVE_C_UNIT_NOT_INDEPENDENTLY_VERIFIED'],conflict))
    for key in ('earnings_quality','cash_generation','valuation_ttm_pe','valuation_ev_ebitda'):
        out.append(feature(key,None,'UNKNOWN','MISSING_STATEMENTS_OR_TTM_VALUATION_INPUTS'))
    industry=[r for r in by['index_member_all'] if r['values'].get('is_new')=='Y']
    labels={'/'.join(filter(None,(r['values'].get('l1_name'),r['values'].get('l2_name'),r['values'].get('l3_name')))) for r in industry}
    out.append(feature('current_observed_industry',next(iter(labels)) if len(labels)==1 else None,'SOURCE_DECLARATION_NOT_HISTORICAL_MEMBERSHIP','SOURCE_LITERAL',industry,['WAVE_C_INDUSTRY_HISTORY_UNKNOWN']))
    out.append(feature('historical_industry_membership',None,'UNKNOWN','CURRENT_CLASSIFICATION_CANNOT_BACKFILL_HISTORY'))
    out.append(feature('corporate_action_observations',str(len(by['dividend'])),'PHYSICAL_OBSERVATIONS_NOT_UNIQUE_ACTIONS','COUNT_ELIGIBLE_OBSERVATIONS',by['dividend']))
    out.append(feature('factor_observations',str(len(by['adj_factor'])),'PHYSICAL_OBSERVATIONS_NOT_ADJUSTED_PRICES','COUNT_ELIGIBLE_OBSERVATIONS',by['adj_factor']))
    out.append(feature('company_announcement_catalyst',None,'UNKNOWN','NO_COMPANY_ANNOUNCEMENT_ENTITLEMENT_OR_CAPTURE'))
    out.append(feature('verified_action_reconciliation',None,'UNKNOWN','WAVE_B_ACTION_AMBIGUITIES_AND_NONZERO_REFERENCES_PRESERVED',by['dividend']+by['adj_factor']))
    coverage=[]
    category_apis={'security':'stock_basic','calendar':'trade_cal','bars':'daily','actions':'dividend','factors':'adj_factor','financial':'fina_indicator','industry':'index_member_all','announcements':None}
    for category,api in category_apis.items():
        count=len(by[api]) if api else 0
        coverage.append({'category':category,'eligible_observation_count':count,'state':'OBSERVED_PARTIAL' if count else 'UNKNOWN','formal_admission':'BLOCKED'})
    warnings=['来源、许可与HTTP传输完整性未经独立核验；所有结论仅为网关观察的本地实验计算。','Quality仅覆盖ROE、利润同比及负债率，现金流与盈利质量未知，不能称为完整公司质量评分。','Timing来自未复权原始价格，现金分红及公司行动可能扭曲趋势、回撤和波动；因子未应用。','财报期间不是公告时刻；所有版本首次可见时间与修订顺序未知，未作历史PIT或回测声明。','估值、订单/新闻催化、行业基本面及状态完整性不足；空响应不能证明非ST或未停牌。','八类覆盖分仅衡量工程可用观察，不代表许可证、可信度或预测成功率。','原Wave B的5处action多原件歧义与8个非零参照差額仍保留，没有构造权益现金流或复权价格。']
    if input['body']['excluded']:warnings.append('整响应DQ失败及窗口外行已排除，原件与排除清单仍保留；排除不能证明该类别不存在。')
    return out,coverage,conflicts,warnings

def score(name,components,all_features,rules):
    scores=[]
    periods=[next((f['value'] for f in fs if f['name']=='latest_observed_report_period'),None) for fs in all_features]
    mismatched_periods=name=='quality' and any(p is not None for p in periods) and (None in periods or len(set(periods))!=1)
    for feature_name,direction in components.items():
        values=[next(f['value'] for f in fs if f['name']==feature_name) for fs in all_features]
        ranks=[None]*len(values) if mismatched_periods else pairwise_rank(values,direction)
        scores.append((feature_name,ranks))
    result=[]
    for i,features in enumerate(all_features):
        coords=[{'feature_name':key,'value':ranks[i],'source_refs':refs([{'source_ref':r} for fs in all_features for f in fs if f['name']==key for r in f['source_refs']])} for key,ranks in scores]
        val=mean_score([x['value'] for x in coords])
        result.append({'state':'EXPERIMENTAL_UNCALIBRATED' if val is not None else 'UNKNOWN','value':val,'meaning':rules[name]['meaning'],'component_scores':{'components':coords},'cohort':list(SYMBOLS),'calibrated':False,'probability_claim':'UNSET_REQUIRED'})
    return result

def _assessment_bodies(inputs):
    require(type(inputs) is list and tuple(v['symbol'] for v in inputs)==SYMBOLS,'WAVE_C_COHORT_OR_NAMESPACE_INVALID')
    for v in inputs:assert_registered(v)
    ctx,_=context_for(inputs[0]);require(all(v['source_identity']==inputs[0]['source_identity'] for v in inputs),'WAVE_C_COHORT_VERSION_MISMATCH')
    records=[build_features(v) for v in inputs];features=[r[0] for r in records]
    qualities=score('quality',ctx['rules']['quality']['metrics'],features,ctx['rules']);timings=score('timing',ctx['rules']['timing']['metrics'],features,ctx['rules'])
    assessments=[]
    for i,v in enumerate(inputs):
        fs,coverage,conflicts,warnings=records[i];usable=sum(x['eligible_observation_count']>0 for x in coverage)
        groups={'company_quality':['eps','roe','debt_to_assets','netprofit_yoy','earnings_quality','cash_generation'],'sector_quality':['current_observed_industry','historical_industry_membership'],'catalyst':['corporate_action_observations','company_announcement_catalyst','verified_action_reconciliation'],'evidence_quality':['observed_bar_sessions'],'valuation':['valuation_ttm_pe','valuation_ev_ebitda'],'timing':list(PRICE_NAMES),'risk':['raw_daily_volatility_20_sessions_pct','raw_max_drawdown_60_sessions_pct','debt_to_assets','st_status','suspension_status'],'cost':[],'account_suitability':[],'tradeability':[]}
        dimensions=[{'name':name,'state':'UNSET_REQUIRED' if name in ('cost','account_suitability') else 'BLOCKED' if name=='tradeability' else 'UNKNOWN' if name=='valuation' or not any(f['value'] is not None for f in fs if f['name'] in groups[name]) else 'OBSERVED_PARTIAL','feature_names':groups[name],'limitation':'SOURCE_TRUST_AND_MISSING_EVIDENCE_REMAIN_UNRESOLVED; NOT_A_FORMAL_GATE'} for name in DIMENSIONS]
        with localcontext() as c:c.prec=50;evidence=text(Decimal(usable)*100/8)
        body={'input_ref':{k:v[k] for k in ('object_id','object_version','content_hash')},'features':fs,'dimensions':dimensions,'quality_score':qualities[i],'timing_score':timings[i],'coverage':coverage,
          'evidence_quality':{'value':evidence,'meaning':'ENGINEERING_COVERAGE_NOT_TRUST_OR_PROBABILITY','usable_categories':usable,'total_categories':8},'conflicting_evidence':conflicts,
          'missing_categories':[x['category'] for x in coverage if x['eligible_observation_count']==0],'warnings':warnings,'experimental_grade':'UNSET_REQUIRED','grade_mapping':'UNSET_REQUIRED','cost':'UNSET_REQUIRED','account_suitability':'UNSET_REQUIRED','tradeability':'BLOCKED'}
        assessments.append(body)
    return assessments

def assess_all(inputs):return produce_assessments(inputs)
