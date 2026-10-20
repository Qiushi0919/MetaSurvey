"""One bounded request through the existing shared low-priority queue."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, urllib.request
from backtest_5y.gateway import _credential_module, NoRedirect
from tools.long_forward.capture import queue
from .probe import ROOT, ARCHIVE, now, save

FIELDS='ts_code,name,pre_close,high,open,low,close,vol,amount,num,ask_price1,ask_volume1,bid_price1,bid_volume1,trade_time'
def capture(api, params):
    if api not in ('rt_k','trade_cal','dividend','stk_limit','suspend_d'): raise ValueError('UNREGISTERED_API')
    members=json.loads((ROOT/'experiments/account20k_v1/Config.json').read_text())['members']
    if api!='trade_cal' and params.get('ts_code') not in members:
        raise ValueError('SINGLE_REGISTERED_SECURITY_REQUIRED')
    if (ARCHIVE/'STOP').exists(): raise ValueError('OWNER_STOP')
    if datetime.now(timezone.utc).date().isoformat()>='2026-11-05':raise ValueError('SOURCE_EXPIRED')
    folder=ARCHIVE/'captures'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder.mkdir(parents=True,mode=0o700)
    old=_credential_module(); cfg=json.loads((ROOT/'config/provider/tushare-monthly-gateway.json').read_text())
    if cfg['endpoint']!=old.BASE_URL: raise ValueError('ENDPOINT_CHANGED')
    cred,lookup=old.lookup_credential();save(folder/'Lookup.json',lookup)
    receipt=dict(api=api,params=params,started_at=now(),state='SECRET_UNAVAILABLE',path=str(folder))
    rows=[]
    if cred is not None:
        receipt['state']='REQUEST_FAILED'
        try:
            with queue('history'):
                if (ARCHIVE/'STOP').exists(): raise ValueError('OWNER_STOP')
                fields=FIELDS if api=='rt_k' else ''
                body=old._canonical(dict(api_name=api,token=cred._value,params=dict(params,ts_type_name=old.BASE_URL),fields=fields))
                url=old.BASE_URL+'/'+api
                request=urllib.request.Request(url,data=body,method='POST',headers={'Content-Type':'application/json'})
                receipt['sent_at']=now()
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
                with opener.open(request,timeout=25) as response:
                    if response.geturl()!=url: raise ValueError('REDIRECT')
                    raw=response.read(old.MAX_BYTES+1)
                if len(raw)>old.MAX_BYTES: raise ValueError('RESPONSE_SIZE_LIMIT')
                old._secret_check(raw,cred)
            p=folder/'Response.json';p.write_bytes(raw);p.chmod(0o600)
            receipt['response_hash']='sha256:'+hashlib.sha256(raw).hexdigest()
            table=json.loads(raw,parse_float=str)
            if type(table.get('code')) is int and table['code']==0:
                data=table['data'];keys=data['fields'];items=data['items']
                if len(set(keys))!=len(keys) or any(len(i)!=len(keys) for i in items):
                    raise ValueError('SCHEMA_INVALID')
                rows=[dict(zip(keys,item)) for item in items]
                receipt.update(state='SUCCESS' if rows else 'EMPTY_RESPONSE',fields=keys,row_count=len(rows))
            else:
                receipt.update(state='API_REJECTED',code=table.get('code'))
        except Exception as exc: receipt['error_type']=type(exc).__name__
    receipt['received_at']=now();save(folder/'Receipt.json',receipt)
    return receipt,rows
