"""Pinned local package reader. Registry cannot choose an arbitrary file to expose."""
from pathlib import Path
import json, shutil, subprocess
SAMPLE=Path('/Users/qiushi/投资研究/.p1b-archives/score-review-20261014/Sample-r2.json')
ARCHIVE=Path('/Users/qiushi/投资研究/.p1b-archives/wave-d-20261006')
SOURCES=tuple(ARCHIVE/p for p in ('captures/G1/report.json','captures/FULL-G1/report.json','captures/G1/stock_basic-603228.SH.response.json','captures/G1/fina_indicator-603228.SH.response.json','captures/FULL-G1/FULL-income-603228.SH.response.json'))
CODE=('experiments/sector_stock_v0/config.json','experiments/sector_stock_v0/engine.mjs','experiments/sector_stock_v01/admission.mjs','experiments/sector_stock_v01/config.json','experiments/sector_stock_v01/applicability.mjs','tools/score_review/prepare_sample.py')+tuple('contracts/sector-stock-v0/'+name+'.schema.json' for name in ('CandidateSet','EvidenceBundle','ResearchHypothesis','ScoreInput','ScoreResult','ValidationResult'))
def load(reader,sample_path=SAMPLE,sources=SOURCES):
 from workbench.server import ReadError,digest
 registry,meta=reader.json('score-review-registry','LocalScoreReviewRegistry')
 if registry.get('sample_path')!=str(sample_path) or set(registry.get('code_pins',{}))!=set(CODE):raise ReadError('SCORE_REGISTRY_SCOPE','score-review-registry')
 def check(path,base,expected,size=None):
  raw,_=reader.read_path(path,base)
  if digest(raw)!=expected or (size is not None and len(raw)!=size):raise ReadError('SCORE_PIN_MISMATCH',path.name)
  return raw
 for rel,h in registry['code_pins'].items():check(reader.root/rel,reader.root,h)
 pins=registry.get('source_files',[])
 if len(pins)!=len(sources) or {p.get('path') for p in pins}!={str(p) for p in sources}:raise ReadError('SCORE_SOURCE_SCOPE','score-review-registry')
 for p in pins:check(Path(p['path']),Path(p['path']).parent,p['sha256'],p['bytes'])
 raw=check(sample_path,sample_path.parent,registry['sample_sha256']);package=json.loads(raw)
 if package.get('source_files')!=pins or package.get('content_hash')!=registry.get('sample_content_hash'):raise ReadError('SCORE_EVIDENCE_BINDING','score-review-registry')
 node=shutil.which('node')
 if not node:
  bundled=Path('/Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
  node=str(bundled) if bundled.is_file() else None
 if not node:raise ReadError('NODE_RUNTIME_REQUIRED','score-review-registry')
 try:
  run=subprocess.run([node,str(reader.root/'experiments/sector_stock_v01/admission.mjs')],input=raw,capture_output=True,timeout=10,cwd=reader.root)
 except (OSError,subprocess.SubprocessError):raise ReadError('SCORE_VALIDATOR_UNAVAILABLE','score-review-registry')
 if run.returncode:raise ReadError('SCORE_VALIDATION_FAILED','score-review-registry')
 try:value=json.loads(run.stdout)
 except ValueError:raise ReadError('SCORE_VALIDATION_FAILED','score-review-registry')
 value['provenance']=meta;value['archive_observation_cutoff']=registry['archive_observation_cutoff'];value['integrity']='PINNED_FILES_AND_GRAPH_RECOMPUTATION_MATCH';return value
