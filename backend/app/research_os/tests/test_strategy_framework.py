from app.research_os.strategy.strategy_manifest import StrategyManifest
from app.research_os.strategy.decision_event import DecisionEvent
from app.research_os.strategy.strategy_context import StrategyContext
from app.research_os.strategy.strategy_registry import StrategyRegistry
from app.research_os.strategy.plugins.pcr_divergence_plugin import PCRDivergencePlugin


def test_strategy_manifest_and_frozen_decision_event():
    plugin = PCRDivergencePlugin()
    manifest = plugin.manifest

    assert manifest.strategy_name == "PCRDivergenceStrategy"
    assert manifest.strategy_version == "ST-v1.0.0"
    assert "pcr_volume" in manifest.required_features

    # Create immutable DecisionEvent
    event = DecisionEvent(
        decision_id="DEC-TEST-001",
        strategy_name=manifest.strategy_name,
        strategy_version=manifest.strategy_version,
        session_id="SESS-001",
        timestamp="2021-03-01T09:15:00+05:30",
        timestamp_utc=1614570300,
        symbol="NIFTY",
        spot_price=14500.0,
        feature_version="F-v1.0.0",
        replay_version="R-v1.0.0",
        signal="BULLISH",
        confidence=0.88,
        reasoning="Test Reasoning",
    )

    assert event.signal == "BULLISH"

    # Requirement 5: Verify Frozen Immutability
    frozen_passed = False
    try:
        event.signal = "BEARISH"
    except Exception:
        frozen_passed = True
    assert frozen_passed, "DecisionEvent must be frozen immutable!"


def test_strategy_registry_and_validation():
    StrategyRegistry.register_strategy(PCRDivergencePlugin)
    listed = StrategyRegistry.list_strategies()
    assert len(listed) >= 1

    plugin = PCRDivergencePlugin()

    # Valid compatibility check
    valid = StrategyRegistry.validate_strategy_compatibility(
        plugin,
        available_features=["pcr_volume", "buildup_signal", "spot_price"],
        feature_version="F-v1.0.0",
    )
    assert valid

    # Incompatible feature version check
    compat_failed = False
    try:
        StrategyRegistry.validate_strategy_compatibility(
            plugin,
            available_features=["pcr_volume", "buildup_signal", "spot_price"],
            feature_version="F-v0.9.0",
        )
    except ValueError:
        compat_failed = True
    assert compat_failed, "Should reject lower feature version!"


def test_pcr_divergence_plugin_execution():
    plugin = PCRDivergencePlugin()
    plugin.on_session_start({"session_id": "SESS-001"})

    # Bullish Snapshot Context
    ctx_dict = {
        "session_id": "SESS-001",
        "symbol": "NIFTY",
        "replay_timestamp": "2021-03-01T09:15:00+05:30",
        "timestamp_utc": 1614570300,
        "spot_price": 14500.0,
        "pcr_volume": 1.35,
        "buildup_signal": "LONG_BUILDUP",
        "feature_version": "F-v1.0.0",
        "replay_version": "R-v1.0.0",
    }
    context = StrategyContext.from_enriched_event(ctx_dict)
    decision = plugin.on_snapshot(context)

    assert decision is not None
    assert decision.signal == "BULLISH"
    assert decision.confidence == 0.88


if __name__ == "__main__":
    test_strategy_manifest_and_frozen_decision_event()
    test_strategy_registry_and_validation()
    test_pcr_divergence_plugin_execution()
    print("\nALL STRATEGY FRAMEWORK TESTS PASSED SUCCESSFULLY!")
