"""External public trust roots + separate opaque capabilities; no actual signer.

Enrollment is an Owner-operated trust installation outside producer APIs. H-A
does not install that registry. Filesystem/interpreter compromise is not claimed
to be resisted; caller-supplied keys, roles, timestamps and JSON are resisted.
"""
from __future__ import annotations
import base64,copy,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .common import (ROOT,VERSION,SYMBOLS,bindings,canonical,checked_file,digest,
                     hash_value,keys,policy,require,sha,timestamp)

AUTHORITY=Path('/Users/qiushi/投资研究/.p1b-authority/wave-h/enrollment.json')
ZONE=ZoneInfo('Asia/Shanghai')
_ISSUED={}
_KINDS={'CAPTURE':('HUMAN_USER',['LOCAL_READ_ONLY_CAPTURE'],
                     ('plan_hash','session_evidence_hash','snapshot_a_hash')),
        'REVIEW':('INDEPENDENT_REVIEWER',['INDEPENDENT_CAPTURE_ACCEPTANCE'],
                  ('capture_hash','capture_manifest_hash','plan_hash',
                   'acceptance_request_hash','originals_digest')),
        'FORWARD':('HUMAN_USER',['ACTUAL_FORWARD_NO_DECISION_APPEND'],
                   ('snapshot_hash','session','expected_head'))}
_BODY=('version','kind','phase','role','namespace','permissions','session','symbols',
       'bindings','source_identity','source_schema_version','issued_at','not_before',
       'expires_at','nonce','scope')

def _json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            require(k not in out,'WH_AUTH_DUPLICATE_KEY');out[k]=v
        return out
    def bad(_):raise ValueError('WH_AUTH_NONFINITE')
    try:return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    except ValueError:raise
    except Exception:raise ValueError('WH_AUTH_JSON_INVALID') from None

def _instant(value):
    timestamp(value)
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)

def _now():return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')

def _node():
    p=Path(sys.executable).resolve().parents[2]/'node/bin/node'
    require(p.is_file(),'WH_AUTH_NODE_RUNTIME_REQUIRED');return str(p)

def fixture_signature_verify(public_der,body,signature):
    """Pure Ed25519 verification; never enrolls a key or issues a capability."""
    require(type(public_der) is str and re.fullmatch('[0-9a-f]{88}',public_der),'WH_AUTH_PUBLIC_KEY_FORMAT')
    require(type(signature) is str and re.fullmatch('[0-9a-f]{128}',signature),'WH_AUTH_SIGNATURE_FORMAT')
    data={'public_der':public_der,'signature':signature,'message':base64.b64encode(canonical(body)).decode('ascii')}
    r=subprocess.run([_node(),str(ROOT/'wave_h/crypto.mjs')],input=canonical(data),
                     stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10,check=False)
    return r.returncode==0 and r.stdout==b'PASS'

