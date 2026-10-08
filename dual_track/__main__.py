"""Manual local research tools. No schedule, market fetch or trading commands."""
import argparse
import json
from .common import ref,reopen
from .forward import fixture_head, append_actual_outcome, validate_prediction


def main():
    parser=argparse.ArgumentParser(description='Local research sidecar: inspect, head, or score an existing signed Snapshot B.')
    parser.add_argument('command',choices=['inspect','head','append-reviewed-outcome'])
    parser.add_argument('--freeze-receipt',required=True)
    parser.add_argument('--store')
    parser.add_argument('--snapshot')
    parser.add_argument('--symbol')
    parser.add_argument('--horizon',type=int)
    parser.add_argument('--expected-head')
    args=parser.parse_args()
    receipt=json.loads(reopen(ref(args.freeze_receipt)))
    prediction_ref=receipt['prediction_ref'];prediction=validate_prediction(json.loads(reopen(prediction_ref)))
    reopen(prediction['source_ref'])
    if args.command=='inspect':
        output={'prediction_ref':prediction_ref,'original_hash_verified':False,'outcomes':'NOT_READ','actual_authority':False}
    elif args.command=='head':
        if not args.store:parser.error('--store required')
        head,seen=fixture_head(args.store,prediction_ref,'ACTUAL_RESEARCH_ONLY')
        output={'head':head,'outcome_count':len(seen),'actual_forward_days_increment':0}
    else:
        if not all((args.store,args.snapshot,args.symbol,args.horizon,args.expected_head)):
            parser.error('store/snapshot/symbol/horizon/expected-head required')
        output=append_actual_outcome(args.store,prediction_ref,args.expected_head,ref(args.snapshot),args.symbol,args.horizon)
    print(json.dumps(output,ensure_ascii=False,sort_keys=True))


if __name__=='__main__':main()
