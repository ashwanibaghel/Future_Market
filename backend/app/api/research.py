import io
import csv
import json
import math
from itertools import combinations
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterable, Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import (
    DatasetMetadata,
    EntryTimingEvaluation,
    ExecutionStrikeCandidate,
    ExitTimingEvaluation,
    FeatureLineage,
    FeatureStoreDefinition,
    MLFeatureSnapshot,
    PatternLibrary,
    PatternObservation,
    PremiumEvolution,
    RiskEvaluation,
    TrainingRegistry,
)

router = APIRouter()

FEATURE_COLUMNS = {
    "pcr": MLFeatureSnapshot.pcr,
    "pcr_velocity": MLFeatureSnapshot.pcr_velocity,
    "oi_imbalance": MLFeatureSnapshot.oi_imbalance,
    "average_iv": MLFeatureSnapshot.average_iv,
    "iv_change": MLFeatureSnapshot.iv_change,
    "atr": MLFeatureSnapshot.atr,
    "order_flow": MLFeatureSnapshot.order_flow,
    "sr_compression": MLFeatureSnapshot.sr_compression,
}


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return round(sorted_values[0], 4)
    position = (len(sorted_values) - 1) * pct
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(sorted_values[int(position)], 4)
    weight = position - lower
    return round(sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight, 4)


def _distribution(values: Iterable[Optional[float]]) -> dict:
    cleaned = sorted(float(value) for value in values if value is not None)
    count = len(cleaned)
    if not cleaned:
        return {
            "count": 0,
            "mean": 0.0,
            "median": 0.0,
            "std_dev": 0.0,
            "skewness": 0.0,
            "kurtosis": 0.0,
            "p5": 0.0,
            "p25": 0.0,
            "p50": 0.0,
            "p75": 0.0,
            "p95": 0.0,
        }
    mean = sum(cleaned) / count
    variance = sum((value - mean) ** 2 for value in cleaned) / count
    std_dev = math.sqrt(variance)
    if std_dev > 0:
        skewness = sum(((value - mean) / std_dev) ** 3 for value in cleaned) / count
        kurtosis = (sum(((value - mean) / std_dev) ** 4 for value in cleaned) / count) - 3
    else:
        skewness = 0.0
        kurtosis = 0.0
    return {
        "count": count,
        "mean": round(mean, 4),
        "median": _percentile(cleaned, 0.50),
        "std_dev": round(std_dev, 4),
        "skewness": round(skewness, 4),
        "kurtosis": round(kurtosis, 4),
        "p5": _percentile(cleaned, 0.05),
        "p25": _percentile(cleaned, 0.25),
        "p50": _percentile(cleaned, 0.50),
        "p75": _percentile(cleaned, 0.75),
        "p95": _percentile(cleaned, 0.95),
    }


def _class_counts(rows: list[MLFeatureSnapshot], horizon: str) -> dict:
    field = f"direction_{horizon}"
    counts = {"UP": 0, "DOWN": 0, "SIDEWAYS": 0}
    for row in rows:
        value = getattr(row, field, None)
        if value in counts:
            counts[value] += 1
    return counts


def _imbalance_summary(counts: dict) -> dict:
    total = sum(counts.values())
    pct = {key: round((value / total * 100.0), 2) if total else 0.0 for key, value in counts.items()}
    if not total:
        return {
            "counts": counts,
            "percentages": pct,
            "is_imbalanced": True,
            "recommendation": "Need labeled observations before class balance can be trusted.",
        }
    minority = min(pct, key=pct.get)
    majority = max(pct, key=pct.get)
    is_imbalanced = pct[minority] < 20.0 or pct[majority] > 60.0
    recommendation = (
        f"Need more {minority.lower()} observations."
        if is_imbalanced else
        "Class balance is usable for research."
    )
    return {
        "counts": counts,
        "percentages": pct,
        "is_imbalanced": is_imbalanced,
        "dominant_class": majority,
        "minority_class": minority,
        "recommendation": recommendation,
    }


def _week_start(market_date: Optional[str]) -> Optional[datetime]:
    if not market_date:
        return None
    try:
        parsed = datetime.strptime(market_date, "%Y-%m-%d")
    except ValueError:
        return None
    return parsed - timedelta(days=parsed.weekday())


