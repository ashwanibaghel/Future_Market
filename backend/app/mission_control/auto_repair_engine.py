from __future__ import annotations

from datetime import datetime


def build_auto_repair_plan(dataset: dict, lineage: dict, replay: dict) -> dict:
    actions = []

    def add_action(
        action_id: str,
        title: str,
        severity: str,
        can_auto_run: bool,
        repair_type: str,
        reason: str,
        expected_impact: dict[str, float],
        safety_rule: str,
    ) -> None:
        actions.append({
            "id": action_id,
            "title": title,
            "severity": severity,
            "can_auto_run": can_auto_run,
            "repair_type": repair_type,
            "reason": reason,
            "expected_impact": expected_impact,
            "safety_rule": safety_rule,
            "status": "READY_TO_RUN" if can_auto_run else "NEEDS_HUMAN_APPROVAL",
        })

    if dataset.get("duplicate_records", 0) > 0:
        add_action(
            "repair.derived-dataset-duplicate-filter",
            "Apply duplicate filter to derived training export",
            "HIGH",
            True,
            "DERIVED_EXPORT_FILTER",
            f"{dataset.get('duplicate_records', 0)} duplicate derived rows detected.",
            {"dataset_health": 2.5, "ml_readiness": 2.0},
            "Do not delete raw rows. Filter duplicates only in derived training/export layer.",
        )

    if dataset.get("collection_gaps", 0) > 0:
        add_action(
            "repair.crawl-gap-backfill-plan",
            "Create provider backfill queue for crawl gaps",
            "HIGH",
            True,
            "BACKFILL_QUEUE",
            f"{dataset.get('collection_gaps', 0)} crawl gaps detected.",
            {"dataset_health": 4.0, "replay_quality": 4.5},
            "Recovered rows must be versioned as provider-recovered or derived; raw captured rows remain append-only.",
        )

    if dataset.get("missing_iv_pct", 0.0) > 5 or dataset.get("missing_greeks_pct", 0.0) > 5:
        add_action(
            "repair.options-completeness-audit",
            "Run IV/Greeks completeness audit",
            "HIGH",
            True,
            "PROVIDER_COMPLETENESS_AUDIT",
            f"Missing IV {dataset.get('missing_iv_pct', 0.0)}%, missing Greeks {dataset.get('missing_greeks_pct', 0.0)}%.",
            {"dataset_health": 4.5, "ml_readiness": 2.0},
            "Audit and derived backfill only; no production signal formula change.",
        )

    if dataset.get("lineage_coverage", 0.0) < 85:
        add_action(
            "repair.lineage-backfill",
            "Backfill feature lineage for derived pattern rows",
            "MEDIUM",
            True,
            "DERIVED_LINEAGE_BACKFILL",
            f"Lineage coverage is {dataset.get('lineage_coverage', 0.0)}%.",
            {"explainability": 5.0, "ml_readiness": 1.5},
            "Only derived lineage records are created; source market data remains unchanged.",
        )

    if not lineage.get("versions", {}).get("version_consistency", False):
        add_action(
            "repair.version-consistency-report",
            "Generate version consistency report",
            "MEDIUM",
            True,
            "VERSION_REPORT",
            "Multiple dataset, feature, or engine versions are present.",
            {"governance": 3.0, "reproducibility": 4.0},
            "Report only unless human approves derived dataset migration.",
        )

    if replay.get("average_session_coverage_pct", 0.0) < 85:
        add_action(
            "repair.replay-session-coverage",
            "Prioritize replay session coverage repair",
            "HIGH",
            True,
            "REPLAY_COVERAGE_QUEUE",
            f"Average replay coverage is {replay.get('average_session_coverage_pct', 0.0)}%.",
            {"replay_quality": 5.0, "research_quality": 3.0},
            "Repair queue can fetch missing intervals; deployment still requires replay validation.",
        )

    return {
        "engine": "Auto Repair Engine",
        "status": "READY" if actions else "NO_ACTION_NEEDED",
        "generated_at": datetime.utcnow().isoformat(),
        "actions": actions,
        "summary": {
            "total_actions": len(actions),
            "auto_runnable": sum(1 for action in actions if action["can_auto_run"]),
            "needs_approval": sum(1 for action in actions if not action["can_auto_run"]),
        },
        "hard_limits": [
            "Never overwrite or delete raw market data.",
            "Never change production trading logic automatically.",
            "Formula changes require replay validation and human approval.",
        ],
    }


def run_auto_repair_dry_run(plan: dict) -> dict:
    return {
        "engine": "Auto Repair Engine",
        "mode": "DRY_RUN",
        "ran_at": datetime.utcnow().isoformat(),
        "actions": [
            {
                "id": action["id"],
                "title": action["title"],
                "would_run": action["can_auto_run"],
                "status": "SIMULATED" if action["can_auto_run"] else "WAITING_FOR_APPROVAL",
                "safety_rule": action["safety_rule"],
            }
            for action in plan.get("actions", [])
        ],
        "message": "Dry run only. No production trading logic or raw market data was modified.",
    }

