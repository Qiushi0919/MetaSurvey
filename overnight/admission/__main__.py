import argparse
from pathlib import Path
import re
from ..data.dataset import canonical, load_verified_dataset, require, sha
from ..data.__main__ import exclusive_write
from .dry_run import build_readiness
ROOT = Path('/Users/qiushi/投资研究/.p1b-archives/overnight-20261005/admission')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--run-id',required=True); args=parser.parse_args()
    try:
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{1,90}',args.run_id),'OUTPUT_RUN_ID_INVALID')
        directory=ROOT/args.run_id; require(not directory.exists() and not directory.is_symlink(),'OUTPUT_RUN_EXISTS')
        value=build_readiness(load_verified_dataset()); raw=canonical(value)+b'\n'
        exclusive_write(directory/'admission-readiness.json',raw)
        exclusive_write(directory/'artifact-index.json',canonical({'version':'1.0.0-diagnostic','artifacts':[
            {'object':'admission-readiness.json','bytes':len(raw),'sha256':sha(raw)}],
            'source_admission':'BLOCKED','productionGate':False})+b'\n')
        print('EIGHT_CATEGORY_DRY_RUN_COMPLETE real_receipts=0 closed_business_conditions=0')
    except Exception:
        print('ADMISSION_DRY_RUN_FAILED_NO_PERMISSION'); return 1
    return 0

if __name__ == '__main__': raise SystemExit(main())
