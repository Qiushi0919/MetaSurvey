"""Controlled rolling paper task. Daily capture is explicit, serial, local only.

The activated runtime is a separate pinned source snapshot. A STOP file prevents
any market request or state transition. No broker/account or old Forward use.
"""
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal
import argparse, fcntl, json, os
from tools.long_forward import run, builder, forward
from tools.long_forward.capture import capture
ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT.parent/'.p1b-archives/long-forward-20261015'
TZ=ZoneInfo('Asia/Shanghai')

def _atomic(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp')
 with tmp.open('w') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 tmp.chmod(0o600);tmp.replace(p)

def current():
 pointer=ARCHIVE/'forward/ACTIVE/CURRENT.json'
 if not pointer.exists():return None,None,None
 ref=run.read(pointer);name=ref['directory']
 if not run.NAME.fullmatch(name):raise ValueError('FORWARD_POINTER_SCOPE')
 folder=ARCHIVE/'forward'/name
 if folder.resolve()!=folder or run.sha(folder/'Bundle.json')!=ref['bundle_hash']:raise ValueError('FORWARD_POINTER_HASH')
 from tools.long_forward.verify_forward import verify_folder
 data=verify_folder(folder)
 return folder,data.get('Case.json'),data.get('State.json')

def execute(capture_dir,run_id):
 run.check_freeze()
 if (ARCHIVE/'STOP').exists():raise ValueError('OWNER_STOP_FILE_PRESENT')
 if not run.NAME.fullmatch(run_id):raise ValueError('RUN_ID')
 capture_dir=Path(capture_dir)
 if capture_dir.parent!=ARCHIVE or capture_dir.resolve()!=capture_dir:raise ValueError('CAPTURE_SCOPE')
 prior_folder,prior_case,state=current();prior_state=state
 at=run.stamp();report,case=builder.build_case(capture_dir,run_id,at,'FORWARD_A',prior_case)
 folder=ARCHIVE/'forward'/run_id;folder.mkdir(parents=True,exist_ok=False);run.write(folder/'BuildReport.json',report)
 event=dict(kind='LongForwardEvent',version='1.0.0',run_id=run_id,recorded_at=at,capture_dir=str(capture_dir),status='SOURCE_OR_INPUT_BLOCKED',errors=[],
  prior_directory=prior_folder.name if prior_folder else None,prior_bundle_hash=run.sha(prior_folder/'Bundle.json') if prior_folder else None,
  prior_case=str(prior_folder/'Case.json') if prior_case else None,prior_case_hash=run.sha(prior_folder/'Case.json') if prior_case else None,
  activation=dict(virtual_initial_cents=10000000,mode='VIRTUAL_ONLY_DAILY_OPEN_PROXY',rolling=True,old_forward_untouched=True))
 transitions=[]
 if case is not None:
  run.write(folder/'Case.json',case)
  verify=lambda c:builder.verify_provenance(c,capture_dir,prior_case)
  try:
   now=run.stamp();event['operated_at']=now;last=case['calendar'][-1]['date']
   if state and state['active_plan']:
    plan=state['active_plan']
    if last<plan['execution_session']:event['status']='WAITING_EXECUTION_SESSION'
    elif last>plan['execution_session']:event['status']='MISSED_ACTIVE_PLAN_EXPIRED';event['errors'].append({'code':'EXPLICIT_EXPIRED_PLAN_REVIEW_REQUIRED_NO_RETROACTIVE_FILL'})
    else:
     event.update(attempted_operation='settle',attempted_at=now)
     outcome=forward.settle(case,state,plan,now,builder.protocol(),verify);transitions.append(dict(operation='settle',at=now,result=outcome));state=outcome['state'];event['status']=outcome['status']
   elif state and state['last_consumed_session']!=last:
    event.update(attempted_operation='settle_mark_only',attempted_at=now)
    outcome=forward.settle(case,state,None,now,builder.protocol(),verify);transitions.append(dict(operation='settle_mark_only',at=now,result=outcome));state=outcome['state'];event['status']=outcome['status']
   if state is None or (state['active_plan'] is None and event['status'] not in ('SETTLEMENT_BLOCKED','MISSED_ACTIVE_PLAN_EXPIRED')):
    now=run.stamp();event.update(attempted_operation='prepare',attempted_at=now);outcome=forward.prepare(case,state,now,builder.protocol(),verify);transitions.append(dict(operation='prepare',at=now,result=outcome));state=outcome['state'];event['status']=outcome['status']
  except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
   completed=event['status']
   preserved=(event.get('attempted_operation')=='prepare' and completed in ('SETTLED','ALREADY_SETTLED','MISSED_NO_PLAN_MARK_ONLY','ALREADY_MARKED_MISSED'))
   event.update(status=('SETTLED_PREPARE_BLOCKED' if completed in ('SETTLED','ALREADY_SETTLED') else 'MISSED_MARK_PREPARE_BLOCKED') if preserved else 'FORWARD_BLOCKED',
                failed_operation=event.get('attempted_operation'),failed_at=event.get('attempted_at'))
   event['errors'].append({'type':type(exc).__name__,'detail':str(exc)})
   if preserved:
    # Settlement is a completed independent transition. A subsequent planning
    # failure cannot erase its fills, cash, marks or consumed-plan receipt.
    event.update(completed_transition_status=completed,completed_state_preserved=True,
                 continuation='RETRY_PREPARE_FROM_COMPLETED_STATE')
   else:state=prior_state
 if state:
  run.write(folder/'State.json',state)
  if state.get('active_plan'):run.write(folder/'Plan.json',state['active_plan'])
 if state:
  observed=[r for r in state['result']['daily'] if r.get('observation_status')=='FROZEN_PLAN_SETTLED']
  count=len(observed)
  if count in builder.protocol()['forward']['review_sessions']:
   run.write(folder/'Milestone.json',dict(kind='ForwardMilestoneReview',observed_sessions=count,recorded_at=run.stamp(),run_id=run_id,
    status='EXPLORATORY_VIRTUAL_OBSERVATION_NOT_EDGE_PROOF',state_hash=state['content_hash'],first_session=observed[0]['session'],last_session=observed[-1]['session'],
    net_return_fraction=str((Decimal(observed[-1]['nav_cents'])-10000000)/10000000),maximum_drawdown=state['runtime']['max_dd'],
    filled_orders=len(state['result']['fills']),complete_trades=state['result']['complete_trades'],errors=state['result']['errors']))
 run.write(folder/'Transitions.json',transitions);run.write(folder/'Event.json',event);run.seal(folder)
 # Failed planning retains and activates any already completed settlement.
 # A failure without a completed transition cannot replace the latest state.
 if case is not None and state is not None and event['status'] not in ('FORWARD_BLOCKED','SETTLEMENT_BLOCKED'):
  _atomic(ARCHIVE/'forward/ACTIVE/CURRENT.json',dict(directory=run_id,bundle_hash=run.sha(folder/'Bundle.json')))
 run.write(ARCHIVE/'attempts'/(run_id+'.json'),dict(directory=str(folder),status=event['status'],recorded_at=event['recorded_at'],bundle_hash=run.sha(folder/'Bundle.json')))
 return folder,event

def daily():
 run.check_freeze()
 if (ARCHIVE/'STOP').exists():return {'status':'STOPPED','market_requests':0}
 now=datetime.now(TZ);p=builder.protocol();date=now.date().isoformat()
 if date>p['forward']['fee_expiry'] or date>=p['forward']['current_owner_asserted_source_validity_end']:return {'status':'BLOCKED_POLICY_EXPIRY','market_requests':0}
 if now.hour<18:return {'status':'BEFORE_POST_CLOSE_CAPTURE','market_requests':0}
 if now.weekday()>=5:return {'status':'WEEKEND_NO_TASK','market_requests':0}
 lock=ARCHIVE/'daily.lock';lock.parent.mkdir(parents=True,exist_ok=True)
 with lock.open('a') as f:
  try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'status':'ALREADY_RUNNING','market_requests':0}
  previous,case,state=current()
  if state and case['calendar_coverage']['end']==date and state['active_plan']:return {'status':'ALREADY_PLANNED','market_requests':0}
  identifier='FORWARD-'+now.strftime('%Y%m%d-%H%M%S');end=now.strftime('%Y%m%d');future=(now.date()+timedelta(days=21)).strftime('%Y%m%d')
  folder,manifest=capture(p['forward']['warmup_start'].replace('-',''),end,'capture-'+identifier.lower(),priority='forward',future_end=future)
  target,event=execute(folder,identifier)
  return {'status':event['status'],'directory':str(target),'market_requests':len(manifest['sources'])+len(manifest.get('auxiliary_calendar',[]))}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--daily',action='store_true');p.add_argument('--capture-dir');p.add_argument('--run-id');a=p.parse_args()
 if a.daily:r=daily()
 else:
  if not a.capture_dir or not a.run_id:p.error('explicit capture-dir and run-id required')
  f,e=execute(a.capture_dir,a.run_id);r=dict(directory=str(f),status=e['status'])
 print(json.dumps(r,ensure_ascii=False))
