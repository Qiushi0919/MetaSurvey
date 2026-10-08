"""Repeatable local data import/update/check/diagnose entry, isolated from Forward."""
from __future__ import annotations
import argparse
import copy
import json
from datetime import date
from pathlib import Path
from .interface import *
from .requirements import requirements, evaluate_coverage, policy_gaps

def load_packets(path):
    packets=json.loads(Path(path).read_bytes())
    batches=[]
    for packet in packets:
        b=dict(packet)
        rawref=b.pop('raw_ref',None)
        if rawref is None and b.get('records'):
            rawref=b['records'][0].get('provenance',{}).get('raw_ref')
        if rawref is None: raise ValueError('PACKET_RAW_REFERENCE_REQUIRED')
        p=Path(rawref['path'] if isinstance(rawref,dict) else rawref)
        raw=p.read_bytes()
        expected=rawref.get('sha256') if isinstance(rawref,dict) else b.get('raw_sha256')
        if expected and expected.removeprefix('sha256:')!=digest(raw):
            raise ValueError('PACKET_RAW_HASH_CONFLICT_STOP')
        # Reconstruct numeric rows from the exact raw response. A caller's valid
        # content hash cannot bind independently edited normalized values.
        source=b.get('source');symbol=b.get('symbol');request=b.get('request',{})
        from .collectors import parse_tencent,parse_sina,parse_cninfo,_record
        if source=='OWNER_PROVIDED_MONTHLY_GATEWAY':
            from .gateway import _records,DEFINITIONS
            if request.get('api') not in DEFINITIONS or request.get('domain')!=DEFINITIONS[request['api']][0] or request.get('symbol')!=symbol:
                raise ValueError('PACKET_GATEWAY_SCOPE_CONFLICT')
            reconstructed=_records(json.loads(raw,parse_float=str)['data'],request)
        elif source=='TENCENT_PUBLIC_RAW_PRICE':
            params=request.get('params',{}).get('param','').split(',')
            if len(params)<4: raise ValueError('PACKET_PRICE_RANGE_REQUIRED')
            reconstructed=parse_tencent(raw,symbol,start=params[2],end=params[3])
        elif source=='SINA_PUBLIC_FINANCIAL':
            ends=[r.get('event_date') for r in b.get('records',[]) if r.get('event_date')]
            reconstructed=parse_sina(raw,symbol,request['params']['source'],
                start=min(ends) if ends else FINANCIAL_START,end=max([HISTORY_END,*ends]))
        elif source=='CNINFO_ISSUER_DISCLOSURES' and raw.startswith(b'%PDF-'):
            if len(b['records'])!=1: raise ValueError('PACKET_PDF_RECORD_SCOPE')
            rec=b['records'][0];parent=rec['provenance']['parent_index_provenance']
            pref=parent['raw_ref'];praw=Path(pref['path']).read_bytes()
            if digest(praw)!=pref['sha256']: raise ValueError('PACKET_PDF_PARENT_HASH_CONFLICT')
            originals=parse_cninfo(praw,symbol)[0]
            original=next(r for r in originals if r['identity']+':body'==rec['identity'])
            if request.get('url')!=original['fields']['document_url']: raise ValueError('PACKET_PDF_PARENT_URL_CONFLICT')
            reconstructed=[_record(original['identity']+':body',original['event_date'],
                {**original['fields'],'body_status':'PDF_BYTES_CAPTURED_NOT_NUMERICALLY_EXTRACTED'},0)]
        elif source=='CNINFO_ISSUER_DISCLOSURES':
            reconstructed=parse_cninfo(raw,symbol)[0]
        else: raise ValueError('PACKET_SOURCE_REPARSER_REQUIRED')
        projection=lambda rs:[{k:r.get(k) for k in ('identity','event_date','fields','units')} for r in rs]
        # The PDF parser's units default is UNVERIFIED; no numerical claim made.
        if projection(reconstructed)!=projection(b['records']): raise ValueError('PACKET_RAW_ROW_BINDING_CONFLICT_STOP')
        if any(r.get(k) is not None for r in b['records'] for k in ('published_at','available_at','first_visible_at','revision_id')):
            raise ValueError('PACKET_UNPROVEN_CLOCK_OR_REVISION_PROMOTION')
        b['raw_bytes']=raw
        batches.append(b)
    return batches

