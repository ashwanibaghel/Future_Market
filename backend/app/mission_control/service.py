from __future__ import annotations

from sqlalchemy.orm import Session

from app.mission_control.auto_repair_engine import build_auto_repair_plan
from app.mission_control.constitution_engine import run_constitution_checks
from app.mission_control.cto_engine import build_ai_cto_report, build_roadmap_ai
from app.mission_control.dataset_inspector import build_dataset_health, collect_dataset_metrics, inspect_dataset
from app.mission_control.execution_intelligence import get_execution_intelligence
from app.mission_control.experiment_engine import recommendations_from_experiments, suggest_experiments
from app.mission_control.knowledge_engine import build_knowledge_graph
from app.mission_control.lineage_engine import get_lineage_summary
from app.mission_control.pattern_intelligence import get_pattern_intelligence
from app.mission_control.recommendation_engine import build_recommendations
from app.mission_control.replay_intelligence import get_replay_intelligence
from app.mission_control.roadmap_engine import get_project_tracker
from app.mission_control.rule_audit_engine import get_rule_audit
from app.mission_control.training_forecast import get_training_forecast
from app.mission_control.scoring_engine import (
    MISSION_CONTROL_HEALTH_WEIGHTS,
    ML_READINESS_WEIGHTS,
    PROJECT_COMPLETION_WEIGHTS,
    build_score_card,
)


def _class_balance_score(class_balance: dict[str, int]) -> float:
    total = sum(class_balance.values())
    if total == 0:
        return 0.0
    percentages = [count / total * 100.0 for count in class_balance.values()]
    if min(percentages) >= 20 and max(percentages) <= 60:
        return 100.0
    return max(0.0, 100.0 - (max(percentages) - min(percentages)))


def build_ml_readiness(metrics: dict, replay_support: float = 0.0) -> dict:
    minimum_history = min(100.0, (metrics.get("total_samples", 0) / 1000.0) * 100.0)
    feature_completeness = max(
        0.0,
        100.0
        - (
            metrics.get("missing_iv_pct", 0.0) * 0.35
            + metrics.get("missing_pcr_pct", 0.0) * 0.25
            + metrics.get("missing_greeks_pct", 0.0) * 0.25
            + metrics.get("missing_oi_pct", 0.0) * 0.15
        ),
    )
    values = {
        "label_coverage": metrics.get("label_coverage", 0.0),
        "feature_completeness": feature_completeness,
        "minimum_history": minimum_history,
        "class_balance": _class_balance_score(metrics.get("class_balance", {})),
        "drift_stability": metrics.get("schema_version_consistency", 0.0),
        "leakage_safety": 100.0,
        "replay_support": replay_support,
    }
    return build_score_card("ML Readiness Score", ML_READINESS_WEIGHTS, values).model_dump()


def build_mission_control_health(evidence_count: int) -> dict:
    values = {
        "api_availability": 100.0,
        "data_access": 100.0,
        "evidence_generation": 100.0 if evidence_count else 75.0,
        "scoring_available": 100.0,
        "recommendation_lifecycle_defined": 100.0,
    }
    return build_score_card("Mission Control Health Score", MISSION_CONTROL_HEALTH_WEIGHTS, values).model_dump()


def build_overview(db: Session, symbol: str | None = None, market_date: str | None = None) -> dict:
    roadmap = get_project_tracker()
    constitution = run_constitution_checks(db)
    dataset_health = build_dataset_health(db, symbol=symbol, market_date=market_date)
    metrics = dataset_health["metrics"]
    evidence = inspect_dataset(db, symbol=symbol, market_date=market_date)
    lineage = get_lineage_summary(db, symbol=symbol)
    ml_readiness = build_ml_readiness(metrics, replay_support=metrics.get("pattern_coverage", 0.0))
    mission_health = build_mission_control_health(len(evidence))
    replay_intelligence = get_replay_intelligence(db, symbol=symbol)
    pattern_intelligence = get_pattern_intelligence(db, symbol=symbol)
    rule_audit = get_rule_audit(db, symbol=symbol)
    execution_intelligence = get_execution_intelligence(db, symbol=symbol)
    training_forecast = get_training_forecast(db, symbol=symbol)
    auto_repair = build_auto_repair_plan(metrics, lineage, replay_intelligence)
    experiments = suggest_experiments(metrics, rule_audit, pattern_intelligence, replay_intelligence)
    recommendations = build_recommendations(evidence, metrics)
    recommendations.extend(recommendations_from_experiments(experiments))

    project_values = {
        "roadmap_completion": roadmap["overall_completion_pct"],
        "dataset_health": dataset_health["score_card"]["score"],
        "ml_readiness": ml_readiness["score"],
        "lineage_coverage": metrics.get("lineage_coverage", 0.0),
        "constitution_compliance": constitution["score"],
        "mission_control_health": mission_health["score"],
    }
    project_completion = build_score_card(
        "Project Completion Score",
        PROJECT_COMPLETION_WEIGHTS,
        project_values,
    ).model_dump()

    return {
        "product": {
            "name": "OI Lens Mission Control",
            "subtitle": "Research Operating System",
            "version": "mission-control-v1.0",
            "mode": "READ_ONLY_RESEARCH",
            "primary_success_metric": "Continuous improvement of dataset quality and research quality",
        },
        "roadmap": roadmap,
        "constitution": constitution,
        "scores": {
            "dataset_health": dataset_health["score_card"],
            "ml_readiness": ml_readiness,
            "project_completion": project_completion,
            "mission_control_health": mission_health,
        },
        "dataset": metrics,
        "lineage": lineage,
        "replay": replay_intelligence,
        "pattern_intelligence": pattern_intelligence,
        "rule_audit": rule_audit,
        "experiments": experiments,
        "execution_intelligence": execution_intelligence,
        "training_forecast": training_forecast,
        "auto_repair": auto_repair,
        "knowledge_graph": build_knowledge_graph(
            metrics,
            rule_audit,
            pattern_intelligence,
            execution_intelligence,
            lineage,
        ),
        "evidence": [item.model_dump() for item in evidence],
        "recommendations": [item.model_dump() for item in recommendations],
        "roadmap_ai": build_roadmap_ai(
            metrics,
            replay_intelligence,
            execution_intelligence,
            [item.model_dump() for item in recommendations],
        ),
        "ai_cto": build_ai_cto_report(
            {
                "dataset_health": dataset_health["score_card"],
                "ml_readiness": ml_readiness,
                "project_completion": project_completion,
                "mission_control_health": mission_health,
            },
            metrics,
            replay_intelligence,
            pattern_intelligence,
            rule_audit,
            execution_intelligence,
            [item.model_dump() for item in recommendations],
        ),
        "lifecycle": [
            "DETECTED",
            "VERIFIED",
            "EVIDENCE_CREATED",
            "RECOMMENDATION_GENERATED",
            "PENDING_APPROVAL",
            "REPLAY_VALIDATION",
            "APPROVED",
            "IMPLEMENTED",
            "MONITORED",
            "CLOSED",
        ],
        "guardrails": {
            "can_modify_trading_logic": False,
            "can_place_live_trades": False,
            "raw_market_data_append_only": True,
            "requires_human_approval": True,
        },
    }
