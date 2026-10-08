"""Predeclare this bounded reconstruction, not production strategy policy."""
from .common import BOUNDARIES, HORIZONS, SYMBOLS, ROOT, now, ref, write_new
from .history import COST_GRID_BPS


def freeze(path):
    return write_new(path, {'version': '1.0.0', 'kind': 'DualTrackProtocol',
        'frozen_at': now(), 'symbols': list(SYMBOLS), 'horizons': list(HORIZONS),
        'boundaries': BOUNDARIES,
        'historical_name_requested': 'Historical-OOS-Lite / PRICE_ONLY',
        'actual_historical_tier': 'RETROSPECTIVE_DIAGNOSTIC_ONLY',
        'forecast_method': 'EXPANDING_PAST_HORIZON_MEAN_RAW_RETURN_REFERENCE_ONLY',
        'meaning': 'PARAMETER_FREE_REFERENCE_NOT_METASURVEY_FULL_STRATEGY',
        'training': 'ALL_COMPLETED_H_SESSION_RAW_CLOSE_CHANGES_WITH_ENDPOINT_LE_LOGICAL_CUTOFF',
        'minimum_training_pairs': 1, 'parameter_selection': 'NONE', 'optimization': False,
        'out_of_sample': 'TEMPORAL_PREFIX_RECONSTRUCTION_ONLY_PREVIOUSLY_EXPOSED',
        'forward_label_horizons': list(HORIZONS),
        'cost_grid_roundtrip_bps': list(COST_GRID_BPS),
        'cost_scope': 'SCENARIO_ONLY_NOT_PRODUCTION_DEFAULTS',
        'rounding': 'DECIMAL_80_RATIO_NO_CURRENCY_ROUNDING; OWNER_PRICE_CENT_ROUND_HALF_UP',
        'unit': 'RETURN_RATIO_1_EQUALS_100_PERCENT; MONEY_CNY_DECIMAL_STRINGS',
        'timezone': 'OFFSET_REQUIRED_UTC_PERSISTED_ASIA_SHANGHAI_SESSION_DATES',
        'source_strategy_ref': ref(ROOT/'docs/wave-f/Frozen-StrategySpec-v1.json'),
        'frozen_families': ['CORE40_Q_PULLBACK_V1', 'CORE40_Q_BREAKOUT_V1'],
        'full_family_decision': 'NO_DECISION', 'raw_adjustment': 'RAW_ONLY_ACTIONS_UNRESOLVED',
        'calendar': 'COMPLETE_CURRENT_REFERENCE_GRID_NOT_HISTORICAL_AUTHORITY',
        'full_predecessor_sample_exposure': True, 'purge_embargo': 'NO_PARAMETER_SELECTION_NO_UNTOUCHED_OOS_CLAIM',
        'correlation_warning': 'OVERLAPPING_TARGET_WINDOWS_AND_THREE_SELECTED_SURVIVORS',
        'freeze_before_reveal': 'THIS_RUN_PERSISTED_FORECASTS_BEFORE_LABEL_CALCULATION_NOT_FIRST_HISTORICAL_EXPOSURE',
        'forward_prediction': 'NEW_OWNER_TEXT_IMPORT_OLD_EXTERNAL_ARTIFACT_ABSENT',
        'actual_G_semantics': 'UNCHANGED_OBSERVED_FACTS_THEN_HUMAN_CAPTURE_REVIEW_FORWARD_SEPARATE',
        'historical_expansion': 'NOT_AUTHORIZED_NO_NEW_DOWNLOADS', 'auto_run': False})
