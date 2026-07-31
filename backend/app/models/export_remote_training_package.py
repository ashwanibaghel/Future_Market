"""
🏛️ OI Lens — REMOTE GPU TRAINING PACKAGER (v5.0 LINUX FORWARD SLASH ZIP FIX)

Packages all 12 Cognitive Intelligence Module clean datasets, Constitution specs,
LeakageGuard v2.0 dual-layer policy enforcer, ModelRegistry service, training scripts,
preflight check, and run_all_gpu_training.py into a zip file with strict Linux forward slashes '/'.
"""

import os
import sys
import zipfile
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("remote_packager")

PROJECT_ROOT = "E:/Future Stock"
OUTPUT_ZIP = os.path.join(PROJECT_ROOT, "remote_gpu_training_package.zip")

FILES_TO_PACKAGE = [
    "brain_constitution.md",
    "brain_communication_protocol.md",
    "scientific_reproducibility_contract.md",
    "backend/app/models/base_model_trainer.py",
    "backend/app/models/model_registry.py",
    "backend/app/models/run_all_gpu_training.py",
    "backend/app/models/phase6_1_perception_trainer.py",
    "backend/app/models/phase6_2_direction_trainer.py",
    "backend/app/validation/leakage_guard.py",
    "backend/app/validation/preflight_gpu_check.py",
    "backend/app/validation/audit_model_explainability.py"
]

DIRS_TO_PACKAGE = [
    "research_storage/model_datasets/v1"
]


def package_for_remote_gpu():
    log.info("=" * 80)
    log.info("PACKAGING RESUMABLE ASSETS WITH FORWARD SLASHES FOR LINUX UNZIP")
    log.info("=" * 80)

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for rel_path in FILES_TO_PACKAGE:
            abs_path = os.path.join(PROJECT_ROOT, rel_path)
            if os.path.exists(abs_path):
                # Enforce forward slashes for Linux compatibility
                arc_name = rel_path.replace("\\", "/")
                zipf.write(abs_path, arc_name)
                log.info(" [+] Added file: %s", arc_name)

        for rel_dir in DIRS_TO_PACKAGE:
            abs_dir = os.path.join(PROJECT_ROOT, rel_dir)
            if os.path.exists(abs_dir):
                for root, dirs, files in os.walk(abs_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_file = os.path.relpath(full_path, PROJECT_ROOT)
                        arc_name = rel_file.replace("\\", "/")
                        zipf.write(full_path, arc_name)
                log.info(" [+] Added directory: %s", rel_dir)

    size_mb = os.path.getsize(OUTPUT_ZIP) / (1024 * 1024)
    log.info("PACKAGE CREATED SUCCESSFULLY: %s (%.2f MB)", OUTPUT_ZIP, size_mb)
    return OUTPUT_ZIP


if __name__ == "__main__":
    package_for_remote_gpu()
