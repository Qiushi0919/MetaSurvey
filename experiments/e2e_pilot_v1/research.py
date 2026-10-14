"""Isolated current-observed experiment. Recompute every displayed score from inputs.
No source certification, order authority, historical PIT or probability is inferred.
"""
from pathlib import Path
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from datetime import datetime
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
NAMESPACE='EXPERIMENT:CORE40:E2E_PILOT_V1'
SYMBOLS=('603228.SH','002463.SZ','002916.SZ','600312.SH','601179.SH','002028.SZ','603993.SH','601899.SH','600362.SH')

def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
def seal(value):return digest(canonical({k:v for k,v in value.items() if k!='content_hash'}))
def exact(x):
 if type(x) is not str:raise ValueError('DECIMAL_STRING_REQUIRED')
 d=Decimal(x)
 if not d.is_finite() or len(d.as_tuple().digits)>40 or abs(d.as_tuple().exponent)>30:raise ValueError('DECIMAL_INVALID')
 return d

def score(value,anchor):
 with localcontext() as c:
  c.prec=40;c.rounding=ROUND_HALF_EVEN
  lo,hi=map(Decimal,anchor)
  return format((min(Decimal(1),max(Decimal(0),(value-lo)/(hi-lo)))*100).quantize(Decimal('.0001')),'f')

def avg(values):
 if not values or any(v is None for v in values):return None
 with localcontext() as c:
  c.prec=40;c.rounding=ROUND_HALF_EVEN
  return format((sum(map(Decimal,values))/len(values)).quantize(Decimal('.0001')),'f')

def fact_value(company,key,cutoff):
 f=company.get('facts',{}).get(key)
 if not isinstance(f,dict) or f.get('value') is None:raise ValueError('MISSING_'+key.upper())
 if f.get('unit')!='CNY' or f.get('period')!=('FY2024' if key=='prior_revenue' else 'FY2025'):raise ValueError('FACT_UNIT_OR_PERIOD')
 if f.get('consolidation')!='CONSOLIDATED_GROUP':raise ValueError('CONSOLIDATION_MISMATCH')
 if not f.get('source_id') or not isinstance(f.get('page'),int) or f['page']<1 or not f.get('location'):raise ValueError('FACT_LOCATION_REQUIRED')
 if f.get('historical_visibility_proven') is not False:raise ValueError('CURRENT_ONLY_FACT_REQUIRED')
 for field in ('retrieved_at','available_at'):
  t=datetime.fromisoformat(f[field]); end=datetime.fromisoformat(cutoff)
  if t.tzinfo is None or end.tzinfo is None or t>end:raise ValueError('FUTURE_OR_NAIVE_FACT_CLOCK')
 if datetime.fromisoformat(f['available_at'])<datetime.fromisoformat(f['retrieved_at']):raise ValueError('AVAILABLE_BEFORE_OBSERVED')
 if f.get('text_numeric_presence_verified') is not True:raise ValueError('ORIGINAL_TABLE_UNVERIFIED')
 return exact(f['value'])

def financial(company,cfg,cutoff):
 out=[]
 formulas={'revenue_growth':('revenue','prior_revenue'),'cash_conversion':('operating_cashflow','net_profit'),'net_margin':('net_profit','revenue')}
 for name,(num,den) in formulas.items():
  row={'id':name,'label':{'revenue_growth':'营收同比','cash_conversion':'经营现金流/合并净利润','net_margin':'合并净利率'}[name],'formula':f'{num}/{den}'+('-1' if name=='revenue_growth' else ''),'unit':'RATIO','value':None,'score':None,'state':'BLOCKED','reasons':[],'evidence':[company.get('facts',{}).get(k,{'missing':k}) for k in (num,den)]}
  try:
   a,b=fact_value(company,num,cutoff),fact_value(company,den,cutoff)
   if b<=0:raise ValueError('NONPOSITIVE_DENOMINATOR')
   with localcontext() as c:
    c.prec=40;c.rounding=ROUND_HALF_EVEN
    v=a/b-(1 if name=='revenue_growth' else 0)
    row.update(value=format(v,'f'),score=score(v,cfg['anchors'][name]),state='COMPUTED_CURRENT_OBSERVED')
  except (ValueError,KeyError,TypeError) as e:row['reasons']=[str(e)]
  out.append(row)
 return out

