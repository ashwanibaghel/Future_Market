# OI Lens Mission Control Spec v1

Mission Control is a separate Research Operating System inside OI Lens. It monitors, audits, validates, and improves the research pipeline. It does not participate in live trading decisions and it never modifies production trading logic automatically.

## Product Identity

Name: OI Lens Mission Control

Subtitle: Research Operating System

Primary success metric: continuous improvement of dataset quality, research reproducibility, explainability, and validation depth.

## Stage Plan

Stage 1 Foundation:

- Constitution Engine
- Dataset Health
- Dataset Inspector
- Lineage
- Project Tracker
- Mission Control Health

Stage 2 Research Intelligence:

- Replay Center
- Pattern Intelligence
- Rule Audit
- Experiment Engine
- ML Readiness

Stage 3 Leadership Intelligence:

- AI CTO
- Knowledge Graph
- Roadmap AI
- Execution Intelligence
- Recommendation Engine

## Constitution

These rules are non-negotiable:

1. Mission Control must remain separate from production trading logic.
2. No Mission Control module may place, alter, approve, or block live trades.
3. No module may modify production signal logic automatically.
4. Any proposed change must flow through Detect -> Analyze -> Recommend -> Human Approval -> Replay Validation -> Deployment.
5. Raw market data is append-only.
6. Derived datasets must be versioned.
7. Feature outputs must be traceable to source fields, transformations, and versions.
8. Recommendations must include confidence, supporting metrics, expected impact, risks, and affected modules.
9. Scores must be calculated from transparent formulas with fixed weights.
10. Replay and validation must avoid future-data leakage.
11. Research quality is more important than UI complexity or signal count.
12. Mission Control itself must expose health, freshness, and coverage.

## Data Contracts

Evidence:

- id
- module
- severity
- finding
- metric
- value
- target
- supporting_data
- confidence
- affected_modules
- created_at
- version

Recommendation:

- id
- title
- module
- status
- confidence
- supporting_evidence
- supporting_metrics
- expected_impact
- risks
- affected_modules
- lifecycle_state
- created_at
- version

Violation:

- id
- rule
- status
- severity
- reason
- evidence
- affected_modules
- created_at

Dataset Version:

- dataset_version
- source_tables
- feature_version
- engine_version
- row_count
- label_count
- schema_version
- created_at
- quality_score

Feature Lineage:

- feature_name
- feature_version
- source_fields
- source_values
- transformation
- output_value
- dataset_version
- created_at

Research Finding:

- id
- module
- finding_type
- severity
- summary
- metrics
- evidence_ids
- created_at
- version

Replay Session:

- symbol
- market_date
- start_time
- end_time
- replay_version
- snapshot_count
- hindsight_available
- leakage_safe

Experiment:

- id
- title
- hypothesis
- current_value
- proposed_value
- expected_impact
- confidence
- risks
- validation_method
- status

Research Report:

- id
- report_date
- summary
- scores
- bottlenecks
- recommendations
- evidence_ids
- version

## Scoring Formulas

All scores are 0 to 100. Weights are fixed in this spec unless a future constitution version changes them.

Dataset Health Score:

```text
0.25 * feature_quality
+ 0.20 * label_coverage
+ 0.15 * metadata_coverage
+ 0.10 * lineage_coverage
+ 0.10 * continuity_score
+ 0.08 * duplicate_integrity
+ 0.07 * provider_stability
+ 0.05 * schema_version_consistency
```

ML Readiness Score:

```text
0.25 * label_coverage
+ 0.20 * feature_completeness
+ 0.15 * minimum_history
+ 0.15 * class_balance
+ 0.10 * drift_stability
+ 0.10 * leakage_safety
+ 0.05 * replay_support
```

Project Completion Score:

```text
0.25 * roadmap_completion
+ 0.25 * dataset_health
+ 0.15 * ml_readiness
+ 0.15 * lineage_coverage
+ 0.10 * constitution_compliance
+ 0.10 * mission_control_health
```

Mission Control Health Score:

```text
0.30 * api_availability
+ 0.25 * data_access
+ 0.20 * evidence_generation
+ 0.15 * scoring_available
+ 0.10 * recommendation_lifecycle_defined
```

Severity:

- Critical: blocks research integrity or violates no-auto-trading/append-only rules.
- High: materially reduces dataset quality, labels, replay, or lineage.
- Medium: localized quality issue with limited blast radius.
- Low: cleanup, visibility, or non-blocking improvement.

Impact:

- Dataset impact: expected Dataset Health Score gain.
- ML impact: expected ML Readiness Score gain.
- Replay impact: expected replay coverage or validation gain.
- Governance impact: expected constitution compliance gain.

## Recommendation Lifecycle

Mission Control recommendations must move through this state machine:

```text
Detected
-> Verified
-> Evidence Created
-> Recommendation Generated
-> Pending Approval
-> Replay Validation
-> Approved
-> Implemented
-> Monitored
-> Closed
```

Allowed terminal states:

- Closed
- Rejected
- Superseded

Forbidden transitions:

- Recommendation Generated -> Deployment
- Pending Approval -> Deployment
- Detected -> Production Logic Change

## Stage 1 Acceptance Criteria

- Mission Control has its own backend namespace.
- Mission Control has its own API router.
- Mission Control has its own frontend route.
- Stage 1 endpoints are read-only.
- Dataset Health Score is transparent.
- Constitution checks are visible.
- Dataset Inspector creates evidence-like findings.
- Lineage coverage is visible.
- Project Tracker reports phase completion.
- Recommendations are evidence-backed and non-mutating.
