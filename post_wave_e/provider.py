"""Local redacted evidence intake. Intake never validates a licence or endpoint."""
from pathlib import Path
import json,re,os
from .common import *

ROOT=Path('/Users/qiushi/投资研究/.p1b-archives/provider')
STAGING=Path('/Users/qiushi/投资研究/.p1b-archives/post-wave-e-20261006/staging')
KINDS=('ORDER','PROVIDER','LICENSE','ENDPOINT','TERMS')
def parse_redacted_evidence(x):
    keys(x,('version','kind','provenance','provider_id','product_name','valid_from','valid_until','purpose','retention','storage','transfer','endpoint','independent_verification'))
    require(x['version']==VERSION and x['kind'] in KINDS,'PREP_PROVIDER_KIND_INVALID')
    require(x['provenance'] in ('OWNER_REDACTED_DOCUMENT','SYNTHETIC_FIXTURE'),'PREP_PROVIDER_PROVENANCE')
    for k in ('provider_id','product_name','valid_from','valid_until','purpose','retention','storage','transfer','endpoint','independent_verification'):
        require(type(x[k]) is str and 0<len(x[k])<=2000,'PREP_PROVIDER_TEXT_INVALID')
        require(not re.search(r'(?i)token|api[_ -]?key|authorization|password|secret|bearer\s+\S+|\?[^\s]*=|[0-9a-f]{40,}',x[k]),'PREP_PROVIDER_SECRET_OR_QUERY_REJECTED')
    for k in ('valid_from','valid_until'):
        if x[k]!=UNSET:timestamp(x[k])
    if x['valid_from']!=UNSET and x['valid_until']!=UNSET:
        require(timestamp(x['valid_from'])<timestamp(x['valid_until']),'PREP_PROVIDER_EXPIRY_INVALID')
    return seal({'version':VERSION,'kind':x['kind'],'document_hash':digest(x),'evidence_received':True,'verification':'UNVERIFIED','entitlement_verified':False,'provider_identity_verified':False,'license_verified':False,'transport_integrity_verified':False,'historical_visibility_proven':False,'cloud_transfer_permitted':False,'formal_source_admission':'BLOCKED','live_authority':False})
def _unique_object(pairs):
    x={}
    for k,v in pairs:
        require(k not in x,'PREP_PROVIDER_DUPLICATE_JSON_KEY')
        x[k]=v
    return x
def ingest_evidence(path):
    p=Path(path);require(p.is_relative_to(ROOT) and p.suffix=='.json','PREP_PROVIDER_PATH_RESTRICTED')
    raw=checked_file(p);require(len(raw)<=65536,'PREP_PROVIDER_SIZE')
    # Validate decoded raw JSON before retaining the original. Duplicate keys
    # must not hide credential-bearing text behind a safe final field.
    x=json.loads(raw.decode('utf-8'),object_pairs_hook=_unique_object);result=parse_redacted_evidence(x)
    require(x['provenance']=='OWNER_REDACTED_DOCUMENT','PREP_PROVIDER_FIXTURE_REAL_INGEST_BLOCKED')
    require(STAGING.resolve()==STAGING and STAGING.is_dir() and STAGING.stat().st_mode&0o777==0o700,'PREP_PROVIDER_STAGING_PATH')
    dest=STAGING/(sha(raw)[7:]+'.evidence.json')
    with dest.open('xb') as f:os.chmod(dest,0o600);f.write(raw)
    return result
def gap_matrix():
    return {'state':'BLOCKED','actual_account_tier':'OWNER_DECLARED_15000_MONTHLY','independently_verified_tier':UNSET,'product_name':UNSET,'seller_identity':UNSET,'exact_expiry':UNSET,'actual_materials_ingested':0,'evidence_dimensions':[{'name':k,'state':'UNVERIFIED','evidence_present':False} for k in ('provider_identity','order_product_expiry','entitlement_per_api','local_research_license','retention_storage','cloud_transfer_redistribution','endpoint_ownership','transport_integrity')],'api_success_is_license':False,'public_docs_are_account_entitlement':False,'legal_conclusion':'NOT_DETERMINED','source_admission':'BLOCKED','historical_visibility_proven':False,'cloud_transfer_permitted':False,'live_authority':False}
