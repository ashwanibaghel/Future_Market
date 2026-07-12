import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import DatasetMetadata, FeatureLineage, MLFeatureSnapshot, PatternLibrary, PatternObservation
from app.db.session import get_db

router = APIRouter()


@router.get("/patterns/library")
def get_pattern_library(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(PatternLibrary)
    if symbol:
        query = query.filter(PatternLibrary.symbol == symbol.upper())
    if timeframe:
        query = query.filter(PatternLibrary.timeframe == timeframe)
    rows = query.order_by(PatternLibrary.observed_count.desc(), PatternLibrary.pattern_id.asc()).limit(limit).all()
    return {
        "count": len(rows),
        "data": [
            {
                "id": row.id,
                "symbol": row.symbol,
                "timeframe": row.timeframe,
                "pattern_id": row.pattern_id,
                "pattern_version": row.pattern_version,
                "signature": json.loads(row.signature_json or "{}"),
                "observed_count": row.observed_count,
                "average_confidence": row.average_confidence,
                "maximum_confidence": row.maximum_confidence,
                "average_age_snapshots": row.average_age_snapshots,
                "maximum_age_snapshots": row.maximum_age_snapshots,
                "first_seen_at": row.first_seen_at,
                "last_seen_at": row.last_seen_at,
                "engine_version": row.engine_version,
                "feature_version": row.feature_version,
                "dataset_version": row.dataset_version,
            }
            for row in rows
        ],
    }


def _pattern_expected_direction(pattern_id: str) -> str:
    if pattern_id.startswith("TrendUp"):
        return "UP"
    if pattern_id.startswith("TrendDown"):
        return "DOWN"
    return "SIDEWAYS"


def _wilson_interval(wins: int, total: int) -> dict:
    if total <= 0:
        return {"low": 0.0, "high": 0.0}
    z = 1.96
    phat = wins / total
    denominator = 1 + z * z / total
    center = (phat + z * z / (2 * total)) / denominator
    margin = (z * ((phat * (1 - phat) + z * z / (4 * total)) / total) ** 0.5) / denominator
    return {
        "low": round(max(0.0, (center - margin) * 100.0), 2),
        "high": round(min(100.0, (center + margin) * 100.0), 2),
    }


@router.get("/patterns/leaderboard")
def get_pattern_leaderboard(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(PatternLibrary)
    if symbol:
        query = query.filter(PatternLibrary.symbol == symbol.upper())
    if timeframe:
        query = query.filter(PatternLibrary.timeframe == timeframe)
    libraries = query.order_by(PatternLibrary.observed_count.desc()).limit(limit).all()

    data = []
    for library in libraries:
        observations = db.query(PatternObservation, MLFeatureSnapshot).join(
            MLFeatureSnapshot,
            PatternObservation.feature_snapshot_id == MLFeatureSnapshot.id,
        ).filter(
            PatternObservation.pattern_id == library.pattern_id,
            PatternObservation.pattern_version == library.pattern_version,
            PatternObservation.symbol == library.symbol,
            PatternObservation.timeframe == library.timeframe,
        ).all()
        expected = _pattern_expected_direction(library.pattern_id)
        wins = losses = flats = 0
        moves = []
        holding_times = []
        previous_timestamp = None
        for observation, feature in observations:
            direction = feature.direction_30m
            if direction == expected:
                wins += 1
            elif direction == "SIDEWAYS" or direction is None:
                flats += 1
            else:
                losses += 1
            if feature.return_30m_points is not None:
                moves.append(float(feature.return_30m_points))
            if previous_timestamp:
                holding_times.append((observation.timestamp - previous_timestamp).total_seconds() / 60.0)
            previous_timestamp = observation.timestamp
        completed = wins + losses + flats
        win_rate = round((wins / completed * 100.0), 2) if completed else 0.0
        reliability = round(
            (win_rate * 0.70) + (min(100.0, library.average_confidence or 0.0) * 0.30),
            2,
        ) if completed else 0.0
        sorted_moves = sorted(moves)
        median_move = sorted_moves[len(sorted_moves) // 2] if sorted_moves else 0.0
        data.append({
            "pattern_id": library.pattern_id,
            "pattern_version": library.pattern_version,
            "timeframe": library.timeframe,
            "occurrences": library.observed_count,
            "wins": wins,
            "losses": losses,
            "flats": flats,
            "win_rate": win_rate,
            "reliability": reliability,
            "average_move": round(sum(moves) / len(moves), 4) if moves else 0.0,
            "median_move": round(median_move, 4),
            "maximum_move": round(max(moves), 4) if moves else 0.0,
            "maximum_drawdown": round(min(moves), 4) if moves else 0.0,
            "average_holding_time": round(sum(holding_times) / len(holding_times), 2) if holding_times else 0.0,
            "best_strike": None,
            "best_entry_delay": None,
            "best_exit_time": None,
            "confidence_interval": _wilson_interval(wins, completed),
        })

    data.sort(key=lambda item: (item["reliability"], item["occurrences"]), reverse=True)
    return {"count": len(data), "data": data}


@router.get("/patterns/transitions")
def get_pattern_transitions(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(PatternObservation)
    if symbol:
        query = query.filter(PatternObservation.symbol == symbol.upper())
    if timeframe:
        query = query.filter(PatternObservation.timeframe == timeframe)
    observations = query.order_by(
        PatternObservation.symbol,
        PatternObservation.timeframe,
        PatternObservation.timestamp,
        PatternObservation.id,
    ).all()
    transitions = {}
    previous_by_stream = {}
    for observation in observations:
        stream = (observation.symbol, observation.timeframe)
        previous = previous_by_stream.get(stream)
        if previous and previous.pattern_id != observation.pattern_id:
            key = (previous.pattern_id, observation.pattern_id, observation.timeframe)
            minutes = (observation.timestamp - previous.timestamp).total_seconds() / 60.0
            payload = transitions.setdefault(key, {"count": 0, "minutes": []})
            payload["count"] += 1
            payload["minutes"].append(minutes)
        previous_by_stream[stream] = observation
    rows = []
    for (from_pattern, to_pattern, row_timeframe), payload in transitions.items():
        rows.append({
            "from_pattern_id": from_pattern,
            "to_pattern_id": to_pattern,
            "timeframe": row_timeframe,
            "transition_count": payload["count"],
            "average_minutes": round(sum(payload["minutes"]) / len(payload["minutes"]), 2),
        })
    rows.sort(key=lambda item: item["transition_count"], reverse=True)
    return {"count": len(rows[:limit]), "data": rows[:limit]}


@router.get("/patterns/lifecycles")
def get_pattern_lifecycles(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(PatternObservation)
    if symbol:
        query = query.filter(PatternObservation.symbol == symbol.upper())
    if timeframe:
        query = query.filter(PatternObservation.timeframe == timeframe)
    observations = query.order_by(
        PatternObservation.symbol,
        PatternObservation.timeframe,
        PatternObservation.timestamp,
        PatternObservation.id,
    ).all()
    lifecycles = []
    current_by_stream = {}
    for observation in observations:
        stream = (observation.symbol, observation.timeframe)
        current = current_by_stream.get(stream)
        if not current or current["pattern_id"] != observation.pattern_id:
            if current:
                lifecycles.append(current)
            current = {
                "symbol": observation.symbol,
                "timeframe": observation.timeframe,
                "pattern_id": observation.pattern_id,
                "pattern_version": observation.pattern_version,
                "pattern_start": observation.timestamp,
                "pattern_end": observation.timestamp,
                "observations": 0,
                "peak_confidence": 0.0,
                "scores": [],
                "moves": [],
                "source_observation_ids": [],
            }
            current_by_stream[stream] = current
        current["pattern_end"] = observation.timestamp
        current["observations"] += 1
        current["peak_confidence"] = max(current["peak_confidence"], observation.pattern_confidence or 0.0)
        current["scores"].append(observation.pattern_confidence or 0.0)
        current["moves"].append(observation.oi_change_pct or 0.0)
        current["source_observation_ids"].append(observation.id)
    lifecycles.extend(current_by_stream.values())
    rows = []
    for lifecycle in lifecycles[-limit:]:
        duration = (lifecycle["pattern_end"] - lifecycle["pattern_start"]).total_seconds() / 60.0
        moves = lifecycle["moves"]
        rows.append({
            "symbol": lifecycle["symbol"],
            "timeframe": lifecycle["timeframe"],
            "pattern_id": lifecycle["pattern_id"],
            "pattern_version": lifecycle["pattern_version"],
            "pattern_start": lifecycle["pattern_start"],
            "pattern_end": lifecycle["pattern_end"],
            "duration_minutes": round(duration, 2),
            "observations": lifecycle["observations"],
            "peak_confidence": round(lifecycle["peak_confidence"], 2),
            "peak_score": round(max(lifecycle["scores"]), 2) if lifecycle["scores"] else 0.0,
            "average_score": round(sum(lifecycle["scores"]) / len(lifecycle["scores"]), 2) if lifecycle["scores"] else 0.0,
            "average_move": round(sum(moves) / len(moves), 4) if moves else 0.0,
            "largest_move": round(max(moves, key=abs), 4) if moves else 0.0,
            "failure_reason": None,
            "completion_status": "CLOSED",
            "source_observation_ids": lifecycle["source_observation_ids"],
        })
    rows.sort(key=lambda item: item["pattern_end"], reverse=True)
    return {"count": len(rows), "data": rows}


@router.get("/patterns/rule-leaderboard")
def get_rule_leaderboard(
    symbol: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(
        FeatureLineage.feature_name,
        func.count(FeatureLineage.id).label("usage_count"),
    ).join(PatternObservation, FeatureLineage.pattern_observation_id == PatternObservation.id)
    if symbol:
        query = query.filter(PatternObservation.symbol == symbol.upper())
    rows = query.group_by(FeatureLineage.feature_name).order_by(func.count(FeatureLineage.id).desc()).all()
    total = sum(row.usage_count for row in rows) or 1
    return {
        "count": len(rows),
        "data": [
            {
                "rule": row.feature_name,
                "usage_count": row.usage_count,
                "coverage_pct": round(row.usage_count / total * 100.0, 2),
                "status": "CORE" if row.usage_count / total >= 0.15 else "SUPPORTING",
            }
            for row in rows
        ],
    }


@router.get("/patterns/observations")
def get_pattern_observations(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    pattern_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(PatternObservation)
    if symbol:
        query = query.filter(PatternObservation.symbol == symbol.upper())
    if timeframe:
        query = query.filter(PatternObservation.timeframe == timeframe)
    if pattern_id:
        query = query.filter(PatternObservation.pattern_id == pattern_id)
    rows = query.order_by(PatternObservation.timestamp.desc(), PatternObservation.id.desc()).limit(limit).all()
    return {
        "count": len(rows),
        "data": [
            {
                "id": row.id,
                "timestamp": row.timestamp,
                "symbol": row.symbol,
                "expiry_date": row.expiry_date,
                "timeframe": row.timeframe,
                "source_snapshot_id": row.source_snapshot_id,
                "pattern_id": row.pattern_id,
                "pattern_version": row.pattern_version,
                "pattern_confidence": row.pattern_confidence,
                "pattern_age_snapshots": row.pattern_age_snapshots,
                "pattern_started_at": row.pattern_started_at,
                "trend_state": row.trend_state,
                "oi_state": row.oi_state,
                "pcr_state": row.pcr_state,
                "market_state": row.market_state,
                "regime_trend": row.regime_trend,
                "spot_price": row.spot_price,
                "oi_change_pct": row.oi_change_pct,
                "pcr": row.pcr,
                "pcr_change": row.pcr_change,
                "data_quality_score": row.data_quality_score,
                "dataset_metadata_id": row.dataset_metadata_id,
            }
            for row in rows
        ],
    }


@router.get("/patterns/observations/{observation_id}/lineage")
def get_pattern_lineage(observation_id: int, db: Session = Depends(get_db)):
    observation = db.query(PatternObservation).filter(PatternObservation.id == observation_id).first()
    if not observation:
        raise HTTPException(status_code=404, detail="Pattern observation not found")
    rows = db.query(FeatureLineage).filter(
        FeatureLineage.pattern_observation_id == observation_id
    ).order_by(FeatureLineage.feature_name.asc()).all()
    return {
        "observation_id": observation_id,
        "pattern_id": observation.pattern_id,
        "count": len(rows),
        "data": [
            {
                "feature_name": row.feature_name,
                "feature_version": row.feature_version,
                "source_fields": json.loads(row.source_fields or "[]"),
                "source_values": json.loads(row.source_values or "{}"),
                "transformation": row.transformation,
                "output_value": json.loads(row.output_value or "null"),
            }
            for row in rows
        ],
    }


@router.get("/dataset-metadata")
def get_dataset_metadata(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(DatasetMetadata)
    if symbol:
        query = query.filter(DatasetMetadata.symbol == symbol.upper())
    if timeframe:
        query = query.filter(DatasetMetadata.timeframe == timeframe)
    rows = query.order_by(DatasetMetadata.market_timestamp.desc(), DatasetMetadata.id.desc()).limit(limit).all()
    return {
        "count": len(rows),
        "data": [
            {
                "id": row.id,
                "market_timestamp": row.market_timestamp,
                "symbol": row.symbol,
                "expiry_date": row.expiry_date,
                "timeframe": row.timeframe,
                "source_table": row.source_table,
                "source_snapshot_id": row.source_snapshot_id,
                "provider": row.provider,
                "provider_version": row.provider_version,
                "api_source": row.api_source,
                "engine_version": row.engine_version,
                "feature_version": row.feature_version,
                "dataset_version": row.dataset_version,
                "symbol_version": row.symbol_version,
                "timezone": row.timezone,
                "crawl_latency_ms": row.crawl_latency_ms,
                "crawl_success": row.crawl_success,
                "missing_fields": json.loads(row.missing_fields or "[]"),
                "quality_score": row.quality_score,
            }
            for row in rows
        ],
    }
