from app.research_os.perception.pattern.pattern_observation import PatternObservation, TYPE_PRICE_OI_RELATION
from app.research_os.perception.regime.regime_feature import RegimeFeature
from app.research_os.perception.regime.regime_observation import RegimeObservation, DIM_TREND, STATE_STRONG_TREND
from app.research_os.perception.regime.regime_history import RegimeSessionHistory
from app.research_os.perception.regime.assessors.trend_assessor import TrendAssessor
from app.research_os.perception.regime.regime_engine import MarketRegimeModule


def test_trend_assessor():
    history = RegimeSessionHistory()
    assessor = TrendAssessor()

    snapshot = {"pcr_volume": 1.45, "timestamp_utc": 1614570300}
    patterns = [
        PatternObservation(
            observation_id="OBS-P1",
            observation_type=TYPE_PRICE_OI_RELATION,
            lifecycle_state="ACTIVE",
            confidence=0.9,
            evidence="Sample",
        )
    ]

    features = assessor.assess(snapshot, patterns, history)
    assert len(features) == 1
    feat = features[0]
    assert feat.feature_name == "trend_persistence"
    assert feat.value == 0.45
    assert "OBS-P1" in feat.supporting_pattern_ids


def test_two_stage_regime_pipeline_and_state_confidence_separation():
    module = MarketRegimeModule()
    module.initialize()

    snapshot = {
        "pcr_volume": 1.45,
        "total_ce_oi": 60000,
        "total_pe_oi": 50000,
        "snapshot_index": 12,
        "timestamp_utc": 1614570300,
        "dataset_manifest_id": "CANONICAL-NIFTY-2021-03",
    }

    prior_perceptions = {
        "pattern_recognition": {
            "metadata": {
                "observations": [
                    {
                        "observation_id": "OBS-P1",
                        "observation_type": TYPE_PRICE_OI_RELATION,
                        "lifecycle_state": "ACTIVE",
                        "confidence": 0.9,
                        "evidence": "Price rising",
                        "attributes": {},
                        "timestamp_utc": 1614570300,
                    }
                ]
            }
        }
    }

    result = module.process_snapshot(snapshot, prior_perceptions)

    assert result["confidence"] == 0.91
    meta = result["metadata"]
    assert meta["total_regime_observations"] == 2
    assert len(meta["stage1_features"]) >= 5

    obs_list = meta["observations"]
    trend_obs = next(o for o in obs_list if o["regime_dimension"] == DIM_TREND)

    # Requirement 5: Verify independent State vs Confidence separation
    assert trend_obs["state_label"] == STATE_STRONG_TREND
    assert trend_obs["confidence"] == 0.58
    assert "OBS-P1" in trend_obs["supporting_pattern_ids"]
    assert trend_obs["dataset_manifest_id"] == "CANONICAL-NIFTY-2021-03"


def test_regime_session_history_tracking():
    history = RegimeSessionHistory()

    obs1 = RegimeObservation(
        regime_id="REG-1",
        regime_dimension=DIM_TREND,
        state_label="STRONG_TREND",
        confidence=0.58,
        evidence="Obs 1",
    )
    obs2 = RegimeObservation(
        regime_id="REG-2",
        regime_dimension=DIM_TREND,
        state_label="STRONG_TREND",
        confidence=0.58,
        evidence="Obs 2",
    )
    obs3 = RegimeObservation(
        regime_id="REG-3",
        regime_dimension=DIM_TREND,
        state_label="NON_TRENDING",
        confidence=0.85,
        evidence="Obs 3",
    )

    history.add_observation(obs1)
    assert history.current_regime == "STRONG_TREND"
    assert history.duration_ticks == 1

    history.add_observation(obs2)
    assert history.current_regime == "STRONG_TREND"
    assert history.duration_ticks == 2

    history.add_observation(obs3)
    assert history.current_regime == "NON_TRENDING"
    assert history.previous_regime == "STRONG_TREND"
    assert history.duration_ticks == 1
    assert history.transition_count == 1


if __name__ == "__main__":
    test_trend_assessor()
    test_two_stage_regime_pipeline_and_state_confidence_separation()
    test_regime_session_history_tracking()
    print("\nALL REGIME ENGINE UNIT TESTS PASSED SUCCESSFULLY!")