def evaluate(financial_inputs,cfg):
 if financial_inputs.get('kind')!='E2EPilotFinancialInputs' or financial_inputs.get('version')!='1.0.0':raise ValueError('INPUT_VERSION')
 cutoff=financial_inputs['created_at'];companies=financial_inputs['companies']
 if financial_inputs.get('method_sha256')!=hashlib.sha256((ROOT/'experiments/e2e_pilot_v1/method.json').read_bytes()).hexdigest():raise ValueError('INPUT_METHOD_BINDING')
 sources={s['source_id']:s for s in financial_inputs['sources']}
 if len(sources)!=9:raise ValueError('SOURCE_UNIVERSE')
 for co in companies:
  for key,f in co.get('facts',{}).items():
   if f.get('value') is None:continue
   source=sources.get(f.get('source_id'),{})
   if source.get('symbol')!=co['symbol'].split('.')[0] or source.get('sha256')!=f.get('revision_version'):raise ValueError('FACT_SOURCE_BINDING')
   if f.get('retrieved_at')!=source.get('retrieved_at') or f.get('available_at')!=source.get('available_at'):raise ValueError('FACT_CLOCK_BINDING')
   if not source.get('url','').startswith('https://') or source.get('historical_visibility_proven') is not False:raise ValueError('SOURCE_SCOPE')
   vals=[exact(x) for x in f.get('source_components',[])]
   if not vals or sum(vals)!=exact(f['value']):raise ValueError('SOURCE_COMPONENT_ARITHMETIC')
 if len(companies)!=9 or {c['symbol'] for c in companies}!=set(SYMBOLS):raise ValueError('FIXED_UNIVERSE_REQUIRED')
 sectors=[];stocks=[]
 for spec in cfg['universe']:
  members=[]
  for member in spec['members']:
   co=next(c for c in companies if c['symbol']==member['symbol'])
   if co['sector']!=spec['id']:raise ValueError('SECTOR_MEMBERSHIP_MISMATCH')
   components=financial(co,cfg,cutoff);fund=avg([x['score'] for x in components])
   stocks.append({'symbol':co['symbol'],'name':member['name'],'sector':spec['id'],'components':components,'financial_proxy_subtotal':fund,'fundamental_factor_score':fund,'total':None,'state':'PARTIAL_CURRENT_RESEARCH' if fund is not None else 'BLOCKED','reasons':['MISSING_SECTOR_BUSINESS_SHARE_CATALYST_TREND_VALUATION_LIQUIDITY_EVIDENCE_FACTOR','APPLICABLE_COMPANY_RISK_UNKNOWN'],'business_evidence':co.get('business_evidence'), 'risk':{'concentration':'UNKNOWN','leverage':'UNKNOWN','uncertainty':'UNKNOWN'},'quality_not_timing':True,'account_affordability':'NOT_EVALUATED_NO_ADMITTED_PRICE'})
   members.append(stocks[-1])
  comps=[{'id':name,'label':name,'score':avg([next(x['score'] for x in co['components'] if x['id']==name) for co in members]),'formula':'equal arithmetic mean of all3 fixed members; incomplete means NULL','state':'COMPUTED_CURRENT_OBSERVED' if all(next(x['score'] for x in co['components'] if x['id']==name) is not None for co in members) else 'BLOCKED'} for name in cfg['sector_dimensions']]
  subtotal=avg([x['score'] for x in comps])
  sectors.append({'id':spec['id'],'name':spec['name'],'members':[x['symbol'] for x in members],'method':'SAMPLE_FINANCIAL_HEALTH_V1','components':comps,'financial_proxy_subtotal':subtotal,'total':None,'state':'PARTIAL_CURRENT_RESEARCH' if subtotal is not None else 'BLOCKED','reasons':['SECTOR_THESIS_AND_ADVERSE_AUDIT_BREADTH_NOT_VERIFIED'],'sample_not_industry':True,'content_hash':None})
  sectors[-1]['content_hash']=seal(sectors[-1])
 for co in stocks:
  upstream=next(x for x in sectors if x['id']==co['sector'])
  co['upstream_sector_ref']={'id':upstream['id'],'content_hash':upstream['content_hash']}
  co['factors']={k:{'weight_percent':w,'score':co['fundamental_factor_score'] if k=='fundamental' else None,'state':'COMPUTED_CURRENT_OBSERVED' if k=='fundamental' and co['fundamental_factor_score'] is not None else 'BLOCKED'} for k,w in cfg['stock_weights'].items()}
  co['selection']='NOT_ELIGIBLE_INCOMPLETE_TOTAL_AND_RISK';co['content_hash']=seal(co)
 return {'sectors':sectors,'companies':stocks}

