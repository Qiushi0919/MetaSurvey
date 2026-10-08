"""Eight-dimensional source evidence intake; supplied material never auto-admits."""
from .common import *
import re

DIMENSIONS=('seller_identity','order_product','validity','account_entitlements',
            'purpose_license','storage_transfer','endpoint_identity','transport')
NEEDS={
 'seller_identity':['seller legal identity','contact/role','relationship to supplied product'],
 'order_product':['redacted order/payment reference','exact product/month-card description'],
 'validity':['contractual effective date/time','contractual expiry date/time and timezone'],
 'account_entitlements':['redacted account identity','tier and per-product grant evidence, independent products separate'],
 'purpose_license':['personal/local research','strategy research/backtest/derivative calculation permissions'],
 'storage_transfer':['local retention/backup','cloud transfer','redistribution and restriction terms'],
 'endpoint_identity':['operator','endpoint relation to seller and Tushare','authorized service chain'],
 'transport':['specific HTTP/HTTPS path and network boundary','redirect/proxy policy','provider transport explanation']}

def public_evidence():
    p=ARCHIVE/'public/provider/manifest-G1.json'
    m=json.loads(checked_file(p))
    refs=[reference(p)]
    for r in m['captures']:
        raw=checked_file(r['path'],r['sha256']);require(len(raw)==r['bytes'],'WG_PUBLIC_SIZE')
        require(r['authenticated'] is False and r['license_for_third_party_account_proven'] is False,'WG_PUBLIC_SCOPE')
        refs.extend([reference(Path(r['path'])),reference(Path(r['path']).with_suffix('.capture.json'))])
    refs.append(reference(ARCHIVE/'provider/official-facts-G1.json'))
    return m,refs

def _material_text_safe(value):
    """Bounded text/key validation; not a universal secret detector."""
    if type(value) is dict:
        for k,v in value.items():
            require(type(k) is str and not re.search(r'(?i)token|password|credential|api.?key|secret|authorization',k),'WG_SENSITIVE_MATERIAL_REJECTED')
            _material_text_safe(v)
    elif type(value) is list:
        for v in value:_material_text_safe(v)
    elif type(value) is str:
        require(len(value)<=1024,'WG_MATERIAL_TEXT_LIMIT')
        require(not re.search(r'(?i)[?&](?:token|api_key|access_token)=|Bearer\s|(?:token|password|api_key)\s*[:=]',value),'WG_SENSITIVE_MATERIAL_REJECTED')
    else:require(type(value) in (bool,int,type(None)),'WG_MATERIAL_VALUE_INVALID')

def inspect_redacted_material(path):
    """Only explicitly staged JSON. Return presence/hash, never material values."""
    p=Path(path);require(p.is_absolute() and p.is_relative_to(ARCHIVE/'provider/materials'),'WG_MATERIAL_NOT_STAGED')
    raw=checked_file(p);require(len(raw)<=65536,'WG_MATERIAL_TOO_LARGE')
    def unique_pairs(pairs):
        d={}
        for k,v in pairs:
            require(k not in d,'WG_DUPLICATE_MATERIAL_KEYS')
            d[k]=v
        return d
    d=json.loads(raw,object_pairs_hook=unique_pairs);_material_text_safe(d)
    keys(d,('version','redacted','dimensions'))
    require(d['version']=='1.0.0' and d['redacted'] is True,'WG_REDACTED_TEMPLATE_REQUIRED')
    require(type(d['dimensions']) is dict and set(d['dimensions'])==set(DIMENSIONS),'WG_EIGHT_DIMENSIONS_REQUIRED')
    present=[]
    for name,x in d['dimensions'].items():
        keys(x,('statement','evidence_paths'))
        require(x['statement'] is None or type(x['statement']) is str,'WG_MATERIAL_STATEMENT')
        require(type(x['evidence_paths']) is list and all(type(v) is str for v in x['evidence_paths']),'WG_MATERIAL_PATH_LIST')
        # Merely mentioned paths are not opened/admitted. Independent acceptance is separate.
        if x['statement'] is not None or x['evidence_paths']:present.append(name)
    return metadata('REDACTED_MATERIAL_PRESENCE_ONLY',{
        'material_ref':{'path':str(p),'sha256':sha(raw),'bytes':len(raw)},
        'dimensions_supplied':sorted(present),'state':'SUPPLIED_NOT_VERIFIED',
        'native_source_authority':False,'seller_license_entitlement_transport_verified':False,
        'content_values_exposed':False,'sensitive_scan_limit':'bounded allowed JSON keys/text only'})

def evidence_pack():
    m,refs=public_evidence()
    return metadata('PROVIDER_LICENSE_TRANSPORT_EVIDENCE_PACK',{
        'dimensions':[{'dimension':n,'state':'UNKNOWN','actual_independently_verified_materials':0,
                       'required_evidence':NEEDS[n],'verified_value':UNSET} for n in DIMENSIONS],
        'owner_declared_tier':'15000_MONTHLY_NOT_INDEPENDENTLY_VERIFIED',
        'actual_materials_supplied_this_phase':0,'actual_expiry':UNSET,
        'official_documents':refs,'official_public_successes':sum(x['http_status']==200 for x in m['captures']),
        'public_docs_scope':'official product/field/protocol/general terms only; not third-party account/product entitlement',
        'http_policy':'HTTP protocol alone neither proves nor disproves specific provider identity/license/transport integrity; official HTTP example does not authenticate private gateway',
        'current_owner_scope':'LOCAL_ONLY_EXISTING_QUARANTINED_RETROSPECTIVE_DIAGNOSTIC_EXCEPTION; not supplier license',
        'legal_conclusion':'NOT_DETERMINED','verified_provider_identity':False,
        'license_admitted':False,'transport_integrity_verified':False,
        'cloud_transfer_permitted':False,'redistribution_permitted':False,
        'former_gap_ref':reference(ROOT/'docs/post-wave-e/Provider-License-Transport-Gap.json'),
        'network_counts':{'GETs':m['public_GETs'],'queries':m['web_discovery_queries'],'discovery_calls':m['web_discovery_calls'],'document_opens':m['web_document_opens']},
        'actionable_next':'Owner/vendor may stage redacted documents explicitly; no Token requested/read; independent evidence acceptance required'})

def admit_source(*args,**kwargs):blocked('WG_SOURCE_ADMISSION_NOT_AUTHORIZED')
def cloud_export(*args,**kwargs):blocked('WG_CLOUD_EXPORT_BLOCKED')
