from __future__ import annotations

from app.mission_control.contracts import EvidenceItem, Recommendation, Severity


def build_recommendations(evidence: list[EvidenceItem], metrics: dict) -> list[Recommendation]:
    recommendations: list[Recommendation] = []

    def add_from_evidence(
        key: str,
        title: str,
        module: str,
        evidence_ids: list[str],
        confidence: float,
        impact: dict[str, float],
        risks: list[str],
        affected_modules: list[str],
        supporting_metrics: dict,
    ) -> None:
        recommendations.append(
            Recommendation(
                id=f"rec.{key}",
                title=title,
                module=module,
                confidence=round(confidence, 2),
                supporting_evidence=evidence_ids,
                supporting_metrics=supporting_metrics,
                expected_impact=impact,
                risks=risks,
                affected_modules=affected_modules,
            )
        )

    evidence_by_metric = {item.metric: item for item in evidence}

    if "missing_iv_pct" in evidence_by_metric or "missing_greeks_pct" in evidence_by_metric:
        ids = [
            item.id
            for metric_name, item in evidence_by_metric.items()
            if metric_name in ("missing_iv_pct", "missing_greeks_pct")
        ]
        add_from_evidence(
            "repair-options-completeness",
            "Prioritize IV and Greeks completeness audit before new signal work",
            "dataset_health",
            ids,
            0.84,
            {"dataset_health": 4.5, "ml_readiness": 2.0, "replay_quality": 2.5},
            [
                "Provider payload may be inconsistent across symbols.",
                "Derived datasets may need a backfill run after validation.",
            ],
            ["dataset_health", "ml_readiness", "market_replay"],
            {
                "missing_iv_pct": metrics.get("missing_iv_pct", 0.0),
                "missing_greeks_pct": metrics.get("missing_greeks_pct", 0.0),
            },
        )

    if "collection_gaps" in evidence_by_metric:
        add_from_evidence(
            "close-crawl-gaps",
            "Investigate crawler continuity and provider latency windows",
            "dataset_inspector",
            [evidence_by_metric["collection_gaps"].id],
            0.81,
            {"dataset_health": 5.0, "replay_quality": 4.0, "ml_readiness": 1.5},
            [
                "Gap repair must not rewrite raw market data.",
                "Backfill must be marked as derived or provider-recovered data.",
            ],
            ["dataset_health", "market_replay", "lineage"],
            {
                "collection_gaps": metrics.get("collection_gaps", 0),
                "largest_gap_minutes": metrics.get("largest_gap_minutes", 0.0),
                "p95_latency_ms": metrics.get("p95_latency_ms", 0.0),
            },
        )

    if "duplicate_records" in evidence_by_metric:
        add_from_evidence(
            "dedupe-derived-features",
            "Add a derived-feature duplicate gate before training exports",
            "dataset_inspector",
            [evidence_by_metric["duplicate_records"].id],
            0.78,
            {"dataset_health": 2.5, "ml_readiness": 2.5, "governance": 1.0},
            [
                "Do not delete raw rows.",
                "Only derived export filters should suppress duplicates.",
            ],
            ["dataset_health", "ml_readiness", "exports"],
            {"duplicate_records": metrics.get("duplicate_records", 0)},
        )

    if metrics.get("lineage_coverage", 0.0) < 85:
        add_from_evidence(
            "increase-lineage-coverage",
            "Expand feature lineage coverage for pattern and replay features",
            "lineage",
            [item.id for item in evidence if item.severity in (Severity.HIGH, Severity.CRITICAL)],
            0.76,
            {"dataset_health": 3.0, "ml_readiness": 2.0, "explainability": 6.0},
            [
                "Lineage expansion can expose old derived rows with incomplete provenance.",
                "Requires versioned migration for derived datasets only.",
            ],
            ["lineage", "market_replay", "research_reports"],
            {
                "lineage_coverage": metrics.get("lineage_coverage", 0.0),
                "lineage_count": metrics.get("lineage_count", 0),
                "pattern_count": metrics.get("pattern_count", 0),
            },
        )

    if not recommendations:
        add_from_evidence(
            "continue-foundation-hardening",
            "Continue Stage 1 hardening and collect more labeled sessions",
            "roadmap",
            [item.id for item in evidence],
            0.68,
            {"dataset_health": 1.0, "ml_readiness": 1.5, "project_completion": 2.0},
            ["Impact depends on new market sessions becoming available."],
            ["project_tracker", "dataset_health", "ml_readiness"],
            {
                "total_samples": metrics.get("total_samples", 0),
                "label_coverage": metrics.get("label_coverage", 0.0),
            },
        )
    return recommendations

