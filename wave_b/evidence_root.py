"""Read-only relocation binding to the single approved, unmoved evidence root."""
from pathlib import Path
from types import FunctionType
from .primitives import require

ARCHIVE=Path('/Users/qiushi/投资研究/.p1b-archives/wave-b-20261006')
EXPECTED_ARCHIVE='/Users/qiushi/投资研究/.p1b-archives/wave-b-20261006'

def verify_registered_capture(ref):
    from . import probe
    require(str(ARCHIVE)==EXPECTED_ARCHIVE and ARCHIVE.resolve()==ARCHIVE and not ARCHIVE.is_symlink(), 'EVIDENCE_ROOT_INVALID')
    require(type(ref) is dict and set(ref)=={'path','sha256','bytes'} and
            ref['path']==str(ARCHIVE/'captures'/'WAVE-B-PROBE-20261006-G2'/'report.json'), 'EVIDENCE_ROOT_OR_REF_INVALID')
    # Bind only the verifier's path constant. No live collector, module global,
    # API plan, policy, permission, raw bytes or capture clock is changed.
    scope=dict(probe.verify_capture.__globals__)
    scope['DEST']=ARCHIVE/'captures'/'WAVE-B-PROBE-20261006-G2'
    verifier=FunctionType(probe.verify_capture.__code__,scope,'fixed_evidence_verifier',
                          probe.verify_capture.__defaults__,probe.verify_capture.__closure__)
    return verifier(ref)
