"""Reuse strict immutable helpers; JSON/hashes never confer authority."""
from post_wave_e.common import (SYMBOLS, UNSET, require, canonical, sha, digest,
                               seal, keys, hash_value, timestamp, decimal_string,
                               checked_file, blocked)
from pathlib import Path
from datetime import date
import re

ROOT = Path(__file__).resolve().parents[1]
# A relocated Git checkout reuses the same immutable private evidence root.
# This does not claim evidence-root relocation or remote CI portability.
ARCHIVE = Path('/Users/qiushi/投资研究/.p1b-archives/wave-f-20261006')
VERSION = '1.0.0'
LABEL = 'SYNTHETIC_NOT_OWNER_POLICY'

def session_date(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), 'WF_SESSION_DATE')
    return date.fromisoformat(value)

def unavailable(reason='WF_SEPARATE_HUMAN_AUTHORIZATION_REQUIRED'):
    blocked(reason)

def metadata(body):
    canonical(body)
    return seal({'version': VERSION, 'namespace': 'LOCAL_ONLY_NON_TRADEABLE:CORE_40',
                 'body': body, 'productionGate': False, 'live_authority': False,
                 'actual_forward_days': 0, 'historical_visibility_proven': False})
