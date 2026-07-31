from app.research_os.perception.pattern.pattern_observation import (
    PatternObservation,
    TYPE_OPTION_WALL,
    TYPE_PRICE_OI_RELATION,
    STATE_ACTIVE,
)
from app.research_os.perception.pattern.pattern_history import PatternSessionHistory
from app.research_os.perception.pattern.detectors.option_walls import OptionWallsDetector
from app.research_os.perception.pattern.detectors.price_oi_relationship import PriceOIRelationshipDetector
from app.research_os.perception.pattern.pattern_engine import PatternRecognitionModule


def test_option_walls_detector():
    history = PatternSessionHistory()
    detector = OptionWallsDetector()

    snapshot = {
        "spot_price": 14500.0,
        "atm_strike": 14500.0,
        "total_ce_oi": 50000,
        "total_pe_oi": 60000,
        "timestamp_utc": 1614570300,
    }

    obs_list = detector.detect(snapshot, history)
    assert len(obs_list) == 1
    obs = obs_list[0]

    assert obs.observation_type == TYPE_OPTION_WALL
    assert obs.lifecycle_state == STATE_ACTIVE
    assert "Highest Call OI" in obs.evidence

    raw = obs.attributes["raw_observations"]
    assert raw["call_wall_strike"] == 14700.0
    assert raw["put_floor_strike"] == 14300.0


def test_raw_vs_derived_separation():
    history = PatternSessionHistory()
    detector = PriceOIRelationshipDetector()

    snapshot = {
        "spot_price": 14510.0,
        "oi_change_ce": 1500,
        "oi_change_pe": 2000,
        "buildup_signal": "LONG_BUILDUP",
        "timestamp_utc": 1614570300,
    }

    obs_list = detector.detect(snapshot, history)
    assert len(obs_list) == 1
    obs = obs_list[0]

    assert obs.observation_type == TYPE_PRICE_OI_RELATION
    # Requirement 1 & 2: Verify raw observations vs derived classifications separation
    assert "raw_observations" in obs.attributes
    assert "derived_classifications" in obs.attributes
    assert obs.attributes["raw_observations"]["spot_price"] == 14510.0
    assert obs.attributes["derived_classifications"]["buildup_signal"] == "LONG_BUILDUP"


def test_pattern_recognition_module_orchestration():
    module = PatternRecognitionModule()
    module.initialize()

    snapshot = {
        "spot_price": 14500.0,
        "atm_strike": 14500.0,
        "pcr_volume": 1.35,
        "total_ce_oi": 50000,
        "total_pe_oi": 60000,
        "oi_change_ce": 1000,
        "oi_change_pe": 1500,
        "max_pain_strike": 14500.0,
        "buildup_signal": "LONG_BUILDUP",
        "timestamp_utc": 1614570300,
    }

    result = module.process_snapshot(snapshot, prior_perceptions={})

    assert result["confidence"] == 0.93
    assert "Highest Call OI" in result["evidence"]
    meta = result["metadata"]
    assert meta["total_observations"] == 5
    assert len(meta["observations"]) == 5


if __name__ == "__main__":
    test_option_walls_detector()
    test_raw_vs_derived_separation()
    test_pattern_recognition_module_orchestration()
    print("\nALL PATTERN ENGINE UNIT TESTS PASSED SUCCESSFULLY!")
