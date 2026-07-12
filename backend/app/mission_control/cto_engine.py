from __future__ import annotations

from datetime import datetime


def _priority_from_impacts(recommendations: list[dict]) -> list[dict]:
    ranked = []
    for item in recommendations:
        impact = sum(float(value or 0.0) for value in item.get("expected_impact", {}).values())
        confidence = float(item.get("confidence") or 0.0)
        ranked.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "priority_score": round(impact * confidence, 2),
            "confidence": confidence,
            "expected_impact": item.get("expected_impact", {}),
            "risks": item.get("risks", []),
            "affected_modules": item.get("affected_modules", []),
        })
    ranked.sort(key=lambda row: row["priority_score"], reverse=True)
    return ranked


def build_roadmap_ai(dataset: dict, replay: dict, execution: dict, recommendations: list[dict]) -> dict:
    priorities = _priority_from_impacts(recommendations)
    bottlenecks = []
    if dataset.get("label_coverage", 0.0) < 80:
        bottlenecks.append("Label coverage is below ML readiness threshold.")
    if dataset.get("missing_iv_pct", 0.0) > 5:
        bottlenecks.append("IV completeness is limiting dataset health.")
    if replay.get("average_session_coverage_pct", 0.0) < 85:
        bottlenecks.append("Replay coverage is limiting validation quality.")
    if execution.get("blockers"):
        bottlenecks.extend(execution["blockers"][:3])

    return {
        "engine": "Roadmap AI",
        "status": "READY",
        "current_bottlenecks": bottlenecks,
        "next_sprint": priorities[:5],
        "selection_rule": "Rank by expected impact multiplied by confidence, with dataset quality weighted above UI scope.",
    }


def build_ai_cto_report(
    scores: dict,
    dataset: dict,
    replay: dict,
    pattern: dict,
    rule_audit: dict,
    execution: dict,
    recommendations: list[dict],
) -> dict:
    roadmap_ai = build_roadmap_ai(dataset, replay, execution, recommendations)
    score_summary = {
        key: {"score": value.get("score"), "status": value.get("status")}
        for key, value in scores.items()
    }
    return {
        "engine": "AI CTO",
        "report_date": datetime.utcnow().date().isoformat(),
        "status": "READY",
        "today_summary": {
            "dataset_health": score_summary.get("dataset_health"),
            "ml_readiness": score_summary.get("ml_readiness"),
            "project_completion": score_summary.get("project_completion"),
            "mission_control_health": score_summary.get("mission_control_health"),
            "patterns": pattern.get("unique_patterns", 0),
            "replay_days": replay.get("total_replay_days", 0),
            "signals_audited": rule_audit.get("total_signals_audited", 0),
        },
        "bottlenecks": roadmap_ai["current_bottlenecks"],
        "recommended_next_sprint": roadmap_ai["next_sprint"],
        "engineering_principle": "Improve dataset quality and research quality before increasing signal count.",
        "deployment_gate": "Detect -> Analyze -> Recommend -> Human Approval -> Replay Validation -> Deployment",
    }

