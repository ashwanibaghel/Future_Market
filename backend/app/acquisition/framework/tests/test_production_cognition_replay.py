import os
import tempfile
import pyarrow as pa
import pyarrow.parquet as pq

from app.research_os.feature_store.feature_store import FeatureStore
from app.research_os.replay.replay_config import ReplayConfig
from app.research_os.replay.replay_engine import HistoricalReplayEngine
from app.research_os.replay.replay_registry import ReplayRegistry
from app.research_os.perception.perception_engine import PerceptionEngine
from app.research_os.perception.pattern.pattern_engine import PatternRecognitionModule
from app.research_os.perception.regime.regime_engine import MarketRegimeModule
from app.research_os.perception.situation.situation_engine import SituationAssessmentModule
from app.research_os.strategy.plugins.pcr_divergence_plugin import PCRDivergencePlugin
from app.research_os.strategy.strategy_context import StrategyContext
from app.research_os.decision_lake.decision_lake import DecisionLake
from app.acquisition.sqlite_lake_exporter import export_sqlite_to_canonical_lake


def test_production_real_dataset_cognition_replay():
    """
    Production Validation: Replays REAL exported historical option chain dataset through
    complete 11-stage cognitive loop (Replay -> Pattern -> Regime -> Situation -> Strategy -> Decision Lake).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        store_dir = os.path.join(tmpdir, "feature_store")
        reg_dir = os.path.join(tmpdir, "replay_sessions")
        dec_dir = os.path.join(tmpdir, "decision_lake")

        feature_store = FeatureStore(base_dir=store_dir)
        registry = ReplayRegistry(base_dir=reg_dir)
        decision_lake = DecisionLake(base_dir=dec_dir)
        replay_engine = HistoricalReplayEngine(feature_store=feature_store, registry=registry)

        # Step 1: Export REAL SQLite Option Chain snapshots for NIFTY
        manifest = export_sqlite_to_canonical_lake(symbol="NIFTY")
        assert manifest is not None
        assert manifest.row_count > 0

        # Load exported parquet table and save into FeatureStore
        lake_path = "E:/Future Stock/research_storage/parquet_lake/exchange=NSE_FO/symbol=NIFTY_OPTIONS/year=2026/month=07/option_chain.parquet"
        assert os.path.exists(lake_path)

        pf = pq.ParquetFile(lake_path)
        real_table = pf.read()
        del pf
        feature_store.save_features(real_table, "NIFTY", 2026, 7, "F-v1.0.0")

        # Step 2: Initialize PerceptionEngine with production perception modules
        perception_engine = PerceptionEngine()
        perception_engine.register_module(PatternRecognitionModule())
        perception_engine.register_module(MarketRegimeModule())
        perception_engine.register_module(SituationAssessmentModule())

        # Step 3: Initialize Replay Session for REAL NIFTY dataset
        config = ReplayConfig(symbol="NIFTY", start_date="2026-07-08", end_date="2026-07-08", feature_version="F-v1.0.0")
        session_id = "SESS-REAL-PRODUCTION-NIFTY-001"
        session = replay_engine.create_session(session_id, config)

        strategy = PCRDivergencePlugin()
        strategy.initialize(config={"pcr_bullish_threshold": 1.0, "pcr_bearish_threshold": 1.0})
        strategy.on_session_start({"session_id": session_id})

        decisions_collected = []
        frames_generated = []

        def integrated_listener(event: dict):
            # Pass real snapshot through Perception Engine
            frame = perception_engine.process_snapshot(event, session_id=session_id)
            frames_generated.append(frame)

            context = StrategyContext.from_enriched_event(event)
            perception_engine.enrich_strategy_context(context, frame)

            decision = strategy.on_snapshot(context)
            if decision is not None:
                record = decision_lake.record_decision(decision.to_dict())
                decisions_collected.append(record)

        session.register_listener(integrated_listener)

        # Execute Replay over REAL dataset
        for _ in session.play():
            pass

        # Validation 1: Replayed all REAL snapshots
        assert len(frames_generated) == real_table.num_rows

        # Validation 2: Topological execution sequence preserved
        first_frame = frames_generated[0]
        assert first_frame.executed_modules == ["pattern_recognition", "market_regime", "situation_assessment"]

        # Validation 3: SituationAssessment cognitive artifact generated
        sit_obs = first_frame.get_perception("situation_assessment")
        assert sit_obs is not None
        assert sit_obs["metadata"]["assessment"]["artifact_type"] == "SITUATION_ASSESSMENT"

        # Validation 4: Strategy predictions recorded in Decision Lake
        assert len(decisions_collected) == real_table.num_rows
        lake_records = decision_lake.list_decisions()
        assert len(lake_records) > 0


if __name__ == "__main__":
    test_production_real_dataset_cognition_replay()
    print("\nPRODUCTION REAL DATASET COGNITION REPLAY PASSED SUCCESSFULLY!")
