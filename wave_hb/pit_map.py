"""Source-pinned Historical PIT blocker inventory, never an admission issuer.

This module performs no network, signing, enrollment, credential, trading or
state-store operation. Existing originals are reopened read-only. The fixture
selector exercises cutoff/revision semantics and cannot admit actual history.
"""
from copy import deepcopy
from pathlib import Path
import json

from wave_h.common import (ROOT, BASELINE_ROOT, SYMBOLS, canonical, digest, sha,
                          require, keys, timestamp, hash_value, checked_file,
                          reopen)
from wave_h.core import frozen_context

VERSION = '1.0.0'
NAMESPACE = 'EVIDENCE_ONLY_HISTORICAL_PIT:CORE_40'
FIXTURE_NAMESPACE = 'PIT_EVIDENCE_SYNTHETIC:CORE_40'
H_A_CONTEXT = 'sha256:5159515509c7cf5959a2c572af9981ba4fa886d5ec7a911d56ff3e9c3b655096'
FIXED_METADATA = (
 ('docs/wave-h/Historical-PIT-Three-Symbol-Matrix.json', 'sha256:bf39a854fd5418c840a92b165a56e1fd2e478093256cd5107ad9adf6466ad80a', 138128),
 ('docs/wave-h/Historical-PIT-Closure-Progress.json', 'sha256:a07e7823ad406901d8e5617c9d5b46489f3ca5787291b43ef1371cc74244ac17', 13908),
 ('docs/wave-f/Frozen-StrategySpec-v1.json', 'sha256:d4eb866d6675e52f4b5158374f94a3152e4ae406c62add22a8c807762b0215da', 11343),
 ('docs/wave-d/evidence.json', 'sha256:38b7d6044676f4424f65fa091665809b9eeb34a408f5e58d97d339cc7daf5069', 3629),
 ('docs/wave-g/Provider-Redacted-Material-Template.json', 'sha256:82e85a9779f727005e32973a14b0ae92da7d2e3e45280ac9f99558bd771547b5', 732),
)

