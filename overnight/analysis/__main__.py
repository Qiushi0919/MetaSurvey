"""Fixed G2 analysis replay to new private files; never an admission or price feed."""
import argparse
from pathlib import Path
import re
from ..data.dataset import canonical, load_verified_dataset, require, sha
from ..data.__main__ import exclusive_write
from .reconcile import analyze_reconciliation
from .financial import analyze_financial

OUTPUT_ROOT = Path('/Users/qiushi/投资研究/.p1b-archives/overnight-20261005/analysis')

def write_outputs(dataset, factor, financial, run_id):
    require(type(run_id) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{1,90}', run_id), 'OUTPUT_RUN_ID_INVALID')
    require(dataset['fixture'] is False, 'FIXTURE_REAL_OUTPUT_BLOCKED')
    require(canonical(factor) == canonical(analyze_reconciliation(dataset)) and
            canonical(financial) == canonical(analyze_financial(dataset)), 'ANALYSIS_OUTPUT_MUTATED')
    root = OUTPUT_ROOT / run_id
    require(not root.exists() and not root.is_symlink(), 'OUTPUT_RUN_EXISTS')
    inventory = []
    for name, value in (('factor-action-report.json', factor), ('financial-observed-versions.json', financial)):
        raw = canonical(value) + b'\n'
        exclusive_write(root / name, raw)
        inventory.append({'object': name, 'sha256': sha(raw), 'bytes': len(raw)})
    index = {'version': '1.0.0-diagnostic', 'run_id': run_id, 'state': 'QUARANTINED',
             'source_admission': 'BLOCKED', 'historical_visibility_proven': False,
             'productionGate': False, 'artifacts': inventory}
    exclusive_write(root / 'artifact-index.json', canonical(index) + b'\n')
    return index

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    try:
        dataset = load_verified_dataset()
        write_outputs(dataset, analyze_reconciliation(dataset), analyze_financial(dataset), args.run_id)
        print('OFFLINE_FACTOR_FINANCIAL_DIAGNOSTICS_WRITTEN source_admission=BLOCKED')
    except Exception:
        print('ANALYSIS_OUTPUT_FAILED_NO_ADMISSION')
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
