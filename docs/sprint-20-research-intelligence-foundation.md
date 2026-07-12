# Sprint 20 - Research Intelligence Foundation

## Objective

Convert the master improvement blueprint into production-safe foundations without starting ML training or auto-trading. The sprint strengthens dataset monitoring, Pattern Engine analytics, replay context, and future execution/risk/training datasets.

## Implemented Scope

### Dataset Integrity

- Added `GET /api/research/intelligence`.
- Added label monitor with completed, pending, expired, failed, completion percentage, and expected completion minutes.
- Added class imbalance detection for 15m, 30m, and 60m labels.
- Added weekly feature drift detection for PCR, PCR velocity, OI imbalance, average IV, IV change, ATR, order flow, and SR compression.
- Added feature distribution stats: mean, median, std dev, skewness, kurtosis, P5, P25, P50, P75, and P95.
- Added training readiness checklist with explicit `READY` / `NOT_READY` status.

### Pattern Engine V2 Analytics

- Added computed Pattern Leaderboard: occurrences, wins, losses, flats, win rate, reliability, average move, median move, max move, drawdown proxy, holding-time proxy, and confidence interval.
- Added computed Pattern Lifecycles from contiguous pattern sequences.
- Added computed Pattern Transitions between deterministic pattern IDs.
- Added Rule Leaderboard from feature lineage coverage.

### Execution, Risk, Training, and Feature Store Foundations

Created append-only foundation tables:

- `pattern_lifecycles`
- `pattern_transitions`
- `execution_strike_candidates`
- `premium_evolution`
- `entry_timing_evaluations`
- `exit_timing_evaluations`
- `risk_evaluations`
- `training_registry`
- `feature_store_definitions`

These tables are foundations only. No model training, prediction UI, or automated execution was added.

### Replay V2 Context

Replay payload now includes signal context:

- signal type
- raw signal
- confidence
- bullish score
- bearish score
- decision margin
- dynamic threshold
- closest failed rule
- suggested strike
- premium proxy
- ROI placeholder
- expected move proxy

### Research Dashboard

`/research` now includes a fourth tab:

- Dataset Health
- Research Intelligence
- Market Replay
- Exports

The Research Intelligence tab shows label monitor, training readiness, imbalance recommendations, feature drift, feature distributions, pattern leaderboard, rule leaderboard, feature importance proxy, correlation explorer, similar historical day proxy, and phase foundation counts.

## Architecture Guardrails

- Raw market data remains append-only.
- Research observations and execution/risk/training datasets are append-only.
- Signal Engine and Pattern Engine remain separate.
- ML is still on hold until dataset readiness passes.
- Auto-trading remains out of scope.

## Verification

Local verification completed:

```text
python -m unittest discover -s app/engine -p "test_*.py"
npx eslint src/app/research/page.tsx
npm run build
python -m app.db.migrate
```

Results:

- Backend tests: 51 passed.
- Research page lint: passed.
- Frontend production build: passed.
- Migration created new foundation tables and append-only triggers.

## Known Limitation

Feature importance uses a lightweight Pearson proxy for now, not Mutual Information or SHAP. This is intentional to avoid adding heavy ML dependencies before the dataset is ready.
