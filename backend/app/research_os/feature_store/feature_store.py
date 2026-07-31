import os
import json
import logging
import hashlib
from typing import Dict, Any, List, Optional, Union
import pyarrow as pa
import pyarrow.parquet as pq

from app.research_os.governance.dataset_registry import FEATURE_STORE_DIR, ensure_research_storage_structure
from app.research_os.feature_store.feature_version import DEFAULT_FEATURE_VERSION, DEFAULT_FEATURE_SCHEMA_VERSION, build_feature_metadata_header
from app.research_os.feature_store.feature_registry import FeatureRegistry

logger = logging.getLogger("research_os.feature_store.store")


class FeatureStore:
    """
    Decoupled, Versioned Feature Store for Quantitative Research.
    Serves as the Single Source of Truth for derived features (PCR, IV Skew, OI Build-Up, Max Pain, VWAP).
    Enforces 'Compute once, reuse everywhere' across Replay Engine and Strategy Plugins.
    """

    def __init__(self, base_dir: str = FEATURE_STORE_DIR):
        ensure_research_storage_structure()
        self.base_dir = base_dir
        self.registry = FeatureRegistry(base_dir=base_dir)

    def get_feature_file_path(
        self,
        symbol: str,
        year: Union[int, str],
        month: Union[int, str],
        feature_version: str = DEFAULT_FEATURE_VERSION,
    ) -> str:
        """Constructs canonical storage path for versioned feature parquet file."""
        m_str = f"{int(month):02d}"
        return os.path.join(
            self.base_dir,
            f"symbol={symbol.upper()}",
            f"version={feature_version}",
            f"year={year}",
            f"month={m_str}",
            "features.parquet"
        )

    def has_features(
        self,
        symbol: str,
        year: Union[int, str],
        month: Union[int, str],
        feature_version: str = DEFAULT_FEATURE_VERSION,
    ) -> bool:
        """Checks if pre-computed feature parquet dataset exists and is non-empty."""
        path = self.get_feature_file_path(symbol, year, month, feature_version)
        if os.path.exists(path):
            try:
                pf = pq.ParquetFile(path)
                return pf.metadata.num_rows > 0
            except Exception:
                return False
        return False

    def save_features(
        self,
        features_table: pa.Table,
        symbol: str,
        year: Union[int, str],
        month: Union[int, str],
        feature_version: str = DEFAULT_FEATURE_VERSION,
        schema_version: str = DEFAULT_FEATURE_SCHEMA_VERSION,
    ) -> Dict[str, Any]:
        """
        Persists a computed PyArrow Table into the versioned Feature Store using ZSTD Parquet.
        Registers entry in Feature Registry.
        """
        path = self.get_feature_file_path(symbol, year, month, feature_version)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Write Parquet File
        pq.write_table(features_table, path, compression="zstd")
        file_size = os.path.getsize(path)

        # Calculate SHA256
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256_hash.update(chunk)
        checksum = sha256_hash.hexdigest()

        dataset_id = f"FEAT-{symbol.upper()}-{feature_version}-{year}-{int(month):02d}"

        metadata = {
            "feature_dataset_id": dataset_id,
            "symbol": symbol.upper(),
            "year": str(year),
            "month": f"{int(month):02d}",
            "feature_version": feature_version,
            "schema_version": schema_version,
            "total_rows": features_table.num_rows,
            "storage_size_bytes": file_size,
            "sha256_checksum": checksum,
            "status": "RESEARCH_READY",
        }

        # Register in Feature Registry
        self.registry.register_feature_dataset(metadata)
        logger.info("Persisted Feature Store Parquet %s (%d rows, %d KB)", path, features_table.num_rows, file_size // 1024)
        return metadata

    def get_features(
        self,
        symbol: str,
        year: Union[int, str],
        month: Union[int, str],
        feature_version: str = DEFAULT_FEATURE_VERSION,
    ) -> Optional[pa.Table]:
        """Retrieves a cached PyArrow feature table from the Feature Store."""
        path = self.get_feature_file_path(symbol, year, month, feature_version)
        if not os.path.exists(path):
            return None

        try:
            pf = pq.ParquetFile(path)
            return pf.read()
        except Exception as exc:
            logger.error("Failed reading feature parquet %s: %s", path, str(exc))
            return None
