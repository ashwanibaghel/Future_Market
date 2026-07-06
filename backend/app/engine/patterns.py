import json
import logging
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    AnalyticsSnapshot,
    AnalyticsSnapshot5m,
    AnalyticsSnapshot15m,
    DatasetMetadata,
    FeatureLineage,
    MLFeatureSnapshot,
    OptionChainSnapshot,
    OptionChainSnapshot5m,
    OptionChainSnapshot15m,
    OptionChainStrike,
    OptionChainStrike5m,
    OptionChainStrike15m,
    PatternLibrary,
    PatternObservation,
)

logger = logging.getLogger(__name__)

SOURCE_TABLES = {
    "1m": ("option_chain_snapshots", OptionChainSnapshot, OptionChainStrike, AnalyticsSnapshot),
    "5m": ("aggregated_5m_snapshots", OptionChainSnapshot5m, OptionChainStrike5m, AnalyticsSnapshot5m),
    "15m": ("aggregated_15m_snapshots", OptionChainSnapshot15m, OptionChainStrike15m, AnalyticsSnapshot15m),
}


def get_source_contract(timeframe: str):
    try:
        return SOURCE_TABLES[timeframe]
    except KeyError as exc:
        raise ValueError(f"Unsupported pattern timeframe: {timeframe}") from exc


def classify_pattern_signature(
    spot_price: float,
    ema20: Optional[float],
    atr: Optional[float],
    total_oi: int,
    previous_total_oi: Optional[int],
    pcr: Optional[float],
    previous_pcr: Optional[float],
) -> Dict[str, Any]:
    """Classify market structure without producing a trading decision."""
    safe_atr = max(float(atr or 0.0), 1.0)
    safe_ema20 = float(ema20 if ema20 is not None else spot_price)
    trend_deadband = safe_atr * 0.05

    if spot_price > safe_ema20 + trend_deadband:
        trend_state = "TrendUp"
    elif spot_price < safe_ema20 - trend_deadband:
        trend_state = "TrendDown"
    else:
        trend_state = "TrendFlat"

    oi_change_pct = 0.0
    if previous_total_oi and previous_total_oi > 0:
        oi_change_pct = ((total_oi - previous_total_oi) / previous_total_oi) * 100.0

    if oi_change_pct > 0.01:
        oi_state = "OIUp"
    elif oi_change_pct < -0.01:
        oi_state = "OIDown"
    else:
        oi_state = "OIFlat"

    pcr_change = 0.0
    if pcr is not None and previous_pcr is not None:
        pcr_change = float(pcr - previous_pcr)

    if pcr_change > 0.001:
        pcr_state = "PCRUp"
    elif pcr_change < -0.001:
        pcr_state = "PCRDown"
    else:
        pcr_state = "PCRFlat"

    return {
        "pattern_id": f"{trend_state}_{oi_state}_{pcr_state}",
        "trend_state": trend_state,
        "oi_state": oi_state,
        "pcr_state": pcr_state,
        "oi_change_pct": oi_change_pct,
        "pcr_change": pcr_change,
        "trend_distance_atr": abs(spot_price - safe_ema20) / safe_atr,
    }


def calculate_pattern_confidence(
    signature: Dict[str, Any], data_quality_score: int
) -> float:
    """Score classification evidence, not trade direction or profitability."""
    trend_evidence = min(1.0, float(signature["trend_distance_atr"]))
    oi_evidence = min(1.0, abs(float(signature["oi_change_pct"])) / 2.0)
    pcr_evidence = min(1.0, abs(float(signature["pcr_change"])) / 0.1)
    evidence = (trend_evidence * 0.40) + (oi_evidence * 0.35) + (pcr_evidence * 0.25)
    quality_factor = 0.5 + (max(0, min(100, data_quality_score)) / 200.0)
    return round(evidence * quality_factor * 100.0, 2)


def _provider_api_source(provider: Optional[str]) -> str:
    normalized = (provider or "unknown").upper()
    if normalized == "NSE":
        return "NSE_NEXT_API"
    if normalized == "UPSTOX":
        return "UPSTOX_OPTION_CHAIN_API"
    return normalized


