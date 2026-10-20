"""Append-only checkpoints, receipts and config/code integrity; no raw publication."""
from copy import deepcopy
from pathlib import Path
import hashlib, json, os
from .probe import ROOT, ARCHIVE, now, save

def digest(value):
    return 'sha256:'+hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def filehash(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())
def config(): return read(ROOT/'experiments/account20k_v1/Config.json')
def verify_freeze():
    frozen=read(ARCHIVE/'Deployment-V2.json')
    for p,h in frozen['files'].items():
        f=Path(p)
        if f.is_symlink() or filehash(f)!=h: raise ValueError('RUNTIME_FILE_CHANGED:'+f.name)
    if (ARCHIVE/'STOP').exists(): raise ValueError('OWNER_STOP')
    return frozen
def state():
    pointer=ARCHIVE/'CURRENT.json'
    if not pointer.exists(): return read(ARCHIVE/'Initial-State.json')
    ref=read(pointer);path=ARCHIVE/'checkpoints'/ref['file']
    if path.parent!=ARCHIVE/'checkpoints' or path.resolve()!=path or path.is_symlink():
        raise ValueError('STATE_PATH')
    if filehash(path)!=ref['hash']: raise ValueError('STATE_HASH')
    value=read(path);h=value.pop('content_hash')
    if digest(value)!=h: raise ValueError('STATE_CONTENT_HASH')
    value['content_hash']=h
    if value['config_hash']!=filehash(ROOT/'experiments/account20k_v1/Config.json'):
        raise ValueError('STATE_CONFIG_HASH')
    cash=2000000
    for i,row in enumerate(value['ledger']):
        if row['sequence']!=i or row['before_cents']!=cash: raise ValueError('LEDGER_SEQUENCE')
        expected=digest(value['ledger'][i-1]) if i else digest({'initial_cash_cents':2000000})
        if row['previous_hash']!=expected: raise ValueError('LEDGER_HASH_CHAIN')
        cash+=row['delta_cents']
        if cash!=row['after_cents'] or cash<0: raise ValueError('LEDGER_CASH')
    if cash!=value['cash_cents']: raise ValueError('STATE_CASH')
    prior=value.get('previous_checkpoint')
    previous_hash=value.get('previous_state_hash')
    seen=set()
    while prior:
        p=ARCHIVE/'checkpoints'/prior['file']
        if p.parent!=ARCHIVE/'checkpoints' or p.resolve()!=p or p.is_symlink() or p.name in seen:
            raise ValueError('CHECKPOINT_CHAIN_PATH')
        seen.add(p.name)
        if filehash(p)!=prior['hash']:raise ValueError('CHECKPOINT_CHAIN_FILE_HASH')
        parent=read(p);h=parent.pop('content_hash')
        if digest(parent)!=h or h!=previous_hash:raise ValueError('CHECKPOINT_CHAIN_CONTENT')
        prior=parent.get('previous_checkpoint');previous_hash=parent.get('previous_state_hash')
    if previous_hash is not None:raise ValueError('CHECKPOINT_CHAIN_ROOT')
    return value
def checkpoint(value,event):
    value=deepcopy(value)
    value['previous_state_hash']=value.pop('content_hash',None)
    value['previous_checkpoint']=read(ARCHIVE/'CURRENT.json') if (ARCHIVE/'CURRENT.json').exists() else None
    value['updated_at']=now();value['last_event']=event
    value['available_cash_cents']=value['cash_cents']-value['frozen_cash_cents']-value.get('tax_reserve_cents',0)
    if value['available_cash_cents']<0: raise ValueError('CASH_RESERVATION_UNDERFLOW')
    value['content_hash']=digest(value)
    folder=ARCHIVE/'checkpoints';folder.mkdir(exist_ok=True)
    filename=value['updated_at'].replace(':','').replace('+','_')+'.json'
    path=folder/filename;save(path,value)
    tmp=ARCHIVE/'CURRENT.tmp'
    tmp.write_text(json.dumps({'file':filename,'hash':filehash(path)}));tmp.chmod(0o600)
    os.replace(tmp,ARCHIVE/'CURRENT.json')
    return value
def event(kind,**fields):
    value={'kind':kind,'at':now(),**fields}
    folder=ARCHIVE/'events';folder.mkdir(exist_ok=True)
    name=value['at'].replace(':','').replace('+','_')+'-'+kind+'.json'
    save(folder/name,value)
    return value
def ledger(account,kind,delta,reference):
    before=account['cash_cents'];after=before+delta
    if after<0: raise ValueError('CASH_UNDERFLOW')
    row=dict(sequence=len(account['ledger']),kind=kind,at=now(),before_cents=before,
             delta_cents=delta,after_cents=after,reference=reference,
             previous_hash=digest(account['ledger'][-1]) if account['ledger'] else digest({'initial_cash_cents':2000000}))
    account['ledger'].append(row);account['cash_cents']=after
