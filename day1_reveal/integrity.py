"""Reopen the external Owner-fixed ZIP and its entire manifest; no repair."""
import json
import zipfile
from pathlib import Path

from dual_track.common import FORWARD_V1_REF, ref, reopen, require, sha
from dual_track.forward import validate_prediction
from wave_h.forward import _json

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path('/Users/qiushi/投资研究/.p1b-archives/dual-track-20261007')
ZIP = Path('/Users/qiushi/投资研究/交付文件/MetaSurvey-双线验证与预测冻结验收包-20261007.zip')
ZIP_HASH = 'sha256:6502262756081c70d7af0e0bc4d7b494851238eaca5a99f4b70a4f04efed78e5'
SOURCE_HASH = 'sha256:f990215f49d5b572f17c7b4eacbf203243268783b324b7dadd02637f48f95b60'
PINS = {
 'Freeze-Receipt.json':('forward-freeze/Freeze-Receipt.json',763,'sha256:09146f50cafadd4b0e2298589ab3b045148ae4aa3f207e58edda7929cfdccd81'),
 'contracts/ForwardPrediction-v1.schema.json':('contracts/dual-track/ForwardPrediction-v1.schema.json',6888,'sha256:ce16e1a75864c9a3dad953980c0c3684030980225851c34e975bf4bce83603c7'),
 'contracts/ForwardOutcome-v1.schema.json':('contracts/dual-track/ForwardOutcome-v1.schema.json',22496,'sha256:bc693de9d9744cf24b4121528fd43774dbdb5227cb93abb9f7ecb806eb51c24d'),
}


def check_day0():
    zip_ref = ref(ZIP)
    require(zip_ref['sha256']==ZIP_HASH, 'D1_BASELINE_ZIP_CHANGED_STOP')
    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        require(len(names)==32 and len(set(names))==32 and z.testzip() is None,
                'D1_PACKAGE_INTEGRITY_STOP')
        manifest = _json(z.read('Package-Manifest.json'))
        require(len(manifest['files'])==31 and
                {r['path'] for r in manifest['files']}==set(names)-{'Package-Manifest.json'},
                'D1_PACKAGE_MANIFEST_STOP')
        for row in manifest['files']:
            raw = z.read(row['path'])
            require(len(raw)==row['bytes'] and sha(raw)=='sha256:'+row['sha256'],
                    'D1_PACKAGE_MEMBER_CHANGED_STOP')
        raw = reopen(FORWARD_V1_REF)
        require(z.read('ForwardPrediction-v1-OWNER_TEXT_IMPORT.json')==raw,
                'D1_PREDICTION_CHANGED_STOP')
        pred = validate_prediction(_json(raw))
        source = reopen(pred['source_ref'])
        require(sha(source)==SOURCE_HASH and z.read('Owner-Provided-Text.txt')==source,
                'D1_SOURCE_CHANGED_STOP')
        checked = []
        for member,(path,size,hash_value) in PINS.items():
            p = (ARCHIVE if member=='Freeze-Receipt.json' else ROOT)/path
            r = {'path':str(p),'bytes':size,'sha256':hash_value}
            data = reopen(r)
            require(z.read(member)==data, 'D1_RECEIPT_OR_SCHEMA_CHANGED_STOP')
            checked.append(r)
        receipt = _json(reopen(checked[0]))
        require(receipt['prediction_ref']==FORWARD_V1_REF and receipt['source_ref']==pred['source_ref'] and
                receipt['human_execution_signature'] is False and receipt['independent_timestamp'] is False and
                receipt['actual_authority'] is False, 'D1_FREEZE_RECEIPT_CHANGED_STOP')
        require(Path(FORWARD_V1_REF['path']).stat().st_mode&0o222==0, 'D1_PREDICTION_NOT_READ_ONLY')
        for member in list(PINS)[1:]:
            require(_json(z.read(member))['$id'].endswith(':1.0.0'), 'D1_SCHEMA_VERSION')
        return {'version':'1.0.0','kind':'Day0IntegrityRecheck','state':'PASS',
                'prediction_ref':FORWARD_V1_REF,'source_ref':pred['source_ref'],
                'baseline_zip_ref':zip_ref,'zip_members_checked':32,'manifest_payloads_checked':31,
                'manifest_sha256':sha(z.read('Package-Manifest.json')),'receipt_and_schema_refs':checked,
                'read_only':True,'prediction_bytes_rewritten':False,
                'original_external_state':'ORIGINAL_NOT_PROVIDED_HASH_NOT_VERIFIED',
                'preopen_by_local_host_clock':True,'independent_timestamp':False,
                'human_prediction_signature_verified':False,'actual_authority':False,
                'horizons':[1,5,10],'D20':'UNSET','D40':'UNSET'}