def _missing_fields(feature: MLFeatureSnapshot, strikes) -> list:
    missing = []
    try:
        flags = json.loads(feature.feature_flags or "{}")
    except (TypeError, json.JSONDecodeError):
        flags = {}
    if not strikes:
        missing.append("option_chain")
    if not flags.get("has_iv", False):
        missing.append("iv")
    if not flags.get("has_pcr", False):
        missing.append("pcr")
    if not flags.get("has_sr", False):
        missing.append("support_resistance")
    if strikes and not any(
        (strike.call_delta or strike.put_delta or strike.call_gamma or strike.put_gamma)
        for strike in strikes
    ):
        missing.append("greeks")
    if strikes and not any((strike.call_oi or strike.put_oi) for strike in strikes):
        missing.append("oi")
    return missing


def _lineage_payloads(
    observation: PatternObservation,
    previous: Optional[PatternObservation],
    signature: Dict[str, Any],
) -> Tuple[Dict[str, Any], ...]:
    previous_oi = previous.total_oi if previous else None
    previous_pcr = previous.pcr if previous else None
    return (
        {
            "feature_name": "pcr",
            "source_fields": ["option_chain_strikes.put_oi", "option_chain_strikes.call_oi"],
            "source_values": {"current_pcr": observation.pcr},
            "transformation": "sum(put_oi) / max(sum(call_oi), 1)",
            "output_value": observation.pcr,
        },
        {
            "feature_name": "oi_change_pct",
            "source_fields": ["current.total_oi", "previous.total_oi"],
            "source_values": {"current": observation.total_oi, "previous": previous_oi},
            "transformation": "((current - previous) / previous) * 100",
            "output_value": observation.oi_change_pct,
        },
        {
            "feature_name": "pcr_change",
            "source_fields": ["current.pcr", "previous.pcr"],
            "source_values": {"current": observation.pcr, "previous": previous_pcr},
            "transformation": "current_pcr - previous_pcr",
            "output_value": observation.pcr_change,
        },
        {
            "feature_name": "pattern_id",
            "source_fields": ["spot_price", "ema20", "atr", "oi_change_pct", "pcr_change"],
            "source_values": {
                "spot_price": observation.spot_price,
                "ema20": observation.ema20,
                "atr": observation.atr,
                "trend_state": signature["trend_state"],
                "oi_state": signature["oi_state"],
                "pcr_state": signature["pcr_state"],
            },
            "transformation": "TrendState_OIState_PCRState deterministic signature",
            "output_value": observation.pattern_id,
        },
        {
            "feature_name": "pattern_confidence",
            "source_fields": ["trend_distance_atr", "oi_change_pct", "pcr_change", "data_quality_score"],
            "source_values": {
                "trend_distance_atr": signature["trend_distance_atr"],
                "oi_change_pct": observation.oi_change_pct,
                "pcr_change": observation.pcr_change,
                "data_quality_score": observation.data_quality_score,
            },
            "transformation": "weighted evidence (40% trend, 35% OI, 25% PCR) * quality factor",
            "output_value": observation.pattern_confidence,
        },
    )


