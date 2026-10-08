"""Action reconciliation mathematics; never declares actual factors authoritative."""
from decimal import localcontext, ROUND_HALF_EVEN
from copy import deepcopy
from .common import *

TREATMENTS=('RAW_UNADJUSTED','FACTOR_SENSITIVITY','RAW_WITH_SYNTHETIC_ENTITLEMENT')
def reconcile_fixture(x):
    keys(x,('provenance','symbol','treatment','raw_price','factor','anchor_factor','cash_dividend_per_share','share_multiplier','money_unit','rounding','tolerance','source_refs','credits_applied'))
    require(x['provenance']=='SYNTHETIC_NOT_OWNER_POLICY' and x['symbol'] in SYMBOLS,'PREP_ACTION_FIXTURE_REQUIRED')
    require(x['treatment'] in TREATMENTS and type(x['credits_applied']) is bool,'PREP_ACTION_TREATMENT_INVALID')
    require(x['money_unit']=='CNY_DECIMAL' and x['rounding']=='ROUND_HALF_EVEN','PREP_ACTION_UNITS_UNSET')
    refs=x['source_refs'];require(type(refs) is list and refs,'PREP_ACTION_SOURCE_REQUIRED')
    for r in refs:hash_value(r)
    p=decimal_string(x['raw_price']);f=decimal_string(x['factor']);a=decimal_string(x['anchor_factor']);d=decimal_string(x['cash_dividend_per_share']);m=decimal_string(x['share_multiplier']);t=decimal_string(x['tolerance'])
    require(p>0 and f>0 and a>0 and m>0,'PREP_ACTION_POSITIVE_REQUIRED')
    require(not(x['treatment']=='FACTOR_SENSITIVITY' and x['credits_applied']),'PREP_DOUBLE_ACTION_BLOCKED')
    require(x['treatment']=='RAW_WITH_SYNTHETIC_ENTITLEMENT' or not x['credits_applied'],'PREP_ACTION_UNEXPECTED_CREDIT')
    require(x['treatment']!='RAW_WITH_SYNTHETIC_ENTITLEMENT' or x['credits_applied'],'PREP_ACTION_CREDIT_MISSING')
    with localcontext() as c:
        c.prec=100;c.rounding=ROUND_HALF_EVEN
        value=p if x['treatment']=='RAW_UNADJUSTED' else p*f/a if x['treatment']=='FACTOR_SENSITIVITY' else p*m+d
        return seal({'version':VERSION,'status':'FIXTURE_ONLY','value':format(value,'f'),'unit':'CNY_DECIMAL','source_refs':deepcopy(refs),'tolerance':format(t,'f'),'authoritative_adjustment':False,'historical_visibility_proven':False,'live_authority':False,'actual_cash_entitlement':False})

def actual_readiness(evidence):
    require(evidence['preserved_multi_original_action_ambiguities']==5 and evidence['preserved_nonzero_pre_close_deltas']==8,'PREP_ACTION_BASELINE_DRIFT')
    require(evidence['tolerance']==UNSET and evidence['source_rounding_policy']==UNSET,'PREP_ACTION_POLICY_PROMOTION')
    return {'state':'BLOCKED','preserved_ambiguous_actions':5,'preserved_nonzero_pre_close_deltas':8,'price_paths':['RAW_UNADJUSTED','FACTOR_SENSITIVITY'],'same_provider_factor_authoritative':False,'factor_plus_cash_credit':'FORBIDDEN','actual_entitlement_credits':0,'tolerance':UNSET,'source_rounding':UNSET,'share_quantity_rounding':UNSET,'cash_dividend_units':'UNVERIFIED','needs_independent_action_evidence':True,'revision_resolution':'UNSET_REQUIRED','live_authority':False}
