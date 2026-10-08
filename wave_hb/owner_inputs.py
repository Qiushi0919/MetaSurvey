"""Unconfigured Owner form, never native AccountProfile or cost authority."""
import json
from .common import ROOT,UNSET,checked_file,metadata,require,ref
ADDITIONAL={
 'available_cash_cents':'INTEGER_CENTS_STRING','max_position_cents':'INTEGER_CENTS_STRING',
 'max_order_cents':'INTEGER_CENTS_STRING','max_portfolio_risk_bps':'DECIMAL_BPS',
 'leverage_allowed':'BOOLEAN_OWNER_DECISION','shorting_allowed':'BOOLEAN_OWNER_DECISION',
 'human_order_approval_policy':'OWNER_POLICY_WITH_EVIDENCE','kill_switch_policy':'OWNER_POLICY_WITH_EVIDENCE',
 'clearing_fee_rate':'DECIMAL_FRACTION','clearing_fee_inclusion':'COMMISSION_OR_EXCLUDED_WITH_BROKER_EVIDENCE',
 'slippage_treatment':'INCLUDED_IN_EXECUTION_PRICE_OR_SEPARATE_ESTIMATE',
 'cost_evidence_refs':'BROKER_AND_STATUTORY_ORIGINAL_REFERENCES',
 'edge_acceptance_policy':'PRE_REGISTERED_OWNER_POLICY','OOS_evaluation_policy':'PRE_REGISTERED_OWNER_POLICY',
 'forward_edge_acceptance_policy':'PRE_REGISTERED_OWNER_POLICY'}
def build_template():
    inv=json.loads(checked_file(ROOT/'config/p1a/unset-required.inventory.json'))
    actual=json.loads(checked_file(ROOT/'config/account-profile.unconfigured.v1.json'))
    fields=[]
    for f in inv['fields']:
        value=actual
        for part in f['pointer'].split('/')[1:]:value=value[part]
        require(value==UNSET,'HB_ORIGINAL_REAL_CONFIG_MUST_REMAIN_UNSET')
        fields.append(dict(pointer=f['pointer'],required=True,value=UNSET,unit_or_schema=f['schema'],
          evidence_required=True,owner_decision_only=True,execution_authority=False))
    require(len(fields)==30,'HB_OWNER_INPUT_INVENTORY_DRIFT')
    return metadata('OWNER_TRADING_INPUT_TEMPLATE',{
        'state':'UNCONFIGURED_NOT_EXECUTABLE','original_required_field_count':30,'original_fields':fields,
        'additional_required_fields':{k:{'value':UNSET,'unit_or_type':v,'evidence_required':True} for k,v in ADDITIONAL.items()},
        'derived_defaults':False,'historical_experiment_values_inherited':False,
        'money_rule':'CNY integer cents strings / Decimal rates; never binary float',
        'rate_unit':'fraction per CNY, not percent or bps; conversion explicit with original evidence',
        'known_public_rates_are_account_defaults':False,'native_AccountProfile':False,
        'save_does_not_activate':'Owner fields require independent evidence/cost/risk/approval gates; no order authority',
        'template_input_refs':[ref(ROOT/'config/p1a/unset-required.inventory.json'),ref(ROOT/'config/account-profile.unconfigured.v1.json')]})
