from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation, TYPE_MAX_PAIN_SHIFT
from app.research_os.perception.regime.regime_feature import RegimeFeature
from app.research_os.perception.regime.base_assessor import BaseRegimeAssessor
from app.research_os.perception.regime.regime_history import RegimeSessionHistory


class VolatilityAssessor(BaseRegimeAssessor):
    """Assesses option chain volatility environment into Stage 1 RegimeFeature."""

    @property
    def assessor_name(self) -> str:
        return "volatility_assessor"

    def assess(
        self,
        snapshot: Dict[str, Any],
        pattern_observations: List[PatternObservation],
        history: RegimeSessionHistory,
    ) -> List[RegimeFeature]:
        ts_utc = int(snapshot.get("timestamp_utc", 0))
        total_ce = snapshot.get("total_ce_oi", 0)
        total_pe = snapshot.get("total_pe_oi", 0)

        supporting_ids = [p.observation_id for p in pattern_observations if p.observation_type == TYPE_MAX_PAIN_SHIFT]
        vol_score = (total_ce + total_pe) / 100000.0

        feat = RegimeFeature(
            feature_id=f"FEAT-VOL-{ts_utc}",
            feature_name="volatility_expansion_score",
            value=round(vol_score, 4),
            confidence=0.88,
            supporting_pattern_ids=supporting_ids,
            timestamp_utc=ts_utc,
        )
        return [feat]
