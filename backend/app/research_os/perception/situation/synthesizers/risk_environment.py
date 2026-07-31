from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation
from app.research_os.perception.regime.regime_observation import RegimeObservation, DIM_VOLATILITY, STATE_HIGH_VOL
from app.research_os.perception.situation.situation_assessment import (
    RISK_ELEVATED_TAIL_RISK,
    RISK_STABLE_LIQUIDITY_ZONE,
)
from app.research_os.perception.situation.base_synthesizer import BaseSituationSynthesizer


class RiskEnvironmentSynthesizer(BaseSituationSynthesizer):
    """Evaluates volatility & liquidity concentration for risk environment warnings."""

    @property
    def synthesizer_name(self) -> str:
        return "risk_environment"

    def synthesize(
        self,
        snapshot: Dict[str, Any],
        pattern_observations: List[PatternObservation],
        regime_observations: List[RegimeObservation],
    ) -> Dict[str, Any]:
        vol_obs = next((r for r in regime_observations if r.regime_dimension == DIM_VOLATILITY), None)
        vol_state = vol_obs.state_label if vol_obs else "LOW_VOLATILITY"

        if vol_state == STATE_HIGH_VOL:
            label = RISK_ELEVATED_TAIL_RISK
            evidence = f"Risk Environment assessed as '{label}' due to elevated option volatility."
        else:
            label = RISK_STABLE_LIQUIDITY_ZONE
            evidence = f"Risk Environment assessed as '{label}' with normal option liquidity bounds."

        return {
            "risk_environment_label": label,
            "evidence": evidence,
            "confidence": 0.90,
        }
