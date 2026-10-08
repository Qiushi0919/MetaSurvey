# MetaSurvey P1 historical-data sidecar

Owner priority: complete data for both unchanged CORE_40 families and maintain it repeatably. Timing ablation is disabled. Existing Wave G features and Wave F pure cost arithmetic are reused; strict synthetic or actual-admission guards are not bypassed.

All current outputs carry NON_PIT_DIAGNOSTIC / NOT_FORMAL_OOS / NON_TRADEABLE. Provider rights, historical disclosure versions, units and complete state/action/calendar histories remain separate from successful collection. Actual account parameters are UNSET_REQUIRED. ENGINE_NOT_RUN metrics are null; no ledger or NAV is invented.

Run from `/Users/qiushi/投资研究/ashare-backtest-5y` using the bundled Python and `-B`. Output directories must be new children of `/Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008`. The database and exact raw blobs remain outside Git.

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m backtest_5y.run import --db /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/evidence.sqlite --output /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/example-new-import --packets /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/gateway-batch-01/packets.json --packets /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/data/Public-Batches-Metadata-v2.json --packets /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/public-financial-warmup-v3.json

PYTHONDONTWRITEBYTECODE=1 /Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m backtest_5y.run refresh --db /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/evidence.sqlite --output /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/example-new-refresh --sources public --through 2026-10-08

PYTHONDONTWRITEBYTECODE=1 /Users/qiushi/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -B -m backtest_5y.run check --db /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/evidence.sqlite --output /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008/example-new-check
```

`import` verifies existing pinned originals and reparses packet numeric rows from raw bytes. Exact repeat packets are idempotent. New captures are appended, and content-addressed raw blobs are rechecked. Structural/numeric invalidity rejects the whole batch; valid conflicting versions are retained and reported.

`refresh` actually consumes the update plan, collects an explicit batch, rechecks remaining gaps and emits another plan. PRICE/VALUATION/ACTION overlap uses 30 calendar days, including old missing intervals. This is an operational overlap, not a PIT guarantee. Financial, industry, status and universe data are swept over historical intervals; a vendor may expose only current restatements, which remains a reported gap. Calendar gaps require explicit exchange dates, never Monday-Friday inference. Sources without complete access are reported as BLOCKED_SOURCE_ACCESS.

Public collectors have bounded HTTPS requests, no credentials or implicit proxy, no endpoint fallback and no hidden retries. Gateway collection uses the already authorized fixed Keychain reference/HTTP endpoint and remains quarantined; IP concurrency errors stop the remaining request plan. Do not re-enable gateway collection until the stable-IP/access restriction is addressed. TUN can still affect both collectors. No machine-wide proxy settings were changed.

The engineering collection range is price/valuation2016 onward and financial2014 onward. The financial buffer supports early EV/EBITDA valuation inputs; it does not define the missing normalized-cycle method. Listing history, positive1260-observation availability and actual sessions govern warmup. The ranges do not establish a formal walk-forward anchor.

Each run emits requirements, coverage, DQ/conflicts, raw integrity, ingestion receipts, store summary, update plans, both-family prerequisites and precise execution blocking. `--through` manages newer data in the same database; historical strategy observations stay bounded to the frozen historical evaluation interval. No automatic schedule is installed.

Candidate metadata schemas live in `contracts/backtest-5y/`; they are submitted for main-controller field review. Internal DTO checks are limited to the current conservative consumer shape and do not certify complete JSON Schema compatibility. Six candidate DTOs do not replace native contracts or issue admission.

Tests: `python -B -m unittest discover -s backtest_5y/tests -p 'test_*.py' -v`. Real-data replay requires the unchanged external evidence roots. No remote CI or relocated raw-root portability is claimed.