# These are requirements derived from the frozen declarations, not defaults.
# Underlying fields are explicit so a derived score cannot hide an unproved
# financial, sector, action, benchmark, policy or execution prerequisite.
INPUT_GROUPS = (
 ('raw_bars_volume', ('open','high','low','close','pre_close','volume','amount','trade_date','MA20','MA60','MA60_t_minus_20','true_range','ATR20','previous3_high','previous60_high','breakout_reference','entry_price','entry_ATR20','stock_total_return20'),
  'RAW_NOT_ADJUSTED; source declared CNY/share, share/lot and amount scales require independent proof'),
 ('financial_ann_fann_date', ('revenue','operating_cost','gross_profit','net_income_consolidated','net_income_parent','operating_cashflow','capital_expenditure','total_assets','total_liabilities','cash','interest_bearing_debt','accounts_receivable','inventories','equity_including_minority','EBITDA','ROIC','report_period','report_type','company_type','ann_date','f_ann_date','quarterly_de_cumulated_revenue','TTM_revenue','previous_comparable_TTM_revenue','TTM_gross_margin','previous_comparable_TTM_gross_margin','TTM_net_income','TTM_operating_cashflow','TTM_EBITDA','net_debt','invested_capital','NOPAT'),
  'Versioned consolidated scope; currency/scale; YTD to quarter/TTM construction; date-only publication is not an instant'),
 ('revision_chronology_first_visibility', ('revision_id','supersedes_revision_id','revision_first_visible','statement_original_hash','restatement_scope'),
  'Append-only issuer original chronology; update_flag cannot order revisions'),
 ('valuation_history', ('PE_TTM','PB','PS_TTM','enterprise_value','total_market_value','circulating_market_value','total_shares','turnover_rate','normalized_cycle_earnings','valuation_multiple_percentile'),
  'Positive multiple/1260 actual-session window; source multiple not independently reconstructed TTM; EV and cycle policy UNSET'),
 ('industry_history', ('industry_classification_version','industry_membership_interval','sector_total_return','sector_constituents','sector_RS20'),
  'Dated membership and contemporaneous licensed sector total-return series, not current industry'),
 ('catalyst_originals', ('issuer_event_body','event_type','human_coding_version','event_publication_instant','rescission_expiry','thesis_invalidation','hard_negative_evidence'),
  'Verified original body ORDER_AWARD/CAPACITY_COMMISSIONING/POSITIVE_PROFIT_GUIDANCE; exact clock; no title/LLM substitute'),
 ('st_history', ('ST_status','risk_warning_status_interval'), 'Official dated start/withdrawal and first-visible originals'),
 ('suspension_history', ('halt_resume_status','halt_resume_interval'), 'Daily complete halt/resume evidence; missing bar or empty query is UNKNOWN'),
 ('name_status_history', ('security_name','name_change_interval'), 'Historical name change originals; current name cannot backfill'),
 ('listing_delisting_history', ('security_identity','exchange_board','listing_date','delisting_date','restoration_relisting_trigger'), 'A-share identity and effective/visible intervals; a listing anchor is not continuous membership'),
 ('historical_universe_completeness', ('historical_universe_membership','selection_exclusion_reason','universe_snapshot_version'), 'Exact pilot scope is not whole-market evidence; current survivors are not historical universe'),
 ('corporate_actions', ('action_id','record_date','ex_date','payment_date','cash_dividend','stock_distribution','rights_issue','action_revision'), 'Independent implementation/payment originals; entitlements/units and event semantics'),
 ('adjustment_factor_semantics', ('adjustment_factor','factor_version','factor_method','anchor_version','factor_rounding'), 'Raw preserved; versioned factor methodology/rounding and independent action reconciliation'),
 ('dividend_action_reconciliation', ('ex_reference_price','cash_entitlement','dividend_cash_receipt','total_return_reconciliation'), 'Cash plus factor double counting forbidden; five ambiguities/eight deltas retained'),
 ('historical_price_limit_regime', ('dated_rule_version','rule_effective_interval','per_security_rule_applicability','limit_up','limit_down','tick_size','lot_size','price_rounding','first_listing_session_exception','risk_board_exception','ex_dividend_limit_reference','T_plus_1'), 'Dated board/ST/IPO/action applicability; band or OHLC does not prove fill'),
 ('exchange_calendar_version', ('actual_session','calendar_version','exceptional_closure','next_exchange_open','actual_holding_sessions'), 'Planned calendar differs from actual session; complete exception history'),
 ('benchmark_total_return', ('benchmark_identifier','benchmark_total_return','benchmark_constituent_history','benchmark_tax_action_method'), 'Owner selection UNSET; licensed PIT total-return series, not price-only proxy'),
 ('dated_costs_and_account', ('commission','minimum_commission','stamp_tax','exchange_clearing_fee','fee_inclusion','slippage','partial_fill','shared_cash','fee_inclusive_affordability','lot_quantity','account_capital','position_exposure','industry_exposure','loss_drawdown_kill','historical_position_lots','settled_sellable_quantity','cash_release_ordering','next_open_execution_price','fillability_and_order_rejection'), 'Owner/account dated original evidence required; actual settings remain UNSET_REQUIRED; OHLC/band is not fill proof'),
 ('economic_estimation_policy', ('contemporaneous_cost_of_capital','scenario_gross_return','scenario_probability','uncertainty_buffer','NetEdge','round_trip_cost','edge_to_cost_ratio'), 'Versioned calibrated estimation/cost policy UNSET; zero cost is not infinite Edge'),
)
EXTRA_DOMAINS = tuple(g[0] for g in INPUT_GROUPS if g[0] not in (
 'financial_ann_fann_date','revision_chronology_first_visibility','industry_history',
 'st_history','suspension_history','name_status_history','listing_delisting_history',
 'historical_universe_completeness','corporate_actions','adjustment_factor_semantics',
 'dividend_action_reconciliation','historical_price_limit_regime','exchange_calendar_version'))
