"""Public derived-only projection. No original market rows or credentials."""
from collections import Counter,defaultdict
from decimal import Decimal as D
import csv
from tools.account20k_history import run

def project_summary(row):
 return {k:v for k,v in row.items() if k not in ('terminal_positions','terminal_receivables')}|dict(terminal_position_count=len(row['terminal_positions']),terminal_receivable_cents=sum(x['net_cents'] for x in row['terminal_receivables'].values()))

def build():
 run.check_code();reg=run.registration();data=run.read(run.ARCHIVE/'Results.json');lock=run.read(run.ARCHIVE/'CandidateLock.json');base,proof=run.source()
 if data['registration_hash']!=run.sha(run.REG) or data['code_freeze_hash']!=run.sha(run.ARCHIVE/'CodeFreeze.json') or data['candidate_lock_hash']!=run.sha(run.ARCHIVE/'CandidateLock.json'):raise ValueError('RESULTS_BINDING')
 if lock['selection_table_hash']!=run.engine.digest(data['rows'][:432]):raise ValueError('TRAINING_LOCK')
 table=[];curves=[];details=[]
 selected=set(reg['fixed_candidate_ids']+lock['locked_ids'])
 for row in data['fixed_rows']+data['rows']+data['leave_one_out']:
  omit=row.get('omitted_symbol');folder=run.ARCHIVE/'trials'/(f"{row['config_id']}-{row['partition']}-S{row['bps']}"+('-without-'+omit if omit else ''))
  for name,h in run.read(folder/'Manifest.json')['files'].items():
   if run.sha(folder/name)!=h:raise ValueError('TRIAL_PIN_CHANGED')
  s=run.read(folder/'Summary.json')
  if any(row[k]!=v for k,v in s.items()):raise ValueError('SUMMARY_CHANGED')
 # Derive readable curves and company contribution only for fixed and locked nonomitted results.
 seen=set()
 for row in data['fixed_rows']+data['rows']:
  cid,win,bp=row['config_id'],row['partition'],row['bps'];key=(cid,win,bp)
  if key in seen or cid not in selected:continue
  seen.add(key);folder=run.ARCHIVE/'trials'/f'{cid}-{win}-S{bp}';x=run.read(folder/'Inputs.json');c,p=run.derive(base,x['config'],win,bp,x['at']);r=run.unzipped(folder/'EngineResult.json.gz')
  if run.engine.digest(c)!=x['case_hash'] or r['input_hash']!=x['case_hash'] or r['content_hash']!=run.engine.digest({k:v for k,v in r.items() if k!='content_hash'}):raise ValueError('CASE_RESULT_BINDING')
  if run.summary(c,r)!=run.read(folder/'Summary.json'):raise ValueError('SUMMARY_RECALCULATION')
  peak=reg['initial_cash_cents'];points=[]
  for d in r['daily']:
   peak=max(peak,d['nav_cents']);points.append(dict(session=d['session'],nav_cents=d['nav_cents'],drawdown_fraction=str(D(peak-d['nav_cents'])/peak),exposure_fraction=str(D(d['exposure_cents'])/d['nav_cents'])))
  curves.append(dict(id=cid,partition=win,bps=bp,run_id=r['run_id'],points=points))
  contrib=defaultdict(int)
  for l in r['ledger']:
   if l.get('symbol'):contrib[l['symbol']]+=l['cash_delta_cents']
  for pos in r['daily'][-1]['positions']:contrib[pos['symbol']]+=pos['market_value_cents']
  for rec in r['receivables'].values():contrib[rec['symbol']]+=rec['net_cents']
  if sum(contrib.values())!=r['daily'][-1]['nav_cents']-reg['initial_cash_cents']:raise ValueError('CONTRIBUTION_RECONCILIATION')
  reasons=dict(Counter(u['reason'] for u in r['unfilled']))
  details.append(dict(id=cid,partition=win,bps=bp,unfilled_reasons=reasons,company_net_contributions_cents=dict(contrib),commission_cents=sum(f['fees']['commission_cents'] for f in r['fills']),minimum_commission_uplift_cents=sum(f['fees']['minimum_commission_uplift_cents'] for f in r['fills']),orders_at_minimum=sum(f['fees']['commission_cents']==500 for f in r['fills']),total_orders=len(r['fills'])))
 lookup={(r['config_id'],r['partition'],r['bps']):r for r in data['rows']};recommend=[]
 for cid in lock['locked_ids']:
  if cid in lock['qualified'] and all(lookup[cid,'check',b]['valid'] and D(lookup[cid,'check',b]['net_return'])>D(lookup[reg['baseline_id'],'check',b]['net_return']) and D(lookup[cid,'check',b]['max_drawdown'])<=D(lookup[reg['baseline_id'],'check',b]['max_drawdown']) for b in ('10','30')):recommend.append(cid)
 controls=[]
 for c in data['controls']:
  controls.append({k:v for k,v in c.items() if k not in ('trades','ledger','nav_series','actions','partial_holdings','terminal_positions')}|dict(terminal_position_count=len(c['terminal_positions']),filled_orders=len(c['trades']),turnover=str(D(sum(t['notional_cents'] for t in c['trades']))/(sum(D(p['nav_cents']) for p in c['nav_series'])/len(c['nav_series'])))))
  curves.append(dict(id=c['id'],partition=c['partition'],bps=c['bps'],run_id=c['run_id'],points=[{k:p[k] for k in ('session','nav_cents','drawdown_fraction','exposure_fraction')} for p in c['nav_series']]))
 return dict(kind='Account20kHistoryReview',experiment=reg['strategy_id'],classification=reg['classification'],initial_cash_cents=reg['initial_cash_cents'],completed_at=data['completed_at'],registration_hash=run.sha(run.REG),code_freeze_hash=run.sha(run.ARCHIVE/'CodeFreeze.json'),results_hash=run.sha(run.ARCHIVE/'Results.json'),candidate_lock_hash=run.sha(run.ARCHIVE/'CandidateLock.json'),search_configs=108,training_trials=432,actual_unique_trial_dirs=data['actual_unique_trial_dirs'],controls_count=len(controls),leave_one_out_count=len(data['leave_one_out']),locked_ids=lock['locked_ids'],qualified=lock['qualified'],recommendation= recommend,forward_strategy_replacement_authorized=False,fixed_comparisons=[project_summary(r) for r in data['fixed_rows']],rows=[project_summary(r) for r in data['rows']],leave_one_out=[project_summary(r) for r in data['leave_one_out']],controls=controls,curves=curves,details=details,stability=lock['stability'],failed_trials=[r['run_id'] for r in data['rows']+data['fixed_rows']+data['leave_one_out'] if not r['valid']],limitations=['EXPOSED_HISTORY_EXPLORATORY_OPTIMIZATION','FIXED_CONTEMPORARY_NINE','RECONSTRUCTED_NOT_PIT','SIMULATED_COSTS_DAILY_PROXY','HISTORICAL_FLAT20_DIVIDEND_TAX_NOT_ACTUAL_TAX','20k commission includes handling/regulatory by Owner simulated assumption, not contract-note verified','Prior invalidated epoch preserved: inherited capital metadata corrected, no parameter/selection change','Fixed three candidates checked before new search; lock algorithm exclusively uses development/selection; all history exposed','No statistical multiple-testing correction or evidence of actual investment effectiveness'])

