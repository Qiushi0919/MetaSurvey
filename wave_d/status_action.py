"""Conservative observed-day status and same-provider adjusted-series diagnostics."""
from decimal import Decimal,localcontext,ROUND_HALF_EVEN
from wave_c.core import digest
from wave_c.math import num,text
from wave_c.research import refs

def feature(name,value,unit,formula,rows=(),reasons=(),period=None,state=None):
 return {'name':name,'value':value,'state':state or ('UNKNOWN' if value is None else 'OBSERVED' if formula=='SOURCE_LITERAL' else 'DERIVED'),'unit':unit,'formula':formula,'source_refs':refs(rows),'reason_codes':list(reasons),'period':period}

def complete_set(requests,api):
 qs={q['request_id'].rsplit('-',1)[-1]:q for q in requests if q['api_name']==api}
 if set(qs)!={'MAIN','TERMINAL','REPEAT'}:return False,'STATUS_CAPTURE_INCOMPLETE'
 a,b,c=(qs[k] for k in ('MAIN','TERMINAL','REPEAT'))
 if any(q['response_blocked'] or q['excluded'] for q in (a,b,c)):return False,'STATUS_SCHEMA_OR_SCOPE_NOT_PROVEN'
 if len(a['rows'])==0 or len(a['rows'])>=a['max_rows'] or b['rows']:return False,'STATUS_TRUNCATION_OR_EMPTY_UNPROVEN'
 unique=lambda q:sorted(digest(r['values']) for r in q['rows'])
 if unique(a)!=unique(c) or len(set(unique(a)))!=len(a['rows']):return False,'STATUS_REPLAY_OR_DUPLICATE_UNPROVEN'
 if any(r['values'].get('trade_date')!='20260930' for q in (a,c) for r in q['rows']):return False,'STATUS_DAY_MISMATCH'
 return True,'COMPLETE_OBSERVED_PROVIDER_DAY_SET_NOT_INDEPENDENT_CURRENT_AUTHORITY'

def status_features(observations,requests,symbol):
 out=[];basic=[r for r in observations if r['api_name']=='stock_basic' and r['source_ref']['origin']=='WAVE_D']
 for key,name in [('name','current_observed_name'),('list_status','current_observed_listing'),('industry','current_observed_industry')]:
  values={r['values'].get(key) for r in basic if r['values'].get(key) not in (None,'')}
  out.append(feature(name,next(iter(values)) if len(values)==1 else None,'SOURCE_CURRENT_DECLARATION_NOT_HISTORICAL_PIT','SOURCE_LITERAL',basic,['UNVERIFIED_GATEWAY_CURRENT_DECLARATION_ONLY'],state='CONFLICT' if len(values)>1 else None))
 out.append(feature('historical_industry_membership',None,'UNKNOWN','CURRENT_MEMBERSHIP_CANNOT_BACKFILL_HISTORY',reasons=['HISTORICAL_VISIBILITY_NOT_PROVEN']))
 states=[]
 for api,name in [('stock_st','st_status'),('suspend_d','suspension_status')]:
  complete,reason=complete_set(requests,api)
  main=next((q for q in requests if q['api_name']==api and q['request_id'].endswith('-MAIN')),None)
  present=bool(main and not main['response_blocked'] and any(r['values']['ts_code']==symbol for r in main['rows']))
  # A provider's complete prior-day set is explicitly dated; never today's trading eligibility.
  value='IN_OBSERVED_PROVIDER_DAY_SET' if present else 'NOT_IN_COMPLETE_OBSERVED_PROVIDER_DAY_SET' if complete else None
  proofrows=[r for r in observations if r['api_name']==api]
  out.append(feature(name,value,'PROVIDER_OBSERVED_DAY_MEMBERSHIP_NOT_CURRENT_TRADEABILITY','DAY_SET_COMPLETENESS_AND_MEMBERSHIP',proofrows,[reason,'SOURCE_DAY_20260930_NOT_OCTOBER6'],period='20260930'))
  states.append({'api_name':api,'scope_complete':complete,'negative_status_proven':complete and not present,'source_day':'20260930','reason_code':reason,'formal_admission':'BLOCKED'})
 return out,states

def adjustment_features(observations):
 by={api:[r for r in observations if r['api_name']==api] for api in ('daily','adj_factor')};maps={};conflict=False
 for api,rows in by.items():
  groups={}
  for r in rows:groups.setdefault(r['values']['trade_date'],[]).append(r)
  key='close' if api=='daily' else 'adj_factor';out={}
  for day,rs in groups.items():
   vals={r['values'].get(key) for r in rs}
   if len(vals)!=1 or None in vals:conflict=True
   else:out[day]=rs[0]
  maps[api]=out
 dates=sorted(maps['daily']);aligned=bool(dates) and set(dates)==set(maps['adj_factor']) and not conflict
 evidence=by['daily']+by['adj_factor'];features=[];series=[]
 if aligned:
  with localcontext() as c:
   c.prec=50;c.rounding=ROUND_HALF_EVEN
   anchor=num(maps['adj_factor'][dates[-1]]['values']['adj_factor']);positive=anchor>0 and all(num(maps['adj_factor'][d]['values']['adj_factor'])>0 for d in dates)
   if positive:
    for d in dates:
     bar=maps['daily'][d];factor=maps['adj_factor'][d]
     series.append({'trade_date':d,'raw_close':bar['values']['close'],'source_factor':factor['values']['adj_factor'],'adjusted_close':text(num(bar['values']['close'])*num(factor['values']['adj_factor'])/anchor),'source_refs':refs([bar,factor])})
    value=str(len(series));reason='SAME_PROVIDER_MATHEMATICAL_CONSISTENCY_ONLY_NOT_INDEPENDENT_ACTION_PROOF'
   else:value=None;reason='FACTOR_NONPOSITIVE'
 else:value=None;reason='FACTOR_RAW_DATE_OR_VERSION_CONFLICT'
 features.append(feature('adjusted_series_consistency_sessions',value,'OBSERVED_DATES_NOT_TOTAL_RETURN','RAW_CLOSE_TIMES_FACTOR_DIVIDED_BY_LATEST_OBSERVED_FACTOR',evidence,[reason]))
 features.append(feature('independently_verified_action_reconciliation',None,'UNKNOWN','PRESERVED_WAVE_B_5_AMBIGUITIES_8_NONZERO_DELTAS',evidence,['ACTION_AMBIGUITIES_NOT_RESOLVED','TOLERANCE_POLICY_UNSET_REQUIRED']))
 return features,{'method':'RAW_CLOSE * SOURCE_FACTOR / LATEST_OBSERVED_FACTOR','anchor_date':dates[-1] if dates else None,'source':'SAME_UNVERIFIED_GATEWAY','independent_source_verified':False,'raw_series_overwritten':False,'total_return_claim':False,'series':series,'preserved_ambiguous_actions':5,'preserved_nonzero_references':8,'tolerance_policy':'UNSET_REQUIRED'}
