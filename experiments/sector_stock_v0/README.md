# CORE40_SECTOR_STOCK_BASELINE_V0

Isolated, deterministic research-scoring experiment. No network, CLI data ingestion, optimizer, order or production capability. Uses existing locked `ajv`, `ajv-formats`, `decimal.js`; no dependency/lock changes.

From repository root (Node24+, existing dependencies installed with `npm ci --ignore-scripts`):

```sh
node --test experiments/sector_stock_v0/tests/engine.test.mjs
python3 -B -m unittest discover -s workbench/tests -v
python3 -B -m workbench.server --port 8765
```

Open `http://127.0.0.1:8765/`. Python3.12 stdlib runs the viewer; Node is only needed for offline experiment tests.

A fully reproducible **SYNTHETIC ONLY** two-layer computation:

```sh
node --input-type=module -e 'import {evaluate} from "./experiments/sector_stock_v0/engine.mjs"; import {pair} from "./experiments/sector_stock_v0/tests/fixtures.mjs"; const {stock,sector}=pair(); console.log(JSON.stringify(evaluate(stock.input,stock.bundle,sector),null,2));'
```

Expected synthetic stock score50.50: fundamental50×.25 + sector(50×.8)×.20 + catalyst50×.15 + trend50×.15 + valuation50×.10 + liquidity50×.10 + evidence100×.05. Invented identifiers/facts and scenario values are never production defaults. The viewer does not load or show these fixtures as real scores.

The structured inputs are precomputed evidence-backed features, not a raw financial extraction engine. See [rules](../../docs/sector-stock-v0/Scoring-Rules.md), [preregistration](../../docs/sector-stock-v0/Preregistration.json) and [acceptance](../../docs/sector-stock-v0/Acceptance-Report.md). Existing frozen strategy and native contracts are unchanged. Stop after engineering acceptance.
