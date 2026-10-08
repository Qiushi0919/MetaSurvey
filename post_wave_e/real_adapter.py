"""Read-only actual observation projection for the future Paper adapter boundary.

Adapts the immutable three-stock current observation anchors, not a new
Snapshot B or a daily Paper ledger. This code has no append/native interface.
Persistent storage is tested separately with strictly synthetic NO_DECISION
records. Actual activation/policy/authority/source re-probe is a later phase.
"""
from .common import *
def _project(ctx):
    return {'adapter_version':VERSION,'state':'BLOCKED','projection_kind':'ACTUAL_CURRENT_OBSERVATION_ANCHOR_DISPLAY_ONLY','source_refs':[{'symbol':x['symbol'],'object_id':x['object_id'],'object_version':x['object_version'],'content_hash':x['content_hash'],'source_identity':x['source_identity'],'retrieval_cutoff':x['retrieval_cutoff']} for x in ctx['inputs']],'anchor_is_admitted_snapshot':False,'fresh_snapshot_b':None,'actual_session_record_appended':False,'actual_forward_days':0,'required_owner_policies':{'account':UNSET,'cost':UNSET,'risk':UNSET,'strategy':UNSET},'formal_source_admission':'BLOCKED','live_authority':False,'native_order_fields_supported':False}
def preview():
    from .core import frozen_context
    c=frozen_context();return seal({'version':VERSION,'source_identity':c['source_identity'],'namespace':c['rules']['namespace'],'projection':_project(c),'productionGate':False,'live_authority':False})
def append_actual_session(*args,**kwargs):blocked('PREP_ACTUAL_PAPER_APPEND_NOT_AUTHORIZED')
