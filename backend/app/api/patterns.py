import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import DatasetMetadata, FeatureLineage, PatternLibrary, PatternObservation
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
