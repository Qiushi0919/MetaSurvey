# ADR-012 — Experimental incremental edge and cost stress
Status: P1-A experiment only. Production safety_multiple remains UNSET_REQUIRED.

Predetermined synthetic signals are fixed; no selection, score, timing or strategy optimization runs. Stress profiles LOW/BASE/HIGH vary explicit synthetic friction only. With Edge disabled signals, fills and gross PNL must be identical. With Edge enabled, every rejected tranche reports incremental-edge, net-edge or edge/cost-ratio reasons.

Each tranche's expected benefit is compared with its independent all-in transaction costs, including actual commission (and its minimum-effect attribution), stamp, exchange, other fees and slippage. Minimum effect is not double counted. Experimental multiples are fixture inputs and cannot become production defaults. CORE_40 has a 20–40-session target review horizon, not a forced minimum. Four explicit thesis/risk/material/structure invalidations permit earlier exit. EVENT_3 remains a namespace placeholder.
