import time
import hashlib
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from app.acquisition.framework.data_version import DEFAULT_DATASET_VERSION


@dataclass(frozen=True)
class DataProvenance:
    """
    Requirement 2 Scientific Data Provenance Header.
    Attached to every raw archive and canonical Parquet file to guarantee 100% scientific reproducibility.
    """
    provider: str
    provider_version: str
    collection_version: str
    collection_timestamp: str
    collection_latency_ms: float
    sha256_checksum: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_version": self.provider_version,
            "collection_version": self.collection_version,
            "collection_timestamp": self.collection_timestamp,
            "collection_latency_ms": round(self.collection_latency_ms, 3),
            "sha256_checksum": self.sha256_checksum,
        }

    @classmethod
    def create(
        cls,
        provider: str,
        content_bytes: bytes,
        provider_version: str = "v1.0",
        collection_version: str = DEFAULT_DATASET_VERSION,
        latency_ms: float = 0.0,
    ) -> "DataProvenance":
        sha256 = hashlib.sha256(content_bytes).hexdigest()
        ts = datetime.now(timezone.utc).isoformat()
        return cls(
            provider=provider.upper(),
            provider_version=provider_version,
            collection_version=collection_version,
            collection_timestamp=ts,
            collection_latency_ms=latency_ms,
            sha256_checksum=sha256,
        )
