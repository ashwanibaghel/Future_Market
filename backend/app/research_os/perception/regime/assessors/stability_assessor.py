from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation
from app.research_os.perception.regime.regime_feature import RegimeFeature
from app.research_os.perception.regime.base_assessor import BaseRegimeAssessor
from app.research_os.perception.regime.regime_history import RegimeSessionHistory


class StabilityAssessor(BaseRegimeAssessor):
    """Assesses regime stability evolution and transition probability into Stage 1 RegimeFeature."""

    @property
    def assessor_name(self) -> str:
        return "stability_assessor"

    def assess(
        self,
        snapshot: Dict[str, Any],
        pattern_observations: List[PatternObservation],
        history: RegimeSessionHistory,
    ) -> List[RegimeFeature]:
        ts_utc = int(snapshot.get("timestamp_utc", 0))
        dur = history.duration_ticks
        stability_score = min(1.0, dur / 10.0)

        feat = RegimeFeature(
            feature_id=f"FEAT-STAB-{ts_utc}",
            feature_name="stability_score",
            value=round(stability_score, 4),
            confidence=0.91,
            supporting_pattern_ids=[p.observation_id for p in pattern_observations],
            timestamp_utc=ts_utc,
        )
        return [feat]
