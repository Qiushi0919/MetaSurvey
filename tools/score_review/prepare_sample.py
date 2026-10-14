"""One bounded LOCAL_ONLY archive review. No collector/imported live clients or secrets."""
from pathlib import Path
from decimal import Decimal, localcontext, ROUND_HALF_UP
from datetime import datetime, timezone
import argparse, hashlib, json, os, subprocess
ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=Path('/Users/qiushi/投资研究/.p1b-archives/wave-d-20261006')
OUT=Path('/Users/qiushi/投资研究/.p1b-archives/score-review-20261014')
SYMBOL='603228.SH'
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def dump(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2);f.write('\n')
 os.chmod(p,0o600)
def checked(p,expected):
 if p.resolve()!=p or not p.is_relative_to(ARCHIVE):raise ValueError('UNSAFE_ARCHIVE')
 b=p.read_bytes()
 if sha(b)!=expected:raise ValueError('ORIGINAL_HASH_MISMATCH')
 return json.loads(b,parse_float=str),{'path':str(p),'sha256':sha(b),'bytes':len(b)}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--node',default='node');args=parser.parse_args()
 if (OUT/'Sample-r2.json').exists():raise ValueError('PRESERVE_EXISTING_SAMPLE')
 refs=[];captures={}
 for name in ['capture-ref.json','full-statements-ref.json']:
  pin=json.loads((ROOT/'docs/wave-d'/name).read_text());c,r=checked(Path(pin['path']),pin['sha256']);refs.append(r);captures[name]=c
 selected={}
 for capture_name,request_id in [('capture-ref.json','stock_basic-'+SYMBOL),('capture-ref.json','fina_indicator-'+SYMBOL),('full-statements-ref.json','FULL-income-'+SYMBOL)]:
  q=next(q for q in captures[capture_name]['requests'] if q['request_id']==request_id);raw,r=checked(Path(q['raw_ref']),q['raw_sha256']);refs.append(r)
  rows=[dict(zip(raw['data']['fields'],v)) for v in raw['data']['items']];selected[request_id]=(q,r,rows)
 q,rawref,income=selected['FULL-income-'+SYMBOL]
 periods=['20250630','20260630'];values=[];locators=[]
 for period in periods:
  matches=[(i,x) for i,x in enumerate(income) if x['end_date']==period and x['report_type']=='1' and x['ts_code']==SYMBOL]
  if not matches or len({str(row['revenue']) for _,row in matches})!=1:raise ValueError('AMBIGUOUS_COMPARABLE_HALF_YEAR')
  values.append(Decimal(str(matches[0][1]['revenue'])))
  for i,row in matches:locators.append({'period':period,'row_ordinal':i,'field':'revenue','raw_ref':rawref,'event_time':None,'published_at':None,'reported_ann_date':row['f_ann_date'],'available_at':q['available_at'],'retrieved_at':q['retrieved_at'],'unit':'PROVIDER_REPORTED_CNY_YUAN_NOT_INDEPENDENTLY_CERTIFIED','value':str(row['revenue']),'update_flag':row['update_flag']})
 with localcontext() as ctx:
  ctx.prec=40;yoy=((values[1]/values[0]-1)*10000).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP)
 cfg=json.loads((ROOT/'experiments/sector_stock_v0/config.json').read_text())
 metrics=cfg['sector_metrics']+[k for f in cfg['stock_factors'] for k in f['inputs']]
 gaps={'revenue_growth_bps':['HALF_YEAR_YOY_IS_NOT_TTM','UNIT_NOT_INDEPENDENTLY_CERTIFIED','PUBLICATION_INSTANT_UNKNOWN','MULTIPLE_UPDATE_FLAGS_SAME_REVENUE_REVISION_CHAIN_UNPROVEN'], 'cash_conversion':['TTM_CASHFLOW_PROFIT_BRIDGE_MISSING'], 'roic_spread_bps':['M01_CAPITAL_COST_NOT_APPROVED','ROIC_BRIDGE_MISSING'], 'sector_revenue_share':['SEGMENT_REVENUE_MEMBERSHIP_NOT_VERIFIED'], 'catalyst_balance':['BODY_SEARCH_WINDOW_AND_TWO_CODER_RECORDS_MISSING'], 'stock_rs20_bps':['SECTOR_TOTAL_RETURN_AND_ACTION_BRIDGE_MISSING'], 'stock_valuation_percentile':['PIT_MULTIPLE_HISTORY_AND_METHOD_MISSING'], 'median_turnover_cny':['AMOUNT_UNIT_AND_COMPLETE_20_SESSION_WINDOW_UNVERIFIED'], 'verified_fact_share':['FACT_DENOMINATOR_AND_REVIEW_NOT_FROZEN']}
 matrix=[]
 for metric in metrics:
  matrix.append({'metric':metric,'unit':cfg['metrics'][metric]['unit'],'calculation':cfg['metrics'][metric]['definition'],'score_input_value':None,'status':'BLOCKED','originals':locators if metric=='revenue_growth_bps' else [],'gaps':gaps.get(metric,['SECTOR_UNIVERSE_MEMBERSHIP_AND_ORIGINAL_SERIES_MISSING','INSUFFICIENT_PEERS'])+['OWNER_ECONOMIC_METHOD_PENDING']})
 now=datetime.now(timezone.utc).isoformat()
 sample={'kind':'CurrentObservationScoreReviewPackage','version':'0.1.0-admission','symbol':SYMBOL,'sector_id':'PROPOSED:PCB_MANUFACTURING','peer_count':1,'trace_id':'real-archive-review-20261014-pcb','recorded_at':now,'decision_cutoff':now,'archive_observation_cutoff':'2026-10-06T07:50:49.627682Z','scope':'CURRENT_ARCHIVE_REVIEW_NOT_NEW_MARKET_OBSERVATION','sector_definition':'Proposed PCB manufacturing: issuers with verified PCB manufacturing segment; membership/revenue threshold not approved. This sample does not establish sector membership or represent an industry basket.','selection_basis':'Existing allowed three-stock scope; PCB manufacturing offers a specific product boundary. Selected for field/segment audit, not score or observed performance. Only one eligible engineering subject; no universe expansion.','method_state':'OWNER_PENDING','formal_candidate':False,'can_produce_order':False,'historical_visibility_proven':False,'local_only':True,'field_matrix':matrix,'source_files':refs,'arithmetic_only':[{'id':'reported_half_year_revenue_yoy','formula':'(revenue_20260630/revenue_20250630-1)*10000','value':str(yoy),'unit':'BPS','input_locators':locators,'status':'ARITHMETIC_ONLY_NOT_A_SCORE_NOT_TTM','original_truth_or_license_certified':False}]}
 js="import fs from 'node:fs';import {blockedGraph,seal,adapterHash,engineHash,configHash,candidateHash,applicabilityHash,applicability,validatePackage} from './experiments/sector_stock_v01/admission.mjs';let p=JSON.parse(fs.readFileSync(0,'utf8'));Object.assign(p,{config_sha256:configHash,engine_sha256:engineHash,adapter_sha256:adapterHash,candidate_sha256:candidateHash,applicability_sha256:applicabilityHash,applicability:applicability()});p.objects=blockedGraph(p);p=seal(p);validatePackage(p);process.stdout.write(JSON.stringify(p));"
 r=subprocess.run([args.node,'--input-type=module','-e',js],cwd=ROOT,input=json.dumps(sample),text=True,capture_output=True,check=True);sample=json.loads(r.stdout);dump(OUT/'Sample-r2.json',sample)
 pins={f:sha((ROOT/f).read_bytes()) for f in ['experiments/sector_stock_v0/config.json','experiments/sector_stock_v0/engine.mjs','experiments/sector_stock_v01/admission.mjs','experiments/sector_stock_v01/config.json','experiments/sector_stock_v01/applicability.mjs','tools/score_review/prepare_sample.py']}
 pins.update({str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in (ROOT/'contracts/sector-stock-v0').glob('*.schema.json')})
 registry={'kind':'LocalScoreReviewRegistry','version':'1.0.0','sample_path':str(OUT/'Sample-r2.json'),'sample_sha256':sha((OUT/'Sample-r2.json').read_bytes()),'sample_content_hash':sample['content_hash'],'code_pins':pins,'source_files':refs,'method_state':'OWNER_PENDING','label':'LOCAL_ONLY_CURRENT_OBSERVATION_NOT_TRADEABLE','declared_results':{'full_scores':0,'score_components':0,'arithmetic_only_checks':1,'peers':1},'recorded_at':now,'archive_observation_cutoff':sample['archive_observation_cutoff']}
 (ROOT/'docs/score-review-v01/Sample-Registry.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'sample_path':str(OUT/'Sample-r2.json'),'field_rows':len(matrix),'raw_files_verified':len(refs),'real_complete_scores':0}))
if __name__=='__main__':main()
