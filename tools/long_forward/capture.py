"""Existing endpoint only, serial bounded capture. Raw receipts never go to Git."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from contextlib import contextmanager
import argparse, fcntl, hashlib, json, os, re, time, shutil, urllib.request, urllib.error
from tools.e2e_gateway.capture import FIELDS
from backtest_5y.gateway import _credential_module, NoRedirect

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT.parent/'.p1b-archives/long-forward-20261015'
OWNER=ROOT/'docs/long-forward/Authorization.md'
CAPTURE_CODE_BYTES=Path(__file__).read_bytes()
def stamp():return datetime.now(timezone.utc).isoformat()
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):
    with p.open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
    p.chmod(0o600)

class CaptureStopped(RuntimeError):pass
def check_stop():
    if (ARCHIVE/'STOP').exists():raise CaptureStopped('OWNER_STOP_FILE_PRESENT')
def controlled_sleep(seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        check_stop();time.sleep(max(0,min(1,end-time.monotonic())))
    check_stop()

@contextmanager
def queue(priority):
    """One lock for both lanes; a waiting Forward request preempts between calls."""
    check_stop()
    q=ARCHIVE/'queue';q.mkdir(parents=True,exist_ok=True)
    marker=q/'forward-priority.json'
    if priority=='forward':marker.write_text(json.dumps({'pid':os.getpid(),'at':time.time()}))
    try:
        while priority=='history' and marker.exists():
            try:
                m=json.loads(marker.read_text());os.kill(m['pid'],0)
                if time.time()-m['at']>600:break
            except (OSError,ValueError,KeyError):break
            controlled_sleep(1)
        with (q/'gateway.lock').open('a') as f:
            while True:
                check_stop()
                try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:controlled_sleep(1)
            last=q/'last-request.json'
            if last.exists():
                delay=30-(time.time()-json.loads(last.read_text())['at'])
                if delay>0:controlled_sleep(delay)
            check_stop()
            try:yield
            finally:
                last.write_text(json.dumps({'at':time.time()}));fcntl.flock(f,fcntl.LOCK_UN)
    finally:
        if priority=='forward' and marker.exists():marker.unlink()

def capture(start,end,epoch,priority='history',future_end=None,resume=None):
    if not re.fullmatch(r'capture-[A-Za-z0-9._-]+',epoch):raise ValueError('SAFE_NEW_EPOCH_REQUIRED')
    for d in (start,end,future_end or end):datetime.strptime(d,'%Y%m%d')
    if start>end or start<'20210601':raise ValueError('REGISTERED_DATE_SCOPE')
    if priority not in ('history','forward'):raise ValueError('UNKNOWN_PRIORITY')
    protocol=json.loads((ROOT/'experiments/long_forward_v1/protocol.json').read_text())
    if priority=='history' and (start,end)!=(protocol['target_window']['warmup_start'].replace('-',''),protocol['target_window']['end'].replace('-','')):raise ValueError('REGISTERED_HISTORY_SCOPE')
    if priority=='forward':
        now=datetime.now(ZoneInfo('Asia/Shanghai'));complete=now.date() if now.hour>=18 else now.date()-timedelta(days=1)
        if start!=protocol['forward']['warmup_start'].replace('-','') or end>complete.strftime('%Y%m%d'):raise ValueError('COMPLETED_FORWARD_SCOPE')
    if future_end and (future_end<end or (datetime.strptime(future_end,'%Y%m%d')-datetime.strptime(end,'%Y%m%d')).days>35):raise ValueError('CALENDAR_LOOKAHEAD_SCOPE')
    folder=ARCHIVE/epoch;folder.mkdir(parents=True,exist_ok=False);folder.chmod(0o700)
    (folder/'Capture-Adapter.py').write_bytes(CAPTURE_CODE_BYTES);(folder/'Capture-Adapter.py').chmod(0o600)
    cfg=json.loads((ROOT/'config/provider/tushare-monthly-gateway.json').read_text());old=_credential_module()
    if cfg['endpoint']!=old.BASE_URL:raise ValueError('EXISTING_ENDPOINT_CHANGED')
    symbols=list(json.loads((ROOT/'experiments/long_forward_v1/protocol.json').read_text())['members'])
    requests=[('trade_cal',dict(exchange=e,start_date=start,end_date=end),False) for e in ('SSE','SZSE')]
    for sym in symbols:
        for api in ('stock_basic','daily','stk_limit','suspend_d','adj_factor','dividend','namechange'):
            params={'ts_code':sym}
            if api in ('daily','stk_limit','suspend_d','adj_factor'):params.update(start_date=start,end_date=end)
            requests.append((api,params,False))
    if future_end:
        requests.extend(('trade_cal',dict(exchange=e,start_date=end,end_date=future_end),True) for e in ('SSE','SZSE'))
    sources=[];aux=[]
    manifest=dict(kind='GatewayCaptureManifest',version='1.0.0',scope=dict(symbols=symbols,start_date=start,end_date=end),endpoint=old.BASE_URL,
                  connection_kind='COMPATIBLE_GATEWAY_NOT_VERIFIED_OFFICIAL_TUSHARE',capture_code_sha256='sha256:'+hashlib.sha256(CAPTURE_CODE_BYTES).hexdigest(),owner_authorization_ref=sha(OWNER),
                  provider_license_status='OWNER_AUTHORIZED_LOCAL_USE_UNVERIFIED_PROVIDER_LICENSE',started_at=stamp(),sources=sources,
                  historical_visibility_proven=False,public_raw_distribution=False,cloud_transfer=False,auxiliary_calendar=aux,priority=priority)
    if resume:
        previous=Path(resume)
        if previous.parent!=ARCHIVE or previous.resolve()!=previous:raise ValueError('RESUME_SCOPE')
        prior=json.loads((previous/'Manifest.json').read_text())
        if any(prior[k]!=manifest[k] for k in ('scope','endpoint','owner_authorization_ref')):raise ValueError('RESUME_SCOPE_CHANGED')
        manifest['predecessor']={'path':str(previous/'Manifest.json'),'sha256':sha(previous/'Manifest.json')}
        for entry in prior['sources']:
            if entry['state'] not in ('SUCCESS','EMPTY_RESPONSE'):continue
            src=previous/entry['path'];obj=json.loads(src.read_text());raw=previous/obj['raw_path']
            if src.parent!=previous or raw.parent!=previous or src.is_symlink() or raw.is_symlink() or sha(src)!=entry['sha256'] or sha(raw)!=obj['raw_sha256']:raise ValueError('RESUME_PIN_MISMATCH')
            shutil.copyfile(src,folder/src.name);shutil.copyfile(raw,folder/raw.name);sources.append(entry)
    manifest['request_interval_seconds']=30
    if (ARCHIVE/'STOP').exists():
        manifest.update(state='CAPTURE_STOPPED',retrieved_at=stamp());dump(folder/'Manifest.json',manifest);return folder,manifest
    credential,lookup=old.lookup_credential();dump(folder/'credential-lookup.json',lookup)
    if credential is None:
        manifest.update(state='SECRET_NOT_AVAILABLE',retrieved_at=stamp());dump(folder/'Manifest.json',manifest);return folder,manifest
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    try:
        for i,(api,params,is_aux) in enumerate(requests):
            check_stop()
            if any(e['api_name']==api and e['params']==params for e in sources):continue
            fields=FIELDS[api];name=f'{i:03d}-{api}-{params.get("ts_code",params.get("exchange"))}'
            for attempt in range(3):
                wrapper=dict(api_name=api,params=params,request_fields=fields,request_started_at=stamp(),retrieved_at=None,fields=[],items=[],error_code=None,row_count=0,state='REQUEST_FAILED',raw_path=None,raw_sha256=None)
                try:
                    with queue(priority):
                        body=old._canonical({'api_name':api,'token':credential._value,'params':dict(params,ts_type_name=old.BASE_URL),'fields':fields})
                        url=old.BASE_URL+'/'+api;req=urllib.request.Request(url,data=body,method='POST',headers={'Content-Type':'application/json'})
                        wrapper['request_sent_at']=stamp()
                        try:response=opener.open(req,timeout=25)
                        except urllib.error.HTTPError as err:
                            if 300<=err.code<400:raise ValueError('AUTH_REDIRECT_BLOCKED') from None
                            response=err
                        with response:
                            if response.geturl()!=url:raise ValueError('AUTH_REDIRECT_BLOCKED')
                            status=response.code;raw=response.read(old.MAX_BYTES+1)
                        if len(raw)>old.MAX_BYTES:raise ValueError('RESPONSE_SIZE_LIMIT')
                        old._secret_check(raw,credential)
                    rawfile=folder/(name+f'-attempt{attempt}.raw.json')
                    with rawfile.open('xb') as f:f.write(raw)
                    rawfile.chmod(0o600);table=json.loads(raw,parse_float=str);data=table.get('data')
                    wrapper.update(raw_path=rawfile.name,raw_sha256=sha(rawfile),http_status=status,error_code=table.get('code'))
                    if status==200 and type(table.get('code')) is int and table['code']==0 and isinstance(data,dict):
                        keys=data.get('fields',[]);items=data.get('items',[])
                        if len(set(keys))!=len(keys) or any(len(v)!=len(keys) for v in items):raise ValueError('TABLE_INVALID')
                        wrapper.update(fields=keys,items=items,row_count=len(items),state='SUCCESS' if items else 'EMPTY_RESPONSE')
                    else:
                        msg=str(table.get('msg') or '')
                        wrapper['state']='IP_CONCURRENCY_LIMIT' if 'IP' in msg.upper() and any(w in msg for w in ('限制','超限','多个')) else ('ENTITLEMENT_NOT_GRANTED' if any(w in msg for w in ('权限','积分','无权')) else 'API_ERROR')
                except CaptureStopped:raise
                except Exception as exc:wrapper['error_type']=type(exc).__name__
                wrapper['retrieved_at']=stamp();p=folder/(name+f'-attempt{attempt}.json');dump(p,wrapper)
                entry={k:wrapper[k] for k in ('api_name','params','fields','row_count','error_code','state')};entry.update(path=p.name,sha256=sha(p))
                if wrapper['state'] in ('SUCCESS','EMPTY_RESPONSE','ENTITLEMENT_NOT_GRANTED') or attempt==2:break
                controlled_sleep(10*(attempt+1))
            (aux if is_aux else sources).append(entry)
            print(json.dumps({k:entry[k] for k in ('api_name','params','row_count','state')},ensure_ascii=False),flush=True)
            if wrapper['state']=='IP_CONCURRENCY_LIMIT':break
    except CaptureStopped:
        manifest['state']='CAPTURE_STOPPED'
    finally:
        manifest.update(retrieved_at=stamp(),state=manifest.get('state') or ('CAPTURE_COMPLETE' if len(sources)==65 else 'CAPTURE_PARTIAL'),planned_requests=len(requests));dump(folder/'Manifest.json',manifest)
    return folder,manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--epoch',required=True);p.add_argument('--priority',choices=['history','forward'],default='history');p.add_argument('--future-end');p.add_argument('--resume');a=p.parse_args()
    folder,m=capture(a.start,a.end,a.epoch,a.priority,a.future_end,a.resume);print(json.dumps({'directory':str(folder),'state':m['state']}))
