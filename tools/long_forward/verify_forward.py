"""Rebuild and replay immutable Forward bundles, without capture or credentials.

Trust comes from the caller's active Bundle hash + frozen code pins. Each prior
bundle is scope constrained and hash bound; a self-rehashed State alone is never
accepted. Original failed attempts are checked by replaying their failure clock.
"""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from tools.long_forward import builder,forward,run

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT.parent/'.p1b-archives/long-forward-20261015'

class VerificationError(ValueError):pass

def _require(ok,label):
    if not ok:raise VerificationError(label)

def _folder(path):
    path=Path(path)
    _require(path.parent==ARCHIVE/'forward' and run.NAME.fullmatch(path.name) and path.name!='ACTIVE', 'FORWARD_VERIFY_FOLDER_SCOPE')
    _require(path.resolve()==path and not path.is_symlink(),'FORWARD_VERIFY_FOLDER_ALIAS')
    manifest=path/'Bundle.json'
    _require(manifest.is_file() and not manifest.is_symlink(),'FORWARD_VERIFY_MANIFEST_ALIAS')
    return path

def _clock(at,event,previous=None):
    from experiments.long_forward_v1.engine import instant
    value=instant(at)
    _require(value>=instant(event['recorded_at']),'TRANSITION_BEFORE_CAPTURE_BUILD')
    _require(value<=datetime.now(timezone.utc),'TRANSITION_CLOCK_IN_FUTURE')
    if previous is not None:_require(value>=instant(previous),'TRANSITION_CLOCK_REVERSED')
    return at

