"""Owner-pending policy display. No native money or approval issuer."""
from .common import *

def owner_settings():
    account=json.loads(checked_file(ROOT/'config/account-profile.unconfigured.v1.json'))
    inventory=json.loads(checked_file(ROOT/'config/p1a/unset-required.inventory.json'))
    require(len(inventory['fields'])==30,'WG_ACCOUNT_INVENTORY_CHANGED')
    for field in inventory['fields']:
        v=account
        for part in field['pointer'].split('/')[1:]:v=v[part]
        require(v==UNSET,'WG_OWNER_SETTINGS_BASELINE_CHANGED')
    return [{'pointer':x['pointer'],'status':UNSET,'offline_engineering_blocked':False} for x in inventory['fields']]

def small_live_policy():
    d=json.loads(checked_file(ROOT/'docs/wave-g/Small-Live-Pilot-Policy-v0.json'))
    require(d['state']=='OWNER_PENDING_NOT_EXECUTABLE_POLICY' and d['adopted_by_owner'] is False and d['execution_allowed'] is False and d['productionGate'] is False,'WG_POLICY_CANNOT_BE_ACCEPTED_BY_CALLER')
    return metadata('SMALL_LIVE_POLICY_DRAFT',{'draft':d,'actual_owner_settings':owner_settings(),
        'acceptance':'OWNER_PENDING','parameters_are_executable_defaults':False,
        'conditions':'formalPIT/costs/independentunseen/actualForward/brokerdryrun + separateHuman authorization; no current activation'})

def execute_small_live(*args,**kwargs):blocked('WG_SMALL_LIVE_NOT_AUTHORIZED')
def approve_order(*args,**kwargs):blocked('WG_NATIVE_APPROVAL_NOT_AUTHORIZED')
