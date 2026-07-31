import logging
from typing import Dict, Any, List, Optional
from app.research_os.perception.base_perception import BasePerceptionModule
from app.research_os.perception.pattern.pattern_observation import PatternObservation
from app.research_os.perception.regime.regime_observation import RegimeObservation
from app.research_os.perception.situation.situation_assessment import SituationAssessment
from app.research_os.perception.situation.base_synthesizer import BaseSituationSynthesizer
from app.research_os.perception.situation.synthesizers.macro_state import MacroStateSynthesizer
from app.research_os.perception.situation.synthesizers.risk_environment import RiskEnvironmentSynthesizer
from app.research_os.perception.situation.synthesizers.conflict_resolver import ConflictResolver

logger = logging.getLogger("research_os.perception.situation.engine")


class SituationAssessmentModule(BasePerceptionModule):
    """
    Sprint 7D Situation Assessment Perception Engine.
    Subclasses BasePerceptionModule established in Sprint 7A.
    Declares dependency on ['pattern_recognition', 'market_regime'].
    Synthesizes pattern and regime observations into a unified CognitiveArtifact subclass (SituationAssessment).
    MUST NEVER emit trade signals (BUY/SELL).
    """

    def __init__(self, synthesizers: Optional[List[BaseSituationSynthesizer]] = None):
        self.synthesizers = synthesizers or [
            MacroStateSynthesizer(),
            RiskEnvironmentSynthesizer(),
            ConflictResolver(),
        ]

    @property
    def module_name(self) -> str:
        return "situation_assessment"

    @property
    def module_version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> List[str]:
        # Requirement: Topological dependency resolution
        return ["pattern_recognition", "market_regime"]

    def process_snapshot(self, snapshot: Dict[str, Any], prior_perceptions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes synthesizers and returns explainable SituationAssessment object dictionary.
        """
        ts = str(snapshot.get("replay_timestamp", snapshot.get("timestamp", "")))
        ts_utc = int(snapshot.get("timestamp_utc", 0))
        replay_tick = int(snapshot.get("snapshot_index", 0))
        manifest_id = str(snapshot.get("dataset_manifest_id", "CANONICAL-NIFTY-2021-03"))

        # Extract PatternObservations
        pattern_data = prior_perceptions.get("pattern_recognition", {}).get("metadata", {}).get("observations", [])
        pattern_observations = [
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
            for p in pattern_data if isinstance(p, dict)
        ]

        # Extract RegimeObservations
        regime_data = prior_perceptions.get("market_regime", {}).get("metadata", {}).get("observations", [])
        regime_observations = [
            RegimeObservation(
                regime_id=r.get("regime_id", ""),
                regime_dimension=r.get("regime_dimension", ""),
                state_label=r.get("state_label", ""),
                confidence=r.get("confidence", 1.0),
                evidence=r.get("evidence", ""),
                attributes=r.get("attributes", {}),
                supporting_pattern_ids=r.get("supporting_pattern_ids", []),
                replay_tick=r.get("replay_tick", replay_tick),
                dataset_manifest_id=r.get("dataset_manifest_id", manifest_id),
                timestamp=r.get("timestamp", ts),
                timestamp_utc=r.get("timestamp_utc", ts_utc),
            )
            for r in regime_data if isinstance(r, dict)
        ]

        # Run synthesizers
        synth_results = {}
        for synth in self.synthesizers:
            try:
                res = synth.synthesize(snapshot, pattern_observations, regime_observations)
                synth_results[synth.synthesizer_name] = res
            except Exception as exc:
                logger.error("Synthesizer '%s' failed: %s", synth.synthesizer_name, str(exc))

        macro_res = synth_results.get("macro_state", {})
        risk_res = synth_results.get("risk_environment", {})
        conflict_res = synth_results.get("conflict_resolver", {})

        combined_evidence = f"{macro_res.get('evidence', '')} | {risk_res.get('evidence', '')} | {conflict_res.get('evidence', '')}"

        # Requirement: Inherits from CognitiveArtifact
        assessment = SituationAssessment(
            artifact_id=f"ART-SITUATION-{ts_utc}",
            artifact_type="SITUATION_ASSESSMENT",
            confidence=round((macro_res.get("confidence", 0.9) + risk_res.get("confidence", 0.9)) / 2.0, 4),
            evidence=combined_evidence,
            attributes={"synthesizer_details": synth_results},
            parent_artifact_ids=[r.regime_id for r in regime_observations] + [p.observation_id for p in pattern_observations],
            replay_tick=replay_tick,
            dataset_manifest_id=manifest_id,
            timestamp=ts,
            timestamp_utc=ts_utc,
            macro_situation_label=macro_res.get("macro_situation_label", "PINNED_CONSOLIDATION"),
            risk_environment_label=risk_res.get("risk_environment_label", "STABLE_LIQUIDITY_ZONE"),
            conflict_status=conflict_res.get("conflict_status", "ALIGNED"),
            supporting_regime_ids=[r.regime_id for r in regime_observations],
            supporting_pattern_ids=[p.observation_id for p in pattern_observations],
        )

        return {
            "confidence": assessment.confidence,
            "evidence": assessment.evidence,
            "metadata": {
                "macro_situation_label": assessment.macro_situation_label,
                "risk_environment_label": assessment.risk_environment_label,
                "conflict_status": assessment.conflict_status,
                "assessment": assessment.to_dict(),
            },
        }
