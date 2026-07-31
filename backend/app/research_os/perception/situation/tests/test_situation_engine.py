from app.research_os.perception.situation.cognitive_artifact import CognitiveArtifact
from app.research_os.perception.situation.situation_assessment import SituationAssessment
from app.research_os.perception.situation.synthesizers.macro_state import MacroStateSynthesizer
from app.research_os.perception.situation.situation_engine import SituationAssessmentModule


def test_cognitive_artifact_inheritance():
    assessment = SituationAssessment(
        artifact_id="ART-100",
        artifact_type="SITUATION_ASSESSMENT",
        confidence=0.92,
        evidence="Sample evidence string",
        macro_situation_label="VOLATILITY_EXPANSION_TREND",
        risk_environment_label="STABLE_LIQUIDITY_ZONE",
        conflict_status="ALIGNED",
    )

    assert isinstance(assessment, CognitiveArtifact)
    assert assessment.artifact_id == "ART-100"
    d = assessment.to_dict()
    assert d["macro_situation_label"] == "VOLATILITY_EXPANSION_TREND"
    assert d["confidence"] == 0.92


def test_macro_state_synthesizer():
    synth = MacroStateSynthesizer()
    snapshot = {"timestamp_utc": 1614570300}
    result = synth.synthesize(snapshot, [], [])
    assert result["macro_situation_label"] == "PINNED_CONSOLIDATION"


def test_situation_assessment_module_process():
    module = SituationAssessmentModule()
    snapshot = {
        "timestamp_utc": 1614570300,
        "snapshot_index": 5,
        "dataset_manifest_id": "CANONICAL-NIFTY-2021-03",
    }

    prior_perceptions = {
        "pattern_recognition": {"metadata": {"observations": []}},
        "market_regime": {"metadata": {"observations": []}},
    }

    result = module.process_snapshot(snapshot, prior_perceptions)
    assert result["confidence"] > 0.0
    meta = result["metadata"]
    assert meta["macro_situation_label"] == "PINNED_CONSOLIDATION"
    assert meta["assessment"]["artifact_type"] == "SITUATION_ASSESSMENT"


if __name__ == "__main__":
    test_cognitive_artifact_inheritance()
    test_macro_state_synthesizer()
    test_situation_assessment_module_process()
    print("\nALL SITUATION ENGINE UNIT TESTS PASSED SUCCESSFULLY!")
