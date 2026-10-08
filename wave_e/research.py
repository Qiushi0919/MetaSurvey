"""Frozen diagnostic scenarios and factual readiness, private output only."""
from copy import deepcopy
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import csv, io
from .core import canonical, digest, require, SYMBOLS, price_series
from .engine import run_scenario
from .forward import readiness

PRICE_DOMAINS=('source_admission','provider_identity','license','transport_integrity','raw_bar_readiness','adjustment_readiness','corporate_action_readiness','security_status_history','suspension_history','limit_tradability_history','universe_history','historical_visibility','transaction_cost_policy','account_policy','strategy_parameter_freeze')
FUNDAMENTAL_DOMAINS=('financial_publication_timing','revision_chronology','industry_history')
SNAPSHOT_CHECKS=['SEPARATE_HUMAN_OWNER_AUTHORIZATION','OFFICIAL_ACTUALLY_RESUMED_SESSION','FRESH_SOURCE_DAY_AFTER_20260930','ACTUAL_POST_MARKET_AVAILABILITY','AVAILABLE_RETRIEVED_CUTOFF_ORDER','EXACT_THREE_SYMBOLS','SOURCE_RULE_CODE_SCHEMA_BINDINGS','APPEND_NEW_ORIGINALS','COMPARE_WITH_SNAPSHOT_A','PROVIDER_LICENSE_POLICY_RECHECK']
DAILY_FIELDS=['decision_cutoff','observed_universe','candidate_or_no_candidate','signal_source','hypothetical_entry','hypothetical_exit','tradeability','cost_assumptions','risk_state','unknowns','reason_codes','daily_hash','predecessor_hash']

def backtest_readiness(ctx):
    reason={
      'source_admission':'Underlying gateway QUARANTINED; API access is not admission.',
      'provider_identity':'Seller/channel identity independently UNVERIFIED.',
      'license':'Purpose/storage/transfer/license grants independently UNVERIFIED.',
      'transport_integrity':'Original gateway HTTP; integrity independently UNVERIFIED.',
      'raw_bar_readiness':'327 aligned current-observed sessions usable for diagnostics only; formal source/PIT unproven.',
      'adjustment_readiness':'Same-provider factors only; no independent authoritative adjustment.',
      'corporate_action_readiness':'5 ambiguities and 8 pre_close deltas preserved; tolerance/rounding UNSET_REQUIRED.',
      'security_status_history':'Historical ST/delist/status absent; current terminal schema failures preserved.',
      'suspension_history':'Historical suspension coverage UNKNOWN; absence is not clear status.',
      'limit_tradability_history':'Historical daily limits/executability UNKNOWN; assumption never proof.',
      'universe_history':'Three present-day engineer-selected securities; survivorship/selection not historical universe.',
      'historical_visibility':'Today-retrieved historical dates have no past decision-time available_at proof.',
      'financial_publication_timing':'ann_date/f_ann_date DATE_ONLY literals; historical first visibility UNKNOWN.',
      'revision_chronology':'Current versions/update_flag cannot reconstruct independent revision availability.',
      'industry_history':'Current membership cannot be backfilled into historical universe or features.',
      'transaction_cost_policy':'Only synthetic DPU scenarios; actual dated fees/minimum/tax/slippage UNSET.',
      'account_policy':'Actual capital/account/broker/risk unknown; 30 UNSET_REQUIRED.',
      'strategy_parameter_freeze':'Diagnostic rule frozen; formal strategy/risk configuration UNSET_REQUIRED.'}
    return {'conditions':[{'domain':d,'state':'PARTIAL' if d in ('raw_bar_readiness','adjustment_readiness','corporate_action_readiness','strategy_parameter_freeze') else 'BLOCKED','reason':reason[d]} for d in ctx['rules']['readiness_domains']], 'ENGINE_DIAGNOSTIC_READY':'READY','FORMAL_PRICE_BACKTEST_READY':'BLOCKED','FORMAL_FUNDAMENTAL_PIT_BACKTEST_READY':'BLOCKED','price_blockers':list(PRICE_DOMAINS),'fundamental_additional_blockers':list(FUNDAMENTAL_DOMAINS),'history_is_current_observed':True,'unset_actual_parameters':30}

