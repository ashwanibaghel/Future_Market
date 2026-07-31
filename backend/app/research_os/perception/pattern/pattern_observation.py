from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from app.research_os.perception.perception_version import DEFAULT_PERCEPTION_VERSION
from app.research_os.feature_store.feature_version import DEFAULT_FEATURE_VERSION

# Pattern Lifecycle States
STATE_DETECTED = "DETECTED"
STATE_ACTIVE = "ACTIVE"
STATE_STRENGTHENING = "STRENGTHENING"
STATE_WEAKENING = "WEAKENING"
STATE_EXPIRED = "EXPIRED"

# Pattern Observation Types
TYPE_OPTION_WALL = "OPTION_WALL_CONCENTRATION"
TYPE_STRIKE_CLUSTER = "STRIKE_CLUSTERING"
TYPE_MAX_PAIN_SHIFT = "MAX_PAIN_SHIFT"
TYPE_OI_MOVEMENT = "OI_MOVEMENT"
TYPE_PRICE_OI_RELATION = "PRICE_OI_RELATION"


@dataclass
class PatternObservation:
    """
    Requirement 3 & 7 Strongly-Typed Explainable Pattern Observation.
    Contains raw structural observations without subjective trading interpretations.
    """
    observation_id: str
    observation_type: str
    lifecycle_state: str  # DETECTED, ACTIVE, STRENGTHENING, WEAKENING, EXPIRED
    confidence: float
    evidence: str  # Human-readable + AI-parseable explanation string
    attributes: Dict[str, Any] = field(default_factory=dict)  # Contains raw_observations and derived_classifications
    timestamp: str = ""
    timestamp_utc: int = 0
    feature_version: str = DEFAULT_FEATURE_VERSION
    perception_version: str = DEFAULT_PERCEPTION_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "observation_type": self.observation_type,
            "lifecycle_state": self.lifecycle_state,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
            "attributes": self.attributes,
            "timestamp": self.timestamp,
            "timestamp_utc": self.timestamp_utc,
            "feature_version": self.feature_version,
            "perception_version": self.perception_version,
        }
