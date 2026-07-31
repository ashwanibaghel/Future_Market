from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class StrategyContext:
    """
    Requirement 3 Strategy Context.
    Provides strategies with snapshot data, feature values, session metadata, configuration,
    and runtime state without exposing Replay Engine internals.
    """
    snapshot: Dict[str, Any]
    session_id: str
    symbol: str
    timestamp: str
    timestamp_utc: int
    spot_price: float
    feature_version: str
    replay_version: str
    config: Dict[str, Any] = field(default_factory=dict)
    state: Dict[str, Any] = field(default_factory=dict)  # Isolated runtime state

    def get_feature(self, name: str, default: Any = None) -> Any:
        """Helper to extract a specific feature value safely."""
        return self.snapshot.get(name, default)

    @classmethod
    def from_enriched_event(cls, event: Dict[str, Any], config: Optional[Dict[str, Any]] = None, state: Optional[Dict[str, Any]] = None) -> "StrategyContext":
        return cls(
            snapshot=event,
            session_id=str(event.get("session_id", "SESS-UNKNOWN")),
            symbol=str(event.get("symbol", "NIFTY")).upper(),
            timestamp=str(event.get("replay_timestamp", event.get("timestamp", ""))),
            timestamp_utc=int(event.get("timestamp_utc", 0)),
            spot_price=float(event.get("spot_price", 0.0)),
            feature_version=str(event.get("feature_version", "F-v1.0.0")),
            replay_version=str(event.get("replay_version", "R-v1.0.0")),
            config=config or {},
            state=state if state is not None else {},
        )
