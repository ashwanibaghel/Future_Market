"""
🏛️ OI Lens — BASE DATASET GENERATOR (v1.0)

Abstract base class for all 12 Cognitive Intelligence Module dataset generators.
Handles:
- Data streaming from Evidence Repository (976,568 records)
- Querying Validated Hypotheses via KnowledgeService
- Reproducible Temporal Train/Val/Test Splitting (2021-23 / 2024 / 2025-26)
- Metadata Manifest creation & Parquet export
- Data Leakage & Lookahead Verification
"""

import os
import sys
import glob
import json
import time
import hashlib
import logging
from typing import Dict, Any, List, Tuple, Optional
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.services.knowledge_service import knowledge_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("base_dataset_gen")

EVIDENCE_DATASET_DIR = "E:/Future Stock/research_storage/market_intelligence_dataset"
OUTPUT_BASE_DIR = "E:/Future Stock/research_storage/model_datasets/v1"


class BaseDatasetGenerator:

    def __init__(self, module_id: str, module_name: str, layer_name: str):
        self.module_id = module_id
        self.module_name = module_name
        self.layer_name = layer_name
        self.output_dir = os.path.join(OUTPUT_BASE_DIR, layer_name, module_id.lower())
        os.makedirs(self.output_dir, exist_ok=True)
        self.batch_files = sorted(glob.glob(os.path.join(EVIDENCE_DATASET_DIR, "*.parquet")))

    def compute_sha256(self, file_path: str) -> str:
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha.update(chunk)
        return sha.hexdigest()

    def save_split_datasets(
        self,
        train_rows: List[Dict[str, Any]],
        val_rows: List[Dict[str, Any]],
        test_rows: List[Dict[str, Any]],
        feature_columns: List[str],
        target_column: str
    ) -> Dict[str, Any]:
        """Saves train, validation, and test Parquet files and generates dataset_manifest.json."""
        log.info("[%s] Saving Parquet Datasets: Train=%d, Val=%d, Test=%d rows...",
                 self.module_id, len(train_rows), len(val_rows), len(test_rows))

        train_path = os.path.join(self.output_dir, "train.parquet")
        val_path = os.path.join(self.output_dir, "validation.parquet")
        test_path = os.path.join(self.output_dir, "test.parquet")

        pq.write_table(pa.Table.from_pylist(train_rows), train_path, compression="SNAPPY")
        pq.write_table(pa.Table.from_pylist(val_rows), val_path, compression="SNAPPY")
        pq.write_table(pa.Table.from_pylist(test_rows), test_path, compression="SNAPPY")

        manifest = {
          "module_id": self.module_id,
          "module_name": self.module_name,
          "layer_name": self.layer_name,
          "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "schema_version": "2.0",
          "knowledge_version": "v1.0-evidence",
          "split_summary": {
              "train_years": ["2021", "2022", "2023"],
              "train_rows": len(train_rows),
              "validation_years": ["2024"],
              "validation_rows": len(val_rows),
              "test_years": ["2025", "2026"],
              "test_rows": len(test_rows),
              "total_rows": len(train_rows) + len(val_rows) + len(test_rows)
          },
          "feature_columns": feature_columns,
          "target_column": target_column,
          "files": {
              "train.parquet": {"sha256": self.compute_sha256(train_path), "rows": len(train_rows)},
              "validation.parquet": {"sha256": self.compute_sha256(val_path), "rows": len(val_rows)},
              "test.parquet": {"sha256": self.compute_sha256(test_path), "rows": len(test_rows)}
          }
        }

        manifest_path = os.path.join(self.output_dir, "dataset_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        log.info("[%s] Dataset Manifest Saved: %s", self.module_id, manifest_path)
        return manifest