def verify_folder(folder):
    # Import locally: reporting.forward uses this module, while bundle is the
    # low-level file/code verifier and does not call forward projections.
    from tools.long_forward.reporting import bundle
    folder=_folder(folder);chain=[];seen=set();current=folder
    while True:
        current=_folder(current)
        _require(current not in seen and len(seen)<4096,'FORWARD_PRIOR_CYCLE_OR_DEPTH')
        seen.add(current);data=bundle(current);event=data['Event.json']
        _require(event['run_id']==current.name,'FORWARD_EVENT_RUN_ID')
        chain.append(current)
        name=event.get('prior_directory')
        if name is None:
            _require(all(event.get(k) is None for k in ('prior_bundle_hash','prior_case','prior_case_hash')),'FORWARD_PRIOR_NULL_FIELDS')
            break
        _require(type(name) is str and run.NAME.fullmatch(name) and name!='ACTIVE','FORWARD_PRIOR_NAME')
        prior=_folder(ARCHIVE/'forward'/name)
        _require(run.sha(prior/'Bundle.json')==event['prior_bundle_hash'],'FORWARD_PRIOR_BUNDLE_HASH')
        prior_data=bundle(prior)
        _require(prior_data['Event.json']['status'] not in ('SOURCE_OR_INPUT_BLOCKED','FORWARD_BLOCKED','SETTLEMENT_BLOCKED'),'PRIOR_FAILURE_CANNOT_BE_ACTIVE_STATE')
        if prior_data.get('Case.json') is not None:
            _require(event.get('prior_case')==str(prior/'Case.json') and event.get('prior_case_hash')==run.sha(prior/'Case.json'),'FORWARD_PRIOR_CASE_BINDING')
        else:_require(event.get('prior_case') is None and event.get('prior_case_hash') is None,'FORWARD_PRIOR_CASE_NULL')
        current=prior
    previous_state=None;previous_case=None;last_data=None
    for path in reversed(chain):
        data=bundle(path);event=data['Event.json'];case=data.get('Case.json');transitions=data['Transitions.json']
        _require(type(transitions) is list,'TRANSITIONS_ARRAY_REQUIRED')
        capture=Path(event['capture_dir'])
        _require(capture.parent==ARCHIVE and capture.name.startswith('capture-') and capture.resolve()==capture and not capture.is_symlink(),'FORWARD_CAPTURE_SCOPE')
        report,repeated=builder.build_case(capture,event['run_id'],event['recorded_at'],'FORWARD_A',previous_case)
        _require(report==data['BuildReport.json'] and repeated==case,'FORWARD_INPUT_REBUILD_MISMATCH')
        if case is not None:
            _require(case['run_id']==event['run_id'] and case['mode']=='FORWARD_A' and case['run_at']==event['recorded_at'],'FORWARD_CASE_EVENT_IDENTITY')
        state=deepcopy(previous_state);prior_state=deepcopy(previous_state);cursor=0;clock=None;status='SOURCE_OR_INPUT_BLOCKED';errors=[]
        def invoke(operation):
            nonlocal state,cursor,clock
            failed=event['status'] in ('FORWARD_BLOCKED','SETTLED_PREPARE_BLOCKED','MISSED_MARK_PREPARE_BLOCKED') and cursor==len(transitions)
            if failed:
                _require(event.get('failed_operation')==operation and bool(event.get('failed_at')),'FAILURE_OPERATION_CLOCK_REQUIRED')
                at=event['failed_at']
            else:
                _require(cursor<len(transitions),'MISSING_REQUIRED_TRANSITION')
                transition=transitions[cursor]
                _require(transition.get('operation')==operation,'TRANSITION_OPERATION_ORDER')
                at=transition['at']
            clock=_clock(at,event,clock)
            verify=lambda c:builder.verify_provenance(c,capture,previous_case)
            if operation=='prepare':outcome=forward.prepare(case,state,at,builder.protocol(),verify)
            elif operation=='settle':outcome=forward.settle(case,state,state['active_plan'],at,builder.protocol(),verify)
            else:outcome=forward.settle(case,state,None,at,builder.protocol(),verify)
            _require(not failed,'CLAIMED_FAILURE_DID_NOT_OCCUR')
            _require(outcome==transitions[cursor]['result'],'TRANSITION_REPLAY_MISMATCH')
            cursor+=1;state=outcome['state'];return outcome['status']
        if case is not None:
            try:
                last=case['calendar'][-1]['date']
                if state and state['active_plan']:
                    plan=state['active_plan']
                    if last<plan['execution_session']:status='WAITING_EXECUTION_SESSION'
                    elif last>plan['execution_session']:
                        status='MISSED_ACTIVE_PLAN_EXPIRED';errors.append({'code':'EXPLICIT_EXPIRED_PLAN_REVIEW_REQUIRED_NO_RETROACTIVE_FILL'})
                    else:status=invoke('settle')
                elif state and state['last_consumed_session']!=last:status=invoke('settle_mark_only')
                if state is None or (state['active_plan'] is None and status not in ('SETTLEMENT_BLOCKED','MISSED_ACTIVE_PLAN_EXPIRED')):
                    status=invoke('prepare')
            except VerificationError:
                raise
            except (ValueError,TypeError,KeyError,ArithmeticError) as exc:
                # Verification failures cannot masquerade as business failures.
                _require(event['status'] in ('FORWARD_BLOCKED','SETTLED_PREPARE_BLOCKED','MISSED_MARK_PREPARE_BLOCKED') and cursor==len(transitions) and event.get('failed_at')==clock,
                         'FORWARD_REPLAY_FAILURE_NOT_RECORDED:'+str(exc))
                actual={'type':type(exc).__name__,'detail':str(exc)}
                _require(event.get('errors')==[actual],'FORWARD_FAILURE_REPLAY_MISMATCH')
                completed=status
                preserved=(event.get('failed_operation')=='prepare' and completed in ('SETTLED','ALREADY_SETTLED','MISSED_NO_PLAN_MARK_ONLY','ALREADY_MARKED_MISSED'))
                if preserved:
                    _require(event.get('completed_transition_status')==completed and event.get('completed_state_preserved') is True and event.get('continuation')=='RETRY_PREPARE_FROM_COMPLETED_STATE','COMPLETED_TRANSITION_PRESERVATION_REQUIRED')
                    status='SETTLED_PREPARE_BLOCKED' if completed in ('SETTLED','ALREADY_SETTLED') else 'MISSED_MARK_PREPARE_BLOCKED'
                else:
                    _require(not event.get('completed_state_preserved'),'UNPROVEN_COMPLETED_TRANSITION')
                    status='FORWARD_BLOCKED';state=prior_state
                errors=[actual]
        _require(cursor==len(transitions),'EXTRA_TRANSITIONS')
        _require(status==event['status'] and errors==event.get('errors',[]),'FORWARD_EVENT_STATUS_OR_ERROR_MISMATCH')
        _require(state==data.get('State.json'),'FORWARD_FINAL_STATE_REPLAY_MISMATCH')
        _require((state.get('active_plan') if state else None)==data.get('Plan.json'),'FORWARD_FINAL_PLAN_REPLAY_MISMATCH')
        if state:forward._check(state,'STATE')
        previous_case=case;previous_state=state;last_data=data
    return last_data