def _drift_status(current: dict, previous: dict) -> tuple[str, float]:
    current_mean = current.get("mean", 0.0)
    previous_mean = previous.get("mean", 0.0)
    previous_std = previous.get("std_dev", 0.0)
    if not current.get("count") or not previous.get("count"):
        return "INSUFFICIENT_DATA", 0.0
    denominator = previous_std if previous_std > 0 else max(abs(previous_mean), 1.0)
    drift_score = abs(current_mean - previous_mean) / denominator
    if drift_score >= 1.5:
        return "HIGH", round(drift_score, 4)
    if drift_score >= 0.75:
        return "MEDIUM", round(drift_score, 4)
    return "LOW", round(drift_score, 4)


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 3 or len(xs) != len(ys):
        return 0.0
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denom_x == 0 or denom_y == 0:
        return 0.0
    return round(numerator / (denom_x * denom_y), 4)

@router.get("/ml-dataset-status")
def get_ml_dataset_status(
    symbol: Optional[str] = Query(None),
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Returns statistics and health metrics for the ML Feature Store.
    """
    query = db.query(MLFeatureSnapshot)
    if symbol:
        query = query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        query = query.filter(MLFeatureSnapshot.market_date == date)
        
    total_count = query.count()
    completed_count = query.filter(MLFeatureSnapshot.status == "COMPLETED").count()
    pending_count = total_count - completed_count

    # 1. Label quality breakdown
    quality_query = db.query(
        MLFeatureSnapshot.label_quality, func.count(MLFeatureSnapshot.id)
    )
    if symbol:
        quality_query = quality_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        quality_query = quality_query.filter(MLFeatureSnapshot.market_date == date)
    quality_counts = quality_query.group_by(MLFeatureSnapshot.label_quality).all()
    
    label_quality_breakdown = {
        "FULL": 0,
        "PARTIAL": 0,
        "INCOMPLETE": 0
    }
    for q, count in quality_counts:
        key = q if q else "INCOMPLETE"
        label_quality_breakdown[key] = count

    # 2. Timeframe breakdown
    timeframe_query = db.query(
        MLFeatureSnapshot.timeframe, func.count(MLFeatureSnapshot.id)
    )
    if symbol:
        timeframe_query = timeframe_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        timeframe_query = timeframe_query.filter(MLFeatureSnapshot.market_date == date)
    timeframe_counts = timeframe_query.group_by(MLFeatureSnapshot.timeframe).all()
    
    timeframe_breakdown = {
        "1m": 0,
        "5m": 0,
        "15m": 0
    }
    for t, count in timeframe_counts:
        if t in timeframe_breakdown:
            timeframe_breakdown[t] = count

    # 3. Expiry type breakdown
    expiry_query = db.query(
        MLFeatureSnapshot.expiry_type, func.count(MLFeatureSnapshot.id)
    )
    if symbol:
        expiry_query = expiry_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        expiry_query = expiry_query.filter(MLFeatureSnapshot.market_date == date)
    expiry_counts = expiry_query.group_by(MLFeatureSnapshot.expiry_type).all()
    
    expiry_breakdown = {
        "WEEKLY": 0,
        "MONTHLY": 0
    }
    for exp, count in expiry_counts:
        if exp in expiry_breakdown:
            expiry_breakdown[exp] = count

    # 4. Data Quality Metrics
    q_query = db.query(func.avg(MLFeatureSnapshot.data_quality_score))
    if symbol:
        q_query = q_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        q_query = q_query.filter(MLFeatureSnapshot.market_date == date)
    avg_quality = q_query.scalar() or 0.0
    avg_quality = round(float(avg_quality), 2)
    
    iv_query = db.query(MLFeatureSnapshot).filter(
        MLFeatureSnapshot.feature_flags.like('%"has_iv": false%')
    )
    pcr_query = db.query(MLFeatureSnapshot).filter(
        MLFeatureSnapshot.feature_flags.like('%"has_pcr": false%')
    )
    if symbol:
        iv_query = iv_query.filter(MLFeatureSnapshot.symbol == symbol)
        pcr_query = pcr_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        iv_query = iv_query.filter(MLFeatureSnapshot.market_date == date)
        pcr_query = pcr_query.filter(MLFeatureSnapshot.market_date == date)
        
    missing_iv_count = iv_query.count()
    missing_pcr_count = pcr_query.count()
    
    missing_iv_pct = round((missing_iv_count / total_count * 100.0), 2) if total_count > 0 else 0.0
    missing_pcr_pct = round((missing_pcr_count / total_count * 100.0), 2) if total_count > 0 else 0.0

    # 5. Research provenance and pattern coverage
    pattern_query = db.query(PatternObservation).join(
        MLFeatureSnapshot, PatternObservation.feature_snapshot_id == MLFeatureSnapshot.id
    )
    if symbol:
        pattern_query = pattern_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        pattern_query = pattern_query.filter(MLFeatureSnapshot.market_date == date)
    pattern_observation_count = pattern_query.with_entities(
        PatternObservation.feature_snapshot_id
    ).distinct().count()

    metadata_query = db.query(DatasetMetadata).join(
        PatternObservation, PatternObservation.dataset_metadata_id == DatasetMetadata.id
    ).join(MLFeatureSnapshot, PatternObservation.feature_snapshot_id == MLFeatureSnapshot.id)
    if symbol:
        metadata_query = metadata_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        metadata_query = metadata_query.filter(MLFeatureSnapshot.market_date == date)
    metadata_count = metadata_query.with_entities(DatasetMetadata.id).distinct().count()
    missing_greeks_count = metadata_query.filter(
        DatasetMetadata.missing_fields.like('%"greeks"%')
    ).with_entities(DatasetMetadata.id).distinct().count()
    missing_oi_count = metadata_query.filter(
        DatasetMetadata.missing_fields.like('%"oi"%')
    ).with_entities(DatasetMetadata.id).distinct().count()

    lineage_query = db.query(FeatureLineage).join(
        PatternObservation, FeatureLineage.pattern_observation_id == PatternObservation.id
    ).join(MLFeatureSnapshot, PatternObservation.feature_snapshot_id == MLFeatureSnapshot.id)
    if symbol:
        lineage_query = lineage_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        lineage_query = lineage_query.filter(MLFeatureSnapshot.market_date == date)
    lineage_count = lineage_query.count()

    duplicate_query = db.query(
        MLFeatureSnapshot.source_table,
        MLFeatureSnapshot.source_snapshot_id,
        MLFeatureSnapshot.timeframe,
        MLFeatureSnapshot.feature_schema_version,
        func.count(MLFeatureSnapshot.id).label("row_count"),
    )
    if symbol:
        duplicate_query = duplicate_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        duplicate_query = duplicate_query.filter(MLFeatureSnapshot.market_date == date)
    duplicate_groups = duplicate_query.group_by(
        MLFeatureSnapshot.source_table,
        MLFeatureSnapshot.source_snapshot_id,
        MLFeatureSnapshot.timeframe,
        MLFeatureSnapshot.feature_schema_version,
    ).having(func.count(MLFeatureSnapshot.id) > 1).all()
    duplicate_records = sum(row.row_count - 1 for row in duplicate_groups)

    metadata_coverage_pct = round((metadata_count / total_count * 100.0), 2) if total_count else 0.0
    pattern_coverage_pct = round((pattern_observation_count / total_count * 100.0), 2) if total_count else 0.0
    missing_greeks_pct = round((missing_greeks_count / metadata_count * 100.0), 2) if metadata_count else 0.0
    missing_oi_pct = round((missing_oi_count / metadata_count * 100.0), 2) if metadata_count else 0.0

    # 6. Class balance breakdown across horizons
    class_balance = {
        "15m": {"UP": 0, "DOWN": 0, "SIDEWAYS": 0},
        "30m": {"UP": 0, "DOWN": 0, "SIDEWAYS": 0},
        "60m": {"UP": 0, "DOWN": 0, "SIDEWAYS": 0}
    }
    
    # 15m counts
    c15_query = db.query(
        MLFeatureSnapshot.direction_15m, func.count(MLFeatureSnapshot.id)
    ).filter(MLFeatureSnapshot.direction_15m.isnot(None))
    if symbol:
        c15_query = c15_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        c15_query = c15_query.filter(MLFeatureSnapshot.market_date == date)
    counts_15 = c15_query.group_by(MLFeatureSnapshot.direction_15m).all()
    for direction, count in counts_15:
        if direction in class_balance["15m"]:
            class_balance["15m"][direction] = count

    # 30m counts
    c30_query = db.query(
        MLFeatureSnapshot.direction_30m, func.count(MLFeatureSnapshot.id)
    ).filter(MLFeatureSnapshot.direction_30m.isnot(None))
    if symbol:
        c30_query = c30_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        c30_query = c30_query.filter(MLFeatureSnapshot.market_date == date)
    counts_30 = c30_query.group_by(MLFeatureSnapshot.direction_30m).all()
    for direction, count in counts_30:
        if direction in class_balance["30m"]:
            class_balance["30m"][direction] = count

    # 60m counts
    c60_query = db.query(
        MLFeatureSnapshot.direction_60m, func.count(MLFeatureSnapshot.id)
    ).filter(MLFeatureSnapshot.direction_60m.isnot(None))
    if symbol:
        c60_query = c60_query.filter(MLFeatureSnapshot.symbol == symbol)
    if date:
        c60_query = c60_query.filter(MLFeatureSnapshot.market_date == date)
    counts_60 = c60_query.group_by(MLFeatureSnapshot.direction_60m).all()
    for direction, count in counts_60:
        if direction in class_balance["60m"]:
            class_balance["60m"][direction] = count

    # 7. Operational collection health
    timeline_rows = query.with_entities(
        MLFeatureSnapshot.symbol,
        MLFeatureSnapshot.market_date,
        MLFeatureSnapshot.timeframe,
        MLFeatureSnapshot.timestamp,
    ).order_by(
        MLFeatureSnapshot.symbol,
        MLFeatureSnapshot.market_date,
        MLFeatureSnapshot.timeframe,
        MLFeatureSnapshot.timestamp,
    ).all()
    expected_seconds = {"1m": 60, "5m": 300, "15m": 900}
    previous_by_stream = {}
    collection_gaps = 0
    largest_gap_minutes = 0.0
    for row in timeline_rows:
        stream_key = (row.symbol, row.market_date, row.timeframe)
        previous_timestamp = previous_by_stream.get(stream_key)
        if previous_timestamp:
            gap_seconds = (row.timestamp - previous_timestamp).total_seconds()
            largest_gap_minutes = max(largest_gap_minutes, gap_seconds / 60.0)
            expected = expected_seconds.get(row.timeframe, 60)
            if gap_seconds > expected * 2.5:
                collection_gaps += 1
        previous_by_stream[stream_key] = row.timestamp

    metadata_rows = metadata_query.with_entities(
        DatasetMetadata.crawl_latency_ms,
        DatasetMetadata.crawl_success,
    ).all()
    latencies = sorted(
        float(row.crawl_latency_ms or 0) for row in metadata_rows if row.crawl_latency_ms is not None
    )
    successful_crawls = sum(1 for row in metadata_rows if row.crawl_success)
    crawl_success_pct = round(
        (successful_crawls / len(metadata_rows) * 100.0), 2
    ) if metadata_rows else 0.0
    average_latency_ms = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    p95_latency_ms = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else 0.0
    maximum_latency_ms = latencies[-1] if latencies else 0.0

    pattern_library_query = db.query(PatternLibrary)
    if symbol:
        pattern_library_query = pattern_library_query.filter(PatternLibrary.symbol == symbol)
    unique_patterns = pattern_library_query.count()

    full_label_pct = round(
        (label_quality_breakdown["FULL"] / total_count * 100.0), 2
    ) if total_count else 0.0
    continuity_pct = round(
        max(0.0, 100.0 - ((collection_gaps / max(1, total_count - 1)) * 100.0)), 2
    ) if total_count else 0.0
    duplicate_integrity_pct = 100.0 if duplicate_records == 0 else max(
        0.0, 100.0 - ((duplicate_records / max(1, total_count)) * 100.0)
    )
    health_components = {
        "feature_quality": round(avg_quality, 2),
        "full_label_coverage": full_label_pct,
        "pattern_coverage": pattern_coverage_pct,
        "metadata_coverage": metadata_coverage_pct,
        "continuity": continuity_pct,
        "duplicate_integrity": round(duplicate_integrity_pct, 2),
    }
    health_score = round(
        (health_components["feature_quality"] * 0.35)
        + (health_components["full_label_coverage"] * 0.20)
        + (health_components["pattern_coverage"] * 0.15)
        + (health_components["metadata_coverage"] * 0.15)
        + (health_components["continuity"] * 0.10)
        + (health_components["duplicate_integrity"] * 0.05),
        1,
    )
    health_status = "READY" if health_score >= 85 else ("DEGRADED" if health_score >= 60 else "BLOCKED")
    health_checks = [
        {"key": "feature_quality", "label": "Feature quality", "passed": avg_quality >= 80, "value": round(avg_quality, 2), "target": 80},
        {"key": "full_labels", "label": "Full label coverage", "passed": full_label_pct >= 95, "value": full_label_pct, "target": 95},
        {"key": "patterns", "label": "Pattern coverage", "passed": pattern_coverage_pct >= 99, "value": pattern_coverage_pct, "target": 99},
        {"key": "metadata", "label": "Metadata coverage", "passed": metadata_coverage_pct >= 99, "value": metadata_coverage_pct, "target": 99},
        {"key": "duplicates", "label": "Duplicate records", "passed": duplicate_records == 0, "value": duplicate_records, "target": 0},
        {"key": "gaps", "label": "Collection gaps", "passed": collection_gaps == 0, "value": collection_gaps, "target": 0},
        {"key": "crawl_success", "label": "Crawl success", "passed": crawl_success_pct >= 99, "value": crawl_success_pct, "target": 99},
        {"key": "iv", "label": "IV availability", "passed": missing_iv_pct <= 5, "value": round(100.0 - missing_iv_pct, 2), "target": 95},
        {"key": "greeks", "label": "Greeks availability", "passed": missing_greeks_pct <= 5, "value": round(100.0 - missing_greeks_pct, 2), "target": 95},
    ]

    return {
        "total_samples": total_count,
        "completed_labels": completed_count,
        "pending_labels": pending_count,
        "label_quality_breakdown": label_quality_breakdown,
        "timeframe_breakdown": timeframe_breakdown,
        "expiry_breakdown": expiry_breakdown,
        "data_quality_metrics": {
            "avg_quality_score": avg_quality,
            "missing_iv_pct": missing_iv_pct,
            "missing_pcr_pct": missing_pcr_pct,
            "missing_greeks_pct": missing_greeks_pct,
            "missing_oi_pct": missing_oi_pct,
            "duplicate_records": duplicate_records,
        },
        "research_coverage": {
            "pattern_observations": pattern_observation_count,
            "feature_lineage_records": lineage_count,
            "metadata_records": metadata_count,
            "pattern_coverage_pct": pattern_coverage_pct,
            "metadata_coverage_pct": metadata_coverage_pct,
            "unique_patterns": unique_patterns,
        },
        "collection_health": {
            "collection_gaps": collection_gaps,
            "largest_gap_minutes": round(largest_gap_minutes, 2),
            "crawl_success_pct": crawl_success_pct,
            "average_latency_ms": average_latency_ms,
            "p95_latency_ms": round(p95_latency_ms, 2),
            "maximum_latency_ms": round(maximum_latency_ms, 2),
        },
        "health_summary": {
            "score": health_score,
            "status": health_status,
            "components": health_components,
            "checks": health_checks,
        },
        "class_balance": class_balance
    }


@router.get("/research/intelligence")
def get_research_intelligence(
    symbol: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Research-first monitoring layer across dataset, drift, patterns, execution, and training readiness."""
    query = db.query(MLFeatureSnapshot)
    if symbol:
        query = query.filter(MLFeatureSnapshot.symbol == symbol.upper())
    rows = query.order_by(MLFeatureSnapshot.timestamp.asc()).all()
    total = len(rows)
    now = datetime.utcnow()

    completed = sum(1 for row in rows if row.status == "COMPLETED")
    failed = sum(1 for row in rows if row.status == "FAILED")
    pending_rows = [row for row in rows if row.status not in ("COMPLETED", "FAILED")]
    expired = sum(1 for row in pending_rows if row.label_ready_at and row.label_ready_at < now)
    future_ready_times = [row.label_ready_at for row in pending_rows if row.label_ready_at and row.label_ready_at > now]
    expected_completion_minutes = 0
    if future_ready_times:
        expected_completion_minutes = max(
            0,
            int((max(future_ready_times) - now).total_seconds() // 60),
        )

    label_monitor = {
        "total": total,
        "completed": completed,
        "pending": len(pending_rows),
        "expired": expired,
        "failed": failed,
        "completion_pct": round((completed / total * 100.0), 2) if total else 0.0,
        "expected_completion_minutes": expected_completion_minutes,
    }

    imbalance = {
        horizon: _imbalance_summary(_class_counts(rows, horizon))
        for horizon in ("15m", "30m", "60m")
    }

    week_groups: dict[str, list[MLFeatureSnapshot]] = defaultdict(list)
    for row in rows:
        week = _week_start(row.market_date)
        if week:
            week_groups[week.strftime("%Y-%m-%d")].append(row)
    week_keys = sorted(week_groups.keys())
    current_week_key = week_keys[-1] if week_keys else None
    previous_week_key = week_keys[-2] if len(week_keys) >= 2 else None
    current_week = week_groups.get(current_week_key, [])
    previous_week = week_groups.get(previous_week_key, [])

    feature_distribution = {}
    feature_drift = {}
    for feature_name, column in FEATURE_COLUMNS.items():
        values = [getattr(row, feature_name) for row in rows]
        current_distribution = _distribution(getattr(row, feature_name) for row in current_week)
        previous_distribution = _distribution(getattr(row, feature_name) for row in previous_week)
        status, score = _drift_status(current_distribution, previous_distribution)
        feature_distribution[feature_name] = _distribution(values)
        feature_drift[feature_name] = {
            "status": status,
            "score": score,
            "current_week": current_week_key,
            "previous_week": previous_week_key,
            "current": current_distribution,
            "previous": previous_distribution,
        }

    target_pairs = []
    for feature_name in FEATURE_COLUMNS:
        xs = []
        ys = []
        for row in rows:
            feature_value = getattr(row, feature_name)
            target_value = row.return_30m_pct
            if feature_value is not None and target_value is not None:
                xs.append(float(feature_value))
                ys.append(float(target_value))
        target_pairs.append({
            "feature": feature_name,
            "method": "pearson_proxy",
            "score": _pearson(xs, ys),
            "sample_size": len(xs),
        })
    target_pairs.sort(key=lambda item: abs(item["score"]), reverse=True)

    correlation_pairs = []
    for left, right in combinations(FEATURE_COLUMNS.keys(), 2):
        xs = []
        ys = []
        for row in rows:
            left_value = getattr(row, left)
            right_value = getattr(row, right)
            if left_value is not None and right_value is not None:
                xs.append(float(left_value))
                ys.append(float(right_value))
        correlation = _pearson(xs, ys)
        if xs:
            correlation_pairs.append({
                "left": left,
                "right": right,
                "correlation": correlation,
                "sample_size": len(xs),
            })
    correlation_pairs.sort(key=lambda item: abs(item["correlation"]), reverse=True)
    strong_correlations = [item for item in correlation_pairs if abs(item["correlation"]) >= 0.70][:10]
    redundant_features = [item for item in correlation_pairs if abs(item["correlation"]) >= 0.90][:10]

    pattern_count = db.query(PatternObservation.id)
    metadata_count = db.query(DatasetMetadata.id)
    if symbol:
        pattern_count = pattern_count.filter(PatternObservation.symbol == symbol.upper())
        metadata_count = metadata_count.filter(DatasetMetadata.symbol == symbol.upper())
    pattern_coverage = round((pattern_count.count() / total * 100.0), 2) if total else 0.0
    metadata_coverage = round((metadata_count.count() / total * 100.0), 2) if total else 0.0

    metadata_rows = metadata_count.with_entities(
        DatasetMetadata.crawl_success,
        DatasetMetadata.missing_fields,
    ).all()
    crawl_success_pct = round(
        (sum(1 for row in metadata_rows if row.crawl_success) / len(metadata_rows) * 100.0), 2
    ) if metadata_rows else 0.0
    missing_field_hits = 0
    for row in metadata_rows:
        try:
            missing_field_hits += len(json.loads(row.missing_fields or "[]"))
        except json.JSONDecodeError:
            missing_field_hits += 1
    missing_value_pressure = round(
        (missing_field_hits / max(1, len(metadata_rows) * 4)) * 100.0, 2
    ) if metadata_rows else 100.0

    feature_versions = {row.feature_schema_version for row in rows if row.feature_schema_version}
    dataset_versions = {row.dataset_version for row in rows if row.dataset_version}
    high_drift_features = [
        name for name, payload in feature_drift.items()
        if payload["status"] == "HIGH"
    ]
    balance_ok = all(not payload["is_imbalanced"] for payload in imbalance.values())
    readiness_checks = [
        {"key": "minimum_samples", "label": "Minimum samples", "passed": total >= 1000, "value": total, "target": 1000},
        {"key": "class_balance", "label": "Class balance", "passed": balance_ok, "value": 0 if balance_ok else 1, "target": 0},
        {"key": "label_completion", "label": "Label completion", "passed": label_monitor["completion_pct"] >= 80, "value": label_monitor["completion_pct"], "target": 80},
        {"key": "pattern_coverage", "label": "Pattern coverage", "passed": pattern_coverage >= 95, "value": pattern_coverage, "target": 95},
        {"key": "missing_values", "label": "Missing value pressure", "passed": missing_value_pressure <= 20, "value": missing_value_pressure, "target": 20},
        {"key": "feature_drift", "label": "High drift features", "passed": len(high_drift_features) == 0, "value": len(high_drift_features), "target": 0},
        {"key": "provider_stability", "label": "Provider stability", "passed": crawl_success_pct >= 99, "value": crawl_success_pct, "target": 99},
        {"key": "version_consistency", "label": "Version consistency", "passed": len(feature_versions) <= 1 and len(dataset_versions) <= 1, "value": len(feature_versions) + len(dataset_versions), "target": 2},
    ]
    ready = all(check["passed"] for check in readiness_checks)

    similar_summary = {
        "reference_snapshot_id": None,
        "similar_count": 0,
        "success_30m_pct": 0.0,
        "average_30m_move_pct": 0.0,
        "method": "nearest-neighbor proxy on PCR, OI imbalance, and ATR",
    }
    latest = next((row for row in reversed(rows) if row.pcr is not None), None)
    if latest:
        candidates = []
        for row in rows:
            if row.id == latest.id or row.return_30m_pct is None:
                continue
            score = 0.0
            for feature_name in ("pcr", "oi_imbalance", "atr"):
                latest_value = getattr(latest, feature_name)
                row_value = getattr(row, feature_name)
                if latest_value is None or row_value is None:
                    score += 10.0
                    continue
                score += abs(float(latest_value) - float(row_value)) / max(abs(float(latest_value)), 1.0)
            candidates.append((score, row))
        nearest = [row for _, row in sorted(candidates, key=lambda item: item[0])[:50]]
        if nearest:
            positive = sum(1 for row in nearest if abs(row.return_30m_pct or 0.0) >= 0.8)
            similar_summary = {
                "reference_snapshot_id": latest.id,
                "similar_count": len(nearest),
                "success_30m_pct": round((positive / len(nearest)) * 100.0, 2),
                "average_30m_move_pct": round(sum(row.return_30m_pct or 0.0 for row in nearest) / len(nearest), 4),
                "method": "nearest-neighbor proxy on PCR, OI imbalance, and ATR",
            }

    registry_counts = {
        "training_registry": db.query(TrainingRegistry).count(),
        "feature_store_definitions": db.query(FeatureStoreDefinition).count(),
        "strike_candidates": db.query(ExecutionStrikeCandidate).count(),
        "premium_evolution": db.query(PremiumEvolution).count(),
        "entry_timing": db.query(EntryTimingEvaluation).count(),
        "exit_timing": db.query(ExitTimingEvaluation).count(),
        "risk_evaluations": db.query(RiskEvaluation).count(),
    }

    return {
        "label_monitor": label_monitor,
        "dataset_imbalance": imbalance,
        "feature_distribution": feature_distribution,
        "feature_drift": feature_drift,
        "feature_importance": target_pairs[:10],
        "correlation_explorer": {
            "strong_correlations": strong_correlations,
            "redundant_features": redundant_features,
            "top_pairs": correlation_pairs[:15],
        },
        "training_readiness": {
            "ready": ready,
            "status": "READY" if ready else "NOT_READY",
            "checks": readiness_checks,
            "blocking_reasons": [check["label"] for check in readiness_checks if not check["passed"]],
        },
        "similar_historical_day_search": similar_summary,
        "phase_foundations": registry_counts,
        "coverage": {
            "pattern_coverage_pct": pattern_coverage,
            "metadata_coverage_pct": metadata_coverage,
            "crawl_success_pct": crawl_success_pct,
            "missing_value_pressure_pct": missing_value_pressure,
        },
    }


@router.get("/ml-dataset-export")
def export_ml_dataset(
    start_date: str = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(None, description="End date (YYYY-MM-DD)"),
    timeframe: str = Query(None, description="Filter by timeframe (1m, 5m, 15m)"),
    symbol: str = Query(None, description="Filter by symbol"),
    db: Session = Depends(get_db)
):
    """
    Exports completed/partial features and labels from the database as a CSV stream.
    """
    query = db.query(MLFeatureSnapshot)
    
    if start_date:
        query = query.filter(MLFeatureSnapshot.market_date >= start_date)
    if end_date:
        query = query.filter(MLFeatureSnapshot.market_date <= end_date)
    if timeframe:
        query = query.filter(MLFeatureSnapshot.timeframe == timeframe)
    if symbol:
        query = query.filter(MLFeatureSnapshot.symbol == symbol)
        
    records = query.order_by(MLFeatureSnapshot.timestamp.asc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers listing all columns in MLFeatureSnapshot
    headers_list = [
        "id", "timestamp", "market_date", "timeframe", "symbol", "expiry_date", "expiry_type",
        "days_to_expiry", "minutes_from_open", "minutes_to_close", "session_phase", "day_type",
        "data_quality_score", "snapshot_age_seconds", "feature_flags", "feature_schema_version",
        "pcr", "pcr_velocity", "oi_imbalance", "average_iv", "iv_change",
        "total_call_oi", "total_put_oi", "call_change_oi", "put_change_oi",
        "distance_to_s1", "distance_to_s2", "distance_to_r1", "distance_to_r2",
        "distance_to_s1_pct", "distance_to_r1_pct", "sr_compression",
        "support_strength", "resistance_strength", "market_state", "market_state_id",
        "strength", "strength_score", "ema20", "ema50", "atr", "regime_trend", "order_flow",
        "return_15m_pct", "return_30m_pct", "return_60m_pct",
        "return_15m_points", "return_30m_points", "return_60m_points",
        "direction_15m", "direction_30m", "direction_60m", "label_quality", "available_horizons",
        "status"
    ]
    writer.writerow(headers_list)
    
    for r in records:
        writer.writerow([
            r.id,
            r.timestamp.isoformat() if r.timestamp else "",
            r.market_date or "",
            r.timeframe or "",
            r.symbol or "",
            r.expiry_date or "",
            r.expiry_type or "",
            r.days_to_expiry,
            r.minutes_from_open,
            r.minutes_to_close,
            r.session_phase or "",
            r.day_type or "",
            r.data_quality_score,
            r.snapshot_age_seconds,
            r.feature_flags or "",
            r.feature_schema_version or "v1",
            r.pcr,
            r.pcr_velocity,
            r.oi_imbalance,
            r.average_iv,
            r.iv_change,
            r.total_call_oi,
            r.total_put_oi,
            r.call_change_oi,
            r.put_change_oi,
            r.distance_to_s1,
            r.distance_to_s2,
            r.distance_to_r1,
            r.distance_to_r2,
            r.distance_to_s1_pct,
            r.distance_to_r1_pct,
            r.sr_compression,
            r.support_strength or "",
            r.resistance_strength or "",
            r.market_state or "",
            r.market_state_id,
            r.strength or "",
            r.strength_score,
            r.ema20,
            r.ema50,
            r.atr,
            r.regime_trend or "",
            r.order_flow,
            r.return_15m_pct,
            r.return_30m_pct,
            r.return_60m_pct,
            r.return_15m_points,
            r.return_30m_points,
            r.return_60m_points,
            r.direction_15m or "",
            r.direction_30m or "",
            r.direction_60m or "",
            r.label_quality or "",
            r.available_horizons or "",
            r.status or ""
        ])
        
    output.seek(0)
    
    filename = f"ml_features_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type='text/csv',
        headers=headers
    )
