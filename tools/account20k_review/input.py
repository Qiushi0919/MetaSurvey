"""Independent issuer-input chain checks. No network or source mutation.
Real cached capture is the positive case; mutations are injected in memory only.
"""
from copy import deepcopy
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import argparse,json
from tools.forward_c20k import input as sut
from tools.long_forward import builder


def review():
    root=sut.ROOT; archive=sut.ARCHIVE
    capture=root.parent/'.p1b-archives/long-forward-20261015/capture-forward-20261019-183015'
    checks=[];at=datetime.now(timezone.utc).isoformat()
    policy=sut.read(root/'experiments/account20k_v1/InputPolicy.json');s=policy['supplement']
    original_adapter=builder._adapter
    def run(adapter=None,prior=None,at_override=None):
        with TemporaryDirectory() as tmp:
            with patch.object(builder,'_adapter',adapter or original_adapter):
                return sut.build_case(capture,'INDEPENDENT-C20K-INPUT',at_override or at,Path(tmp).resolve(),prior)
    def check(name,passed,actual=None):checks.append(dict(name=name,passed=bool(passed),actual=actual))
    def refused(name,call):
        try:
            report,case=call();ok=case is None;detail=report.get('errors')
        except (ValueError,KeyError,TypeError,OSError,ArithmeticError) as e:ok=True;detail=str(e)
        check(name,ok,detail)
    before=sut.filehash(capture/'Manifest.json')
    report,case=run()
    check('real_capture_admitted_846_bars',case is not None and len(case['bars'])==846,len(case['bars']) if case else report['errors'])
    actions=[a for a in case['actions'] if a['id']=='600312.SH:2026-10-15']
    check('issuer_terms_match_hand_transcription',len(actions)==1 and {k:actions[0][k] for k in ('record_date','ex_date','pay_date','cash_per_share','bonus_ratio','split_ratio')}==dict(record_date='2026-10-14',ex_date='2026-10-15',pay_date='2026-10-15',cash_per_share='0.242',bonus_ratio='0',split_ratio='1'))
    proof=case['evidence'][actions[0]['evidence_ref']]
    check('derived_source_explicit_not_provider',proof['source']=='DERIVED_GATEWAY_DIVIDENDS_PLUS_ISSUER_CNINFO_PDF' and proof['upstream_original_hash'].startswith('sha256:'))
    check('issuer_actual_clock_not_printed_publication',builder.old.clock(proof['available_at'])>=builder.old.clock(s['retrieved_at']) and proof['published_at'] is None,proof['available_at'])
    check('no_historical_visibility_claim',report['historical_visibility_proven'] is False and 'NOT_ORIGINAL_PIT' in proof['visibility_assumption'])
    oldreport,oldcase=builder.build_case(capture,'INDEPENDENT-OLD-A',at,mode='FORWARD_A')
    check('old_a_still_blocked_factor_action',oldcase is None and any('UNMATCHED_FACTOR_ACTION:600312.SH:2026-10-15' in x['detail'] for x in oldreport['errors']),oldreport['errors'])
    refused('cannot_run_before_new_policy_freeze',lambda:run(at_override='2026-10-20T06:28:00+00:00'))
    read=sut.read
    def mutated_read(target,change):
        def f(path):
            value=read(path)
            if Path(path)==target:value=deepcopy(value);value.update(change)
            return value
        return f
    with patch.object(sut,'read',mutated_read(builder.POLICY,{'allowed_purposes':[]})):
        refused('forward_purpose_removed_blocks',run)
    rp=archive/'official-action/Receipt.json'
    for label,change in [('issuer_retrieval_disagrees_policy',{'retrieved_at':'2026-10-20T06:28:12+00:00'}),('issuer_request_starts_after_receipt',{'request_started_at':'2026-10-20T06:29:00+00:00'})]:
        with patch.object(sut,'read',mutated_read(rp,change)):
            refused(label,run)
    fh=sut.filehash
    with patch.object(sut,'filehash',lambda p:'sha256:BAD' if Path(p).name=='600312-20261015.pdf' else fh(p)):
        refused('issuer_pdf_hash_mismatch_blocks',run)
    # Additional rows enter AFTER the original byte/schema checks for a targeted
    # source-conflict unit test, not as assertions of actual supplier responses.
    supplied=dict(ts_code='600312.SH',end_date='20260630',ann_date='20261009',imp_ann_date='20261009',div_proc='实施',ex_date='20261015',record_date='20261014',pay_date='20261015',div_listdate=None,cash_div_tax='0.242',stk_div='0',stk_bo_rate='0',stk_co_rate='0')
    def injected(change):
        def adapter(p):
            m=original_adapter(p);original=m.indexed_capture
            def index(*args,**kw):
                idx,pins,receipt=original(*args,**kw)
                if not kw.get('_inherited'):
                    obj,rows,path,h=idx['dividend','600312.SH'];rows=deepcopy(rows);rows.append(dict(supplied,**change));idx['dividend','600312.SH']=obj,rows,path,h
                return idx,pins,receipt
            m.indexed_capture=index;return m
        return adapter
    for key,value in [('cash_div_tax','0.243'),('record_date','20261013'),('pay_date','20261016'),('stk_div','0.1'),('ts_code','603228.SH'),('stk_bo_rate','0.1')]:
        refused('provider_conflict_'+key,lambda key=key,value=value:run(injected({key:value})))
    # Alter only the hash expectation inside an in-memory prior, to require that
    # the consumed upstream raw is checked as well as its derived wrapper.
    prior=deepcopy(case);p=prior['evidence'][actions[0]['evidence_ref']];p['upstream_original_hash']='sha256:'+'0'*64
    # The temporary derived path no longer exists, so use persistent observed
    # case for this counterexample; only upstream assertion is mutated.
    prior=sut.read(archive/'input-check-20261019/Case.json')
    for p in prior['evidence'].values():
        if p.get('upstream_original_hash'):p['upstream_original_hash']='sha256:'+'0'*64
    refused('consumed_upstream_raw_hash_is_verified',lambda:run(prior=prior))
    check('capture_manifest_unchanged',before==sut.filehash(capture/'Manifest.json'))
    return dict(kind='IndependentC20kIssuerInputReview',recorded_at=at,passed=all(c['passed'] for c in checks),count=len(checks),checks=checks,source_hashes={str(root/p):fh(root/p) for p in ('tools/forward_c20k/input.py','tools/forward_c20k/plan.py','experiments/account20k_v1/InputPolicy.json')},limitations=['Reviewer visually checked archived page1.png: 600312 issuer, 2026 half-year distribution, 0.242/share gross, record10/14 ex/pay10/15. Script binds PDF receipt/hash; not independent provider licensing or historical first visibility','Mutated inputs are in-memory counterexamples, not real source observations','No credentials, network, market execution or old source modification'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=review()
    with a.output.open('x') as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(dict(passed=r['passed'],count=r['count'],failed=[x for x in r['checks'] if not x['passed']])))
