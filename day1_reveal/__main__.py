"""Explicit one-shot research entry; never starts a collector or next session."""
import argparse
import json
from .integrity import check_day0
from .reveal import journal_head,append_day1,verify_attestation
from dual_track.common import ref

p=argparse.ArgumentParser(description='Read-only Day0 check / explicitly gated Day1 journal')
s=p.add_subparsers(dest='operation',required=True)
s.add_parser('check')
h=s.add_parser('head');h.add_argument('journal')
a=s.add_parser('append');a.add_argument('journal');a.add_argument('actual_store')
a.add_argument('snapshot');a.add_argument('symbol',choices=['603993.SH','600312.SH','603228.SH'])
a.add_argument('--expected-head',required=True)
v=s.add_parser('verify-attestation');v.add_argument('body');v.add_argument('signature')
v.add_argument('role',choices=['HUMAN_USER','INDEPENDENT_REVIEWER'])
args=p.parse_args()
if args.operation=='check': result=check_day0()
elif args.operation=='head':
    head,seen=journal_head(args.journal);result={'head':head,'scored_symbols':sorted(seen)}
elif args.operation=='append':
    result=append_day1(args.journal,args.expected_head,args.actual_store,ref(args.snapshot),args.symbol)
else: result=verify_attestation(ref(args.body),ref(args.signature),args.role)
print(json.dumps(result,ensure_ascii=False,sort_keys=True))
