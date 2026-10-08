# ADR-010 — Paper settlement and reservation
Status: P1-A engineering reference; broker settlement configuration is UNSET_REQUIRED.

The cost profile is explicit, versioned and synthetic. Integer-cent strings/BigInt and a private 100-digit Decimal constructor determine money; no IEEE-754 monetary arithmetic. Actual commission contains the proportional commission plus the minimum-commission effect. The effect is attribution only and is never added a second time to friction. Fees included in commission and slippage included in price are not charged twice.

Partial fills settle cumulative per-order fee differences. Reservations, settled cash and available cash persist across restart. Cash and risk limits belong to the account; lots and positions belong to account + strategy + security. The reference supports only DEV/PAPER and explicit sessions. No broker transport exists. A new independent ladder tranche is a new order paying its own minimum, not the incremental fill delta of an existing order.
