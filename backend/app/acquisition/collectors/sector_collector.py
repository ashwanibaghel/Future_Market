import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import pyarrow as pa

from app.acquisition.framework.base_collector import BaseCollectorPlugin
from app.acquisition.framework.canonical_schema_registry import CanonicalSchemaRegistry, EQUITY_CANDLE_SCHEMA
from app.acquisition.framework.data_source_registry import DataSourceRegistry
from app.acquisition.upstox_client import UpstoxApiClient

logger = logging.getLogger("acquisition.collectors.sector")


class SectorIndexCollector(BaseCollectorPlugin):
    """
    Sprint D2 Production Sector Index OHLCV Collector Plugin.
    Connects to production UpstoxApiClient for real historical sector index data.
    """

    def __init__(self, api_client: Optional[UpstoxApiClient] = None):
        self.api_client = api_client or UpstoxApiClient()

    @property
    def source_name(self) -> str:
        return "SECTOR_INDEX_COLLECTOR"

    @property
    def asset_type(self) -> str:
        return "INDICES"

    @property
    def canonical_schema(self) -> pa.Schema:
        return EQUITY_CANDLE_SCHEMA

    def fetch_historical_chunk(self, symbol: str, start_date: str, end_date: str) -> Optional[pa.Table]:
        """
        Fetches production sector index OHLCV candles using UpstoxApiClient.
        Returns normalized PyArrow Table matching EQUITY_CANDLE_SCHEMA.
        """
        sym = symbol.upper()
        instrument_key = f"NSE_INDEX|{sym}"

        raw_candles = self.api_client.fetch_historical_candles(
            instrument_key=instrument_key,
            interval="1minute",
            to_date=end_date,
            from_date=start_date,
        )

        if not raw_candles:
            logger.warning("No raw candles returned by UpstoxApiClient for %s (%s to %s)", sym, start_date, end_date)
            return None

        timestamps = []
        ts_utcs = []
        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []
        vwaps = []

        for c in raw_candles:
            ts_str = str(c[0])
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                ts_utc = int(dt.timestamp())
            except Exception:
                ts_utc = 0

            timestamps.append(ts_str)
            ts_utcs.append(ts_utc)
            opens.append(float(c[1]))
            highs.append(float(c[2]))
            lows.append(float(c[3]))
            closes.append(float(c[4]))
            volumes.append(int(c[5]) if len(c) > 5 else 0)
            vwaps.append(float(c[4]))

        table = pa.Table.from_arrays(
            [
                pa.array(timestamps, type=pa.string()),
                pa.array(ts_utcs, type=pa.int64()),
                pa.array([sym] * len(timestamps), type=pa.string()),
                pa.array(["NSE"] * len(timestamps), type=pa.string()),
                pa.array(opens, type=pa.float64()),
                pa.array(highs, type=pa.float64()),
                pa.array(lows, type=pa.float64()),
                pa.array(closes, type=pa.float64()),
                pa.array(volumes, type=pa.int64()),
                pa.array(vwaps, type=pa.float64()),
                pa.array(["UPSTOX"] * len(timestamps), type=pa.string()),
            ],
            schema=self.canonical_schema,
        )
        return table


# Register with DataSourceRegistry
DataSourceRegistry.register_collector(SectorIndexCollector)
