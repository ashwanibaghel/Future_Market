import hashlib
import os
import re
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("research_os.versioning")

# Universal Semantic Version Matrix
RULE_ENGINE_VERSION = "R-v2.5.0"
KNOWLEDGE_ENGINE_VERSION = "K-v1.0.0"
REPLAY_ENGINE_VERSION = "RP-v1.0.0"
FEATURE_REGISTRY_VERSION = "F-v1.0.0"
MEMORY_LIBRARY_VERSION = "MEM-v1.0.0"
ETL_TOOL_VERSION = "ETL-v1.0.0"
DEFAULT_DATASET_VERSION = "DS-v1.0.0"

SEMVER_REGEX = re.compile(r"^(R|K|RP|F|MEM|ETL|DS)-v\d+\.\d+\.\d+$")


def validate_semver(version_str: str) -> bool:
    """Validates if a version string complies with OI Lens SemVer format (e.g., DS-v1.0.0)."""
    return bool(SEMVER_REGEX.match(version_str))


def get_git_commit_hash() -> str:
    """Retrieve the current git commit hash for exact code reproducibility."""
    try:
        cmd = ["git", "rev-parse", "HEAD"]
        repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        res = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception as exc:
        logger.warning("Failed to retrieve git commit hash: %s", str(exc))
    return "UNKNOWN_GIT_COMMIT"


def calculate_file_sha256(filepath: str) -> str:
    """Compute the SHA256 checksum of a file for data integrity verification."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found for SHA256 calculation: {filepath}")
    
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def calculate_bytes_sha256(data_bytes: bytes) -> str:
    """Compute SHA256 checksum of in-memory bytes."""
    return hashlib.sha256(data_bytes).hexdigest()


def build_provenance_header(
    dataset_id: str,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    sha256_checksum: str = "",
    source_database: str = "options_data.db",
    git_commit_hash: Optional[str] = None,
    rule_version: str = RULE_ENGINE_VERSION,
    feature_version: str = FEATURE_REGISTRY_VERSION,
    provenance_status: str = "VALIDATED"
) -> Dict[str, Any]:
    """
    Constructs an immutable Provenance Header enforcing the CTO Mandate:
    'No Data Without Provenance'
    """
    if not validate_semver(dataset_version):
        logger.warning("dataset_version '%s' does not match SemVer regex format", dataset_version)

    if not git_commit_hash or git_commit_hash == "UNKNOWN_GIT_COMMIT":
        git_commit_hash = get_git_commit_hash()

    return {
        "provenance": {
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "export_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "export_tool_version": ETL_TOOL_VERSION,
            "git_commit_hash": git_commit_hash,
            "rule_version": rule_version,
            "knowledge_version": KNOWLEDGE_ENGINE_VERSION,
            "feature_version": feature_version,
            "source_database": source_database,
            "sha256_checksum": sha256_checksum,
            "provenance_status": provenance_status,
        }
    }

