"""Fixed whitelist projection of the new virtual account and historical review."""
from datetime import datetime,timezone
from pathlib import Path
import json

def load(reader):
    from workbench.server import ReadError,digest
    registry,source=reader.json('account20k-registry','Account20kRegistry')
    # This sealed producer uses experiment identity rather than a version field.
    # Accept that exact shape; do not relax the native Reader's version checks.
    history,hs=reader.json('account20k-history','Account20kHistoryReview',version=None)
    if history.get('experiment')!='CORE40_ACCOUNT20K_HISTORY_V1':
        raise ReadError('ACCOUNT20K_HISTORY_EXPERIMENT','account20k-history')
    if hs['sha256']!=registry['history_hash']:raise ReadError('ACCOUNT20K_HISTORY_HASH','account20k-history')
    for relative,h in registry['code_pins'].items():
        p=Path(relative)
        if p.is_absolute() or '..' in p.parts:raise ReadError('ACCOUNT20K_CODE_PATH','account20k-registry')
        raw,_=reader.read_path(reader.root/p,reader.root)
        if digest(raw)!=h:raise ReadError('ACCOUNT20K_CODE_HASH',relative)
    status,ss=reader.json('account20k-status','Account20kPublicStatus')
    if ss['sha256']!=registry['status_hash']:raise ReadError('ACCOUNT20K_STATUS_HASH','account20k-status')
    out=dict(status='PUBLIC_ARCHIVED_METADATA_ONLY',history=history,account=status,source=source)
    archive=reader.root.parent/'.p1b-archives/forward-c20k-20261020'
    if archive.exists():
        if archive.resolve()!=archive or archive.is_symlink():raise ReadError('ACCOUNT20K_PRIVATE_PATH','account20k-status')
        from tools.forward_c20k import store
        if archive!=store.ARCHIVE:raise ReadError('ACCOUNT20K_ARCHIVE_MISMATCH','account20k-status')
        account=store.state()
        heartbeat_path=archive/'Heartbeat.json'
        heartbeat=store.read(heartbeat_path) if heartbeat_path.exists() else {'status':'NOT_TRIGGERED','at':None}
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(heartbeat['at'])).total_seconds() if heartbeat['at'] else None
        out.update(status='LOCAL_STATE_HASH_CHAIN_VERIFIED',account=account,heartbeat=heartbeat,
            heartbeat_age_seconds=age,task_live=bool(age is not None and 0<=age<=600),
            task_state='STOPPED' if (archive/'STOP').exists() else 'OFFLINE_OR_ASLEEP' if age is None or age>600 else heartbeat['status'],
            read_at=datetime.now(timezone.utc).isoformat())
        deploy=archive/'Deployment-V2.json'
        if deploy.exists():
            dep=store.read(deploy)
            for p,h in dep['files'].items():
                if store.filehash(Path(p))!=h:raise ReadError('ACCOUNT20K_FROZEN_RUNTIME_CHANGED','account20k-status')
            out['runtime_binding']={'version':dep['version'],'deployed_at':dep['deployed_at'],'hash':store.filehash(deploy)}
    return out
