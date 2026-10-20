"""Deterministic performance projection. Raw historical records never published."""
from decimal import Decimal as D
from tools.param_opt import run
from tools.v3_review.performance import derive_performance

def build():
 run.check_code();reg=run.registration();data=run.read(run.ARCHIVE/'Results.json');lock=run.read(run.ARCHIVE/'CandidateLock.json')
 for name,h in run.read(run.ARCHIVE/'Preservation-Before.json')['baseline'].items():
  if run.sha(run.Path(name))!=h:raise ValueError('ORIGINAL_BASELINE_CHANGED')
 if data['registration_hash']!=run.sha(run.REG) or data['code_freeze_hash']!=run.sha(run.ARCHIVE/'CodeFreeze.json') or lock['registration_hash']!=run.sha(run.REG):raise ValueError('RESULTS_FREEZE_BINDING')
 if data['candidate_lock_hash']!=run.sha(run.ARCHIVE/'CandidateLock.json') or lock['selection_table_hash']!=run.engine.digest(data['rows'][:432]):raise ValueError('SELECTION_LOCK_BINDING')
 if len(data['rows'])!=432+2*(1+len(lock['locked_ids'])):raise ValueError('TRIAL_COUNT')
 original=run.read(run.BASE/'Case.json');rows=data['rows'];lookup={(r['config_id'],r['partition'],r['bps']):r for r in rows}
 selected=[reg['baseline_id']]+lock['locked_ids'];curves=[];contributions=[]
 for row in rows:
  folder=run.ARCHIVE/'trials'/f"{row['config_id']}-{row['partition']}-S{row['bps']}";manifest=run.read(folder/'Manifest.json')
  for name,h in manifest['files'].items():
   if run.sha(folder/name)!=h:raise ValueError('TRIAL_HASH_MISMATCH')
  s=run.read(folder/'Summary.json')
  if any(row[k]!=v for k,v in s.items()):raise ValueError('RESULTS_SUMMARY_MISMATCH')
  inputs=run.read(folder/'Inputs.json')
  if inputs['registration_hash']!=run.sha(run.REG) or inputs['code_freeze_hash']!=run.sha(run.ARCHIVE/'CodeFreeze.json'):raise ValueError('TRIAL_FREEZE_MISMATCH')
  if row['partition']=='check' and inputs['at']<=lock['locked_at']:raise ValueError('CHECK_BEFORE_LOCK')
  if row['config_id'] in selected:
   c,p=run.derive(original,inputs['config'],inputs['window'],inputs['slippage_bps'],inputs['at']);r=run.unzipped(folder/'EngineResult.json.gz')
   if run.engine.digest(c)!=inputs['case_hash'] or r['input_hash']!=inputs['case_hash'] or r['content_hash']!=run.engine.digest({k:v for k,v in r.items() if k!='content_hash'}):raise ValueError('RESULT_CASE_BINDING')
   if run.summary(c,r)!=s:raise ValueError('SUMMARY_RECOMPUTATION')
   perf=derive_performance(c,r)
   curves.append(dict(id=row['config_id'],partition=row['partition'],bps=row['bps'],run_id=row['run_id'],points=[{'session':x['session'],'nav_cents':x['nav_cents'],'drawdown_fraction':x['drawdown_fraction'],'exposure_fraction':x['exposure_fraction']} for x in perf['nav_series']]))
   contributions.append(dict(id=row['config_id'],partition=row['partition'],bps=row['bps'],run_id=row['run_id'],companies=perf['symbol_contributions'],groups=perf['group_contributions']))
 recommendation=[];checks=[]
 for cid in lock['locked_ids']:
  guards={}
  for bp in ('10','30'):
   s=lookup[cid,'check',bp];b=lookup[reg['baseline_id'],'check',bp]
   guards[bp]=s['valid'] and D(s['net_return'])>D(b['net_return']) and D(s['max_drawdown'])<=D(b['max_drawdown'])
  eligible=cid in lock['qualified'] and all(guards.values())
  if eligible:recommendation.append(cid)
  checks.append(dict(id=cid,qualified_before_check=cid in lock['qualified'],check_guards=guards,recommended=eligible))
 comparisons=[{k:v for k,v in r.items() if k not in ('terminal_positions','terminal_receivables')}|{'id':r['config_id'],'terminal_position_count':len(r['terminal_positions']),'terminal_receivable_cents':sum(x['net_cents'] for x in r['terminal_receivables'].values()),'terminal_value_realized':not r['terminal_positions'] and not r['terminal_receivables']} for r in rows if r['config_id'] in selected]
 for c in data['controls']:
  avg=sum(D(p['nav_cents']) for p in c['nav_series'])/len(c['nav_series'])
  comparisons.append(dict(id=c['id'],run_id=c['run_id'],partition=c['partition'],bps=c['bps'],status=c['status'],net_return=c['net_return'],max_drawdown=c['max_drawdown'],average_exposure=c['average_exposure_fraction'],turnover=str(sum(t['notional_cents'] for t in c['trades'])/avg),fees_cents=c['fees_cents'],slippage_cents=c['slippage_cents'],dividend_cents=c['dividend_cents'],filled_orders=len(c['trades']),unfilled_orders=len(c['rejections']),complete_trades=0,terminal_cash_cents=c['terminal_cash_cents'],terminal_receivable_cents=c['terminal_receivable_cents'],terminal_position_count=len(c['terminal_positions']),terminal_value_realized=False,terminal_sale_executed=False,initial_invested_notional_cents=c['initial_invested_notional_cents'],hypothetical_terminal_sell_fees_cents=c['hypothetical_terminal_sell_fees_cents'],yearly=c['yearly']))
 table=[]
 for cfg in reg['configs']:
  table.append(dict(cfg,results=[lookup[cfg['id'],w,b] for w in ('development','selection') for b in ('10','30')],stability=next(x for x in lock['stability'] if x['id']==cfg['id']),role=lock['roles'].get(cfg['id'],'BASELINE' if cfg['id']==reg['baseline_id'] else 'NOT_SELECTED')))
 return dict(kind='ParameterOptimizationReview',version='1.0.0',experiment=reg['strategy_id'],namespace=reg['namespace'],classification=reg['classification'],registration_hash=run.sha(run.REG),code_freeze_hash=run.sha(run.ARCHIVE/'CodeFreeze.json'),results_hash=run.sha(run.ARCHIVE/'Results.json'),candidate_lock_hash=run.sha(run.ARCHIVE/'CandidateLock.json'),completed_at=data['completed_at'],baseline_id=reg['baseline_id'],baseline_equivalence=run.read(run.ARCHIVE/'Equivalence.json'),search_configs=108,training_trials=data['training_trials'],check_trials=data['check_trials'],controls_count=len(data['controls']),failed_trials=[r['run_id'] for r in rows if not r['valid']],locked_at=lock['locked_at'],locked_ids=lock['locked_ids'],qualified_before_check=lock['qualified'],recommendation=recommendation,conclusion='CANDIDATE_FOR_OWNER_FORWARD_C_REVIEW' if recommendation else 'NO_ROBUST_RECOMMENDED_IMPROVEMENT',check_guards=checks,table=table,comparisons=comparisons,curves=curves,contributions=contributions,forward_c={'status':'NOT_STARTED','candidate_ids':recommendation,'owner_approval_required':True,'inherit_A_records':False},limitations=['EXPOSED_HISTORY_NOT_UNTOUCHED_OOS','FIXED_CONTEMPORARY_NINE_NOT_MARKET_SELECTION','RECONSTRUCTED_HISTORY_NOT_FORMAL_PIT','SIMULATED_COSTS_DAILY_OPEN_PROXY','PRICE_VOLUME_PARAMETERS_NOT_FULL_RESEARCH','No statistical multiple-testing adjustment: no significant superiority claim','Turnover=sum BUY+SELL notional/mean daily NAV. Registration near_tie says one-way in error; all calculations and ranks consistently use this two-sided definition.','Stress slippage can change fills, quantity and paths; stress return is not guaranteed monotonically worse.'])

if __name__=='__main__':
 result=build();run.write(run.ARCHIVE/'Review.json',result)
 run.write(run.ROOT/'docs/param-opt-v1/Results.json',result)
 print(result['conclusion'],result['recommendation'])
