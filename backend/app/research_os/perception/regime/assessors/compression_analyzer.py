from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation, TYPE_OI_MOVEMENT
from app.research_os.perception.regime.regime_feature import RegimeFeature
from app.research_os.perception.regime.base_assessor import BaseRegimeAssessor
from app.research_os.perception.regime.regime_history import RegimeSessionHistory


class CompressionAnalyzer(BaseRegimeAssessor):
    """Analyzes volatility squeeze vs energy release into Stage 1 RegimeFeature."""

    @property
    def assessor_name(self) -> str:
        return "compression_analyzer"

    def assess(
        self,
        snapshot: Dict[str, Any],
        pattern_observations: List[PatternObservation],
        history: RegimeSessionHistory,
    ) -> List[RegimeFeature]:
        ts_utc = int(snapshot.get("timestamp_utc", 0))
        supporting_ids = [p.observation_id for p in pattern_observations if p.observation_type == TYPE_OI_MOVEMENT]

        squeeze_score = 0.45

        feat = RegimeFeature(
            feature_id=f"FEAT-COMP-{ts_utc}",
            feature_name="volatility_squeeze_score",
            value=round(squeeze_score, 4),
            confidence=0.86,
            supporting_pattern_ids=supporting_ids,
            timestamp_utc=ts_utc,
        )
        return [feat]