def position_ledger(result):
    states={s:{'symbol':s,'quantity':0,'acquired_date':None,'acquired_source_ref':None,'book_cost_minor':'0'} for s in sorted(SYMBOLS)};rows=[]
    for day in result['equity']:
        for f in result['fills']:
            if f['fill_date']!=day['trade_date']:continue
            s=f['symbol']
            if f['direction']=='ENTER_HYPOTHETICAL':states[s]={'symbol':s,'quantity':f['quantity'],'acquired_date':f['fill_date'],'acquired_source_ref':f['fill_source_ref'],'book_cost_minor':str(int(f['gross_minor'])+int(f['fees_minor']))}
            else:states[s]={'symbol':s,'quantity':0,'acquired_date':None,'acquired_source_ref':None,'book_cost_minor':'0'}
        for s in sorted(SYMBOLS):
            require(states[s]['quantity']==day['quantities'][s],'WAVE_E_DAILY_POSITION_LEDGER_MISMATCH')
            rows.append({'trade_date':day['trade_date'],**deepcopy(states[s]),'marked_value_minor':day['marked_positions_minor'][s],'unit':'DPU_MINOR_DIAGNOSTIC_ONLY'})
    require(list(states.values())==result['positions'],'WAVE_E_FINAL_POSITION_LEDGER_MISMATCH');return rows

def audit_run(series,policy,result):
    dates=[r['trade_date'] for r in series[SYMBOLS[0]]];assertions=0
    for s in result['signals']:
        i=int(s['decision_index']);require(s['decision_date']==dates[i] and all(r['trade_date']<=dates[i] for r in s['window_source_refs']) and s['momentum_base_source_ref']['trade_date']==dates[i-20], 'WAVE_E_FUTURE_WINDOW');assertions+=1
    for f in result['fills']:
        require(int(f['fill_index'])==int(f['decision_index'])+1 and f['fill_date']>f['decision_date'],'WAVE_E_SAME_BAR_FILL');assertions+=1
    require(not any(result['audit'][k] for k in ('future_index_violations','same_bar_fill_violations','t_plus_one_violations','ledger_mismatch_violations','negative_cash_violations')),'WAVE_E_ENGINE_AUDIT_VIOLATION');assertions+=1
    if policy['tradeability']=='BLOCK_UNKNOWN':require(not result['fills'],'WAVE_E_UNKNOWN_STATUS_FALSE_ACCEPTANCE');assertions+=1
    proofs=[]
    for n in (60,120,240):
        prefix={s:deepcopy(rs[:n]) for s,rs in series.items()};a=run_scenario(prefix,policy);b=run_scenario(prefix,policy)
        require(a==b,'WAVE_E_PREFIX_NONDETERMINISM')
        cutoff=dates[n-1];expected={k:[v for v in result[k] if v['decision_date']<=cutoff] if k=='signals' else [v for v in result[k] if v['fill_date']<=cutoff] if k=='fills' else result[k][:n] for k in ('signals','fills','equity')}
        require(all(a[k]==expected[k] for k in expected),'WAVE_E_PREFIX_LOOKAHEAD')
        perturbed=deepcopy(series)
        with localcontext() as c:
            c.prec=100;c.rounding=ROUND_HALF_EVEN
            for rs in perturbed.values():
                for row in rs[n:]:
                    for k in ('open','high','low','close'):row[k]=format(Decimal(row[k])*Decimal('1.125'),'f')
        changed=run_scenario(perturbed,policy)
        require([s for s in changed['signals'] if s['decision_date']<=cutoff]==a['signals'] and [f for f in changed['fills'] if f['fill_date']<=cutoff]==a['fills'] and changed['equity'][:n]==a['equity'],'WAVE_E_FUTURE_TAIL_LEAKAGE')
        proofs.append({'prefix_sessions':n,'deterministic':True,'signal_fill_equity_prefix_identical':True,'future_tail_perturbation_invariant':True});assertions+=3
    return {'state':'PASS','assertions':assertions,'prefix_proofs':proofs,'same_bar_fill_count':0,'future_window_count':0,'historical_pit_proven':False,'financial_features_used':0,'availability_audit':'ALL_SOURCE_RETRIEVALS_AT_CURRENT_CAPTURE_BEFORE_GLOBAL_ENGINE_CUTOFF; NOT_HISTORICAL_DECISION_AVAILABILITY','historical_universe':'CURRENT_THREE_STOCK_DIAGNOSTIC_COHORT_NOT_HISTORICAL_UNIVERSE'}

