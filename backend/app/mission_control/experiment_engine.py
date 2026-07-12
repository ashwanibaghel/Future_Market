from __future__ import annotations

from app.mission_control.contracts import Recommendation


def suggest_experiments(dataset_metrics: dict, rule_audit: dict, pattern_intelligence: dict, replay_intelligence: dict) -> dict:
    experiments = []

    if dataset_metrics.get("missing_iv_pct", 0.0) > 5 or dataset_metrics.get("missing_greeks_pct", 0.0) > 5:
        experiments.append({
            "id": "exp.options-completeness-backfill",
            "title": "Validate IV and Greeks completeness backfill",
            "hypothesis": "Improving IV/Greeks coverage will improve replay quality and ML feature completeness.",
            "current_value": {
                "missing_iv_pct": dataset_metrics.get("missing_iv_pct", 0.0),
                "missing_greeks_pct": dataset_metrics.get("missing_greeks_pct", 0.0),
            },
            "suggested_change": "Run provider-specific completeness audit and derived-dataset backfill plan.",
            "expected_impact": {"dataset_health": 4.5, "ml_readiness": 2.0},
            "confidence": 0.82,
            "risks": ["Backfill must remain derived data and must not rewrite raw provider payloads."],
            "validation_method": "Replay impacted sessions before and after derived backfill.",
            "production_mutation_allowed": False,
        })

    if rule_audit.get("signal_quality", {}).get("calibration_gap", 0.0) > 20:
        experiments.append({
            "id": "exp.confidence-calibration",
            "title": "Replay-test signal confidence calibration bands",
            "hypothesis": "Confidence scores are not aligned with resolved win rate.",
            "current_value": rule_audit.get("signal_quality", {}),
            "suggested_change": "Evaluate calibration curves by confidence band in replay mode.",
            "expected_impact": {"research_quality": 4.0, "ml_readiness": 1.5},
            "confidence": 0.74,
            "risks": ["Do not change thresholds until human approval and replay validation are complete."],
            "validation_method": "Historical replay split by confidence band and market regime.",
            "production_mutation_allowed": False,
        })

    if pattern_intelligence.get("sparse_patterns", 0) > pattern_intelligence.get("mature_patterns", 0):
        experiments.append({
            "id": "exp.pattern-coverage-sessions",
            "title": "Collect targeted sessions for sparse pattern families",
            "hypothesis": "More diverse market sessions will improve pattern reliability estimates.",
            "current_value": {
                "sparse_patterns": pattern_intelligence.get("sparse_patterns", 0),
                "mature_patterns": pattern_intelligence.get("mature_patterns", 0),
            },
            "suggested_change": "Prioritize bearish, expiry, and sideways sessions in dataset collection.",
            "expected_impact": {"dataset_health": 2.0, "pattern_reliability": 5.0},
            "confidence": 0.79,
            "risks": ["Impact depends on actual market regime availability."],
            "validation_method": "Compare pattern reliability intervals after new sessions.",
            "production_mutation_allowed": False,
        })

    if replay_intelligence.get("average_session_coverage_pct", 0.0) < 85:
        experiments.append({
            "id": "exp.replay-coverage-gap-repair",
            "title": "Improve full-day replay coverage",
            "hypothesis": "Replay validation quality is limited by session coverage gaps.",
            "current_value": {"average_session_coverage_pct": replay_intelligence.get("average_session_coverage_pct", 0.0)},
            "suggested_change": "Audit crawler availability and provider latency for partial sessions.",
            "expected_impact": {"replay_quality": 5.0, "dataset_health": 3.0},
            "confidence": 0.8,
            "risks": ["Recovered data must be versioned and marked as derived."],
            "validation_method": "Replay day completeness and timestamp continuity checks.",
            "production_mutation_allowed": False,
        })

    return {
        "engine": "Experiment Engine",
        "status": "READY",
        "experiments": experiments,
        "rule": "Experiments are suggestions only. Production logic changes require human approval and replay validation.",
    }


def recommendations_from_experiments(experiments: dict) -> list[Recommendation]:
    recommendations = []
    for item in experiments.get("experiments", []):
        recommendations.append(
            Recommendation(
                id=item["id"].replace("exp.", "rec.exp."),
                title=item["title"],
                module="experiment_engine",
                confidence=item["confidence"],
                supporting_evidence=[],
                supporting_metrics=item["current_value"] if isinstance(item["current_value"], dict) else {"current": item["current_value"]},
                expected_impact=item["expected_impact"],
                risks=item["risks"],
                affected_modules=["experiments", "replay", "dataset_health"],
            )
        )
    return recommendations

