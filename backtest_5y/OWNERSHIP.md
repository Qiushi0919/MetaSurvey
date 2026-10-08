# P1 sidecar ownership

This phase is authorized by the Owner's current chat instructions. Earlier STOPs are superseded only within this scope. All existing tracked files, old evidence epochs, shared contracts, ADRs, migrations, StrategySpec, Forward Day0/Day1 and parent checkout are immutable. No automatic merge or push.

Root: backtest_5y/__init__.py, interface.py, requirements.py, gateway.py, run.py, dto.py, tests/test_integration.py; protocol.json, OWNERSHIP.md, README.md inside backtest_5y; new contracts/backtest-5y/ and docs/backtest-5y/. Root integrates and owns Git.

Data/PIT Agent: backtest_5y/data.py, collectors.py, sources.py, tests/test_data.py, tests/test_collectors.py. Private outputs only new epoch/data/.

Backtest Agent: backtest_5y/strategy.py, pit.py, tests/test_strategy.py, tests/test_pit.py. Private outputs only new epoch/backtest/. Reuse frozen Wave G price feature logic and Wave F pure helpers. Full-family prerequisites remain distinct from price-only observations. No ablation simulation authorized.

Cost/Risk Agent: backtest_5y/store.py, maintenance.py, economics.py, tests/test_store.py, tests/test_maintenance.py, tests/test_economics.py. Private outputs only new epoch/maintenance/. Reuse pure Wave F costs. Actual account remains UNSET_REQUIRED.

Independent Reviewer: read-only source and candidate; only new epoch/reviewer/ outputs. Independent adversarial checks of visibility, source versions, accounting, strategy hashes, disabled execution and update idempotency.

Private new epoch: /Users/qiushi/投资研究/.p1b-archives/backtest-5y-p1-20261008. Every run writes a new exclusive child; no overwrite of failed runs. No credentials in outputs. Python runs with bytecode disabled.