def ensure_actual_enrolled():
    """Only fixed operator path; check before any caller path/secret/network IO."""
    pending=_json(checked_file(ROOT/'config/wave-h/authority.pending.json'))
    require(pending['state']=='NOT_ENROLLED' and pending['signing_keys_in_product'] is False,
            'WH_AUTH_PENDING_TEMPLATE_CHANGED')
    require(AUTHORITY.exists(),'WH_ACTUAL_AUTHORITY_NOT_ENROLLED')
    require(AUTHORITY.resolve()==AUTHORITY and AUTHORITY.parent.stat().st_mode&0o777==0o700 and
            AUTHORITY.stat().st_mode&0o777==0o600,'WH_AUTH_OPERATOR_REGISTRY_PERMISSIONS')
    reg=_json(checked_file(AUTHORITY))
    keys(reg,('version','kind','phase','enrollment_id','owner_installed_outside_producer',
              'fixture_keys','bindings','roles','owner_authorization_ref'))
    require(reg['version']==VERSION and reg['kind']=='OWNER_INSTALLED_ACTUAL_PUBLIC_TRUST_ROOTS' and
            reg['phase']=='H_B_FRESH_OWNER_AUTH' and reg['owner_installed_outside_producer'] is True and
            reg['fixture_keys'] is False and reg['bindings']==bindings(),'WH_AUTH_ENROLLMENT_INVALIDATED')
    require(type(reg['enrollment_id']) is str and re.fullmatch('[A-Za-z0-9_-]{16,120}',reg['enrollment_id']),
            'WH_AUTH_ENROLLMENT_ID')
    ar=reg['owner_authorization_ref'];keys(ar,('path','sha256','bytes'))
    ap=Path(ar['path']);require(ap.is_relative_to(AUTHORITY.parent) and ap.resolve()==ap and
            ap.stat().st_mode&0o777==0o600 and type(ar['bytes']) is int,'WH_AUTH_OWNER_INSTALLATION_EVIDENCE')
    raw=checked_file(ap,ar['sha256']);require(len(raw)==ar['bytes'] and len(raw)>0,'WH_AUTH_OWNER_INSTALLATION_EVIDENCE')
    keys(reg['roles'],('HUMAN_USER','INDEPENDENT_REVIEWER'));seen=set()
    for role,item in reg['roles'].items():
        keys(item,('key_id','public_der','public_key_sha256','scope'))
        require(type(item['key_id']) is str and re.fullmatch('[A-Za-z0-9_-]{16,120}',item['key_id']), 'WH_AUTH_KEY_ID')
        require(type(item['public_der']) is str and re.fullmatch('302a300506032b6570032100[0-9a-f]{64}',item['public_der']),
                'WH_AUTH_ED25519_KEY_REQUIRED')
        require(item['scope']=='ACTUAL_H_B_ONLY' and sha(bytes.fromhex(item['public_der']))==item['public_key_sha256'],
                'WH_AUTH_PUBLIC_KEY_PIN')
        require(item['public_key_sha256'] not in seen,'WH_AUTH_REVIEWER_NOT_INDEPENDENT');seen.add(item['public_key_sha256'])
    return copy.deepcopy(reg)

def _shape(body,kind):
    keys(body,_BODY);role,permissions,scope=_KINDS[kind];p=policy()
    require(body['version']==VERSION and body['kind']==kind and body['phase']=='H_B_FRESH_OWNER_AUTH' and
            body['role']==role and body['namespace']=='ACTUAL_FORWARD_NO_DECISION' and
            body['permissions']==permissions and body['symbols']==list(SYMBOLS),'WH_AUTH_ROLE_SCOPE_INVALID')
    require(type(body['session']) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}',body['session']), 'WH_AUTH_SESSION')
    datetime.fromisoformat(body['session'])
    require(body['bindings']==bindings() and body['source_identity']==p['source_identity'] and
            body['source_schema_version']==p['source_schema_version'],'WH_AUTH_BINDING_INVALIDATED')
    require(type(body['nonce']) is str and re.fullmatch('[A-Za-z0-9_-]{16,120}',body['nonce']),'WH_AUTH_NONCE')
    keys(body['scope'],scope)
    for field in scope:
        if field=='session':require(body['scope'][field]==body['session'],'WH_AUTH_FORWARD_SESSION')
        else:hash_value(body['scope'][field])
    issued,nb,ex=(timestamp(body[k]) for k in ('issued_at','not_before','expires_at'))
    require(nb<=issued<ex and ex-nb<=86400*1_000_000_000,'WH_AUTH_EXPIRY_RANGE')
    require(_instant(body['issued_at']).astimezone(ZONE).date().isoformat()==body['session'] and
            _instant(body['expires_at']).astimezone(ZONE).date().isoformat()==body['session'],'WH_AUTH_CURRENT_SESSION_ONLY')
    return issued,nb,ex

