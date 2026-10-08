"""New Owner-authorized exact-three historical gateway collection, quarantine.

The earlier persistent credential reuse and exact HTTP endpoint authorization
remain in force. Current Owner expands the historical-data collection scope.
No license, transport integrity, PIT or execution authority is inferred.
"""
from __future__ import annotations
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from .interface import *

DEFINITIONS = {
    'daily': ('PRICE', 'ts_code,trade_date,open,high,low,close,pre_close,vol,amount', HISTORY_START),
    'daily_basic': ('VALUATION', 'ts_code,trade_date,close,pe,pe_ttm,pb,total_share,total_mv', HISTORY_START),
    'fina_indicator': ('FINANCIAL_INDICATOR', 'ts_code,ann_date,end_date,roic,ebitda,netdebt,interestdebt,grossprofit_margin,roe,update_flag', FINANCIAL_START),
    'income': ('FINANCIAL_INCOME', 'ts_code,ann_date,f_ann_date,end_date,report_type,revenue,oper_cost,n_income,ebit,ebitda,update_flag', FINANCIAL_START),
    'balancesheet': ('FINANCIAL_BALANCE', 'ts_code,ann_date,f_ann_date,end_date,report_type,money_cap,total_liab,st_borr,lt_borr,bond_payable,non_cur_liab_due_1y,update_flag', FINANCIAL_START),
    'cashflow': ('FINANCIAL_CASHFLOW', 'ts_code,ann_date,f_ann_date,end_date,report_type,n_cashflow_act,update_flag', FINANCIAL_START),
    'adj_factor': ('ACTION', 'ts_code,trade_date,adj_factor', HISTORY_START),
    'suspend_d': ('STATUS', 'ts_code,trade_date,suspend_timing,suspend_type', HISTORY_START),
    'stk_limit': ('STATUS', 'ts_code,trade_date,pre_close,up_limit,down_limit', HISTORY_START),
    'namechange': ('STATUS', 'ts_code,name,start_date,end_date,ann_date,change_reason', HISTORY_START),
    'index_member_all': ('INDUSTRY_MEMBERSHIP', 'ts_code,l1_code,l2_code,l3_code,in_date,out_date,is_new', HISTORY_START),
}

def _credential_module():
    path=ROOT/'tushare-real-admission/probe.py'
    name='_backtest5y_readonly_credential_utilities'
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('AUTH_REDIRECT_BLOCKED')

def plan(apis=None, update_plan=None, through=HISTORY_END):
    selected=list(DEFINITIONS) if apis is None else list(apis)
    if any(a not in DEFINITIONS for a in selected): raise ValueError('API_OUTSIDE_FROZEN_DATA_PLAN')
    requests=[]
    for api in selected:
        domain,fields,start=DEFINITIONS[api]
        for symbol in SYMBOLS:
            params={'ts_code':symbol,'start_date':start.replace('-',''),'end_date':through.replace('-','')}
            if update_plan and api not in ('income','balancesheet','cashflow','fina_indicator','namechange','index_member_all'):
                matches=[r for r in update_plan.get('rows',[]) if r.get('domain')==domain and r.get('symbol')==symbol]
                intervals=[q for r in matches for q in r.get('requested_intervals',r.get('intervals',[])) if isinstance(q,dict)]
                starts=[q.get('start') for q in intervals if q.get('start')]
                # Include historical gap repair as well as tail overlap, never only MAX(date).
                if starts: params['start_date']=min(starts).replace('-','')
            if api=='index_member_all': params={'ts_code':symbol,'is_new':'N'}
            requests.append(dict(api=api,domain=domain,symbol=symbol,params=params,fields=fields))
    return requests

def _records(data, request):
    fields=data.get('fields',[]);items=data.get('items',[])
    if not isinstance(fields,list) or not isinstance(items,list) or len(set(fields))!=len(fields):
        raise ValueError('MALFORMED_TABLE')
    rows=[]
    for i,values in enumerate(items):
        if not isinstance(values,list) or len(values)!=len(fields): raise ValueError('ROW_WIDTH_CONFLICT')
        # Preserve decimal lexical values; no implicit binary float arithmetic.
        raw=dict(zip(fields,values))
        if raw.get('ts_code') not in (None,request['symbol']): raise ValueError('CROSS_SYMBOL_RESPONSE')
        event=raw.get('trade_date',raw.get('end_date',raw.get('in_date',raw.get('start_date'))))
        text=str(event) if event else None
        event_iso=text[:4]+'-'+text[4:6]+'-'+text[6:] if text and len(text)==8 and text.isdigit() else None
        units={'price':'CNY','vol':'100_SHARES','amount':'1000_CNY'} if request['api']=='daily' else {}
        # Source ann_date is DATE_ONLY, not an invented midnight timestamp.
        identity='|'.join(str(raw.get(k,'')) for k in ('ts_code','trade_date','end_date','report_type','in_date','start_date','suspend_type'))
        rows.append(dict(identity=identity,event_date=event_iso,published_at=None,available_at=None,
            first_visible_at=None,revision_id=None,fields=raw,units=units,
            provenance={'api_name':request['api'],'row_ordinal':i,'original_ann_date':raw.get('ann_date'),
                'original_f_ann_date':raw.get('f_ann_date'),'publication_precision':'DATE_ONLY_OR_UNRECORDED',
                'origin':'NEW_GATEWAY_COLLECTION','version_semantics':'CONTENT_HASH_NOT_VENDOR_REVISION_ID',
                'historical_visibility_proven':False,'units_state':'SOURCE_DECLARED_NOT_INDEPENDENTLY_ACCEPTED'}))
    return rows

