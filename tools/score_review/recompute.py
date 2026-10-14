"""Independent Fraction arithmetic/direct source row check, not a human signature."""
from pathlib import Path
from fractions import Fraction
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def run():
 reg=json.loads((ROOT/'docs/score-review-v01/Sample-Registry.json').read_text());raw=Path(reg['sample_path']).read_bytes();assert sha(raw)==reg['sample_sha256'];p=json.loads(raw)
 for f in reg['source_files']:assert sha(Path(f['path']).read_bytes())==f['sha256']
 a=p['arithmetic_only'][0];groups={}
 for loc in a['input_locators']:
  raw=Path(loc['raw_ref']['path']).read_bytes();assert sha(raw)==loc['raw_ref']['sha256'];d=json.loads(raw,parse_float=Fraction);row=dict(zip(d['data']['fields'],d['data']['items'][loc['row_ordinal']]))
  assert row['end_date']==loc['period'] and row['ts_code']==p['symbol'] and row['update_flag']==loc['update_flag'];value=Fraction(row['revenue']);assert value==Fraction(loc['value']);groups.setdefault(row['end_date'],set()).add(value)
 assert len(groups)==2 and all(len(v)==1 for v in groups.values());v0=next(iter(groups['20250630']));v1=next(iter(groups['20260630']));exact=(v1/v0-1)*10000
 scaled=abs(exact)*10000;whole,remainder=divmod(scaled.numerator,scaled.denominator);rounded=whole+(2*remainder>=scaled.denominator);text=('-' if exact<0 else '')+str(rounded//10000)+'.'+str(rounded%10000).zfill(4);assert text==a['value']
 assert all(x['score_input_value'] is None for x in p['field_matrix']);assert len(p['field_matrix'])==18
 results=[x for x in p['objects'] if x['kind']=='ScoreResult'];assert len(results)==2
 for s in results:assert s['state']=='BLOCKED' and s['final_score'] is s['raw_score'] is s['risk_deduction'] is None and all(x is None for x in s['components'].values())
 report={'version':'1.0.0','scope':'INDEPENDENT_IMPLEMENTATION_READBACK_NOT_HUMAN_SIGNOFF','checked_at':datetime.now(timezone.utc).isoformat(),'sample_sha256':reg['sample_sha256'],'implementation_sha256':sha(Path(__file__).read_bytes()),'producer_implementation':'Python Decimal / Node graph','independent_implementation':'Python Fraction exact rational / direct original row locators','original_rows_checked':len(a['input_locators']),'original_files_checked':len(reg['source_files']),'half_year_yoy_arithmetic_match':True,'raw_values_exported':False,'revision_variants_preserved':True,'revision_chain_proven':False,'score_input_rows_null':18,'score_results_blocked':2,'real_scores_computed':0,'upstream_graph':'Separately recomputed by Node validateGraph on workbench reads','economic_method_approval':False}
 (ROOT/'docs/score-review-v01/Independent-Recompute.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':run()
