import os
from datetime import datetime, timezone
from typing import Dict, Any

DEFAULT_FEATURE_VERSION = "F-v1.0.0"
DEFAULT_FEATURE_SCHEMA_VERSION = "FS-v1.0.0"


def build_feature_metadata_header(
    feature_version: str = DEFAULT_FEATURE_VERSION,
    schema_version: str = DEFAULT_FEATURE_SCHEMA_VERSION,
    symbol: str = "NIFTY",
) -> Dict[str, Any]:
    """Generates immutable provenance header for versioned feature datasets."""
    return {
        "feature_version": feature_version,
        "schema_version": schema_version,
        "symbol": symbol.upper(),
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
        "provider_source": "OI_LENS_CANONICAL_LAKE",
    }
