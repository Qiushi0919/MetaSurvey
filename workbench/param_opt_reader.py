"""Fixed read-only optimization projection; no capture, search or task execution."""
from pathlib import Path
import re

def load(reader):
 from workbench.server import ReadError, digest
 registry,source=reader.json('param-opt-registry','ParameterOptimizationRegistry')
 if registry.get('version')!='1.0.0':raise ReadError('PARAM_OPT_VERSION','param-opt-registry')
 result,provenance=reader.json('param-opt-results','ParameterOptimizationReview')
 if provenance['sha256']!=registry.get('results_hash'):raise ReadError('PARAM_OPT_RESULTS_HASH','param-opt-results')
 for name,h in registry.get('code_pins',{}).items():
  p=Path(name)
  if p.is_absolute() or '..' in p.parts or p.suffix not in ('.py','.json') or not re.fullmatch('sha256:[0-9a-f]{64}',h):raise ReadError('PARAM_OPT_CODE_SCOPE',name)
  raw,_=reader.read_path(reader.root/p,reader.root)
  if digest(raw)!=h:raise ReadError('PARAM_OPT_CODE_CHANGED',name)
 if not {'experiments/param_opt_v1/engine.py','tools/param_opt/run.py','tools/param_opt/report.py','workbench/param_opt_reader.py'}.issubset(registry.get('code_pins',{})):raise ReadError('PARAM_OPT_CODE_PINS_MISSING','param-opt-registry')
 if result.get('version')!='1.0.0' or result.get('experiment')!='CORE40_PARAM_OPT_V1' or result.get('search_configs')!=108 or len(result.get('table',[]))!=108:raise ReadError('PARAM_OPT_SHAPE','param-opt-results')
 if result.get('classification')!='EXPOSED_HISTORY_EXPLORATORY_OPTIMIZATION' or len(result.get('locked_ids',[]))>3:raise ReadError('PARAM_OPT_SCOPE','param-opt-results')
 from tools.param_opt import report,run
 archive=reader.root.parent/'.p1b-archives/param-opt-20261020'
 status='PUBLIC_ARCHIVED_METADATA_ONLY'
 if archive.exists():
  if archive.is_symlink() or archive.resolve()!=archive or archive!=run.ARCHIVE:raise ReadError('PARAM_OPT_PRIVATE_SCOPE','param-opt-registry')
  if report.build()!=result:raise ReadError('PARAM_OPT_RECOMPUTATION_MISMATCH','param-opt-results')
  status='LOCAL_ARTIFACTS_REVERIFIED'
 return dict(status=status,data=result,source=provenance,registry_source=source)
