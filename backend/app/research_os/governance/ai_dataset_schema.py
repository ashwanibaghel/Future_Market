import os
from typing import Dict, Any
import pyarrow as pa

from app.research_os.governance.dataset_registry import RESEARCH_STORAGE_DIR

AI_DATASETS_DIR = os.path.join(RESEARCH_STORAGE_DIR, "ai_datasets")
AI_FEATURES_DIR = os.path.join(AI_DATASETS_DIR, "features")
AI_LABELS_DIR = os.path.join(AI_DATASETS_DIR, "labels")
AI_TARGETS_DIR = os.path.join(AI_DATASETS_DIR, "targets")
AI_MODELS_DIR = os.path.join(AI_DATASETS_DIR, "models")


def ensure_ai_storage_structure() -> Dict[str, str]:
    """Phase 9: AI Dataset Foundation Architecture Setup."""
    dirs = {
        "root": AI_DATASETS_DIR,
        "features": AI_FEATURES_DIR,
        "labels": AI_LABELS_DIR,
        "targets": AI_TARGETS_DIR,
        "models": AI_MODELS_DIR,
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    return dirs