def validate_run(package,root=ROOT):
 """A pinned reader separately checks source files. This validates complete value lineage."""
 cfgraw=(root/'experiments/e2e_pilot_v1/method.json').read_bytes();protoraw=(root/'experiments/e2e_pilot_v1/protocol.json').read_bytes();cfg=json.loads(cfgraw)
 if package.get('kind')!='E2EPilotRun' or package.get('version')!='1.0.0' or package.get('namespace')!=NAMESPACE or package.get('experiment_id')!='CORE40_E2E_PILOT_V1':raise ValueError('RUN_IDENTITY')
 if package.get('method_hash')!=digest(cfgraw) or package.get('protocol_hash')!=digest(protoraw):raise ValueError('METHOD_BINDING')
 if package.get('method_version')!='SAMPLE_FINANCIAL_HEALTH_V1 / COMPANY_SEVEN_FACTOR_V1_PARTIAL':raise ValueError('RESULT_METHOD_VERSION')
 if datetime.fromisoformat(package['recorded_at'])<datetime.fromisoformat(package['financial_inputs']['created_at']):raise ValueError('RESULT_BEFORE_INPUT')
 if package.get('content_hash')!=seal(package):raise ValueError('RUN_HASH')
 if package.get('result_type')!='CURRENT_OBSERVED_EXPERIMENTAL_RESEARCH' or package.get('diagnostic_case',{}).get('label')!='HISTORICAL_DIAGNOSTIC':raise ValueError('REAL_SYNTHETIC_SCOPE_MISMATCH')
 if package.get('productionGate') is not False or package.get('historical_visibility_proven') is not False:raise ValueError('AUTHORITY_ESCALATION')
 if datetime.fromisoformat(package['recorded_at'])<datetime.fromisoformat(cfg['frozen_at']):raise ValueError('FREEZE_BEFORE_RESULT')
 computed=evaluate(package['financial_inputs'],cfg)
 if any(package.get(k)!=computed[k] for k in ('sectors','companies')):raise ValueError('SCORE_RECOMPUTATION_MISMATCH')
 from experiments.e2e_pilot_v1.execution import run_diagnostic
 diagnostic=run_diagnostic(package['diagnostic_case'])
 if package.get('diagnostic')!=diagnostic:raise ValueError('DIAGNOSTIC_RECOMPUTATION_MISMATCH')
 from experiments.e2e_pilot_v1.execution import build_portfolio
 p=build_portfolio([],10000000,[],10000000,json.loads(protoraw)['fee_schedule'],'2026-10-14')
 p.update(state='BLOCKED_NO_COMPLETE_CANDIDATES_OR_ADMITTED_PRICE',cash_cents=p['remaining_cash_cents'],positions=[],planned_orders=p['plans'],risk_budget_cents=100000,account_kind='VIRTUAL_EXPERIMENT_NOT_OWNER_ACCOUNT',builder_called=True,eligibility_rejections=[{'symbol':x['symbol'],'reason':'FULL_SCORE_AND_EXECUTION_INPUTS_INCOMPLETE'} for x in computed['companies']])
 if package.get('portfolio')!=p:raise ValueError('PORTFOLIO_BINDING')
 keep=('experiment_id','namespace','run_id','recorded_at','method_version','result_type','sectors','companies','portfolio','diagnostic','limitations','method_hash','protocol_hash','content_hash')
 return {k:package[k] for k in keep}
