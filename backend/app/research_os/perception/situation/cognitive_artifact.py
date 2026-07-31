from dataclasses import dataclass, field
from typing import Dict, Any, List
from app.research_os.perception.perception_version import DEFAULT_PERCEPTION_VERSION
from app.research_os.feature_store.feature_version import DEFAULT_FEATURE_VERSION


@dataclass
class CognitiveArtifact:
    """
    Universal Base Class for all Cognitive Objects in OI Lens.
    Provides standardized provenance, evidence, timestamps, replay references, and confidence handling.
    """
    artifact_id: str
    artifact_type: str
    confidence: float
    evidence: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    parent_artifact_ids: List[str] = field(default_factory=list)
    replay_tick: int = 0
    dataset_manifest_id: str = "UNKNOWN_MANIFEST"
    timestamp: str = ""
    timestamp_utc: int = 0
    feature_version: str = DEFAULT_FEATURE_VERSION
    perception_version: str = DEFAULT_PERCEPTION_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "confidence": round(self.confidence, 4),
            "evidence": self.evidence,
            "attributes": self.attributes,
            "parent_artifact_ids": self.parent_artifact_ids,
            "replay_tick": self.replay_tick,
            "dataset_manifest_id": self.dataset_manifest_id,
            "timestamp": self.timestamp,
            "timestamp_utc": self.timestamp_utc,
            "feature_version": self.feature_version,
            "perception_version": self.perception_version,
        }
