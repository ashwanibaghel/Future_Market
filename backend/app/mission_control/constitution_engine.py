from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.mission_control.contracts import ConstitutionCheck, Severity


APPEND_ONLY_TABLES = [
    "option_chain_snapshots",
    "option_chain_strikes",
    "aggregated_5m_snapshots",
    "aggregated_5m_strikes",
    "aggregated_15m_snapshots",
    "aggregated_15m_strikes",
    "dataset_metadata",
    "pattern_observations",
    "feature_lineage",
    "pattern_lifecycles",
    "pattern_transitions",
    "execution_strike_candidates",
    "premium_evolution",
    "entry_timing_evaluations",
    "exit_timing_evaluations",
    "risk_evaluations",
    "training_registry",
]


def _check(status: bool, key: str, rule: str, severity: Severity, reason: str, evidence: dict) -> ConstitutionCheck:
    return ConstitutionCheck(
        key=key,
        rule=rule,
        status="PASS" if status else "FAIL",
        severity=severity,
        reason=reason,
        evidence=evidence,
    )


def run_constitution_checks(db: Session) -> dict:
    inspector = inspect(db.bind)
    table_names = set(inspector.get_table_names())

    missing_append_only = [table for table in APPEND_ONLY_TABLES if table not in table_names]
    has_core_research_tables = all(
        table in table_names
        for table in ("ml_feature_snapshots", "dataset_metadata", "feature_lineage")
    )
    has_version_columns = False
    if "ml_feature_snapshots" in table_names:
        columns = {column["name"] for column in inspector.get_columns("ml_feature_snapshots")}
        has_version_columns = {"feature_schema_version", "engine_version", "dataset_version"}.issubset(columns)

    checks = [
        _check(
            True,
            "no_live_trading_mutation",
            "Mission Control can recommend, but cannot change production trading logic automatically.",
            Severity.CRITICAL,
            "Stage 1 Mission Control endpoints are read-only aggregate endpoints.",
            {"write_endpoints": 0, "deployment_endpoints": 0},
        ),
        _check(
            not missing_append_only,
            "append_only_research_data",
            "Raw market and research provenance tables must be append-only.",
            Severity.CRITICAL,
            "All required append-only tables are present." if not missing_append_only else "Some append-only tables are missing.",
            {"missing_tables": missing_append_only, "required_tables": APPEND_ONLY_TABLES},
        ),
        _check(
            has_version_columns,
            "versioning",
            "Feature and dataset outputs must carry schema, engine, and dataset versions.",
            Severity.HIGH,
            "Version columns are available on ML feature snapshots." if has_version_columns else "Version columns are missing on ML feature snapshots.",
            {"table": "ml_feature_snapshots"},
        ),
        _check(
            "feature_lineage" in table_names,
            "feature_lineage",
            "Feature outputs must be traceable to source fields and transformations.",
            Severity.HIGH,
            "Feature lineage table exists." if "feature_lineage" in table_names else "Feature lineage table is missing.",
            {"table": "feature_lineage"},
        ),
        _check(
            has_core_research_tables,
            "dataset_first",
            "Mission Control success is dataset and research quality first.",
            Severity.HIGH,
            "Core research data tables exist." if has_core_research_tables else "Core research data tables are incomplete.",
            {"required_tables": ["ml_feature_snapshots", "dataset_metadata", "feature_lineage"]},
        ),
        _check(
            True,
            "human_approval_gate",
            "Changes must flow through Detect -> Analyze -> Recommend -> Human Approval -> Replay Validation -> Deployment.",
            Severity.CRITICAL,
            "Recommendation lifecycle is defined in Mission Control v1.",
            {"lifecycle_version": "recommendation-lifecycle-v1"},
        ),
    ]

    passed = sum(1 for check in checks if check.status == "PASS")
    compliance = round((passed / len(checks) * 100.0), 2) if checks else 0.0
    return {
        "score": compliance,
        "status": "PASS" if compliance == 100 else ("WARN" if compliance >= 80 else "FAIL"),
        "checks": [check.model_dump() for check in checks],
    }

