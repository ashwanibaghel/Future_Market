from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation, TYPE_PRICE_OI_RELATION
from app.research_os.perception.regime.regime_observation import RegimeObservation
from app.research_os.perception.situation.situation_assessment import (
    CONFLICT_ALIGNED,
    CONFLICT_MILD_CONFLICT,
    CONFLICT_SEVERE_DIVERGENCE,
)
from app.research_os.perception.situation.base_synthesizer import BaseSituationSynthesizer


class ConflictResolver(BaseSituationSynthesizer):
    """Evaluates alignment vs divergence across price movement and option wall shifts."""

    @property
    def synthesizer_name(self) -> str:
        return "conflict_resolver"

    def synthesize(
        self,
        snapshot: Dict[str, Any],
        pattern_observations: List[PatternObservation],
        regime_observations: List[RegimeObservation],
    ) -> Dict[str, Any]:
        p_diverge = any(
            p.attributes.get("derived_classifications", {}).get("is_divergence_trap", False)
            for p in pattern_observations
            if p.observation_type == TYPE_PRICE_OI_RELATION
        )

        if p_diverge:
            status = CONFLICT_MILD_CONFLICT
            evidence = f"Conflict Status resolved as '{status}' due to short covering divergence trap."
        else:
            status = CONFLICT_ALIGNED
            evidence = f"Conflict Status resolved as '{status}' with aligned price and OI flows."

        return {
            "conflict_status": status,
            "evidence": evidence,
            "confidence": 0.92,
        }
