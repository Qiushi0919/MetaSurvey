"""Print a read-only engineering review; no filesystem outputs or market calls."""
import argparse
import json
from pathlib import Path
from .boundary import check_refs, review_changes, git_output

p = argparse.ArgumentParser()
p.add_argument('--baseline', required=True)
p.add_argument('--forward-checkpoint', required=True)
p.add_argument('--parent', required=True)
p.add_argument('--child', required=True)
a = p.parse_args()
b = json.loads(Path(a.baseline).read_text())
f = json.loads(Path(a.forward_checkpoint).read_text())
parent = check_refs(a.parent, b)
child = check_refs(a.child, b)
forward = check_refs(a.parent, f, absolute=True)
changes = review_changes(a.child, b['parent_head'])
result = {'version': '1.0.0', 'kind': 'ParallelEngineeringBoundaryReview',
          'parent_head': git_output(a.parent, ['rev-parse', 'HEAD']).decode().strip(),
          'child_head': git_output(a.child, ['rev-parse', 'HEAD']).decode().strip(),
          'parent_baseline': parent, 'child_baseline': child,
          'forward_engineering_checkpoint': forward, 'child_changes': changes,
          'actual_authority': False, 'productionGate': False,
          'scope': 'POINT_IN_TIME_ENGINEERING_NOT_FINAL_CHILD_ACCEPTANCE',
          'note': 'Forward journal checkpoint is this engineering batch only; later legitimate signed appends need a new reviewed checkpoint, never a rewritten freeze.'}
result['state'] = 'PASS' if all(x['state'] == 'PASS' for x in (parent, child, forward, changes)) else 'FAIL'
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result['state'] == 'PASS' else 1)