FIELD_REQUIREMENTS = {
 'decision_time': 'REQUIRED_PER_DECISION_NOT_SUPPLIED; exact timezone-aware cutoff for this decision, not a report cutoff or chosen midnight',
 'event_time': 'REQUIRED_WITH_DOMAIN_PRECISION; preserve event/report-period/date-only meaning separately',
 'published_at': 'REQUIRED_EXACT_OR_EXPLICIT_PRECISION_LIMIT; date-only is not midnight',
 'available_at': 'REQUIRED_INDEPENDENT_HISTORICAL_FIRST_USABLE_EVIDENCE <= decision_time',
 'retrieved_at': 'REQUIRED_LITERAL_CAPTURE_CLOCK; present retrieval is not historical availability',
 'first_visible_evidence': 'REQUIRED_ORIGINAL_OBSERVED_THEN_OR_INDEPENDENT_RECONSTRUCTION_PROOF; reconstruction labelled separately',
 'revision_version_chain': 'REQUIRED_VERSION_ID/SUPERSEDES/SOURCE_HASH; no current/latest backfill',
 'rule_effective_interval': 'REQUIRED_DOMAIN_APPLICABLE_INTERVAL_AND_EXCEPTION_HISTORY; date precision retained',
 'security_applicability': 'REQUIRED_EXACT_SECURITY/BOARD/NAMESPACE_AND_HISTORICAL_MEMBERSHIP',
 'original_refs': 'REQUIRED_REOPENABLE_ORIGINAL_SHA256_PLUS_CLOCK_AND_VERSION_LINEAGE; index/title/failed body insufficient',
 'license_status': 'REQUIRED_PRODUCT/PURPOSE/ACCOUNT/RETENTION/STORAGE/TRANSFER_BOUNDARY; API200 insufficient',
 'units_rounding_method': 'REQUIRED_VERSIONED_CURRENCY/SCALE/ROUNDING/FORMULA; no implicit floats or adjusted/raw replacement',
}
GLOBAL_REASONS = ['PER_DECISION_CUTOFF_NOT_SUPPLIED','HISTORICAL_FIRST_VISIBLE_UNPROVEN',
                  'CONTINUOUS_SECURITY_HISTORY_INCOMPLETE','PROVIDER_LICENSE_TRANSPORT_UNVERIFIED',
                  'SEPARATE_FORMAL_RESEARCH_AUTHORIZATION_NOT_GRANTED']


def _load_fixed():
    result={};refs=[]
    for rel,h,n in FIXED_METADATA:
        r={'path':str(BASELINE_ROOT/rel),'sha256':h,'bytes':n}
        result[rel]=json.loads(reopen(r));refs.append(r)
    return result,refs


def _feature_domains(name):
    if name in ('current_observed_name',):return ['name_status_history']
    if name in ('current_observed_listing',):return ['listing_delisting_history','historical_universe_completeness']
    if 'industry' in name:return ['industry_history']
    if name=='st_status':return ['st_history','historical_price_limit_regime']
    if name=='suspension_status':return ['suspension_history']
    if name in ('adjusted_series_consistency_sessions',):return ['adjustment_factor_semantics','corporate_actions']
    if name=='independently_verified_action_reconciliation':return ['dividend_action_reconciliation','corporate_actions']
    if 'announcement' in name or 'catalyst' in name:return ['catalyst_originals']
    if name=='historical_as_of_visibility':return ['revision_chronology_first_visibility']
    if name.startswith(('raw_','distance_ma')) or name in ('last_raw_close','reported_amount_mean20','last_reported_bar_date','observed_bar_sessions'):
        return ['raw_bars_volume','corporate_actions','exchange_calendar_version']
    if name.startswith('valuation_') or name in ('source_pe_ttm','source_pb','source_ps_ttm','source_total_mv','source_circ_mv','source_total_share','source_turnover_rate','source_daily_basic_close'):
        return ['valuation_history','raw_bars_volume','revision_chronology_first_visibility']
    return ['financial_ann_fann_date','revision_chronology_first_visibility']


def _requirements(domains):
    return {'required_domains':list(domains),'required_per_decision_fields':deepcopy(FIELD_REQUIREMENTS),
            'decision_time':None,'historical_available_at':None,'historical_first_visible':None,
            'covered_historical_intervals':[],'historical_visibility_proven':False,
            'formal_admission':'BLOCKED','safe_to_trade':False,'reason_codes':list(GLOBAL_REASONS)}


def _lineage(feature,by_hash):
    originals={};clocks={}
    for r in feature['source_refs']:
        h=r['raw_sha256'];require(h in by_hash,'HB_PIT_REPORT_ORIGINAL_MISSING')
        for original in by_hash[h]:originals[original['path']]=deepcopy(original)
        clock={k:r[k] for k in ('request_id','raw_sha256','event_time','published_at','available_at','retrieved_at','origin','scope')}
        clocks[digest(clock)]=clock
    return {'current_observation_original_refs':[originals[p] for p in sorted(originals)],
            'current_observation_clocks':[clocks[k] for k in sorted(clocks)],
            'full_row_ordinal_lineage_in_pinned_report':True,
            'source_row_reference_count':len(feature['source_refs']),
            'clock_interpretation':'CURRENT_RETRIEVAL_ONLY_NOT_HISTORICAL_FIRST_VISIBLE'}