def collect_gateway(output_root, apis=None, max_attempts=33, update_plan=None, through=HISTORY_END):
    requests=plan(apis,update_plan,through)
    if len(requests)>max_attempts: raise ValueError('REQUEST_BUDGET_EXCEEDED')
    root=Path(output_root);root.mkdir(parents=True,exist_ok=False);root.chmod(0o700)
    config=json.loads((ROOT/'config/provider/tushare-monthly-gateway.json').read_bytes())
    old=_credential_module()
    if config['endpoint']!=old.BASE_URL: raise ValueError('ENDPOINT_CONFLICT_STOP')
    credential,lookup=old.lookup_credential()
    write_new(root/'credential-lookup.json',lookup)  # Presence only, never value/hash.
    if credential is None:
        return {'batches':[],'attempts':[{'state':'BLOCKED_SECRET_NOT_AVAILABLE',**lookup}]}
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    batches=[];attempts=[]
    for ordinal,request in enumerate(requests):
        url=old.BASE_URL+'/'+request['api']
        public=dict(request=request,source_url=url,labels=LABELS,license_state='UNVERIFIED_OWNER_LOCAL_QUARANTINE_ONLY',
            provider_identity='UNVERIFIED',transport_integrity='UNVERIFIED_OWNER_HTTP_EXCEPTION',historical_visibility_proven=False)
        try:
            params=dict(request['params'],ts_type_name=old.BASE_URL)
            body=canonical({'api_name':request['api'],'token':credential._value,'params':params,'fields':request['fields']})
            req=urllib.request.Request(url,data=body,method='POST',headers={'Content-Type':'application/json'})
            try: response=opener.open(req,timeout=20)
            except urllib.error.HTTPError as error:
                if 300<=error.code<400: raise ValueError('AUTH_REDIRECT_BLOCKED') from None
                response=error
            with response:
                if response.geturl()!=url: raise ValueError('AUTH_REDIRECT_BLOCKED')
                status=response.code;raw=response.read(old.MAX_BYTES+1)
            retrieved=utc_now()
            old._secret_check(raw,credential) # Discard echo BEFORE hash or persistence.
            raw_path=root/f'{ordinal:03d}-{request["api"]}-{request["symbol"]}.json'
            with raw_path.open('xb') as f: f.write(raw)
            raw_path.chmod(0o600)
            table=json.loads(raw,parse_float=str)
            ok=status==200 and table.get('code')==0 and isinstance(table.get('data'),dict)
            records=_records(table['data'],request) if ok else []
            message=str(table.get('msg') or '').lower()
            access_limit=not ok and ('ip超限' in message or '多个ip' in message)
            state='ROWS_COLLECTED_NOT_ADMITTED' if records else ('EMPTY_RESPONSE_NOT_STATUS_PROOF' if ok else ('IP_CONCURRENCY_LIMIT' if access_limit else 'API_ERROR'))
            attempt=dict(public,state=state,http_status=status,api_code=table.get('code'),retrieved_at=retrieved,
                         row_count=len(records),raw_ref=str(raw_path),raw_sha256=digest(raw),response_msg_omitted=True)
            attempts.append(attempt)
            if ok:
                batches.append(dict(source='OWNER_PROVIDED_MONTHLY_GATEWAY',domain=request['domain'],symbol=request['symbol'],
                    request=request,retrieved_at=retrieved,raw_bytes=raw,source_url=url,records=records,
                    license_state='UNVERIFIED_OWNER_LOCAL_QUARANTINE_ONLY'))
        except Exception as error:
            # Never stringify arbitrary transport exceptions or response body.
            reason=str(error) if isinstance(error,ValueError) and str(error) in {'AUTH_REDIRECT_BLOCKED','MALFORMED_TABLE','ROW_WIDTH_CONFLICT','CROSS_SYMBOL_RESPONSE'} else type(error).__name__
            attempts.append(dict(public,state='COLLECTION_FAILED',reason=reason,retrieved_at=utc_now()))
        write_new(root/f'{ordinal:03d}-attempt.json',attempts[-1])
        if attempts[-1]['state']=='IP_CONCURRENCY_LIMIT':
            attempts.append({'state':'REMAINING_REQUESTS_DEFERRED_ACCESS_LIMIT','remaining_requests':requests[ordinal+1:],
                'reason':'Supplier IP concurrency restriction; no automatic retries or endpoint switch'})
            break
        if ordinal+1<len(requests): time.sleep(3) # Same prior bounded rate policy.
    write_new(root/'attempts.json',attempts)
    return {'batches':batches,'attempts':attempts}
