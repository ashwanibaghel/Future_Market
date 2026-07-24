import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.research_os.replay.exceptions import TemporalLeakageError
from app.research_os.datalake.reader import DuckDBDataReader

logger = logging.getLogger("research_os.replay.context")


class BlindSnapshotContext:
    """
    Strict Temporal Isolation Context (`BlindSnapshotContext`).
    Enforces zero look-ahead bias at the system level.
    NO API exists to access data beyond self.current_time.
    """

    def __init__(self, current_time: datetime, data_reader: DuckDBDataReader):
        self._current_time: datetime = current_time
        self._reader: DuckDBDataReader = data_reader

    @property
    def current_time(self) -> datetime:
        """Returns the current simulation timestamp."""
        return self._current_time

    def _guard_timestamp(self, requested_time: datetime):
        """Temporal Firewall: Raises TemporalLeakageError if requested_time > current_time."""
        if requested_time > self._current_time:
            logger.error("Temporal Firewall Triggered! Requested %s > Current %s", requested_time, self._current_time)
            raise TemporalLeakageError(requested_time, self._current_time)

    def get_snapshot(self, symbol: str, target_time: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves option chain snapshot for symbol at target_time (defaults to current_time).
        Raises TemporalLeakageError if target_time > current_time.
        """
        effective_time = target_time if target_time is not None else self._current_time
        self._guard_timestamp(effective_time)

        # Query snapshot safely bounded by effective_time
        year_str = effective_time.strftime("%Y")
        month_str = effective_time.strftime("%m")
        
        raw_snapshots = self._reader.query_snapshots(symbol=symbol, year=year_str, month=month_str, limit=5000)
        
        # Enforce strict temporal filter: timestamp <= effective_time
        iso_target = effective_time.isoformat()
        matching = [s for s in raw_snapshots if s["timestamp"] <= iso_target]

        if not matching:
            return None

        # Return exact or latest snapshot up to effective_time
        exact = [s for s in matching if s["timestamp"] == iso_target]
        if exact:
            return exact[0]
        return matching[-1]

    def get_previous_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves snapshot immediately preceding current_time (current_time - 1 minute).
        """
        prev_time = self._current_time - timedelta(minutes=1)
        return self.get_snapshot(symbol=symbol, target_time=prev_time)

    def get_history(self, symbol: str, minutes: int) -> List[Dict[str, Any]]:
        """
        Retrieves historical snapshot window in range [current_time - minutes, current_time].
        Raises TemporalLeakageError if minutes < 0.
        """
        if minutes < 0:
            raise ValueError("History minutes parameter cannot be negative.")

        start_time = self._current_time - timedelta(minutes=minutes)
        year_str = self._current_time.strftime("%Y")
        month_str = self._current_time.strftime("%m")

        raw_snapshots = self._reader.query_snapshots(symbol=symbol, year=year_str, month=month_str, limit=10000)
        
        iso_start = start_time.isoformat()
        iso_current = self._current_time.isoformat()

        # Strict temporal isolation window: iso_start <= timestamp <= iso_current
        history = [
            s for s in raw_snapshots 
            if iso_start <= s["timestamp"] <= iso_current
        ]

        # Double check no future record leaked
        for record in history:
            rec_dt = datetime.fromisoformat(record["timestamp"])
            self._guard_timestamp(rec_dt)

        return sorted(history, key=lambda x: x["timestamp"])

    def get_market_state(self, symbol: str) -> Dict[str, Any]:
        """
        Returns high-level analytical market state (PCR, State, Support, Resistance) 
        at current_time without leaking future metrics.
        """
        snapshot = self.get_snapshot(symbol=symbol)
        if not snapshot:
            return {
                "symbol": symbol,
                "timestamp": self._current_time.isoformat(),
                "pcr": 1.0,
                "market_state": "NEUTRAL",
                "strength": "LOW",
                "support_s1": 0.0,
                "resistance_r1": 0.0,
            }

        return {
            "symbol": symbol,
            "timestamp": snapshot["timestamp"],
            "pcr": snapshot.get("pcr", 1.0),
            "market_state": snapshot.get("market_state", "NEUTRAL"),
            "strength": snapshot.get("strength", "LOW"),
            "support_s1": snapshot.get("support_s1", 0.0),
            "resistance_r1": snapshot.get("resistance_r1", 0.0),
            "spot_price": snapshot.get("spot_price", 0.0),
        }
