"""Offline, bounded registered search. No capture or credentials. Single low-priority worker."""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal as D
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import argparse, gzip, hashlib, json, os, time
from experiments.account20k_history_v1 import engine
from tools.long_forward import history_v2
from experiments.account20k_history_v1.benchmarks import build_benchmarks, yearly
from tools.v3_review.performance import derive_performance

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT.parent/'.p1b-archives/account20k-history-20261020-v2'
BASE=ROOT.parent/'.p1b-archives/long-forward-20261015/runs/LF5Y-20261015-RAW-V2-03'
REG=ROOT/'experiments/account20k_history_v1/Registration.json'
def read(p):return json.loads(p.read_text())
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
 p.chmod(0o600)
def zipped(p,x):
 with p.open('xb') as f:
  with gzip.GzipFile(fileobj=f,mode='wb',mtime=0) as g:g.write(json.dumps(x,ensure_ascii=False,separators=(',',':')).encode())
 p.chmod(0o600)
def unzipped(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def registration():
 r=read(REG)
 if r!=read(ARCHIVE/'Registration.json'):raise ValueError('REGISTRATION_CHANGED')
 return r
def check_code():
 for path,h in read(ARCHIVE/'CodeFreeze.json')['files'].items():
  if sha(ROOT/path)!=h:raise ValueError('CODE_CHANGED:'+path)
def source():
 pins=read(ARCHIVE/'Preservation-Before.json')['baseline']
 for path,h in pins.items():
  if sha(Path(path))!=h:raise ValueError('ORIGINAL_BASELINE_CHANGED')
 c=read(BASE/'Case.json');r=read(BASE/'Run.json')
 proof=history_v2.verify_provenance(c,Path(r['capture_dir']))
 return c,proof
def derive(base,config,window,bps,at,omit=None,capital=None,original_fees=False):
 reg=registration();c=deepcopy(base);p=deepcopy(history_v2.protocol())
 p.update(strategy_id=reg['strategy_id'],namespace=reg['namespace'],frozen_at=reg['frozen_at'],method_ref=sha(REG),rules_hash=engine.digest(engine.RULES),parameters=config['parameters'],allowed_parameters=[x['parameters'] for x in reg['configs']])
 p['data_use']={'optimization_allowed':True,'classification':reg['classification']}
 if window!='full':p['target_window'].update(reg['windows'][window])
 p['initial_cash_cents']=capital or reg['initial_cash_cents']
 target=p['target_window'];end=target['end']
 for profile in p['fee_schedule']:
  profile['slippage_bps']=bps
  if not original_fees:profile.update(version='ACCOUNT20K_'+profile['effective_from'],commission_rate='0.00025',minimum_commission_cents=500,exchange_included=True,other_included=False)
 if omit:
  if omit not in p['members']:raise ValueError('OMISSION_NOT_IN_FIXED_SCOPE')
  p['members']={s:g for s,g in p['members'].items() if s!=omit}
  c['universe']=[m for m in c['universe'] if m['symbol']!=omit]
  c['bars']=[b for b in c['bars'] if b['symbol']!=omit]
  c['actions']=[a for a in c['actions'] if a['symbol']!=omit]
 c.update(initial_cash_cents=p['initial_cash_cents'],strategy_id=p['strategy_id'],namespace=p['namespace'],protocol_ref=engine.digest(p),method_ref=p['method_ref'],rules=deepcopy(engine.RULES),rules_hash=p['rules_hash'],parameters=deepcopy(config['parameters']),fee_schedule=deepcopy(p['fee_schedule']),run_at=at,run_id=f"A20-{config['id']}-{window}-S{bps}"+("-without-"+omit if omit else ""))
 c['calendar']=[x for x in c['calendar'] if x['date']<=end]
 c['calendar_coverage']['days']=[x for x in c['calendar_coverage']['days'] if x['date']<=end];c['calendar_coverage']['end']=end
 c['bars']=[x for x in c['bars'] if x['session']<=end]
 c['actions']=[x for x in c['actions'] if x['ex_date']<=end]
 active=[x['date'] for x in c['calendar'] if x['date']>=target['start']]
 c['window']={'first_session':active[0],'last_session':active[-1]}
 return c,p
def guard():
 # Offline calculation yields the entire evening priority window to Forward.
 while True:
  now=datetime.now(ZoneInfo('Asia/Shanghai'))
  if not ((18,0)<=(now.hour,now.minute)<(19,30)):break
  time.sleep(30)
 check_code()
def verifier(base,config,window,bps,at,proof,omit=None,capital=None,original_fees=False):
 def verify(case):
  expected,_=derive(base,config,window,bps,at,omit,capital,original_fees)
  if expected!=case:raise ValueError('DERIVED_CASE_REPLAY_MISMATCH')
  return dict(verified=True,case_hash=engine.digest(case),receipt_hash=engine.digest({'upstream':proof,'source_case':engine.digest(base),'registration':sha(REG),'derived_case':engine.digest(case)}),purpose='LOCAL_HISTORICAL_DIAGNOSTIC')
 return verify
def summary(c,r):
 rows=r['daily'];valid=r['status'] in ('SIMULATED_TRADES','RUN_NO_TRADES') and r['engine_called'] and not r['errors']
 if valid:
  for x in rows:
   if x['nav_cents']!=x['cash_cents']+x['exposure_cents']+x['receivable_cents']:raise ValueError('NAV_RECONCILIATION')
  cash=c['initial_cash_cents']
  for x in r['ledger']:
   if x['cash_before_cents']!=cash or x['cash_after_cents']!=cash+x['cash_delta_cents']:raise ValueError('LEDGER_RECONCILIATION')
   cash=x['cash_after_cents']
  if cash!=r['final_cash_cents']:raise ValueError('FINAL_CASH')
 navmean=sum(D(x['nav_cents']) for x in rows)/len(rows) if rows else None
 return dict(run_id=c['run_id'],parameters=c['parameters'],window=c['window'],status=r['status'],valid=valid,engine_called=r['engine_called'],errors=r['errors'],sessions=len(rows),net_return=r['net_return'],max_drawdown=r['maximum_drawdown'],average_exposure=str(sum(D(x['exposure_cents'])/x['nav_cents'] for x in rows)/len(rows)) if rows else None,turnover=str(sum(x['fees']['notional_cents'] for x in r['fills'])/navmean) if navmean else None,turnover_definition='sum_buy_and_sell_executed_notional/mean_daily_NAV',fees_cents=r.get('total_fee_cents'),slippage_cents=r.get('total_slippage_cents'),filled_orders=len(r['fills']),complete_trades=r['complete_trades'],unfilled_orders=len(r['unfilled']),terminal_cash_cents=r.get('final_cash_cents'),terminal_positions=r.get('positions'),terminal_receivables=r.get('receivables'),dividend_cents=sum(x['cash_delta_cents'] for x in r['ledger'] if x['kind']=='DIVIDEND_PAYMENT'),yearly=yearly(rows,c['initial_cash_cents']) if valid else [],equity_hash=engine.digest(rows),result_hash=r['content_hash'],cost_label='SIMULATED_COSTS')
def trial(base,proof,cfg,win,bps,omit=None):
 guard();folder=ARCHIVE/'trials'/(f"{cfg['id']}-{win}-S{bps}"+("-without-"+omit if omit else ""))
 if (folder/'Manifest.json').exists():
  m=read(folder/'Manifest.json')
  for n,h in m['files'].items():
   if sha(folder/n)!=h:raise ValueError('TRIAL_PIN_CHANGED')
  return read(folder/'Summary.json')
 folder.mkdir(parents=True,exist_ok=False);at=stamp();c,p=derive(base,cfg,win,bps,at,omit)
 write(folder/'Inputs.json',dict(at=at,config=cfg,window=win,slippage_bps=bps,omitted_symbol=omit,case_hash=engine.digest(c),protocol_hash=engine.digest(p),source_case_hash=engine.digest(base),registration_hash=sha(REG),code_freeze_hash=sha(ARCHIVE/'CodeFreeze.json')))
 result=engine.run_diagnostic(c,verifier(base,cfg,win,bps,at,proof,omit),p)
 zipped(folder/'EngineResult.json.gz',result);s=summary(c,result);write(folder/'Summary.json',s)
 write(folder/'Manifest.json',dict(recorded_at=stamp(),files={f.name:sha(f) for f in folder.iterdir() if f.is_file()}))
 print(json.dumps({'trial':folder.name,'status':s['status'],'return':s['net_return']},ensure_ascii=False),flush=True)
 return s
def equivalence(base,proof,reg):
 cfg=next(x for x in reg['configs'] if x['id']==reg['baseline_id']);at=stamp()
 c,p=derive(base,cfg,'full','10',at,capital=10000000,original_fees=True)
 new=engine.run_diagnostic(c,verifier(base,cfg,'full','10',at,proof,capital=10000000,original_fees=True),p);old=read(BASE/'EngineResult.json')
 allowed={'version','namespace','strategy_id','run_id','input_hash','provenance_receipt','content_hash'}
 differences=[k for k in set(old)|set(new) if k not in allowed and old.get(k)!=new.get(k)]
 report=dict(passed=not differences,differences=differences,allowed_metadata_changes=sorted(allowed),original_result_hash=sha(BASE/'EngineResult.json'),new_result_hash=new['content_hash'],recorded_at=stamp(),scope='100k originalfee economic equivalence before 20k adaptation')
 path=ARCHIVE/'Equivalence.json'
 if not path.exists():write(path,report);zipped(ARCHIVE/'EquivalenceEngineResult.json.gz',new)
 if differences:raise ValueError('BASELINE_ECONOMIC_MISMATCH:'+','.join(differences))
def neighbors(cfg,configs):
 keys=list(cfg['parameters']);grid={k:sorted({x['parameters'][k] for x in configs}) for k in keys}
 return [x['id'] for x in configs if sum(x['parameters'][k]!=cfg['parameters'][k] for k in keys)==1 and all(abs(grid[k].index(x['parameters'][k])-grid[k].index(cfg['parameters'][k]))<=1 for k in keys)]
def lock_candidates(reg,table):
 from statistics import median
 lookup={(r['config_id'],r['partition'],r['bps']):r for r in table};base=reg['baseline_id'];qual=[];details=[]
 for cfg in reg['configs']:
  cid=cfg['id'];s=lookup[cid,'selection','10'];b=lookup[base,'selection','10'];dev=lookup[cid,'development','10'];bd=lookup[base,'development','10'];stress=lookup[cid,'selection','30'];bs=lookup[base,'selection','30'];ns=neighbors(cfg,reg['configs']);nr=[lookup[n,'selection','10'] for n in ns]
  valid=all(lookup[cid,w,bp]['valid'] for w in ('development','selection') for bp in ('10','30'))
  vals=[D(x['net_return']) for x in nr if x['valid']];mid=median(vals) if vals else None
  checks={'valid':valid,'selection':valid and D(s['net_return'])>D(b['net_return']) and D(s['max_drawdown'])<=D(b['max_drawdown']),'development':valid and D(dev['net_return'])>=D(bd['net_return'])-D('.05') and D(dev['max_drawdown'])<=D(bd['max_drawdown'])+D('.05'),'stress':valid and D(stress['net_return'])>D(bs['net_return']) and D(stress['max_drawdown'])<=D(bs['max_drawdown']),'stable':valid and len(vals)==len(ns) and mid>D(b['net_return']) and sum(v>D(b['net_return']) for v in vals)*2>=len(vals) and D(s['net_return'])-mid<=D('.05')}
  if all(checks.values()):qual.append(cid)
  details.append(dict(id=cid,checks=checks,neighbor_ids=ns,neighbor_median_return=str(mid) if mid is not None else None,neighbor_positive_excess_count=sum(v>D(b['net_return']) for v in vals)))
 def order(ids):
  result=[];remaining=list(ids)
  while remaining:
   best=max(D(lookup[i,'selection','10']['net_return']) for i in remaining)
   near=[i for i in remaining if D(lookup[i,'selection','10']['net_return'])>=best-D('.0025')]
   chosen=min(near,key=lambda i:(D(lookup[i,'selection','10']['max_drawdown']),D(lookup[i,'selection','10']['turnover']),i));result.append(chosen);remaining.remove(chosen)
  return result
 ranked=order(qual);refs=sorted([c['id'] for c in reg['configs'] if c['id']!=base and lookup[c['id'],'selection','10']['valid']],key=lambda i:(-D(lookup[i,'selection','10']['net_return']),i))
 locked=ranked[:2]
 if locked:
  if refs and refs[0] not in locked:locked.append(refs[0])
 else:locked=refs[:3]
 return dict(kind='LockedOptimizationCandidates',locked_at=stamp(),registration_hash=sha(REG),selection_table_hash=engine.digest(table),qualified=ranked,locked_ids=locked,roles={i:'QUALIFIED_CANDIDATE' if i in ranked else 'EXPLORATORY_RETURN_REFERENCE_NOT_RECOMMENDED' for i in locked},stability=details,check_results_seen=False,replacement_allowed=False)
def main():
 os.umask(0o077);os.nice(10);reg=registration();check_code();base,proof=source();equivalence(base,proof,reg)
 configs={c['id']:c for c in reg['configs']};fixed=[]
 for cid in reg['fixed_candidate_ids']:
  for win in ['full']+list(reg['windows']):
   for bp in ('10','30'):fixed.append(dict(trial(base,proof,configs[cid],win,bp),config_id=cid,partition=win,bps=bp))
 controls=[]
 for win in ['full']+list(reg['windows']):
  for bp in ('10','30'):
   guard();c,p=derive(base,configs[reg['baseline_id']],win,bp,stamp())
   for row in build_benchmarks(c,p):controls.append(dict(row,partition=win,bps=bp))
 if not (ARCHIVE/'FixedComparison.json').exists():write(ARCHIVE/'FixedComparison.json',dict(completed_at=stamp(),rows=fixed,controls=controls))
 table=[]
 for cfg in reg['configs']:
  for win in ('development','selection'):
   for bps in ('10','30'):
    table.append(dict(trial(base,proof,cfg,win,bps),config_id=cfg['id'],partition=win,bps=bps))
    tmp=ARCHIVE/'Progress.tmp';tmp.write_text(json.dumps(dict(completed_training_trials=len(table),total_training_trials=432,updated_at=stamp())));tmp.replace(ARCHIVE/'Progress.json')
 lockpath=ARCHIVE/'CandidateLock.json';proposed=lock_candidates(reg,table)
 proposed['fixed_candidate_check_already_exposed']=reg['fixed_candidate_ids']
 if lockpath.exists():
  lock=read(lockpath)
  if any(lock[k]!=proposed[k] for k in ('locked_ids','selection_table_hash','qualified','roles','stability')):raise ValueError('LOCK_MISMATCH')
 else:write(lockpath,proposed);lock=proposed
 allrows=list(table)
 for cid in [reg['baseline_id']]+lock['locked_ids']:
  for bps in ('10','30'):allrows.append(dict(trial(base,proof,configs[cid],'check',bps),config_id=cid,partition='check',bps=bps))
 omissions=[]
 for symbol in sorted(m['symbol'] for m in base['universe']):
  for cid in reg['fixed_candidate_ids']:
   for win in reg['windows']:
    for bp in ('10','30'):omissions.append(dict(trial(base,proof,configs[cid],win,bp,symbol),config_id=cid,partition=win,bps=bp,omitted_symbol=symbol))
 if not (ARCHIVE/'Results.json').exists():write(ARCHIVE/'Results.json',dict(kind='Account20kHistoricalResults',classification=reg['classification'],registration_hash=sha(REG),candidate_lock_hash=sha(lockpath),code_freeze_hash=sha(ARCHIVE/'CodeFreeze.json'),completed_at=stamp(),rows=allrows,fixed_rows=fixed,controls=controls,leave_one_out=omissions,search_config_count=108,training_trials=len(table),check_trials=len(allrows)-len(table),new_network_requests=0,actual_unique_trial_dirs=len(list((ARCHIVE/'trials').iterdir())),historical_dividend_tax='SIMULATED_FLAT_20_PERCENT_NOT_ACTUAL_TAX'))
 print(json.dumps({'results':str(ARCHIVE/'Results.json'),'locked':lock['locked_ids'],'qualified':lock['qualified']}),flush=True)

if __name__=='__main__':main()
