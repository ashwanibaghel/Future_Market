from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from app.research_os.perception.perception_version import DEFAULT_PERCEPTION_VERSION
from app.research_os.perception.perception_diagnostics import PerceptionDiagnostics


@dataclass(frozen=True)
class PerceptionFrame:
    """
    Requirement 2, 4, & 5 Explainable, Immutable Perception Frame Container.
    Synthesizes perceived market observations across all active perception modules at tick T.
    Guarantees 100% deterministic reproducibility and complete provenance tracking.
    """
    frame_id: str
    timestamp: str
    timestamp_utc: int
    symbol: str
    perception_version: str
    feature_version: str
    replay_version: str
    executed_modules: List[str]
    perceptions: Dict[str, Any]  # Keyed by module_name -> {confidence, evidence, metadata}
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def get_perception(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves perceived observation output for a specific perception module."""
        return self.perceptions.get(module_name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "timestamp": self.timestamp,
            "timestamp_utc": self.timestamp_utc,
            "symbol": self.symbol,
            "perception_version": self.perception_version,
            "feature_version": self.feature_version,
            "replay_version": self.replay_version,
            "executed_modules": self.executed_modules,
            "perceptions": self.perceptions,
            "diagnostics": self.diagnostics,
        }
