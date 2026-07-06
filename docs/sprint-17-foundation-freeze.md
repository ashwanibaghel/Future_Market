# Sprint 17 Foundation Freeze

## Frozen Core Architecture

The project is organized around six stable pillars:

1. Signal Engine
2. Pattern Engine
3. Research Dataset
4. Execution Dataset
5. Replay Engine
6. Dataset Health

Future work may improve each pillar, but should not replace or bypass this architecture.

## Research Freeze Policy

Before accepting a feature, answer:

1. Does it improve dataset quality?
2. Is the result explainable?
3. Can it be verified through replay?

Postpone the feature when two or more answers are no.

## Sprint Definition of Done

A sprint is complete only when:

- Database migrations are applied successfully.
- Unit and regression tests pass.
- Historical replay tests pass.
- Dataset health or data correctness measurably improves.
- Existing functionality remains operational.
- Documentation is updated.
- Live-market observation is completed after deployment.

## Sprint 17 Foundation Corrections

- Signal stats now imports the math dependency used by distribution and correlation calculations.
- API signal versions are restricted to `v2` and `v2.5`.
- Empty latest-signal responses use the weighted model's 100-point scale.
- `feature_version` and `dataset_version` now match the selected signal engine version.
- PCR volume and PCR trend direction are explicit, symmetric, and regression-tested.
- Market session labels convert stored UTC timestamps to IST before classification.
- Expiry parsing supports both `DD-Mon-YYYY` and `YYYY-MM-DD`.
- Closest failed rule selects the smallest contribution gap.
- Historical backfill maintains independent watermarks and coverage for both signal versions.

## Release Gate

Code completion does not close Sprint 17. Deploy the changes, observe live collection for two to three market days, review dataset health and replay output, and only then mark the sprint complete.

## July 6, 2026 Audit Baseline

- Successful raw snapshots: 60
- ML feature rows: 144
- Completed labels: 144
- Average data quality score: 60
- Missing PCR: 0%
- Missing IV: 100%
- Stored signal coverage: `v1=60`, `v2=0`, `v2.5=50`

The version-specific startup backfill is expected to repair historical `v2` and
`v2.5` coverage after deployment. Missing IV remains an explicit dataset-health
blocker because the active NSE NextApi payload does not provide IV and the
system does not yet contain a validated IV estimation engine.

## Known Repository Debt

- Frontend production build passes, but lint currently reports 85 errors and 53 warnings.
- A private SSH key and deployment archive are already tracked by Git. The ignore rules now block future private key additions, but the existing key must be rotated and removed from repository history through a separate security operation.
