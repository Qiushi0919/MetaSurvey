"""Portable public-only setup audit. Does not enroll, grant or read any secret.

Usage: python audit_public.py <unpacked-public-directory> --openssl <OpenSSL3>
The bundle itself is not an independent identity certificate or preopen timestamp.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

REGISTRY_SHA='0278b10f426f6484e1fdb428961364feb8e309d1276f301dc18572a6f802f677'
KEYS={'HUMAN_USER':('Owner','3374e1b962dea302d3bb24918cf573b6a6ca7583de9c83f1720faed4e36c128a'),
      'INDEPENDENT_REVIEWER':('Reviewer','c415df6c2fc5504afee0df54e92ebc5f6ecdbe1004a7044e81a11503bf16fb0f')}


def audit(directory,openssl):
    p=Path(directory);raw=(p/'enrollment.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=REGISTRY_SHA:raise ValueError('PUBLIC_REGISTRY_CHANGED')
    reg=json.loads(raw);decl=reg['owner_authorization_ref']
    raw=(p/Path(decl['path']).name).read_bytes()
    if len(raw)!=decl['bytes'] or 'sha256:'+hashlib.sha256(raw).hexdigest()!=decl['sha256']:
        raise ValueError('PUBLIC_OWNER_DECLARATION_CHANGED')
    receipts=[]
    for role,(label,hash_value) in KEYS.items():
        raw=(p/(label+'.pub.der')).read_bytes();item=reg['roles'][role]
        if len(raw)!=44 or raw.hex()!=item['public_der'] or hashlib.sha256(raw).hexdigest()!=hash_value:
            raise ValueError('PUBLIC_KEY_CHANGED')
        sig=p/(label+'-Signer-Check.sig')
        if len(sig.read_bytes())!=64:raise ValueError('PUBLIC_SETUP_SIGNATURE_LENGTH')
        result=subprocess.run([openssl,'pkeyutl','-verify','-rawin','-pubin','-keyform','DER',
            '-inkey',str(p/(label+'.pub.der')),'-in',str(p/(label+'-Signer-Check.body.json')),
            '-sigfile',str(sig)],env={**os.environ,'OPENSSL_CONF':'/dev/null'},
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        if result.returncode!=0:raise ValueError('PUBLIC_SETUP_SIGNATURE_REJECTED')
        receipts.append({'role':role,'public_key_sha256':'sha256:'+hash_value,
                         'setup_signature_verified':True,'prediction_signature_verified':False})
    return {'version':'1.0.0','kind':'PortablePublicSetupAudit','state':'PASS',
            'registry_sha256':'sha256:'+REGISTRY_SHA,'roles':receipts,
            'scope':'SETUP_INTEROPERABILITY_ONLY_NOT_PREDICTION_OR_EXECUTION_GRANT',
            'independent_identity_certificate':False,'independent_timestamp':False,
            'actual_authority':False,'private_key_reads':0}


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('directory');a.add_argument('--openssl',default='openssl')
    args=a.parse_args();print(json.dumps(audit(args.directory,args.openssl),sort_keys=True))
