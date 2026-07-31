from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Generator
import pyarrow as pa


class BaseCollectorPlugin(ABC):
    """
    Abstract Collector Plugin Interface.
    Every market data collector (Options, Equity Stocks, Sector Indices, VIX, Breadth, Macro)
    implements this interface.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the data source collector."""
        pass

    @property
    @abstractmethod
    def asset_type(self) -> str:
        """Asset class type (OPTIONS, EQUITIES, INDICES, VIX, BREADTH, MACRO)."""
        pass

    @property
    @abstractmethod
    def canonical_schema(self) -> pa.Schema:
        """PyArrow schema for the normalized canonical dataset."""
        pass

    def initialize(self, config: Optional[Dict[str, Any]] = None):
        """Lifecycle initialization method."""
        pass

    @abstractmethod
    def fetch_historical_chunk(self, symbol: str, start_date: str, end_date: str) -> Optional[pa.Table]:
        """Fetches and normalizes a historical data chunk into a PyArrow Table."""
        pass

    def stream_live_tick(self) -> Generator[Dict[str, Any], None, None]:
        """Streams real-time live market ticks."""
        return
        yield {}
