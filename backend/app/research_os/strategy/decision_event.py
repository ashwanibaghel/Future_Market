import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class DecisionEvent:
    """
    Requirement 5 Standardized Immutable Decision Event.
    Canonical output emitted by any strategy plugin or AI reasoning model.
    Enforces frozen immutability post-creation.
    """
    decision_id: str
    strategy_name: str
    strategy_version: str
    session_id: str
    timestamp: str
    timestamp_utc: int
    symbol: str
    spot_price: float
    feature_version: str
    replay_version: str
    signal: str  # BULLISH, BEARISH, NEUTRAL, EXIT
    confidence: float
    reasoning: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "timestamp_utc": self.timestamp_utc,
            "symbol": self.symbol,
            "spot_price": self.spot_price,
            "feature_version": self.feature_version,
            "replay_version": self.replay_version,
            "signal": self.signal,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }
