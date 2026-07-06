import io
import csv
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.db.models import (
    DatasetMetadata,
    FeatureLineage,
    MLFeatureSnapshot,
    PatternLibrary,
    PatternObservation,
)

router = APIRouter()

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
