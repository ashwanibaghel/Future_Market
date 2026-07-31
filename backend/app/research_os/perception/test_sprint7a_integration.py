import os
import tempfile
import pyarrow as pa

from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.replay.replay_config import ReplayConfig
from app.research_os.replay.replay_engine import HistoricalReplayEngine
from app.research_os.replay.replay_registry import ReplayRegistry
from app.research_os.perception.base_perception import BasePerceptionModule
from app.research_os.perception.perception_engine import PerceptionEngine
from app.research_os.strategy.plugins.pcr_divergence_plugin import PCRDivergencePlugin
from app.research_os.strategy.strategy_context import StrategyContext
from app.research_os.decision_lake.decision_lake import DecisionLake
from app.research_os.tests.benchmark_fixtures import generate_benchmark_dataset


class ObservationPatternModule(BasePerceptionModule):
    """Sample Perception Module generating observation outputs."""
    @property
    def module_name(self) -> str:
        return "sample_pattern_observer"

    @property
    def module_version(self) -> str:
        return "1.0.0"

    def process_snapshot(self, snapshot: dict, prior_perceptions: dict) -> dict:
        pcr_vol = snapshot.get("pcr_volume", 1.0)
        return {
            "confidence": 0.90,
            "evidence": f"Perceived PCR Volume level at {pcr_vol}",
            "metadata": {"perceived_pcr_volume": pcr_vol},
        }


def test_sprint7a_end_to_end_perception_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        store_dir = os.path.join(tmpdir, "feature_store")
        reg_dir = os.path.join(tmpdir, "replay_sessions")
        dec_dir = os.path.join(tmpdir, "decision_lake")

        feature_store = FeatureStore(base_dir=store_dir)
        registry = ReplayRegistry(base_dir=reg_dir)
        decision_lake = DecisionLake(base_dir=dec_dir)
        replay_engine = HistoricalReplayEngine(feature_store=feature_store, registry=registry)

        # Seed Benchmark dataset
        benchmark_table = generate_benchmark_dataset(num_snapshots=10)
        feature_store.save_features(benchmark_table, "NIFTY", 2021, 3, "F-v1.0.0")

        # Initialize Perception Engine with Observation Module
        perception_engine = PerceptionEngine()
        perception_engine.register_module(ObservationPatternModule())

        # Initialize Replay Session
        config = ReplayConfig(symbol="NIFTY", start_date="2021-03-01", end_date="2021-03-31", feature_version="F-v1.0.0")
        session_id = "SESS-PERCEPTION-E2E-001"
        session = replay_engine.create_session(session_id, config)

        strategy = PCRDivergencePlugin()
        strategy.initialize()
        strategy.on_session_start({"session_id": session_id})

        decisions_collected = []
        frames_generated = []

        def integrated_listener(event: dict):
            # Step 1: Synthesize PerceptionFrame via PerceptionEngine
            frame = perception_engine.process_snapshot(event, session_id=session_id)
            frames_generated.append(frame)

            # Step 2: Bind PerceptionFrame to StrategyContext
            context = StrategyContext.from_enriched_event(event)
            perception_engine.enrich_strategy_context(context, frame)

            # Step 3: Evaluate Strategy Prediction over Perception-Enriched Context
            decision = strategy.on_snapshot(context)
            if decision is not None:
                record = decision_lake.record_decision(decision.to_dict())
                decisions_collected.append(record)

        session.register_listener(integrated_listener)

        # Execute Replay
        for _ in session.play():
            pass

        assert len(frames_generated) == 10
        assert frames_generated[0].perception_version == "P-v1.0.0"
        assert "sample_pattern_observer" in frames_generated[0].executed_modules

        # Verify Strategy Decision Lake persistence
        assert len(decisions_collected) > 0
        lake_records = decision_lake.list_decisions()
        assert len(lake_records) == len(decisions_collected)


if __name__ == "__main__":
    test_sprint7a_end_to_end_perception_pipeline()
    print("\nSPRINT 7A INTEGRATION TEST PASSED SUCCESSFULLY!")
