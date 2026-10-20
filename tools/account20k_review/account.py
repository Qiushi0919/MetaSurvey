"""Independent hand-valued dividend timing and append-chain corruption fixtures."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
from tools.forward_c20k import account,store

def review():
    checks=[]
    def eq(name,a,b):checks.append(dict(name=name,passed=a==b,actual=a,expected=b))
    a=dict(cash_cents=1900000,positions={'TEST':dict(sector='S',lots=[dict(lot_id='L',quantity=100,acquired='2026-10-19',available_date='2026-10-20',dividends=[],acquisition_cost_cents=100000)],entry_session='2026-10-19',entry_compare_price='10',stop_price='8',mark_price='10')},orders={},fills=[],ledger=[],dividends=[],peak_cents=2000000,maximum_drawdown='0')
    action=dict(id='D',symbol='TEST',record_date='2026-10-20',ex_date='2026-10-21',pay_date='2026-10-22',cash_per_share='1',bonus_ratio='0',split_ratio='1')
    c=dict(calendar=[{'date':d} for d in ['2026-10-20','2026-10-21','2026-10-22']],actions=[action],bars=[dict(session=d,symbol='TEST',status='TRADABLE',close='10' if d=='2026-10-20' else '9') for d in ['2026-10-20','2026-10-21','2026-10-22']])
    account.reconcile_close(a,c,'2026-10-20');eq('record_day_no_receivable',a['receivable_cents'],0);eq('record_day_no_double_NAV',a['nav_cents'],2000000)
    account.reconcile_close(a,c,'2026-10-21');eq('ex_day_receivable',a['receivable_cents'],10000);eq('ex_day_cash_unchanged',a['cash_cents'],1900000);eq('ex_day_NAV_reconciles',a['nav_cents'],2000000);eq('ex_day_price_stop_adjusted',a['positions']['TEST']['stop_price'],'7')
    account.reconcile_close(a,c,'2026-10-22');eq('pay_day_cash',a['cash_cents'],1910000);eq('pay_day_receivable_zero',a['receivable_cents'],0);eq('pay_day_NAV',a['nav_cents'],2000000)
    old=deepcopy(a);account.reconcile_close(a,c,'2026-10-22');eq('repeat_close_idempotent',a,old)
    with TemporaryDirectory() as directory:
        root=Path(directory).resolve();archive=root/'archive';archive.mkdir();cfg=root/'experiments/account20k_v1/Config.json';cfg.parent.mkdir(parents=True);cfg.write_text('{}')
        initial=dict(cash_cents=2000000,ledger=[],frozen_cash_cents=0,tax_reserve_cents=0,config_hash=store.filehash(cfg))
        (archive/'Initial-State.json').write_text(json.dumps(initial))
        with patch.object(store,'ROOT',root),patch.object(store,'ARCHIVE',archive):
            s=store.state();s=store.checkpoint(s,'FIXTURE_INITIAL');store.ledger(s,'FIXTURE_ONLY',-100,'test');s=store.checkpoint(s,'FIXTURE_NEXT')
            eq('checkpoint_valid_cash',store.state()['cash_cents'],1999900)
            ref=json.loads((archive/'CURRENT.json').read_text());path=archive/'checkpoints'/ref['file'];tamper=json.loads(path.read_text());tamper['ledger'][0]['previous_hash']='sha256:'+'0'*64;tamper.pop('content_hash');tamper['content_hash']=store.digest(tamper);path.write_text(json.dumps(tamper));ref['hash']=store.filehash(path);(archive/'CURRENT.json').write_text(json.dumps(ref))
            try:store.state();rejected=False
            except ValueError:rejected=True
            eq('resealed_bad_ledger_chain_rejected',rejected,True)
    return dict(kind='Independent20kAccountTimingAndChain',synthetic=True,at=datetime.now(timezone.utc).isoformat(),passed=all(x['passed'] for x in checks),checks=checks,count=len(checks),sources={m.__file__:store.filehash(Path(m.__file__)) for m in (account,store)})
if __name__=='__main__':
    import sys
    r=review();p=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(r,f,ensure_ascii=False,indent=2);f.write('\n')
    print(dict(passed=r['passed'],count=r['count'],failures=[x['name'] for x in r['checks'] if not x['passed']]))