def jsonl(rows):return b''.join(canonical(x)+b'\n' for x in rows)
def equity_csv(rows):
    b=io.StringIO(newline='');w=csv.writer(b,lineterminator='\n');w.writerow(['trade_date','cash_minor_DPU','equity_minor_DPU','peak_equity_minor_DPU','drawdown_ratio_diagnostic_only'])
    for r in rows:w.writerow([r['trade_date'],r['cash_minor'],r['equity_minor'],r['peak_equity_minor'],r['drawdown_ratio']])
    return b.getvalue().encode()

def build(ctx):
    paths,coverage=price_series(ctx);blobs={};scenarios=[];audits=[];sensitivity=[];assumptions=[]
    binding={k:ctx[k] for k in ('source_identity','rules_hash','code_hash','schema_hash','predecessor_hash')};binding.update(contract_version='1.0.0',decision_cutoff=ctx['rules']['decision_cutoff'],retrieval_cutoff=ctx['retrieval_cutoff'],labels=ctx['rules']['labels'],namespace=ctx['rules']['namespace'],symbols=list(SYMBOLS),invalidation_conditions=['SOURCE_RULE_CODE_SCHEMA_CUTOFF_CHANGED','PREDECESSOR_MUTATED','PRIVATE_PATH_SUBSTITUTION'],known_unknowns=['PROVIDER','LICENSE','TRANSPORT','HISTORICAL_PIT','STATUS','ACTION','COST_ACCOUNT_RISK','HISTORICAL_UNIVERSE','FINANCIAL_PUBLICATION_REVISION','INDUSTRY_HISTORY'])
    for treatment,series in paths.items():
        for item in ctx['rules']['scenarios']:
            name=treatment+':'+item['name'];policy=item['policy'];result=run_scenario(series,policy);positions=position_ledger(result);audit=audit_run(series,policy,result);audits.append({'scenario':name,**audit})
            base=treatment+'/'+item['name']+'/'
            for fname,rows in [('signal-ledger.jsonl',result['signals']),('hypothetical-fill-ledger.jsonl',result['fills']),('position-ledger.jsonl',positions),('equity-ledger.jsonl',result['equity'])]:blobs[base+fname]=jsonl(rows)
            blobs[base+'equity-curve.csv']=equity_csv(result['equity']);blobs[base+'diagnostic-output.json']=canonical({'binding':binding,'scenario':name,'price_treatment':treatment,'policy':policy,'policy_hash':digest(policy),'result':result})+b'\n'
            blobs[base+'drawdown.json']=canonical({'binding':binding,'scenario':name,'record':result['drawdown']})+b'\n';blobs[base+'turnover.json']=canonical({'binding':binding,'scenario':name,'record':result['turnover']})+b'\n'
            scenarios.append({'name':name,'price_treatment':treatment,'policy_hash':digest(policy),'signals_count':len(result['signals']),'hypothetical_fills_count':len(result['fills']),'sessions_count':327,'output_hash':digest(result),'tradeability_proven':False,'financial_features_used':0})
            sensitivity.append({'scenario':name,'price_treatment':treatment,'policy':policy,'initial_cash_minor':policy['initial_cash_minor'],'terminal_equity_minor':result['equity'][-1]['equity_minor'],'terminal_cash_minor':result['audit']['final_cash_minor'],'drawdown':result['drawdown'],'turnover':result['turnover'],'unit':'SYNTHETIC_DPU_MINOR_ONLY','NOT_STRATEGY_EVIDENCE':True,'corporate_actions_credited':False,'total_return':False})
            assumptions.append({'scenario':name,**result['assumptions'],'security_status':'UNKNOWN','suspension':'UNKNOWN','limit_status':'UNKNOWN','delisting':'UNKNOWN','missing_rows':'BLOCK_ENTIRE_RUN','historical_universe':'PRESENT_DAY_THREE_STOCK_ENGINEERING_SELECTION','survivorship_bias_disclosed':True,'financial_features_used':0})
    def put(name,obj):blobs[name]=canonical({'binding':binding,**obj})+b'\n'
    put('lookahead-audit.json',{'state':'PASS','scenarios':audits,'same_bar_fill_count':0,'future_window_count':0,'historical_visibility_proven':False})
    put('action-adjustment-sensitivity.json',{'state':'SENSITIVITY_ONLY','scenarios':sensitivity,'preserved_multi_original_action_ambiguities':5,'preserved_nonzero_pre_close_deltas':8,'tolerance':'UNSET_REQUIRED','source_rounding_policy':'UNSET_REQUIRED','cash_entitlement_inferred':False,'cash_dividend_share_credits':False,'authoritative_adjusted_price':False,'total_return':False,'factor_anchor':'FIRST_OBSERVED_SESSION_NOT_FUTURE_LATEST_FACTOR','predecessor_action_evidence':'IMMUTABLE_WAVE_D_INPUT_ASSESSMENT_REPORT_AND_GATE','raw_factor_math_does_not_close_action_gaps':True})
    put('cost-sensitivity.json',{'scenarios':sensitivity,'all_parameters_synthetic_DPU':True,'actual_settings':'UNSET_REQUIRED','net_edge_computed':False})
    put('tradeability-assumption-registry.json',{'scenarios':assumptions,'real_tradeability_proven':False})
    put('source-coverage.json',{'coverage':coverage,'historical_visibility_proven':False,'financial_rows_used':0,'source_fingerprints_and_raw_hashes':'PER_ROW_PRIVATE_SIGNAL_FILL_EQUITY_REFERENCES','private_artifact_refs':'BOUND_BY_ARTIFACT_MANIFEST'})
    f=readiness();require(f['actual_forward_days']==0 and f['real_start_state']=='BLOCKED','WAVE_E_FORWARD_FALSE_ACCEPTANCE')
    bodies={
      'HistoricalBacktestReadiness':backtest_readiness(ctx),
      'DiagnosticBacktestResult':{'scenarios':scenarios,'lookahead_audit':'PASS','ledger_reconciliation':'PASS','formal_strategy_evidence':False,'historical_universe_claim':False,'cost_is_net_edge':False,'corporate_action_applied':False,'adjusted_authority':'NONE_FACTOR_SENSITIVITY_ONLY','monetary_unit':'UNVERIFIED_SOURCE_PRICE_DPU','real_account_settings':'UNSET_REQUIRED'},
      'SnapshotBPreflight':{'runner_ready':True,'actual_run_authorized':False,'actual_run_executed':False,'state':'PENDING','actual_forward_days':0,'checks':SNAPSHOT_CHECKS,'noncounted_days':['20261006','20261007','OLD_20260930_RETRIEVAL','SYNTHETIC_FIXTURE','HISTORICAL_REPLAY'],'automatic_scheduling':False},
      'ForwardPaperReadiness':{'engine_ready':True,'real_start_state':'BLOCKED','actual_forward_days':0,'fixture_namespace':f['namespace'],'actual_settings':'UNSET_REQUIRED','unset_actual_parameter_count':30,'snapshot_b_state':'PENDING','minimum_actual_sessions':20,'scheduling_enabled':False,'native_promotion':False,'required_daily_fields':DAILY_FIELDS,'actual_ledger_started':False}}
    put('forward-paper-empty-ledger.json',{'records':[],'actual_forward_days':0,'actual_ledger_started':False,'required_daily_fields':DAILY_FIELDS,'next_real_authority':'SEPARATE_OWNER_DECISION_AND_REVIEWED_REAL_AUTHORITY_IMPLEMENTATION_REQUIRED','fixture_positive_proofs':'UNIT_TESTS_ONLY_NOT_ACTUAL_DAYS'})
    lines=['# Wave E 三股诊断回放报告','', 'NON_PIT_DIAGNOSTIC / NOT_STRATEGY_EVIDENCE / NON_TRADEABLE / LOCAL_ONLY','', '已使用冻结的三个证券现有日线观测，各327个共同日期。数据今天可查询的事实不证明历史决策时可见；所选现有证券不是历史 universe。本报告仅验证引擎、账本、时间顺序和敏感性。','', '规则在运行前冻结：close(t) > MA20(t) > MA60(t)，且20期动量比 >1；退出 close(t) < MA20(t)。最早在下一个已观测交易日开盘进行假设成交。每股最多一个合成 lot；先退出再进入、证券代码排序、共享合成现金、T+1、费用包含在可负担性内。没有强制终端清仓，没有优化或财务特征。','', '下面所有余额和费用使用 DPU/100 的整数最小单位；DPU 是来源价格标度未经验证的诊断单位，不能解释为实际人民币账户、实际费率、策略收益或盈利能力。','', '| 诊断场景 | 信号数 | 假设成交数 | 终端权益 DPU minor | 最大回撤诊断比 |','|---|---:|---:|---:|---:|']
    for x,s in zip(scenarios,sensitivity):lines.append('| '+x['name']+' | '+str(x['signals_count'])+' | '+str(x['hypothetical_fills_count'])+' | '+s['terminal_equity_minor']+' | '+s['drawdown']['max_drawdown_ratio']+' |')
    lines+=['','UNKNOWN_BLOCK 两个价格路径均不允许成交。其他路径仅明确假设可交易；ST、停牌、涨跌停、退市与历史 universe 仍 UNKNOWN。零费率仅敏感性基线，未计算 NetEdge/胜率/概率/评级。','', 'Raw 原始路径与 factor(first observed anchor) 敏感性路径分开；后者并非权威复权。未计入现金股息或送转股份；5项行动歧义、8项非零 pre_close 差异、UNSET 容忍度/源舍入政策均保持。源单位、来源修订以及 factor 比值尺度会影响金额和敏感性，不能据此推断现金权益或总回报。','', '逐场景前缀60/120/240期重复回放并扰动未来尾部，信号、成交和权益前缀保持一致；同 bar 成交/未来价格窗口/账本差异为0。此项证明计算顺序，没有证明历史 available_at。','', '输出含信号、假设成交、逐日持仓、逐日权益、回撤、换手、费用/行动敏感性、未知可交易性登记、逐行来源指纹/原始hash与版本清单。正式 price / fundamental PIT backtest 均 BLOCKED；真实 Snapshot B 与 Forward Paper 尚未运行，实际天数0；30项实际账户参数UNSET_REQUIRED。','', '## 版本绑定','', '```json',canonical(binding).decode(),'```','', '任何前驱/来源原始字节、代码、规则、合同、cutoff、namespace 或私有路径替换均使结果失效。此报告不得进入正式 ResearchCard / Signal / Approval / Order / cloud 路径。']
    blobs['Diagnostic-Backtest-Report.md']=('\n'.join(lines)+'\n').encode()
    return bodies,blobs
