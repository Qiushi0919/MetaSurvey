"""Synthetic positive prepare -> JSON -> activate -> partial-fill chain.
No source calls, credential access, or real account writes. Production decision,
sizing, serialization, activation, matching and ledger remain system-under-test.
"""
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import ExitStack
import argparse,json
from tools.long_forward.tests.test_forward import fixture
from tools.forward_c20k import plan,runtime,account,store,input as input_module
from experiments.account20k_v1 import matching


def review(cent_compatible=False):
    checks=[];artifacts={}
    def check(name,value,expected=True):checks.append(dict(name=name,actual=value,expected=expected,passed=value==expected))
    c,_=fixture(end=21);session=c['calendar'][-1]['date'];execution=c['execution_calendar'][0]['date'];at=session+'T18:35:00+08:00';c['run_at']=at
    if cent_compatible:
        for bar in c['bars']:
            for key in ('open','high','low','close'):bar[key]=str(D(bar[key])+D('.40'))
    artifacts['cent_compatible_fixture']=cent_compatible
    cfg=dict(account_id='SYNTHETIC_C20K',members={'SSE:TEST':'TEST'},parameters=dict(rs_window=10,exit_ma=20,exit_min_age=10,atr_multiple='2.5'))
    a=dict(cash_cents=2000000,available_cash_cents=2000000,frozen_cash_cents=0,tax_reserve_cents=0,positions={},orders={},fills=[],ledger=[],dividends=[],dividend_rights={},peak_cents=2000000,nav_cents=2000000,maximum_drawdown='0',settlements=[],effective_observation_days=0)
    try:
        with TemporaryDirectory() as temporary,ExitStack() as stack:
            temp=Path(temporary).resolve();capture=temp/'capture';capture.mkdir();(capture/'Manifest.json').write_text('{}')
            for module,key,value in [(plan,'ARCHIVE',temp),(plan,'now',lambda:at),(plan,'config',lambda:deepcopy(cfg)),(plan,'latest_capture',lambda _:capture),(plan,'event',lambda *args,**kwargs:None),(plan,'filehash',lambda p:'sha256:'+sha256(Path(p).read_bytes()).hexdigest() if Path(p).is_relative_to(temp) else 'sha256:'+'a'*64),(input_module,'build_case',lambda *args,**kwargs:({'errors':[]},deepcopy(c)))]:stack.enter_context(patch.object(module,key,value))
            receipt=plan.prepare(a,session);artifacts['prepare_return']=receipt
            check('prepare_actual_decide_and_sizing_frozen',receipt.get('state'),'FROZEN')
            check('prepare_actual_engine_called',receipt.get('engine_called'),True)
            paths=list((temp/'plans').glob('*/Plan.json'))
            check('plan_file_complete_valid_json',len(paths),1)
            serialized=json.loads(paths[0].read_text()) if paths else {}
            check('serialized_plan_equals_return',serialized,receipt)
            check('positive_signal_creates_one_order',len(receipt.get('orders',[])),1)
            if receipt.get('state')!='FROZEN' or len(receipt.get('orders',[]))!=1:return result(checks,artifacts)
            a['plan']=serialized
            submission=execution+'T09:35:00+08:00'
            with patch.object(runtime,'now',return_value=submission),patch.object(runtime,'local',return_value=datetime.fromisoformat(submission)):
                activated=runtime.activate(a,{'days':{d['date']:True for d in c['execution_calendar']}},execution)
            check('serialized_frozen_plan_activates',activated)
            order=next(iter(a['orders'].values()));artifacts['order']=deepcopy(order)
            check('quantity_multiple_of_lot',order['quantity']%100,0)
            check('quantity_positive_and_risk_budget',order['quantity']>100 and order['planned_loss_cents']<=20000)
            def quote(minute,volume):return dict(symbol='SSE:TEST',source_at=execution+f'T09:{minute}:00+08:00',received_at=execution+f'T09:{minute}:01+08:00',volume=volume,volume_unit='SHARES',last='12.10',status='TRADABLE',state_evidence_verified=True,limits_evidence_verified=True,down_limit='1',up_limit='100')
            q1,q2,q3=quote('36',100000),quote('37',110000),quote('38',120000)
            fills=[]
            for previous,current,minute in [(q1,q2,'37'),(q2,q3,'38')]:
                fill=matching.match(order,previous,current,execution+f'T09:{minute}:02+08:00',a['available_cash_cents']+order['reserve_cents'],0)
                check('fresh_causal_partial_'+minute,fill.get('state'),'SIMULATED_FILL')
                if fill.get('state')!='SIMULATED_FILL':break
                check('volume_caps_partial_'+minute,fill['quantity'],100)
                with patch.object(account,'now',return_value=execution+f'T09:{minute}:02+08:00'),patch.object(store,'now',return_value=execution+f'T09:{minute}:02+08:00'):
                    account.apply_fill(a,order['order_id'],fill,store.digest(current))
                fills.append(fill)
            artifacts['fills']=fills
            if len(fills)==2:
                check('first_minimum_commission',fills[0]['fees']['commission_cents'],500)
                check('second_same_order_incremental_commission',fills[1]['fees']['commission_cents'],0)
                # 12.10 * 1.001 rounds upward to 12.12; 100 shares =>121200 fen.
                # Each transfer rounds 1 fen; first commission500, next0.
                check('independent_hand_cash_after_200_shares',a['cash_cents'],2000000-121701-121201)
                check('position_200_shares',sum(l['quantity'] for l in a['positions']['SSE:TEST']['lots']),200)
                check('two_ledger_rows',len(a['ledger']),2)
                check('ledger_cash_continuity',a['ledger'][1]['before_cents'],a['ledger'][0]['after_cents'])
                check('ledger_hash_chain',a['ledger'][1]['previous_hash'],store.digest(a['ledger'][0]))
                check('remaining_order_quantity',order['remaining_quantity'],order['quantity']-200)
                check('snapshot_consumption_count',len(order['consumed_snapshots']),2)
                try:account.apply_fill(a,order['order_id'],fills[-1],store.digest(q3));duplicate_refused=False
                except ValueError:duplicate_refused=True
                check('duplicate_snapshot_refused',duplicate_refused)
                artifacts['final_account']=a
    except Exception as e:
        artifacts['exception']={'type':type(e).__name__,'detail':str(e)};check('flow_completes_without_exception',False)
    return result(checks,artifacts)


def result(checks,artifacts):
    root=Path(__file__).resolve().parents[2]
    return dict(kind='IndependentC20kPositivePlanFlow',synthetic=True,at=datetime.now(timezone.utc).isoformat(),passed=all(x['passed'] for x in checks),count=len(checks),checks=checks,artifacts=artifacts,source_hashes={str(Path(m.__file__).relative_to(root)):'sha256:'+sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (plan,runtime,account,store,matching)},limitations=['Synthetic single-symbol fixture; does not constitute actual plan, trading day or market execution','Only input builder/clock/config/archive boundary mocked; real production _run/_decide/sizing/save/activate/match/apply_fill used','No credentials, network, frozen-file changes or business archive writes'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--cent-compatible',action='store_true');args=p.parse_args();r=review(args.cent_compatible)
    with args.output.open('x') as f:json.dump(r,f,ensure_ascii=False,indent=2,default=str)
    print(json.dumps({'passed':r['passed'],'count':r['count'],'failures':[x for x in r['checks'] if not x['passed']],'exception':r['artifacts'].get('exception')},ensure_ascii=False))
