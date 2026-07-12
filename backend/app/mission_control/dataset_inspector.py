from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import DatasetMetadata, FeatureLineage, MLFeatureSnapshot, PatternObservation
from app.mission_control.contracts import EvidenceItem, Severity
from app.mission_control.scoring_engine import DATASET_HEALTH_WEIGHTS, build_score_card, clamp_score


EXPECTED_SECONDS = {"1m": 60, "5m": 300, "15m": 900}


def _safe_json(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _pct(numerator: float, denominator: float) -> float:
    return round((numerator / denominator * 100.0), 2) if denominator else 0.0


def _severity_for_pct(value: float, high: float, critical: float) -> Severity:
    if value >= critical:
        return Severity.CRITICAL
    if value >= high:
        return Severity.HIGH
    if value > 0:
        return Severity.MEDIUM
    return Severity.LOW


def collect_dataset_metrics(db: Session, symbol: str | None = None, market_date: str | None = None) -> dict[str, Any]:
    query = db.query(MLFeatureSnapshot)
    if symbol:
        query = query.filter(MLFeatureSnapshot.symbol == symbol.upper())
    if market_date:
        query = query.filter(MLFeatureSnapshot.market_date == market_date)

    total = query.count()
    completed_labels = query.filter(MLFeatureSnapshot.status == "COMPLETED").count()
    full_labels = query.filter(MLFeatureSnapshot.label_quality == "FULL").count()
    avg_quality = float(query.with_entities(func.avg(MLFeatureSnapshot.data_quality_score)).scalar() or 0.0)

    duplicate_groups = query.with_entities(
        MLFeatureSnapshot.source_table,
        MLFeatureSnapshot.source_snapshot_id,
        MLFeatureSnapshot.timeframe,
        MLFeatureSnapshot.feature_schema_version,
        func.count(MLFeatureSnapshot.id).label("row_count"),
    ).group_by(
        MLFeatureSnapshot.source_table,
        MLFeatureSnapshot.source_snapshot_id,
        MLFeatureSnapshot.timeframe,
        MLFeatureSnapshot.feature_schema_version,
    ).having(func.count(MLFeatureSnapshot.id) > 1).all()
    duplicate_records = sum(row.row_count - 1 for row in duplicate_groups)

    rows = query.with_entities(
        MLFeatureSnapshot.id,
        MLFeatureSnapshot.symbol,
        MLFeatureSnapshot.market_date,
        MLFeatureSnapshot.timeframe,
        MLFeatureSnapshot.timestamp,
        MLFeatureSnapshot.feature_flags,
        MLFeatureSnapshot.feature_schema_version,
        MLFeatureSnapshot.engine_version,
        MLFeatureSnapshot.dataset_version,
        MLFeatureSnapshot.pcr,
        MLFeatureSnapshot.average_iv,
        MLFeatureSnapshot.direction_15m,
        MLFeatureSnapshot.direction_30m,
        MLFeatureSnapshot.direction_60m,
    ).order_by(
        MLFeatureSnapshot.symbol,
        MLFeatureSnapshot.market_date,
        MLFeatureSnapshot.timeframe,
        MLFeatureSnapshot.timestamp,
    ).all()

    missing_iv = 0
    missing_pcr = 0
    version_counter = Counter()
    class_counter = {"UP": 0, "DOWN": 0, "SIDEWAYS": 0}
    previous_by_stream: dict[tuple[str, str, str], datetime] = {}
    collection_gaps = 0
    largest_gap_minutes = 0.0
    for row in rows:
        flags = _safe_json(row.feature_flags, {})
        if flags.get("has_iv") is False or row.average_iv in (None, 0):
            missing_iv += 1
        if flags.get("has_pcr") is False or row.pcr is None:
            missing_pcr += 1
        version_counter[(row.feature_schema_version, row.engine_version, row.dataset_version)] += 1
        for direction in (row.direction_15m, row.direction_30m, row.direction_60m):
            if direction in class_counter:
                class_counter[direction] += 1
        stream_key = (row.symbol or "", row.market_date or "", row.timeframe or "")
        previous_timestamp = previous_by_stream.get(stream_key)
        if previous_timestamp:
            gap_seconds = (row.timestamp - previous_timestamp).total_seconds()
            largest_gap_minutes = max(largest_gap_minutes, gap_seconds / 60.0)
            expected = EXPECTED_SECONDS.get(row.timeframe or "1m", 60)
            if gap_seconds > expected * 2.5:
                collection_gaps += 1
        previous_by_stream[stream_key] = row.timestamp

    metadata_query = db.query(DatasetMetadata)
    pattern_query = db.query(PatternObservation)
    lineage_query = db.query(FeatureLineage)
    if symbol:
        metadata_query = metadata_query.filter(DatasetMetadata.symbol == symbol.upper())
        pattern_query = pattern_query.filter(PatternObservation.symbol == symbol.upper())
    metadata_count = metadata_query.count()
    pattern_count = pattern_query.count()
    lineage_count = lineage_query.count()

    metadata_rows = metadata_query.with_entities(
        DatasetMetadata.crawl_latency_ms,
        DatasetMetadata.crawl_success,
        DatasetMetadata.missing_fields,
    ).all()
    missing_greeks = 0
    missing_oi = 0
    successful_crawls = 0
    latencies = []
    for row in metadata_rows:
        fields = _safe_json(row.missing_fields, [])
        if "greeks" in fields:
            missing_greeks += 1
        if "oi" in fields:
            missing_oi += 1
        if row.crawl_success:
            successful_crawls += 1
        if row.crawl_latency_ms is not None:
            latencies.append(float(row.crawl_latency_ms or 0))

    latencies.sort()
    p95_latency = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else 0.0
    crawl_success_pct = _pct(successful_crawls, len(metadata_rows))
    duplicate_integrity = 100.0 if duplicate_records == 0 else max(0.0, 100.0 - _pct(duplicate_records, total))
    continuity_score = 100.0 if collection_gaps == 0 else max(0.0, 100.0 - _pct(collection_gaps, max(1, total - 1)))
    version_consistency = 100.0 if len(version_counter) <= 1 else max(0.0, 100.0 - ((len(version_counter) - 1) * 15.0))

    return {
        "total_samples": total,
        "completed_labels": completed_labels,
        "full_labels": full_labels,
        "feature_quality": round(avg_quality, 2),
        "label_coverage": _pct(full_labels, total),
        "completed_label_coverage": _pct(completed_labels, total),
        "metadata_count": metadata_count,
        "metadata_coverage": _pct(metadata_count, total),
        "pattern_count": pattern_count,
        "pattern_coverage": _pct(pattern_count, total),
        "lineage_count": lineage_count,
        "lineage_coverage": _pct(lineage_count, max(1, pattern_count)),
        "missing_iv_pct": _pct(missing_iv, total),
        "missing_pcr_pct": _pct(missing_pcr, total),
        "missing_greeks_pct": _pct(missing_greeks, metadata_count),
        "missing_oi_pct": _pct(missing_oi, metadata_count),
        "duplicate_records": duplicate_records,
        "duplicate_integrity": round(duplicate_integrity, 2),
        "collection_gaps": collection_gaps,
        "largest_gap_minutes": round(largest_gap_minutes, 2),
        "continuity_score": round(continuity_score, 2),
        "crawl_success_pct": crawl_success_pct,
        "provider_stability": crawl_success_pct,
        "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "p95_latency_ms": round(p95_latency, 2),
        "version_groups": len(version_counter),
        "schema_version_consistency": round(version_consistency, 2),
        "class_balance": class_counter,
    }


def build_dataset_health(db: Session, symbol: str | None = None, market_date: str | None = None) -> dict[str, Any]:
    metrics = collect_dataset_metrics(db, symbol=symbol, market_date=market_date)
    score_values = {key: metrics.get(key, 0.0) for key in DATASET_HEALTH_WEIGHTS}
    score_card = build_score_card("Dataset Health Score", DATASET_HEALTH_WEIGHTS, score_values)
    return {"metrics": metrics, "score_card": score_card.model_dump()}


def inspect_dataset(db: Session, symbol: str | None = None, market_date: str | None = None) -> list[EvidenceItem]:
    metrics = collect_dataset_metrics(db, symbol=symbol, market_date=market_date)
    evidence: list[EvidenceItem] = []

    checks = [
        ("missing_iv", "Missing IV detected", "missing_iv_pct", 5.0, ["dataset_health", "ml_readiness", "replay"]),
        ("missing_pcr", "Missing PCR detected", "missing_pcr_pct", 3.0, ["dataset_health", "signal_audit"]),
        ("missing_greeks", "Missing Greeks detected", "missing_greeks_pct", 5.0, ["dataset_health", "execution_intelligence"]),
        ("missing_oi", "Missing OI detected", "missing_oi_pct", 2.0, ["dataset_health", "pattern_intelligence"]),
        ("crawl_gaps", "Collection gaps detected", "collection_gaps", 0, ["dataset_health", "market_replay"]),
        ("duplicates", "Duplicate feature rows detected", "duplicate_records", 0, ["dataset_health", "lineage"]),
        ("version_inconsistency", "Multiple schema/engine/dataset versions detected", "version_groups", 1, ["lineage", "ml_readiness"]),
    ]
    for key, finding, metric, target, modules in checks:
        value = metrics.get(metric, 0)
        violated = value > target if target == 0 else value > target
        if not violated:
            continue
        severity = Severity.HIGH
        if metric.endswith("_pct"):
            severity = _severity_for_pct(float(value), high=10.0, critical=25.0)
        elif metric == "collection_gaps" and value >= 5:
            severity = Severity.CRITICAL
        evidence.append(
            EvidenceItem(
                id=f"evidence.dataset.{key}",
                module="dataset_inspector",
                severity=severity,
                finding=finding,
                metric=metric,
                value=value,
                target=target,
                supporting_data=metrics,
                confidence=0.88 if metrics["total_samples"] else 0.55,
                affected_modules=modules,
            )
        )

    if metrics["total_samples"] == 0:
        evidence.append(
            EvidenceItem(
                id="evidence.dataset.no_samples",
                module="dataset_inspector",
                severity=Severity.CRITICAL,
                finding="No ML feature samples available for Mission Control audit",
                metric="total_samples",
                value=0,
                target=1,
                supporting_data=metrics,
                confidence=0.95,
                affected_modules=["dataset_health", "ml_readiness", "project_tracker"],
            )
        )
    return evidence

