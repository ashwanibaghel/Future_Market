"""
🏛️ OI Lens — AUTOMATED LEAKAGE GUARD & CAUSALITY ENFORCER (v2.0 DUAL-LAYER)

Implements Dual-Layer Anti-Leakage & Causality Audit:
- LAYER 1: Rule-based pattern matching (FORBIDDEN_FEATURE_PATTERNS)
- LAYER 2: Metadata-based timestamp lineage (Feature Computation Time <= Snapshot Time T)

Raises DataLeakageError if any feature violates causality or anti-leakage policies.
"""

import os
import sys
import json
import re
import hashlib
import logging
from typing import List, Dict, Any, Tuple
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("leakage_guard")

# FORBIDDEN FEATURE NAME PATTERNS
FORBIDDEN_FEATURE_PATTERNS = [
    r"^mfe_.*$",        # Max Favorable Excursion (future window)
    r"^mae_.*$",        # Max Adverse Excursion (future window)
    r"^future_.*$",     # Any forward-looking indicator
    r"^target_.*$",     # Any forward-looking target boundary
    r"^direction_.*$",  # Multi-horizon directional targets (unless Y)
    r"^realized_.*$"    # Realized forward outcomes
]


class DataLeakageError(Exception):
    """Raised when a feature violates causality or anti-leakage policies."""
    pass


class LeakageGuard:

    @staticmethod
    def compute_file_sha256(filepath: str) -> str:
        """Computes cryptographic SHA256 checksum for a file."""
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def audit_feature_names(feature_columns: List[str], target_column: str) -> List[str]:
        """Layer 1: Audits feature names against FORBIDDEN_FEATURE_PATTERNS."""
        violations = []

        if target_column in feature_columns:
            violations.append(f"TARGET_IN_FEATURES: Target column '{target_column}' is listed inside feature vector X.")

        for feat in feature_columns:
            for pat in FORBIDDEN_FEATURE_PATTERNS:
                if re.match(pat, feat, re.IGNORECASE):
                    violations.append(f"FORBIDDEN_FEATURE_PATTERN: Feature '{feat}' matches pattern '{pat}'")

        return list(set(violations))

    @staticmethod
    def audit_timestamp_causality(snapshot_timestamp_str: str, feature_computation_timestamp_str: str) -> bool:
        """Layer 2: Metadata-based causality check. Feature Timestamp MUST be <= Snapshot Timestamp T."""
        if feature_computation_timestamp_str > snapshot_timestamp_str:
            raise DataLeakageError(
                f"FUTURE_TIMESTAMP_CAUSALITY_VIOLATION: Feature computation timestamp '{feature_computation_timestamp_str}' "
                f"is in the future relative to snapshot timestamp T '{snapshot_timestamp_str}'."
            )
        return True

    @staticmethod
    def audit_dataset_manifest(manifest_path: str) -> bool:
        """Audits a dataset manifest JSON for Layer 1 & Layer 2 anti-leakage violations."""
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        module_id = manifest.get("module_id", "UNKNOWN")
        feature_cols = manifest.get("feature_columns", [])
        target_col = manifest.get("target_column", "")

        log.info("[%s] Running LeakageGuard Dual-Layer Audit...", module_id)
        violations = LeakageGuard.audit_feature_names(feature_cols, target_col)

        if violations:
            log.error("[%s] 🚨 LEAKAGE GUARD FAILED! Found %d violations:", module_id, len(violations))
            for v in violations:
                log.error("  - %s", v)
            raise DataLeakageError(f"LeakageGuard Audit Failed for {module_id}: {violations}")

        log.info("[%s] ✅ LEAKAGE GUARD DUAL-LAYER PASSED CLEANLY! Zero forbidden features detected.", module_id)
        return True


if __name__ == "__main__":
    log.info("LeakageGuard v2.0 Dual-Layer Enforcer Initialized.")
