"""
🏛️ OI Lens — BASE MODEL TRAINER (v2.0 REPRODUCIBLE FINGERPRINTING)

Abstract base class for training ML models across the 12 Cognitive Intelligence Modules.
Handles:
- Dataset loading & SHA256 Fingerprint calculation
- Training Fingerprint generation (Python version, Library versions, Random seed, Duration)
- LeakageGuard pre-training audit
- Model Registry registration (`model_registry.py`)
- Metric evaluation & Explainability summary persistence
"""

import os
import sys
import json
import time
import hashlib
import platform
import logging
from typing import Dict, Any, List, Tuple, Optional
import pyarrow.parquet as pq
import sklearn
import lightgbm as lgb

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from app.validation.leakage_guard import LeakageGuard
from app.models.model_registry import model_registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("base_model_trainer")

MODEL_DATASETS_DIR = "E:/Future Stock/research_storage/model_datasets/v1"
TRAINED_MODELS_DIR = "E:/Future Stock/research_storage/trained_models/v1"
os.makedirs(TRAINED_MODELS_DIR, exist_ok=True)


class BaseModelTrainer:

    def __init__(self, module_id: str, module_name: str, layer_name: str, model_version: str = "v1.0.0"):
        self.module_id = module_id
        self.module_name = module_name
        self.layer_name = layer_name
        self.model_version = model_version
        self.dataset_dir = os.path.join(MODEL_DATASETS_DIR, layer_name, module_id.lower())
        self.model_dir = os.path.join(TRAINED_MODELS_DIR, module_id.lower())
        os.makedirs(self.model_dir, exist_ok=True)

    def load_split_datasets(self) -> Tuple[Any, Any, Any, List[str], str, Dict[str, str]]:
        """Loads datasets, audits with LeakageGuard, and computes SHA256 Fingerprints."""
        manifest_path = os.path.join(self.dataset_dir, "dataset_manifest.json")
        train_path = os.path.join(self.dataset_dir, "train.parquet")
        val_path = os.path.join(self.dataset_dir, "validation.parquet")
        test_path = os.path.join(self.dataset_dir, "test.parquet")

        # 1. LeakageGuard Pre-Training Audit
        LeakageGuard.audit_dataset_manifest(manifest_path)

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        feature_cols = manifest["feature_columns"]
        target_col = manifest["target_column"]

        # 2. Compute SHA256 Dataset Fingerprints
        dataset_fingerprint = {
            "train_sha256": LeakageGuard.compute_file_sha256(train_path),
            "val_sha256": LeakageGuard.compute_file_sha256(val_path),
            "test_sha256": LeakageGuard.compute_file_sha256(test_path),
            "manifest_sha256": LeakageGuard.compute_file_sha256(manifest_path)
        }

        tbl_train = pq.read_table(train_path)
        tbl_val = pq.read_table(val_path)
        tbl_test = pq.read_table(test_path)

        log.info("[%s] Datasets Loaded & SHA256 Audited: Train=%d, Val=%d, Test=%d rows.",
                 self.module_id, tbl_train.num_rows, tbl_val.num_rows, tbl_test.num_rows)

        return tbl_train, tbl_val, tbl_test, feature_cols, target_col, dataset_fingerprint

    def get_training_fingerprint(self, random_seed: int, hyperparameters: Dict[str, Any], duration_sec: float) -> Dict[str, Any]:
        """Generates complete Training Fingerprint for 100% scientific reproducibility."""
        return {
            "random_seed": random_seed,
            "python_version": platform.python_version(),
            "os_system": platform.system(),
            "library_versions": {
                "scikit-learn": sklearn.__version__,
                "lightgbm": lgb.__version__
            },
            "training_duration_sec": round(duration_sec, 2),
            "hyperparameters": hyperparameters
        }

    def save_model_manifest_and_register(
        self,
        metrics_summary: Dict[str, Any],
        feature_importance: Dict[str, float],
        hyperparameters: Dict[str, Any],
        dataset_fingerprint: Dict[str, str],
        model_filename: str,
        duration_sec: float,
        random_seed: int = 42,
        deployment_status: str = "RESEARCH_DRAFT"
    ):
        """Saves persistent manifest and registers model in ModelRegistry."""
        training_fp = self.get_training_fingerprint(random_seed, hyperparameters, duration_sec)

        manifest = {
            "module_id": self.module_id,
            "module_name": self.module_name,
            "layer_name": self.layer_name,
            "version": self.model_version,
            "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "schema_version": "2.0",
            "model_filename": model_filename,
            "dataset_fingerprint": dataset_fingerprint,
            "training_fingerprint": training_fp,
            "metrics": metrics_summary,
            "feature_importance": feature_importance
        }

        out_path = os.path.join(self.model_dir, "model_manifest.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Register in ModelRegistry
        model_registry.register_model(
            module_id=self.module_id,
            version=self.model_version,
            dataset_fingerprint=dataset_fingerprint,
            training_fingerprint=training_fp,
            metrics=metrics_summary,
            explainability_summary={"feature_importance_gain_pct": feature_importance},
            deployment_status=deployment_status
        )

        log.info("[%s] Model Manifest & Registry Entry Saved: %s", self.module_id, out_path)