def _declared_inputs(spec):
    nodes=[]
    for domain,fields,semantics in INPUT_GROUPS:
        for name in fields:
            nodes.append({'input_id':'underlying:'+name,'declaration_scope':'FROZEN_FAMILIES_REQUIRED_DEPENDENCY',
                          'field':name,'semantics':semantics,**_requirements([domain])})
    for name,v in spec['metric_definitions'].items():
        domains={'Quality':['financial_ann_fann_date','economic_estimation_policy'],
          'Growth':['financial_ann_fann_date'], 'Financial Quality':['financial_ann_fann_date'],
          'Valuation':['valuation_history','industry_history'], 'Catalyst':['catalyst_originals'],
          'Risk':['st_history','suspension_history','catalyst_originals','historical_price_limit_regime'],
          'Evidence Quality':['revision_chronology_first_visibility'],
          'Timing':['raw_bars_volume','industry_history','corporate_actions','exchange_calendar_version'],
          'Edge':['economic_estimation_policy','dated_costs_and_account']}[name]
        nodes.append({'input_id':'metric:'+name,'source_path':'metric_definitions.'+name,
                      'declaration_scope':'FROZEN_RESEARCH_PROPOSAL_NOT_OWNER_POLICY',
                      'frozen_definition':deepcopy(v),**_requirements(domains)})
    for family in spec['families']:
        for name in family['timing_features']:
            ds=['raw_bars_volume','corporate_actions','exchange_calendar_version']
            if name=='sector_rs20':ds+=['industry_history']
            nodes.append({'input_id':'family:'+family['family_id']+':'+name,'family_id':family['family_id'],
                          'field':name,'source_path':'families.'+family['family_id']+'.timing_features',
                          'frozen_entry_rule':family['entry_rule'],'frozen_entry_execution':family['entry_execution'],
                          'declaration_scope':'FROZEN_RESEARCH_PROPOSAL_NOT_OWNER_POLICY',**_requirements(ds)})
    # Every decision-bearing policy object remains visible, including exits and
    # economic/OOS gates. No proposal threshold is adopted as Owner policy.
    for name in ('exit_rule','allow_flat_rule','rebalance_frequency','position_rule','kill_conditions',
                 'evaluation','required_research_policy_decisions','candidate_universe'):
        nodes.append({'input_id':'policy:'+name,'source_path':name,'frozen_definition':deepcopy(spec[name]),
                      'declaration_scope':'FROZEN_RESEARCH_PROPOSAL_NOT_OWNER_POLICY',
                      **_requirements(['dated_costs_and_account','exchange_calendar_version',
                                       'historical_price_limit_regime','benchmark_total_return',
                                       'economic_estimation_policy','historical_universe_completeness'])})
    return nodes


