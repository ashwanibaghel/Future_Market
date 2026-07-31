from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from app.research_os.feature_store.feature_version import DEFAULT_FEATURE_VERSION
from app.research_os.replay.replay_version import DEFAULT_REPLAY_VERSION


@dataclass
class ReplayConfig:
    """
    Requirement 2 Encapsulated Replay Configuration Object.
    Contains all parameters required for a deterministic, reproducible replay session.
    """
    symbol: str = "NIFTY"
    start_date: str = "2021-01-01"
    end_date: str = "2021-12-31"
    feature_version: str = DEFAULT_FEATURE_VERSION
    replay_version: str = DEFAULT_REPLAY_VERSION
    replay_speed: float = 0.0  # 0.0 = Maximum throughput (backtest mode), > 0.0 = Real-time delay seconds
    session_options: Dict[str, Any] = field(default_factory=dict)
    strategy_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol.upper(),
            "start_date": self.start_date,
            "end_date": self.end_date,
            "feature_version": self.feature_version,
            "replay_version": self.replay_version,
            "replay_speed": self.replay_speed,
            "session_options": self.session_options,
            "strategy_config": self.strategy_config,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReplayConfig":
        return cls(
            symbol=d.get("symbol", "NIFTY"),
            start_date=d.get("start_date", "2021-01-01"),
            end_date=d.get("end_date", "2021-12-31"),
            feature_version=d.get("feature_version", DEFAULT_FEATURE_VERSION),
            replay_version=d.get("replay_version", DEFAULT_REPLAY_VERSION),
            replay_speed=float(d.get("replay_speed", 0.0)),
            session_options=d.get("session_options", {}),
            strategy_config=d.get("strategy_config", {}),
        )
