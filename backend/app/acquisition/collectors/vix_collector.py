import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import pyarrow as pa

from app.acquisition.framework.base_collector import BaseCollectorPlugin
from app.acquisition.framework.canonical_schema_registry import CanonicalSchemaRegistry, VIX_SCHEMA
from app.acquisition.framework.data_source_registry import DataSourceRegistry
from app.acquisition.upstox_client import UpstoxApiClient

logger = logging.getLogger("acquisition.collectors.vix")


class IndiaVixCollector(BaseCollectorPlugin):
    """
    Sprint D2 Production India VIX Volatility Collector Plugin.
    Connects to production UpstoxApiClient for real India VIX data.
    """

    def __init__(self, api_client: Optional[UpstoxApiClient] = None):
        self.api_client = api_client or UpstoxApiClient()

    @property
    def source_name(self) -> str:
        return "INDIA_VIX_COLLECTOR"

    @property
    def asset_type(self) -> str:
        return "VIX"

    @property
    def canonical_schema(self) -> pa.Schema:
        return VIX_SCHEMA

    def fetch_historical_chunk(self, symbol: str, start_date: str, end_date: str) -> Optional[pa.Table]:
        """
        Fetches production India VIX candles using UpstoxApiClient.
        Returns normalized PyArrow Table matching VIX_SCHEMA.
        """
        instrument_key = "NSE_INDEX|India VIX"

        raw_candles = self.api_client.fetch_historical_candles(
            instrument_key=instrument_key,
            interval="1minute",
            to_date=end_date,
            from_date=start_date,
        )

        if not raw_candles:
            logger.warning("No raw candles returned by UpstoxApiClient for India VIX (%s to %s)", start_date, end_date)
            return None

        timestamps = []
        ts_utcs = []
        opens = []
        highs = []
        lows = []
        closes = []
        pcts = []

        prev_close = None
        for c in raw_candles:
            ts_str = str(c[0])
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                ts_utc = int(dt.timestamp())
            except Exception:
                ts_utc = 0

            op = float(c[1])
            hi = float(c[2])
            lo = float(c[3])
            cl = float(c[4])

            pct = round(((cl - prev_close) / prev_close) * 100.0, 4) if prev_close else 0.0
            prev_close = cl

            timestamps.append(ts_str)
            ts_utcs.append(ts_utc)
            opens.append(op)
            highs.append(hi)
            lows.append(lo)
            closes.append(cl)
            pcts.append(pct)

        table = pa.Table.from_arrays(
            [
                pa.array(timestamps, type=pa.string()),
                pa.array(ts_utcs, type=pa.int64()),
                pa.array(opens, type=pa.float64()),
                pa.array(highs, type=pa.float64()),
                pa.array(lows, type=pa.float64()),
                pa.array(closes, type=pa.float64()),
                pa.array(pcts, type=pa.float64()),
                pa.array(["UPSTOX"] * len(timestamps), type=pa.string()),
            ],
            schema=self.canonical_schema,
        )
        return table


# Register with DataSourceRegistry
DataSourceRegistry.register_collector(IndiaVixCollector)
