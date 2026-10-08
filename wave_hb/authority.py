"""Public-key candidate audit only. No key generation, signer or enrollment writer."""
import hashlib,re
from .common import metadata,require,UNSET

def audit_public_roots(owner=None,reviewer=None):
    """Inputs are public DER hex + externally attested provenance, not signer keys."""
    roles={};seen=set();missing=[]
    for role,item in (('HUMAN_USER',owner),('INDEPENDENT_REVIEWER',reviewer)):
        if item is None:
            roles[role]={'public_der':UNSET,'public_key_sha256':UNSET,'provenance':UNSET,'status':'NOT_SUPPLIED'};missing.append(role);continue
        require(type(item) is dict and set(item)=={'public_der','key_id','provenance','fixture_key'},'HB_PUBLIC_KEY_SHAPE')
        require(item['fixture_key'] is False,'HB_TEST_KEY_FORBIDDEN')
        require(type(item['public_der']) is str and re.fullmatch('302a300506032b6570032100[0-9a-f]{64}',item['public_der']),'HB_PUBLIC_ED25519_REQUIRED')
        require(type(item['key_id']) is str and re.fullmatch('[A-Za-z0-9_-]{16,120}',item['key_id']),'HB_PUBLIC_KEY_ID')
        provenance=item['provenance']
        require(type(provenance) is dict and set(provenance)=={'identity_label','outside_producer','owner_attestation_ref'} and
           type(provenance['identity_label']) is str and 1<=len(provenance['identity_label'])<=160 and
           provenance['outside_producer'] is True,'HB_PUBLIC_KEY_PROVENANCE_REQUIRED')
        # Merely attested candidates are not independently proven or installed roots.
        ar=provenance['owner_attestation_ref'];require(type(ar) is dict and set(ar)=={'path','sha256','bytes'} and
            type(ar['path']) is str and ar['path'].startswith('/') and type(ar['bytes']) is int and ar['bytes']>0 and
            type(ar['sha256']) is str and re.fullmatch('sha256:[0-9a-f]{64}',ar['sha256']),'HB_PUBLIC_KEY_ATTESTATION_REF_REQUIRED')
        fingerprint='sha256:'+hashlib.sha256(bytes.fromhex(item['public_der'])).hexdigest()
        require(fingerprint not in seen,'HB_PUBLIC_KEYS_NOT_INDEPENDENT');seen.add(fingerprint)
        roles[role]=dict(item,public_key_sha256=fingerprint,status='CANDIDATE_ONLY_NOT_INSTALLED')
    return metadata('ACTUAL_AUTHORITY_ENROLLMENT_CANDIDATE',{'roles':roles,
      'state':'HOLD_MISSING_PUBLIC_ROOTS' if missing else 'CANDIDATE_REQUIRES_OUTSIDE_PRODUCER_OWNER_INSTALLATION',
      'missing_roles':missing,'actual_root_installed':False,'actual_authority_issued':False,
      'fixed_actual_enrollment_path':'/Users/qiushi/投资研究/.p1b-authority/wave-h/enrollment.json',
      'public_fingerprints_only':True,'private_key_input_accepted':False,
      'independence_limit':'different DER proves key distinction only; real identity and custody require external evidence',
      'no_private_key_generation':True,'no_auto_enrollment':True,'H_A_bindings_required_on_future_install':True})

def install(*a,**k):raise ValueError('HB_PRODUCER_ENROLLMENT_FORBIDDEN')
def sign(*a,**k):raise ValueError('HB_ACTUAL_SIGNER_FORBIDDEN')
