from dataclasses import dataclass, field
from typing import Dict, Any, List
from app.research_os.perception.situation.cognitive_artifact import CognitiveArtifact

# Macro Situation Labels
SITUATION_VOLATILITY_EXPANSION_TREND = "VOLATILITY_EXPANSION_TREND"
SITUATION_PINNED_CONSOLIDATION = "PINNED_CONSOLIDATION"
SITUATION_SQUEEZE_BEFORE_RELEASE = "SQUEEZE_BEFORE_RELEASE"
SITUATION_DISPERSED_TRANSITION = "DISPERSED_TRANSITION"

# Risk Environment Labels
RISK_ELEVATED_TAIL_RISK = "ELEVATED_TAIL_RISK"
RISK_STABLE_LIQUIDITY_ZONE = "STABLE_LIQUIDITY_ZONE"
RISK_TRANSITION_RISK = "TRANSITION_RISK"

# Conflict Status
CONFLICT_ALIGNED = "ALIGNED"
CONFLICT_MILD_CONFLICT = "MILD_CONFLICT"
CONFLICT_SEVERE_DIVERGENCE = "SEVERE_DIVERGENCE"


@dataclass
class SituationAssessment(CognitiveArtifact):
    """
    Subclass of CognitiveArtifact representing a unified Situation Assessment.
    Synthesizes multiple RegimeObservations and PatternObservations into a coherent description
    of the market situation.
    """
    macro_situation_label: str = SITUATION_PINNED_CONSOLIDATION
    risk_environment_label: str = RISK_STABLE_LIQUIDITY_ZONE
    conflict_status: str = CONFLICT_ALIGNED
    supporting_regime_ids: List[str] = field(default_factory=list)
    supporting_pattern_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "macro_situation_label": self.macro_situation_label,
            "risk_environment_label": self.risk_environment_label,
            "conflict_status": self.conflict_status,
            "supporting_regime_ids": self.supporting_regime_ids,
            "supporting_pattern_ids": self.supporting_pattern_ids,
        })
        return d
