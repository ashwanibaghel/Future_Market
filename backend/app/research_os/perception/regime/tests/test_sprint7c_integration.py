import os
import tempfile
import pyarrow as pa

from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.replay.replay_config import ReplayConfig
from app.research_os.replay.replay_engine import HistoricalReplayEngine
from app.research_os.replay.replay_registry import ReplayRegistry
from app.research_os.perception.perception_engine import PerceptionEngine
from app.research_os.perception.pattern.pattern_engine import PatternRecognitionModule
from app.research_os.perception.regime.regime_engine import MarketRegimeModule
from app.research_os.strategy.plugins.pcr_divergence_plugin import PCRDivergencePlugin
from app.research_os.strategy.strategy_context import StrategyContext
from app.research_os.decision_lake.decision_lake import DecisionLake
from app.research_os.tests.benchmark_fixtures import generate_benchmark_dataset


def test_sprint7c_full_market_regime_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_dir = os.path.join(tmpdir, "feature_store")
        reg_dir = os.path.join(tmpdir, "replay_sessions")
        dec_dir = os.path.join(tmpdir, "decision_lake")

        feature_store = FeatureStore(base_dir=store_dir)
        registry = ReplayRegistry(base_dir=reg_dir)
        decision_lake = DecisionLake(base_dir=dec_dir)
        replay_engine = HistoricalReplayEngine(feature_store=feature_store, registry=registry)

        # Step 1: Seed Benchmark dataset (10 snapshots)
        benchmark_table = generate_benchmark_dataset(num_snapshots=10)
        feature_store.save_features(benchmark_table, "NIFTY", 2021, 3, "F-v1.0.0")

        # Step 2: Initialize PerceptionEngine with PatternRecognitionModule (7B) & MarketRegimeModule (7C)
        # Register in REVERSE order to test Kahn's Topological Sorting!
        perception_engine = PerceptionEngine()
        regime_module = MarketRegimeModule()
        pattern_module = PatternRecognitionModule()

        perception_engine.register_module(regime_module)
        perception_engine.register_module(pattern_module)

        # Verify Topological Resolution Order: PatternRecognition MUST execute before MarketRegime
        sorted_names = [m.module_name for m in perception_engine._sorted_modules]
        assert sorted_names == ["pattern_recognition", "market_regime"]

        # Step 3: Initialize Replay Session & Strategy Plugin
        config = ReplayConfig(symbol="NIFTY", start_date="2021-03-01", end_date="2021-03-31", feature_version="F-v1.0.0")
        session_id = "SESS-REGIME-E2E-001"
        session = replay_engine.create_session(session_id, config)

        strategy = PCRDivergencePlugin()
        strategy.initialize()
        strategy.on_session_start({"session_id": session_id})

        decisions_collected = []
        frames_generated = []

        def integrated_listener(event: dict):
            frame = perception_engine.process_snapshot(event, session_id=session_id)
            frames_generated.append(frame)

            context = StrategyContext.from_enriched_event(event)
            perception_engine.enrich_strategy_context(context, frame)

            decision = strategy.on_snapshot(context)
            if decision is not None:
                record = decision_lake.record_decision(decision.to_dict())
                decisions_collected.append(record)

        session.register_listener(integrated_listener)

        # Execute Replay
        for _ in session.play():
            pass

        assert len(frames_generated) == 10
        first_frame = frames_generated[0]

        # Verify Topological Execution Sequence in PerceptionFrame
        assert first_frame.executed_modules == ["pattern_recognition", "market_regime"]

        # Verify Market Regime Perception Output
        regime_perception = first_frame.get_perception("market_regime")
        assert regime_perception is not None
        assert regime_perception["confidence"] == 0.91
        meta = regime_perception["metadata"]
        assert meta["total_regime_observations"] == 2
        assert "TREND_STRENGTH" in meta["regime_states"]
        assert "VOLATILITY_STATE" in meta["regime_states"]

        # Verify Strategy Decision Lake persistence
        assert len(decisions_collected) > 0
        lake_records = decision_lake.list_decisions()
        assert len(lake_records) == len(decisions_collected)


if __name__ == "__main__":
    test_sprint7c_full_market_regime_pipeline()
    print("\nSPRINT 7C INTEGRATION TEST PASSED SUCCESSFULLY!")
