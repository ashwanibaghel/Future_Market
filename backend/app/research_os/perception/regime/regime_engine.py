import logging
from typing import Dict, Any, List, Optional
from app.research_os.perception.base_perception import BasePerceptionModule
from app.research_os.perception.pattern.pattern_observation import PatternObservation
from app.research_os.perception.regime.regime_feature import RegimeFeature
from app.research_os.perception.regime.regime_observation import (
    RegimeObservation,
    DIM_TREND,
    DIM_VOLATILITY,
    DIM_LIQUIDITY,
    DIM_COMPRESSION,
    DIM_STABILITY,
    STATE_STRONG_TREND,
    STATE_WEAK_TREND,
    STATE_NON_TRENDING,
    STATE_HIGH_VOL,
    STATE_LOW_VOL,
    STATE_CLUSTERED_PINNING,
    STATE_VOLATILITY_SQUEEZE,
    STATE_STABLE_REGIME,
)
from app.research_os.perception.regime.regime_history import RegimeSessionHistory
from app.research_os.perception.regime.base_assessor import BaseRegimeAssessor
from app.research_os.perception.regime.assessors.trend_assessor import TrendAssessor
from app.research_os.perception.regime.assessors.volatility_assessor import VolatilityAssessor
from app.research_os.perception.regime.assessors.liquidity_assessor import LiquidityAssessor
from app.research_os.perception.regime.assessors.compression_analyzer import CompressionAnalyzer
from app.research_os.perception.regime.assessors.stability_assessor import StabilityAssessor

logger = logging.getLogger("research_os.perception.regime.engine")


class MarketRegimeModule(BasePerceptionModule):
    """
    Sprint 7C Market Regime Detection Engine.
    Subclasses BasePerceptionModule established in Sprint 7A.
    Declares dependency on 'pattern_recognition'.
    Executes Two-Stage Pipeline:
      Stage 1: BaseRegimeAssessor plugins -> RegimeFeature[]
      Stage 2: Feature Synthesizer -> RegimeObservation[]
    Maintains RegimeSessionHistory and emits explainable observations into PerceptionFrame.
    MUST NEVER emit trade signals (BUY/SELL).
    """

    def __init__(self, assessors: Optional[List[BaseRegimeAssessor]] = None):
        self.assessors = assessors or [
            TrendAssessor(),
            VolatilityAssessor(),
            LiquidityAssessor(),
            CompressionAnalyzer(),
            StabilityAssessor(),
        ]
        self.history = RegimeSessionHistory()

    @property
    def module_name(self) -> str:
        return "market_regime"

    @property
    def module_version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> List[str]:
        # Requirement 3 from Sprint 7A & Sprint 7C: Topological dependency resolution
        return ["pattern_recognition"]

    def initialize(self, config: Optional[Dict[str, Any]] = None):
        self.history.clear()

    def process_snapshot(self, snapshot: Dict[str, Any], prior_perceptions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes Two-Stage Regime Pipeline.
        """
        ts = str(snapshot.get("replay_timestamp", snapshot.get("timestamp", "")))
        ts_utc = int(snapshot.get("timestamp_utc", 0))
        replay_tick = int(snapshot.get("snapshot_index", 0))
        manifest_id = str(snapshot.get("dataset_manifest_id", "CANONICAL-NIFTY-2021-03"))

        # Extract PatternObservations from prior 'pattern_recognition' perception frame
        pattern_data = prior_perceptions.get("pattern_recognition", {}).get("metadata", {}).get("observations", [])
        pattern_observations: List[PatternObservation] = []
        for p in pattern_data:
            if isinstance(p, dict):
                pattern_observations.append(
                    PatternObservation(
                        observation_id=p.get("observation_id", ""),
                        observation_type=p.get("observation_type", ""),
                        lifecycle_state=p.get("lifecycle_state", "ACTIVE"),
                        confidence=p.get("confidence", 1.0),
                        evidence=p.get("evidence", ""),
                        attributes=p.get("attributes", {}),
                        timestamp=p.get("timestamp", ts),
                        timestamp_utc=p.get("timestamp_utc", ts_utc),
                    )
                )

        # STAGE 1: Execute Assessors & Analyzers to generate RegimeFeature collection
        regime_features: List[RegimeFeature] = []
        for assessor in self.assessors:
            try:
                feats = assessor.assess(snapshot, pattern_observations, self.history)
                regime_features.extend(feats)
            except Exception as exc:
                logger.error("Regime Assessor '%s' failed: %s", assessor.assessor_name, str(exc))

        # STAGE 2: Synthesize RegimeFeature collection into explainable RegimeObservation collection
        regime_observations: List[RegimeObservation] = []
        all_supporting_ids = [p.observation_id for p in pattern_observations]

        # 1. Trend Strength Dimension
        trend_feat = next((f for f in regime_features if f.feature_name == "trend_persistence"), None)
        trend_val = trend_feat.value if trend_feat else 0.0
        trend_state = STATE_STRONG_TREND if trend_val > 0.3 else (STATE_WEAK_TREND if trend_val > 0.1 else STATE_NON_TRENDING)
        # Requirement 5: Independent State vs Confidence separation
        trend_conf = 0.58 if trend_state == STATE_STRONG_TREND else 0.85

        obs_trend = RegimeObservation(
            regime_id=f"REG-TREND-{ts_utc}",
            regime_dimension=DIM_TREND,
            state_label=trend_state,
            confidence=trend_conf,
            evidence=f"Market Trend Strength assessed as '{trend_state}' based on trend persistence score {trend_val:.4f}.",
            attributes={"raw_features": {"trend_persistence": trend_val}},
            supporting_pattern_ids=all_supporting_ids,
            replay_tick=replay_tick,
            dataset_manifest_id=manifest_id,
            timestamp=ts,
            timestamp_utc=ts_utc,
        )
        regime_observations.append(obs_trend)
        self.history.add_observation(obs_trend)

        # 2. Volatility State Dimension
        vol_feat = next((f for f in regime_features if f.feature_name == "volatility_expansion_score"), None)
        vol_val = vol_feat.value if vol_feat else 0.0
        vol_state = STATE_HIGH_VOL if vol_val > 1.0 else STATE_LOW_VOL

        obs_vol = RegimeObservation(
            regime_id=f"REG-VOL-{ts_utc}",
            regime_dimension=DIM_VOLATILITY,
            state_label=vol_state,
            confidence=0.88,
            evidence=f"Volatility State assessed as '{vol_state}' based on volatility expansion score {vol_val:.4f}.",
            attributes={"raw_features": {"volatility_expansion_score": vol_val}},
            supporting_pattern_ids=all_supporting_ids,
            replay_tick=replay_tick,
            dataset_manifest_id=manifest_id,
            timestamp=ts,
            timestamp_utc=ts_utc,
        )
        regime_observations.append(obs_vol)
        self.history.add_observation(obs_vol)

        evidences = [obs.evidence for obs in regime_observations]
        combined_evidence = " | ".join(evidences)

        return {
            "confidence": 0.91,
            "evidence": combined_evidence,
            "metadata": {
                "total_regime_observations": len(regime_observations),
                "regime_states": {obs.regime_dimension: obs.state_label for obs in regime_observations},
                "observations": [obs.to_dict() for obs in regime_observations],
                "stage1_features": [f.__dict__ for f in regime_features],
                "history_summary": {
                    "current_regime": self.history.current_regime,
                    "previous_regime": self.history.previous_regime,
                    "duration_ticks": self.history.duration_ticks,
                    "transition_count": self.history.transition_count,
                },
            },
        }
