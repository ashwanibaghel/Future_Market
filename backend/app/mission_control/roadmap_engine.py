from __future__ import annotations

from app.mission_control.contracts import RoadmapPhase


ROADMAP = [
    RoadmapPhase(
        phase="stage-1",
        title="Foundation",
        completion_pct=72.0,
        completed_tasks=5,
        total_tasks=7,
        status="IN_PROGRESS",
        modules=[
            "Constitution Engine",
            "Dataset Health",
            "Dataset Inspector",
            "Lineage",
            "Project Tracker",
            "Mission Control Health",
        ],
    ),
    RoadmapPhase(
        phase="stage-2",
        title="Research Intelligence",
        completion_pct=28.0,
        completed_tasks=2,
        total_tasks=7,
        status="PLANNED",
        modules=[
            "Replay Center",
            "Pattern Intelligence",
            "Rule Audit",
            "Experiment Engine",
            "ML Readiness",
        ],
    ),
    RoadmapPhase(
        phase="stage-3",
        title="Leadership Intelligence",
        completion_pct=8.0,
        completed_tasks=1,
        total_tasks=8,
        status="PLANNED",
        modules=[
            "AI CTO",
            "Knowledge Graph",
            "Roadmap AI",
            "Execution Intelligence",
            "Recommendation Engine",
        ],
    ),
]


def get_project_tracker() -> dict:
    phases = [phase.model_dump() for phase in ROADMAP]
    completed = sum(phase.completed_tasks for phase in ROADMAP)
    total = sum(phase.total_tasks for phase in ROADMAP)
    completion = round((completed / total * 100.0), 2) if total else 0.0
    return {
        "name": "OI Lens Mission Control",
        "version": "mission-control-v1.0",
        "overall_completion_pct": completion,
        "completed_tasks": completed,
        "total_tasks": total,
        "current_stage": "stage-1",
        "primary_success_metric": "Dataset quality and research quality improvement",
        "phases": phases,
    }

