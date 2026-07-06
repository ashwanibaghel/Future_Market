# Sprint 18 - Independent Pattern Engine

## Objective

Build a research-only Pattern Engine that observes and classifies market structure without producing `BUY_CALL`, `BUY_PUT`, or `NO_TRADE` decisions.

## Frozen Boundary

- Signal Engine owns trading decisions.
- Pattern Engine owns deterministic market classification and pattern statistics.
- Pattern observations, dataset metadata, and feature lineage are append-only.
- Pattern Library is an aggregate index and may be updated as observations arrive.
- No ML model or auto-trading behavior is introduced in this sprint.

## Version Contract

| Contract | Current version |
| --- | --- |
| Pattern engine | `pattern-v1.0` |
| Feature schema | `v2.0` for new captures; historical rows retain their actual version |
| Research dataset | `research-v1.0` |
| Symbol schema | `v1` |

Changing classification thresholds or formulas requires a new version. Historical records must not be rewritten under a new interpretation.

## Research Tables

### `pattern_observations`

One immutable classification per source snapshot, timeframe, and engine version. It stores pattern ID, confidence, age, sequence start, component states, source values, and version identifiers.

### `pattern_library`

Versioned aggregate statistics by symbol, timeframe, and pattern ID. It stores observation frequency, average and maximum confidence, age statistics, and first/last seen timestamps.

### `dataset_metadata`

Immutable provenance for every captured observation: provider, API source, engine/feature/dataset versions, crawl latency, timezone, missing fields, and quality score.

### `feature_lineage`

Immutable derivation records for PCR, OI change, PCR change, pattern ID, and pattern confidence. Each record stores source fields, source values, transformation, and output.

## Capture Flow

```text
Provider payload
  -> immutable market snapshot and strikes
  -> analytics snapshot
  -> versioned ML feature snapshot
  -> independent Pattern Engine observation
  -> Signal Engine consumes pattern context
```

The same capture flow runs for `1m`, `5m`, and `15m` timeframes. Startup backfill processes existing feature snapshots chronologically and is idempotent.

## Replay Contract

Replay now emits, for every historical step:

- deterministic pattern ID and version
- pattern confidence
- pattern age
- trend, OI, and PCR component states
- in-memory feature lineage
- sequence reset after gaps greater than 30 minutes

Replay does not write research records.

## APIs

- `GET /api/patterns/library`
- `GET /api/patterns/observations`
- `GET /api/patterns/observations/{id}/lineage`
- `GET /api/dataset-metadata`
- `GET /api/ml-dataset-status` includes research coverage, missing Greeks/OI, and duplicate counts

## Definition Of Done

- [x] Database migration is idempotent.
- [x] Market snapshot updates are blocked by ORM and SQLite triggers.
- [x] Pattern capture is independent from signal scoring.
- [x] Capture and historical backfill are idempotent.
- [x] Feature lineage and dataset provenance are queryable.
- [x] Replay reproduces pattern evolution without database writes.
- [x] Unit and regression tests pass locally.
- [ ] Deploy to production.
- [ ] Observe 2-3 live market days before Sprint 19 starts.

## Known Data Limitation

The current NSE Next API payload does not provide IV or Greeks. Metadata records this absence explicitly; the engine does not fabricate those values.
