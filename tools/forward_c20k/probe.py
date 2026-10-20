"""Bounded capability capture, same configured gateway and Forward A serial queue.

Raw responses and lookup receipts remain outside Git. Never print exception
messages, credentials or provider response text.
"""
from pathlib import Path
from datetime import datetime, timezone
import json, os, urllib.request, urllib.error
from tools.long_forward.capture import queue
from backtest_5y.gateway import _credential_module, NoRedirect

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT.parent / '.p1b-archives/forward-c20k-20261020'
def now(): return datetime.now(timezone.utc).isoformat()
def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    path.chmod(0o600)

def probe(detailed=False, single=False):
    os.umask(0o077)
    folder = ARCHIVE / ('probe-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    folder.mkdir(mode=0o700)
    if (ARCHIVE/'STOP').exists(): raise RuntimeError('OWNER_STOP')
    if datetime.now(timezone.utc).date().isoformat() >= '2026-11-05':
        raise RuntimeError('SOURCE_EXPIRED')
    old = _credential_module()
    cfg = json.loads((ROOT/'config/provider/tushare-monthly-gateway.json').read_text())
    if cfg['endpoint'] != old.BASE_URL: raise ValueError('ENDPOINT_CHANGED')
    credential, lookup = old.lookup_credential()
    save(folder/'Lookup.json', lookup)
    if credential is None:
        save(folder/'Receipt.json', {'at':now(), 'state':'SECRET_UNAVAILABLE'})
        return
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    requests = [
        ('trade_cal', {'exchange':'SSE','start_date':'20261020','end_date':'20261023'}),
        ('rt_k', {'ts_code':'603228.SH'}),
        ('rt_min', {'ts_code':'603228.SH','freq':'1MIN'}),
    ]
    if detailed:
        symbols=json.loads((ROOT/'experiments/long_forward_v1/protocol.json').read_text())['members']
        requests=[('rt_k', {'ts_code':','.join(symbols)}),
                  ('rt_min', {'ts_code':','.join(symbols),'freq':'1MIN'})]
        if single: requests=[('rt_k', {'ts_code':'603228.SH'})]
    results=[]
    for api, params in requests:
        if (ARCHIVE/'STOP').exists(): break
        receipt={'api':api, 'params':params, 'started_at':now(), 'state':'REQUEST_FAILED'}
        try:
            with queue('history'):
                fields=('ts_code,name,pre_close,high,open,low,close,vol,amount,num,ask_price1,ask_volume1,bid_price1,bid_volume1,trade_time'
                        if detailed and api=='rt_k' else '')
                receipt['requested_fields']=fields
                body=old._canonical({'api_name':api,'token':credential._value,
                    'params':dict(params,ts_type_name=old.BASE_URL),'fields':fields})
                url=old.BASE_URL+'/'+api
                request=urllib.request.Request(url, data=body, method='POST',
                    headers={'Content-Type':'application/json'})
                receipt['sent_at']=now()
                with opener.open(request,timeout=25) as response:
                    if response.geturl()!=url: raise ValueError('REDIRECT')
                    raw=response.read(old.MAX_BYTES+1)
                if len(raw)>old.MAX_BYTES: raise ValueError('SIZE')
                old._secret_check(raw,credential)
            data=json.loads(raw,parse_float=str)
            (folder/(api+'.raw.json')).write_bytes(raw)
            (folder/(api+'.raw.json')).chmod(0o600)
            table=data.get('data') or {}; msg=str(data.get('msg') or '')
            receipt.update(code=data.get('code'),fields=table.get('fields',[]),
                row_count=len(table.get('items',[])))
            if data.get('code')==0:
                receipt['state']='SUCCESS' if receipt['row_count'] else 'EMPTY_RESPONSE'
            else:
                receipt['state']=('ENTITLEMENT_NOT_GRANTED' if any(w in msg for w in ('权限','积分','无权'))
                    else 'IP_CONCURRENCY_LIMIT' if 'IP' in msg.upper() else 'API_ERROR')
        except Exception as exc: receipt['error_type']=type(exc).__name__
        receipt['received_at']=now()
        save(folder/(api+'.receipt.json'), receipt); results.append(receipt)
        print(json.dumps(receipt,ensure_ascii=False),flush=True)
    import hashlib
    save(folder/'Receipt.json',{'kind':'RealtimeCapabilityProbe','at':now(),
        'connection_kind':'COMPATIBLE_GATEWAY_NOT_VERIFIED_OFFICIAL_TUSHARE',
        'provider_license_verified':False,'results':results,
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}})
    print(str(folder),flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--detailed',action='store_true')
    parser.add_argument('--single',action='store_true');args=parser.parse_args()
    probe(args.detailed,args.single)
