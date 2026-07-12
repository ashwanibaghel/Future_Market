from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import PatternLibrary, PatternObservation


def get_pattern_intelligence(db: Session, symbol: str | None = None) -> dict:
    library_query = db.query(PatternLibrary)
    observation_query = db.query(PatternObservation)
    if symbol:
        upper_symbol = symbol.upper()
        library_query = library_query.filter(PatternLibrary.symbol == upper_symbol)
        observation_query = observation_query.filter(PatternObservation.symbol == upper_symbol)

    libraries = library_query.order_by(PatternLibrary.observed_count.desc()).all()
    observations = observation_query.count()
    unique_patterns = len(libraries)
    total_observed = sum(row.observed_count or 0 for row in libraries)
    average_confidence = round(
        sum((row.average_confidence or 0.0) * (row.observed_count or 0) for row in libraries) / total_observed,
        2,
    ) if total_observed else 0.0
    lifecycle_rows = []
    for row in libraries[:12]:
        lifecycle_rows.append({
            "pattern_id": row.pattern_id,
            "timeframe": row.timeframe,
            "observed_count": row.observed_count,
            "average_confidence": row.average_confidence,
            "maximum_confidence": row.maximum_confidence,
            "average_age_snapshots": row.average_age_snapshots,
            "maximum_age_snapshots": row.maximum_age_snapshots,
            "first_seen_at": row.first_seen_at,
            "last_seen_at": row.last_seen_at,
            "reliability_status": "MATURE" if (row.observed_count or 0) >= 50 else ("EMERGING" if (row.observed_count or 0) >= 10 else "SPARSE"),
        })

    timeframe_rows = library_query.with_entities(
        PatternLibrary.timeframe,
        func.count(PatternLibrary.id),
        func.sum(PatternLibrary.observed_count),
    ).group_by(PatternLibrary.timeframe).all()

    return {
        "engine": "Pattern Intelligence",
        "status": "READY" if observations >= 100 else ("DEGRADED" if observations else "BLOCKED"),
        "unique_patterns": unique_patterns,
        "pattern_observations": observations,
        "average_pattern_confidence": average_confidence,
        "mature_patterns": sum(1 for row in libraries if (row.observed_count or 0) >= 50),
        "emerging_patterns": sum(1 for row in libraries if 10 <= (row.observed_count or 0) < 50),
        "sparse_patterns": sum(1 for row in libraries if (row.observed_count or 0) < 10),
        "timeframe_distribution": [
            {"timeframe": timeframe or "unknown", "patterns": count or 0, "observations": observations_count or 0}
            for timeframe, count, observations_count in timeframe_rows
        ],
        "top_lifecycles": lifecycle_rows,
        "independence_rule": "Patterns are tracked as market structure, not trading signals.",
    }

