"""Reported membership intervals, never availability or historical-label authority."""
from copy import deepcopy
from .core import (SYMBOLS, START, END, observations, request_views, require_inputs,
                   make_result, require, date_literal, clock)


def analyze(inputs):
    require_inputs(inputs)
    views=request_views(inputs,'index_member_all')
    by_key={(q['origin'],q['request_id']):q for q in views}
    rows=[]
    for o in observations(inputs,'index_member_all'):
        v,ref=o['values'],o['ref'];q=by_key[(ref['origin'],ref['request_id'])]
        require(v.get('ts_code') in SYMBOLS and v['ts_code']==q['ts_code'],'INDUSTRY_SYMBOL_SCOPE_INVALID')
        require(ref['available_at']==ref['retrieved_at'] and ref['published_at'] is None,'INDUSTRY_CLOCK_BACKFILL_FORBIDDEN')
        clock(ref['available_at'])
        entered,left=v.get('in_date'),v.get('out_date')
        known=date_literal(entered) and date_literal(left)
        ordered=known and entered<=left
        expected=q.get('params',{}).get('is_new')
        mismatch=expected is not None and v.get('is_new')!=expected
        blocked=o['response_blocked'] or mismatch or not ordered
        status='AMBIGUOUS' if known and not ordered else 'UNKNOWN' if not known else 'BLOCKED' if blocked else 'PARTIAL'
        rows.append({'ts_code':v['ts_code'],'reported_values':deepcopy(v),'source_ref':deepcopy(ref),
            'origin':ref['origin'],'effective_interval':{'in_date_literal':entered,'out_date_literal':left,
                'precision':'DATE_ONLY','boundary_semantics':'UNVERIFIED','ordering_known':bool(ordered),
                'overlaps_authorized_window':(entered<=END and left>=START) if ordered else None},
            'membership_status':status,'response_blocked':blocked,
            'is_new_observed':v.get('is_new'),'is_new_is_historical_visibility':False,
            'empty_out_date_is_infinity':False,'published_at':None,'available_at':ref['available_at'],
            'historical_visibility_proven':False,'historical_label_issued':False})
    requests=[{'origin':q['origin'],'request_id':q['request_id'],'ts_code':q['ts_code'],
        'requested_is_new':q.get('params',{}).get('is_new'),'raw_sha256':q['raw_sha256'],
        'row_count':q['row_count'],'response_blocked':q['response_blocked'],
        'reason_codes':q['reason_codes'],'retrieved_at':q['retrieved_at'],
        'available_at':q['available_at'],'date_filter_supported':False,'negative_membership_proven':False}
        for q in views]
    return make_result(inputs,'INDUSTRY_MEMBERSHIP_CANDIDATE',{
        'industry_membership_candidate':{'status':'PARTIAL' if rows else 'UNKNOWN','observations':rows,
            'requests':requests,'observation_count':len(rows),'legacy_count':sum(r['origin']=='legacy' for r in rows),
            'new_count':sum(r['origin']=='new' for r in rows),'valid_ordered_interval_count':sum(r['effective_interval']['ordering_known'] for r in rows),
            'intervals_merged_or_old_versions_overwritten':False},
        'industry_pit_known_gaps':{'status':'UNKNOWN','source_admission':'BLOCKED','historical_visibility_proven':False,
            'supplier_blank_out_date_semantics':'UNKNOWN','effective_date_is_available_at':False,
            'is_new_backfill_allowed':False,'current_membership_is_complete_history':False,
            'published_at_exact_instant':'UNKNOWN','date_filter_supported':False,
            'history_negative_or_completeness_proven':False,'historical_labels_issued':0,
            'unresolved':['PROVIDER_LICENSE_TRANSPORT','SOURCE_DATE_FILTER_NOT_SUPPORTED',
                'BLANK_OUT_DATE_SEMANTICS','MEMBERSHIP_HISTORY_COMPLETENESS','HISTORICAL_FIRST_VISIBLE_TIME']}},__file__)
