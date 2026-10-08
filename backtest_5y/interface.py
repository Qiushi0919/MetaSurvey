"""Sidecar-only internal interface. Does not extend shared/native contracts."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ('603993.SH', '600312.SH', '603228.SH')
FAMILIES = ('CORE40_Q_PULLBACK_V1', 'CORE40_Q_BREAKOUT_V1')
SPEC_PATH = ROOT / 'docs/wave-f/Frozen-StrategySpec-v1.json'
SPEC_SHA256 = 'd4eb866d6675e52f4b5158374f94a3152e4ae406c62add22a8c807762b0215da'
EVALUATION_START = '2021-10-08'
HISTORY_START = '2016-01-01'  # Collection buffer; actual1260-session coverage is checked.
FINANCIAL_START = '2014-01-01'  # Financial warmup for2016 EV/EBITDA history; cycle policy remains UNSET.
HISTORY_END = '2026-09-30'
LABELS = ['NON_PIT_DIAGNOSTIC', 'NOT_FORMAL_OOS', 'NON_TRADEABLE']
UNSET = 'UNSET_REQUIRED'

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def frozen_spec():
    raw = SPEC_PATH.read_bytes()
    if digest(raw) != SPEC_SHA256:
        raise ValueError('STRATEGY_HASH_CONFLICT_STOP')
    return json.loads(raw)

def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode() + b'\n')
    path.chmod(0o600)

# Collector batch interface:
# {source, domain, symbol, request:dict, retrieved_at:UTC offset timestamp,
#  raw_bytes:bytes, source_url:str, records:list[record], license_state:str}
# record = {identity:str, event_date:ISO date or None, published_at:str or None,
#           available_at:str or None, first_visible_at:str or None,
#           revision_id:str or None, fields:dict, units:dict, provenance:dict}
# Missing clocks remain None. Current collection cannot prove past visibility.
# Empty responses and collection errors are evidence, never zero-valued data.
# Store API: EvidenceStore(db_path).ingest(batch)->receipt; .records(domain=None,
# symbol=None)->list; .close(); immutable source versions + captured raw bytes.
# Data API: read_existing()->list[batch]; collect_public(output_root)->dict with
# batches:list, attempts:list (no credentials, bounded exact-three collection).
# Requirements: requirements(spec)->list[dict]; evaluate_coverage(records)->dict.
# Strategy API: diagnose(records, coverage)->dict; retains both families and
# computes available price components using existing Wave G, full gates unknown.
# Maintenance API: build_update_plan(records, requirements, through)->dict;
# validate_records(records)->dict; explicit CLI refresh, never hidden scheduling.
