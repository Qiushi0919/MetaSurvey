"""Planning only. A future calendar date is not a captured session."""
from .common import *

def readiness():
    return {'state':'BLOCKED_SEPARATE_OWNER_REQUIRED','planned_first_post_holiday_session':'2026-10-08','actual_fresh_session_observed':False,'fresh_eod_available':False,'snapshot_b_created':False,'scheduled':False,'actual_forward_days':0,'required_checks':['NEW_HUMAN_OWNER_AUTHORIZATION','ACTUAL_EXCHANGE_SESSION_OPEN','ACTUAL_EOD_SOURCE_AVAILABLE','EXACT_3_SYMBOLS','FRESH_POST_SNAPSHOT_A_RETRIEVAL','FOUR_CLOCKS_NO_DATE_IMPUTATION','SOURCE_POLICY_VERSION_HASH','NO_PROVIDER_LICENSE_PROMOTION','NEW_IMMUTABLE_SNAPSHOT_LINEAGE','OWNER_ACCOUNT_COST_RISK_STRATEGY_POLICIES','NO_NATIVE_EXECUTION_AUTHORITY'],'live_authority':False}
def run_snapshot_b(*args,**kwargs):blocked('PREP_SNAPSHOT_B_NOT_AUTHORIZED')
