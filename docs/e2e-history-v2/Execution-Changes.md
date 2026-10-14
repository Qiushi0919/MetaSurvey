# V2 execution successor

This is an isolated successor. `experiments/e2e_pilot_v1` is unchanged. No real strategy outcomes were run by the execution implementation task; the tests below are synthetic engineering evidence only.

## Frozen meaning

The V2 protocol selects `CORE40_RECONSTRUCTED_PRICE_VOLUME_DIAGNOSTIC_V2`, with nine unchanged contemporary sample members, the preregistered 2025-10-01–2026-09-30 window and warmup beginning 2025-06-03. It is reconstructed-history diagnosis, never proof of original historical PIT, untouched OOS, full research effectiveness, or actual-account performance.

The public entry point is `experiments.e2e_history_v2.engine.run_diagnostic(case, provenance_verifier=None)`. `RULES` exports the inherited position, risk, timing and selection rules plus the explicitly frozen V2 clock, suspension and corporate-action rules. The pure V1 portfolio builder and existing hypothetical fee calculator are reused. No collector, secret lookup, broker, account, optimizer or database access is implemented here.

## Input contract

The module docstring and `tests/test_engine.py::case()` document the entire shape. The fixture generator is synthetic and must not be used to fill missing real observations.

Real inputs bind raw-byte SHA-256 references for `protocol.json` and the unchanged V1 `method.json`, the exact protocol fee schedule, namespace, strategy, nine-symbol/sector mapping and complete date scope. `calendar_coverage.days` contains every civil date with a sourced explicit `is_open`; the exchange-session calendar must be exactly its open-day subset. The window must equal the first and last open session inside the frozen dates; omission or date cropping blocks before execution.

`case.evidence` maps evidence references to source, source version, raw hash, nullable publication time, actual available/retrieval times and an explicit visibility assumption. These clocks are never replaced by historical simulation clocks. Each exchange session has separate `close_at`, `decision_at`, and `decision_clock_label=SIMULATED_POST_CLOSE_DECISION_TIME`. The frozen decision time is 18:00 Asia/Shanghai and must precede the next open.

A real case cannot authorize itself with a boolean. The root builder supplies a callable provenance verifier, which verifies original files and licensed purpose and returns a receipt with `verified`, a matching `case_hash`, `receipt_hash`, and purpose `LOCAL_HISTORICAL_DIAGNOSTIC`. The engine rejects absent or mismatched receipts. This contract still relies on the verifier to establish authenticity, scope and complete source-domain coverage; a content hash alone does not prove them.

## Suspension and corporate actions

Suspended rows require all four RAW OHLC fields to be null and share volume zero. They never become synthetic price bars. Held positions may be valued at the last genuine closing observation, marked stale. Existing exit requests remain pending; new entry requires 21 consecutive genuine tradable bars after a suspension. Holding age remains exchange sessions.

Corporate-action records are closed-shape: ID, symbol, record/ex/payment/share-availability dates, gross cash per old share, bonus and split ratios, simulated tax rate and evidence reference. Unknown fields representing rights or other complex events are rejected. Record and ex dates must be adjacent exchange sessions. Cash payment and additional-share availability require actual ISO dates only when the corresponding entitlement exists; otherwise the respective field may be null. A due date may be outside the window or on a closed day: payment is processed at the first later exchange session, and future entitlements remain outstanding at the terminal date. Unknown required dates, multiple unreviewed event compositions or fractional share entitlements block rather than disappear.

Record-date closing shares fix entitlements. At ex-date, and only then, prior known prices, stop and entry comparison are transformed by `(price - gross_cash_per_share) / (split_ratio + bonus_ratio)`. An already-pending entry's ATR is divided by the share ratio to preserve its price unit. Historical volume remains the original observed share volume as a conservative capacity limit. Internal causal prices and accounting use Decimal precision 80. At the unchanged V1 sizing-function boundary only, ATR rounds upward to 12 decimals and mark prices round HALF_EVEN to 12 decimals, within that helper’s bounded lexical input contract; actual RAW execution prices are unchanged. This avoids float conversion or rejecting normal nonterminating share-ratio arithmetic. This bridge was agreed before any real strategy result, is bound into V2 `RULES`/`rules_hash`, and exists solely to satisfy the unchanged V1 exact-numeric interface; it does not rewrite the frozen protocol or old helper. Future corporate actions never alter earlier decisions.

Net dividends use the frozen conservative 20% simulated withholding. They become receivables at ex-date and enter NAV, but become spendable cash only on payment. Integer new shares enter position value at ex-date and remain unavailable for sale until their specified date. An exit sells available shares and retains the remaining locked shares and pending exit. This is not a statement of an investor's actual dividend tax liability.

## Output and failures

Outputs retain every decision, fill, unfilled reason, hash-chained cash ledger entry, dividend event, daily cash, position lots and availability, receivables, equity and errors. `DATA_BLOCKED` means preflight failed before execution; `RUN_NO_TRADES` means an executed empty strategy; `SIMULATED_TRADES` means simulated fills occurred.

A runtime missing bar, unsupported fractional entitlement or other error returns `ENGINE_FAILED`, `engine_called=true`, `partial_run=true`, `failed_at`, and the preceding completed evidence plus any current-day completed ledger entries. It does not erase earlier fills or pretend the engine never ran. Reported partial performance is explicitly limited to completed days; final cash and positions may include later completed entries on the failing day and therefore must not be confused with the last completed day's NAV.

## Synthetic verification

32 unique tests currently cover dividends and cash reconciliation; receivable versus spendable cash; integer bonus shares and locked-share exits; hash-chain integrity; T+1; suspension without invented OHLC; recovery eligibility; failed exits; causal adjustment; separate source/decision clocks; partial failures; scope cropping; and provenance receipt binding.

Run from the repository root:

```sh
python3 -m unittest discover -s experiments/e2e_history_v2/tests -p test_engine.py -v
```

These tests establish execution arithmetic and boundaries. They are not evidence that a source has been admitted or that an investment method has predictive value.