def capture_pattern_observation(
    db: Session, snapshot_id: int, timeframe: str = "1m"
) -> Optional[PatternObservation]:
    """Persist one idempotent, append-only pattern observation and its provenance."""
    source_table, snapshot_cls, strike_cls, _ = get_source_contract(timeframe)
    engine_version = settings.RESEARCH_ENGINE_VERSION

    existing = db.query(PatternObservation).filter(
        PatternObservation.source_table == source_table,
        PatternObservation.source_snapshot_id == snapshot_id,
        PatternObservation.timeframe == timeframe,
        PatternObservation.engine_version == engine_version,
    ).first()
    if existing:
        return existing

    snapshot = db.query(snapshot_cls).filter(snapshot_cls.id == snapshot_id).first()
    if not snapshot or snapshot.collection_status != "SUCCESS":
        return None

    feature = db.query(MLFeatureSnapshot).filter(
        MLFeatureSnapshot.source_table == source_table,
        MLFeatureSnapshot.source_snapshot_id == snapshot_id,
        MLFeatureSnapshot.timeframe == timeframe,
    ).order_by(MLFeatureSnapshot.id.desc()).first()
    if not feature:
        logger.warning("Pattern capture skipped: feature snapshot missing for %s/%s", source_table, snapshot_id)
        return None
    feature_version = feature.feature_schema_version or "v1"
    dataset_version = feature.dataset_version or settings.RESEARCH_DATASET_VERSION

    strikes = db.query(strike_cls).filter(strike_cls.snapshot_id == snapshot_id).all()
    previous = db.query(PatternObservation).filter(
        PatternObservation.symbol == snapshot.symbol,
        PatternObservation.expiry_date == snapshot.expiry_date,
        PatternObservation.timeframe == timeframe,
        PatternObservation.engine_version == engine_version,
        PatternObservation.timestamp < snapshot.timestamp,
    ).order_by(PatternObservation.timestamp.desc(), PatternObservation.id.desc()).first()

    total_oi = sum((strike.call_oi or 0) + (strike.put_oi or 0) for strike in strikes)
    signature = classify_pattern_signature(
        spot_price=float(snapshot.spot_price or 0.0),
        ema20=feature.ema20,
        atr=feature.atr,
        total_oi=total_oi,
        previous_total_oi=previous.total_oi if previous else None,
        pcr=feature.pcr,
        previous_pcr=previous.pcr if previous else None,
    )
    confidence = calculate_pattern_confidence(signature, feature.data_quality_score or 0)
    same_sequence = previous is not None and previous.pattern_id == signature["pattern_id"]
    pattern_age = (previous.pattern_age_snapshots + 1) if same_sequence else 1
    pattern_started_at = previous.pattern_started_at if same_sequence else snapshot.timestamp

    library = db.query(PatternLibrary).filter(
        PatternLibrary.symbol == snapshot.symbol,
        PatternLibrary.timeframe == timeframe,
        PatternLibrary.pattern_id == signature["pattern_id"],
        PatternLibrary.pattern_version == engine_version,
    ).first()
    if not library:
        library = PatternLibrary(
            symbol=snapshot.symbol,
            timeframe=timeframe,
            pattern_id=signature["pattern_id"],
            pattern_version=engine_version,
            signature_json=json.dumps({key: signature[key] for key in ("trend_state", "oi_state", "pcr_state")}),
            observed_count=0,
            average_confidence=0.0,
            maximum_confidence=0.0,
            average_age_snapshots=0.0,
            maximum_age_snapshots=0,
            first_seen_at=snapshot.timestamp,
            last_seen_at=snapshot.timestamp,
            engine_version=engine_version,
            feature_version=feature_version,
            dataset_version=dataset_version,
        )
        db.add(library)
        db.flush()
    elif library.feature_version != feature_version:
        library.feature_version = "mixed"

    old_count = library.observed_count or 0
    new_count = old_count + 1
    library.average_confidence = round(
        (((library.average_confidence or 0.0) * old_count) + confidence) / new_count, 2
    )
    library.average_age_snapshots = round(
        (((library.average_age_snapshots or 0.0) * old_count) + pattern_age) / new_count, 2
    )
    library.observed_count = new_count
    library.maximum_confidence = max(library.maximum_confidence or 0.0, confidence)
    library.maximum_age_snapshots = max(library.maximum_age_snapshots or 0, pattern_age)
    library.last_seen_at = snapshot.timestamp

    metadata = db.query(DatasetMetadata).filter(
        DatasetMetadata.source_table == source_table,
        DatasetMetadata.source_snapshot_id == snapshot_id,
        DatasetMetadata.timeframe == timeframe,
        DatasetMetadata.dataset_version == dataset_version,
    ).first()
    if not metadata:
        missing_fields = _missing_fields(feature, strikes)
        metadata = DatasetMetadata(
            market_timestamp=snapshot.timestamp + timedelta(hours=5, minutes=30),
            symbol=snapshot.symbol,
            expiry_date=snapshot.expiry_date,
            timeframe=timeframe,
            source_table=source_table,
            source_snapshot_id=snapshot_id,
            provider=snapshot.provider or settings.ACTIVE_PROVIDER,
            provider_version="unversioned",
            api_source=_provider_api_source(snapshot.provider),
            engine_version=engine_version,
            feature_version=feature_version,
            dataset_version=dataset_version,
            symbol_version=settings.SYMBOL_SCHEMA_VERSION,
            timezone=settings.MARKET_TIMEZONE,
            crawl_latency_ms=snapshot.collection_duration_ms or 0,
            crawl_success=True,
            missing_fields=json.dumps(missing_fields),
            quality_score=feature.data_quality_score or 0,
        )
        db.add(metadata)
        db.flush()

    observation = PatternObservation(
        timestamp=snapshot.timestamp,
        symbol=snapshot.symbol,
        expiry_date=snapshot.expiry_date,
        timeframe=timeframe,
        source_table=source_table,
        source_snapshot_id=snapshot_id,
        feature_snapshot_id=feature.id,
        dataset_metadata_id=metadata.id,
        pattern_library_id=library.id,
        pattern_id=signature["pattern_id"],
        pattern_version=engine_version,
        pattern_confidence=confidence,
        pattern_age_snapshots=pattern_age,
        pattern_started_at=pattern_started_at,
        trend_state=signature["trend_state"],
        oi_state=signature["oi_state"],
        pcr_state=signature["pcr_state"],
        market_state=feature.market_state,
        regime_trend=feature.regime_trend,
        spot_price=snapshot.spot_price,
        ema20=feature.ema20,
        atr=feature.atr,
        total_oi=total_oi,
        oi_change_pct=signature["oi_change_pct"],
        pcr=feature.pcr,
        pcr_change=signature["pcr_change"],
        data_quality_score=feature.data_quality_score or 0,
        engine_version=engine_version,
        feature_version=feature_version,
        dataset_version=dataset_version,
    )
    db.add(observation)
    db.flush()

    for payload in _lineage_payloads(observation, previous, signature):
        db.add(FeatureLineage(
            pattern_observation_id=observation.id,
            feature_name=payload["feature_name"],
            feature_version=feature_version,
            source_fields=json.dumps(payload["source_fields"]),
            source_values=json.dumps(payload["source_values"]),
            transformation=payload["transformation"],
            output_value=json.dumps(payload["output_value"]),
        ))

    db.commit()
    db.refresh(observation)
    logger.info(
        "Captured %s pattern %s for %s snapshot %s",
        timeframe,
        observation.pattern_id,
        snapshot.symbol,
        snapshot_id,
    )
    return observation


