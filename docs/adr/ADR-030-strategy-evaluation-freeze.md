# ADR-030 — Freeze evaluation requirements before performance reveal

Status: accepted engineering protocol; Owner economic decisions outstanding.
Version1.0.0. A FrozenStrategySpec is an evaluation requirements contract.
Wave E MA20/MA60 remains an engineering diagnostic and is not the final Owner
strategy. No parameter optimisation or economic Edge inference is authorized.

Entry/exit, benchmark and return treatment, history range, acceptable drawdown,
minimum excess return/trades, trade frequency, chronological split/OOS and
multiple-testing policy remain UNSET_REQUIRED, alongside account/cost/risk
policies. Production account settings remain the existing30 UNSET fields;
strategy requirement fields are separately counted and not fabricated account
settings. Do not replace unknowns with synthetic fee scenarios.

The protocol requires freeze-before-reveal, next-session execution, T+1,
fee-inclusive affordability, raw/adjusted isolation, historical universe/PIT,
explicit terminal positions and documented dated fee/unit/rounding policies.
Actual formal evaluation entry unconditionally blocks in this phase. Changing
requirements/source/version invalidates the future comparison baseline;
economic thresholds require a separate human decision and versioned policy.
