"""Reproducible closed metadata schemas; never run implicitly in checks."""
import json
from pathlib import Path
from .common import BOUNDARIES, ROOT, SYMBOLS
from .forward import ENTRY_FIELDS, ORIGINAL_HASH


def obj(properties):
    return {'type':'object', 'additionalProperties':False, 'required':list(properties), 'properties':properties}


def schemas():
    string = {'type':'string'}
    dec = {'type':'string', 'pattern':r'^-?(0|[1-9][0-9]*)(\.[0-9]+)?$', 'maxLength':110,
           'description':'Exact Decimal lexeme; no JSON float; percentages are percent, error is percentage points.'}
    nullable_dec = {'anyOf':[dec, {'type':'null'}]}
    digest = {'type':'string', 'pattern':r'^sha256:[0-9a-f]{64}$'}
    reference = obj({'path':{'type':'string', 'pattern':'^/'}, 'bytes':{'type':'integer', 'minimum':1}, 'sha256':digest})
    symbol = {'enum':list(SYMBOLS)}
    horizon = {'enum':[1,5,10]}
    date = {'type':'string', 'format':'date'}
    clock = {'type':'string', 'format':'date-time', 'description':'Offset required; UTC persisted, Asia/Shanghai session boundary.'}
    entry = obj({'symbol':symbol,'horizon':horizon,'target_session':date,'base_close_cny':dec,
        'low_return_percent':dec,'high_return_percent':dec,'center_return_percent':dec,
        'd10_positive_probability_percent':nullable_dec,'quoted_d10_center_price_cny':nullable_dec,'derived_center_price_cny':dec})
    prediction = obj({'version':{'const':'1.0.0'},'kind':{'const':'ForwardPrediction'},
        'prediction_id':{'const':'ForwardPrediction-v1-OWNER_TEXT_IMPORT'},
        'namespace':{'const':'FORWARD_RESEARCH_ONLY:CORE_40:OWNER_TEXT_V1'},'boundaries':{'const':BOUNDARIES},
        'producer':{'const':'OWNER_TEXT_CHATGPT_ASSISTED_UNVERIFIED'},'source_ref':reference,
        'original_artifact_sha256_claim':{'const':'sha256:'+ORIGINAL_HASH},
        'original_artifact_state':{'const':'ORIGINAL_NOT_PROVIDED_HASH_NOT_VERIFIED'},'frozen_at':clock,
        'timestamp_evidence':{'const':'LOCAL_HOST_CLOCK_NO_INDEPENDENT_TIMESTAMP'},'base_session':{'const':'2026-09-30'},
        'base_price_evidence':{'const':'OWNER_SUPPLIED_RAW_CLOSE_ASSUMPTION_UNVERIFIED'},
        'target_mapping_evidence':{'const':'OWNER_PLANNED_SESSIONS_NOT_ACTUAL_OPEN_WITNESS'},
        'entries':{'type':'array','minItems':9,'maxItems':9,'items':entry},
        'd10_ordinal_order':{'const':list(SYMBOLS)},'d10_centers_tied':{'const':['600312.SH','603228.SH']},
        'probability_calibrated':{'const':False},'bands_calibrated':{'const':False},'version_parent':{'type':'null'},
        'invalidation':{'const':['FILE_HASH_CHANGED','BASE_ASSUMPTION_DISPROVED','TARGET_SESSION_MAPPING_DISPROVED','SOURCE_TEXT_CHANGED','BOUNDARY_CHANGED']},
        'reason_codes':{'const':['ORIGINAL_ARTIFACT_MISSING','NEW_OWNER_TEXT_IMPORT','SUBJECTIVE_PROBABILITY_NOT_WIN_RATE','NO_ACTUAL_MARKET_OUTCOMES']}})
    score_properties = {'symbol':symbol,'horizon':horizon,'target_session':date,
        'realized_return_percent':dec,'forecast_error_percent_points':dec,
        'direction_hit':{'type':'boolean'},'range_hit':{'type':'boolean'},'mae_percent':nullable_dec,'mfe_percent':nullable_dec,
        'zero_direction_policy':{'const':'THREE_WAY_SIGN_ZERO_IS_NEUTRAL'},'action_reconciliation':{'const':'UNKNOWN'},
        'metric_scope':{'const':'SYNTHETIC_RAW_PRICE_PATH_NOT_EXECUTION_PNL'}}
    synthetic = obj(score_properties)
    actual = obj({**score_properties,'metric_scope':{'const':'CURRENT_REVIEWED_RAW_PRICE_NOT_EXECUTION_PNL'},
        'snapshot_ref':reference,'base_raw_ref':reference,'outcome_raw_ref':reference,'clock_ref':reference,'scored_at':clock,
        'capture_signature_verified':{'const':True},'independent_review_signature_verified':{'const':True},
        'base_assumption_matches_pinned_raw':{'const':True},'source_admission':{'const':'BLOCKED'},
        'path_metric_state':{'enum':['D1_RAW_PATH_OBSERVED','COMPLETE_PATH_CALENDAR_AND_ORIGINALS_REQUIRED']},
        'horizon_mapping':{'const':'OWNER_FIXED_TARGET_DATE_NOT_HISTORICAL_SESSION_AUTHORITY'},
        'actual_authority':{'const':False},'actual_forward_days_increment':{'const':0},
        'reason_codes':{'const':['SOURCE_PROVIDER_LICENSE_ACTIONS_UNRESOLVED','NO_EXECUTION_OR_PROFIT_AUTHORITY']}})
    outcome = obj({'version':{'const':'1.0.0'},'kind':{'const':'ForwardOutcome'},
        'mode':{'enum':['SYNTHETIC_FIXTURE','ACTUAL_RESEARCH_ONLY']},'sequence':{'type':'integer','minimum':1,'maximum':9},
        'previous_hash':digest,'prediction_sha256':digest,'score':{'oneOf':[synthetic,actual]},'hash':digest})
    outcome['allOf'] = [{'if':{'properties':{'mode':{'const':'ACTUAL_RESEARCH_ONLY'}}},
        'then':{'properties':{'score':actual}},'else':{'properties':{'score':synthetic}}}]
    for name, schema in [('ForwardPrediction',prediction),('ForwardOutcome',outcome)]:
        schema.update({'$schema':'http://json-schema.org/draft-07/schema#',
            '$id':f'urn:metasurvey:dual-track:{name}:1.0.0', 'title':name+' research sidecar 1.0.0',
            'description':'Closed independent research metadata. Runtime also verifies hash, source originals, scope, temporal bounds and signatures. Never native trading authority.'})
    return {'ForwardPrediction-v1.schema.json':prediction,'ForwardOutcome-v1.schema.json':outcome}


if __name__=='__main__':
    directory = ROOT/'contracts/dual-track'
    directory.mkdir(parents=True, exist_ok=True)
    for name,schema in schemas().items():
        with (directory/name).open('x') as stream:
            json.dump(schema,stream,ensure_ascii=False,sort_keys=True,indent=2)
            stream.write('\n')
