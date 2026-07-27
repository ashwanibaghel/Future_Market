import os
import json
import logging
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger("research_os.governance.dataset_registry")

# Base directory for Research Operating System Layer 2 Storage
RESEARCH_STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../research_storage"))

# Subdirectory Hierarchy Setup
PARQUET_LAKE_DIR = os.path.join(RESEARCH_STORAGE_DIR, "parquet_lake")
DATASET_REGISTRY_DIR = os.path.join(RESEARCH_STORAGE_DIR, "dataset_registry")
QUALITY_REPORTS_DIR = os.path.join(RESEARCH_STORAGE_DIR, "quality_reports")
CHECKSUMS_DIR = os.path.join(RESEARCH_STORAGE_DIR, "checksums")
EXPERIMENT_REGISTRY_DIR = os.path.join(RESEARCH_STORAGE_DIR, "experiment_registry")
CASE_LIBRARY_DIR = os.path.join(RESEARCH_STORAGE_DIR, "case_library")
RESEARCH_NOTEBOOKS_DIR = os.path.join(RESEARCH_STORAGE_DIR, "research_notebooks")
FEATURE_STORE_DIR = os.path.join(RESEARCH_STORAGE_DIR, "feature_store")

DATASET_INDEX_SCHEMA = pa.schema([
    ("dataset_id", pa.string()),
    ("dataset_version", pa.string()),
    ("created_date", pa.string()),
    ("symbol", pa.string()),
    ("start_date", pa.string()),
    ("end_date", pa.string()),
    ("total_rows", pa.int64()),
    ("total_snapshots", pa.int64()),
    ("feature_version", pa.string()),
    ("rule_version", pa.string()),
    ("git_commit", pa.string()),
    ("sha256_checksum", pa.string()),
    ("compression_format", pa.string()),
    ("storage_size_bytes", pa.int64()),
    ("status", pa.string()),
])



def ensure_research_storage_structure() -> Dict[str, str]:
    """Ensures all 8 research storage directories exist."""
    directories = {
        "root": RESEARCH_STORAGE_DIR,
        "parquet_lake": PARQUET_LAKE_DIR,
        "dataset_registry": DATASET_REGISTRY_DIR,
        "quality_reports": QUALITY_REPORTS_DIR,
        "checksums": CHECKSUMS_DIR,
        "experiment_registry": EXPERIMENT_REGISTRY_DIR,
        "case_library": CASE_LIBRARY_DIR,
        "research_notebooks": RESEARCH_NOTEBOOKS_DIR,
        "feature_store": FEATURE_STORE_DIR,
    }
    for key, path in directories.items():
        os.makedirs(path, exist_ok=True)
    return directories


class DatasetRegistry:
    """Manages recording, indexing, and querying registered analytical datasets."""

    def __init__(self):
        self.dirs = ensure_research_storage_structure()
        self.index_parquet = os.path.join(DATASET_REGISTRY_DIR, "dataset_index.parquet")
        self.index_json = os.path.join(DATASET_REGISTRY_DIR, "dataset_index.json")

    def register_dataset(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registers a dataset entry into dataset_registry using atomic file swaps.
        Mandatory provenance fields required.
        """
        required_fields = ["dataset_id", "dataset_version", "symbol", "total_rows", "sha256_checksum"]
        for field in required_fields:
            if field not in metadata:
                logger.error("Registration failed: Missing mandatory field '%s'", field)
                raise ValueError(f"Dataset metadata missing mandatory provenance field: '{field}'")

        entry = {
            "dataset_id": str(metadata["dataset_id"]),
            "dataset_version": str(metadata.get("dataset_version", "DS-v1.0.0")),
            "created_date": str(metadata.get("created_date", datetime.now(timezone.utc).isoformat())),
            "symbol": str(metadata["symbol"]),
            "start_date": str(metadata.get("start_date", "")),
            "end_date": str(metadata.get("end_date", "")),
            "total_rows": int(metadata["total_rows"]),
            "total_snapshots": int(metadata.get("total_snapshots", 0)),
            "feature_version": str(metadata.get("feature_version", "F-v1.0.0")),
            "rule_version": str(metadata.get("rule_version", "R-v2.5.0")),
            "git_commit": str(metadata.get("git_commit", "")),
            "sha256_checksum": str(metadata["sha256_checksum"]),
            "compression_format": str(metadata.get("compression_format", "PARQUET_ZSTD")),
            "storage_size_bytes": int(metadata.get("storage_size_bytes", 0)),
            "status": str(metadata.get("status", "VALIDATED")),
        }

        # 1. Update JSON index file atomically (Write to temp file -> os.replace)
        existing_entries = self.list_datasets()
        filtered = [e for e in existing_entries if e["dataset_id"] != entry["dataset_id"]]
        filtered.append(entry)

        self._write_json_index_atomic(filtered)

        # 2. Update Parquet index file atomically
        self._write_parquet_index_atomic(filtered)
        logger.info("Successfully registered dataset '%s' (Status: %s)", entry["dataset_id"], entry["status"])
        return entry

    def list_datasets(self, symbol: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all registered datasets with optional filtering."""
        if not os.path.exists(self.index_json):
            return []
        
        try:
            with open(self.index_json, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception as exc:
            logger.warning("Failed to read JSON dataset index: %s", str(exc))
            return []

        if symbol:
            entries = [e for e in entries if e.get("symbol") == symbol]
        if status:
            entries = [e for e in entries if e.get("status") == status]
        return entries

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Fetch details for a specific dataset ID."""
        entries = self.list_datasets()
        for e in entries:
            if e.get("dataset_id") == dataset_id:
                return e
        return None

    def _write_json_index_atomic(self, entries: List[Dict[str, Any]]):
        """Helper to write JSON index atomically to prevent corruption."""
        temp_dir = os.path.dirname(self.index_json)
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(entries, tf, indent=2)
            temp_name = tf.name
        os.replace(temp_name, self.index_json)

    def _write_parquet_index_atomic(self, entries: List[Dict[str, Any]]):
        """Helper to write Parquet index atomically."""
        if not entries:
            return
        temp_dir = os.path.dirname(self.index_parquet)
        with tempfile.NamedTemporaryFile("wb", dir=temp_dir, delete=False, suffix=".parquet") as tf:
            temp_name = tf.name

        table = pa.Table.from_pylist(entries, schema=DATASET_INDEX_SCHEMA)
        pq.write_table(table, temp_name, compression="zstd")
        os.replace(temp_name, self.index_parquet)



