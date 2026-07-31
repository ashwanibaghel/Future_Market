from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.acquisition.framework.data_version import DEFAULT_DATASET_VERSION, DEFAULT_CANONICAL_SCHEMA_VERSION


@dataclass(frozen=True)
class DatasetManifest:
    """
    Requirement 1 Generic Dataset Manifest Specification.
    Uniquely identifies every ingested dataset for deterministic replay, reproducible experiments,
    and future AI model training.
    """
    dataset_id: str
    dataset_version: str
    schema_version: str
    provider: str
    symbols: List[str]
    asset_type: str  # OPTIONS, EQUITIES, INDICES, VIX, BREADTH, MACRO
    time_range: Dict[str, str]  # {"start_date": "...", "end_date": "..."}
    row_count: int
    checksum: str
    creation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "schema_version": self.schema_version,
            "provider": self.provider,
            "symbols": self.symbols,
            "asset_type": self.asset_type,
            "time_range": self.time_range,
            "row_count": self.row_count,
            "checksum": self.checksum,
            "creation_timestamp": self.creation_timestamp,
        }