def build_map():
    """Reopen immutable H-A context and Wave D original lineage; return metadata."""
    fixed,metadata_refs=_load_fixed();c=frozen_context()
    require(c['context_hash']==H_A_CONTEXT and len(c['source_dependencies'])==1697,'HB_PIT_H_A_CONTEXT_CHANGED')
    matrix=fixed['docs/wave-h/Historical-PIT-Three-Symbol-Matrix.json']['body']
    progress=fixed['docs/wave-h/Historical-PIT-Closure-Progress.json']['body']
    spec=fixed['docs/wave-f/Frozen-StrategySpec-v1.json']
    require(matrix['symbols']==list(SYMBOLS) and matrix['continuous_historical_domains_closed']==0 and
            spec['candidate_universe']['symbols']==list(SYMBOLS) and spec['historical_visibility_proven'] is False,
            'HB_PIT_BASELINE_HISTORY_PROMOTION')
    require([f['family_id'] for f in spec['families']]==['CORE40_Q_PULLBACK_V1','CORE40_Q_BREAKOUT_V1'],
            'HB_PIT_FAMILY_MUTATION')
    by_hash={}
    for r in c['source_dependencies']:by_hash.setdefault(r['sha256'],[]).append(r)
    domains=[]
    for row in matrix['rows']:
        require(row['symbol'] in SYMBOLS and row['historical_visibility_proven'] is False,'HB_PIT_SCOPE_PROMOTION')
        for d in row['domains']:
            require(d['covered_intervals']==[] and d['formal_admission']=='BLOCKED','HB_PIT_BASELINE_DOMAIN_PROMOTION')
            domains.append({'symbol':row['symbol'],**deepcopy(d),
                            'required_per_decision_fields':deepcopy(FIELD_REQUIREMENTS),
                            'historical_decision_time':None,
                            'classification':'SINGLE_EVENT_OR_GENERIC_STRUCTURE_NOT_CONTINUOUS_PIT',
                            'required_decision_input_ids':[]})
        for domain in EXTRA_DOMAINS:
            domains.append({'symbol':row['symbol'],'domain':domain,'facts':[],
                            'classification':'MISSING_HISTORICAL_REQUIRED_INPUT_DOMAIN',
                            'required_decision_input_ids':[],**_requirements([domain])})
    declared=_declared_inputs(spec);reported=[];report_refs=[]
    artifacts=fixed['docs/wave-d/evidence.json']['artifacts']
    for symbol in SYMBOLS:
        selected=[r for r in artifacts if r['name']==symbol+'.report.json']
        require(len(selected)==1,'HB_PIT_REPORT_IDENTITY')
        r={k:selected[0][k] for k in ('path','sha256','bytes')}
        require(r in c['source_dependencies'],'HB_PIT_UNPINNED_REPORT')
        x=json.loads(reopen(r,private=True));report_refs.append(r)
        require(x['symbol']==symbol and x['namespace']=='LOCAL_EXPERIMENTAL_REAL_RESEARCH:CORE_40' and
                x['historical_visibility_proven'] is False and len(x['body']['features'])==58,
                'HB_PIT_REPORT_SCOPE_OR_VERSION')
        for f in x['body']['features']:
            reported.append({'input_id':'wave_d:'+symbol+':'+f['name'],'symbol':symbol,'field':f['name'],
                'declaration_scope':'CURRENT_REAL_REPORT_DIAGNOSTIC_NOT_HISTORICAL_DECISION',
                'report_ref':r,'original_feature_state':f['state'],'original_feature_period':f['period'],
                'original_feature_unit':f['unit'],'original_feature_formula':f['formula'],
                'preserved_report_reason_codes':f['reason_codes'],
                'current_report_cutoff_not_historical_run_cutoff':x['decision_cutoff'],
                'current_report_retrieval_cutoff':x['retrieval_cutoff'],
                **_requirements(_feature_domains(f['name'])),**_lineage(f,by_hash)})
    for d in domains:
        d['required_decision_input_ids']=[n['input_id'] for n in declared+reported
            if d['domain'] in n['required_domains'] and ('symbol' not in n or n['symbol']==d['symbol'])]
    dimensions=fixed['docs/wave-g/Provider-Redacted-Material-Template.json']['dimensions']
    require(len(dimensions)==8 and all(v=={'statement':None,'evidence_paths':[]} for v in dimensions.values()),
            'HB_PIT_SOURCE_LICENSE_PROMOTION')
    from wave_h import pit as h_pit
    from wave_g import pit as g_pit
    from wave_f import pit as f_pit
    captures=[]
    for epoch,mod in (('WAVE_F',f_pit),('WAVE_G',g_pit),('WAVE_H_A',h_pit)):
        for original in mod.evidence()['captures']:
            captures.append({'epoch':epoch,'capture_id':original['capture_id'],
              'body_ref':deepcopy(original['body_ref']),'capture_ref':deepcopy(original['capture_ref']),
              'parsed_ref':deepcopy(original['parsed_ref']),'url':original['url'],
              'http_status':original['http_status'],'error':original['error'],
              'retrieved_at':original['retrieved_at'],'published_at':original['published_at'],
              'available_at':original['available_at'],'source_version':original['source_version'],
              'classification':('FAILED_RESPONSE_NOT_ADMITTED_ORIGINAL' if original['http_status']!=200 or original['error']
                                else 'EXISTING_CURRENT_RETRIEVED_OFFICIAL_ORIGINAL_NOT_HISTORICAL_PIT'),
              'historical_visibility_proven':False,'formal_admission':'BLOCKED'})
    pins={r['path']:deepcopy(r) for r in c['source_dependencies']+metadata_refs}
    source_refs=[pins[p] for p in sorted(pins)]
    result={'version':VERSION,'kind':'HISTORICAL_PIT_BLOCKER_MAP','namespace':NAMESPACE,
        'symbols':list(SYMBOLS),'H_A_context_hash':H_A_CONTEXT,'H_A_dependency_count':1697,
        'source_dependency_refs':source_refs,'source_dependency_hash':digest(source_refs),
        'existing_public_evidence_lineage_refs':matrix['direct_source_refs'],
        'existing_public_capture_evidence':captures,
        'current_report_refs':report_refs,'frozen_strategy_ref':metadata_refs[2],
        'per_decision_field_requirements':deepcopy(FIELD_REQUIREMENTS),
        'historical_decision_time':None,'cutoff_state':'REQUIRED_PER_DECISION_NOT_SUPPLIED',
        'domains':domains,'domain_groups':sorted({d['domain'] for d in domains}),
        'declared_decision_inputs':declared,'current_report_inputs':reported,
        'input_counts':{'frozen_declared_inputs':len(declared),'report_features_per_symbol':58,
                        'report_feature_occurrences':len(reported),'domain_groups':len({d['domain'] for d in domains})},
        'provider_license_transport':{name:'UNKNOWN' for name in dimensions},
        'evidence_interpretation':{'official_originals':'HASH_REOPENED_EXISTING_ORIGINALS_NOT_NEW_CAPTURE',
          'generic_structural_rules':'DATED_RULE_FACTS_NOT_SECURITY_APPLICABILITY_OR_FIRST_VISIBLE',
          'listing_anchors':'SINGLE_EVENT_NOT_UNBROKEN_LISTED_OR_DELISTED_INTERVAL',
          'current_observations':'CAPTURE_AVAILABLE_AT_ONLY_NOT_HISTORICAL_VISIBILITY',
          'financial_versions':'REPORT_PERIOD/DATE_ONLY/UPDATE_FLAG_NOT_REVISION_CHAIN',
          'reconstruction':'ONLY_WITH_INDEPENDENT_FIRST_VISIBLE_ORIGINALS; currently not proven'},
        'preserved_missing_targets':progress['missing_targets'],
        'preserved_previous_failed_originals':matrix['preserved_predecessor_failed_capture_ids'],
        'preserved_failed_discovery_calls':matrix['failed_discovery_calls'],
        'closure_requirements':['PER_DECISION_CUTOFF','REOPEN_ORIGINALS_AND_HASH','INDEPENDENT_FIRST_VISIBLE',
          'REVISION_CHAIN','COMPLETE_EFFECTIVE_INTERVAL','EXACT_SECURITY_APPLICABILITY',
          'DATED_RULE_VERSION','UNITS_AND_ACTION_RECONCILIATION','PURPOSE_LICENSE','INDEPENDENT_FORMAL_REVIEW'],
        'continuous_historical_domains_closed':0,'new_original_captures':0,'network_requests':0,
        'credential_lookups':0,'actual_forward_days':0,'historical_visibility_proven':False,
        'formal_price_backtest':'BLOCKED','formal_fundamental_backtest':'BLOCKED','source_admission':'BLOCKED',
        'native_signal_order_broker':False,'safe_to_trade':False,'productionGate':False,
        'cloud_export':False,'actual_authority':False,'is_authority':False,
        'body':{'state':'BLOCKED','continuous_historical_domains_closed':0,
                'input_counts':{'frozen_declared_inputs':len(declared),'report_feature_occurrences':len(reported),
                                'domain_groups':len({d['domain'] for d in domains})},
                'cutoff_state':'REQUIRED_PER_DECISION_NOT_SUPPLIED','inspection_only':True},
        'role':'ENGINEERING_REQUIREMENTS_NOT_OWNER_BUSINESS_POLICY'}
    return dict(result,content_hash=digest(result))


