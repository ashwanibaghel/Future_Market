import logging
import pyarrow as pa
from typing import Dict, Any, Optional
from app.acquisition.normalizer import CANONICAL_OPTION_SCHEMA

logger = logging.getLogger("acquisition.framework.schema_registry")

# Equity Stock Candle Schema (NIFTY 50)
EQUITY_CANDLE_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("timestamp_utc", pa.int64()),
    ("symbol", pa.string()),
    ("exchange", pa.string()),
    ("open", pa.float64()),
    ("high", pa.float64()),
    ("low", pa.float64()),
    ("close", pa.float64()),
    ("volume", pa.int64()),
    ("vwap", pa.float64()),
    ("provider", pa.string()),
])

# Volatility Index Schema (India VIX)
VIX_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("timestamp_utc", pa.int64()),
    ("vix_open", pa.float64()),
    ("vix_high", pa.float64()),
    ("vix_low", pa.float64()),
    ("vix_close", pa.float64()),
    ("vix_change_pct", pa.float64()),
    ("provider", pa.string()),
])

# Market Breadth Schema
BREADTH_SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("timestamp_utc", pa.int64()),
    ("advances", pa.int32()),
    ("declines", pa.int32()),
    ("unchanged", pa.int32()),
    ("advance_decline_ratio", pa.float64()),
    ("new_52w_highs", pa.int32()),
    ("new_52w_lows", pa.int32()),
])


class CanonicalSchemaRegistry:
    """Central registry for discovering and validating PyArrow canonical schemas across asset classes."""

    _schemas: Dict[str, pa.Schema] = {
        "OPTIONS": CANONICAL_OPTION_SCHEMA,
        "EQUITIES": EQUITY_CANDLE_SCHEMA,
        "INDICES": EQUITY_CANDLE_SCHEMA,
        "VIX": VIX_SCHEMA,
        "BREADTH": BREADTH_SCHEMA,
    }

    @classmethod
    def register_schema(cls, asset_type: str, schema: pa.Schema):
        cls._schemas[asset_type.upper()] = schema
        logger.info("Registered Canonical Schema for Asset Type '%s'", asset_type.upper())

    @classmethod
    def get_schema(cls, asset_type: str) -> Optional[pa.Schema]:
        return cls._schemas.get(asset_type.upper())
