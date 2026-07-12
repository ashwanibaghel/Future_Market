from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import DatasetMetadata, FeatureLineage, MLFeatureSnapshot, PatternObservation


def get_lineage_summary(db: Session, symbol: str | None = None) -> dict:
    feature_query = db.query(MLFeatureSnapshot)
    metadata_query = db.query(DatasetMetadata)
    pattern_query = db.query(PatternObservation)
    if symbol:
        upper_symbol = symbol.upper()
        feature_query = feature_query.filter(MLFeatureSnapshot.symbol == upper_symbol)
        metadata_query = metadata_query.filter(DatasetMetadata.symbol == upper_symbol)
        pattern_query = pattern_query.filter(PatternObservation.symbol == upper_symbol)

    feature_rows = feature_query.count()
    metadata_rows = metadata_query.count()
    pattern_rows = pattern_query.count()
    lineage_rows = db.query(FeatureLineage).count()

    dataset_versions = [
        row[0]
        for row in feature_query.with_entities(MLFeatureSnapshot.dataset_version)
        .filter(MLFeatureSnapshot.dataset_version.isnot(None))
        .distinct()
        .all()
    ]
    engine_versions = [
        row[0]
        for row in feature_query.with_entities(MLFeatureSnapshot.engine_version)
        .filter(MLFeatureSnapshot.engine_version.isnot(None))
        .distinct()
        .all()
    ]
    feature_versions = [
        row[0]
        for row in feature_query.with_entities(MLFeatureSnapshot.feature_schema_version)
        .filter(MLFeatureSnapshot.feature_schema_version.isnot(None))
        .distinct()
        .all()
    ]

    by_dataset = [
        {"dataset_version": version or "unknown", "rows": count}
        for version, count in feature_query.with_entities(
            MLFeatureSnapshot.dataset_version,
            func.count(MLFeatureSnapshot.id),
        ).group_by(MLFeatureSnapshot.dataset_version).all()
    ]

    coverage = {
        "metadata_coverage_pct": round((metadata_rows / feature_rows * 100.0), 2) if feature_rows else 0.0,
        "pattern_coverage_pct": round((pattern_rows / feature_rows * 100.0), 2) if feature_rows else 0.0,
        "feature_lineage_per_pattern_pct": round((lineage_rows / pattern_rows * 100.0), 2) if pattern_rows else 0.0,
    }

    return {
        "counts": {
            "feature_rows": feature_rows,
            "dataset_metadata_rows": metadata_rows,
            "pattern_observation_rows": pattern_rows,
            "feature_lineage_rows": lineage_rows,
        },
        "coverage": coverage,
        "versions": {
            "dataset_versions": dataset_versions,
            "engine_versions": engine_versions,
            "feature_versions": feature_versions,
            "version_consistency": len(dataset_versions) <= 1 and len(engine_versions) <= 1 and len(feature_versions) <= 1,
        },
        "dataset_history": by_dataset,
    }