def render_map(x):
    """Human-readable companion to the complete machine input/original map."""
    require(x['content_hash']==digest({k:v for k,v in x.items() if k!='content_hash'}),'HB_PIT_MAP_INVALIDATED')
    require(x['kind']=='HISTORICAL_PIT_BLOCKER_MAP' and x['namespace']==NAMESPACE and
            all(x[k] is False for k in ('is_authority','actual_authority','historical_visibility_proven',
            'safe_to_trade','productionGate','native_signal_order_broker','cloud_export')) and
            x['continuous_historical_domains_closed']==0 and x['actual_forward_days']==0,
            'HB_PIT_DISPLAY_SCOPE_PROMOTION')
    lines=['# Historical PIT 阻断地图 V1','',
      '本图重开既有 H-A 原件和 Wave D 三股报告；新增网络请求、历史连续域闭环、实际 Forward 天数均为 0。',
      '正式价格/基本面回测、来源许可、交易、云端和生产继续 BLOCKED。',
      '',f"范围：{', '.join(x['symbols'])}；{x['input_counts']['domain_groups']} 个域组；"
      f"{x['input_counts']['frozen_declared_inputs']} 个冻结规格输入节点；174 个既有报告特征实例（每股 58）。",'',
      '历史 decision_time 未提供，必须逐决策提供；本图不会替 Owner 选择截止、午夜时间或历史区间。',
      '每个输入均要求 event_time、published_at、available_at、retrieved_at、first-visible、revision/version、'
      '有效区间、证券适用性、原件 SHA 和用途许可。现有报告的 2026 年捕获时间只证明当前观察。', '',
      '| PIT 域 | 当前依据与缺口 | 正式状态 |','|---|---|---|']
    for domain in x['domain_groups']:
        rows=[d for d in x['domains'] if d['domain']==domain]
        counts=[len(d.get('facts',[]))+len(d.get('wave_g_new_facts',[]))+len(d.get('wave_h_new_facts',[])) for d in rows]
        label='已有单事件/通用规则结构；缺连续适用区间、首次可见和修订链' if any(counts) else '缺三股逐决策完整原件/版本/适用区间/首次可见证明'
        lines.append('| '+domain+' | '+label+' | BLOCKED |')
    lines += ['', '机器地图逐项保留两个冻结 family 的 timing、共同指标、退出/仓位/风险/经济/OOS 规格及每股 58 个报告特征。'
      '冻结规格中的阈值仍是研究提案；费用、账户和业务决策不因列入地图而成为生产默认值。', '',
      '官方上市锚、2020/2023/2026 交易规则、公告索引、当下可查询历史行情、同源因子数学一致性，'
      '均不能单独关闭证券连续历史 PIT。失败正文、5 处行动歧义、8 个 pre_close 差异和财报修订缺口保留。', '',
      'Provider/License/Transport 的 8 个维度仍 UNKNOWN。来源 hash 绑定的是捕获内容，不证明提供方版本、许可或历史首次可见。', '',
      '后续每个正式 decision input 只有在原件可重开、历史 first-visible ≤ decision_time、有效区间/证券适用性、'
      '版本修订链、规则/单位/用途许可和独立审查均有证据时才可申请闭环；本模块没有实际准入接口。', '',
      '测试仅使用明确 SYNTHETIC fixture 演练四时钟、未来版本隔离和修订选择；fixture 一致也不会获得正式回测或交易权限。', '',
      '原件位于既有不可迁移 private archive；JSON 索引包含路径和 hash，验收包不得据此复制 raw/数据库/凭证。', '',
      '地图 hash：'+x['content_hash'], 'H-A context：'+x['H_A_context_hash'], '']
    return '\n'.join(lines)


