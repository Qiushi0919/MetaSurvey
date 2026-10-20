"""New C-only input supplement. Original capture/Forward A parser never changes."""
from copy import deepcopy
from pathlib import Path
from decimal import Decimal as D
from tools.long_forward import builder
from .store import ROOT,ARCHIVE,read,filehash,save,digest

def build_case(folder,run_id,run_at,output,prior=None):
    if 'LOCAL_FORWARD_VIRTUAL_LEDGER' not in read(builder.POLICY).get('allowed_purposes',[]):
        raise ValueError('FORWARD_PURPOSE_NOT_AUTHORIZED')
    policy=read(ROOT/'experiments/account20k_v1/InputPolicy.json');s=policy['supplement']
    pdf=ARCHIVE/'official-action/600312-20261015.pdf'
    receipt_path=ARCHIVE/'official-action/Receipt.json';r=read(receipt_path)
    if filehash(pdf)!=s['pdf_sha256'] or filehash(receipt_path)!=s['receipt_sha256']:
        raise ValueError('ISSUER_SUPPLEMENT_HASH')
    if r['url']!=s['source_url'] or r['http_status']!=200 or r['sha256']!=filehash(pdf):
        raise ValueError('ISSUER_RECEIPT_BINDING')
    if (r['retrieved_at']!=s['retrieved_at'] or
        builder.old.clock(r['request_started_at'])>builder.old.clock(r['retrieved_at'])):
        raise ValueError('ISSUER_RECEIPT_CLOCK')
    for proof in (prior or {}).get('evidence',{}).values():
        if proof.get('source')=='DERIVED_GATEWAY_DIVIDENDS_PLUS_ISSUER_CNINFO_PDF':
            upstream=Path(proof['upstream_original_path'])
            if (not upstream.is_relative_to(ROOT.parent/'.p1b-archives/long-forward-20261015')
                or upstream.resolve()!=upstream or filehash(upstream)!=proof['upstream_original_hash']
                or proof['issuer_sha256']!=filehash(pdf)):
                raise ValueError('PRIOR_DERIVED_UPSTREAM_CHANGED')
    if not builder.old.clock(policy['frozen_at'])<=builder.old.clock(run_at):
        raise ValueError('INPUT_RUN_BEFORE_FREEZE')
    if builder.old.clock(r['retrieved_at'])>builder.old.clock(run_at):raise ValueError('FUTURE_ISSUER_CAPTURE')
    p=builder.protocol();effective=deepcopy(p);manifest=read(folder/'Manifest.json')
    end=builder.old.day(manifest['scope']['end_date'])
    effective['target_window']={'warmup_start':p['forward']['warmup_start'],'start':p['forward']['first_decision_session'],'end':end}
    module=builder._adapter(effective)
    original_index=module.indexed_capture
    supplement_state={}
    def index(*args,**kwargs):
        idx,pins,successful=original_index(*args,**kwargs)
        if kwargs.get('_inherited'): return idx,pins,successful
        obj,rows,path,h=idx['dividend',s['symbol']]
        rows=deepcopy(rows)
        matching=[x for x in rows if x.get('ex_date')==s['ex_date'].replace('-','') and x.get('div_proc')=='实施']
        if matching:
            for x in matching:
                if (D(str(x.get('cash_div_tax')))!=D(s['cash_per_share']) or
                    x.get('record_date')!=s['record_date'].replace('-','') or
                    x.get('pay_date')!=s['pay_date'].replace('-','') or D(str(x.get('stk_div')))!=0):
                    raise ValueError('ISSUER_PROVIDER_ACTION_CONFLICT')
            supplement_state['state']='PROVIDER_EVENT_NOW_MATCHES_ISSUER'
            return idx,pins,successful
        row=dict(ts_code=s['symbol'],end_date='20260630',ann_date='20261009',imp_ann_date='20261009',
            div_proc='实施',ex_date=s['ex_date'].replace('-',''),record_date=s['record_date'].replace('-',''),
            pay_date=s['pay_date'].replace('-',''),div_listdate=None,cash_div_tax=s['cash_per_share'],
            stk_div='0',stk_bo_rate='0',stk_co_rate='0')
        rows.append(row)
        derived=output/'Derived-Dividend-Table.json'
        body=dict(kind='DerivedDividendTableNotProviderResponse',rows=rows,original_path=path,
            original_hash=h,issuer_pdf_path=str(pdf),issuer_pdf_hash=filehash(pdf),
            issuer_receipt_hash=filehash(receipt_path),input_policy_hash=filehash(ROOT/'experiments/account20k_v1/InputPolicy.json'))
        save(derived,body)
        modified=deepcopy(obj);modified['retrieved_at']=max(
            (obj['retrieved_at'],r['retrieved_at']),key=builder.old.clock)
        idx['dividend',s['symbol']]=(modified,rows,str(derived),filehash(derived))
        pins.update({str(pdf):filehash(pdf),str(receipt_path):filehash(receipt_path),str(derived):filehash(derived)})
        supplement_state.update(state='ISSUER_EVENT_SUPPLEMENTED',derived_path=str(derived),original_path=path,
            original_hash=h,provider_retrieved_at=obj['retrieved_at'])
        return idx,pins,successful
    module.indexed_capture=index
    report,case=module.build_case(folder,run_id,run_at)
    report.update(kind='ForwardC20kCurrentInputBuild',input_policy_hash=filehash(ROOT/'experiments/account20k_v1/InputPolicy.json'),
                  supplement=supplement_state,old_forward_a_modified=False,historical_visibility_proven=False)
    if case is None:return report,None
    if supplement_state.get('derived_path'):
        ref=Path(supplement_state['derived_path']).name
        proof=case['evidence'][ref]
        proof.update(source='DERIVED_GATEWAY_DIVIDENDS_PLUS_ISSUER_CNINFO_PDF',
                     visibility_assumption='ACTUAL_CAPTURE_FOR_CURRENT_DECISIONS_ONLY_NOT_ORIGINAL_PIT',
                     upstream_original_path=supplement_state['original_path'],
                     upstream_original_hash=supplement_state['original_hash'],
                     issuer_source=s['source_url'],issuer_sha256=s['pdf_sha256'])
    case.update(mode='FORWARD_A',source_epoch='FORWARD_C20K_CURRENT_INPUT_V1',
        forward_scope=effective['target_window'],evidence_grade='CURRENT_OBSERVED_FORWARD')
    builder._aux(folder,manifest,case,report);builder._future_actions(folder,manifest,case,report)
    builder._prefix(case,folder.name)
    if prior is not None:builder._merge_prefix(case,prior)
    report.update(status='ADMITTED_CURRENT_OBSERVATION_WITH_ISSUER_SUPPLEMENT',
        case_hash=digest(case),input_clock='ACTUAL_RETRIEVAL_NO_HISTORICAL_FIRST_SEEN_INFERENCE')
    return report,case
