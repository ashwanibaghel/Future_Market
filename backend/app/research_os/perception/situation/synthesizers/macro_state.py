from typing import Dict, Any, List
from app.research_os.perception.pattern.pattern_observation import PatternObservation
from app.research_os.perception.regime.regime_observation import RegimeObservation, DIM_TREND, DIM_VOLATILITY, STATE_STRONG_TREND, STATE_HIGH_VOL
from app.research_os.perception.situation.situation_assessment import (
    SITUATION_VOLATILITY_EXPANSION_TREND,
    SITUATION_PINNED_CONSOLIDATION,
    SITUATION_SQUEEZE_BEFORE_RELEASE,
)
from app.research_os.perception.situation.base_synthesizer import BaseSituationSynthesizer


class MacroStateSynthesizer(BaseSituationSynthesizer):
    """Synthesizes Trend Strength and Volatility State into overall macro situation."""

    @property
    def synthesizer_name(self) -> str:
        return "macro_state"

    def synthesize(
        self,
        snapshot: Dict[str, Any],
        pattern_observations: List[PatternObservation],
        regime_observations: List[RegimeObservation],
    ) -> Dict[str, Any]:
        trend_obs = next((r for r in regime_observations if r.regime_dimension == DIM_TREND), None)
        vol_obs = next((r for r in regime_observations if r.regime_dimension == DIM_VOLATILITY), None)

        trend_state = trend_obs.state_label if trend_obs else "NON_TRENDING"
        vol_state = vol_obs.state_label if vol_obs else "LOW_VOLATILITY"

        if trend_state == STATE_STRONG_TREND and vol_state == STATE_HIGH_VOL:
            label = SITUATION_VOLATILITY_EXPANSION_TREND
            evidence = f"Macro Situation assessed as '{label}' due to aligned Strong Trend and High Volatility."
        elif vol_state == "COMPRESSED_VOLATILITY":
            label = SITUATION_SQUEEZE_BEFORE_RELEASE
            evidence = f"Macro Situation assessed as '{label}' due to compressed volatility energy buildup."
        else:
            label = SITUATION_PINNED_CONSOLIDATION
            evidence = f"Macro Situation assessed as '{label}' due to non-trending equilibrium."

        return {
            "macro_situation_label": label,
            "evidence": evidence,
            "confidence": 0.89,
        }
