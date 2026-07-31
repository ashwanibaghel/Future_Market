import os
import json
import logging
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq

from app.research_os.governance.dataset_registry import (
    RESEARCH_STORAGE_DIR,
    FEATURE_STORE_DIR,
    ensure_research_storage_structure,
)

logger = logging.getLogger("research_os.feature_store.registry")

FEATURE_INDEX_SCHEMA = pa.schema([
    ("feature_dataset_id", pa.string()),
    ("symbol", pa.string()),
    ("year", pa.string()),
    ("month", pa.string()),
    ("feature_version", pa.string()),
    ("schema_version", pa.string()),
    ("generation_timestamp", pa.string()),
    ("total_rows", pa.int64()),
    ("storage_size_bytes", pa.int64()),
    ("sha256_checksum", pa.string()),
    ("status", pa.string()),
])


class FeatureRegistry:
    """Manages metadata registration, version tracking, and querying for Feature Store datasets."""

    def __init__(self, base_dir: str = FEATURE_STORE_DIR):
        ensure_research_storage_structure()
        self.feature_dir = base_dir
        os.makedirs(self.feature_dir, exist_ok=True)
        self.index_json = os.path.join(self.feature_dir, "feature_index.json")
        self.index_parquet = os.path.join(self.feature_dir, "feature_index.parquet")

    def register_feature_dataset(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Registers a computed feature dataset into the Feature Registry using atomic swaps."""
        required_fields = ["feature_dataset_id", "symbol", "year", "month", "feature_version", "total_rows"]
        for f in required_fields:
            if f not in metadata:
                raise ValueError(f"Feature metadata missing mandatory field: '{f}'")

        entry = {
            "feature_dataset_id": str(metadata["feature_dataset_id"]),
            "symbol": str(metadata["symbol"]).upper(),
            "year": str(metadata["year"]),
            "month": str(metadata["month"]),
            "feature_version": str(metadata.get("feature_version", "F-v1.0.0")),
            "schema_version": str(metadata.get("schema_version", "FS-v1.0.0")),
            "generation_timestamp": str(metadata.get("generation_timestamp", datetime.now(timezone.utc).isoformat())),
            "total_rows": int(metadata["total_rows"]),
            "storage_size_bytes": int(metadata.get("storage_size_bytes", 0)),
            "sha256_checksum": str(metadata.get("sha256_checksum", "")),
            "status": str(metadata.get("status", "RESEARCH_READY")),
        }

        existing = self.list_feature_datasets()
        filtered = [e for e in existing if e["feature_dataset_id"] != entry["feature_dataset_id"]]
        filtered.append(entry)

        self._write_json_index_atomic(filtered)
        self._write_parquet_index_atomic(filtered)
        logger.info("Registered Feature Dataset '%s' (Version: %s, Rows: %d)", entry["feature_dataset_id"], entry["feature_version"], entry["total_rows"])
        return entry

    def list_feature_datasets(self, symbol: Optional[str] = None, feature_version: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists registered feature datasets with optional filtering."""
        if not os.path.exists(self.index_json):
            return []

        try:
            with open(self.index_json, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception as exc:
            logger.warning("Failed to read feature registry JSON index: %s", str(exc))
            return []

        if symbol:
            entries = [e for e in entries if e.get("symbol") == symbol.upper()]
        if feature_version:
            entries = [e for e in entries if e.get("feature_version") == feature_version]
        return entries

    def get_feature_dataset_entry(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Fetches metadata entry for a specific feature dataset ID."""
        entries = self.list_feature_datasets()
        for e in entries:
            if e.get("feature_dataset_id") == dataset_id:
                return e
        return None

    def _write_json_index_atomic(self, entries: List[Dict[str, Any]]):
        """Writes JSON index atomically using temporary file swap."""
        temp_dir = os.path.dirname(self.index_json)
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(entries, tf, indent=2)
            temp_name = tf.name
        os.replace(temp_name, self.index_json)

    def _write_parquet_index_atomic(self, entries: List[Dict[str, Any]]):
        """Writes Parquet index atomically."""
        if not entries:
            return
        temp_dir = os.path.dirname(self.index_parquet)
        with tempfile.NamedTemporaryFile("wb", dir=temp_dir, delete=False, suffix=".parquet") as tf:
            temp_name = tf.name

        table = pa.Table.from_pylist(entries, schema=FEATURE_INDEX_SCHEMA)
        pq.write_table(table, temp_name, compression="zstd")
        try:
            os.replace(temp_name, self.index_parquet)
        except PermissionError:
            pq.write_table(table, self.index_parquet, compression="zstd")
            try:
                os.remove(temp_name)
            except Exception:
                pass
