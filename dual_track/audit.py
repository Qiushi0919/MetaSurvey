"""Separate arithmetic and lineage audit of persisted historical artifacts.

Uses an independently written incremental expanding-label formula. Does not
rerun the writer or select a winning method. Independent-human review is not
implied by this automated check.
"""
import json
from decimal import Decimal,localcontext
from pathlib import Path

from .common import HORIZONS,SYMBOLS,now,ref,reopen,require,write_new


def audit(board_ref,path):
    board=json.loads(reopen(board_ref))
    frozen=json.loads(reopen(board['prediction_ref']))
    labels=json.loads(reopen(board['label_ref']))
    require(labels['prediction_ref']==board['prediction_ref'] and
            frozen['frozen_at']<=labels['revealed_at']<=board['scored_at'],'DT_FREEZE_REVEAL_CLOCK_ORDER')
    predictions={(p['symbol'],p['logical_cutoff_date'],p['horizon']):p for p in frozen['predictions']}
    require(len(predictions)==len(frozen['predictions'])==4905,'DT_PREDICTION_ROWS')
    checked=0;endpoint_checked=0
    for symbol in SYMBOLS:
        input_ref=next(r for r in frozen['direct_source_refs'] if r['path'].endswith('/REPORTS-G4/'+symbol+'.input.json'))
        observed=json.loads(reopen(input_ref))['body']['observations']
        daily={}
        for row in observed:
            if row['api_name']!='daily':continue
            value=row['values'];date=value['trade_date']
            shape=tuple(str(value[k]) for k in ('open','high','low','close','vol'))
            require(date not in daily or daily[date]==shape,'DT_AUDIT_CONFLICT')
            daily[date]=shape
        dates=sorted(daily)
        require(len(dates)==327,'DT_AUDIT_INPUT_COUNT')
        require(all(predictions[(symbol,d,h)]['historical_visibility_proven'] is False for d in dates for h in HORIZONS),'DT_PIT_PROMOTION')
        with localcontext() as ctx:
            ctx.prec=80
            closes=[Decimal(daily[d][3]) for d in dates]
            for horizon in HORIZONS:
                cumulative=Decimal(0)
                for i,date in enumerate(dates):
                    prediction=predictions[(symbol,date,horizon)]
                    if i>=horizon:
                        cumulative+=closes[i]/closes[i-horizon]-1
                        require(Decimal(prediction['center_return_ratio'])==cumulative/Decimal(i-horizon+1),'DT_AUDIT_PREFIX_ARITHMETIC')
                        require(prediction['training_pairs']==i-horizon+1 and prediction['training_end_max']==date,'DT_TRAINING_BOUNDARY')
                    else:require(prediction['state']=='WARMUP' and prediction['center_return_ratio'] is None,'DT_AUDIT_WARMUP')
                    checked+=1
            for label in (r for r in labels['labels'] if r['symbol']==symbol):
                i=dates.index(label['logical_cutoff_date']);h=label['horizon']
                if i+h<len(dates):
                    require(label['endpoint_date']==dates[i+h] and Decimal(label['raw_return_ratio'])==closes[i+h]/closes[i]-1,'DT_AUDIT_LABEL_ENDPOINT')
                    endpoint_checked+=1
                else:require(label['state']=='PENDING','DT_AUDIT_RIGHT_CENSORING')
    return write_new(path,{'version':'1.0.0','kind':'DualTrackArithmeticAudit','audited_at':now(),
        'state':'PASS','board_ref':board_ref,'predictions_checked':checked,'observed_label_endpoints_checked':endpoint_checked,
        'freeze_before_this_run_reveal_verified':True,'historical_first_visibility_proven':False,
        'untouched_oos_proven':False,'independent_human_review':False,
        'actual_signature_positive_path_tested':False,'productionGate':False})
