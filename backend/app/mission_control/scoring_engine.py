from __future__ import annotations

from app.mission_control.contracts import ScoreCard, ScoreComponent


DATASET_HEALTH_WEIGHTS = {
    "feature_quality": 0.25,
    "label_coverage": 0.20,
    "metadata_coverage": 0.15,
    "lineage_coverage": 0.10,
    "continuity_score": 0.10,
    "duplicate_integrity": 0.08,
    "provider_stability": 0.07,
    "schema_version_consistency": 0.05,
}

ML_READINESS_WEIGHTS = {
    "label_coverage": 0.25,
    "feature_completeness": 0.20,
    "minimum_history": 0.15,
    "class_balance": 0.15,
    "drift_stability": 0.10,
    "leakage_safety": 0.10,
    "replay_support": 0.05,
}

PROJECT_COMPLETION_WEIGHTS = {
    "roadmap_completion": 0.25,
    "dataset_health": 0.25,
    "ml_readiness": 0.15,
    "lineage_coverage": 0.15,
    "constitution_compliance": 0.10,
    "mission_control_health": 0.10,
}

MISSION_CONTROL_HEALTH_WEIGHTS = {
    "api_availability": 0.30,
    "data_access": 0.25,
    "evidence_generation": 0.20,
    "scoring_available": 0.15,
    "recommendation_lifecycle_defined": 0.10,
}


LABELS = {
    "api_availability": "API availability",
    "class_balance": "Class balance",
    "constitution_compliance": "Constitution compliance",
    "continuity_score": "Collection continuity",
    "data_access": "Research data access",
    "dataset_health": "Dataset health",
    "drift_stability": "Feature drift stability",
    "duplicate_integrity": "Duplicate integrity",
    "evidence_generation": "Evidence generation",
    "feature_completeness": "Feature completeness",
    "feature_quality": "Feature quality",
    "label_coverage": "Label coverage",
    "leakage_safety": "Leakage safety",
    "lineage_coverage": "Lineage coverage",
    "metadata_coverage": "Metadata coverage",
    "minimum_history": "Minimum history",
    "mission_control_health": "Mission Control health",
    "provider_stability": "Provider stability",
    "recommendation_lifecycle_defined": "Recommendation lifecycle defined",
    "replay_support": "Replay support",
    "roadmap_completion": "Roadmap completion",
    "schema_version_consistency": "Schema/version consistency",
    "scoring_available": "Scoring available",
    "ml_readiness": "ML readiness",
}


def clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 2)


def score_status(score: float) -> str:
    if score >= 85:
        return "READY"
    if score >= 60:
        return "DEGRADED"
    return "BLOCKED"


def build_score_card(name: str, weights: dict[str, float], values: dict[str, float]) -> ScoreCard:
    components = []
    total = 0.0
    for key, weight in weights.items():
        value = clamp_score(values.get(key, 0.0))
        weighted_value = round(value * weight, 2)
        total += weighted_value
        components.append(
            ScoreComponent(
                key=key,
                label=LABELS.get(key, key.replace("_", " ").title()),
                value=value,
                weight=weight,
                weighted_value=weighted_value,
                target=85.0,
                status="PASS" if value >= 85 else ("WARN" if value >= 60 else "FAIL"),
            )
        )
    score = clamp_score(total)
    return ScoreCard(name=name, score=score, status=score_status(score), components=components)

