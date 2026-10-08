"""Freeze fair evaluation requirements, not an economic trading strategy."""
from .common import *
from copy import deepcopy

PARAMETERS={
 'entry_rule':'VERSIONED_RULE','exit_rule':'VERSIONED_RULE','feature_windows':'SESSIONS',
 'history_start':'DATE','history_end':'DATE','history_years':'YEARS',
 'benchmark':'INDEX_ID_AND_TOTAL_RETURN_TREATMENT','minimum_excess_return':'DECIMAL_RATIO',
 'maximum_drawdown':'DECIMAL_RATIO','minimum_trade_count':'INTEGER',
 'maximum_trade_frequency':'TRADES_PER_YEAR','economic_goal':'OWNER_DEFINED',
 'account_policy':'VERSION_HASH','cost_policy':'DATED_VERSION_HASH','risk_policy':'VERSION_HASH',
 'calendar_policy':'DATED_VERSION_HASH','initial_capital':'CNY_MINOR_INTEGER_STRING',
 'position_limit':'DECIMAL_RATIO','total_exposure_limit':'DECIMAL_RATIO',
 'kill_policy':'VERSION_HASH','allow_flat':'BOOLEAN', 'slippage_policy':'VERSION_HASH',
 'train_validation_test_split':'CHRONOLOGICAL_DATES','out_of_sample_protocol':'FROZEN_RULE',
 'multiple_testing_policy':'FROZEN_RULE','rebalance_frequency':'SESSIONS',
 'evaluation_cutoff':'EXACT_INSTANT','minimum_commission':'CNY_MINOR_INTEGER_STRING',
 'commission':'DECIMAL_RATIO','sell_tax':'DATED_DECIMAL_RATIO'}
def frozen_spec():
    return {'version':VERSION,'state':'BLOCKED_UNSET_REQUIREMENTS','purpose':'EVALUATION_REQUIREMENTS_ONLY','owner_strategy_selected':False,'diagnostic_ma20_ma60_is_owner_strategy':False,'optimized_against_wave_e':False,'parameters':{k:{'value':UNSET,'unit':u,'required':True} for k,u in PARAMETERS.items()},'evaluation_protocol':{'freeze_before_reveal':True,'next_observed_open_after_decision':True,'same_bar_fills':False,'t_plus_one':True,'fees_in_affordability':True,'raw_adjusted_isolated':True,'no_survivorship_backfill':True,'historical_pit_required':True,'terminal_open_positions_explicit':True,'no_forced_liquidation_default':True,'diagnostic_profit_is_evidence':False},'invalidation':['STRATEGY_POLICY_VERSION_CHANGED','EVALUATION_POLICY_VERSION_CHANGED','SOURCE_HISTORY_CLOCK_CHANGED','UNSET_REQUIRED','DIAGNOSTIC_TO_STRATEGY_PROMOTION'],'live_authority':False}
def evaluate_strategy(spec,result):
    # No performance numbers or a caller-labelled policy unlock this phase.
    canonical(spec);canonical(result)
    blocked('PREP_FORMAL_STRATEGY_EVALUATION_NOT_AUTHORIZED')
def fixture_freeze(x):
    keys(x,('provenance','rules','evaluation','frozen_at','reveal_at'))
    require(x['provenance']=='SYNTHETIC_NOT_OWNER_POLICY','PREP_OWNER_POLICY_REQUIRED')
    require(timestamp(x['frozen_at'])<timestamp(x['reveal_at']),'PREP_FREEZE_BEFORE_REVEAL')
    require(type(x['rules']) is dict and type(x['evaluation']) is dict and x['rules'] and x['evaluation'],'PREP_FIXTURE_POLICY_EMPTY')
    require(UNSET not in str(x),'PREP_UNSET_BLOCKED')
    return seal({'version':VERSION,'status':'FIXTURE_ONLY','spec':deepcopy(x),'productionGate':False,'live_authority':False})
