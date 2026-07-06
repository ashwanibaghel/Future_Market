# Sprint 19 - Dataset Health Dashboard and Market Replay

## Objective

Make dataset quality visible before more research features are added. Sprint 19 turns the research page into an operational dashboard for health gates, coverage, label balance, pattern frequency, and historical replay.

## Frozen Boundary

- Dataset Health measures whether research data is training-ready.
- Market Replay is a read-only debugging surface.
- Replay must not mutate snapshots, labels, metadata, patterns, or lineage.
- Health score is a release gate, not a prediction score.
- No ML model, prediction UI, or auto-trading behavior is introduced in this sprint.

## Health Score

The `GET /api/ml-dataset-status` response now includes `health_summary`.

| Component | Weight |
| --- | ---: |
| Feature quality | 35 |
| Full label coverage | 20 |
| Pattern coverage | 15 |
| Metadata coverage | 15 |
| Collection continuity | 10 |
| Duplicate integrity | 5 |

Current local NIFTY data scores `64.5 / 100` with status `DEGRADED`. This is expected because the historical sample has no IV/Greeks, no full labels, and known collection gaps.

## Dataset Health Checks

The dashboard surfaces these release checks:

- Feature quality
- Full label coverage
- Pattern coverage
- Metadata coverage
- Duplicate records
- Collection gaps
- Crawl success
- IV availability
- Greeks availability

The goal is to make weak data impossible to ignore before ML experiments begin.

## Collection Health

`collection_health` reports:

- collection gaps
- largest gap in minutes
- crawl success percentage
- average crawl latency
- p95 crawl latency
- maximum crawl latency

This is derived from immutable feature snapshots and dataset metadata.

## Market Replay

`GET /api/replay/session` loads one market date as an IST trading session from `09:15` to `15:30`.

Query parameters:

```text
symbol=NIFTY
market_date=YYYY-MM-DD
```

The dashboard replay tab supports:

- load-by-date session replay
- previous and next step controls
- play, pause, and restart
- 1x, 5x, 10x, and 30x speed controls
- timeline slider
- pattern state, confidence, age, support, resistance, PCR, and IV delta
- feature lineage and replay insights for the selected step

Replay is intentionally observational. It helps debug what the engine saw at that point in time.

## UI Scope

`/research` now has three tabs:

- Dataset Health
- Market Replay
- Exports

The health tab displays release gate score, validation checks, coverage components, missing field rates, label balance, timeframe mix, collection health, and pattern frequency.

## Why ML Pattern Recognition Is Still On Hold

Unsupervised learning is not skipped permanently. It is delayed because the current priority is building a clean, versioned, explainable dataset.

Clustering models such as K-Means, GMM, HDBSCAN, and SOM need enough stable observations across multiple market regimes. If we train them now, clusters will mostly learn today's data gaps: missing IV, missing Greeks, sparse labels, and short history.

The deterministic Pattern Engine is the baseline. It gives stable IDs, lineage, versioning, replay verification, and a clean target for future comparison. Once dataset health improves, ML clusters can be added as a separate research layer and compared against deterministic patterns without replacing them prematurely.

## Definition Of Done

- [x] Database/API health metrics include score, checks, gaps, latency, metadata, pattern coverage, and duplicates.
- [x] Dataset Health dashboard is visible on `/research`.
- [x] Market Replay dashboard is visible on `/research`.
- [x] Replay session endpoint is read-only and bounded to one trading session.
- [x] Unit tests pass locally.
- [x] Frontend build passes locally.
- [x] Browser verification passes on desktop and mobile without horizontal overflow.
- [ ] Deploy to production.
- [ ] Observe 2-3 live market days before Sprint 20 starts.

## Verification

Local verification completed:

```text
python -m unittest discover -s app/engine -p "test_*.py"
npx eslint src/app/research/page.tsx
npm run build
```

Browser verification completed on `http://localhost:3000/research` for desktop and 390px mobile viewport.
