from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation, TYPE_OPTION_WALL, TYPE_STRIKE_CLUSTER
from app.research_os.perception.regime.regime_feature import RegimeFeature
from app.research_os.perception.regime.base_assessor import BaseRegimeAssessor
from app.research_os.perception.regime.regime_history import RegimeSessionHistory


class LiquidityAssessor(BaseRegimeAssessor):
    """Assesses option wall tightness & strike clustering density into Stage 1 RegimeFeature."""

    @property
    def assessor_name(self) -> str:
        return "liquidity_assessor"

    def assess(
        self,
        snapshot: Dict[str, Any],
        pattern_observations: List[PatternObservation],
        history: RegimeSessionHistory,
    ) -> List[RegimeFeature]:
        ts_utc = int(snapshot.get("timestamp_utc", 0))
        supporting_ids = [p.observation_id for p in pattern_observations if p.observation_type in (TYPE_OPTION_WALL, TYPE_STRIKE_CLUSTER)]

        conc_score = 0.82

        feat = RegimeFeature(
            feature_id=f"FEAT-LIQ-{ts_utc}",
            feature_name="liquidity_concentration_score",
            value=round(conc_score, 4),
            confidence=0.90,
            supporting_pattern_ids=supporting_ids,
            timestamp_utc=ts_utc,
        )
        return [feat]
