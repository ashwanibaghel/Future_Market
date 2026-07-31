import logging
from typing import Dict, Any, List, Optional
from app.research_os.perception.base_perception import BasePerceptionModule
from app.research_os.perception.pattern.pattern_observation import PatternObservation
from app.research_os.perception.pattern.pattern_history import PatternSessionHistory
from app.research_os.perception.pattern.base_detector import BasePatternDetector
from app.research_os.perception.pattern.detectors.option_walls import OptionWallsDetector
from app.research_os.perception.pattern.detectors.strike_cluster import StrikeClusterDetector
from app.research_os.perception.pattern.detectors.max_pain import MaxPainDetector
from app.research_os.perception.pattern.detectors.oi_movement import OIMovementDetector
from app.research_os.perception.pattern.detectors.price_oi_relationship import PriceOIRelationshipDetector

logger = logging.getLogger("research_os.perception.pattern.engine")


class PatternRecognitionModule(BasePerceptionModule):
    """
    Sprint 7B Pattern Recognition Perception Engine.
    Subclasses BasePerceptionModule established in Sprint 7A.
    Orchestrates independent BasePatternDetector plugins, tracks pattern lifecycles in PatternSessionHistory,
    and returns explainable PatternObservation collections.
    MUST NEVER emit trade signals (BUY/SELL).
    """

    def __init__(self, detectors: Optional[List[BasePatternDetector]] = None):
        self.detectors = detectors or [
            OptionWallsDetector(),
            StrikeClusterDetector(),
            MaxPainDetector(),
            OIMovementDetector(),
            PriceOIRelationshipDetector(),
        ]
        self.history = PatternSessionHistory()

    @property
    def module_name(self) -> str:
        return "pattern_recognition"

    @property
    def module_version(self) -> str:
        return "1.0.0"

    @property
    def required_features(self) -> List[str]:
        return ["spot_price", "atm_strike", "pcr_volume", "oi_change_ce", "oi_change_pe"]

    def initialize(self, config: Optional[Dict[str, Any]] = None):
        self.history.clear()

    def process_snapshot(self, snapshot: Dict[str, Any], prior_perceptions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes active sub-detectors and returns explainable PatternObservation payload.
        """
        all_observations: List[PatternObservation] = []

        for detector in self.detectors:
            try:
                obs_list = detector.detect(snapshot, self.history)
                for obs in obs_list:
                    all_observations.append(obs)
                    self.history.add_observation(obs)
            except Exception as exc:
                logger.error("Pattern Sub-Detector '%s' failed: %s", detector.detector_name, str(exc))

        # Synthesize combined evidence explanation string for downstream AI models
        evidences = [obs.evidence for obs in all_observations]
        combined_evidence = " | ".join(evidences)

        return {
            "confidence": 0.93,
            "evidence": combined_evidence,
            "metadata": {
                "total_observations": len(all_observations),
                "active_pattern_ids": [obs.observation_id for obs in all_observations],
                "observations": [obs.to_dict() for obs in all_observations],
            },
        }