def public_projection(result):
 from copy import deepcopy
 from math import ceil
 out=deepcopy(result)
 for curve in out['curves']:
  points=curve['points'];step=max(1,ceil(len(points)/240));indices=set(range(0,len(points),step))
  if points:
   indices.update((len(points)-1,max(range(len(points)),key=lambda i:points[i]['nav_cents']),max(range(len(points)),key=lambda i:D(points[i]['drawdown_fraction']))))
  curve.update(source_point_count=len(points),source_points_hash=run.engine.digest(points),sampling='VISUALIZATION_ONLY_EVERY_N_PLUS_FINAL_GLOBAL_NAV_PEAK_AND_MAX_DRAWDOWN',sampling_step=step,points=[points[i] for i in sorted(indices)])
 out['visualization_note']='Chart points sampled for public file size; every value is an actual computed day. Full continuous daily series in private sealed EngineResult and controls. Metrics use all days, not sampled curves.'
 return out

def main():
 result=build();run.write(run.ARCHIVE/'Review.json',result);
 public=run.ROOT/'docs/account20k-history/Results.json'
 with public.open('x') as f:run.json.dump(public_projection(result),f,ensure_ascii=False,separators=(',',':'));f.write('\n')
 path=run.ROOT/'docs/account20k-history/All-108-Results.csv'
 with path.open('x') as f:
  cols=['config_id','partition','bps','net_return','max_drawdown','average_exposure','turnover','fees_cents','filled_orders','unfilled_orders','status'];w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
  for row in result['rows']:w.writerow({c:row[c] for c in cols})
 print('recommendation',result['recommendation'])
if __name__=='__main__':main()