def run(mode, db_path, output_root, *, packet_paths=(), sources=(), through=HISTORY_END):
    from .store import EvidenceStore
    from .maintenance import build_update_plan, validate_records
    from .strategy import diagnose
    if date.fromisoformat(through)>date.today(): raise ValueError('FUTURE_COLLECTION_END_REJECTED')
    out=Path(output_root).resolve()
    private=Path('/Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008')
    if not out.is_relative_to(private): raise ValueError('OUTPUT_OUTSIDE_NEW_PRIVATE_EPOCH')
    out.mkdir(parents=True,exist_ok=False);out.chmod(0o700)
    if not Path(db_path).resolve().is_relative_to(private): raise ValueError('DB_OUTSIDE_NEW_PRIVATE_EPOCH')
    spec=frozen_spec()
    reqs=copy.deepcopy(requirements(spec))
    for r in reqs: r['end']=through
    store=EvidenceStore(db_path)
    receipts=[];attempts=[];failures=[]
    try:
        if mode in ('import','refresh'):
            from .data import read_existing
            # Import hash-checked original versions; repeat is idempotent.
            batches=read_existing()
            for b in batches:
                try: receipts.append(store.ingest(b))
                except Exception as error:
                    failures.append({'stage':'EXISTING_IMPORT','domain':b['domain'],'symbol':b['symbol'],
                                     'reason':type(error).__name__,'message':str(error)[:300]})
        for p in packet_paths:
            for b in load_packets(p):
                try: receipts.append(store.ingest(b))
                except Exception as error:
                    failures.append({'stage':'PACKET_IMPORT','domain':b['domain'],'symbol':b['symbol'],
                                     'reason':type(error).__name__,'message':str(error)[:300]})
        plan=build_update_plan(store.records(),reqs,through)
        write_new(out/'update-plan-before.json',plan)
        if mode=='refresh':
            for source in sources:
                if source=='public':
                    from .collectors import collect_public
                    result=collect_public(private/'data',update_plan=plan,through=through)
                elif source=='gateway':
                    from .gateway import collect_gateway
                    result=collect_gateway(out/'gateway',update_plan=plan,through=through)
                else: raise ValueError('SOURCE_NOT_CONFIGURED')
                attempts += result['attempts']
                for b in result['batches']:
                    try: receipts.append(store.ingest(b))
                    except Exception as error:
                        failures.append({'stage':'NEW_COLLECTION_IMPORT','domain':b['domain'],'symbol':b['symbol'],
                                         'reason':type(error).__name__,'message':str(error)[:300]})
                # Re-evaluate after each source batch before the next source.
                plan=build_update_plan(store.records(),reqs,through)
        audit=store.audit_raw()
        write_new(out/'raw-integrity.json',audit)
        if audit['state']!='PASS_INTEGRITY_ONLY': raise ValueError('STORED_RAW_INTEGRITY_FAILURE_STOP')
        records=store.records()
        coverage=evaluate_coverage(records)
        dq=validate_records(records)
        result=diagnose(records,coverage)
        write_new(out/'ingestion-receipts.json',receipts)
        write_new(out/'store-summary.json',store.summary())
        write_new(out/'collection-attempts.json',attempts)
        write_new(out/'requirements.json',reqs)
        write_new(out/'coverage.json',coverage)
        write_new(out/'data-quality.json',dq)
        write_new(out/'policy-gaps.json',policy_gaps(spec))
        write_new(out/'update-plan-after.json',build_update_plan(records,reqs,through))
        write_new(out/'frozen-family-diagnostic.json',result)
        write_new(out/'failures.json',failures)
        summary=dict(mode=mode,recorded_at=utc_now(),labels=LABELS,through=through,
            database=str(Path(db_path).resolve()),record_versions=len(records),
            ingested_batches=len(receipts),failed_batches=len(failures),new_collection_attempts=len(attempts),
            domain_counts=__import__('collections').Counter(r['domain'] for r in records),
            strategy_spec_sha256=SPEC_SHA256,engine_state='ENGINE_NOT_RUN',strategy_state='NOT_COMPUTABLE',
            full_family_performance=None,actual_account_parameters=UNSET,
            automatic_scheduling=False,untouched_oos=False,productionGate=False,
            metrics={'return':None,'fees':None,'max_drawdown':None,'MAE':None,'MFE':None,'benchmark_excess':None},
            ledger_state='NOT_CREATED_PREREQUISITES_BLOCK_EXECUTION',nav_state='NOT_CREATED_PREREQUISITES_BLOCK_EXECUTION')
        write_new(out/'summary.json',summary)
        return summary
    except Exception as error:
        write_new(out/'run-failure.json',{'stage':'INTEGRATION','reason':type(error).__name__,
            'message':str(error)[:300],'labels':LABELS,'engine_state':'ENGINE_NOT_RUN','metrics':None})
        raise
    finally: store.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['import','refresh','check','diagnose'])
    parser.add_argument('--db',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--packets',action='append',default=[])
    parser.add_argument('--sources',default='public')
    parser.add_argument('--through',default=HISTORY_END)
    args=parser.parse_args()
    result=run(args.mode,args.db,args.output,packet_paths=args.packets,
               sources=args.sources.split(',') if args.sources else [],through=args.through)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__': main()