FIXTURE_KEYS = ('kind','namespace','symbol','field','event_time','published_at','available_at',
    'retrieved_at','first_visible','revision_id','supersedes_revision_id','source_version',
    'effective_from','effective_to','security_applicability','original_ref','first_visible_original_ref',
    'revision_original_ref','license_state')


def _fixture_original(r):
    keys(r,('path','sha256','bytes'));p=Path(r['path'])
    require(p.is_absolute() and p.resolve()==p and not p.is_symlink() and p.is_file(),
            'HB_PIT_FIXTURE_ORIGINAL_MISSING_OR_ALIAS')
    require(type(r['bytes']) is int and r['bytes']>=0 and p.stat().st_mode&0o777==0o600,
            'HB_PIT_FIXTURE_ORIGINAL_PRIVATE')
    b=checked_file(p,r['sha256']);require(len(b)==r['bytes'],'HB_PIT_FIXTURE_ORIGINAL_BYTES')
    return b


def assess_fixture_record(record,decision_time,*,symbol,field):
    """Pure SYNTHETIC consistency result: never actual availability/admission."""
    keys(record,FIXTURE_KEYS);canonical(record)
    require(record['kind']=='SYNTHETIC_PIT_RECORD' and record['namespace']==FIXTURE_NAMESPACE,
            'HB_PIT_FIXTURE_NAMESPACE_ONLY')
    require(symbol in SYMBOLS and record['symbol']==symbol and record['security_applicability']==[symbol]
            and record['field']==field and type(field) is str and bool(field),'HB_PIT_SECURITY_OR_FIELD_MISMATCH')
    for k in ('revision_id','source_version'):
        require(type(record[k]) is str and bool(record[k]),'HB_PIT_REVISION_VERSION_REQUIRED')
    require(record['supersedes_revision_id'] is None or
            (type(record['supersedes_revision_id']) is str and bool(record['supersedes_revision_id']) and
             record['supersedes_revision_id']!=record['revision_id']),'HB_PIT_REVISION_SELF_OR_INVALID')
    originals={k:_fixture_original(record[k]) for k in ('original_ref','first_visible_original_ref','revision_original_ref')}
    require(record['source_version']==record['original_ref']['sha256'],'HB_PIT_SOURCE_VERSION_NOT_ORIGINAL_HASH')
    t={k:timestamp(record[k]) for k in ('event_time','published_at','available_at','retrieved_at','first_visible','effective_from','effective_to')}
    cutoff=timestamp(decision_time)
    require(t['event_time']<=t['published_at']<=t['first_visible']<=t['available_at']<=t['retrieved_at'],
            'HB_PIT_FOUR_CLOCK_ORDER')
    require(t['effective_from']<t['effective_to'],'HB_PIT_EFFECTIVE_INTERVAL_INVALID')
    # The fixture proofs must bind the actual fixture metadata, rather than
    # allowing any hash-bearing file to stand in for a first-visible witness.
    expected={
      'original_ref':{'kind':'SYNTHETIC_PIT_VALUE_ORIGINAL','namespace':FIXTURE_NAMESPACE,
        'symbol':symbol,'field':field,'revision_id':record['revision_id'],'event_time':record['event_time']},
      'first_visible_original_ref':{'kind':'SYNTHETIC_PIT_FIRST_VISIBLE_ORIGINAL','namespace':FIXTURE_NAMESPACE,
        'symbol':symbol,'field':field,'revision_id':record['revision_id'],
        'original_sha256':record['original_ref']['sha256'],'published_at':record['published_at'],
        'first_visible':record['first_visible'],'available_at':record['available_at']},
      'revision_original_ref':{'kind':'SYNTHETIC_PIT_REVISION_ORIGINAL','namespace':FIXTURE_NAMESPACE,
        'symbol':symbol,'field':field,'revision_id':record['revision_id'],
        'original_sha256':record['original_ref']['sha256'],'supersedes_revision_id':record['supersedes_revision_id']},
    }
    for k,raw in originals.items():
        require(raw==canonical(expected[k]),'HB_PIT_FIXTURE_PROOF_METADATA_BINDING')
    reasons=[]
    if t['available_at']>cutoff:reasons.append('FUTURE_AVAILABLE_AT')
    if not t['effective_from']<=cutoff<t['effective_to']:reasons.append('NOT_EFFECTIVE_AT_DECISION')
    if record['license_state']!='SYNTHETIC_ONLY_NO_ACTUAL_LICENSE':reasons.append('FIXTURE_LICENSE_SCOPE_INVALID')
    return {'version':VERSION,'kind':'SYNTHETIC_PIT_CONSISTENCY_RESULT','namespace':FIXTURE_NAMESPACE,
            'consistent_at_cutoff':not reasons,'reason_codes':reasons,'decision_time':decision_time,
            'revision_id':record['revision_id'],'historical_visibility_proven':False,
            'formal_admission':'BLOCKED','productionGate':False,'actual_authority':False,'safe_to_trade':False}


