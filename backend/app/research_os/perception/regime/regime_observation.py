from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from app.research_os.perception.perception_version import DEFAULT_PERCEPTION_VERSION
from app.research_os.feature_store.feature_version import DEFAULT_FEATURE_VERSION

# Regime Dimensions
DIM_TREND = "TREND_STRENGTH"
DIM_VOLATILITY = "VOLATILITY_STATE"
DIM_LIQUIDITY = "LIQUIDITY_CONCENTRATION"
DIM_COMPRESSION = "COMPRESSION_EXPANSION"
DIM_STABILITY = "REGIME_STABILITY"

# Regime State Labels
STATE_STRONG_TREND = "STRONG_TREND"
STATE_WEAK_TREND = "WEAK_TREND"
STATE_NON_TRENDING = "NON_TRENDING"

STATE_COMPRESSED_VOL = "COMPRESSED_VOLATILITY"
STATE_EXPANDING_VOL = "EXPANDING_VOLATILITY"
STATE_HIGH_VOL = "HIGH_VOLATILITY"
STATE_LOW_VOL = "LOW_VOLATILITY"

STATE_CLUSTERED_PINNING = "CLUSTERED_PINNING"
STATE_DISPERSED_LIQUIDITY = "DISPERSED_LIQUIDITY"

STATE_VOLATILITY_SQUEEZE = "VOLATILITY_SQUEEZE"
STATE_ENERGY_RELEASE = "ENERGY_RELEASE"
STATE_EQUILIBRIUM = "EQUILIBRIUM"

STATE_STABLE_REGIME = "STABLE_REGIME"
STATE_REGIME_TRANSITION = "REGIME_TRANSITION_WINDOW"


@dataclass
class RegimeObservation:
    """
    Requirement 2, 4 & 5 Stage 2 Explainable Regime Observation.
    Synthesizes RegimeFeature objects into explainable market-state observations.
    Separates State label from Confidence score independently.
    """
    regime_id: str
    regime_dimension: str
    state_label: str
    confidence: float
    evidence: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    supporting_pattern_ids: List[str] = field(default_factory=list)
    replay_tick: int = 0
    dataset_manifest_id: str = "UNKNOWN_MANIFEST"
    timestamp: str = ""
    timestamp_utc: int = 0
    feature_version: str = DEFAULT_FEATURE_VERSION
    perception_version: str = DEFAULT_PERCEPTION_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regime_id": self.regime_id,
            "regime_dimension": self.regime_dimension,
            "state_label": self.state_label,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
            "attributes": self.attributes,
            "supporting_pattern_ids": self.supporting_pattern_ids,
            "replay_tick": self.replay_tick,
            "dataset_manifest_id": self.dataset_manifest_id,
            "timestamp": self.timestamp,
            "timestamp_utc": self.timestamp_utc,
            "feature_version": self.feature_version,
            "perception_version": self.perception_version,
        }