def validate_time_window(body,kind,now=None,persisted=False):
    """Pure strict nanosecond check; it never verifies a role or grants authority."""
    issued,nb,ex=_shape(body,kind)
    t=issued if persisted else timestamp(now)
    require(nb<=issued<=t<ex,'WH_AUTH_EXPIRED_NOT_ISSUED_OR_NOT_YET_VALID')
    if not persisted:
        require(_instant(now).astimezone(ZONE).date().isoformat()==body['session'],'WH_AUTH_WRONG_ACTUAL_DAY')
    return True

def _verify(envelope,kind,now,persisted=False):
    reg=ensure_actual_enrolled()
    keys(envelope,('version','kind','key_id','body','signature'))
    require(envelope['version']==VERSION and envelope['kind']=='SIGNED_WAVE_H_CAPABILITY','WH_AUTH_ENVELOPE_KIND')
    body=envelope['body'];_shape(body,kind)
    key=reg['roles'][_KINDS[kind][0]]
    require(envelope['key_id']==key['key_id'],'WH_AUTH_WRONG_ENROLLED_SIGNER')
    require(fixture_signature_verify(key['public_der'],body,envelope['signature']),'WH_AUTH_SIGNATURE_REJECTED')
    validate_time_window(body,kind,now,persisted)
    return dict(copy.deepcopy(body),signed_envelope=copy.deepcopy(envelope),enrollment_hash=digest(reg))

class _Capability:
    __slots__=('__weakref__',)
    def __copy__(self):return _Capability()
    def __deepcopy__(self,memo):return _Capability()

def _issue(envelope,kind,now=None):
    # A supplied timestamp cannot move current wall-clock authorization into the past.
    real=_now()
    if now is not None:require(_instant(now)==_instant(real),'WH_AUTH_CALLER_CLOCK_FORBIDDEN')
    claims=_verify(envelope,kind,real)
    handle=_Capability();_ISSUED[id(handle)]=(handle,kind,claims,digest(claims));return handle

def capture_capability(signed_grant,now=None):return _issue(signed_grant,'CAPTURE',now)
def review_capability(signed_acceptance,now=None):return _issue(signed_acceptance,'REVIEW',now)
def forward_capability(signed_grant,now=None):return _issue(signed_grant,'FORWARD',now)

def _require(handle,kind,field,value):
    ensure_actual_enrolled()
    issued=_ISSUED.get(id(handle))
    require(issued is not None and issued[0] is handle and issued[1]==kind and
            digest(issued[2])==issued[3],'WH_AUTH_NOT_ISSUED_OR_WRONG_CAPABILITY')
    claims=_verify(issued[2]['signed_envelope'],kind,_now())
    require(claims==issued[2] and claims['scope'][field]==value,'WH_AUTH_SUBJECT_INVALIDATED')
    return copy.deepcopy(claims)

def require_capture(handle,plan_hash):return _require(handle,'CAPTURE','plan_hash',plan_hash)
def require_review(handle,capture_hash):return _require(handle,'REVIEW','capture_hash',capture_hash)
def require_forward(handle,snapshot_hash):return _require(handle,'FORWARD','snapshot_hash',snapshot_hash)
def verify_persisted_capture(envelope):return _verify(envelope,'CAPTURE',None,True)
def verify_persisted_review(envelope):return _verify(envelope,'REVIEW',None,True)
def verify_persisted_forward(envelope):return _verify(envelope,'FORWARD',None,True)

def issue_native(*args,**kwargs):raise ValueError('WH_AUTH_NATIVE_AUTHORITY_FORBIDDEN')
def execute_trade(*args,**kwargs):raise ValueError('WH_AUTH_TRADE_FORBIDDEN')
def connect_broker(*args,**kwargs):raise ValueError('WH_AUTH_BROKER_FORBIDDEN')
def cloud_export(*args,**kwargs):raise ValueError('WH_AUTH_CLOUD_EXPORT_FORBIDDEN')