def select_fixture_revision(records,decision_time,*,symbol,field):
    """Select latest visible synthetic revision; demand a complete fixture chain."""
    require(type(records) is list and bool(records),'HB_PIT_REVISION_CHAIN_REQUIRED')
    by={};checks=[]
    for r in records:
        result=assess_fixture_record(r,decision_time,symbol=symbol,field=field)
        require(r['revision_id'] not in by,'HB_PIT_DUPLICATE_REVISION_ID')
        by[r['revision_id']]=r;checks.append((r,result))
    roots=0
    for r in records:
        previous=r['supersedes_revision_id']
        if previous is None:roots+=1;continue
        require(previous in by,'HB_PIT_REVISION_PREDECESSOR_MISSING')
        old=by[previous]
        require(timestamp(old['first_visible'])<timestamp(r['first_visible']) and
                timestamp(old['available_at'])<timestamp(r['available_at']),'HB_PIT_REVISION_CHRONOLOGY_INVALID')
    require(roots==1,'HB_PIT_REVISION_ROOT_AMBIGUOUS')
    followers={}
    for r in records:
        p=r['supersedes_revision_id']
        if p is not None:
            require(p not in followers,'HB_PIT_REVISION_BRANCH_AMBIGUOUS');followers[p]=r['revision_id']
    visible=[r for r,result in checks if result['consistent_at_cutoff']]
    chosen=max(visible,key=lambda r:timestamp(r['available_at'])) if visible else None
    return {'version':VERSION,'kind':'SYNTHETIC_PIT_REVISION_SELECTION','namespace':FIXTURE_NAMESPACE,
            'selected_revision_id':chosen['revision_id'] if chosen else None,
            'decision_time':decision_time,'excluded_revision_ids':[r['revision_id'] for r,c in checks if not c['consistent_at_cutoff']],
            'historical_visibility_proven':False,'formal_admission':'BLOCKED','productionGate':False,
            'actual_authority':False,'safe_to_trade':False}


def run_formal(*args,**kwargs):
    raise ValueError('HB_PIT_FORMAL_HISTORY_NOT_ADMITTED')
