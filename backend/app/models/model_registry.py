"""
🏛️ OI Lens — MODEL REGISTRY & VERSIONING SERVICE (v1.0)

Tracks complete scientific provenance for every trained model version (e.g. v1.0.0, v1.1.0).
Stores:
- Dataset SHA256 Fingerprints
- Training Fingerprints (Random seed, Python version, library versions)
- Out-of-Time Test Metrics & Explainability Reports
- Deployment Status (RESEARCH_DRAFT, SHADOW_READY, PRODUCTION_READY)
"""

import os
import sys
import json
import time
import hashlib
import logging
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("model_registry")

REGISTRY_FILE = "E:/Future Stock/research_storage/trained_models/v1/model_registry_db.json"
os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)


class ModelRegistry:

    def __init__(self):
        self.registry_path = REGISTRY_FILE
        self._ensure_registry_db()

    def _ensure_registry_db(self):
        if not os.path.exists(self.registry_path):
            initial_db = {
                "registry_version": "1.0",
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "models": {}
            }
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump(initial_db, f, indent=2)

    def load_db(self) -> Dict[str, Any]:
        with open(self.registry_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_db(self, db: Dict[str, Any]):
        db["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)

    def register_model(
        self,
        module_id: str,
        version: str,
        dataset_fingerprint: Dict[str, str],
        training_fingerprint: Dict[str, Any],
        metrics: Dict[str, Any],
        explainability_summary: Dict[str, Any],
        deployment_status: str = "RESEARCH_DRAFT"
    ) -> Dict[str, Any]:

        db = self.load_db()

        model_entry = {
            "module_id": module_id.upper(),
            "version": version,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "dataset_fingerprint": dataset_fingerprint,
            "training_fingerprint": training_fingerprint,
            "metrics": metrics,
            "explainability_summary": explainability_summary,
            "deployment_status": deployment_status
        }

        if module_id.upper() not in db["models"]:
            db["models"][module_id.upper()] = []

        db["models"][module_id.upper()].append(model_entry)
        self.save_db(db)

        log.info("[%s] Registered Version '%s' (Status: %s)", module_id.upper(), version, deployment_status)
        return model_entry

    def get_latest_model(self, module_id: str) -> Optional[Dict[str, Any]]:
        db = self.load_db()
        models = db["models"].get(module_id.upper(), [])
        return models[-1] if models else None


model_registry = ModelRegistry()

if __name__ == "__main__":
    log.info("ModelRegistry Service Initialized at: %s", REGISTRY_FILE)