def backfill_pattern_observations(db: Session, limit: Optional[int] = None) -> int:
    """Capture missing historical pattern observations in chronological order."""
    query = db.query(MLFeatureSnapshot).outerjoin(
        PatternObservation,
        and_(
            PatternObservation.source_table == MLFeatureSnapshot.source_table,
            PatternObservation.source_snapshot_id == MLFeatureSnapshot.source_snapshot_id,
            PatternObservation.timeframe == MLFeatureSnapshot.timeframe,
            PatternObservation.engine_version == settings.RESEARCH_ENGINE_VERSION,
        ),
    ).filter(
        PatternObservation.id.is_(None),
        MLFeatureSnapshot.source_snapshot_id.isnot(None),
        MLFeatureSnapshot.source_table.in_([contract[0] for contract in SOURCE_TABLES.values()]),
    ).order_by(MLFeatureSnapshot.timestamp.asc(), MLFeatureSnapshot.id.asc())
    if limit is not None:
        query = query.limit(limit)

    captured = 0
    for feature in query.all():
        try:
            observation = capture_pattern_observation(
                db,
                snapshot_id=feature.source_snapshot_id,
                timeframe=feature.timeframe,
            )
            if observation:
                captured += 1
        except Exception:
            db.rollback()
            logger.exception(
                "Pattern backfill failed for feature snapshot %s",
                feature.id,
            )
    return captured
