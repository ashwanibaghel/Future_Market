import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq

# Base directory for Research Operating System Layer 2 Storage
RESEARCH_STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../research_storage"))

# Subdirectory Hierarchy Setup
PARQUET_LAKE_DIR = os.path.join(RESEARCH_STORAGE_DIR, "parquet_lake")
DATASET_REGISTRY_DIR = os.path.join(RESEARCH_STORAGE_DIR, "dataset_registry")
QUALITY_REPORTS_DIR = os.path.join(RESEARCH_STORAGE_DIR, "quality_reports")
CHECKSUMS_DIR = os.path.join(RESEARCH_STORAGE_DIR, "checksums")
EXPERIMENT_REGISTRY_DIR = os.path.join(RESEARCH_STORAGE_DIR, "experiment_registry")
CASE_LIBRARY_DIR = os.path.join(RESEARCH_STORAGE_DIR, "case_library")
RESEARCH_NOTEBOOKS_DIR = os.path.join(RESEARCH_STORAGE_DIR, "research_notebooks")
FEATURE_STORE_DIR = os.path.join(RESEARCH_STORAGE_DIR, "feature_store")


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
        Registers a dataset entry into dataset_registry.
        Mandatory provenance fields required.
        """
        required_fields = ["dataset_id", "dataset_version", "symbol", "total_rows", "sha256_checksum"]
        for field in required_fields:
            if field not in metadata:
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

        # 1. Update JSON index file for lightweight reading
        existing_entries = self.list_datasets()
        # Remove duplicate dataset_id if re-registering
        filtered = [e for e in existing_entries if e["dataset_id"] != entry["dataset_id"]]
        filtered.append(entry)

        with open(self.index_json, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2)

        # 2. Update Parquet index file
        self._write_parquet_index(filtered)
        return entry

    def list_datasets(self, symbol: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all registered datasets with optional filtering."""
        if not os.path.exists(self.index_json):
            return []
        
        try:
            with open(self.index_json, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception:
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

    def _write_parquet_index(self, entries: List[Dict[str, Any]]):
        """Helper to write entries to Parquet format."""
        if not entries:
            return
        table = pa.Table.from_pylist(entries)
        pq.write_table(table, self.index_parquet, compression="zstd")
